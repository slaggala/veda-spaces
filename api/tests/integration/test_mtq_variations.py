"""MTQ B4 variations (change orders): the accepted quotation never changes; changes are delta quotations against the
accepted baseline. SYNTHETIC sites, card and policy only."""

from __future__ import annotations

from tests.support.commercial import ALL_ON, Commercial, approved_estimate, install_full_policy, load_card, ok, step

pytestmark = ALL_ON


def _accepted_base(c: Commercial, key: str = "2BHK"):
    prop, est = approved_estimate(c, key, optional="EXCLUDED")
    q = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    step(c, q, "issue", c.manager)
    q = ok(step(c, q, "decision", c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY"}))
    return prop, est, q


def _changed_estimate(c: Commercial, prop: dict) -> dict:
    """The customer adds a TV unit in Bedroom 2 and switches the master wardrobe to sliding doors."""
    api = c.as_(c.estimator)
    spaces = {sp["label"]: sp for sp in ok(api.get(f"/api/v1/properties/{prop['id']}/spaces"))}
    ok(api.post(f"/api/v1/properties/{prop['id']}/requirements",
                {"space_id": spaces["Bedroom 2"]["id"], "requirement_type_code": "TV_UNIT",
                 "source_code": "CUSTOMER_REQUEST", "necessity_code": "RECOMMENDED"}), 201)  # fmt: skip
    scope = c.fill_staff_inputs(c.draft_scope(prop))
    tv = next(i for i in scope["items"] if i["item_type_code"] == "TV_UNIT" and i["space_label"] == "Bedroom 2")
    ok(api.patch(f"/api/v1/scope-items/{tv['id']}", {"dimension_overrides": {"WIDTH": 6},
                 "override_reason": "No TV wall tagged; width from the design"}, if_match=tv["version"]))  # fmt: skip
    wardrobe = next(
        i for i in scope["items"] if i["item_type_code"] == "WARDROBE" and i["space_label"] == "Master bedroom"
    )
    ok(
        api.patch(
            f"/api/v1/scope-items/{wardrobe['id']}", {"options": {"DOOR": "SLIDING"}}, if_match=wardrobe["version"]
        )
    )
    boq = c.boq(c.confirm(scope))
    ok(c.review(boq))
    est = ok(api.post(f"/api/v1/boqs/{boq['id']}/cost-estimates", {"tier_code": "ESSENTIAL"}), 201)
    return ok(c.as_(c.manager).post(f"/api/v1/cost-estimates/{est['id']}/approve", if_match=est["version"]))


def test_variation_after_acceptance_keeps_the_base_immutable(api, factory):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    prop, est, base = _accepted_base(c)
    sha, total = base["snapshot_sha256"], base["decision"]["accepted_total_minor"]
    r = step(c, base, "versions", c.estimator, {"cost_estimate_id": est["id"]}, code=409)
    assert r.code == "QUOTATION_ACCEPTED"
    est2 = _changed_estimate(c, prop)
    v = ok(c.as_(c.sales).post(f"/api/v1/quotations/{base['id']}/variations", {"cost_estimate_id": est2["id"]}), 201)
    assert v["quotation_kind"] == "VARIATION" and v["variation_no"] == 1 and v["label"].endswith("-V01 v1")
    assert v["baseline_quotation_id"] == base["id"] and v["variation_of_quotation_id"] == base["id"]
    lines = [x for sec in v["sections"] for x in sec["lines"]]
    codes = {x["change_code"] for x in lines}
    assert "ADD" in codes and "CHANGE_MATERIAL" in codes and "NONE" not in codes
    tv = [x for x in lines if x["change_code"] == "ADD"]
    assert all(x["baseline_amount_minor"] == 0 and x["delta_amount_minor"] == x["amount_minor"] for x in tv)
    net = sum(x["delta_amount_minor"] for x in lines)
    assert v["base_total_minor"] == net and v["total_minor"] == net + v["tax_minor"]
    assert v["blockers"] == []
    step(c, v, "submit", c.sales)
    step(c, v, "approve", c.manager)
    v = ok(step(c, v, "issue", c.manager))
    doc = ok(c.as_(c.sales).get(f"/api/v1/quotations/{v['id']}/document"))["document"]
    assert doc["title"] == "Variation (change order)" and doc["summary"]["net_change"]
    v = ok(step(c, v, "decision", c.sales, {"decision": "ACCEPTED", "method": "STAFF_RECORDED"}))
    after = ok(c.as_(c.sales).get(f"/api/v1/quotations/{base['id']}"))
    assert after["status"] == "ACCEPTED" and after["snapshot_sha256"] == sha and after["snapshot_verified"] is True
    chain = ok(c.as_(c.sales).get(f"/api/v1/quotations/{base['id']}/chain"))
    assert chain["accepted_value_minor"] == total + v["decision"]["accepted_total_minor"]
    assert [x["label"].split()[-1] for x in chain["versions"]] == ["v1", "v1"]


def test_variation_waits_for_the_variation_policy(api, factory):
    install_full_policy(OI_MTQ_13=None)
    load_card()
    c = Commercial(api, factory)
    prop, _, base = _accepted_base(c)
    v = ok(c.as_(c.sales).post(f"/api/v1/quotations/{base['id']}/variations",
                               {"cost_estimate_id": _changed_estimate(c, prop)["id"]}), 201)  # fmt: skip
    assert {(b["code"], b.get("decision")) for b in v["blockers"]} == {("OWNER_DECISION_REQUIRED", "OI-MTQ-13")}
    second = c.as_(c.sales).post(f"/api/v1/quotations/{base['id']}/variations", {"cost_estimate_id": v["cost_estimate_id"]
                                 if "cost_estimate_id" in v else v["lineage"]["cost_estimate_id"]})  # fmt: skip
    assert second.status == 409 and second.code == "VARIATION_OPEN"
