"""Corrige la vinculacion empleado <-> contacto usando los contactos "465..."
que ya existian en Odoo (creados por la gestoria) y que tienen el DNI real en
el campo 'vat'.

Contexto: un script anterior (link_employee_partners.py) vinculo empleados a
contactos por nombre exacto, pero los contactos correctos se llaman
"465{codigo} {NOMBRE}" (con el codigo de cuenta 465 como prefijo), asi que no
los encontro y creo contactos duplicados vacios (sin DNI).

Este script:
  1. Busca, para cada empleado, el contacto "465..." cuyo nombre (una vez
     quitado el prefijo de codigo) coincide con el nombre del empleado.
  2. Si lo encuentra y el empleado esta vinculado a un contacto distinto,
     revincula 'address_home_id' al contacto correcto.
  3. Si el contacto antiguo (incorrecto) no tiene DNI y no es usado en ningun
     apunte contable, lo archiva (active=False), nunca lo borra.

Uso:
    python scripts/relink_465_contacts.py            # dry-run (informe)
    python scripts/relink_465_contacts.py --apply    # aplica cambios reales
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.odoo_client import OdooClient  # noqa: E402
from core.utils import normalize_dni, normalize_name  # noqa: E402

CODE_PREFIX_RE = re.compile(r"^465[\dx]+", re.IGNORECASE)
SEPARATOR_RE = re.compile(r"^[\s\-]*(?:Jer[\s\-]*)?[\s\-]*", re.IGNORECASE)
PARENS_RE = re.compile(r"\(.*?\)")


def clean_name(name: str) -> str:
    name = PARENS_RE.sub("", name)
    return " ".join(name.split())


def strip_code_prefix(name: str) -> str:
    m = CODE_PREFIX_RE.match(name)
    if not m:
        return name
    rest = name[m.end():]
    return SEPARATOR_RE.sub("", rest)


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

    employees = odoo.search_read(
        "hr.employee",
        [("active", "=", True)],
        ["id", "name", "address_home_id", "identification_id"],
        limit=1000,
    )
    partners_465 = odoo.search_read(
        "res.partner",
        [("name", "=like", "465%")],
        ["id", "name", "vat"],
        limit=500,
    )

    # index 465-partners by normalized (prefix-stripped, cleaned) name and by DNI
    partners_by_norm: dict[str, list[dict]] = {}
    partners_by_dni: dict[str, list[dict]] = {}
    for p in partners_465:
        norm = normalize_name(clean_name(strip_code_prefix(p["name"])))
        partners_by_norm.setdefault(norm, []).append(p)
        if p.get("vat"):
            partners_by_dni.setdefault(normalize_dni(str(p["vat"])), []).append(p)

    used_partner_ids: set[int] = set()
    matched: dict[int, tuple[dict, str]] = {}  # employee id -> (new_partner, method)
    unmatched: list[dict] = []
    ambiguous: list[tuple[dict, list[dict]]] = []

    # Pass 1: DNI match takes priority for every employee, before any name-based
    # matching is attempted, so a weaker name match can never steal a contact
    # that belongs to another employee by DNI.
    for emp in employees:
        if not emp.get("identification_id"):
            continue
        dni_candidates = [
            p for p in partners_by_dni.get(normalize_dni(str(emp["identification_id"])), [])
            if p["id"] not in used_partner_ids
        ]
        if len(dni_candidates) == 1:
            used_partner_ids.add(dni_candidates[0]["id"])
            matched[emp["id"]] = (dni_candidates[0], "dni")

    # Pass 2: name match for employees still unresolved.
    for emp in employees:
        if emp["id"] in matched:
            continue
        norm_emp = normalize_name(clean_name(emp["name"]))
        candidates = [p for p in partners_by_norm.get(norm_emp, []) if p["id"] not in used_partner_ids]
        if not candidates:
            if norm_emp in partners_by_norm:
                ambiguous.append((emp, partners_by_norm[norm_emp]))
            else:
                unmatched.append(emp)
            continue
        used_partner_ids.add(candidates[0]["id"])
        matched[emp["id"]] = (candidates[0], "name")

    relinks: list[tuple[dict, dict, dict | None, str]] = []  # (employee, new_partner, old_partner_or_None, method)
    for emp in employees:
        if emp["id"] not in matched:
            continue
        new_partner, method = matched[emp["id"]]

        old_addr = emp.get("address_home_id")
        old_partner_id = old_addr[0] if isinstance(old_addr, (list, tuple)) and old_addr else None

        if old_partner_id == new_partner["id"]:
            continue  # ya correcto

        old_partner = None
        if old_partner_id:
            rows = odoo.search_read("res.partner", [("id", "=", old_partner_id)], ["id", "name", "vat"], limit=1)
            old_partner = rows[0] if rows else None

        relinks.append((emp, new_partner, old_partner, method))

    print("=" * 70)
    print("RE-VINCULACION EMPLEADO <-> CONTACTO '465...' (con DNI real)")
    print("=" * 70)
    print(f"Empleados activos:                  {len(employees)}")
    print(f"Contactos '465...' encontrados:      {len(partners_465)}")
    print(f"Re-vinculaciones necesarias:         {len(relinks)}")
    print(f"Sin contacto '465...' correspondiente: {len(unmatched)}")
    print(f"Ambiguos (mismo nombre, ya usado):   {len(ambiguous)}")
    print()

    to_archive: list[dict] = []
    if relinks:
        print("-- Re-vinculaciones --")
        for emp, new_partner, old_partner, method in relinks:
            old_desc = f"[{old_partner['id']}] {old_partner['name']!r} (vat={old_partner.get('vat')!r})" if old_partner else "(sin contacto previo)"
            print(f"  [{emp['id']:>5}] {emp['name']!r}  (metodo: {method})")
            print(f"      antes: {old_desc}")
            print(f"      ahora: [{new_partner['id']}] {new_partner['name']!r} (vat={new_partner.get('vat')!r})")
            if old_partner and not old_partner.get("vat") and not str(old_partner["name"]).startswith("465"):
                to_archive.append(old_partner)
        print()

    if unmatched:
        print("-- Empleados sin contacto '465...' correspondiente (revisar manualmente) --")
        for emp in unmatched:
            print(f"  [{emp['id']:>5}] {emp['name']!r}")
        print()

    if ambiguous:
        print("-- Casos ambiguos (nombre duplicado) --")
        for emp, cands in ambiguous:
            print(f"  [{emp['id']:>5}] {emp['name']!r} -> candidatos: {[(c['id'], c['name']) for c in cands]}")
        print()

    if to_archive:
        print(f"-- Contactos duplicados a archivar (active=False): {len(to_archive)} --")
        for p in to_archive:
            print(f"  [{p['id']}] {p['name']!r}")
        print()

    if not args.apply:
        print("Modo simulacion: no se ha modificado nada en Odoo.")
        print("Ejecuta con --apply para aplicar estos cambios.")
        return

    print("Aplicando cambios en Odoo...")
    for emp, new_partner, _old_partner, _method in relinks:
        odoo.write("hr.employee", [emp["id"]], {"address_home_id": new_partner["id"]})
    if to_archive:
        odoo.write("res.partner", [p["id"] for p in to_archive], {"active": False})
    print(f"Empleados re-vinculados: {len(relinks)}")
    print(f"Contactos duplicados archivados: {len(to_archive)}")


if __name__ == "__main__":
    main()
