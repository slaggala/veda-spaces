"""IR-02: Turnstile siteverify never runs while the database write lock is held (public intake, CAPTCHA-gated
sign-in). The stub verifier checks, while "on the network", that another writer can commit at once."""

import time
from datetime import timedelta

import pytest
import sqlalchemy as sa

from veda.kernel import clock, db, turnstile
from veda.kernel.context import actor, system_context


@pytest.fixture
def lock_probe(monkeypatch):
    seen = []

    def slow_verify(token, remote_ip):
        started = time.perf_counter()
        # A staff write from another connection while siteverify is in flight.
        with actor(system_context()), db.unit_of_work(write=True) as s:
            s.execute(sa.text("SELECT 1"))
        seen.append(time.perf_counter() - started)
        return True

    monkeypatch.setattr(turnstile, "verify", slow_verify)
    return seen


def test_IR02_Q5_intake_verifies_captcha_without_the_write_lock(api, factory, lock_probe):
    r = factory.public_lead(api)
    assert r.status == 201
    assert lock_probe and lock_probe[0] < 1.0, f"a concurrent writer waited {lock_probe}s"


def test_IR02_replay_needs_no_captcha_and_no_lock(api, factory, lock_probe):
    key = "replay-key-000000000001"
    assert factory.public_lead(api, key=key, name="Kiran Rao", phone="9812300001").status == 201
    lock_probe.clear()
    r = factory.public_lead(api, key=key, name="Kiran Rao", phone="9812300001")
    assert r.status == 201 and not lock_probe, "the idempotent replay never calls siteverify"


def test_IR02_captcha_gated_login_verifies_without_the_write_lock(api, factory, lock_probe):
    sales = factory.user("SALES")
    for _ in range(5):
        api.post("/api/v1/auth/login", {"email": sales.email, "password": "bad-password-000"}, anonymous=True)
    clock.advance(timedelta(seconds=31))  # past the escalating delay; the CAPTCHA requirement remains
    r = api.post(
        "/api/v1/auth/login",
        {"email": sales.email, "password": sales.password, "turnstile_token": "t0k"},
        anonymous=True,
    )
    assert r.status == 200, r
    assert lock_probe and lock_probe[0] < 1.0
