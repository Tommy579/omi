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

def draw_omi_logo_canvas(canvas, cx, cy, size=28, color="#FFFFFF"):
    """Dessine le logo OMI (cercles concentriques) centré en (cx, cy)."""
    r1 = size
    r2 = size * 0.55
    r3 = size * 0.25
    canvas.create_oval(cx-r1, cy-r1, cx+r1, cy+r1, fill=color, outline="")
    canvas.create_oval(cx-r2, cy-r2, cx+r2, cy+r2, fill=BG, outline="")
    canvas.create_oval(cx-r3, cy-r3, cx+r3, cy+r3, fill=color, outline="")


def draw_step_indicator(parent, current_step: int, total_steps: int, bg: str) -> tk.Canvas:
    """Dessine un indicateur de progression par points.
    current_step commence à 1.
    Retourne le canvas créé."""
    W = total_steps * 20
    c = tk.Canvas(parent, width=W, height=10, bg=bg, highlightthickness=0)
    for i in range(total_steps):
        x = i * 20 + 5
        if i + 1 < current_step:
            # Étape passée : petit point plein
            c.create_oval(x-3, 2, x+3, 8, fill=ACCENT, outline="")
        elif i + 1 == current_step:
            # Étape courante : grand point
            c.create_oval(x-5, 0, x+5, 10, fill=ACCENT, outline="")
        else:
            # Étape future : point creux
            c.create_oval(x-3, 2, x+3, 8, fill="", outline="#333333", width=1)
    return c

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

        # Zone pour l'indicateur de progression (steps)
        self._step_indicator_zone = tk.Frame(root, bg=BG, height=20)
        self._step_indicator_zone.pack(fill="x", pady=(4, 0))
        self._current_step = 1
        self._total_steps = 4  # Accueil, Config IA, Persona, Installation
        self._refresh_step_indicator()

        self._build_step_welcome()

    def _refresh_step_indicator(self):
        """Redessine l'indicateur de progression en haut."""
        for w in self._step_indicator_zone.winfo_children():
            w.destroy()
        c = draw_step_indicator(self._step_indicator_zone,
                                self._current_step,
                                self._total_steps, BG)
        c.pack(pady=4)

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _build_step_welcome(self):
        self._current_step = 1
        self._refresh_step_indicator()
        self._clear_content()
        
        logo_canvas = tk.Canvas(self.content_frame, width=80, height=80,
                                bg=BG, highlightthickness=0)
        logo_canvas.pack(pady=(30, 8))
        draw_omi_logo_canvas(logo_canvas, 40, 40, size=30, color=ACCENT)

        tk.Label(self.content_frame, text="OMI",
                 font=("Segoe UI", 28, "bold"), fg=ACCENT, bg=BG).pack()
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
        self._current_step = 2
        self._refresh_step_indicator()
        self._clear_content()

        tk.Label(self.content_frame, text="Configuration IA",
                 font=("Segoe UI", 18, "bold"), fg=ACCENT, bg=BG).pack(pady=(20, 16))

        # Clé API
        tk.Label(self.content_frame, text="Clé API Gemini",
                 font=("Segoe UI", 10), fg=FG_SEC, bg=BG).pack(anchor="w")

        key_frame = tk.Frame(self.content_frame, bg=SURFACE,
                             highlightthickness=1,
                             highlightbackground=BORDER)
        key_frame.pack(fill="x", pady=(4, 2))

        self._key_show = False
        self._key_entry = tk.Entry(key_frame, textvariable=self.api_key,
                                   font=("Segoe UI", 10),
                                   bg=SURFACE, fg=ACCENT,
                                   insertbackground=ACCENT,
                                   bd=0, show="•")
        self._key_entry.pack(side="left", fill="x", expand=True,
                             padx=8, pady=7)

        eye_btn = tk.Label(key_frame, text="◉", font=("Segoe UI", 10),
                           fg=FG_SEC, bg=SURFACE, cursor="hand2")
        eye_btn.pack(side="right", padx=8)
        eye_btn.bind("<Button-1>", self._toggle_key_visibility)

        link = tk.Label(self.content_frame,
                        text="Obtenir une clé gratuite sur Google AI Studio",
                        font=("Segoe UI", 8, "underline"), fg=FG_SEC,
                        bg=BG, cursor="hand2")
        link.pack(anchor="w", pady=(2, 16))
        link.bind("<Button-1>",
                  lambda e: os.startfile("https://aistudio.google.com/apikey"))

        # Sélection modèle par cartes
        tk.Label(self.content_frame, text="Modèle Gemini",
                 font=("Segoe UI", 10), fg=FG_SEC, bg=BG).pack(anchor="w", pady=(0, 6))

        self._model_cards = {}
        for label, model_id in MODELS:
            card = tk.Canvas(self.content_frame, bg=BG,
                             highlightthickness=0, height=44, cursor="hand2")
            card.pack(fill="x", pady=2)
            is_sel = model_id == self.selected_model
            self._draw_model_card(card, label, model_id, is_sel)
            card.bind("<Button-1>",
                      lambda e, m=model_id, c=card: self._select_model(m, c))
            self._model_cards[model_id] = card

        btn_frame = tk.Frame(self.content_frame, bg=BG)
        btn_frame.pack(side="bottom", fill="x", pady=20)
        tk.Button(btn_frame, text="Continuer →",
                  font=("Segoe UI", 11, "bold"), bg=ACCENT, fg=BG,
                  bd=0, padx=20, pady=10, cursor="hand2",
                  command=self._build_step_persona).pack(side="right")

    def _toggle_key_visibility(self, event=None):
        self._key_show = not self._key_show
        self._key_entry.config(show="" if self._key_show else "•")

    def _draw_model_card(self, canvas, label, model_id, selected):
        canvas.delete("all")
        canvas.update()
        w = canvas.winfo_width() or 420
        h = 42
        bg_color = "#1E1E1E" if selected else SURFACE
        border_color = ACCENT if selected else BORDER
        pts = [8,0, w-8,0, w,0, w,8, w,h-8, w,h, w-8,h, 8,h, 0,h, 0,h-8, 0,8, 0,0]
        canvas.create_polygon(pts, smooth=True, fill=bg_color,
                              outline=border_color,
                              width=2 if selected else 1)
        dot = ACCENT if selected else "#333333"
        canvas.create_oval(14, 17, 24, 27, fill=dot, outline="")
        canvas.create_text(34, 21, text=label,
                           font=("Segoe UI", 9, "bold" if selected else "normal"),
                           fill=ACCENT if selected else "#AAAAAA",
                           anchor="w")

    def _select_model(self, model_id, clicked_card):
        self.selected_model = model_id
        for mid, card in self._model_cards.items():
            label = next(m[0] for m in MODELS if m[1] == mid)
            self._draw_model_card(card, label, mid, mid == self.selected_model)

    def _on_model_change(self, val):
        self.selected_model = next(m[1] for m in MODELS if m[0] == val)

    def _build_step_persona(self):
        """Étape 2b : Choix de l'objectif d'OMI."""
        self._current_step = 3
        self._refresh_step_indicator()
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
        self._current_step = 4
        self._refresh_step_indicator()
        self._clear_content()

        tk.Label(self.content_frame, text="Installation",
                 font=("Segoe UI", 18, "bold"), fg=ACCENT, bg=BG).pack(pady=(20, 10))

        # Log animé (remplace la barre de progression)
        self.log_text = tk.Text(self.content_frame, height=10, bg=BG,
                                fg=FG_SEC, font=("Consolas", 9),
                                bd=0, highlightthickness=0, padx=10)
        self.log_text.pack(fill="x", pady=20)
        self.log_text.config(state="disabled")

        self.btn_install = tk.Button(self.content_frame,
                                     text="Lancer l'installation",
                                     font=("Segoe UI", 11, "bold"),
                                     bg=ACCENT, fg=BG, bd=0, padx=20, pady=10,
                                     cursor="hand2",
                                     command=self.run_installation)
        self.btn_install.pack(side="bottom", pady=40)

    def log(self, msg: str):
        """Ajoute une ligne au log avec un petit effet 'typing'."""
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"> {msg}\n")
        self.log_text.config(state="disabled")
        self.log_text.see("end")
        self.root.update()

    def run_installation(self):
        key = self.api_key.get().strip()
        if not key.startswith("AIza"):
            if not messagebox.askyesno("Attention", "La clé API semble incorrecte. Continuer ?") :
                return

        self.btn_install.config(state="disabled")
        self.log("Démarrage de l'installation...")

        try:
            # 1. Préparation du dossier
            if self.install_path.exists():
                self.log("Mise à jour d'une installation existante...")
                for item in self.install_path.iterdir():
                    if item.name in ["omi_profile.json", ".env", "omi_history.db"]:
                        continue
                    try:
                        if item.is_file(): item.unlink()
                        elif item.is_dir(): shutil.rmtree(item)
                    except: pass
            
            os.makedirs(self.install_path, exist_ok=True)
            self.log("Dossiers créés.")

            # 2. Copie des fichiers
            source_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
            exe_name = "OmiAssistant.exe"
            
            self.log("Copie de l'exécutable principal...")
            if (source_dir / exe_name).exists():
                shutil.copy2(source_dir / exe_name, self.install_path / exe_name)
            elif Path("dist/OmiAssistant.exe").exists():
                shutil.copy2("dist/OmiAssistant.exe", self.install_path / exe_name)

            if (source_dir / "omi_icon.ico").exists():
                shutil.copy2(source_dir / "omi_icon.ico", self.install_path / "omi_icon.ico")
            
            # 3. Configuration (.env)
            self.log("Configuration des variables d'environnement...")
            env_file = self.install_path / ".env"
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

            # 4. Raccourcis
            self.log("Création des raccourcis Bureau et Démarrage...")
            desktop = Path(os.path.join(os.environ['USERPROFILE'], 'Desktop'))
            start_menu = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs"
            startup = start_menu / "Startup"
            
            target = self.install_path / exe_name
            create_shortcut(str(target), desktop / "OMI.lnk", str(self.install_path))
            create_shortcut(str(target), start_menu / "OMI.lnk", str(self.install_path))
            create_shortcut(str(target), startup / "OMI.lnk", str(self.install_path))

            self.log("Installation terminée avec succès.")
            self.root.after(1000, self._build_step_success)

        except Exception as e:
            self.log(f"ERREUR : {str(e)}")
            messagebox.showerror("Erreur", f"L'installation a échoué : {e}")
            self.btn_install.config(state="normal")

    def _build_step_success(self):
        self._clear_content()
        self._step_indicator_zone.pack_forget()

        logo_canvas = tk.Canvas(self.content_frame, width=80, height=80, bg=BG, highlightthickness=0)
        logo_canvas.pack(pady=(60, 10))
        draw_omi_logo_canvas(logo_canvas, 40, 40, size=30, color=ACCENT)

        tk.Label(self.content_frame, text="OMI est prêt !",
                 font=("Segoe UI", 22, "bold"), fg=ACCENT, bg=BG).pack()
        
        tk.Label(self.content_frame,
                 text="L'assistant est installé et configuré.\nIl va maintenant se lancer.",
                 font=("Segoe UI", 10), fg=FG_SEC, bg=BG, pady=20).pack()

        tk.Button(self.content_frame, text="Terminer",
                  font=("Segoe UI", 11, "bold"), bg=ACCENT, fg=BG,
                  bd=0, padx=40, pady=10, cursor="hand2",
                  command=self._finish).pack(side="bottom", pady=40)

    def _finish(self):
        target = self.install_path / "OmiAssistant.exe"
        if target.exists():
            os.startfile(target)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = InstallerApp(root)
    root.mainloop()
