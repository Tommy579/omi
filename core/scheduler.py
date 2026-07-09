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
