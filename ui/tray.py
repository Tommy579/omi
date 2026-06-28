"""
Interface utilisateur :
- Icône dans la barre des tâches (system tray)
- Popup avec coins arrondis globaux, thème cohérent, chat intégré
- Filigrane (watermark) transparent pour le dernier message lors de la réduction
"""

import threading
import tkinter as tk
from tkinter import scrolledtext
import pystray
from PIL import Image, ImageDraw
try:
    import winreg
except ImportError:
    winreg = None

# ─────────────────────────────────────────────────────────
# Thème
# ─────────────────────────────────────────────────────────

def get_windows_theme():
    if not winreg:
        return "dark"
    try:
        reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(reg, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"

import tkinter.font as tkfont

def _resolve_font() -> str:
    try:
        preferred = [
            "Söhne", "Segoe UI Variable Display", "Segoe UI Variable",
            "Inter", "Segoe UI", "Helvetica Neue", "Ubuntu",
        ]
        available = tkfont.families()
        for f in preferred:
            if f in available:
                return f
    except Exception:
        pass
    return "Segoe UI"

FONT = "Segoe UI"

THEMES = {
    "dark": {
        "bg":           "#0F0F0F",
        "surface":      "#1A1A1A",
        "surface2":     "#222222",
        "input_bg":     "#181818",
        "border":       "#2A2A2A",
        "border_focus": "#444444",
        "fg":           "#EFEFEF",
        "fg_sec":       "#666666",
        "fg_ter":       "#444444",
        "fg_omi":       "#FFFFFF",
        "accent":       "#FFFFFF",
        "accent_dim":   "#CCCCCC",
        "bubble_omi":   "#1E1E1E",
        "bubble_user":  "#2A2A2A",
        "dot_active":   "#FFFFFF",
        "dot_inactive": "#333333",
        "badge_bg":     "#252525",
        "badge_fg":     "#666666",
        "btn_bg":       "#1A1A1A",
        "btn_hover":    "#252525",
        "border_line":  "#2A2A2A",
        "scrollbar":    "#2A2A2A",
        "scrollbar_hover": "#3A3A3A",
        "send_btn_bg":    "#1A3A5C",
        "send_btn_fg":    "#7BB8F0",
        "send_btn_hover": "#1E4A7A",
    },
    "light": {
        "bg":           "#F2F2F2",
        "surface":      "#FFFFFF",
        "surface2":     "#F8F8F8",
        "input_bg":     "#EBEBEB",
        "border":       "#E0E0E0",
        "border_focus": "#BBBBBB",
        "fg":           "#111111",
        "fg_sec":       "#999999",
        "fg_ter":       "#CCCCCC",
        "fg_omi":       "#111111",
        "accent":       "#000000",
        "accent_dim":   "#444444",
        "bubble_omi":   "#F0F0F0",
        "bubble_user":  "#E8E8E8",
        "dot_active":   "#000000",
        "dot_inactive": "#DDDDDD",
        "badge_bg":     "#EEEEEE",
        "badge_fg":     "#AAAAAA",
        "btn_bg":       "#FFFFFF",
        "btn_hover":    "#F0F0F0",
        "border_line":  "#E0E0E0",
        "scrollbar":    "#DDDDDD",
        "scrollbar_hover": "#CCCCCC",
        "send_btn_bg":    "#1A5CCC",
        "send_btn_fg":    "#FFFFFF",
        "send_btn_hover": "#1A4FB0",
    },
}

# Couleur "magique" utilisée comme transparence pour les coins de la fenêtre
# Doit être une couleur qui n'apparaît nulle part dans l'UI
CHROMA = "#010203"



# ─────────────────────────────────────────────────────────
# Helpers Canvas
# ─────────────────────────────────────────────────────────

def rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    pts = [
        x1+r, y1,  x2-r, y1,
        x2,   y1,  x2,   y1+r,
        x2,   y2-r,x2,   y2,
        x2-r, y2,  x1+r, y2,
        x1,   y2,  x1,   y2-r,
        x1,   y1+r,x1,   y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kwargs)


def draw_omi_logo(canvas, cx, cy, size=10, color="#FFFFFF"):
    """Dessine le logo OMI (3 cercles concentriques) centré en (cx, cy)."""
    r1, r2, r3 = size, size * 0.55, size * 0.25
    canvas.create_oval(cx-r1, cy-r1, cx+r1, cy+r1, fill=color, outline="")
    canvas.create_oval(cx-r2, cy-r2, cx+r2, cy+r2, fill=canvas["bg"], outline="")
    canvas.create_oval(cx-r3, cy-r3, cx+r3, cy+r3, fill=color, outline="")


class HoverButton(tk.Label):
    """Label cliquable avec effet hover via changement de couleur."""
    def __init__(self, parent, normal_fg, hover_fg, bg, **kwargs):
        super().__init__(parent, fg=normal_fg, bg=bg, **kwargs)
        self._normal_fg = normal_fg
        self._hover_fg = hover_fg
        self.bind("<Enter>", lambda e: self.config(fg=self._hover_fg))
        self.bind("<Leave>", lambda e: self.config(fg=self._normal_fg))

    def update_colors(self, normal_fg, hover_fg, bg):
        self._normal_fg = normal_fg
        self._hover_fg = hover_fg
        self.config(fg=normal_fg, bg=bg)


class LoadingDots:
    """Anime un texte de chargement avec des points (...) dans un widget Text."""
    def __init__(self, root):
        self._root = root
        self._running = False
        self._step = 0
        self._frames = ["   ", ".  ", ".. ", "..."]
        self._callback = None

    def start(self, callback):
        """callback(text) est appelé à chaque frame avec le texte animé."""
        self._callback = callback
        self._running = True
        self._step = 0
        self._tick()

    def stop(self):
        self._running = False

    def _tick(self):
        if not self._running:
            return
        if self._callback:
            self._callback(f"Réflexion{self._frames[self._step % len(self._frames)]}")
        self._step += 1
        self._root.after(400, self._tick)


# ─────────────────────────────────────────────────────────
# Filigrane (Watermark)
# ─────────────────────────────────────────────────────────

class OverlayWindow:
    def __init__(self, root):
        self.root = root
        self.window = None
        self.text = ""

    def update_text(self, text):
        self.text = text
        if self.window and self.window.winfo_exists() and self.window.winfo_viewable():
            self._draw()

    def show(self, text=None):
        if text:
            self.text = text
        if not self.text:
            return
            
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self._draw()
        else:
            self.window = tk.Toplevel(self.root)
            self.window.overrideredirect(True)
            self.window.attributes("-topmost", True)
            if winreg is not None:
                self.window.attributes("-transparentcolor", CHROMA)
                self.window.config(bg=CHROMA)
                self.window.attributes("-disabled", True)
            else:
                theme = get_windows_theme()
                bg_color = THEMES[theme]["bg"]
                self.window.config(bg=bg_color)
                try:
                    self.window.attributes("-alpha", 0.8)
                except Exception:
                    pass
            self._draw()

    def _draw(self):
        for widget in self.window.winfo_children():
            widget.destroy()
            
        # Style "Activate Windows" : Gris semi-transparent, Segoe UI
        # Limité à environ 3-4 cm (300px) et 3 lignes
        display_text = self.text
        
        theme = get_windows_theme()
        bg_color = CHROMA if winreg is not None else THEMES[theme]["bg"]
        font_name = "Segoe UI" if winreg is not None else "DejaVu Sans"
        lbl = tk.Label(self.window, text=display_text, font=(font_name, 11),
                       fg="#888888", bg=bg_color, justify="right", anchor="e",
                       wraplength=280) # wraplength limite la largeur du texte
        lbl.pack(padx=10, pady=10)
        
        self.window.update_idletasks()
        
        # On force la hauteur pour max 3 lignes (environ 100px)
        w = 300
        h = 100
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        
        # Position en bas à droite, au-dessus de la barre des tâches
        self.window.geometry(f"{w}x{h}+{sw - w - 10}+{sh - h - 50}")

    def hide(self):
        if self.window and self.window.winfo_exists():
            self.window.withdraw()


# ─────────────────────────────────────────────────────────
# Popup
# ─────────────────────────────────────────────────────────

class PopupWindow:
    def __init__(self, assistant, root):
        self.assistant = assistant
        self.root = root
        self.window = None
        self._current_theme_name = get_windows_theme()
        self.t = THEMES[self._current_theme_name]
        self.show_transcripts = False
        self.last_omi_message = ""
        self.overlay = OverlayWindow(self.root)
        self.trans_btn = None # FIX: Initialisation explicite

    def _make_toolbar_btn(self, parent_canvas: tk.Canvas, text: str,
                           x: int, y: int, anchor: str = "e",
                           font_size: int = 10, bold: bool = False,
                           command=None) -> tk.Label:
        """
        Creates a consistent toolbar button.
        All toolbar buttons must go through this helper.
        Returns the Label widget for later state updates (e.g. pause toggle).
        """
        weight = "bold" if bold else "normal"
        btn = tk.Label(
            parent_canvas,
            text=text,
            font=(FONT, font_size, weight),
            fg=self.t["fg_sec"],
            bg=self.t["bg"],
            cursor="hand2",
            padx=2,
        )
        parent_canvas.create_window(x, y, anchor=anchor, window=btn)

        # Hover effects
        def on_enter(e):
            btn.config(fg=self.t["fg"])
        def on_leave(e):
            btn.config(fg=self.t["fg_sec"])

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

        if command:
            btn.bind("<Button-1>", lambda e: command())

        return btn


    def update_theme(self, theme_name):
        """Met à jour le thème en temps réel"""
        if theme_name == self._current_theme_name:
            return
            
        self._current_theme_name = theme_name
        self.t = THEMES[theme_name]
        
        if self.window and self.window.winfo_exists():
            # Sauvegarde de l'état actuel
            current_input = self.input_var.get()
            is_visible = self.window.winfo_viewable()
            
            # On détruit et on recrée pour appliquer proprement les nouvelles couleurs
            self.window.destroy()
            self.window = None
            
            if is_visible:
                self.show()
                if hasattr(self, 'input_var'):
                    self.input_var.set(current_input)

    def show(self):
        self.overlay.hide()
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return
        
        # On s'assure d'avoir le dernier thème au moment de l'ouverture
        self._current_theme_name = get_windows_theme()
        self.t = THEMES[self._current_theme_name]
        
        self.window = tk.Toplevel(self.root)
        self._build_ui()

    def minimize(self, event=None):
        if self.window:
            self.window.withdraw()
            if self.last_omi_message:
                self.overlay.show(self.last_omi_message)

    def close_completely(self, event=None):
        if self.window:
            self.window.withdraw()
        self.overlay.hide()

    def _build_ui(self):
        from config import OMI_PERSONA
        W, H = 370, 520
        R = 18
        win = self.window
        t = self.t

        win.title("OMI")
        win.geometry(f"{W}x{H}")
        win.resizable(False, False)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=CHROMA)
        win.attributes("-transparentcolor", CHROMA)

        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{sw - W - 16}+{sh - H - 52}")

        # Canvas principal
        root_canvas = tk.Canvas(win, width=W, height=H, bg=CHROMA,
                                highlightthickness=0, bd=0)
        root_canvas.place(x=0, y=0)
        rounded_rect(root_canvas, 0, 0, W, H, R,
                     fill=t["bg"], outline=t["border_line"], width=1)

        root_canvas.bind("<ButtonPress-1>", self._drag_start)
        root_canvas.bind("<B1-Motion>", self._drag_move)

        # ── Header ────────────────────────────────────────────
        HEADER_H = 44

        # Logo OMI dessiné
        draw_omi_logo(root_canvas, 22, HEADER_H // 2, size=9,
                      color=t["accent"])

        # Titre (clickable = minimize)
        lbl_title = tk.Label(
            root_canvas, text="OMI",
            font=(FONT, 11, "bold"),
            fg=self.t["fg"], bg=self.t["bg"], cursor="hand2"
        )
        root_canvas.create_window(38, HEADER_H // 2, anchor="w", window=lbl_title)
        lbl_title.bind("<Button-1>", self.minimize)

        # Badge persona (petit, discret)
        persona_labels = {
            "developer": "DEV", "student": "ETU", "creative": "CRE",
            "manager": "MGR", "streamer": "STR", "custom": "PRO",
        }
        persona_text = persona_labels.get(OMI_PERSONA, "OMI")
        badge_canvas = tk.Canvas(root_canvas, width=34, height=16,
                                 bg=t["bg"], highlightthickness=0)
        root_canvas.create_window(78, HEADER_H // 2, anchor="w",
                                  window=badge_canvas)
        rounded_rect(badge_canvas, 0, 0, 34, 16, 4,
                     fill=t["badge_bg"], outline="")
        badge_canvas.create_text(17, 8, text=persona_text,
                                 font=(FONT, 7, "bold"),
                                 fill=t["badge_fg"])

        # Séparateur horizontal sous le header
        root_canvas.create_line(0, HEADER_H, W, HEADER_H,
                                fill=t["border_line"], width=1)

        # Boutons de contrôle (droite)
        PAD_RIGHT = 14
        BTN_Y = HEADER_H // 2
        
        # Close ×
        self._make_toolbar_btn(root_canvas, "×", W - PAD_RIGHT, BTN_Y, anchor="e",
                                font_size=15, command=self.close_completely)
        # Minimize —
        self._make_toolbar_btn(root_canvas, "—", W - PAD_RIGHT - 24, BTN_Y, anchor="e",
                                font_size=11, command=self.minimize)
        # Transcripts: "MIC" text (replaces broken 🎙️ emoji)
        self.trans_btn = self._make_toolbar_btn(
            root_canvas, "MIC", W - PAD_RIGHT - 50, BTN_Y, anchor="e",
            font_size=8, bold=True, command=self._toggle_transcripts
        )
        # Pause/Resume: "||" (replaces broken ⏸ emoji)
        self.pause_label = self._make_toolbar_btn(
            root_canvas, "||", W - PAD_RIGHT - 76, BTN_Y, anchor="e",
            font_size=11, bold=True, command=self._toggle_pause
        )
        # Analyze ↺
        self._make_toolbar_btn(
            root_canvas, "↺", W - PAD_RIGHT - 102, BTN_Y, anchor="e",
            font_size=13, bold=True, command=self._force_analyze
        )

        # ── Zone messages ─────────────────────────────────────
        PAD = 12
        MSG_Y = HEADER_H + 8
        INPUT_H = 42
        BOTTOM_PAD = 10
        MSG_H = H - MSG_Y - INPUT_H - BOTTOM_PAD - 8

        # Conteneur messages
        msg_frame = tk.Frame(root_canvas, bg=t["bg"])
        root_canvas.create_window(PAD, MSG_Y, anchor="nw",
                                  window=msg_frame,
                                  width=W - PAD * 2,
                                  height=MSG_H)

        self.msg_text = tk.Text(
            msg_frame,
            wrap="word",
            font=(FONT, 10),
            bg=t["bg"],
            fg=t["fg"],
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=6,
            state="disabled",
            cursor="arrow",
            spacing1=2,
            spacing3=4,
            yscrollcommand=self._on_scroll,
        )
        self.msg_text.pack(fill="both", expand=True)
        self.msg_text.bind("<MouseWheel>", self._on_mousewheel)

        # Scrollbar fine personnalisée (Canvas)
        self._scroll_canvas = tk.Canvas(root_canvas, width=3, bg=t["bg"],
                                        highlightthickness=0)
        root_canvas.create_window(W - 4, MSG_Y, anchor="nw",
                                  window=self._scroll_canvas,
                                  width=3, height=MSG_H)
        self._scroll_thumb = None
        self._scroll_canvas.bind("<Enter>",
            lambda e: self._scroll_canvas.config(width=5))
        self._scroll_canvas.bind("<Leave>",
            lambda e: self._scroll_canvas.config(width=3))

        # Zone transcriptions (cachée)
        self.trans_text = tk.Text(
            msg_frame,
            wrap="word",
            font=("Consolas", 9),
            bg=t["bg"],
            fg=t["fg_sec"],
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=6,
            state="disabled",
            cursor="arrow",
        )

        # Tags messages — style moderne
        self.msg_text.tag_config("ts",
            foreground=t["fg_ter"],
            font=(FONT, 7),
            spacing1=8)
        self.msg_text.tag_config("sender_omi",
            foreground=t["fg_sec"],
            font=(FONT, 8, "bold"),
            spacing1=8)
        self.msg_text.tag_config("text_omi",
            foreground=t["fg_omi"],
            font=(FONT, 10),
            lmargin1=0, lmargin2=0,
            spacing3=4)
        self.msg_text.tag_config("sender_you",
            foreground=t["fg_sec"],
            font=(FONT, 8, "bold"),
            spacing1=8)
        self.msg_text.tag_config("text_you",
            foreground=t["fg"],
            font=(FONT, 10),
            lmargin1=0, lmargin2=0,
            spacing3=4)
        self.msg_text.tag_config("text_system",
            foreground=t["fg_ter"],
            font=(FONT, 8, "italic"),
            spacing1=4, spacing3=4)

        self._load_history()

        # ── Input ─────────────────────────────────────────────
        INPUT_Y = H - INPUT_H - BOTTOM_PAD
        INPUT_W = W - PAD * 2

        input_canvas = tk.Canvas(root_canvas, width=INPUT_W, height=INPUT_H,
                                 bg=t["bg"], highlightthickness=0)
        root_canvas.create_window(PAD, INPUT_Y, anchor="nw", window=input_canvas)
        self._input_rect = rounded_rect(input_canvas, 0, 2, INPUT_W, INPUT_H - 2, 12,
                                        fill=t["input_bg"], outline=t["border"], width=1)

        # Placeholder + champ texte
        self.input_var = tk.StringVar()
        self._placeholder_active = True
        entry = tk.Entry(input_canvas,
                         textvariable=self.input_var,
                         font=(FONT, 10),
                         bg=t["input_bg"], fg=t["fg_sec"],
                         insertbackground=t["fg"],
                         bd=0, highlightthickness=0)
        
        SEND_W, SEND_H = 34, 26   # Size of the blue send button
        SEND_R = 8                 # Corner radius
        
        input_canvas.create_window(10, INPUT_H // 2, anchor="w",
                                   window=entry,
                                   width=W - PAD*2 - SEND_W - 20,
                                   height=24)

        # Gestion placeholder
        def _focus_in(e):
            if self._placeholder_active:
                self.input_var.set("")
                entry.config(fg=t["fg"])
                self._placeholder_active = False
            input_canvas.itemconfig(self._input_rect, outline=t["border_focus"])

        def _focus_out(e):
            if not self.input_var.get():
                self.input_var.set("Écris un message...")
                entry.config(fg=t["fg_sec"])
                self._placeholder_active = True
            input_canvas.itemconfig(self._input_rect, outline=t["border"])

        entry.bind("<FocusIn>", _focus_in)
        entry.bind("<FocusOut>", _focus_out)
        entry.bind("<Return>", self._send)
        self.input_var.set("Écris un message...")

        # Canvas inside input_canvas to hold the send button
        send_canvas = tk.Canvas(
            input_canvas,
            width=SEND_W,
            height=SEND_H,
            bg=t["input_bg"],
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        input_canvas.create_window(
            INPUT_W - 6, INPUT_H // 2,
            anchor="e", window=send_canvas,
            width=SEND_W, height=SEND_H
        )

        def _draw_send_btn(pressed: bool = False):
            send_canvas.delete("all")
            bg = t["send_btn_bg"]
            if pressed:
                bg = t.get("send_btn_bg_pressed", bg)
            # Draw rounded rectangle (the blue box)
            pts = [
                SEND_R, 0,   SEND_W - SEND_R, 0,
                SEND_W, 0,   SEND_W, SEND_R,
                SEND_W, SEND_H - SEND_R, SEND_W, SEND_H,
                SEND_W - SEND_R, SEND_H, SEND_R, SEND_H,
                0, SEND_H, 0, SEND_H - SEND_R,
                0, SEND_R, 0, 0,
            ]
            send_canvas.create_polygon(pts, smooth=True, fill=bg, outline="")
            # Arrow ↑ centered on the button
            send_canvas.create_text(
                SEND_W // 2, SEND_H // 2,
                text="↑",
                font=(FONT, 12, "bold"),
                fill=t["send_btn_fg"],
                anchor="center",
            )

        _draw_send_btn()

        # Hover and click effects
        def _on_send_enter(e): 
            send_canvas.config(cursor="hand2")
            # Slightly brighter on hover — redraw with a lighter shade
            send_canvas.delete("all")
            pts = [SEND_R,0, SEND_W-SEND_R,0, SEND_W,0, SEND_W,SEND_R,
                   SEND_W,SEND_H-SEND_R, SEND_W,SEND_H, SEND_W-SEND_R,SEND_H,
                   SEND_R,SEND_H, 0,SEND_H, 0,SEND_H-SEND_R, 0,SEND_R, 0,0]
            hover_bg = t.get("send_btn_hover", t["send_btn_bg"])
            send_canvas.create_polygon(pts, smooth=True, fill=hover_bg, outline="")
            send_canvas.create_text(SEND_W//2, SEND_H//2, text="↑",
                                     font=(FONT, 12, "bold"), fill=t["send_btn_fg"], anchor="center")

        def _on_send_leave(e):
            _draw_send_btn()

        send_canvas.bind("<Enter>", _on_send_enter)
        send_canvas.bind("<Leave>", _on_send_leave)
        send_canvas.bind("<Button-1>", self._send)

        # Référencer pour le thème
        self._input_canvas = input_canvas
        self._entry = entry

        # Loader animation
        self._loader = LoadingDots(self.root)

    def _on_scroll(self, first, last):
        """Met à jour la scrollbar personnalisée."""
        if not hasattr(self, '_scroll_canvas'):
            return
        self._scroll_canvas.delete("all")
        first, last = float(first), float(last)
        if last - first >= 1.0:
            return  # Tout est visible, pas de scrollbar
        h = self._scroll_canvas.winfo_height() or 200
        y0 = int(first * h)
        y1 = int(last * h)
        t = self.t
        self._scroll_thumb = self._scroll_canvas.create_rectangle(
            0, y0, 3, max(y1, y0 + 20),
            fill=t["scrollbar"], outline="", width=0
        )

    def _on_mousewheel(self, event):
        self.msg_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def set_mode_badge(self, mode: str):
        """Met à jour le badge de mode (DOCUMENT / TEXTE / IMAGE) dans le header."""
        pass


    # ── Drag ──────────────────────────────────────────────
    def _drag_start(self, e):
        self._dx = e.x_root - self.window.winfo_x()
        self._dy = e.y_root - self.window.winfo_y()

    def _drag_move(self, e):
        x = e.x_root - self._dx
        y = e.y_root - self._dy
        self.window.geometry(f"+{x}+{y}")

    # ── Messages ──────────────────────────────────────────
    def _append(self, sender, text, sender_tag, text_tag):
        from datetime import datetime
        if sender in ["OMI", "ÉCRAN", "AUDIO"]:
            self.last_omi_message = text
            self.overlay.update_text(text)

        t = self.msg_text
        t.config(state="normal")

        # Timestamp discret
        now = datetime.now().strftime("%H:%M")
        t.insert("end", f"\n{sender}  {now}\n", "sender_" + ("omi" if sender_tag == "sender_omi" else "you"))
        t.insert("end", f"{text}\n", text_tag)

        t.config(state="disabled")
        t.see("end")

    def _load_history(self):
        memory = self.assistant.get_memory()
        if not memory:
            self.msg_text.config(state="normal")
            self.msg_text.insert("end", "\nEn attente d'activité...\n", "text_system")
            self.msg_text.config(state="disabled")
            return
        for item in memory:
            label = "ÉCRAN" if item["type"] == "vision" else "AUDIO"
            self._append(label, item["content"], "sender_omi", "text_omi")

    def _set_suggestion(self, text):
        if self.popup and self.popup.window and self.popup.window.winfo_exists():
            label = "AUDIO" if text.startswith("🎤") else "ÉCRAN"
            clean = text.lstrip("🎤 ")
            self._append(label, clean, "sender_omi", "text_omi")

    def _send(self, event=None):
        if not hasattr(self, '_placeholder_active'):
            msg = self.input_var.get().strip()
        else:
            msg = "" if self._placeholder_active else self.input_var.get().strip()
        if not msg:
            return
        self.input_var.set("")
        if hasattr(self, '_placeholder_active'):
            self._placeholder_active = False
            if hasattr(self, '_entry'):
                self._entry.config(fg=self.t["fg"])
        self._append("VOUS", msg, "sender_you", "text_you")
        self._last_status = "Réflexion..."

        # Insérer le message de chargement
        t = self.msg_text
        t.config(state="normal")
        t.insert("end", "\nOMI\n", "sender_omi")
        t.insert("end", "Réflexion...\n", "text_system")
        t.config(state="disabled")
        t.see("end")

        # Démarrer l'animation
        def _update_loading(text):
            if self.window and self.window.winfo_exists():
                self.window.after(0, lambda: self._do_update_status(text))

        self._loader.start(_update_loading)
        threading.Thread(target=self._do_chat, args=(msg,), daemon=True).start()

    def trigger_vocal_chat(self, query):
        self.show()
        self._append("VOUS (VOIX)", query, "sender_you", "text_you")
        self._last_status = "Réflexion en cours..."
        self._append("OMI", self._last_status, "sender_omi", "text_omi")
        threading.Thread(target=self._do_chat, args=(query,), daemon=True).start()

    def _do_chat(self, msg):
        response = self.assistant.chat(msg, status_callback=self._update_chat_status)
        if self.window and self.window.winfo_exists():
            self.window.after(0, lambda: self._replace_last(response))

    def _update_chat_status(self, status):
        if self.window and self.window.winfo_exists():
            self.window.after(0, lambda: self._do_update_status(status))

    def _do_update_status(self, new_status):
        self.last_omi_message = new_status
        self.overlay.update_text(new_status)
        t = self.msg_text
        t.config(state="normal")
        idx = t.search(self._last_status, "1.0", backwards=True, stopindex="end")
        if idx:
            end_idx = t.index(f"{idx} lineend")
            t.delete(idx, end_idx)
            t.insert(idx, new_status, "text_system")
            self._last_status = new_status
        t.config(state="disabled")
        t.see("end")

    def _replace_last(self, text):
        self._loader.stop()
        self.last_omi_message = text
        self.overlay.update_text(text)
        t = self.msg_text
        t.config(state="normal")
        idx = t.search(self._last_status, "1.0", backwards=True, stopindex="end")
        if idx:
            end_idx = t.index(f"{idx} lineend")
            t.delete(idx, end_idx)
            t.insert(idx, text, "text_omi")
        else:
            self._append("OMI", text, "sender_omi", "text_omi")
        t.config(state="disabled")
        t.see("end")

    def _toggle_transcripts(self, event=None):
        self.show_transcripts = not self.show_transcripts
        if self.show_transcripts:
            self.msg_text.pack_forget()
            self.trans_text.pack(fill="both", expand=True)
            if self.trans_btn:
                self.trans_btn.config(fg=self.t["accent"], font=(FONT, 8, "bold"))
            # Charger les dernières transcriptions
            from core.database import query_transcripts
            recent = query_transcripts(limit=20)
            self.trans_text.config(state="normal")
            self.trans_text.delete("1.0", "end")
            for r in reversed(recent):
                self.trans_text.insert("end", f"[{r[0][-8:]}] {r[1]}: {r[2]}\n")
            self.trans_text.config(state="disabled")
            self.trans_text.see("end")
        else:
            self.trans_text.pack_forget()
            self.msg_text.pack(fill="both", expand=True)
            if self.trans_btn:
                self.trans_btn.config(fg=self.t["fg_sec"], font=(FONT, 8, "bold"))

    def _add_transcript_to_ui(self, text):
        if self.window and self.window.winfo_exists():
            t = self.trans_text
            t.config(state="normal")
            from datetime import datetime
            now = datetime.now().strftime("%H:%M:%S")
            t.insert("end", f"[{now}] User: {text}\n")
            t.config(state="disabled")
            if self.show_transcripts:
                t.see("end")

    def _toggle_pause(self, event=None):
        is_paused = self.assistant.toggle_pause()
        if hasattr(self, 'pause_label'):
            self.pause_label.config(text="▶" if is_paused else "||")
        msg = "Analyse en pause." if is_paused else "Analyse reprend."
        t = self.msg_text
        t.config(state="normal")
        t.insert("end", f"\n{msg}\n", "text_system")
        t.config(state="disabled")
        t.see("end")

    def _force_analyze(self, event=None):
        self._append("SYSTÈME", "Analyse en cours...", "sender_omi", "text_omi")
        threading.Thread(target=self._do_force_analyze, daemon=True).start()

    def _do_force_analyze(self):
        try:
            img = self.assistant._capture_screen()
            self.assistant._analyze_vision([img])
        except Exception as e:
            if self.window and self.window.winfo_exists():
                self.window.after(0, lambda: self._append("ERREUR", str(e),
                                                          "sender_omi", "text_omi"))

    def _refresh_history(self): pass
    def _set_chat_response(self, text): pass


# ─────────────────────────────────────────────────────────
# Tray
# ─────────────────────────────────────────────────────────

def create_icon_image():
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill="#111111")
    draw.ellipse([20, 20, 44, 44], fill="#FFFFFF")
    draw.ellipse([28, 28, 36, 36], fill="#111111")
    return img


class TrayApp:
    def __init__(self, assistant):
        self.assistant = assistant
        self.popup = None
        self._root = None
        self._current_theme_name = get_windows_theme()

    def run(self):
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("OmiAssistant")

        global FONT
        FONT = _resolve_font()

        self.popup = PopupWindow(self.assistant, self._root)
        self.assistant.on_suggestion_callback = self._on_new_suggestion
        self.assistant.on_transcript_callback = self._on_new_transcript
        self.assistant.on_vocal_query_callback = self._on_vocal_query

        # Lancer la surveillance du thème Windows
        self._check_theme_loop()

        icon_img = create_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Ouvrir", self._open_popup, default=True),
            pystray.MenuItem("Quitter", self._quit),
        )
        self.icon = pystray.Icon("OmiAssistant", icon_img, "Omi", menu=menu)

        threading.Thread(target=self.icon.run, daemon=True).start()
        self._root.mainloop()

    def _check_theme_loop(self):
        """Vérifie périodiquement si le thème Windows a changé"""
        new_theme = get_windows_theme()
        if new_theme != self._current_theme_name:
            self._current_theme_name = new_theme
            if self.popup:
                self.popup.update_theme(new_theme)
        
        if self._root:
            self._root.after(3000, self._check_theme_loop)

    def _open_popup(self, icon=None, item=None):
        self._root.after(0, self.popup.show)

    def _on_new_suggestion(self, text):
        if self.popup and self.popup.window and self.popup.window.winfo_exists():
            self._root.after(0, lambda: self.popup._set_suggestion(text))

    def _on_new_transcript(self, text):
        if self.popup and self.popup.window and self.popup.window.winfo_exists():
            self._root.after(0, lambda: self.popup._add_transcript_to_ui(text))

    def _on_vocal_query(self, query):
        if self.popup:
            self._root.after(0, lambda: self.popup.trigger_vocal_chat(query))

    def _quit(self, icon, item):
        self.assistant.stop()
        self.icon.stop()
        self._root.after(0, self._root.destroy)
