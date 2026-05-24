"""KID source registry.

Importing this package triggers registration of the built-in sources
(Amundi, BNP Paribas). Issuer URL-builders (BlackRock, Vanguard) are
importable for ad-hoc use without populating the registry.
"""

# Import side-effect: each issuer module calls register_source() at import.
from . import amundi, bnp  # noqa: F401
from . import blackrock, vanguard  # noqa: F401  (helpers, no auto-registration)
from .base import KIDSource, all_sources, get_source, register_source

__all__ = [
    "KIDSource",
    "register_source",
    "get_source",
    "all_sources",
    "amundi",
    "bnp",
    "blackrock",
    "vanguard",
]
