"""VisionLLM protocols — the contracts every LLM backend must implement.

`VisionLLM` for sync code, `AsyncVisionLLM` for async (webhook handlers,
batch processing). Default implementations in `pea_audit.llm.ollama`;
community implementations might wrap Anthropic Claude vision, OpenAI
GPT-4o, Google Gemini, etc.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VisionLLM(Protocol):
    """A vision-capable LLM that returns JSON conforming to a schema.

    Pass images + prompt + JSON schema, get back a dict that satisfies
    the schema. Retries, observability, streaming, and other concerns
    are the implementation's job — not the protocol's.
    """

    def analyze_images(
        self,
        images: list[bytes],
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
    ) -> dict[str, Any]:
        """Send images + prompt + schema, get back a dict matching the schema.

        Args:
            images: PNG/JPEG bytes, one per page. Most vision models prefer
                images placed before text in the prompt.
            prompt: User-message text.
            schema: JSON Schema dict the output must conform to.
            system: Optional system prompt.

        Returns:
            A dict satisfying `schema`.

        Raises:
            Implementation-defined for transport errors (network, 4xx, 5xx).
            Should raise on schema-incompatible output.
        """
        ...


@runtime_checkable
class AsyncVisionLLM(Protocol):
    """Async sibling of `VisionLLM` for use with `aaudit_pdf` / `aaudit_ticker`."""

    async def analyze_images(
        self,
        images: list[bytes],
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
    ) -> dict[str, Any]:
        ...
