from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.signature_tokens import create_token, expires_at, is_expired, token_hash


def test_token_generation_and_hash():
    token = create_token()
    assert isinstance(token, str)
    assert len(token) > 20
    hashed = token_hash(token)
    assert len(hashed) == 64


def test_expires_at_not_expired_immediately():
    exp = expires_at(1)
    assert is_expired(exp) is False
