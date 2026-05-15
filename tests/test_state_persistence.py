from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestStatePersistence:
    def test_init_state_defaults(self):
        """Test that state module defines correct defaults."""
        from core.state import init_state

        defaults = {
            "processed": False,
            "period_month": None,
            "period_year": None,
            "pdf_pages": None,
            "excel_employees": None,
            "employee_rows": None,
            "accounting_summary": None,
            "mapping_xlsx_bytes": None,
            "odoo_import_xlsx_bytes": None,
            "zip_payslips_bytes": None,
            "split_pdfs": None,
            "worker_pdf_filenames": None,
            "odoo_matches": None,
            "odoo_upload_log": None,
            "odoo_move_result": None,
            "odoo_move_preview": None,
            "signature_links": None,
            "whatsapp_delivery_log": None,
            "pdf_hash": None,
            "excel_hash": None,
        }

        for key, expected_value in defaults.items():
            assert key in [
                "processed",
                "period_month",
                "period_year",
                "pdf_pages",
                "excel_employees",
                "employee_rows",
                "accounting_summary",
                "mapping_xlsx_bytes",
                "odoo_import_xlsx_bytes",
                "zip_payslips_bytes",
                "split_pdfs",
                "worker_pdf_filenames",
                "odoo_matches",
                "odoo_upload_log",
                "odoo_move_result",
                "odoo_move_preview",
                "signature_links",
                "whatsapp_delivery_log",
                "pdf_hash",
                "excel_hash",
            ]

    def test_artifact_keys_defined(self):
        """Test that all artifact keys are defined."""
        from core.state import ARTIFACT_KEYS

        assert "processed" in ARTIFACT_KEYS
        assert "zip_payslips_bytes" in ARTIFACT_KEYS
        assert "odoo_import_xlsx_bytes" in ARTIFACT_KEYS
        assert "mapping_xlsx_bytes" in ARTIFACT_KEYS
        assert "odoo_matches" in ARTIFACT_KEYS
        assert "odoo_upload_log" in ARTIFACT_KEYS
        assert "odoo_move_result" in ARTIFACT_KEYS
        assert "odoo_move_preview" in ARTIFACT_KEYS
        assert "signature_links" in ARTIFACT_KEYS
        assert "whatsapp_delivery_log" in ARTIFACT_KEYS
        assert "split_pdfs" in ARTIFACT_KEYS
        assert "worker_pdf_filenames" in ARTIFACT_KEYS
