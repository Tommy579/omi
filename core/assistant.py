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
from core.profile import get_profile_summary


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

        # Charger et injecter le profil existant dans le prompt initial
        initial_profile = get_profile_summary()
        if initial_profile:
            enhanced_prompt += f"\n\n{initial_profile}"

        enhanced_prompt += """

### MÉMOIRE LONG TERME (CRITIQUE) :
Tu avez accès à un profil persistant de l'utilisateur via les outils `get_user_profile` et `update_user_profile`.
Ce profil survit aux redémarrages — c'est ta mémoire long terme.

**Quand mettre à jour le profil :**
- Tu apprends le prénom de l'utilisateur → `update_user_profile(section='identity', key='name', value='Prénom')`
- Tu vois qu'il utilise un langage de programmation → `update_user_profile(section='work', key='tech_stack', items=[...])`
- Tu observes une mauvaise habitude récurrente → `update_user_profile(section='habits', key='bad_habits', items=[...])`
- Tu remarques un pattern de travail → `update_user_profile(section='schedule', key='most_productive_hours', items=[...])`
- Tu veux noter une observation importante → `update_user_profile(section='notes', value='Observation...')`

**Règles :**
- Ne mets à jour que ce que tu as observé directement, pas ce que tu supposes.
- Pour les listes (tech_stack, bad_habits, etc.), utilise toujours `items` avec la liste complète à jour.
- Pour les notes et les champs simples (nom), utilise `value`.
- Ne demande pas confirmation pour les mises à jour mineures (stack, apps fréquentes).
- Consulte le profil avec `get_user_profile()` si l'utilisateur te pose une question sur lui-même."""
        
        self.chat_session = self.client.chats.create(
            model=GEMINI_MODEL,
            config={"system_instruction": enhanced_prompt, "tools": TOOLS_LIST}
            
        )
        self._enhanced_prompt = enhanced_prompt  # Gardé pour le trim de session
        self._last_screen_arr = None
        self._unchanged_count = 0
        self._doc_cache: dict = {"title": None, "path": None, "content": None}

        self._camera = None
        if ENABLE_CAMERA:
            try:
                self._camera = cv2.VideoCapture(0)
                if not self._camera.isOpened():
                    self._camera = None
                    print("[Caméra] Aucun périphérique trouvé.")
            except Exception as e:
                print(f"[Caméra] Erreur init : {e}")

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

    def _get_screen_text(self, active_window=None) -> str | None:
        """Extrait le texte de la fenêtre active via UI Automation (local, gratuit, instantané).
        
        active_window : objet pywinauto déjà récupéré (optionnel, pour éviter un double appel).
        Retourne None si l'écran est trop peu textuel (< UI_TREE_MIN_WORDS mots).
        """
        try:
            from pywinauto import Desktop
            app = active_window or Desktop(backend="uia").active_window()
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

            text = "\n".join(elements[:200])
            if len(text.split()) < UI_TREE_MIN_WORDS:
                return None

            return text
        except Exception as e:
            print(f"[UI Tree] Erreur extraction texte : {e}")
            return None

    def _get_active_document(self) -> tuple[str, str] | tuple[None, None]:
        """Détecte si la fenêtre active affiche un fichier lisible et retourne (chemin, contenu).
        
        - Ignore la fenêtre OMI elle-même
        - Met en cache le résultat pour éviter un appel search_files à chaque cycle
        - Retourne (None, None) si aucun fichier détectable ou lisible
        """
        try:
            import re
            import pygetwindow as gw
            from core.tools import search_files, read_file

            active = gw.getActiveWindow()
            if not active or not active.title:
                return None, None

            title = active.title

            # Ignorer la fenêtre OMI pour éviter l'auto-analyse
            if title.strip().upper() in ("OMI", "OMIASSISTANT"):
                return None, None

            # Cache : si le titre de la fenêtre n'a pas changé, on réutilise le résultat précédent
            if title == self._doc_cache.get("title"):
                cached_path = self._doc_cache.get("path")
                cached_content = self._doc_cache.get("content")
                if cached_path and cached_content:
                    return cached_path, cached_content
                return None, None

            # Nouveau titre : vider le cache et recalculer
            self._doc_cache = {"title": title, "path": None, "content": None}

            pattern = r'([\w\-. ]+\.(?:' + '|'.join(e.lstrip('.') for e in READABLE_EXTENSIONS) + r'))'
            match = re.search(pattern, title, re.IGNORECASE)
            if not match:
                return None, None

            filename = match.group(1).strip()
            result = search_files(filename)
            matches = result.get("matches", [])
            if not matches:
                return None, None

            file_path = matches[0]
            content_result = read_file(file_path)
            if "error" in content_result:
                return None, None

            content = content_result.get("content", "")
            if not content or len(content.strip()) < 50:
                return None, None

            # Mettre en cache
            self._doc_cache["path"] = file_path
            self._doc_cache["content"] = content

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

        # Résumé du profil pour personnaliser les suggestions
        profile_ctx = get_profile_summary()

        # Récupérer la fenêtre active une seule fois pour les deux méthodes
        try:
            from pywinauto import Desktop
            _active_win = Desktop(backend="uia").active_window()
        except Exception:
            _active_win = None

        # --- Priorité 1 : document lisible ouvert ---
        file_path, doc_content = self._get_active_document()

        try:
            if file_path and doc_content:
                # Tronquer si trop long (limite raisonnable pour éviter de saturer le contexte)
                max_chars = 12000
                truncated = ""
                if len(doc_content) > max_chars:
                    doc_content = doc_content[:max_chars]
                    truncated = f"\n[... document tronqué à {max_chars} caractères ...]"

                prompt = (
                    f"{profile_ctx}\n\n" if profile_ctx else ""
                ) + (
                    f"Je travaille sur le fichier `{file_path}`.\n"
                    f"Voici son contenu complet :\n\n"
                    f"```\n{doc_content}{truncated}\n```\n\n"
                    f"Analyse ce contenu. Si tu vois des erreurs, des améliorations possibles "
                    f"ou quelque chose d'important, dis-le moi brièvement."
                )
                mode = "document"

            else:
                # --- Priorité 2 : écran textuel via UI Tree ---
                screen_text = self._get_screen_text(active_window=_active_win)

                if screen_text:
                    prompt = (
                        f"{profile_ctx}\n\n" if profile_ctx else ""
                    ) + (
                        f"Voici le contenu textuel de mon écran (extrait via l'arbre UI) :\n\n"
                        f"{screen_text}\n\n"
                        f"Analyse la situation. Si tu remarques des mauvaises habitudes "
                        f"ou une opportunité d'aider, fais une suggestion courte."
                    )
                    mode = "texte"

                else:
                    # --- Priorité 3 : écran visuel, envoi de l'image ---
                    prompt = (
                        f"{profile_ctx}\n\n" if profile_ctx else ""
                    ) + (
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
        try:
            with self._lock:
                history = self.chat_session.get_history()
            if len(history) <= MAX_CHAT_TURNS * 2:
                return

            recent = history[-(MAX_CHAT_TURNS * 2):]

            # Avancer jusqu'à un tour "user" propre (pas une function_response)
            start = 0
            for i, turn in enumerate(recent):
                if turn.role == "user":
                    # Vérifier qu'aucune part n'est une function_response
                    parts = turn.parts if hasattr(turn, "parts") else []
                    is_func_response = any(
                        hasattr(p, "function_response") and p.function_response
                        for p in parts
                    )
                    if not is_func_response:
                        start = i
                        break

            recent = recent[start:]

            profile_summary = get_profile_summary()
            prompt_with_profile = self._enhanced_prompt
            if profile_summary:
                prompt_with_profile = self._enhanced_prompt + f"\n\n{profile_summary}"

            with self._lock:
                self.chat_session = self.client.chats.create(
                    model=GEMINI_MODEL,
                    config={"system_instruction": prompt_with_profile, "tools": TOOLS_LIST},
                    history=recent
                )
            print(f"[Chat] Historique taillé à {len(recent)} tours. Profil injecté.")
        except Exception as e:
            print(f"[Chat] Erreur trim historique : {e}")
            # En dernier recours, repartir d'une session vide
            with self._lock:
                self.chat_session = self.client.chats.create(
                    model=GEMINI_MODEL,
                    config={"system_instruction": self._enhanced_prompt, "tools": TOOLS_LIST}
                )

    # ─────────────────────────────────────────────
    # Microphone
    # ─────────────────────────────────────────────

    def _mic_loop(self):
        import sounddevice as sd
        import numpy as np
        try:
            import whisper
            model = whisper.load_model("base")
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
            print(f"[Audio] pyaudiowpatch non disponible : {e}")
            print("[Audio] Tentative de fallback via sounddevice...")
            keywords = ["mixage", "stereo mix", "loopback", "what u hear", "voicemeeter output", "cable output"]
            devices = sd.query_devices()
            print("[Audio] Périphériques d'entrée disponibles :")
            for i, dev in enumerate(devices):
                try:
                    if dev['max_input_channels'] > 0:
                        print(f"  [{i}] {dev['name']} (canaux : {dev['max_input_channels']})")
                        if any(k in dev['name'].lower() for k in keywords):
                            loopback_device_index = i
                            print(f"[Audio] Loopback fallback sélectionné : {dev['name']}")
                            break
                except Exception:
                    pass
            if loopback_device_index is None:
                print("[Audio] Aucun device loopback trouvé. L'audio système ne sera pas transcrit.")

        print(f"[Audio] Micro système : {'index ' + str(loopback_device_index) if loopback_device_index is not None else 'non disponible'}")

        def capture_mic():
            """Capture et transcrit le micro physique en continu."""
            while self.is_running:
                try:
                    mic_audio = sd.rec(
                        int(AUDIO_SEGMENT_DURATION * sample_rate),
                        samplerate=sample_rate, channels=1, dtype="float32",
                        device=None
                    )
                    sd.wait()
                    mic_data = mic_audio.flatten()
                    if np.abs(mic_data).mean() > 0.005:
                        result = model.transcribe(
                            mic_data,
                            language="fr",
                            task="transcribe",
                            condition_on_previous_text=False,
                            no_speech_threshold=0.6,
                            logprob_threshold=-1.0,
                            beam_size=5,
                        )
                        text = result["text"].strip()
                        if len(text) > 10:
                            add_transcript("User", text)
                            if self.on_transcript_callback:
                                self.on_transcript_callback(text)
                except Exception as e:
                    print(f"[Micro] Erreur capture voix : {e}")
                    time.sleep(5)

        def capture_loopback():
            """Capture et transcrit l'audio système (loopback) en continu."""
            if loopback_device_index is None:
                print("[Loopback] Aucun device détecté — thread loopback inactif.")
                print("[Loopback] Pour activer : installez pyaudiowpatch ou activez 'Mixage stéréo' dans les paramètres audio Windows.")
                return

            print(f"[Loopback] Démarrage capture sur device index {loopback_device_index}")

            while self.is_running:
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
                    for _ in range(int(dev_sample_rate / 1024 * AUDIO_SEGMENT_DURATION)):
                        frames.append(stream.read(1024, exception_on_overflow=False))
                    stream.stop_stream()
                    stream.close()
                    p.terminate()

                    raw = b"".join(frames)
                    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    if channels > 1:
                        arr = arr.reshape(-1, channels).mean(axis=1)

                    audio_level = np.abs(arr).mean()
                    print(f"[Loopback] Niveau audio : {audio_level:.4f}")  # debug — à retirer une fois stable

                    if audio_level > 0.001:  # seuil abaissé (était 0.005)
                        result = model.transcribe(
                            arr,
                            language="fr",
                            task="transcribe",
                            condition_on_previous_text=False,
                            no_speech_threshold=0.6,
                            logprob_threshold=-1.0,
                            beam_size=5,
                        )
                        sys_text = result["text"].strip()
                        if len(sys_text) > 10:
                            add_transcript("System_Audio", sys_text)
                            print(f"[Loopback] Transcrit : {sys_text[:80]}...")
                    else:
                        print("[Loopback] Silence détecté, pas de transcription.")

                except Exception as e:
                    print(f"[Loopback] Erreur capture : {e}")
                    time.sleep(5)

        # Lancer les deux captures en parallèle
        t_mic = threading.Thread(target=capture_mic, daemon=True)
        t_loop = threading.Thread(target=capture_loopback, daemon=True)
        t_mic.start()
        t_loop.start()
        t_mic.join()
        t_loop.join()

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
            if not is_system:
                recent = query_transcripts(limit=5)
                context = "\n".join([f"[{r[0]}] {r[1]}: {r[2]}" for r in reversed(recent)])
                full_prompt = f"Historique récent des transcriptions :\n{context}\n\nUtilisateur : {user_message}"
            else:
                full_prompt = f"Système : {user_message}"

            if status_callback: status_callback("Analyse du contexte...")

            # Essayer d'abord le mode texte (moins de tokens, plus rapide)
            file_path, doc_content = self._get_active_document()
            if file_path and doc_content:
                max_chars = 12000
                if len(doc_content) > max_chars:
                    doc_content = doc_content[:max_chars] + "\n[... tronqué ...]"
                context_block = f"\nContexte — fichier ouvert `{file_path}` :\n```\n{doc_content}\n```\n"
                full_prompt = context_block + full_prompt
                if status_callback: status_callback("Analyse Gemini en cours (mode document)...")
                with self._lock:
                    response = self.chat_session.send_message(full_prompt)
            else:
                screen_text = self._get_screen_text()
                if screen_text:
                    full_prompt = f"Contenu de l'écran :\n{screen_text}\n\n{full_prompt}"
                    if status_callback: status_callback("Analyse Gemini en cours (mode texte)...")
                    with self._lock:
                        response = self.chat_session.send_message(full_prompt)
                else:
                    # Fallback image
                    if status_callback: status_callback("Capture de l'écran...")
                    screen_img = self._capture_screen()
                    if status_callback: status_callback("Analyse Gemini en cours (mode image)...")
                    with self._lock:
                        response = self.chat_session.send_message([full_prompt, screen_img])

            text_response = response.text.strip()

            if "[UPDATE_SCREEN]" in text_response:
                clean_text = text_response.replace("[UPDATE_SCREEN]", "").strip()
                if clean_text and self.on_suggestion_callback:
                    self._update_suggestion(f"⚙️ {clean_text}")
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
