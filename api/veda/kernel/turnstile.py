"""Cloudflare Turnstile verification (LEAD-018, 05 §4).

``cloudflare`` mode calls the siteverify API server-to-server. ``dev`` mode
accepts any non-empty token except ones starting with ``fail`` so tests and
local runs can exercise both outcomes. A counter lets tests assert the
idempotency lookup happens before CAPTCHA (08 §2.8, F-04).
"""

from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request

from veda.config import settings

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

_lock = threading.Lock()
calls = 0


def reset_counter() -> None:
    global calls
    with _lock:
        calls = 0


def verify(token: str | None, remote_ip: str | None) -> bool:
    global calls
    with _lock:
        calls += 1
    if not token or not isinstance(token, str) or len(token) > 2048:
        return False
    s = settings()
    if s.turnstile_mode != "cloudflare":
        # The development verifier exists for local and test only; anywhere else it fails closed (IR-09).
        return s.dev_keys_allowed and not token.startswith("fail")
    data = urllib.parse.urlencode({"secret": s.turnstile_secret or "", "response": token, "remoteip": remote_ip or ""})
    try:  # pragma: no cover - network
        # Bandit B310 (url open) does not apply: SITEVERIFY_URL is a constant https URL.
        with urllib.request.urlopen(SITEVERIFY_URL, data=data.encode(), timeout=5) as resp:  # nosec B310
            return accept(json.loads(resp.read()))
    except Exception:  # pragma: no cover - network
        return False


def expected_hostnames() -> set[str]:
    s = settings()
    return {urllib.parse.urlparse(o).hostname or "" for o in (*s.public_site_origins, s.app_origin)} - {""}


def accept(result: dict) -> bool:
    """A siteverify answer counts only when it succeeded for one of our own sites (IR-A13): a token solved on
    another site that uses the same (leaked) site key is refused."""
    return bool(result.get("success")) and result.get("hostname") in expected_hostnames()
