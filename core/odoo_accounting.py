from __future__ import annotations

from decimal import Decimal
from typing import Any

from .odoo_client import OdooClient
from .utils import is_zero, money


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return money(value)
    if value is None or value == "":
        return Decimal("0.00")
    return money(Decimal(str(value)))


def _is_total_center(center: str | None) -> bool:
    return center is not None and "TOTAL" in center.upper()


def build_payroll_move_lines(
    employees: list[Any],
    employee_rows: list[dict[str, Any]],
    month: int,
    year: int,
    aggregate_ss: bool = True,
    center_filter: str | None = None,
) -> list[dict[str, Any]]:
    mapping = {str(row.get("n_trabajador")): row for row in employee_rows}
    lines: list[dict[str, Any]] = []
    total_tc1 = Decimal("0.00")
    first_included_map: dict[str, Any] = {}

    for emp in employees:
        if _is_total_center(emp.center):
            continue
        if center_filter is not None and (emp.center or "") != center_filter:
            continue

        map_row = mapping.get(str(emp.worker_number), {})
        include = str(map_row.get("incluir", "SI")).upper()
        if include not in ("SI", "S", "YES", "TRUE", "1"):
            continue

        if not first_included_map:
            first_included_map = map_row

        gross = _to_decimal(emp.concepts.get("total_bruto", 0))
        net = _to_decimal(emp.concepts.get("total_neto", 0))
        irpf = _to_decimal(emp.concepts.get("descuento_irpf", 0))
        ss_company = _to_decimal(emp.concepts.get("ss_empresa", 0))
        tc1 = _to_decimal(emp.concepts.get("coste_tc1", 0))
        embargo = _to_decimal(emp.concepts.get("embargo_juzgado", 0))
        especie = _to_decimal(emp.concepts.get("valores_especie_autonomo", 0))
        indemniz_inss = _to_decimal(emp.concepts.get("total_indemniz_inss", 0))

        total_tc1 += tc1

        def append_line(account_key: str, label: str, debit: Decimal, credit: Decimal, _map_row=map_row):
            account_code = str(_map_row.get(account_key) or "").strip()
            if not account_code:
                return
            lines.append(
                {
                    "worker_number": str(emp.worker_number),
                    "employee_name": emp.name,
                    "account_code": account_code,
                    "partner_name": str(_map_row.get("partner_odoo") or "").strip(),
                    "name": label,
                    "debit": float(money(debit)),
                    "credit": float(money(credit)),
                }
            )

        label_base = f"NOMINA {month:02d}/{year} {emp.worker_number} {emp.name}"
        if not is_zero(gross):
            append_line("cuenta_sueldos", label_base, gross, Decimal("0.00"))
        if not is_zero(ss_company):
            append_line(
                "cuenta_ss_empresa",
                f"SEGURIDAD SOCIAL EMPRESA {emp.worker_number} {emp.name}",
                ss_company,
                Decimal("0.00"),
            )
        if not is_zero(net):
            append_line(
                "cuenta_remuneraciones",
                f"LIQUIDO NOMINA {emp.worker_number} {emp.name}",
                Decimal("0.00"),
                net,
            )
        if not is_zero(irpf):
            append_line(
                "cuenta_irpf",
                f"IRPF NOMINA {emp.worker_number} {emp.name}",
                Decimal("0.00"),
                irpf,
            )
        if not is_zero(embargo):
            append_line(
                "cuenta_embargo",
                f"EMBARGO JUZGADO {emp.worker_number} {emp.name}",
                Decimal("0.00"),
                embargo,
            )
        if not is_zero(especie):
            append_line(
                "cuenta_especie_autonomo",
                f"VALORES EN ESPECIE/AUTONOMO {emp.worker_number} {emp.name}",
                Decimal("0.00"),
                especie,
            )
        if not is_zero(indemniz_inss):
            append_line(
                "cuenta_indemniz_inss",
                f"PRESTACIONES/INDEMNIZACIONES INSS {emp.worker_number} {emp.name}",
                Decimal("0.00"),
                indemniz_inss,
            )

        if not aggregate_ss and not is_zero(tc1):
            append_line(
                "cuenta_ss_acreedora",
                f"TC1 {emp.worker_number} {emp.name}",
                Decimal("0.00"),
                tc1,
            )

    if aggregate_ss and not is_zero(total_tc1):
        map_for_ss = first_included_map or (next(iter(mapping.values()), {}) if mapping else {})
        account_code = str(map_for_ss.get("cuenta_ss_acreedora") or "").strip()
        if account_code:
            lines.insert(
                0,
                {
                    "worker_number": "",
                    "employee_name": "",
                    "account_code": account_code,
                    "partner_name": "",
                    "name": f"TC1 NOMINA {month:02d}/{year}",
                    "debit": 0.0,
                    "credit": float(money(total_tc1)),
                },
            )

    return lines


def build_payroll_moves_by_center(
    employees: list[Any],
    employee_rows: list[dict[str, Any]],
    month: int,
    year: int,
    aggregate_ss: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    centers: list[str] = []
    for emp in employees:
        c = emp.center or ""
        if not _is_total_center(c) and c not in centers:
            centers.append(c)

    result: dict[str, list[dict[str, Any]]] = {}
    for center in centers:
        lines = build_payroll_move_lines(
            employees, employee_rows, month, year, aggregate_ss, center_filter=center
        )
        if lines:
            result[center] = lines
    return result


def summarize_move_lines(lines: list[dict[str, Any]]) -> dict[str, Any]:
    total_debit = sum(float(line.get("debit", 0) or 0) for line in lines)
    total_credit = sum(float(line.get("credit", 0) or 0) for line in lines)
    balance = round(total_debit - total_credit, 2)
    return {
        "line_count": len(lines),
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "balance": balance,
        "is_balanced": abs(balance) < 0.01,
    }


def _resolve_journal_id(odoo: OdooClient, journal: str) -> int:
    journal = str(journal or "").strip()
    if not journal:
        raise ValueError("Diario vacio para crear el asiento.")

    if journal.isdigit():
        ids = odoo.search("account.journal", [("id", "=", int(journal))], limit=1)
        if ids:
            return ids[0]

    by_code = odoo.search("account.journal", [("code", "=", journal)], limit=1)
    if by_code:
        return by_code[0]

    by_name = odoo.search("account.journal", [("name", "=", journal)], limit=1)
    if by_name:
        return by_name[0]

    raise ValueError(f"No se encontro diario en Odoo para '{journal}'.")


def _prefix_search(odoo: OdooClient, prefix: str, cache: dict[str, int | None]) -> int | None:
    if prefix in cache:
        return cache[prefix]
    rows = odoo.search_read(
        "account.account",
        [("code", "like", prefix + "%")],
        ["id", "code"],
        limit=1,
    )
    found = int(rows[0]["id"]) if rows else None
    cache[prefix] = found
    return found


def _resolve_account_ids(odoo: OdooClient, codes: list[str]) -> dict[str, int]:
    uniq_codes = sorted({str(code).strip() for code in codes if str(code).strip()})
    result: dict[str, int] = {}
    prefix_cache: dict[str, int | None] = {}

    for code in uniq_codes:
        # 1. Búsqueda exacta
        rows = odoo.search_read("account.account", [("code", "=", code)], ["id", "code"], limit=1)
        if rows:
            result[code] = int(rows[0]["id"])
            continue

        # 2. Para cuentas 4651XXXX: buscar por prefijo 4650 (cuenta genérica de remuneraciones)
        if code.startswith("4651"):
            found = _prefix_search(odoo, "4650", prefix_cache)
            if found:
                result[code] = found
                continue

        # 3. Búsqueda por prefijo progresivo (quitar dígito a dígito desde la derecha)
        for trim in range(1, len(code)):
            prefix = code[:-trim]
            if len(prefix) < 3:
                break
            found = _prefix_search(odoo, prefix, prefix_cache)
            if found:
                result[code] = found
                break

    return result


def _resolve_partner_ids(odoo: OdooClient, names: list[str]) -> dict[str, int]:
    uniq_names = sorted({str(name).strip() for name in names if str(name).strip()})
    result: dict[str, int] = {}
    for name in uniq_names:
        rows = odoo.search_read("res.partner", [("name", "=", name)], ["id", "name"], limit=1)
        if rows:
            result[name] = int(rows[0]["id"])
    return result


def create_payroll_move_in_odoo(
    odoo: OdooClient,
    lines: list[dict[str, Any]],
    move_date: str,
    journal: str,
    reference: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    summary = summarize_move_lines(lines)
    if not lines:
        return {"status": "ERROR", "message": "No hay lineas para crear el asiento.", "summary": summary}

    journal_id = _resolve_journal_id(odoo, journal)
    account_ids = _resolve_account_ids(odoo, [line.get("account_code", "") for line in lines])
    partner_ids = _resolve_partner_ids(odoo, [line.get("partner_name", "") for line in lines])

    missing_accounts = sorted(
        {str(line.get("account_code", "")).strip() for line in lines if str(line.get("account_code", "")).strip() and str(line.get("account_code", "")).strip() not in account_ids}
    )

    if missing_accounts:
        return {
            "status": "ERROR",
            "message": "Cuentas no encontradas en Odoo: " + ", ".join(missing_accounts),
            "summary": summary,
        }

    move_lines: list[tuple[int, int, dict[str, Any]]] = []
    for line in lines:
        account_code = str(line.get("account_code", "")).strip()
        partner_name = str(line.get("partner_name", "")).strip()
        values: dict[str, Any] = {
            "name": str(line.get("name", "")).strip() or "Nomina",
            "account_id": account_ids[account_code],
            "debit": float(line.get("debit", 0) or 0),
            "credit": float(line.get("credit", 0) or 0),
        }
        if partner_name and partner_name in partner_ids:
            values["partner_id"] = partner_ids[partner_name]
        move_lines.append((0, 0, values))

    payload = {
        "move_type": "entry",
        "date": move_date,
        "journal_id": journal_id,
        "ref": reference,
        "line_ids": move_lines,
    }

    if dry_run:
        return {
            "status": "OK_SIMULADO",
            "message": "Simulacion completada. El asiento se podria crear en Odoo.",
            "summary": summary,
            "journal_id": journal_id,
            "line_count": len(move_lines),
        }

    move_id = odoo.create("account.move", payload)
    return {
        "status": "CREADO",
        "message": f"Asiento creado en Odoo con ID {move_id}.",
        "summary": summary,
        "move_id": move_id,
    }
