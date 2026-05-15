from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def month_to_number(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 12 else None
    text = str(value).strip().lower()
    if text.isdigit():
        number = int(text)
        return number if 1 <= number <= 12 else None
    text = strip_accents(text)
    return SPANISH_MONTHS.get(text)


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def slugify_filename(value: str, max_len: int = 120) -> str:
    value = strip_accents(str(value or ""))
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return value[:max_len] or "sin_nombre"


def parse_decimal(value: Any) -> Decimal:
    """Parse Excel/PDF Spanish-style numbers into Decimal with 2 decimal precision."""
    if value is None or value == "":
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return money(value)
    if isinstance(value, (int, float)):
        return money(Decimal(str(value)))
    text = str(value).strip()
    text = text.replace("€", "").replace(" ", "")
    # Spanish format: 1.234,56. English/plain: 1234.56.
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return money(Decimal(text))
    except InvalidOperation:
        return Decimal("0.00")


def money(value: Decimal | float | int | str) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decimal_to_float(value: Decimal) -> float:
    return float(money(value))


def is_zero(value: Decimal) -> bool:
    return money(value) == Decimal("0.00")


def safe_account_465(worker_number: str | int) -> str:
    """Default account convention observed in the supplied Odoo screenshot: 46510 + 3-digit worker number."""
    try:
        return f"46510{int(worker_number):03d}"
    except Exception:
        return "46510000"


def normalize_concept(value: str) -> str:
    txt = strip_accents(str(value or "")).upper()
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def normalize_dni(value: str) -> str:
    if not value:
        return ""
    text = str(value).strip().upper()
    text = text.replace(" ", "").replace("-", "").replace(".", "")
    return text


def normalize_worker_number(value: str) -> str:
    if not value:
        return ""
    text = str(value).strip()
    text = text.replace(" ", "").replace("-", "")
    try:
        return str(int(text))
    except (ValueError, TypeError):
        return text


def normalize_name(value: str) -> str:
    if not value:
        return ""
    text = strip_accents(str(value)).upper()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def mask_dni(dni: str) -> str:
    if not dni or len(dni) < 4:
        return dni
    return dni[:4] + "*" * (len(dni) - 5) + dni[-1]
