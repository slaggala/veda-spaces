"""Lead endpoints (08 §8, §9). Every nested route first resolves the parent lead
within the actor's lead.read scope; out of scope or soft-deleted → 404."""

from __future__ import annotations

import hashlib
from datetime import timedelta

import sqlalchemy as sa

from veda.kernel import clock, turnstile
from veda.kernel.dto import csv, normalize_email, parse_phone
from veda.kernel.errors import ApiError, field_error
from veda.kernel.http import (
    IDEMPOTENCY_KEY_RE,
    PUBLIC_MAX_BODY,
    Api,
    Req,
    Result,
    decode_cursor,
    encode_cursor,
    no_content,
    offset_meta,
    ok,
)
from veda.kernel.ids import is_valid_id
from veda.kernel.jcs import canonical_bytes
from veda.platform.auth import security_events
from veda.platform.identity.models import User
from veda.platform.lookups.models import LookupCategory, LookupValue
from veda.platform.rbac.resolver import load_grants

from . import activities as acts
from . import dashboard, service
from . import repository as repo
from . import schemas as S
from .models import OPEN_STATUSES, Lead, LeadActivity, LeadNote

api = Api("leads", "/api/v1", tags=("leads",))


# --- public intake (RBX-005, 08 §8.4) ------------------------------------------------------------


def _public_ip_key():
    from veda.kernel.ratelimit import ip_key

    return "public:" + ip_key()


def _intake_key_and_fingerprint(req: Req) -> tuple[str, str]:
    key = req.headers.get("Idempotency-Key")
    if not key:
        raise ApiError(428, "IDEMPOTENCY_KEY_REQUIRED", "Send an Idempotency-Key header.")
    if not IDEMPOTENCY_KEY_RE.match(key):
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "Invalid Idempotency-Key.",
            errors=[field_error("Idempotency-Key", "INVALID", "16–64 characters from [A-Za-z0-9_-].")],
        )
    payload = {k: v for k, v in (req.raw or {}).items() if k not in ("turnstile_token", "company_website_url")}
    return key, hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _replay(req: Req, key: str, fingerprint: str) -> Result | None:
    existing = service.find_by_idempotency_key(req.session, key)
    if existing is None:
        return None
    if existing.intake_request_fingerprint != fingerprint:
        raise ApiError(422, "IDEMPOTENCY_KEY_REUSED", "This key was used with a different request.")
    return ok({"reference": existing.public_reference, "message": service.PUBLIC_MESSAGE}, status=201)


def _public_lead_prepare(req: Req):
    """Steps 3–5 outside the write lock (IR-02): idempotency replay first (F-04), then Turnstile siteverify, which
    may take up to 5 s, with only a read-only session open."""
    key, fingerprint = _intake_key_and_fingerprint(req)
    replay = _replay(req, key, fingerprint)
    if replay is not None:
        return replay
    req.session.rollback()  # no transaction stays open across the network call
    if not turnstile.verify(req.body.turnstile_token if isinstance(req.body.turnstile_token, str) else None, req.ip):
        security_events.defer(
            "PUBLIC_INTAKE_BLOCKED", "BLOCKED", failure_reason="CAPTCHA_FAILED", detail={"reason": "captcha"}
        )
        raise ApiError(422, "CAPTCHA_FAILED", "We couldn't verify this submission.")
    return {"key": key, "fingerprint": fingerprint, "captcha": True}


@api.route(
    "POST",
    "/public/leads",
    rbx="RBX-005",
    auth="public",
    body=S.PublicLeadIn,
    status=201,
    max_body=PUBLIC_MAX_BODY,
    requirement="LEAD-001",
    prepare=_public_lead_prepare,
    limits=[("20 per minute", _public_ip_key), ("120 per hour", _public_ip_key)],
    summary="Public website enquiry (anonymous, Turnstile-gated)",
)
def public_lead(req: Req):
    key, fingerprint = req.prepared["key"], req.prepared["fingerprint"]
    # A concurrent request with the same key may have committed meanwhile: re-check inside the transaction.
    replay = _replay(req, key, fingerprint)
    if replay is not None:
        return replay
    # 6–11. Validation, honeypot, normalization, duplicate flag, insert — one transaction.
    data = service.create_public(
        req.session, req.body, key=key, fingerprint=fingerprint, ip=req.ip, ua=req.user_agent, request_id=req.request_id
    )
    result = ok(data, status=201)
    result.headers["Cache-Control"] = "no-store"
    return result


# --- list / create / detail ----------------------------------------------------------------------

SORTS = {
    "created_on": Lead.created_on,
    "status_changed_on": Lead.status_changed_on,
    "next_follow_up_on": Lead.next_follow_up_on,
    "name": Lead.name,
    "priority": Lead.priority,
}


def _lookup_filter(stmt, column, category: str, codes: str | None):
    if not codes:
        return stmt
    ids = (
        sa.select(LookupValue.id)
        .join(LookupCategory, LookupCategory.id == LookupValue.category_id)
        .where(LookupCategory.code == category, LookupValue.code.in_(csv(codes)))
    )
    return stmt.where(column.in_(ids))


def _date_range(stmt, column, day_from, day_to, tz):
    if day_from or day_to:
        start, end = clock.local_day_range_utc(day_from or day_to, day_to or day_from, tz)
        if day_from:
            stmt = stmt.where(column >= start)
        if day_to:
            stmt = stmt.where(column < end)
    return stmt


@api.route("GET", "/leads", permission="lead.read", query=S.LeadListQuery, write=False, requirement="LEAD-013")
def list_leads(req: Req):
    q, ctx = req.query, req.ctx
    if (q.include_deleted or q.deleted_only) and not ctx.has("lead.restore"):
        raise ApiError(403, "PERMISSION_DENIED", "Requires lead.restore.", extra={"permission": "lead.restore"})
    stmt = repo.visible_select(ctx, include_deleted=q.include_deleted, deleted_only=q.deleted_only)
    if q.q:
        stmt = stmt.where(repo.search_condition(q.q))
    if q.open:
        stmt = stmt.where(Lead.status.in_(OPEN_STATUSES))
    if q.status:
        stmt = stmt.where(Lead.status.in_(csv(q.status)))
    if q.assigned_to:
        values = csv(q.assigned_to)
        conds = []
        for v in values:
            if v == "me":
                conds.append(Lead.assigned_to == ctx.user.id)
            elif v == "unassigned":
                conds.append(Lead.assigned_to.is_(None))
            elif is_valid_id(v):
                conds.append(Lead.assigned_to == v)
            else:
                raise ApiError(422, "INVALID_ID", "assigned_to must be me, unassigned or user ids.")
        stmt = stmt.where(sa.or_(*conds))
    stmt = _lookup_filter(stmt, Lead.project_type_id, "PROJECT_TYPE", q.project_type)
    stmt = _lookup_filter(stmt, Lead.budget_range_id, "BUDGET_RANGE", q.budget_range)
    stmt = _lookup_filter(stmt, Lead.property_type_id, "PROPERTY_TYPE", q.property_type)
    stmt = _lookup_filter(stmt, Lead.source_id, "LEAD_SOURCE", q.source)
    if q.priority:
        stmt = stmt.where(Lead.priority.in_(csv(q.priority)))
    if q.city:
        stmt = stmt.where(sa.func.lower(Lead.city).in_([c.lower() for c in csv(q.city)]))
    tz = ctx.user.timezone
    stmt = _date_range(stmt, Lead.created_on, q.created_on_from, q.created_on_to, tz)
    stmt = _date_range(stmt, Lead.status_changed_on, q.status_changed_on_from, q.status_changed_on_to, tz)
    now = clock.now()
    if q.follow_up == "overdue":
        stmt = stmt.where(Lead.next_follow_up_on < now)
    elif q.follow_up == "today":
        day = clock.start_of_local_day(now, tz)
        stmt = stmt.where(Lead.next_follow_up_on >= day, Lead.next_follow_up_on < day + timedelta(days=1))
    elif q.follow_up == "this_week":
        stmt = stmt.where(
            Lead.next_follow_up_on >= clock.start_of_local_day(now, tz),
            Lead.next_follow_up_on < clock.start_of_local_day(now, tz) + timedelta(days=7),
        )
    elif q.follow_up == "none":
        stmt = stmt.where(Lead.next_follow_up_on.is_(None))
    if q.duplicate_status:
        stmt = stmt.where(Lead.duplicate_status.in_(csv(q.duplicate_status)))
    if q.spam_status:
        stmt = stmt.where(Lead.spam_status.in_(csv(q.spam_status)))
    else:
        stmt = stmt.where(Lead.spam_status.not_in(repo.HIDDEN_SPAM))
    if q.consent == "withdrawn":
        stmt = stmt.where(Lead.consent_withdrawn_on.is_not(None))
    order = []
    for key in csv(q.sort or "-created_on"):
        col = SORTS.get(key.lstrip("-"))
        if col is None:
            raise ApiError(
                422,
                "INVALID_QUERY_PARAM",
                f"Unsupported sort {key}.",
                errors=[field_error("sort", "INVALID_QUERY_PARAM", "Unsupported sort field.")],
            )
        order.append(col.desc() if key.startswith("-") else col.asc())
    total = req.session.execute(sa.select(sa.func.count()).select_from(stmt.order_by(None).subquery())).scalar()
    rows = (
        req.session.execute(stmt.order_by(*order, Lead.id).offset((q.page - 1) * q.page_size).limit(q.page_size))
        .scalars()
        .all()
    )
    meta, links = offset_meta(q.page, q.page_size, int(total or 0), "/api/v1/leads", q.model_dump(exclude_none=True))
    return ok([service.present_item(req.session, lead) for lead in rows], meta=meta, links=links)


@api.route(
    "POST",
    "/leads",
    permission="lead.create",
    body=S.LeadCreateIn,
    status=201,
    idempotent_create=True,
    requirement="LEAD-003",
)
def create_lead(req: Req):
    lead, dups = service.create_manual(req.session, req.ctx, req.body)
    req.session.flush()
    return ok(service.present(req.session, req.ctx, lead), status=201, meta={"possible_duplicates": dups})


@api.route(
    "GET", "/leads/duplicates", permission="lead.read", query=S.DuplicatesQuery, write=False, requirement="LEAD-010"
)
def duplicates(req: Req):
    q = req.query
    conds = []
    if q.phone:
        try:
            conds.append(Lead.phone == parse_phone(q.phone))
        except ValueError:
            return ok([])
    if q.email:
        conds.append(Lead.email_normalized == normalize_email(q.email))
    if not conds:
        return ok([])
    since = clock.now() - service.DUPLICATE_WINDOW
    stmt = repo.visible_select(req.ctx).where(sa.or_(*conds), Lead.created_on >= since)
    if q.exclude_id:
        stmt = stmt.where(Lead.id != q.exclude_id)
    rows = req.session.execute(stmt.order_by(Lead.created_on.desc()).limit(10)).scalars().all()
    return ok(
        [
            {
                "id": r.id,
                "lead_number": r.lead_number,
                "name": r.name,
                "status": r.status,
                "assigned_to": service._user_ref(req.session, r.assigned_to),
                "created_on": clock.to_rfc3339(r.created_on),
            }
            for r in rows
        ]
    )


@api.route("GET", "/leads/summary", permission="lead.read", query=S.SummaryQuery, write=False, requirement="LEAD-014")
def summary(req: Req):
    q = req.query
    return ok(dashboard.summary(req.session, req.ctx, q.period, q.from_, q.to))


class LeadGetQuery(S.Query):
    include_deleted: bool = False


def _lead(req: Req, lead_id: str, *, include_deleted: bool = False) -> Lead:
    lead = repo.get_visible(req.session, req.ctx, lead_id, include_deleted=include_deleted)
    if req.spec.method != "GET" and lead.anonymized_on is not None:
        # An erased lead is closed: no write may re-introduce personal data (IR-28, LEAD-029).
        raise ApiError(409, "INVALID_STATE", "This lead was erased and can no longer be changed.")
    return lead


@api.route("GET", "/leads/<lead_id>", permission="lead.read", query=LeadGetQuery, write=False, requirement="LEAD-013")
def get_lead(req: Req, lead_id: str):
    include = req.query.include_deleted and req.ctx.has("lead.restore")
    return ok(service.present(req.session, req.ctx, _lead(req, lead_id, include_deleted=include)))


def _for_write(req: Req, lead_id: str, permission: str, *, include_deleted: bool = False) -> Lead:
    lead = _lead(req, lead_id, include_deleted=include_deleted)
    repo.require_scope(req.ctx, lead, permission)
    service.check_version(req.session, lead, req.if_match)
    return lead


@api.route(
    "PATCH", "/leads/<lead_id>", permission="lead.update", body=S.LeadPatchIn, if_match=True, requirement="LEAD-024"
)
def patch_lead(req: Req, lead_id: str):
    lead = _for_write(req, lead_id, "lead.update")
    service.update(req.session, req.ctx, lead, req.body)
    req.session.flush()
    return ok(service.present(req.session, req.ctx, lead))


@api.route(
    "DELETE", "/leads/<lead_id>", permission="lead.delete", body=S.DeleteIn, if_match=True, requirement="LEAD-016"
)
def delete_lead(req: Req, lead_id: str):
    lead = _for_write(req, lead_id, "lead.delete")
    from veda.kernel.context import reason

    with reason(req.body.reason if req.body else None):
        service.delete(req.session, req.ctx, lead, req.body.reason if req.body else None)
        req.session.flush()
    return no_content()


@api.route("POST", "/leads/<lead_id>/restore", permission="lead.restore", if_match=True, requirement="LEAD-016")
def restore_lead(req: Req, lead_id: str):
    lead = _lead(req, lead_id, include_deleted=True)
    service.check_version(req.session, lead, req.if_match)
    service.restore(req.session, req.ctx, lead)
    req.session.flush()
    return ok(service.present(req.session, req.ctx, lead))


@api.route(
    "POST",
    "/leads/<lead_id>/status",
    any_of=("lead.status.change", "lead.reopen"),
    body=S.StatusChangeIn,
    if_match=True,
    requirement="LEAD-005",
)
def change_status(req: Req, lead_id: str):
    lead = _lead(req, lead_id)
    service.check_version(req.session, lead, req.if_match)
    from veda.kernel.context import reason

    with reason(req.body.comment):
        act = service.change_status(req.session, req.ctx, lead, req.body)
        req.session.flush()
    return ok(service.present(req.session, req.ctx, lead), meta={"activity_id": act.id})


@api.route(
    "POST", "/leads/<lead_id>/assign", permission="lead.assign", body=S.AssignIn, if_match=True, requirement="LEAD-007"
)
def assign(req: Req, lead_id: str):
    lead = _lead(req, lead_id)
    service.check_version(req.session, lead, req.if_match)
    service.assign(req.session, req.ctx, lead, req.body.assigned_to, req.body.comment)
    req.session.flush()
    return ok(service.present(req.session, req.ctx, lead))


@api.route(
    "POST",
    "/leads/<lead_id>/duplicate-resolution",
    permission="lead.update",
    body=S.DuplicateResolutionIn,
    requirement="LEAD-010",
)
def duplicate_resolution(req: Req, lead_id: str):
    lead = _lead(req, lead_id)
    if req.if_match is not None:
        service.check_version(req.session, lead, req.if_match)
    service.resolve_duplicate(req.session, req.ctx, lead, req.body.resolution, req.body.duplicate_of_lead_id)
    req.session.flush()
    return ok(service.present(req.session, req.ctx, lead))


@api.route(
    "POST",
    "/leads/<lead_id>/spam-resolution",
    permission="lead.update",
    body=S.SpamResolutionIn,
    if_match=True,
    requirement="LEAD-018",
)
def spam_resolution(req: Req, lead_id: str):
    lead = _lead(req, lead_id)
    service.check_version(req.session, lead, req.if_match)
    service.resolve_spam(req.session, req.ctx, lead, req.body.resolution)
    req.session.flush()
    return ok(service.present(req.session, req.ctx, lead))


@api.route(
    "POST",
    "/leads/<lead_id>/consent/withdraw",
    permission="lead.update",
    body=S.ConsentWithdrawIn,
    if_match=True,
    requirement="LEAD-027",
)
def withdraw_consent(req: Req, lead_id: str):
    lead = _lead(req, lead_id)
    service.check_version(req.session, lead, req.if_match)
    cancelled = service.withdraw_consent(req.session, req.ctx, lead, req.body.channel, req.body.note)
    req.session.flush()
    return ok(service.present(req.session, req.ctx, lead), meta={"cancelled_activities": cancelled})


@api.route(
    "POST", "/leads/<lead_id>/erasure", permission="lead.erase", body=S.ErasureIn, if_match=True, requirement="LEAD-029"
)
def erasure(req: Req, lead_id: str):
    lead = _lead(req, lead_id, include_deleted=True)
    service.check_version(req.session, lead, req.if_match)
    service.erase(req.session, req.ctx, lead, req.body)
    req.session.flush()
    return ok(service.present(req.session, req.ctx, lead))


@api.route(
    "GET",
    "/leads/<lead_id>/history",
    permission=("lead.read", "audit.read"),
    query=S.CursorQuery,
    write=False,
    requirement="AUDIT-006",
)
def history(req: Req, lead_id: str):
    from veda.platform.audit.routes import AuditQuery, audit_query, cursor_page, present_audit

    _lead(req, lead_id, include_deleted=req.ctx.has("lead.restore"))
    q = AuditQuery.model_validate(
        {"entity_id": lead_id, "include_children": True, "cursor": req.query.cursor, "limit": req.query.limit}
    )
    rows = req.session.execute(audit_query(q)).scalars().all()
    rows, meta = cursor_page(rows, q.limit, "performed_on")
    return ok([present_audit(req.session, req.ctx, r) for r in rows], meta=meta)


# --- notes (08 §9.1) ---------------------------------------------------------------------------------


@api.route(
    "GET",
    "/leads/<lead_id>/notes",
    permission="lead_note.read",
    query=S.NotesQuery,
    write=False,
    requirement="NOTE-001",
)
def list_notes(req: Req, lead_id: str):
    lead = _lead(req, lead_id)
    q = req.query
    base = sa.select(LeadNote).where(LeadNote.lead_id == lead.id)
    total = req.session.execute(sa.select(sa.func.count()).select_from(base.subquery())).scalar()
    rows = (
        req.session.execute(
            base.order_by(LeadNote.is_pinned.desc(), LeadNote.created_on.desc(), LeadNote.id.desc())
            .offset((q.page - 1) * q.page_size)
            .limit(q.page_size)
        )
        .scalars()
        .all()
    )
    meta, links = offset_meta(q.page, q.page_size, int(total or 0), f"/api/v1/leads/{lead_id}/notes", q.model_dump())
    return ok([acts.present_note(req.ctx, req.session, n) for n in rows], meta=meta)


@api.route(
    "POST", "/leads/<lead_id>/notes", permission="lead_note.create", body=S.NoteIn, status=201, requirement="NOTE-001"
)
def create_note(req: Req, lead_id: str):
    lead = _lead(req, lead_id)
    note = acts.create_note(req.session, req.ctx, lead, req.body)
    return ok(acts.present_note(req.ctx, req.session, note), status=201)


@api.route(
    "PATCH",
    "/leads/<lead_id>/notes/<note_id>",
    permission="lead_note.update",
    body=S.NotePatch,
    if_match=True,
    requirement="NOTE-002",
)
def patch_note(req: Req, lead_id: str, note_id: str):
    lead = _lead(req, lead_id)
    note = repo.note_visible(req.session, lead, note_id)
    req.require_version(note.version)
    acts.update_note(req.session, req.ctx, note, req.body)
    req.session.flush()
    return ok(acts.present_note(req.ctx, req.session, note))


@api.route(
    "DELETE", "/leads/<lead_id>/notes/<note_id>", permission="lead_note.delete", if_match=True, requirement="NOTE-002"
)
def delete_note(req: Req, lead_id: str, note_id: str):
    lead = _lead(req, lead_id)
    note = repo.note_visible(req.session, lead, note_id)
    req.require_version(note.version)
    acts.delete_note(req.session, req.ctx, note)
    return no_content()


# --- activities (08 §9.2) -----------------------------------------------------------------------------


@api.route(
    "GET",
    "/leads/<lead_id>/activities",
    permission="lead_activity.read",
    query=S.ActivitiesQuery,
    write=False,
    requirement="ACT-001",
)
def list_activities(req: Req, lead_id: str):
    lead = _lead(req, lead_id)
    q = req.query
    stmt = sa.select(LeadActivity).where(LeadActivity.lead_id == lead.id)
    if q.type:
        stmt = stmt.where(LeadActivity.activity_type.in_(csv(q.type)))
    if q.status:
        stmt = stmt.where(LeadActivity.activity_status.in_(csv(q.status)))
    cur = decode_cursor(q.cursor)
    if cur:
        t = clock.parse_rfc3339(cur[0])
        stmt = stmt.where(
            sa.or_(LeadActivity.created_on < t, sa.and_(LeadActivity.created_on == t, LeadActivity.id < cur[1]))
        )
    rows = (
        req.session.execute(stmt.order_by(LeadActivity.created_on.desc(), LeadActivity.id.desc()).limit(q.limit + 1))
        .scalars()
        .all()
    )
    has_more = len(rows) > q.limit
    rows = rows[: q.limit]
    nxt = encode_cursor(clock.to_rfc3339(rows[-1].created_on, micros=True), rows[-1].id) if has_more else None
    return ok(
        [acts.present_activity(req.ctx, req.session, a) for a in rows],
        meta={"limit": q.limit, "next_cursor": nxt, "has_more": has_more},
    )


@api.route(
    "POST",
    "/leads/<lead_id>/activities",
    permission="lead_activity.create",
    body=S.ActivityIn,
    status=201,
    requirement="ACT-001",
)
def create_activity(req: Req, lead_id: str):
    lead = _lead(req, lead_id)
    act = acts.create_activity(req.session, req.ctx, lead, req.body)
    req.session.flush()
    return ok(
        acts.present_activity(req.ctx, req.session, act),
        status=201,
        meta={"lead_next_follow_up_on": clock.to_rfc3339(lead.next_follow_up_on), "lead_version": lead.version},
    )


def _activity(req: Req, lead_id: str, activity_id: str) -> tuple[Lead, LeadActivity]:
    lead = _lead(req, lead_id)
    act = repo.activity_visible(req.session, lead, activity_id)
    return lead, act


@api.route(
    "PATCH",
    "/leads/<lead_id>/activities/<activity_id>",
    permission="lead_activity.update",
    body=S.ActivityPatch,
    if_match=True,
    requirement="ACT-002",
)
def patch_activity(req: Req, lead_id: str, activity_id: str):
    lead, act = _activity(req, lead_id, activity_id)
    req.require_version(act.version)
    acts.update_activity(req.session, req.ctx, lead, act, req.body)
    req.session.flush()
    return ok(
        acts.present_activity(req.ctx, req.session, act),
        meta={"lead_next_follow_up_on": clock.to_rfc3339(lead.next_follow_up_on)},
    )


@api.route(
    "POST",
    "/leads/<lead_id>/activities/<activity_id>/complete",
    permission="lead_activity.update",
    body=S.ActivityComplete,
    if_match=True,
    requirement="ACT-003",
)
def complete_activity(req: Req, lead_id: str, activity_id: str):
    lead, act = _activity(req, lead_id, activity_id)
    req.require_version(act.version)
    acts.complete_activity(req.session, req.ctx, lead, act, req.body)
    req.session.flush()
    return ok(
        acts.present_activity(req.ctx, req.session, act),
        meta={"lead_next_follow_up_on": clock.to_rfc3339(lead.next_follow_up_on)},
    )


@api.route(
    "POST",
    "/leads/<lead_id>/activities/<activity_id>/cancel",
    permission="lead_activity.update",
    body=S.ActivityCancel,
    if_match=True,
    requirement="ACT-003",
)
def cancel_activity(req: Req, lead_id: str, activity_id: str):
    lead, act = _activity(req, lead_id, activity_id)
    req.require_version(act.version)
    acts.cancel_activity(req.session, req.ctx, lead, act, req.body.reason if req.body else None)
    req.session.flush()
    return ok(
        acts.present_activity(req.ctx, req.session, act),
        meta={"lead_next_follow_up_on": clock.to_rfc3339(lead.next_follow_up_on)},
    )


@api.route(
    "DELETE",
    "/leads/<lead_id>/activities/<activity_id>",
    permission="lead_activity.delete",
    if_match=True,
    requirement="ACT-002",
)
def delete_activity(req: Req, lead_id: str, activity_id: str):
    lead, act = _activity(req, lead_id, activity_id)
    req.require_version(act.version)
    acts.delete_activity(req.session, req.ctx, lead, act)
    return no_content()


@api.route(
    "GET",
    "/activities",
    permission="lead_activity.read",
    query=S.MyActivitiesQuery,
    write=False,
    requirement="LEAD-015",
)
def my_activities(req: Req):
    rows, has_more = acts.my_activities(req.session, req.ctx, req.query)
    data = [acts.present_activity(req.ctx, req.session, a, with_lead=lead) for a, lead in rows]
    nxt = None
    if has_more and rows:
        a = rows[-1][0]
        nxt = encode_cursor(clock.to_rfc3339(a.scheduled_on or a.created_on, micros=True), a.id)
    return ok(data, meta={"limit": req.query.limit, "next_cursor": nxt, "has_more": has_more})


# --- assignable users (08 §5.12; owned here because it depends on lead data, PLAT-011) -------------------


@api.route("GET", "/users/assignable", permission="lead.assign", write=False, requirement="LEAD-007")
def assignable(req: Req):
    out = []
    for user in req.session.execute(
        sa.select(User).where(User.user_type == "HUMAN", User.status == "ACTIVE").order_by(User.full_name)
    ).scalars():
        if "lead.read" not in load_grants(req.session, user.id).granted:
            continue
        count = req.session.execute(
            sa.select(sa.func.count())
            .select_from(Lead)
            .where(Lead.assigned_to == user.id, Lead.status.in_(OPEN_STATUSES))
        ).scalar()
        out.append(
            {"id": user.id, "display_name": user.display_name or user.full_name, "open_lead_count": int(count or 0)}
        )
    return ok(out)
