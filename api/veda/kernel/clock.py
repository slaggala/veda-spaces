"""The platform clock (PLAT-007).

All instants are timezone-aware UTC. Tests replace the clock through
``set_clock``/``advance`` instead of patching ``datetime``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

_lock = threading.Lock()
_override: Callable[[], datetime] | None = None
_offset = timedelta(0)


def now() -> datetime:
    with _lock:
        base = _override() if _override else datetime.now(UTC)
        return base + _offset


def set_clock(fn: Callable[[], datetime] | None) -> None:
    global _override, _offset
    with _lock:
        _override = fn
        _offset = timedelta(0)


def advance(delta: timedelta) -> None:
    global _offset
    with _lock:
        _offset += delta


def reset() -> None:
    set_clock(None)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive datetime")
    return value.astimezone(UTC)


def to_rfc3339(value: datetime | None, *, micros: bool = False) -> str | None:
    """RFC 3339 UTC with ``Z``. The API uses milliseconds (08 §2.2); evidence
    stores (JCS, audit payloads) use microseconds (05 §9.6)."""
    if value is None:
        return None
    value = ensure_utc(value)
    if micros:
        return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def parse_rfc3339(text: str) -> datetime:
    """Parse an RFC 3339 instant. Offset-less values are rejected (03 §2.2)."""
    if not isinstance(text, str) or "T" not in text:
        raise ValueError("not a datetime")
    candidate = text.strip()
    if candidate.endswith("Z") or candidate.endswith("z"):
        candidate = candidate[:-1] + "+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        raise ValueError("offset required")
    return parsed.astimezone(UTC)


def local_day_range_utc(day_from: date, day_to: date, tz_name: str) -> tuple[datetime, datetime]:
    """Calendar days in the user's zone → UTC half-open range [from, to+1d) (08 §2.6)."""
    tz = ZoneInfo(tz_name)
    start = datetime.combine(day_from, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    end = datetime.combine(day_to + timedelta(days=1), datetime.min.time(), tzinfo=tz).astimezone(UTC)
    return start, end


def start_of_local_day(instant: datetime, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    local = instant.astimezone(tz)
    return datetime.combine(local.date(), datetime.min.time(), tzinfo=tz).astimezone(UTC)
