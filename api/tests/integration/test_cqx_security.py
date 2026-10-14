"""CQX-13 security and privacy: cross-customer isolation, enumeration and brute force, CORS and CSRF surface, response
headers, body limits, least-privilege staff permissions, and erasure of acceptance evidence. SYNTHETIC only."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support.proposal import FLAGS, INTERACTION_ON, PROPOSAL_ON, customer, ok, setup, share
from veda.kernel import db
from veda.kernel.context import actor, system_context


@INTERACTION_ON
def test_one_customer_never_reaches_another_customers_proposal(api, factory):
    c, prop_a, est_a, qa = setup(api, factory, "2BHK")
    from tests.support.proposal import issued

    prop_b, est_b, qb = issued(c, "3BHK")
    ga, gb = share(c, qa), share(c, qb)
    page_a, page_b = customer(api, ga).get().data, customer(api, gb).get().data
    assert page_a["proposal"]["quotation_number"] == qa["quotation_number"]
    assert page_b["proposal"]["quotation_number"] == qb["quotation_number"]
    assert qb["quotation_number"] not in str(page_a) and qa["quotation_number"] not in str(page_b)
    # a reference is only ever resolved inside the link's own version: B's optional line named with A's link is A's (or
    # nothing), never B's
    b_opt = next(x for x in page_b["proposal"]["optional_items"] if x["priced"])
    r = customer(api, ga).post("/selections", {"line_ref": b_opt["ref"], "state": "SELECTED"})
    with db.unit_of_work() as s:
        from veda.modules.customer_proposal.models import CustomerOptionalSelection

        rows = s.execute(sa.select(CustomerOptionalSelection)).scalars().all()
        assert all(row.quotation_id == qa["id"] for row in rows), r
    # nothing in the customer API accepts an identifier: the link is the only key
    assert api.get(f"/api/v1/public/proposal?quotation_id={qb['id']}", anonymous=True,
                   headers={"X-Veda-Proposal": ga["token"]}).status == 422  # fmt: skip


@pytest.mark.settings(**FLAGS, customer_proposal_enabled=True, rate_limits_enabled=True)
def test_guessing_links_is_rate_limited_per_address(api, factory):
    statuses = [api.get("/api/v1/public/proposal", anonymous=True, headers={"X-Veda-Proposal": f"vsp_{n:043d}"}).status
                for n in range(25)]  # fmt: skip
    assert statuses[:20] == [404] * 20 and 429 in statuses[20:]


@PROPOSAL_ON
def test_cors_csrf_surface_and_headers(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    g = share(c, q)
    evil = api.client.open("/api/v1/public/proposal", method="OPTIONS",
                           headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET",
                                    "Access-Control-Request-Headers": "X-Veda-Proposal"})  # fmt: skip
    assert "Access-Control-Allow-Origin" not in evil.headers  # a cross-site page cannot send the header
    good = api.client.open("/api/v1/public/proposal", method="OPTIONS",
                           headers={"Origin": api.APP_ORIGIN, "Access-Control-Request-Method": "GET",
                                    "Access-Control-Request-Headers": "X-Veda-Proposal"})  # fmt: skip
    assert good.headers.get("Access-Control-Allow-Origin") == api.APP_ORIGIN
    assert "X-Veda-Proposal" in good.headers.get("Access-Control-Allow-Headers", "")
    r = customer(api, g).get()
    assert r.headers["Cache-Control"].startswith("no-store") and r.headers["Pragma"] == "no-cache"
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["Referrer-Policy"] == "no-referrer"
    assert "noindex" in r.headers["X-Robots-Tag"] and "Set-Cookie" not in r.headers  # no ambient credential


@INTERACTION_ON
def test_oversized_and_unknown_bodies_are_refused(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    cust = customer(api, share(c, q))
    r = api.post("/api/v1/public/proposal/requests", raw_body=b"{" + b'"message": "' + b"x" * 20_000 + b'"}', anonymous=True,
                 headers={"X-Veda-Proposal": cust.token, "Idempotency-Key": "z" * 32})  # fmt: skip
    assert r.status in (413, 422)
    r = cust.post(
        "/requests", {"category": "GENERAL_QUESTION", "message": "Hello there", "quotation_id": q["id"]}, key="u" * 32
    )
    assert r.status == 422 and r.code in ("UNKNOWN_FIELD", "VALIDATION_FAILED")


def test_staff_permissions_are_least_privilege():
    from veda.modules.customer_proposal.permissions import MATRIX

    assert set(MATRIX) == {"proposal.preview", "proposal.share", "proposal.access.revoke", "proposal.request.review",
                           "proposal.acceptance.review"}  # fmt: skip
    for code, grants in MATRIX.items():
        assert "DESIGNER" not in grants and "SURVEYOR" not in grants, code  # site roles never see customer proposals
        assert grants.get("SALES") in (None, "O"), code  # sales only on their own leads
    assert "ESTIMATOR" not in MATRIX["proposal.share"] and "ESTIMATOR" not in MATRIX["proposal.access.revoke"]
    assert "ESTIMATOR" not in MATRIX["proposal.acceptance.review"]
    from veda.modules.mtq_commercial.permissions import MATRIX as COMMERCIAL

    # proposal permissions give no pricing: the rate and lineage codes stay exactly as they were
    assert "SALES" not in COMMERCIAL["cost_estimate.rate.view"] and "SALES" not in COMMERCIAL["quotation.lineage.read"]


@PROPOSAL_ON
def test_a_sales_user_on_another_lead_sees_nothing(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    g = share(c, q)
    stranger = factory.user("SALES")
    for method, path in (("GET", f"/api/v1/quotations/{q['id']}/access-grants"),
                         ("GET", f"/api/v1/quotations/{q['id']}/proposal-preview"),
                         ("POST", f"/api/v1/proposal-access-grants/{g['id']}/revoke")):  # fmt: skip
        r = c.as_(stranger).call(
            method, path, {} if method == "POST" else None, if_match=1 if method == "POST" else None
        )
        assert r.status == 404, (method, path, r)


@pytest.mark.settings(**FLAGS, customer_proposal_enabled=True, customer_proposal_interaction_enabled=True,
                      customer_quotation_acceptance_enabled=True)  # fmt: skip
def test_lead_erasure_removes_network_evidence_but_keeps_the_commercial_record(api, factory):
    from tests.integration.test_cqx_acceptance import _ack_required, _body, _ready

    c, prop, est, q, g, cust, picked = _ready(api, factory, choose=False,
                                              CQX_D04={"record_ip": True, "record_user_agent": True, "retention_days": 30})  # fmt: skip
    page = _ack_required(cust)
    assert cust.post("/decision", _body(page), key="e" * 32).status == 200
    from veda.modules.crm.leads import erasure as lead_erasure
    from veda.modules.crm.leads.models import Lead
    from veda.modules.customer_proposal.models import QuotationAcceptanceEvidence

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead_erasure.run(s, s.get(Lead, prop["lead_id"]))
    with db.unit_of_work() as s:
        ev = s.execute(sa.select(QuotationAcceptanceEvidence)).scalar_one()
        assert ev.network is None and ev.decision == "ACCEPTED" and len(ev.evidence_sha256) == 64
    assert ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))["status"] == "ACCEPTED"
