"""pea-audit — PEA-eligibility auditor for ETF KID documents.

Audits ETF KID/DIC PDFs against French PEA (Plan d'Épargne en Actions)
rules using a vision LLM. Ships with pluggable LLM backends, a registry
of KID source URLs by ticker, versioned prompts, and a 13-case regression
eval suite.

Quickstart:
    from pathlib import Path
    from pea_audit import audit_pdf, VerdictCache
    from pea_audit.llm import OllamaCloudClient

    llm = OllamaCloudClient(api_key="sk-...")
    cache = VerdictCache(Path("./cache"))

    verdict = audit_pdf("kid.pdf", llm=llm, cache=cache)
    print(verdict.eligible, verdict.replication, verdict.isin)
"""

from .cache import VerdictCache
from .compare import HARD_FIELDS, SOFT_FIELDS, compare_verdicts
from .core import (
    DEFAULT_PROMPT_VERSION,
    PEA_VERDICT_SCHEMA,
    Citation,
    PeaVerdict,
    audit_pdf,
)
from .isin import extract_isins, isin_check_digit_valid
from .ticker import TickerAuditResult, audit_ticker, get_cached_verdict

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Core audit
    "audit_pdf",
    "audit_ticker",
    "get_cached_verdict",
    # Dataclasses
    "PeaVerdict",
    "Citation",
    "TickerAuditResult",
    # Cache
    "VerdictCache",
    # Comparison (for re-audit cron)
    "compare_verdicts",
    "HARD_FIELDS",
    "SOFT_FIELDS",
    # Schema (for advanced users with custom LLMs)
    "PEA_VERDICT_SCHEMA",
    "DEFAULT_PROMPT_VERSION",
    # ISIN helpers
    "extract_isins",
    "isin_check_digit_valid",
]
