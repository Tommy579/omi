# OMI — Assistant IA Personnel pour Windows

OMI est un assistant IA qui tourne en arrière-plan dans ta barre des tâches. Il observe ton écran, écoute via le micro, accède à ton système de fichiers et peut interagir avec ton OS — le tout propulsé par Gemini.

---

## Fonctionnalités

- **Vision** : Analyse ton écran toutes les quelques secondes et te fait des suggestions proactives
- **Caméra** : Capture périodique via webcam (posture, concentration, habitudes)
- **Micro** : Transcription en temps réel de ce qui est dit, stockée en base locale
- **Agent OS** : Peut lister/lire/écrire des fichiers, voir les processus, gérer le presse-papier, exécuter des commandes, interagir avec des fenêtres en arrière-plan
- **Chat contextuel** : Répond à tes questions en ayant accès à ton écran et à l'historique de session
- **Thème automatique** : Suit le mode clair/sombre de Windows en temps réel

---

## Prérequis

- Windows 10 ou 11
- Python 3.10+
- Une clé API Gemini (voir ci-dessous)

---

## Installation

### 1. Cloner le projet

```bash
git clone <url-du-repo>
cd OMI
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Obtenir une clé API Gemini

1. Va sur [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Connecte-toi avec ton compte Google
3. Clique sur **Create API key**
4. Copie la clé (commence par `AIza...`)

### 4. Configurer la clé

Ouvre `config.py` et remplace la valeur de `GEMINI_API_KEY` :

```python
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "COLLE-TA-CLÉ-ICI")
```

> **Recommandé** : utilise une variable d'environnement plutôt que de coller la clé directement dans le fichier, surtout si tu utilises Git.

### 5. Lancer

```bash
pythonw main.py
```

L'icône OMI apparaît dans la barre des tâches. Clique dessus pour ouvrir le panel.

---

## Démarrage automatique avec Windows

Lance le script d'installation :

```bash
python install.py
```

Il configure un fichier `.bat` dans le dossier Startup de Windows pour que OMI se lance automatiquement à chaque démarrage.

---

## Utilisation

| Action | Résultat |
|---|---|
| Clic sur l'icône OMI | Ouvre le panel |
| `↺` dans le panel | Force une analyse de l'écran maintenant |
| `⏸` dans le panel | Met l'analyse automatique en pause |
| `🎙️` dans le panel | Affiche l'historique des transcriptions micro |
| `—` dans le panel | Réduit en filigrane (dernier message visible en bas à droite) |
| `×` dans le panel | Ferme le panel |
| Zone de chat en bas | Envoie un message à OMI avec contexte écran complet |

---

## Configuration (`config.py`)

| Paramètre | Description | Défaut |
|---|---|---|
| `SCREEN_CAPTURE_INTERVAL` | Fréquence d'analyse écran (secondes) | `5` |
| `ENABLE_CAMERA` | Active la capture webcam | `True` |
| `CAMERA_CAPTURE_INTERVAL` | Fréquence capture caméra (secondes) | `30` |
| `ENABLE_MICROPHONE` | Active la transcription micro | `True` |
| `AUDIO_SEGMENT_DURATION` | Durée de chaque segment audio (secondes) | `10` |
| `GEMINI_MODEL` | Modèle Gemini utilisé | `gemini-3.1-flash-lite-preview` |
| `SYSTEM_PROMPT` | Personnalité et comportement de l'assistant | voir fichier |

---

## Structure du projet

```
OMI/
├── main.py               # Point d'entrée
├── config.py             # ⚙️ Configuration
├── install.py            # Script d'installation CLI
├── requirements.txt      # Dépendances Python
├── core/
│   ├── assistant.py      # Cerveau : vision, micro, appels Gemini
│   ├── tools.py          # Outils OS accessibles par Gemini
│   └── database.py       # Base SQLite pour l'historique audio
└── ui/
    └── tray.py           # Interface : icône système + popup
```

---

## Outils disponibles pour Gemini

Gemini peut appeler ces outils de manière autonome selon le contexte :

**Fichiers** : `list_directory`, `read_file`, `write_file`, `search_files`  
**OS** : `execute_command`, `get_active_window_info`, `get_ui_tree`, `get_system_stats`  
**Processus** : `list_processes`, `get_process_details`, `kill_process`  
**Interface** : `mouse_click`, `type_text`, `press_key`, `background_interact`  
**Réseau** : `get_network_connections`  
**Système** : `get_clipboard`, `set_clipboard`, `get_machine_info`, `get_windows_event_logs`  
**Apps** : `control_itunes`, `open_url`, `search_web`, `send_notification`  
**Historique** : `query_transcript_history`

---

## Dépendances principales

```
google-genai          # API Gemini (nouveau SDK)
mss                   # Capture d'écran
Pillow                # Traitement image
opencv-python         # Capture webcam
pystray               # Icône système tray
sounddevice + numpy   # Capture audio
openai-whisper        # Transcription locale
psutil                # Monitoring processus
pywinauto             # Interaction fenêtres en arrière-plan
pyodbc                # Accès à l'index Windows Search
pyperclip             # Presse-papier
pygetwindow           # Info fenêtres
pyautogui             # Contrôle souris/clavier
pywin32               # APIs Windows (logs événements)
win10toast-persist    # Notifications Windows
```

---

## Sécurité

- Ne commite jamais ta clé API dans Git
- Le fichier `.env` est dans `.gitignore` — tu peux y stocker `GEMINI_API_KEY=ta_clé` et la lire via `os.getenv()`
- `execute_command` et `write_file` donnent à Gemini un accès complet à ton système — à utiliser en connaissance de cause
