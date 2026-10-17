"""Anonymous funnel beacons (SCA-008): one count per browser session, event and day; nothing about the person.

The page sends ``{event, client, utm_source?, utm_medium?, referrer_host?}``. The server derives the acquisition
channel with the same rule the lead uses, and counts the event once per (client, event, day): the digest of that
triple is remembered in memory, bounded and rolled over daily, the way the platform's idempotency store works
(single-process deployment, ``deploy-check``). The client token is a random value the browser keeps for its session;
it is never stored, and no IP address, user agent, page or free text is kept. After a restart a session could be
counted once more; the funnel reports beacon counts as CLIENT_EVENT, never as authoritative.
"""

from __future__ import annotations

import hashlib
import re
import threading
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.kernel.errors import field_error, validation_failed

from . import attribution
from .models import AcquisitionEventDaily
from .vocab import EVENTS

BUSINESS_TZ = "Asia/Kolkata"
CLIENT_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
TEXT_RE = re.compile(r"^[A-Za-z0-9._:%+-]{1,100}$")
SEEN_LIMIT = 200_000  # digests kept for today and yesterday; beyond it the oldest day is dropped first

_lock = threading.Lock()
_seen: dict[str, set[str]] = {}  # day → digests


def business_day() -> date:
    return clock.now().astimezone(ZoneInfo(BUSINESS_TZ)).date()


def digest(client: str, event: str, day: date) -> str:
    return hashlib.sha256(f"{client}\n{event}\n{day.isoformat()}".encode()).hexdigest()


def _first_time(d: str, day: date) -> bool:
    today, yesterday = day.isoformat(), (day - timedelta(days=1)).isoformat()
    with _lock:
        for stale in [k for k in _seen if k not in (today, yesterday)]:
            del _seen[stale]
        bucket = _seen.setdefault(today, set())
        if d in bucket:
            return False
        if sum(len(b) for b in _seen.values()) >= SEEN_LIMIT:
            _seen[min(_seen)].clear()
        bucket.add(d)
        return True


def reset_for_tests() -> None:
    with _lock:
        _seen.clear()


def _text(value, name: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not TEXT_RE.match(value):
        raise validation_failed([field_error(name, "INVALID", "Not a valid value.")])
    return value


def record(s: Session, body) -> bool:
    """Count the beacon once; return whether it was new. Validation errors are 422; nothing else is reported."""
    event = body.event
    if event not in EVENTS:
        raise validation_failed([field_error("event", "INVALID", "Unknown event.")])
    client = body.client
    if not isinstance(client, str) or not CLIENT_RE.match(client):
        raise validation_failed(
            [field_error("client", "INVALID", "A session token of 16 to 64 characters is required.")]
        )
    utm_source = _text(body.utm_source, "utm_source")
    utm_medium = _text(body.utm_medium, "utm_medium")
    referrer = _text(body.referrer_host, "referrer_host")
    ch = attribution.channel("WEBSITE", utm_source, utm_medium, referrer).code
    day = business_day()
    if not _first_time(digest(client, event, day), day):
        return False
    row = s.execute(
        sa.select(AcquisitionEventDaily).where(
            AcquisitionEventDaily.day == day.isoformat(),
            AcquisitionEventDaily.event == event,
            AcquisitionEventDaily.channel == ch,
        )
    ).scalar_one_or_none()
    if row is None:
        s.add(AcquisitionEventDaily(day=day.isoformat(), event=event, channel=ch, count=1))
    else:
        row.count += 1
    return True
