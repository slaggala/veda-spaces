"""Measurement-visit state machine (MTQ B1-T05; blueprint §4.1, §12.3; B1-SCOPE §1.1).

    REQUESTED ──schedule──► SCHEDULED ──start──► IN_PROGRESS ──complete──► COMPLETED
        │                      │  ▲                  │
        │                      └──┘ reschedule        └──cancel──► CANCELLED
        └──cancel──► CANCELLED │
                               ├──cancel──► CANCELLED
                               └──no_show─► NO_SHOW

Scheduling, rescheduling, cancelling and no-shows need ``measurement.visit.schedule``; starting and completing are
capture (``measurement.capture``) by the assigned surveyor. Completion needs a measurement set of the property
submitted since the visit started (fail closed). There is no pause state in the frozen model. Terminal states never change.

Lead synchronisation goes through the lead module's own status service, acting as SYSTEM: the first schedule moves
the lead forward to SITE_VISIT when it is earlier in the pipeline, never backward, and never touches a won or lost
lead. Each schedule, completion, cancellation and no-show writes a system activity on the lead carrying the visit id.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db, sequences
from veda.kernel.context import acting, current_actor, system_context
from veda.kernel.dto import parse_phone
from veda.kernel.errors import ApiError, field_error, not_found
from veda.kernel.ids import SYSTEM_USER_ID
from veda.modules.crm.leads import service as lead_service
from veda.modules.crm.leads.models import OPEN_STATUSES, Lead
from veda.platform.identity.models import User
from veda.platform.rbac.resolver import load_grants

from . import scope
from .models import MeasurementSet, MeasurementVisit, Property

TERMINAL = ("COMPLETED", "CANCELLED", "NO_SHOW")
# (from, to) → (action, permission)
TRANSITIONS: dict[tuple[str, str], tuple[str, str]] = {
    ("REQUESTED", "SCHEDULED"): ("schedule", "measurement.visit.schedule"),
    ("SCHEDULED", "SCHEDULED"): ("reschedule", "measurement.visit.schedule"),
    ("SCHEDULED", "IN_PROGRESS"): ("start", "measurement.capture"),
    ("IN_PROGRESS", "COMPLETED"): ("complete", "measurement.capture"),
    ("REQUESTED", "CANCELLED"): ("cancel", "measurement.visit.schedule"),
    ("SCHEDULED", "CANCELLED"): ("cancel", "measurement.visit.schedule"),
    ("IN_PROGRESS", "CANCELLED"): ("cancel", "measurement.visit.schedule"),
    ("SCHEDULED", "NO_SHOW"): ("no_show", "measurement.visit.schedule"),
}
MAX_VISIT = timedelta(hours=14)  # a long independent-house visit fits one day (03 §13)


@dataclass(frozen=True)
class _SystemUser:
    id: str = SYSTEM_USER_ID


@dataclass(frozen=True)
class SystemLeadContext:
    """The SYSTEM actor's authority for the lead synchronisation only: lead.status.change at ALL scope."""

    user: _SystemUser = _SystemUser()

    def scope(self, code: str) -> str | None:
        return "ALL" if code == "lead.status.change" else None

    def has(self, code: str) -> bool:
        return self.scope(code) is not None


def allowed(visit: MeasurementVisit, ctx) -> list[str]:
    return sorted(
        {to for (frm, to), (_, perm) in TRANSITIONS.items() if frm == visit.status and ctx.scope(perm) is not None}
    )


def get_visible(s: Session, ctx, visit_id: str, permission: str = "measurement.visit.read") -> MeasurementVisit:
    visit = s.execute(
        sa.select(MeasurementVisit).where(
            MeasurementVisit.id == visit_id, scope.condition(ctx, permission, MeasurementVisit.lead_id)
        )
    ).scalar_one_or_none()
    if visit is None:
        raise not_found()
    return visit


def _lead(s: Session, lead_id: str) -> Lead:
    lead = s.get(Lead, lead_id)
    if lead is None:
        raise not_found()
    return lead


def _eligible_surveyor(s: Session, user_id: str) -> None:
    user = s.get(User, user_id)
    ok = bool(
        user
        and user.user_type == "HUMAN"
        and user.status == "ACTIVE"
        and "measurement.capture" in load_grants(s, user_id).granted
    )
    if not ok:
        raise ApiError(422, "INVALID_ASSIGNEE", "Choose an active team member who can capture measurements.",
                       errors=[field_error("assigned_to", "INVALID_ASSIGNEE", "Not an eligible surveyor.")])  # fmt: skip


def _check_window(start, end) -> None:
    if start is None:
        raise ApiError(422, "SCHEDULE_REQUIRED", "Choose when the visit starts.",
                       errors=[field_error("scheduled_start_on", "REQUIRED", "Choose a start.")])  # fmt: skip
    if end is not None and not (start < end <= start + MAX_VISIT):
        raise ApiError(422, "VALIDATION_FAILED", "A visit ends after it starts and lasts at most 14 hours.",
                       errors=[field_error("scheduled_end_on", "OUT_OF_RANGE", "End after start, within 14 h.")])  # fmt: skip


def _system_activity(s: Session, lead: Lead, visit: MeasurementVisit, subject: str, kind: str):
    return lead_service.add_system_activity(
        s,
        lead,
        "SYSTEM",
        subject,
        metadata={"measurement_visit_id": visit.id, "visit_number": visit.visit_number, "event": kind},
    )


def _sync_lead(s: Session, lead: Lead, visit: MeasurementVisit, kind: str, subject: str) -> None:
    """Act as SYSTEM (07 §3): the lead's own services do every write. The user's pending changes are flushed first,
    so the audit trail stamps each write with its true actor."""
    s.flush()
    caller = current_actor()
    request_id = caller.request_id if caller is not None else None
    with acting(s, system_context("SYSTEM_JOB", request_id)):
        act = _system_activity(s, lead, visit, subject, kind)
        if kind == "schedule" and lead.status in OPEN_STATUSES:
            if OPEN_STATUSES.index(lead.status) < OPEN_STATUSES.index("SITE_VISIT"):
                lead_service.change_status(s, SystemLeadContext(), lead, _ToSiteVisit())
        s.flush()
    if visit.lead_activity_id is None:
        visit.lead_activity_id = act.id


class _ToSiteVisit:
    to_status = "SITE_VISIT"
    comment = None
    lost_reason_code = None
    lost_reason_note = None
    won_on = None


def create(s: Session, ctx, body) -> MeasurementVisit:
    prop = s.get(Property, body.property_id)
    if prop is None or prop.is_deleted:
        raise not_found()
    scope.require_lead(s, ctx, prop.lead_id, "measurement.visit.create")
    lead = _lead(s, prop.lead_id)
    now = db.tx_time(s)
    visit = MeasurementVisit(
        visit_number=sequences.next_number(s, "MEASUREMENT"),
        property_id=prop.id,
        lead_id=prop.lead_id,
        visit_type_code=body.visit_type_code,
        status="REQUESTED",
        survey_level_code=body.survey_level_code,
        status_changed_on=now,
        customer_contact_name=body.customer_contact_name,
        customer_contact_phone=parse_phone(body.customer_contact_phone) if body.customer_contact_phone else None,
        access_notes=body.access_notes,
    )
    s.add(visit)
    s.flush()
    if body.scheduled_start_on is not None:
        scope.require_in_scope(s, ctx, prop.lead_id, "measurement.visit.schedule")
        _schedule(s, ctx, visit, lead, body.scheduled_start_on, body.scheduled_end_on, body.assigned_to)
    return visit


def _schedule(s: Session, ctx, visit: MeasurementVisit, lead: Lead, start, end, assignee) -> None:
    if lead.status in ("WON", "LOST"):
        raise ApiError(422, "LEAD_CLOSED", "Reopen the lead before scheduling a visit.")
    _check_window(start, end)
    if assignee is None:
        raise ApiError(422, "VALIDATION_FAILED", "Assign a surveyor.",
                       errors=[field_error("assigned_to", "REQUIRED", "Choose a surveyor.")])  # fmt: skip
    _eligible_surveyor(s, assignee)
    first = visit.status == "REQUESTED"
    visit.scheduled_start_on, visit.scheduled_end_on, visit.assigned_to = start, end, assignee
    visit.status = "SCHEDULED"
    visit.status_changed_on = db.tx_time(s)
    when = clock.to_rfc3339(start)
    if first:
        _sync_lead(s, lead, visit, "schedule", f"Site measurement visit {visit.visit_number} scheduled for {when}")
    else:
        _sync_lead(s, lead, visit, "reschedule", f"Site measurement visit {visit.visit_number} moved to {when}")


def transition(s: Session, ctx, visit: MeasurementVisit, body) -> MeasurementVisit:
    frm, to = visit.status, body.to_status
    if frm in TERMINAL:
        raise ApiError(409, "INVALID_STATE", f"A {frm.lower()} visit cannot change.")
    rule = TRANSITIONS.get((frm, to))
    if rule is None:
        raise ApiError(422, "INVALID_STATUS_TRANSITION", f"A {frm.lower()} visit cannot become {to.lower()}.",
                       extra={"allowed_transitions": allowed(visit, ctx)})  # fmt: skip
    action, permission = rule
    scope.require_in_scope(s, ctx, visit.lead_id, permission)
    lead = _lead(s, visit.lead_id)
    now = db.tx_time(s)
    if action in ("schedule", "reschedule"):
        start = body.scheduled_start_on or visit.scheduled_start_on
        end = body.scheduled_end_on if "scheduled_end_on" in body.provided() else visit.scheduled_end_on
        _schedule(s, ctx, visit, lead, start, end, body.assigned_to or visit.assigned_to)
        return visit
    if (
        action in ("start", "complete")
        and ctx.scope("measurement.capture") != "ALL"
        and visit.assigned_to != ctx.user.id
    ):
        raise ApiError(403, "PERMISSION_DENIED", "Only the assigned surveyor starts or completes this visit.",
                       extra={"permission": "measurement.capture"})  # fmt: skip
    if action == "start":
        visit.started_on = now
    elif action == "complete":
        # A set of this property submitted since the visit started: the visit's own set, or the shared draft a
        # second surveyor worked on (one DRAFT per property, B1-SCOPE §2.9.3).
        submitted = s.execute(
            sa.select(MeasurementSet.id).where(
                MeasurementSet.property_id == visit.property_id,
                MeasurementSet.status.in_(("SUBMITTED", "VERIFIED", "SUPERSEDED", "REJECTED")),
                MeasurementSet.submitted_on >= visit.started_on,
            )
        ).first()
        if submitted is None:
            raise ApiError(409, "SET_NOT_SUBMITTED", "Submit the measurement set before completing the visit.")
        visit.completed_on = now
        _sync_lead(s, lead, visit, "complete", f"Site measurement visit {visit.visit_number} completed")
    elif action == "cancel":
        if not body.reason:
            raise ApiError(422, "REASON_REQUIRED", "Say why the visit is cancelled.",
                           errors=[field_error("reason", "REQUIRED", "A reason is required.")])  # fmt: skip
        visit.cancel_reason = body.reason
        _sync_lead(s, lead, visit, "cancel", f"Site measurement visit {visit.visit_number} cancelled")
    elif action == "no_show":
        _sync_lead(s, lead, visit, "no_show", f"Site measurement visit {visit.visit_number}: customer not available")
    visit.status = to
    visit.status_changed_on = now
    return visit


def update(s: Session, ctx, visit: MeasurementVisit, body) -> MeasurementVisit:
    """Contact and access details; the schedule changes only through a status transition (reschedule)."""
    scope.require_in_scope(s, ctx, visit.lead_id, "measurement.visit.schedule")
    if visit.status in TERMINAL:
        raise ApiError(409, "INVALID_STATE", "A finished visit cannot change.")
    provided = body.provided()
    for name in ("customer_contact_name", "access_notes"):
        if name in provided:
            setattr(visit, name, getattr(body, name))
    if "customer_contact_phone" in provided:
        phone = body.customer_contact_phone
        visit.customer_contact_phone = parse_phone(phone) if phone else None
    if "survey_level_code" in provided and body.survey_level_code is not None:
        visit.survey_level_code = body.survey_level_code
    return visit


def present(s: Session, ctx, visit: MeasurementVisit) -> dict[str, Any]:
    def user_ref(uid: str | None):
        if not uid:
            return None
        u = s.get(User, uid)
        return {"id": uid, "display_name": u.display_name if u else None}

    return {
        "id": visit.id,
        "version": visit.version,
        "visit_number": visit.visit_number,
        "property_id": visit.property_id,
        "lead_id": visit.lead_id,
        "visit_type_code": visit.visit_type_code,
        "status": visit.status,
        "survey_level_code": visit.survey_level_code,
        "status_changed_on": clock.to_rfc3339(visit.status_changed_on),
        "scheduled_start_on": clock.to_rfc3339(visit.scheduled_start_on) if visit.scheduled_start_on else None,
        "scheduled_end_on": clock.to_rfc3339(visit.scheduled_end_on) if visit.scheduled_end_on else None,
        "started_on": clock.to_rfc3339(visit.started_on) if visit.started_on else None,
        "completed_on": clock.to_rfc3339(visit.completed_on) if visit.completed_on else None,
        "assigned_to": user_ref(visit.assigned_to),
        "lead_activity_id": visit.lead_activity_id,
        "customer_contact_name": visit.customer_contact_name,
        "customer_contact_phone": visit.customer_contact_phone,
        "access_notes": visit.access_notes,
        "cancel_reason": visit.cancel_reason,
        "allowed_transitions": allowed(visit, ctx) if visit.status not in TERMINAL else [],
    }
