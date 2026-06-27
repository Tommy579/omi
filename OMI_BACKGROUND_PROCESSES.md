# OMI — Gestion de processus en arrière-plan (Windows + Linux)

## Réponse directe : est-ce possible ?

**Oui, complètement — et sans C.**

Python's `subprocess.Popen` appelle directement les primitives OS (`CreateProcess` sur Windows, `fork/exec` sur Linux). Les seules situations où du C apporterait un vrai gain sont :
- Des hooks kernel temps-réel (surveiller chaque accès fichier, intercepter des syscalls)
- Un daemon natif ultra-léger tournant en ring-0
- Des bindings à des APIs Win32/Linux non exposées par Python

Pour ce que tu décris (lancer la musique, planifier, chercher sur internet, tout en arrière-plan), **Python + ctypes suffit largement** — et c'est déjà le pattern utilisé dans `smart_media_control` pour les touches médias Windows.

---

## État actuel du projet (analyse du code réel)

### Ce qui existe déjà ✅
| Outil | Fonctionnement | Problème |
|---|---|---|
| `execute_command(cmd)` | `subprocess.run(shell=True, timeout=10)` | **Bloquant 10s max**, tue le process si OMI quitte |
| `smart_media_control(action)` | `ctypes.windll.user32.keybd_event` (VK_MEDIA) | **Windows only**, Linux = erreur |
| `list_processes()` | `psutil.process_iter()` | ✅ Cross-platform |
| `kill_process(pid)` | `psutil.Process(pid).terminate()` | ✅ Cross-platform |
| `get_process_details(pid)` | `psutil.Process(pid)` | ✅ Cross-platform |
| `launch_app` via `execute_command` | `start appname.exe` (Windows) | Windows only, bloquant |

### Ce qui manque ❌
1. **Lancement détaché** : `execute_command` utilise `subprocess.run` (bloquant). Un process lancé par OMI meurt si OMI quitte. Il faut `Popen` avec les bons flags.
2. **Contrôle média Linux** : `smart_media_control` fait `ctypes.windll` → crash immédiat sur Linux. Il faut `playerctl` ou D-Bus.
3. **Recherche web sans browser** : `search_web` ouvre Chrome/Firefox en premier plan, prend le focus. Il faut une API headless.
4. **Scheduling** : zéro support. Ni `at`, ni `cron`, ni Task Scheduler Windows.
5. **Volume système cross-platform** : non implémenté.
6. **Lancement par nom d'app** : il faut savoir que "spotify" → `spotify.exe` sur Windows, `spotify` sur Linux, avec fallback sur les deep links.

---

## Plan d'action

### Nouveaux fichiers à créer
```
core/
  process_manager.py     # Lancement/monitoring de processus détachés (cross-platform)
  system_bridge.py       # Media, volume, notifications, clipboard (cross-platform)
  scheduler.py           # Planification de tâches (cross-platform)
  web_fetcher.py         # Recherche web headless (pas de browser popup)
```

### Fichiers à modifier
```
core/tools.py            # Ajouter les nouveaux outils dans TOOLS_LIST + remplacer smart_media_control
omi-2.0-prompt.md        # Mettre à jour la hiérarchie des outils
```

---

## Implémentation détaillée

### 1. `core/process_manager.py` — Lancement de processus détachés

Ce module remplace l'usage direct de `execute_command` pour tout ce qui doit tourner en arrière-plan sans bloquer OMI et sans mourir quand OMI s'arrête.

```python
"""
core/process_manager.py
Lancement et gestion de processus en arrière-plan, cross-platform.
Utilise Popen avec les bons flags pour détacher le process du process parent.
"""

import os
import subprocess
import platform
import psutil
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"

# Flags Windows pour lancer un process en arrière-plan, sans console
WIN_DETACHED = 0x00000008   # DETACHED_PROCESS
WIN_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW
WIN_NEW_GROUP = 0x00000200  # CREATE_NEW_PROCESS_GROUP


def launch_detached(command: str | list, cwd: str = None) -> dict:
    """
    Lance un processus complètement détaché d'OMI :
    - Ne bloque pas OMI
    - Ne meurt pas quand OMI s'arrête
    - N'affiche pas de fenêtre console
    - Cross-platform (Windows + Linux)

    command : str (shell) ou list (args directs, préférable)
    cwd     : répertoire de travail optionnel
    """
    try:
        kwargs = dict(
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
        )

        if IS_WINDOWS:
            # DETACHED_PROCESS + CREATE_NO_WINDOW = process totalement invisible
            # Le process survit à la fermeture d'OMI
            kwargs["creationflags"] = WIN_DETACHED | WIN_NO_WINDOW | WIN_NEW_GROUP
            if isinstance(command, str):
                kwargs["shell"] = True
        else:
            # start_new_session=True = setsid() → détache du terminal parent
            # Le process survit à la fermeture d'OMI
            kwargs["start_new_session"] = True
            if isinstance(command, str):
                kwargs["shell"] = True

        proc = subprocess.Popen(command, **kwargs)
        return {
            "status": "lancé en arrière-plan",
            "pid": proc.pid,
            "command": command if isinstance(command, str) else " ".join(command)
        }
    except FileNotFoundError:
        return {"error": f"Commande introuvable : {command}"}
    except Exception as e:
        return {"error": str(e)}


def run_and_wait(command: str | list, timeout: int = 15, cwd: str = None) -> dict:
    """
    Exécute une commande et attend le résultat (pour les commandes courtes).
    Amélioration de l'ancien execute_command : timeout configurable,
    gestion propre des erreurs, cross-platform.
    """
    try:
        flags = {}
        if IS_WINDOWS:
            flags["creationflags"] = WIN_NO_WINDOW

        result = subprocess.run(
            command,
            shell=isinstance(command, str),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            **flags
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout après {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


def launch_app(app_name: str, args: list = None) -> dict:
    """
    Lance une application par son nom commun, cross-platform.
    Gère les deep links, les noms d'exécutables, et les apps packagées.

    Exemples :
      launch_app("spotify")
      launch_app("chrome", ["https://google.com"])
      launch_app("code", ["/home/user/project"])
    """
    args = args or []

    # Mapping nom commun → commande par OS
    APP_MAP = {
        "windows": {
            "spotify":    ["start", "spotify:"],
            "chrome":     ["start", "chrome"],
            "firefox":    ["start", "firefox"],
            "vscode":     ["code"],
            "notepad":    ["notepad.exe"],
            "explorer":   ["explorer.exe"],
            "calculator": ["calc.exe"],
            "terminal":   ["wt.exe"],   # Windows Terminal
        },
        "linux": {
            "spotify":    ["spotify"],
            "chrome":     ["google-chrome-stable"],
            "firefox":    ["firefox"],
            "vscode":     ["code"],
            "notepad":    ["gedit"],
            "explorer":   ["dolphin"],  # KDE file manager
            "calculator": ["kcalc"],    # KDE, ou "gnome-calculator"
            "terminal":   ["konsole"],  # KDE, ou "gnome-terminal"
        }
    }

    os_key = "windows" if IS_WINDOWS else "linux"
    name_lower = app_name.lower().strip()

    if name_lower in APP_MAP[os_key]:
        cmd = APP_MAP[os_key][name_lower] + args
    else:
        # Essai direct par nom
        cmd = [app_name] + args

    return launch_detached(cmd)


def get_process_by_name(name: str) -> list:
    """
    Cherche des processus en cours par nom (partiel, insensible à la casse).
    Retourne la liste des processus trouvés avec pid, nom, cpu%, ram%.
    """
    results = []
    name_lower = name.lower()
    for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_percent']):
        try:
            if name_lower in proc.info['name'].lower():
                results.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "status": proc.info['status'],
                    "cpu_percent": proc.info['cpu_percent'],
                    "memory_percent": round(proc.info['memory_percent'] or 0, 2)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return results


def kill_by_name(name: str, force: bool = False) -> dict:
    """
    Termine tous les processus correspondant au nom donné.
    force=True utilise SIGKILL/TerminateProcess au lieu de SIGTERM/terminate().
    """
    found = get_process_by_name(name)
    if not found:
        return {"error": f"Aucun processus trouvé avec le nom '{name}'"}

    killed = []
    errors = []
    for proc_info in found:
        try:
            p = psutil.Process(proc_info['pid'])
            if force:
                p.kill()
            else:
                p.terminate()
            killed.append(f"{proc_info['name']} (PID {proc_info['pid']})")
        except Exception as e:
            errors.append(str(e))

    return {
        "killed": killed,
        "errors": errors if errors else None
    }
```

---

### 2. `core/system_bridge.py` — Media, volume, notifications (cross-platform)

Ce module centralise toutes les interactions système qui ont une implémentation différente sur Windows et Linux.

```python
"""
core/system_bridge.py
Pont système cross-platform : media, volume, notifications, calendrier.
"""

import platform
import subprocess
import os

IS_WINDOWS = platform.system() == "Windows"


# ──────────────────────────────────────────────────────────────────────────────
# CONTRÔLE MÉDIA
# ──────────────────────────────────────────────────────────────────────────────

def media_control(action: str) -> dict:
    """
    Contrôle la lecture multimédia EN ARRIÈRE-PLAN, sans toucher la souris.
    Fonctionne avec n'importe quelle app audio active (Spotify, VLC, navigateur…)

    action : 'play', 'pause', 'play_pause', 'next', 'previous', 'stop'

    Windows : envoie une touche média via keybd_event (VK_MEDIA_*)
    Linux   : utilise playerctl (universel) ou D-Bus en fallback
    """
    if IS_WINDOWS:
        return _media_control_windows(action)
    else:
        return _media_control_linux(action)


def _media_control_windows(action: str) -> dict:
    import ctypes
    VK_MAP = {
        'play':       0xB3,   # VK_MEDIA_PLAY_PAUSE
        'pause':      0xB3,
        'play_pause': 0xB3,
        'next':       0xB0,   # VK_MEDIA_NEXT_TRACK
        'previous':   0xB1,   # VK_MEDIA_PREV_TRACK
        'stop':       0xB2,   # VK_MEDIA_STOP
    }
    vk = VK_MAP.get(action.lower())
    if not vk:
        return {"error": f"Action inconnue : {action}. Valeurs : play, pause, next, previous, stop"}
    try:
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        return {"status": f"Commande média '{action}' envoyée (Windows VK_MEDIA)"}
    except Exception as e:
        return {"error": str(e)}


def _media_control_linux(action: str) -> dict:
    """
    Utilise playerctl (disponible sur Arch : sudo pacman -S playerctl)
    Fallback : D-Bus MPRIS si playerctl absent.
    playerctl fonctionne avec Spotify, VLC, navigateurs, Rhythmbox, etc.
    """
    PLAYERCTL_MAP = {
        'play':       'play',
        'pause':      'pause',
        'play_pause': 'play-pause',
        'next':       'next',
        'previous':   'previous',
        'stop':       'stop',
    }
    cmd_action = PLAYERCTL_MAP.get(action.lower())
    if not cmd_action:
        return {"error": f"Action inconnue : {action}"}

    # Essai 1 : playerctl (recommandé, universel)
    try:
        result = subprocess.run(
            ['playerctl', cmd_action],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            return {"status": f"playerctl {cmd_action} — OK"}
        # playerctl installé mais pas de player actif
        return {"error": f"playerctl: {result.stderr.strip() or 'aucun lecteur actif'}"}
    except FileNotFoundError:
        pass  # playerctl non installé, essayer D-Bus

    # Essai 2 : D-Bus MPRIS via python-dbus
    try:
        import dbus  # pip install dbus-python (nécessite libdbus-1-dev)
        bus = dbus.SessionBus()
        # Trouver le premier lecteur MPRIS actif
        for service in bus.list_names():
            if service.startswith('org.mpris.MediaPlayer2.'):
                obj = bus.get_object(service, '/org/mpris/MediaPlayer2')
                iface = dbus.Interface(obj, 'org.mpris.MediaPlayer2.Player')
                dbus_map = {
                    'play': iface.Play,
                    'pause': iface.Pause,
                    'play_pause': iface.PlayPause,
                    'next': iface.Next,
                    'previous': iface.Previous,
                    'stop': iface.Stop,
                }
                dbus_map[cmd_action]()
                return {"status": f"D-Bus MPRIS {cmd_action} → {service}"}
        return {"error": "Aucun lecteur MPRIS actif détecté"}
    except ImportError:
        pass

    return {
        "error": "Contrôle média non disponible. Installe playerctl : sudo pacman -S playerctl",
        "fix": "sudo pacman -S playerctl  (Arch) | sudo apt install playerctl  (Ubuntu)"
    }


# ──────────────────────────────────────────────────────────────────────────────
# CONTRÔLE VOLUME
# ──────────────────────────────────────────────────────────────────────────────

def set_volume(level: int) -> dict:
    """
    Règle le volume système à un niveau de 0 à 100.
    Windows : ctypes + Core Audio API
    Linux   : pactl (PulseAudio/PipeWire)
    """
    level = max(0, min(100, level))

    if IS_WINDOWS:
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            # pycaw utilise une échelle 0.0 → 1.0
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            return {"status": f"Volume Windows réglé à {level}%"}
        except ImportError:
            # Fallback : nircmd (si installé)
            val = int(level * 655.35)  # 0-65535
            result = subprocess.run(
                ['nircmd.exe', 'setsysvolume', str(val)],
                capture_output=True, timeout=3
            )
            if result.returncode == 0:
                return {"status": f"Volume réglé à {level}% via nircmd"}
            return {"error": "Installe pycaw (pip install pycaw) ou nircmd pour contrôler le volume"}
    else:
        try:
            subprocess.run(
                ['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{level}%'],
                check=True, capture_output=True, timeout=3
            )
            return {"status": f"Volume Linux réglé à {level}% (pactl)"}
        except FileNotFoundError:
            # Fallback amixer (ALSA)
            try:
                subprocess.run(
                    ['amixer', '-q', 'set', 'Master', f'{level}%'],
                    check=True, capture_output=True, timeout=3
                )
                return {"status": f"Volume réglé à {level}% (amixer)"}
            except Exception as e:
                return {"error": f"pactl et amixer non disponibles : {e}"}
        except Exception as e:
            return {"error": str(e)}


def get_volume() -> dict:
    """Récupère le volume système actuel (0-100)."""
    if IS_WINDOWS:
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            level = round(volume.GetMasterVolumeLevelScalar() * 100)
            muted = volume.GetMute()
            return {"volume": level, "muted": bool(muted)}
        except Exception as e:
            return {"error": str(e)}
    else:
        try:
            out = subprocess.check_output(
                ['pactl', 'get-sink-volume', '@DEFAULT_SINK@'],
                text=True, timeout=3
            )
            # Format : "Volume: front-left: 65536 / 100% ..."
            import re
            match = re.search(r'(\d+)%', out)
            level = int(match.group(1)) if match else -1
            mute_out = subprocess.check_output(
                ['pactl', 'get-sink-mute', '@DEFAULT_SINK@'],
                text=True, timeout=3
            )
            muted = 'yes' in mute_out.lower()
            return {"volume": level, "muted": muted}
        except Exception as e:
            return {"error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS
# ──────────────────────────────────────────────────────────────────────────────

def send_notification(title: str, message: str, urgency: str = "normal") -> dict:
    """
    Envoie une notification système.
    Windows : win10toast (non-bloquant, threaded=True)
    Linux   : notify-send (libnotify)

    urgency : 'low', 'normal', 'critical' (Linux only)
    """
    if IS_WINDOWS:
        try:
            from win10toast_persist import ToastNotifier
            ToastNotifier().show_toast(title, message, duration=5, threaded=True)
            return {"status": "Notification Windows envoyée"}
        except Exception as e:
            return {"error": str(e)}
    else:
        try:
            subprocess.Popen(
                ['notify-send', '-u', urgency, title, message],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return {"status": "Notification Linux envoyée (notify-send)"}
        except FileNotFoundError:
            return {"error": "notify-send non installé. sudo pacman -S libnotify"}
        except Exception as e:
            return {"error": str(e)}
```

---

### 3. `core/scheduler.py` — Planification de tâches

```python
"""
core/scheduler.py
Planification de tâches en arrière-plan, cross-platform.

Windows : Windows Task Scheduler via schtasks.exe (pas besoin d'admin)
Linux   : at (immédiat) + cron (récurrent)

Note : OMI lui-même peut aussi maintenir une file de tâches en mémoire
pour les tâches courtes (<= quelques heures), indépendamment de l'OS.
"""

import platform
import subprocess
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"

# DB locale pour les tâches planifiées par OMI lui-même
SCHEDULER_DB = Path(__file__).parent.parent / "omi_scheduler.db"


def _init_scheduler_db():
    conn = sqlite3.connect(SCHEDULER_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            command   TEXT NOT NULL,
            run_at    TEXT NOT NULL,           -- ISO datetime
            created   TEXT NOT NULL,
            status    TEXT DEFAULT 'pending',  -- pending/done/error
            result    TEXT
        )
    """)
    conn.commit()
    conn.close()


_init_scheduler_db()


def schedule_task(name: str, command: str, delay_minutes: int = None,
                  run_at_time: str = None) -> dict:
    """
    Planifie une commande système pour s'exécuter plus tard, en arrière-plan.
    La tâche est stockée dans la DB locale d'OMI ET dans le planificateur OS.

    name          : nom lisible de la tâche (ex: "Rappel réunion")
    command       : commande à exécuter (ex: "notify-send 'Réunion dans 5 min'")
    delay_minutes : exécuter dans N minutes
    run_at_time   : heure exacte, format "HH:MM" (aujourd'hui) ou "YYYY-MM-DD HH:MM"

    Exemples d'usage par Gemini :
      schedule_task("Musique off", "playerctl stop", delay_minutes=30)
      schedule_task("Rappel standup", "notify-send 'Standup!'", run_at_time="09:55")
    """
    # Calculer l'heure d'exécution
    now = datetime.now()
    if delay_minutes is not None:
        run_at = now + timedelta(minutes=delay_minutes)
    elif run_at_time is not None:
        try:
            if len(run_at_time) == 5:  # "HH:MM"
                run_at = datetime.strptime(f"{now.date()} {run_at_time}", "%Y-%m-%d %H:%M")
                if run_at < now:
                    run_at += timedelta(days=1)  # Demain si l'heure est passée
            else:
                run_at = datetime.strptime(run_at_time, "%Y-%m-%d %H:%M")
        except ValueError as e:
            return {"error": f"Format d'heure invalide : {e}. Utilise 'HH:MM' ou 'YYYY-MM-DD HH:MM'"}
    else:
        return {"error": "Précise delay_minutes ou run_at_time"}

    # Stocker en DB OMI
    conn = sqlite3.connect(SCHEDULER_DB)
    cursor = conn.execute(
        "INSERT INTO tasks (name, command, run_at, created) VALUES (?, ?, ?, ?)",
        (name, command, run_at.isoformat(), now.isoformat())
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Enregistrer dans le planificateur OS
    os_result = _schedule_os(name, command, run_at)

    return {
        "status": f"Tâche '{name}' planifiée pour {run_at.strftime('%H:%M le %d/%m')}",
        "task_id": task_id,
        "run_at": run_at.isoformat(),
        "os_scheduler": os_result
    }


def _schedule_os(name: str, command: str, run_at: datetime) -> str:
    """Enregistre la tâche dans le planificateur natif OS."""
    if IS_WINDOWS:
        return _schedule_windows(name, command, run_at)
    else:
        return _schedule_linux_at(command, run_at)


def _schedule_windows(name: str, command: str, run_at: datetime) -> str:
    """Windows Task Scheduler via schtasks.exe — pas besoin d'admin."""
    time_str = run_at.strftime("%H:%M")
    date_str = run_at.strftime("%m/%d/%Y")
    safe_name = f"OMI_{name.replace(' ', '_')[:30]}"
    result = subprocess.run([
        'schtasks', '/create', '/tn', safe_name,
        '/tr', command,
        '/sc', 'once',
        '/st', time_str,
        '/sd', date_str,
        '/f'  # Overwrite si existe déjà
    ], capture_output=True, text=True, timeout=10)
    return "OK (schtasks)" if result.returncode == 0 else f"Erreur schtasks: {result.stderr.strip()}"


def _schedule_linux_at(command: str, run_at: datetime) -> str:
    """Linux 'at' — planifie une commande pour une heure précise."""
    try:
        time_str = run_at.strftime("%H:%M %Y-%m-%d")
        proc = subprocess.Popen(
            ['at', time_str],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        proc.communicate(input=command.encode(), timeout=5)
        return "OK (at)"
    except FileNotFoundError:
        return "at non disponible. sudo pacman -S at && sudo systemctl enable --now atd"
    except Exception as e:
        return f"Erreur at: {e}"


def list_scheduled_tasks() -> dict:
    """Liste les tâches planifiées par OMI (depuis la DB locale)."""
    conn = sqlite3.connect(SCHEDULER_DB)
    rows = conn.execute(
        "SELECT id, name, command, run_at, status FROM tasks WHERE status='pending' ORDER BY run_at"
    ).fetchall()
    conn.close()
    return {
        "tasks": [
            {"id": r[0], "name": r[1], "command": r[2], "run_at": r[3], "status": r[4]}
            for r in rows
        ]
    }


def cancel_task(task_id: int) -> dict:
    """Annule une tâche planifiée par son ID."""
    conn = sqlite3.connect(SCHEDULER_DB)
    affected = conn.execute(
        "UPDATE tasks SET status='cancelled' WHERE id=? AND status='pending'", (task_id,)
    ).rowcount
    conn.commit()
    conn.close()
    if affected:
        return {"status": f"Tâche #{task_id} annulée"}
    return {"error": f"Tâche #{task_id} non trouvée ou déjà exécutée"}
```

---

### 4. `core/web_fetcher.py` — Recherche web sans popup navigateur

```python
"""
core/web_fetcher.py
Recherche web et récupération de pages en arrière-plan.
Retourne les résultats directement à Gemini, sans ouvrir de navigateur.

Utilise l'API DuckDuckGo (pas de clé requise) ou Google Custom Search.
"""

import urllib.parse
import urllib.request
import json
import re

USER_AGENT = "Mozilla/5.0 (compatible; OMI-Assistant/2.0)"


def search_web_headless(query: str, max_results: int = 5) -> dict:
    """
    Effectue une recherche web et retourne les résultats directement.
    PAS de popup navigateur. Les résultats sont donnés à Gemini pour réponse.

    Utilise l'API DuckDuckGo Instant Answer (gratuite, pas de clé).

    Exemples d'usage par Gemini :
      search_web_headless("météo Paris demain")
      search_web_headless("Python asyncio tutorial")
    """
    try:
        # DuckDuckGo Instant Answer API
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        results = []

        # Réponse directe (définition, calcul, etc.)
        if data.get("AbstractText"):
            results.append({
                "type": "answer",
                "text": data["AbstractText"],
                "source": data.get("AbstractSource", ""),
                "url": data.get("AbstractURL", "")
            })

        # Réponse instantanée
        if data.get("Answer"):
            results.append({
                "type": "instant",
                "text": data["Answer"]
            })

        # Résultats liés
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "type": "result",
                    "text": topic["Text"][:300],
                    "url": topic.get("FirstURL", "")
                })

        if not results:
            # Fallback : construire l'URL Google et retourner (sans ouvrir)
            google_url = f"https://www.google.com/search?q={encoded}"
            return {
                "results": [],
                "fallback_url": google_url,
                "message": "Pas de résultat instantané. URL Google construite mais non ouverte."
            }

        return {"query": query, "results": results[:max_results]}

    except Exception as e:
        return {"error": str(e)}


def fetch_page_text(url: str, max_chars: int = 3000) -> dict:
    """
    Récupère le contenu textuel d'une page web (sans JS, sans navigateur).
    Utile pour lire un article, une doc, un prix, etc.

    Note : ne fonctionne pas sur les SPAs React/Vue qui nécessitent JS.
    Pour ces cas, utilise execute_command avec un outil CLI comme lynx.
    """
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')

        # Nettoyage HTML basique (retire scripts, styles, balises)
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', html).strip()

        return {
            "url": url,
            "text": text[:max_chars],
            "truncated": len(text) > max_chars
        }
    except Exception as e:
        return {"error": str(e)}
```

---

### 5. Modifications de `core/tools.py`

#### A. Remplacer `execute_command` par la version améliorée

```python
# Ajouter au début des imports
from core.process_manager import launch_detached, run_and_wait, launch_app, get_process_by_name, kill_by_name
from core.system_bridge import media_control, set_volume, get_volume, send_notification as _send_notification
from core.scheduler import schedule_task, list_scheduled_tasks, cancel_task
from core.web_fetcher import search_web_headless, fetch_page_text

# Remplacer execute_command par :
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


# Remplacer smart_media_control par :
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


# Remplacer send_notification par :
def send_notification(title: str, message: str, urgency: str = "normal") -> dict:
    """Affiche une notification système (cross-platform)."""
    return _send_notification(title, message, urgency)


# Ajouter les nouveaux outils :

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
```

#### B. Mettre à jour `TOOLS_LIST`

```python
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
```

---

### 6. Mise à jour de `omi-2.0-prompt.md` (section à ajouter)

```markdown
## Tool Hierarchy — Mise à jour v2.1

### Priority 1 — Background, zéro interruption

| Situation | Outil |
|---|---|
| Musique (play/pause/next/stop) | `smart_media_control` (Windows + Linux) |
| Volume système | `control_volume(0-100)` |
| Lancer une app | `launch_app_background("spotify")` |
| Commande longue en arrière-plan | `execute_command(cmd, background=True)` |
| Chercher sur internet | `web_search("query")` — retourne les résultats, pas de browser |
| Lire une page web | `fetch_url_content("https://...")` |
| Planifier un rappel | `schedule_reminder("nom", "commande", delay_minutes=30)` |
| Trouver une app en cours | `find_process("spotify")` |
| Fermer une app par nom | `terminate_app("chrome")` |

### Règles cross-platform (CRITIQUE)

- `smart_media_control` fonctionne sur **Windows ET Linux** (playerctl sur Linux)
- `launch_app_background` connaît les noms communs (spotify, chrome, vscode…)
- `web_search` ne demande **jamais** d'ouvrir un navigateur — retourne les résultats directement
- `schedule_reminder` utilise Task Scheduler sur Windows, `at` sur Linux

### Nouveaux exemples de workflows

#### "Lance ma musique"
```
1. smart_media_control(action='play')
```

#### "Baisse le volume à 30%"
```
1. control_volume(30)
```

#### "Ouvre Spotify"
```
1. launch_app_background("spotify")
```

#### "Cherche la météo de Paris"
```
1. web_search("météo Paris aujourd'hui") → résultats directs
```

#### "Rappelle-moi dans 45 min de faire une pause"
```
1. schedule_reminder("Pause", "notify-send 'Fais une pause !'", delay_minutes=45)
```

#### "Ferme Chrome"
```
1. terminate_app("chrome")
   ou terminate_app("chrome", force=True) si ça ne répond pas
```
```

---

## Dépendances à ajouter

### `requirements.txt`

```
# Nouveaux (cross-platform)
pycaw; sys_platform == 'win32'   # Volume Windows (ou utiliser nircmd comme fallback)

# Linux (optionnels mais recommandés)
# dbus-python → pip install dbus-python (nécessite libdbus-1-dev)
# playerctl   → sudo pacman -S playerctl
# at          → sudo pacman -S at && sudo systemctl enable --now atd
```

### Sur Arch Linux (ton environnement)

```bash
sudo pacman -S playerctl at libnotify
sudo systemctl enable --now atd
```

---

## Sur la question du C

### Quand C serait justifié

- **Hooks kernel** : surveiller chaque appel système (inotify sur Linux, ReadDirectoryChangesW sur Windows) en temps réel, latence < 1ms
- **Daemon très léger** : un process en ring-0 qui tourne 24/7 avec < 1MB RAM
- **Bindings natifs** : appeler des APIs OS non exposées en Python (certaines APIs Win32 obscures, eBPF sur Linux)

### Pourquoi C n'est PAS nécessaire ici

- `subprocess.Popen` avec `start_new_session=True` (Linux) ou `DETACHED_PROCESS` (Windows) **appelle directement `fork/exec` ou `CreateProcess`** — c'est exactement ce que ferait du C, juste avec une abstraction Python au-dessus
- `ctypes` permet d'appeler les APIs Win32 directement depuis Python (déjà utilisé pour `keybd_event`)
- `psutil` wrappe les APIs kernel de monitoring des deux OS
- La latence de Python pour ces opérations est < 1ms, largement suffisant pour un assistant

**Conclusion** : Python + ctypes couvre 100% des besoins décrits. C serait une complexité inutile (build cross-platform, compilation dans l'installeur) sans bénéfice mesurable.

---

## Résumé des nouveaux fichiers

| Fichier | Rôle | Lignes ~|
|---|---|---|
| `core/process_manager.py` | Popen détaché, launch_app, find/kill par nom | 100 |
| `core/system_bridge.py` | Media, volume, notifications (cross-platform) | 150 |
| `core/scheduler.py` | Planification at/schtasks + DB locale | 130 |
| `core/web_fetcher.py` | Recherche DuckDuckGo + fetch HTML | 80 |
| `core/tools.py` (modifié) | +12 nouveaux outils, refactor execute_command | +200 |
| `omi-2.0-prompt.md` (modifié) | Mise à jour hiérarchie + exemples | +50 |

## Ordre d'implémentation recommandé

1. `core/process_manager.py` + modifier `execute_command` → test immédiat
2. `core/system_bridge.py` + remplacer `smart_media_control` → test media Linux
3. `core/web_fetcher.py` + ajouter `web_search` → test recherche
4. `core/scheduler.py` + ajouter `schedule_reminder` → test at/schtasks
5. Mettre à jour `TOOLS_LIST` + `omi-2.0-prompt.md`
