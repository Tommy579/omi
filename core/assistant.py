"""
Assistant principal - OMI (Open Mind Interface)
Orchestre la capture d'écran, le micro, et les appels à l'API Gemini (gratuit)
"""

import time
import threading
from datetime import datetime
from collections import deque
import os
import cv2
import numpy as np

from google import genai
import mss
from PIL import Image

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    SCREEN_CAPTURE_INTERVAL,
    ENABLE_CAMERA,
    CAMERA_CAPTURE_INTERVAL,
    SYSTEM_PROMPT,
    MAX_MEMORY_ITEMS,
    ENABLE_MICROPHONE,
    AUDIO_SEGMENT_DURATION,
    ALLOW_AUTONOMOUS_UI_INTERACTION,
    SCREEN_CAPTURE_SIZE,
    CAMERA_CAPTURE_SIZE,
    SCREEN_CHANGE_THRESHOLD,
    MAX_UNCHANGED_FRAMES,
    MAX_CHAT_TURNS,
    UI_TREE_MIN_WORDS,
    READABLE_EXTENSIONS,
)

from core.tools import TOOLS_LIST
from core.database import add_transcript, query_transcripts


class Assistant:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        
        # On définit un prompt système plus complet pour le côté agent
        enhanced_prompt = SYSTEM_PROMPT + "\n\n"
        
        if ALLOW_AUTONOMOUS_UI_INTERACTION:
            enhanced_prompt += """
TU AS UN ACCÈS INTÉGRAL À CET ORDINATEUR ET TU ES UN AGENT AUTONOME.
Ton but est d'exécuter les demandes de l'utilisateur de manière RAPIDE et INVISIBLE.

### Stratégie de Rapidité (Priorité 1) :
- **Ne pas utiliser la Vision par défaut** : L'analyse d'image est lente. Utilise `get_ui_tree()` pour lire instantanément le texte et les boutons.
- **Actions d'Arrière-plan** : Utilise `background_interact` pour cliquer ou taper sans bouger la souris physique.
- **Fallback** : Si l'arrière-plan échoue, utilise alors la Vision (`[UPDATE_SCREEN]`) et `mouse_click` en dernier recours.
"""
        else:
            enhanced_prompt += """
TU ES UN ASSISTANT OBSERVATEUR. Ton rôle est d'aider l'utilisateur par des suggestions.
### RÈGLE CRITIQUE :
- INTERDICTION d'utiliser la souris ou le clavier (`mouse_click`, `type_text`, `press_key`, `background_interact`) SAUF si l'utilisateur en fait la demande explicite.
- Ne tente pas d'interagir avec l'interface graphique de ton propre chef.
"""

        enhanced_prompt += """
### Style de réponse (CRITIQUE) :
- Parle avec des vraies phrases, simples et naturelles.
- Reste très court (10-15 mots maximum par réponse).
- Pas de blabla inutile, va droit au but.

### Capacités OS :
- **Recherche de fichiers** : Utilise `search_files(query)` qui est instantané grâce à l'index Windows. Ne parcours pas le disque manuellement.
- **iTunes** : Utilise TOUJOURS `control_itunes(command)` pour la musique.
- **Monitoring** : Utilise `get_system_stats()` pour diagnostiquer des lenteurs (CPU/RAM) et `get_windows_event_logs()` pour les erreurs système.
- **Processus** : Utilise `list_processes()` pour voir ce qui tourne et `get_process_details(pid)` pour analyser un process suspect.
- **Fichiers** : Tu peux `read_file` ET `write_file`. Tu es capable de corriger du code ou de créer des scripts.
- **Presse-papier** : Utilise `get_clipboard()` pour voir ce que l'utilisateur a copié.
- **Notifications** : Utilise `send_notification(title, message)` pour informer l'utilisateur.

Tu es invisible, rapide, et efficace.
"""
        
        self.chat_session = self.client.chats.create(
            model=GEMINI_MODEL,
            config={"system_instruction": enhanced_prompt, "tools": TOOLS_LIST}
            
        )
        self._enhanced_prompt = enhanced_prompt  # Gardé pour le trim de session
        self._last_screen_arr = None
        self._unchanged_count = 0

        self._camera = None
        if ENABLE_CAMERA:
            try:
                self._camera = cv2.VideoCapture(0)
                if not self._camera.isOpened():
                    self._camera = None
                    print("[Caméra] Aucun périphérique trouvé.")
            except Exception as e:
                print(f"[Caméra] Erreur init : {e}")

        # On utilise une session de chat pour le function calling automatique et le maintien du contexte
        # removed
        self.memory = deque(maxlen=MAX_MEMORY_ITEMS)
        self.latest_suggestion = "Démarrage en cours..."
        self.is_running = False
        self.paused = False
        self.on_suggestion_callback = None
        self.on_transcript_callback = None
        self._lock = threading.Lock()
        self.last_camera_time = 0

    # ─────────────────────────────────────────────
    # Contrôles
    # ─────────────────────────────────────────────

    def start(self):
        self.is_running = True
        threading.Thread(target=self._vision_loop, daemon=True).start()
        if ENABLE_MICROPHONE:
            try:
                threading.Thread(target=self._mic_loop, daemon=True).start()
            except Exception as e:
                print(f"[Micro] Désactivé : {e}")

    def stop(self):
        self.is_running = False
        if self._camera is not None:
            self._camera.release()
            self._camera = None

    def toggle_pause(self):
        self.paused = not self.paused
        status = "en pause" if self.paused else "actif"
        print(f"[Assistant] État : {status}")
        return self.paused

    # ─────────────────────────────────────────────
    # Capture Vision (Écran + Caméra) et Analyse
    # ─────────────────────────────────────────────

    def _get_screen_text(self) -> str | None:
        """Extrait le texte de la fenêtre active via UI Automation (local, gratuit, instantané).
        
        Retourne le texte si l'écran est suffisamment textuel (> UI_TREE_MIN_WORDS mots),
        None sinon (dans ce cas on envoie l'image à la place).
        """
        try:
            from pywinauto import Desktop
            app = Desktop(backend="uia").active_window()
            if app is None:
                return None

            elements = []
            for child in app.descendants():
                try:
                    name = child.window_text()
                    if name and len(name.strip()) > 2:
                        elements.append(name.strip())
                except Exception:
                    continue

            if not elements:
                return None

            text = "\n".join(elements[:200])  # Limite à 200 éléments pour éviter le flood
            word_count = len(text.split())

            if word_count < UI_TREE_MIN_WORDS:
                return None  # Pas assez de texte → mode image

            return text
        except Exception as e:
            print(f"[UI Tree] Erreur extraction texte : {e}")
            return None

    def _get_active_document(self) -> tuple[str, str] | tuple[None, None]:
        """Détecte si la fenêtre active affiche un fichier lisible et retourne (chemin, contenu).
        
        Cherche le nom de fichier dans le titre de la fenêtre, le localise sur le disque
        via search_files(), puis lit son contenu complet avec read_file().
        Retourne (None, None) si aucun fichier détectable ou lisible.
        """
        try:
            import re
            import pygetwindow as gw
            from core.tools import search_files, read_file

            active = gw.getActiveWindow()
            if not active or not active.title:
                return None, None

            title = active.title

            # Cherche un nom de fichier avec extension dans le titre de la fenêtre
            # Couvre : "main.py — VS Code", "rapport.pdf - Adobe", "README.md · GitHub", etc.
            pattern = r'([\w\-. ]+\.(?:' + '|'.join(e.lstrip('.') for e in READABLE_EXTENSIONS) + r'))'
            match = re.search(pattern, title, re.IGNORECASE)
            if not match:
                return None, None

            filename = match.group(1).strip()

            # Localiser le fichier sur le disque
            result = search_files(filename)
            matches = result.get("matches", [])
            if not matches:
                return None, None

            file_path = matches[0]

            # Lire le contenu du fichier
            content_result = read_file(file_path)
            if "error" in content_result:
                return None, None

            content = content_result.get("content", "")
            if not content or len(content.strip()) < 50:
                return None, None

            return file_path, content

        except Exception as e:
            print(f"[Document] Erreur détection fichier actif : {e}")
            return None, None

    def _screen_changed(self, img: Image.Image) -> bool:
        """Retourne True si l'écran a changé suffisamment pour justifier un appel API."""
        import numpy as np
        small = img.resize((160, 90)).convert("L")
        arr = np.array(small, dtype=np.float32) / 255.0
        if self._last_screen_arr is None:
            self._last_screen_arr = arr
            return True
        diff = np.abs(arr - self._last_screen_arr).mean()
        self._last_screen_arr = arr
        if diff < SCREEN_CHANGE_THRESHOLD:
            self._unchanged_count += 1
            return False
        self._unchanged_count = 0
        return True

    def _vision_loop(self):
        while self.is_running:
            try:
                if not self.paused:
                    screen_img = self._capture_screen()
                    changed = self._screen_changed(screen_img)
                    # On skip si l'écran n'a pas changé, sauf si ça fait trop longtemps
                    if not changed and self._unchanged_count < MAX_UNCHANGED_FRAMES:
                        time.sleep(SCREEN_CAPTURE_INTERVAL)
                        continue
                    images = [screen_img]
                    now = time.time()
                    if ENABLE_CAMERA and (now - self.last_camera_time) >= CAMERA_CAPTURE_INTERVAL:
                        camera_img = self._capture_camera()
                        if camera_img:
                            images.append(camera_img)
                            self.last_camera_time = now
                    self._analyze_vision(images)
            except Exception as e:
                print(f"[Vision] Erreur : {e}")
            time.sleep(SCREEN_CAPTURE_INTERVAL)

    def _capture_screen(self):
        """Capture l'écran principal et retourne un objet PIL Image redimensionné."""
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img.thumbnail(SCREEN_CAPTURE_SIZE, Image.LANCZOS)
        return img

    def _capture_camera(self):
        """Capture une image depuis la webcam (instance persistante, pas de fuite mémoire)."""
        try:
            if self._camera is None or not self._camera.isOpened():
                return None
            ret, frame = self._camera.read()
            if not ret:
                return None
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail(CAMERA_CAPTURE_SIZE, Image.LANCZOS)
            return img
        except Exception as e:
            print(f"[Caméra] Erreur de capture : {e}")
            return None

    def _analyze_vision(self, images):
        """Analyse la situation en choisissant le mode le plus économique :
        
        Priorité 1 — Document ouvert détecté → lire le fichier complet (texte, 0 token image)
        Priorité 2 — Écran textuel → envoyer le texte UI Tree (texte, 0 token image)
        Priorité 3 — Écran visuel → envoyer l'image (tokens image normaux)
        """
        self._trim_chat_history_if_needed()

        try:
            # --- Priorité 1 : document lisible ouvert ---
            file_path, doc_content = self._get_active_document()
            if file_path and doc_content:
                # Tronquer si trop long (limite raisonnable pour éviter de saturer le contexte)
                max_chars = 12000
                truncated = ""
                if len(doc_content) > max_chars:
                    doc_content = doc_content[:max_chars]
                    truncated = f"\n[... document tronqué à {max_chars} caractères ...]"

                prompt = (
                    f"Je travaille sur le fichier `{file_path}`.\n"
                    f"Voici son contenu complet :\n\n"
                    f"```\n{doc_content}{truncated}\n```\n\n"
                    f"Analyse ce contenu. Si tu vois des erreurs, des améliorations possibles "
                    f"ou quelque chose d'important, dis-le moi brièvement."
                )
                mode = "document"

            else:
                # --- Priorité 2 : écran textuel via UI Tree ---
                screen_text = self._get_screen_text()

                if screen_text:
                    prompt = (
                        f"Voici le contenu textuel de mon écran (extrait via l'arbre UI) :\n\n"
                        f"{screen_text}\n\n"
                        f"Analyse la situation. Si tu remarques des mauvaises habitudes "
                        f"ou une opportunité d'aider, fais une suggestion courte."
                    )
                    mode = "texte"

                else:
                    # --- Priorité 3 : écran visuel, envoi de l'image ---
                    prompt = (
                        "Voici mon écran actuel"
                        + (" et une vue de ma caméra." if len(images) > 1 else ".")
                        + " Analyse la situation. Si tu remarques des mauvaises habitudes "
                        + "(se ronger les ongles, posture, distraction) ou une opportunité "
                        + "d'aider, fais une suggestion courte."
                    )
                    mode = "image"

            # --- Envoi à Gemini ---
            with self._lock:
                if mode == "image":
                    response = self.chat_session.send_message([prompt] + images)
                else:
                    response = self.chat_session.send_message(prompt)

            suggestion = response.text.strip()
            print(f"[Vision] Mode : {mode} | Réponse : {suggestion[:60]}...")

            if "Rien de particulier" in suggestion or len(suggestion) < 5:
                return

        except Exception as e:
            suggestion = f"Erreur API : {e}"
            print(f"[Gemini Vision] Erreur : {e}")

        self._add_to_memory("vision", suggestion)
        self._update_suggestion(suggestion)

    def _trim_chat_history_if_needed(self):
        """Recrée la session de chat si elle devient trop longue pour limiter les tokens."""
        try:
            with self._lock:
                history = self.chat_session.get_history()
            if len(history) > MAX_CHAT_TURNS * 2:
                recent = history[-(MAX_CHAT_TURNS * 2):]
                with self._lock:
                    self.chat_session = self.client.chats.create(
                        model=GEMINI_MODEL,
                        config={"system_instruction": self._enhanced_prompt, "tools": TOOLS_LIST},
                        history=recent
                    )
                print(f"[Chat] Historique taillé à {MAX_CHAT_TURNS} tours.")
        except Exception as e:
            print(f"[Chat] Erreur trim historique : {e}")

    # ─────────────────────────────────────────────
    # Microphone
    # ─────────────────────────────────────────────

    def _mic_loop(self):
        import sounddevice as sd
        import numpy as np
        try:
            import whisper
            model = whisper.load_model("tiny")
        except ImportError:
            print("[Micro] whisper non installé, micro désactivé")
            return

        sample_rate = 16000
        loopback_device_index = None

        # --- Détection du loopback WASAPI (son interne du PC) ---
        try:
            import pyaudiowpatch as pyaudio
            p = pyaudio.PyAudio()
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if (dev["name"] == default_speakers["name"]
                        and dev["hostApi"] == wasapi_info["index"]
                        and dev.get("isLoopbackDevice")):
                    loopback_device_index = i
                    print(f"[Audio] Loopback WASAPI trouvé : {dev['name']}")
                    break
            p.terminate()
        except Exception as e:
            print(f"[Audio] pyaudiowpatch non disponible, loopback désactivé : {e}")
            # Fallback : chercher un device loopback via sounddevice (Stereo Mix, etc.)
            keywords = ["mixage", "stereo mix", "loopback", "what u hear", "voicemeeter output", "cable output"]
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                try:
                    if dev['max_input_channels'] > 0 and any(k in dev['name'].lower() for k in keywords):
                        loopback_device_index = i
                        print(f"[Audio] Loopback fallback détecté : {dev['name']}")
                        break
                except Exception:
                    pass

        print(f"[Audio] Micro système : {'index ' + str(loopback_device_index) if loopback_device_index is not None else 'non disponible'}")

        while self.is_running:
            try:
                # --- Capture micro physique (voix utilisateur) ---
                try:
                    mic_audio = sd.rec(
                        int(AUDIO_SEGMENT_DURATION * sample_rate),
                        samplerate=sample_rate, channels=1, dtype="float32",
                        device=None  # micro par défaut
                    )
                    sd.wait()
                    mic_data = mic_audio.flatten()

                    if np.abs(mic_data).mean() > 0.005:  # silence detection basique
                        result = model.transcribe(mic_data, language="fr", fp16=False)
                        text = result["text"].strip()
                        if len(text) > 10:
                            add_transcript("User", text)
                            if self.on_transcript_callback:
                                self.on_transcript_callback(text)
                except Exception as e:
                    print(f"[Micro] Erreur capture voix : {e}")

                # --- Capture audio système (loopback) — stocké sans analyse automatique ---
                if loopback_device_index is not None:
                    try:
                        import pyaudiowpatch as pyaudio
                        p = pyaudio.PyAudio()
                        dev_info = p.get_device_info_by_index(loopback_device_index)
                        channels = int(dev_info["maxInputChannels"])
                        dev_sample_rate = int(dev_info["defaultSampleRate"])
                        stream = p.open(
                            format=pyaudio.paInt16,
                            channels=channels,
                            rate=dev_sample_rate,
                            input=True,
                            input_device_index=loopback_device_index,
                            frames_per_buffer=1024
                        )
                        frames = []
                        n_frames = int(dev_sample_rate / 1024 * AUDIO_SEGMENT_DURATION)
                        for _ in range(n_frames):
                            frames.append(stream.read(1024, exception_on_overflow=False))
                        stream.stop_stream()
                        stream.close()
                        p.terminate()

                        raw = b"".join(frames)
                        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                        if channels > 1:
                            arr = arr.reshape(-1, channels).mean(axis=1)

                        if np.abs(arr).mean() > 0.005:
                            result = model.transcribe(arr, language="fr", fp16=False)
                            sys_text = result["text"].strip()
                            if len(sys_text) > 10:
                                # Stocké avec speaker "System_Audio", accessible sur demande via query_transcript_history
                                add_transcript("System_Audio", sys_text)
                                print(f"[Audio Système] Transcrit : {sys_text[:60]}...")
                    except Exception as e:
                        print(f"[Loopback] Erreur capture : {e}")

            except Exception as e:
                print(f"[Micro] Erreur générale : {e}")
                time.sleep(5)


    def _analyze_audio(self, transcript):
        prompt = f'J\'ai entendu ceci : "{transcript}". Réagis si c\'est important ou utile.'
        try:
            with self._lock:
                response = self.chat_session.send_message(prompt)
            suggestion = response.text.strip()
            add_transcript("System", f"Suggestion: {suggestion}")
            self._add_to_memory("audio", suggestion)
            self._update_suggestion(f"🎤 {suggestion}")
        except Exception as e:
            print(f"[Gemini Audio] Erreur : {e}")

    # ─────────────────────────────────────────────
    # Chat interactif (depuis le popup)
    # ─────────────────────────────────────────────

    def chat(self, user_message: str, is_system: bool = False, status_callback=None) -> str:
        try:
            if status_callback: status_callback("Capture de l'écran...")
            
            if not is_system:
                recent = query_transcripts(limit=5)
                context = "\n".join([f"[{r[0]}] {r[1]}: {r[2]}" for r in reversed(recent)])
                full_prompt = f"Historique récent des transcriptions :\n{context}\n\nUtilisateur : {user_message}"
            else:
                full_prompt = f"Système : {user_message}"
            
            # Prendre un screenshot actuel
            screen_img = self._capture_screen()
            
            if status_callback: status_callback("Analyse Gemini en cours...")
            
            with self._lock:
                response = self.chat_session.send_message([full_prompt, screen_img])
            text_response = response.text.strip()
            
            if "[UPDATE_SCREEN]" in text_response:
                clean_text = text_response.replace("[UPDATE_SCREEN]", "").strip()
                if clean_text and self.on_suggestion_callback:
                    # Permet d'afficher à l'utilisateur l'étape en cours
                    self._update_suggestion(f"⚙️ {clean_text}")
                
                # Boucle automatique pour donner le nouvel écran à l'agent
                if status_callback: status_callback(f"Action : {clean_text}...")
                next_step = self.chat("Voici l'écran mis à jour. Continue ton action.", is_system=True, status_callback=status_callback)
                return f"{clean_text}\n{next_step}".strip()
                
            return text_response
        except Exception as e:
            return f"Erreur API : {e}"

    # ─────────────────────────────────────────────
    # Mémoire et contexte
    # ─────────────────────────────────────────────

    def _add_to_memory(self, source_type: str, content: str):
        with self._lock:
            self.memory.append({
                "type": source_type,
                "content": content,
                "time": datetime.now().strftime("%H:%M"),
            })

    def _update_suggestion(self, text: str):
        with self._lock:
            self.latest_suggestion = text
        if self.on_suggestion_callback:
            self.on_suggestion_callback(text)

    def get_latest_suggestion(self) -> str:
        return self.latest_suggestion

    def get_memory(self) -> list:
        return list(self.memory)
