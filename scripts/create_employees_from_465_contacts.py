"""Crea los registros hr.employee que faltan en Odoo a partir de los contactos
"465{codigo} {NOMBRE}" (res.partner) ya existentes, y los deja vinculados
desde el principio via 'address_home_id'.

Contexto: en el entorno de produccion el modulo de Empleados esta practicamente
vacio (solo existe 'Administrator'), pero los contactos "465..." con el DNI
real (campo 'vat') ya estan cargados. Este script crea un hr.employee por cada
contacto sin empleado vinculado todavia.

Reglas:
  - name: nombre del contacto sin el prefijo de codigo "465..." y sin las
    anotaciones entre parentesis (ej. "(Jerez) (chofer)").
  - active: False si el nombre del contacto contiene la palabra "inactivo"
    (en cualquier capitalizacion), True en caso contrario.
  - identification_id: el DNI del contacto (vat), si lo tiene.
  - address_home_id: el contacto de origen.

Uso:
    python scripts/create_employees_from_465_contacts.py            # dry-run
    python scripts/create_employees_from_465_contacts.py --apply    # aplica
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.odoo_client import OdooClient  # noqa: E402

CODE_PREFIX_RE = re.compile(r"^465[\dx]+", re.IGNORECASE)
SEPARATOR_RE = re.compile(r"^[\s\-]*(?:Jer[\s\-]*)?[\s\-]*", re.IGNORECASE)
PARENS_RE = re.compile(r"\(.*?\)")
INACTIVO_RE = re.compile(r"inactivo", re.IGNORECASE)


def clean_name(name: str) -> str:
    name = PARENS_RE.sub("", name)
    return " ".join(name.split())


def strip_code_prefix(name: str) -> str:
    m = CODE_PREFIX_RE.match(name)
    if not m:
        return name
    rest = name[m.end():]
    return SEPARATOR_RE.sub("", rest)


def employee_name_from_partner(partner_name: str) -> str:
    return clean_name(strip_code_prefix(partner_name))


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Ejecuta los cambios en Odoo.")
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

    print(f"Conectado a: {env['ODOO_URL']}  (db: {env['ODOO_DB']})")

    partners_465 = odoo.search_read(
        "res.partner",
        [("name", "=like", "465%")],
        ["id", "name", "vat"],
        limit=500,
    )

    existing_employees = odoo.search_read(
        "hr.employee",
        [("active", "in", [True, False])],
        ["id", "name", "address_home_id"],
        limit=5000,
    )
    linked_partner_ids = {
        e["address_home_id"][0]
        for e in existing_employees
        if isinstance(e.get("address_home_id"), (list, tuple)) and e["address_home_id"]
    }

    to_create: list[dict] = []
    already_linked: list[dict] = []

    for p in partners_465:
        if p["id"] in linked_partner_ids:
            already_linked.append(p)
            continue
        name = employee_name_from_partner(p["name"])
        if not name:
            continue
        active = not bool(INACTIVO_RE.search(p["name"]))
        to_create.append(
            {
                "partner": p,
                "name": name,
                "active": active,
                "identification_id": p.get("vat") or False,
            }
        )

    print("=" * 70)
    print("CREACION DE EMPLEADOS A PARTIR DE CONTACTOS '465...'")
    print("=" * 70)
    print(f"Contactos '465...' encontrados:         {len(partners_465)}")
    print(f"Ya vinculados a un empleado existente:   {len(already_linked)}")
    print(f"Empleados a crear:                       {len(to_create)}")
    print(f"  -> activos:                            {sum(1 for e in to_create if e['active'])}")
    print(f"  -> archivados (contacto dice inactivo): {sum(1 for e in to_create if not e['active'])}")
    print()

    if to_create:
        print("-- Empleados que se crearian --")
        for item in to_create:
            p = item["partner"]
            estado = "ACTIVO" if item["active"] else "ARCHIVADO"
            dni = item["identification_id"] or "(sin DNI)"
            print(f"  [{p['id']}] {p['name']!r} -> hr.employee {item['name']!r} [{estado}] DNI={dni}")
        print()

    if not args.apply:
        print("Modo simulacion: no se ha modificado nada en Odoo.")
        print("Ejecuta con --apply para aplicar estos cambios.")
        return

    print("Aplicando cambios en Odoo...")
    created = 0
    for item in to_create:
        p = item["partner"]
        values = {
            "name": item["name"],
            "address_home_id": p["id"],
            "active": item["active"],
        }
        if item["identification_id"]:
            values["identification_id"] = item["identification_id"]
        odoo.create("hr.employee", values)
        created += 1
    print(f"Empleados creados: {created}")


if __name__ == "__main__":
    main()
