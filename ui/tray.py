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
import winreg

# ─────────────────────────────────────────────────────────
# Thème
# ─────────────────────────────────────────────────────────

def get_windows_theme():
    try:
        reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(reg, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"

THEMES = {
    "dark": {
        "bg":        "#111111",
        "surface":   "#1C1C1C",
        "input_bg":  "#1C1C1C",
        "border":    "#2A2A2A",
        "fg":        "#F0F0F0",
        "fg_sec":    "#888888",
        "fg_omi":    "#FFFFFF",
        "accent":    "#FFFFFF",
        "btn_bg":    "#232323",
        "btn_hover": "#2E2E2E",
        "border_line": "#3a3a3a",
    },
    "light": {
        "bg":        "#F5F5F5",
        "surface":   "#FFFFFF",
        "input_bg":  "#ECECEC",
        "border":    "#E0E0E0",
        "fg":        "#111111",
        "fg_sec":    "#888888",
        "fg_omi":    "#111111",
        "accent":    "#000000",
        "btn_bg":    "#E8E8E8",
        "btn_hover": "#DCDCDC",
        "border_line": "#CCCCCC",
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
            self.window.attributes("-transparentcolor", CHROMA)
            self.window.config(bg=CHROMA)
            # Désactiver le focus pour que ce soit vraiment un filigrane
            self.window.attributes("-disabled", True)
            self._draw()

    def _draw(self):
        for widget in self.window.winfo_children():
            widget.destroy()
            
        # Style "Activate Windows" : Gris semi-transparent, Segoe UI
        # Limité à environ 3-4 cm (300px) et 3 lignes
        display_text = self.text
        
        lbl = tk.Label(self.window, text=display_text, font=("Segoe UI", 11),
                       fg="#888888", bg=CHROMA, justify="right", anchor="e",
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
        W, H = 360, 500
        R = 16          # rayon des coins de la fenêtre
        win = self.window
        t = self.t

        win.title("OMI")
        win.geometry(f"{W}x{H}")
        win.resizable(False, False)
        win.overrideredirect(True)
        win.attributes("-topmost", True)

        # ── Radius global via transparentcolor ──────────────
        # Le fond de la fenêtre est CHROMA (couleur invisible)
        # On dessine un rectangle arrondi par-dessus : les coins restent transparents
        win.configure(bg=CHROMA)
        win.attributes("-transparentcolor", CHROMA)

        # Position bas-droite
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{sw - W - 16}+{sh - H - 52}")

        # Canvas principal qui couvre toute la fenêtre
        root_canvas = tk.Canvas(win, width=W, height=H,
                                bg=CHROMA, highlightthickness=0, bd=0)
        root_canvas.place(x=0, y=0)

        # Rectangle arrondi = fond réel de la fenêtre
        rounded_rect(root_canvas, 0, 0, W, H, R, fill=t["bg"], outline=t["border_line"], width=1.5)

        # Drag sur le canvas racine
        root_canvas.bind("<ButtonPress-1>", self._drag_start)
        root_canvas.bind("<B1-Motion>",     self._drag_move)

        # ── Titlebar — widgets posés directement sur le canvas ──
        # (pas de Frame intermédiaire pour ne pas boucher les coins arrondis)

        lbl_title = tk.Label(root_canvas, text="OMI", font=("Segoe UI", 11, "bold"),
                             fg=t["fg"], bg=t["bg"], cursor="hand2")
        root_canvas.create_window(16, 22, anchor="w", window=lbl_title)
        lbl_title.bind("<Button-1>", self.minimize)

        close_btn = tk.Label(root_canvas, text="×", font=("Segoe UI", 15),
                             fg=t["fg_sec"], bg=t["bg"], cursor="hand2")
        root_canvas.create_window(W - 14, 22, anchor="e", window=close_btn)
        close_btn.bind("<Button-1>", self.close_completely)

        min_btn = tk.Label(root_canvas, text="—", font=("Segoe UI", 11),
                             fg=t["fg_sec"], bg=t["bg"], cursor="hand2")
        root_canvas.create_window(W - 38, 22, anchor="e", window=min_btn)
        min_btn.bind("<Button-1>", self.minimize)

        self.trans_btn = tk.Label(root_canvas, text="🎙️", font=("Segoe UI", 10),
                                    fg=t["fg_sec"], bg=t["bg"], cursor="hand2")
        root_canvas.create_window(W - 64, 22, anchor="e", window=self.trans_btn)
        self.trans_btn.bind("<Button-1>", self._toggle_transcripts)

        self.pause_label = tk.Label(root_canvas, text="⏸", font=("Segoe UI", 10),
                                    fg=t["fg_sec"], bg=t["bg"], cursor="hand2")
        root_canvas.create_window(W - 90, 22, anchor="e", window=self.pause_label)
        self.pause_label.bind("<Button-1>", self._toggle_pause)

        analyze_label = tk.Label(root_canvas, text="↺", font=("Segoe UI", 12),
                                 fg=t["fg_sec"], bg=t["bg"], cursor="hand2")
        root_canvas.create_window(W - 116, 22, anchor="e", window=analyze_label)
        analyze_label.bind("<Button-1>", self._force_analyze)

        # ── Zone messages ─────────────────────────────────────
        PAD = 14
        MSG_Y = 52
        MSG_H = H - MSG_Y - 60   # laisse de la place pour l'input en bas

        outer_msg = tk.Canvas(root_canvas, bg=t["bg"], highlightthickness=0, bd=0,
                              width=W - PAD*2, height=MSG_H)
        root_canvas.create_window(PAD, MSG_Y, anchor="nw", window=outer_msg)
        rounded_rect(outer_msg, 0, 0, W - PAD*2, MSG_H, 12, fill=t["surface"], outline="")

        msg_inner = tk.Frame(outer_msg, bg=t["surface"])
        outer_msg.create_window(8, 8, anchor="nw", window=msg_inner,
                                width=W - PAD*2 - 16, height=MSG_H - 16)

        self.msg_text = scrolledtext.ScrolledText(
            msg_inner,
            wrap="word",
            font=("Segoe UI", 10),
            bg=t["surface"],
            fg=t["fg"],
            bd=0,
            highlightthickness=0,
            padx=4,
            pady=4,
            state="disabled",
            cursor="arrow",
        )
        self.msg_text.pack(fill="both", expand=True)

        # Zone de transcription (cachée par défaut)
        self.trans_text = scrolledtext.ScrolledText(
            msg_inner,
            wrap="word",
            font=("Consolas", 9),
            bg=t["input_bg"],
            fg=t["fg_sec"],
            bd=0,
            highlightthickness=0,
            padx=4,
            pady=4,
            state="disabled",
            cursor="arrow",
        )
        # On ne la pack pas encore

        self.msg_text.tag_config("sender_omi", foreground=t["fg_sec"],
                                  font=("Segoe UI", 8, "bold"))
        self.msg_text.tag_config("text_omi",   foreground=t["fg_omi"],
                                  font=("Segoe UI", 10))
        self.msg_text.tag_config("sender_you", foreground=t["fg_sec"],
                                  font=("Segoe UI", 8, "bold"))
        self.msg_text.tag_config("text_you",   foreground=t["fg"],
                                  font=("Segoe UI", 10, "italic"))

        self._load_history()

        # ── Input ─────────────────────────────────────────────
        INPUT_Y = H - 50
        INPUT_H = 38

        outer_input = tk.Canvas(root_canvas, bg=t["bg"], highlightthickness=0, bd=0,
                                width=W - PAD*2, height=INPUT_H)
        root_canvas.create_window(PAD, INPUT_Y, anchor="nw", window=outer_input)
        rounded_rect(outer_input, 0, 0, W - PAD*2, INPUT_H, 10,
                     fill=t["input_bg"], outline="")

        self.input_var = tk.StringVar()
        entry = tk.Entry(outer_input, textvariable=self.input_var,
                         font=("Segoe UI", 10),
                         bg=t["input_bg"], fg=t["fg"],
                         insertbackground=t["fg"],
                         bd=0, highlightthickness=0)
        outer_input.create_window(10, INPUT_H // 2, anchor="w",
                                  window=entry, width=W - PAD*2 - 44, height=24)
        entry.bind("<Return>", self._send)

        send_btn = tk.Label(outer_input, text="↑", font=("Segoe UI", 13, "bold"),
                            fg=t["accent"], bg=t["input_bg"], cursor="hand2")
        outer_input.create_window(W - PAD*2 - 16, INPUT_H // 2,
                                  anchor="center", window=send_btn)
        send_btn.bind("<Button-1>", self._send)


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
        if sender in ["OMI", "📷 ÉCRAN", "🎤 AUDIO"]:
            self.last_omi_message = text
            self.overlay.update_text(text)
        t = self.msg_text
        t.config(state="normal")
        t.insert("end", f"\n{sender}\n", sender_tag)
        t.insert("end", f"{text}\n", text_tag)
        t.config(state="disabled")
        t.see("end")

    def _load_history(self):
        memory = self.assistant.get_memory()
        if not memory:
            self.msg_text.config(state="normal")
            self.msg_text.insert("end", "\nEn attente d'activité...\n", "sender_omi")
            self.msg_text.config(state="disabled")
            return
        for item in memory:
            label = "📷 ÉCRAN" if item["type"] == "screen" else "🎤 AUDIO"
            self._append(label, item["content"], "sender_omi", "text_omi")

    def _set_suggestion(self, text):
        if self.window and self.window.winfo_exists():
            label = "🎤 AUDIO" if text.startswith("🎤") else "📷 ÉCRAN"
            self._append(label, text.lstrip("🎤 "), "sender_omi", "text_omi")

    def _send(self, event=None):
        msg = self.input_var.get().strip()
        if not msg:
            return
        self.input_var.set("")
        self._append("VOUS", msg, "sender_you", "text_you")
        self._last_status = "Réflexion en cours..."
        self._append("OMI", self._last_status, "sender_omi", "text_omi")
        threading.Thread(target=self._do_chat, args=(msg,), daemon=True).start()

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
            t.insert(idx, new_status)
            self._last_status = new_status
        t.config(state="disabled")
        t.see("end")

    def _replace_last(self, text):
        self.last_omi_message = text
        self.overlay.update_text(text)
        t = self.msg_text
        t.config(state="normal")
        idx = t.search(self._last_status, "1.0", backwards=True, stopindex="end")
        if idx:
            end_idx = t.index(f"{idx} lineend")
            t.delete(idx, end_idx)
            t.insert(idx, text)
        else:
            self._append("OMI", text, "sender_omi", "text_omi")
        t.config(state="disabled")
        t.see("end")

    def _toggle_transcripts(self, event=None):
        self.show_transcripts = not self.show_transcripts
        if self.show_transcripts:
            self.msg_text.pack_forget()
            self.trans_text.pack(fill="both", expand=True)
            self.trans_btn.config(fg=self.t["accent"])
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
            self.trans_btn.config(fg=self.t["fg_sec"])

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
        self.pause_label.config(text="▶" if is_paused else "⏸")
        self._append("SYSTÈME",
                     "Analyse en pause." if is_paused else "Analyse reprend.",
                     "sender_omi", "text_omi")

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

        self.popup = PopupWindow(self.assistant, self._root)
        self.assistant.on_suggestion_callback = self._on_new_suggestion
        self.assistant.on_transcript_callback = self._on_new_transcript

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

    def _quit(self, icon, item):
        self.assistant.stop()
        self.icon.stop()
        self._root.after(0, self._root.destroy)
