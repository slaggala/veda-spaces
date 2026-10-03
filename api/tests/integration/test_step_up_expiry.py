"""RR-18 (AX-07): the step-up dialog warns before the challenge expires, so the expiry it is told must be the real one.

The 403 STEP_UP_REQUIRED reports ``expires_in``; the stored challenge must expire exactly then, a wrong code must
report the attempts left, and an expired challenge must be refused (the dialog then shows its expired state)."""

from datetime import timedelta

import sqlalchemy as sa

from tests.support.dbh import rows
from veda.kernel import clock
from veda.platform.auth.models import MfaChallenge
from veda.platform.auth.request_auth import STEP_UP_CHALLENGE_TTL
from veda.platform.auth.service import CHALLENGE_TTLS


def _step_up_required(api, factory):
    admin = factory.user("ADMIN")
    target = factory.user("SALES")
    factory.login(api, admin)
    clock.advance(timedelta(minutes=11))  # past the 10-minute step-up window
    r = api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)
    api.token = r.data["access_token"] if r.status == 200 else api.token
    r = api.post(f"/api/v1/users/{target.id}/sessions/revoke", {"reason": "Lost phone"})
    assert r.status == 403 and r.code == "STEP_UP_REQUIRED" and r.json["kind"] == "mfa"
    return admin, r.json


def test_RR18_step_up_expires_in_is_the_challenge_lifetime(api, factory):
    _, problem = _step_up_required(api, factory)
    assert problem["expires_in"] == int(STEP_UP_CHALLENGE_TTL.total_seconds()) == 300
    assert CHALLENGE_TTLS["STEP_UP"] == STEP_UP_CHALLENGE_TTL, "one lifetime for every STEP_UP challenge"
    (challenge,) = rows(sa.select(MfaChallenge).where(MfaChallenge.purpose == "STEP_UP"))
    assert (challenge.expires_on - challenge.created_on).total_seconds() == problem["expires_in"]


def test_RR18_wrong_code_reports_attempts_left(api, factory):
    _, problem = _step_up_required(api, factory)
    r = api.post("/api/v1/auth/mfa/step-up", {"mfa_token": problem["mfa_token"], "code": "000000"})
    assert r.code == "MFA_CODE_INVALID" and r.json["attempts_remaining"] == 4


def test_RR18_expired_step_up_challenge_is_refused(api, factory):
    admin, problem = _step_up_required(api, factory)
    clock.advance(timedelta(seconds=problem["expires_in"] + 1))
    r = api.post("/api/v1/auth/mfa/step-up", {"mfa_token": problem["mfa_token"], "code": admin.code()})
    assert r.status == 401 and r.code == "MFA_CHALLENGE_INVALID"
