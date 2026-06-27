import os
import subprocess
import time
import platform
import sqlite3
import webbrowser
import urllib.parse
import base64
import io
import psutil
import pyperclip
try:
    import pyodbc
except ImportError:
    pyodbc = None
from datetime import datetime
from pathlib import Path
from PIL import Image

try:
    import win32evtlog
except ImportError:
    win32evtlog = None

try:
    from pywinauto import Desktop, Application
except ImportError:
    Desktop = None
    Application = None

try:
    import comtypes.client
except ImportError:
    comtypes = None

from config import SCREEN_CAPTURE_SIZE, ALLOW_AUTONOMOUS_UI_INTERACTION
from core.database import DB_PATH, query_transcripts, search_transcripts
from core.profile import load_profile, save_profile

# Background process and system bridge imports
from core.process_manager import launch_detached, run_and_wait, launch_app, get_process_by_name, kill_by_name
from core.system_bridge import media_control, set_volume, get_volume, send_notification as _send_notification
from core.scheduler import schedule_task, list_scheduled_tasks, cancel_task
from core.web_fetcher import search_web_headless, fetch_page_text

def get_user_profile() -> dict:
    """Lit le profil complet de l'utilisateur — tout ce qu'OMI a appris sur lui jusqu'ici.
    Utilise cet outil pour personnaliser tes suggestions ou retrouver des informations connues."""
    try:
        return load_profile()
    except Exception as e:
        return {"error": str(e)}


def update_user_profile(section: str, key: str, value: str = None, items: list[str] = None) -> dict:
    """Met à jour une information dans le profil de l'utilisateur.

    - section : catégorie à modifier ('identity', 'work', 'habits', 'preferences', 'schedule', 'notes')
    - key     : nom du champ (ex: 'name', 'tech_stack', 'bad_habits')
    - value   : nouvelle valeur texte (pour les champs simples ou les notes)
    - items   : nouvelle liste de valeurs (pour les champs de type liste comme tech_stack)

    Utilise soit 'value' (texte) soit 'items' (liste), selon le champ.
    """
    try:
        profile = load_profile()
        final_value = items if items is not None else value

        if section == "notes":
            # Cas spécial : ajouter une note horodatée
            note_text = str(final_value)
            profile.setdefault("notes", []).append({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "text": note_text
            })
            # Limiter à 50 notes
            profile["notes"] = profile["notes"][-50:]
            save_profile(profile)
            return {"status": f"Note ajoutée : {note_text[:60]}"}

        if section not in profile:
            return {"error": f"Section '{section}' inconnue."}

        # Fusion pour les listes
        current = profile[section].get(key)
        if isinstance(current, list) and isinstance(final_value, list):
            merged = list(dict.fromkeys(current + final_value))
            profile[section][key] = merged
        else:
            profile[section][key] = final_value

        save_profile(profile)
        return {"status": f"Profil mis à jour — {section}.{key} = {final_value}"}

    except Exception as e:
        return {"error": str(e)}

def get_ui_tree(window_title: str = None):
    """Récupère la structure textuelle d'une fenêtre (boutons, textes, etc.). 
    C'est beaucoup plus rapide que l'analyse d'image. Si window_title est None, prend la fenêtre active."""
    if not Desktop:
        return {"error": "Cet outil est uniquement supporté sur Windows."}
    try:
        if window_title:
            app = Desktop(backend="uia").window(title_re=f".*{window_title}.*")
        else:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if not active:
                return {"error": "Aucune fenêtre active détectée."}
            app = Desktop(backend="uia").window(handle=active._hWnd)
        
        elements = []
        for child in app.descendants():
            name = child.window_text()
            control_type = child.control_type()
            if name and len(name) > 1:
                elements.append(f"{control_type}: '{name}'")
        
        return {"window": app.window_text(), "elements": elements[:100]}
    except Exception as e:
        return {"error": str(e)}

def background_interact(window_title: str, element_name: str, action: str = "click", text: str = None):
    """Interagit avec une application en arrière-plan sans bouger la souris physique.
    Actions: 'click', 'type'. Utile pour Mobile Connecté, iTunes, etc."""
    if not Desktop:
        return {"error": "Cet outil est uniquement supporté sur Windows."}
    try:
        app = Desktop(backend="uia").window(title_re=f".*{window_title}.*")
        element = app.child_window(title=element_name)
        
        if action == "click":
            element.click_input(simulate_click=True)
            return {"status": f"Clic simulé sur '{element_name}' dans '{window_title}'"}
        elif action == "type":
            element.type_keys(text, with_spaces=True)
            return {"status": f"Texte '{text}' envoyé à '{element_name}'"}
    except Exception as e:
        return {"error": str(e)}

def click_element_by_name(element_name: str, window_title: str = None, action: str = 'click', text: str = None):
    """Clicks or types into a UI element found by its text label, without moving the physical mouse.
    - element_name: the target element's label text.
    - window_title: optional, window title filter.
    - action: 'click' or 'type'.
    - text: text to type when action is 'type'.
    """
    if not Desktop:
        return {"error": "Cet outil est uniquement supporté sur Windows."}
    try:
        if window_title:
            app = Desktop(backend="uia").window(title_re=f".*{window_title}.*")
        else:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if not active:
                return {"error": "Aucune fenêtre active détectée."}
            app = Desktop(backend="uia").window(handle=active._hWnd)
            
        try:
            element = app.child_window(title=element_name, control_type="Button")
            element.wait('exists', timeout=1)
        except Exception:
            element = app.child_window(title=element_name)
            
        if action == "click":
            try:
                element.invoke()
                return {"status": f"Clic (invoke) sur '{element_name}' effectué"}
            except Exception:
                element.click_input(simulate_click=True)
                return {"status": f"Clic simulé sur '{element_name}'"}
        elif action == "type":
            element.type_keys(text, with_spaces=True)
            return {"status": f"Texte '{text}' envoyé à '{element_name}'"}
        else:
            return {"error": f"Action non supportée: {action}"}
    except Exception as e:
        return {"error": f"Élément '{element_name}' non trouvé ou erreur: {str(e)}. Utilisez get_ui_tree() pour vérifier le nom de l'élément."}


def control_itunes(command: str):
    """Contrôle iTunes en arrière-plan (Play, Pause, Next, Previous, Volume)."""
    if not comtypes:
        return {"error": "Cet outil est uniquement supporté sur Windows."}
    try:
        itunes = comtypes.client.CreateObject("iTunes.Application")
        if command.lower() == "play": itunes.Play()
        elif command.lower() == "pause": itunes.Pause()
        elif command.lower() == "next": itunes.NextTrack()
        elif command.lower() == "previous": itunes.BackTrack()
        return {"status": f"Commande iTunes '{command}' exécutée."}
    except Exception as e:
        return {"error": f"iTunes n'est probablement pas lancé ou erreur : {str(e)}"}

def smart_media_control(action: str, app_hint: str = None) -> dict:
    """
    Contrôle la lecture multimédia EN ARRIÈRE-PLAN, sans toucher la souris.
    Fonctionne avec n'importe quelle app audio (Spotify, VLC, navigateur…)
    Cross-platform : Windows (VK_MEDIA) + Linux (playerctl/D-Bus)

    action   : 'play', 'pause', 'play_pause', 'next', 'previous', 'stop'
    app_hint : 'itunes' uniquement si l'utilisateur nomme explicitement iTunes
    """
    if app_hint and app_hint.lower() == 'itunes':
        return control_itunes(action)
    return media_control(action)

def wait_for_ui(seconds: float):
    """Met en pause l'exécution pour laisser le temps à une application de s'ouvrir ou à l'interface de se mettre à jour.
    TRÈS IMPORTANT: Après avoir appelé cet outil, tu dois ABSOLUMENT inclure le mot-clé [UPDATE_SCREEN] dans ta réponse finale pour que le système te renvoie une nouvelle capture d'écran avant ta prochaine action."""
    time.sleep(seconds)
    return {"status": f"Attente de {seconds} secondes terminée. Rédige ta réponse en incluant [UPDATE_SCREEN] pour continuer avec la nouvelle vue."}

def list_directory(path: str = "."):
    """Liste les fichiers et dossiers dans un chemin donné."""
    try:
        p = Path(path).expanduser().resolve()
        items = []
        for item in p.iterdir():
            items.append(f"{'[DIR]' if item.is_dir() else '[FILE]'} {item.name}")
        return {"items": items, "current_path": str(p)}
    except Exception as e:
        return {"error": str(e)}

def read_file(file_path: str):
    """Lit le contenu textuel d'un fichier."""
    try:
        path = Path(file_path).expanduser().resolve()
        text_extensions = {'.py', '.txt', '.md', '.json', '.js', '.html', '.css', '.c', '.cpp', '.h', '.rs', '.go', '.sh', '.bat', '.ps1', '.yaml', '.yml'}
        if path.suffix.lower() not in text_extensions:
             if path.stat().st_size > 50000:
                return {"error": "Type de fichier non supporté ou trop volumineux."}
        if path.stat().st_size > 500000:
            return {"error": "Fichier trop volumineux."}
        return {"content": path.read_text(encoding="utf-8", errors="replace")}
    except Exception as e:
        return {"error": str(e)}

def write_file(file_path: str, content: str, force: bool = False):
    """Écrit ou modifie un fichier texte.
    
    Par défaut, restreint l'écriture au dossier utilisateur (USERPROFILE).
    Passe force=True pour écrire ailleurs (chemins système, etc.) — à utiliser avec précaution.
    """
    try:
        path = Path(file_path).expanduser().resolve()
        user_root = Path(os.environ.get("USERPROFILE", os.path.expanduser("~"))).resolve()
        
        if not force and not str(path).startswith(str(user_root)):
            return {
                "error": f"Écriture refusée hors du dossier utilisateur ({user_root}). "
                         f"Utilise force=True si tu es certain de vouloir écrire dans '{path}'."
            }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"status": f"Fichier '{path}' écrit avec succès."}
    except Exception as e:
        return {"error": str(e)}

def search_files(query: str, root_dir: str = None):
    """Recherche des fichiers par nom. Utilise l'index Windows Search (instantané) ou scandir (rapide)."""
    matches = []
    
    if pyodbc:
        try:
            conn_str = "Driver={Search.CollatorDSO};Extended Properties='Application=Windows';"
            with pyodbc.connect(conn_str, autocommit=True) as conn:
                with conn.cursor() as cursor:
                    sql = f"SELECT TOP 50 System.ItemPathDisplay FROM SystemIndex WHERE System.FileName LIKE '%{query}%'"
                    cursor.execute(sql)
                    for row in cursor.fetchall():
                        matches.append(row[0])
            if matches:
                return {"matches": matches, "method": "windows_index"}
        except Exception:
            pass

    try:
        if not root_dir:
            user_dirs = [os.path.join(os.environ['USERPROFILE'], d) for d in ['Documents', 'Desktop', 'Downloads']]
            user_dirs.append(os.getcwd())
        else:
            user_dirs = [root_dir]

        for start_dir in user_dirs:
            if not os.path.exists(start_dir): continue
            for root, dirs, files in os.walk(start_dir):
                for name in files:
                    if query.lower() in name.lower():
                        matches.append(os.path.join(root, name))
                        if len(matches) >= 50: break
                if len(matches) >= 50: break
            if len(matches) >= 50: break
        
        return {"matches": matches, "method": "scandir"}
    except Exception as e:
        return {"error": str(e)}

def get_process_details(pid: int):
    """Récupère des détails avancés sur un processus (fichiers ouverts, connexions, chemin)."""
    try:
        p = psutil.Process(pid)
        return {
            "pid": pid,
            "name": p.name(),
            "exe": p.exe(),
            "status": p.status(),
            "create_time": time.ctime(p.create_time()),
            "cpu_percent": p.cpu_percent(interval=0.1),
            "memory_info": p.memory_info()._asdict(),
            "open_files": [f.path for f in p.open_files()][:20],
            "connections": [{"laddr": f"{c.laddr.ip}:{c.laddr.port}", "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None, "status": c.status} for c in p.connections()][:20]
        }
    except Exception as e:
        return {"error": str(e)}

def send_notification(title: str, message: str, urgency: str = "normal") -> dict:
    """Affiche une notification système (cross-platform)."""
    return _send_notification(title, message, urgency)

def inspect_image(file_path: str):
    """Permet à l'assistant de 'voir' une image sur le disque.
    Retourne l'image encodée en base64 pour que Gemini puisse l'analyser."""
    try:
        path = Path(file_path).expanduser().resolve()
        if path.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']:
            return {"error": "Format non supporté. Formats acceptés : png, jpg, jpeg, webp, bmp."}
        img = Image.open(path)
        img.thumbnail((1280, 720), Image.LANCZOS)
        buffer = io.BytesIO()
        fmt = "JPEG" if path.suffix.lower() in ['.jpg', '.jpeg'] else "PNG"
        img.save(buffer, format=fmt)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        mime = "image/jpeg" if fmt == "JPEG" else "image/png"
        return {
            "status": "Image chargée et encodée.",
            "path": str(path),
            "mime_type": mime,
            "base64_data": encoded
        }
    except Exception as e:
        return {"error": str(e)}

def execute_command(command: str, background: bool = False, timeout: int = 15) -> dict:
    """
    Exécute une commande système.
    background=True : lance en arrière-plan sans bloquer OMI (Popen détaché)
    background=False : attend le résultat (max timeout secondes)

    Exemples :
      execute_command("spotify", background=True)    # Lance Spotify sans bloquer
      execute_command("git status", timeout=5)       # Attend le résultat
    """
    if background:
        return launch_detached(command)
    else:
        return run_and_wait(command, timeout=timeout)

def get_active_window_info():
    """Récupère des infos sur les fenêtres ouvertes."""
    try:
        import pygetwindow as gw
        windows = gw.getAllWindows()
        active = gw.getActiveWindow()
        return {
            "active_window": active.title if active else "None",
            "all_windows": [w.title for w in windows if w.title]
        }
    except Exception as e:
        return {"error": str(e)}

def mouse_click(x: int, y: int):
    """Clique à une position spécifique sur l'écran.
    Les coordonnées sont basées sur la résolution de capture définie dans SCREEN_CAPTURE_SIZE."""
    try:
        import pyautogui
        capture_w, capture_h = SCREEN_CAPTURE_SIZE
        screen_w, screen_h = pyautogui.size()
        real_x = int(x * screen_w / capture_w)
        real_y = int(y * screen_h / capture_h)
        pyautogui.click(real_x, real_y)
        return {"status": f"Cliqué à {real_x}, {real_y} (depuis coordonnées capture {x}, {y})"}
    except Exception as e:
        return {"error": str(e)}

def type_text(text: str):
    """Tape du texte au clavier via le presse-papier (compatible AZERTY)."""
    try:
        import pyperclip
        import pyautogui
        import time
        
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.05)
        return {"status": f"Texte collé : {text}"}
    except Exception as e:
        return {"error": str(e)}

def press_key(*keys: str):
    """Appuie sur une ou plusieurs touches du clavier (ex: 'enter', 'tab', 'ctrl', 'c'). Pour les raccourcis, passe plusieurs arguments."""
    try:
        import pyautogui
        if len(keys) == 1:
            pyautogui.press(keys[0])
            return {"status": f"Touche appuyée : {keys[0]}"}
        else:
            pyautogui.hotkey(*keys)
            return {"status": f"Raccourci exécuté : {' + '.join(keys)}"}
    except Exception as e:
        return {"error": str(e)}

def query_transcript_history(query: str = None, limit: int = 50, speaker: str = None):
    """Consulte la base de données des transcriptions audio.
    
    - query  : recherche textuelle dans les transcriptions
    - speaker: filtre par source — 'User' (micro physique), 'System_Audio' (son interne), None (tout)
    - limit  : nombre maximum de résultats
    
    query et speaker peuvent être combinés.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if query and speaker:
            cursor.execute(
                'SELECT timestamp, speaker, text FROM transcripts '
                'WHERE text LIKE ? AND speaker = ? ORDER BY timestamp DESC LIMIT ?',
                (f'%{query}%', speaker, limit)
            )
        elif query:
            cursor.execute(
                'SELECT timestamp, speaker, text FROM transcripts '
                'WHERE text LIKE ? ORDER BY timestamp DESC LIMIT ?',
                (f'%{query}%', limit)
            )
        elif speaker:
            cursor.execute(
                'SELECT timestamp, speaker, text FROM transcripts '
                'WHERE speaker = ? ORDER BY timestamp DESC LIMIT ?',
                (speaker, limit)
            )
        else:
            cursor.execute(
                'SELECT timestamp, speaker, text FROM transcripts '
                'ORDER BY timestamp DESC LIMIT ?',
                (limit,)
            )

        rows = cursor.fetchall()
        conn.close()
        return {"transcripts": [{"timestamp": r[0], "speaker": r[1], "text": r[2]} for r in rows]}
    except Exception as e:
        return {"error": str(e)}

def open_url(url: str):
    """Ouvre une URL dans le navigateur ou lance une app via son URI (ex: 'ms-phone:', 'itunes:')."""
    try:
        webbrowser.open(url)
        return {"status": f"Ouverture de {url}"}
    except Exception as e:
        return {"error": str(e)}

def search_web(query: str):
    """Effectue une recherche Google."""
    try:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return {"status": f"Recherche Google lancée pour : {query}"}
    except Exception as e:
        return {"error": str(e)}

def get_system_stats():
    """Récupère les statistiques globales du système (CPU, RAM, Disque, Batterie)."""
    try:
        cpu_pct = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        battery = psutil.sensors_battery()
        
        return {
            "cpu_usage_pct": cpu_pct,
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_used_gb": round(ram.used / (1024**3), 2),
            "ram_available_gb": round(ram.available / (1024**3), 2),
            "ram_usage_pct": ram.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_usage_pct": disk.percent,
            "battery_pct": battery.percent if battery else "N/A",
            "battery_plugged": battery.power_plugged if battery else "N/A"
        }
    except Exception as e:
        return {"error": str(e)}

def list_processes(limit: int = 20, sort_by: str = 'cpu_percent'):
    """Liste les processus actifs. sort_by peut être 'cpu_percent' ou 'memory_percent'."""
    try:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        procs.sort(key=lambda x: x.get(sort_by, 0) or 0, reverse=True)
        return {"processes": procs[:limit]}
    except Exception as e:
        return {"error": str(e)}

def kill_process(pid: int):
    """Termine un processus par son PID."""
    try:
        p = psutil.Process(pid)
        name = p.name()
        p.terminate()
        return {"status": f"Processus {pid} ({name}) terminé."}
    except Exception as e:
        return {"error": str(e)}

def get_clipboard():
    """Récupère le contenu actuel du presse-papier."""
    try:
        return {"content": pyperclip.paste()}
    except Exception as e:
        return {"error": str(e)}

def set_clipboard(text: str):
    """Définit le contenu du presse-papier."""
    try:
        pyperclip.copy(text)
        return {"status": "Texte copié dans le presse-papier."}
    except Exception as e:
        return {"error": str(e)}

def get_network_connections(limit: int = 50):
    """Liste les connexions réseau actives."""
    try:
        connections = []
        for conn in psutil.net_connections(kind='inet'):
            connections.append({
                "fd": conn.fd,
                "family": str(conn.family),
                "type": str(conn.type),
                "laddr": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                "raddr": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                "status": conn.status,
                "pid": conn.pid
            })
        return {"connections": connections[:limit]}
    except Exception as e:
        return {"error": str(e)}

def get_machine_info():
    """Récupère les informations sur la machine et l'environnement (OS, utilisateur, variables d'env)."""
    try:
        env_vars = {k: v for k, v in os.environ.items() 
                    if not any(secret in k.upper() for secret in ["KEY", "SECRET", "TOKEN", "PASS", "AUTH"])}
        try:
            user = os.getlogin()
        except Exception:
            try:
                import getpass
                user = getpass.getuser()
            except Exception:
                user = os.environ.get('USERNAME') or os.environ.get('USER') or "Unknown"
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "node": platform.node(),
            "user": user,
            "cwd": os.getcwd(),
            "env_vars": env_vars
        }
    except Exception as e:
        return {"error": str(e)}

def get_windows_event_logs(log_type: str = "System", count: int = 10):
    """Lit les derniers événements des logs Windows (System, Application, Security)."""
    if not win32evtlog:
        return {"error": "win32evtlog n'est pas disponible."}
    try:
        server = 'localhost'
        hand = win32evtlog.OpenEventLog(server, log_type)
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        total = win32evtlog.GetNumberOfEventLogRecords(hand)
        
        events = []
        while len(events) < count:
            objects = win32evtlog.ReadEventLog(hand, flags, 0)
            if not objects:
                break
            for obj in objects:
                if len(events) >= count:
                    break
                events.append({
                    "time": obj.TimeGenerated.Format(),
                    "source": obj.SourceName,
                    "event_id": obj.EventID,
                    "type": obj.EventType,
                    "message": obj.StringInserts
                })
        return {"log_type": log_type, "total_records": total, "recent_events": events}
    except Exception as e:
        return {"error": str(e)}

def launch_app_background(app_name: str, args: list = None) -> dict:
    """
    Lance une application en arrière-plan par son nom commun.
    Cross-platform. L'app survit si OMI s'arrête.

    app_name : 'spotify', 'chrome', 'firefox', 'vscode', 'terminal', etc.
    args     : arguments supplémentaires (ex: ["https://google.com"] pour Chrome)

    [PRIORITÉ 1 pour lancer des apps — toujours avant execute_command]
    """
    return launch_app(app_name, args or [])


def control_volume(level: int) -> dict:
    """
    Règle le volume système à un niveau de 0 à 100.
    Cross-platform : Windows (Core Audio) + Linux (pactl/PipeWire)

    Exemples :
      control_volume(50)   # Moitié du volume
      control_volume(0)    # Muet
      control_volume(100)  # Maximum
    """
    return set_volume(level)


def get_volume_level() -> dict:
    """Récupère le volume système actuel (0-100) et l'état muet."""
    return get_volume()


def find_process(name: str) -> dict:
    """
    Cherche des processus en cours par nom (partiel, insensible à la casse).
    Plus pratique que list_processes() pour trouver une app spécifique.

    Exemple : find_process("spotify") → tous les processus Spotify
    """
    found = get_process_by_name(name)
    if not found:
        return {"status": f"Aucun processus '{name}' trouvé"}
    return {"processes": found, "count": len(found)}


def terminate_app(name: str, force: bool = False) -> dict:
    """
    Termine une application par son nom (plus simple que kill_process qui nécessite un PID).
    force=True force la fermeture immédiate (SIGKILL).

    Exemples :
      terminate_app("spotify")
      terminate_app("chrome", force=True)
    """
    return kill_by_name(name, force)


def schedule_reminder(name: str, command: str,
                      delay_minutes: int = None, run_at_time: str = None) -> dict:
    """
    Planifie une tâche ou un rappel pour plus tard, en arrière-plan.
    Ne bloque pas. La tâche s'exécutera même si OMI est fermé (via OS scheduler).

    name          : nom du rappel (ex: "Rappel réunion")
    command       : commande à exécuter (ex: "notify-send 'Standup!'")
    delay_minutes : dans combien de minutes (ex: 30)
    run_at_time   : heure exacte "HH:MM" ou "YYYY-MM-DD HH:MM"

    Exemples :
      schedule_reminder("Pause", "notify-send 'Pause!'", delay_minutes=45)
      schedule_reminder("Standup", "notify-send 'Standup!'", run_at_time="09:55")
      schedule_reminder("Musique off", "playerctl stop", delay_minutes=60)
    """
    return schedule_task(name, command, delay_minutes, run_at_time)


def list_reminders() -> dict:
    """Liste les rappels/tâches planifiés par OMI."""
    return list_scheduled_tasks()


def cancel_reminder(task_id: int) -> dict:
    """Annule un rappel planifié par son ID (obtenu via list_reminders)."""
    return cancel_task(task_id)


def web_search(query: str, max_results: int = 5) -> dict:
    """
    Recherche sur internet et retourne les résultats directement.
    PAS de popup navigateur — les résultats sont donnés à Gemini.
    Utilise DuckDuckGo Instant Answer (gratuit, pas de clé API).

    Utilise cet outil pour répondre à des questions factuelles en temps réel :
    météo, cours de bourse, actualités, définitions, calculs, etc.

    [PRIORITÉ 1 pour toute recherche internet — avant open_url ou search_web]
    """
    return search_web_headless(query, max_results)


def fetch_url_content(url: str, max_chars: int = 3000) -> dict:
    """
    Récupère et lit le contenu textuel d'une page web, sans ouvrir de navigateur.
    Utile pour lire un article, une documentation, un prix, etc.

    Note : ne fonctionne pas sur les sites nécessitant JavaScript (SPAs).
    """
    return fetch_page_text(url, max_chars)


TOOLS_LIST = [
    # ── PRIORITÉ 1 : Arrière-plan total, zéro interruption ──────────────────
    smart_media_control,      # Media play/pause/next (Windows + Linux)
    control_volume,           # Volume système (Windows + Linux)
    launch_app_background,    # Lancer une app détachée
    execute_command,          # Commande shell (background=True pour détacher)
    web_search,               # Recherche internet → résultats directs
    fetch_url_content,        # Lire une page web
    schedule_reminder,        # Planifier une tâche
    list_reminders,           # Voir les tâches planifiées
    cancel_reminder,          # Annuler une tâche

    # ── PRIORITÉ 2 : Interaction UI sans souris (Windows) ────────────────────
    get_ui_tree,
    click_element_by_name,
    background_interact,
    control_itunes,

    # ── PRIORITÉ 3 : Lecture système ─────────────────────────────────────────
    get_active_window_info,
    list_directory,
    read_file,
    write_file,
    search_files,
    inspect_image,
    get_clipboard,
    set_clipboard,
    get_system_stats,
    list_processes,
    find_process,            # Chercher par nom (plus simple que list_processes)
    get_process_details,
    kill_process,            # Par PID
    terminate_app,           # Par nom d'app
    get_network_connections,
    get_machine_info,
    get_windows_event_logs,

    # ── PRIORITÉ 4 : Communication ───────────────────────────────────────────
    send_notification,
    open_url,                # Ouvre dans le navigateur (pour navigation manuelle)
    query_transcript_history,
    wait_for_ui,

    # ── DERNIER RECOURS : Souris/clavier physiques ───────────────────────────
    mouse_click,
    type_text,
    press_key,

    # ── Profil ───────────────────────────────────────────────────────────────
    get_user_profile,
    update_user_profile,
]


def get_active_app_name() -> str:
    """Récupère de façon cross-platform le nom exact de l'exécutable actif."""
    try:
        import psutil
        if os.name == 'nt':
            try:
                import win32gui
                import win32process
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid:
                        return psutil.Process(pid).name()
            except Exception:
                pass
        else:
            try:
                import subprocess
                pid_out = subprocess.check_output(["xdotool", "getactivewindow", "getwindowpid"], stderr=subprocess.DEVNULL)
                pid = int(pid_out.strip())
                if pid:
                    return psutil.Process(pid).name()
            except Exception:
                pass
    except Exception:
        pass
    return "Unknown"


def send_message_with_retry(session, prompt, images=None, max_retries=3):
    """Envoie un message à Gemini avec retry exponentiel en cas d'erreur de quota (429)."""
    import time
    delay = 1.0
    for attempt in range(max_retries):
        try:
            if images:
                return session.send_message([prompt] + images)
            else:
                return session.send_message(prompt)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resource_exhausted" in err_str or "exhausted" in err_str or "quota" in err_str:
                if attempt == max_retries - 1:
                    raise e
                print(f"[Gemini] Quota dépassé (429), nouvel essai dans {delay}s...")
                time.sleep(delay)
                delay *= 2.0
            else:
                raise e
