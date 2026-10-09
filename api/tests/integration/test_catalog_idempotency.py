"""Idempotency of public V3 estimates (customer-safety closure Phase 4; canonical customer-copy closure Phase 9).

A V3 estimate needs an Idempotency-Key: one per request, from the browser, with at least 128 random bits. The server
stores only a SHA-256 of the key scoped to the browser's X-Veda-Client token.

Behaviour:
- A repeat of the same request within 24 hours (a double click, a network retry, or a timeout then retry) returns
  the original response, answered before the anti-bot check because the token was single-use.
- Different choices under the same key are refused with 409.
- A request still in flight is refused with 409.
- An expired key is refused with 409.
- Another browser presenting the same key never sees the first browser's estimate.

Documented in docs/implementation/catalog/CATALOG-V3-idempotency.md. Synthetic data only."""

from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.integration.test_catalog import ON, SITE, approve_all, living, release, seed_slice
from tests.support.dbh import rows
from veda.kernel import clock, db
from veda.kernel.context import ActorContext, acting
from veda.kernel.errors import ApiError
from veda.kernel.ids import WEB_INTAKE_USER_ID
from veda.modules.catalog import configure
from veda.modules.catalog.models import CatalogConfiguration
from veda.modules.estimator.models import BudgetEstimate

KEY = "v3-0123456789abcdef0123456789abcdef"
CLIENT = "client-aaaaaaaaaaaaaaaaaaaaaaaa"
OTHER_CLIENT = "client-bbbbbbbbbbbbbbbbbbbbbbbb"
TURNSTILE = pytest.mark.settings(catalog_estimator_enabled=True, estimate_turnstile_required=True)


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


@pytest.fixture(autouse=True)
def _clock():
    yield
    clock.reset()


def live(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b)


def post(api, config, *, key=KEY, token="ok-token", client=CLIENT):
    headers = {
        "Origin": SITE,
        **({"Idempotency-Key": key} if key else {}),
        **({"X-Veda-Client": client} if client else {}),
    }
    return api.post("/api/v1/public/catalog/estimates", {"configuration": config, "turnstile_token": token},
                    anonymous=True, headers=headers)  # fmt: skip


def estimates():
    return len(rows(sa.select(BudgetEstimate)))


@ON
@TURNSTILE
def test_a_repeated_request_creates_one_estimate(api, people):
    live(people)
    first = post(api, living())
    again = post(api, living(), token="fail-spent-token")  # the token was single-use
    third = post(api, living(), token="")
    assert first.status == again.status == third.status == 201
    assert again.headers.get("Idempotent-Replayed") == "true"
    ref = first.json["data"]["configuration_reference"]
    assert again.json["data"]["configuration_reference"] == third.json["data"]["configuration_reference"] == ref
    assert again.json["data"] == first.json["data"], "the original response is recovered exactly"
    assert estimates() == 1 and len(rows(sa.select(CatalogConfiguration))) == 1


@ON
def test_the_key_is_stored_only_as_a_scoped_digest(api, people):
    live(people)
    assert post(api, living()).status == 201
    snap = rows(sa.select(CatalogConfiguration))[0]
    assert snap.idempotency_key == configure.key_digest(KEY, CLIENT) and KEY not in snap.idempotency_key
    assert configure.key_digest(KEY, CLIENT) != configure.key_digest(KEY, OTHER_CLIENT)


@ON
def test_a_key_reused_for_different_choices_is_refused(api, people):
    live(people)
    assert post(api, living()).status == 201
    other = post(api, living(extras={"feature-wall": {}}))
    assert other.status == 409 and other.json["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert estimates() == 1


@ON
def test_the_client_drops_its_key_after_a_409_and_a_new_key_succeeds(api, people):
    """The V3 page clears its key on any answered failure; a replacement key is a fresh 128-bit random value."""
    live(people)
    assert post(api, living()).status == 201
    assert post(api, living(extras={"feature-wall": {}})).status == 409
    replacement = "v3-fedcba9876543210fedcba9876543210"
    retry = post(api, living(extras={"feature-wall": {}}), key=replacement)
    assert retry.status == 201 and estimates() == 2


@ON
def test_another_browser_with_the_same_key_never_sees_the_first_estimate(api, people):
    live(people)
    mine = post(api, living())
    theirs = post(api, living(), client=OTHER_CLIENT)
    assert mine.status == theirs.status == 201
    assert theirs.headers.get("Idempotent-Replayed") is None, "no replay across browsers"
    assert theirs.json["data"]["configuration_reference"] != mine.json["data"]["configuration_reference"]
    assert theirs.json["data"]["reference"] != mine.json["data"]["reference"]
    assert estimates() == 2


@ON
def test_replay_before_and_after_expiry(api, people):
    live(people)
    assert post(api, living()).status == 201
    clock.advance(configure.IDEMPOTENCY_TTL - timedelta(minutes=1))
    assert post(api, living()).status == 201, "a retry within 24 hours replays"
    clock.advance(timedelta(minutes=2))
    late = post(api, living())
    assert late.status == 409 and late.json["code"] == "IDEMPOTENCY_KEY_EXPIRED"
    assert estimates() == 1
    fresh = post(api, living(), key="v3-11111111111111111111111111111111")
    assert fresh.status == 201, "after expiry the page starts again with a new key"


@ON
def test_a_timeout_then_retry_recovers_the_original_response(api, people):
    """The first response was lost (the browser timed out after the server answered): the retry with the same key
    and choices gets that response back, not a second estimate."""
    live(people)
    first = post(api, living())
    assert first.status == 201
    retry = post(api, living())
    assert retry.status == 201 and retry.headers.get("Idempotent-Replayed") == "true"
    assert retry.json["data"]["reference"] == first.json["data"]["reference"] and estimates() == 1


@ON
def test_a_request_still_in_flight_is_refused(api, people):
    """Concurrent identical requests: the first has stored its snapshot but not its estimate yet."""
    live(people)
    with acting_intake() as s:
        s.add(CatalogConfiguration(configuration_reference="CINFLIGHT", release_id=_active_release(s),
                                   manifest_sha256="0" * 64, versions={}, selections={}, resolved_request={},
                                   idempotency_key=configure.key_digest(KEY, CLIENT), request_fingerprint="0" * 64))  # fmt: skip
    r = post(api, living())
    assert r.status == 409 and r.json["code"] == "IDEMPOTENCY_CONFLICT"
    assert estimates() == 0


@ON
def test_concurrent_identical_requests_create_one_estimate(api, people, monkeypatch):
    """Two identical requests race past the replay check: the unique index lets one win; the other is a 409."""
    live(people)
    assert post(api, living()).status == 201
    monkeypatch.setattr(configure, "stored_for_key", lambda s, key: None)  # both requests passed the check at once
    racer = post(api, living())
    assert racer.status == 409 and racer.json["code"] == "IDEMPOTENCY_CONFLICT"
    assert estimates() == 1, "the loser's estimate is rolled back with its transaction"


@ON
def test_concurrent_conflicting_requests_create_one_estimate(api, people, monkeypatch):
    live(people)
    assert post(api, living()).status == 201
    monkeypatch.setattr(configure, "stored_for_key", lambda s, key: None)
    racer = post(api, living(extras={"feature-wall": {}}))
    assert racer.status == 409 and estimates() == 1


@ON
def test_a_missing_or_malformed_key_is_refused(api, people):
    live(people)
    missing = post(api, living(), key=None)
    assert missing.status == 422 and missing.json["errors"][0] == {
        "field": "Idempotency-Key", "code": "REQUIRED", "message": "An Idempotency-Key is required."}  # fmt: skip
    for bad in (
        "short",
        "x" * 65,
        "v3-0123456789abcdef",
        "has spaces in it ok but long enough!",
        "ünïcødé-key-" + "0" * 24,
    ):
        r = post(api, living(), key=bad)
        assert r.status == 422 and r.json["errors"][0]["field"] == "Idempotency-Key", bad
    assert estimates() == 0


@ON
@TURNSTILE
def test_a_new_request_still_needs_a_valid_token(api, people):
    live(people)
    assert post(api, living(), token="fail-bad").status == 422
    assert estimates() == 0, "only an answered key skips the anti-bot check"


@ON
@TURNSTILE
def test_a_replay_from_another_browser_still_needs_a_token(api, people):
    live(people)
    assert post(api, living()).status == 201
    assert post(api, living(), client=OTHER_CLIENT, token="fail-spent").status == 422
    assert estimates() == 1


def acting_intake():
    from contextlib import contextmanager

    @contextmanager
    def run():
        with db.unit_of_work(write=True) as s, acting(s, ActorContext(actor_id=WEB_INTAKE_USER_ID, via="PUBLIC_FORM")):
            yield s

    return run()


def _active_release(s):
    from veda.modules.catalog import service

    return service.active_release(s).id


def test_replay_refuses_a_snapshot_without_its_estimate(people):
    """Service level: `replay` itself refuses an unfinished request, whatever route calls it."""
    live(people)
    with acting_intake() as s:
        s.add(CatalogConfiguration(configuration_reference="COLD00001", release_id=_active_release(s),
                                   manifest_sha256="0" * 64, versions={}, selections={}, resolved_request={},
                                   idempotency_key="a" * 64, request_fingerprint="0" * 64))  # fmt: skip
    with db.unit_of_work(write=False) as s:
        with pytest.raises(ApiError) as err:
            configure.replay(s, "a" * 64, {})
    assert err.value.code == "IDEMPOTENCY_CONFLICT", "no estimate yet: still in flight"
