"""Authentication endpoints (08 §4). Gates are permissions or RBX entries (06 §11)."""

from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from pydantic import Field

from veda.config import settings
from veda.kernel import clock
from veda.kernel.dto import Closed, Email, Id, Query, TimeZone, mask_email, optional_text, text
from veda.kernel.errors import ApiError, not_found
from veda.kernel.http import PUBLIC_MAX_BODY, Api, Req, Result, mask_ip, no_content, ok
from veda.kernel.ratelimit import body_email_key
from veda.platform.identity import service as identity
from veda.platform.identity.models import PROFILE_FIELDS

from . import jwt_tokens, mfa, security_events, service
from .models import UserSession
from .request_auth import require_not_cooling_off, require_step_up

api = Api("auth", "/api/v1/auth", tags=("auth",))


def _with_cookie(data: dict, status: int = 200) -> Result:
    refresh = data.pop("_refresh_token", None)
    result = ok(data, status=status)
    if refresh:
        result.cookies.append(service.refresh_cookie(refresh))
    result.headers["Cache-Control"] = "no-store"
    return result


# --- login / session -------------------------------------------------------------------

class LoginIn(Closed):
    email: Annotated[str, text(254, min_len=1)]
    password: Annotated[str, Field(min_length=1, max_length=1024)]
    turnstile_token: Annotated[str | None, Field(default=None, max_length=2048)] = None


@api.route("POST", "/login", rbx="RBX-001", auth="public", body=LoginIn, requirement="AUTH-001",
           limits=["10 per minute", ("5 per minute", body_email_key)], summary="Sign in with email and password")
def login(req: Req):
    return _with_cookie(service.login(req.session, req.body.email, req.body.password, req.body.turnstile_token))


@api.route("POST", "/refresh", rbx="RBX-002", auth="public", requirement="AUTH-005", summary="Rotate the refresh token")
def refresh(req: Req):
    service.check_csrf(req.headers)
    raw = req.cookies.get(settings().cookie_name)
    try:
        return _with_cookie(service.refresh(req.session, raw))
    except ApiError as err:
        if err.code == "SESSION_INVALID":
            err.headers["Set-Cookie"] = (f"{settings().cookie_name}=; Path=/api/v1/auth; Max-Age=0; HttpOnly; "
                                         f"SameSite=Strict{'; Secure' if settings().cookie_secure else ''}")
        raise


@api.route("POST", "/logout", rbx="RBX-002", recovery_allowed=True, pwd_change_allowed=True, requirement="AUTH-007",
           summary="Revoke the current session")
def logout(req: Req):
    service.check_csrf(req.headers)
    service.revoke_session(req.session, req.ctx.session, "LOGOUT", event=False)
    security_events.record(req.session, "LOGOUT", "SUCCESS", subject_user_id=req.ctx.user.id, detail={"scope": "current"})
    result = no_content()
    result.delete_cookies.append(service.clear_cookie())
    return result


@api.route("POST", "/logout-all", rbx="RBX-002", requirement="AUTH-007", summary="Revoke all own sessions")
def logout_all(req: Req):
    service.check_csrf(req.headers)
    service.revoke_all_sessions(req.session, req.ctx.user.id, "LOGOUT_ALL")
    security_events.record(req.session, "LOGOUT", "SUCCESS", subject_user_id=req.ctx.user.id, detail={"scope": "all"})
    result = no_content()
    result.delete_cookies.append(service.clear_cookie())
    return result


@api.route("GET", "/.well-known/jwks.json", rbx="RBX-006", auth="public", write=False, requirement="AUTH-004")
def jwks_route(req: Req):
    result = Result(status=200, raw_body=jwt_tokens.jwks())
    result.headers["Cache-Control"] = "public, max-age=300"
    return result


# --- profile -------------------------------------------------------------------------------

@api.route("GET", "/me", permission="profile.read", recovery_allowed=True, pwd_change_allowed=True, write=False,
           requirement="USER-004", summary="Own profile, effective permissions and MFA state")
def me(req: Req):
    return ok(identity.me_payload(req.session, req.ctx))


class ProfilePatch(Closed):
    __not_updatable__ = frozenset({
        "email", "proposed_email", "password", "status", "roles", "permissions", "mfa_required", "protection_level",
        "is_founder",
    })
    full_name: Annotated[str | None, text(150, min_len=1)] = None
    display_name: Annotated[str | None, optional_text(80)] = None
    phone: Annotated[str | None, optional_text(30)] = None
    timezone: TimeZone | None = None
    locale: Annotated[str | None, text(10, min_len=2)] = None


@api.route("PATCH", "/me", permission="profile.update", body=ProfilePatch, if_match=True, requirement="USER-004",
           summary="Edit own profile fields only")
def patch_me(req: Req):
    req.require_version(req.ctx.user.version)
    identity.apply_profile(req.session, req.ctx.user, req.body)
    req.session.flush()
    return ok(identity.me_payload(req.session, req.ctx))


class EmailChangeIn(Closed):
    new_email: Email


@api.route("PUT", "/me/email", rbx="RBX-004", body=EmailChangeIn, status=202, requirement="USER-007",
           summary="Start the proposed-email workflow for yourself")
def change_own_email(req: Req):
    require_not_cooling_off(req.ctx.user)
    require_step_up(req.ctx, allow_password=True)
    return ok(service.start_email_change(req.session, req.ctx.user, req.body.new_email, requested_by=req.ctx.user.id),
              status=202)


class TokenIn(Closed):
    token: Annotated[str, Field(min_length=10, max_length=200)]


@api.route("POST", "/email/verify", rbx="RBX-003", auth="public", body=TokenIn, requirement="USER-007")
def verify_email(req: Req):
    service.verify_email_change(req.session, req.body.token)
    return no_content()


@api.route("POST", "/email/cancel", rbx="RBX-003", auth="public", body=TokenIn, requirement="USER-007")
def cancel_email(req: Req):
    service.cancel_email_change(req.session, req.body.token)
    return no_content()


# --- passwords -------------------------------------------------------------------------------

class ForgotIn(Closed):
    email: Email


@api.route("POST", "/password/forgot", rbx="RBX-003", auth="public", body=ForgotIn, status=202, requirement="AUTH-008",
           limits=["5 per minute", ("3 per hour", body_email_key)], max_body=PUBLIC_MAX_BODY)
def forgot(req: Req):
    service.forgot_password(req.session, req.body.email)
    return ok({"message": "If an account exists, we've emailed a reset link."}, status=202)


class ResetIn(Closed):
    token: Annotated[str, Field(min_length=10, max_length=200)]
    new_password: Annotated[str, Field(min_length=1, max_length=1024)]


@api.route("POST", "/password/reset", rbx="RBX-003", auth="public", body=ResetIn, requirement="AUTH-008",
           limits=["5 per minute"])
def reset(req: Req):
    service.reset_password(req.session, req.body.token, req.body.new_password)
    return no_content()


class ChangeIn(Closed):
    current_password: Annotated[str, Field(min_length=1, max_length=1024)]
    new_password: Annotated[str, Field(min_length=1, max_length=1024)]


@api.route("POST", "/password/change", rbx="RBX-004", body=ChangeIn, pwd_change_allowed=True, requirement="AUTH-012")
def change(req: Req):
    new_refresh = service.change_password(req.session, req.ctx, req.body.current_password, req.body.new_password)
    result = no_content()
    result.cookies.append(service.refresh_cookie(new_refresh))
    return result


class AcceptInviteIn(Closed):
    token: Annotated[str, Field(min_length=10, max_length=200)]
    new_password: Annotated[str, Field(min_length=1, max_length=1024)]
    full_name: Annotated[str | None, optional_text(150)] = None


@api.route("POST", "/invite/accept", rbx="RBX-003", auth="public", body=AcceptInviteIn, requirement="AUTH-011",
           limits=["10 per minute"])
def accept_invite(req: Req):
    outcome = service.accept_invite(req.session, req.body.token, req.body.new_password, req.body.full_name)
    return no_content() if outcome is None else ok(outcome)


class ReauthIn(Closed):
    password: Annotated[str, Field(min_length=1, max_length=1024)]


@api.route("POST", "/reauth", rbx="RBX-004", body=ReauthIn, requirement="MFA-011")
def reauth(req: Req):
    service.reauth(req.session, req.ctx, req.body.password)
    return no_content()


# --- own sessions ----------------------------------------------------------------------------

class SessionsQuery(Query):
    cursor: str | None = None
    limit: int | None = None


@api.route("GET", "/sessions", permission="session.read", query=SessionsQuery, write=False, requirement="AUTH-016")
def sessions(req: Req):
    rows = req.session.execute(
        sa.select(UserSession).where(UserSession.user_id == req.ctx.user.id, UserSession.revoked_on.is_(None),
                                     UserSession.absolute_expires_on > clock.now())
        .order_by(UserSession.last_seen_on.desc(), UserSession.id.desc())
    ).scalars().all()
    data = [{
        "id": r.id, "device_label": r.device_label, "session_type": r.session_type, "ip_address": mask_ip(r.ip_address),
        "ip_city": None, "started_on": clock.to_rfc3339(r.started_on), "last_seen_on": clock.to_rfc3339(r.last_seen_on),
        "current": r.id == req.ctx.session.id,
    } for r in rows]
    return ok(data, meta={"limit": 50, "next_cursor": None, "has_more": False})


@api.route("DELETE", "/sessions/<session_id>", permission="session.revoke", requirement="AUTH-016")
def revoke_own_session(req: Req, session_id: str):
    us = req.session.get(UserSession, session_id)
    if us is None or us.user_id != req.ctx.user.id or us.revoked_on is not None:
        raise not_found()
    service.revoke_session(req.session, us, "LOGOUT")
    return no_content()


# --- MFA -----------------------------------------------------------------------------------------

class MfaVerifyIn(Closed):
    mfa_token: Annotated[str, Field(min_length=1, max_length=200)]
    code: Annotated[str, Field(min_length=1, max_length=12)]


@api.route("POST", "/mfa/verify", rbx="RBX-001", auth="public", body=MfaVerifyIn, requirement="MFA-001",
           limits=["10 per minute"])
def mfa_verify(req: Req):
    return _with_cookie(mfa.verify_login(req.session, req.body.mfa_token, req.body.code))


class MfaRecoveryIn(Closed):
    mfa_token: Annotated[str, Field(min_length=1, max_length=200)]
    password: Annotated[str, Field(min_length=1, max_length=1024)]
    recovery_code: Annotated[str, Field(min_length=1, max_length=32)]


@api.route("POST", "/mfa/recovery", rbx="RBX-001", auth="public", body=MfaRecoveryIn, requirement="MFA-013",
           limits=["10 per minute"])
def mfa_recovery(req: Req):
    result = ok(mfa.recover(req.session, req.body.mfa_token, req.body.password, req.body.recovery_code))
    result.headers["Cache-Control"] = "no-store"
    return result


class EnrollStartIn(Closed):
    reauth: bool | None = None
    replace: bool | None = None
    invite_context: Annotated[str | None, Field(default=None, max_length=200)] = None
    enrollment_token: Annotated[str | None, Field(default=None, max_length=200)] = None
    password: Annotated[str | None, Field(default=None, max_length=1024)] = None


@api.route("POST", "/mfa/enroll/start", rbx="RBX-004", auth="optional", body=EnrollStartIn, recovery_allowed=True,
           requirement="MFA-014", limits=["10 per minute"])
def enroll_start(req: Req):
    result = ok(mfa.enroll_start(req.session, req.ctx, req.body))
    result.headers["Cache-Control"] = "no-store"
    return result


class EnrollConfirmIn(Closed):
    challenge_token: Annotated[str, Field(min_length=1, max_length=200)]
    code: Annotated[str, Field(min_length=1, max_length=12)]
    label: Annotated[str | None, optional_text(100)] = None


@api.route("POST", "/mfa/enroll/confirm", rbx="RBX-004", auth="optional", body=EnrollConfirmIn, recovery_allowed=True,
           requirement="MFA-014", limits=["10 per minute"])
def enroll_confirm(req: Req):
    return _with_cookie(mfa.enroll_confirm(req.session, req.ctx, req.body.challenge_token, req.body.code, req.body.label))


@api.route("POST", "/mfa/step-up", rbx="RBX-004", body=MfaVerifyIn, requirement="MFA-011", limits=["10 per minute"])
def mfa_step_up(req: Req):
    mfa.step_up(req.session, req.ctx, req.body.mfa_token, req.body.code)
    return no_content()


@api.route("POST", "/mfa/recovery-codes", rbx="RBX-004", requirement="MFA-005")
def mfa_regenerate(req: Req):
    result = ok({"recovery_codes": mfa.regenerate_codes(req.session, req.ctx)})
    result.headers["Cache-Control"] = "no-store"
    return result


@api.route("DELETE", "/mfa/factor", rbx="RBX-004", requirement="MFA-003")
def mfa_remove(req: Req):
    mfa.remove_factor(req.session, req.ctx)
    return no_content()


@api.route("GET", "/mfa", permission="profile.read", write=False, requirement="MFA-001")
def mfa_status(req: Req):
    return ok(mfa.status(req.session, req.ctx.user))


__all__ = ["api", "body_email_key", "mask_email", "Id", "PROFILE_FIELDS"]
