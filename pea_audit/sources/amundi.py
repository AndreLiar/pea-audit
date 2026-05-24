"""Amundi ETF France — KID URL pattern: /pdfDocuments/kid-priips/{ISIN}/FRA/FRA"""

from __future__ import annotations

from .base import KIDSource, register_source

_BASE = "https://www.amundietf.fr/pdfDocuments/kid-priips"


def amundi_url(isin: str) -> str:
    """Build the canonical Amundi KID URL from an ISIN.

    Useful for registering custom Amundi tickers without re-typing the pattern.
    """
    return f"{_BASE}/{isin}/FRA/FRA"


# Built-in Amundi entries — extend by calling register_source(KIDSource(...))
# from your app code (or send a PR).

register_source(KIDSource(
    ticker="EWLD.PA",
    isin="LU2655993207",
    url=amundi_url("LU2655993207"),
    issuer="Amundi",
))

register_source(KIDSource(
    ticker="PAEEM.PA",
    isin="FR0011440478",
    url=amundi_url("FR0011440478"),
    issuer="Amundi",
))

# NB: Amundi restructured the "PEA Nasdaq-100" fund — the PANX.PA ticker
# now tracks "US Tech Screened" under ISIN FR0013412269. The historical
# Nasdaq-100 still exists under FR0011871110 but is a separate fund.
register_source(KIDSource(
    ticker="PANX.PA",
    isin="FR0013412269",
    url=amundi_url("FR0013412269"),
    issuer="Amundi",
))
