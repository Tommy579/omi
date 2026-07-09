# OMI — Optimisation consommation tokens (sessions séparées + routeur local + cooldowns)

## Contexte du problème

Le vision loop d'OMI appelle Gemini toutes les `SCREEN_CAPTURE_INTERVAL` secondes (10s par défaut) via `self.chat_session`, qui est **la même session** utilisée pour le chat interactif. Cette session inclut `tools=TOOLS_LIST` (maintenant ~30 outils avec docstrings détaillées) dans sa config.

**Conséquence** : chaque appel du vision loop renvoie l'intégralité des définitions d'outils à l'API (~2000-4000 tokens), même si la vision n'a jamais besoin d'appeler `schedule_reminder`, `web_search`, ou `smart_media_control` de son propre chef — son seul rôle est d'observer et de répondre en texte.

Ce fichier décrit 3 changements indépendants, à appliquer dans l'ordre, chacun testable séparément.

---

## Changement 1 — Séparer vision_session et agent_session

### Fichier : `core/assistant.py`

#### 1a. Remplacer l'attribut unique par deux sessions

Chercher dans `__init__` :

```python
self.chat_session = self.client.chats.create(
    model=GEMINI_MODEL,
    config={"system_instruction": enhanced_prompt, "tools": TOOLS_LIST}
)
self._enhanced_prompt = enhanced_prompt  # Gardé pour le trim de session
```

Remplacer par :

```python
# Session VISION : observation passive, AUCUN outil d'action.
# Le rôle de cette session est uniquement de regarder l'écran/texte et de
# répondre par une suggestion textuelle courte. Elle ne doit jamais pouvoir
# déclencher une action (musique, scheduling, web, fichiers...).
vision_prompt = enhanced_prompt + """

### RAPPEL CRITIQUE — MODE OBSERVATION SEULE
Tu n'as accès à AUCUN outil dans ce contexte. Réponds uniquement par du texte.
Si tu n'as rien de pertinent à signaler, réponds exactement : "Rien de particulier."
"""
self.vision_session = self.client.chats.create(
    model=GEMINI_MODEL,
    config={"system_instruction": vision_prompt}  # ← pas de "tools" ici
)

# Session AGENT : chat interactif déclenché par l'utilisateur.
# Cette session garde l'accès à tous les outils (process, scheduler, web, media...).
self.agent_session = self.client.chats.create(
    model=GEMINI_MODEL,
    config={"system_instruction": enhanced_prompt, "tools": TOOLS_LIST}
)

self._enhanced_prompt = enhanced_prompt   # prompt complet, pour le trim de agent_session
self._vision_prompt = vision_prompt       # prompt vision, pour le trim de vision_session

# Alias de compatibilité : tout code legacy qui référence self.chat_session
# pointe maintenant vers la session agent (comportement le plus proche de l'actuel)
self.chat_session = self.agent_session
```

#### 1b. Mettre à jour `_analyze_vision` pour utiliser `vision_session`

Chercher dans `_analyze_vision` :

```python
with self._lock:
    if mode == "image":
        response = self.chat_session.send_message([prompt] + images)
    else:
        response = self.chat_session.send_message(prompt)
```

Remplacer par :

```python
with self._lock:
    if mode == "image":
        response = self.vision_session.send_message([prompt] + images)
    else:
        response = self.vision_session.send_message(prompt)
```

#### 1c. Mettre à jour `_analyze_audio` pour utiliser `vision_session`

L'analyse audio passive (réaction à une transcription captée) ne doit pas non plus déclencher d'outils — c'est de l'observation, pas une demande explicite de l'utilisateur.

Chercher dans `_analyze_audio` :

```python
with self._lock:
    response = self.chat_session.send_message(prompt)
```

Remplacer par :

```python
with self._lock:
    response = self.vision_session.send_message(prompt)
```

#### 1d. Mettre à jour `chat()` pour utiliser explicitement `agent_session`

Chercher dans `chat()`, les 3 occurrences de :

```python
with self._lock:
    response = self.chat_session.send_message(full_prompt)
```
et
```python
with self._lock:
    response = self.chat_session.send_message([full_prompt, screen_img])
```

Remplacer `self.chat_session` par `self.agent_session` dans les 3 endroits (un seul remplacement texte si tu fais un rename global de l'attribut, voir note ci-dessous).

> **Note simplification** : Si tu préfères éviter de toucher 3 endroits dans `chat()`, tu peux laisser l'alias `self.chat_session = self.agent_session` de l'étape 1a tel quel — `chat()` continuera de fonctionner sans modification puisqu'il pointera vers la bonne session. Dans ce cas, saute l'étape 1d. **C'est l'approche recommandée pour limiter le diff.**

#### 1e. Mettre à jour `_trim_chat_history_if_needed` pour trimmer les DEUX sessions

Cette fonction ne doit trimmer que `agent_session` (c'est la seule qui accumule un vrai historique de conversation avec tool calls). La session vision peut être recréée à l'identique à chaque fois sans trim complexe puisqu'elle n'a pas d'historique de tool calls — mais elle accumule quand même les échanges image/texte au fil du temps, donc il faut la trimmer aussi, plus simplement.

Remplacer toute la fonction `_trim_chat_history_if_needed` par :

```python
def _trim_chat_history_if_needed(self):
    self._trim_agent_session()
    self._trim_vision_session()

def _trim_agent_session(self):
    """Trim de la session agent (avec tool calls) — logique identique à avant."""
    try:
        with self._lock:
            history = self.agent_session.get_history()
        if len(history) <= MAX_CHAT_TURNS * 2:
            return

        recent = history[-(MAX_CHAT_TURNS * 2):]

        start = 0
        for i, turn in enumerate(recent):
            if turn.role == "user":
                parts = turn.parts if hasattr(turn, "parts") else []
                is_func_response = any(
                    hasattr(p, "function_response") and p.function_response
                    for p in parts
                )
                if not is_func_response:
                    start = i
                    break

        recent = recent[start:]

        profile_summary = get_profile_summary()
        prompt_with_profile = self._enhanced_prompt
        if profile_summary:
            prompt_with_profile = self._enhanced_prompt + f"\n\n{profile_summary}"

        with self._lock:
            self.agent_session = self.client.chats.create(
                model=GEMINI_MODEL,
                config={"system_instruction": prompt_with_profile, "tools": TOOLS_LIST},
                history=recent
            )
            self.chat_session = self.agent_session  # garder l'alias synchronisé
        print(f"[Chat] Historique agent taillé à {len(recent)} tours.")
    except Exception as e:
        print(f"[Chat] Erreur trim historique agent : {e}")
        with self._lock:
            self.agent_session = self.client.chats.create(
                model=GEMINI_MODEL,
                config={"system_instruction": self._enhanced_prompt, "tools": TOOLS_LIST}
            )
            self.chat_session = self.agent_session

def _trim_vision_session(self):
    """Trim de la session vision — pas de tool calls à préserver, donc plus simple.
    Seuil plus bas car le vision loop tourne beaucoup plus fréquemment."""
    VISION_MAX_TURNS = 10  # seuil bas, cette session n'a pas besoin de longue mémoire
    try:
        with self._lock:
            history = self.vision_session.get_history()
        if len(history) <= VISION_MAX_TURNS * 2:
            return

        recent = history[-(VISION_MAX_TURNS * 2):]
        # Pas de filtrage function_response nécessaire (vision_session n'a pas de tools)

        profile_summary = get_profile_summary()
        prompt_with_profile = self._vision_prompt
        if profile_summary:
            prompt_with_profile = self._vision_prompt + f"\n\n{profile_summary}"

        with self._lock:
            self.vision_session = self.client.chats.create(
                model=GEMINI_MODEL,
                config={"system_instruction": prompt_with_profile},
                history=recent
            )
        print(f"[Vision] Historique vision taillé à {len(recent)} tours.")
    except Exception as e:
        print(f"[Vision] Erreur trim historique vision : {e}")
        with self._lock:
            self.vision_session = self.client.chats.create(
                model=GEMINI_MODEL,
                config={"system_instruction": self._vision_prompt}
            )
```

#### 1f. Réduire `MAX_CHAT_TURNS` dans `config.py`

Chercher :
```python
MAX_CHAT_TURNS = 20
```
Remplacer par :
```python
MAX_CHAT_TURNS = 10
```

Raison : les tool calls remplissent l'historique de `agent_session` beaucoup plus vite que de simples échanges texte (chaque appel d'outil = 1 tour "model" avec function_call + 1 tour "user" avec function_response). Un seuil de 20 tours peut accumuler 40+ entrées avant de trim, ce qui fait grossir le coût de chaque appel API entre-temps.

---

## Changement 2 — Routeur local pour les commandes triviales

### Nouveau fichier : `core/local_router.py`

Ce module intercepte les commandes évidentes (musique, volume) avant tout appel à Gemini, pour un coût de **0 token** sur ces cas.

```python
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
```

### Modification : `core/assistant.py` → méthode `chat()`

Chercher le tout début de la méthode `chat()` :

```python
def chat(self, user_message: str, is_system: bool = False, status_callback=None) -> str:
    try:
        if not is_system:
```

Insérer juste avant `try:` un import en haut du fichier, et juste après `def chat(...):` une interception locale :

**En haut du fichier**, ajouter à côté des autres imports `core.*` :
```python
from core.local_router import try_local_route
```

**Dans `chat()`**, juste après la ligne `def chat(self, user_message: str, is_system: bool = False, status_callback=None) -> str:` :

```python
def chat(self, user_message: str, is_system: bool = False, status_callback=None) -> str:
    # Interception locale AVANT tout appel API : commandes triviales (musique, volume)
    # Coût : 0 token. Si pas de match, on continue normalement vers Gemini.
    if not is_system:
        local_result = try_local_route(user_message)
        if local_result is not None:
            status_text = local_result.get("status") or local_result.get("error", "Fait.")
            self._add_to_memory("local", status_text)
            return status_text

    try:
        if not is_system:
```

> Le `try:` existant reste inchangé juste en dessous, c'est bien un ajout, pas un remplacement de logique.

---

## Changement 3 — Cooldown sur les outils coûteux

### Nouveau fichier : `core/tool_cooldown.py`

```python
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
```

### Modification : `core/tools.py`

Pour chaque fonction concernée par un cooldown (`web_search`, `fetch_url_content`, `schedule_reminder`), ajouter une vérification en première ligne du corps de la fonction.

**Ajouter l'import** en haut de `core/tools.py` :
```python
from core.tool_cooldown import check_cooldown
```

**Modifier `web_search`** :
```python
def web_search(query: str, max_results: int = 5) -> dict:
    """
    Recherche sur internet et retourne les résultats directement.
    [...docstring existante inchangée...]
    """
    allowed, wait_time = check_cooldown("web_search")
    if not allowed:
        return {"error": f"Trop de recherches récentes, réessaie dans {wait_time}s"}
    return search_web_headless(query, max_results)
```

**Modifier `fetch_url_content`** :
```python
def fetch_url_content(url: str, max_chars: int = 3000) -> dict:
    """
    [...docstring existante inchangée...]
    """
    allowed, wait_time = check_cooldown("fetch_url_content")
    if not allowed:
        return {"error": f"Trop de requêtes récentes, réessaie dans {wait_time}s"}
    return fetch_page_text(url, max_chars)
```

**Modifier `schedule_reminder`** :
```python
def schedule_reminder(name: str, command: str,
                      delay_minutes: int = None, run_at_time: str = None) -> dict:
    """
    [...docstring existante inchangée...]
    """
    allowed, wait_time = check_cooldown("schedule_reminder")
    if not allowed:
        return {"error": f"Trop de planifications récentes, réessaie dans {wait_time}s"}
    return schedule_task(name, command, delay_minutes, run_at_time)
```

---

## Récapitulatif des fichiers touchés

| Fichier | Type de modification |
|---|---|
| `core/assistant.py` | Modifié — sessions séparées (1a-1e), import + interception locale (2) |
| `config.py` | Modifié — `MAX_CHAT_TURNS = 20` → `10` |
| `core/local_router.py` | **Nouveau** — routeur regex local |
| `core/tool_cooldown.py` | **Nouveau** — cooldown générique |
| `core/tools.py` | Modifié — import + 3 fonctions avec check_cooldown |

---

## Vérification après implémentation

1. **Lancer OMI et observer les logs** : le vision loop ne doit plus afficher d'appels d'outils dans la console (puisque `vision_session` n'a pas de `tools`). Seul `[Vision] Mode : ... | Réponse : ...` doit apparaître.

2. **Tester le routeur local** : taper "lance la musique" dans le chat → la réponse doit être quasi-instantanée (pas d'attente réseau Gemini) et `_add_to_memory("local", ...)` doit apparaître dans `get_memory()`.

3. **Tester le cooldown** : demander 3 recherches web d'affilée en moins de 5 secondes via le chat → la 2e et 3e doivent retourner l'erreur de cooldown au lieu de réellement chercher.

4. **Vérifier le trim séparé** : laisser tourner OMI longtemps (30+ min) et observer dans les logs `[Chat] Historique agent taillé...` et `[Vision] Historique vision taillé...` apparaître à des fréquences différentes (vision beaucoup plus souvent, vu son seuil plus bas et sa fréquence d'appel plus élevée).

5. **Mesurer le gain réel** : si possible, logger `response.usage_metadata` (disponible sur les réponses Gemini) avant/après pour `vision_session` afin de confirmer la baisse du nombre de tokens de prompt par appel.

---

## Note sur le C / approches alternatives non retenues

Aucun changement bas niveau (C, threads natifs, etc.) n'est nécessaire ici — le coût vient exclusivement de la *taille des requêtes API*, pas de la performance d'exécution locale. Tout le gain vient de réduire ce qui est envoyé à Gemini, pas d'accélérer du code Python.
