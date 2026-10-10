"""B1-B3 policy closure, Phase 6 (B3): a governed claim is re-validated every time V3 content is served.

The release gate approves a claim once, but a claim is time-bounded and its standing can change after activation.
Each check below runs on every public serve (catalog, estimate, replay), with a controllable clock:
- the review date: valid before it, lapsed on it and after it;
- withdrawal and reinstatement;
- owner removal and reassignment;
- narrowed applicability;
- the environment.

Any problem fails closed. The catalog's cache lifetime never reaches past the next claim boundary.

Synthetic data only; owners are role placeholders."""

import copy
from datetime import datetime

import pytest

from tests.integration.test_catalog import CLIENT, SITE, approve_all, living, new_key, release, seed_slice, tx
from tests.support import claims as claim_docs
from veda.kernel import clock, db
from veda.modules.catalog import claims, configure, service
from veda.modules.catalog import compile as catalog_compile
from veda.modules.catalog.models import CatalogRelease

ON = pytest.mark.settings(catalog_estimator_enabled=True, catalog_admin_enabled=True)
KEY = "copy.badge.chosen"


def at(text):
    """A moment in India time (the business date claims are judged by)."""
    return datetime.fromisoformat(text).replace(tzinfo=claims.BUSINESS_TZ)


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


@pytest.fixture(autouse=True)
def _reset():
    configure._view_cache.clear()
    clock.set_clock(lambda: at("2026-10-09T10:00:00"))
    yield
    clock.reset()
    configure._view_cache.clear()


def live_with_claim(people, **over):
    a, b = people
    seed_slice(a)
    tx(a, service.create_record, "copy", KEY, claim_docs.claim_copy("Most chosen", **over))
    with db.unit_of_work(write=False) as s:
        row = service.versions(s, "package", "slice.essential")[-1]
        rid, doc = row.id, copy.deepcopy(row.document)
    doc["badge"] = KEY
    tx(a, service.update_draft, rid, doc)
    approve_all(a, b)
    return release(a, b)


def catalog(api):
    return api.get("/api/v1/public/catalog", anonymous=True)


def estimate(api, key=None):
    return api.post("/api/v1/public/catalog/estimates", {"configuration": living(), "turnstile_token": "ok-token"},
                    anonymous=True, headers={"Origin": SITE, "Idempotency-Key": key or new_key(), "X-Veda-Client": CLIENT})  # fmt: skip


def control(people, action, **kw):
    a, _ = people
    tx(a, lambda s: claims.control(s, KEY, action, "Claim review after activation (synthetic test)", **kw))


def unavailable(r):
    return r.status == 503 and r.json["code"] == "ESTIMATOR_UNAVAILABLE"


@ON
def test_a_claim_is_valid_before_its_review_date_and_lapses_on_and_after_it(api, people):
    live_with_claim(people)  # review_by 2027-03-31
    clock.set_clock(lambda: at("2027-03-30T23:00:00"))
    r = catalog(api)
    assert r.status == 200 and r.data["claim"][KEY]["statement"] == "Most chosen"
    assert estimate(api).status == 201
    clock.set_clock(lambda: at("2027-03-31T00:00:01"))
    assert unavailable(catalog(api)), "at the review date the cached release stops showing the claim"
    assert unavailable(estimate(api))
    clock.set_clock(lambda: at("2027-04-15T12:00:00"))
    assert unavailable(catalog(api))


@ON
def test_the_cache_lifetime_never_reaches_past_the_next_claim_boundary(api, people):
    live_with_claim(people)
    clock.set_clock(lambda: at("2026-10-20T10:00:00"))
    assert catalog(api).headers["Cache-Control"] == f"public, max-age={configure.CATALOG_MAX_AGE}"
    clock.set_clock(lambda: at("2027-03-30T23:59:30"))
    assert catalog(api).headers["Cache-Control"] == "public, max-age=30"


@ON
def test_a_claim_withdrawn_after_activation_is_not_served(api, people):
    live_with_claim(people)
    key = new_key()
    assert catalog(api).status == 200 and estimate(api, key).status == 201
    control(people, "WITHDRAW")
    assert unavailable(catalog(api)), "the cached payload is not served once its claim is withdrawn"
    assert unavailable(estimate(api)), "no new estimate while a shown claim is invalid"
    assert unavailable(estimate(api, key)), "a replay is not served either"
    control(people, "REINSTATE")
    assert catalog(api).status == 200


@ON
def test_removing_the_owner_after_activation_fails_closed_until_one_is_assigned(api, people):
    live_with_claim(people)
    control(people, "UNASSIGN_OWNER")
    assert unavailable(catalog(api))
    control(people, "ASSIGN_OWNER", owner="Brand lead (role, test)")
    assert catalog(api).status == 200
    a, _ = people
    with pytest.raises(claims.ClaimError, match="owner"):
        tx(
            a,
            lambda s: claims.control(
                s, KEY, "ASSIGN_OWNER", "No owner named here (synthetic test)", owner="UNASSIGNED"
            ),
        )


@ON
def test_narrowing_applicability_after_activation_fails_closed_where_it_no_longer_applies(api, people):
    live_with_claim(people)
    control(people, "RESTRICT_APPLICABILITY", applies_to={"packages": ["slice.premium"]})
    assert unavailable(catalog(api)), "the badge is shown on slice.essential, which the claim no longer covers"
    control(people, "RESTRICT_APPLICABILITY", applies_to={"packages": ["slice.essential"]})
    assert catalog(api).status == 200


@ON
def test_the_environment_must_remain_permitted(api, people):
    rel = live_with_claim(people)
    with db.unit_of_work(write=False) as s:
        cat = catalog_compile.load_release(s, s.get(CatalogRelease, rel))
    assert claims.problems(cat, env="test") == []
    assert any("not approved for the production environment" in p for p in claims.problems(cat, env="production"))


def test_a_claim_not_permitted_in_this_environment_is_refused_by_the_release_gate(people):
    from tests.integration.test_catalog_claims import _release_with_badge

    _a, _b, _rel, report = _release_with_badge(people, claim_docs.claim_copy("Most chosen", environments=["staging"]))
    assert not report["ok"] and any("not approved for the test environment" in e for e in report["errors"])


def test_controls_are_refused_for_text_that_is_not_a_governed_claim(people):
    a, _ = people
    seed_slice(a)
    with pytest.raises(claims.ClaimError, match="not a governed claim"):
        tx(a, lambda s: claims.control(s, "copy.disclaimer", "WITHDRAW", "Not a claim at all (synthetic test)"))
    with pytest.raises(claims.ClaimError, match="at least 10"):
        tx(a, lambda s: claims.control(s, "copy.soft-close.promise", "WITHDRAW", "short"))


@ON
def test_staff_list_and_withdraw_claims_through_the_api(api, factory, people):
    live_with_claim(people)
    founder = factory.user("FOUNDER")
    token = factory.login(api, founder, set_default=False)
    listed = api.get("/api/v1/catalog/claims", token=token)
    assert listed.status == 200 and {"key": KEY, "valid": True} == {
        k: v for k, v in listed.data[0].items() if k in ("key", "valid")
    }
    done = api.post(f"/api/v1/catalog/claims/{KEY}/control",
                    {"action": "WITHDRAW", "reason": "Evidence no longer current (synthetic test)"}, token=token)  # fmt: skip
    assert done.status == 200 and done.data["action"] == "WITHDRAW"
    after = api.get("/api/v1/catalog/claims", token=token).data[0]
    assert after["valid"] is False and after["control"] == "WITHDRAW"
    assert unavailable(catalog(api))
    assert api.post(f"/api/v1/catalog/claims/{KEY}/control", {"action": "WITHDRAW", "reason": "x"},
                    anonymous=True).status in (401, 403)  # fmt: skip
