"""Authentication flows (05 §3–§8): login, sessions, refresh, logout, passwords,
invitation and the proposed-email workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db, outbox, turnstile
from veda.kernel.context import ActorContext, acting, current_actor
from veda.kernel.dto import mask_email, normalize_email
from veda.kernel.errors import ApiError, field_error
from veda.kernel.http import network_of
from veda.kernel.ids import ANONYMOUS_USER_ID
from veda.platform.identity.models import User, UserCredential
from veda.platform.rbac import resolver

from . import jwt_tokens, passwords, security_events, throttle
from .crypto import derive_action_token, new_opaque_token, sha256_hex
from .models import MfaChallenge, RefreshToken, UserActionToken, UserMfaFactor, UserSession
from .request_auth import AuthContext, schedule_write

TOKEN_TTLS = {
    "PASSWORD_RESET": timedelta(minutes=30),
    "INVITE": timedelta(hours=72),
    "INVITE_SENSITIVE": timedelta(hours=24),
    "MFA_ENROLLMENT": timedelta(minutes=30),
}
CHALLENGE_TTLS = {"LOGIN": timedelta(minutes=5), "STEP_UP": timedelta(minutes=5), "ENROLLMENT": timedelta(minutes=15)}
METHODS_AMR = {"pwd": ["pwd"], "pwd+totp": ["pwd", "otp"], "pwd+recovery": ["pwd", "recovery"]}


def invalid_credentials(captcha_required: bool = False) -> ApiError:
    extra = {"captcha_required": True} if captcha_required else {}
    return ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.", extra=extra)


# --- users and credentials ----------------------------------------------------------


def find_user_by_email(s: Session, email: str) -> User | None:
    return s.execute(sa.select(User).where(User.email_normalized == normalize_email(email))).scalar_one_or_none()


def credential_for(s: Session, user_id: str) -> UserCredential | None:
    return s.execute(sa.select(UserCredential).where(UserCredential.user_id == user_id)).scalar_one_or_none()


def active_factor(s: Session, user_id: str) -> UserMfaFactor | None:
    return s.execute(
        sa.select(UserMfaFactor).where(UserMfaFactor.user_id == user_id, UserMfaFactor.status == "ACTIVE")
    ).scalar_one_or_none()


def user_ref(user: User | None, *, with_email: bool = False) -> dict | None:
    if user is None:
        return None
    ref = {"id": user.id, "display_name": user.display_name or user.full_name}
    if with_email:
        ref["email"] = user.email
    return ref


# --- sessions and tokens ---------------------------------------------------------------


@dataclass
class IssuedSession:
    session: UserSession
    access_token: str
    expires_in: int
    refresh_token: str | None


def _device_label(ua: str | None) -> str | None:
    if not ua:
        return None
    browser = next((b for b in ("Edg", "Chrome", "Firefox", "Safari") if b in ua), "Browser")
    browser = {"Edg": "Edge"}.get(browser, browser)
    system = next((o for o in ("Android", "iPhone", "iPad", "Windows", "Mac OS X", "Linux") if o in ua), None)
    system = {"Mac OS X": "macOS", "iPhone": "iOS", "iPad": "iPadOS"}.get(system, system)
    return f"{browser} on {system}" if system else browser


def create_session(
    s: Session,
    user: User,
    *,
    methods: str,
    session_type: str = "FULL",
    mfa_verified: bool = False,
    pwd_change: bool = False,
) -> IssuedSession:
    cfg = settings()
    now = db.tx_time(s)
    ctx = current_actor()
    if session_type == "RECOVERY":
        idle = absolute = now + cfg.recovery_session_ttl
    else:
        idle, absolute = now + cfg.refresh_idle_ttl, now + cfg.refresh_absolute_ttl
    us = UserSession(
        user_id=user.id,
        started_on=now,
        last_seen_on=now,
        idle_expires_on=idle,
        absolute_expires_on=absolute,
        session_type=session_type,
        auth_methods=methods,
        mfa_verified_on=now if mfa_verified else None,
        ip_address=ctx.ip if ctx else None,
        user_agent=(ctx.user_agent[:500] if ctx and ctx.user_agent else None),
        device_label=_device_label(ctx.user_agent if ctx else None),
    )
    s.add(us)
    s.flush()
    refresh = None
    if session_type == "FULL":
        refresh = new_opaque_token()
        s.add(RefreshToken(session_id=us.id, token_hash=sha256_hex(refresh), issued_on=now, expires_on=idle))
    access, ttl = jwt_tokens.issue(
        user_id=user.id,
        session_id=us.id,
        authz_version=user.authz_version,
        amr=METHODS_AMR[methods],
        session_type=session_type,
        pwd_change=pwd_change,
    )
    return IssuedSession(us, access, ttl, refresh)


def access_token_for(user: User, us: UserSession, *, pwd_change: bool = False) -> tuple[str, int]:
    return jwt_tokens.issue(
        user_id=user.id,
        session_id=us.id,
        authz_version=user.authz_version,
        amr=METHODS_AMR[us.auth_methods],
        session_type=us.session_type,
        pwd_change=pwd_change,
    )


def refresh_cookie(value: str) -> tuple[tuple, dict]:
    cfg = settings()
    return (
        (cfg.cookie_name, value),
        {
            "httponly": True,
            "secure": cfg.cookie_secure,
            "samesite": "Strict",
            "path": "/api/v1/auth",
            "max_age": int(cfg.refresh_idle_ttl.total_seconds()),
        },
    )


def clear_cookie() -> tuple[tuple, dict]:
    cfg = settings()
    return (
        (cfg.cookie_name,),
        {"path": "/api/v1/auth", "secure": cfg.cookie_secure, "httponly": True, "samesite": "Strict"},
    )


def revoke_session(s: Session, us: UserSession, reason: str, *, by: str | None = None, event: bool = True) -> bool:
    if us.revoked_on is not None:
        return False
    now = db.tx_time(s)
    us.revoked_on = now
    us.revoke_reason = reason
    us.revoked_by = by or (current_actor().actor_id if current_actor() else None)
    if event:
        security_events.record(
            s, "SESSION_REVOKED", "SUCCESS", subject_user_id=us.user_id, session_id=us.id, detail={"reason": reason}
        )
    return True


def revoke_all_sessions(s: Session, user_id: str, reason: str, *, except_session_id: str | None = None) -> int:
    count = 0
    q = sa.select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_on.is_(None))
    for us in s.execute(q).scalars():
        if us.id == except_session_id:
            continue
        if revoke_session(s, us, reason):
            count += 1
    return count


def invalidate_challenges(s: Session, user_id: str, *, except_id: str | None = None) -> None:
    now = db.tx_time(s)
    for ch in s.execute(
        sa.select(MfaChallenge).where(
            MfaChallenge.user_id == user_id, MfaChallenge.completed_on.is_(None), MfaChallenge.expires_on > now
        )
    ).scalars():
        if ch.id != except_id:
            ch.expires_on = now


def invalidate_action_tokens(s: Session, user_id: str, purposes: tuple[str, ...]) -> None:
    now = db.tx_time(s)
    for tok in s.execute(
        sa.select(UserActionToken).where(
            UserActionToken.user_id == user_id,
            UserActionToken.purpose.in_(purposes),
            UserActionToken.used_on.is_(None),
            UserActionToken.invalidated_on.is_(None),
        )
    ).scalars():
        tok.invalidated_on = now


def create_action_token(
    s: Session,
    user: User,
    purpose: str,
    *,
    ttl: timedelta,
    send_to: str | None = None,
    expires_on: datetime | None = None,
) -> tuple[UserActionToken, str]:
    now = db.tx_time(s)
    tok = UserActionToken(
        user_id=user.id,
        purpose=purpose,
        token_hash="0" * 64,
        expires_on=expires_on or now + ttl,
        sent_to_email_normalized=normalize_email(send_to or user.email_normalized),
        requested_ip=current_actor().ip if current_actor() else None,
    )
    from veda.kernel.ids import new_id

    tok.id = new_id()
    raw = derive_action_token(tok.id, purpose)
    tok.token_hash = sha256_hex(raw)
    s.add(tok)
    return tok, raw


def consume_action_token(s: Session, raw: str | None, purpose: str, error_code: str) -> UserActionToken:
    if not raw or not isinstance(raw, str) or len(raw) > 200:
        raise ApiError(400, error_code, "This link has expired or was already used.")
    tok = s.execute(
        sa.select(UserActionToken).where(UserActionToken.token_hash == sha256_hex(raw))
    ).scalar_one_or_none()
    now = db.tx_time(s)
    if (
        tok is None
        or tok.purpose != purpose
        or tok.used_on is not None
        or tok.invalidated_on is not None
        or tok.expires_on <= now
    ):
        _token_rejected(raw, purpose, tok, now)
        raise ApiError(400, error_code, "This link has expired or was already used.")
    return tok


TOKEN_EVENTS = {
    "PASSWORD_RESET": "PASSWORD_RESET_COMPLETED",
    "INVITE": "INVITE_ACCEPTED",
    "EMAIL_VERIFICATION": "EMAIL_CHANGE_VERIFIED",
    "EMAIL_CHANGE_CANCEL": "EMAIL_CHANGE_CANCELLED",
    "APPROVAL_CANCEL": "BREAK_GLASS_CANCELLED",
    "MFA_ENROLLMENT": "MFA_ENROLLMENT_STARTED",
}


def _token_rejected(raw: str, purpose: str, tok: UserActionToken | None, now) -> None:
    """A presented single-use link that is unknown, spent, superseded or expired (IR-25, AUTH-013)."""
    if tok is None or tok.purpose != purpose:
        reason, subject = "TOKEN_INVALID", None
    elif tok.used_on is not None:
        reason, subject = "TOKEN_REUSED", tok.user_id
    elif tok.expires_on <= now:
        reason, subject = "TOKEN_EXPIRED", tok.user_id
    else:
        reason, subject = "TOKEN_INVALID", tok.user_id
    security_events.defer(
        TOKEN_EVENTS[purpose],
        "FAILURE",
        subject_user_id=subject,
        failure_reason=reason,
        detail={"stage": "link"},
        dedupe_key=f"tok:{purpose}:{sha256_hex(raw)[:16]}",
        dedupe_seconds=300,
    )


def create_challenge(
    s: Session,
    user_id: str,
    purpose: str,
    *,
    session_id: str | None = None,
    factor_id: str | None = None,
    enrollment_path: str | None = None,
) -> str:
    raw = new_opaque_token()
    now = db.tx_time(s)
    s.add(
        MfaChallenge(
            user_id=user_id,
            purpose=purpose,
            token_hash=sha256_hex(raw),
            session_id=session_id,
            expires_on=now + CHALLENGE_TTLS[purpose],
            failed_attempts=0,
            ip_address=current_actor().ip if current_actor() else None,
            factor_id=factor_id,
            enrollment_path=enrollment_path,
        )
    )
    return raw


def invalidate_enrollment(s: Session, user_id: str, *, except_id: str | None = None) -> None:
    """End every open enrollment transaction of a user: open ENROLLMENT challenges (including invitation
    contexts) expire and PENDING factors are revoked (IR-01, IR-20, IR-21)."""
    now = db.tx_time(s)
    for ch in s.execute(
        sa.select(MfaChallenge).where(
            MfaChallenge.user_id == user_id,
            MfaChallenge.purpose == "ENROLLMENT",
            MfaChallenge.completed_on.is_(None),
            MfaChallenge.expires_on > now,
        )
    ).scalars():
        if ch.id != except_id:
            ch.expires_on = now
    for f in s.execute(
        sa.select(UserMfaFactor).where(UserMfaFactor.user_id == user_id, UserMfaFactor.status == "PENDING")
    ).scalars():
        f.status, f.revoked_on, f.revoke_reason = "REVOKED", now, "ENROLLMENT_ABANDONED"


def mfa_policy(s: Session, user: User) -> resolver.Resolution:
    return resolver.load_grants(s, user.id)


# --- login (05 §3) ------------------------------------------------------------------------


def _login_failure(email_norm: str, network: str, user: User | None, reason: str) -> None:
    subject = user.id if user else None
    fields = {"failure_reason": reason, "detail": {"method": "password", "network": network}}
    if user is None:
        fields["email_attempted_hash"] = security_events.email_attempt_hash(email_norm)
    else:
        fields["subject_user_id"] = subject
    security_events.defer("LOGIN", "FAILURE", **fields)


def _captcha_now(account_key: str, network: str) -> bool:
    """Whether the next attempt for this identifier from this network needs Turnstile (pair or budget)."""
    return throttle.pair_state(account_key, network)[1] or throttle.account_state(account_key)[0]


def _record_budget_failure(account_key: str, user: User | None, email_norm: str) -> None:
    count = throttle.record_account_failure(account_key)
    if count in (throttle.ACCOUNT_CAPTCHA_FAILURES, throttle.ACCOUNT_DELAY_FAILURES):
        who = (
            {"subject_user_id": user.id}
            if user is not None
            else {"email_attempted_hash": security_events.email_attempt_hash(email_norm)}
        )
        security_events.defer(
            "ACCOUNT_THROTTLED",
            "SUCCESS",
            detail={"scope": "account_challenge" if count == throttle.ACCOUNT_CAPTCHA_FAILURES else "account_delay"},
            **who,
        )


def verify_login_captcha(turnstile_token: str | None) -> bool | None:
    """Verify a presented Turnstile token (network I/O, called outside the write transaction). None when no
    token was sent; the throttle decides later whether one was required (DEV-003)."""
    if not turnstile_token:
        return None
    ctx = current_actor()
    return turnstile.verify(turnstile_token, ctx.ip if ctx else None)


_UNSET: Any = object()


def login(
    s: Session, email: str, password: str, turnstile_token: str | None, *, captcha_verified: bool | None = _UNSET
) -> dict:
    ctx = current_actor()
    email_norm = normalize_email(email)
    network = network_of(ctx.ip if ctx else None)
    user = find_user_by_email(s, email_norm)
    account_key = user.id if user else "unknown:" + security_events.email_attempt_hash(email_norm)
    blocked, captcha_required = throttle.pair_state(account_key, network)
    # Layered bounds across networks (RR-04): the same for known and unknown identifiers, never a lock-out.
    budget_captcha, retry_after = throttle.account_state(account_key)
    if retry_after:
        _login_failure(email_norm, network, user, "RATE_LIMITED")
        raise ApiError(
            429, "RATE_LIMITED", "Too many attempts. Try again later.", headers={"Retry-After": str(retry_after)}
        )
    captcha_required = captcha_required or budget_captcha
    if captcha_verified is _UNSET:  # direct callers without a prepare step
        captcha_verified = verify_login_captcha(turnstile_token) if captcha_required else None
    if captcha_required and captcha_verified is not True:
        passwords.verify_dummy(password)
        _login_failure(email_norm, network, user, "CAPTCHA_FAILED" if turnstile_token else "THROTTLED")
        raise invalid_credentials(captcha_required=True)
    if blocked:
        passwords.verify_dummy(password)
        _login_failure(email_norm, network, user, "THROTTLED")
        raise invalid_credentials(captcha_required=True)

    if user is None or user.user_type != "HUMAN":
        passwords.verify_dummy(password)
        throttle.record_password_failure(account_key, network)
        _record_budget_failure(account_key, user, email_norm)
        _login_failure(email_norm, network, user, "UNKNOWN_USER" if user is None else "NOT_HUMAN")
        raise invalid_credentials(captcha_required=_captcha_now(account_key, network))

    cred = credential_for(s, user.id)
    factor = active_factor(s, user.id)
    now = clock.now()
    reason = None
    if user.status == "INVITED":
        reason = "INVITED"
    elif user.status != "ACTIVE":
        reason = "DISABLED"
    elif cred is None or cred.password_hash is None:
        reason = "BAD_PASSWORD"
    elif cred.locked_until is not None and cred.locked_until > now and factor is None:
        reason = "THROTTLED"
    ok = passwords.verify_password(cred.password_hash if cred else None, password)
    if reason is None and not ok:
        reason = "BAD_PASSWORD"
    if reason is not None:
        if throttle.record_password_failure(account_key, network):
            security_events.defer(
                "ACCOUNT_THROTTLED", "SUCCESS", subject_user_id=user.id, detail={"scope": "network", "networks": 1}
            )
        _record_budget_failure(account_key, user, email_norm)
        _login_failure(email_norm, network, user, reason)
        if reason == "BAD_PASSWORD" and user.status == "ACTIVE":
            distinct = throttle.record_network_failure(user.id, network)
            user_id = user.id

            def count_failure(ws: Session) -> None:
                c = credential_for(ws, user_id)
                if c is None:
                    return
                t = db.tx_time(ws)
                if c.failed_window_started_on is None or t - c.failed_window_started_on > throttle.GLOBAL_WINDOW:
                    c.failed_window_started_on = t
                    c.failed_login_count = 0
                c.failed_login_count += 1
                if distinct >= throttle.GLOBAL_NETWORKS and (c.locked_until is None or c.locked_until <= t):
                    c.locked_until = t + throttle.GLOBAL_THROTTLE
                    security_events.record(
                        ws,
                        "ACCOUNT_THROTTLED",
                        "SUCCESS",
                        subject_user_id=user_id,
                        detail={"scope": "global", "networks": distinct},
                    )
                    outbox.enqueue(ws, "auth.account_throttled", "app_user", user_id, user_id=user_id)

            with acting(
                s,
                ActorContext(
                    actor_id=ANONYMOUS_USER_ID,
                    via="API",
                    request_id=ctx.request_id,
                    ip=ctx.ip,
                    user_agent=ctx.user_agent,
                ),
            ):
                schedule_write(count_failure)
        raise invalid_credentials(captcha_required=_captcha_now(account_key, network))

    throttle.record_password_success(account_key, network)
    with acting(
        s, ActorContext(actor_id=user.id, via="API", request_id=ctx.request_id, ip=ctx.ip, user_agent=ctx.user_agent)
    ):
        if cred.failed_login_count or cred.failed_window_started_on:
            cred.failed_login_count = 0
            cred.failed_window_started_on = None
        if passwords.needs_rehash(cred.password_hash):
            cred.password_hash = passwords.hash_password(password)
        if factor is not None:
            token = create_challenge(s, user.id, "LOGIN")
            s.flush()
            return {
                "status": "MFA_REQUIRED",
                "mfa_token": token,
                "methods": ["totp"],
                "recovery_available": True,
                "expires_in": int(CHALLENGE_TTLS["LOGIN"].total_seconds()),
            }
        if mfa_policy(s, user).mfa_required:
            invalidate_action_tokens(s, user.id, ("MFA_ENROLLMENT",))
            tok, _ = create_action_token(s, user, "MFA_ENROLLMENT", ttl=TOKEN_TTLS["MFA_ENROLLMENT"])
            s.flush()
            outbox.enqueue(s, "auth.mfa_enrollment_link", "app_user", user.id, user_id=user.id, token_id=tok.id)
            security_events.record(s, "MFA_ENROLLMENT_EMAIL_SENT", "SUCCESS", subject_user_id=user.id)
            return {
                "status": "MFA_ENROLLMENT_EMAIL_SENT",
                "message": "Check your email to set up two-step verification.",
            }
        return complete_login(s, user, cred, methods="pwd")


def complete_login(s: Session, user: User, cred: UserCredential | None, *, methods: str) -> dict:
    now = db.tx_time(s)
    ctx = current_actor()
    with acting(
        s,
        ActorContext(
            actor_id=user.id,
            via="API",
            request_id=ctx.request_id if ctx else None,
            ip=ctx.ip if ctx else None,
            user_agent=ctx.user_agent if ctx else None,
        ),
    ):
        pwd_change = bool(cred and cred.must_change_password)
        issued = create_session(s, user, methods=methods, mfa_verified="totp" in methods, pwd_change=pwd_change)
        user.last_login_on = now
        with acting(
            s,
            ActorContext(
                actor_id=user.id,
                via="API",
                request_id=ctx.request_id if ctx else None,
                session_id=issued.session.id,
                ip=ctx.ip if ctx else None,
                user_agent=ctx.user_agent if ctx else None,
            ),
        ):
            security_events.record(s, "LOGIN", "SUCCESS", subject_user_id=user.id, detail={"method": methods})
        s.flush()
    return {
        "status": "AUTHENTICATED",
        "access_token": issued.access_token,
        "token_type": "Bearer",
        "expires_in": issued.expires_in,
        "must_change_password": pwd_change,
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "display_name": user.display_name,
            "timezone": user.timezone,
        },
        "_refresh_token": issued.refresh_token,
    }


# --- refresh (05 §6) ------------------------------------------------------------------------


def check_csrf(headers) -> None:
    cfg = settings()
    origin = headers.get("Origin")
    # Only the workspace origin may use the refresh cookie; public-site origins never can (IR-A03).
    if headers.get("X-Requested-With") != "veda-workspace" or not origin or origin != cfg.app_origin:
        raise ApiError(403, "CSRF_REJECTED", "Request rejected.")


def refresh(s: Session, raw: str | None) -> dict:
    cfg = settings()
    now = db.tx_time(s)
    if not raw:
        security_events.defer("TOKEN_REFRESH", "FAILURE", failure_reason="TOKEN_INVALID")
        raise ApiError(401, "SESSION_INVALID", "Sign in again.")
    tok = s.execute(sa.select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(raw))).scalar_one_or_none()
    if tok is None:
        security_events.defer("TOKEN_REFRESH", "FAILURE", failure_reason="TOKEN_INVALID")
        raise ApiError(401, "SESSION_INVALID", "Sign in again.")
    us = s.get(UserSession, tok.session_id)
    user = s.get(User, us.user_id, execution_options={"include_deleted": True})
    ctx = current_actor()
    user_ctx = ActorContext(
        actor_id=user.id, via="API", request_id=ctx.request_id, session_id=us.id, ip=ctx.ip, user_agent=ctx.user_agent
    )
    with acting(s, user_ctx):
        if (
            us.revoked_on is not None
            or now >= us.absolute_expires_on
            or now >= us.idle_expires_on
            or user.is_deleted
            or user.status != "ACTIVE"
        ):
            security_events.defer("TOKEN_REFRESH", "FAILURE", subject_user_id=user.id, failure_reason="SESSION_REVOKED")
            raise ApiError(401, "SESSION_INVALID", "Sign in again.")
        if tok.used_on is None:
            if tok.expires_on <= now:
                security_events.defer(
                    "TOKEN_REFRESH", "FAILURE", subject_user_id=user.id, failure_reason="TOKEN_EXPIRED"
                )
                raise ApiError(401, "SESSION_INVALID", "Sign in again.")
            new_raw = new_opaque_token()
            idle = min(now + cfg.refresh_idle_ttl, us.absolute_expires_on)
            successor = RefreshToken(session_id=us.id, token_hash=sha256_hex(new_raw), issued_on=now, expires_on=idle)
            s.add(successor)
            s.flush()
            tok.used_on = now
            tok.replaced_by_id = successor.id
            us.idle_expires_on = idle
            us.last_seen_on = now
            cred = credential_for(s, user.id)
            access, ttl = access_token_for(user, us, pwd_change=bool(cred and cred.must_change_password))
            security_events.record(s, "TOKEN_REFRESH", "SUCCESS", subject_user_id=user.id)
            return {"access_token": access, "token_type": "Bearer", "expires_in": ttl, "_refresh_token": new_raw}
        successor = s.get(RefreshToken, tok.replaced_by_id) if tok.replaced_by_id else None
        within_grace = now - tok.used_on <= cfg.refresh_grace
        if within_grace and tok.grace_used_on is None and successor is not None and successor.used_on is None:
            tok.grace_used_on = now
            cred = credential_for(s, user.id)
            access, ttl = access_token_for(user, us, pwd_change=bool(cred and cred.must_change_password))
            security_events.record(s, "TOKEN_REFRESH", "SUCCESS", subject_user_id=user.id, detail={"stage": "grace"})
            return {"access_token": access, "token_type": "Bearer", "expires_in": ttl, "_refresh_token": None}
        # Reuse outside the grace window: treat as theft (05 §6.1).
        session_id, user_id = us.id, user.id

        def revoke_for_reuse(ws: Session) -> None:
            target = ws.get(UserSession, session_id)
            revoke_session(ws, target, "TOKEN_REUSE")
            outbox.enqueue(
                ws, "auth.refresh_reuse_detected", "app_user", user_id, user_id=user_id, session_id=session_id
            )

        schedule_write(revoke_for_reuse)
        security_events.defer(
            "REFRESH_REUSE_DETECTED", "FAILURE", subject_user_id=user.id, failure_reason="TOKEN_REUSED"
        )
        raise ApiError(401, "SESSION_INVALID", "Sign in again.")


# --- password flows (05 §8) -------------------------------------------------------------------


def check_policy(password: str, user: User) -> None:
    problems = passwords.policy_violations(password, email=user.email, full_name=user.full_name)
    if problems:
        raise ApiError(
            422,
            "PASSWORD_POLICY",
            "Choose a stronger password.",
            errors=[field_error("new_password", p, _POLICY_MESSAGES[p]) for p in problems],
        )


_POLICY_MESSAGES = {
    "TOO_SHORT": "Use at least 12 characters.",
    "TOO_LONG": "Use at most 128 characters.",
    "TOO_COMMON": "This password is too common.",
    "CONTAINS_PERSONAL_INFO": "Don't include your name, email or the company name.",
}


def set_password(s: Session, user: User, password: str) -> UserCredential:
    cred = credential_for(s, user.id)
    now = db.tx_time(s)
    if cred is None:
        cred = UserCredential(user_id=user.id)
        s.add(cred)
    cred.password_hash = passwords.hash_password(password)
    cred.password_changed_on = now
    cred.must_change_password = False
    cred.failed_login_count = 0
    cred.failed_window_started_on = None
    cred.locked_until = None
    return cred


def forgot_password(s: Session, email: str) -> None:
    email_norm = normalize_email(email)
    user = find_user_by_email(s, email_norm)
    if user is None or user.user_type != "HUMAN" or user.status != "ACTIVE":
        security_events.record(
            s,
            "PASSWORD_RESET_REQUESTED",
            "FAILURE",
            failure_reason="UNKNOWN_USER" if user is None else "POLICY",
            email_attempted_hash=security_events.email_attempt_hash(email_norm),
            subject_user_id=user.id if user else None,
        )
        return
    if not throttle.reset_email_allowed(user.id):
        # Answered like any other request; the account holder already has recent links (RR-04).
        security_events.record(
            s,
            "PASSWORD_RESET_REQUESTED",
            "FAILURE",
            failure_reason="RATE_LIMITED",
            subject_user_id=user.id,
            detail={"scope": "account"},
        )
        return
    invalidate_action_tokens(s, user.id, ("PASSWORD_RESET",))
    tok, _ = create_action_token(s, user, "PASSWORD_RESET", ttl=TOKEN_TTLS["PASSWORD_RESET"])
    s.flush()
    outbox.enqueue(s, "auth.password_reset_requested", "app_user", user.id, user_id=user.id, token_id=tok.id)
    security_events.record(s, "PASSWORD_RESET_REQUESTED", "SUCCESS", subject_user_id=user.id)


def reset_password(s: Session, raw: str, new_password: str) -> None:
    tok = consume_action_token(s, raw, "PASSWORD_RESET", "RESET_TOKEN_INVALID")
    user = s.get(User, tok.user_id)
    if user is None or user.status != "ACTIVE":
        raise ApiError(400, "RESET_TOKEN_INVALID", "This link has expired or was already used.")
    ctx = current_actor()
    with acting(
        s, ActorContext(actor_id=user.id, via="API", request_id=ctx.request_id, ip=ctx.ip, user_agent=ctx.user_agent)
    ):
        check_policy(new_password, user)
        cred = credential_for(s, user.id)
        if cred and cred.password_hash and passwords.verify_password(cred.password_hash, new_password):
            raise ApiError(422, "PASSWORD_REUSED", "Choose a password you haven't used for this account.")
        set_password(s, user, new_password)
        tok.used_on = db.tx_time(s)
        throttle.clear_account(user.id)
        revoke_all_sessions(s, user.id, "PASSWORD_RESET")
        # Challenges and enrollment transactions opened with the old password end with it (IR-A04).
        invalidate_challenges(s, user.id)
        invalidate_enrollment(s, user.id)
        security_events.record(s, "PASSWORD_RESET_COMPLETED", "SUCCESS", subject_user_id=user.id)
        outbox.enqueue(s, "auth.password_changed", "app_user", user.id, user_id=user.id)


def _check_reauth_throttle(user_id: str) -> None:
    until = throttle.reauth_blocked(user_id)
    if until:
        retry = max(1, int((until - clock.now()).total_seconds()))
        raise ApiError(429, "RATE_LIMITED", "Too many attempts. Try again later.", headers={"Retry-After": str(retry)})


def _reauth_failed(user_id: str) -> None:
    if throttle.record_reauth_failure(user_id):
        security_events.defer(
            "ACCOUNT_THROTTLED",
            "SUCCESS",
            subject_user_id=user_id,
            detail={"scope": "reauth", "until": clock.to_rfc3339(throttle.reauth_blocked(user_id))},
        )


def rotate_session_refresh(s: Session, us: UserSession) -> str:
    """Issue a new refresh token for this session and retire the live ones, each linked to the successor so a
    concurrent refresh with the previous cookie gets the grace-window treatment of an ordinary rotation instead
    of reuse detection (05 §6.1, RR-08). Only tokens of this session are touched."""
    now = db.tx_time(s)
    raw = new_opaque_token()
    successor = RefreshToken(
        session_id=us.id,
        token_hash=sha256_hex(raw),
        issued_on=now,
        expires_on=min(now + settings().refresh_idle_ttl, us.absolute_expires_on),
    )
    s.add(successor)
    s.flush()
    for rt in s.execute(
        sa.select(RefreshToken).where(
            RefreshToken.session_id == us.id, RefreshToken.used_on.is_(None), RefreshToken.id != successor.id
        )
    ).scalars():
        rt.used_on = now
        rt.replaced_by_id = successor.id
    return raw


def change_password(s: Session, ctx: AuthContext, current: str, new_password: str) -> str:
    from .request_auth import require_not_cooling_off

    user = ctx.user
    require_not_cooling_off(user)
    _check_reauth_throttle(user.id)
    cred = credential_for(s, user.id)
    if cred is None or not passwords.verify_password(cred.password_hash, current):
        _reauth_failed(user.id)
        security_events.defer("PASSWORD_CHANGED", "FAILURE", subject_user_id=user.id, failure_reason="BAD_PASSWORD")
        raise invalid_credentials()
    check_policy(new_password, user)
    if passwords.verify_password(cred.password_hash, new_password):
        raise ApiError(422, "PASSWORD_REUSED", "Choose a different password.")
    set_password(s, user, new_password)
    revoke_all_sessions(s, user.id, "PASSWORD_CHANGED", except_session_id=ctx.session.id)
    # Rotate the current session's refresh token (05 §8.5).
    new_raw = rotate_session_refresh(s, ctx.session)
    security_events.record(s, "PASSWORD_CHANGED", "SUCCESS", subject_user_id=user.id)
    outbox.enqueue(s, "auth.password_changed", "app_user", user.id, user_id=user.id)
    return new_raw


def reauth(s: Session, ctx: AuthContext, password: str) -> None:
    _check_reauth_throttle(ctx.user.id)
    cred = credential_for(s, ctx.user.id)
    if cred is None or not passwords.verify_password(cred.password_hash, password):
        _reauth_failed(ctx.user.id)
        security_events.defer(
            "LOGIN", "FAILURE", subject_user_id=ctx.user.id, failure_reason="BAD_PASSWORD", detail={"stage": "reauth"}
        )
        raise invalid_credentials()
    ctx.session.reauth_on = db.tx_time(s)


# --- invitation (05 §8.4) ------------------------------------------------------------------


def accept_invite(s: Session, raw: str, new_password: str, full_name: str | None) -> dict | None:
    tok = consume_action_token(s, raw, "INVITE", "INVITE_TOKEN_INVALID")
    user = s.get(User, tok.user_id)
    if user is None or user.status != "INVITED":
        raise ApiError(400, "INVITE_TOKEN_INVALID", "This invitation has expired or was already used.")
    ctx = current_actor()
    with acting(
        s, ActorContext(actor_id=user.id, via="API", request_id=ctx.request_id, ip=ctx.ip, user_agent=ctx.user_agent)
    ):
        if full_name:
            user.full_name = full_name
        check_policy(new_password, user)
        set_password(s, user, new_password)
        if mfa_policy(s, user).mfa_required:
            # Path B: the invite token (out-of-band) + the new password are the two proofs (05 §11.3).
            # A repeated acceptance supersedes every earlier context and pending factor (IR-21).
            invalidate_enrollment(s, user.id)
            s.flush()
            context_token = create_challenge(s, user.id, "ENROLLMENT", enrollment_path="INVITE_CONTEXT")
            security_events.record(
                s, "INVITE_ACCEPTED", "SUCCESS", subject_user_id=user.id, detail={"stage": "password_set"}
            )
            s.flush()
            return {
                "status": "MFA_ENROLLMENT_REQUIRED",
                "invite_context": context_token,
                "expires_in": int(CHALLENGE_TTLS["ENROLLMENT"].total_seconds()),
            }
        activate_invited_user(s, user, tok)
    return None


def activate_invited_user(s: Session, user: User, tok: UserActionToken | None) -> None:
    now = db.tx_time(s)
    user.status = "ACTIVE"
    user.status_changed_on = now
    user.email_verified_on = now
    resolver.bump_authz_version(user)
    if tok is None:
        tok = (
            s.execute(
                sa.select(UserActionToken).where(
                    UserActionToken.user_id == user.id,
                    UserActionToken.purpose == "INVITE",
                    UserActionToken.used_on.is_(None),
                    UserActionToken.invalidated_on.is_(None),
                )
            )
            .scalars()
            .first()
        )
    if tok is not None:
        tok.used_on = now
    invalidate_action_tokens(s, user.id, ("INVITE",))
    security_events.record(s, "INVITE_ACCEPTED", "SUCCESS", subject_user_id=user.id)
    outbox.enqueue(s, "invite.accepted", "app_user", user.id, user_id=user.id)


# --- email change (05 §8.6) ---------------------------------------------------------------------


def email_in_use(s: Session, email_norm: str, *, exclude_user_id: str | None = None) -> bool:
    q = (
        sa.select(sa.func.count())
        .select_from(User)
        .where(sa.or_(User.email_normalized == email_norm, User.proposed_email_normalized == email_norm))
    )
    if exclude_user_id:
        q = q.where(User.id != exclude_user_id)
    return bool(s.execute(q).scalar())


def start_email_change(s: Session, target: User, new_email: str, *, requested_by: str) -> dict:
    email_norm = normalize_email(new_email)
    if email_norm == target.email_normalized:
        raise ApiError(
            422,
            "SAME_AS_CURRENT",
            "That is already the sign-in email.",
            errors=[field_error("new_email", "SAME_AS_CURRENT", "That is already the sign-in email.")],
        )
    if email_in_use(s, email_norm, exclude_user_id=target.id):
        raise ApiError(
            409,
            "DUPLICATE",
            "That email is in use.",
            errors=[field_error("new_email", "DUPLICATE", "That email is in use.")],
        )
    now = db.tx_time(s)
    invalidate_action_tokens(s, target.id, ("EMAIL_VERIFICATION", "EMAIL_CHANGE_CANCEL"))
    target.proposed_email = new_email.strip()
    target.proposed_email_normalized = email_norm
    target.proposed_email_requested_on = now
    target.proposed_email_requested_by = requested_by
    ttl = settings().email_verification_ttl
    verify_tok, _ = create_action_token(s, target, "EMAIL_VERIFICATION", ttl=ttl, send_to=email_norm)
    cancel_tok, _ = create_action_token(s, target, "EMAIL_CHANGE_CANCEL", ttl=ttl)
    s.flush()
    outbox.enqueue(
        s,
        "auth.email_change_requested",
        "app_user",
        target.id,
        user_id=target.id,
        verification_token_id=verify_tok.id,
        cancel_token_id=cancel_tok.id,
        requested_by=requested_by,
    )
    security_events.record(
        s,
        "EMAIL_CHANGE_REQUESTED",
        "SUCCESS",
        subject_user_id=target.id,
        detail={
            "proposed_email": mask_email(new_email),
            "requested_by": "self" if requested_by == target.id else "administrator",
        },
    )
    return {
        "status": "VERIFICATION_SENT",
        "proposed_email": mask_email(new_email),
        "expires_on": clock.to_rfc3339(verify_tok.expires_on),
    }


def verify_email_change(s: Session, raw: str) -> None:
    from veda.platform.rbac import guards

    # The governance-class check below must not interleave with a promotion or role change (OD-3): take the
    # governance lock before any row is touched, in the same order as those changes (no deadlock on PostgreSQL).
    guards.lock_governance(s)
    tok = consume_action_token(s, raw, "EMAIL_VERIFICATION", "EMAIL_TOKEN_INVALID")
    user = s.get(User, tok.user_id)
    if user is None or user.proposed_email_normalized != tok.sent_to_email_normalized:
        raise ApiError(400, "EMAIL_TOKEN_INVALID", "This link has expired or was already used.")
    from veda.platform.rbac import governance

    # OD-3: a change authorised under a weaker governance class than the account now holds (for example an
    # administrator's change to someone since promoted to Founder) never completes. The rollback leaves the
    # proposal unusable; it expires or is cancelled, and the refusal is recorded (RR-03).
    if user.status == "DISABLED" or not governance.proposal_still_authorised(s, user):
        security_events.defer(
            "EMAIL_CHANGE_VERIFIED",
            "FAILURE",
            subject_user_id=user.id,
            failure_reason="FOUNDER_PROTECTED" if user.protection_level == "FOUNDER" else "POLICY",
            detail={"reason": "ACCOUNT_DISABLED" if user.status == "DISABLED" else "GOVERNANCE_CLASS_CHANGED"},
        )
        if user.protection_level == "FOUNDER":
            security_events.defer(
                "FOUNDER_GOVERNANCE_BYPASS_BLOCKED",
                "BLOCKED",
                subject_user_id=user.id,
                target=("app_user", user.id),
                detail={"action": "email_verify"},
            )
        raise ApiError(400, "EMAIL_TOKEN_INVALID", "This link has expired or was already used.")
    ctx = current_actor()
    with acting(
        s, ActorContext(actor_id=user.id, via="API", request_id=ctx.request_id, ip=ctx.ip, user_agent=ctx.user_agent)
    ):
        if email_in_use(s, user.proposed_email_normalized, exclude_user_id=user.id):
            raise ApiError(409, "DUPLICATE", "That email is now in use by another account.")
        now = db.tx_time(s)
        old_email = user.email
        new_email = user.proposed_email
        user.email = new_email
        user.email_normalized = user.proposed_email_normalized
        user.email_verified_on = now
        user.proposed_email = None
        user.proposed_email_normalized = None
        user.proposed_email_requested_on = None
        user.proposed_email_requested_by = None
        tok.used_on = now
        invalidate_action_tokens(
            s, user.id, ("PASSWORD_RESET", "INVITE", "MFA_ENROLLMENT", "EMAIL_VERIFICATION", "EMAIL_CHANGE_CANCEL")
        )
        s.flush()
        revoke_all_sessions(s, user.id, "EMAIL_CHANGED")
        security_events.record(
            s, "EMAIL_CHANGE_VERIFIED", "SUCCESS", subject_user_id=user.id, detail={"new_email": mask_email(new_email)}
        )
        security_events.record(
            s,
            "EMAIL_CHANGE_COMPLETED",
            "SUCCESS",
            subject_user_id=user.id,
            detail={"previous_email": mask_email(old_email), "new_email": mask_email(new_email)},
        )
        from veda.platform.audit.models import AuditLog

        audit_row = s.execute(
            sa.select(AuditLog.id)
            .where(
                AuditLog.entity_type == "app_user",
                AuditLog.entity_id == user.id,
                AuditLog.transaction_id == db.transaction_id(s),
            )
            .order_by(AuditLog.id.desc())
            .limit(1)
        ).scalar()
        outbox.enqueue(s, "auth.email_change_completed", "app_user", user.id, user_id=user.id, audit_id=audit_row)


def cancel_email_change(s: Session, raw: str) -> None:
    tok = consume_action_token(s, raw, "EMAIL_CHANGE_CANCEL", "EMAIL_TOKEN_INVALID")
    user = s.get(User, tok.user_id)
    if user is None or user.proposed_email_normalized is None:
        raise ApiError(400, "EMAIL_TOKEN_INVALID", "This link has expired or was already used.")
    ctx = current_actor()
    with acting(
        s, ActorContext(actor_id=user.id, via="API", request_id=ctx.request_id, ip=ctx.ip, user_agent=ctx.user_agent)
    ):
        proposed = user.proposed_email
        clear_proposal(s, user)
        tok.used_on = db.tx_time(s)
        security_events.record(
            s,
            "EMAIL_CHANGE_CANCELLED",
            "SUCCESS",
            subject_user_id=user.id,
            detail={"proposed_email": mask_email(proposed)},
        )


def clear_proposal(s: Session, user: User) -> None:
    user.proposed_email = None
    user.proposed_email_normalized = None
    user.proposed_email_requested_on = None
    user.proposed_email_requested_by = None
    invalidate_action_tokens(s, user.id, ("EMAIL_VERIFICATION", "EMAIL_CHANGE_CANCEL"))


def pending_email_change(s: Session, user: User) -> dict | None:
    if not user.proposed_email:
        return None
    tok = (
        s.execute(
            sa.select(UserActionToken)
            .where(
                UserActionToken.user_id == user.id,
                UserActionToken.purpose == "EMAIL_VERIFICATION",
                UserActionToken.used_on.is_(None),
                UserActionToken.invalidated_on.is_(None),
            )
            .order_by(UserActionToken.created_on.desc())
        )
        .scalars()
        .first()
    )
    return {
        "proposed_email": mask_email(user.proposed_email),
        "requested_on": clock.to_rfc3339(user.proposed_email_requested_on),
        "expires_on": clock.to_rfc3339(tok.expires_on) if tok else None,
    }
