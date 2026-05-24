"""Vanguard — KID URL pattern: fund-docs.vanguard.com/{ISIN_lower}_priipskid_fr.pdf

Most Vanguard UCITS ETFs are physical replication of non-EEA indexes →
NOT PEA-eligible. Helper provided for eval cases / advanced users.
"""

from __future__ import annotations

_BASE = "https://fund-docs.vanguard.com"


def vanguard_url(isin: str) -> str:
    return f"{_BASE}/{isin.lower()}_priipskid_fr.pdf"
