from __future__ import annotations

import secrets


def generate_api_key(slot_id: str | None = None) -> str:
    rand = secrets.token_urlsafe(18)  # ~24 chars
    slot_part = f"{slot_id}_" if slot_id else ""
    return f"psai_{slot_part}{rand}"
