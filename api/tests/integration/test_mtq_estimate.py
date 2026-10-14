"""MTQ B3 pricing integration: estimates priced from the active rate card with full provenance.

SYNTHETIC: the rate card is the synthetic test card. No real rate is used or implied."""

from __future__ import annotations

from decimal import Decimal

from tests.support.commercial import ON, Commercial, load_card, ok
from veda.modules.estimator import engine

pytestmark = ON


def _estimate(c: Commercial, boq: dict, tier: str = "ESSENTIAL", user=None):
    return c.as_(user or c.estimator).post(f"/api/v1/boqs/{boq['id']}/cost-estimates", {"tier_code": tier})


def test_essential_estimate_has_provenance_and_explicit_blockers(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop, scope, boq = c.reviewed_boq("2BHK", optional="ACCEPTED")
    est = ok(_estimate(c, boq), 201)
    assert est["status"] == "DRAFT" and est["rate_card_version"] == "SYNTHETIC-2"
    assert est["boq_revision_no"] == boq["revision_no"] and est["scope_revision_no"] == scope["revision_no"]
    priced = [x for x in est["lines"] if x["rate_status"] == "PRICED" and x["boq_line_id"]]
    assert priced
    for x in priced:
        assert x["amount_minor"] == engine.line_amount_minor(Decimal(x["quantity_centi"]) / 100, x["rate_minor"])
        assert x["provenance"]["card_version"] == "SYNTHETIC-2" and x["provenance"]["boq_line_id"] == x["boq_line_id"]
        assert x["provenance"]["measurement_source"]["measurement_set_id"] == scope["measurement_set_id"]
    prep = [x for x in est["lines"] if x["prep_component_code"]]
    assert prep and all(x["rate_status"] == "PRICED" and x["provenance"]["home_size"] == "2BHK" for x in prep)
    assert {x["component_code"] for x in prep} <= {"SITE_PROTECTION", "TRANSPORT", "OTHER_SERVICE"}
    unmapped = [x for x in est["lines"] if x["rate_status"] == "CATALOGUE_MAPPING_MISSING"]
    assert unmapped and all(x["amount_minor"] is None for x in unmapped)
    codes = {b["code"]: b for b in est["blockers"]}
    assert codes["GST_POLICY_REQUIRED"]["decision"] == "OI-MTQ-07" and est["total_minor"] is None
    assert est["tax_status"] == "GST_POLICY_REQUIRED" and est["tax_minor"] is None
    assert "RULESET_NOT_APPROVED" in codes
    assert est["subtotal_minor"] == sum(x["amount_minor"] for x in est["lines"]
                                        if x["rate_status"] == "PRICED" and not x["is_optional"])  # fmt: skip
    assert est["taxable_minor"] == est["subtotal_minor"]
    views = est["views"]
    assert sum(r["amount_minor"] for r in views["rooms"]) == est["subtotal_minor"]
    assert sum(r["amount_minor"] for r in views["categories"]) == est["subtotal_minor"]
    # owner-decision blockers do not stop the internal approval; they stop customer issuance later
    mgr = c.as_(c.manager)
    approved = ok(mgr.post(f"/api/v1/cost-estimates/{est['id']}/approve", if_match=est["version"]))
    assert approved["status"] == "APPROVED" and len(approved["snapshot_sha256"]) == 64
    assert ok(mgr.get(f"/api/v1/cost-estimates/{est['id']}/reproduce"))["reproducible"] is True


def test_sales_sees_amounts_but_never_rates(api, factory):
    load_card()
    c = Commercial(api, factory)
    _, _, boq = c.reviewed_boq("2BHK")
    est = ok(_estimate(c, boq), 201)
    sales = ok(c.as_(c.sales).get(f"/api/v1/cost-estimates/{est['id']}"))
    assert sales["subtotal_minor"] == est["subtotal_minor"] and sales["rate_card_version"] is None
    assert all(x["rate_minor"] is None and x["provenance"] is None for x in sales["lines"])
    assert c.as_(c.sales).get(f"/api/v1/cost-estimates/{est['id']}/reproduce").status == 403
    assert c.as_(c.sales).post(f"/api/v1/cost-estimates/{est['id']}/approve", if_match=est["version"]).status == 403
    assert c.as_(c.designer).get(f"/api/v1/cost-estimates/{est['id']}").status == 403
