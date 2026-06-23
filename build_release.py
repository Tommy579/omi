"""
Script d'automatisation des Releases pour OMI.
1. Compile OmiAssistant.exe
2. Compile OMI_Setup.exe (en incluant OmiAssistant.exe)
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Force UTF-8 encoding for standard output on Windows to avoid UnicodeEncodeError
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

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

    exe_ext = ".exe" if os.name == "nt" else ""
    sep = ";" if os.name == "nt" else ":"
    icon_args = ["--icon", "omi_icon.ico"] if os.name == "nt" else []

    # 1. Compiler OmiAssistant
    # On n'inclut PAS le .env ici car le Setup s'en chargera pour l'utilisateur
    cmd_assistant = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "OmiAssistant",
    ] + icon_args + ["main.py"]
    run_command(cmd_assistant, f"Compilation de OmiAssistant{exe_ext}")

    # 2. Vérifier que l'assistant est bien créé
    assistant_exe = DIST_DIR / f"OmiAssistant{exe_ext}"
    if not assistant_exe.exists():
        print(f"!!! OmiAssistant{exe_ext} n'a pas été trouvé après la compilation.")
        exit(1)

    # 3. Compiler OMI_Setup
    # On inclut OmiAssistant et l'icône dans le bundle du Setup
    cmd_setup = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "OMI_Setup",
    ] + icon_args + [
        "--add-data", f"{assistant_exe}{sep}.",
        "--add-data", f"{APP_DIR / 'omi_icon.ico'}{sep}.",
        "installer_gui.py"
    ]
    run_command(cmd_setup, f"Compilation de OMI_Setup{exe_ext} (Installeur)")

    print("\n" + "="*50)
    print("   RELEASE TERMINÉE AVEC SUCCÈS")
    print("="*50)
    print(f"Fichier à distribuer : {DIST_DIR / f'OMI_Setup{exe_ext}'}")
    print("="*50)

if __name__ == "__main__":
    main()
