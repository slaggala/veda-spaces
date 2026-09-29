"""Effective-permission resolution (06 §5) and MFA policy (05 §11.1).

    0 user not ACTIVE or deleted            → ∅
    1 RECOVERY session                      → ∅
    3 denies = live DENY rows
    4 grants = live role grants ∪ live direct GRANTs
    5 scope  = broadest (ALL > TEAM > OWN)
    6 remove denied codes
    7 supports_scope = false → ALL
    8 MFA gate: sensitive codes need an ACTIVE factor and a 'totp' session,
      and are suspended during recovery cooling-off (all classes, N-A2)

The map is cached in-process keyed by (user_id, authz_version, session_type,
MFA-verified flag, cooling-off flag, factor flag) (06 §9). One process holds
all caches (OPS-010).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.platform.auth.models import UserMfaFactor
from veda.platform.identity.models import User

from .models import Permission, Role, RolePermission, UserPermission, UserRole

SCOPE_RANK = {"OWN": 1, "TEAM": 2, "ALL": 3}


def broader(a: str | None, b: str | None) -> str | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if SCOPE_RANK[a] >= SCOPE_RANK[b] else b


def scope_covers(held: str | None, needed: str) -> bool:
    return held is not None and SCOPE_RANK[held] >= SCOPE_RANK[needed]


@dataclass
class PermissionMeta:
    code: str
    supports_scope: bool
    sensitivity_class: str | None
    grant_path: str


@dataclass
class Resolution:
    user_id: str
    authz_version: int
    effective: dict[str, str] = field(default_factory=dict)
    suspended: dict[str, str] = field(default_factory=dict)  # code → reason
    granted: dict[str, str] = field(default_factory=dict)  # after DENY, before the MFA gate
    denied: dict[str, list[dict]] = field(default_factory=dict)
    sources: dict[str, list[dict]] = field(default_factory=dict)
    meta: dict[str, PermissionMeta] = field(default_factory=dict)
    role_mfa_required: bool = False
    user_mfa_required: bool = False
    has_active_factor: bool = False

    def has(self, code: str) -> bool:
        return code in self.effective

    def scope(self, code: str) -> str | None:
        return self.effective.get(code)

    @property
    def holds_sensitive(self) -> bool:
        return any(m.sensitivity_class for c, m in self.meta.items() if c in self.granted)

    @property
    def mfa_required_by(self) -> list[str]:
        out = []
        if self.role_mfa_required:
            out.append("ROLE_POLICY")
        if self.user_mfa_required:
            out.append("USER_POLICY")
        if self.holds_sensitive:
            out.append("SENSITIVE_PERMISSION")
        return out

    @property
    def mfa_required(self) -> bool:
        return bool(self.mfa_required_by)


def _live(model, now: datetime):
    return sa.and_(
        model.is_deleted == sa.false(),
        sa.or_(model.valid_from.is_(None), model.valid_from <= now),
        sa.or_(model.valid_until.is_(None), model.valid_until > now),
    )


def load_grants(session: Session, user_id: str, now: datetime | None = None) -> Resolution:
    """Steps 3–7: the granted map with sources, before the MFA gate."""
    now = now or clock.now()
    user = session.get(User, user_id, execution_options={"include_deleted": True})
    res = Resolution(user_id=user_id, authz_version=user.authz_version if user else 0)
    if user is None:
        return res
    res.user_mfa_required = bool(user.mfa_required)
    role_rows = session.execute(
        sa.select(Permission.code, Permission.supports_scope, Permission.sensitivity_class, Permission.grant_path,
                  RolePermission.scope, Role.code.label("role_code"), Role.id.label("role_id"), Role.mfa_required)
        .select_from(UserRole)
        .join(Role, sa.and_(Role.id == UserRole.role_id, Role.is_deleted == sa.false()))
        .join(RolePermission, sa.and_(RolePermission.role_id == Role.id, RolePermission.is_deleted == sa.false()))
        .join(Permission, sa.and_(Permission.id == RolePermission.permission_id, Permission.is_deleted == sa.false()))
        .where(UserRole.user_id == user_id, _live(UserRole, now))
    ).all()
    res.role_mfa_required = bool(session.execute(
        sa.select(sa.func.count()).select_from(UserRole)
        .join(Role, sa.and_(Role.id == UserRole.role_id, Role.is_deleted == sa.false()))
        .where(UserRole.user_id == user_id, _live(UserRole, now), Role.mfa_required == sa.true())
    ).scalar())
    direct_rows = session.execute(
        sa.select(Permission.code, Permission.supports_scope, Permission.sensitivity_class, Permission.grant_path,
                  UserPermission.scope, UserPermission.effect, UserPermission.id, UserPermission.reason)
        .join(Permission, sa.and_(Permission.id == UserPermission.permission_id, Permission.is_deleted == sa.false()))
        .where(UserPermission.user_id == user_id, _live(UserPermission, now))
    ).all()
    grants: dict[str, str] = {}
    for r in role_rows:
        res.meta[r.code] = PermissionMeta(r.code, r.supports_scope, r.sensitivity_class, r.grant_path)
        grants[r.code] = broader(grants.get(r.code), r.scope)
        res.sources.setdefault(r.code, []).append({"type": "ROLE", "role_code": r.role_code, "role_id": r.role_id, "scope": r.scope})
    denies: set[str] = set()
    for r in direct_rows:
        res.meta[r.code] = PermissionMeta(r.code, r.supports_scope, r.sensitivity_class, r.grant_path)
        if r.effect == "DENY":
            denies.add(r.code)
            res.denied.setdefault(r.code, []).append({"type": "USER_DENY", "grant_id": r.id, "reason": r.reason})
        else:
            grants[r.code] = broader(grants.get(r.code), r.scope)
            res.sources.setdefault(r.code, []).append({"type": "USER_GRANT", "grant_id": r.id, "scope": r.scope})
    for code, scope in grants.items():
        if code in denies:
            continue
        res.granted[code] = "ALL" if not res.meta[code].supports_scope else scope
    res.has_active_factor = bool(session.execute(
        sa.select(sa.func.count()).select_from(UserMfaFactor)
        .where(UserMfaFactor.user_id == user_id, UserMfaFactor.status == "ACTIVE")
    ).scalar())
    return res


def apply_gate(base: Resolution, *, user: User, session_type: str, mfa_verified: bool, now: datetime) -> Resolution:
    res = Resolution(
        user_id=base.user_id, authz_version=base.authz_version, granted=dict(base.granted), denied=base.denied,
        sources=base.sources, meta=base.meta, role_mfa_required=base.role_mfa_required,
        user_mfa_required=base.user_mfa_required, has_active_factor=base.has_active_factor,
    )
    if user.status != "ACTIVE" or user.is_deleted or user.user_type != "HUMAN":
        return res
    if session_type == "RECOVERY":
        res.suspended = {c: "RECOVERY_SESSION" for c in res.granted}
        return res
    cooling = user.security_cooling_off_until is not None and user.security_cooling_off_until > now
    for code, scope in res.granted.items():
        meta = res.meta[code]
        if meta.sensitivity_class:
            if not (res.has_active_factor and mfa_verified):
                res.suspended[code] = "MFA_REQUIRED"
                continue
            if cooling:
                res.suspended[code] = "COOLING_OFF"
                continue
        res.effective[code] = scope
    return res


class _Cache:
    def __init__(self, max_entries: int = 5000):
        self._lock = threading.Lock()
        self._data: dict[tuple, Resolution] = {}
        self._max = max_entries

    def get(self, key):
        with self._lock:
            return self._data.get(key)

    def put(self, key, value):
        with self._lock:
            if len(self._data) >= self._max:
                self._data.clear()
            self._data[key] = value

    def clear(self):
        with self._lock:
            self._data.clear()


_cache = _Cache()


def clear_cache() -> None:
    _cache.clear()


def resolve(session: Session, user: User, *, session_type: str, mfa_verified: bool, now: datetime | None = None) -> Resolution:
    now = now or clock.now()
    cooling = user.security_cooling_off_until is not None and user.security_cooling_off_until > now
    key = (user.id, user.authz_version, user.status, session_type, mfa_verified, cooling)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    base = load_grants(session, user.id, now)
    res = apply_gate(base, user=user, session_type=session_type, mfa_verified=mfa_verified, now=now)
    _cache.put(key, res)
    return res


def resolve_for_user_id(session: Session, user_id: str) -> Resolution:
    """Granted permissions of another user (G9, holders, I2): suspension ignored."""
    return load_grants(session, user_id)


def is_privileged(session: Session, user_id: str) -> bool:
    """Holds any sensitive permission, including suspended ones (08 §5.1)."""
    return load_grants(session, user_id).holds_sensitive


def bump_authz_version(user: User) -> None:
    """Increment in the same transaction as any change that can alter effective permissions (06 §9)."""
    user.authz_version = (user.authz_version or 1) + 1


def holders_of(session: Session, code: str, *, min_scope: str = "OWN", active_only: bool = True) -> list[str]:
    """Users granted ``code`` (suspension ignored), resolved by permission never by role name (RBAC-002)."""
    q = sa.select(User.id).where(User.user_type == "HUMAN")
    if active_only:
        q = q.where(User.status == "ACTIVE")
    out = []
    for (uid,) in session.execute(q).all():
        scope = load_grants(session, uid).granted.get(code)
        if scope_covers(scope, min_scope):
            out.append(uid)
    return out
