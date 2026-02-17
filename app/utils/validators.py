"""AMZ_Designy - Text validation for Amazon Merch policy compliance."""

from __future__ import annotations

import re

# Hard-banned: content that must NEVER appear in listings.
BANNED_TERMS: list[str] = [
    # Violence / hate
    "kill", "murder", "terrorist", "hate crime", "genocide",
    # Adult content
    "pornography", "xxx", "nude", "naked",
    # Drugs (non-medical)
    "cocaine", "heroin", "meth",
    # Slurs (representative subset -- extend as needed)
    "racial slur placeholder",
]

# Soft risk: may be acceptable in context but flag for review.
RISK_TERMS: list[str] = [
    # Trademarked brands / franchises
    "nike", "adidas", "disney", "marvel", "nintendo", "pokemon",
    "star wars", "harry potter", "coca-cola", "pepsi",
    "minecraft", "fortnite", "roblox",
    # Celebrity names (representative)
    "taylor swift", "beyonce", "elon musk",
    # Potentially misleading
    "official", "licensed", "authentic brand",
    "fda approved", "clinically proven",
    # Political
    "maga", "antifa",
]


def _find_terms(text: str, terms: list[str]) -> list[str]:
    """Return all terms found in *text* (case-insensitive, word-boundary)."""
    lower = text.lower()
    found: list[str] = []
    for term in terms:
        pattern = rf"\b{re.escape(term.lower())}\b"
        if re.search(pattern, lower):
            found.append(term)
    return found


def scan_for_banned_terms(text: str) -> list[str]:
    """Return banned terms found in *text*."""
    return _find_terms(text, BANNED_TERMS)


def scan_for_risk_terms(text: str) -> list[str]:
    """Return risk terms found in *text*."""
    return _find_terms(text, RISK_TERMS)


def validate_text_content(text: str) -> tuple[bool, list[str]]:
    """Validate text for policy compliance.

    Returns:
        (is_valid, detected_terms) -- is_valid is False if any banned
        term is found.  Risk terms alone return True but are still listed.
    """
    banned = scan_for_banned_terms(text)
    risk = scan_for_risk_terms(text)
    all_detected = banned + risk
    is_valid = len(banned) == 0
    return is_valid, all_detected
