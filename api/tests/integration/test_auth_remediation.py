"""Authentication remediation (independent review IR-20…IR-25, IR-35, IR-A03, IR-A04)."""

from datetime import timedelta

import pytest

from tests.integration.test_mfa import code_for, link_from, login_challenge, secret_from_uri
from tests.integration.test_mfa_binding import path_c_transaction
from tests.support.dbh import events
from veda.kernel import clock, net

START = "/api/v1/auth/mfa/enroll/start"
CONFIRM = "/api/v1/auth/mfa/enroll/confirm"


# --- IR-20: path C never replaces an ACTIVE factor; enrollment ends open links -----------------------------


def test_IR20_P2_old_emailed_link_cannot_replace_a_factor_enrolled_by_another_path(api, factory):
    founder = factory.user(founder=True)
    ftoken = factory.login(api, founder, set_default=False)
    sales = factory.user("SALES", mfa=True)
    version = api.get(f"/api/v1/users/{sales.id}", token=ftoken).data["version"]
    assert api.post(
        f"/api/v1/users/{sales.id}/mfa/reset", {"reason": "lost phone"}, if_match=version, token=ftoken
    ).status in (200, 204)
    link = link_from(sales.email, "#token=")
    # The user signs in (MFA is optional for them) and re-enrolls voluntarily through path A…
    token = factory.login(api, sales, set_default=False)
    assert api.post("/api/v1/auth/reauth", {"password": sales.password}, token=token).status == 204
    r = api.post(START, {"reauth": True}, token=token)
    assert (
        api.post(
            CONFIRM,
            {"challenge_token": r.data["challenge_token"], "code": code_for(secret_from_uri(r.data["otpauth_uri"]))},
            token=token,
        ).status
        == 200
    )
    # …so the emailed link from the reset is dead and cannot replace the new ACTIVE factor (P2/P2b).
    r = api.post(START, {"enrollment_token": link, "password": sales.password}, anonymous=True)
    assert r.status == 401 and r.code == "ENROLLMENT_PROOF_INVALID"


def test_IR20_P2b_confirm_by_another_path_invalidates_open_enrollment_links(api, factory):
    user, _, _ = path_c_transaction(api, factory)
    # A fresh link is emailed; before using it the user completes enrollment through the first transaction.
    r = api.post("/api/v1/auth/login", {"email": user.email, "password": user.password}, anonymous=True)
    assert r.data["status"] == "MFA_ENROLLMENT_EMAIL_SENT"
    link = link_from(user.email, "two-step verification")
    r = api.post(START, {"enrollment_token": link, "password": user.password}, anonymous=True)
    assert (
        api.post(
            CONFIRM,
            {"challenge_token": r.data["challenge_token"], "code": code_for(secret_from_uri(r.data["otpauth_uri"]))},
            anonymous=True,
        ).status
        == 200
    )
    older = api.post(START, {"enrollment_token": link, "password": user.password}, anonymous=True)
    assert older.status == 401 and older.code == "ENROLLMENT_PROOF_INVALID"


def test_IR20_path_c_with_active_factor_is_refused(api, factory):
    admin = factory.user("ADMIN")  # has an ACTIVE factor
    from veda.kernel import db
    from veda.kernel.context import actor, system_context
    from veda.platform.auth import service
    from veda.platform.identity.models import User

    with actor(system_context()), db.unit_of_work(write=True) as s:
        _, raw = service.create_action_token(s, s.get(User, admin.id), "MFA_ENROLLMENT", ttl=timedelta(hours=1))
    r = api.post(START, {"enrollment_token": raw, "password": admin.password}, anonymous=True)
    assert r.status == 409 and r.code == "MFA_ALREADY_ENROLLED"


# --- IR-21: resend and repeated acceptance supersede earlier contexts ----------------------------------------


def test_IR21_P3_resend_revokes_earlier_invitation_contexts(api, factory):
    founder = factory.user(founder=True)
    ftoken = factory.login(api, founder, set_default=False)
    r = api.post(
        "/api/v1/users",
        {"email": "nisha@vedaspaces.test", "full_name": "Nisha Rao", "role_ids": [factory.role_id("ADMIN")]},
        token=ftoken,
    )
    uid = r.data["id"]
    first = link_from("nisha@vedaspaces.test", "invited")
    context = api.post(
        "/api/v1/auth/invite/accept", {"token": first, "new_password": "Harbour-Lights-Evening-3"}, anonymous=True
    ).data["invite_context"]
    assert api.post(f"/api/v1/users/{uid}/invite/resend", {}, token=ftoken).status in (200, 202, 204)
    assert api.post(START, {"invite_context": context}, anonymous=True).status == 401, "old context revoked"
    second = link_from("nisha@vedaspaces.test", "invited")
    assert second != first
    ctx2 = api.post(
        "/api/v1/auth/invite/accept", {"token": second, "new_password": "Harbour-Lights-Evening-4"}, anonymous=True
    ).data["invite_context"]
    ctx3 = api.post(
        "/api/v1/auth/invite/accept", {"token": second, "new_password": "Harbour-Lights-Evening-5"}, anonymous=True
    ).data["invite_context"]
    assert api.post(START, {"invite_context": ctx2}, anonymous=True).status == 401, "replayed acceptance supersedes"
    assert api.post(START, {"invite_context": ctx3}, anonymous=True).status == 200
    assert any((e.detail or {}).get("stage") == "password_set" for e in events("INVITE_ACCEPTED"))


# --- IR-22: network grouping ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "a,b",
    [
        ("2001:db8:1:2::1", "2001:0db8:0001:0002:ffff::9"),
        ("2001:db8::1", "2001:db8:0:0:1::2"),
        ("::ffff:49.205.10.1", "49.205.10.200"),
    ],
)
def test_IR22_same_network_for_equivalent_address_forms(a, b):
    assert net.network_of(a) == net.network_of(b)


def test_IR22_different_networks_and_invalid_input():
    assert net.network_of("2001:db8:1:2::1") != net.network_of("2001:db8:1:3::1")
    assert net.network_of("not-an-ip") == "unknown" and net.network_of(None) == "unknown"
    assert net.network_of("2001:db8:1:2::1") == "2001:db8:1:2::/64"


def test_IR22_P4_compressed_ipv6_failures_trigger_the_pair_captcha(api, factory):
    sales = factory.user("SALES")
    forms = ["2001:db8:1:2::1", "2001:db8:1:2:0:0:0:2", "2001:db8:1:2::3", "2001:0db8:0001:0002::4", "2001:db8:1:2::5"]
    for ip in forms:
        api.post(
            "/api/v1/auth/login",
            {"email": sales.email, "password": "bad-password-000"},
            anonymous=True,
            headers={"CF-Connecting-IP": ip},
        )
    r = api.post(
        "/api/v1/auth/login",
        {"email": sales.email, "password": sales.password},
        anonymous=True,
        headers={"CF-Connecting-IP": "2001:db8:1:2::99"},
    )
    assert r.status == 401 and r.json.get("captcha_required") is True
    assert not events("ACCOUNT_THROTTLED", subject_user_id=sales.id, outcome="SUCCESS") or all(
        (e.detail or {}).get("scope") != "global" for e in events("ACCOUNT_THROTTLED", subject_user_id=sales.id)
    )
    r = api.post(
        "/api/v1/auth/login",
        {"email": sales.email, "password": sales.password},
        anonymous=True,
        headers={"CF-Connecting-IP": "49.205.1.1"},
    )
    assert r.status == 200, "one /64 is one network: no false global lockout"


# --- IR-23: the per-email limit is per (email, network) ----------------------------------------------------


@pytest.mark.settings(rate_limits_enabled=True)
def test_IR23_P5_third_party_cannot_rate_limit_the_victim_from_elsewhere(api, factory):
    victim = factory.user("SALES")
    for _ in range(6):
        api.post(
            "/api/v1/auth/login",
            {"email": victim.email, "password": "bad-password-000"},
            anonymous=True,
            headers={"CF-Connecting-IP": "103.21.44.9"},
        )
    r = api.post(
        "/api/v1/auth/login",
        {"email": victim.email, "password": "bad-password-000"},
        anonymous=True,
        headers={"CF-Connecting-IP": "103.21.44.10"},
    )
    assert r.status == 429, "the attacker's network is limited"
    r = api.post(
        "/api/v1/auth/login",
        {"email": victim.email, "password": victim.password},
        anonymous=True,
        headers={"CF-Connecting-IP": "49.205.10.1"},
    )
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED"


# --- IR-24: re-authentication is throttled ----------------------------------------------------------------


def test_IR24_reauth_and_change_password_guessing_is_throttled(api, factory):
    sales = factory.user("SALES")
    token = factory.login(api, sales, set_default=False)
    for i in range(10):
        path = "/api/v1/auth/reauth" if i % 2 else "/api/v1/auth/password/change"
        body = (
            {"password": f"guess-number-{i:04d}"}
            if i % 2
            else {"current_password": f"guess-number-{i:04d}", "new_password": "Brand-New-Lantern-77"}
        )
        assert api.post(path, body, token=token).status in (401, 403, 422)
    r = api.post("/api/v1/auth/reauth", {"password": sales.password}, token=token)
    assert r.status == 429, "the correct password is refused while throttled"
    assert any((e.detail or {}).get("scope") == "reauth" for e in events("ACCOUNT_THROTTLED", subject_user_id=sales.id))
    clock.advance(timedelta(minutes=16))
    token = factory.login(api, sales, set_default=False)
    assert api.post("/api/v1/auth/reauth", {"password": sales.password}, token=token).status == 204


# --- IR-25: security-event gaps ------------------------------------------------------------------------------


def test_IR25_invalid_action_tokens_are_recorded(api, factory):
    r = api.post(
        "/api/v1/auth/password/reset", {"token": "x" * 43, "new_password": "Brand-New-Lantern-77"}, anonymous=True
    )
    assert r.status == 400
    assert any(
        e.outcome == "FAILURE" and e.failure_reason == "TOKEN_INVALID" for e in events("PASSWORD_RESET_COMPLETED")
    )


def test_IR25_csrf_rejected_refresh_is_recorded(api, factory):
    r = api.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://evil.example", "X-Requested-With": "veda-workspace"},
        anonymous=True,
    )
    assert r.status == 403 and r.code == "CSRF_REJECTED"
    assert any(
        e.outcome == "FAILURE" and (e.detail or {}).get("reason") == "CSRF_REJECTED" for e in events("TOKEN_REFRESH")
    )


def test_IR25_mfa_throttle_activation_is_recorded(api, factory):
    admin = factory.user("ADMIN")
    for _ in range(2):
        token = login_challenge(api, admin)
        for _ in range(5):
            api.post("/api/v1/auth/mfa/verify", {"mfa_token": token, "code": "000000"}, anonymous=True)
    assert any((e.detail or {}).get("scope") == "mfa" for e in events("ACCOUNT_THROTTLED", subject_user_id=admin.id))


def test_IR25_pair_throttle_activation_is_recorded(api, factory):
    sales = factory.user("SALES")
    for _ in range(5):
        api.post(
            "/api/v1/auth/login",
            {"email": sales.email, "password": "bad-password-000"},
            anonymous=True,
            headers={"CF-Connecting-IP": "49.205.10.1"},
        )
    assert any(
        (e.detail or {}).get("scope") == "network" for e in events("ACCOUNT_THROTTLED", subject_user_id=sales.id)
    )


# --- IR-A03: refresh CSRF accepts only the workspace origin -----------------------------------------------


def test_IRA03_public_site_origin_cannot_refresh(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)
    r = api.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://localhost:8000", "X-Requested-With": "veda-workspace"},
        anonymous=True,
    )
    assert r.status == 403 and r.code == "CSRF_REJECTED"
    assert api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True).status == 200


# --- IR-A04: password reset ends open MFA challenges and enrollment ---------------------------------------


def test_IRA04_password_reset_invalidates_open_challenges(api, factory):
    admin = factory.user("ADMIN")
    challenge = login_challenge(api, admin)
    api.post("/api/v1/auth/password/forgot", {"email": admin.email}, anonymous=True)
    reset = link_from(admin.email, "reset")
    assert api.post(
        "/api/v1/auth/password/reset", {"token": reset, "new_password": "Brand-New-Lantern-77"}, anonymous=True
    ).status in (200, 204)
    r = api.post("/api/v1/auth/mfa/verify", {"mfa_token": challenge, "code": admin.code()}, anonymous=True)
    assert r.status == 401 and r.code == "MFA_CHALLENGE_INVALID"


def test_IRA04_password_reset_retires_the_emailed_enrollment_link(api, factory):
    flagged = factory.user("SALES", mfa_required=True)
    r = api.post("/api/v1/auth/login", {"email": flagged.email, "password": flagged.password}, anonymous=True)
    assert r.data["status"] == "MFA_ENROLLMENT_EMAIL_SENT"
    enrollment = link_from(flagged.email, "two-step verification")
    api.post("/api/v1/auth/password/forgot", {"email": flagged.email}, anonymous=True)
    new_password = "Brand-New-Lantern-77"
    reset = link_from(flagged.email, "reset")
    assert api.post(
        "/api/v1/auth/password/reset", {"token": reset, "new_password": new_password}, anonymous=True
    ).status in (200, 204)
    # The link sent before the reset is dead even with the new password; a fresh login sends a new one.
    r = api.post(
        "/api/v1/auth/mfa/enroll/start", {"enrollment_token": enrollment, "password": new_password}, anonymous=True
    )
    assert r.status == 401 and r.code == "ENROLLMENT_PROOF_INVALID"
    r = api.post("/api/v1/auth/login", {"email": flagged.email, "password": new_password}, anonymous=True)
    assert r.data["status"] == "MFA_ENROLLMENT_EMAIL_SENT"
    fresh = link_from(flagged.email, "two-step verification")
    r = api.post("/api/v1/auth/mfa/enroll/start", {"enrollment_token": fresh, "password": new_password}, anonymous=True)
    assert r.status == 200 and r.data["secret"]


# --- IR-35: CF-Connecting-IP only from a trusted proxy -----------------------------------------------------


def test_IR35_forwarded_address_is_ignored_from_untrusted_peers(app):
    from veda import config

    assert net.client_ip("127.0.0.1", "49.205.10.1") == "49.205.10.1"
    assert net.client_ip("203.0.113.9", "49.205.10.1") == "203.0.113.9", "a direct client cannot choose its IP"
    assert net.client_ip("127.0.0.1", "not-an-ip") == "127.0.0.1"
    config.settings().trusted_proxy_cidrs = ["172.18.0.0/16"]
    try:
        assert net.client_ip("172.18.0.1", "49.205.10.1") == "49.205.10.1"
        assert net.client_ip("127.0.0.1", "49.205.10.1") == "127.0.0.1"
    finally:
        config.settings().trusted_proxy_cidrs = ["127.0.0.1/32", "::1/128"]
