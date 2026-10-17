"""Post-handover subscribers (PLB-30): what other workstreams do once a project is handed over.

The lifecycle imports none of them. A module registers a subscriber at import time; the ``project.handed_over`` outbox
handler (``events``) calls each one in its own savepoint after the handover has committed, so a subscriber's failure
never undoes the handover, its approval or the team's notification, and is retried by nothing here (each subscriber
offers its own idempotent command to catch up). One handler per event type is kept.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

log = logging.getLogger("veda.project.hooks")

AFTER_HANDOVER: list[Callable[[Session, Any, dict[str, Any]], None]] = []


def after_handover(fn: Callable[[Session, Any, dict[str, Any]], None]):
    if fn not in AFTER_HANDOVER:
        AFTER_HANDOVER.append(fn)
    return fn


def run_after_handover(s: Session, project, payload: dict[str, Any]) -> None:
    from veda.kernel import metrics

    for fn in list(AFTER_HANDOVER):
        try:
            with s.begin_nested():
                fn(s, project, payload)
        except Exception:  # noqa: BLE001  (isolated: the handover and its notification stand)
            log.exception("post-handover subscriber %s failed for project %s", fn.__qualname__, project.id)
            metrics.emit("PostHandoverSubscriberFailed", 1)
