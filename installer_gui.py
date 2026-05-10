"""
OMI Installer GUI
Ce script sera compilé en un seul EXE qui installe l'application,
configure la clé API, et crée les raccourcis.
"""

import os
import sys
import shutil
import ctypes
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

# On utilise winshell ou dispatch pour les raccourcis si dispo, 
# sinon on utilise un script VBS temporaire (méthode la plus robuste sans dépendances)
def create_shortcut(target, shortcut_path, work_dir):
    vbs = f'Set oWS = WScript.CreateObject("WScript.Shell") : sLinkFile = "{shortcut_path}" : Set oLink = oWS.CreateShortcut(sLinkFile) : oLink.TargetPath = "{target}" : oLink.WorkingDirectory = "{work_dir}" : oLink.Save'
    vbs_path = Path(os.environ["TEMP"]) / "shortcut.vbs"
    vbs_path.write_text(vbs, encoding="cp1252")
    os.system(f'cscript //nologo "{vbs_path}"')
    os.remove(vbs_path)

class InstallerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Installation de OMI")
        self.root.geometry("500x350")
        self.root.resizable(False, False)
        
        # Style
        self.bg = "#f0f0f0"
        self.root.configure(bg=self.bg)
        
        # Variables
        self.api_key = tk.StringVar()
        self.install_path = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "OMI"
        
        self._build_ui()

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#111111", height=80)
        header.pack(fill="x")
        tk.Label(header, text="OMI — Assistant IA", font=("Segoe UI", 16, "bold"), fg="white", bg="#111111").pack(pady=20)
        
        # Content
        content = tk.Frame(self.root, bg=self.bg, padx=30, pady=20)
        content.pack(fill="both", expand=True)
        
        tk.Label(content, text="Clé API Gemini :", font=("Segoe UI", 10), bg=self.bg).pack(anchor="w")
        tk.Entry(content, textvariable=self.api_key, font=("Segoe UI", 10), width=50).pack(pady=5)
        tk.Label(content, text="Tu peux en obtenir une gratuitement sur https://aistudio.google.com/apikey", 
                 font=("Segoe UI", 8), fg="#666666", bg=self.bg).pack(anchor="w")
        
        tk.Label(content, text=f"\nL'application sera installée dans :\n{self.install_path}", 
                 font=("Segoe UI", 9), bg=self.bg, justify="left").pack(anchor="w")
        
        # Progress (hidden at start)
        self.progress = ttk.Progressbar(content, orient="horizontal", length=400, mode="determinate")
        
        # Footer
        footer = tk.Frame(self.root, bg=self.bg, pady=20)
        footer.pack(fill="x")
        
        self.btn_install = tk.Button(footer, text="Installer maintenant", font=("Segoe UI", 10, "bold"), 
                                     bg="#111111", fg="white", padx=20, pady=5, command=self.install)
        self.btn_install.pack()

    def install(self):
        key = self.api_key.get().strip()
        if not key.startswith("AIza"):
            if not messagebox.askyesno("Attention", "La clé API semble invalide. Continuer quand même ?"):
                return
        
        self.btn_install.config(state="disabled")
        self.progress.pack(pady=10)
        self.root.update()

        try:
            # 1. Créer le dossier d'installation
            os.makedirs(self.install_path, exist_ok=True)
            self.progress['value'] = 20
            self.root.update()

            # 2. Déterminer où sont les fichiers (si compilé avec PyInstaller)
            # Dans un EXE --onefile, les fichiers sont dans sys._MEIPASS
            source_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
            
            # 3. Copier les fichiers
            # On simule la copie pour cet exemple, mais en réalité on copierait 
            # tout le contenu du bundle vers self.install_path
            # Pour l'instant, on suppose que l'assistant est déjà compilé sous le nom OMI.exe
            # ou qu'on installe les scripts.
            
            # NOTE: Dans un vrai setup.exe, on copierait l'EXE de l'appli.
            # Ici, on va copier les dossiers sources essentiels pour que l'appli tourne.
            for item in ['core', 'ui', 'main.py', 'config.py', 'omi_icon.ico']:
                src = source_dir / item
                dst = self.install_path / item
                if src.is_dir():
                    if dst.exists(): shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                elif src.exists():
                    shutil.copy2(src, dst)
            
            self.progress['value'] = 60
            self.root.update()

            # 4. Configurer la clé API dans le fichier .env
            env_file = self.install_path / ".env"
            env_file.write_text(f"GEMINI_API_KEY={key}\n", encoding="utf-8")

            # 5. Créer les raccourcis
            exe_target = self.install_path / "main.py" # Ou OMI.exe si compilé
            # Pour un script .py, on doit lancer avec python.exe (ou pythonw.exe)
            python_exe = sys.executable.replace("python.exe", "pythonw.exe")
            target_cmd = f'"{python_exe}" "{exe_target}"'
            
            desktop = Path(winshell_get_desktop())
            start_menu = Path(os.environ["PROGRAMDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            
            create_shortcut(python_exe, desktop / "OMI.lnk", self.install_path)
            # On ajoute l'argument du script via VBS est plus complexe, 
            # simplifions : on crée un petit .bat de lancement dans le dossier install
            launcher_bat = self.install_path / "launcher.vbs"
            launcher_bat.write_text(f'CreateObject("WScript.Shell").Run "pythonw.exe ""{exe_target}""", 0, False', encoding="utf-8")
            
            create_shortcut(launcher_bat, desktop / "OMI.lnk", self.install_path)
            create_shortcut(launcher_bat, start_menu / "OMI.lnk", self.install_path)

            self.progress['value'] = 100
            self.root.update()
            
            messagebox.showinfo("Succès", "OMI a été installé avec succès !\nDes raccourcis ont été créés sur le bureau et dans le menu Démarrer.")
            self.root.destroy()

        except Exception as e:
            messagebox.showerror("Erreur", f"Une erreur est survenue lors de l'installation :\n{e}")
            self.btn_install.config(state="normal")

def winshell_get_desktop():
    # Fallback si winshell non présent
    return os.path.join(os.environ['USERPROFILE'], 'Desktop')

if __name__ == "__main__":
    root = tk.Tk()
    app = InstallerApp(root)
    root.mainloop()
