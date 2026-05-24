"""Example 02 — Audit by ticker (no PDF needed, library downloads it).

Uses the built-in KIDSource registry to fetch the right KID URL for the
ticker, downloads it (cached on disk), then audits.

Run :  OLLAMA_API_KEY=... python examples/02_audit_by_ticker.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pea_audit import VerdictCache, audit_ticker
from pea_audit.llm import OllamaCloudClient


def main() -> int:
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        print("set OLLAMA_API_KEY in env first", file=sys.stderr)
        return 1

    llm = OllamaCloudClient(api_key=api_key)
    cache = VerdictCache(Path("./cache/audits"))
    kid_dir = Path("./cache/kids")

    for ticker in ["EWLD.PA", "PAEEM.PA", "ESE.PA", "PANX.PA"]:
        r = audit_ticker(ticker, llm=llm, kid_dir=kid_dir, cache=cache)
        if r.verdict is None:
            print(f"{ticker:<10} ❌ {r.error}")
            continue
        v = r.verdict
        emoji = {"yes": "✅", "no": "❌", "uncertain": "⚠️"}[v.eligible.value]
        print(f"{ticker:<10} {emoji} {v.eligible.value:<10} {v.replication.value:<16} {v.underlying_index}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
