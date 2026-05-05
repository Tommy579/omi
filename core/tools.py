import os
import subprocess
from pathlib import Path
from PIL import Image
import base64
import io
import time
import platform
import psutil
import pyperclip
import pyodbc
try:
    import win32evtlog
except ImportError:
    win32evtlog = None
from pywinauto import Desktop, Application
import comtypes.client

def get_ui_tree(window_title: str = None):
    """Récupère la structure textuelle d'une fenêtre (boutons, textes, etc.). 
    C'est beaucoup plus rapide que l'analyse d'image. Si window_title est None, prend la fenêtre active."""
    try:
        # On utilise le backend 'uia' pour les apps modernes comme Mobile Connecté
        if window_title:
            app = Desktop(backend="uia").window(title_re=f".*{window_title}.*")
        else:
            app = Desktop(backend="uia").active_window()
        
        # On récupère les éléments importants pour ne pas saturer le contexte
        elements = []
        for child in app.descendants():
            name = child.window_text()
            control_type = child.control_type()
            if name and len(name) > 1:
                elements.append(f"{control_type}: '{name}'")
        
        return {"window": app.window_text(), "elements": elements[:100]} # Limite à 100 éléments
    except Exception as e:
        return {"error": str(e)}

def background_interact(window_title: str, element_name: str, action: str = "click", text: str = None):
    """Interagit avec une application en arrière-plan sans bouger la souris physique.
    Actions: 'click', 'type'. Utile pour Mobile Connecté, iTunes, etc."""
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

def control_itunes(command: str):
    """Contrôle iTunes en arrière-plan (Play, Pause, Next, Previous, Volume)."""
    try:
        itunes = comtypes.client.CreateObject("iTunes.Application")
        if command.lower() == "play": itunes.Play()
        elif command.lower() == "pause": itunes.Pause()
        elif command.lower() == "next": itunes.NextTrack()
        elif command.lower() == "previous": itunes.BackTrack()
        return {"status": f"Commande iTunes '{command}' exécutée."}
    except Exception as e:
        return {"error": f"iTunes n'est probablement pas lancé ou erreur : {str(e)}"}

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

def write_file(file_path: str, content: str):
    """Écrit ou modifie un fichier texte. Utile pour corriger du code ou prendre des notes."""
    try:
        path = Path(file_path).expanduser().resolve()
        path.write_text(content, encoding="utf-8")
        return {"status": f"Fichier '{file_path}' écrit avec succès."}
    except Exception as e:
        return {"error": str(e)}

def search_files(query: str, root_dir: str = None):
    """Recherche des fichiers par nom. Utilise l'index Windows Search (instantané) ou scandir (rapide)."""
    matches = []
    
    # Tentative via Windows Search Index (instantané)
    try:
        conn_str = "Driver={Search.CollatorDSO};Extended Properties='Application=Windows';"
        with pyodbc.connect(conn_str, autocommit=True) as conn:
            with conn.cursor() as cursor:
                # On cherche dans l'index. System.ItemPathDisplay est le chemin complet.
                sql = f"SELECT TOP 50 System.ItemPathDisplay FROM SystemIndex WHERE System.FileName LIKE '%{query}%'"
                cursor.execute(sql)
                for row in cursor.fetchall():
                    matches.append(row[0])
        if matches:
            return {"matches": matches, "method": "windows_index"}
    except Exception:
        pass # Fallback sur scandir si l'index échoue

    # Fallback sur os.scandir (beaucoup plus rapide que rglob)
    try:
        if not root_dir:
            # On restreint par défaut aux dossiers utilisateurs courants pour la rapidité
            user_dirs = [os.path.join(os.environ['USERPROFILE'], d) for d in ['Documents', 'Desktop', 'Downloads']]
            # On ajoute le dossier courant
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

def send_notification(title: str, message: str):
    """Affiche une notification Windows (Toast)."""
    try:
        from win10toast_persist import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=5, threaded=True)
        return {"status": "Notification envoyée."}
    except Exception as e:
        return {"error": str(e)}

def inspect_image(file_path: str):
    """Permet à l'assistant de 'voir' une image sur le disque."""
    try:
        path = Path(file_path).expanduser().resolve()
        if path.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']:
            return {"error": "Ce n'est pas une image supportée."}
        img = Image.open(path)
        img.thumbnail((1280, 720), Image.LANCZOS)
        return {"status": "Image chargée.", "path": str(path)}
    except Exception as e:
        return {"error": str(e)}

def execute_command(command: str):
    """Exécute une commande système (Prudence !)."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        return {"error": str(e)}

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
    """Clique à une position spécifique sur l'écran (coordonnées basées sur une image 1280x720)."""
    try:
        import pyautogui
        screen_w, screen_h = pyautogui.size()
        real_x = int(x * screen_w / 1280)
        real_y = int(y * screen_h / 720)
        pyautogui.click(real_x, real_y)
        return {"status": f"Cliqué à {real_x}, {real_y} (échelle {x}, {y})"}
    except Exception as e:
        return {"error": str(e)}

def type_text(text: str):
    """Tape du texte au clavier."""
    try:
        import pyautogui
        pyautogui.write(text, interval=0.01)
        return {"status": f"Texte tapé : {text}"}
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

from core.database import query_transcripts, search_transcripts

def query_transcript_history(query: str = None, limit: int = 50):
    """Consulte la base de données des transcriptions."""
    try:
        if query:
            rows = search_transcripts(query)[:limit]
        else:
            rows = query_transcripts(limit=limit)
        return {"transcripts": [{"timestamp": r[0], "speaker": r[1], "text": r[2]} for r in rows]}
    except Exception as e:
        return {"error": str(e)}

import webbrowser
import urllib.parse

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
        
        # On trie et on limite
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
        # On filtre les variables d'env sensibles
        env_vars = {k: v for k, v in os.environ.items() 
                    if not any(secret in k.upper() for secret in ["KEY", "SECRET", "TOKEN", "PASS", "AUTH"])}
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "node": platform.node(),
            "user": os.getlogin() if hasattr(os, 'getlogin') else os.environ.get('USERNAME'),
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

TOOLS_LIST = [
    list_directory, 
    read_file, 
    write_file,
    search_files, 
    inspect_image, 
    execute_command, 
    get_active_window_info,
    mouse_click,
    type_text,
    press_key,
    query_transcript_history,
    open_url,
    search_web,
    wait_for_ui,
    get_ui_tree,
    background_interact,
    control_itunes,
    get_system_stats,
    list_processes,
    get_process_details,
    kill_process,
    get_clipboard,
    set_clipboard,
    get_network_connections,
    get_machine_info,
    get_windows_event_logs,
    send_notification
]
