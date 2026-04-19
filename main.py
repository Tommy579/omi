"""
OMI Windows Assistant - Point d'entrée principal
Lance l'icône système et démarre tous les services en arrière-plan
"""

import sys
import threading
import os

# Ajoute le dossier courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.assistant import Assistant
from ui.tray import TrayApp

def main():
    # Démarre l'assistant (capture écran + micro + IA)
    assistant = Assistant()
    
    # Lance l'assistant dans un thread séparé
    assistant_thread = threading.Thread(target=assistant.start, daemon=True)
    assistant_thread.start()
    
    # Lance l'UI (icône barre des tâches) - bloque le thread principal
    tray = TrayApp(assistant)
    tray.run()

if __name__ == "__main__":
    main()
