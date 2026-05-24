"""FastAPI service exposing pea-audit + ETFTracker over HTTP.

Run :
    uvicorn api:app --host 0.0.0.0 --port 8080

Endpoints :
    GET  /                              health + version
    GET  /portfolio                     totals + valued positions
    GET  /portfolio/positions           list, with cached PEA verdict per line
    GET  /audit/{ticker}                cached verdict only (404 if not audited)
    POST /audit/{ticker}                force re-audit (1 LLM call)
    POST /audit/upload                  multipart PDF → verdict
    POST /audit/portfolio/recheck       re-audit every position (N LLM calls)
    GET  /audit/history                 cache/audit_history.json
    GET  /audit/alerts                  list cache/alerts/*.md

Auth : set API_TOKEN in env to require Authorization: Bearer <token> on
mutating endpoints. If unset, the API runs unauthenticated and logs a warning.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Header, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from pea_audit import (
    PeaVerdict,
    TickerAuditResult,
    VerdictCache,
    audit_pdf,
    audit_ticker,
    get_cached_verdict,
)
from pea_audit.llm import OllamaCloudClient, enable_langfuse
from pea_audit.sources import all_sources

from etftracker.data_source import get_prices
from etftracker.portfolio import load_positions, totaux, valoriser

logger = logging.getLogger("pea-audit-api")
logging.basicConfig(level=logging.INFO)

CACHE_DIR = Path("cache/audits")
KID_DIR = Path("cache/kids")
HISTORY_FILE = Path("cache/audit_history.json")
ALERTS_DIR = Path("cache/alerts")

# ─── Singletons (constructed once at startup) ────────────────────────────────

_api_key = os.environ.get("OLLAMA_API_KEY")
if not _api_key:
    raise RuntimeError("OLLAMA_API_KEY missing — add it to .env before starting the API.")

enable_langfuse()
_llm = OllamaCloudClient(api_key=_api_key)
_cache = VerdictCache(CACHE_DIR)

_API_TOKEN = os.environ.get("API_TOKEN")
if not _API_TOKEN:
    logger.warning(
        "API_TOKEN not set — API runs UNAUTHENTICATED. Set API_TOKEN in .env "
        "to require bearer auth on mutating endpoints."
    )


# ─── Auth dependency ─────────────────────────────────────────────────────────


def require_auth(authorization: Annotated[str | None, Header()] = None) -> None:
    """Bearer-token auth. No-op when API_TOKEN is unset (dev mode)."""
    if _API_TOKEN is None:
        return
    expected = f"Bearer {_API_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Pydantic response models ────────────────────────────────────────────────


class CitationModel(BaseModel):
    quote: str
    page: int


class VerdictModel(BaseModel):
    eligible: str
    confidence: str
    replication: str
    underlying_index: str
    issuer: str
    isin: str
    evidence: list[CitationModel]
    red_flags: list[str]
    summary_fr: str

    @classmethod
    def from_verdict(cls, v: PeaVerdict) -> "VerdictModel":
        d = asdict(v)
        return cls(**d)


class PositionModel(BaseModel):
    ticker: str
    nom: str
    parts: float
    pru: float
    cours: float | None
    valeur: float | None
    cout: float
    plus_value: float | None
    plus_value_pct: float | None
    pea_eligible: str | None  # "yes" / "no" / "uncertain" / None (not audited)


class TotalsModel(BaseModel):
    cout_total: float
    valeur_actuelle: float
    plus_value: float
    plus_value_pct: float | None
    lignes_valorisees: int
    lignes_total: int


class PortfolioModel(BaseModel):
    totals: TotalsModel
    positions: list[PositionModel]


class TickerAuditModel(BaseModel):
    ticker: str
    verdict: VerdictModel | None
    error: str | None

    @classmethod
    def from_result(cls, r: TickerAuditResult) -> "TickerAuditModel":
        return cls(
            ticker=r.ticker,
            verdict=VerdictModel.from_verdict(r.verdict) if r.verdict else None,
            error=r.error,
        )


# ─── App ─────────────────────────────────────────────────────────────────────


app = FastAPI(
    title="pea-audit API",
    version="0.1.0",
    description=(
        "HTTP API on top of pea-audit + ETFTracker. Audits ETF KID PDFs "
        "for French PEA (Plan d'Épargne en Actions) eligibility using "
        "a vision LLM."
    ),
)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": "pea-audit",
        "version": "0.1.0",
        "registered_sources": sorted(all_sources().keys()),
        "auth_required": _API_TOKEN is not None,
        "docs": "/docs",
    }


# ─── Portfolio (read-only, no LLM) ───────────────────────────────────────────


@app.get("/portfolio", response_model=PortfolioModel, tags=["portfolio"])
def portfolio() -> PortfolioModel:
    """Live portfolio valuation + cached PEA verdict per position."""
    positions_cfg = load_positions()
    prices = get_prices([p.ticker for p in positions_cfg])
    lignes = valoriser(positions_cfg, prices)
    t = totaux(lignes)

    rows: list[PositionModel] = []
    for l in lignes:
        cached = get_cached_verdict(l.ticker, cache=_cache, kid_dir=KID_DIR)
        rows.append(PositionModel(
            ticker=l.ticker,
            nom=l.nom,
            parts=l.nb_parts,
            pru=l.prix_achat_moyen,
            cours=l.prix_actuel,
            valeur=l.valeur_actuelle,
            cout=l.cout_total,
            plus_value=l.plus_value,
            plus_value_pct=l.plus_value_pct,
            pea_eligible=cached.eligible if cached else None,
        ))

    return PortfolioModel(
        totals=TotalsModel(
            cout_total=t.cout_total,
            valeur_actuelle=t.valeur_actuelle,
            plus_value=t.plus_value,
            plus_value_pct=t.plus_value_pct,
            lignes_valorisees=sum(1 for l in lignes if l.valeur_actuelle is not None),
            lignes_total=len(lignes),
        ),
        positions=rows,
    )


@app.get("/portfolio/positions", response_model=list[PositionModel], tags=["portfolio"])
def positions_list() -> list[PositionModel]:
    return portfolio().positions


# ─── Audit ───────────────────────────────────────────────────────────────────


@app.get("/audit/{ticker}", response_model=VerdictModel, tags=["audit"])
def audit_get(ticker: str) -> VerdictModel:
    """Read-only cached verdict for a ticker. Returns 404 if not yet audited."""
    v = get_cached_verdict(ticker, cache=_cache, kid_dir=KID_DIR)
    if v is None:
        raise HTTPException(
            status_code=404,
            detail=f"No cached verdict for {ticker!r}. POST /audit/{ticker} to run one.",
        )
    return VerdictModel.from_verdict(v)


@app.post(
    "/audit/{ticker}", response_model=TickerAuditModel, tags=["audit"],
    dependencies=[Depends(require_auth)],
)
def audit_post(ticker: str, force_refresh: bool = False) -> TickerAuditModel:
    """Audit a ticker (downloads KID if needed). Cached on success.

    `force_refresh=true` re-downloads the KID and bypasses the verdict cache.
    """
    result = audit_ticker(
        ticker, llm=_llm, kid_dir=KID_DIR, cache=_cache, force_refresh=force_refresh,
    )
    return TickerAuditModel.from_result(result)


@app.post(
    "/audit/upload", response_model=VerdictModel, tags=["audit"],
    dependencies=[Depends(require_auth)],
)
async def audit_upload(file: UploadFile) -> VerdictModel:
    """Upload a DIC/KID PDF directly, get back a verdict."""
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(400, f"Expected PDF, got {file.content_type!r}")
    data = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        verdict = audit_pdf(tmp_path, llm=_llm, cache=_cache)
    finally:
        tmp_path.unlink(missing_ok=True)
    return VerdictModel.from_verdict(verdict)


@app.post(
    "/audit/portfolio/recheck", response_model=list[TickerAuditModel], tags=["audit"],
    dependencies=[Depends(require_auth)],
)
def audit_portfolio_recheck(force_refresh: bool = False) -> list[TickerAuditModel]:
    """Audit every ticker in positions.csv. Returns the batch results."""
    positions_cfg = load_positions()
    results = [
        audit_ticker(
            p.ticker, llm=_llm, kid_dir=KID_DIR, cache=_cache, force_refresh=force_refresh,
        )
        for p in positions_cfg
    ]
    return [TickerAuditModel.from_result(r) for r in results]


@app.get("/audit/history", tags=["audit"])
def audit_history() -> dict:
    """Return the full audit_history.json (per-ticker timeline of verdicts)."""
    if not HISTORY_FILE.exists():
        return {}
    return json.loads(HISTORY_FILE.read_text())


@app.get("/audit/alerts", tags=["audit"])
def audit_alerts_list() -> list[str]:
    """List dates that have alert files (changes detected during re-audit)."""
    if not ALERTS_DIR.exists():
        return []
    return sorted(p.stem for p in ALERTS_DIR.glob("*.md"))


@app.get("/audit/alerts/{date}", response_class=PlainTextResponse, tags=["audit"])
def audit_alert_get(date: str) -> str:
    """Return the markdown alert file for a given date (YYYY-MM-DD)."""
    f = ALERTS_DIR / f"{date}.md"
    if not f.exists():
        raise HTTPException(404, f"No alert for date {date!r}")
    return f.read_text()
