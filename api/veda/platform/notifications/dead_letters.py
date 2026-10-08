"""Operator handling of dead-lettered outbox events (R3).

A DEAD event keeps the ``outbox-dead`` alarm in ALARM, and CloudWatch notifies only on a state change: while one
stays, a new dead event (a lead notification that never went out) would not alert. The operator lists dead events and
either requeues one (the cause is fixed and it should run again) or retires it (it must not run: for example an
invite that was already accepted). Both act on DEAD events only, need a reason, and leave a record: the reason on the
event (``last_error``) and a warning log line. Payloads are never shown; they can name users and tokens.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
import structlog

from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.kernel.ids import is_valid_id
from veda.platform.notifications.models import OutboxEvent

log = structlog.get_logger("veda.outbox")

MIN_REASON = 10
MAX_ERROR = 2000


class DeadLetterError(ValueError):
    """The event is unknown, not DEAD, or the reason is too short."""


def list_dead() -> list[dict]:
    with db.unit_of_work(write=False) as s:
        rows = s.execute(sa.select(OutboxEvent).where(OutboxEvent.status == "DEAD").order_by(OutboxEvent.id)).scalars()
        return [
            {
                "id": ev.id,
                "event_type": ev.event_type,
                "aggregate_type": ev.aggregate_type,
                "attempts": ev.attempts,
                "last_error": ev.last_error,
                "created_on": _iso(ev.created_on),
            }
            for ev in rows
        ]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dead(s, event_id: str, reason: str) -> OutboxEvent:
    if len((reason or "").strip()) < MIN_REASON:
        raise DeadLetterError(f"a reason of at least {MIN_REASON} characters is required")
    ev = s.get(OutboxEvent, event_id) if is_valid_id(event_id) else None
    if ev is None:
        raise DeadLetterError(f"no outbox event {event_id}")
    if ev.status != "DEAD":
        raise DeadLetterError(f"outbox event {event_id} is {ev.status}, not DEAD")
    return ev


def _note(prefix: str, reason: str) -> str:
    return f"{prefix}: {' '.join(reason.split())}"[:MAX_ERROR]


def retire(event_id: str, reason: str) -> dict:
    """Close a DEAD event without running it: it leaves the dead count and is never retried."""
    with actor(system_context("CLI").with_reason(reason)), db.unit_of_work(write=True) as s:
        ev = _dead(s, event_id, reason)
        ev.status, ev.processed_on, ev.last_error = "DONE", db.tx_time(s), _note("RETIRED", reason)
        ev.locked_by = ev.locked_on = None
        result = {"id": ev.id, "event_type": ev.event_type, "status": "DONE", "action": "retired"}
    log.warning("outbox_event_retired event_id=%s type=%s", result["id"], result["event_type"])
    return result


def requeue(event_id: str, reason: str) -> dict:
    """Run a DEAD event again from the first attempt (after its cause is fixed)."""
    with actor(system_context("CLI").with_reason(reason)), db.unit_of_work(write=True) as s:
        ev = _dead(s, event_id, reason)
        ev.status, ev.attempts, ev.next_attempt_on = "PENDING", 0, db.tx_time(s)
        ev.last_error = _note("REQUEUED", reason)
        ev.locked_by = ev.locked_on = None
        result = {"id": ev.id, "event_type": ev.event_type, "status": "PENDING", "action": "requeued"}
    log.warning("outbox_event_requeued event_id=%s type=%s", result["id"], result["event_type"])
    return result
