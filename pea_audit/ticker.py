"""Ticker-based audit: resolve ticker → KID URL → download → audit.

`audit_ticker(...)` is the convenience entry point for "I have a ticker,
tell me if it's PEA-eligible." Returns a `TickerAuditResult` that never
raises — errors are captured in the `.error` field for batch processing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import requests

from .core import PeaVerdict, audit_pdf
from .sources.base import KIDSource, get_source

# Hard cap on KID download size — real KIDs are 100–500 KB; anything past
# this is almost certainly hostile (zip-bomb redirect, infinite stream).
MAX_KID_BYTES = 20 * 1024 * 1024  # 20 MB
_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "application/octet-stream",
    "binary/octet-stream",
)


class KIDDownloadError(RuntimeError):
    """Raised when a KID download fails, is rejected for safety, or oversized."""

if TYPE_CHECKING:
    from .cache import VerdictCache
    from .llm.base import AsyncVisionLLM, VisionLLM


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

    Guards (against the fact that `KIDSource.url` is user-registrable):
      * URL scheme must be http or https (no file://, data://, etc.)
      * Response body is streamed; aborts above MAX_KID_BYTES (default 20 MB)
      * Content-Type must look like a PDF before bytes hit disk
    """
    parsed = urlparse(src.url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise KIDDownloadError(
            f"URL scheme {parsed.scheme!r} not allowed (http/https only)"
        )

    kid_dir.mkdir(parents=True, exist_ok=True)
    out = kid_dir / f"{src.ticker}.pdf"
    if not force and out.exists() and out.stat().st_size > 1024:
        return out

    with requests.get(
        src.url,
        headers={"User-Agent": "pea-audit/0.1"},
        timeout=30,
        allow_redirects=True,
        stream=True,
    ) as resp:
        resp.raise_for_status()

        ctype = resp.headers.get("Content-Type", "").lower()
        if not any(ctype.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
            raise KIDDownloadError(
                f"Unexpected Content-Type {ctype!r} for {src.url} — expected PDF"
            )

        # Stream into memory with a hard cap so a hostile server can't OOM us.
        buf = bytearray()
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            buf.extend(chunk)
            if len(buf) > MAX_KID_BYTES:
                raise KIDDownloadError(
                    f"KID exceeds {MAX_KID_BYTES} bytes — refusing to download"
                )

    out.write_bytes(bytes(buf))
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
    prompt_version: str = "",
) -> PeaVerdict | None:
    """Look up a previously-cached verdict for `ticker` without any network/LLM call.

    Resolves ticker → kid_dir/{ticker}.pdf → sha256 → cache lookup.
    Returns None if the KID was never downloaded or never audited.

    `prompt_version` must match the version used when the verdict was cached
    (the cache key incorporates it since v0.2.0). Pass `DEFAULT_PROMPT_VERSION`
    or read it from `pea_audit.core.DEFAULT_PROMPT_VERSION`.
    """
    src = get_source(ticker)
    if src is None:
        return None
    pdf_path = kid_dir / f"{src.ticker}.pdf"
    return cache.get_by_path(pdf_path, prompt_version=prompt_version)


# ─── Async variant ───────────────────────────────────────────────────────────


async def aaudit_ticker(
    ticker: str,
    llm: "AsyncVisionLLM",
    kid_dir: Path,
    cache: "VerdictCache | None" = None,
    force_refresh: bool = False,
) -> TickerAuditResult:
    """Async sibling of `audit_ticker`. KID download stays sync (small one-shot
    request); only the LLM call is awaited."""
    from .core import aaudit_pdf

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
        verdict = await aaudit_pdf(
            pdf_path, llm=llm, cache=None if force_refresh else cache,
        )
    except Exception as e:
        return TickerAuditResult(
            ticker=ticker, source=src, verdict=None,
            error=f"Audit failed: {e}",
        )
    return TickerAuditResult(ticker=ticker, source=src, verdict=verdict, error=None)
