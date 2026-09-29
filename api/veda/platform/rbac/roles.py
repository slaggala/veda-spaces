"""Role and permission administration (08 §6, 06 §3, §7.1 G2/G5/G13)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, outbox
from veda.kernel.errors import ApiError, field_error, not_found
from veda.platform.auth.request_auth import AuthContext, record_sensitive_action, require_step_up
from veda.platform.identity.models import User

from . import guards, registry, resolver
from .models import Permission, Role, RolePermission, UserPermission, UserRole


def _holders(s: Session, role_id: str) -> list[User]:
    return s.execute(sa.select(User).join(UserRole, UserRole.user_id == User.id).where(UserRole.role_id == role_id)).scalars().all()


def present_role(s: Session, role: Role) -> dict:
    user_count = s.execute(sa.select(sa.func.count()).select_from(UserRole).join(User, User.id == UserRole.user_id)
                           .where(UserRole.role_id == role.id)).scalar()
    perm_count = s.execute(sa.select(sa.func.count()).select_from(RolePermission).where(RolePermission.role_id == role.id)).scalar()
    return {"id": role.id, "code": role.code, "name": role.name, "description": role.description,
            "is_system": role.is_system, "is_assignable": role.is_assignable, "mfa_required": role.mfa_required,
            "grant_path": role.grant_path, "founder_governed": role.grant_path == registry.FOUNDER_WORKFLOW_ONLY,
            "user_count": int(user_count or 0), "permission_count": int(perm_count or 0), "sort_order": role.sort_order,
            "created_on": clock.to_rfc3339(role.created_on), "updated_on": clock.to_rfc3339(role.updated_on),
            "version": role.version}


def role_permissions(s: Session, role: Role) -> list[dict]:
    rows = s.execute(sa.select(RolePermission, Permission).join(Permission, Permission.id == RolePermission.permission_id)
                     .where(RolePermission.role_id == role.id).order_by(Permission.module, Permission.code)).all()
    return [{"permission_code": p.code, "permission_name": p.name, "module": p.module, "resource": p.resource,
             "scope": rp.scope, "is_sensitive": p.is_sensitive, "sensitivity_class": p.sensitivity_class,
             "supports_scope": p.supports_scope} for rp, p in rows]


def load_role(s: Session, role_id: str) -> Role:
    role = s.get(Role, role_id)
    if role is None:
        raise not_found()
    return role


def create_role(s: Session, ctx: AuthContext, body) -> Role:
    name_norm = body.name.strip().lower()
    if s.execute(sa.select(Role).where(sa.or_(Role.code == body.code, Role.name_normalized == name_norm))).first():
        raise ApiError(409, "DUPLICATE", "A role with this code or name exists.",
                       errors=[field_error("code", "DUPLICATE", "Code or name already used.")])
    source = None
    if body.copy_from_role_id:
        source = load_role(s, body.copy_from_role_id)
        guards.g13_role(source, None)
        guards.g2_can_use_role(s, ctx.res, source.id)
    require_step_up(ctx)
    role = Role(code=body.code, name=body.name.strip(), name_normalized=name_norm, description=body.description,
                is_system=False, is_assignable=True, grant_path="STANDARD", mfa_required=False, sort_order=100)
    s.add(role)
    s.flush()
    if source is not None:
        for rp in s.execute(sa.select(RolePermission).where(RolePermission.role_id == source.id)).scalars().all():
            s.add(RolePermission(role_id=role.id, permission_id=rp.permission_id, scope=rp.scope))
    record_sensitive_action(s, ctx, "role.manage", action="create_role", target=("role", role.id))
    return role


def update_role(s: Session, ctx: AuthContext, role: Role, body) -> Role:
    guards.g13_role(role, None)
    provided = body.provided()
    require_step_up(ctx)
    if "name" in provided and body.name:
        name_norm = body.name.strip().lower()
        clash = s.execute(sa.select(Role).where(Role.name_normalized == name_norm, Role.id != role.id)).first()
        if clash:
            raise ApiError(409, "DUPLICATE", "A role with this name exists.")
        role.name, role.name_normalized = body.name.strip(), name_norm
    if "description" in provided:
        role.description = body.description
    if "is_assignable" in provided and body.is_assignable is not None:
        role.is_assignable = body.is_assignable
    if "mfa_required" in provided and body.mfa_required is not None and body.mfa_required != role.mfa_required:
        role.mfa_required = body.mfa_required
        for holder in _holders(s, role.id):
            resolver.bump_authz_version(holder)
    record_sensitive_action(s, ctx, "role.manage", action="update_role", target=("role", role.id))
    return role


def delete_role(s: Session, ctx: AuthContext, role: Role) -> None:
    guards.g13_role(role, None)
    if role.is_system:
        raise ApiError(409, "SYSTEM_OBJECT", "System roles cannot be deleted.")
    if s.execute(sa.select(sa.func.count()).select_from(UserRole).where(UserRole.role_id == role.id)).scalar():
        raise ApiError(409, "ROLE_IN_USE", "Unassign this role from all users first.")
    require_step_up(ctx)
    for rp in s.execute(sa.select(RolePermission).where(RolePermission.role_id == role.id)).scalars():
        rp.is_deleted = True
    role.is_deleted = True
    record_sensitive_action(s, ctx, "role.manage", action="delete_role", target=("role", role.id))


def replace_permissions(s: Session, ctx: AuthContext, role: Role, items: list, reason: str) -> dict:
    guards.g13_role(role, None)
    holders = _holders(s, role.id)
    if any(h.id == ctx.user.id for h in holders):
        raise ApiError(403, "SELF_MODIFICATION_DENIED", "You can't edit the grants of a role you hold.")
    wanted: dict[str, str] = {}
    perms: dict[str, Permission] = {}
    for item in items:
        perm = s.execute(sa.select(Permission).where(Permission.code == item.permission_code)).scalar_one_or_none()
        if perm is None:
            raise ApiError(422, "VALIDATION_FAILED", "Unknown permission.",
                           errors=[field_error("permissions", "INVALID_LOOKUP", f"Unknown permission {item.permission_code}.")])
        guards.g13_permission(perm, None)
        scope = item.scope if perm.supports_scope else (item.scope or "ALL")
        guards.g8_scope(scope, perm.supports_scope)
        wanted[perm.code] = scope
        perms[perm.code] = perm
    current = {p.code: (rp, p) for rp, p in s.execute(
        sa.select(RolePermission, Permission).join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id == role.id)).all()}
    # G2: the actor must hold every permission in the resulting role and every removed one.
    for code, scope in wanted.items():
        guards.g1_can_grant(ctx.res, code, scope)
    for code, (rp, _p) in current.items():
        if code not in wanted:
            guards.g1_can_grant(ctx.res, code, rp.scope)
    require_step_up(ctx)
    inv = guards.InvariantGuard(s)
    diff = {"added": 0, "removed": 0, "changed": 0}
    sensitive_added = []
    for code, scope in wanted.items():
        if code in current:
            rp, _ = current[code]
            if rp.scope != scope:
                rp.scope = scope
                diff["changed"] += 1
        else:
            s.add(RolePermission(role_id=role.id, permission_id=perms[code].id, scope=scope))
            diff["added"] += 1
            if perms[code].sensitivity_class:
                sensitive_added.append(code)
    for code, (rp, _p) in current.items():
        if code not in wanted:
            rp.is_deleted = True
            diff["removed"] += 1
    if any(diff.values()):
        for holder in holders:
            resolver.bump_authz_version(holder)
    inv.check()
    record_sensitive_action(s, ctx, "role.manage", action="replace_permissions", target=("role", role.id))
    if sensitive_added:
        outbox.enqueue(s, "rbac.sensitive_grant", "role", role.id, role_id=role.id)
    return {"permissions": role_permissions(s, role), "diff": diff}


# --- permissions ------------------------------------------------------------------------------

def present_permission(s: Session, perm: Permission) -> dict:
    roles = s.execute(sa.select(Role.code, Role.name, RolePermission.scope).join(RolePermission, RolePermission.role_id == Role.id)
                      .where(RolePermission.permission_id == perm.id).order_by(Role.sort_order)).all()
    return {"id": perm.id, "code": perm.code, "module": perm.module, "resource": perm.resource, "action": perm.action,
            "name": perm.name, "description": perm.description, "supports_scope": perm.supports_scope,
            "is_sensitive": perm.is_sensitive, "sensitivity_class": perm.sensitivity_class,
            "grant_path": perm.grant_path, "requirement_ref": perm.requirement_ref,
            "granted_to_roles": [{"code": r.code, "name": r.name, "scope": r.scope} for r in roles],
            "version": perm.version}


def update_permission(s: Session, ctx: AuthContext, perm: Permission, body) -> Permission:
    require_step_up(ctx)
    provided = body.provided()
    if "name" in provided and body.name:
        perm.name = body.name
    if "description" in provided:
        perm.description = body.description
    record_sensitive_action(s, ctx, "permission.manage", action="update_permission", target=("permission", perm.id))
    return perm


def holders(s: Session, perm: Permission) -> list[dict]:
    out = []
    for user in s.execute(sa.select(User).where(User.user_type == "HUMAN").order_by(User.full_name)).scalars():
        grants = resolver.load_grants(s, user.id)
        if perm.code in grants.granted or perm.code in grants.denied:
            out.append({"user": {"id": user.id, "display_name": user.display_name or user.full_name, "email": user.email,
                                 "status": user.status},
                        "scope": grants.granted.get(perm.code),
                        "status": "DENIED" if perm.code in grants.denied else "GRANTED",
                        "sources": grants.sources.get(perm.code, []) + grants.denied.get(perm.code, [])})
    return out


def direct_exceptions(s: Session, perm: Permission) -> list[dict]:
    rows = s.execute(sa.select(UserPermission, User).join(User, User.id == UserPermission.user_id)
                     .where(UserPermission.permission_id == perm.id)).all()
    return [{"id": up.id, "user": {"id": u.id, "display_name": u.display_name or u.full_name}, "effect": up.effect,
             "scope": up.scope, "reason": up.reason} for up, u in rows]
