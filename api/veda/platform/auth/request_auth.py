"""Per-request authentication and the enforcement gates (05 §5, 06 §8).

Every bearer request performs one indexed read of ``user_session`` joined
with ``app_user`` — uncached — so revocation, deactivation and permission
changes apply from the very next request (AUTH-006, AUTH-017, F-10).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import timedelta

import sqlalchemy as sa
from flask import request
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db
from veda.kernel.context import ActorContext, actor, current_actor
from veda.kernel.errors import ApiError
from veda.kernel.ids import ANONYMOUS_USER_ID, new_id
from veda.platform.identity.models import User
from veda.platform.rbac import registry, resolver
from veda.platform.rbac.resolver import Resolution

from . import jwt_tokens, security_events
from .crypto import new_opaque_token, sha256_hex
from .models import MfaChallenge, UserMfaFactor, UserSession

log = logging.getLogger("veda.auth")

LAST_SEEN_INTERVAL = timedelta(minutes=5)


@dataclass
class AuthContext:
    user: User
    session: UserSession
    claims: dict
    res: Resolution

    @property
    def is_recovery(self) -> bool:
        return self.session.session_type == "RECOVERY"

    @property
    def mfa_verified(self) -> bool:
        return "totp" in self.session.methods

    def has(self, code: str) -> bool:
        return self.res.has(code)

    def scope(self, code: str) -> str | None:
        return self.res.scope(code)

    def require(self, code: str) -> str:
        if not self.res.has(code):
            deny(self, code)
        return self.res.effective[code]


# --- post-request writes (own short transactions) ----------------------------------

_post_writes: ContextVar[list[tuple[ActorContext | None, Callable[[Session], None]]] | None] = ContextVar(
    "veda_post_writes", default=None)


def schedule_write(fn: Callable[[Session], None]) -> None:
    items = _post_writes.get()
    if items is None:
        items = []
        _post_writes.set(items)
    items.append((current_actor(), fn))


def run_post_request_writes() -> None:
    items = _post_writes.get()
    if not items:
        return
    _post_writes.set([])
    for ctx, fn in items:
        try:
            with actor(ctx or ActorContext(actor_id=ANONYMOUS_USER_ID)), db.unit_of_work(write=True) as s:
                fn(s)
        except Exception:  # pragma: no cover - must not break the response
            log.exception("post_request_write_failed")


def anonymous_actor_id() -> str:
    return ANONYMOUS_USER_ID


# --- authentication -------------------------------------------------------------------

def _bearer() -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "AUTH_REQUIRED", "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    return token.strip()


def _abandon_recovery(session_id: str, user_id: str) -> None:
    """Expired RECOVERY session: revoke PENDING factors (ENROLLMENT_ABANDONED) (05 §11.5, TD-C)."""

    def write(s: Session) -> None:
        now = db.tx_time(s)
        for factor in s.execute(sa.select(UserMfaFactor).where(
                UserMfaFactor.user_id == user_id, UserMfaFactor.status == "PENDING")).scalars():
            factor.status = "REVOKED"
            factor.revoked_on = now
            factor.revoke_reason = "ENROLLMENT_ABANDONED"

    from veda.kernel.http import client_ip, request_id

    ctx = ActorContext(actor_id=user_id, via="API", session_id=session_id, request_id=request_id(), ip=client_ip())
    with actor(ctx):
        schedule_write(write)
    with actor(ctx):
        security_events.defer("MFA_RECOVERY_SESSION_EXPIRED", "FAILURE", subject_user_id=user_id,
                              failure_reason="TOKEN_EXPIRED", dedupe_key=f"recexp:{session_id}", dedupe_seconds=60)


def _session_invalid(detail: str = "Your session has ended. Sign in again.") -> ApiError:
    return ApiError(401, "SESSION_INVALID", detail)


def authenticate(session: Session, spec) -> AuthContext:
    token = _bearer()
    expired_claims = None
    try:
        claims = jwt_tokens.decode(token)
    except jwt_tokens.TokenExpired as exc:
        claims = exc.claims
        expired_claims = claims
    except jwt_tokens.TokenInvalid as exc:
        raise ApiError(401, "AUTH_REQUIRED", "Sign in to continue.") from exc

    now = clock.now()
    row = session.execute(
        sa.select(UserSession, User).join(User, User.id == UserSession.user_id)
        .where(UserSession.id == claims["sid"]).execution_options(include_deleted=True)
    ).first()
    if row is None:
        raise _session_invalid()
    us, user = row
    if user.id != claims["sub"]:
        raise _session_invalid()
    is_recovery = us.session_type == "RECOVERY"
    if expired_claims is not None:
        if is_recovery:
            if us.revoked_on is None:
                _abandon_recovery(us.id, user.id)
            raise _session_invalid()
        raise ApiError(401, "TOKEN_EXPIRED", "The access token expired. Refresh it.")
    if us.revoked_on is not None:
        raise _session_invalid()
    if now >= us.absolute_expires_on or now >= us.idle_expires_on:
        if is_recovery:
            _abandon_recovery(us.id, user.id)
        raise _session_invalid()
    if user.is_deleted or user.status != "ACTIVE" or user.user_type != "HUMAN":
        raise _session_invalid()

    res = resolver.resolve(session, user, session_type=us.session_type, mfa_verified="totp" in us.methods, now=now)
    ctx = AuthContext(user=user, session=us, claims=claims, res=res)

    if now - us.last_seen_on >= LAST_SEEN_INTERVAL:
        sid = us.id

        def touch(s: Session) -> None:
            fresh = s.get(UserSession, sid)
            if fresh is not None and fresh.revoked_on is None:
                fresh.last_seen_on = db.tx_time(s)

        with actor(ActorContext(actor_id=user.id, via="API", session_id=us.id)):
            schedule_write(touch)
    return ctx


def deny(ctx: AuthContext, code: str, *, route: str | None = None) -> None:
    reason = ctx.res.suspended.get(code)
    security_events.defer(
        "PERMISSION_DENIED", "BLOCKED", subject_user_id=ctx.user.id, permission_code=code,
        failure_reason="MFA_REQUIRED" if reason == "MFA_REQUIRED" else ("COOLING_OFF" if reason == "COOLING_OFF" else None),
        detail={"route": (route or request.path)[:200]},
        dedupe_key=f"pd:{ctx.user.id}:{code}", dedupe_seconds=60,
    )
    extra = {"permission": code}
    if reason:
        extra["reason"] = reason
    raise ApiError(403, "PERMISSION_DENIED", f"Requires {code}.", extra=extra)


def enforce_gates(session: Session, ctx: AuthContext, spec) -> None:
    # Layer 0: RECOVERY sessions reach only the allow-list (05 §11.5).
    if ctx.is_recovery and not spec.recovery_allowed:
        security_events.defer("RECOVERY_SESSION_BLOCKED", "BLOCKED", subject_user_id=ctx.user.id,
                              detail={"route": request.path[:200]})
        raise ApiError(403, "RECOVERY_SESSION_RESTRICTED",
                       "Recovery mode only allows setting up a new authenticator.",
                       extra={"allowed": ["GET /auth/me", "POST /auth/mfa/enroll/start",
                                          "POST /auth/mfa/enroll/confirm", "POST /auth/logout"]})
    if ctx.claims.get("pwd_change") and not spec.pwd_change_allowed:
        raise ApiError(403, "PASSWORD_CHANGE_REQUIRED", "Change your password to continue.")
    if ctx.is_recovery:
        return  # allow-listed recovery endpoints carry no permission logic (RECOVERY sessions resolve to ∅)
    # Layer 1: route permission gate (06 §8).
    for code in spec.permission:
        if not ctx.has(code):
            deny(ctx, code)
    if spec.any_of and not any(ctx.has(c) for c in spec.any_of):
        deny(ctx, spec.any_of[0])
    # Sensitive reads are recorded, de-duplicated per (actor, permission, 15 min) (06 §3.2, F-06).
    if spec.method == "GET":
        for code in spec.permission:
            klass = registry.sensitivity(code)
            if klass in registry.READ_RECORDED_CLASSES:
                security_events.defer(
                    "SENSITIVE_READ", "SUCCESS", subject_user_id=ctx.user.id, permission_code=code,
                    detail={"sensitivity_class": klass, "route": spec.rule[:200]},
                    dedupe_key=f"sr:{ctx.user.id}:{code}", dedupe_seconds=900,
                )


# --- step-up (G10, MFA-011) --------------------------------------------------------------

def _issue_step_up_challenge(ctx: AuthContext) -> str:
    token = new_opaque_token()
    token_hash = sha256_hex(token)
    user_id, session_id = ctx.user.id, ctx.session.id

    def write(s: Session) -> None:
        now = db.tx_time(s)
        s.add(MfaChallenge(user_id=user_id, purpose="STEP_UP", token_hash=token_hash, session_id=session_id,
                           expires_on=now + timedelta(minutes=5), failed_attempts=0, ip_address=current_actor().ip))

    schedule_write(write)
    return token


def require_step_up(ctx: AuthContext, *, allow_password: bool = False) -> None:
    """Protected operations need MFA verified within 10 minutes (G10), or — for users without a
    factor where the flow allows it — a password re-entry within 5 minutes (05 §11.6)."""
    now = clock.now()
    s = settings()
    if ctx.res.has_active_factor:
        if ctx.session.mfa_verified_on is not None and now - ctx.session.mfa_verified_on <= s.step_up_window:
            return
        security_events.defer("MFA_CHALLENGE", "FAILURE", subject_user_id=ctx.user.id,
                              failure_reason="STEP_UP_REQUIRED", detail={"stage": "step_up"},
                              dedupe_key=f"su:{ctx.session.id}", dedupe_seconds=60)
        raise ApiError(403, "STEP_UP_REQUIRED", "Confirm it's you with your authenticator.",
                       extra={"kind": "mfa", "mfa_token": _issue_step_up_challenge(ctx), "expires_in": 300})
    if allow_password:
        if ctx.session.reauth_on is not None and now - ctx.session.reauth_on <= s.reauth_window:
            return
        raise ApiError(403, "STEP_UP_REQUIRED", "Confirm your password to continue.", extra={"kind": "password"})
    # Sensitive permissions are never effective without MFA, so this is unreachable for G10 routes;
    # fail closed regardless.
    raise ApiError(403, "STEP_UP_REQUIRED", "Two-step verification is required.", extra={"kind": "mfa"})


def require_not_cooling_off(user: User) -> None:
    until = user.security_cooling_off_until
    if until is not None and until > clock.now():
        raise ApiError(403, "COOLING_OFF", "This change is locked after a recent account recovery.",
                       extra={"cooling_off_until": clock.to_rfc3339(until)})


def record_sensitive_action(session: Session, ctx: AuthContext, code: str, *, action: str,
                            target: tuple[str, str] | None = None, subject_user_id: str | None = None) -> None:
    """Mutations using any sensitive permission write one SENSITIVE_ACTION event (06 §3.2)."""
    klass = registry.sensitivity(code)
    if not klass:
        return
    security_events.record(session, "SENSITIVE_ACTION", "SUCCESS", subject_user_id=subject_user_id or ctx.user.id,
                           permission_code=code, target=target,
                           detail={"action": action[:200], "sensitivity_class": klass})


def new_session_id() -> str:
    return new_id()
