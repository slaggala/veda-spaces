"""Customer-safety closure, Phase 4 (server side): a public V3 estimate is created once per Idempotency-Key.

A double click, a key repeat or a network retry that sends the same request again gets the same estimate back. A
real anti-bot token is single-use, so the repeat is answered before the token is checked again. Synthetic only."""

import pytest
import sqlalchemy as sa

from tests.integration.test_catalog import ON, SITE, approve_all, living, release, seed_slice
from tests.support.dbh import rows
from veda.modules.catalog.models import CatalogConfiguration
from veda.modules.estimator.models import BudgetEstimate

KEY = "est-0123456789abcdef"


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


def live(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b)


def post(api, config, *, key=None, token="ok-token"):
    headers = {"Origin": SITE, **({"Idempotency-Key": key} if key else {})}
    return api.post("/api/v1/public/catalog/estimates", {"configuration": config, "turnstile_token": token},
                    anonymous=True, headers=headers)  # fmt: skip


@ON
@pytest.mark.settings(catalog_estimator_enabled=True, estimate_turnstile_required=True)
def test_a_repeated_request_creates_one_estimate(api, people):
    live(people)
    first = post(api, living(), key=KEY)
    again = post(api, living(), key=KEY, token="fail-spent-token")  # the token was single-use
    third = post(api, living(), key=KEY, token="")
    assert first.status == again.status == third.status == 201
    assert again.headers.get("Idempotent-Replayed") == "true"
    ref = first.json["data"]["configuration_reference"]
    assert again.json["data"]["configuration_reference"] == third.json["data"]["configuration_reference"] == ref
    assert again.json["data"]["range"] == first.json["data"]["range"]
    assert len(rows(sa.select(BudgetEstimate))) == 1 and len(rows(sa.select(CatalogConfiguration))) == 1


@ON
@pytest.mark.settings(catalog_estimator_enabled=True, estimate_turnstile_required=True)
def test_a_key_reused_for_different_choices_is_refused(api, people):
    live(people)
    assert post(api, living(), key=KEY).status == 201
    other = post(api, living(extras={"feature-wall": {}}), key=KEY)
    assert other.status == 409 and other.json["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert len(rows(sa.select(BudgetEstimate))) == 1


@ON
def test_a_malformed_key_is_refused(api, people):
    live(people)
    for bad in ("short", "x" * 65, "has spaces in it ok", "ünïcødé-key-0000000"):
        r = post(api, living(), key=bad)
        assert r.status == 422 and r.json["errors"][0]["field"] == "Idempotency-Key", bad
    assert not rows(sa.select(BudgetEstimate))


@ON
@pytest.mark.settings(catalog_estimator_enabled=True, estimate_turnstile_required=True)
def test_a_new_request_still_needs_a_valid_token(api, people):
    live(people)
    assert post(api, living(), key="est-new-key-000000001", token="fail-bad").status == 422
    assert not rows(sa.select(BudgetEstimate)), "only an answered key skips the anti-bot check"


@ON
def test_without_a_key_each_request_is_its_own_estimate(api, people):
    live(people)
    assert post(api, living()).status == 201 and post(api, living()).status == 201
    assert len(rows(sa.select(BudgetEstimate))) == 2
