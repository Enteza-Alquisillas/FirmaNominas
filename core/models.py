from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PayslipPage:
    page_index: int
    worker_number: str | None
    employee_name: str | None
    dni: str | None
    month: int | None
    year: int | None
    raw_period: str | None = None
    text_preview: str = ""


@dataclass
class PayrollEmployee:
    worker_number: str
    name: str
    center: str | None = None
    concepts: dict[str, Any] = field(default_factory=dict)

    def get(self, concept_name: str):
        return self.concepts.get(concept_name, 0)


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
