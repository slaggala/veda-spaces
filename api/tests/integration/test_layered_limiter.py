"""Layered sign-in limiting (targeted re-review RR-04, DEV-007; proposed amendment AM-7 revised).

The reviewer's probe — 40 guesses in one minute against one account from eight IPv6 /64s, all evaluated, and 18
reset emails — is bounded here, while the IR-23 property (a third party cannot rate-limit the victim from its own
network) and the certified per-(account, network) throttle still hold.
"""

import threading
from collections import deque
from datetime import timedelta

import pytest

from tests.integration.test_mfa import emails_to, link_from, login_challenge
from tests.support.dbh import events
from veda.kernel import clock
from veda.platform.auth import throttle

LOGIN = "/api/v1/auth/login"
BAD = "not-the-password-0"


def _login(api, email, password, ip, token=None):
    body = {"email": email, "password": password}
    if token:
        body["turnstile_token"] = token
    return api.post(LOGIN, body, anonymous=True, headers={"CF-Connecting-IP": ip})


def _shape(r):
    return (r.status, r.code, (r.json or {}).get("captcha_required"), r.headers.get("Retry-After") is not None)


def _v6(i):
    return f"2001:db8:{i:x}:{i:x}::7"  # a distinct /48 and /64 per attempt: pure rotation


# --- many networks → one account ---------------------------------------------------------------------------


def test_RR04_many_networks_one_mfa_account_is_bounded_without_lockout(api, factory):
    victim = factory.user("ADMIN")  # an MFA holder: the certified global lock never applies (05 §4)
    shapes = [_shape(_login(api, victim.email, BAD, _v6(i))) for i in range(throttle.ACCOUNT_CAPTCHA_FAILURES)]
    assert all(s[0] == 401 for s in shapes)
    # The password oracle is closed: the correct password without a challenge is not evaluated.
    r = _login(api, victim.email, victim.password, _v6(100))
    assert r.status == 401 and r.json["captcha_required"] is True and "mfa_token" not in (r.data or {})
    # The victim still signs in by solving the challenge (no lockout).
    r = _login(api, victim.email, victim.password, _v6(101), token="solved")
    assert r.status == 200 and r.data["status"] == "MFA_REQUIRED"
    # Further guesses need a solved challenge each; past the delay tier they are also spaced out.
    for i in range(throttle.ACCOUNT_DELAY_FAILURES - throttle.ACCOUNT_CAPTCHA_FAILURES):
        assert _login(api, victim.email, BAD, _v6(200 + i), token="solved").status == 401
    r = _login(api, victim.email, BAD, _v6(300), token="solved")
    assert r.status == 429 and r.code == "RATE_LIMITED" and int(r.headers["Retry-After"]) >= 1
    clock.advance(timedelta(seconds=int(r.headers["Retry-After"])))
    r = _login(api, victim.email, victim.password, _v6(301), token="solved")
    assert r.status == 200 and r.data["status"] == "MFA_REQUIRED", "victim-targeted DoS is bounded to seconds"
    throttled = [e.detail["scope"] for e in events("ACCOUNT_THROTTLED", subject_user_id=victim.id)]
    assert "account_challenge" in throttled and "account_delay" in throttled


def test_RR04_reviewer_probe_forty_guesses_from_eight_networks(api, factory):
    victim = factory.user("ADMIN")
    evaluated = 0
    for i in range(40):
        r = _login(api, victim.email, BAD, _v6(i % 8))
        if r.status == 401 and not r.json.get("captcha_required"):
            evaluated += 1
    assert evaluated <= throttle.ACCOUNT_CAPTCHA_FAILURES, f"{evaluated} unchallenged guesses (was 40)"


def test_RR04_non_mfa_victim_keeps_the_certified_global_lock_and_the_budget(api, factory):
    victim = factory.user("SALES")
    for i in range(throttle.GLOBAL_NETWORKS):
        _login(api, victim.email, BAD, f"49.{i}.1.1")
    r = _login(api, victim.email, victim.password, "49.200.1.1")
    assert r.status == 401, "certified 05 §4 lock for accounts without a factor"


def test_RR04_nonexistent_account_is_indistinguishable(api, factory):
    real = factory.user("ADMIN")
    ghost = "nobody-here@vedaspaces.test"
    seq = []
    for email in (real.email, ghost):
        throttle.reset()
        seq.append(
            [_shape(_login(api, email, BAD, _v6(i))) for i in range(throttle.ACCOUNT_DELAY_FAILURES + 1)]
            + [_shape(_login(api, email, BAD, _v6(99), token="solved"))]
        )
    assert seq[0] == seq[1]
    hashed = [e for e in events("ACCOUNT_THROTTLED") if e.subject_user_id is None]
    assert hashed and all(e.email_attempted_hash and ghost not in str(e.detail) for e in hashed)


def test_RR04_successful_sign_in_does_not_reset_the_budget(api, factory):
    victim = factory.user("ADMIN")
    for i in range(throttle.ACCOUNT_CAPTCHA_FAILURES):
        _login(api, victim.email, BAD, _v6(i))
    assert _login(api, victim.email, victim.password, _v6(50), token="solved").data["status"] == "MFA_REQUIRED"
    r = _login(api, victim.email, BAD, _v6(51))
    assert r.json["captcha_required"] is True, "the attacker's failures only decay with the window"
    clock.advance(throttle.ACCOUNT_WINDOW + timedelta(seconds=1))
    r = _login(api, victim.email, victim.password, _v6(52))
    assert r.status == 200 and r.data["status"] == "MFA_REQUIRED"


# --- one network → one account / many accounts ------------------------------------------------------------


def test_RR04_one_network_one_account_pair_throttle_still_applies(api, factory):
    victim = factory.user("SALES")
    for _ in range(throttle.PAIR_THRESHOLD):
        _login(api, victim.email, BAD, "103.21.44.9")
    assert _login(api, victim.email, victim.password, "103.21.44.10").json["captcha_required"] is True
    r = _login(api, victim.email, victim.password, "49.205.10.1")
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED", "IR-23: another network is unaffected"


@pytest.mark.settings(rate_limits_enabled=True)
def test_RR04_one_network_many_accounts_hits_the_source_limit(api, factory):
    statuses = [_login(api, f"victim{i}@vedaspaces.test", BAD, "198.51.100.7").status for i in range(11)]
    assert statuses[:10] == [401] * 10 and statuses[10] == 429


@pytest.mark.settings(rate_limits_enabled=True)
def test_RR04_ipv6_rotation_inside_one_allocation_shares_a_budget(api, factory):
    statuses = [_login(api, f"target{i}@vedaspaces.test", BAD, f"2001:db8:77:{i:x}::1").status for i in range(31)]
    assert statuses[:30] == [401] * 30 and statuses[30] == 429, "rotating /64s inside one /48"


def test_RR04_aggregate_escalation_across_accounts_and_networks(api, factory, monkeypatch):
    monkeypatch.setattr(throttle, "AGGREGATE_CAPTCHA_FAILURES", 5)
    monkeypatch.setattr(throttle, "_aggregate", deque(maxlen=5))
    bystander = factory.user("SALES")
    for i in range(5):
        _login(api, f"stuffed{i}@vedaspaces.test", BAD, _v6(i))
    r = _login(api, bystander.email, bystander.password, "49.205.10.1")
    assert r.status == 401 and r.json["captcha_required"] is True
    r = _login(api, bystander.email, bystander.password, "49.205.10.1", token="solved")
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED"
    clock.advance(throttle.AGGREGATE_WINDOW + timedelta(seconds=1))
    assert _login(api, bystander.email, bystander.password, "49.205.10.2").status == 200


# --- trusted proxy and spoofing ------------------------------------------------------------------------------


def test_RR04_forwarded_header_from_an_untrusted_peer_cannot_rotate_networks(app, factory):
    victim = factory.user("SALES")
    client = app.test_client()

    def attempt(i, password=BAD):
        return client.post(
            LOGIN,
            json={"email": victim.email, "password": password},
            headers={"CF-Connecting-IP": f"49.{i}.9.9"},
            environ_base={"REMOTE_ADDR": "203.0.113.9"},
        )

    for i in range(throttle.PAIR_THRESHOLD):
        attempt(i)
    r = attempt(99, victim.password)
    assert r.status_code == 401 and r.get_json()["captcha_required"] is True, "all attempts are one network"
    assert not [e for e in events("ACCOUNT_THROTTLED", subject_user_id=victim.id) if e.detail["scope"] == "global"]


def test_RR04_challenge_provider_failure_fails_closed(api, factory):
    victim = factory.user("ADMIN")
    for i in range(throttle.ACCOUNT_CAPTCHA_FAILURES):
        _login(api, victim.email, BAD, _v6(i))
    r = _login(api, victim.email, victim.password, _v6(40), token="fail-provider-down")
    assert r.status == 401 and r.json["captcha_required"] is True
    failures = [e for e in events("LOGIN", subject_user_id=victim.id) if e.failure_reason == "CAPTCHA_FAILED"]
    assert failures


# --- reset emails, recovery, email change, MFA confirmation ---------------------------------------------------


def test_RR04_reset_emails_are_capped_per_account_across_networks(api, factory):
    victim = factory.user("SALES")
    bodies = set()
    for i in range(6):
        r = api.post(
            "/api/v1/auth/password/forgot",
            {"email": victim.email},
            anonymous=True,
            headers={"CF-Connecting-IP": _v6(i)},
        )
        bodies.add((r.status, str(r.json)))
    assert bodies == {(202, str(r.json))}, "every answer is identical"
    sent = [e for e in events("PASSWORD_RESET_REQUESTED", subject_user_id=victim.id) if e.outcome == "SUCCESS"]
    assert len(sent) == throttle.RESET_EMAILS, "at most three links per hour, whatever the network"
    assert len([m for m in emails_to(victim.email) if "reset" in m.subject.lower()]) <= throttle.RESET_EMAILS
    capped = [e for e in events("PASSWORD_RESET_REQUESTED", subject_user_id=victim.id) if e.outcome == "FAILURE"]
    assert len(capped) == 3 and all(e.failure_reason == "RATE_LIMITED" for e in capped)
    assert link_from(victim.email, "reset"), "the victim still holds a working link"


def test_RR04_recovery_endpoint_is_throttled_per_account(api, factory):
    victim = factory.user("ADMIN")
    statuses = []
    for i in range(throttle.MFA_FAILURES + 1):
        token = login_challenge(api, victim)
        r = api.post(
            "/api/v1/auth/mfa/recovery",
            {"mfa_token": token, "password": victim.password, "recovery_code": f"AAAA-BBBB-{i:04d}"},
            anonymous=True,
        )
        statuses.append(r.status)
    assert statuses[-1] == 429, statuses


@pytest.mark.settings(rate_limits_enabled=True)
def test_RR04_email_change_endpoints_have_a_source_limit(api):
    statuses = [
        api.post("/api/v1/auth/email/verify", {"token": f"x{i:020d}"}, anonymous=True).status for i in range(11)
    ]
    assert statuses[:10] == [400] * 10 and statuses[10] == 429
    statuses = [
        api.post("/api/v1/auth/email/cancel", {"token": f"y{i:020d}"}, anonymous=True).status for i in range(11)
    ]
    assert statuses[10] == 429


def test_RR04_mfa_confirmation_failures_share_the_mfa_throttle(api, factory):
    user = factory.user("SALES")
    token = factory.login(api, user, set_default=False)
    api.post("/api/v1/auth/reauth", {"password": user.password}, token=token)
    challenge = api.post("/api/v1/auth/mfa/enroll/start", {"reauth": True}, token=token).data["challenge_token"]
    statuses = []
    for i in range(throttle.MFA_FAILURES + 1):
        if i and i % 4 == 0:  # a challenge allows a few attempts; start a new transaction
            api.post("/api/v1/auth/reauth", {"password": user.password}, token=token)
            r = api.post("/api/v1/auth/mfa/enroll/start", {"reauth": True, "replace": True}, token=token)
            challenge = (r.data or {}).get("challenge_token", challenge)
        r = api.post("/api/v1/auth/mfa/enroll/confirm", {"challenge_token": challenge, "code": "000000"}, token=token)
        statuses.append(r.status)
    assert 429 in statuses, statuses


# --- state properties -------------------------------------------------------------------------------------------


def test_RR04_concurrent_failures_are_counted_exactly():
    throttle.reset()
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        for _ in range(25):
            throttle.record_account_failure("user:concurrent")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(throttle._budgets["user:concurrent"].failures) == 200
    assert throttle.account_state("user:concurrent")[0] is True


def test_RR04_tracked_state_is_bounded(monkeypatch):
    throttle.reset()
    monkeypatch.setattr(throttle, "MAX_TRACKED", 100)
    for i in range(1000):
        throttle.record_account_failure(f"unknown:{i:064x}")
        throttle.record_password_failure(f"unknown:{i:064x}", f"198.51.{i % 250}.0/24")
        throttle.reset_email_allowed(f"user-{i}")
    assert len(throttle._budgets) <= 101 and len(throttle._pairs) <= 101 and len(throttle._reset_emails) <= 101
    assert "unknown:" + f"{999:064x}" in throttle._budgets, "the most recent identifier is kept"


def test_RR04_limiter_keys_and_events_carry_no_raw_address(app, api, factory):
    from veda.kernel.ratelimit import body_email_key

    with app.test_request_context(LOGIN, method="POST", json={"email": "Private.Person@Example.test"}):
        key = body_email_key()
    assert "private" not in key.lower() and "example" not in key.lower() and key.startswith("email:")
    for i in range(throttle.ACCOUNT_DELAY_FAILURES):
        _login(api, "Private.Person@Example.test", BAD, _v6(i))
    for e in events():
        assert "private.person" not in str(e.detail or {}).lower()


# --- IR-A08: per-user limit across all endpoints (08 §12) -----------------------------------------------------


def test_IRA08_user_limit_is_the_documented_value():
    from veda.kernel import ratelimit

    assert ratelimit.USER_LIMIT == "600 per 5 minutes"


@pytest.mark.settings(rate_limits_enabled=True)
def test_IRA08_authenticated_user_is_limited_across_endpoints(api, factory, monkeypatch):
    from veda.kernel import ratelimit

    monkeypatch.setattr(ratelimit, "USER_LIMIT", "3 per 5 minutes")
    reader = factory.user("SALES")
    token = factory.login(api, reader)
    # One budget for the user, whatever the endpoint.
    assert api.get("/api/v1/auth/me", token=token).status == 200
    assert api.get("/api/v1/leads", token=token).status == 200
    assert api.get("/api/v1/auth/me", token=token).status == 200
    r = api.get("/api/v1/leads", token=token)
    assert r.status == 429 and r.code == "RATE_LIMITED"
    assert 1 <= int(r.headers["Retry-After"]) <= 300
    # Another user and unauthenticated public routes keep their own budgets.
    other = factory.user("SALES")
    assert api.get("/api/v1/auth/me", token=factory.login(api, other)).status == 200
    assert api.get("/api/v1/auth/me", token=token).status == 429


def test_IRA08_user_limit_off_when_rate_limits_are_disabled(api, factory, monkeypatch):
    from veda.kernel import ratelimit

    monkeypatch.setattr(ratelimit, "USER_LIMIT", "1 per 5 minutes")
    reader = factory.user("SALES")
    token = factory.login(api, reader)
    assert [api.get("/api/v1/auth/me", token=token).status for _ in range(3)] == [200, 200, 200]
