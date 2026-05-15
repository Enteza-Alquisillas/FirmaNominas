from __future__ import annotations

import re
from decimal import Decimal
from typing import Any


DNI_PATTERN = re.compile(r"^[XYZ]?\d{7,8}[A-Z0-9]$", re.IGNORECASE)


def validate_dni(dni: str) -> bool:
    if not dni:
        return False
    return bool(DNI_PATTERN.match(dni.strip()))


def validate_employee_id(employee_id: int | None) -> bool:
    return employee_id is not None and employee_id > 0


def validate_accounting_entry(lines: list[dict[str, Any]]) -> dict[str, Any]:
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    warnings: list[str] = []

    for line in lines:
        debit = Decimal(str(line.get("debit", 0) or 0))
        credit = Decimal(str(line.get("credit", 0) or 0))
        total_debit += debit
        total_credit += credit

        account = line.get("account_id", "")
        if not account:
            warnings.append(f"Linea sin cuenta: {line.get('name', 'N/A')}")

    balance = total_debit - total_credit
    is_balanced = abs(balance) < Decimal("0.01")

    return {
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "balance": float(balance),
        "is_balanced": is_balanced,
        "line_count": len(lines),
        "warnings": warnings,
    }


def validate_mapping_row(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    worker = row.get("n_trabajador", "")
    if not worker:
        errors.append("Falta numero de trabajador")

    incluir = str(row.get("incluir", "SI")).upper()
    if incluir not in ("SI", "NO", "S", "N", "YES", "NO"):
        errors.append(f"Valor de 'incluir' invalido: {incluir}")

    return errors
