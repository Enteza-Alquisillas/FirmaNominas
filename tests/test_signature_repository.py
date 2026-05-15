from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import signature_repository as repo


def test_create_and_list_requests(tmp_path):
    repo.DB_PATH = tmp_path / "signatures.db"
    repo.init_db()

    req_id = repo.create_request(
        {
            "employee_id_odoo": 1,
            "worker_number": "10",
            "dni": "12345678A",
            "employee_name": "Empleado",
            "period_month": 5,
            "period_year": 2026,
            "pdf_original_path": "a.pdf",
            "token_hash": "abc",
            "token_expires_at": "2099-01-01T00:00:00+00:00",
        }
    )
    assert req_id
    rows = repo.list_requests(period_month=5, period_year=2026)
    assert len(rows) == 1
    assert rows[0]["employee_name"] == "Empleado"
