"""
OMI Windows Assistant - Point d'entrée principal
Lance l'icône système et démarre tous les services en arrière-plan
"""

import sys
import threading
import os
import ctypes

def hide_console():
    """Cache la console si le script est lancé avec python.exe sur Windows"""
    if os.name == 'nt':
        # On essaie de récupérer le handle de la fenêtre de console
        whnd = ctypes.windll.kernel32.GetConsoleWindow()
        if whnd != 0:
            # On cache la fenêtre (SW_HIDE = 0)
            ctypes.windll.user32.ShowWindow(whnd, 0)
            # On détache le processus de la console pour qu'elle puisse se fermer proprement
            # ctypes.windll.kernel32.FreeConsole()

# Ajoute le dossier courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.assistant import Assistant
from ui.tray import TrayApp

def main():
    hide_console()
    
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
