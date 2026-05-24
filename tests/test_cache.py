"""Tests for VerdictCache."""

from __future__ import annotations

import json
from pathlib import Path

from pea_audit import Citation, Eligible, PeaVerdict, VerdictCache


def _v() -> PeaVerdict:
    return PeaVerdict(
        eligible="yes",
        confidence="high",
        replication="synthetic_swap",
        underlying_index="MSCI World",
        issuer="Amundi",
        isin="FR001400U5Q4",
        evidence=[Citation(quote="test", page=1)],
        summary_fr="ok",
    )


def test_round_trip(tmp_path: Path) -> None:
    cache = VerdictCache(tmp_path)
    pdf = b"fake pdf bytes"

    assert cache.get(pdf) is None  # cold

    cache.put(pdf, _v())
    loaded = cache.get(pdf)

    assert loaded is not None
    assert loaded.eligible is Eligible.YES
    assert loaded.isin == "FR001400U5Q4"
    assert loaded.evidence[0].quote == "test"


def test_different_pdf_bytes_different_keys(tmp_path: Path) -> None:
    cache = VerdictCache(tmp_path)
    cache.put(b"pdf-A", _v())
    assert cache.get(b"pdf-B") is None  # different bytes → no hit


def test_prompt_version_invalidates_cache(tmp_path: Path) -> None:
    """Verdicts cached under v2 must not be served to v3 callers."""
    cache = VerdictCache(tmp_path)
    pdf = b"fake pdf bytes"

    cache.put(pdf, _v(), prompt_version="v2")
    assert cache.get(pdf, prompt_version="v2") is not None  # hit
    assert cache.get(pdf, prompt_version="v3") is None      # miss — different prompt


def test_cache_key_deterministic() -> None:
    k1 = VerdictCache.cache_key(b"abc", "v2")
    k2 = VerdictCache.cache_key(b"abc", "v2")
    k3 = VerdictCache.cache_key(b"abc", "v3")
    k4 = VerdictCache.cache_key(b"abd", "v2")
    assert k1 == k2          # same inputs → same key
    assert k1 != k3          # different prompt → different key
    assert k1 != k4          # different bytes → different key
    assert len(k1) == 16     # short prefix for filename


def test_get_by_path(tmp_path: Path) -> None:
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake")

    cache = VerdictCache(tmp_path / "cache")
    cache.put(b"fake", _v())

    loaded = cache.get_by_path(pdf_file)
    assert loaded is not None
    assert loaded.eligible is Eligible.YES


def test_get_by_path_missing_pdf_returns_none(tmp_path: Path) -> None:
    cache = VerdictCache(tmp_path)
    assert cache.get_by_path(tmp_path / "nope.pdf") is None


def test_cached_json_is_human_readable(tmp_path: Path) -> None:
    """Sanity check the on-disk format — useful when debugging cache state."""
    cache = VerdictCache(tmp_path)
    cache.put(b"x", _v())
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["eligible"] == "yes"  # Enum serializes as its str value
    assert data["isin"] == "FR001400U5Q4"
