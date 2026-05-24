"""Tests for audit_pdf — uses FakeVisionLLM so no real LLM calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from pea_audit import (
    Eligible,
    PeaVerdict,
    Replication,
    VerdictCache,
    audit_pdf,
)

from .conftest import FakeVisionLLM, _verdict_dict


def test_audit_pdf_returns_typed_verdict(fake_llm_eligible: FakeVisionLLM, sample_kid: str) -> None:
    v = audit_pdf(sample_kid, llm=fake_llm_eligible)
    assert isinstance(v, PeaVerdict)
    assert v.eligible is Eligible.YES
    assert v.replication is Replication.SYNTHETIC_SWAP
    assert v.issuer == "Amundi"


def test_audit_pdf_calls_llm_with_images_and_schema(
    fake_llm_eligible: FakeVisionLLM, sample_kid: str
) -> None:
    audit_pdf(sample_kid, llm=fake_llm_eligible)
    assert len(fake_llm_eligible.calls) == 1
    call = fake_llm_eligible.calls[0]
    assert call["n_images"] >= 1  # pdf_to_images rendered at least one page
    assert "eligible" in call["schema_keys"]
    assert "replication" in call["schema_keys"]
    assert call["system"] is not None  # system prompt loaded


def test_audit_pdf_extracts_isin_deterministically(
    fake_llm_eligible: FakeVisionLLM, sample_kid: str
) -> None:
    """The sample PDF's text layer has ISIN FR001400U5Q4. If the LLM returns
    a different (wrong) ISIN, the deterministic extractor should override."""
    fake = FakeVisionLLM(response=_verdict_dict(isin="WRONG12345WR"))
    v = audit_pdf(sample_kid, llm=fake)
    assert v.isin == "FR001400U5Q4"  # reconciled from PDF text


def test_audit_pdf_keeps_llm_isin_if_extracted_matches(
    fake_llm_eligible: FakeVisionLLM, sample_kid: str
) -> None:
    """If the LLM's ISIN is in the extracted set, it's kept verbatim."""
    v = audit_pdf(sample_kid, llm=fake_llm_eligible)
    assert v.isin == "FR001400U5Q4"
    # only one valid ISIN in the sample, so the LLM's "FR001400U5Q4" is preserved
    # and the test confirms no reconciliation diverged.


def test_audit_pdf_cache_hit_skips_llm(
    fake_llm_eligible: FakeVisionLLM, sample_kid: str, tmp_path: Path
) -> None:
    cache = VerdictCache(tmp_path)
    # First call: cache miss → LLM is called
    audit_pdf(sample_kid, llm=fake_llm_eligible, cache=cache)
    assert len(fake_llm_eligible.calls) == 1

    # Second call: cache hit → LLM is NOT called again
    fresh_calls = list(fake_llm_eligible.calls)
    audit_pdf(sample_kid, llm=fake_llm_eligible, cache=cache)
    assert fake_llm_eligible.calls == fresh_calls  # no new call


def test_audit_pdf_cache_miss_on_different_prompt_version(
    fake_llm_eligible: FakeVisionLLM, sample_kid: str, tmp_path: Path
) -> None:
    """Prompt version is part of the cache key — v2 hits ≠ v1 hits."""
    cache = VerdictCache(tmp_path)
    audit_pdf(sample_kid, llm=fake_llm_eligible, cache=cache, prompt_version="v2")
    assert len(fake_llm_eligible.calls) == 1

    # Different version → must re-call the LLM
    audit_pdf(sample_kid, llm=fake_llm_eligible, cache=cache, prompt_version="v1")
    assert len(fake_llm_eligible.calls) == 2


def test_audit_pdf_propagates_llm_errors(sample_kid: str) -> None:
    failing = FakeVisionLLM(raises=RuntimeError("Ollama 503"))
    with pytest.raises(RuntimeError, match="Ollama 503"):
        audit_pdf(sample_kid, llm=failing)


def test_audit_pdf_handles_string_evidence_from_llm(sample_kid: str) -> None:
    """Some LLMs return evidence items as bare strings instead of {quote, page}."""
    raw = _verdict_dict()
    raw["evidence"] = ["This is a bare string quote", "Another one"]
    fake = FakeVisionLLM(response=raw)
    v = audit_pdf(sample_kid, llm=fake)
    assert len(v.evidence) == 2
    assert v.evidence[0].quote == "This is a bare string quote"
    assert v.evidence[0].page == 1  # default when no page provided


def test_audit_pdf_handles_text_key_instead_of_quote(sample_kid: str) -> None:
    """Some LLMs use 'text' instead of 'quote' in citation dicts."""
    raw = _verdict_dict()
    raw["evidence"] = [{"text": "Test text", "page": 2}]
    fake = FakeVisionLLM(response=raw)
    v = audit_pdf(sample_kid, llm=fake)
    assert v.evidence[0].quote == "Test text"
    assert v.evidence[0].page == 2
