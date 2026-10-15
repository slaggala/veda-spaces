"""CQX-10 digital acceptance: fail closed on every undecided policy; version- and digest-bound; explicit choices;
required acknowledgements; idempotent; evidence; hand-off; the accepted baseline includes the chosen items and a later
variation never counts them twice. SYNTHETIC policies only (refused outside tests); SYNTHETIC_VALIDATED."""

from __future__ import annotations

import hashlib
from datetime import timedelta

import sqlalchemy as sa

from tests.integration.test_mtq_variations import _changed_estimate
from tests.support.proposal import (
    ACCEPTANCE_ON,
    customer,
    digital_acceptance_policy,
    install_proposal_policy,
    ok,
    setup,
    share,
    step,
)
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.kernel.jcs import canonical_bytes

pytestmark = ACCEPTANCE_ON


def _ack_required(cust) -> dict:
    page = cust.get().data
    for sec in page["terms"]["sections"]:
        if sec["required"] and not sec["acknowledged_on"]:
            assert (
                cust.post("/acknowledgements", {"section": sec["code"], "section_sha256": sec["sha256"]}).status == 201
            )
    return cust.get().data


def _body(page: dict, decision: str = "ACCEPTED", **over) -> dict:
    d = page["decision"]
    body = {"decision": decision, "version_no": page["proposal"]["version_no"],
            "snapshot_sha256": page["proposal"]["snapshot_sha256"], "displayed_total": d.get("total"),
            "selected_line_refs": d.get("selected_refs", []) if decision == "ACCEPTED" else [], "confirm": True}  # fmt: skip
    body.update(over)
    return body


def _ready(api, factory, key="2BHK", *, choose=True, **policy):
    c, prop, est, q = setup(
        api, factory, key, OI_MTQ_11={"methods": ["STAFF_RECORDED", "SIGNED_COPY", "CUSTOMER_DIGITAL"]}
    )
    install_proposal_policy(**policy)
    g = share(c, q)
    cust = customer(api, g)
    picked = None
    if choose:
        picked = next(x for x in cust.get().data["proposal"]["optional_items"] if x["priced"])
        assert cust.post("/selections", {"line_ref": picked["ref"], "state": "SELECTED"}).status == 200
    return c, prop, est, q, g, cust, picked


def test_acceptance_fails_closed_while_policies_are_undecided(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")  # SYNTHETIC commercial policy without CUSTOMER_DIGITAL; CQX all null
    cust = customer(api, share(c, q))
    page = cust.get().data
    assert page["capabilities"]["acceptance"] is True and page["decision"]["available"] is False
    assert "not available" in page["decision"]["reason"]
    assert not any(a["code"] == "DECIDE" for a in page["actions"])
    r = cust.post("/decision", _body(page, displayed_total=page["proposal"]["summary"]["total"]), key="a" * 32)
    assert r.status == 409 and r.code == "ACCEPTANCE_UNAVAILABLE"
    assert "OI-MTQ" not in str(r.json)  # owner-decision codes stay internal
    assert ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))["status"] == "ISSUED"
    ev = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/acceptance-evidence"))
    codes = {(b["code"], b["decision"]) for b in ev["blockers"]}
    assert ("METHOD_NOT_APPROVED", "OI-MTQ-11") in codes
    for d in ("CQX-D01", "CQX-D03", "CQX-D04"):
        assert ("OWNER_DECISION_REQUIRED", d) in codes
    assert ev["evidence"] is None


def test_digital_acceptance_records_evidence_baseline_and_hand_off(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory, "3BHK")
    page = cust.get().data
    assert page["decision"]["available"] is False and "acknowledge" in page["decision"]["reason"]
    page = _ack_required(cust)
    d = page["decision"]
    assert d["available"] is True and d["selected_refs"] == [picked["ref"]] and d["total"]
    assert any(a["code"] == "DECIDE" for a in page["actions"])
    lead_before = ok(c.as_(c.sales).get(f"/api/v1/leads/{prop['lead_id']}"))["status"]
    r = cust.post("/decision", _body(page), key="k" * 32)
    assert r.status == 200 and r.data["state"] == "ACCEPTED" and r.data["decision"]["decided"] == "ACCEPTED"
    qa = ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))
    assert qa["status"] == "ACCEPTED" and qa["decision"]["method"] == "CUSTOMER_DIGITAL"
    assert qa["snapshot_sha256"] == q["snapshot_sha256"] and qa["total_minor"] == q["total_minor"]  # frozen, unchanged
    from veda.modules.customer_proposal import selections
    from veda.modules.mtq_commercial.models import Quotation

    with db.unit_of_work() as s:
        row = s.get(Quotation, q["id"])
        chosen = [e for e in row.accepted_baseline if e["selected_optional"]]
        assert [e["label"] for e in chosen] == [picked["description"]]  # the choice is in the accepted baseline
        assert selections.money(row.accepted_total_minor) == d["total"]
    ev = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/acceptance-evidence"))["evidence"]
    assert (
        ev["evidence_verified"] is True and ev["decision"] == "ACCEPTED" and ev["recipient_kind"] == "PRIMARY_CUSTOMER"
    )
    assert ev["selected_line_refs"] == [picked["ref"]] and ev["displayed_total"] == d["total"]
    assert {a["section"] for a in ev["acknowledgements"]} == {"SCOPE", "PAYMENT_MILESTONES", "WARRANTY", "TERMS"}
    assert ev["network"] is None  # CQX-D04 (synthetic) records neither address nor device
    assert ev["evidence"]["snapshot_sha256"] == q["snapshot_sha256"] and ev["evidence"]["version_no"] == 1
    assert hashlib.sha256(canonical_bytes(ev["evidence"])).hexdigest() == ev["evidence_sha256"]
    lead = ok(c.as_(c.sales).get(f"/api/v1/leads/{prop['lead_id']}"))
    assert lead["status"] == lead_before  # the lead's status is staff's to change, as with B4 acceptance
    from veda.modules.crm.leads.models import LeadActivity
    from veda.platform.notifications.models import OutboxEvent

    with db.unit_of_work() as s:
        acts = s.execute(sa.select(LeadActivity).where(LeadActivity.lead_id == prop["lead_id"])).scalars().all()
        assert any("accepted by the customer (digital)" in a.subject for a in acts)
        assert "quotation.accepted" in [o.event_type for o in s.execute(sa.select(OutboxEvent)).scalars()]
    # the accepted proposal is shown as accepted, with nothing left to do
    page = cust.get().data
    assert page["state"] == "ACCEPTED" and page["capabilities"] == {"interaction": False, "acceptance": False}
    assert page["decision"]["by_this_link"] is True


def test_duplicate_acceptance_is_idempotent_and_a_conflicting_one_is_refused(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory)
    page = _ack_required(cust)
    first = cust.post("/decision", _body(page), key="k" * 32)
    again = cust.post("/decision", _body(page), key="k" * 32)  # a retry
    other_key = cust.post("/decision", _body(page), key="m" * 32)  # a second identical acceptance
    assert first.status == again.status == other_key.status == 200
    assert first.data["decision"] == again.data["decision"] == other_key.data["decision"]
    r = cust.post("/decision", _body(page, decision="DECLINED"), key="n" * 32)
    assert r.status == 409 and r.code == "ALREADY_DECIDED"
    from veda.modules.customer_proposal.models import QuotationAcceptanceEvidence

    with db.unit_of_work() as s:
        assert s.execute(sa.select(sa.func.count()).select_from(QuotationAcceptanceEvidence)).scalar() == 1


def test_acceptance_is_bound_to_this_version_its_digest_its_choices_and_the_total_shown(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory)
    page = _ack_required(cust)
    for over, code in (({"version_no": 2}, "VERSION_MISMATCH"), ({"snapshot_sha256": "0" * 64}, "PROPOSAL_CHANGED"),
                       ({"selected_line_refs": []}, "SELECTION_MISMATCH"), ({"displayed_total": "1.00"}, "TOTAL_MISMATCH")):  # fmt: skip
        r = cust.post("/decision", _body(page, **over), key="x" * 32)
        assert r.status == 409 and r.code == code, (over, r)
    assert cust.post("/decision", {**_body(page), "confirm": False}, key="y" * 32).status == 422
    assert cust.post("/decision", _body(page)).status == 422  # Idempotency-Key required
    assert ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))["status"] == "ISSUED"


def test_tampered_superseded_expired_and_revoked_proposals_are_never_accepted(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory, choose=False)
    page = _ack_required(cust)
    from veda.modules.mtq_commercial.models import Quotation

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        row = s.get(Quotation, q["id"])
        good = row.snapshot
        row.snapshot = {**row.snapshot, "subject": "Something else"}
    r = cust.post("/decision", _body(page), key="t" * 32)
    assert r.status == 409 and r.code == "SNAPSHOT_INTEGRITY_FAILED"
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        s.get(Quotation, q["id"]).snapshot = good
        s.get(Quotation, q["id"]).valid_until = clock.now().date() - timedelta(days=1)
    r = cust.post("/decision", _body(page), key="u" * 32)
    assert r.status == 409 and r.code == "ACCEPTANCE_UNAVAILABLE"
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        s.get(Quotation, q["id"]).valid_until = clock.now().date() + timedelta(days=5)
    q2 = ok(step(c, q, "versions", c.estimator, {"cost_estimate_id": est["id"]}, code=201))
    step(c, q2, "submit", c.estimator)
    step(c, q2, "approve", c.manager)
    step(c, q2, "issue", c.manager)
    r = cust.post("/decision", _body(page), key="v" * 32)  # v1 is superseded by an issued v2
    assert r.status == 409 and r.code == "ACCEPTANCE_UNAVAILABLE"
    assert ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))["status"] == "SUPERSEDED"
    g2 = share(c, q2)
    cust2 = customer(api, g2)
    cur = next(x for x in ok(c.as_(c.sales).get(f"/api/v1/quotations/{q2['id']}/access-grants")) if x["id"] == g2["id"])
    ok(c.as_(c.sales).post(f"/api/v1/proposal-access-grants/{g2['id']}/revoke", if_match=cur["version"]))
    r = cust2.post("/decision", _body(page, version_no=2), key="w" * 32)
    assert r.status == 410 and r.code == "PROPOSAL_LINK_REVOKED"


def test_choices_without_a_shown_price_block_acceptance(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory, CQX_D02={"live_total": False})
    page = _ack_required(cust)
    assert page["decision"]["available"] is False and "confirm the price" in page["decision"]["reason"]
    cust.post("/selections", {"line_ref": picked["ref"], "state": "DESELECTED"})
    page = cust.get().data
    assert page["decision"]["available"] is True and page["decision"]["total"] == page["proposal"]["summary"]["total"]


def test_decline_needs_no_acknowledgement_and_network_evidence_follows_policy(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory, choose=False,
                                              CQX_D04={"record_ip": True, "record_user_agent": True, "retention_days": 30})  # fmt: skip
    page = cust.get().data
    assert page["decision"]["can_decline"] is True
    r = cust.post("/decision", _body(page, decision="DECLINED", displayed_total=None), key="d" * 32)
    assert r.status == 200 and r.data["decision"]["decided"] == "DECLINED"
    qa = ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))
    assert qa["status"] == "REJECTED" and qa["decision"]["method"] == "CUSTOMER_DIGITAL"
    ev = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/acceptance-evidence"))["evidence"]
    assert set(ev["network"]) <= {"ip", "user_agent"} and ev["evidence"]["network_recorded"] == sorted(ev["network"])


def test_variation_after_digital_acceptance_never_counts_the_chosen_option_twice(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory)
    page = _ack_required(cust)
    assert cust.post("/decision", _body(page), key="k" * 32).status == 200
    v = ok(c.as_(c.sales).post(f"/api/v1/quotations/{q['id']}/variations",
                               {"cost_estimate_id": _changed_estimate(c, prop)["id"]}), 201)  # fmt: skip
    lines = [x for sec in v["sections"] for x in sec["lines"]]
    assert not any(x["change_code"] == "ADD" and x["description"] == picked["description"] for x in lines)
    pv = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{v['id']}/variation-preview"))
    assert picked["description"] in [k["description"] for k in pv["kept_choices"]]


def test_digital_acceptance_policy_helper_is_synthetic_only():
    import pytest

    from veda.modules.customer_proposal import policy

    doc = {"schema": "veda.customer-proposal-policy/1", "version": "X", "status": "APPROVED", "note": "n",
           "decisions": {"CQX-D01": None, "CQX-D02": None, "CQX-D03": None, "CQX-D04": None}}  # fmt: skip
    with pytest.raises(RuntimeError):
        policy.install_for_tests(doc)  # only SYNTHETIC_TEST_ONLY documents may be installed
    assert digital_acceptance_policy is not None
