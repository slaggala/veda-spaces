"""PR #91 certification remediation: one-property lineage, staleness after a rate-card change, staleness after a
requirement decision, BOQ review safety (merge blockers 1, 2, 3, 5; merge condition 2). SYNTHETIC sites, cards and
policies only."""

from __future__ import annotations

import sqlalchemy as sa

from tests.integration.test_mtq_variations import _accepted_base, _changed_estimate
from tests.support.commercial import ALL_ON, Commercial, approved_estimate, install_full_policy, load_card, ok, step
from veda.kernel import db

pytestmark = ALL_ON


def _count(number: str) -> int:
    with db.engine().connect() as conn:
        return conn.execute(
            sa.text("SELECT count(*) FROM quotation WHERE quotation_number = :n"), {"n": number}
        ).scalar()


def _sql(stmt: str, **params) -> None:
    with db.engine().begin() as conn:
        conn.execute(sa.text(stmt), params)


# --- merge blocker 1: one property lineage ------------------------------------------------------------------------
def test_quotation_version_only_from_its_own_propertys_estimate(api, factory):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    _, est_a = approved_estimate(c, "2BHK")
    q = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est_a['id']}/quotations", {}), 201)
    _, est_b = approved_estimate(c, "3BHK")
    before = _count(q["quotation_number"])
    r = step(c, q, "versions", c.estimator, {"cost_estimate_id": est_b["id"]}, code=422)
    assert r.code == "LINEAGE_MISMATCH" and "estimate" in r.json["mismatched"]
    assert _count(q["quotation_number"]) == before  # nothing partially created
    assert ok(c.as_(c.estimator).get(f"/api/v1/quotations/{q['id']}"))["status"] == "DRAFT"  # not superseded
    q2 = ok(step(c, q, "versions", c.estimator, {"cost_estimate_id": est_a["id"]}, code=201))  # same property: fine
    assert q2["version_no"] == 2 and q2["property_id"] == q["property_id"]


def test_variation_only_from_its_own_propertys_estimate(api, factory):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    prop, _, base = _accepted_base(c)
    _, other = approved_estimate(c, "3BHK")
    sales = c.as_(c.sales)
    before = _count(base["quotation_number"])
    r = sales.post(f"/api/v1/quotations/{base['id']}/variations", {"cost_estimate_id": other["id"]})
    assert r.status == 422 and r.code == "LINEAGE_MISMATCH"
    assert _count(base["quotation_number"]) == before
    v = ok(c.as_(c.sales).post(f"/api/v1/quotations/{base['id']}/variations",
                               {"cost_estimate_id": _changed_estimate(c, prop)["id"]}), 201)  # fmt: skip
    # the reviewer's probe: a new version of the variation from another property's estimate
    r = step(c, v, "versions", c.estimator, {"cost_estimate_id": other["id"]}, code=422)
    assert r.code == "LINEAGE_MISMATCH"
    assert ok(c.as_(c.estimator).get(f"/api/v1/quotations/{v['id']}"))["status"] == "DRAFT"
    assert _count(base["quotation_number"]) == before + 1


def test_manipulated_boq_and_scope_lineage_is_refused(api, factory):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    _, est_a = approved_estimate(c, "2BHK")
    _, est_b = approved_estimate(c, "3BHK")
    est = c.as_(c.estimator)
    # manipulated BOQ lineage: the estimate's BOQ now claims another property's scope
    _sql("UPDATE boq SET scope_id = :s WHERE id = :b", s=est_b["scope_id"], b=est_a["boq_id"])
    r = est.post(f"/api/v1/cost-estimates/{est_a['id']}/quotations", {})
    assert r.status == 422 and r.code == "LINEAGE_MISMATCH"
    _sql("UPDATE boq SET scope_id = :s WHERE id = :b", s=est_a["scope_id"], b=est_a["boq_id"])
    # manipulated scope lineage: the scope now claims another property's measurement set
    _sql("UPDATE scope SET measurement_set_id = :m WHERE id = :s", m=est_b["measurement_set_id"], s=est_a["scope_id"])
    r = est.post(f"/api/v1/cost-estimates/{est_a['id']}/quotations", {})
    assert r.status == 422 and r.code == "LINEAGE_MISMATCH" and "scope" in r.json["mismatched"]
    with db.engine().connect() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM quotation WHERE cost_estimate_id = :e"),
                            {"e": est_a["id"]}).scalar() == 0  # fmt: skip


# --- merge blocker 2: the pricing context -------------------------------------------------------------------------
def test_an_estimate_is_priced_only_with_its_boqs_card(api, factory):
    load_card()
    c = Commercial(api, factory)
    _, scope, boq = c.reviewed_boq("2BHK")
    estimator = c.as_(c.estimator)
    est_a = ok(estimator.post(f"/api/v1/boqs/{boq['id']}/cost-estimates", {"tier_code": "ESSENTIAL"}), 201)
    assert est_a["lineage"] == {"stale": False, "reasons": []}  # current
    added: dict = {}

    def add_line(d):  # card B adds a line to a product the BOQ uses (the reviewer's probe)
        for p in d["products"]:
            if p["code"] == "KITCHEN":
                extra = dict(p["lines"][0], code="EXTRA_LINE", label="Extra line")
                extra.pop("when", None)
                p["lines"].append(extra)
                added["product"] = p["code"]

    load_card(version="SYNTHETIC-B", mutate=add_line)
    assert added
    again = ok(estimator.get(f"/api/v1/cost-estimates/{est_a['id']}"))
    assert again["lineage"]["stale"] and {"RATE_CARD_CHANGED", "CATALOGUE_CHANGED"} <= {
        r["code"] for r in again["lineage"]["reasons"]
    }
    assert again["subtotal_minor"] == est_a["subtotal_minor"]  # no hidden re-pricing
    assert [x["amount_minor"] for x in again["lines"]] == [x["amount_minor"] for x in est_a["lines"]]
    assert ok(estimator.get(f"/api/v1/cost-estimates/{est_a['id']}/reproduce"))["reproducible"] is True
    r = estimator.post(f"/api/v1/boqs/{boq['id']}/cost-estimates", {"tier_code": "ESSENTIAL"})
    assert r.status == 409 and r.code == "BOQ_STALE"  # never priced against a card it was not built with
    assert ok(estimator.get(f"/api/v1/boqs/{boq['id']}"))["lineage"]["reasons"][0]["code"] == "CATALOGUE_CHANGED"
    boq_b = ok(c.review(c.boq(scope)))
    assert boq_b["catalogue_card_version"] == "SYNTHETIC-B"
    est_b = ok(estimator.post(f"/api/v1/boqs/{boq_b['id']}/cost-estimates", {"tier_code": "ESSENTIAL"}), 201)
    assert any(x["card_line_code"] == "EXTRA_LINE" for x in est_b["lines"])  # the added line is priced, not lost
    assert est_b["rate_card_version"] == "SYNTHETIC-B" and not est_b["lineage"]["stale"]


# --- merge blocker 3: staleness after requirement decisions ---------------------------------------------------------
def _wardrobe(c: Commercial, prop: dict) -> dict:
    reqs = ok(c.as_(c.estimator).get(f"/api/v1/properties/{prop['id']}/requirements"))
    return next(r for r in reqs if r["requirement_type_code"] == "WARDROBE" and r["status"] == "ACCEPTED")


def _decide(c: Commercial, req: dict, status: str):
    api = c.as_(c.estimator)
    cur = next(r for r in ok(api.get(f"/api/v1/properties/{req['property_id']}/requirements")) if r["id"] == req["id"])
    return ok(api.post(f"/api/v1/requirements/{req['id']}/decision", {"status": status, "reason": "customer changed it"},
                       if_match=cur["version"]))  # fmt: skip


def test_requirement_decision_after_confirm_stales_everything_downstream(api, factory):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    prop, est = approved_estimate(c, "2BHK")
    estimator = c.as_(c.estimator)
    q = ok(estimator.post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    wardrobe = _wardrobe(c, prop)
    _decide(c, wardrobe, "EXCLUDED")  # accepted → excluded after the scope was confirmed
    scope = ok(estimator.get(f"/api/v1/scopes/{est['scope_id']}"))
    assert scope["lineage"]["reasons"][0]["code"] == "REQUIREMENTS_CHANGED"
    boq = ok(estimator.get(f"/api/v1/boqs/{est['boq_id']}"))
    assert boq["lineage"]["stale"] and boq["status"] == "REVIEWED"  # history unchanged, reported stale
    assert ok(estimator.get(f"/api/v1/cost-estimates/{est['id']}"))["lineage"]["stale"]
    r = estimator.post(f"/api/v1/scopes/{scope['id']}/boqs")
    assert r.status == 409 and r.code == "SCOPE_STALE"  # the changed scope cannot feed a BOQ
    r = estimator.post(f"/api/v1/boqs/{boq['id']}/cost-estimates", {"tier_code": "ESSENTIAL"})
    assert r.status == 409 and r.code == "BOQ_STALE"  # nor the stale BOQ an estimate
    r = step(c, q, "issue", c.manager, code=409)  # nor the stale estimate a customer quotation
    assert r.code == "NOT_CUSTOMER_ISSUABLE" and any(b["code"] == "STALE_LINEAGE" for b in r.json["blockers"])
    # regeneration: the excluded wardrobe is not an active BOQ line any more
    scope2 = c.confirm(c.fill_staff_inputs(c.draft_scope(prop)))
    assert wardrobe["id"] not in {i["requirement_id"] for i in scope2["items"]}
    boq2 = ok(c.review(c.boq(scope2)))
    assert wardrobe["id"] not in {x["requirement_id"] for x in boq2["lines"]}
    assert any(x["requirement_id"] == wardrobe["id"] for x in boq2["summary"]["requirement_exclusions"])
    old = ok(estimator.get(f"/api/v1/boqs/{boq['id']}"))
    assert old["status"] == "SUPERSEDED" and old["snapshot_sha256"] == boq["snapshot_sha256"]
    # excluded → accepted again: stale again
    _decide(c, wardrobe, "ACCEPTED")
    assert (
        ok(estimator.get(f"/api/v1/scopes/{scope2['id']}"))["lineage"]["reasons"][0]["code"] == "REQUIREMENTS_CHANGED"
    )


def test_additions_and_preference_changes_stale_the_scope(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop, scope, boq = c.reviewed_boq("2BHK")
    estimator = c.as_(c.estimator)
    spaces = {sp["label"]: sp for sp in ok(estimator.get(f"/api/v1/properties/{prop['id']}/spaces"))}
    added = ok(estimator.post(f"/api/v1/properties/{prop['id']}/requirements",
                              {"space_id": spaces["Bedroom 2"]["id"], "requirement_type_code": "TV_UNIT",
                               "source_code": "CUSTOMER_REQUEST"}), 201)  # fmt: skip
    assert ok(estimator.get(f"/api/v1/boqs/{boq['id']}"))["lineage"]["reasons"][0]["code"] == "REQUIREMENTS_CHANGED"
    scope2 = c.confirm(c.fill_staff_inputs(c.draft_scope(prop)))
    assert not ok(estimator.get(f"/api/v1/scopes/{scope2['id']}"))["lineage"]["stale"]
    cur = next(r for r in ok(estimator.get(f"/api/v1/properties/{prop['id']}/requirements")) if r["id"] == added["id"])
    ok(estimator.patch(f"/api/v1/requirements/{added['id']}", {"preferences": {"finish_code": "ACRYLIC"}},
                       if_match=cur["version"]))  # fmt: skip
    assert (
        ok(estimator.get(f"/api/v1/scopes/{scope2['id']}"))["lineage"]["reasons"][0]["code"] == "REQUIREMENTS_CHANGED"
    )
    # a manual addition decided not applicable still changes the decisions the scope was built from
    scope3 = c.confirm(c.fill_staff_inputs(c.draft_scope(prop)))
    _decide(c, {**added, "property_id": prop["id"]}, "NOT_APPLICABLE")
    assert ok(estimator.get(f"/api/v1/scopes/{scope3['id']}"))["lineage"]["stale"]


# --- merge blocker 5: review safety ---------------------------------------------------------------------------------
def test_only_one_reviewed_boq_and_count_quantities_are_whole(api, factory):
    load_card()
    c = Commercial(api, factory)
    _, scope, boq1 = c.reviewed_boq("2BHK")
    estimator = c.as_(c.estimator)
    boq2 = c.boq(scope)
    tandem = next(x for x in boq2["lines"] if x["card_line_code"] == "TANDEM")
    r = estimator.post(f"/api/v1/boq-lines/{tandem['id']}/override", {"quantity_centi": 250, "reason": "layout"},
                       if_match=tandem["version"])  # fmt: skip
    assert r.status == 422 and r.json["errors"][0]["code"] == "NOT_WHOLE"
    assert all(x["quantity_status"] in ("VALID", "VALID_ZERO") for x in boq2["lines"] if not x["is_optional"])
    ok(c.review(boq2))
    first = ok(estimator.get(f"/api/v1/boqs/{boq1['id']}"))
    assert first["status"] == "SUPERSEDED" and first["lineage"]["reasons"][-1]["code"] == "BOQ_SUPERSEDED"
    r = estimator.post(f"/api/v1/boqs/{boq1['id']}/cost-estimates", {"tier_code": "ESSENTIAL"})
    assert r.status == 409


def test_a_fractional_count_entry_is_refused(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop = c.site("2BHK")
    c.seed(prop)
    c.decide_all(prop)
    scope = c.draft_scope(prop)
    kitchen = next(i for i in scope["items"] if i["item_type_code"] == "KITCHEN")
    r = c.as_(c.estimator).patch(f"/api/v1/scope-items/{kitchen['id']}", {"dimension_overrides": {"DRAWERS": 2.5},
                                 "override_reason": "layout"}, if_match=kitchen["version"])  # fmt: skip
    assert r.status == 422 and r.json["errors"][0]["code"] == "NOT_WHOLE"


def test_an_included_item_without_a_catalogue_line_blocks_review(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop = c.site("2BHK")
    c.seed(prop)
    c.decide_all(prop, optional="ACCEPTED")
    scope = c.fill_staff_inputs(c.draft_scope(prop))
    estimator = c.as_(c.estimator)
    mirror = next(i for i in scope["items"] if i["item_type_code"] == "MIRROR_PANEL")
    assert mirror["inclusion_code"] == "OPTIONAL"
    ok(
        estimator.patch(
            f"/api/v1/scope-items/{mirror['id']}", {"inclusion_code": "INCLUDED"}, if_match=mirror["version"]
        )
    )
    boq = c.boq(c.confirm(scope))
    line = next(x for x in boq["lines"] if x["item_type_code"] == "MIRROR_PANEL")
    assert line["quantity_status"] == "UNRESOLVED" and line["issues"][0]["code"] == "UNRESOLVED_CATALOGUE_MAPPING"
    r = c.review(boq)
    assert r.status == 409 and r.code == "BOQ_HAS_BLOCKING_ISSUES"
    assert any(i["code"] == "UNRESOLVED_CATALOGUE_MAPPING" for i in r.json["issues"])
