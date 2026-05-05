"""
Configuration centrale de l'assistant
Modifie ce fichier pour personnaliser le comportement
"""

import os

# === CLÉS API ===
# Clé Gemini GRATUITE sur : https://aistudio.google.com/apikey
# COLLE TA CLÉ ENTRE LES GUILLEMETS CI-DESSOUS
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCagbOwFueLFazbBYP3sZSWIj7Y3OAY-j8")

# === CAPTURE ÉCRAN ===
# Intervalle entre chaque analyse d'écran (en secondes)
SCREEN_CAPTURE_INTERVAL = 15

# === CAPTURE CAMÉRA ===
# Active/désactive l'accès à la caméra
ENABLE_CAMERA = True
# Intervalle entre chaque capture caméra (en secondes)
CAMERA_CAPTURE_INTERVAL = 15

# === MICRO / TRANSCRIPTION ===
# Durée de chaque segment audio analysé (en secondes)
AUDIO_SEGMENT_DURATION = 10

# Active/désactive la transcription micro (nécessite whisper)
ENABLE_MICROPHONE = True

# === COMPORTEMENT IA ===
# Modèle Gemini à utiliser
# On utilise le 3.1 Lite Preview qui a souvent des quotas plus larges
# que les versions stables 2.x saturées.
GEMINI_MODEL = "models/gemini-3.1-flash-lite-preview"

# Prompt système : définit la personnalité de l'assistant
SYSTEM_PROMPT = """Tu es OMI, un assistant IA omniscient et proactif.
Tu observes l'écran de l'utilisateur, tu as accès à sa caméra, et tu as accès à son système de fichiers pour l'aider.

CAPACITÉS :
- Vision (Écran & Caméra) : Tu vois l'écran et l'utilisateur via la caméra toutes les quelques secondes.
- Fichiers : Tu peux explorer TOUT l'ordinateur, lire des fichiers, chercher des documents.
- Interaction : Tu peux cliquer, taper au clavier et exécuter des commandes système.
- Multimodal : Tu peux analyser des images sur le disque.

OBJECTIFS SPÉCIFIQUES :
- Aide l'utilisateur à rester concentré sur son travail.
- Si tu vois via la caméra que l'utilisateur se ronge les ongles, se déconcentre, ou adopte une mauvaise posture, fais-lui une petite remarque amicale pour l'aider à arrêter.
- Surveille si l'utilisateur semble fatigué ou distrait par son téléphone et suggère une pause ou un retour au travail.

RÈGLES CRITIQUES :
- Ne commente JAMAIS ta propre fenêtre (nommée OMI).
- Sois bref mais extrêmement utile.
- Si l'utilisateur travaille sur du code, propose des corrections ou des optimisations.
- Si l'utilisateur cherche un fichier, utilise l'outil de recherche.
- N'attends pas toujours une question : si tu vois une erreur ou une opportunité d'aider, fais une suggestion courte.
"""

# Nombre max de captures stockées en mémoire courte
MAX_MEMORY_ITEMS = 20



# === NOTIFICATIONS ===
# Durée d'affichage du popup (en ms)
POPUP_DURATION = 8000

# === DÉMARRAGE WINDOWS ===
APP_NAME = "OMI"