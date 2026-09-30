"""User administration (08 §5, 06 §7, ADR-010).

Security-sensitive attributes change only through dedicated operations with
their own permission and guards; generic profile edits cannot touch them.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db, outbox
from veda.kernel.dto import normalize_email, parse_phone
from veda.kernel.errors import ApiError, field_error, not_found
from veda.kernel.ids import SYSTEM_ACTOR_IDS
from veda.platform.auth import mfa as mfa_flows
from veda.platform.auth import security_events, throttle
from veda.platform.auth import service as auth_service
from veda.platform.auth.models import MfaChallenge, UserActionToken
from veda.platform.auth.request_auth import AuthContext, record_sensitive_action, require_step_up
from veda.platform.identity.models import User, UserCredential

from . import governance, guards, registry, resolver
from .models import Permission, Role, UserPermission, UserRole


def load_target(s: Session, user_id: str, *, include_deleted: bool = False) -> User:
    user = s.get(User, user_id, execution_options={"include_deleted": include_deleted})
    if user is None or user.user_type != "HUMAN" or (user.is_deleted and not include_deleted):
        raise not_found()
    return user


def _account_control_preamble(
    ctx: AuthContext, target: User, code: str, s: Session, *, step_up: bool = True, self_allowed: bool = False
) -> None:
    if not self_allowed:
        guards.g3_not_self(ctx.user.id, target.id)
    guards.g11_not_founder(target)
    guards.g9_not_stronger(s, ctx.res, target.id)
    if step_up:
        require_step_up(ctx)


# --- invite (05 §8.4) -------------------------------------------------------------------------


def invite(s: Session, ctx: AuthContext, body) -> User:
    email_norm = normalize_email(body.email)
    if auth_service.email_in_use(s, email_norm):
        raise ApiError(
            409,
            "DUPLICATE",
            "A user with this email already exists.",
            errors=[field_error("email", "DUPLICATE", "A user with this email already exists.")],
        )
    role_ids = list(dict.fromkeys(body.role_ids or []))
    if role_ids and not ctx.has("user.role.manage"):
        from veda.platform.auth.request_auth import deny

        deny(ctx, "user.role.manage")
    roles = []
    for rid in role_ids:
        role = s.get(Role, rid)
        if role is None:
            raise ApiError(
                422,
                "VALIDATION_FAILED",
                "Unknown role.",
                errors=[field_error("role_ids", "INVALID_ID", "Unknown role.")],
            )
        guards.g13_role(role, None)
        if not role.is_assignable:
            raise ApiError(
                422,
                "VALIDATION_FAILED",
                "Role is not assignable.",
                errors=[field_error("role_ids", "NOT_ASSIGNABLE", "This role can't be assigned.")],
            )
        guards.g2_can_use_role(s, ctx.res, rid)
        roles.append(role)
    if roles and any(registry.sensitivity(c) for r in roles for c in guards.role_grants(s, r.id)):
        require_step_up(ctx)
    now = db.tx_time(s)
    phone = None
    if body.phone:
        try:
            phone = parse_phone(body.phone)
        except ValueError:
            raise ApiError(
                422,
                "VALIDATION_FAILED",
                "1 field is invalid.",
                errors=[field_error("phone", "INVALID_PHONE", "Enter a valid phone number.")],
            ) from None
    user = User(
        email=body.email.strip(),
        email_normalized=email_norm,
        full_name=body.full_name,
        display_name=body.display_name,
        phone_e164=phone,
        user_type="HUMAN",
        status="INVITED",
        status_changed_on=now,
        timezone=body.timezone or "Asia/Kolkata",
        locale="en-IN",
        protection_level="STANDARD",
        mfa_required=False,
        authz_version=1,
    )
    s.add(user)
    s.flush()
    s.add(UserCredential(user_id=user.id, password_hash=None, must_change_password=False, failed_login_count=0))
    for role in roles:
        s.add(UserRole(user_id=user.id, role_id=role.id, reason="Invitation"))
    s.flush()
    _send_invite(s, user)
    for role in roles:
        if any(registry.sensitivity(c) for c in guards.role_grants(s, role.id)):
            record_sensitive_action(
                s, ctx, "user.role.manage", action="invite_with_role", target=("role", role.id), subject_user_id=user.id
            )
    return user


def _send_invite(s: Session, user: User) -> None:
    sensitive = resolver.load_grants(s, user.id).holds_sensitive
    ttl = auth_service.TOKEN_TTLS["INVITE_SENSITIVE" if sensitive else "INVITE"]
    auth_service.invalidate_action_tokens(s, user.id, ("INVITE",))
    # A new invitation supersedes every enrollment context minted from an earlier link (IR-21).
    auth_service.invalidate_enrollment(s, user.id)
    tok, _ = auth_service.create_action_token(s, user, "INVITE", ttl=ttl)
    s.flush()
    outbox.enqueue(s, "user.invited", "app_user", user.id, user_id=user.id, token_id=tok.id)
    security_events.record(s, "INVITE_SENT", "SUCCESS", subject_user_id=user.id)


def resend_invite(s: Session, ctx: AuthContext, target: User) -> None:
    guards.g9_not_stronger(s, ctx.res, target.id)
    if target.status != "INVITED":
        raise ApiError(409, "INVALID_STATE", "Only invited users can be re-sent an invitation.")
    _send_invite(s, target)


# --- profile (RBAC-019) ---------------------------------------------------------------------------


def update_profile(s: Session, ctx: AuthContext, target: User, body) -> None:
    from veda.platform.identity.service import apply_profile

    if target.id == ctx.user.id:
        raise ApiError(403, "SELF_MODIFICATION_DENIED", "Edit your own profile under Profile.")
    apply_profile(s, target, body)


# --- status, unlock, delete, restore ----------------------------------------------------------------


def _disable_effects(s: Session, target: User) -> None:
    auth_service.revoke_all_sessions(s, target.id, "USER_DISABLED")
    now = db.tx_time(s)
    for tok in s.execute(
        sa.select(UserActionToken).where(
            UserActionToken.user_id == target.id,
            UserActionToken.used_on.is_(None),
            UserActionToken.invalidated_on.is_(None),
        )
    ).scalars():
        tok.invalidated_on = now
    for ch in s.execute(
        sa.select(MfaChallenge).where(
            MfaChallenge.user_id == target.id, MfaChallenge.completed_on.is_(None), MfaChallenge.expires_on > now
        )
    ).scalars():
        ch.expires_on = now
    if target.proposed_email:
        auth_service.clear_proposal(s, target)


def apply_status(s: Session, target: User, status: str, *, reason: str | None = None) -> None:
    """Effect of a status change; shared with FOUNDER_STATUS_CHANGE (06 §7.2.2)."""
    now = db.tx_time(s)
    if status == "UNLOCK":
        unlock_effects(s, target)
        return
    if status == "DELETE":
        target.status = "DISABLED"
        target.status_changed_on = now
        _disable_effects(s, target)
        target.is_deleted = True
        resolver.bump_authz_version(target)
        return
    if status == "DISABLED":
        if target.status == "DISABLED":
            raise ApiError(409, "INVALID_STATE", "The user is already deactivated.")
        target.status = "DISABLED"
        target.status_changed_on = now
        _disable_effects(s, target)
    elif status == "ACTIVE":
        if target.status in ("ACTIVE", "INVITED"):
            raise ApiError(409, "INVALID_STATE", "The user is not deactivated.")
        cred = auth_service.credential_for(s, target.id)
        target.status = "ACTIVE" if (cred and cred.password_hash and target.email_verified_on) else "INVITED"
        target.status_changed_on = now
    resolver.bump_authz_version(target)


def unlock_effects(s: Session, target: User) -> None:
    cred = auth_service.credential_for(s, target.id)
    if cred is not None:
        cred.locked_until = None
        cred.failed_login_count = 0
        cred.failed_window_started_on = None
    throttle.clear_account(target.id)
    security_events.record(s, "ACCOUNT_UNTHROTTLED", "SUCCESS", subject_user_id=target.id, detail={"scope": "admin"})


def change_status(s: Session, ctx: AuthContext, target: User, status: str, reason: str) -> None:
    _account_control_preamble(ctx, target, "user.status.manage", s)
    inv = guards.InvariantGuard(s)
    apply_status(s, target, status, reason=reason)
    inv.check()
    record_sensitive_action(
        s,
        ctx,
        "user.status.manage",
        action=f"status:{status}",
        target=("app_user", target.id),
        subject_user_id=target.id,
    )


def unlock(s: Session, ctx: AuthContext, target: User) -> None:
    _account_control_preamble(ctx, target, "user.status.manage", s)
    unlock_effects(s, target)
    record_sensitive_action(
        s, ctx, "user.status.manage", action="unlock", target=("app_user", target.id), subject_user_id=target.id
    )


def delete_user(s: Session, ctx: AuthContext, target: User, reason: str) -> None:
    if target.id in SYSTEM_ACTOR_IDS:
        raise ApiError(409, "SYSTEM_OBJECT", "System users cannot be deleted.")
    _account_control_preamble(ctx, target, "user.delete", s)
    inv = guards.InvariantGuard(s)
    apply_status(s, target, "DELETE", reason=reason)
    inv.check()
    record_sensitive_action(
        s, ctx, "user.delete", action="delete", target=("app_user", target.id), subject_user_id=target.id
    )


def restore_user(s: Session, ctx: AuthContext, target: User) -> None:
    """Restore a deleted STANDARD account (returns DISABLED). A deleted Founder keeps FOUNDER protection and is
    restored only through FOUNDER_STATUS_CHANGE status=RESTORE with a second eligible Founder (OD-2, RR-02)."""
    if not target.is_deleted:
        raise ApiError(409, "INVALID_STATE", "The user is not deleted.")
    guards.g3_not_self(ctx.user.id, target.id)
    if target.protection_level == "FOUNDER":
        security_events.defer(
            "FOUNDER_GOVERNANCE_BYPASS_BLOCKED",
            "BLOCKED",
            subject_user_id=target.id,
            permission_code="user.restore",
            target=("app_user", target.id),
            detail={"action": "restore"},
        )
    guards.g11_not_founder(target)
    guards.g9_not_stronger(s, ctx.res, target.id)
    restore_effects(s, target)
    record_sensitive_action(
        s, ctx, "user.restore", action="restore", target=("app_user", target.id), subject_user_id=target.id
    )


def restore_effects(s: Session, target: User) -> None:
    """Shared with FOUNDER_STATUS_CHANGE status=RESTORE: the account returns DISABLED and must be reactivated."""
    if auth_service.email_in_use(s, target.email_normalized, exclude_user_id=target.id):
        raise ApiError(409, "DUPLICATE", "Another live user has this email.")
    target.is_deleted = False
    target.status = "DISABLED"
    target.status_changed_on = db.tx_time(s)
    resolver.bump_authz_version(target)


def send_password_reset(s: Session, ctx: AuthContext, target: User) -> None:
    guards.g3_not_self(ctx.user.id, target.id)
    guards.g11_not_founder(target)
    guards.g9_not_stronger(s, ctx.res, target.id)
    if target.status != "ACTIVE":
        raise ApiError(409, "INVALID_STATE", "Only active users can be sent a reset link.")
    auth_service.invalidate_action_tokens(s, target.id, ("PASSWORD_RESET",))
    tok, _ = auth_service.create_action_token(
        s, target, "PASSWORD_RESET", ttl=auth_service.TOKEN_TTLS["PASSWORD_RESET"]
    )
    s.flush()
    outbox.enqueue(s, "auth.password_reset_requested", "app_user", target.id, user_id=target.id, token_id=tok.id)
    security_events.record(
        s, "PASSWORD_RESET_REQUESTED", "SUCCESS", subject_user_id=target.id, detail={"stage": "admin"}
    )


def revoke_sessions(s: Session, ctx: AuthContext, target: User, reason: str) -> int:
    _account_control_preamble(ctx, target, "user.session.revoke", s)
    count = auth_service.revoke_all_sessions(s, target.id, "ADMIN_REVOKE")
    record_sensitive_action(
        s,
        ctx,
        "user.session.revoke",
        action="revoke_sessions",
        target=("app_user", target.id),
        subject_user_id=target.id,
    )
    return count


# --- email change (USER-007) --------------------------------------------------------------------------


def admin_email_change(s: Session, ctx: AuthContext, target: User, new_email: str, reason: str) -> dict:
    _account_control_preamble(ctx, target, "user.email.change", s)
    email_norm = normalize_email(new_email)
    if email_norm == target.email_normalized:
        raise ApiError(422, "SAME_AS_CURRENT", "That is already the sign-in email.")
    if auth_service.email_in_use(s, email_norm, exclude_user_id=target.id):
        raise ApiError(409, "DUPLICATE", "That email is in use.")
    record_sensitive_action(
        s, ctx, "user.email.change", action="email_change", target=("app_user", target.id), subject_user_id=target.id
    )
    if resolver.is_privileged(s, target.id):
        req = governance.request_standard(s, ctx, target, "EMAIL_CHANGE", reason, {"new_email": new_email.strip()})
        return {"status": "APPROVAL_REQUIRED", "approval_id": req.id}
    return auth_service.start_email_change(s, target, new_email, requested_by=ctx.user.id)


# --- MFA administration (05 §11.7) --------------------------------------------------------------------


def mfa_reset(s: Session, ctx: AuthContext, target: User, reason: str) -> dict | None:
    _account_control_preamble(ctx, target, "user.mfa.reset", s)
    record_sensitive_action(
        s, ctx, "user.mfa.reset", action="mfa_reset", target=("app_user", target.id), subject_user_id=target.id
    )
    if resolver.is_privileged(s, target.id):
        req = governance.request_standard(s, ctx, target, "MFA_RESET", reason, {})
        return {"status": "APPROVAL_REQUIRED", "approval_id": req.id}
    security_events.record(s, "ADMIN_MFA_RESET_REQUESTED", "SUCCESS", subject_user_id=target.id)
    mfa_flows.admin_reset(s, target)
    security_events.record(s, "ADMIN_MFA_RESET_COMPLETED", "SUCCESS", subject_user_id=target.id)
    outbox.enqueue(s, "auth.mfa_reset_completed", "app_user", target.id, user_id=target.id)
    return None


def set_mfa_requirement(s: Session, ctx: AuthContext, target: User, required: bool, reason: str) -> None:
    _account_control_preamble(ctx, target, "user.mfa.require", s)
    if target.mfa_required != required:
        target.mfa_required = required
        resolver.bump_authz_version(target)
    record_sensitive_action(
        s,
        ctx,
        "user.mfa.require",
        action=f"mfa_required:{required}",
        target=("app_user", target.id),
        subject_user_id=target.id,
    )


# --- roles on users (RBAC-009) ---------------------------------------------------------------------------


def set_roles(s: Session, ctx: AuthContext, target: User, items: list, reason: str) -> dict:
    guards.g3_not_self(ctx.user.id, target.id)
    for item in items:
        guards.reject_time_bound(item.valid_from, item.valid_until)
    wanted = list(dict.fromkeys(i.role_id for i in items))
    current = {ur.role_id: ur for ur in s.execute(sa.select(UserRole).where(UserRole.user_id == target.id)).scalars()}
    added = [rid for rid in wanted if rid not in current]
    removed = [rid for rid in current if rid not in wanted]
    for rid in added + removed:
        role = s.get(Role, rid)
        if role is None:
            raise ApiError(
                422, "VALIDATION_FAILED", "Unknown role.", errors=[field_error("roles", "INVALID_ID", "Unknown role.")]
            )
        guards.g13_role(role, target.id)
    if target.protection_level == "FOUNDER":
        guards.g13_block(target.id, target=("app_user", target.id))
    guards.g9_not_stronger(s, ctx.res, target.id)
    for rid in added:
        role = s.get(Role, rid)
        if not role.is_assignable:
            raise ApiError(
                422,
                "VALIDATION_FAILED",
                "Role is not assignable.",
                errors=[field_error("roles", "NOT_ASSIGNABLE", "This role can't be assigned.")],
            )
        guards.g2_can_use_role(s, ctx.res, rid)
    for rid in removed:
        guards.g2_can_use_role(s, ctx.res, rid)
    require_step_up(ctx)
    inv = guards.InvariantGuard(s)
    before = governance.governance_class(s, target)
    for rid in added:
        s.add(UserRole(user_id=target.id, role_id=rid, reason=reason))
    for rid in removed:
        current[rid].is_deleted = True
    if added or removed:
        resolver.bump_authz_version(target)
    inv.check()
    governance.revalidate_after_escalation(s, target, before, "TARGET_BECAME_PRIVILEGED")
    record_sensitive_action(
        s, ctx, "user.role.manage", action="set_roles", target=("app_user", target.id), subject_user_id=target.id
    )
    grants = resolver.load_grants(s, target.id)
    sensitive_added = [c for rid in added for c in guards.role_grants(s, rid) if registry.sensitivity(c)]
    if sensitive_added:
        outbox.enqueue(s, "rbac.sensitive_grant", "app_user", target.id, user_id=target.id)
        if not grants.has_active_factor:
            security_events.record(
                s,
                "PERMISSION_SUSPENDED",
                "SUCCESS",
                subject_user_id=target.id,
                detail={"reason": "MFA_REQUIRED", "codes": sorted(set(sensitive_added))},
            )
    return present_roles(s, target, grants)


def present_roles(s: Session, target: User, grants=None) -> dict:
    grants = grants or resolver.load_grants(s, target.id)
    rows = s.execute(
        sa.select(UserRole, Role)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == target.id)
        .order_by(Role.sort_order)
    ).all()
    items = []
    for ur, role in rows:
        role_codes = guards.role_grants(s, role.id)
        pending = [c for c in role_codes if registry.sensitivity(c) and not grants.has_active_factor]
        items.append(
            {
                "id": ur.id,
                "role": {"id": role.id, "code": role.code, "name": role.name},
                "role_id": role.id,
                "since": clock.to_rfc3339(ur.created_on),
                "created_on": clock.to_rfc3339(ur.created_on),
                "reason": ur.reason,
                "valid_from": None,
                "valid_until": None,
                "pending_mfa": bool(pending),
                "pending_mfa_permissions": sorted(pending),
                "version": ur.version,
            }
        )
    return {"items": items, "authz_version": target.authz_version}


# --- direct permissions (RBAC-006) --------------------------------------------------------------------------


def add_permission(s: Session, ctx: AuthContext, target: User, body) -> UserPermission:
    guards.reject_time_bound(body.valid_from, body.valid_until)
    guards.g3_not_self(ctx.user.id, target.id)
    perm = s.execute(sa.select(Permission).where(Permission.code == body.permission_code)).scalar_one_or_none()
    if perm is None:
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "Unknown permission.",
            errors=[field_error("permission_code", "INVALID_LOOKUP", "Unknown permission.")],
        )
    guards.g13_permission(perm, target.id)
    guards.g11_not_founder(target)
    scope = "ALL" if body.effect == "DENY" else body.scope
    guards.g8_scope(scope, perm.supports_scope or body.effect == "DENY")
    if body.effect == "GRANT":
        guards.g1_can_grant(ctx.res, perm.code, scope)
    guards.g9_not_stronger(s, ctx.res, target.id)
    if s.execute(
        sa.select(UserPermission).where(UserPermission.user_id == target.id, UserPermission.permission_id == perm.id)
    ).first():
        raise ApiError(409, "DUPLICATE", "A direct entry for this permission already exists.")
    require_step_up(ctx)
    inv = guards.InvariantGuard(s)
    before = governance.governance_class(s, target)
    row = UserPermission(user_id=target.id, permission_id=perm.id, effect=body.effect, scope=scope, reason=body.reason)
    s.add(row)
    resolver.bump_authz_version(target)
    inv.check()
    governance.revalidate_after_escalation(s, target, before, "TARGET_BECAME_PRIVILEGED")
    record_sensitive_action(
        s,
        ctx,
        "user.permission.manage",
        action=f"{body.effect.lower()}:{perm.code}",
        target=("app_user", target.id),
        subject_user_id=target.id,
    )
    if body.effect == "GRANT" and perm.sensitivity_class:
        outbox.enqueue(s, "rbac.sensitive_grant", "app_user", target.id, user_id=target.id)
        if not resolver.load_grants(s, target.id).has_active_factor:
            security_events.record(
                s,
                "PERMISSION_SUSPENDED",
                "SUCCESS",
                subject_user_id=target.id,
                detail={"reason": "MFA_REQUIRED", "codes": [perm.code]},
            )
    return row


def remove_permission(s: Session, ctx: AuthContext, target: User, grant_id: str) -> None:
    guards.g3_not_self(ctx.user.id, target.id)
    row = s.get(UserPermission, grant_id)
    if row is None or row.user_id != target.id:
        raise not_found()
    perm = s.get(Permission, row.permission_id, execution_options={"include_deleted": True})
    guards.g13_permission(perm, target.id)
    guards.g11_not_founder(target)
    guards.g9_not_stronger(s, ctx.res, target.id)
    require_step_up(ctx)
    inv = guards.InvariantGuard(s)
    before = governance.governance_class(s, target)
    row.is_deleted = True
    s.flush()
    if row.effect == "DENY":
        regained = resolver.load_grants(s, target.id).granted.get(perm.code)
        if regained:
            guards.g1_can_grant(ctx.res, perm.code, regained)
    resolver.bump_authz_version(target)
    inv.check()
    record_sensitive_action(
        s,
        ctx,
        "user.permission.manage",
        action=f"remove:{perm.code}",
        target=("app_user", target.id),
        subject_user_id=target.id,
    )
    governance.revalidate_after_escalation(s, target, before, "TARGET_BECAME_PRIVILEGED")  # removing a DENY


def present_permissions(s: Session, target: User) -> list[dict]:
    rows = s.execute(
        sa.select(UserPermission, Permission)
        .join(Permission, Permission.id == UserPermission.permission_id)
        .where(UserPermission.user_id == target.id)
        .order_by(Permission.code)
    ).all()
    return [
        {
            "id": up.id,
            "permission_code": p.code,
            "permission_name": p.name,
            "effect": up.effect,
            "scope": up.scope,
            "reason": up.reason,
            "valid_from": None,
            "valid_until": None,
            "created_on": clock.to_rfc3339(up.created_on),
            "created_by": up.created_by,
            "version": up.version,
        }
        for up, p in rows
    ]


def effective_permissions(s: Session, target: User) -> dict:
    grants = resolver.load_grants(s, target.id)
    now = clock.now()
    cooling = target.security_cooling_off_until is not None and target.security_cooling_off_until > now
    out = []
    codes = sorted(set(grants.granted) | set(grants.denied) | set(grants.sources))
    for code in codes:
        meta = grants.meta.get(code)
        entry: dict = {"code": code, "sources": grants.sources.get(code, []) + grants.denied.get(code, [])}
        if code in grants.denied:
            entry["status"] = "DENIED"
        else:
            entry["scope"] = grants.granted.get(code)
            if meta and meta.sensitivity_class and not grants.has_active_factor:
                entry.update(status="SUSPENDED", suspended_reason="MFA_REQUIRED")
            elif meta and meta.sensitivity_class and cooling:
                entry.update(status="SUSPENDED", suspended_reason="COOLING_OFF")
            else:
                entry["status"] = "EFFECTIVE"
        if meta:
            entry["is_sensitive"] = meta.sensitivity_class is not None
        out.append(entry)
    return {
        "authz_version": target.authz_version,
        "mfa": {
            "enrolled": grants.has_active_factor,
            "required": grants.mfa_required,
            "required_by": grants.mfa_required_by,
        },
        "permissions": out,
    }
