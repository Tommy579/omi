"""
core/local_router.py
Intercepte les commandes triviales (musique, volume) par pattern matching
AVANT tout appel à l'API Gemini. Coût : 0 token pour ces cas.

Le but n'est PAS de remplacer Gemini pour tout, juste pour les actions
déterministes où l'intelligence n'apporte rien (jouer/pause/suivant/volume).
"""

import re
from core.system_bridge import media_control, set_volume

# Chaque entrée : (regex compilé, fonction à appeler avec les groupes de match)
# Les regex sont volontairement strictes pour éviter les faux positifs sur
# des phrases qui parlent DE musique sans demander une action.
_RULES = [
    (re.compile(r"^(lance|joue|mets|démarre)\s+(la\s+)?(musique|chanson)s?\.?$", re.I),
        lambda m: media_control("play")),
    (re.compile(r"^(mets en pause|pause)\s+(la\s+)?musique\.?$", re.I),
        lambda m: media_control("pause")),
    (re.compile(r"^(reprends?|continue)\s+(la\s+)?musique\.?$", re.I),
        lambda m: media_control("play")),
    (re.compile(r"^(stop|arrête)\s+(la\s+)?musique\.?$", re.I),
        lambda m: media_control("stop")),
    (re.compile(r"^(chanson|musique|titre)\s+suivante?\.?$|^next\.?$", re.I),
        lambda m: media_control("next")),
    (re.compile(r"^(chanson|musique|titre)\s+précédente?\.?$|^previous\.?$", re.I),
        lambda m: media_control("previous")),
    (re.compile(r"^(mets le|règle le)?\s*volume\s+(à|a)\s+(\d{1,3})\s*%?\.?$", re.I),
        lambda m: set_volume(int(m.group(3)))),
    (re.compile(r"^(coupe|mute)\s+(le\s+)?(son|volume)\.?$", re.I),
        lambda m: set_volume(0)),
]


def try_local_route(user_message: str) -> dict | None:
    """
    Essaie de matcher le message utilisateur contre les règles locales.
    Retourne le résultat de l'action si un match est trouvé, sinon None
    (auquel cas l'appelant doit passer la main à Gemini normalement).
    """
    cleaned = user_message.strip().lower()
    for pattern, action in _RULES:
        match = pattern.match(cleaned)
        if match:
            try:
                result = action(match)
                return result
            except Exception as e:
                return {"error": str(e)}
    return None
