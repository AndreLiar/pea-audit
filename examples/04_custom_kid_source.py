"""Example 04 — Register a custom KIDSource for a ticker the library doesn't ship.

The built-in registry covers Amundi + BNP Paribas tickers. To audit a Lyxor,
SPDR, or any other issuer, you register the mapping yourself.

Run :  OLLAMA_API_KEY=... python examples/04_custom_kid_source.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pea_audit import VerdictCache, audit_ticker
from pea_audit.llm import OllamaCloudClient
from pea_audit.sources import KIDSource, all_sources, register_source


def main() -> int:
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        print("set OLLAMA_API_KEY in env first", file=sys.stderr)
        return 1

    print("Built-in sources:", sorted(all_sources().keys()))
    print()

    # Register an Amundi MSCI World Swap II (FR0010315770) — happens to be
    # PEA-eligible. The URL follows Amundi's pattern.
    register_source(KIDSource(
        ticker="CW8B.PA",  # made-up ticker for example purposes
        isin="FR0010315770",
        url="https://www.amundietf.fr/pdfDocuments/kid-priips/FR0010315770/FRA/FRA",
        issuer="Amundi",
    ))

    print("After registration:", sorted(all_sources().keys()))
    print()

    llm = OllamaCloudClient(api_key=api_key)
    cache = VerdictCache(Path("./cache/audits"))
    kid_dir = Path("./cache/kids")

    r = audit_ticker("CW8B.PA", llm=llm, kid_dir=kid_dir, cache=cache)
    if r.verdict is None:
        print(f"❌ {r.error}")
        return 1

    v = r.verdict
    print(f"✓ {v.eligible.value} — {v.issuer} — {v.underlying_index} — {v.replication.value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
