"""
core/tool_cooldown.py
Évite qu'un raisonnement Gemini en boucle déclenche plusieurs fois de suite
un outil coûteux (recherche web, scheduling) en quelques secondes.
"""

import time
import threading

_last_call_time: dict[str, float] = {}
_cooldown_lock = threading.Lock()

# Délai minimum (secondes) entre deux appels du même outil
COOLDOWNS = {
    "web_search": 5,
    "fetch_url_content": 5,
    "schedule_reminder": 2,
}


def check_cooldown(tool_name: str) -> tuple[bool, float]:
    """
    Vérifie si l'outil peut être appelé maintenant.
    Retourne (autorisé: bool, secondes_restantes: float).
    Si autorisé=True, le compteur est mis à jour immédiatement.
    """
    limit = COOLDOWNS.get(tool_name)
    if limit is None:
        return True, 0.0  # Pas de cooldown défini pour cet outil

    with _cooldown_lock:
        now = time.time()
        last = _last_call_time.get(tool_name, 0)
        elapsed = now - last
        if elapsed < limit:
            return False, round(limit - elapsed, 1)
        _last_call_time[tool_name] = now
        return True, 0.0
