"""
Script d'installation :
1. Installe les dépendances Python
2. Configure le démarrage automatique avec Windows
3. Génère l'exécutable .exe (optionnel)

Lance avec : python install.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


APP_NAME = "OmiAssistant"
APP_DIR = Path(__file__).parent.resolve()
MAIN_SCRIPT = APP_DIR / "main.py"


def step(msg):
    print(f"\n{'─'*50}")
    print(f"  {msg}")
    print('─'*50)


def install_dependencies():
    step("📦 Installation des dépendances...")
    
    packages = [
        "google-generativeai",
        "mss",
        "Pillow",
        "pystray",
        "sounddevice",
        "numpy",
        "pygetwindow",
        "pyautogui",
        "win10toast-persist",
        "requests",
        # whisper est optionnel et plus lourd
    ]
    
    for pkg in packages:
        print(f"  → Installation de {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
    
    print("\n  ✓ Dépendances installées")
    
    # Whisper séparément (plus lourd)
    install_whisper = input("\n  Installer Whisper pour la transcription micro ? (y/n) : ").strip().lower()
    if install_whisper == "y":
        subprocess.check_call([sys.executable, "-m", "pip", "install", "openai-whisper", "-q"])
        print("  ✓ Whisper installé")


def setup_api_key():
    step("🔑 Configuration de la clé API Gemini")
    print("  1. Va sur https://aistudio.google.com/apikey")
    print("  2. Créé un compte gratuit")
    print("  3. Dans 'API Keys', génère une clé")
    print()
    
    key = input("  Colle ta clé API ici (commence par AIza...) : ").strip()
    
    if not key.startswith("AIza"):
        print("  ⚠ La clé ne semble pas valide, mais on continue.")
    
    # Met à jour config.py avec la vraie clé
    config_path = APP_DIR / "config.py"
    lines = config_path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    for line in lines:
        if line.startswith("GEMINI_API_KEY ="):
            new_lines.append(f'GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "{key}")')
        else:
            new_lines.append(line)
    config_path.write_text("\n".join(new_lines), encoding="utf-8")
    print("  ✓ Clé enregistrée dans config.py")


def setup_autostart():
    step("🚀 Configuration du démarrage automatique avec Windows")
    
    # Dossier Startup de Windows
    startup_dir = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    
    # Crée un fichier .bat qui lance le script Python en arrière-plan
    bat_content = f"""@echo off
start "" /B pythonw "{MAIN_SCRIPT}"
"""
    bat_path = startup_dir / f"{APP_NAME}.bat"
    bat_path.write_text(bat_content, encoding="utf-8")
    
    print(f"  ✓ Fichier de démarrage créé :")
    print(f"    {bat_path}")
    print(f"\n  L'assistant se lancera automatiquement au prochain démarrage de Windows.")


def build_exe():
    step("📦 Construction du fichier .exe (optionnel)")
    build = input("  Construire un .exe standalone ? (y/n) : ").strip().lower()
    
    if build != "y":
        print("  → Ignoré. Tu peux relancer install.py plus tard.")
        return
    
    print("  Installation de PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "-q"])
    
    print("  Construction en cours (peut prendre quelques minutes)...")
    cmd = [
        "pyinstaller",
        "--onefile",           # tout dans un seul .exe
        "--windowed",          # pas de console
        "--name", APP_NAME,
        "--add-data", f"{APP_DIR / 'config.py'};.",
        str(MAIN_SCRIPT),
    ]
    
    result = subprocess.run(cmd, cwd=APP_DIR)
    
    if result.returncode == 0:
        exe_path = APP_DIR / "dist" / f"{APP_NAME}.exe"
        print(f"\n  ✓ Exécutable créé : {exe_path}")
        
        # Met à jour le bat pour pointer sur le .exe
        startup_dir = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        bat_content = f'@echo off\nstart "" "{exe_path}"\n'
        bat_path = startup_dir / f"{APP_NAME}.bat"
        bat_path.write_text(bat_content, encoding="utf-8")
        print(f"  ✓ Démarrage automatique mis à jour pour pointer sur le .exe")
    else:
        print("  ⚠ Erreur lors de la construction du .exe")


def launch_now():
    step("▶ Lancement de l'assistant")
    launch = input("  Lancer l'assistant maintenant ? (y/n) : ").strip().lower()
    if launch == "y":
        print("  Démarrage... (l'icône va apparaître dans la barre des tâches)")
        subprocess.Popen([sys.executable, str(MAIN_SCRIPT)], 
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        print("  ✓ Assistant lancé !")


def main():
    print("\n" + "═"*50)
    print("   OMI ASSISTANT — INSTALLATION")
    print("═"*50)
    
    try:
        install_dependencies()
        setup_api_key()
        setup_autostart()
        build_exe()
        launch_now()
        
        print("\n" + "═"*50)
        print("  ✅ Installation terminée !")
        print("  L'icône ◉ apparaît dans ta barre des tâches.")
        print("  Clique dessus pour ouvrir le panel.")
        print("═"*50 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n  Installation annulée.")
    except Exception as e:
        print(f"\n  ❌ Erreur : {e}")
        input("  Appuie sur Entrée pour quitter.")


if __name__ == "__main__":
    main()
