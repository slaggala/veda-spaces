"""MFA (12 §4.5): policy, enrollment proofs A–D, login challenge, recovery,
TD-C expired recovery session, TD-D challenge reuse, TD-E failed re-enrollment,
step-up, recovery codes, cooling-off, factor removal."""

import re
from datetime import timedelta

import sqlalchemy as sa

from tests.support.dbh import events, rows
from veda.kernel import clock
from veda.platform.auth import totp
from veda.platform.auth.models import MfaChallenge, UserMfaFactor, UserMfaRecoveryCode, UserSession
from veda.platform.notifications import worker
from veda.platform.notifications.email import CaptureEmailProvider


def emails_to(address):
    worker.drain_all()
    return [m for m in CaptureEmailProvider.sent if address in m.to]


def link_from(address, fragment):
    for m in reversed(emails_to(address)):
        if fragment in m.text:
            return m.text.split("#token=")[1].split()[0]
    raise AssertionError(fragment)


def secret_from_uri(uri: str) -> bytes:
    import base64

    b32 = re.search(r"secret=([A-Z2-7]+)", uri).group(1)
    return base64.b32decode(b32 + "=" * (-len(b32) % 8))


def code_for(secret: bytes) -> str:
    clock.advance(timedelta(seconds=31))
    return totp.code_at(secret, clock.now())


def login_challenge(api, user):
    r = api.post("/api/v1/auth/login", {"email": user.email, "password": user.password}, anonymous=True)
    assert r.data["status"] == "MFA_REQUIRED", r
    return r.data["mfa_token"]


def recovery_codes_for(api, factory, user) -> list[str]:
    """Rotate the factor through path A replacement to obtain a known code batch."""
    factory.login(api, user)
    r = api.post("/api/v1/auth/mfa/recovery-codes", {})
    assert r.status == 200, r
    return r.data["recovery_codes"]


# --- policy (05 §11.1) -----------------------------------------------------------------------


def test_MFA_002_policy_sources(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)
    me = api.get("/api/v1/auth/me").data
    assert me["mfa"] == {"required": False, "required_by": [], "enrolled": False}
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    assert api.get("/api/v1/auth/mfa").data["required_by"] == ["ROLE_POLICY", "SENSITIVE_PERMISSION"]
    flagged = factory.user("SALES", mfa_required=True)
    r = api.post("/api/v1/auth/login", {"email": flagged.email, "password": flagged.password}, anonymous=True)
    assert r.data["status"] == "MFA_ENROLLMENT_EMAIL_SENT" and "access_token" not in r.data


def test_MFA_014_required_without_factor_emails_link_and_never_issues_token(api, factory):
    flagged = factory.user("SALES", mfa_required=True)
    r = api.post("/api/v1/auth/login", {"email": flagged.email, "password": flagged.password}, anonymous=True)
    assert r.status == 200 and r.data == {
        "status": "MFA_ENROLLMENT_EMAIL_SENT",
        "message": "Check your email to set up two-step verification.",
    }
    assert "Set-Cookie" not in r.headers
    token = link_from(flagged.email, "two-step verification")
    # Path C needs the password too: the emailed token alone is not enough.
    assert (
        api.post("/api/v1/auth/mfa/enroll/start", {"enrollment_token": token}, anonymous=True).code
        == "ENROLLMENT_PROOF_INVALID"
    )
    assert (
        api.post(
            "/api/v1/auth/mfa/enroll/start", {"enrollment_token": token, "password": "wrong-password-1"}, anonymous=True
        ).code
        == "ENROLLMENT_PROOF_INVALID"
    )
    token = link_from(flagged.email, "two-step verification")
    r = api.post("/api/v1/auth/login", {"email": flagged.email, "password": flagged.password}, anonymous=True)
    token = link_from(flagged.email, "two-step verification")
    r = api.post(
        "/api/v1/auth/mfa/enroll/start", {"enrollment_token": token, "password": flagged.password}, anonymous=True
    )
    assert r.status == 200 and r.data["secret"] and r.data["otpauth_uri"].startswith("otpauth://totp/")
    secret = secret_from_uri(r.data["otpauth_uri"])
    r = api.post(
        "/api/v1/auth/mfa/enroll/confirm",
        {"challenge_token": r.data["challenge_token"], "code": code_for(secret), "label": "Phone"},
        anonymous=True,
    )
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED" and len(r.data["recovery_codes"]) == 10
    assert events("MFA_ENROLLMENT_COMPLETED", subject_user_id=flagged.id)
    # Secret never returned again (MFA-010).
    api.token = r.data["access_token"]
    assert "secret" not in str(api.get("/api/v1/auth/mfa").json)


def test_MFA_014_mfa_token_alone_cannot_enroll(api, factory):
    admin = factory.user("ADMIN")
    token = login_challenge(api, admin)
    r = api.post("/api/v1/auth/mfa/enroll/start", {"invite_context": token}, anonymous=True)
    assert r.status == 401
    r = api.post("/api/v1/auth/mfa/enroll/start", {}, anonymous=True)
    assert r.code == "ENROLLMENT_PROOF_INVALID"


def test_MFA_014_path_a_voluntary_enrollment_needs_fresh_password(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)
    r = api.post("/api/v1/auth/mfa/enroll/start", {"reauth": True})
    assert r.status == 403 and r.code == "STEP_UP_REQUIRED" and r.json["kind"] == "password"
    assert api.post("/api/v1/auth/reauth", {"password": "wrong-password-1"}).code == "INVALID_CREDENTIALS"
    assert api.post("/api/v1/auth/reauth", {"password": sales.password}).status == 204
    r = api.post("/api/v1/auth/mfa/enroll/start", {"reauth": True})
    assert r.status == 200
    secret = secret_from_uri(r.data["otpauth_uri"])
    bad = api.post("/api/v1/auth/mfa/enroll/confirm", {"challenge_token": r.data["challenge_token"], "code": "000000"})
    assert bad.code == "MFA_CODE_INVALID"
    r = api.post(
        "/api/v1/auth/mfa/enroll/confirm", {"challenge_token": r.data["challenge_token"], "code": code_for(secret)}
    )
    assert r.status == 200 and r.data["access_token"]
    # Voluntary enrollment is always challenged afterwards.
    r = api.post("/api/v1/auth/login", {"email": sales.email, "password": sales.password}, anonymous=True)
    assert r.data["status"] == "MFA_REQUIRED"


def test_MFA_014_path_b_invitation_enrollment(api, factory):
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    r = api.post(
        "/api/v1/users",
        {"email": "anand@vedaspaces.test", "full_name": "Anand Nair", "role_ids": [factory.role_id("ADMIN")]},
    )
    assert r.status == 201, r
    invite = link_from("anand@vedaspaces.test", "invited")
    r = api.post(
        "/api/v1/auth/invite/accept", {"token": invite, "new_password": "Harbour-Lights-Evening-3"}, anonymous=True
    )
    assert r.status == 200 and r.data["status"] == "MFA_ENROLLMENT_REQUIRED"
    r = api.post("/api/v1/auth/mfa/enroll/start", {"invite_context": r.data["invite_context"]}, anonymous=True)
    assert r.status == 200
    secret = secret_from_uri(r.data["otpauth_uri"])
    r = api.post(
        "/api/v1/auth/mfa/enroll/confirm",
        {"challenge_token": r.data["challenge_token"], "code": code_for(secret)},
        anonymous=True,
    )
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED"
    me = api.get("/api/v1/auth/me", token=r.data["access_token"]).data
    assert me["status"] == "ACTIVE" and me["suspended_permissions"] == []
    assert events("INVITE_ACCEPTED") and events("MFA_ENROLLMENT_COMPLETED")


def test_MFA_012_sensitive_grant_without_factor_is_suspended_until_enrollment(api, factory):
    founder = factory.user(founder=True)
    sales = factory.user("SALES")
    token = factory.login(api, sales)
    factory.grant(sales, "audit.read")  # granted while the session exists; effective from the next request
    me = api.get("/api/v1/auth/me", token=token).data
    assert "audit.read" not in me["permissions"]
    assert {"code": "audit.read", "reason": "MFA_REQUIRED"} in me["suspended_permissions"]
    r = api.get("/api/v1/audit-logs", token=token)
    assert r.status == 403 and r.json["reason"] == "MFA_REQUIRED"
    # N-A1: path A is not available for a sensitive holder without a factor → emailed link (path C).
    api.post("/api/v1/auth/reauth", {"password": sales.password}, token=token)
    r = api.post("/api/v1/auth/mfa/enroll/start", {"reauth": True}, token=token)
    assert r.code == "ENROLLMENT_PROOF_INVALID"
    # A fresh sign-in yields no session, only the emailed enrollment link (05 §3, §11.3 path C).
    r = api.post("/api/v1/auth/login", {"email": sales.email, "password": sales.password}, anonymous=True)
    assert r.data["status"] == "MFA_ENROLLMENT_EMAIL_SENT"
    token = link_from(sales.email, "two-step verification")
    start = api.post(
        "/api/v1/auth/mfa/enroll/start", {"enrollment_token": token, "password": sales.password}, anonymous=True
    ).data
    secret = secret_from_uri(start["otpauth_uri"])
    r = api.post(
        "/api/v1/auth/mfa/enroll/confirm",
        {"challenge_token": start["challenge_token"], "code": code_for(secret)},
        anonymous=True,
    )
    assert api.get("/api/v1/audit-logs", token=r.data["access_token"]).status == 200, "effective after enrollment"
    del founder


def test_MFA_001_login_challenge_attempt_limits(api, factory):
    admin = factory.user("ADMIN")
    token = login_challenge(api, admin)
    for i in range(5):
        r = api.post("/api/v1/auth/mfa/verify", {"mfa_token": token, "code": "000000"}, anonymous=True)
        assert r.code in ("MFA_CODE_INVALID", "MFA_CHALLENGE_INVALID"), (i, r)
    r = api.post("/api/v1/auth/mfa/verify", {"mfa_token": token, "code": admin.code()}, anonymous=True)
    assert r.code == "MFA_CHALLENGE_INVALID", "the challenge is void after 5 failures"


def test_MFA_009_code_replay_rejected(api, factory):
    admin = factory.user("ADMIN")
    code = admin.code()
    t1 = login_challenge(api, admin)
    assert api.post("/api/v1/auth/mfa/verify", {"mfa_token": t1, "code": code}, anonymous=True).status == 200
    t2 = login_challenge(api, admin)
    r = api.post("/api/v1/auth/mfa/verify", {"mfa_token": t2, "code": code}, anonymous=True)
    assert r.code == "MFA_CODE_INVALID"
    assert any(e.failure_reason == "CODE_REPLAYED" for e in events("MFA_CHALLENGE"))


def test_MFA_011_step_up_flow(api, factory):
    admin = factory.user("ADMIN")
    target = factory.user("SALES")
    factory.login(api, admin)
    clock.advance(timedelta(minutes=11))
    api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)
    r = api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)
    api.token = r.data["access_token"] if r.status == 200 else api.token
    user = factory.get_user(target.id)
    r = api.post(f"/api/v1/users/{target.id}/sessions/revoke", {"reason": "Lost phone"})
    assert r.status == 403 and r.code == "STEP_UP_REQUIRED" and r.json["kind"] == "mfa" and r.json["mfa_token"]
    assert (
        api.post("/api/v1/auth/mfa/step-up", {"mfa_token": r.json["mfa_token"], "code": "000000"}).code
        == "MFA_CODE_INVALID"
    )
    r2 = api.post(f"/api/v1/users/{target.id}/sessions/revoke", {"reason": "Lost phone"})
    assert api.post("/api/v1/auth/mfa/step-up", {"mfa_token": r2.json["mfa_token"], "code": admin.code()}).status == 204
    r = api.post(f"/api/v1/users/{target.id}/sessions/revoke", {"reason": "Lost phone"})
    assert r.status == 200
    del user


# --- recovery (MFA-013) -------------------------------------------------------------------------


def test_MFA_013_recovery_requires_password_and_code(api, factory, client):
    admin = factory.user("ADMIN")
    codes = recovery_codes_for(api, factory, admin)
    other_session = api.token
    token = login_challenge(api, admin)
    for body in (
        {"password": admin.password, "recovery_code": "AAAAA-BBBBB"},
        {"password": "wrong-password-1", "recovery_code": codes[0]},
    ):
        r = api.post("/api/v1/auth/mfa/recovery", {"mfa_token": token, **body}, anonymous=True)
        assert r.status == 401 and r.code == "MFA_RECOVERY_INVALID"
    client.delete_cookie("vs_rt", path="/api/v1/auth")
    r = api.post(
        "/api/v1/auth/mfa/recovery",
        {"mfa_token": token, "password": admin.password, "recovery_code": codes[0]},
        anonymous=True,
    )
    assert r.status == 200 and r.data["status"] == "RECOVERY_SESSION" and "Set-Cookie" not in r.headers
    rec = r.data["access_token"]
    assert api.get("/api/v1/auth/me", token=other_session).code == "SESSION_INVALID"
    for method, path in (
        ("GET", "/api/v1/users"),
        ("GET", "/api/v1/roles"),
        ("PUT", "/api/v1/auth/me/email"),
        ("POST", "/api/v1/auth/password/change"),
        ("GET", "/api/v1/leads"),
        ("GET", "/api/v1/security-events"),
    ):
        r = api.call(method, path, {"new_email": "x@y.test"} if method == "PUT" else None, token=rec)
        assert r.status == 403 and r.code == "RECOVERY_SESSION_RESTRICTED", (path, r)
    assert api.get("/api/v1/auth/me", token=rec).data["session"]["type"] == "RECOVERY"
    r = api.post("/api/v1/auth/mfa/enroll/start", {}, token=rec)
    assert r.status == 200, r
    secret = secret_from_uri(r.data["otpauth_uri"])
    r = api.post(
        "/api/v1/auth/mfa/enroll/confirm",
        {"challenge_token": r.data["challenge_token"], "code": code_for(secret)},
        token=rec,
    )
    assert r.status == 200 and r.data["cooling_off_until"] and len(r.data["recovery_codes"]) == 10
    full = r.data["access_token"]
    assert api.get("/api/v1/auth/me", token=rec).code == "SESSION_INVALID"
    me = api.get("/api/v1/auth/me", token=full).data
    assert me["session"]["type"] == "FULL" and me["session"]["cooling_off_until"]
    assert {s["reason"] for s in me["suspended_permissions"]} == {"COOLING_OFF"}
    # Old batch rejected; cooling-off blocks self-service security changes.
    token = login_challenge(api, admin)
    assert (
        api.post(
            "/api/v1/auth/mfa/recovery",
            {"mfa_token": token, "password": admin.password, "recovery_code": codes[1]},
            anonymous=True,
        ).code
        == "MFA_RECOVERY_INVALID"
    )
    assert api.put("/api/v1/auth/me/email", {"new_email": "new@vedaspaces.test"}, token=full).code == "COOLING_OFF"
    assert (
        api.post(
            "/api/v1/auth/password/change",
            {"current_password": admin.password, "new_password": "Brand-New-Phrase-77"},
            token=full,
        ).code
        == "COOLING_OFF"
    )
    assert api.post("/api/v1/auth/mfa/recovery-codes", {}, token=full).code == "COOLING_OFF"
    assert api.delete("/api/v1/auth/mfa/factor", token=full).code == "COOLING_OFF"
    kinds = {e.event_type for e in events(subject_user_id=admin.id)}
    assert {
        "MFA_RECOVERY_CODE_CONSUMED",
        "MFA_RECOVERY_INITIATED",
        "MFA_RECOVERY_COMPLETED",
        "MFA_AUTHENTICATOR_RE_ENROLLED",
        "SESSION_REVOKED",
    } <= kinds
    alerts = [m for m in emails_to(admin.email) if "recovery" in m.subject.lower()]
    assert alerts, "security notification to the verified email"


def test_TD_C_expired_recovery_session(api, factory):
    admin = factory.user("ADMIN")
    codes = recovery_codes_for(api, factory, admin)
    token = login_challenge(api, admin)
    rec = api.post(
        "/api/v1/auth/mfa/recovery",
        {"mfa_token": token, "password": admin.password, "recovery_code": codes[0]},
        anonymous=True,
    ).data["access_token"]
    api.post("/api/v1/auth/mfa/enroll/start", {}, token=rec)
    clock.advance(timedelta(minutes=15, seconds=1))
    for method, path, body in (
        ("POST", "/api/v1/auth/mfa/enroll/start", {}),
        ("GET", "/api/v1/auth/me", None),
        ("GET", "/api/v1/leads", None),
        ("PUT", "/api/v1/auth/me/email", {"new_email": "a@b.test"}),
    ):
        r = api.call(method, path, body, token=rec)
        assert r.status == 401 and r.code == "SESSION_INVALID", (path, r)
    factors = rows(sa.select(UserMfaFactor).where(UserMfaFactor.user_id == admin.id))
    assert all(f.status != "PENDING" for f in factors)
    assert any(f.revoke_reason == "ENROLLMENT_ABANDONED" for f in factors)
    assert sum(1 for f in factors if f.status == "ACTIVE") == 1, "old factor still ACTIVE"
    token = login_challenge(api, admin)
    assert (
        api.post(
            "/api/v1/auth/mfa/recovery",
            {"mfa_token": token, "password": admin.password, "recovery_code": codes[0]},
            anonymous=True,
        ).code
        == "MFA_RECOVERY_INVALID"
    ), "the consumed code stays consumed"
    token = login_challenge(api, admin)
    assert (
        api.post(
            "/api/v1/auth/mfa/recovery",
            {"mfa_token": token, "password": admin.password, "recovery_code": codes[1]},
            anonymous=True,
        ).status
        == 200
    )
    assert events("MFA_RECOVERY_SESSION_EXPIRED")
    assert len(events("MFA_RECOVERY_CODE_CONSUMED")) == 2


def test_TD_D_challenge_reuse_after_recovery(api, factory, client):
    admin = factory.user("ADMIN")
    codes = recovery_codes_for(api, factory, admin)
    s1 = factory.login(api, admin)
    s2 = factory.login(api, admin)
    s2_cookie = client.get_cookie("vs_rt", path="/api/v1/auth").value
    m1 = login_challenge(api, admin)
    m2 = login_challenge(api, admin)
    assert (
        api.post(
            "/api/v1/auth/mfa/recovery",
            {"mfa_token": m1, "password": admin.password, "recovery_code": codes[0]},
            anonymous=True,
        ).status
        == 200
    )
    assert (
        api.post("/api/v1/auth/mfa/verify", {"mfa_token": m1, "code": admin.code()}, anonymous=True).code
        == "MFA_CHALLENGE_INVALID"
    )
    assert (
        api.post("/api/v1/auth/mfa/verify", {"mfa_token": m2, "code": admin.code()}, anonymous=True).code
        == "MFA_CHALLENGE_INVALID"
    )
    assert (
        api.post(
            "/api/v1/auth/mfa/recovery",
            {"mfa_token": m2, "password": admin.password, "recovery_code": codes[1]},
            anonymous=True,
        ).code
        == "MFA_CHALLENGE_INVALID"
    )
    assert api.get("/api/v1/auth/me", token=s1).code == "SESSION_INVALID"
    client.set_cookie("vs_rt", s2_cookie, path="/api/v1/auth")
    assert api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True).code == "SESSION_INVALID"
    del s2
    assert len(events("MFA_CHALLENGE_REPLAY_BLOCKED")) >= 3
    revoked = rows(
        sa.select(UserSession).where(UserSession.user_id == admin.id, UserSession.revoke_reason == "MFA_RECOVERY")
    )
    assert len(revoked) >= 2
    challenges = rows(sa.select(MfaChallenge).where(MfaChallenge.user_id == admin.id, MfaChallenge.purpose == "LOGIN"))
    assert any(c.completed_on for c in challenges)


def test_TD_E_failed_reenrollment_commits_nothing_that_grants_access(api, factory):
    founder = factory.user(founder=True)
    codes = recovery_codes_for(api, factory, founder)
    token = login_challenge(api, founder)
    rec = api.post(
        "/api/v1/auth/mfa/recovery",
        {"mfa_token": token, "password": founder.password, "recovery_code": codes[0]},
        anonymous=True,
    ).data["access_token"]
    start = api.post("/api/v1/auth/mfa/enroll/start", {}, token=rec).data
    for _ in range(5):
        assert (
            api.post(
                "/api/v1/auth/mfa/enroll/confirm",
                {"challenge_token": start["challenge_token"], "code": "000000"},
                token=rec,
            ).status
            == 401
        )
    factors = rows(sa.select(UserMfaFactor).where(UserMfaFactor.user_id == founder.id))
    assert [f.status for f in factors].count("ACTIVE") == 1
    assert any(f.revoke_reason == "ENROLLMENT_ABANDONED" for f in factors), "F1 revoked after 5 failures"
    me = api.get("/api/v1/auth/me", token=rec).data
    assert me["session"]["type"] == "RECOVERY" and me["permissions"] == {}
    start = api.post("/api/v1/auth/mfa/enroll/start", {}, token=rec).data
    pending = [
        f for f in rows(sa.select(UserMfaFactor).where(UserMfaFactor.user_id == founder.id)) if f.status == "PENDING"
    ]
    assert len(pending) == 1
    secret = secret_from_uri(start["otpauth_uri"])
    r = api.post(
        "/api/v1/auth/mfa/enroll/confirm",
        {"challenge_token": start["challenge_token"], "code": code_for(secret)},
        token=rec,
    )
    assert r.status == 200
    factors = rows(sa.select(UserMfaFactor).where(UserMfaFactor.user_id == founder.id))
    assert [f.status for f in factors].count("ACTIVE") == 1
    assert any(f.revoke_reason == "REPLACED" for f in factors)
    old_batch = rows(
        sa.select(UserMfaRecoveryCode).where(
            UserMfaRecoveryCode.user_id == founder.id, UserMfaRecoveryCode.invalidated_on.is_not(None)
        )
    )
    assert len(old_batch) >= 9
    assert len(events("MFA_AUTHENTICATOR_RE_ENROLLED", subject_user_id=founder.id)) == 1


def test_MFA_005_regenerate_codes_needs_step_up_and_invalidates_old(api, factory):
    admin = factory.user("ADMIN")
    first = recovery_codes_for(api, factory, admin)
    clock.advance(timedelta(minutes=11))
    r = api.post("/api/v1/auth/mfa/recovery-codes", {})
    assert r.code == "STEP_UP_REQUIRED"
    assert api.post("/api/v1/auth/mfa/step-up", {"mfa_token": r.json["mfa_token"], "code": admin.code()}).status == 204
    second = api.post("/api/v1/auth/mfa/recovery-codes", {}).data["recovery_codes"]
    assert set(first).isdisjoint(second)
    token = login_challenge(api, admin)
    assert (
        api.post(
            "/api/v1/auth/mfa/recovery",
            {"mfa_token": token, "password": admin.password, "recovery_code": first[0]},
            anonymous=True,
        ).code
        == "MFA_RECOVERY_INVALID"
    )
    stored = rows(sa.select(UserMfaRecoveryCode).where(UserMfaRecoveryCode.user_id == admin.id))
    assert all(len(c.code_hash) == 64 for c in stored)
    assert not any(code.replace("-", "") in c.code_hash for c in stored for code in second), "only HMACs stored"


def test_MFA_003_factor_removal_only_when_policy_allows(api, factory):
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    assert api.delete("/api/v1/auth/mfa/factor").code == "MFA_REQUIRED_BY_POLICY"
    sales = factory.user("SALES", mfa=True)
    factory.login(api, sales)
    assert api.delete("/api/v1/auth/mfa/factor").status == 204
    r = api.post("/api/v1/auth/login", {"email": sales.email, "password": sales.password}, anonymous=True)
    assert r.data["status"] == "AUTHENTICATED"
    assert events("MFA_FACTOR_REMOVED", subject_user_id=sales.id)
