"""
Profil utilisateur persistant d'OMI.
Se remplit automatiquement au fur et à mesure des observations.
Stocké dans omi_profile.json à côté de main.py.
"""

import json
import os
from datetime import datetime
from pathlib import Path

PROFILE_PATH = Path(__file__).parent.parent / "omi_profile.json"

# Structure par défaut du profil — créée au premier démarrage
DEFAULT_PROFILE = {
    "_meta": {
        "created_at": None,
        "last_updated": None,
        "version": "1.0"
    },
    "identity": {
        "name": None,                  # Prénom ou pseudo détecté
        "language": "fr",              # Langue principale
        "timezone": "Europe/Paris"
    },
    "work": {
        "current_projects": [],        # Projets en cours détectés (noms, dossiers)
        "tech_stack": [],              # Langages et outils utilisés
        "frequent_apps": [],           # Applications ouvertes souvent
        "frequent_files": [],          # Fichiers ouverts souvent
        "work_style": None             # ex: "travaille tard le soir", "courtes sessions"
    },
    "habits": {
        "bad_habits": [],              # ex: ["se ronge les ongles", "téléphone fréquent"]
        "posture_issues": [],          # ex: ["dos courbé", "écran trop proche"]
        "distraction_patterns": [],    # ex: ["YouTube en milieu d'après-midi"]
        "focus_score": None            # Score subjectif de concentration (0-10)
    },
    "preferences": {
        "communication_style": None,   # ex: "direct", "détaillé", "humoristique"
        "music_genres": [],            # Genres ou artistes détectés via iTunes/loopback
        "topics_of_interest": []       # Sujets récurrents dans les conversations
    },
    "schedule": {
        "typical_start_time": None,    # Heure habituelle de début de travail
        "typical_end_time": None,      # Heure habituelle de fin
        "most_productive_hours": []    # Créneaux où l'utilisateur semble le plus actif
    },
    "notes": []                        # Observations libres d'OMI, horodatées
}


def load_profile() -> dict:
    """Charge le profil depuis le fichier JSON. Le crée s'il n'existe pas."""
    if not PROFILE_PATH.exists():
        profile = DEFAULT_PROFILE.copy()
        profile["_meta"]["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        profile["_meta"]["last_updated"] = profile["_meta"]["created_at"]
        save_profile(profile)
        print(f"[Profil] Nouveau profil créé : {PROFILE_PATH}")
        return profile

    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Profil] Erreur lecture profil : {e} — profil par défaut utilisé")
        return DEFAULT_PROFILE.copy()


def save_profile(profile: dict) -> bool:
    """Sauvegarde le profil dans le fichier JSON."""
    try:
        profile["_meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[Profil] Erreur sauvegarde : {e}")
        return False


def get_profile_summary() -> str:
    """Retourne un résumé textuel du profil pour injection dans les prompts."""
    profile = load_profile()
    lines = ["=== Profil utilisateur connu ==="]

    identity = profile.get("identity", {})
    if identity.get("name"):
        lines.append(f"Nom : {identity['name']}")

    work = profile.get("work", {})
    if work.get("current_projects"):
        lines.append(f"Projets en cours : {', '.join(work['current_projects'])}")
    if work.get("tech_stack"):
        lines.append(f"Stack technique : {', '.join(work['tech_stack'])}")
    if work.get("frequent_apps"):
        lines.append(f"Apps fréquentes : {', '.join(work['frequent_apps'])}")
    if work.get("work_style"):
        lines.append(f"Style de travail : {work['work_style']}")

    habits = profile.get("habits", {})
    if habits.get("bad_habits"):
        lines.append(f"Mauvaises habitudes connues : {', '.join(habits['bad_habits'])}")
    if habits.get("posture_issues"):
        lines.append(f"Problèmes de posture récurrents : {', '.join(habits['posture_issues'])}")
    if habits.get("distraction_patterns"):
        lines.append(f"Distractions fréquentes : {', '.join(habits['distraction_patterns'])}")

    prefs = profile.get("preferences", {})
    if prefs.get("communication_style"):
        lines.append(f"Style de communication préféré : {prefs['communication_style']}")
    if prefs.get("topics_of_interest"):
        lines.append(f"Centres d'intérêt : {', '.join(prefs['topics_of_interest'])}")

    schedule = profile.get("schedule", {})
    if schedule.get("typical_start_time"):
        lines.append(f"Heure habituelle de début : {schedule['typical_start_time']}")
    if schedule.get("most_productive_hours"):
        lines.append(f"Heures productives : {', '.join(schedule['most_productive_hours'])}")

    notes = profile.get("notes", [])
    if notes:
        recent_notes = notes[-3:]  # Les 3 dernières notes
        lines.append("Notes récentes :")
        for note in recent_notes:
            lines.append(f"  [{note.get('date', '?')}] {note.get('text', '')}")

    if len(lines) == 1:
        return ""  # Profil vide, pas la peine d'injecter

    lines.append("================================")
    return "\n".join(lines)


def record_active_app(app_name: str):
    """Enregistre l'application active dans les statistiques d'utilisation du profil."""
    try:
        profile = load_profile()
        log = profile.setdefault("activity_log", [])
        log.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "app": app_name
        })
        # Garder les 100 dernières entrées pour éviter de gonfler le fichier
        profile["activity_log"] = log[-100:]
        
        # Mettre à jour la liste des applications fréquentes
        from collections import Counter
        apps = [entry["app"] for entry in profile["activity_log"]]
        common_apps = [app for app, count in Counter(apps).most_common(5)]
        profile.setdefault("work", {})["frequent_apps"] = common_apps
        
        save_profile(profile)
    except Exception as e:
        print(f"[Profil] Erreur record_active_app : {e}")


def generate_daily_summary():
    """Génère un résumé quotidien basé sur les statistiques d'applications de la journée."""
    try:
        profile = load_profile()
        activity_log = profile.get("activity_log", [])
        if not activity_log:
            return
            
        from collections import Counter
        apps = [entry["app"] for entry in activity_log]
        app_counts = Counter(apps)
        
        summary_lines = ["Résumé d'activité quotidienne :"]
        # On estime le temps de travail basé sur les occurrences (une capture environ toutes les 10 secondes)
        for app, count in app_counts.most_common(5):
            minutes = int(count * 10 / 60)
            if minutes > 0:
                summary_lines.append(f"- {app} : environ {minutes} min")
            else:
                summary_lines.append(f"- {app} : actif ({count} captures)")
                
        summary_text = "\n".join(summary_lines)
        
        # Enregistrer dans notes
        profile.setdefault("notes", []).append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "text": summary_text
        })
        # Limiter à 50 notes
        profile["notes"] = profile["notes"][-50:]
        save_profile(profile)
        print("[Profil] Résumé quotidien enregistré dans les notes.")
    except Exception as e:
        print(f"[Profil] Erreur génération résumé : {e}")
