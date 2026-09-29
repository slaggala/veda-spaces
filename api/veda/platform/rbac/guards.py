"""Account- and access-control guards G1–G13 and invariants I1–I3 (06 §7).

Guards compare permission codes and data attributes only; nothing references
role codes (RBAC-002). Founder protection is ``protection_level``; Founder-only
grantability is ``grant_path = FOUNDER_WORKFLOW_ONLY``.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError
from veda.platform.auth import security_events
from veda.platform.identity.models import User

from . import registry
from .models import Permission, Role, RolePermission, UserPermission, UserRole
from .resolver import SCOPE_RANK, Resolution, load_grants, scope_covers

# --- guards --------------------------------------------------------------------------------


def g1_can_grant(actor: Resolution, code: str, scope: str) -> None:
    """G1: to grant P at scope S the actor must hold P at ≥ S."""
    if not scope_covers(actor.effective.get(code), scope):
        raise ApiError(
            403, "ESCALATION_DENIED", f"You can't grant {code} at scope {scope}.", extra={"permission": code}
        )


def role_grants(s: Session, role_id: str) -> dict[str, str]:
    rows = s.execute(
        sa.select(Permission.code, RolePermission.scope, Permission.supports_scope)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id == role_id)
    ).all()
    return {r.code: (r.scope if r.supports_scope else "ALL") for r in rows}


def g2_can_use_role(s: Session, actor: Resolution, role_id: str) -> None:
    """G2: assigning, editing or copying role R requires holding every permission in R at ≥ scope."""
    for code, scope in role_grants(s, role_id).items():
        if not scope_covers(actor.effective.get(code), scope):
            raise ApiError(
                403, "ESCALATION_DENIED", "This role includes permissions you don't have.", extra={"permission": code}
            )


def g3_not_self(actor_id: str, target_id: str) -> None:
    if actor_id == target_id:
        raise ApiError(403, "SELF_MODIFICATION_DENIED", "You can't change your own access here.")


def g9_not_stronger(s: Session, actor: Resolution, target_id: str) -> Resolution:
    """G9: the target's granted permissions (suspension included) ⊆ the actor's, each at ≤ scope."""
    target = load_grants(s, target_id)
    for code, scope in target.granted.items():
        if not scope_covers(actor.effective.get(code), scope):
            raise ApiError(
                403, "ESCALATION_DENIED", "This account holds permissions you don't have.", extra={"permission": code}
            )
    return target


def g11_not_founder(target: User) -> None:
    if target.protection_level == "FOUNDER":
        raise ApiError(403, "FOUNDER_PROTECTED", "Founder accounts use the Founder workflow.")


def g8_scope(scope: str, supports_scope: bool) -> None:
    if scope == "TEAM":
        raise ApiError(422, "SCOPE_NOT_SUPPORTED", "Team scope is available when teams are introduced.")
    if not supports_scope and scope != "ALL":
        raise ApiError(422, "SCOPE_NOT_SUPPORTED", "This permission has no scope; use ALL.")


def g13_block(
    subject_user_id: str | None, *, permission_code: str | None = None, target: tuple[str, str] | None = None
) -> None:
    security_events.defer(
        "FOUNDER_GOVERNANCE_BYPASS_BLOCKED",
        "BLOCKED",
        subject_user_id=subject_user_id,
        permission_code=permission_code,
        target=target,
    )
    raise ApiError(403, "FOUNDER_GOVERNANCE_REQUIRED", "Founder changes go only through the Founder workflow.")


def g13_role(role: Role, subject_user_id: str | None) -> None:
    if role.grant_path == registry.FOUNDER_WORKFLOW_ONLY:
        g13_block(subject_user_id, target=("role", role.id))


def g13_permission(permission: Permission, subject_user_id: str | None) -> None:
    if permission.grant_path == registry.FOUNDER_WORKFLOW_ONLY:
        g13_block(subject_user_id, permission_code=permission.code, target=("permission", permission.id))


def reject_time_bound(valid_from, valid_until) -> None:
    if valid_from is not None or valid_until is not None:
        raise ApiError(422, "TIME_BOUND_GRANTS_NOT_ENABLED", "Time-bound grants are not enabled (P1).")


# --- invariants (06 §7.3) ------------------------------------------------------------------


@dataclass
class InvariantState:
    i1: bool
    i2: bool
    i2_effective: bool
    i3: bool
    problems: list[str]


def founder_role_ids(s: Session) -> list[str]:
    return list(s.execute(sa.select(Role.id).where(Role.grant_path == registry.FOUNDER_WORKFLOW_ONLY)).scalars())


def is_founder(s: Session, user: User) -> bool:
    """06 §7.2.1: protection_level = FOUNDER and holds the FOUNDER role."""
    if user.protection_level != "FOUNDER":
        return False
    ids = founder_role_ids(s)
    return bool(ids) and bool(
        s.execute(
            sa.select(sa.func.count())
            .select_from(UserRole)
            .where(UserRole.user_id == user.id, UserRole.role_id.in_(ids))
        ).scalar()
    )


def active_founders(s: Session) -> list[User]:
    users = (
        s.execute(
            sa.select(User).where(
                User.user_type == "HUMAN", User.status == "ACTIVE", User.protection_level == "FOUNDER"
            )
        )
        .scalars()
        .all()
    )
    return [u for u in users if is_founder(s, u)]


def evaluate(s: Session) -> InvariantState:
    from veda.platform.auth.models import UserMfaFactor

    problems: list[str] = []
    i1 = bool(active_founders(s))
    if not i1:
        problems.append("I1: no ACTIVE Founder")
    admins = []
    for user in s.execute(sa.select(User).where(User.user_type == "HUMAN", User.status == "ACTIVE")).scalars():
        grants = load_grants(s, user.id).granted
        if all(grants.get(c) == "ALL" for c in registry.RECOVERY_ADMIN_CODES):
            admins.append(user)
    i2 = bool(admins)
    if not i2:
        problems.append("I2: no recovery administrator")
    i2_effective = any(
        s.execute(
            sa.select(sa.func.count())
            .select_from(UserMfaFactor)
            .where(UserMfaFactor.user_id == u.id, UserMfaFactor.status == "ACTIVE")
        ).scalar()
        for u in admins
    )
    founder_ids = set(founder_role_ids(s))
    i3 = True
    # I3 is evaluated over the same population on both sides: live (not soft-deleted) accounts. A deleted
    # Founder keeps its FOUNDER role row and protection level as history (IR-08).
    holders = (
        set(
            s.execute(
                sa.select(UserRole.user_id)
                .join(User, User.id == UserRole.user_id)
                .where(UserRole.role_id.in_(founder_ids), User.is_deleted == sa.false())
            ).scalars()
        )
        if founder_ids
        else set()
    )
    protected = set(
        s.execute(sa.select(User.id).where(User.protection_level == "FOUNDER", User.is_deleted == sa.false())).scalars()
    )
    if holders != protected:
        i3 = False
        problems.append("I3: protection_level and FOUNDER role differ")
    fwo = (
        s.execute(sa.select(Permission.id).where(Permission.grant_path == registry.FOUNDER_WORKFLOW_ONLY))
        .scalars()
        .all()
    )
    if fwo:
        leak_q = sa.select(sa.func.count()).select_from(RolePermission).where(RolePermission.permission_id.in_(fwo))
        if founder_ids:
            leak_q = leak_q.where(RolePermission.role_id.not_in(founder_ids))
        leaking_roles = s.execute(leak_q).scalar()
        direct = s.execute(
            sa.select(sa.func.count()).select_from(UserPermission).where(UserPermission.permission_id.in_(fwo))
        ).scalar()
        if leaking_roles or direct:
            i3 = False
            problems.append("I3: FOUNDER_WORKFLOW_ONLY permission outside the FOUNDER role")
    return InvariantState(i1, i2, i2_effective, i3, problems)


def lock_governance(s: Session) -> None:
    """Serialize invariant-affecting changes: SQLite already holds BEGIN IMMEDIATE;
    PostgreSQL takes a transaction advisory lock (06 §7.2.5, §7.3)."""
    if s.get_bind().dialect.name == "postgresql":
        s.execute(sa.text("SELECT pg_advisory_xact_lock(7845120002)"))


class InvariantGuard:
    """Re-run the invariants over the post-change state before commit (G4)."""

    def __init__(self, s: Session):
        self.s = s
        lock_governance(s)
        self.before = evaluate(s)

    def check(self) -> None:
        self.s.flush()
        after = evaluate(self.s)
        if self.before.i1 and not after.i1:
            raise ApiError(409, "LAST_FOUNDER", "This would leave no active Founder.")
        if self.before.i2 and not after.i2:
            raise ApiError(409, "LAST_ADMINISTRATOR", "This would leave no recovery administrator.")
        if self.before.i3 and not after.i3:
            raise ApiError(409, "FOUNDER_STATE_INCONSISTENT", "This would make Founder state inconsistent.")


def scope_rank(scope: str) -> int:
    return SCOPE_RANK[scope]
