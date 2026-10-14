"""MTQ B3 estimate versioning: sealed revisions, comparison, reproducibility after a rate-card change, owner-decision
lines kept visible. SYNTHETIC rate cards only."""

from __future__ import annotations

from tests.support.commercial import ON, Commercial, load_card, ok

pytestmark = ON


def _estimate(c: Commercial, boq: dict, tier: str = "ESSENTIAL", user=None):
    return c.as_(user or c.estimator).post(f"/api/v1/boqs/{boq['id']}/cost-estimates", {"tier_code": tier})


def test_rate_card_change_never_moves_a_stored_estimate(api, factory):
    load_card()
    c = Commercial(api, factory)
    _, _, boq = c.reviewed_boq("2BHK")
    est = ok(_estimate(c, boq), 201)
    approved = ok(c.as_(c.manager).post(f"/api/v1/cost-estimates/{est['id']}/approve", if_match=est["version"]))

    def dearer(d):
        for p in d["products"]:
            for line in p["lines"]:
                line["rates"] = {k: v * 11 // 10 for k, v in line["rates"].items()}

    load_card(version="SYNTHETIC-3", mutate=dearer)
    mgr = c.as_(c.manager)
    again = ok(mgr.get(f"/api/v1/cost-estimates/{est['id']}"))
    assert (
        again["subtotal_minor"] == approved["subtotal_minor"]
        and again["snapshot_sha256"] == approved["snapshot_sha256"]
    )
    codes = {r["code"] for r in again["lineage"]["reasons"]}
    assert again["lineage"]["stale"] and {"RATE_CARD_CHANGED", "CATALOGUE_CHANGED"} <= codes
    assert ok(mgr.get(f"/api/v1/cost-estimates/{est['id']}/reproduce"))["reproducible"] is True
    # the BOQ was built against the old card: pricing it with the new one is refused, never silently mixed
    r = _estimate(c, boq)
    assert r.status == 409 and r.code == "BOQ_STALE" and r.json["reasons"][0]["code"] == "CATALOGUE_CHANGED"
    boq = ok(c.review(c.boq(ok(c.as_(c.estimator).get(f"/api/v1/scopes/{boq['scope_id']}")))))
    new = ok(_estimate(c, boq), 201)
    assert new["rate_card_version"] == "SYNTHETIC-3" and new["subtotal_minor"] > again["subtotal_minor"]
    diff = ok(mgr.get(f"/api/v1/cost-estimates/{est['id']}/compare/{new['id']}"))
    assert diff["rate_card"] == {"from": "SYNTHETIC-2", "to": "SYNTHETIC-3"}
    assert any("RATE" in x.get("tags", []) for x in diff["lines"])


def test_five_bhk_and_independent_house_preparation_waits_for_the_owner(api, factory):
    load_card()
    c = Commercial(api, factory)
    for key in ("5BHK", "IH"):
        _, _, boq = c.reviewed_boq(key)
        est = ok(_estimate(c, boq), 201)
        prep = [x for x in est["lines"] if x["prep_component_code"]]
        assert prep and all(x["rate_status"] == "OWNER_DECISION_REQUIRED" for x in prep), key
        assert any(b["code"] == "OWNER_DECISION_REQUIRED" and b["decision"] == "OI-MTQ-15" for b in est["blockers"])
        ok(c.as_(c.manager).post(f"/api/v1/cost-estimates/{est['id']}/approve", if_match=est["version"]))
