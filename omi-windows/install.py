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


def get_or_create_venv():
    venv_dir = APP_DIR / ".venv"
    if not venv_dir.exists():
        print("  → Création de l'environnement virtuel (.venv)...")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe", venv_dir / "Scripts" / "pythonw.exe"
    else:
        python_bin = venv_dir / "bin" / "python"
        return python_bin, python_bin


def install_dependencies(venv_python):
    step("📦 Installation des dépendances...")
    
    packages = [
        "google-genai",
        "mss",
        "Pillow",
        "pystray",
        "sounddevice",
        "numpy",
        "pyautogui",
        "requests",
        "opencv-python",
        "psutil",
        "pyperclip",
        "python-dotenv",
    ]
    if sys.platform == "win32":
        packages.extend(["pygetwindow", "win10toast-persist"])
    
    for pkg in packages:
        print(f"  → Installation de {pkg}...")
        subprocess.check_call([str(venv_python), "-m", "pip", "install", pkg])
    
    print("\n  ✓ Dépendances installées")
    
    # Whisper séparément (plus lourd)
    install_whisper = input("\n  Installer Whisper pour la transcription micro ? (y/n) : ").strip().lower()
    if install_whisper == "y":
        subprocess.check_call([str(venv_python), "-m", "pip", "install", "openai-whisper"])
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
    
    # Enregistre la clé dans le fichier .env
    env_path = APP_DIR / ".env"
    env_path.write_text(f"GEMINI_API_KEY={key}\n", encoding="utf-8")
    print("  ✓ Clé enregistrée dans .env (ignoré par Git)")


def setup_autostart(venv_python, venv_python_w):
    if sys.platform == "win32":
        step("🚀 Configuration du démarrage automatique avec Windows")
        startup_dir = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        bat_content = f"""@echo off\nstart "" /B "{venv_python_w}" "{MAIN_SCRIPT}"\n"""
        bat_path = startup_dir / f"{APP_NAME}.bat"
        bat_path.write_text(bat_content, encoding="utf-8")
        print(f"  ✓ Fichier de démarrage créé : {bat_path}")
        print(f"\n  L'assistant se lancera automatiquement au prochain démarrage de Windows.")
    else:
        step("🚀 Configuration du démarrage automatique avec Linux")
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        desktop_content = f"""[Desktop Entry]
Type=Application
Exec="{venv_python}" "{MAIN_SCRIPT}"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=OmiAssistant
Comment=Assistant IA Personnel
"""
        desktop_path = autostart_dir / f"{APP_NAME}.desktop"
        desktop_path.write_text(desktop_content, encoding="utf-8")
        os.chmod(desktop_path, 0o755)
        print(f"  ✓ Fichier de démarrage créé : {desktop_path}")
        print(f"\n  L'assistant se lancera automatiquement au prochain démarrage de Linux.")


def build_exe(venv_python):
    exe_name = f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME
    step(f"📦 Construction du fichier {exe_name} (optionnel)")
    build = input(f"  Construire un {exe_name} standalone ? (y/n) : ").strip().lower()
    
    if build != "y":
        print("  → Ignoré. Tu peux relancer install.py plus tard.")
        return
    
    print("  Installation de PyInstaller...")
    subprocess.check_call([str(venv_python), "-m", "pip", "install", "pyinstaller", "-q"])
    
    print("  Construction en cours (peut prendre quelques minutes)...")
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        str(venv_python), "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--add-data", f"{APP_DIR / 'config.py'}{sep}.",
        "--add-data", f"{APP_DIR / '.env'}{sep}.",
        str(MAIN_SCRIPT),
    ]
    
    result = subprocess.run(cmd, cwd=APP_DIR)
    
    if result.returncode == 0:
        exe_path = APP_DIR / "dist" / exe_name
        print(f"\n  ✓ Exécutable créé : {exe_path}")
        
        if sys.platform == "win32":
            startup_dir = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            bat_content = f'@echo off\nstart "" "{exe_path}"\n'
            bat_path = startup_dir / f"{APP_NAME}.bat"
            bat_path.write_text(bat_content, encoding="utf-8")
            print(f"  ✓ Démarrage automatique mis à jour pour pointer sur le .exe")
        else:
            autostart_dir = Path.home() / ".config" / "autostart"
            desktop_content = f"""[Desktop Entry]
Type=Application
Exec="{exe_path}"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=OmiAssistant
Comment=Assistant IA Personnel
"""
            desktop_path = autostart_dir / f"{APP_NAME}.desktop"
            desktop_path.write_text(desktop_content, encoding="utf-8")
            os.chmod(desktop_path, 0o755)
            print(f"  ✓ Démarrage automatique mis à jour pour pointer sur l'exécutable Linux")
    else:
        print("  ⚠ Erreur lors de la construction de l'exécutable")


def launch_now(venv_python_w):
    step("▶ Lancement de l'assistant")
    launch = input("  Lancer l'assistant maintenant ? (y/n) : ").strip().lower()
    if launch == "y":
        print("  Démarrage... (l'icône va apparaître dans la barre des tâches)")
        subprocess.Popen([str(venv_python_w), str(MAIN_SCRIPT)], 
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        print("  ✓ Assistant lancé !")


def main():
    print("\n" + "═"*50)
    print("   OMI ASSISTANT — INSTALLATION")
    print("═"*50)
    
    try:
        venv_python, venv_python_w = get_or_create_venv()
        install_dependencies(venv_python)
        setup_api_key()
        setup_autostart(venv_python, venv_python_w)
        build_exe(venv_python)
        launch_now(venv_python_w)
        
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
