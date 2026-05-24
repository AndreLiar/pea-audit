"""Versioned prompt loader.

Prompts live in `pea_audit/prompts/audit_v{N}.md` as markdown files with
two clearly marked sections:

    ## System prompt
    <text>

    ## User prompt
    <text>

Any text before the first `## System prompt` heading is treated as
changelog/notes and ignored.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_SECTION_RE = re.compile(
    r"^##\s+System prompt\s*\n(.*?)\n##\s+User prompt\s*\n(.*)$",
    re.DOTALL | re.MULTILINE,
)


@lru_cache(maxsize=8)
def load_prompt(version: str, prompts_dir: Path | None = None) -> tuple[str, str]:
    """Return `(system, user)` for the requested prompt version.

    Raises:
        FileNotFoundError: if the version file doesn't exist.
        ValueError: if the file doesn't have the expected sections.
    """
    directory = prompts_dir or PROMPTS_DIR
    path = directory / f"audit_{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    text = path.read_text()
    body = text[text.index("## System prompt"):]

    m = _SECTION_RE.match(body)
    if not m:
        raise ValueError(
            f"Expected '## System prompt' then '## User prompt' sections in {path}."
        )
    return m.group(1).strip(), m.group(2).strip()
