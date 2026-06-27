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
        except Exception:
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
