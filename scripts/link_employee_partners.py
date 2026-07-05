"""Vincula empleados (hr.employee) sin contacto particular (address_home_id) con
un res.partner. En modo simulacion (por defecto) solo genera un informe; con
--apply ejecuta los cambios en Odoo.

Uso:
    python scripts/link_employee_partners.py            # dry-run (informe)
    python scripts/link_employee_partners.py --apply    # aplica cambios reales
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.odoo_client import OdooClient  # noqa: E402


def load_env(env_path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def clean_name(name: str) -> str:
    """Elimina anotaciones entre parentesis y normaliza espacios."""
    name = re.sub(r"\(.*?\)", "", name)
    return " ".join(name.split())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ejecuta los cambios en Odoo. Sin esta opcion solo se muestra el informe.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    env = load_env(root / ".env.local")
    for key in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_PASSWORD"):
        env.setdefault(key, os.environ.get(key, ""))

    missing = [k for k in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_PASSWORD") if not env.get(k)]
    if missing:
        raise SystemExit(f"Faltan variables de entorno: {', '.join(missing)}")

    odoo = OdooClient(env["ODOO_URL"], env["ODOO_DB"], env["ODOO_USER"], env["ODOO_PASSWORD"])
    odoo.authenticate()

    employees = odoo.search_read(
        "hr.employee",
        [("active", "=", True)],
        ["id", "name", "address_home_id", "identification_id"],
        limit=1000,
    )
    without_partner = [e for e in employees if not e.get("address_home_id")]

    to_link: list[tuple[dict, dict]] = []  # (empleado, partner existente)
    to_create: list[dict] = []  # empleados sin partner -> crear nuevo

    for emp in without_partner:
        cname = clean_name(emp["name"])
        partner_rows = odoo.search_read(
            "res.partner",
            [("name", "=ilike", cname), ("company_type", "=", "person")],
            ["id", "name"],
            limit=1,
        )
        if partner_rows:
            to_link.append((emp, partner_rows[0]))
        else:
            to_create.append(emp)

    total = len(employees)
    with_partner = total - len(without_partner)

    print("=" * 70)
    print("INFORME DE VINCULACION EMPLEADO <-> CONTACTO (res.partner)")
    print("=" * 70)
    print(f"Empleados activos totales:        {total}")
    print(f"Ya con address_home_id:           {with_partner}")
    print(f"Sin address_home_id:              {len(without_partner)}")
    print(f"  -> con partner existente (link): {len(to_link)}")
    print(f"  -> sin partner (crear nuevo):    {len(to_create)}")
    print()

    if to_link:
        print("-- Empleados que se vincularian a un contacto YA EXISTENTE --")
        for emp, partner in to_link:
            print(f"  [{emp['id']:>5}] {emp['name']!r}  ->  res.partner [{partner['id']}] {partner['name']!r}")
        print()

    if to_create:
        print("-- Empleados para los que se CREARIA un contacto nuevo --")
        for emp in to_create:
            cname = clean_name(emp["name"])
            dni = emp.get("identification_id") or ""
            extra = f" (DNI/NIE: {dni})" if dni else ""
            print(f"  [{emp['id']:>5}] {emp['name']!r}  ->  nuevo res.partner {cname!r}{extra}")
        print()

    if not args.apply:
        print("Modo simulacion: no se ha modificado nada en Odoo.")
        print("Ejecuta con --apply para aplicar estos cambios.")
        return

    print("Aplicando cambios en Odoo...")
    linked_count = 0
    created_count = 0

    for emp, partner in to_link:
        odoo.write("hr.employee", [emp["id"]], {"address_home_id": partner["id"]})
        linked_count += 1

    for emp in to_create:
        cname = clean_name(emp["name"])
        dni = emp.get("identification_id") or False
        partner_values = {
            "name": cname,
            "company_type": "person",
            "is_company": False,
            "type": "private",
        }
        if dni:
            partner_values["vat"] = dni
        partner_id = odoo.create("res.partner", partner_values)
        odoo.write("hr.employee", [emp["id"]], {"address_home_id": partner_id})
        created_count += 1

    print(f"Vinculados a contacto existente: {linked_count}")
    print(f"Contactos nuevos creados y vinculados: {created_count}")


if __name__ == "__main__":
    main()
