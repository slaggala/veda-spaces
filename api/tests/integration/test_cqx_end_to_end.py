"""CQX-14 synthetic end-to-end validation: the twenty scenarios of the instruction, for 2 BHK, 3 BHK, 4 BHK, 5 BHK and
an independent house, through the real API (B1 measurement → B2 scope and BOQ → B3 estimate → B4 quotation → CQX).

SYNTHETIC sites, rate card and owner policies only (the policies are refused outside tests). Results are
SYNTHETIC_VALIDATED; nothing here says anything about real customers or conversion.

Scenarios (numbered as in the instruction): 1 view, 2 room-by-room scope, 3 specifications and media, 4 select an optional
item, 5 deselect it, 6 question, 7 change request, 8 staff turn the request into a revision, 9 the customer views the
revised version, 10 superseded link, 11 expired link, 12 revoked link, 13 unauthorised access, 14 cross-customer attempt,
15 tampered frozen document, 16 duplicate acceptance, 17 acceptance of the wrong version, 18 the chosen optional item in
the accepted baseline, 19 a variation does not count it twice, 20 production refusal.
"""

from __future__ import annotations

import copy
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.integration.test_cqx_acceptance import _ack_required, _body
from tests.integration.test_estimator_spec import SPEC_DOC, load_spec
from tests.support.proposal import ACCEPTANCE_ON, customer, install_proposal_policy, issued, ok, setup, share, step
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context

pytestmark = ACCEPTANCE_ON
DIGITAL = {"methods": ["STAFF_RECORDED", "SIGNED_COPY", "CUSTOMER_DIGITAL"]}


def _grant_row(c, q, g):
    return next(x for x in ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/access-grants")) if x["id"] == g["id"])


def _issue(c, q):
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    return ok(step(c, q, "issue", c.manager))


@pytest.mark.parametrize("key", ["2BHK", "3BHK", "4BHK", "5BHK", "IH"])
def test_customer_quotation_journey(api, factory, key):
    load_spec(copy.deepcopy(SPEC_DOC))
    c, prop, est, q1 = setup(api, factory, key, OI_MTQ_11=DIGITAL)
    install_proposal_policy()  # SYNTHETIC CQX-D01..D04
    g1 = share(c, q1)
    cust = customer(api, g1)

    # 1 view, 2 rooms, 3 specifications and media
    page = cust.get().data
    assert page["state"] == "OPEN" and page["proposal"]["version_no"] == 1
    rooms = [r for r in page["proposal"]["rooms"] if r["kind"] == "ROOM"]
    assert rooms and all(r["lines"] for r in page["proposal"]["rooms"])
    assert page["specifications"] is not None and page["specifications"]["lines"]
    assert page["media"]["lines"] == {}  # catalogue media is not served here: placeholders, never an unchecked image

    # 4 select, 5 deselect
    option = next(x for x in page["proposal"]["optional_items"] if x["priced"])
    assert cust.post("/selections", {"line_ref": option["ref"], "state": "SELECTED"}).data["selected_refs"] == [
        option["ref"]
    ]
    assert cust.post("/selections", {"line_ref": option["ref"], "state": "DESELECTED"}).data["selected_refs"] == []

    # 6 question, 7 change request
    line = rooms[0]["lines"][0]
    assert cust.post("/requests", {"category": "LINE_QUESTION", "line_ref": line["ref"],
                                   "message": "What is the shutter thickness?"}, key="q" * 32).status == 201  # fmt: skip
    r = cust.post("/requests", {"category": "CHANGE_FINISH", "line_ref": line["ref"], "message": "Acrylic instead, please"},
                  key="c" * 32)  # fmt: skip
    assert r.status == 201 and len(r.data) == 2

    # 8 staff turn the change request into a revision (version 2), issue and share it
    q2 = ok(step(c, q1, "versions", c.estimator, {"cost_estimate_id": est["id"]}, code=201))
    req = next(x for x in ok(c.as_(c.estimator).get(f"/api/v1/quotations/{q1['id']}/customer-activity"))["requests"]
               if x["category"] == "CHANGE_FINISH")  # fmt: skip
    ok(c.as_(c.estimator).post(f"/api/v1/customer-requests/{req['id']}/link",
                               {"resulting_quotation_id": q2["id"], "response": "See version 2."}, if_match=req["version"]))  # fmt: skip
    q2 = _issue(c, q2)
    g2 = share(c, q2)
    cust2 = customer(api, g2)

    # 9 the customer views the revised version, compares it, and sees what answered the request
    page2 = cust2.get().data
    assert page2["proposal"]["version_no"] == 2 and page2["history"][0]["version_no"] == 1
    assert cust2.get("/comparison").data["comparison"]["from_version"] == 1
    assert any(i["answered_by_revision"] == "Version 2" for i in page2["requests"]["items"])

    # 10 the superseded link
    r = cust.get()
    assert r.status == 410 and r.code == "PROPOSAL_SUPERSEDED"

    # 11 an expired link (a CO_OWNER link past its own expiry), 12 a revoked link
    g_exp = share(c, q2, kind="CO_OWNER")
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        from veda.modules.customer_proposal.models import ProposalAccessGrant

        s.get(ProposalAccessGrant, g_exp["id"]).expires_on = clock.now() - timedelta(minutes=1)
    assert customer(api, g_exp).get().code == "PROPOSAL_LINK_EXPIRED"
    g_rev = share(c, q2, kind="FAMILY_MEMBER")
    ok(
        c.as_(c.sales).post(
            f"/api/v1/proposal-access-grants/{g_rev['id']}/revoke", if_match=_grant_row(c, q2, g_rev)["version"]
        )
    )
    assert customer(api, g_rev).get().code == "PROPOSAL_LINK_REVOKED"

    # 13 unauthorised access: no link, a guessed link, a staff session
    assert api.get("/api/v1/public/proposal", anonymous=True).code == "PROPOSAL_LINK_INVALID"
    assert (
        api.get("/api/v1/public/proposal", anonymous=True, headers={"X-Veda-Proposal": "vsp_" + "x" * 43}).status == 404
    )
    c.as_(c.founder)
    assert api.get("/api/v1/public/proposal").status == 404

    # 14 cross-customer: another lead's link shows only that lead's proposal; references never cross
    _p, _e, other = issued(c, "2BHK")
    other_page = customer(api, share(c, other)).get().data
    assert other_page["proposal"]["quotation_number"] != q2["quotation_number"]
    assert q2["quotation_number"] not in str(other_page)

    # 15 a tampered frozen document is never shown or accepted (restored afterwards)
    from veda.modules.mtq_commercial.models import Quotation

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        row = s.get(Quotation, q2["id"])
        good = row.snapshot
        row.snapshot = {**good, "summary": {**good["summary"], "total": "1.00"}}
    assert cust2.get().code == "SNAPSHOT_INTEGRITY_FAILED"
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        s.get(Quotation, q2["id"]).snapshot = good

    # 17 acceptance of the wrong version is refused; 16 a duplicate acceptance is idempotent
    assert cust2.post("/selections", {"line_ref": option["ref"], "state": "SELECTED"}).status == 200
    page2 = _ack_required(cust2)
    assert page2["decision"]["available"] is True
    r = cust2.post("/decision", _body(page2, version_no=1), key="w" * 32)
    assert r.status == 409 and r.code == "VERSION_MISMATCH"
    first = cust2.post("/decision", _body(page2), key="a" * 32)
    again = cust2.post("/decision", _body(page2), key="a" * 32)
    assert first.status == again.status == 200 and first.data["decision"] == again.data["decision"]
    from veda.modules.customer_proposal.models import QuotationAcceptanceEvidence

    with db.unit_of_work() as s:
        assert s.execute(sa.select(sa.func.count()).select_from(QuotationAcceptanceEvidence)).scalar() == 1
        # 18 the chosen optional item is part of the effective accepted baseline
        accepted = s.get(Quotation, q2["id"])
        assert accepted.status == "ACCEPTED" and accepted.decision_method == "CUSTOMER_DIGITAL"
        assert [e["label"] for e in accepted.accepted_baseline if e["selected_optional"]] == [option["description"]]

    # 19 a variation keeps the chosen item once (B4 compares by line key): never added a second time
    from tests.integration.test_mtq_variations import _changed_estimate

    try:
        est3 = _changed_estimate(c, prop)
    except (AssertionError, StopIteration, KeyError):
        pytest.skip(f"{key}: the change helper's rooms (Bedroom 2, Master bedroom) are not in this template")
    v = ok(c.as_(c.sales).post(f"/api/v1/quotations/{q2['id']}/variations", {"cost_estimate_id": est3["id"]}), 201)
    lines = [x for sec in v["sections"] for x in sec["lines"]]
    assert not any(x["change_code"] == "ADD" and x["description"] == option["description"] for x in lines)
    preview = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{v['id']}/variation-preview"))
    assert option["description"] in [k["description"] for k in preview["kept_choices"]]


def test_production_refuses_every_customer_proposal_flag(monkeypatch):
    """20: production refuses viewing, interaction and acceptance (and the API does not start with them)."""
    from tests.unit.test_config_environments import deployed_env
    from veda import config

    mtq = {"VEDA_MTQ_SITE_ENABLED": "true", "VEDA_MTQ_ESTIMATION_ENABLED": "true", "VEDA_MTQ_QUOTATION_ENABLED": "true"}
    for flag in ("VEDA_CUSTOMER_PROPOSAL_ENABLED", "VEDA_CUSTOMER_PROPOSAL_INTERACTION_ENABLED",
                 "VEDA_CUSTOMER_QUOTATION_ACCEPTANCE_ENABLED"):  # fmt: skip
        problems = config.validate_environment(deployed_env(monkeypatch, "production", **mtq, **{flag: "true"}))
        assert f"{flag} is not authorised in production (customer quotation experience)" in problems
