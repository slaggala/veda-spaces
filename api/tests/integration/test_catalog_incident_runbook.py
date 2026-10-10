"""B1-B3 policy closure, Phase 9: the V3 incident runbook (docs/implementation/catalog/CATALOG-V3-incident-runbook.md).

Rollback stays fail-closed: it restores the previous manifest only when the restored customer payload is exactly the
one that was approved, and every governed claim in it is still valid. When a rollback is blocked, recovery is a new
reviewed release; the emergency action is to switch V3 off, which leaves V1 and V2 untouched. Synthetic data only."""

import pytest

from tests.integration.test_catalog import approve_all, release, seed_slice, tx
from tests.integration.test_catalog_claim_validity import KEY, live_with_claim
from tests.integration.test_catalog_closure import change
from tests.integration.test_estimator_spec import load_spec, spec_version
from veda.kernel import clock, db
from veda.modules.catalog import claims, configure, service
from veda.modules.catalog.models import CatalogRelease

ON = pytest.mark.settings(catalog_estimator_enabled=True, catalog_admin_enabled=True)


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


@pytest.fixture(autouse=True)
def _reset():
    configure._view_cache.clear()
    yield
    clock.reset()
    configure._view_cache.clear()


def next_release(people, code, description):
    a, b = people
    change(a, "product", "tv-unit", lambda d: d.update(description=description))
    approve_all(a, b)
    return release(a, b, code)


def active_code():
    with db.unit_of_work(write=False) as s:
        return service.active_release(s).release_code


def test_an_ordinary_rollback_restores_the_previous_manifest(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b, "INC-A")
    next_release(people, "INC-B", "A unit for the TV wall, second.")
    restored = tx(a, service.rollback, "Restore INC-A after an incident (test)", "INC-B")
    with db.unit_of_work(write=False) as s:
        row = s.get(CatalogRelease, restored.id)
        assert row.status == "ACTIVE" and row.manifest["rollback_of"] == "INC-A"


def test_a_rollback_to_a_release_whose_claim_is_now_invalid_is_refused(people):
    a, _b = people
    live_with_claim(people)  # INC: the slice with a governed badge claim (SLICE-1)
    next_release(people, "INC-B", "A unit for the TV wall, second.")
    tx(a, lambda s: claims.control(s, KEY, "WITHDRAW", "Evidence withdrawn after activation (test)"))
    with pytest.raises(service.CatalogError, match="claim withdrawn"):
        tx(a, service.rollback, "Restore SLICE-1 after an incident (test)", "INC-B")
    assert active_code() == "INC-B", "the active release is untouched; nothing is half-restored"


def test_a_rollback_blocked_by_a_changed_specification_is_refused(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b, "INC-A")
    next_release(people, "INC-B", "A unit for the TV wall, second.")
    load_spec({**spec_version(7), "package": "ESSENTIAL"})  # the specification customers would see has changed
    with pytest.raises(service.CatalogError, match="public payload changed"):
        tx(a, service.rollback, "Restore INC-A after an incident (test)", "INC-B")
    assert active_code() == "INC-B"


@pytest.mark.settings(catalog_estimator_enabled=False, catalog_admin_enabled=True, estimator_enabled=True)
def test_the_emergency_action_switches_v3_off_and_leaves_v1_v2_alone(api, people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b, "INC-A")
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 404
    assert api.post("/api/v1/public/catalog/estimates", {"configuration": {}, "turnstile_token": "x"},
                    anonymous=True).status == 404  # fmt: skip
    v2 = api.post("/api/v1/public/estimates", {}, anonymous=True, headers={"Origin": "http://localhost:8000"})
    assert v2.status != 404, "the V1/V2 public estimate route is governed by its own switch, not by V3's"


@pytest.mark.settings(catalog_estimator_enabled=True, catalog_admin_enabled=True)
def test_recovery_is_a_new_reviewed_release(api, people):
    a, b = people
    live_with_claim(people)
    tx(a, lambda s: claims.control(s, KEY, "WITHDRAW", "Evidence withdrawn after activation (test)"))
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 503, "fail closed while the claim is shown"
    change(a, "package", "slice.essential", lambda d: d.update(badge=None))  # the recovery drops the claim ...
    approve_all(a, b)
    rel = tx(a, service.create_release, "INC-RECOVERY", exclude=(("copy", KEY),))  # ... and retires its record
    assert tx(a, service.validate_release, rel.id)["ok"]
    tx(b, service.approve_preview, rel.id)  # four eyes: reviewed by someone other than the author
    tx(a, service.submit_release, rel.id)
    tx(b, service.approve_release, rel.id, "Owner approval 2026-10-10 (synthetic recovery release)")
    tx(a, service.activate_release, rel.id)
    configure._view_cache.clear()
    r = api.get("/api/v1/public/catalog", anonymous=True)
    assert r.status == 200 and r.data["release"] == "INC-RECOVERY" and KEY not in r.data["claim"]
