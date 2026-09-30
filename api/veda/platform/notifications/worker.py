"""The outbox worker (02 §10.1).

1. claim: status IN (PENDING, FAILED) AND next_attempt_on <= now, plus stale
   PROCESSING rows (> 5 min) → PROCESSING, locked_by, locked_on
2. dispatch to the handler for the event type
3. success → DONE; failure → attempts++, backoff 2^n s (max 1 h); ≥ 8 → DEAD
"""

from __future__ import annotations

import hashlib
import logging
import os
import socket
import time
from datetime import timedelta

import sqlalchemy as sa

from veda.kernel import clock, db
from veda.kernel.context import ActorContext, actor

from . import email as email_mod
from .handlers import MAINTENANCE_ONLY, begin_email_queue, dispatch, take_email_queue
from .models import OutboxEvent

log = logging.getLogger("veda.worker")

MAX_ATTEMPTS = 8
STALE_AFTER = timedelta(minutes=5)
_stop = False


def worker_label() -> str:
    return f"{socket.gethostname()[:40]}:{os.getpid()}"[:64]


def _system(request_id: str | None = None) -> ActorContext:
    from veda.kernel.ids import SYSTEM_USER_ID

    return ActorContext(actor_id=SYSTEM_USER_ID, via="SYSTEM_JOB", request_id=request_id)


def claim(batch: int = 20, *, only: frozenset[str] | None = None, include_maintenance: bool = False) -> list[str]:
    label = worker_label()
    with actor(_system()), db.unit_of_work(write=True) as s:
        now = db.tx_time(s)
        q = sa.select(OutboxEvent).where(
            sa.or_(
                sa.and_(OutboxEvent.status.in_(("PENDING", "FAILED")), OutboxEvent.next_attempt_on <= now),
                sa.and_(OutboxEvent.status == "PROCESSING", OutboxEvent.locked_on < now - STALE_AFTER),
            )
        )
        if only is not None:
            q = q.where(OutboxEvent.event_type.in_(only))
        elif not include_maintenance:
            q = q.where(OutboxEvent.event_type.not_in(MAINTENANCE_ONLY))
        q = q.order_by(OutboxEvent.next_attempt_on, OutboxEvent.id).limit(batch)
        if s.get_bind().dialect.name == "postgresql":
            q = q.with_for_update(skip_locked=True)
        events = s.execute(q).scalars().all()
        for ev in events:
            ev.status, ev.locked_by, ev.locked_on = "PROCESSING", label, now
        return [ev.id for ev in events]


DELIVERED_KEY = "_email_delivered"


def delivery_key(message) -> str:
    """Identity of one email of an event: template and recipients (no content, no addresses in clear)."""
    return hashlib.sha256(f"{message.template}|{','.join(sorted(message.to))}".encode()).hexdigest()[:32]


def _mark_delivered(event_id: str, key: str, request_id: str | None) -> None:
    with actor(_system(request_id)), db.unit_of_work(write=True) as s:
        ev = s.get(OutboxEvent, event_id)
        payload = dict(ev.payload or {})
        payload[DELIVERED_KEY] = sorted({*payload.get(DELIVERED_KEY, []), key})
        ev.payload = payload


def process(event_id: str, *, handler=None) -> bool:
    try:
        with db.unit_of_work(write=True) as probe:
            ev = probe.get(OutboxEvent, event_id)
            request_id = (ev.payload or {}).get("request_id") if ev else None
            delivered = set((ev.payload or {}).get(DELIVERED_KEY, [])) if ev else set()
        # 1. In-app handler work commits on its own (idempotent per event and recipient).
        begin_email_queue()
        with actor(_system(request_id)), db.unit_of_work(write=True) as s:
            ev = s.get(OutboxEvent, event_id)
            if ev is None or ev.status != "PROCESSING":
                take_email_queue()
                return False
            (handler or dispatch)(s, ev)
        # 2. Email after commit; a provider failure marks the event FAILED and never touches business data.
        #    Each delivered message is recorded on the event, so a retry sends only what has not gone out (IR-30).
        for message in take_email_queue():
            key = delivery_key(message)
            if key in delivered:
                continue
            email_mod.provider().send(message)
            _mark_delivered(event_id, key, request_id)
            delivered.add(key)
        with actor(_system(request_id)), db.unit_of_work(write=True) as s:
            ev = s.get(OutboxEvent, event_id)
            ev.status, ev.processed_on, ev.last_error = "DONE", db.tx_time(s), None
            ev.locked_by = ev.locked_on = None
        return True
    except Exception as exc:
        take_email_queue()
        log.warning("outbox_handler_failed event_id=%s error=%s", event_id, type(exc).__name__)
        with actor(_system()), db.unit_of_work(write=True) as s:
            ev = s.get(OutboxEvent, event_id)
            if ev is not None:
                ev.attempts += 1
                now = db.tx_time(s)
                ev.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"[:2000]
                ev.locked_by = ev.locked_on = None
                if ev.attempts >= MAX_ATTEMPTS:
                    ev.status = "DEAD"
                    log.error("outbox_event_dead event_id=%s type=%s", ev.id, ev.event_type)
                else:
                    ev.status = "FAILED"
                    ev.next_attempt_on = now + timedelta(seconds=min(2**ev.attempts, 3600))
        return False


def drain_once(batch: int = 20, **kwargs) -> int:
    ids = claim(batch, **kwargs)
    done = 0
    for event_id in ids:
        done += 1 if process(event_id) else 0
    return len(ids)


def drain_all(max_rounds: int = 50, **kwargs) -> int:
    total = 0
    for _ in range(max_rounds):
        n = drain_once(**kwargs)
        total += n
        if n == 0:
            break
    return total


def lag_seconds() -> float | None:
    with db.unit_of_work(write=False) as s:
        oldest = s.execute(
            sa.select(sa.func.min(OutboxEvent.created_on)).where(OutboxEvent.status.in_(("PENDING", "FAILED")))
        ).scalar()
    return None if oldest is None else max(0.0, (clock.now() - oldest).total_seconds())


def outbox_stats() -> dict[str, float]:
    """Depth and age of undelivered events and the number of dead-lettered ones (02 §9 alerts, IR-A14)."""
    with db.unit_of_work(write=False) as s:
        depth, oldest = s.execute(
            sa.select(sa.func.count(), sa.func.min(OutboxEvent.created_on)).where(
                OutboxEvent.status.in_(("PENDING", "FAILED"))
            )
        ).one()
        dead = s.execute(sa.select(sa.func.count()).where(OutboxEvent.status == "DEAD")).scalar() or 0
    age = 0.0 if oldest is None else max(0.0, (clock.now() - oldest).total_seconds())
    return {"depth": float(depth or 0), "oldest_age_s": age, "dead": float(dead)}


def emit_outbox_metrics() -> dict[str, float]:
    from veda.kernel import metrics

    stats = outbox_stats()
    metrics.emit_many(
        {
            "OutboxDepth": (stats["depth"], "Count"),
            "OutboxOldestAge": (stats["oldest_age_s"], "Seconds"),
            "OutboxDead": (stats["dead"], "Count"),
        }
    )
    if stats["dead"]:
        log.error("outbox_dead_events count=%d", int(stats["dead"]))
    return stats


def run_forever(poll_seconds: float = 2.0) -> None:  # pragma: no cover - process loop
    import signal

    def stop(*_):
        global _stop
        _stop = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("outbox_worker_started label=%s", worker_label())
    last_metrics = 0.0
    while not _stop:
        try:
            if time.monotonic() - last_metrics >= 60:
                emit_outbox_metrics()
                last_metrics = time.monotonic()
            if drain_once() == 0:
                time.sleep(poll_seconds)
        except Exception:
            log.exception("outbox_worker_loop_error")
            time.sleep(poll_seconds)
