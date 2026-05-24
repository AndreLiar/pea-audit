"""BlackRock / iShares — KID URL pattern (FR variant):
/fr/intermediaries/literature/kiid/eu-priips-{slug}-{ISIN_lower}-fr.pdf

Slug formats vary by fund; safest to verify with curl before registering.
This module ships no default registrations because the user's PEA-only
portfolio is unlikely to hold iShares funds (most are PEA-INELIGIBLE physical
replications) — but the helper is here for eval cases.
"""

from __future__ import annotations

_BASE = "https://www.blackrock.com/fr/intermediaries/literature/kiid"


def blackrock_url(slug: str, isin: str) -> str:
    """Build a BlackRock FR KID URL given the fund slug + ISIN.

    Example:
        blackrock_url("ishares-core-sp-500-ucits-etf-usd-acc", "IE00B5BMR087")
    """
    return f"{_BASE}/eu-priips-{slug}-{isin.lower()}-fr.pdf"
