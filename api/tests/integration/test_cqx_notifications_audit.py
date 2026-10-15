"""CQX-11 notifications and audit: staff-only in-app notifications through the existing outbox (idempotent, no prices,
no customer text, no token), no customer message, the housekeeping job, the audit trail and log hygiene.
SYNTHETIC only; SYNTHETIC_VALIDATED."""

from __future__ import annotations

import json
import logging
from datetime import timedelta

import sqlalchemy as sa

from tests.support.proposal import INTERACTION_ON, PROPOSAL_ON, customer, setup, share
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context


def _notifications(s):
    from veda.platform.notifications.models import Notification

    return s.execute(sa.select(Notification)).scalars().all()


@INTERACTION_ON
def test_staff_are_notified_once_without_customer_text_prices_or_tokens(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    g = share(c, q)
    cust = customer(api, g)
    cust.get()
    cust.post(
        "/requests", {"category": "GENERAL_QUESTION", "message": "Secret family detail about the flat"}, key="q" * 32
    )
    from veda.platform.notifications import worker
    from veda.platform.notifications.email import CaptureEmailProvider

    worker.drain_all()
    worker.drain_all()  # a second drain delivers nothing twice
    with db.unit_of_work() as s:
        rows = _notifications(s)
        kinds = {n.notification_type for n in rows}
        assert {"PROPOSAL_SHARED", "PROPOSAL_VIEWED", "PROPOSAL_QUESTION"} <= kinds
        per = [(n.notification_type, n.recipient_user_id) for n in rows]
        assert len(per) == len(set(per))
        text = json.dumps([(n.title, n.body, n.link_path) for n in rows])
        assert "Secret family detail" not in text and g["token"] not in text and "₹" not in text
        assert str(q["total_minor"]) not in text
        recipients = {n.recipient_user_id for n in rows if n.notification_type == "PROPOSAL_QUESTION"}
        assert c.estimator.id in recipients and c.designer.id not in recipients  # by permission and scope
    from veda.platform.identity.models import User

    with db.unit_of_work() as s:
        staff = {u.email for u in s.execute(sa.select(User)).scalars()}
    sent_to = {to for m in CaptureEmailProvider.sent for to in m.to}
    assert sent_to <= staff  # every message went to staff: no customer-directed message (no approved channel)


@PROPOSAL_ON
def test_housekeeping_records_expired_links_and_reminds_staff_once(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    g1 = share(c, q)
    share(c, q, kind="CO_OWNER")
    from veda.modules.customer_proposal.models import ProposalAccessGrant, ProposalEvent
    from veda.modules.mtq_commercial.models import Quotation
    from veda.platform import maintenance

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        s.get(ProposalAccessGrant, g1["id"]).expires_on = clock.now() - timedelta(minutes=5)
        s.get(Quotation, q["id"]).valid_until = clock.now().date() + timedelta(days=2)
    assert maintenance.customer_proposal_housekeeping() == {"links_expired": 1, "reminders": 1}
    assert maintenance.customer_proposal_housekeeping() == {"links_expired": 0, "reminders": 0}
    with db.unit_of_work() as s:
        assert s.get(ProposalAccessGrant, g1["id"]).status == "EXPIRED"
        assert "EXPIRED" in [e.event_code for e in s.execute(sa.select(ProposalEvent)).scalars()]


def test_housekeeping_is_skipped_while_proposals_are_off(app):
    from veda.platform import maintenance

    assert "skipped" in maintenance.customer_proposal_housekeeping()


@INTERACTION_ON
def test_audit_trail_and_logs_never_hold_a_token(api, factory, capfd):
    logging.getLogger().setLevel(logging.DEBUG)
    c, prop, est, q = setup(api, factory, "2BHK")
    g = share(c, q)
    cust = customer(api, g)
    cust.get()
    api.get("/api/v1/public/proposal", anonymous=True, headers={"X-Veda-Proposal": g["token"][:-1] + "Z"})
    from veda.platform.audit.models import AuditLog

    with db.unit_of_work() as s:
        rows = s.execute(sa.select(AuditLog).where(AuditLog.entity_type == "proposal_access_grant")).scalars().all()
        assert rows and all(r.parent_entity_type == "quotation" and r.parent_entity_id == q["id"] for r in rows)
        assert g["token"] not in json.dumps([(r.old_value, r.new_value) for r in rows], default=str)
    out, err = capfd.readouterr()
    assert "/api/v1/public/proposal" in out + err  # the request log is there…
    assert g["token"] not in out + err and g["token"][4:] not in out + err  # …and holds no token
