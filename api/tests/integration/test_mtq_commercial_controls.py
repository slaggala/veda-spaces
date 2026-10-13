"""MTQ B3 commercial controls: unapproved tiers and finishes refused, discounts disabled until OI-MTQ-06 is
decided then authority and four-eyes, GST only from a decided treatment. Any decided policy here is the SYNTHETIC
test policy, never an owner decision."""

from __future__ import annotations

from tests.support.commercial import ON, Commercial, install_policy, load_card, ok

pytestmark = ON


def _estimate(c: Commercial, boq: dict, tier: str = "ESSENTIAL", user=None):
    return c.as_(user or c.estimator).post(f"/api/v1/boqs/{boq['id']}/cost-estimates", {"tier_code": tier})


def test_unapproved_tiers_are_refused_never_invented(api, factory):
    load_card()
    c = Commercial(api, factory)
    _, _, boq = c.reviewed_boq("2BHK")
    r = _estimate(c, boq, "PREMIUM")
    assert r.status == 409 and r.code == "RATE_CARD_NOT_APPROVED" and r.json["decision"] == "OI-MTQ-05"
    assert _estimate(c, boq, "LUXURY").code == "RATE_CARD_NOT_APPROVED"
    install_policy()  # SYNTHETIC: Premium staff rates decided; Luxury still disabled on the card
    assert ok(_estimate(c, boq, "PREMIUM"), 201)["tier_code"] == "PREMIUM"
    assert _estimate(c, boq, "LUXURY").code == "RATE_CARD_NOT_APPROVED"


def test_finish_variant_without_an_approved_rate_is_unpriced(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop = c.site("2BHK")
    c.seed(prop)
    c.decide_all(prop)
    scope = c.fill_staff_inputs(c.draft_scope(prop))
    api_ = c.as_(c.estimator)
    wardrobe = next(i for i in scope["items"] if i["item_type_code"] == "WARDROBE")
    ok(api_.patch(f"/api/v1/scope-items/{wardrobe['id']}", {"finish_code": "ACRYLIC"}, if_match=wardrobe["version"]))
    boq = c.boq(c.confirm(scope))
    ok(c.review(boq))
    est = ok(_estimate(c, boq), 201)
    lines = [x for x in est["lines"] if x["scope_item_id"] == wardrobe["id"]]
    assert lines and all(x["rate_status"] == "FINISH_RATE_NOT_APPROVED" for x in lines)
    assert "OI-MTQ-05" in lines[0]["rate_note"]
    install_policy()  # SYNTHETIC: an acrylic WARDROBE.BODY rate exists; other wardrobe lines still have none
    est = ok(_estimate(c, boq), 201)
    body = next(x for x in est["lines"] if x["scope_item_id"] == wardrobe["id"] and x["card_line_code"] == "BODY")
    assert body["rate_status"] == "PRICED" and body["rate_minor"] == 150000 and body["finish_code"] == "ACRYLIC"


def test_discounts_disabled_until_decided_then_authority_and_four_eyes(api, factory):
    load_card()
    c = Commercial(api, factory)
    _, _, boq = c.reviewed_boq("3BHK")
    est = ok(_estimate(c, boq), 201)
    api_ = c.as_(c.estimator)
    r = api_.post(f"/api/v1/cost-estimates/{est['id']}/adjustments",
                  {"scope_code": "PROJECT", "kind_code": "PERCENT", "value_bp": 100, "reason": "Festive offer"})  # fmt: skip
    assert r.status == 409 and r.code == "OWNER_DECISION_REQUIRED" and r.json["decision"] == "OI-MTQ-06"
    assert est["discount_policy"]["enabled"] is False
    install_policy()  # SYNTHETIC: self limit 2 %, maximum 10 %, four-eyes
    line = next(x for x in est["lines"] if x["rate_status"] == "PRICED" and not x["is_optional"] and x["boq_line_id"])
    est = ok(api_.post(f"/api/v1/cost-estimates/{est['id']}/adjustments",
                       {"scope_code": "LINE", "target_line_id": line["id"], "kind_code": "AMOUNT", "amount_minor": 100,
                        "reason": "Rounding for the customer"}), 201)  # fmt: skip
    small = est["adjustments"][0]
    assert small["status"] == "APPROVED" and small["authority_code"] == "WITHIN_LIMIT"
    assert small["base_minor"] == line["amount_minor"] and small["post_minor"] == line["amount_minor"] - 100
    after = next(x for x in est["lines"] if x["id"] == line["id"])
    assert after["rate_minor"] == line["rate_minor"] and after["amount_minor"] == line["amount_minor"]  # rate untouched
    assert after["discount_minor"] == 100 and est["discount_minor"] == 100
    est = ok(api_.post(f"/api/v1/cost-estimates/{est['id']}/adjustments",
                       {"scope_code": "CATEGORY", "target_category": "CARPENTRY", "kind_code": "PERCENT",
                        "value_bp": 500, "reason": "Full-home order"}), 201)  # fmt: skip
    big = est["adjustments"][1]
    assert big["status"] == "PROPOSED" and est["discount_minor"] == 100  # only approved discounts count
    assert any(b["code"] == "DISCOUNT_APPROVAL_PENDING" for b in est["blockers"])
    too_much = api_.post(f"/api/v1/cost-estimates/{est['id']}/adjustments",
                         {"scope_code": "PROJECT", "kind_code": "PERCENT", "value_bp": 900, "reason": "Too much"})  # fmt: skip
    assert too_much.status == 422 and too_much.code == "DISCOUNT_LIMIT_EXCEEDED"
    mgr = c.as_(c.manager)
    est = ok(mgr.post(f"/api/v1/estimate-adjustments/{big['id']}/decision", {"decision": "APPROVE", "note": "ok"},
                      if_match=big["version"]))  # fmt: skip
    big = est["adjustments"][1]
    assert big["status"] == "APPROVED" and big["authority_code"] == "APPROVER" and big["decided_by"] == c.manager.id
    assert est["discount_minor"] == 100 + big["discount_minor"]
    assert est["taxable_minor"] == est["subtotal_minor"] - est["discount_minor"]
    # GST (SYNTHETIC single rate) on the discounted value, reconciled line by line
    taxed = [x for x in est["lines"] if x["rate_status"] == "PRICED" and not x["is_optional"]]
    assert est["tax_status"] == "APPLIED" and est["tax_minor"] == sum(x["tax_minor"] for x in taxed)
    assert all(x["taxable_minor"] == x["amount_minor"] - x["discount_minor"] for x in taxed)
    assert est["total_minor"] == est["taxable_minor"] + est["tax_minor"]
    # a discounted estimate is approved by someone other than its preparer
    prepared_by_manager = ok(_estimate(c, boq, user=c.manager), 201)
    ok(mgr.post(f"/api/v1/cost-estimates/{prepared_by_manager['id']}/adjustments",
                {"scope_code": "PROJECT", "kind_code": "AMOUNT", "amount_minor": 500, "reason": "Goodwill"}), 201)  # fmt: skip
    cur = ok(mgr.get(f"/api/v1/cost-estimates/{prepared_by_manager['id']}"))
    r = mgr.post(f"/api/v1/cost-estimates/{cur['id']}/approve", if_match=cur["version"])
    assert r.status == 409 and r.code == "FOUR_EYES_REQUIRED"
    ok(c.as_(c.second_manager).post(f"/api/v1/cost-estimates/{cur['id']}/approve", if_match=cur["version"]))
