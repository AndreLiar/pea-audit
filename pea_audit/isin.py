"""ISIN extraction + Luhn check-digit validation.

Used to deterministically pull ISINs from PDF text layers, overriding
fuzzy vision-LLM reads of the same field.
"""

from __future__ import annotations

import re
from pathlib import Path

import pypdfium2 as pdfium

ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")


def isin_check_digit_valid(isin: str) -> bool:
    """Verify the ISIN Luhn check digit (letters → 2-digit pairs, then Luhn)."""
    if not ISIN_RE.fullmatch(isin):
        return False
    digits = "".join(
        str(ord(c) - 55) if c.isalpha() else c for c in isin
    )  # A→10, B→11, ..., Z→35
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n >= 10:
                n -= 9
        total += n
    return total % 10 == 0


def extract_isins(pdf_path: str | Path) -> list[str]:
    """Extract valid ISINs from a PDF's text layer, in document order.

    Only returns ISINs with a valid check digit. Deduplicates while
    preserving the first-seen order — the first ISIN in a KID is usually
    the fund being described.

    Returns [] if the PDF has no text layer (e.g. scanned image only).
    """
    pdf = pdfium.PdfDocument(str(pdf_path))
    seen: dict[str, None] = {}
    for page in pdf:
        text = page.get_textpage().get_text_range()
        for m in ISIN_RE.finditer(text):
            isin = m.group()
            if isin not in seen and isin_check_digit_valid(isin):
                seen[isin] = None
    return list(seen.keys())
