"""
Script d'automatisation des Releases pour OMI.
1. Compile OmiAssistant.exe
2. Compile OMI_Setup.exe (en incluant OmiAssistant.exe)
"""

import os
import subprocess
import shutil
from pathlib import Path

APP_DIR = Path(__file__).parent.resolve()
DIST_DIR = APP_DIR / "dist"
BUILD_DIR = APP_DIR / "build"

def run_command(cmd, msg):
    print(f"\n>>> {msg}")
    result = subprocess.run(cmd, cwd=APP_DIR)
    if result.returncode != 0:
        print(f"!!! Erreur lors de : {msg}")
        exit(1)

def main():
    # Nettoyage
    if DIST_DIR.exists(): shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists(): shutil.rmtree(BUILD_DIR)

    # 1. Compiler OmiAssistant.exe
    # On n'inclut PAS le .env ici car le Setup s'en chargera pour l'utilisateur
    cmd_assistant = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", "OmiAssistant",
        "--icon", "omi_icon.ico",
        "main.py"
    ]
    run_command(cmd_assistant, "Compilation de OmiAssistant.exe")

    # 2. Vérifier que l'assistant est bien créé
    assistant_exe = DIST_DIR / "OmiAssistant.exe"
    if not assistant_exe.exists():
        print("!!! OmiAssistant.exe n'a pas été trouvé après la compilation.")
        exit(1)

    # 3. Compiler OMI_Setup.exe
    # On inclut OmiAssistant.exe et l'icône dans le bundle du Setup
    cmd_setup = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", "OMI_Setup",
        "--icon", "omi_icon.ico",
        "--add-data", f"{assistant_exe};.",
        "--add-data", f"{APP_DIR / 'omi_icon.ico'};.",
        "installer_gui.py"
    ]
    run_command(cmd_setup, "Compilation de OMI_Setup.exe (Installeur)")

    print("\n" + "="*50)
    print("   RELEASE TERMINÉE AVEC SUCCÈS")
    print("="*50)
    print(f"Fichier à distribuer : {DIST_DIR / 'OMI_Setup.exe'}")
    print("="*50)

if __name__ == "__main__":
    main()
