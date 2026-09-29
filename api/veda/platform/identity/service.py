"""User presentation and profile edits (03 §4.1, 08 §4.4, §5)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.kernel.dto import mask_email, parse_phone
from veda.kernel.errors import ApiError, field_error
from veda.platform.rbac.models import Role, UserRole
from veda.platform.rbac.resolver import load_grants

from .models import User


def roles_of(s: Session, user_id: str) -> list[dict]:
    rows = s.execute(
        sa.select(Role.id, Role.code, Role.name).join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id).order_by(Role.sort_order, Role.name)
    ).all()
    return [{"id": r.id, "code": r.code, "name": r.name} for r in rows]


def apply_profile(s: Session, user: User, body) -> None:
    """Profile fields only: full_name, display_name, phone, timezone, locale (08 §5.4)."""
    provided = body.provided()
    if "full_name" in provided:
        if body.full_name is None:
            raise ApiError(422, "VALIDATION_FAILED", "Name is required.",
                           errors=[field_error("full_name", "REQUIRED", "Name is required.")])
        user.full_name = body.full_name
    if "display_name" in provided:
        user.display_name = body.display_name
    if "phone" in provided:
        if body.phone is None:
            user.phone_e164 = None
        else:
            try:
                user.phone_e164 = parse_phone(body.phone)
            except ValueError:
                raise ApiError(422, "VALIDATION_FAILED", "1 field is invalid.",
                               errors=[field_error("phone", "INVALID_PHONE", "Enter a valid phone number.")]) from None
    if "timezone" in provided and body.timezone:
        user.timezone = body.timezone
    if "locale" in provided and body.locale:
        user.locale = body.locale


def me_payload(s: Session, ctx) -> dict:
    from veda.platform.auth.mfa import status as mfa_status
    from veda.platform.auth.service import pending_email_change

    user = ctx.user
    res = ctx.res
    now = clock.now()
    mfa = mfa_status(s, user)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "display_name": user.display_name,
        "phone": user.phone_e164,
        "timezone": user.timezone,
        "locale": user.locale,
        "status": user.status,
        "protection_level": user.protection_level,
        "roles": roles_of(s, user.id),
        "authz_version": user.authz_version,
        "permissions": dict(sorted(res.effective.items())),
        "suspended_permissions": [{"code": c, "reason": r} for c, r in sorted(res.suspended.items())],
        "session": {
            "id": ctx.session.id,
            "type": ctx.session.session_type,
            "auth_methods": ctx.session.methods,
            "mfa_verified_on": clock.to_rfc3339(ctx.session.mfa_verified_on),
            "cooling_off_until": clock.to_rfc3339(user.security_cooling_off_until)
            if user.security_cooling_off_until and user.security_cooling_off_until > now else None,
        },
        "mfa": {"required": mfa["required"], "required_by": mfa["required_by"], "enrolled": mfa["factor"] is not None},
        "email_change": pending_email_change(s, user),
        "must_change_password": bool(ctx.claims.get("pwd_change")),
        "version": user.version,
    }


def mfa_summary(s: Session, user_id: str) -> dict:
    from veda.platform.auth.models import UserMfaFactor

    grants = load_grants(s, user_id)
    enrolled = bool(s.execute(sa.select(sa.func.count()).select_from(UserMfaFactor).where(
        UserMfaFactor.user_id == user_id, UserMfaFactor.status == "ACTIVE")).scalar())
    return {"required": grants.mfa_required, "enrolled": enrolled, "required_by": grants.mfa_required_by}


def user_list_item(s: Session, user: User, *, grants=None) -> dict:
    grants = grants or load_grants(s, user.id)
    from veda.platform.auth.models import UserMfaFactor

    enrolled = bool(s.execute(sa.select(sa.func.count()).select_from(UserMfaFactor).where(
        UserMfaFactor.user_id == user.id, UserMfaFactor.status == "ACTIVE")).scalar())
    return {
        "id": user.id,
        "email": user.email,
        "email_change_pending": user.proposed_email is not None,
        "full_name": user.full_name,
        "display_name": user.display_name,
        "status": user.status,
        "protection_level": user.protection_level,
        "is_privileged": grants.holds_sensitive,
        "roles": roles_of(s, user.id),
        "mfa": {"required": grants.mfa_required, "enrolled": enrolled},
        "last_login_on": clock.to_rfc3339(user.last_login_on),
        "created_on": clock.to_rfc3339(user.created_on),
        "is_deleted": user.is_deleted,
        "version": user.version,
    }


def user_detail(s: Session, user: User) -> dict:
    from veda.platform.auth.models import UserSession
    from veda.platform.auth.service import credential_for, pending_email_change
    from veda.platform.rbac.models import AdminApprovalRequest

    grants = load_grants(s, user.id)
    item = user_list_item(s, user, grants=grants)
    cred = credential_for(s, user.id)
    now = clock.now()
    pending = s.execute(sa.select(AdminApprovalRequest.id, AdminApprovalRequest.action_type).where(
        AdminApprovalRequest.target_user_id == user.id,
        AdminApprovalRequest.status.in_(("PENDING", "APPROVED")))).all()
    active_sessions = s.execute(sa.select(sa.func.count()).select_from(UserSession).where(
        UserSession.user_id == user.id, UserSession.revoked_on.is_(None), UserSession.absolute_expires_on > now)).scalar()
    item.update({
        "phone": user.phone_e164,
        "timezone": user.timezone,
        "locale": user.locale,
        "user_type": user.user_type,
        "email_verified_on": clock.to_rfc3339(user.email_verified_on),
        "email_change": pending_email_change(s, user),
        "security_cooling_off_until": clock.to_rfc3339(user.security_cooling_off_until)
        if user.security_cooling_off_until and user.security_cooling_off_until > now else None,
        "throttled_until": clock.to_rfc3339(cred.locked_until) if cred and cred.locked_until and cred.locked_until > now else None,
        "must_change_password": bool(cred and cred.must_change_password),
        "mfa": {**item["mfa"], "required_by": grants.mfa_required_by},
        "pending_approvals": [{"id": r.id, "action_type": r.action_type} for r in pending],
        "active_session_count": int(active_sessions or 0),
        "status_changed_on": clock.to_rfc3339(user.status_changed_on),
        "updated_on": clock.to_rfc3339(user.updated_on),
        "created_by": user.created_by,
        "updated_by": user.updated_by,
    })
    return item


def masked(email: str | None) -> str | None:
    return mask_email(email)
