"""
OMI Installer GUI
Ce script est compilé en OMI_Setup.exe.
Il installe l'exécutable OmiAssistant.exe, configure la clé API, l'objectif et crée les raccourcis.
"""

import os
import sys
import shutil
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

# --- CONFIGURATION VISUELLE ---
BG = "#0A0A0A"
SURFACE = "#161616"
ACCENT = "#FFFFFF"
FG_SEC = "#888888"
BORDER = "#222222"

# --- PERSONAS ---
PERSONAS = [
    {
        "id": "developer",
        "title": "Développeur",
        "subtitle": "Aide au code, détection d'erreurs, optimisations, review",
        "objective": (
            "L'utilisateur est développeur. Tu dois surveiller son code en permanence : "
            "détecter les erreurs, bugs, et mauvaises pratiques dès qu'ils apparaissent à l'écran. "
            "Propose des corrections concrètes et courtes. Si tu vois un message d'erreur dans un terminal, "
            "donne la cause et le fix immédiatement. Signale les opportunités d'optimisation dans le code ouvert. "
            "Tu connais tous les langages de programmation et frameworks courants."
        ),
    },
    {
        "id": "student",
        "title": "Étudiant",
        "subtitle": "Concentration, aide aux devoirs, résumés, Pomodoro",
        "objective": (
            "L'utilisateur est étudiant. Ton rôle principal est de l'aider à rester concentré sur ses révisions. "
            "Si tu le vois sur des réseaux sociaux ou des vidéos non liées à ses études, rappelle-le doucement à l'ordre. "
            "Si tu vois un exercice, un QCM ou une question ouverte à l'écran, propose une réponse ou un indice. "
            "Aide-le à résumer les documents qu'il lit. Suggère des pauses régulières (toutes les 45 minutes)."
        ),
    },
    {
        "id": "creative",
        "title": "Créatif",
        "subtitle": "Design, écriture, musique, feedback sur les créations",
        "objective": (
            "L'utilisateur est un créatif (designer, écrivain, musicien, vidéaste). "
            "Donne-lui du feedback constructif sur ce que tu vois à l'écran : compositions visuelles, "
            "textes en cours d'écriture, interfaces en design. Propose des idées, alternatives, sources d'inspiration. "
            "Sois encourageant mais honnête. Si tu vois qu'il tourne en rond sur un même élément depuis un moment, "
            "suggère de prendre du recul ou d'essayer une approche différente."
        ),
    },
    {
        "id": "manager",
        "title": "Manager / Productivité",
        "subtitle": "Emails, réunions, organisation, suivi des tâches",
        "objective": (
            "L'utilisateur travaille sur des tâches de management et productivité : emails, documents, "
            "planification, réunions. Aide-le à rédiger des messages clairs et concis. Si tu vois un email "
            "long à l'écran, propose un résumé ou une reformulation plus efficace. Rappelle-lui les deadlines "
            "si tu les détectes dans ses documents. Signale si une réunion approche si tu vois son calendrier."
        ),
    },
    {
        "id": "streamer",
        "title": "Streamer / Créateur de contenu",
        "subtitle": "OBS, stream, YouTube, engagement, idées de contenu",
        "objective": (
            "L'utilisateur crée du contenu (streaming, YouTube, podcasts, réseaux sociaux). "
            "Aide-le à surveiller son stream (alertes, chat visible à l'écran). Propose des idées de contenu "
            "basées sur ses centres d'intérêt. Si tu vois OBS ou un logiciel de streaming à l'écran, "
            "tu peux commenter la qualité de la mise en scène. Aide-le à rédiger des descriptions, titres, "
            "et hashtags pour ses publications."
        ),
    },
    {
        "id": "custom",
        "title": "Personnalisé",
        "subtitle": "Décris toi-même ce que tu veux qu'OMI fasse",
        "objective": None,  # Rempli par le champ libre
    },
]

MODELS = [
    ("Gemini 3.1 Flash Lite (Rapide, recommandé)", "models/gemini-3.1-flash-lite"),
    ("Gemini 2.0 Flash (Équilibré)", "models/gemini-2.0-flash"),
    ("Gemini 2.0 Pro (Performant)", "models/gemini-2.0-pro-exp-02-05")
]

def create_shortcut(target, shortcut_path, work_dir):
    """Crée un raccourci (Windows Lnk ou Linux Desktop)"""
    try:
        if sys.platform == "win32":
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
        else:
            desktop_entry = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=OMI\n"
                f"Exec=\"{target}\"\n"
                f"Path={work_dir}\n"
                "Icon=omi_icon\n"
                "Terminal=false\n"
                "Categories=Utility;Application;\n"
            )
            shortcut_path = Path(shortcut_path)
            shortcut_path.parent.mkdir(parents=True, exist_ok=True)
            shortcut_path.write_text(desktop_entry, encoding="utf-8")
            os.chmod(shortcut_path, 0o755)
    except Exception as e:
        print(f"Erreur raccourci : {e}")

class InstallerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OMI Setup")
        self.root.geometry("500x580")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # Variables
        self.api_key = tk.StringVar()
        self.selected_model = MODELS[0][1]
        self.selected_persona_id = "developer"
        self.custom_objective = tk.StringVar()
        if sys.platform == "win32":
            self.install_path = Path(os.environ.get("LOCALAPPDATA", "~/.local/share")) / "Programs" / "OMI"
        else:
            self.install_path = Path.home() / ".local" / "share" / "omi"
        
        # UI Setup
        self.header_frame = tk.Frame(root, bg=BG, height=60)
        self.header_frame.pack(fill="x")
        
        self.content_frame = tk.Frame(root, bg=BG, padx=40)
        self.content_frame.pack(fill="both", expand=True)

        self._build_step_welcome()

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _build_step_welcome(self):
        self._clear_content()
        
        tk.Label(self.content_frame, text="OMI", font=("Segoe UI", 32, "bold"), fg=ACCENT, bg=BG).pack(pady=(40, 10))
        tk.Label(self.content_frame, text="Open Mind Interface", font=("Segoe UI", 12), fg=FG_SEC, bg=BG).pack()
        
        desc = (
            "OMI est ton assistant IA proactif.\n"
            "Il observe ton écran pour t'aider en temps réel."
        )
        tk.Label(self.content_frame, text=desc, font=("Segoe UI", 10), fg=FG_SEC, bg=BG, pady=30).pack()

        tk.Button(self.content_frame, text="Commencer la configuration →", 
                  font=("Segoe UI", 11, "bold"), bg=ACCENT, fg=BG, bd=0, padx=20, pady=10, 
                  cursor="hand2", command=self._build_step_model).pack(side="bottom", pady=40)

    def _build_step_model(self):
        self._clear_content()

        tk.Label(self.content_frame, text="Configuration IA", font=("Segoe UI", 18, "bold"), fg=ACCENT, bg=BG).pack(pady=(20, 20))
        
        tk.Label(self.content_frame, text="Clé API Gemini :", font=("Segoe UI", 10), fg=ACCENT, bg=BG).pack(anchor="w")
        entry = tk.Entry(self.content_frame, textvariable=self.api_key, font=("Segoe UI", 10), 
                         bg=SURFACE, fg=ACCENT, insertbackground=ACCENT, bd=0, highlightthickness=1, highlightbackground=BORDER)
        entry.pack(fill="x", pady=(5, 2))
        
        link = tk.Label(self.content_frame, text="Obtenir une clé gratuite sur Google AI Studio", 
                        font=("Segoe UI", 8, "underline"), fg=FG_SEC, bg=BG, cursor="hand2")
        link.pack(anchor="w", pady=(0, 20))
        import webbrowser
        link.bind("<Button-1>", lambda e: webbrowser.open("https://aistudio.google.com/apikey"))

        tk.Label(self.content_frame, text="Modèle Gemini :", font=("Segoe UI", 10), fg=ACCENT, bg=BG).pack(anchor="w")
        
        self.model_var = tk.StringVar(value=MODELS[0][0])
        model_menu = tk.OptionMenu(self.content_frame, self.model_var, *[m[0] for m in MODELS], command=self._on_model_change)
        model_menu.config(bg=SURFACE, fg=ACCENT, bd=0, highlightthickness=1, highlightbackground=BORDER, font=("Segoe UI", 9))
        model_menu["menu"].config(bg=SURFACE, fg=ACCENT)
        model_menu.pack(fill="x", pady=5)

        # Boutons
        btn_frame = tk.Frame(self.content_frame, bg=BG)
        btn_frame.pack(side="bottom", fill="x", pady=20)
        
        tk.Button(btn_frame, text="Continuer →", font=("Segoe UI", 11, "bold"), bg=ACCENT, fg=BG, bd=0, padx=20, pady=10, 
                  cursor="hand2", command=self._build_step_persona).pack(side="right")

    def _on_model_change(self, val):
        self.selected_model = next(m[1] for m in MODELS if m[0] == val)

    def _build_step_persona(self):
        """Étape 2b : Choix de l'objectif d'OMI."""
        self._clear_content()

        tk.Label(self.content_frame, text="À quoi doit servir OMI ?",
                 font=("Segoe UI", 16, "bold"), fg=ACCENT, bg=BG).pack(pady=(0, 4))
        tk.Label(self.content_frame,
                 text="Adapte le comportement d'OMI à ton usage principal.",
                 font=("Segoe UI", 10), fg=FG_SEC, bg=BG).pack(pady=(0, 16))

        self._persona_cards = {}
        cards_frame = tk.Frame(self.content_frame, bg=BG)
        cards_frame.pack(fill="x")

        for persona in PERSONAS:
            card = tk.Canvas(cards_frame, bg=BG, highlightthickness=0,
                             height=56, cursor="hand2")
            card.pack(fill="x", pady=3)

            is_selected = persona["id"] == self.selected_persona_id
            self._draw_persona_card(card, persona, is_selected)
            card.bind("<Button-1>", lambda e, p=persona, c=card: self._select_persona(p, c))
            self._persona_cards[persona["id"]] = card

        # Champ libre (visible uniquement si "custom" sélectionné)
        self.custom_frame = tk.Frame(self.content_frame, bg=BG)
        tk.Label(self.custom_frame, text="Décris l'objectif d'OMI :",
                 font=("Segoe UI", 10), fg=FG_SEC, bg=BG).pack(anchor="w", pady=(8, 2))
        self.custom_entry_text = tk.Text(self.custom_frame, font=("Segoe UI", 10),
                               bg=SURFACE, fg=ACCENT, insertbackground=ACCENT,
                               bd=0, highlightthickness=1, highlightbackground=BORDER,
                               height=4, wrap="word")
        self.custom_entry_text.pack(fill="x")
        self.custom_entry_text.bind("<KeyRelease>",
                          lambda e: self.custom_objective.set(self.custom_entry_text.get("1.0", "end-1c")))

        if self.selected_persona_id == "custom":
            self.custom_frame.pack(fill="x", pady=(4, 0))

        # Boutons
        btn_frame = tk.Frame(self.content_frame, bg=BG)
        btn_frame.pack(side="bottom", fill="x", pady=(16, 0))

        tk.Label(btn_frame, text="← Retour", font=("Segoe UI", 10),
                 fg=FG_SEC, bg=BG, cursor="hand2").pack(side="left")
        btn_frame.winfo_children()[0].bind("<Button-1>", lambda e: self._build_step_model())

        tk.Button(btn_frame, text="Continuer →",
                  font=("Segoe UI", 11, "bold"),
                  bg=ACCENT, fg=BG, bd=0, padx=20, pady=8,
                  cursor="hand2",
                  command=self._on_persona_next).pack(side="right")


    def _draw_persona_card(self, canvas, persona, selected):
        """Dessine une carte de persona sur le canvas."""
        canvas.delete("all")
        # Forcer un rendu pour avoir la largeur réelle
        canvas.update()
        w = canvas.winfo_width() or 420
        h = 54
        bg_color = "#222222" if selected else SURFACE
        border_color = ACCENT if selected else BORDER
        border_w = 2 if selected else 1

        # Fond arrondi
        pts = [
            8, 0,   w-8, 0,
            w, 0,   w, 8,
            w, h-8, w, h,
            w-8, h, 8, h,
            0, h,   0, h-8,
            0, 8,   0, 0,
        ]
        canvas.create_polygon(pts, smooth=True, fill=bg_color,
                              outline=border_color, width=border_w)

        # Indicateur sélection
        dot_color = ACCENT if selected else "#444444"
        canvas.create_oval(16, 19, 28, 31, fill=dot_color, outline="")

        # Texte
        canvas.create_text(44, 18, text=persona["title"],
                           font=("Segoe UI", 10, "bold"),
                           fill=ACCENT if selected else "#CCCCCC",
                           anchor="w")
        canvas.create_text(44, 36, text=persona["subtitle"],
                           font=("Segoe UI", 9),
                           fill=FG_SEC,
                           anchor="w")


    def _select_persona(self, persona, clicked_card):
        """Sélectionne un persona et redessine toutes les cartes."""
        self.selected_persona_id = persona["id"]
        for pid, card in self._persona_cards.items():
            p = next(p for p in PERSONAS if p["id"] == pid)
            self._draw_persona_card(card, p, pid == self.selected_persona_id)

        # Afficher/masquer le champ custom
        if persona["id"] == "custom":
            self.custom_frame.pack(fill="x", pady=(4, 0))
        else:
            self.custom_frame.pack_forget()


    def _on_persona_next(self):
        """Valide la sélection du persona et passe à l'installation."""
        if self.selected_persona_id == "custom":
            obj = self.custom_objective.get().strip()
            if len(obj) < 20:
                messagebox.showwarning("Objectif trop court", "Merci de décrire ton objectif en au moins 20 caractères.")
                return
        self._build_step_install()

    def _build_step_install(self):
        self._clear_content()

        tk.Label(self.content_frame, text="Prêt pour l'installation", font=("Segoe UI", 18, "bold"), fg=ACCENT, bg=BG).pack(pady=(40, 10))
        
        info = (
            f"Clé API : {'Définie' if self.api_key.get() else 'Manquante'}\n"
            f"Modèle : {self.selected_model.split('/')[-1]}\n"
            f"Persona : {self.selected_persona_id}\n\n"
            f"Installation dans :\n{self.install_path}"
        )
        tk.Label(self.content_frame, text=info, font=("Segoe UI", 10), fg=FG_SEC, bg=BG, justify="left").pack(pady=20)

        self.progress = ttk.Progressbar(self.content_frame, orient="horizontal", length=300, mode="determinate")
        self.progress.pack(pady=20)

        self.btn_install = tk.Button(self.content_frame, text="Installer maintenant", font=("Segoe UI", 11, "bold"), 
                                     bg=ACCENT, fg=BG, bd=0, padx=20, pady=10, cursor="hand2", command=self.run_installation)
        self.btn_install.pack(side="bottom", pady=40)

    def run_installation(self):
        key = self.api_key.get().strip()
        if not key.startswith("AIza"):
            if not messagebox.askyesno("Attention", "La clé API semble incorrecte. Continuer ?"):
                return

        self.btn_install.config(state="disabled")
        self.root.update()

        try:
            # 1. Préparation du dossier (Nettoyage intelligent)
            if self.install_path.exists():
                # On ne supprime pas tout le dossier pour garder le .json et le .env
                # On supprime seulement les anciens binaires et dossiers temporaires
                for item in self.install_path.iterdir():
                    if item.name in ["omi_profile.json", ".env", "omi_history.db"]:
                        continue # Préserver la mémoire et la config
                    try:
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    except Exception as e:
                        print(f"Impossible de supprimer {item.name}: {e}")

            os.makedirs(self.install_path, exist_ok=True)
            self.progress['value'] = 20
            self.root.update()

            # 2. Dossier source (fichiers embarqués dans le Setup)
            source_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
            exe_name = "OmiAssistant.exe" if sys.platform == "win32" else "OmiAssistant"
            icon_name = "omi_icon.ico"
 
            # 3. Copier l'exécutable et l'icône
            if (source_dir / exe_name).exists():
                shutil.copy2(source_dir / exe_name, self.install_path / exe_name)
            else:
                # Fallback pour le dev si on lance le script tel quel
                fallback_path = Path("dist") / exe_name
                if fallback_path.exists():
                    shutil.copy2(fallback_path, self.install_path / exe_name)
 
            if (source_dir / icon_name).exists():
                shutil.copy2(source_dir / icon_name, self.install_path / icon_name)

            self.progress['value'] = 60
            self.root.update()

            # 4. Gérer le fichier .env (préserver ou créer)
            env_file = self.install_path / ".env"
            if not env_file.exists():
                # Résoudre l'objectif selon le persona sélectionné
                if self.selected_persona_id == "custom":
                    objective = self.custom_objective.get().strip()
                else:
                    persona = next(p for p in PERSONAS if p["id"] == self.selected_persona_id)
                    objective = persona["objective"]

                env_content = (
                    f"GEMINI_API_KEY={key}\n"
                    f"GEMINI_MODEL={self.selected_model}\n"
                    f"OMI_PERSONA={self.selected_persona_id}\n"
                    f"OMI_OBJECTIVE={objective}\n"
                )
                env_file.write_text(env_content, encoding="utf-8")
            else:
                # Mettre à jour seulement la clé si elle a changé dans l'installeur
                old_content = env_file.read_text(encoding="utf-8")
                if key and key not in old_content:
                    # Remplacement simple de la clé
                    import re
                    new_content = re.sub(r"GEMINI_API_KEY=.*", f"GEMINI_API_KEY={key}", old_content)
                    env_file.write_text(new_content, encoding="utf-8")

            # 5. Raccourcis
            if sys.platform == "win32":
                desktop = Path(os.path.join(os.environ['USERPROFILE'], 'Desktop'))
                start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"     
                startup_dir = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
                shortcut_ext = ".lnk"
            else:
                desktop = Path.home() / "Desktop"
                start_menu = Path.home() / ".local" / "share" / "applications"
                startup_dir = Path.home() / ".config" / "autostart"
                shortcut_ext = ".desktop"
 
            target_exe = self.install_path / exe_name
 
            create_shortcut(str(target_exe), desktop / f"OMI{shortcut_ext}", str(self.install_path))
            create_shortcut(str(target_exe), start_menu / f"OMI{shortcut_ext}", str(self.install_path))
            create_shortcut(str(target_exe), startup_dir / f"OMI{shortcut_ext}", str(self.install_path))
 
            self.progress['value'] = 100
            self.root.update()
 
            messagebox.showinfo("Succès", "OMI a été mis à jour !\n\nL'assistant se lancera automatiquement au démarrage.\nTes données et ton profil ont été conservés.")
            if sys.platform == "win32":
                os.startfile(target_exe)
            else:
                import subprocess
                subprocess.Popen([str(target_exe)])
            self.root.destroy()

        except Exception as e:
            messagebox.showerror("Erreur", f"L'installation a échoué : {e}")
            self.btn_install.config(state="normal")
if __name__ == "__main__":
    root = tk.Tk()
    app = InstallerApp(root)
    root.mainloop()
