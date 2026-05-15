from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.signature_delivery import (
    build_sign_link,
    build_whatsapp_url,
    normalize_base_url,
    normalize_phone_for_whatsapp,
    render_message,
)


def test_normalize_phone_for_whatsapp():
    assert normalize_phone_for_whatsapp("+34 600-123-123") == "+34600123123"
    assert normalize_phone_for_whatsapp("600 123 123") == "600123123"


def test_render_message_template():
    msg = render_message("Hola {nombre} {periodo} {link}", "Ana", "03/2026", "https://x")
    assert "Ana" in msg
    assert "03/2026" in msg
    assert "https://x" in msg


def test_build_whatsapp_url():
    url = build_whatsapp_url("+34 600123123", "Hola prueba")
    assert url.startswith("https://wa.me/34600123123?text=")


def test_normalize_base_url_adds_scheme():
    assert normalize_base_url("firma.midominio.com") == "https://firma.midominio.com"


def test_build_sign_link_format():
    link = build_sign_link("firma.midominio.com/", "abc")
    assert link == "https://firma.midominio.com/?token=abc"
