from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

from .models import UploadResult
from .odoo_client import OdooClient


def find_existing_attachment(odoo: OdooClient, employee_id: int, filename: str) -> dict | None:
    domain = [
        ("res_model", "=", "hr.employee"),
        ("res_id", "=", employee_id),
        ("name", "=", filename),
    ]
    records = odoo.search_read(
        "ir.attachment",
        domain=domain,
        fields=["id", "name", "res_model", "res_id"],
        limit=1,
    )
    return records[0] if records else None


def upload_employee_payslip_attachment(
    odoo: OdooClient,
    employee_id: int,
    filename: str,
    pdf_bytes: bytes,
    month: int,
    year: int,
    duplicate_policy: str = "skip",
    dry_run: bool = True,
) -> dict[str, Any]:
    existing = find_existing_attachment(odoo, employee_id, filename)

    if existing and duplicate_policy == "skip":
        return {
            "status": "DUPLICADO_OMITIDO",
            "message": f"Ya existe el adjunto {filename}",
            "attachment_id": existing["id"],
        }

    final_filename = filename
    if existing and duplicate_policy == "duplicate":
        suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = filename.replace(".pdf", f"_{suffix}.pdf")

    values = {
        "name": final_filename,
        "type": "binary",
        "datas": base64.b64encode(pdf_bytes).decode("utf-8"),
        "res_model": "hr.employee",
        "res_id": employee_id,
        "mimetype": "application/pdf",
        "description": f"Nomina {month:02d}/{year} importada automaticamente desde Streamlit",
    }

    if dry_run:
        return {
            "status": "OK_SIMULADO",
            "message": f"Se subiria {final_filename} al empleado {employee_id}",
            "attachment_id": existing["id"] if existing else None,
        }

    if existing and duplicate_policy == "replace":
        odoo.write("ir.attachment", [existing["id"]], values)
        return {
            "status": "REEMPLAZADO",
            "message": f"Adjunto reemplazado: {final_filename}",
            "attachment_id": existing["id"],
        }

    attachment_id = odoo.create("ir.attachment", values)
    return {
        "status": "CREADO",
        "message": f"Adjunto creado: {final_filename}",
        "attachment_id": attachment_id,
    }


def delete_unsigned_attachment(odoo: OdooClient, employee_id: int, signed_filename: str) -> bool:
    """Elimina el adjunto sin firmar tras subir el firmado.

    Deriva el nombre original quitando el sufijo '-firmada' del stem del archivo firmado.
    Devuelve True si se eliminó, False si no existía o hubo error.
    """
    stem = signed_filename
    if stem.lower().endswith(".pdf"):
        stem = stem[:-4]
    # Quitar sufijo -firmada (o _firmada por si acaso)
    for suffix in ("-firmada", "_firmada"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    unsigned_filename = stem + ".pdf"

    existing = find_existing_attachment(odoo, employee_id, unsigned_filename)
    if not existing:
        return False
    try:
        odoo.execute_kw("ir.attachment", "unlink", [[existing["id"]]])
        return True
    except Exception:
        return False


def upload_all_payslips(
    odoo: OdooClient,
    matches: list[Any],
    split_pdfs: dict[str, bytes],
    month: int,
    year: int,
    duplicate_policy: str = "skip",
    dry_run: bool = True,
) -> list[UploadResult]:
    results: list[UploadResult] = []

    for match in matches:
        if match.match_status != "MATCH_OK" or match.employee_id_odoo is None:
            results.append(
                UploadResult(
                    filename=match.filename,
                    worker_number=match.worker_number,
                    dni=match.dni,
                    employee_id_odoo=None,
                    employee_name_odoo=match.employee_name_odoo,
                    status=match.match_status,
                    message=f"No se sube: {match.match_status} - {match.observations}",
                )
            )
            continue

        pdf_bytes = split_pdfs.get(match.filename)
        if pdf_bytes is None:
            results.append(
                UploadResult(
                    filename=match.filename,
                    worker_number=match.worker_number,
                    dni=match.dni,
                    employee_id_odoo=match.employee_id_odoo,
                    employee_name_odoo=match.employee_name_odoo,
                    status="ERROR",
                    message=f"PDF no encontrado: {match.filename}",
                )
            )
            continue

        try:
            upload_result = upload_employee_payslip_attachment(
                odoo=odoo,
                employee_id=match.employee_id_odoo,
                filename=match.filename,
                pdf_bytes=pdf_bytes,
                month=month,
                year=year,
                duplicate_policy=duplicate_policy,
                dry_run=dry_run,
            )

            results.append(
                UploadResult(
                    filename=match.filename,
                    worker_number=match.worker_number,
                    dni=match.dni,
                    employee_id_odoo=match.employee_id_odoo,
                    employee_name_odoo=match.employee_name_odoo,
                    status=upload_result["status"],
                    message=upload_result["message"],
                    attachment_id=upload_result.get("attachment_id"),
                )
            )
        except Exception as e:
            results.append(
                UploadResult(
                    filename=match.filename,
                    worker_number=match.worker_number,
                    dni=match.dni,
                    employee_id_odoo=match.employee_id_odoo,
                    employee_name_odoo=match.employee_name_odoo,
                    status="ERROR",
                    message=f"Error al subir: {e}",
                )
            )

    return results
