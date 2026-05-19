from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF
from pypdf import PdfReader, PdfWriter

from .utils import month_to_number, slugify_filename


@dataclass
class PayslipPage:
    page_index: int
    worker_number: str | None
    employee_name: str | None
    dni: str | None
    month: int | None
    year: int | None
    raw_period: str | None
    text_preview: str


DNI_AFTER_RE = re.compile(r"NIF:\s*([XYZ]?\d{7,8}[A-Z0-9])", re.IGNORECASE)
DNI_BEFORE_RE = re.compile(r"([XYZ]?\d{7,8}[A-Z])\s*\n\s*NIF:", re.IGNORECASE)
PERIOD_RE = re.compile(
    r"Periodo\s+de\s+liquidaci[oó]n\s+\d{1,2}/([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s+a\s+\d{1,2}/([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)


def extract_pdf_pages(pdf_path: str | Path) -> list[PayslipPage]:
    doc = fitz.open(str(pdf_path))
    pages: list[PayslipPage] = []
    for idx, page in enumerate(doc):
        text = page.get_text("text") or ""
        pages.append(parse_page_text(text, idx))
    doc.close()
    return pages


def parse_page_text(text: str, page_index: int) -> PayslipPage:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    worker_number: str | None = None
    employee_name: str | None = None
    for i, line in enumerate(lines[:20]):
        if re.fullmatch(r"\d{1,6}", line):
            worker_number = line
            if i + 1 < len(lines):
                employee_name = lines[i + 1]
            break

    dni_match = DNI_AFTER_RE.search(text) or DNI_BEFORE_RE.search(text)
    dni = dni_match.group(1).upper() if dni_match else None

    period_match = PERIOD_RE.search(text)
    month = year = None
    raw_period = None
    if period_match:
        raw_period = period_match.group(0)
        month = month_to_number(period_match.group(2)) or month_to_number(period_match.group(1))
        year = int(period_match.group(3))

    return PayslipPage(
        page_index=page_index,
        worker_number=worker_number,
        employee_name=employee_name,
        dni=dni,
        month=month,
        year=year,
        raw_period=raw_period,
        text_preview="\n".join(lines[:12]),
    )


def split_pdf_to_zip(
    pdf_path: str | Path,
    pages: Iterable[PayslipPage],
    default_month: int,
    default_year: int,
) -> bytes:
    reader = PdfReader(str(pdf_path))
    output = io.BytesIO()
    used_names: set[str] = set()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for page_info in pages:
            writer = PdfWriter()
            writer.add_page(reader.pages[page_info.page_index])
            page_buf = io.BytesIO()
            writer.write(page_buf)
            month = page_info.month or default_month
            year = page_info.year or default_year
            base = page_info.dni or f"trabajador_{page_info.worker_number or page_info.page_index + 1:>03}"
            nombre_slug = slugify_filename(page_info.employee_name or "")
            if nombre_slug and nombre_slug != "sin_nombre":
                filename = f"{slugify_filename(base)}-{nombre_slug}-{month:02d}-{year:04d}.pdf"
            else:
                filename = f"{slugify_filename(base)}-{month:02d}-{year:04d}.pdf"
            filename = unique_filename(filename, used_names)
            used_names.add(filename)
            zf.writestr(filename, page_buf.getvalue())

    return output.getvalue()


def unique_filename(filename: str, used_names: set[str]) -> str:
    if filename not in used_names:
        return filename
    stem = filename[:-4] if filename.lower().endswith(".pdf") else filename
    ext = ".pdf" if filename.lower().endswith(".pdf") else ""
    counter = 2
    while True:
        candidate = f"{stem}_{counter}{ext}"
        if candidate not in used_names:
            return candidate
        counter += 1
