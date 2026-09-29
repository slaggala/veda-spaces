"""Transactional outbox (02 §10.1, NOTIF-003).

Services add ``outbox_event`` rows in the business transaction. Payloads hold
ids and ``request_id`` only — never PII or secrets. The worker drains them
after commit, so external side effects never run inside the request.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from veda.kernel import db
from veda.kernel.context import current_actor


def enqueue(session: Session, event_type: str, aggregate_type: str, aggregate_id: str, **ids) -> None:
    from veda.platform.notifications.models import OutboxEvent

    ctx = current_actor()
    payload = {k: v for k, v in ids.items() if v is not None}
    payload["request_id"] = ctx.request_id if ctx else None
    session.add(OutboxEvent(
        event_type=event_type, aggregate_type=aggregate_type, aggregate_id=aggregate_id, payload=payload,
        status="PENDING", attempts=0, next_attempt_on=db.tx_time(session),
    ))
