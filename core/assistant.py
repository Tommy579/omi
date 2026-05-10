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

    def toggle_pause(self):
        self.paused = not self.paused
        status = "en pause" if self.paused else "actif"
        print(f"[Assistant] État : {status}")
        return self.paused

    # ─────────────────────────────────────────────
    # Capture Vision (Écran + Caméra) et Analyse
    # ─────────────────────────────────────────────

    def _vision_loop(self):
        while self.is_running:
            try:
                if not self.paused:
                    images = []
                    
                    # Capture de l'écran
                    screen_img = self._capture_screen()
                    images.append(screen_img)
                    
                    # Capture de la caméra si activée et intervalle respecté
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
        """Capture l'écran principal et retourne un objet PIL Image redimensionné"""
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img.thumbnail((1280, 720), Image.LANCZOS)
        return img

    def _capture_camera(self):
        """Capture une image depuis la webcam"""
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return None
            
            # Convertir BGR en RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail((640, 480), Image.LANCZOS)
            return img
        except Exception as e:
            print(f"[Caméra] Erreur de capture : {e}")
            return None

    def _analyze_vision(self, images):
        """Envoie les images (écran + caméra) à Gemini via la session de chat"""
        prompt = "Voici mon écran actuel"
        if len(images) > 1:
            prompt += " et une vue de ma caméra."
        else:
            prompt += "."
        
        prompt += " Analyse la situation. Si tu remarques des mauvaises habitudes (se ronger les ongles, posture, distraction téléphone) ou une perte de concentration sur l'écran, fais une suggestion courte pour m'aider."

        try:
            # On envoie les images dans la session
            response = self.chat_session.send_message([prompt] + images)
            suggestion = response.text.strip()
            
            # Filtre pour éviter les suggestions inutiles
            if "Rien de particulier" in suggestion or len(suggestion) < 5:
                return

        except Exception as e:
            suggestion = f"Erreur API : {e}"
            print(f"[Gemini Vision] Erreur : {e}")
        
        self._add_to_memory("vision", suggestion)
        self._update_suggestion(suggestion)

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
        
        # Tentative de trouver un périphérique de loopback pour capturer le son système
        devices = sd.query_devices()
        loopback_idx = None
        keywords = ["mixage", "stereo mix", "loopback", "what u hear", "voicemeeter output", "cable output"]
        print("[Audio] Dispositifs audio disponibles:")
        for i, dev in enumerate(devices):
            try:
                # On affiche seulement les périphériques d'entrée
                if dev['max_input_channels'] > 0:
                    print(f"  {i}: {dev['name']} (Input Channels: {dev['max_input_channels']})")
                    if loopback_idx is None and any(k in dev['name'].lower() for k in keywords):
                        loopback_idx = i
                        print(f"[Audio] Périphérique système détecté : {dev['name']}")
            except:
                pass

        while self.is_running:
            try:
                # On écoute TOUT LE TEMPS, même en pause (mais on n'analyse pas si en pause)
                device = loopback_idx
                # Récupère les infos du device pour adapter les paramètres
                try:
                    dev_info = sd.query_devices(device, 'input')
                    channels = min(dev_info['max_input_channels'], 1)
                    if "mix" in dev_info['name'].lower() or "stéréo" in dev_info['name'].lower():
                        channels = min(dev_info['max_input_channels'], 2)
                except:
                    channels = 1
                    device = None

                audio = sd.rec(
                    int(AUDIO_SEGMENT_DURATION * sample_rate),
                    samplerate=sample_rate,
                    channels=channels,
                    dtype="float32",
                    device=device
                )
                sd.wait()
                
                audio_data = audio.flatten()
                if channels > 1:
                    audio_data = audio.reshape(-1, channels).mean(axis=1)

                result = model.transcribe(audio_data, language="fr", fp16=False)
                text = result["text"].strip()
                
                if len(text) > 10:
                    # On stocke TOUJOURS dans la database
                    add_transcript("User", text)
                    if self.on_transcript_callback:
                        self.on_transcript_callback(text)
                    
                    # L'analyse audio automatique est désactivée (Gemini n'analyse que sur commande chat)
                    # if not self.paused and len(text) > 15:
                    #     self._analyze_audio(text)
            except Exception as e:
                print(f"[Micro] Erreur : {e}")
                if loopback_idx is not None:
                    loopback_idx = None
                time.sleep(5)

    def _analyze_audio(self, transcript):
        prompt = f'J\'ai entendu ceci : "{transcript}". Réagis si c\'est important ou utile.'
        try:
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
