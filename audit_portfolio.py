"""Audite chaque ligne de positions.csv contre son KID.

Usage : `python audit_portfolio.py`
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from pea_audit import TickerAuditResult, VerdictCache, audit_ticker
from pea_audit.llm import OllamaCloudClient, enable_langfuse

from etftracker.portfolio import load_positions

CACHE_DIR = Path("cache/audits")
KID_DIR = Path("cache/kids")

_BADGE = {
    "yes": "\033[32m✅ ELIGIBLE\033[0m",
    "no": "\033[31m❌ NON\033[0m   ",
    "uncertain": "\033[33m⚠️  ?\033[0m       ",
}
_BADGE_ERROR = "\033[90m—\033[0m         "


def _verdict_cell(r: TickerAuditResult) -> str:
    if r.verdict is None:
        return _BADGE_ERROR
    return _BADGE[r.verdict.eligible]


def _short(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> int:
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        print("OLLAMA_API_KEY manquant — ajoute-le dans .env", file=sys.stderr)
        return 1

    llm = OllamaCloudClient(api_key=api_key)
    enable_langfuse()
    cache = VerdictCache(CACHE_DIR)

    positions = load_positions()
    print(f"\n📊 Audit PEA de {len(positions)} positions…\n")

    print(f"  {'Ticker':<10} {'ISIN':<14} {'Verdict':<14} {'Réplication':<18} {'Indice':<28}")
    print("  " + "─" * 86)

    results: list[TickerAuditResult] = []
    for p in positions:
        print(f"  {p.ticker:<10} ", end="", flush=True)
        r = audit_ticker(p.ticker, llm=llm, kid_dir=KID_DIR, cache=cache)
        results.append(r)
        v = r.verdict
        if v is not None:
            print(
                f"{v.isin:<14} {_verdict_cell(r):<14} "
                f"{v.replication.replace('_', ' '):<18} {_short(v.underlying_index, 28):<28}"
            )
        else:
            err = (r.error or "?").splitlines()[0]
            print(f"{'—':<14} {_BADGE_ERROR:<14} {_short(err, 46)}")

    print()
    eligible = sum(1 for r in results if r.verdict and r.verdict.eligible == "yes")
    non = sum(1 for r in results if r.verdict and r.verdict.eligible == "no")
    unc = sum(1 for r in results if r.verdict and r.verdict.eligible == "uncertain")
    err = sum(1 for r in results if r.verdict is None)
    print(f"  Bilan : {eligible} éligible(s), {non} non-éligible(s), "
          f"{unc} incertain(s), {err} non-audité(s).\n")

    return 0 if non == 0 and err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
