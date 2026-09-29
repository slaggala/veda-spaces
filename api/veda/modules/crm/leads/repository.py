"""Lead repository: soft-delete filter, scope filter, search (02 §3.1, 06 §4, §8 Layer 3).

Every list and aggregate ANDs the actor's scope predicate; there is no
unscoped API query path. A lead is "owned" when ``assigned_to = actor`` or
``created_by = actor``.
"""

from __future__ import annotations

import unicodedata

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError, not_found

from .models import Lead, LeadActivity, LeadNote

HIDDEN_SPAM = ("SUSPECTED", "CONFIRMED_SPAM")


def own_predicate(actor_id: str):
    return sa.or_(Lead.assigned_to == actor_id, Lead.created_by == actor_id)


def scope_predicate(scope: str | None, actor_id: str):
    if scope == "ALL":
        return sa.true()
    if scope == "OWN":
        return own_predicate(actor_id)
    return sa.false()


def is_owner(lead: Lead, actor_id: str) -> bool:
    return lead.assigned_to == actor_id or lead.created_by == actor_id


def in_scope(lead: Lead, scope: str | None, actor_id: str) -> bool:
    return scope == "ALL" or (scope == "OWN" and is_owner(lead, actor_id))


def visible_select(ctx, *, include_deleted: bool = False, deleted_only: bool = False):
    stmt = sa.select(Lead).where(scope_predicate(ctx.scope("lead.read"), ctx.user.id))
    if deleted_only:
        stmt = stmt.where(Lead.is_deleted == sa.true())
    if include_deleted or deleted_only:
        stmt = stmt.execution_options(include_deleted=True)
    return stmt


def get_visible(s: Session, ctx, lead_id: str, *, include_deleted: bool = False) -> Lead:
    stmt = visible_select(ctx, include_deleted=include_deleted).where(Lead.id == lead_id)
    lead = s.execute(stmt).scalar_one_or_none()
    if lead is None:
        raise not_found()
    return lead


def require_scope(ctx, lead: Lead, permission: str) -> None:
    """Visible lead but action outside the permission's scope → 403 (the lead is visible, 06 §8)."""
    from veda.platform.auth.request_auth import deny

    scope = ctx.scope(permission)
    if scope is None:
        deny(ctx, permission)
    if not in_scope(lead, scope, ctx.user.id):
        raise ApiError(403, "PERMISSION_DENIED", f"Requires {permission} for this lead.", extra={"permission": permission})


def fold(value: str | None) -> str:
    return unicodedata.normalize("NFKC", value or "").casefold()


def build_search_text(lead: Lead) -> str:
    """Engine-independent search column (A-03)."""
    digits = "".join(ch for ch in (lead.phone or "") if ch.isdigit())
    raw_digits = "".join(ch for ch in (lead.phone_raw or "") if ch.isdigit())
    parts = [lead.name, lead.email_normalized, digits, raw_digits, lead.lead_number, lead.public_reference,
             (lead.public_reference or "").replace("-", ""), lead.city, lead.locality]
    return " ".join(fold(p) for p in parts if p)


def search_condition(q: str):
    tokens = [fold(t) for t in q.split() if len(t.strip()) >= 2]
    if not tokens:
        raise ApiError(422, "INVALID_QUERY_PARAM", "Search terms need at least 2 characters.")
    conds = []
    for token in tokens:
        escaped = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conds.append(Lead.search_text.like(f"%{escaped}%", escape="\\"))
    return sa.and_(*conds)


def note_visible(s: Session, lead: Lead, note_id: str) -> LeadNote:
    note = s.get(LeadNote, note_id)
    if note is None or note.lead_id != lead.id:
        raise not_found()
    return note


def activity_visible(s: Session, lead: Lead, activity_id: str) -> LeadActivity:
    act = s.get(LeadActivity, activity_id)
    if act is None or act.lead_id != lead.id:
        raise not_found()
    return act
