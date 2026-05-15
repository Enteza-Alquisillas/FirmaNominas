from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone


def create_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expires_at(hours: int = 240) -> str:
    dt = datetime.now(timezone.utc) + timedelta(hours=hours)
    return dt.isoformat()


def is_expired(expires_at_iso: str) -> bool:
    dt = datetime.fromisoformat(expires_at_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > dt
