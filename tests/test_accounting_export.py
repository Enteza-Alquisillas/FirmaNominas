from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.payroll_excel import PayrollEmployee
from core.odoo_export import build_employee_rows, generate_odoo_import_xlsx
from core.payroll_pdf import PayslipPage


class TestBuildEmployeeRows:
    def test_basic_row(self):
        employees = [
            PayrollEmployee(
                worker_number="228",
                name="JUAN PEREZ",
                center="Madrid",
                concepts={
                    "total_bruto": Decimal("2000.00"),
                    "total_neto": Decimal("1600.00"),
                    "descuento_irpf": Decimal("300.00"),
                    "descuento_ss": Decimal("100.00"),
                    "ss_empresa": Decimal("500.00"),
                    "coste_tc1": Decimal("400.00"),
                },
            )
        ]
        pdf_pages = [
            PayslipPage(
                page_index=0,
                worker_number="228",
                employee_name="JUAN PEREZ",
                dni="75427433Z",
                month=5,
                year=2026,
                raw_period=None,
                text_preview="",
            )
        ]
        rows = build_employee_rows(employees, pdf_pages)
        assert len(rows) == 1
        assert rows[0]["n_trabajador"] == "228"
        assert rows[0]["dni"] == "75427433Z"
        assert rows[0]["nombre_excel"] == "JUAN PEREZ"

    def test_pdf_not_found(self):
        employees = [
            PayrollEmployee(
                worker_number="999",
                name="MARIA LOPEZ",
                concepts={"total_bruto": Decimal("1500.00")},
            )
        ]
        pdf_pages = []
        rows = build_employee_rows(employees, pdf_pages)
        assert len(rows) == 1
        assert rows[0]["dni"] == ""
        assert rows[0]["nombre_pdf"] == ""


class TestGenerateOdooImportXlsx:
    def test_balanced_entry(self):
        employees = [
            PayrollEmployee(
                worker_number="228",
                name="JUAN PEREZ",
                concepts={
                    "total_bruto": Decimal("2000.00"),
                    "total_neto": Decimal("1600.00"),
                    "descuento_irpf": Decimal("300.00"),
                    "descuento_ss": Decimal("100.00"),
                    "ss_empresa": Decimal("400.00"),
                    "coste_tc1": Decimal("500.00"),
                },
            )
        ]
        employee_rows = [
            {
                "n_trabajador": "228",
                "dni": "75427433Z",
                "nombre_excel": "JUAN PEREZ",
                "nombre_pdf": "JUAN PEREZ",
                "centro": "Madrid",
                "cuenta_sueldos": "64000000",
                "cuenta_ss_empresa": "64200100",
                "cuenta_remuneraciones": "46510228",
                "cuenta_irpf": "47510000",
                "cuenta_ss_acreedora": "47600012",
                "cuenta_embargo": "46599999",
                "cuenta_especie_autonomo": "46599998",
                "cuenta_indemniz_inss": "47100000",
                "partner_odoo": "JUAN PEREZ",
                "tax_grid_sueldo": "mod111[02]",
                "tax_grid_irpf": "mod111[03]",
                "total_bruto": 2000.00,
                "total_neto": 1600.00,
                "descuento_ss": 100.00,
                "descuento_irpf": 300.00,
                "ss_empresa": 400.00,
                "coste_tc1": 500.00,
                "embargo_juzgado": 0.00,
                "valores_especie_autonomo": 0.00,
                "total_indemniz_inss": 0.00,
            }
        ]

        xlsx_bytes, summary = generate_odoo_import_xlsx(
            employees=employees,
            employee_rows=employee_rows,
            month=5,
            year=2026,
            journal="NOMINAS",
            date="2026-05-31",
            reference="NOMINA 05/2026",
            aggregate_ss=True,
        )

        assert xlsx_bytes is not None
        assert len(xlsx_bytes) > 0
        assert summary["is_balanced"] is True

    def test_excluded_employee(self):
        employees = [
            PayrollEmployee(
                worker_number="228",
                name="JUAN PEREZ",
                concepts={"total_bruto": Decimal("2000.00")},
            )
        ]
        employee_rows = [
            {
                "n_trabajador": "228",
                "incluir": "NO",
                "dni": "75427433Z",
                "nombre_excel": "JUAN PEREZ",
                "nombre_pdf": "JUAN PEREZ",
                "centro": "",
                "cuenta_sueldos": "64000000",
                "cuenta_ss_empresa": "64200100",
                "cuenta_remuneraciones": "46510228",
                "cuenta_irpf": "47510000",
                "cuenta_ss_acreedora": "47600012",
                "cuenta_embargo": "46599999",
                "cuenta_especie_autonomo": "46599998",
                "cuenta_indemniz_inss": "47100000",
                "partner_odoo": "JUAN PEREZ",
                "tax_grid_sueldo": "",
                "tax_grid_irpf": "",
            }
        ]

        xlsx_bytes, summary = generate_odoo_import_xlsx(
            employees=employees,
            employee_rows=employee_rows,
            month=5,
            year=2026,
            journal="NOMINAS",
            date="2026-05-31",
            reference="NOMINA 05/2026",
            aggregate_ss=True,
        )

        assert summary["line_count"] == 0
