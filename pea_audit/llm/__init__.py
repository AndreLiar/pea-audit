"""LLM backends.

The library defines a `VisionLLM` protocol that any vision-capable model
can implement. The default implementation wraps Ollama Cloud (Gemma 4).
"""

from .base import VisionLLM
from .ollama import OllamaCloudClient, enable_langfuse

__all__ = ["VisionLLM", "OllamaCloudClient", "enable_langfuse"]
