import os
import subprocess
from pathlib import Path
from PIL import Image
import base64
import io

def list_directory(path="."):
    """Liste les fichiers et dossiers dans un chemin donné."""
    try:
        p = Path(path).expanduser().resolve()
        items = []
        for item in p.iterdir():
            items.append(f"{'[DIR]' if item.is_dir() else '[FILE]'} {item.name}")
        return {"items": items, "current_path": str(p)}
    except Exception as e:
        return {"error": str(e)}

def read_file(file_path):
    """Lit le contenu textuel d'un fichier."""
    try:
        path = Path(file_path).expanduser().resolve()
        # On peut lire les fichiers texte courants
        text_extensions = {'.py', '.txt', '.md', '.json', '.js', '.html', '.css', '.c', '.cpp', '.h', '.rs', '.go', '.sh', '.bat', '.ps1', '.yaml', '.yml'}
        if path.suffix.lower() not in text_extensions:
             # Si c'est pas une extension connue, on essaie quand même si c'est petit
             if path.stat().st_size > 50000:
                return {"error": "Type de fichier non supporté ou trop volumineux pour la lecture directe."}
        
        if path.stat().st_size > 500000: # Max 500kb
            return {"error": "Fichier trop volumineux (max 500kb)."}
            
        return {"content": path.read_text(encoding="utf-8", errors="replace")}
    except Exception as e:
        return {"error": str(e)}

def search_files(query, root_dir="."):
    """Recherche des fichiers par nom dans un répertoire."""
    try:
        root = Path(root_dir).expanduser().resolve()
        matches = []
        for path in root.rglob(f"*{query}*"):
            if len(matches) > 50: break
            matches.append(str(path))
        return {"matches": matches}
    except Exception as e:
        return {"error": str(e)}

def inspect_image(file_path):
    """Permet à l'assistant de 'voir' une image sur le disque."""
    try:
        path = Path(file_path).expanduser().resolve()
        if path.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']:
            return {"error": "Ce n'est pas une image supportée."}
        
        img = Image.open(path)
        img.thumbnail((1280, 720), Image.LANCZOS)
        # On retourne l'image dans un format que l'assistant pourra demander si on change la logique,
        # mais pour l'instant on va dire qu'on l'a "chargée" en contexte.
        # En réalité, pour Gemini API via Tools, il vaut mieux que le tool retourne une confirmation
        # et que l'assistant reçoive l'image dans le tour suivant.
        return {"status": "Image chargée. Vous pouvez maintenant l'analyser.", "path": str(path)}
    except Exception as e:
        return {"error": str(e)}

def execute_command(command):
    """Exécute une commande système (Prudence !)."""
    try:
        # On limite un peu pour la sécurité même si c'est pour l'utilisateur
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

def mouse_click(x, y):
    """Clique à une position spécifique sur l'écran (coordonnées basées sur une image 1280x720)."""
    try:
        import pyautogui
        # On suppose que l'IA travaille sur du 1280x720 (le format envoyé)
        # On remet à l'échelle pour l'écran réel
        screen_w, screen_h = pyautogui.size()
        real_x = int(x * screen_w / 1280)
        real_y = int(y * screen_h / 720)
        
        pyautogui.click(real_x, real_y)
        return {"status": f"Cliqué à {real_x}, {real_y} (échelle {x}, {y})"}
    except Exception as e:
        return {"error": str(e)}

def type_text(text):
    """Tape du texte au clavier."""
    try:
        import pyautogui
        pyautogui.write(text)
        return {"status": f"Texte tapé : {text}"}
    except Exception as e:
        return {"error": str(e)}

def press_key(key):
    """Appuie sur une touche du clavier (ex: 'enter', 'esc', 'ctrl', 'c')."""
    try:
        import pyautogui
        pyautogui.press(key)
        return {"status": f"Touche appuyée : {key}"}
    except Exception as e:
        return {"error": str(e)}

# Liste des outils exportés pour Gemini
TOOLS_LIST = [
    list_directory, 
    read_file, 
    search_files, 
    inspect_image, 
    execute_command, 
    get_active_window_info,
    mouse_click,
    type_text,
    press_key
]
