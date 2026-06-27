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
