from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.odoo_accounting import build_payroll_move_lines, summarize_move_lines
from core.payroll_excel import PayrollEmployee


def test_build_payroll_move_lines_generates_rows():
    employees = [
        PayrollEmployee(
            worker_number="1",
            name="Empleado Uno",
            concepts={
                "total_bruto": Decimal("1000.00"),
                "total_neto": Decimal("700.00"),
                "descuento_irpf": Decimal("100.00"),
                "ss_empresa": Decimal("200.00"),
                "coste_tc1": Decimal("400.00"),
            },
        )
    ]
    rows = [
        {
            "incluir": "SI",
            "n_trabajador": "1",
            "cuenta_sueldos": "64000000",
            "cuenta_ss_empresa": "64200100",
            "cuenta_remuneraciones": "46510001",
            "cuenta_irpf": "47510000",
            "cuenta_ss_acreedora": "47600012",
            "partner_odoo": "Empleado Uno",
        }
    ]
    lines = build_payroll_move_lines(employees, rows, month=5, year=2026, aggregate_ss=True)
    assert len(lines) >= 4
    summary = summarize_move_lines(lines)
    assert summary["line_count"] == len(lines)


def test_summarize_move_lines_balanced():
    lines = [
        {"debit": 100.0, "credit": 0.0},
        {"debit": 0.0, "credit": 100.0},
    ]
    summary = summarize_move_lines(lines)
    assert summary["is_balanced"] is True
    assert summary["balance"] == 0.0
