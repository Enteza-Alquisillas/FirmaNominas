from __future__ import annotations

from urllib.parse import quote


def normalize_phone_for_whatsapp(phone: str) -> str:
    raw = str(phone or "").strip()
    if raw.startswith("+"):
        prefix = "+"
        raw = raw[1:]
    else:
        prefix = ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    return prefix + digits


def build_whatsapp_url(phone: str, message: str) -> str:
    phone_norm = normalize_phone_for_whatsapp(phone)
    if phone_norm.startswith("+"):
        phone_norm = phone_norm[1:]
    return f"https://wa.me/{phone_norm}?text={quote(message)}"


def normalize_base_url(value: str) -> str:
    base = str(value or "").strip()
    if not base:
        return ""
    if not (base.startswith("http://") or base.startswith("https://")):
        base = "https://" + base
    return base.rstrip("/")


def build_sign_link(base_url: str, token_value: str) -> str:
    base = normalize_base_url(base_url)
    return f"{base}/?token={token_value}"


def render_message(template: str, employee_name: str, period_label: str, sign_link: str) -> str:
    msg = template
    msg = msg.replace("{nombre}", employee_name)
    msg = msg.replace("{periodo}", period_label)
    msg = msg.replace("{link}", sign_link)
    if sign_link and sign_link not in msg:
        msg = msg.rstrip() + "\n\n" + sign_link
    return msg
