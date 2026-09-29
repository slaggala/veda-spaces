"""RFC 8785 JSON Canonicalization Scheme for the value types the platform uses.

Used for the security-event keyed chain (05 §9.6) and the public-intake
request fingerprint (08 §2.8). Floats are rejected: evidence rows and intake
bodies never carry them, and ES6 number formatting is therefore not needed.
"""

from __future__ import annotations

import json
from typing import Any


def _encode_string(value: str) -> str:
    # json.dumps with ensure_ascii=False escapes only '"', '\\' and control
    # characters (lowercase \u00xx), matching RFC 8785 §3.2.2.2.
    return json.dumps(value, ensure_ascii=False)


def canonicalize(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        if abs(value) > 2**53 - 1:
            raise ValueError("integer outside the I-JSON safe range")
        return str(value)
    if isinstance(value, float):
        raise TypeError("floats are not canonicalized by this implementation")
    if isinstance(value, str):
        return _encode_string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonicalize(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys(), key=lambda k: str(k).encode("utf-16-be"))
        return "{" + ",".join(f"{_encode_string(str(k))}:{canonicalize(value[k])}" for k in keys) + "}"
    raise TypeError(f"cannot canonicalize {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return canonicalize(value).encode("utf-8")
