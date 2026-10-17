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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from veda.kernel import clock
from veda.kernel.context import acting, current_actor, web_intake_context
from veda.kernel.errors import field_error, validation_failed

from . import attribution
from .models import AcquisitionEventDaily
from .vocab import EVENTS

BUSINESS_TZ = "Asia/Kolkata"
CLIENT_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
TEXT_RE = re.compile(r"^[A-Za-z0-9._:%+-]{1,100}$")
SEEN_LIMIT = 200_000  # digests kept for today and yesterday (about 30 MB at most); beyond it a day is dropped

_lock = threading.Lock()
_seen: dict[str, set[str]] = {}  # day → digests


def business_day() -> date:
    return clock.now().astimezone(ZoneInfo(BUSINESS_TZ)).date()


def digest(client: str, event: str, day: date) -> str:
    return hashlib.sha256(f"{client}\n{event}\n{day.isoformat()}".encode()).hexdigest()


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
    """Count the beacon once; return whether it was new. Validation errors are 422; nothing else is reported.

    The row is written as the web-intake actor **without** the request's IP address or user agent, so the audit row
    of the day's first beacon holds nothing about the visitor either. The database step runs under the module lock
    (one process, several threads) and the session's digest is remembered only after the row was flushed, so a
    beacon that lost a race is counted by the retry inside, never lost and never answered with an error.
    """
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
    d = digest(client, event, day)
    caller = current_actor()
    anonymous = web_intake_context(caller.request_id if caller else None, None, None)
    with _lock:
        if d in _seen.get(day.isoformat(), set()):
            return False
        with acting(s, anonymous):
            _count(s, day, event, ch)
        _remember(d, day)
    return True


def _count(s: Session, day: date, event: str, ch: str) -> None:
    for attempt in (1, 2):
        try:
            with s.begin_nested():
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
                s.flush()
            return
        except (IntegrityError, StaleDataError):
            if attempt == 2:
                raise
            s.expire_all()  # another request created or moved the row: read it again and add to it


def _remember(d: str, day: date) -> None:
    today, yesterday = day.isoformat(), (day - timedelta(days=1)).isoformat()
    for stale in [k for k in _seen if k not in (today, yesterday)]:
        del _seen[stale]
    bucket = _seen.setdefault(today, set())
    if sum(len(b) for b in _seen.values()) >= SEEN_LIMIT:  # a flood: forget yesterday first, else today
        _seen[yesterday if yesterday in _seen and _seen[yesterday] else today].clear()
    bucket.add(d)
