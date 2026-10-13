"""MTQ B2: requirements, scope and BOQ on a SYNTHETIC verified site (instruction B2.1-B2.6)."""

from __future__ import annotations

from decimal import Decimal

from tests.support.commercial import ON, Commercial, load_card, ok

pytestmark = ON


def test_seeded_requirements_are_proposed_with_provenance(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop = c.site("3BHK")
    reqs = c.seed(prop)
    assert reqs and all(r["status"] == "PROPOSED" for r in reqs)
    by_type = {}
    for r in reqs:
        by_type.setdefault(r["requirement_type_code"], []).append(r)
    wardrobes = by_type["WARDROBE"]
    assert len(wardrobes) == 3  # master + bedrooms 2 and 3, each from its tagged wall
    w = wardrobes[0]
    assert w["source_code"] == "MEASUREMENT_RULE" and w["origin_code"] == "AUTO"
    assert w["source_ref"]["rule_key"] == "WARDROBE_FROM_TAGGED_WALL" and w["anchor_wall_index"] == 2
    assert w["source_ref"]["ruleset_status"] == "PROPOSED" and len(w["source_ref"]["ruleset_sha256"]) == 64
    assert w["source_ref"]["measurement_revision_no"] >= 1
    beds = by_type["BED"]
    assert all(b["source_code"] == "SURVEY_TEMPLATE" and b["classification"] == "OPTIONAL" for b in beds)
    # idempotent: a second seed proposes nothing new and leaves decisions alone
    api_ = c.as_(c.estimator)
    again = ok(api_.post(f"/api/v1/properties/{prop['id']}/requirements/seed"))
    assert again["created"] == 0 and again["unchanged"] == len(reqs)


def test_scope_needs_every_recommendation_decided_and_boq_is_explainable(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop = c.site("3BHK")
    c.seed(prop)
    scope = c.draft_scope(prop)
    assert scope["items"] == [] and scope["generation_run"]["undecided_requirement_ids"]
    resp = c.as_(c.estimator).post(f"/api/v1/scopes/{scope['id']}/confirm", if_match=scope["version"])
    assert resp.status == 409 and resp.code == "UNDECIDED_REQUIREMENTS"
    c.decide_all(prop)
    api_ = c.as_(c.estimator)
    cur = ok(api_.get(f"/api/v1/scopes/{scope['id']}"))
    assert api_.post(f"/api/v1/scopes/{scope['id']}/confirm", if_match=cur["version"]).code == "SCOPE_OUT_OF_DATE"
    scope = ok(api_.post(f"/api/v1/scopes/{scope['id']}/refresh", if_match=cur["version"]))
    kitchen = next(i for i in scope["items"] if i["item_type_code"] == "KITCHEN")
    assert kitchen["inputs"]["DRAWERS"]["source"] == "MISSING"
    assert kitchen["inputs"]["RUN"]["source"] in ("MEASURED", "DERIVED")
    scope = c.fill_staff_inputs(scope)
    kitchen = next(i for i in scope["items"] if i["item_type_code"] == "KITCHEN")
    assert kitchen["dimension_overrides"] == {"DRAWERS": "4"} and kitchen["dimension_source_code"] == "STAFF"
    scope = c.confirm(scope)
    assert scope["status"] == "CONFIRMED" and len(scope["snapshot_sha256"]) == 64
    boq = c.boq(scope)
    assert boq["status"] == "GENERATED" and boq["scope_revision_no"] == scope["revision_no"]
    assert boq["catalogue_card_version"] == "SYNTHETIC-2"
    codes = {i["code"] for i in boq["issues"]}
    assert "RULESET_NOT_APPROVED" in codes  # proposed rules are disclosed, never silently treated as approved
    body = next(
        line for line in boq["lines"] if line["card_product_code"] == "WARDROBE" and line["card_line_code"] == "BODY"
    )
    # width = W2 length (no openings on the wardrobe wall), height = min(floor to lintel 2100, 2134) mm
    assert "W2 length" in body["derivation"] and "min(floor to lintel 2100 mm, 2134 mm)" in body["derivation"]
    assert body["formula_inputs"]["inputs"]["WIDTH"]["refs"]["wall_index"] == 2
    assert body["measurement_source"]["measurement_set_id"] == scope["measurement_set_id"]
    width = Decimal(body["formula_inputs"]["inputs"]["WIDTH"]["value"])
    expected = (width * (Decimal(2100) / Decimal("304.8"))).quantize(Decimal("0.01"))
    assert abs(Decimal(body["quantity"]) - expected) <= Decimal("0.01")
    reviewed = ok(c.review(boq))
    assert reviewed["status"] == "REVIEWED" and len(reviewed["snapshot_sha256"]) == 64
    summary = reviewed["summary"]
    assert summary["rooms"] and summary["project"] and summary["totals_by_uom"]["SFT"] > 0


def test_missing_measurement_blocks_review_until_overridden_with_a_reason(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop = c.site("2BHK")
    c.seed(prop)
    c.decide_all(prop)
    scope = c.confirm(c.draft_scope(prop))  # DRAWERS never entered
    boq = c.boq(scope)
    tandem = next(line for line in boq["lines"] if line["card_line_code"] == "TANDEM")
    assert tandem["status"] == "ISSUE" and tandem["calculated_quantity_centi"] is None
    assert tandem["issues"][0]["code"] == "MISSING_MEASUREMENT" and "DRAWERS" in tandem["issues"][0]["message"]
    r = c.review(boq)
    assert r.status == 409 and r.code == "BOQ_HAS_BLOCKING_ISSUES"
    api_ = c.as_(c.estimator)
    bad = api_.post(f"/api/v1/boq-lines/{tandem['id']}/override", {"quantity_centi": 400}, if_match=tandem["version"])
    assert bad.status == 422  # the reason is required
    boq = ok(api_.post(f"/api/v1/boq-lines/{tandem['id']}/override",
                       {"quantity_centi": 400, "reason": "Four drawers on the layout"}, if_match=tandem["version"]))  # fmt: skip
    tandem = next(line for line in boq["lines"] if line["id"] == tandem["id"])
    assert tandem["final_quantity_centi"] == 400 and tandem["calculated_quantity_centi"] is None
    assert tandem["override_reason"] == "Four drawers on the layout" and tandem["status"] == "OK"
    assert boq["summary"]["overridden_lines"] == 1
    assert ok(c.review(boq))["status"] == "REVIEWED"


def test_unmapped_items_stay_in_the_boq_and_are_reported(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop = c.site("2BHK")
    c.seed(prop)
    toilet = next(r for r in ok(c.as_(c.estimator).get(f"/api/v1/properties/{prop['id']}/requirements"))
                  if r["requirement_type_code"] == "MIRROR_PANEL")  # fmt: skip
    assert toilet["catalogue_mapped"] is False
    c.decide_all(prop, optional="ACCEPTED")
    scope = c.confirm(c.fill_staff_inputs(c.draft_scope(prop)))
    boq = c.boq(scope)
    mirror = [line for line in boq["lines"] if line["item_type_code"] == "MIRROR_PANEL"]
    assert mirror and all(
        line["formula_kind"] == "UNMAPPED" and line["calculated_quantity_centi"] is None for line in mirror
    )
    assert (
        mirror[0]["issues"][0]["code"] == "MISSING_CATALOGUE_MAPPING"
        and "OI-MTQ-05" in mirror[0]["issues"][0]["message"]
    )
    assert ok(c.review(boq))["status"] == "REVIEWED"  # a warning, never a silent drop


def test_new_measurement_revision_makes_downstream_stale(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop, scope, boq = c.reviewed_boq("2BHK")
    new = c.remeasure(prop, scope["measurement_set_id"])  # a re-measure: a second FULL revision, verified
    api_ = c.as_(c.estimator)
    stale_boq = ok(api_.get(f"/api/v1/boqs/{boq['id']}"))
    assert stale_boq["lineage"]["stale"] and stale_boq["lineage"]["reasons"][0]["code"] == "MEASUREMENT_REVISED"
    assert stale_boq["status"] == "REVIEWED" and stale_boq["snapshot_sha256"] == boq["snapshot_sha256"]  # unchanged
    r = api_.post(f"/api/v1/scopes/{scope['id']}/boqs")
    assert r.status == 409 and r.code == "SCOPE_STALE"
    journey = ok(api_.get(f"/api/v1/properties/{prop['id']}/commercial"))
    assert journey["current_measurement_set"]["id"] == new["id"]
    assert journey["scopes"][0]["lineage"]["stale"] is True
    # explicit regeneration: a new scope revision on the new measurements carries the staff inputs
    scope2 = c.draft_scope(prop)
    kitchen = next(i for i in scope2["items"] if i["item_type_code"] == "KITCHEN")
    assert kitchen["carried_from_item_id"] and kitchen["dimension_overrides"] == {"DRAWERS": "4"}
    scope2 = c.confirm(scope2)
    boq2 = c.boq(scope2)
    assert boq2["measurement_set_id"] == new["id"] and boq2["revision_no"] == boq["revision_no"] + 1
    diff = ok(api_.get(f"/api/v1/boqs/{boq['id']}/diff/{boq2['id']}"))
    assert diff["from_revision"] == boq["revision_no"]


def test_staff_additions_customer_requests_and_duplicates(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop = c.site("2BHK")
    c.seed(prop)
    api_ = c.as_(c.estimator)
    spaces = {sp["label"]: sp for sp in ok(api_.get(f"/api/v1/properties/{prop['id']}/spaces"))}
    bed2 = spaces["Bedroom 2"]
    r = ok(api_.post(f"/api/v1/properties/{prop['id']}/requirements",
                     {"space_id": bed2["id"], "requirement_type_code": "TV_UNIT", "source_code": "CUSTOMER_REQUEST",
                      "necessity_code": "OPTIONAL", "notes": "Wants a TV in the second bedroom"}), 201)  # fmt: skip
    assert r["status"] == "ACCEPTED" and r["classification"] == "CUSTOMER_REQUESTED"
    assert r["origin_code"] == "CUSTOMER_REQUESTED" and r["decided_by"] == c.estimator.id
    # the same wall twice is duplicate scope
    body = {
        "space_id": bed2["id"],
        "requirement_type_code": "WARDROBE",
        "source_code": "MANUAL",
        "anchor_wall_index": 2,
    }
    dup = api_.post(f"/api/v1/properties/{prop['id']}/requirements", body)
    assert dup.status == 409 and dup.code == "DUPLICATE_SCOPE"
    custom = api_.post(f"/api/v1/properties/{prop['id']}/requirements",
                       {"space_id": bed2["id"], "requirement_type_code": "CUSTOM", "source_code": "MANUAL"})  # fmt: skip
    assert custom.status == 422  # a custom item needs its label
    custom = ok(api_.post(f"/api/v1/properties/{prop['id']}/requirements",
                          {"space_id": bed2["id"], "requirement_type_code": "CUSTOM", "custom_label": "Bar unit",
                           "source_code": "MANUAL"}), 201)  # fmt: skip
    assert custom["label"] == "Bar unit" and custom["catalogue_mapped"] is False
    # a mandatory recommendation is never excluded without a reason
    mandatory = next(x for x in ok(api_.get(f"/api/v1/properties/{prop['id']}/requirements"))
                     if x["necessity_code"] == "MANDATORY" and x["status"] == "PROPOSED")  # fmt: skip
    r = api_.post(
        f"/api/v1/requirements/{mandatory['id']}/decision", {"status": "EXCLUDED"}, if_match=mandatory["version"]
    )
    assert r.status == 422 and r.code == "REASON_REQUIRED"
    r = ok(api_.post(f"/api/v1/requirements/{mandatory['id']}/decision",
                     {"status": "EXCLUDED", "reason": "Customer keeps the existing unit"}, if_match=mandatory["version"]))  # fmt: skip
    assert r["classification"] == "EXCLUDED" and r["decision_reason"] == "Customer keeps the existing unit"
    c.decide_all(prop)
    scope = c.draft_scope(prop)
    assert any(e["requirement_id"] == mandatory["id"] for e in scope["exclusions"])
    origins = {i["origin_code"] for i in scope["items"]}
    assert {"AUTO", "RECOMMENDED", "CUSTOMER_REQUESTED", "MANUAL"} <= origins


def test_material_change_and_invalid_option_and_impossible_quantity(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop = c.site("2BHK")
    c.seed(prop)
    c.decide_all(prop)
    scope = c.fill_staff_inputs(c.draft_scope(prop))
    api_ = c.as_(c.estimator)
    wardrobe = next(i for i in scope["items"] if i["item_type_code"] == "WARDROBE")
    fixed = api_.patch(
        f"/api/v1/scope-items/{wardrobe['id']}", {"options": {"TYPE": "X"}}, if_match=wardrobe["version"]
    )
    assert fixed.status == 422  # not a wardrobe option, but also never a fixed one
    wardrobe = ok(api_.patch(f"/api/v1/scope-items/{wardrobe['id']}", {"options": {"DOOR": "SLIDING"}},
                             if_match=wardrobe["version"]))  # fmt: skip
    assert wardrobe["effective_options"]["DOOR"] == "SLIDING"
    tv = next(i for i in scope["items"] if i["item_type_code"] == "TV_UNIT")
    r = api_.patch(f"/api/v1/scope-items/{tv['id']}", {"dimension_overrides": {"WIDTH": 400}}, if_match=tv["version"])
    assert r.status == 422 and r.code == "OVERRIDE_REASON_REQUIRED"
    ok(api_.patch(f"/api/v1/scope-items/{tv['id']}", {"dimension_overrides": {"WIDTH": 400},
                  "override_reason": "typo test"}, if_match=tv["version"]))  # fmt: skip
    scope = c.confirm(scope)
    boq = c.boq(scope)
    lines = [x for x in boq["lines"] if x["scope_item_id"] == wardrobe["id"]]
    codes = {x["card_line_code"] for x in lines}
    assert "SLIDING" in codes and "SOFT_CLOSE" not in codes  # the card's own option conditions
    tv_lines = [x for x in boq["lines"] if x["scope_item_id"] == tv["id"]]
    assert all(x["status"] == "ISSUE" and x["issues"][0]["code"] == "IMPOSSIBLE_QUANTITY" for x in tv_lines)
    assert c.review(boq).code == "BOQ_HAS_BLOCKING_ISSUES"


def test_least_privilege(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop = c.site("2BHK")
    surveyor = c.ten.lead_surveyor
    assert c.as_(surveyor).get(f"/api/v1/properties/{prop['id']}/requirements").status == 403
    assert c.as_(c.designer).get(f"/api/v1/properties/{prop['id']}/requirements").status == 404  # not the lead owner
    sales = c.as_(c.sales)  # owns the lead: reads and edits scope, never generates or reviews a BOQ
    assert sales.get(f"/api/v1/properties/{prop['id']}/requirements").status == 200
    assert sales.post(f"/api/v1/properties/{prop['id']}/requirements/seed").status == 200
    c.decide_all(prop, user=c.sales)
    scope = c.fill_staff_inputs(c.draft_scope(prop, user=c.sales), user=c.sales)
    assert c.as_(c.sales).post(f"/api/v1/scopes/{scope['id']}/confirm", if_match=scope["version"]).status == 403
    scope = c.confirm(scope)
    assert c.as_(c.sales).post(f"/api/v1/scopes/{scope['id']}/boqs").status == 403
    boq = c.boq(scope)
    line = boq["lines"][0]
    r = c.as_(c.sales).post(f"/api/v1/boq-lines/{line['id']}/override", {"quantity_centi": 1, "reason": "no"},
                            if_match=line["version"])  # fmt: skip
    assert r.status == 403
    assert c.as_(c.sales).get(f"/api/v1/boqs/{boq['id']}").status == 200


def test_lead_erasure_clears_free_text_and_closes_writes(api, factory):
    from tests.support import dbh
    from veda.kernel import db
    from veda.kernel.context import actor, system_context
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead
    from veda.modules.mtq_commercial.models import Requirement

    load_card()
    c = Commercial(api, factory)
    prop, scope, boq = c.reviewed_boq("2BHK")
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, prop["lead_id"]), legal_basis="TEST", request_ref=None)
    reasons = {r.decision_reason for r in dbh.rows(sa_select(Requirement, prop["id"]))}
    assert reasons <= {None, "[erased]"}
    assert c.as_(c.estimator).post(f"/api/v1/properties/{prop['id']}/requirements/seed").status == 409


def sa_select(model, property_id):
    import sqlalchemy as sa

    return sa.select(model).where(model.property_id == property_id)
