"""Tests for the prompt loader."""

from pathlib import Path

import pytest

from pea_audit.prompts import load_prompt


def test_v2_loads_with_system_and_user() -> None:
    system, user = load_prompt("v2")
    assert system, "system prompt empty"
    assert user, "user prompt empty"
    # v2 must include the replication inference rules (the fix that took us from 11/13 to 13/13).
    assert "physique" in system.lower() or "physical" in system.lower()
    assert "swap" in system.lower()


def test_v1_still_loadable() -> None:
    system, user = load_prompt("v1")
    assert system and user


def test_unknown_version_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("v999")


def test_custom_prompts_dir(tmp_path: Path) -> None:
    """A user can ship their own prompts directory."""
    f = tmp_path / "audit_custom.md"
    f.write_text(
        "# Notes\n\n"
        "## System prompt\n"
        "You are a test analyst.\n\n"
        "## User prompt\n"
        "Analyze this.\n"
    )
    # Bust lru_cache for this version (functools.lru_cache is per-args).
    load_prompt.cache_clear()
    system, user = load_prompt("custom", prompts_dir=tmp_path)
    assert system == "You are a test analyst."
    assert user == "Analyze this."
