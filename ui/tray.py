"""
Interface utilisateur :
- Icône dans la barre des tâches (system tray)
- Popup avec suggestions, historique et chat
- Support du mode Clair/Sombre automatique
"""

import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
import pystray
from PIL import Image, ImageDraw, ImageTk
import os
import sys
import winreg
from win10toast_persist import ToastNotifier

toaster = ToastNotifier()

def get_windows_theme():
    """Détecte si Windows est en mode sombre (1) ou clair (0)"""
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"  # Par défaut

def create_icon_image():
    """Génère une icône simple si pas de fichier .ico"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill="#000000")
    draw.ellipse([16, 16, 48, 48], fill="#ffffff")
    draw.ellipse([28, 28, 36, 36], fill="#000000")
    return img

class PopupWindow:
    """Fenêtre popup moderne avec support thématique"""

    def __init__(self, assistant):
        self.assistant = assistant
        self.window = None
        self.theme = get_windows_theme()
        self._apply_theme_colors()

    def _apply_theme_colors(self):
        if self.theme == "light":
            self.bg_main = "#F3F3F3"   # Gris très clair
            self.bg_surf = "#FFFFFF"   # Blanc pur
            self.bg_input = "#EBEBEB"  # Gris léger pour input
            self.fg_main = "#1A1A1A"   # Presque noir
            self.fg_sec = "#666666"    # Gris texte
            self.accent = "#000000"
        else:
            self.bg_main = "#0A0A0A"   # Noir profond
            self.bg_surf = "#1A1A1A"   # Gris sombre
            self.bg_input = "#262626"  # Gris moyen
            self.fg_main = "#FFFFFF"   # Blanc
            self.fg_sec = "#A3A3A3"    # Gris clair
            self.accent = "#FFFFFF"

    def show(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        self.theme = get_windows_theme()
        self._apply_theme_colors()
        
        self.window = tk.Toplevel()
        self._build_ui()

    def _build_ui(self):
        win = self.window
        win.title("OMI")
        win.geometry("420x650")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.configure(bg=self.bg_main)

        # Positionne en bas à droite
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        win.geometry(f"420x650+{screen_w - 440}+{screen_h - 720}")

        # ── Header ──────────────────────────────────
        header = tk.Frame(win, bg=self.bg_main, pady=20)
        header.pack(fill="x", padx=25)

        tk.Label(
            header,
            text="OMI",
            font=("Segoe UI", 18, "bold"),
            fg=self.fg_main,
            bg=self.bg_main,
        ).pack(side="left")

        self.pause_btn = tk.Button(
            header,
            text="⏸ Pause" if not self.assistant.paused else "▶ Reprendre",
            font=("Segoe UI", 9),
            fg=self.fg_main,
            bg=self.bg_surf,
            activebackground=self.bg_input,
            activeforeground=self.fg_main,
            bd=0,
            padx=15,
            pady=6,
            cursor="hand2",
            command=self._toggle_pause,
        )
        self.pause_btn.pack(side="right")

        # ── Suggestion (Card moderne) ────────────────
        tk.Label(
            win,
            text="DERNIÈRE ANALYSE",
            font=("Segoe UI", 8, "bold"),
            fg=self.fg_sec,
            bg=self.bg_main,
        ).pack(anchor="w", padx=30, pady=(10, 5))

        # Simulation d'un container arrondi pour la suggestion
        suggestion_container = tk.Frame(win, bg=self.bg_surf, padx=2, pady=2)
        suggestion_container.pack(fill="x", padx=25)
        
        self.suggestion_box = tk.Text(
            suggestion_container,
            height=4,
            wrap="word",
            font=("Segoe UI", 11),
            bg=self.bg_surf,
            fg=self.fg_main,
            bd=0,
            padx=15,
            pady=15,
            state="disabled",
            highlightthickness=0,
        )
        self.suggestion_box.pack(fill="x")
        self._set_suggestion(self.assistant.get_latest_suggestion())

        # ── Historique ───────────────────────────────
        tk.Label(
            win,
            text="FLUX D'ACTIVITÉ",
            font=("Segoe UI", 8, "bold"),
            fg=self.fg_sec,
            bg=self.bg_main,
        ).pack(anchor="w", padx=30, pady=(20, 5))

        self.history_box = scrolledtext.ScrolledText(
            win,
            height=7,
            wrap="word",
            font=("Segoe UI", 9),
            bg=self.bg_main,
            fg=self.fg_sec,
            bd=0,
            padx=10,
            pady=0,
            state="disabled",
            highlightthickness=0,
        )
        self.history_box.pack(fill="x", padx=25)
        self._refresh_history()

        # ── Chat (Input Moderne) ─────────────────────
        chat_container = tk.Frame(win, bg=self.bg_input, padx=15, pady=2)
        chat_container.pack(fill="x", padx=25, pady=(25, 0))
        
        self.chat_input = tk.Entry(
            chat_container,
            font=("Segoe UI", 11),
            bg=self.bg_input,
            fg=self.fg_main,
            insertbackground=self.fg_main,
            bd=0,
            highlightthickness=0,
        )
        self.chat_input.pack(fill="x", ipady=12)
        self.chat_input.bind("<Return>", self._send_chat)
        self.chat_input.insert(0, "Demande-moi n'importe quoi...")
        self.chat_input.bind("<FocusIn>", lambda e: self.chat_input.delete(0, "end") if "Demande-moi" in self.chat_input.get() else None)

        # Réponse chat
        self.chat_response = tk.Text(
            win,
            height=5,
            wrap="word",
            font=("Segoe UI", 10),
            bg=self.bg_main,
            fg=self.fg_main,
            bd=0,
            padx=5,
            pady=15,
            state="disabled",
        )
        self.chat_response.pack(fill="x", padx=25)

    def _toggle_pause(self):
        is_paused = self.assistant.toggle_pause()
        self.pause_btn.config(text="▶ Reprendre" if is_paused else "⏸ Pause")
        status_text = "Assistant en pause." if is_paused else "Assistant actif."
        self._set_suggestion(status_text)

    def _set_suggestion(self, text):
        self.suggestion_box.config(state="normal")
        self.suggestion_box.delete("1.0", "end")
        self.suggestion_box.insert("end", text)
        self.suggestion_box.config(state="disabled")

    def _refresh_history(self):
        memory = self.assistant.get_memory()
        self.history_box.config(state="normal")
        self.history_box.delete("1.0", "end")
        if not memory:
            self.history_box.insert("end", "Aucun historique.")
        else:
            for item in reversed(memory[-10:]):
                icon = "●"
                time_str = item['time']
                content = item['content']
                self.history_box.insert("end", f"{icon} {time_str} ", "time")
                self.history_box.insert("end", f"{content}\n\n")
        self.history_box.tag_config("time", foreground=self.accent)
        self.history_box.config(state="disabled")

    def _send_chat(self, event=None):
        msg = self.chat_input.get().strip()
        if not msg or "Demande-moi" in msg:
            return
        self.chat_input.delete(0, "end")
        self._set_chat_response("OMI réfléchit...")
        threading.Thread(target=self._do_chat, args=(msg,), daemon=True).start()

    def _do_chat(self, msg):
        response = self.assistant.chat(msg)
        if self.window and self.window.winfo_exists():
            self.window.after(0, lambda: self._set_chat_response(response))

    def _set_chat_response(self, text):
        self.chat_response.config(state="normal")
        self.chat_response.delete("1.0", "end")
        self.chat_response.insert("end", text)
        self.chat_response.config(state="disabled")


class TrayApp:
    """Icône dans la barre des tâches Windows"""

    def __init__(self, assistant):
        self.assistant = assistant
        self.popup = None
        self._root = None

    def run(self):
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("OmiAssistant")

        self.popup = PopupWindow(self.assistant)
        self.assistant.on_suggestion_callback = self._on_new_suggestion

        icon_img = create_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Ouvrir", self._open_popup, default=True),
            pystray.MenuItem("Quitter", self._quit),
        )
        self.icon = pystray.Icon("OmiAssistant", icon_img, "Omi Assistant", menu=menu)

        tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        tray_thread.start()

        self._root.mainloop()

    def _open_popup(self, icon=None, item=None):
        self._root.after(0, self.popup.show)

    def _on_new_suggestion(self, text):
        if self.popup and self.popup.window and self.popup.window.winfo_exists():
            self._root.after(0, lambda: self.popup._set_suggestion(text))
            self._root.after(0, self.popup._refresh_history)
        else:
            if not text.startswith("Erreur") and not text.startswith("Rien de particulier"):
                try:
                    toaster.show_toast("OMI", text, duration=5, threaded=True)
                except: pass

    def _quit(self, icon, item):
        self.assistant.stop()
        self.icon.stop()
        self._root.after(0, self._root.destroy)
