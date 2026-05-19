from __future__ import annotations

import streamlit as st

ARTIFACT_KEYS = [
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
    "odoo_move_results",
    "move_draft_bytes",
    "move_draft_lines_by_center",
    "partner_ids_by_worker",
    "existing_465_accounts",
    "dept_by_worker",
    "signature_links",
    "whatsapp_delivery_log",
    "pdf_hash",
    "excel_hash",
]


def init_state():
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
        "odoo_move_results": None,
        "move_draft_bytes": None,
        "move_draft_lines_by_center": None,
        "partner_ids_by_worker": None,
        "existing_465_accounts": None,
        "dept_by_worker": None,
        "signature_links": None,
        "whatsapp_delivery_log": None,
        "pdf_hash": None,
        "excel_hash": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_processing_state():
    for key in ARTIFACT_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    init_state()
