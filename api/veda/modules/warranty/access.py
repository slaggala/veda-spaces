"""Warranty and service access: the flag, scope and locking (WSV-020).

Staff routes answer 404 before authentication unless VEDA_WARRANTY_SERVICE_ENABLED and the Project Lifecycle's flag
are on; customer routes also need the portal's. Every ``warranty.*`` code is scoped: ALL reaches everything; OWN reaches
a request owned by the actor, or a request or entitlement of a project whose team the actor is an active member of. A
row outside the read scope answers 404 (its existence is not disclosed); a visible row whose action is out of scope
answers 403. Every write takes the request's (or, for submission and registration, the project's) row lock and
re-reads before deciding, and compares If-Match with the re-read version.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel.errors import ApiError, not_found
from veda.kernel.http import check_version

from .models import ServiceRequest, WarrantyEntitlement


def staff_enabled() -> bool:
    cfg = settings()
    return bool(cfg.warranty_service_enabled and cfg.project_lifecycle_enabled)


def customer_enabled() -> bool:
    return staff_enabled() and bool(settings().customer_portal_enabled)


def _team(user_id: str):
    from veda.modules.project.access import member_project_ids

    return member_project_ids(user_id)


def request_condition(ctx, code: str) -> sa.ColumnElement[bool]:
    scope = ctx.scope(code)
    if scope == "ALL":
        return sa.true()
    if scope == "OWN":
        return sa.or_(ServiceRequest.owner_user_id == ctx.user.id, ServiceRequest.project_id.in_(_team(ctx.user.id)))
    return sa.false()


def entitlement_condition(ctx, code: str) -> sa.ColumnElement[bool]:
    scope = ctx.scope(code)
    if scope == "ALL":
        return sa.true()
    if scope == "OWN":
        return WarrantyEntitlement.project_id.in_(_team(ctx.user.id))
    return sa.false()


def _deny(ctx, code: str) -> None:
    from veda.platform.auth.request_auth import deny

    deny(ctx, code)


def visible_request(s: Session, ctx, request_id: str, code: str = "warranty.service.view") -> ServiceRequest:
    if ctx.scope(code) is None:
        _deny(ctx, code)
    r = s.execute(sa.select(ServiceRequest).where(ServiceRequest.id == request_id, ServiceRequest.is_deleted == sa.false(),
                                                  request_condition(ctx, code))).scalar_one_or_none()  # fmt: skip
    if r is None:
        raise not_found()
    return r


def can(s: Session, ctx, r: ServiceRequest, code: str) -> bool:
    scope = ctx.scope(code)
    if scope == "ALL":
        return True
    if scope != "OWN":
        return False
    if r.owner_user_id == ctx.user.id:
        return True
    from veda.modules.project.access import is_member

    return is_member(s, r.project_id, ctx.user.id)


def require(s: Session, ctx, r: ServiceRequest, code: str) -> None:
    if ctx.scope(code) is None:
        _deny(ctx, code)
    if not can(s, ctx, r, code):
        raise ApiError(403, "PERMISSION_DENIED", f"Requires {code} on this request.", extra={"permission": code})


def lock(s: Session, r: ServiceRequest) -> ServiceRequest:
    if s.get_bind().dialect.name == "postgresql":
        s.execute(sa.select(ServiceRequest.id).where(ServiceRequest.id == r.id).with_for_update())
    s.refresh(r)
    return r


def lead_open(s: Session, lead_id: str) -> None:
    from veda.modules.crm.leads.models import Lead

    lead = s.get(Lead, lead_id)
    if lead is None or lead.anonymized_on is not None:
        raise ApiError(409, "INVALID_STATE", "This customer record was erased; the request can no longer change.")


def for_write(s: Session, ctx, r: ServiceRequest, code: str, if_match: int | None) -> ServiceRequest:
    require(s, ctx, r, code)
    lock(s, r)
    lead_open(s, r.lead_id)
    check_version(if_match, r.version)
    return r


def state(r: ServiceRequest, *allowed: str) -> None:
    if r.status not in allowed:
        raise ApiError(409, "INVALID_STATE", f"Request {r.request_number} is {r.status.lower().replace('_', ' ')}; "
                       "this cannot be done now.", extra={"status": r.status})  # fmt: skip
