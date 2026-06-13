from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .payroll_excel import PayrollEmployee  # re-export: canonical definition lives there
from .payroll_pdf import PayslipPage  # re-export: canonical definition lives there

__all__ = ["PayrollEmployee", "PayslipPage", "SplitPdfArtifact", "OdooEmployeeMatch", "UploadResult"]


@dataclass
class SplitPdfArtifact:
    worker_number: str
    dni: str
    employee_name: str
    month: int
    year: int
    filename: str
    pdf_bytes: bytes


@dataclass
class OdooEmployeeMatch:
    worker_number: str
    dni: str
    employee_name_pdf: str
    employee_name_excel: str
    filename: str
    employee_id_odoo: int | None
    employee_name_odoo: str | None
    match_method: str
    match_status: str
    observations: str
    department: str | None = None


@dataclass
class UploadResult:
    filename: str
    worker_number: str
    dni: str
    employee_id_odoo: int | None
    employee_name_odoo: str | None
    status: str
    message: str
    attachment_id: int | None = None
