"""Shared test fixtures, including a fake VisionLLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from pea_audit.llm.base import VisionLLM


@dataclass
class FakeVisionLLM:
    """A VisionLLM impl that returns a pre-baked response and records calls.

    Implements the VisionLLM protocol structurally — anyone implementing
    `analyze_images(images, prompt, schema, system=None) -> dict` satisfies it.
    """

    response: dict[str, Any] = field(default_factory=dict)
    raises: BaseException | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def analyze_images(
        self,
        images: list[bytes],
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append({
            "n_images": len(images),
            "prompt": prompt,
            "schema_keys": sorted(schema.get("properties", {}).keys()),
            "system": system,
        })
        if self.raises is not None:
            raise self.raises
        return self.response


def _verdict_dict(**overrides) -> dict:
    """Canned valid response that matches PEA_VERDICT_SCHEMA."""
    base = dict(
        eligible="yes",
        confidence="high",
        replication="synthetic_swap",
        underlying_index="MSCI World",
        issuer="Amundi",
        isin="FR001400U5Q4",
        evidence=[{"quote": "test quote", "page": 1}],
        red_flags=[],
        summary_fr="Test verdict.",
    )
    base.update(overrides)
    return base


@pytest.fixture
def fake_llm_eligible() -> FakeVisionLLM:
    return FakeVisionLLM(response=_verdict_dict())


@pytest.fixture
def fake_llm_ineligible() -> FakeVisionLLM:
    return FakeVisionLLM(response=_verdict_dict(
        eligible="no",
        replication="physical",
        issuer="iShares",
        isin="IE00B5BMR087",
        underlying_index="S&P 500",
        summary_fr="Physical S&P 500 — not PEA-eligible.",
    ))


@pytest.fixture
def sample_kid() -> str:
    """Path to the real Amundi PEA Monde KID shipped in samples/."""
    return "samples/amundi_pea_monde_kid.pdf"


def test_fake_satisfies_protocol() -> None:
    """Smoke check: FakeVisionLLM passes the runtime-checkable protocol."""
    assert isinstance(FakeVisionLLM(), VisionLLM)
