"""Ticker-based audit: resolve ticker → KID URL → download → audit.

`audit_ticker(...)` is the convenience entry point for "I have a ticker,
tell me if it's PEA-eligible." Returns a `TickerAuditResult` that never
raises — errors are captured in the `.error` field for batch processing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import requests

from .core import PeaVerdict, audit_pdf
from .sources.base import KIDSource, get_source

if TYPE_CHECKING:
    from .cache import VerdictCache
    from .llm.base import VisionLLM


@dataclass(frozen=True)
class TickerAuditResult:
    ticker: str
    source: KIDSource | None
    verdict: PeaVerdict | None
    error: str | None = None


def _download_kid(src: KIDSource, kid_dir: Path, force: bool = False) -> Path:
    """Download `src.url` to `kid_dir/{ticker}.pdf`, caching on disk.

    `force=True` re-downloads even if a cached file exists (used by the
    monthly re-audit to detect silent issuer reissues).
    """
    kid_dir.mkdir(parents=True, exist_ok=True)
    out = kid_dir / f"{src.ticker}.pdf"
    if not force and out.exists() and out.stat().st_size > 1024:
        return out
    resp = requests.get(
        src.url,
        headers={"User-Agent": "pea-audit/0.1"},
        timeout=30,
        allow_redirects=True,
    )
    resp.raise_for_status()
    out.write_bytes(resp.content)
    return out


def audit_ticker(
    ticker: str,
    llm: "VisionLLM",
    kid_dir: Path,
    cache: "VerdictCache | None" = None,
    force_refresh: bool = False,
) -> TickerAuditResult:
    """Audit a fund by ticker. Never raises — errors are returned in the result.

    Args:
        ticker: e.g. "EWLD.PA". Must be registered via pea_audit.sources.
        llm: A VisionLLM (e.g. OllamaCloudClient).
        kid_dir: Where to store downloaded KID PDFs (one per ticker).
        cache: Optional VerdictCache to skip the LLM on previously-seen PDFs.
        force_refresh: If True, re-downloads the KID and bypasses the verdict
            cache — used by the monthly re-audit cron to catch silent issuer
            reissues.

    Returns:
        TickerAuditResult — `.verdict` set on success, `.error` populated otherwise.
    """
    src = get_source(ticker)
    if src is None:
        return TickerAuditResult(
            ticker=ticker, source=None, verdict=None,
            error=f"No KID source registered for ticker {ticker!r}. "
                  "Register one via pea_audit.sources.register_source(...).",
        )
    try:
        pdf_path = _download_kid(src, kid_dir, force=force_refresh)
    except Exception as e:
        return TickerAuditResult(
            ticker=ticker, source=src, verdict=None,
            error=f"KID download failed: {e}",
        )
    try:
        verdict = audit_pdf(
            pdf_path,
            llm=llm,
            cache=None if force_refresh else cache,
        )
    except Exception as e:
        return TickerAuditResult(
            ticker=ticker, source=src, verdict=None,
            error=f"Audit failed: {e}",
        )
    return TickerAuditResult(ticker=ticker, source=src, verdict=verdict, error=None)


def get_cached_verdict(
    ticker: str,
    cache: "VerdictCache",
    kid_dir: Path,
) -> PeaVerdict | None:
    """Look up a previously-cached verdict for `ticker` without any network/LLM call.

    Resolves ticker → kid_dir/{ticker}.pdf → sha256 → cache lookup.
    Returns None if the KID was never downloaded or never audited.
    """
    src = get_source(ticker)
    if src is None:
        return None
    pdf_path = kid_dir / f"{src.ticker}.pdf"
    return cache.get_by_path(pdf_path)
