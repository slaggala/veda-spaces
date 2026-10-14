"""CQX-09 terms and acknowledgements: sections as frozen, unapproved content never presented, acknowledgements bound
to the digest shown, per recipient, idempotent; warranty and Veda Spaces service support distinct.
SYNTHETIC only; SYNTHETIC_VALIDATED."""

from __future__ import annotations

import copy

import sqlalchemy as sa

from tests.support.commercial import SYNTHETIC_POLICY
from tests.support.proposal import INTERACTION_ON, customer, install_proposal_policy, ok, setup, share
from veda.kernel import db

pytestmark = INTERACTION_ON


def _section(page, code):
    return next(x for x in page["terms"]["sections"] if x["code"] == code)


def test_sections_are_frozen_text_and_unapproved_ones_are_not_presented(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    cust = customer(api, share(c, q))
    page = cust.get().data
    assert [x["code"] for x in page["terms"]["sections"]] == ["SCOPE", "ASSUMPTIONS", "EXCLUSIONS", "PAYMENT_MILESTONES",
                                                              "VALIDITY", "WARRANTY", "SERVICE_SUPPORT", "TERMS"]  # fmt: skip
    assert _section(page, "WARRANTY")["items"] == page["proposal"]["warranty"]
    support = _section(page, "SERVICE_SUPPORT")
    assert support["available"] is False and support["items"] == [] and support["sha256"] is None
    r = cust.post("/acknowledgements", {"section": "SERVICE_SUPPORT", "section_sha256": "0" * 64})
    assert r.status == 409 and r.code == "SECTION_NOT_AVAILABLE"
    # CQX-D03 undecided: nothing is "required", no action is pressed on the customer
    assert page["terms"]["policy_decided"] is False and page["terms"]["pending"] == []
    assert not any(a["code"] == "ACKNOWLEDGE_TERMS" for a in page["actions"])


def test_service_support_is_its_own_section_in_document_and_proposal(api, factory):
    terms = copy.deepcopy(SYNTHETIC_POLICY["decisions"]["OI-MTQ-09"])
    terms["service_support"] = ["Synthetic Veda Spaces service-support text for tests."]
    c, prop, est, q = setup(api, factory, "2BHK", OI_MTQ_09=terms)
    p = customer(api, share(c, q)).get().data["proposal"]
    assert p["service_support"] == terms["service_support"] and p["warranty"] == terms["warranty"]
    html = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document"))["html"]
    assert html.index("<h2>Warranty</h2>") < html.index("<h2>Service support (Veda Spaces)</h2>")


def test_acknowledgement_binds_the_digest_shown_and_is_idempotent_per_recipient(api, factory):
    install_proposal_policy()  # SYNTHETIC CQX-D03: SCOPE, PAYMENT_MILESTONES, WARRANTY, TERMS
    c, prop, est, q = setup(api, factory, "2BHK")
    primary = customer(api, share(c, q))
    co_owner = customer(api, share(c, q, kind="CO_OWNER"))
    page = primary.get().data
    assert page["terms"]["policy_decided"] is True
    assert page["terms"]["pending"] == ["SCOPE", "PAYMENT_MILESTONES", "WARRANTY", "TERMS"]
    assert any(a["code"] == "ACKNOWLEDGE_TERMS" for a in page["actions"])
    warranty = _section(page, "WARRANTY")
    r = primary.post("/acknowledgements", {"section": "WARRANTY", "section_sha256": "f" * 64})
    assert r.status == 409 and r.code == "PROPOSAL_CHANGED"
    r = primary.post("/acknowledgements", {"section": "WARRANTY", "section_sha256": warranty["sha256"]})
    assert r.status == 201 and _section(r.data, "WARRANTY")["acknowledged_on"]
    again = primary.post("/acknowledgements", {"section": "WARRANTY", "section_sha256": warranty["sha256"]})
    assert again.status == 201
    from veda.modules.customer_proposal.models import QuotationAcknowledgement

    with db.unit_of_work() as s:
        assert s.execute(sa.select(sa.func.count()).select_from(QuotationAcknowledgement)).scalar() == 1
    assert co_owner.get().data["terms"]["pending"] == ["SCOPE", "PAYMENT_MILESTONES", "WARRANTY", "TERMS"]  # their own
    for code in ("SCOPE", "PAYMENT_MILESTONES", "TERMS"):
        sec = _section(primary.get().data, code)
        assert primary.post("/acknowledgements", {"section": code, "section_sha256": sec["sha256"]}).status == 201
    page = primary.get().data
    assert page["terms"]["pending"] == [] and not any(a["code"] == "ACKNOWLEDGE_TERMS" for a in page["actions"])
    acks = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/customer-activity"))["acknowledgements"]
    assert {a["section"] for a in acks} == {"SCOPE", "PAYMENT_MILESTONES", "WARRANTY", "TERMS"}
    assert all(a["recipient_kind"] == "PRIMARY_CUSTOMER" and len(a["evidence_sha256"]) == 64 for a in acks)
