"""
OMI Installer GUI
Ce script est compilé en OMI_Setup.exe.
Il installe l'exécutable OmiAssistant.exe, configure la clé API et crée les raccourcis.
"""

import os
import sys
import shutil
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

def create_shortcut(target, shortcut_path, work_dir):
    """Crée un raccourci Windows via un script VBS temporaire"""
    try:
        vbs = (
            f'Set oWS = WScript.CreateObject("WScript.Shell")\n'
            f'sLinkFile = "{shortcut_path}"\n'
            f'Set oLink = oWS.CreateShortcut(sLinkFile)\n'
            f'oLink.TargetPath = "{target}"\n'
            f'oLink.WorkingDirectory = "{work_dir}"\n'
            f'oLink.Save'
        )
        vbs_path = Path(os.environ["TEMP"]) / "shortcut.vbs"
        vbs_path.write_text(vbs, encoding="cp1252")
        os.system(f'cscript //nologo "{vbs_path}"')
        os.remove(vbs_path)
    except Exception as e:
        print(f"Erreur raccourci : {e}")

class InstallerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Installation de OMI")
        self.root.geometry("500x400")
        self.root.resizable(False, False)
        
        # Style
        self.bg = "#f0f0f0"
        self.root.configure(bg=self.bg)
        
        # Variables
        self.api_key = tk.StringVar()
        # Installation dans le dossier utilisateur pour éviter les problèmes de droits admin
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
        
        tk.Label(content, text="Bienvenue dans l'installeur de OMI.", font=("Segoe UI", 10, "bold"), bg=self.bg).pack(anchor="w", pady=(0, 10))
        
        tk.Label(content, text="Clé API Gemini :", font=("Segoe UI", 10), bg=self.bg).pack(anchor="w")
        self.entry_key = tk.Entry(content, textvariable=self.api_key, font=("Segoe UI", 10), width=50)
        self.entry_key.pack(pady=5)
        
        tk.Label(content, text="Obtiens ta clé gratuitement sur :", font=("Segoe UI", 8), bg=self.bg).pack(anchor="w")
        link = tk.Label(content, text="https://aistudio.google.com/apikey", font=("Segoe UI", 8, "underline"), fg="blue", bg=self.bg, cursor="hand2")
        link.pack(anchor="w")
        link.bind("<Button-1>", lambda e: os.startfile("https://aistudio.google.com/apikey"))
        
        tk.Label(content, text=f"\nL'application sera installée dans :\n{self.install_path}", 
                 font=("Segoe UI", 9), bg=self.bg, justify="left").pack(anchor="w", pady=10)
        
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
            if not messagebox.askyesno("Attention", "La clé API semble incorrecte. Continuer ?"):
                return
        
        self.btn_install.config(state="disabled")
        self.entry_key.config(state="disabled")
        self.progress.pack(pady=10)
        self.root.update()

        try:
            # 1. Créer le dossier d'installation
            os.makedirs(self.install_path, exist_ok=True)
            self.progress['value'] = 20
            self.root.update()

            # 2. Dossier source (fichiers embarqués dans le Setup.exe)
            source_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
            
            exe_name = "OmiAssistant.exe"
            icon_name = "omi_icon.ico"

            # 3. Copier l'exécutable de l'assistant
            if (source_dir / exe_name).exists():
                shutil.copy2(source_dir / exe_name, self.install_path / exe_name)
            else:
                raise FileNotFoundError(f"Impossible de trouver {exe_name} dans le package d'installation.")

            if (source_dir / icon_name).exists():
                shutil.copy2(source_dir / icon_name, self.install_path / icon_name)
            
            self.progress['value'] = 60
            self.root.update()

            # 4. Créer le fichier .env avec la clé fournie
            env_file = self.install_path / ".env"
            env_file.write_text(f"GEMINI_API_KEY={key}\n", encoding="utf-8")

            # 5. Créer les raccourcis
            desktop = Path(os.path.join(os.environ['USERPROFILE'], 'Desktop'))
            start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            
            target_exe = self.install_path / exe_name
            
            create_shortcut(str(target_exe), desktop / "OMI.lnk", str(self.install_path))
            create_shortcut(str(target_exe), start_menu / "OMI.lnk", str(self.install_path))

            # 6. Optionnel : Ajout au démarrage automatique (Registry ou dossier Startup)
            startup_dir = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            create_shortcut(str(target_exe), startup_dir / "OMI.lnk", str(self.install_path))

            self.progress['value'] = 100
            self.root.update()
            
            messagebox.showinfo("Succès", "OMI a été installé !\n\nL'assistant se lancera automatiquement au démarrage.\nTu peux aussi le lancer depuis le raccourci sur ton bureau.")
            
            # Lancer l'appli immédiatement
            os.startfile(target_exe)
            self.root.destroy()

        except Exception as e:
            messagebox.showerror("Erreur d'installation", f"Détails : {e}")
            self.btn_install.config(state="normal")
            self.entry_key.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    # Icône de la fenêtre si dispo
    source_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    if (source_dir / "omi_icon.ico").exists():
        root.iconbitmap(str(source_dir / "omi_icon.ico"))
    
    app = InstallerApp(root)
    root.mainloop()
