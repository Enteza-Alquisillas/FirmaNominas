from __future__ import annotations

from typing import Any

from .models import OdooEmployeeMatch
from .odoo_client import OdooClient
from .utils import normalize_dni, normalize_name, normalize_worker_number


CANDIDATE_WORKER_FIELDS = [
    "barcode",
    "employee_number",
    "registration_number",
    "x_num_trabajador",
    "x_studio_num_trabajador",
]


def get_available_worker_fields(odoo: OdooClient) -> list[str]:
    try:
        fields_info = odoo.get_employee_fields()
    except Exception:
        return []

    available = []
    for field_name in CANDIDATE_WORKER_FIELDS:
        if field_name in fields_info:
            available.append(field_name)
    return available


def match_employees(
    odoo: OdooClient,
    pdf_pages: list[Any],
    excel_employees: list[Any],
    dni_field: str,
    worker_field: str | None,
    name_field: str = "name",
) -> list[OdooEmployeeMatch]:
    base_fields = ["id", name_field, dni_field, "active", "department_id"]
    if worker_field:
        all_employees = odoo.search_employees(
            [],
            fields=base_fields + [worker_field],
            limit=5000,
        )
    else:
        all_employees = odoo.search_employees([], fields=base_fields, limit=5000)

    employee_by_dni: dict[str, list[dict]] = {}
    employee_by_worker: dict[str, list[dict]] = {}
    employee_by_name: dict[str, list[dict]] = {}

    for emp in all_employees:
        if dni_field and emp.get(dni_field):
            norm = normalize_dni(str(emp[dni_field]))
            employee_by_dni.setdefault(norm, []).append(emp)

        if worker_field and emp.get(worker_field):
            norm = normalize_worker_number(str(emp[worker_field]))
            employee_by_worker.setdefault(norm, []).append(emp)

        norm_name = normalize_name(str(emp.get(name_field, "")))
        employee_by_name.setdefault(norm_name, []).append(emp)

    pdf_by_worker = {p.worker_number: p for p in pdf_pages if p.worker_number}
    excel_by_worker = {e.worker_number: e for e in excel_employees}

    all_worker_numbers = sorted(
        set(list(pdf_by_worker.keys()) + list(excel_by_worker.keys())),
        key=lambda x: int(x) if x.isdigit() else 0,
    )

    # Build department lookup: employee_id → department name
    dept_by_id: dict[int, str] = {}
    for emp in all_employees:
        dept_raw = emp.get("department_id")
        dept_name = dept_raw[1] if isinstance(dept_raw, (list, tuple)) and len(dept_raw) >= 2 else ""
        dept_by_id[int(emp["id"])] = dept_name

    results: list[OdooEmployeeMatch] = []

    for wn in all_worker_numbers:
        pdf = pdf_by_worker.get(wn)
        excel = excel_by_worker.get(wn)

        dni = pdf.dni if pdf else ""
        name_pdf = pdf.employee_name if pdf else ""
        name_excel = excel.name if excel else ""
        filename = f"{normalize_dni(dni) or f'trabajador_{wn}'}.pdf"

        match = _find_match(
            dni=dni,
            worker_number=wn,
            name_pdf=name_pdf,
            name_excel=name_excel,
            employee_by_dni=employee_by_dni,
            employee_by_worker=employee_by_worker,
            employee_by_name=employee_by_name,
            dni_field=dni_field,
            worker_field=worker_field,
            name_field=name_field,
        )

        if match.employee_id_odoo and match.employee_id_odoo in dept_by_id:
            match.department = dept_by_id[match.employee_id_odoo]

        results.append(match)

    return results


def _fallback_filename(dni: str, worker_number: str) -> str:
    return f"{normalize_dni(dni) if dni else f'trabajador_{worker_number}'}.pdf"


def _make_match(
    worker_number: str, dni: str, name_pdf: str, name_excel: str,
    filename: str, emp: dict, name_field: str, method: str, observations: str = "",
) -> OdooEmployeeMatch:
    return OdooEmployeeMatch(
        worker_number=worker_number, dni=dni,
        employee_name_pdf=name_pdf, employee_name_excel=name_excel,
        filename=filename, employee_id_odoo=emp["id"],
        employee_name_odoo=emp.get(name_field, ""),
        match_method=method, match_status="MATCH_OK", observations=observations,
    )


def _make_ambiguous(
    worker_number: str, dni: str, name_pdf: str, name_excel: str,
    filename: str, method: str, observations: str,
) -> OdooEmployeeMatch:
    return OdooEmployeeMatch(
        worker_number=worker_number, dni=dni,
        employee_name_pdf=name_pdf, employee_name_excel=name_excel,
        filename=filename, employee_id_odoo=None, employee_name_odoo=None,
        match_method=method, match_status="AMBIGUO", observations=observations,
    )


def _find_match(
    dni: str,
    worker_number: str,
    name_pdf: str,
    name_excel: str,
    employee_by_dni: dict[str, list[dict]],
    employee_by_worker: dict[str, list[dict]],
    employee_by_name: dict[str, list[dict]],
    dni_field: str,
    worker_field: str | None,
    name_field: str,
) -> OdooEmployeeMatch:
    fallback_fn = _fallback_filename(dni, worker_number)

    if dni:
        norm_dni = normalize_dni(dni)
        candidates = employee_by_dni.get(norm_dni, [])
        if len(candidates) == 1:
            return _make_match(worker_number, dni, name_pdf, name_excel, f"{norm_dni}.pdf", candidates[0], name_field, "dni")
        if len(candidates) > 1:
            return _make_ambiguous(worker_number, dni, name_pdf, name_excel, f"{norm_dni}.pdf", "dni", f"{len(candidates)} empleados con mismo DNI")

    if worker_field:
        norm_worker = normalize_worker_number(worker_number)
        candidates = employee_by_worker.get(norm_worker, [])
        if len(candidates) == 1:
            return _make_match(worker_number, dni, name_pdf, name_excel, fallback_fn, candidates[0], name_field, "worker_number")
        if len(candidates) > 1:
            return _make_ambiguous(worker_number, dni, name_pdf, name_excel, fallback_fn, "worker_number", f"{len(candidates)} empleados con mismo numero de trabajador")

    name_to_match = name_excel or name_pdf
    if name_to_match:
        norm_name = normalize_name(name_to_match)
        candidates = employee_by_name.get(norm_name, [])
        if len(candidates) == 1:
            return _make_match(worker_number, dni, name_pdf, name_excel, fallback_fn, candidates[0], name_field, "name", "Coincidencia por nombre (revisar)")
        if len(candidates) > 1:
            return _make_ambiguous(worker_number, dni, name_pdf, name_excel, fallback_fn, "name", f"{len(candidates)} empleados con mismo nombre")

    return OdooEmployeeMatch(
        worker_number=worker_number, dni=dni,
        employee_name_pdf=name_pdf, employee_name_excel=name_excel,
        filename=fallback_fn, employee_id_odoo=None, employee_name_odoo=None,
        match_method="", match_status="NO_ENCONTRADO",
        observations="No se encontro coincidencia en Odoo",
    )


def apply_manual_mapping(
    auto_matches: list[OdooEmployeeMatch],
    manual_mapping: list[dict[str, Any]],
    odoo: OdooClient,
) -> list[OdooEmployeeMatch]:
    manual_by_worker: dict[str, dict[str, Any]] = {}
    for row in manual_mapping:
        wn = str(row.get("n_trabajador", "")).strip()
        if wn:
            manual_by_worker[wn] = row

    results: list[OdooEmployeeMatch] = []
    for match in auto_matches:
        manual = manual_by_worker.get(match.worker_number)
        if manual and manual.get("employee_id_odoo"):
            try:
                emp_id = int(manual["employee_id_odoo"])
                emp_data = odoo.read("hr.employee", [emp_id], ["id", "name", "active"])
                if emp_data:
                    emp = emp_data[0]
                    obs = manual.get("observaciones", "")
                    if not emp.get("active", True):
                        obs += " [EMPLEADO ARCHIVADO]"
                    results.append(
                        OdooEmployeeMatch(
                            worker_number=match.worker_number,
                            dni=match.dni,
                            employee_name_pdf=match.employee_name_pdf,
                            employee_name_excel=match.employee_name_excel,
                            filename=match.filename,
                            employee_id_odoo=emp_id,
                            employee_name_odoo=emp.get("name", ""),
                            match_method="manual",
                            match_status="MATCH_OK",
                            observations=obs,
                        )
                    )
                else:
                    results.append(
                        OdooEmployeeMatch(
                            worker_number=match.worker_number,
                            dni=match.dni,
                            employee_name_pdf=match.employee_name_pdf,
                            employee_name_excel=match.employee_name_excel,
                            filename=match.filename,
                            employee_id_odoo=None,
                            employee_name_odoo=None,
                            match_method="manual",
                            match_status="NO_ENCONTRADO",
                            observations=f"ID {emp_id} no existe en Odoo",
                        )
                    )
            except (ValueError, TypeError):
                results.append(match)
        else:
            results.append(match)

    return results
