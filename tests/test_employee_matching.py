from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.odoo_employee_matcher import (
    normalize_dni,
    normalize_name,
    normalize_worker_number,
)


class TestEmployeeMatching:
    def test_normalize_dni_for_matching(self):
        assert normalize_dni("75427433Z") == "75427433Z"
        assert normalize_dni("75 427 433 Z") == "75427433Z"

    def test_normalize_name_for_matching(self):
        assert normalize_name("Juan Pérez") == "JUAN PEREZ"
        assert normalize_name("  Maria   Lopez  ") == "MARIA LOPEZ"

    def test_normalize_worker_for_matching(self):
        assert normalize_worker_number("00228") == "228"
        assert normalize_worker_number("228") == "228"

    def test_dni_match_logic(self):
        from core.odoo_employee_matcher import _find_match

        employee_by_dni = {
            "75427433Z": [
                {"id": 10, "name": "JUAN PEREZ GARCIA", "identification_id": "75427433Z", "active": True}
            ]
        }

        result = _find_match(
            dni="75427433Z",
            worker_number="228",
            name_pdf="JUAN PEREZ",
            name_excel="JUAN PEREZ GARCIA",
            employee_by_dni=employee_by_dni,
            employee_by_worker={},
            employee_by_name={},
            dni_field="identification_id",
            worker_field=None,
            name_field="name",
        )

        assert result.match_status == "MATCH_OK"
        assert result.employee_id_odoo == 10
        assert result.match_method == "dni"

    def test_no_match(self):
        from core.odoo_employee_matcher import _find_match

        result = _find_match(
            dni="00000000A",
            worker_number="999",
            name_pdf="DESCONOCIDO",
            name_excel="DESCONOCIDO",
            employee_by_dni={},
            employee_by_worker={},
            employee_by_name={},
            dni_field="identification_id",
            worker_field=None,
            name_field="name",
        )

        assert result.match_status == "NO_ENCONTRADO"

    def test_ambiguous_match(self):
        from core.odoo_employee_matcher import _find_match

        employee_by_dni = {
            "75427433Z": [
                {"id": 10, "name": "JUAN PEREZ 1", "identification_id": "75427433Z"},
                {"id": 11, "name": "JUAN PEREZ 2", "identification_id": "75427433Z"},
            ]
        }

        result = _find_match(
            dni="75427433Z",
            worker_number="228",
            name_pdf="JUAN PEREZ",
            name_excel="JUAN PEREZ",
            employee_by_dni=employee_by_dni,
            employee_by_worker={},
            employee_by_name={},
            dni_field="identification_id",
            worker_field=None,
            name_field="name",
        )

        assert result.match_status == "AMBIGUO"
        assert result.employee_id_odoo is None
