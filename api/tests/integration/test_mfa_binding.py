"""IR-01 regression suite: an enrollment transaction is bound to its principal, initiating session,
intended factor and enrollment path (05 §11.3, MFA-011, MFA-012, MFA-014, AUTH-015).

P1 and P1b are the independent review's reproducers; the path-D variant, the session, factor,
purpose, replay, concurrency and atomicity cases cover the rest of the confusion class. Every case
asserts the failure is closed *and* that nothing was upgraded: the victim session's assurance, the
factor state and the challenge state are checked after each refusal.
"""

import threading
from datetime import timedelta

import sqlalchemy as sa

from tests.integration.test_mfa import code_for, link_from, login_challenge, secret_from_uri
from tests.support.api import ApiClient
from tests.support.dbh import events, get, rows
from veda.kernel import clock
from veda.platform.auth import mfa
from veda.platform.auth.models import MfaChallenge, UserMfaFactor, UserSession

CONFIRM = "/api/v1/auth/mfa/enroll/confirm"
START = "/api/v1/auth/mfa/enroll/start"


# --- helpers ---------------------------------------------------------------------------------------


def path_c_transaction(api, factory, user=None):
    """An MFA-required user without a factor: sign-in → emailed link → start with the password (path C).
    Returns (user, challenge_token, secret). Any such user holds an unbound enrollment transaction."""
    user = user or factory.user("SALES", mfa_required=True)
    r = api.post("/api/v1/auth/login", {"email": user.email, "password": user.password}, anonymous=True)
    assert r.data["status"] == "MFA_ENROLLMENT_EMAIL_SENT", r
    link = link_from(user.email, "two-step verification")
    r = api.post(START, {"enrollment_token": link, "password": user.password}, anonymous=True)
    assert r.status == 200, r
    return user, r.data["challenge_token"], secret_from_uri(r.data["otpauth_uri"])


def path_b_transaction(api, factory, admin_token, email):
    r = api.post(
        "/api/v1/users",
        {"email": email, "full_name": "Invited Person", "role_ids": [factory.role_id("ADMIN")]},
        token=admin_token,
    )
    assert r.status == 201, r
    invite = link_from(email, "invited")
    r = api.post(
        "/api/v1/auth/invite/accept", {"token": invite, "new_password": "Harbour-Lights-Evening-3"}, anonymous=True
    )
    assert r.data["status"] == "MFA_ENROLLMENT_REQUIRED", r
    context = r.data["invite_context"]
    r = api.post(START, {"invite_context": context}, anonymous=True)
    assert r.status == 200, r
    return context, r.data["challenge_token"], secret_from_uri(r.data["otpauth_uri"])


def factors(user_id, status=None):
    q = sa.select(UserMfaFactor).where(UserMfaFactor.user_id == user_id)
    if status:
        q = q.where(UserMfaFactor.status == status)
    return rows(q)


def assert_not_upgraded(session_ids):
    for us in rows(sa.select(UserSession).where(UserSession.id.in_(session_ids))):
        assert "totp" not in us.auth_methods, f"session {us.id} gained MFA assurance"
        assert us.mfa_verified_on is None, f"session {us.id} was marked MFA-verified"


def assert_binding_refused(r):
    assert r.status == 401 and r.code == "MFA_CHALLENGE_INVALID", r
    assert "access_token" not in (r.json or {}).get("data", {}) and "Set-Cookie" not in r.headers


def victim_with_pwd_only_session_and_sensitive_grant(api, factory):
    victim = factory.user("SALES")
    token = factory.login(api, victim, set_default=False)
    factory.grant(victim, "audit.read")  # MFA-gated sensitive permission, suspended in a pwd-only session
    r = api.get("/api/v1/audit-logs", token=token)
    assert r.status == 403 and r.json["reason"] == "MFA_REQUIRED"
    return victim, token


def sid_for(user_id):
    live = rows(
        sa.select(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_on.is_(None))
        .order_by(UserSession.started_on.desc())
    )
    return [s.id for s in live]


# --- the review's reproducers ------------------------------------------------------------------------


def test_IR01_P1_foreign_unbound_challenge_cannot_verify_victim_session(api, factory):
    victim, victim_token = victim_with_pwd_only_session_and_sensitive_grant(api, factory)
    victim_sessions = sid_for(victim.id)
    attacker, challenge, secret = path_c_transaction(api, factory)

    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=victim_token)
    assert_binding_refused(r)

    assert api.get("/api/v1/audit-logs", token=victim_token).status == 403, "victim session must stay pwd-only"
    assert_not_upgraded(victim_sessions)
    assert not factors(attacker.id, "ACTIVE"), "the attacker's factor must not be activated"
    assert factors(attacker.id, "PENDING"), "the refused attempt must not consume the pending factor"
    assert any(
        e.failure_reason == "TOKEN_INVALID" and (e.detail or {}).get("reason") == "BINDING_MISMATCH"
        for e in events("MFA_CHALLENGE")
    ), "a redacted binding-mismatch event is recorded"


def test_IR01_P1b_foreign_challenge_cannot_satisfy_step_up(api, factory):
    admin = factory.user("ADMIN")
    admin_token = factory.login(api, admin, set_default=False)
    clock.advance(timedelta(minutes=11))  # step-up window (10 min) lapsed; access token (15 min) still valid
    r = api.post("/api/v1/auth/mfa/recovery-codes", {}, token=admin_token)
    assert r.status == 403 and r.code == "STEP_UP_REQUIRED"
    before = rows(sa.select(UserSession).where(UserSession.user_id == admin.id))[0].mfa_verified_on

    _, challenge, secret = path_c_transaction(api, factory)
    assert_binding_refused(
        api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=admin_token)
    )

    r = api.post("/api/v1/auth/mfa/recovery-codes", {}, token=admin_token)
    assert r.status == 403 and r.code == "STEP_UP_REQUIRED", "step-up must not be satisfied by a foreign transaction"
    assert rows(sa.select(UserSession).where(UserSession.user_id == admin.id))[0].mfa_verified_on == before


def test_IR01_path_D_recovery_session_with_foreign_challenge(api, factory):
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    codes = api.post("/api/v1/auth/mfa/recovery-codes", {}).data["recovery_codes"]
    mfa_token = login_challenge(api, admin)
    rec = api.post(
        "/api/v1/auth/mfa/recovery",
        {"mfa_token": mfa_token, "password": admin.password, "recovery_code": codes[0]},
        anonymous=True,
    )
    assert rec.data["status"] == "RECOVERY_SESSION", rec
    recovery_token = rec.data["access_token"]
    recovery_sid = sid_for(admin.id)[0]

    attacker, challenge, secret = path_c_transaction(api, factory)
    assert_binding_refused(
        api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=recovery_token)
    )
    assert get(UserSession, recovery_sid).revoked_on is None, "the victim's recovery session is untouched"
    assert not factors(attacker.id, "ACTIVE")
    assert factory.get_user(attacker.id).security_cooling_off_until is None


def test_IR01_attacker_bearer_with_victims_unbound_challenge(api, factory):
    victim, challenge, secret = path_c_transaction(api, factory)
    attacker = factory.user("SALES")
    attacker_token = factory.login(api, attacker, set_default=False)
    attacker_sessions = sid_for(attacker.id)

    assert_binding_refused(
        api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=attacker_token)
    )
    assert_not_upgraded(attacker_sessions)
    assert not factors(attacker.id) and not factors(victim.id, "ACTIVE")
    # The legitimate owner can still finish, anonymously, on the same transaction.
    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, anonymous=True)
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED", r


def test_IR01_unbound_invitation_transaction_refuses_any_bearer(api, factory):
    admin = factory.user("ADMIN")
    admin_token = factory.login(api, admin, set_default=False)
    _, challenge, secret = path_b_transaction(api, factory, admin_token, "ravi@vedaspaces.test")
    before = {s: get(UserSession, s).mfa_verified_on for s in sid_for(admin.id)}
    assert_binding_refused(
        api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=admin_token)
    )
    assert {s: get(UserSession, s).mfa_verified_on for s in sid_for(admin.id)} == before
    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, anonymous=True)
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED"


# --- session binding ----------------------------------------------------------------------------------


def _path_a_start(api, user, token):
    assert api.post("/api/v1/auth/reauth", {"password": user.password}, token=token).status == 204
    r = api.post(START, {"reauth": True}, token=token)
    assert r.status == 200, r
    return r.data["challenge_token"], secret_from_uri(r.data["otpauth_uri"])


def test_IR01_same_user_different_session_cannot_confirm(api, factory):
    user = factory.user("SALES")
    t1 = factory.login(api, user, set_default=False)
    s1 = sid_for(user.id)[0]
    t2 = factory.login(api, user, set_default=False)
    s2 = sid_for(user.id)[0]
    challenge, secret = _path_a_start(api, user, t1)

    assert_binding_refused(api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=t2))
    assert_not_upgraded([s1, s2])
    assert_binding_refused(api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, anonymous=True))

    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=t1)
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED"
    assert "totp" in get(UserSession, s1).auth_methods
    assert_not_upgraded([s2])  # other sessions keep their original assurance


def test_IR01_revoked_session_cannot_confirm(api, factory):
    user = factory.user("SALES")
    token = factory.login(api, user, set_default=False)
    challenge, secret = _path_a_start(api, user, token)
    assert api.post("/api/v1/auth/logout", {}, token=token, headers=api.csrf_headers()).status in (200, 204)
    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=token)
    assert r.status == 401 and r.code == "SESSION_INVALID"
    assert not factors(user.id, "ACTIVE")


def test_IR01_disabled_user_token_cannot_confirm(api, factory):
    founder = factory.user(founder=True)
    ftoken = factory.login(api, founder, set_default=False)
    user = factory.user("SALES")
    token = factory.login(api, user, set_default=False)
    challenge, secret = _path_a_start(api, user, token)
    version = api.get(f"/api/v1/users/{user.id}", token=ftoken).data["version"]
    r = api.post(
        f"/api/v1/users/{user.id}/status",
        {"status": "DISABLED", "reason": "Left the company"},
        token=ftoken,
        if_match=version,
    )
    assert r.status == 200, r
    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=token)
    assert r.status == 401 and r.code == "SESSION_INVALID"
    assert not factors(user.id, "ACTIVE")


def test_IR01_eligibility_rechecked_at_confirm_after_sensitive_grant(api, factory):
    """Stale authorization: path A is only for users without sensitive permissions (N-A1). A grant made
    between start and confirm must be honoured at confirm."""
    user = factory.user("SALES")
    token = factory.login(api, user, set_default=False)
    challenge, secret = _path_a_start(api, user, token)
    factory.grant(user, "audit.read")
    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=token)
    assert r.status == 401 and r.code == "ENROLLMENT_PROOF_INVALID", r
    assert not factors(user.id, "ACTIVE")
    assert_not_upgraded(sid_for(user.id))


# --- transaction state ---------------------------------------------------------------------------------


def test_IR01_expired_transaction(api, factory):
    user, challenge, secret = path_c_transaction(api, factory)
    clock.advance(timedelta(minutes=16))
    assert_binding_refused(api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, anonymous=True))
    assert not factors(user.id, "ACTIVE")


def test_IR01_replay_after_success(api, factory):
    user, challenge, secret = path_c_transaction(api, factory)
    assert api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, anonymous=True).status == 200
    active = factors(user.id, "ACTIVE")
    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, anonymous=True)
    assert_binding_refused(r)
    assert [f.id for f in factors(user.id, "ACTIVE")] == [f.id for f in active]
    assert events("MFA_CHALLENGE_REPLAY_BLOCKED")


def test_IR01_transaction_bound_to_its_own_factor(api, factory):
    """A newer start revokes the older PENDING factor; the older transaction cannot promote the newer factor
    even with a valid code for it."""
    user, old_challenge, _ = path_c_transaction(api, factory)
    _, new_challenge, new_secret = path_c_transaction(api, factory, user)
    assert_binding_refused(
        api.post(CONFIRM, {"challenge_token": old_challenge, "code": code_for(new_secret)}, anonymous=True)
    )
    assert not factors(user.id, "ACTIVE")
    r = api.post(CONFIRM, {"challenge_token": new_challenge, "code": code_for(new_secret)}, anonymous=True)
    assert r.status == 200


def test_IR01_wrong_purpose_tokens_are_not_enrollment_transactions(api, factory):
    admin = factory.user("ADMIN")
    login_token = login_challenge(api, admin)
    assert_binding_refused(api.post(CONFIRM, {"challenge_token": login_token, "code": admin.code()}, anonymous=True))
    # A step-up challenge is not an enrollment transaction either.
    token = factory.login(api, admin, set_default=False)
    clock.advance(timedelta(minutes=11))
    step_up = api.post("/api/v1/auth/mfa/recovery-codes", {}, token=token).json["mfa_token"]
    assert_binding_refused(api.post(CONFIRM, {"challenge_token": step_up, "code": admin.code()}, token=token))
    # An invitation context is a proof for start, never a confirmable transaction.
    ftoken = factory.login(api, factory.user(founder=True), set_default=False)
    context, _, secret = path_b_transaction(api, factory, ftoken, "meera@vedaspaces.test")
    assert_binding_refused(api.post(CONFIRM, {"challenge_token": context, "code": code_for(secret)}, anonymous=True))


def test_IR01_invitation_context_is_single_account_and_unauthenticated(api, factory):
    founder = factory.user(founder=True)
    ftoken = factory.login(api, founder, set_default=False)
    r = api.post(
        "/api/v1/users",
        {"email": "leela@vedaspaces.test", "full_name": "Leela Iyer", "role_ids": [factory.role_id("ADMIN")]},
        token=ftoken,
    )
    assert r.status == 201
    invite = link_from("leela@vedaspaces.test", "invited")
    r = api.post(
        "/api/v1/auth/invite/accept", {"token": invite, "new_password": "Harbour-Lights-Evening-3"}, anonymous=True
    )
    context = r.data["invite_context"]
    other = factory.user("SALES")
    other_token = factory.login(api, other, set_default=False)
    r = api.post(START, {"invite_context": context}, token=other_token)
    assert r.status == 401 and r.code == "ENROLLMENT_PROOF_INVALID", r
    assert not factors(other.id)
    assert api.post(START, {"invite_context": context}, anonymous=True).status == 200


def test_IR01_recovery_transaction_needs_its_recovery_session(api, factory):
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    codes = api.post("/api/v1/auth/mfa/recovery-codes", {}).data["recovery_codes"]
    rec = api.post(
        "/api/v1/auth/mfa/recovery",
        {"mfa_token": login_challenge(api, admin), "password": admin.password, "recovery_code": codes[0]},
        anonymous=True,
    ).data
    start = api.post(START, {}, token=rec["access_token"])
    assert start.status == 200, start
    secret = secret_from_uri(start.data["otpauth_uri"])
    assert_binding_refused(
        api.post(CONFIRM, {"challenge_token": start.data["challenge_token"], "code": code_for(secret)}, anonymous=True)
    )
    # A recovery code is not an emailed enrollment token.
    r = api.post(START, {"enrollment_token": codes[1], "password": admin.password}, anonymous=True)
    assert r.status == 401 and r.code == "ENROLLMENT_PROOF_INVALID"
    r = api.post(
        CONFIRM, {"challenge_token": start.data["challenge_token"], "code": code_for(secret)}, token=rec["access_token"]
    )
    assert r.status == 200 and r.data["cooling_off_until"]


def test_IR01_parallel_confirmations_activate_once(app, api, factory):
    user, challenge, secret = path_c_transaction(api, factory)
    code = code_for(secret)
    barrier = threading.Barrier(2)
    results = []

    def confirm():
        c = ApiClient(app.test_client())
        barrier.wait()
        results.append(c.post(CONFIRM, {"challenge_token": challenge, "code": code}, anonymous=True))

    threads = [threading.Thread(target=confirm) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(r.status for r in results) == [200, 401], [r.json for r in results]
    assert len(factors(user.id, "ACTIVE")) == 1
    assert len(rows(sa.select(UserSession).where(UserSession.user_id == user.id))) == 1


def test_IR01_failure_halfway_commits_nothing(api, factory, monkeypatch):
    user, challenge, secret = path_c_transaction(api, factory)

    def boom(*a, **k):
        raise RuntimeError("injected failure after factor promotion")

    monkeypatch.setattr(mfa, "_issue_recovery_codes", boom)
    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, anonymous=True)
    assert r.status == 500
    monkeypatch.undo()
    assert not factors(user.id, "ACTIVE") and factors(user.id, "PENDING")
    ch = rows(
        sa.select(MfaChallenge)
        .where(MfaChallenge.user_id == user.id, MfaChallenge.purpose == "ENROLLMENT")
        .order_by(MfaChallenge.created_on.desc())
    )[0]
    assert ch.completed_on is None
    assert not rows(sa.select(UserSession).where(UserSession.user_id == user.id))
    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, anonymous=True)
    assert r.status == 200, "the untouched transaction can still be completed"


def test_IR01_failed_replacement_keeps_active_factor_and_assurance(api, factory):
    admin = factory.user("ADMIN")
    token = factory.login(api, admin, set_default=False)
    old = factors(admin.id, "ACTIVE")[0]
    sid = sid_for(admin.id)[0]
    before = get(UserSession, sid).mfa_verified_on
    r = api.post(START, {"reauth": True, "replace": True}, token=token)
    assert r.status == 200, r
    bad = api.post(CONFIRM, {"challenge_token": r.data["challenge_token"], "code": "000000"}, token=token)
    assert bad.code == "MFA_CODE_INVALID"
    assert [f.id for f in factors(admin.id, "ACTIVE")] == [old.id]
    assert get(UserSession, sid).mfa_verified_on == before
    # A foreign principal's transaction cannot complete the replacement either.
    _, foreign, foreign_secret = path_c_transaction(api, factory)
    assert_binding_refused(
        api.post(CONFIRM, {"challenge_token": foreign, "code": code_for(foreign_secret)}, token=token)
    )
    assert [f.id for f in factors(admin.id, "ACTIVE")] == [old.id]


def test_IR01_success_rotates_refresh_token_of_the_elevated_session(api, factory):
    user = factory.user("SALES")
    token = factory.login(api, user, set_default=False)
    challenge, secret = _path_a_start(api, user, token)
    r = api.post(CONFIRM, {"challenge_token": challenge, "code": code_for(secret)}, token=token)
    assert r.status == 200 and r.data["access_token"] != token
    assert "Set-Cookie" in r.headers, "the elevated session gets a fresh refresh token"
    assert events("MFA_ENROLLMENT_COMPLETED")
