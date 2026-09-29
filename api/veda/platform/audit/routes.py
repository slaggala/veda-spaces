"""Audit log and security event viewers (08 §10, 07 §7, 05 §9.5).

Modules register entity label and visibility resolvers so the platform never
imports module internals (PLAT-011). Lead PII is masked for leads outside the
viewer's ``lead.read`` scope (A-12). Security-event hash and chain columns are
never returned.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Annotated, Any

import sqlalchemy as sa
from pydantic import Field
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.kernel.audit_registry import policy_for
from veda.kernel.dto import Id, Instant, Query, csv
from veda.kernel.errors import ApiError, field_error, not_found
from veda.kernel.http import Api, Req, decode_cursor, encode_cursor, mask_ip, ok
from veda.kernel.ids import SYSTEM_ACTOR_IDS
from veda.platform.auth.models import SecurityEventLog
from veda.platform.identity.models import User
from veda.platform.lookups.service import value_ref

from .models import AuditLog

api = Api("audit", "/api/v1", tags=("audit",))

LOOKUP_FIELDS = frozenset({"project_type_id", "property_type_id", "budget_range_id", "source_id", "lost_reason_id",
                           "outcome_id"})

# entity_type → fn(session, ctx, entity_id) -> (label | None, visible: bool)
ENTITY_RESOLVERS: dict[str, Callable[[Session, Any, str], tuple[str | None, bool]]] = {}


def register_entity(entity_type: str, fn: Callable[[Session, Any, str], tuple[str | None, bool]]) -> None:
    ENTITY_RESOLVERS[entity_type] = fn


def _user_label(s: Session, ctx, user_id: str) -> tuple[str | None, bool]:
    u = s.get(User, user_id, execution_options={"include_deleted": True})
    return (u.full_name if u else None), True


register_entity("app_user", _user_label)


def _actor(s: Session, user_id: str | None) -> dict | None:
    if not user_id:
        return None
    u = s.get(User, user_id, execution_options={"include_deleted": True})
    if u is None:
        return {"id": user_id, "display_name": None}
    return {"id": u.id, "display_name": u.display_name or u.full_name, "is_system": u.id in SYSTEM_ACTOR_IDS}


def _resolve_values(s: Session, values: dict | None) -> dict | None:
    if not values:
        return values
    out = {}
    for k, v in values.items():
        if k in LOOKUP_FIELDS and isinstance(v, str):
            ref = value_ref(s, v)
            out[k] = {"id": v, **ref} if ref else v
        else:
            out[k] = v
    return out


def _mask(values: dict | None, pii: frozenset[str]) -> dict | None:
    if not values:
        return values
    return {k: ("[MASKED]" if k in pii and v is not None else v) for k, v in values.items()}


def present_audit(s: Session, ctx, row: AuditLog, *, full: bool = False) -> dict:
    label, visible = None, True
    anchor_type, anchor_id = row.entity_type, row.entity_id
    if row.parent_entity_type and row.parent_entity_type in ENTITY_RESOLVERS and row.entity_type not in ENTITY_RESOLVERS:
        anchor_type, anchor_id = row.parent_entity_type, row.parent_entity_id
    resolver_fn = ENTITY_RESOLVERS.get(row.entity_type) or ENTITY_RESOLVERS.get(anchor_type)
    if resolver_fn:
        label, visible = resolver_fn(s, ctx, row.entity_id if row.entity_type in ENTITY_RESOLVERS else anchor_id)
    policy = policy_for(row.entity_type)
    pii = policy.pii if policy else frozenset()
    old, new = row.old_value, row.new_value
    if not visible:
        old, new = _mask(old, pii), _mask(new, pii)
        if isinstance(old, dict) and "_snapshot" in old:
            old = {**old, "_snapshot": _mask(old["_snapshot"], pii)}
        label = None
    data = {
        "id": row.id, "entity_type": row.entity_type, "entity_id": row.entity_id,
        "entity_label": label, "action": row.action, "changed_fields": row.changed_fields,
        "old_value": _resolve_values(s, old), "new_value": _resolve_values(s, new),
        "performed_by": _actor(s, row.performed_by), "performed_on": clock.to_rfc3339(row.performed_on),
        "performed_via": row.performed_via, "parent_entity_type": row.parent_entity_type,
        "parent_entity_id": row.parent_entity_id, "transaction_id": row.transaction_id, "request_id": row.request_id,
        "ip_address": mask_ip(row.ip_address), "reason": row.reason, "payload_schema": row.payload_schema,
    }
    if full:
        data["user_agent"] = row.user_agent
        data["session_id"] = row.session_id
        data["ip_address"] = row.ip_address if visible else mask_ip(row.ip_address)
    return data


class AuditQuery(Query):
    entity_type: str | None = None
    entity_id: Id | None = None
    include_children: bool = False
    action: str | None = None
    performed_by: str | None = None
    performed_via: str | None = None
    from_: Instant | None = Field(default=None, alias="from")
    to: Instant | None = None
    transaction_id: Id | None = None
    request_id: str | None = None
    cursor: str | None = None
    limit: Annotated[int, Field(ge=1, le=200)] = 50


def audit_query(q: AuditQuery):
    stmt = sa.select(AuditLog)
    if q.entity_id:
        cond = AuditLog.entity_id == q.entity_id
        if q.include_children:
            cond = sa.or_(cond, AuditLog.parent_entity_id == q.entity_id)
        stmt = stmt.where(cond)
    if q.entity_type:
        types = csv(q.entity_type)
        if q.entity_id and q.include_children:
            stmt = stmt.where(sa.or_(AuditLog.entity_type.in_(types), AuditLog.parent_entity_type.in_(types)))
        else:
            stmt = stmt.where(AuditLog.entity_type.in_(types))
    if q.action:
        stmt = stmt.where(AuditLog.action.in_(csv(q.action)))
    if q.performed_by:
        if q.performed_by == "system":
            stmt = stmt.where(AuditLog.performed_by.in_(sorted(SYSTEM_ACTOR_IDS)))
        else:
            from veda.kernel.ids import is_valid_id

            if not is_valid_id(q.performed_by):
                raise ApiError(422, "INVALID_ID", "performed_by is not a canonical id.",
                               errors=[field_error("performed_by", "INVALID_ID", "Expected an id or 'system'.")])
            stmt = stmt.where(AuditLog.performed_by == q.performed_by)
    if q.performed_via:
        stmt = stmt.where(AuditLog.performed_via.in_(csv(q.performed_via)))
    if q.from_:
        stmt = stmt.where(AuditLog.performed_on >= q.from_)
    if q.to:
        stmt = stmt.where(AuditLog.performed_on < q.to)
    if q.transaction_id:
        stmt = stmt.where(AuditLog.transaction_id == q.transaction_id)
    if q.request_id:
        stmt = stmt.where(AuditLog.request_id == q.request_id)
    cur = decode_cursor(q.cursor)
    if cur:
        t = clock.parse_rfc3339(cur[0])
        stmt = stmt.where(sa.or_(AuditLog.performed_on < t, sa.and_(AuditLog.performed_on == t, AuditLog.id < cur[1])))
    return stmt.order_by(AuditLog.performed_on.desc(), AuditLog.id.desc()).limit(q.limit + 1)


def cursor_page(rows: list, limit: int, time_attr: str) -> tuple[list, dict]:
    has_more = len(rows) > limit
    rows = rows[:limit]
    nxt = encode_cursor(clock.to_rfc3339(getattr(rows[-1], time_attr), micros=True), rows[-1].id) if has_more else None
    return rows, {"limit": limit, "next_cursor": nxt, "has_more": has_more}


@api.route("GET", "/audit-logs", permission="audit.read", query=AuditQuery, write=False, requirement="AUDIT-008")
def list_audit(req: Req):
    rows = req.session.execute(audit_query(req.query)).scalars().all()
    rows, meta = cursor_page(rows, req.query.limit, "performed_on")
    return ok([present_audit(req.session, req.ctx, r) for r in rows], meta=meta)


@api.route("GET", "/audit-logs/<audit_id>", permission="audit.read", write=False, requirement="AUDIT-008")
def get_audit(req: Req, audit_id: str):
    row = req.session.get(AuditLog, audit_id)
    if row is None:
        raise not_found()
    return ok(present_audit(req.session, req.ctx, row, full=True))


# --- security events (SEVT-005, owner Decision 1) ----------------------------------------------

class SecurityQuery(Query):
    subject_user_id: Id | None = None
    event_type: str | None = None
    event_category: str | None = None
    outcome: str | None = None
    severity: str | None = None
    ip: str | None = None
    from_: Instant | None = Field(default=None, alias="from")
    to: Instant | None = None
    cursor: str | None = None
    limit: Annotated[int, Field(ge=1, le=200)] = 50


def present_event(s: Session, row: SecurityEventLog) -> dict:
    # email_attempted_hash, chain_seq, prev_hash, chain_key_label and row_hash are never returned (SEVT-005).
    return {
        "id": row.id, "event_type": row.event_type, "event_category": row.event_category, "outcome": row.outcome,
        "severity": row.severity, "subject_user": _actor(s, row.subject_user_id), "actor": _actor(s, row.created_by),
        "failure_reason": row.failure_reason, "permission_code": row.permission_code,
        "target_entity_type": row.target_entity_type, "target_entity_id": row.target_entity_id,
        "occurred_on": clock.to_rfc3339(row.occurred_on), "ip_address": row.ip_address, "user_agent": row.user_agent,
        "request_id": row.request_id, "session_id": row.session_id, "detail": row.detail,
    }


@api.route("GET", "/security-events", permission="security_event.read", query=SecurityQuery, write=False,
           requirement="SEVT-005")
def list_security_events(req: Req):
    q = req.query
    filtered = any([q.subject_user_id, q.event_type, q.event_category, q.outcome, q.severity, q.ip])
    if not filtered and q.from_ and (q.to or clock.now()) - q.from_ > timedelta(days=31):
        raise ApiError(422, "INVALID_QUERY_PARAM", "Unfiltered queries are limited to 31 days.",
                       errors=[field_error("from", "INVALID_QUERY_PARAM", "Narrow the range or add a filter.")])
    stmt = sa.select(SecurityEventLog)
    if q.subject_user_id:
        stmt = stmt.where(SecurityEventLog.subject_user_id == q.subject_user_id)
    for field, col in (("event_type", SecurityEventLog.event_type), ("event_category", SecurityEventLog.event_category),
                       ("outcome", SecurityEventLog.outcome), ("severity", SecurityEventLog.severity)):
        value = getattr(q, field)
        if value:
            stmt = stmt.where(col.in_(csv(value)))
    if q.ip:
        stmt = stmt.where(SecurityEventLog.ip_address == q.ip)
    if q.from_:
        stmt = stmt.where(SecurityEventLog.occurred_on >= q.from_)
    elif not filtered:
        stmt = stmt.where(SecurityEventLog.occurred_on >= clock.now() - timedelta(days=31))
    if q.to:
        stmt = stmt.where(SecurityEventLog.occurred_on < q.to)
    cur = decode_cursor(q.cursor)
    if cur:
        t = clock.parse_rfc3339(cur[0])
        stmt = stmt.where(sa.or_(SecurityEventLog.occurred_on < t,
                                 sa.and_(SecurityEventLog.occurred_on == t, SecurityEventLog.id < cur[1])))
    rows = req.session.execute(stmt.order_by(SecurityEventLog.occurred_on.desc(), SecurityEventLog.id.desc())
                               .limit(q.limit + 1)).scalars().all()
    rows, meta = cursor_page(rows, q.limit, "occurred_on")
    return ok([present_event(req.session, r) for r in rows], meta=meta)


@api.route("GET", "/security-events/<event_id>", permission="security_event.read", write=False, requirement="SEVT-005")
def get_security_event(req: Req, event_id: str):
    row = req.session.get(SecurityEventLog, event_id)
    if row is None:
        raise not_found()
    return ok(present_event(req.session, row))
