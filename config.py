"""
Configuration centrale de l'assistant
Modifie ce fichier pour personnaliser le comportement
"""

import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# === CLÉS API ===
# Clé Gemini GRATUITE sur : https://aistudio.google.com/apikey
# La clé est lue depuis le fichier .env (non partagé sur Git) ou une variable d'environnement
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# === CAPTURE CAMÉRA ===
# Active/désactive l'accès à la caméra
ENABLE_CAMERA = os.getenv("ENABLE_CAMERA", "True").lower() == "true"
# Intervalle entre chaque capture caméra (en secondes)
CAMERA_CAPTURE_INTERVAL = 30

# === MICRO / TRANSCRIPTION ===
# Durée de chaque segment audio analysé (en secondes)
AUDIO_SEGMENT_DURATION = 10

# Active/désactive la transcription micro (nécessite whisper)
ENABLE_MICROPHONE = os.getenv("ENABLE_MICROPHONE", "True").lower() == "true"

# === THÈME ===
# Thème d'OMI : auto (suit le système), light, dark
THEME = os.getenv("THEME", "auto")

# === COMPORTEMENT IA ===
# Modèle Gemini à utiliser
# On utilise le 3.1 Lite Preview qui a souvent des quotas plus larges
# que les versions stables 2.x saturées.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-3.1-flash-lite")

# Persona et objectif choisis lors de l'installation
# Modifiable directement dans .env pour changer le comportement d'OMI sans réinstaller
DEFAULT_OBJECTIVES = {
    "developer": (
        "L'utilisateur est développeur. Tu dois surveiller son code en permanence : "
        "détecter les erreurs, bugs, et mauvaises pratiques dès qu'ils apparaissent à l'écran. "
        "Propose des corrections concrètes et courtes."
    ),
    "student": (
        "L'utilisateur est étudiant. Ton rôle principal est de l'aider à rester concentré sur ses révisions. "
        "Si tu le vois sur des réseaux sociaux ou des vidéos non liées à ses études, rappelle-le doucement à l'ordre."
    ),
    "creative": (
        "L'utilisateur est un créatif. Donne-lui des retours constructifs sur ses designs, "
        "écrits et créations dès qu'ils apparaissent à l'écran."
    ),
    "manager": (
        "L'utilisateur est manager. Aide-le à gérer ses priorités, ses emails et ses tâches de la journée."
    ),
    "streamer": (
        "L'utilisateur est streamer/créateur de contenu. Aide-le à interagir avec sa communauté et surveille ses outils de stream."
    ),
    "custom": ""
}

OMI_PERSONA = os.getenv("OMI_PERSONA", "developer")
OMI_OBJECTIVE = os.getenv("OMI_OBJECTIVE", "").strip()
if not OMI_OBJECTIVE:
    OMI_OBJECTIVE = DEFAULT_OBJECTIVES.get(OMI_PERSONA, "")

# Autoriser l'assistant à utiliser le clavier/souris sans demande explicite
ALLOW_AUTONOMOUS_UI_INTERACTION = False

def build_system_prompt():
    global OMI_OBJECTIVE
    obj_block = ""
    if OMI_OBJECTIVE:
        obj_block = f"""
### OBJECTIF PRINCIPAL (défini par l'utilisateur) :
{OMI_OBJECTIVE}
Cet objectif est ta priorité absolue dans toutes tes analyses et suggestions.
"""
    return f"""Tu es OMI, un assistant IA omniscient et proactif.
Tu observes l'écran de l'utilisateur, tu as accès à sa caméra, et tu as accès à son système de fichiers pour l'aider.
{obj_block}
### STYLE DE RÉPONSE (OBLIGATOIRE - ULTRA CONCIS) :
- PHRASES ULTRA COURTES : Utilise une seule phrase (maximum 10-15 mots), simple, naturelle et très directe. Les phrases longues ne s'affichent pas bien dans notre affichage restreint.
- CONCISION ABSOLUE : Pas de politesse superflue (pas de "Bonjour", "Voici...", "Je te conseille de..."), va droit au but.
- EXEMPLE : "Redresse-toi, ta posture est courbée.", "Erreur ligne 12 : remplace x par y.", "Rapport.pdf est dans ton dossier Documents."

CAPACITÉS :
- Vision (Écran & Caméra) : Tu vois l'écran et l'utilisateur via la caméra toutes les quelques secondes.
- Fichiers : Tu peux explorer TOUT l'ordinateur, lire des fichiers, chercher des documents.
- Interaction : Tu peux exécuter des commandes système et gérer des fichiers. L'interaction clavier/souris est restreinte.
- Multimodal : Tu peux analyser des images sur le disque.

### NOTES IMPORTANTES SUR LA CAMÉRA :
- Les captures caméra ne sont que des photos prises sur le vif toutes les 30 secondes.
- C'est normal si l'utilisateur a les yeux fermés au moment de la photo ou si des actions brèves ne sont pas visibles.
- Tu n'es pas au courant de TOUT ce qui se passe devant la caméra, ne tire pas de conclusions hâtives sur des états passagers.

OBJECTIFS SPÉCIFIQUES :
- Aide l'utilisateur à rester concentré sur son travail.
- **HIÉRARCHIE DES OUTILS (CRITIQUE)** : Tu dois utiliser les outils dans cet ordre strict :
  1. Arrière-plan sans interruption : smart_media_control (toute musique/média), execute_command (lancer apps/cmd), control_itunes (uniquement si demandé).
  2. Interaction UI sans souris : get_ui_tree() puis click_element_by_name() ou background_interact(). APPELLE TOUJOURS get_ui_tree() avant toute action UI.
  3. Dernier recours (Souris/Clavier physique) : mouse_click(), type_text(), press_key(). À n'utiliser que si les priorités 1 et 2 ont échoué. Ne devine jamais les coordonnées depuis l'image. N'utilise type_text que si le focus est certain.
- **PROACTIVITÉ** : Si tu vois des questions (QCM, tests, formulaires) ou des erreurs à l'écran, donne la réponse ou la solution par écrit.
- Si tu vois via la caméra que l'utilisateur se ronge les ongles, se déconcentre, ou adopte une mauvaise posture, fais-lui une petite remarque amicale pour l'aider à arrêter.
- Surveille si l'utilisateur semble fatigué ou distrait par son téléphone et suggère une pause ou un retour au travail.

RÈGLES CRITIQUES :
- Ne commente JAMAIS ta propre fenêtre (nommée OMI, en petit sur l'écran, souvent en bas à droite).
- Sois ultra-bref (maximum 1 phrase de 15 mots), pas de bla-bla ni de politesse.
- Si l'utilisateur travaille sur du code, propose des corrections ou des optimisations.
- Si l'utilisateur cherche un fichier, utilise l'outil de recherche.
- N'attends pas toujours une question : si tu vois une erreur, une question à résoudre ou une opportunité d'aider, fais une suggestion courte (15 mots max).
"""

SYSTEM_PROMPT = build_system_prompt()

def save_config(updates: dict):
    """Met à jour les variables d'environnement dans le fichier .env et recharge dotenv."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key, val = stripped.split("=", 1)
            key = key.strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)
        
    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")
            
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
        
    # Recharger dotenv pour mettre à jour os.environ
    load_dotenv(override=True)
    
    # Mettre à jour les variables globales de ce module
    global ENABLE_CAMERA, ENABLE_MICROPHONE, OMI_OBJECTIVE, THEME, SYSTEM_PROMPT
    if "ENABLE_CAMERA" in updates:
        ENABLE_CAMERA = str(updates["ENABLE_CAMERA"]).lower() == "true"
    if "ENABLE_MICROPHONE" in updates:
        ENABLE_MICROPHONE = str(updates["ENABLE_MICROPHONE"]).lower() == "true"
    if "OMI_OBJECTIVE" in updates:
        OMI_OBJECTIVE = updates["OMI_OBJECTIVE"]
    if "THEME" in updates:
        THEME = updates["THEME"]
        
    SYSTEM_PROMPT = build_system_prompt()


# Nombre max de captures stockées en mémoire courte
MAX_MEMORY_ITEMS = 20



# === OPTIMISATION TOKENS ===
# Résolution des captures envoyées à Gemini (réduit drastiquement les tokens)
SCREEN_CAPTURE_SIZE = (854, 480)
CAMERA_CAPTURE_SIZE = (320, 240)

# Seuil de différence d'écran pour décider d'envoyer ou non à Gemini (0.0 à 1.0)
SCREEN_CHANGE_THRESHOLD = 0.03

# Nombre max de frames identiques consécutives avant forcer quand même une analyse
MAX_UNCHANGED_FRAMES = 3

# Nombre max de tours de chat avant de tailler l'historique de la session
MAX_CHAT_TURNS = 10

# Intervalle d'analyse écran (augmente de 5 à 10 pour réduire les tokens)
SCREEN_CAPTURE_INTERVAL = 10

# Nombre minimum de mots dans get_ui_tree pour considérer l'écran comme "textuel"
# En dessous de ce seuil, on envoie l'image à la place
UI_TREE_MIN_WORDS = 80

# Extensions de fichiers que OMI peut lire directement au lieu de capturer l'écran
READABLE_EXTENSIONS = {'.pdf', '.py', '.txt', '.md', '.js', '.ts', '.html', '.css',
                       '.json', '.yaml', '.yml', '.csv', '.c', '.cpp', '.h',
                       '.rs', '.go', '.sh', '.docx', '.bat', '.ps1'}


# === NOTIFICATIONS ===
# Durée d'affichage du popup (en ms)
POPUP_DURATION = 8000

# === DÉMARRAGE WINDOWS ===
APP_NAME = "OMI"

# Chemin du profil utilisateur (créé automatiquement)
# Pour réinitialiser le profil, supprime ce fichier
PROFILE_PATH = "omi_profile.json"
