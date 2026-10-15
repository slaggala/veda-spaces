"""CQX-08 variation preview and version comparison: the accepted baseline beside the proposed variation (frozen,
digest-checked), chosen optional items kept and never counted twice, the cumulative position, the variation policy
gate; a revised version beside the one issued before it. SYNTHETIC only; SYNTHETIC_VALIDATED."""

from __future__ import annotations

import json
from decimal import Decimal

from tests.integration.test_mtq_variations import _changed_estimate
from tests.support.proposal import PROPOSAL_ON, customer, ok, setup, share, step
from veda.kernel import db
from veda.kernel.context import actor, system_context

pytestmark = PROPOSAL_ON


def _minor(text: str | None) -> int:
    return int(Decimal((text or "0").replace(",", "")) * 100)


def _accept_with_option(c, q):
    pick = next(x for sec in ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))["sections"] for x in sec["lines"]
                if x["is_optional"] and x["is_priced"])  # fmt: skip
    q = ok(step(c, q, "decision", c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY",
                                            "selected_optional_line_ids": [pick["id"]]}))  # fmt: skip
    return q, pick


def test_variation_preview_against_the_accepted_baseline_keeps_choices_once(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    q, pick = _accept_with_option(c, q)
    est2 = _changed_estimate(c, prop)
    v = ok(c.as_(c.sales).post(f"/api/v1/quotations/{q['id']}/variations", {"cost_estimate_id": est2["id"]}), 201)
    pv = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{v['id']}/variation-preview"))
    labels = {ch["change_label"] for ch in pv["changes"]}
    assert "Added" in labels and "Material changed" in labels
    assert pick["description"] in [k["description"] for k in pv["kept_choices"]]
    assert pick["description"] not in [ch["description"] for ch in pv["changes"] if ch["change"] == "ADD"]  # not twice
    assert sum(_minor(ch["delta"]) for ch in pv["changes"]) == _minor(pv["net_change"])
    assert _minor(pv["accepted_value"]) == q["decision"]["accepted_total_minor"]
    assert _minor(pv["value_if_accepted"]) == q["decision"]["accepted_total_minor"] + v["total_minor"]
    text = json.dumps(pv)
    for marker in ("rate_minor", "rate_card", "cost_estimate", "provenance", v["id"], q["id"], "line_key"):
        assert marker not in text, marker
    # issued and shared, the customer sees the same comparison
    step(c, v, "submit", c.sales)
    step(c, v, "approve", c.manager)
    v = ok(step(c, v, "issue", c.manager))
    page = customer(api, share(c, v)).get().data
    assert page["proposal"]["kind"] == "VARIATION" and page["variation"]["changes"] == pv["changes"]


def test_a_variation_is_not_issued_while_the_variation_policy_is_undecided(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK", OI_MTQ_13=None)
    q, _ = _accept_with_option(c, q)
    v = ok(c.as_(c.sales).post(f"/api/v1/quotations/{q['id']}/variations",
                               {"cost_estimate_id": _changed_estimate(c, prop)["id"]}), 201)  # fmt: skip
    pv = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{v['id']}/variation-preview"))
    assert pv["issuable"] is False  # staff-only preview
    step(c, v, "submit", c.sales)
    step(c, v, "approve", c.manager)
    r = step(c, v, "issue", c.manager, code=409)
    assert r.code == "NOT_CUSTOMER_ISSUABLE"
    assert share(c, v, code=409).code == "NOT_SHAREABLE"


def test_a_tampered_accepted_baseline_refuses_the_preview(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    q, _ = _accept_with_option(c, q)
    v = ok(c.as_(c.sales).post(f"/api/v1/quotations/{q['id']}/variations",
                               {"cost_estimate_id": _changed_estimate(c, prop)["id"]}), 201)  # fmt: skip
    from veda.modules.mtq_commercial.models import Quotation

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        row = s.get(Quotation, q["id"])
        row.accepted_baseline = [{**e, "taxable_minor": 1} for e in row.accepted_baseline]
    r = c.as_(c.estimator).get(f"/api/v1/quotations/{v['id']}/variation-preview")
    assert r.status == 409 and r.code == "SNAPSHOT_INTEGRITY_FAILED"


def test_a_revised_version_is_compared_with_the_one_issued_before(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    g1 = share(c, q)
    assert customer(api, g1).get("/comparison").data["comparison"] is None
    assert customer(api, g1).get().data["comparison_available"] is False
    est2 = _changed_estimate(c, prop)
    q2 = ok(step(c, q, "versions", c.estimator, {"cost_estimate_id": est2["id"]}, code=201))
    step(c, q2, "submit", c.estimator)
    step(c, q2, "approve", c.manager)
    q2 = ok(step(c, q2, "issue", c.manager))
    cust = customer(api, share(c, q2))
    assert cust.get().data["comparison_available"] is True
    cmp = cust.get("/comparison").data["comparison"]
    assert cmp["from_version"] == 1 and cmp["to_version"] == 2
    kinds = {ch["change"] for ch in cmp["changes"]}
    assert "ADDED" in kinds and ({"CHANGED", "REMOVED"} & kinds)
    assert cmp["total_before"] != cmp["total_after"]
    assert q["id"] not in json.dumps(cmp) and q2["id"] not in json.dumps(cmp)
