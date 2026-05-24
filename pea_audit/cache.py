"""Opt-in file-based verdict cache.

The library NEVER writes to disk unless the app explicitly passes a
`VerdictCache(cache_dir=...)`. Keyed by sha256(pdf_bytes), so the same
PDF returned from anywhere yields the same cache hit.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .core import Citation, PeaVerdict


class VerdictCache:
    """File-based cache for `PeaVerdict`, keyed by sha256(pdf_bytes)[:16].

    Example:
        >>> cache = VerdictCache(Path("./cache/audits"))
        >>> v = audit_pdf("doc.pdf", llm=client, cache=cache)
        >>> # next call with the same PDF returns instantly, no LLM hit.
    """

    def __init__(self, cache_dir: Path):
        self._dir = Path(cache_dir)

    @staticmethod
    def cache_key(pdf_bytes: bytes) -> str:
        return hashlib.sha256(pdf_bytes).hexdigest()[:16]

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def get(self, pdf_bytes: bytes) -> PeaVerdict | None:
        f = self._path(self.cache_key(pdf_bytes))
        if not f.exists():
            return None
        data = json.loads(f.read_text())
        data["evidence"] = [Citation(**c) for c in data.get("evidence", [])]
        return PeaVerdict(**data)

    def put(self, pdf_bytes: bytes, verdict: PeaVerdict) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path(self.cache_key(pdf_bytes)).write_text(
            json.dumps(asdict(verdict), ensure_ascii=False, indent=2)
        )

    def get_by_path(self, pdf_path: Path) -> PeaVerdict | None:
        """Convenience: load by PDF file path (for badge lookups)."""
        if not pdf_path.exists():
            return None
        return self.get(pdf_path.read_bytes())
