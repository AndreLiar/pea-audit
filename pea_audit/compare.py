"""Verdict comparison — for re-audit cron / change detection."""

from __future__ import annotations

from .core import PeaVerdict

# Hard fields — categorical / deterministic, safe to diff across LLM runs.
HARD_FIELDS = ("eligible", "replication", "isin")

# Soft fields — free-text rendered by the LLM, drifts between runs
# ("BNP Paribas" vs "BNP Paribas Asset Management"). Ignored by default.
SOFT_FIELDS = ("issuer", "underlying_index")


def compare_verdicts(
    old: PeaVerdict,
    new: PeaVerdict,
    include_soft: bool = False,
) -> list[str]:
    """Return human-readable diffs between two verdicts.

    By default compares only the hard fields. `include_soft=True` also
    diffs `issuer` and `underlying_index` (useful for debugging, but
    noisy in a recurring cron).
    """
    fields = HARD_FIELDS + (SOFT_FIELDS if include_soft else ())
    diffs: list[str] = []
    for field_name in fields:
        old_val = getattr(old, field_name)
        new_val = getattr(new, field_name)
        if old_val != new_val:
            diffs.append(f"{field_name}: {old_val!r} → {new_val!r}")
    return diffs
