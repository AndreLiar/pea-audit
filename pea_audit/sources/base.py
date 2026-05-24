"""KIDSource registry — ticker → KID URL mapping with pluggable issuers.

Library users register their own sources via `register_source(...)` or the
`@register_source(...)` decorator on a factory. Builtins for Amundi, BNP
Paribas, BlackRock/iShares, and Vanguard are shipped in sibling modules.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KIDSource:
    """Where to fetch a fund's KID PDF, given its ticker."""

    ticker: str
    isin: str
    url: str
    issuer: str


_REGISTRY: dict[str, KIDSource] = {}


def register_source(source: KIDSource) -> KIDSource:
    """Register a KID source. Returns the source for fluent use.

    Example:
        from pea_audit.sources import register_source, KIDSource
        register_source(KIDSource(
            ticker="LYXOR.PA", isin="FR0010411884",
            url="https://...lyxor.kid.pdf", issuer="Lyxor",
        ))
    """
    _REGISTRY[source.ticker.upper()] = source
    return source


def get_source(ticker: str) -> KIDSource | None:
    """Look up a registered source by ticker (case-insensitive)."""
    return _REGISTRY.get(ticker.upper())


def all_sources() -> dict[str, KIDSource]:
    """Snapshot of the current registry — useful for listing what's supported."""
    return dict(_REGISTRY)
