from __future__ import annotations

from pathlib import Path

import fitz


def find_anchor_below_recibi(
    doc: fitz.Document,
    page_index: int = 0,
    keywords: tuple[str, ...] = ("Recibí", "Recibi", "RECIBI", "RECIBÍ"),
) -> tuple[int, float, float] | None:
    if page_index < 0 or page_index >= len(doc):
        page_index = 0
    page = doc[page_index]

    for keyword in keywords:
        matches = page.search_for(keyword)
        if matches:
            hit = matches[0]
            return page_index, hit.x0, hit.y1 + 6
    return None


def insert_signature_into_pdf(
    pdf_input_path: str | Path,
    signature_png_bytes: bytes,
    pdf_output_path: str | Path,
    page_index: int = 0,
    x: float = 350,
    y: float = 690,
    width: float = 180,
    height: float = 60,
) -> None:
    doc = fitz.open(str(pdf_input_path))
    try:
        anchor = find_anchor_below_recibi(doc, page_index=page_index)
        if anchor is not None:
            page_index, x, y = anchor

        if page_index < 0 or page_index >= len(doc):
            page_index = 0
        page = doc[page_index]
        rect = fitz.Rect(x, y, x + width, y + height)
        page.insert_image(rect, stream=signature_png_bytes)
        doc.save(str(pdf_output_path))
    finally:
        doc.close()
