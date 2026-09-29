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
    from veda.kernel import net

    return net.limiter_key(net.client_ip(request.remote_addr, request.headers.get("CF-Connecting-IP")))


def body_email_key() -> str:
    """Per-email limits are keyed by (email, client network): a third party exhausting the limit from its own
    network cannot lock the account holder out everywhere (IR-23; proposed amendment AM-7 to 08 §12)."""
    from veda.kernel import net

    try:
        data = json.loads(request.get_data(cache=True) or b"{}")
        email = str(data.get("email", "")).strip().lower()
    except (ValueError, AttributeError):
        email = ""
    network = net.network_of(net.client_ip(request.remote_addr, request.headers.get("CF-Connecting-IP")))
    return f"email:{email}|{network}"


limiter = Limiter(
    key_func=ip_key,
    storage_uri="memory://",
    headers_enabled=True,
    header_name_mapping=None,
    strategy="fixed-window",
)
