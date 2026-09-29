"""Lead notes (NOTE-*) and activities / follow-ups (ACT-*, LEAD-015)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError, field_error, validation_failed
from veda.platform.identity.models import User
from veda.platform.lookups import service as lookups

from . import repository as repo
from .models import CONTACT_ACTIVITY_TYPES, SYSTEM_ACTIVITY_TYPES, Lead, LeadActivity, LeadNote
from .service import _user_ref, eligible_assignee, recompute_follow_up

# --- notes ------------------------------------------------------------------------------------


def note_scope_ok(ctx, note: LeadNote, permission: str) -> bool:
    scope = ctx.scope(permission)
    return scope == "ALL" or (scope == "OWN" and note.created_by == ctx.user.id)


def present_note(ctx, s: Session, note: LeadNote) -> dict:
    return {
        "id": note.id,
        "lead_id": note.lead_id,
        "body": note.body,
        "is_pinned": note.is_pinned,
        "visibility": note.visibility,
        "created_by": _user_ref(s, note.created_by),
        "created_on": clock.to_rfc3339(note.created_on),
        "updated_on": clock.to_rfc3339(note.updated_on),
        "is_edited": note.version > 1,
        "can_edit": note_scope_ok(ctx, note, "lead_note.update"),
        "can_delete": note_scope_ok(ctx, note, "lead_note.delete"),
        "version": note.version,
    }


def create_note(s: Session, ctx, lead: Lead, body) -> LeadNote:
    if body.visibility != "INTERNAL":
        raise ApiError(422, "VISIBILITY_NOT_SUPPORTED", "Customer-visible notes are not available yet.")
    note = LeadNote(lead_id=lead.id, body=body.body, is_pinned=body.is_pinned, visibility="INTERNAL")
    s.add(note)
    s.flush()
    return note


def update_note(s: Session, ctx, note: LeadNote, body) -> None:
    if not note_scope_ok(ctx, note, "lead_note.update"):
        raise ApiError(
            403, "PERMISSION_DENIED", "You can edit only your own notes.", extra={"permission": "lead_note.update"}
        )
    if "body" in body.provided() and body.body:
        note.body = body.body
    if "is_pinned" in body.provided() and body.is_pinned is not None:
        note.is_pinned = body.is_pinned


def delete_note(s: Session, ctx, note: LeadNote) -> None:
    if not note_scope_ok(ctx, note, "lead_note.delete"):
        raise ApiError(
            403, "PERMISSION_DENIED", "You can delete only your own notes.", extra={"permission": "lead_note.delete"}
        )
    note.is_deleted = True


# --- activities -----------------------------------------------------------------------------------


def activity_scope_ok(ctx, act: LeadActivity, permission: str) -> bool:
    scope = ctx.scope(permission)
    return scope == "ALL" or (scope == "OWN" and ctx.user.id in (act.owner_user_id, act.created_by))


def present_activity(ctx, s: Session, act: LeadActivity, *, with_lead: Lead | None = None) -> dict:
    now = clock.now()
    data = {
        "id": act.id,
        "lead_id": act.lead_id,
        "activity_type": act.activity_type,
        "activity_status": act.activity_status,
        "is_system_generated": act.is_system_generated,
        "subject": act.subject,
        "description": act.description,
        "direction": act.direction,
        "scheduled_on": clock.to_rfc3339(act.scheduled_on),
        "completed_on": clock.to_rfc3339(act.completed_on),
        "duration_minutes": act.duration_minutes,
        "outcome": lookups.value_ref(s, act.outcome_id),
        "location": act.location,
        "owner": _user_ref(s, act.owner_user_id),
        "from_status": act.from_status,
        "to_status": act.to_status,
        "cancelled_reason": act.cancelled_reason,
        # Superseded consent evidence carried by re-consent system activities (DEV-004, AM-4); null otherwise.
        "consent_evidence": act.metadata_
        if act.is_system_generated and "consent_event" in (act.metadata_ or {})
        else None,
        "is_overdue": act.activity_status == "PLANNED" and act.scheduled_on is not None and act.scheduled_on < now,
        "can_edit": not act.is_system_generated and activity_scope_ok(ctx, act, "lead_activity.update"),
        "can_delete": not act.is_system_generated and activity_scope_ok(ctx, act, "lead_activity.delete"),
        "created_by": _user_ref(s, act.created_by),
        "created_on": clock.to_rfc3339(act.created_on),
        "version": act.version,
    }
    if with_lead is not None:
        data["lead"] = {
            "id": with_lead.id,
            "lead_number": with_lead.lead_number,
            "name": with_lead.name,
            "status": with_lead.status,
        }
    return data


def _outcome(s: Session, code: str | None) -> str | None:
    if code is None:
        return None
    value = lookups.resolve_code(s, "ACTIVITY_OUTCOME", code)
    if value is None:
        raise validation_failed([field_error("outcome_code", "INVALID_LOOKUP", "Unknown outcome.")])
    return value.id


def _owner(s: Session, owner_id: str | None, ctx) -> str:
    owner = owner_id or ctx.user.id
    if owner != ctx.user.id and not eligible_assignee(s, owner):
        raise ApiError(
            422,
            "INVALID_OWNER",
            "Choose an active team member who can view leads.",
            errors=[field_error("owner_user_id", "INVALID_OWNER", "Not an eligible owner.")],
        )
    return owner


def create_activity(s: Session, ctx, lead: Lead, body) -> LeadActivity:
    if body.activity_type in SYSTEM_ACTIVITY_TYPES:
        raise ApiError(422, "SYSTEM_TYPE_NOT_ALLOWED", "This activity type is created by the system.")
    now = db.tx_time(s)
    planned = body.activity_status == "PLANNED"
    if planned:
        if body.scheduled_on is None:
            raise ApiError(
                422,
                "SCHEDULE_REQUIRED",
                "Choose when this is planned.",
                errors=[field_error("scheduled_on", "REQUIRED", "Choose a date and time.")],
            )
        if lead.status in ("WON", "LOST"):
            raise ApiError(422, "LEAD_CLOSED", "Reopen the lead before planning activities.")
        if lead.consent_withdrawn_on is not None and body.activity_type in CONTACT_ACTIVITY_TYPES:
            raise ApiError(422, "CONSENT_WITHDRAWN", "This person asked not to be contacted.")
    act = LeadActivity(
        lead_id=lead.id,
        activity_type=body.activity_type,
        is_system_generated=False,
        activity_status=body.activity_status,
        subject=body.subject,
        description=body.description,
        direction=body.direction,
        scheduled_on=body.scheduled_on if planned else body.scheduled_on,
        completed_on=None if planned else (body.completed_on or now),
        duration_minutes=body.duration_minutes,
        outcome_id=_outcome(s, body.outcome_code),
        owner_user_id=_owner(s, body.owner_user_id, ctx),
        location=body.location,
    )
    if not planned and act.completed_on > now + _five_minutes():
        raise validation_failed([field_error("completed_on", "OUT_OF_RANGE", "Can't be in the future.")])
    s.add(act)
    recompute_follow_up(s, lead)
    return act


def _five_minutes():
    from datetime import timedelta

    return timedelta(minutes=5)


def _require_editable(ctx, act: LeadActivity, permission: str) -> None:
    if act.is_system_generated:
        raise ApiError(422, "SYSTEM_ACTIVITY_READ_ONLY", "System activities are read-only.")
    if not activity_scope_ok(ctx, act, permission):
        raise ApiError(
            403, "PERMISSION_DENIED", "You can change only your own activities.", extra={"permission": permission}
        )


def update_activity(s: Session, ctx, lead: Lead, act: LeadActivity, body) -> None:
    _require_editable(ctx, act, "lead_activity.update")
    provided = body.provided()
    for field in ("subject", "description", "duration_minutes", "location"):
        if field in provided and (getattr(body, field) is not None or field != "subject"):
            setattr(act, field, getattr(body, field))
    if "scheduled_on" in provided:
        if act.activity_status == "PLANNED" and body.scheduled_on is None:
            raise ApiError(422, "SCHEDULE_REQUIRED", "A planned activity needs a schedule.")
        act.scheduled_on = body.scheduled_on
    if "owner_user_id" in provided and body.owner_user_id:
        act.owner_user_id = _owner(s, body.owner_user_id, ctx)
    recompute_follow_up(s, lead)


def complete_activity(s: Session, ctx, lead: Lead, act: LeadActivity, body) -> None:
    _require_editable(ctx, act, "lead_activity.update")
    if act.activity_status != "PLANNED":
        raise ApiError(422, "INVALID_ACTIVITY_STATE", "Only planned activities can be completed.")
    act.activity_status = "COMPLETED"
    act.completed_on = body.completed_on or db.tx_time(s)
    if body.outcome_code:
        act.outcome_id = _outcome(s, body.outcome_code)
    if body.description is not None:
        act.description = body.description
    if body.duration_minutes is not None:
        act.duration_minutes = body.duration_minutes
    recompute_follow_up(s, lead)


def cancel_activity(s: Session, ctx, lead: Lead, act: LeadActivity, reason: str | None) -> None:
    _require_editable(ctx, act, "lead_activity.update")
    if act.activity_status != "PLANNED":
        raise ApiError(422, "INVALID_ACTIVITY_STATE", "Only planned activities can be cancelled.")
    act.activity_status = "CANCELLED"
    act.cancelled_reason = reason
    recompute_follow_up(s, lead)


def delete_activity(s: Session, ctx, lead: Lead, act: LeadActivity) -> None:
    _require_editable(ctx, act, "lead_activity.delete")
    act.is_deleted = True
    recompute_follow_up(s, lead)


def my_activities(s: Session, ctx, q) -> tuple[list[tuple[LeadActivity, Lead]], bool]:
    from veda.kernel.http import decode_cursor

    stmt = (
        sa.select(LeadActivity, Lead)
        .join(Lead, Lead.id == LeadActivity.lead_id)
        .where(repo.scope_predicate(ctx.scope("lead.read"), ctx.user.id), Lead.spam_status.not_in(repo.HIDDEN_SPAM))
    )
    if q.owner == "me":
        stmt = stmt.where(LeadActivity.owner_user_id == ctx.user.id)
    elif q.owner:
        from veda.kernel.ids import is_valid_id

        if not is_valid_id(q.owner):
            raise ApiError(422, "INVALID_ID", "owner must be 'me' or a user id.")
        stmt = stmt.where(LeadActivity.owner_user_id == q.owner)
    if q.status:
        stmt = stmt.where(LeadActivity.activity_status.in_([v for v in q.status.split(",") if v]))
    if q.scheduled_from:
        stmt = stmt.where(LeadActivity.scheduled_on >= q.scheduled_from)
    if q.scheduled_to:
        stmt = stmt.where(LeadActivity.scheduled_on < q.scheduled_to)
    if q.overdue:
        stmt = stmt.where(LeadActivity.activity_status == "PLANNED", LeadActivity.scheduled_on < clock.now())
    cur = decode_cursor(q.cursor)
    order_col = sa.func.coalesce(LeadActivity.scheduled_on, LeadActivity.created_on)
    if cur:
        t = clock.parse_rfc3339(cur[0])
        stmt = stmt.where(sa.or_(order_col > t, sa.and_(order_col == t, LeadActivity.id > cur[1])))
    rows = s.execute(stmt.order_by(order_col, LeadActivity.id).limit(q.limit + 1)).all()
    return [(a, lead) for a, lead in rows[: q.limit]], len(rows) > q.limit


__all__ = ["User"]
