"""The project timeline (PLB-12) and its staff notifications (PLB-38, PLB-30).

``record`` appends a ``project_event`` row. Events are facts: the actor (``created_by``), the time (``created_on``), a
code, the stage and states, and a detail of codes, ids, digests and dates only. Free text never enters the timeline
(``_check`` refuses it), so an event never needs erasing and can be immutable: the database refuses UPDATE and DELETE
on ``project_event`` (migration 0208 triggers), and no route changes or removes one.

Outbox events notify **staff only**, in-app, by permission and project team, never by role name; no customer is
notified and no channel is invented. Payloads hold ids only. ``project.handed_over`` is the post-handover domain event
(PLB-30): it carries what a future warranty/service workstream needs to find the project and its effective commercial
baseline, and nothing here acts on it beyond telling the team.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import outbox
from veda.platform.notifications.handlers import handler, notify_in_app
from veda.platform.notifications.models import OutboxEvent
from veda.platform.rbac.resolver import holders_of

from .models import Project, ProjectEvent, ProjectMember

_SAFE = re.compile(r"^[A-Za-z0-9_.:>+-]{0,80}$")

BLOCKER_ASSIGNED = "project.blocker_assigned"
CUSTOMER_ACTION_REQUIRED = "project.customer_action_required"
AWAITING_APPROVAL = "project.transition_awaiting_approval"
STAGE_ENTERED = "project.stage_entered"
READY_FOR_HANDOVER = "project.ready_for_handover"
HANDED_OVER = "project.handed_over"  # PLB-30: the domain event a warranty/service workstream may consume later
EVENT_TYPES = (BLOCKER_ASSIGNED, CUSTOMER_ACTION_REQUIRED, AWAITING_APPROVAL, STAGE_ENTERED, READY_FOR_HANDOVER,
               HANDED_OVER)  # fmt: skip


def _check(value: Any, key: str) -> None:
    if value is None or isinstance(value, bool | int):
        return
    if isinstance(value, str):
        if not _SAFE.match(value):
            raise ValueError(f"project_event detail {key!r} must be a code, id, digest or date, never free text")
        return
    if isinstance(value, list | tuple):
        for v in value:
            _check(v, key)
        return
    raise ValueError(f"project_event detail {key!r} has an unsupported type {type(value).__name__}")


def record(s: Session, p: Project, code: str, *, stage: str | None = None, frm: str | None = None,
           to: str | None = None, **detail: Any) -> ProjectEvent:  # fmt: skip
    clean = {k: v for k, v in detail.items() if v is not None}
    for k, v in clean.items():
        _check(v, k)
    e = ProjectEvent(project_id=p.id, lead_id=p.lead_id, event_code=code, stage_code=stage, from_state=frm,
                     to_state=to, detail=clean)  # fmt: skip
    s.add(e)
    return e


def timeline(s: Session, project_id: str) -> list[ProjectEvent]:
    return list(s.execute(sa.select(ProjectEvent).where(ProjectEvent.project_id == project_id)
                          .order_by(ProjectEvent.created_on, ProjectEvent.id)).scalars())  # fmt: skip


def notify(s: Session, p: Project, event_type: str, **ids: Any) -> None:
    outbox.enqueue(s, event_type, "project", p.id, project_id=p.id, **ids)


# --- staff notifications ----------------------------------------------------------------------------------------------
def _project(s: Session, event: OutboxEvent) -> Project | None:
    from veda.modules.crm.leads.models import Lead

    p = s.get(Project, event.payload.get("project_id"))
    if p is None:
        return None
    lead = s.get(Lead, p.lead_id)
    return None if lead is None or lead.anonymized_on is not None else p


def _owners(s: Session, p: Project, *responsibilities: str) -> list[str]:
    q = sa.select(ProjectMember.user_id).where(ProjectMember.project_id == p.id, ProjectMember.is_active == sa.true(),
                                               ProjectMember.responsibility != "MEMBER")  # fmt: skip
    if responsibilities:
        q = q.where(ProjectMember.responsibility.in_(responsibilities))
    return [u for (u,) in s.execute(q)]


def _send(s: Session, event: OutboxEvent, p: Project, recipients: Sequence[str | None], kind: str, title: str) -> None:
    notify_in_app(s, event, [r for r in recipients if r is not None], notification_type=kind,
                  title=title.format(project=p.project_number), entity=("project", p.id),
                  link_path=f"/projects/{p.id}")  # fmt: skip


@handler(BLOCKER_ASSIGNED)
def _blocker_assigned(s: Session, event: OutboxEvent) -> None:
    p = _project(s, event)
    if p is not None:
        _send(
            s,
            event,
            p,
            [event.payload.get("assigned_to")],
            "PROJECT_BLOCKER_ASSIGNED",
            "A blocker on {project} was assigned to you",
        )


@handler(CUSTOMER_ACTION_REQUIRED)
def _customer_action(s: Session, event: OutboxEvent) -> None:
    p = _project(s, event)
    if p is not None:
        _send(
            s,
            event,
            p,
            _owners(s, p, "PROJECT", "SITE"),
            "PROJECT_CUSTOMER_ACTION",
            "{project}: the customer has an action to take",
        )


@handler(AWAITING_APPROVAL)
def _awaiting(s: Session, event: OutboxEvent) -> None:
    p = _project(s, event)
    if p is None:
        return
    members = [u for u in _owners(s, p) if u != event.payload.get("requested_by")]
    approvers = [u for u in holders_of(s, "project.approve_transition", min_scope="ALL")
                 if u != event.payload.get("requested_by")]  # fmt: skip
    eligible = [u for u in members if u in set(holders_of(s, "project.approve_transition"))]
    _send(
        s,
        event,
        p,
        [*approvers, *eligible],
        "PROJECT_TRANSITION_APPROVAL",
        "{project}: a stage transition is waiting for your approval",
    )


@handler(STAGE_ENTERED)
def _entered(s: Session, event: OutboxEvent) -> None:
    p = _project(s, event)
    if p is not None:
        _send(s, event, p, [*_owners(s, p)], "PROJECT_STAGE_ENTERED", "{project} moved to its next stage")


@handler(READY_FOR_HANDOVER)
def _ready(s: Session, event: OutboxEvent) -> None:
    p = _project(s, event)
    if p is not None:
        _send(
            s,
            event,
            p,
            _owners(s, p, "HANDOVER", "PROJECT"),
            "PROJECT_READY_FOR_HANDOVER",
            "{project} is ready for handover",
        )


@handler(HANDED_OVER)
def _handed_over(s: Session, event: OutboxEvent) -> None:
    p = _project(s, event)
    if p is not None:
        _send(s, event, p, [*_owners(s, p)], "PROJECT_HANDED_OVER", "{project} was handed over")
