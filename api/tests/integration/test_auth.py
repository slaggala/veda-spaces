"""Authentication (12 §4.5): login outcomes, throttling, sessions, refresh grace,
CSRF, revocation, password reset/change, invitation."""

from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support.dbh import events  # noqa: E402
from tests.support.factory import DEFAULT_PASSWORD
from veda.kernel import clock, db
from veda.platform.auth.models import UserSession
from veda.platform.notifications import worker
from veda.platform.notifications.email import CaptureEmailProvider


def link_token(template_fragment: str, to: str) -> str:
    worker.drain_all()
    for msg in reversed(CaptureEmailProvider.sent):
        if to in msg.to and template_fragment in msg.text:
            return msg.text.split("#token=")[1].split()[0]
    raise AssertionError(f"no email with {template_fragment} to {to}")


def test_AUTH_009_uniform_login_failures(api, factory):
    active = factory.user("SALES")
    invited = factory.user("SALES", status="INVITED")
    disabled = factory.user("SALES", status="DISABLED")
    cases = [
        (active.email, "wrong-password-123"),
        ("nobody@vedaspaces.test", "whatever-12345"),
        (invited.email, invited.password),
        (disabled.email, disabled.password),
        ("system@system.vedaspaces.invalid", "x" * 12),
    ]
    for email, password in cases:
        r = api.post("/api/v1/auth/login", {"email": email, "password": password}, anonymous=True)
        assert r.status == 401 and r.code == "INVALID_CREDENTIALS", (email, r)
        assert set(r.json) == {"type", "title", "status", "code", "detail", "request_id"}
    reasons = {e.failure_reason for e in events("LOGIN", outcome="FAILURE")}
    assert {"BAD_PASSWORD", "UNKNOWN_USER", "INVITED", "DISABLED", "NOT_HUMAN"} <= reasons
    unknown = [e for e in events("LOGIN") if e.failure_reason == "UNKNOWN_USER"][0]
    assert unknown.email_attempted_hash and len(unknown.email_attempted_hash) == 64
    assert unknown.created_by == "00000000000070008000000000000003"  # ANONYMOUS


def test_AUTH_001_login_sets_refresh_cookie_and_session(api, factory, client):
    sales = factory.user("SALES")
    r = api.post("/api/v1/auth/login", {"email": sales.email.upper(), "password": sales.password}, anonymous=True)
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED"
    cookie = r.headers.get("Set-Cookie")
    assert "vs_rt=" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Path=/api/v1/auth" in cookie
    assert r.data["expires_in"] == 900 and r.data["token_type"] == "Bearer"
    assert events("LOGIN", outcome="SUCCESS")


def test_AUTH_010_throttle_is_per_account_and_network(api, factory):
    sales = factory.user("SALES")
    net_a = {"CF-Connecting-IP": "49.205.10.1"}
    net_b = {"CF-Connecting-IP": "103.21.44.9"}
    for _ in range(5):
        api.post(
            "/api/v1/auth/login", {"email": sales.email, "password": "bad-password-000"}, anonymous=True, headers=net_a
        )
    r = api.post(
        "/api/v1/auth/login", {"email": sales.email, "password": sales.password}, anonymous=True, headers=net_a
    )
    assert r.status == 401 and r.json.get("captcha_required") is True
    # The same account from another network is not locked out (A-01).
    r = api.post(
        "/api/v1/auth/login", {"email": sales.email, "password": sales.password}, anonymous=True, headers=net_b
    )
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED"


def test_AUTH_010_distributed_guessing_throttles_account_but_not_mfa_holders(api, factory):
    sales = factory.user("SALES")
    admin = factory.user("ADMIN")
    for user in (sales, admin):
        for i in range(5):
            api.post(
                "/api/v1/auth/login",
                {"email": user.email, "password": "bad-password-000"},
                anonymous=True,
                headers={"CF-Connecting-IP": f"10.{i}.0.1"},
            )
    r = api.post(
        "/api/v1/auth/login",
        {"email": sales.email, "password": sales.password},
        anonymous=True,
        headers={"CF-Connecting-IP": "172.16.9.9"},
    )
    assert r.status == 401, "global throttle applies to a password-only account"
    assert events("ACCOUNT_THROTTLED", subject_user_id=sales.id)
    r = api.post(
        "/api/v1/auth/login",
        {"email": admin.email, "password": admin.password},
        anonymous=True,
        headers={"CF-Connecting-IP": "172.16.9.9"},
    )
    assert r.status == 200 and r.data["status"] == "MFA_REQUIRED", "password + TOTP still succeeds (A-01)"


def test_AUTH_006_revocation_applies_on_next_request(api, factory):
    sales = factory.user("SALES")
    token = factory.login(api, sales)
    assert api.get("/api/v1/auth/me").status == 200
    r = api.post("/api/v1/auth/logout", headers=api.csrf_headers())
    assert r.status == 204
    r = api.get("/api/v1/auth/me", token=token)
    assert r.status == 401 and r.code == "SESSION_INVALID"


def test_AUTH_007_logout_all_revokes_every_session(api, factory):
    sales = factory.user("SALES")
    t1 = factory.login(api, sales)
    t2 = factory.login(api, sales)
    assert api.post("/api/v1/auth/logout-all", token=t2, headers=api.csrf_headers()).status == 204
    for t in (t1, t2):
        assert api.get("/api/v1/auth/me", token=t).code == "SESSION_INVALID"


def test_AUTH_005_refresh_rotation_and_grace_window(api, factory, client):
    sales = factory.user("SALES")
    factory.login(api, sales)
    old_cookie = client.get_cookie("vs_rt", path="/api/v1/auth").value
    r = api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)
    assert r.status == 200 and "vs_rt=" in (r.headers.get("Set-Cookie") or "")
    new_cookie = client.get_cookie("vs_rt", path="/api/v1/auth").value
    assert new_cookie != old_cookie
    # Second presentation of the old token within 20 s → access token only, no Set-Cookie (F-10).
    client.set_cookie("vs_rt", old_cookie, path="/api/v1/auth")
    r = api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)
    assert r.status == 200 and r.data["access_token"] and "Set-Cookie" not in r.headers
    # Third presentation → theft: the session is revoked.
    r = api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)
    assert r.status == 401 and r.code == "SESSION_INVALID"
    assert events("REFRESH_REUSE_DETECTED")[0].severity == "CRITICAL"
    client.set_cookie("vs_rt", new_cookie, path="/api/v1/auth")
    assert api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True).status == 401


def test_AUTH_005_reuse_after_grace_window_is_theft(api, factory, client):
    sales = factory.user("SALES")
    factory.login(api, sales)
    old_cookie = client.get_cookie("vs_rt", path="/api/v1/auth").value
    assert api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True).status == 200
    clock.advance(timedelta(seconds=21))
    client.set_cookie("vs_rt", old_cookie, path="/api/v1/auth")
    r = api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)
    assert r.status == 401
    worker.drain_all()
    assert any(sales.email in m.to for m in CaptureEmailProvider.sent), "the user is emailed (AUTH-005)"


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "http://localhost:5173"},
        {"X-Requested-With": "veda-workspace"},
        {"Origin": "https://evil.example", "X-Requested-With": "veda-workspace"},
    ],
)
def test_CSRF_refresh_and_logout_require_origin_and_header(api, factory, headers):
    sales = factory.user("SALES")
    factory.login(api, sales)
    assert api.post("/api/v1/auth/refresh", headers=headers, anonymous=True).code == "CSRF_REJECTED"
    assert api.post("/api/v1/auth/logout", headers=headers).code == "CSRF_REJECTED"


def test_AUTH_016_own_sessions_list_and_revoke(api, factory):
    sales = factory.user("SALES")
    t1 = factory.login(api, sales)
    t2 = factory.login(api, sales)
    r = api.get("/api/v1/auth/sessions", token=t2)
    assert r.status == 200 and len(r.data) == 2 and sum(1 for x in r.data if x["current"]) == 1
    other = next(x["id"] for x in r.data if not x["current"])
    assert api.delete(f"/api/v1/auth/sessions/{other}", token=t2).status == 204
    assert api.get("/api/v1/auth/me", token=t1).code == "SESSION_INVALID"
    stranger = factory.user("SALES")
    t3 = factory.login(api, stranger)
    current = api.get("/api/v1/auth/sessions", token=t2).data[0]["id"]
    assert api.delete(f"/api/v1/auth/sessions/{current}", token=t3).status == 404


def test_AUTH_008_forgot_is_enumeration_safe_and_reset_revokes_sessions(api, factory):
    sales = factory.user("SALES")
    token = factory.login(api, sales)
    for email in (sales.email, "nobody@vedaspaces.test"):
        r = api.post("/api/v1/auth/password/forgot", {"email": email}, anonymous=True)
        assert r.status == 202 and r.data == {"message": "If an account exists, we've emailed a reset link."}
    reset = link_token("set a new password", sales.email)
    r = api.post("/api/v1/auth/password/reset", {"token": reset, "new_password": "short"}, anonymous=True)
    assert r.status == 422 and r.code == "PASSWORD_POLICY"
    r = api.post(
        "/api/v1/auth/password/reset", {"token": reset, "new_password": "Mango-Monsoon-Courtyard-7"}, anonymous=True
    )
    assert r.status == 204
    assert api.get("/api/v1/auth/me", token=token).code == "SESSION_INVALID"
    assert (
        api.post(
            "/api/v1/auth/password/reset", {"token": reset, "new_password": "Another-Long-Phrase-99"}, anonymous=True
        ).code
        == "RESET_TOKEN_INVALID"
    )
    sales.password = "Mango-Monsoon-Courtyard-7"
    factory.login(api, sales)
    assert events("PASSWORD_RESET_COMPLETED", subject_user_id=sales.id)


def test_AUTH_008_reset_does_not_bypass_mfa(api, factory):
    admin = factory.user("ADMIN")
    api.post("/api/v1/auth/password/forgot", {"email": admin.email}, anonymous=True)
    token = link_token("set a new password", admin.email)
    api.post(
        "/api/v1/auth/password/reset", {"token": token, "new_password": "Mango-Monsoon-Courtyard-7"}, anonymous=True
    )
    r = api.post("/api/v1/auth/login", {"email": admin.email, "password": "Mango-Monsoon-Courtyard-7"}, anonymous=True)
    assert r.data["status"] == "MFA_REQUIRED"


def test_AUTH_012_change_password_requires_current_and_revokes_others(api, factory):
    sales = factory.user("SALES")
    other = factory.login(api, sales)
    token = factory.login(api, sales)
    r = api.post(
        "/api/v1/auth/password/change",
        {"current_password": "nope-nope-nope", "new_password": "Fresh-Jasmine-Terrace-4"},
    )
    assert r.status == 401 and r.code == "INVALID_CREDENTIALS"
    r = api.post("/api/v1/auth/password/change", {"current_password": sales.password, "new_password": sales.password})
    assert r.code == "PASSWORD_REUSED"
    r = api.post(
        "/api/v1/auth/password/change", {"current_password": sales.password, "new_password": "Fresh-Jasmine-Terrace-4"}
    )
    assert r.status == 204 and "vs_rt=" in r.headers.get("Set-Cookie", "")
    assert api.get("/api/v1/auth/me", token=other).code == "SESSION_INVALID"
    assert api.get("/api/v1/auth/me", token=token).status == 200


def test_AUTH_011_invite_accept_without_mfa_requirement(api, factory):
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    r = api.post(
        "/api/v1/users",
        {"email": "ravi@vedaspaces.test", "full_name": "Ravi Kumar", "role_ids": [factory.role_id("SALES")]},
    )
    assert r.status == 201 and r.data["status"] == "INVITED"
    invite = link_token("invited to Veda Workspace", "ravi@vedaspaces.test")
    r = api.post(
        "/api/v1/auth/invite/accept", {"token": invite, "new_password": "Monsoon-Garden-Window-88"}, anonymous=True
    )
    assert r.status == 204
    r = api.post(
        "/api/v1/auth/login", {"email": "ravi@vedaspaces.test", "password": "Monsoon-Garden-Window-88"}, anonymous=True
    )
    assert r.data["status"] == "AUTHENTICATED"
    assert (
        api.post(
            "/api/v1/auth/invite/accept", {"token": invite, "new_password": "Monsoon-Garden-Window-88"}, anonymous=True
        ).code
        == "INVITE_TOKEN_INVALID"
    )
    assert events("INVITE_ACCEPTED")


def test_USER_001_duplicate_email_case_insensitive(api, factory):
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    sales = factory.user("SALES")
    r = api.post("/api/v1/users", {"email": sales.email.upper(), "full_name": "Dup"})
    assert r.status == 409 and r.code == "DUPLICATE"


def test_must_change_password_restricts_endpoints(api, factory):
    sales = factory.user("SALES")
    from veda.kernel.context import actor, system_context
    from veda.platform.auth.service import credential_for

    with actor(system_context()), db.unit_of_work(write=True) as s:
        credential_for(s, sales.id).must_change_password = True
    r = api.post("/api/v1/auth/login", {"email": sales.email, "password": sales.password}, anonymous=True)
    token = r.data["access_token"]
    assert r.data["must_change_password"] is True
    assert api.get("/api/v1/auth/me", token=token).status == 200
    assert api.get("/api/v1/leads", token=token).code == "PASSWORD_CHANGE_REQUIRED"
    r = api.post(
        "/api/v1/auth/password/change",
        {"current_password": sales.password, "new_password": "Fresh-Jasmine-Terrace-4"},
        token=token,
    )
    assert r.status == 204


def test_AUTH_004_jwks_and_token_claims(api, factory):
    import jwt

    r = api.get("/api/v1/auth/.well-known/jwks.json", anonymous=True)
    assert r.status == 200 and r.json["keys"][0]["alg"] == "ES256"
    sales = factory.user("SALES")
    token = factory.login(api, sales)
    header = jwt.get_unverified_header(token)
    claims = jwt.decode(token, options={"verify_signature": False})
    assert header["typ"] == "at+jwt" and header["alg"] == "ES256" and header["kid"]
    assert {"iss", "aud", "sub", "sid", "jti", "iat", "nbf", "exp", "av", "amr", "stp"} <= set(claims)
    assert "permissions" not in claims and "email" not in claims
    clock.advance(timedelta(minutes=16))
    assert api.get("/api/v1/auth/me", token=token).code == "TOKEN_EXPIRED"


def test_session_last_seen_is_touched_at_most_every_five_minutes(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)
    with db.unit_of_work(write=False) as s:
        first = s.execute(sa.select(UserSession.last_seen_on).where(UserSession.user_id == sales.id)).scalar()
    clock.advance(timedelta(minutes=6))
    api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)
    with db.unit_of_work(write=False) as s:
        later = s.execute(sa.select(UserSession.last_seen_on).where(UserSession.user_id == sales.id)).scalar()
    assert later > first


def test_password_is_never_stored_or_logged_in_events(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)
    api.post("/api/v1/auth/login", {"email": sales.email, "password": "Very-Secret-Guess-1"}, anonymous=True)
    for e in events():
        blob = str(e.detail) + str(e.failure_reason) + str(e.user_agent)
        assert "Very-Secret-Guess-1" not in blob and DEFAULT_PASSWORD not in blob


def test_DATA_004_token_flows_are_attributed_to_the_user(api, factory):
    from tests.support.dbh import audits

    sales = factory.user("SALES")
    api.post("/api/v1/auth/password/forgot", {"email": sales.email}, anonymous=True)
    token = link_token("set a new password", sales.email)
    api.post(
        "/api/v1/auth/password/reset", {"token": token, "new_password": "Mango-Monsoon-Courtyard-7"}, anonymous=True
    )
    update = [a for a in audits(entity_type="user_credential", parent_entity_id=sales.id) if a.action == "UPDATE"][-1]
    assert update.performed_by == sales.id


def test_DEV_003_optional_captcha_token_after_network_throttle(api, factory):
    """DEV-003: login accepts an optional turnstile_token; after 5 failures from one network it is required."""
    sales = factory.user("SALES")
    net = {"CF-Connecting-IP": "49.205.77.1"}
    ok = api.post(
        "/api/v1/auth/login",
        {"email": sales.email, "password": sales.password, "turnstile_token": "unused"},
        anonymous=True,
        headers=net,
    )
    assert ok.status == 200, "the optional token is accepted and ignored before throttling"
    for _ in range(5):
        api.post(
            "/api/v1/auth/login", {"email": sales.email, "password": "bad-password-000"}, anonymous=True, headers=net
        )
    clock.advance(timedelta(minutes=16))  # past the escalating delay; the captcha requirement remains
    r = api.post("/api/v1/auth/login", {"email": sales.email, "password": sales.password}, anonymous=True, headers=net)
    assert r.status == 401 and r.json["captcha_required"] is True
    r = api.post(
        "/api/v1/auth/login",
        {"email": sales.email, "password": sales.password, "turnstile_token": "fail-x"},
        anonymous=True,
        headers=net,
    )
    assert r.status == 401 and r.json["captcha_required"] is True
    r = api.post(
        "/api/v1/auth/login",
        {"email": sales.email, "password": sales.password, "turnstile_token": "ok-token"},
        anonymous=True,
        headers=net,
    )
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED"
    unknown = api.post("/api/v1/auth/login", {"email": "nobody@vedaspaces.test", "password": "x" * 12}, anonymous=True)
    assert "captcha_required" not in unknown.json, "no enumeration signal on a first failure"
