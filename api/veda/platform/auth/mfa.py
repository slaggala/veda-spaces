"""MFA (ADR-006, 05 §11): login challenge, recovery, enrollment, step-up.

A new authenticator is never enrolled on a single factor (MFA-014). The four
paths each combine two independent proofs:

    A logged-in FULL session + fresh password re-entry (or step-up to replace)
    B invite token (email) + the new password set during acceptance
    C password at login + emailed MFA_ENROLLMENT token + password re-entry
    D RECOVERY session (password re-entry + recovery code)
"""

from __future__ import annotations

from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db, outbox
from veda.kernel.context import ActorContext, acting, actor, current_actor
from veda.kernel.errors import ApiError
from veda.kernel.ids import new_id
from veda.platform.identity.models import User
from veda.platform.rbac import resolver

from . import passwords, security_events, service, throttle, totp
from .crypto import decrypt_secret, encrypt_secret, new_recovery_code, recovery_code_hash, sha256_hex
from .models import MfaChallenge, UserActionToken, UserMfaFactor, UserMfaRecoveryCode, UserSession
from .request_auth import AuthContext, require_not_cooling_off, require_step_up, schedule_write

RECOVERY_ALLOWED = ["GET /auth/me", "POST /auth/mfa/enroll/start", "POST /auth/mfa/enroll/confirm", "POST /auth/logout"]
MAX_ATTEMPTS = 5


def _challenge(s: Session, raw: str | None, purpose: str) -> MfaChallenge:
    """Load a usable challenge or raise 401 MFA_CHALLENGE_INVALID (+ replay event, N-03)."""
    if not raw or not isinstance(raw, str) or len(raw) > 200:
        raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
    ch = s.execute(sa.select(MfaChallenge).where(MfaChallenge.token_hash == sha256_hex(raw))).scalar_one_or_none()
    now = db.tx_time(s)
    if ch is None or ch.purpose != purpose:
        raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
    nominal_expiry = ch.created_on + service.CHALLENGE_TTLS[ch.purpose]
    invalidated = ch.expires_on < nominal_expiry - timedelta(seconds=1)
    if ch.completed_on is not None or (invalidated and ch.expires_on <= now):
        with acting(
            s,
            ActorContext(
                actor_id=ch.user_id,
                via="API",
                request_id=current_actor().request_id,
                ip=current_actor().ip,
                user_agent=current_actor().user_agent,
            ),
        ):
            security_events.defer(
                "MFA_CHALLENGE_REPLAY_BLOCKED", "BLOCKED", subject_user_id=ch.user_id, failure_reason="TOKEN_REUSED"
            )
        raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
    if ch.expires_on <= now or ch.failed_attempts >= MAX_ATTEMPTS:
        raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
    return ch


def _as_user(user_id: str, session_id: str | None = None) -> ActorContext:
    ctx = current_actor()
    return ActorContext(
        actor_id=user_id,
        via="API",
        request_id=ctx.request_id if ctx else None,
        session_id=session_id,
        ip=ctx.ip if ctx else None,
        user_agent=ctx.user_agent if ctx else None,
    )


def _check_mfa_throttle(user_id: str) -> None:
    until = throttle.mfa_blocked(user_id)
    if until:
        retry = max(1, int((until - clock.now()).total_seconds()))
        raise ApiError(429, "RATE_LIMITED", "Too many attempts. Try again later.", headers={"Retry-After": str(retry)})


def _mfa_failed(user_id: str) -> None:
    """Count an MFA or recovery failure; record the throttle when it starts (MFA-006, IR-25)."""
    if throttle.record_mfa_failure(user_id):
        security_events.defer(
            "ACCOUNT_THROTTLED",
            "SUCCESS",
            subject_user_id=user_id,
            detail={"scope": "mfa", "until": clock.to_rfc3339(throttle.mfa_blocked(user_id))},
        )


def _count_failed_attempt(challenge_id: str, user_id: str, *, abandon_factor_on_exhaust: bool = False) -> int:
    """Increment the attempt counter in its own transaction (the request rolls back)."""
    state = {"attempts": 0}

    def write(ws: Session) -> None:
        ch = ws.get(MfaChallenge, challenge_id)
        if ch is None:
            return
        ch.failed_attempts = min(MAX_ATTEMPTS, ch.failed_attempts + 1)
        state["attempts"] = ch.failed_attempts
        if ch.failed_attempts >= MAX_ATTEMPTS and abandon_factor_on_exhaust:
            now = db.tx_time(ws)
            for f in ws.execute(
                sa.select(UserMfaFactor).where(UserMfaFactor.user_id == user_id, UserMfaFactor.status == "PENDING")
            ).scalars():
                f.status, f.revoked_on, f.revoke_reason = "REVOKED", now, "ENROLLMENT_ABANDONED"

    with actor(_as_user(user_id)):
        schedule_write(write)
    return state["attempts"]


def _secret(f: UserMfaFactor) -> bytes:
    return decrypt_secret(f.secret_ciphertext, f.wrapped_data_key, f.kms_key_arn)


# --- login challenge (05 §11.4) -------------------------------------------------------


def verify_login(s: Session, mfa_token: str, code: str) -> dict:
    ch = _challenge(s, mfa_token, "LOGIN")
    user = s.get(User, ch.user_id)
    _check_mfa_throttle(ch.user_id)
    factor = service.active_factor(s, ch.user_id)
    if user is None or user.status != "ACTIVE" or factor is None:
        raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
    now = db.tx_time(s)
    secret = _secret(factor)
    step = totp.verify(secret, str(code or ""), now, factor.last_used_step)
    if step is None:
        replay = totp.is_replay(secret, str(code or ""), now, factor.last_used_step)
        _count_failed_attempt(ch.id, user.id)
        _mfa_failed(user.id)
        with acting(s, _as_user(user.id)):
            security_events.defer(
                "MFA_CHALLENGE",
                "FAILURE",
                subject_user_id=user.id,
                failure_reason="CODE_REPLAYED" if replay else "CODE_INVALID",
                detail={"method": "totp"},
            )
        raise ApiError(
            401,
            "MFA_CODE_INVALID",
            "That code didn't work.",
            extra={"attempts_remaining": max(0, MAX_ATTEMPTS - ch.failed_attempts - 1)},
        )
    with acting(s, _as_user(user.id)):
        factor.last_used_step = step
        factor.last_used_on = now
        ch.completed_on = now
        security_events.record(s, "MFA_CHALLENGE", "SUCCESS", subject_user_id=user.id, detail={"method": "totp"})
        return service.complete_login(s, user, service.credential_for(s, user.id), methods="pwd+totp")


# --- recovery (05 §11.5) -------------------------------------------------------------


def recover(s: Session, mfa_token: str, password: str, recovery_code: str) -> dict:
    ch = _challenge(s, mfa_token, "LOGIN")
    user = s.get(User, ch.user_id)
    _check_mfa_throttle(ch.user_id)
    cred = service.credential_for(s, ch.user_id)
    password_ok = passwords.verify_password(cred.password_hash if cred else None, password or "")
    code_row = None
    if recovery_code:
        code_row = s.execute(
            sa.select(UserMfaRecoveryCode).where(
                UserMfaRecoveryCode.code_hash == recovery_code_hash(recovery_code),
                UserMfaRecoveryCode.user_id == ch.user_id,
            )
        ).scalar_one_or_none()
    code_ok = code_row is not None and code_row.used_on is None and code_row.invalidated_on is None
    if not (password_ok and code_ok) or user is None or user.status != "ACTIVE":
        _count_failed_attempt(ch.id, ch.user_id)
        _mfa_failed(ch.user_id)
        with acting(s, _as_user(ch.user_id)):
            security_events.defer(
                "MFA_RECOVERY_FAILED",
                "FAILURE",
                subject_user_id=ch.user_id,
                failure_reason="BAD_PASSWORD" if not password_ok else "RECOVERY_CODE_INVALID",
            )
        raise ApiError(401, "MFA_RECOVERY_INVALID", "Password or recovery code is incorrect.")
    now = db.tx_time(s)
    with acting(s, _as_user(user.id)):
        code_row.used_on = now
        security_events.record(s, "MFA_RECOVERY_CODE_CONSUMED", "SUCCESS", subject_user_id=user.id)
        security_events.record(s, "MFA_RECOVERY_INITIATED", "SUCCESS", subject_user_id=user.id)
        ch.completed_on = now
        service.invalidate_challenges(s, user.id, except_id=ch.id)
        service.revoke_all_sessions(s, user.id, "MFA_RECOVERY")
        issued = service.create_session(s, user, methods="pwd+recovery", session_type="RECOVERY")
        s.flush()
        with acting(s, _as_user(user.id, issued.session.id)):
            security_events.record(
                s, "MFA_RECOVERY_COMPLETED", "SUCCESS", subject_user_id=user.id, detail={"stage": "session"}
            )
        outbox.enqueue(s, "auth.mfa_recovery_completed", "app_user", user.id, user_id=user.id)
        outbox.enqueue(s, "auth.mfa_recovery_code_used", "app_user", user.id, user_id=user.id)
    return {
        "status": "RECOVERY_SESSION",
        "access_token": issued.access_token,
        "token_type": "Bearer",
        "expires_in": issued.expires_in,
        "allowed": RECOVERY_ALLOWED,
    }


# --- enrollment (05 §11.3) --------------------------------------------------------------


def _start_factor(s: Session, user: User, *, session_id: str | None, path: str) -> dict:
    """Open one enrollment transaction: a PENDING factor and a challenge bound to it, to the initiating
    session (paths A and D) and to the path. Every earlier transaction of the user ends here (IR-01)."""
    service.invalidate_enrollment(s, user.id)
    s.flush()
    secret = totp.new_secret()
    ciphertext, wrapped, arn = encrypt_secret(secret)
    factor = UserMfaFactor(
        user_id=user.id,
        factor_type="TOTP",
        status="PENDING",
        secret_ciphertext=ciphertext,
        wrapped_data_key=wrapped,
        kms_key_arn=arn,
    )
    s.add(factor)
    s.flush()
    challenge = service.create_challenge(
        s, user.id, "ENROLLMENT", session_id=session_id, factor_id=factor.id, enrollment_path=path
    )
    security_events.record(
        s, "MFA_ENROLLMENT_STARTED", "SUCCESS", subject_user_id=user.id, detail={"stage": path.lower()}
    )
    s.flush()
    b32 = totp.b32(secret)
    return {
        "otpauth_uri": totp.otpauth_uri(secret, user.email),
        "secret": b32,
        "challenge_token": challenge,
        "expires_in": int(service.CHALLENGE_TTLS["ENROLLMENT"].total_seconds()),
    }


def _path_a_blocked_reason(s: Session, user: User) -> str | None:
    """N-A1: a holder of sensitive permissions without a factor enrolls through the emailed link (path C),
    because both path-A proofs would derive from the password."""
    if service.active_factor(s, user.id) is None and resolver.load_grants(s, user.id).holds_sensitive:
        return "Use the setup link we email you. Sign out and sign in again to receive it."
    return None


def enroll_start(s: Session, ctx: AuthContext | None, body) -> dict:
    proofs = [p for p in ("reauth", "invite_context", "enrollment_token") if getattr(body, p, None)]
    if len(proofs) > 1:
        raise ApiError(401, "ENROLLMENT_PROOF_INVALID", "Provide exactly one enrollment proof.")
    now = db.tx_time(s)
    if ctx is not None and ctx.is_recovery:  # Path D
        if proofs:
            raise ApiError(401, "ENROLLMENT_PROOF_INVALID", "Recovery sessions enroll without other proofs.")
        return _start_factor(s, ctx.user, session_id=ctx.session.id, path="PATH_D")
    if not proofs:
        raise ApiError(401, "ENROLLMENT_PROOF_INVALID", "An enrollment proof is required.")
    proof = proofs[0]
    if proof == "reauth":  # Path A
        if ctx is None:
            raise ApiError(401, "AUTH_REQUIRED", "Sign in to continue.")
        existing = service.active_factor(s, ctx.user.id)
        if existing is not None:
            if not getattr(body, "replace", False):
                raise ApiError(409, "MFA_ALREADY_ENROLLED", "An authenticator is already set up.")
            require_not_cooling_off(ctx.user)
            require_step_up(ctx)  # replacement needs step-up with the existing factor
        else:
            blocked = _path_a_blocked_reason(s, ctx.user)
            if blocked:
                raise ApiError(401, "ENROLLMENT_PROOF_INVALID", blocked)
            if ctx.session.reauth_on is None or now - ctx.session.reauth_on > settings().reauth_window:
                raise ApiError(403, "STEP_UP_REQUIRED", "Confirm your password first.", extra={"kind": "password"})
        return _start_factor(s, ctx.user, session_id=ctx.session.id, path="PATH_A")
    # Paths B and C are unauthenticated by definition: the proofs name the principal, so a bearer token
    # for any account is refused rather than ignored (IR-01).
    if ctx is not None:
        raise ApiError(401, "ENROLLMENT_PROOF_INVALID", "Sign out before using a setup link.")
    if proof == "invite_context":  # Path B
        ch = _challenge(s, body.invite_context, "ENROLLMENT")
        user = s.get(User, ch.user_id)
        if (
            user is None
            or user.status != "INVITED"
            or ch.session_id is not None
            or ch.enrollment_path != "INVITE_CONTEXT"
            or not _invite_live(s, user.id)
        ):
            raise ApiError(401, "ENROLLMENT_PROOF_INVALID", "This setup link is no longer valid.")
        with acting(s, _as_user(user.id)):
            ch.completed_on = now
            return _start_factor(s, user, session_id=None, path="PATH_B")
    # Path C: emailed token + password re-entry.
    if not getattr(body, "password", None):
        raise ApiError(401, "ENROLLMENT_PROOF_INVALID", "Enter your password.")
    tok_hash = sha256_hex(body.enrollment_token)
    tok = s.execute(sa.select(UserActionToken).where(UserActionToken.token_hash == tok_hash)).scalar_one_or_none()
    if (
        tok is None
        or tok.purpose != "MFA_ENROLLMENT"
        or tok.used_on is not None
        or tok.invalidated_on is not None
        or tok.expires_on <= now
    ):
        raise ApiError(401, "ENROLLMENT_PROOF_INVALID", "This setup link has expired or was already used.")
    user = s.get(User, tok.user_id)
    cred = service.credential_for(s, tok.user_id)
    if (
        user is None
        or user.status != "ACTIVE"
        or not passwords.verify_password(cred.password_hash if cred else None, body.password)
    ):
        with acting(s, _as_user(tok.user_id)):
            security_events.defer(
                "MFA_ENROLLMENT_STARTED", "FAILURE", subject_user_id=tok.user_id, failure_reason="BAD_PASSWORD"
            )
        raise ApiError(401, "ENROLLMENT_PROOF_INVALID", "Password is incorrect.")
    if service.active_factor(s, user.id) is not None:
        # IR-20: an emailed link never replaces an ACTIVE factor; replacement is path A with step-up by it.
        with acting(s, _as_user(user.id)):
            tok.invalidated_on = now
        raise ApiError(409, "MFA_ALREADY_ENROLLED", "An authenticator is already set up. Replace it from your profile.")
    with acting(s, _as_user(user.id)):
        tok.used_on = now
        return _start_factor(s, user, session_id=None, path="PATH_C")


def _invite_live(s: Session, user_id: str) -> bool:
    """An unused invitation is still within its effective lifetime (24 h once privileged, FC-09)."""
    now = db.tx_time(s)
    return any(
        service.invite_expires_on(s, tok) > now
        for tok in s.execute(
            sa.select(UserActionToken).where(
                UserActionToken.user_id == user_id,
                UserActionToken.purpose == "INVITE",
                UserActionToken.used_on.is_(None),
                UserActionToken.invalidated_on.is_(None),
                UserActionToken.expires_on > now,
            )
        ).scalars()
    )


def _issue_recovery_codes(s: Session, user_id: str) -> list[str]:
    now = db.tx_time(s)
    for row in s.execute(
        sa.select(UserMfaRecoveryCode).where(
            UserMfaRecoveryCode.user_id == user_id,
            UserMfaRecoveryCode.used_on.is_(None),
            UserMfaRecoveryCode.invalidated_on.is_(None),
        )
    ).scalars():
        row.invalidated_on = now
    batch = new_id()
    codes = []
    for _ in range(10):
        code = new_recovery_code()
        codes.append(code)
        s.add(UserMfaRecoveryCode(user_id=user_id, batch_id=batch, code_hash=recovery_code_hash(code)))
    return codes


def _refuse_binding(ch: MfaChallenge, ctx: AuthContext | None, problem: str) -> ApiError:
    """A confirmation presented outside the transaction's binding: count it against the transaction, record a
    redacted event and answer exactly like an unknown challenge, so nothing about the owner leaks (IR-01).
    Returns the error for the caller to raise."""
    _count_failed_attempt(ch.id, ch.user_id)
    security_events.defer(
        "MFA_CHALLENGE",
        "FAILURE",
        subject_user_id=ch.user_id,
        failure_reason="TOKEN_INVALID",
        detail={
            "stage": "enrollment",
            "reason": "BINDING_MISMATCH",
            "scope": problem,
            "method": "bearer" if ctx is not None else "anonymous",
        },
    )
    return ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")


def _bound_transaction(s: Session, ctx: AuthContext | None, challenge_token: str) -> tuple[MfaChallenge, UserMfaFactor]:
    """Load the enrollment transaction and prove every binding from server state (IR-01): the path comes from
    the challenge, never from whether a bearer token was sent."""
    ch = _challenge(s, challenge_token, "ENROLLMENT")
    # Serialise concurrent confirmations of one transaction (PostgreSQL; SQLite writers are already serial).
    ch = s.execute(
        sa.select(MfaChallenge)
        .where(MfaChallenge.id == ch.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    if ch.completed_on is not None:
        _challenge(s, challenge_token, "ENROLLMENT")  # records the replay and raises
    path = ch.enrollment_path
    if path not in ("PATH_A", "PATH_B", "PATH_C", "PATH_D") or ch.factor_id is None:
        raise _refuse_binding(ch, ctx, "path")
    if path in ("PATH_A", "PATH_D"):
        if ctx is None or ctx.user.id != ch.user_id or ctx.session.id != ch.session_id:
            raise _refuse_binding(ch, ctx, "principal")
        if ctx.is_recovery != (path == "PATH_D"):
            raise _refuse_binding(ch, ctx, "session")
    elif ctx is not None or ch.session_id is not None:
        raise _refuse_binding(ch, ctx, "principal")
    factor = s.get(UserMfaFactor, ch.factor_id)
    if factor is None or factor.user_id != ch.user_id or factor.status != "PENDING":
        raise _refuse_binding(ch, ctx, "factor")
    return ch, factor


def _require_eligible(s: Session, user: User | None, path: str) -> User:
    """Re-check at confirm what start checked: account state, invitation liveness and N-A1."""
    if user is None or user.is_deleted:
        raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
    if path == "PATH_B":
        if user.status != "INVITED" or not _invite_live(s, user.id):
            raise ApiError(401, "ENROLLMENT_PROOF_INVALID", "This setup link is no longer valid.")
        return user
    if user.status != "ACTIVE":
        raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
    if path == "PATH_C" and service.active_factor(s, user.id) is not None:
        raise ApiError(409, "MFA_ALREADY_ENROLLED", "An authenticator is already set up.")
    if path == "PATH_A":
        blocked = _path_a_blocked_reason(s, user)
        if blocked:
            raise ApiError(401, "ENROLLMENT_PROOF_INVALID", blocked)
        if service.active_factor(s, user.id) is not None:
            require_not_cooling_off(user)
    return user


def _rotate_refresh(s: Session, us: UserSession) -> str:
    """The session's assurance changed: retire its refresh tokens and issue a new one (05 §6)."""
    return service.rotate_session_refresh(s, us)


def enroll_confirm(s: Session, ctx: AuthContext | None, challenge_token: str, code: str, label: str | None) -> dict:
    ch, pending = _bound_transaction(s, ctx, challenge_token)
    path = str(ch.enrollment_path)  # one of PATH_A..PATH_D, checked by _bound_transaction
    user = _require_eligible(s, s.get(User, ch.user_id), path)
    _check_mfa_throttle(user.id)
    now = db.tx_time(s)
    step = totp.verify(_secret(pending), str(code or ""), now, None)
    if step is None:
        _count_failed_attempt(ch.id, user.id, abandon_factor_on_exhaust=True)
        _mfa_failed(user.id)
        with acting(s, _as_user(user.id)):
            security_events.defer(
                "MFA_CHALLENGE",
                "FAILURE",
                subject_user_id=user.id,
                failure_reason="CODE_INVALID",
                detail={"stage": "enrollment"},
            )
        raise ApiError(
            401,
            "MFA_CODE_INVALID",
            "That code didn't work.",
            extra={"attempts_remaining": max(0, MAX_ATTEMPTS - ch.failed_attempts - 1)},
        )

    with acting(s, _as_user(user.id, ctx.session.id if ctx else None)):
        previous = service.active_factor(s, user.id)
        if previous is not None:
            previous.status, previous.revoked_on, previous.revoke_reason = "REVOKED", now, "REPLACED"
            s.flush()
        pending.status = "ACTIVE"
        pending.confirmed_on = now
        pending.label = label
        pending.last_used_step = step
        pending.last_used_on = now
        ch.completed_on = now
        # Nothing else may complete an enrollment for this user now: open transactions and links end (IR-20).
        service.invalidate_enrollment(s, user.id, except_id=ch.id)
        service.invalidate_action_tokens(s, user.id, ("MFA_ENROLLMENT",))
        codes = _issue_recovery_codes(s, user.id)
        resolver.bump_authz_version(user)
        replaced = previous is not None or path == "PATH_D"
        security_events.record(
            s,
            "MFA_AUTHENTICATOR_RE_ENROLLED" if replaced else "MFA_ENROLLMENT_COMPLETED",
            "SUCCESS",
            subject_user_id=user.id,
            detail={"stage": path.lower()},
        )
        result: dict = {}
        if path == "PATH_A":
            # Only the initiating session is elevated; the user's other sessions keep their assurance.
            if ctx is None:  # unreachable: PATH_A is bound to the caller's session (_bound_transaction)
                raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
            us = ctx.session
            us.auth_methods = "pwd+totp"
            us.mfa_verified_on = now
            refresh = _rotate_refresh(s, us)
            s.flush()
            access, ttl = service.access_token_for(user, us)
            result = {
                "status": "AUTHENTICATED",
                "access_token": access,
                "token_type": "Bearer",
                "expires_in": ttl,
                "must_change_password": False,
                "_refresh_token": refresh,
            }
        else:
            if path == "PATH_B":
                service.activate_invited_user(s, user, None)
            if path == "PATH_D":
                if ctx is None:  # unreachable: PATH_D is bound to the caller's recovery session
                    raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
                service.revoke_session(s, ctx.session, "RECOVERY_COMPLETED")
                user.security_cooling_off_until = now + settings().mfa_recovery_cooling_off
            s.flush()
            result = service.complete_login(s, user, service.credential_for(s, user.id), methods="pwd+totp")
        if path == "PATH_D":
            result["cooling_off_until"] = clock.to_rfc3339(user.security_cooling_off_until)
        if resolver.load_grants(s, user.id).holds_sensitive and path != "PATH_D":
            security_events.record(s, "PERMISSION_REACTIVATED", "SUCCESS", subject_user_id=user.id)
        result["recovery_codes"] = codes
        result["user"] = {
            "id": user.id,
            "full_name": user.full_name,
            "display_name": user.display_name,
            "timezone": user.timezone,
        }
        return result


# --- step-up and self-service (05 §11.5, §11.6) -------------------------------------------


def step_up(s: Session, ctx: AuthContext, mfa_token: str, code: str) -> None:
    ch = _challenge(s, mfa_token, "STEP_UP")
    if ch.user_id != ctx.user.id or ch.session_id != ctx.session.id:
        raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
    _check_mfa_throttle(ctx.user.id)
    factor = service.active_factor(s, ctx.user.id)
    if factor is None:
        raise ApiError(401, "MFA_CHALLENGE_INVALID", "Start again.")
    now = db.tx_time(s)
    step = totp.verify(_secret(factor), str(code or ""), now, factor.last_used_step)
    if step is None:
        _count_failed_attempt(ch.id, ctx.user.id)
        _mfa_failed(ctx.user.id)
        security_events.defer(
            "MFA_CHALLENGE",
            "FAILURE",
            subject_user_id=ctx.user.id,
            failure_reason="CODE_INVALID",
            detail={"stage": "step_up"},
        )
        raise ApiError(
            401,
            "MFA_CODE_INVALID",
            "That code didn't work.",
            extra={"attempts_remaining": max(0, MAX_ATTEMPTS - ch.failed_attempts - 1)},
        )
    factor.last_used_step = step
    factor.last_used_on = now
    ch.completed_on = now
    ctx.session.mfa_verified_on = now
    if "totp" not in ctx.session.methods:
        ctx.session.auth_methods = "pwd+totp"
    security_events.record(s, "MFA_CHALLENGE", "SUCCESS", subject_user_id=ctx.user.id, detail={"stage": "step_up"})


def regenerate_codes(s: Session, ctx: AuthContext) -> list[str]:
    require_not_cooling_off(ctx.user)
    if service.active_factor(s, ctx.user.id) is None:
        raise ApiError(409, "INVALID_STATE", "Set up an authenticator first.")
    require_step_up(ctx)
    codes = _issue_recovery_codes(s, ctx.user.id)
    security_events.record(s, "MFA_RECOVERY_CODES_REGENERATED", "SUCCESS", subject_user_id=ctx.user.id)
    return codes


def remove_factor(s: Session, ctx: AuthContext) -> None:
    require_not_cooling_off(ctx.user)
    factor = service.active_factor(s, ctx.user.id)
    if factor is None:
        raise ApiError(409, "INVALID_STATE", "No authenticator is set up.")
    require_step_up(ctx)
    policy = resolver.load_grants(s, ctx.user.id)
    if policy.mfa_required:
        raise ApiError(
            409,
            "MFA_REQUIRED_BY_POLICY",
            "Two-step verification is required for your account.",
            extra={"required_by": policy.mfa_required_by},
        )
    now = db.tx_time(s)
    factor.status, factor.revoked_on, factor.revoke_reason = "REVOKED", now, "USER_REMOVED"
    for row in s.execute(
        sa.select(UserMfaRecoveryCode).where(
            UserMfaRecoveryCode.user_id == ctx.user.id,
            UserMfaRecoveryCode.used_on.is_(None),
            UserMfaRecoveryCode.invalidated_on.is_(None),
        )
    ).scalars():
        row.invalidated_on = now
    resolver.bump_authz_version(ctx.user)
    security_events.record(s, "MFA_FACTOR_REMOVED", "SUCCESS", subject_user_id=ctx.user.id)


def status(s: Session, user: User) -> dict:
    policy = resolver.load_grants(s, user.id)
    factor = service.active_factor(s, user.id)
    remaining = s.execute(
        sa.select(sa.func.count())
        .select_from(UserMfaRecoveryCode)
        .where(
            UserMfaRecoveryCode.user_id == user.id,
            UserMfaRecoveryCode.used_on.is_(None),
            UserMfaRecoveryCode.invalidated_on.is_(None),
        )
    ).scalar()
    return {
        "required": policy.mfa_required,
        "required_by": policy.mfa_required_by,
        "factor": None
        if factor is None
        else {
            "type": factor.factor_type,
            "label": factor.label,
            "confirmed_on": clock.to_rfc3339(factor.confirmed_on),
            "last_used_on": clock.to_rfc3339(factor.last_used_on),
        },
        "recovery_codes_remaining": int(remaining or 0),
        "cooling_off_until": clock.to_rfc3339(user.security_cooling_off_until)
        if user.security_cooling_off_until and user.security_cooling_off_until > clock.now()
        else None,
    }


def admin_reset(s: Session, target: User, *, send_link: bool = True) -> None:
    """Effect of an executed MFA reset (05 §11.7): factors revoked, codes invalidated, sessions revoked,
    sensitive permissions suspended, enrollment link to the target's verified email."""
    now = db.tx_time(s)
    for f in s.execute(
        sa.select(UserMfaFactor).where(
            UserMfaFactor.user_id == target.id, UserMfaFactor.status.in_(("ACTIVE", "PENDING"))
        )
    ).scalars():
        f.status, f.revoked_on, f.revoke_reason = "REVOKED", now, "ADMIN_RESET"
    for row in s.execute(
        sa.select(UserMfaRecoveryCode).where(
            UserMfaRecoveryCode.user_id == target.id,
            UserMfaRecoveryCode.used_on.is_(None),
            UserMfaRecoveryCode.invalidated_on.is_(None),
        )
    ).scalars():
        row.invalidated_on = now
    service.revoke_all_sessions(s, target.id, "MFA_RESET")
    service.invalidate_challenges(s, target.id)
    resolver.bump_authz_version(target)
    if resolver.load_grants(s, target.id).holds_sensitive:
        security_events.record(
            s, "PERMISSION_SUSPENDED", "SUCCESS", subject_user_id=target.id, detail={"reason": "MFA_RESET"}
        )
    if send_link and target.status == "ACTIVE":
        service.invalidate_action_tokens(s, target.id, ("MFA_ENROLLMENT",))
        tok, _ = service.create_action_token(s, target, "MFA_ENROLLMENT", ttl=service.TOKEN_TTLS["MFA_ENROLLMENT"])
        s.flush()
        outbox.enqueue(s, "auth.mfa_enrollment_link", "app_user", target.id, user_id=target.id, token_id=tok.id)
