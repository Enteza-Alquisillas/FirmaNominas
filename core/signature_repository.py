from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("data/signatures.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signature_requests (
              id TEXT PRIMARY KEY,
              employee_id_odoo INTEGER NOT NULL,
              worker_number TEXT,
              dni TEXT,
              employee_name TEXT,
              period_month INTEGER NOT NULL,
              period_year INTEGER NOT NULL,
              pdf_original_path TEXT NOT NULL,
              token_hash TEXT NOT NULL,
              token_expires_at TEXT NOT NULL,
              status TEXT NOT NULL,
              opened_at TEXT,
              signed_at TEXT,
              uploaded_at TEXT,
              odoo_attachment_id INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signature_artifacts (
              id TEXT PRIMARY KEY,
              request_id TEXT NOT NULL,
              signature_png_path TEXT NOT NULL,
              pdf_signed_path TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY (request_id) REFERENCES signature_requests(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signature_events (
              id TEXT PRIMARY KEY,
              request_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              metadata_json TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (request_id) REFERENCES signature_requests(id)
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_signature_requests_token_hash
              ON signature_requests (token_hash)
            """
        )
        conn.commit()
    finally:
        conn.close()


def create_request(payload: dict[str, Any]) -> str:
    request_id = str(uuid.uuid4())
    now = _now()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO signature_requests (
              id, employee_id_odoo, worker_number, dni, employee_name,
              period_month, period_year, pdf_original_path,
              token_hash, token_expires_at, status,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                int(payload["employee_id_odoo"]),
                str(payload.get("worker_number", "")),
                str(payload.get("dni", "")),
                str(payload.get("employee_name", "")),
                int(payload["period_month"]),
                int(payload["period_year"]),
                str(payload["pdf_original_path"]),
                str(payload["token_hash"]),
                str(payload["token_expires_at"]),
                "pending",
                now,
                now,
            ),
        )
        conn.commit()
        return request_id
    finally:
        conn.close()


def add_event(request_id: str, event_type: str, metadata: dict[str, Any] | None = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO signature_events (id, request_id, event_type, metadata_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), request_id, event_type, json.dumps(metadata or {}), _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_request_by_token_hash(token_hash_value: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM signature_requests WHERE token_hash = ?",
            (token_hash_value,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def mark_opened(request_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE signature_requests SET status = ?, opened_at = COALESCE(opened_at, ?), updated_at = ? WHERE id = ?",
            ("opened", _now(), _now(), request_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_signed(request_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE signature_requests SET status = ?, signed_at = ?, updated_at = ? WHERE id = ?",
            ("signed", _now(), _now(), request_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_uploaded(request_id: str, attachment_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE signature_requests SET status = ?, uploaded_at = ?, odoo_attachment_id = ?, updated_at = ? WHERE id = ?",
            ("uploaded_odoo", _now(), int(attachment_id), _now(), request_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_error(request_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE signature_requests SET status = ?, updated_at = ? WHERE id = ?",
            ("error", _now(), request_id),
        )
        conn.commit()
    finally:
        conn.close()


def save_artifact(request_id: str, signature_png_path: str, pdf_signed_path: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO signature_artifacts (id, request_id, signature_png_path, pdf_signed_path, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), request_id, signature_png_path, pdf_signed_path, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def list_requests(period_month: int | None = None, period_year: int | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT * FROM signature_requests"
        params: list[Any] = []
        clauses: list[str] = []
        if period_month is not None:
            clauses.append("period_month = ?")
            params.append(period_month)
        if period_year is not None:
            clauses.append("period_year = ?")
            params.append(period_year)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
