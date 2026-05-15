from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.payroll_pdf import parse_page_text


class TestParsePageText:
    def test_extract_worker_number(self):
        text = "228\nJUAN PEREZ GARCIA\nNIF: 75427433Z\nPeriodo de liquidacion 1/mayo a 31/mayo de 2026"
        page = parse_page_text(text, 0)
        assert page.worker_number == "228"
        assert page.employee_name == "JUAN PEREZ GARCIA"

    def test_extract_dni(self):
        text = "228\nJUAN PEREZ\nNIF: 75427433Z"
        page = parse_page_text(text, 0)
        assert page.dni == "75427433Z"

    def test_extract_period(self):
        text = "Periodo de liquidacion 1/mayo a 31/mayo de 2026"
        page = parse_page_text(text, 0)
        assert page.month == 5
        assert page.year == 2026

    def test_extract_period_spanish_month(self):
        text = "Periodo de liquidacion 1/marzo a 31/marzo de 2026"
        page = parse_page_text(text, 0)
        assert page.month == 3
        assert page.year == 2026

    def test_no_dni(self):
        text = "228\nJUAN PEREZ\nPeriodo de liquidacion 1/mayo a 31/mayo de 2026"
        page = parse_page_text(text, 0)
        assert page.dni is None

    def test_no_period(self):
        text = "228\nJUAN PEREZ\nNIF: 75427433Z"
        page = parse_page_text(text, 0)
        assert page.month is None
        assert page.year is None

    def test_page_index(self):
        text = "228\nJUAN PEREZ"
        page = parse_page_text(text, 5)
        assert page.page_index == 5
