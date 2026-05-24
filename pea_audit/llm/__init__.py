"""LLM backends.

The library defines a `VisionLLM` protocol that any vision-capable model
can implement. The default implementation wraps Ollama Cloud (Gemma 4).
"""

from .base import AsyncVisionLLM, VisionLLM
from .ollama import AsyncOllamaCloudClient, OllamaCloudClient, enable_langfuse

__all__ = [
    "VisionLLM",
    "AsyncVisionLLM",
    "OllamaCloudClient",
    "AsyncOllamaCloudClient",
    "enable_langfuse",
]
