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
        for topic in data.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
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
