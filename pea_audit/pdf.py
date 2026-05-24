"""PDF utilities — rendering pages to images for vision LLMs."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium


def pdf_to_images(pdf_path: str | Path, dpi: int = 144) -> list[bytes]:
    """Render each page of `pdf_path` to PNG bytes.

    `dpi=144` is a good cost/quality tradeoff for KID-style documents
    (clear OCR without sending huge payloads to the LLM).
    """
    pdf = pdfium.PdfDocument(str(pdf_path))
    scale = dpi / 72
    images: list[bytes] = []
    for page in pdf:
        pil = page.render(scale=scale).to_pil()
        buf = BytesIO()
        pil.save(buf, format="PNG")
        images.append(buf.getvalue())
    return images
