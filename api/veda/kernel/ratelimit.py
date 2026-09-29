"""Application rate limits (08 §12, 02 §11.1 Layer 3).

Flask-Limiter with its in-memory store is authoritative because exactly one
application process runs (OPS-010, F-09). A deployment check fails if the
gunicorn worker count is not 1.
"""

from __future__ import annotations

import json

from flask import request
from flask_limiter import Limiter


def ip_key() -> str:
    return request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"


def body_email_key() -> str:
    try:
        data = json.loads(request.get_data(cache=True) or b"{}")
        email = str(data.get("email", "")).strip().lower()
    except (ValueError, AttributeError):
        email = ""
    return f"email:{email}"


limiter = Limiter(
    key_func=ip_key,
    storage_uri="memory://",
    headers_enabled=True,
    header_name_mapping=None,
    strategy="fixed-window",
)
