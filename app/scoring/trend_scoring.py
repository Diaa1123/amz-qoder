"""AMZ_Designy - Deterministic scoring functions for niche viability.

All functions are pure: no LLM calls, no side effects, no external APIs.
Each returns an int in the range 1-10.
"""

from __future__ import annotations

import re

from app.schemas import TrendEntry

# ---------------------------------------------------------------------------
# Keyword lists used by scoring heuristics
# ---------------------------------------------------------------------------

_COMMERCIAL_KEYWORDS: set[str] = {
    "shirt", "tshirt", "t-shirt", "tee", "hoodie", "sweatshirt",
    "mug", "gift", "merch", "merchandise", "apparel", "clothing",
    "buy", "shop", "store", "fashion", "wear", "outfit", "print",
}

_VISUAL_KEYWORDS: set[str] = {
    "art", "design", "pixel", "retro", "vintage", "cartoon", "anime",
    "illustration", "graphic", "abstract", "floral", "geometric",
    "neon", "watercolor", "minimalist", "pattern", "sketch", "comic",
    "space", "galaxy", "sunset", "mountain", "ocean", "animal",
    "cat", "dog", "wolf", "dragon", "skull", "rose", "heart",
}

_ABSTRACT_KEYWORDS: set[str] = {
    "philosophy", "theory", "concept", "metaphysics", "epistemology",
    "ontology", "hermeneutics", "dialectic",
}

_SEASONAL_KEYWORDS: set[str] = {
    "christmas", "halloween", "valentine", "easter", "thanksgiving",
    "new year", "4th of july", "independence day", "mothers day",
    "fathers day", "black friday", "cyber monday", "summer", "winter",
    "spring break", "back to school",
}

_TRADEMARK_KEYWORDS: set[str] = {
    "nike", "adidas", "disney", "marvel", "dc comics", "nintendo",
    "pokemon", "pikachu", "mario", "zelda", "star wars", "harry potter",
    "coca-cola", "pepsi", "starbucks", "apple", "google", "amazon",
    "minecraft", "fortnite", "roblox", "call of duty", "fifa",
    "nba", "nfl", "mlb", "barbie", "lego", "transformers",
}


def _clamp(value: int) -> int:
    """Clamp a value to the 1-10 range."""
    return max(1, min(10, value))


def _query_words(entry: TrendEntry) -> set[str]:
    """Lowercase word set from the query."""
    return set(entry.query.lower().split())


def _query_lower(entry: TrendEntry) -> str:
    return entry.query.lower()


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------


def score_commercial_intent(entry: TrendEntry) -> int:
    """Score based on buyer-intent keywords in the query.

    More commercial keywords -> higher score.
    """
    words = _query_words(entry)
    hits = len(words & _COMMERCIAL_KEYWORDS)
    if hits >= 3:
        return 10
    if hits == 2:
        return 9
    if hits == 1:
        return 7

    # Fallback: if the category signals shopping intent
    if entry.category and "shopping" in entry.category.lower():
        return 6
    return 4


def score_designability(entry: TrendEntry) -> int:
    """Score based on how easily the concept can become a visual design.

    Concrete visual themes -> high, abstract concepts -> low.
    """
    words = _query_words(entry)
    visual_hits = len(words & _VISUAL_KEYWORDS)
    abstract_hits = len(words & _ABSTRACT_KEYWORDS)

    base = 5
    base += min(visual_hits * 2, 5)   # up to +5 for visual keywords
    base -= min(abstract_hits * 3, 4)  # penalty for abstract terms
    return _clamp(base)


def score_audience_size(entry: TrendEntry) -> int:
    """Score based on search volume.

    Linear mapping: 0 -> 1, 100k+ -> 10.
    """
    vol = entry.volume or 0
    if vol <= 0:
        return 1
    if vol >= 100_000:
        return 10
    return _clamp(int(vol / 100_000 * 9) + 1)


def score_competition_level(entry: TrendEntry) -> int:
    """Score based on estimated competition (1-10, lower is better for the niche).

    Higher growth_rate -> newer trend -> lower competition.
    """
    rate = entry.growth_rate or 0.0
    if rate >= 50:
        return 3   # very new / low competition
    if rate >= 30:
        return 4
    if rate >= 15:
        return 5
    if rate >= 5:
        return 6
    return 7  # stagnant -> probably saturated


def score_seasonality_risk(entry: TrendEntry) -> int:
    """Score based on seasonal keyword presence (1-10, lower is better).

    Holiday / seasonal keywords -> high risk.
    """
    lower = _query_lower(entry)
    for term in _SEASONAL_KEYWORDS:
        if re.search(rf"\b{re.escape(term)}\b", lower):
            return 8
    return 3  # no seasonal signal -> low risk


def score_trademark_risk(entry: TrendEntry) -> int:
    """Score based on trademark / brand keyword presence (1-10, lower is better).

    Known brands / IPs in the query -> high risk.
    """
    lower = _query_lower(entry)
    found = 0
    for term in _TRADEMARK_KEYWORDS:
        if re.search(rf"\b{re.escape(term)}\b", lower):
            found += 1
    if found >= 2:
        return 10
    if found == 1:
        return 8
    return 2  # no trademark signal -> low risk
