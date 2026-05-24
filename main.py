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

    # Vérification de la clé API avant tout
    from config import GEMINI_API_KEY
    if not GEMINI_API_KEY or not GEMINI_API_KEY.startswith("AIza"):
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "OMI — Clé API manquante",
            "Aucune clé API Gemini valide n'a été trouvée.\n\n"
            "1. Va sur https://aistudio.google.com/apikey\n"
            "2. Génère une clé gratuite\n"
            "3. Crée un fichier .env à côté de main.py avec :\n"
            "   GEMINI_API_KEY=ta_clé\n\n"
            "Puis relance OMI."
        )
        root.destroy()
        return

    assistant = Assistant()
    assistant_thread = threading.Thread(target=assistant.start, daemon=True)
    assistant_thread.start()

    tray = TrayApp(assistant)
    tray.run()

if __name__ == "__main__":
    main()
