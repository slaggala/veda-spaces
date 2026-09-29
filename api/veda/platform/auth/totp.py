"""RFC 6238 TOTP: SHA-1, 6 digits, 30-second steps, drift T-1..T+1 (05 §11.2)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from datetime import datetime
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6
ISSUER = "Veda Spaces"


def new_secret() -> bytes:
    return secrets.token_bytes(20)  # 160 bits (MFA-010)


def b32(secret: bytes) -> str:
    return base64.b32encode(secret).decode().rstrip("=")


def time_step(at: datetime) -> int:
    return int(at.timestamp()) // STEP_SECONDS


def hotp(secret: bytes, counter: int, digits: int = DIGITS) -> str:
    mac = hmac.new(secret, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return f"{code:0{digits}d}"


def code_at(secret: bytes, at: datetime) -> str:
    return hotp(secret, time_step(at))


def verify(secret: bytes, code: str, at: datetime, last_used_step: int | None) -> int | None:
    """Return the matched step, or None. Steps ≤ last_used_step are replays (MFA-009)."""
    if not isinstance(code, str) or len(code) != DIGITS or not code.isdigit():
        return None
    current = time_step(at)
    for step in (current - 1, current, current + 1):
        if hmac.compare_digest(hotp(secret, step), code):
            if last_used_step is not None and step <= last_used_step:
                return None
            return step
    return None


def is_replay(secret: bytes, code: str, at: datetime, last_used_step: int | None) -> bool:
    if last_used_step is None or not code.isdigit():
        return False
    current = time_step(at)
    return any(step <= last_used_step and hmac.compare_digest(hotp(secret, step), code)
               for step in (current - 1, current, current + 1))


def otpauth_uri(secret: bytes, account: str) -> str:
    label = quote(f"{ISSUER}:{account}", safe="")
    return f"otpauth://totp/{label}?secret={b32(secret)}&issuer={quote(ISSUER)}&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"
