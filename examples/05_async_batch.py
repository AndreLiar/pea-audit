"""Example 05 — Batch-audit multiple tickers concurrently with the async API.

Useful for webhook handlers, large portfolios, or any code already running
in an event loop. asyncio.gather fans out N audits in parallel; the
underlying retries + cache + Langfuse tracing all still apply.

Run :  OLLAMA_API_KEY=... python examples/05_async_batch.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

from pea_audit import VerdictCache, aaudit_ticker
from pea_audit.llm import AsyncOllamaCloudClient


async def main() -> int:
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        print("set OLLAMA_API_KEY in env first", file=sys.stderr)
        return 1

    llm = AsyncOllamaCloudClient(api_key=api_key)
    cache = VerdictCache(Path("./cache/audits"))
    kid_dir = Path("./cache/kids")

    tickers = ["EWLD.PA", "PAEEM.PA", "ESE.PA", "PANX.PA"]

    t0 = time.perf_counter()
    results = await asyncio.gather(
        *[aaudit_ticker(t, llm=llm, kid_dir=kid_dir, cache=cache) for t in tickers]
    )
    elapsed = time.perf_counter() - t0

    print(f"\n{len(tickers)} audits in {elapsed:.2f}s (concurrent)\n")
    for r in results:
        if r.verdict is None:
            print(f"  {r.ticker:<10} ❌ {r.error}")
        else:
            v = r.verdict
            emoji = {"yes": "✅", "no": "❌", "uncertain": "⚠️"}[v.eligible.value]
            print(f"  {r.ticker:<10} {emoji} {v.replication.value:<16} {v.underlying_index}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
