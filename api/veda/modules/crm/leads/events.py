"""Lead outbox events and platform integrations (02 §10.3, LEAD-020).

The module registers its notification handlers and its audit-viewer entity
resolvers with the platform, so the platform never imports module code.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.dto import single_line
from veda.platform.audit.routes import register_entity
from veda.platform.identity.models import User
from veda.platform.lookups.service import value_ref
from veda.platform.notifications.handlers import app_link, handler, notify_in_app, send
from veda.platform.notifications.models import OutboxEvent
from veda.platform.rbac.resolver import holders_of

from . import repository as repo
from .models import Lead, LeadActivity, LeadNote

LEAD_CREATED = "lead.created"
LEAD_ASSIGNED = "lead.assigned"
LEAD_WON = "lead.won"
LEAD_REOPENED = "lead.reopened"
LEAD_ERASURE_REQUESTED = "lead.erasure_requested"
FOLLOW_UP_DUE = "activity.follow_up_due"
SPAM_REVIEW_DIGEST = "lead.spam_review_digest"


def _lead(s: Session, lead_id: str) -> Lead | None:
    return s.get(Lead, lead_id)


def _summary(s: Session, lead: Lead) -> str:
    """One line: values entered by the public or staff never start a new line in plain-text email (IR-29)."""
    parts = [single_line(lead.name)]
    pt = value_ref(s, lead.project_type_id)
    if pt:
        parts.append(pt["label"])
    if lead.locality or lead.city:
        parts.append(single_line(lead.locality or lead.city))
    return " · ".join(p for p in parts if p)


@handler(LEAD_CREATED)
def _created(s: Session, event: OutboxEvent) -> None:
    lead = _lead(s, event.payload["lead_id"])
    if lead is None or lead.spam_status in repo.HIDDEN_SPAM:
        return
    recipients = holders_of(s, "lead.assign")
    title = f"New enquiry: {lead.lead_number}"
    body = _summary(s, lead)
    notify_in_app(
        s,
        event,
        recipients,
        notification_type="LEAD_CREATED",
        title=title,
        body=body,
        entity=("lead", lead.id),
        link_path=f"/leads/{lead.id}",
    )
    for uid in recipients:
        u = s.get(User, uid)
        send("lead_notification", [u.email], event, title=title, body=body, link=app_link(f"/leads/{lead.id}"))


@handler(LEAD_ASSIGNED)
def _assigned(s: Session, event: OutboxEvent) -> None:
    lead = _lead(s, event.payload["lead_id"])
    assignee = s.get(User, event.payload.get("assignee_id"))
    if lead is None or assignee is None or lead.assigned_to != assignee.id:
        return
    title = f"New lead assigned: {lead.lead_number}"
    body = _summary(s, lead)
    notify_in_app(
        s,
        event,
        [assignee.id],
        notification_type="LEAD_ASSIGNED",
        title=title,
        body=body,
        entity=("lead", lead.id),
        link_path=f"/leads/{lead.id}",
    )
    send("lead_notification", [assignee.email], event, title=title, body=body, link=app_link(f"/leads/{lead.id}"))


@handler(LEAD_WON)
def _won(s: Session, event: OutboxEvent) -> None:
    lead = _lead(s, event.payload["lead_id"])
    if lead is None:
        return
    notify_in_app(
        s,
        event,
        holders_of(s, "lead.read", min_scope="ALL"),
        notification_type="LEAD_WON",
        title=f"Won: {lead.lead_number}",
        body=_summary(s, lead),
        entity=("lead", lead.id),
        link_path=f"/leads/{lead.id}",
    )


@handler(LEAD_REOPENED)
def _reopened(s: Session, event: OutboxEvent) -> None:
    lead = _lead(s, event.payload["lead_id"])
    if lead is None or lead.assigned_to is None:
        return
    notify_in_app(
        s,
        event,
        [lead.assigned_to],
        notification_type="LEAD_REOPENED",
        title=f"Reopened: {lead.lead_number}",
        body=_summary(s, lead),
        entity=("lead", lead.id),
        link_path=f"/leads/{lead.id}",
    )


@handler(FOLLOW_UP_DUE)
def _follow_up(s: Session, event: OutboxEvent) -> None:
    act = s.get(LeadActivity, event.payload["activity_id"])
    if act is None or act.activity_status != "PLANNED":
        return
    lead = _lead(s, act.lead_id)
    if lead is None:
        return
    notify_in_app(
        s,
        event,
        [act.owner_user_id],
        notification_type="FOLLOW_UP_DUE",
        title=f"Follow-up due: {act.subject}",
        body=f"{lead.lead_number} · {lead.name}",
        entity=("lead", lead.id),
        link_path=f"/leads/{lead.id}",
    )


@handler(SPAM_REVIEW_DIGEST)
def _spam_digest(s: Session, event: OutboxEvent) -> None:
    count = s.execute(sa.select(sa.func.count()).select_from(Lead).where(Lead.spam_status == "SUSPECTED")).scalar()
    if not count:
        return
    recipients = holders_of(s, "lead.update", min_scope="ALL")
    title = f"Spam review: {count} enquir{'y' if count == 1 else 'ies'} waiting"
    notify_in_app(
        s,
        event,
        recipients,
        notification_type="SPAM_REVIEW",
        title=title,
        body="Suspected spam is quarantined until reviewed.",
        link_path="/leads?spam_status=SUSPECTED",
    )
    for uid in recipients:
        u = s.get(User, uid)
        send(
            "digest",
            [u.email],
            event,
            name=u.display_name or u.full_name,
            title=title,
            message="Review the quarantined enquiries so no genuine lead is missed.",
            link=app_link("/leads?spam_status=SUSPECTED"),
        )


# --- audit viewer integration (A-12) -------------------------------------------------------------


def _lead_entity(s: Session, ctx, lead_id: str):
    lead = s.get(Lead, lead_id, execution_options={"include_deleted": True})
    if lead is None:
        return None, True  # purged or anonymized history is valid (03 §2.11)
    visible = ctx is not None and repo.in_scope(lead, ctx.scope("lead.read"), ctx.user.id)
    return (f"{lead.lead_number} · {lead.name}" if visible else None), visible


def _child_entity(model):
    def resolve(s: Session, ctx, entity_id: str):
        row = s.get(model, entity_id, execution_options={"include_deleted": True})
        if row is None:
            return None, True
        label, visible = _lead_entity(s, ctx, row.lead_id)
        kind = "Note" if model is LeadNote else "Activity"
        return (f"{kind} on {label.split(' · ')[0]}" if label else None), visible

    return resolve


register_entity("lead", _lead_entity)
register_entity("lead_note", _child_entity(LeadNote))
register_entity("lead_activity", _child_entity(LeadActivity))
