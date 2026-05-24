"""Example 01 — Audit a single KID PDF.

Minimal end-to-end usage. Reads an Ollama Cloud key from env, audits the
shipped Amundi sample, prints the verdict.

Run :  OLLAMA_API_KEY=... python examples/01_basic_audit.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pea_audit import VerdictCache, audit_pdf
from pea_audit.llm import OllamaCloudClient


def main() -> int:
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        print("set OLLAMA_API_KEY in env first", file=sys.stderr)
        return 1

    llm = OllamaCloudClient(api_key=api_key)
    cache = VerdictCache(Path("./cache/audits"))

    verdict = audit_pdf(
        "samples/amundi_pea_monde_kid.pdf",
        llm=llm,
        cache=cache,
    )

    print(f"eligible    : {verdict.eligible.value}")
    print(f"confidence  : {verdict.confidence.value}")
    print(f"replication : {verdict.replication.value}")
    print(f"issuer      : {verdict.issuer}")
    print(f"isin        : {verdict.isin}")
    print(f"index       : {verdict.underlying_index}")
    print()
    print(f"summary     : {verdict.summary_fr}")
    print()
    print("evidence:")
    for c in verdict.evidence:
        print(f"  p.{c.page} — « {c.quote[:120]} »")

    return 0


if __name__ == "__main__":
    sys.exit(main())
