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
        return not token.startswith("fail")
    data = urllib.parse.urlencode({"secret": s.turnstile_secret or "", "response": token, "remoteip": remote_ip or ""})
    try:  # pragma: no cover - network
        with urllib.request.urlopen(SITEVERIFY_URL, data=data.encode(), timeout=5) as resp:
            return bool(json.loads(resp.read()).get("success"))
    except Exception:  # pragma: no cover - network
        return False
