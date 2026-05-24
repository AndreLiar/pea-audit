"""Example 03 — Implement a custom VisionLLM.

The library defines a `VisionLLM` Protocol. Anything implementing
`analyze_images(images, prompt, schema, system=None) -> dict` satisfies it.

This example shows a fake/stub implementation that returns canned output —
the same pattern works for Claude vision, GPT-4o, Gemini, a local Ollama
instance, or anything else you wire up.

Run :  python examples/03_custom_llm.py  (no Ollama key needed)
"""

from __future__ import annotations

from typing import Any

from pea_audit import audit_pdf
from pea_audit.llm import VisionLLM


class StubLLM:
    """Minimal VisionLLM that returns a canned verdict. Useful for tests
    or as a starting point when wiring up a new provider."""

    def analyze_images(
        self,
        images: list[bytes],
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
    ) -> dict[str, Any]:
        print(f"  [StubLLM] received {len(images)} image(s), {len(prompt)} chars of prompt")
        return {
            "eligible": "yes",
            "confidence": "high",
            "replication": "synthetic_swap",
            "underlying_index": "MSCI World (stub)",
            "issuer": "Stub Issuer",
            "isin": "FR001400U5Q4",
            "evidence": [{"quote": "stub evidence", "page": 1}],
            "red_flags": [],
            "summary_fr": "This is a stubbed verdict — no real LLM was called.",
        }


def main() -> None:
    # Runtime protocol check — confirms StubLLM is shape-compatible
    assert isinstance(StubLLM(), VisionLLM)
    print("✓ StubLLM satisfies the VisionLLM protocol")
    print()

    verdict = audit_pdf("samples/amundi_pea_monde_kid.pdf", llm=StubLLM())
    print(f"verdict: {verdict.eligible.value} ({verdict.summary_fr})")


if __name__ == "__main__":
    main()
