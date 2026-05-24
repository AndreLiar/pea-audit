"""OllamaCloudClient — VisionLLM impl backed by Ollama Cloud (Gemma 4 by default).

Two production-grade behaviors built in:
  * `tenacity` retries on transient errors only (network, 5xx) — not on 4xx
    or schema parse errors, since retrying won't fix them.
  * Optional Langfuse tracing — opt-in via `enable_langfuse()` after the
    consuming app has loaded its environment.

This module does NOT call `load_dotenv()` and does NOT read env vars at
import. The app is responsible for loading config and passing an explicit
api_key to the constructor.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from ollama import Client, ResponseError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

DEFAULT_MODEL = "gemma4:31b-cloud"
DEFAULT_HOST = "https://ollama.com"


# ─── Optional Langfuse observability ─────────────────────────────────────────
# Apps call enable_langfuse() (typically after load_dotenv()) to wrap
# `OllamaCloudClient.analyze_images` with the @observe decorator. Library
# users who don't want observability skip this — the class works as-is.

_langfuse_enabled = False
_langfuse_client = None


def enable_langfuse() -> bool:
    """Activate Langfuse tracing for OllamaCloudClient.analyze_images.

    Reads LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY from env. Optionally
    bridges LANGFUSE_BASE_URL → LANGFUSE_HOST (the SDK's canonical name)
    so either env var name works.

    Returns True if Langfuse was successfully activated, False if keys
    are missing (no-op, no error).
    """
    global _langfuse_enabled, _langfuse_client

    if _langfuse_enabled:
        return True

    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return False

    if os.environ.get("LANGFUSE_BASE_URL") and not os.environ.get("LANGFUSE_HOST"):
        os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

    from langfuse import get_client, observe

    _langfuse_client = get_client()

    # Wrap the method on the class so every instance benefits.
    OllamaCloudClient.analyze_images = observe(  # type: ignore[method-assign]
        as_type="generation", name="ollama_chat"
    )(OllamaCloudClient.analyze_images)

    _langfuse_enabled = True
    return True


def _is_transient(exc: BaseException) -> bool:
    """Only retry on network/timeout/5xx — not on 4xx (auth, schema) or parse errors."""
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, ResponseError):
        status = getattr(exc, "status_code", None)
        return status is None or status >= 500
    return False


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    """Strip optional ```json ... ``` fences. Some models (Gemma 4 included)
    wrap their output even when `format=<schema>` is supplied."""
    m = _FENCE_RE.match(text)
    return m.group(1) if m else text.strip()


class OllamaCloudClient:
    """VisionLLM impl using Ollama Cloud.

    Example:
        >>> client = OllamaCloudClient(api_key="sk-...")
        >>> verdict = client.analyze_images(
        ...     images=[png_bytes],
        ...     prompt="Extract the ISIN.",
        ...     schema={"type": "object", "properties": {"isin": {"type": "string"}}},
        ... )
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
    ):
        if not api_key:
            raise ValueError("api_key is required for OllamaCloudClient")
        self._client = Client(host=host, headers={"Authorization": f"Bearer {api_key}"})
        self._model = model

    def analyze_images(
        self,
        images: list[bytes],
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
    ) -> dict[str, Any]:
        if not images:
            raise ValueError("At least one image is required")

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt, "images": images})

        response = self._chat_with_retry(messages, schema)
        raw = response["message"]["content"]
        cleaned = _strip_code_fence(raw)

        # If Langfuse is active, enrich the trace with model + i/o + usage.
        if _langfuse_enabled and _langfuse_client is not None:
            trace_input = [
                m if m.get("role") != "user" else {**m, "images": f"<{len(images)} image(s)>"}
                for m in messages
            ]
            _langfuse_client.update_current_generation(
                model=self._model,
                input=trace_input,
                output=cleaned,
                usage_details=response.get("usage") if isinstance(response, dict) else None,
            )

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Non-JSON response from {self._model} ({len(raw)} chars). "
                f"Start: {raw[:500]!r}"
            ) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        retry=retry_if_exception(_is_transient),
        reraise=True,
    )
    def _chat_with_retry(self, messages: list[dict], schema: dict) -> dict:
        return self._client.chat(
            model=self._model,
            messages=messages,
            format=schema,
            options={"temperature": 1.0, "top_p": 0.95, "top_k": 64},
        )
