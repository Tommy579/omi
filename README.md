# Omi Assistant — Windows

Assistant IA personnel qui tourne dans ta barre des tâches, observe ton écran et t'aide proactivement.

## Installation (1 seule fois)

```bash
python install.py
```

Le script va :
1. Installer toutes les dépendances
2. Te demander ta clé API Gemini (gratuit sur https://aistudio.google.com/api-keys)
3. Configurer le démarrage automatique avec Windows
4. (Optionnel) Générer un .exe standalone

## Structure

```
omi-windows/
├── main.py          # Point d'entrée
├── config.py        # ⚙️ Paramètres à modifier ici
├── install.py       # Script d'installation
├── core/
│   └── assistant.py # Cerveau : capture écran + micro + Gemini API
└── ui/
    └── tray.py      # Icône barre des tâches + popup
```

## Personnalisation

Ouvre `config.py` pour modifier :
- `SCREEN_CAPTURE_INTERVAL` : fréquence d'analyse de l'écran (défaut : 15s)
- `ENABLE_MICROPHONE` : activer/désactiver le micro
- `SYSTEM_PROMPT` : changer la personnalité de l'assistant
- `GEMINI_MODEL` : changer le modèle IA

## Utilisation

- **Icône ◉** dans la barre des tâches = l'assistant est actif
- **Clic** sur l'icône → ouvre le panel
- **↻ Analyser maintenant** → force une analyse immédiate
- **Chat** → pose une question en gardant le contexte de ton écran
- **Pause** → met l'assistant en pause s'il n'y a pas besoin de gaspiller des ressources

## Dépendances

- `google-generativeai` — API Gemini
- `mss` — capture d'écran
- `Pillow` — traitement image
- `pystray` — icône système
- `sounddevice` + `openai-whisper` — transcription micro (optionnel)
