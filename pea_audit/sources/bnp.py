"""BNP Paribas Asset Management — KIDs hosted on docfinder.bnpparibas-am.com.

URLs use opaque UUIDs (no ISIN-based pattern), so each entry must be
researched individually. Add via register_source(KIDSource(...)).
"""

from __future__ import annotations

from .base import KIDSource, register_source

register_source(KIDSource(
    ticker="ESE.PA",
    isin="FR0011550185",
    url="https://docfinder.bnpparibas-am.com/api/files/d56ce147-d9d1-4e68-b057-f3c622dda848/69120",
    issuer="BNP Paribas",
))
