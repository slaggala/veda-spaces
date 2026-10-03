"""Application rate limits (08 §12, 02 §11.1 Layer 3).

Flask-Limiter with its in-memory store is authoritative because exactly one
application process runs (OPS-010, F-09). A deployment check fails if the
gunicorn worker count is not 1.
"""

from __future__ import annotations

import json
import time

from flask import request
from flask_limiter import Limiter
from limits import parse


def ip_key() -> str:
    from veda.kernel import net

    return net.limiter_key(net.client_ip(request.remote_addr, request.headers.get("CF-Connecting-IP")))


def wide_network_key() -> str:
    """Coarse source bucket: IPv6 /48 (a site allocation, so rotating /64s inside it share one budget) and
    IPv4 /24 (RR-04)."""
    from veda.kernel import net

    return "wide:" + net.wide_network_of(net.client_ip(request.remote_addr, request.headers.get("CF-Connecting-IP")))


def body_email_key() -> str:
    """Per-(identifier, network) limits: a third party exhausting the limit from its own network cannot lock the
    account holder out everywhere (IR-23). Cross-network bounds live in the account budget
    (veda.platform.auth.throttle, RR-04). The identifier is an HMAC of the normalized email, so no address
    reaches limiter state or its log lines."""
    from veda.kernel import net
    from veda.kernel.dto import normalize_email
    from veda.platform.auth import security_events

    try:
        data = json.loads(request.get_data(cache=True) or b"{}")
        email = normalize_email(str(data.get("email", "")))
    except (ValueError, AttributeError):
        email = ""
    network = net.network_of(net.client_ip(request.remote_addr, request.headers.get("CF-Connecting-IP")))
    return f"email:{security_events.email_attempt_hash(email)[:32]}|{network}"


limiter = Limiter(
    key_func=ip_key,
    storage_uri="memory://",
    headers_enabled=True,
    header_name_mapping=None,
    strategy="fixed-window",
)


# 08 §12: every authenticated user, across all endpoints (IR-A08). Applied after authentication, so it is keyed by
# the user, not by the address, and a stolen token cannot page through the lead book faster than this.
USER_LIMIT = "600 per 5 minutes"


def user_limit_retry_after(user_id: str) -> int | None:
    """Count one request for ``user_id``; seconds until the window resets if the limit is exceeded, else None."""
    if not limiter.enabled:
        return None
    item = parse(USER_LIMIT)
    if limiter.limiter.hit(item, "user", user_id):
        return None
    reset_at, _remaining = limiter.limiter.get_window_stats(item, "user", user_id)
    return max(1, int(reset_at - time.time()))
