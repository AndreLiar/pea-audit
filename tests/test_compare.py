"""Tests for compare_verdicts — hard vs soft field selection."""

from pea_audit import PeaVerdict, compare_verdicts


def _v(**overrides) -> PeaVerdict:
    defaults = dict(
        eligible="yes",
        confidence="high",
        replication="synthetic_swap",
        underlying_index="MSCI World",
        issuer="Amundi",
        isin="FR001400U5Q4",
    )
    defaults.update(overrides)
    return PeaVerdict(**defaults)  # type: ignore[arg-type]


def test_identical_verdicts_have_no_diffs() -> None:
    assert compare_verdicts(_v(), _v()) == []


def test_eligibility_flip_is_detected() -> None:
    diffs = compare_verdicts(_v(eligible="yes"), _v(eligible="no"))
    assert len(diffs) == 1
    assert "eligible" in diffs[0]


def test_replication_change_is_detected() -> None:
    diffs = compare_verdicts(
        _v(replication="synthetic_swap"),
        _v(replication="physical"),
    )
    assert any("replication" in d for d in diffs)


def test_isin_change_is_detected() -> None:
    diffs = compare_verdicts(
        _v(isin="FR001400U5Q4"),
        _v(isin="FR0013412269"),
    )
    assert any("isin" in d for d in diffs)


def test_issuer_drift_ignored_by_default() -> None:
    """Free-text drift like 'BNP Paribas' vs 'BNP Paribas AM' must NOT trigger."""
    diffs = compare_verdicts(
        _v(issuer="BNP Paribas"),
        _v(issuer="BNP Paribas Asset Management"),
    )
    assert diffs == []


def test_underlying_index_drift_ignored_by_default() -> None:
    diffs = compare_verdicts(
        _v(underlying_index="S&P US Tech 100 Index"),
        _v(underlying_index="S&P US Tech Index"),
    )
    assert diffs == []


def test_soft_fields_detected_with_include_soft_true() -> None:
    diffs = compare_verdicts(
        _v(issuer="BNP Paribas"),
        _v(issuer="BNP Paribas Asset Management"),
        include_soft=True,
    )
    assert any("issuer" in d for d in diffs)


def test_summary_and_evidence_never_diffed() -> None:
    """Even with include_soft, free-form summary/evidence aren't part of the diff set."""
    a = _v(summary_fr="version A")
    b = _v(summary_fr="version B totally different")
    assert compare_verdicts(a, b, include_soft=True) == []
