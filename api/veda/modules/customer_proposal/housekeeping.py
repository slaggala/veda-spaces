"""Proposal housekeeping (CQX-11): run by ``veda maintenance customer-proposal-housekeeping``.

- Links past their own expiry are recorded EXPIRED (they already stop serving on the next request; this records it and
  writes the EXPIRED event, which a refused request cannot, because a refusal rolls back).
- Staff are reminded once per version when an open, shared proposal is close to the end of its validity
  (``REMINDER_DAYS``): an internal reminder, not a customer message and not a commercial term.

Idempotent: a second run the same day changes nothing and reminds nobody twice. Not scheduled by this change; the
staging enablement record schedules it with the other maintenance jobs.
"""

from __future__ import annotations

from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db, outbox
from veda.modules.mtq_commercial.models import Quotation
from veda.platform.notifications.models import OutboxEvent

from . import events, grants
from . import vocab as V
from .models import ProposalAccessGrant

REMINDER_DAYS = 3


def run(s: Session) -> dict[str, int]:
    now = db.tx_time(s)
    expired = 0
    for g in s.execute(sa.select(ProposalAccessGrant).where(ProposalAccessGrant.status.in_(V.LIVE_GRANT_STATUSES),
                                                            ProposalAccessGrant.expires_on <= now)).scalars():  # fmt: skip
        expired += int(grants.expire_if_due(s, g))
    today = now.date()
    shared = {g.quotation_id for g in s.execute(sa.select(ProposalAccessGrant).where(
        ProposalAccessGrant.status.in_(V.LIVE_GRANT_STATUSES))).scalars()}  # fmt: skip
    reminded = 0
    if shared:
        due = s.execute(sa.select(Quotation).where(
            Quotation.id.in_(shared), Quotation.status == "ISSUED", Quotation.valid_until.is_not(None),
            Quotation.valid_until >= today, Quotation.valid_until <= today + timedelta(days=REMINDER_DAYS))).scalars()  # fmt: skip
        for q in due:
            done = s.execute(sa.select(OutboxEvent.id).where(OutboxEvent.event_type == events.NEARING_EXPIRY,
                                                             OutboxEvent.aggregate_id == q.id)).first()  # fmt: skip
            if done is None:
                outbox.enqueue(s, events.NEARING_EXPIRY, "quotation", q.id, quotation_id=q.id)
                reminded += 1
    s.flush()
    return {"links_expired": expired, "reminders": reminded}
