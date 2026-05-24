"""Core audit logic — pure functions + dataclasses.

The library's central function is `audit_pdf(pdf_path, llm, cache=None)`.
Given a PDF and a `VisionLLM`, returns a `PeaVerdict` with structured
fields + verbatim citations.

The audit cache is opt-in: pass `cache=VerdictCache(Path("./cache"))` to
skip the LLM on previously-seen PDFs (keyed by sha256 of the bytes).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .isin import extract_isins
from .pdf import pdf_to_images
from .prompts import load_prompt

if TYPE_CHECKING:
    from .cache import VerdictCache
    from .llm.base import VisionLLM


DEFAULT_PROMPT_VERSION = "v2"


@dataclass(frozen=True)
class Citation:
    quote: str
    page: int


@dataclass(frozen=True)
class PeaVerdict:
    """The structured output of a PEA-eligibility audit.

    Hard fields (`eligible`, `replication`, `isin`) are categorical / deterministic
    and stable across LLM runs. Soft fields (`issuer`, `underlying_index`,
    `summary_fr`, `evidence`) are free-text and may drift between runs of
    the same input — diffing them across audits will produce false positives.
    """

    eligible: Literal["yes", "no", "uncertain"]
    confidence: Literal["low", "medium", "high"]
    replication: Literal["physical", "synthetic_swap", "unknown"]
    underlying_index: str
    issuer: str
    isin: str
    evidence: list[Citation] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    summary_fr: str = ""


PEA_VERDICT_SCHEMA: dict = {
    "type": "object",
    "required": [
        "eligible", "confidence", "replication", "underlying_index",
        "issuer", "isin", "evidence", "red_flags", "summary_fr",
    ],
    "properties": {
        "eligible": {"type": "string", "enum": ["yes", "no", "uncertain"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "replication": {"type": "string", "enum": ["physical", "synthetic_swap", "unknown"]},
        "underlying_index": {"type": "string"},
        "issuer": {"type": "string"},
        "isin": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["quote", "page"],
                "properties": {
                    "quote": {"type": "string"},
                    "page": {"type": "integer", "minimum": 1},
                },
            },
        },
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "summary_fr": {"type": "string"},
    },
}


def _parse_citation(c) -> Citation:
    """Tolerant parser — some LLM outputs use 'text' instead of 'quote',
    or return raw strings instead of dicts."""
    if isinstance(c, str):
        return Citation(quote=c, page=1)
    if isinstance(c, dict):
        quote = c.get("quote") or c.get("text") or ""
        try:
            page = int(c.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        return Citation(quote=str(quote), page=page)
    return Citation(quote=str(c), page=1)


def _reconcile_isin(verdict: PeaVerdict, extracted: list[str]) -> PeaVerdict:
    """Prefer a text-extracted ISIN (deterministic) over the LLM's vision read."""
    if not extracted:
        return verdict
    if verdict.isin in extracted:
        return verdict
    return replace(verdict, isin=extracted[0])


def audit_pdf(
    pdf_path: str | Path,
    llm: "VisionLLM",
    cache: "VerdictCache | None" = None,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> PeaVerdict:
    """Audit a single PDF for PEA eligibility.

    Args:
        pdf_path: Path to the KID/DIC/factsheet PDF.
        llm: Any VisionLLM implementation. Use `OllamaCloudClient(api_key=...)`
            for the default Gemma 4 backend.
        cache: Optional `VerdictCache`. If supplied, a previously-seen PDF
            (by sha256 of bytes) returns its cached verdict instantly.
        prompt_version: Which prompt file under `pea_audit/prompts/audit_v{N}.md`
            to use. Defaults to "v2".

    Returns:
        A `PeaVerdict` with `eligible`, `replication`, `isin`, evidence quotes, etc.
    """
    pdf_path = Path(pdf_path)
    pdf_bytes = pdf_path.read_bytes()

    if cache is not None:
        cached = cache.get(pdf_bytes)
        if cached is not None:
            return cached

    system, user_prompt = load_prompt(prompt_version)

    images = pdf_to_images(pdf_path)
    extracted_isins = extract_isins(pdf_path)

    prompt = user_prompt
    if extracted_isins:
        prompt += (
            "\n\nISIN extraits du texte du PDF (déterministes, check-digit validé) : "
            + ", ".join(extracted_isins)
            + ". Choisis celui qui correspond au fonds analysé."
        )

    raw = llm.analyze_images(
        images=images,
        prompt=prompt,
        schema=PEA_VERDICT_SCHEMA,
        system=system,
    )

    verdict = PeaVerdict(
        eligible=raw["eligible"],
        confidence=raw["confidence"],
        replication=raw["replication"],
        underlying_index=raw["underlying_index"],
        issuer=raw["issuer"],
        isin=raw["isin"],
        evidence=[_parse_citation(c) for c in raw.get("evidence", [])],
        red_flags=list(raw.get("red_flags", [])),
        summary_fr=raw.get("summary_fr", ""),
    )
    verdict = _reconcile_isin(verdict, extracted_isins)

    if cache is not None:
        cache.put(pdf_bytes, verdict)

    return verdict
