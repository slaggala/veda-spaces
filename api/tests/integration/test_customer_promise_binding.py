"""Customer Promise and quotations (CPA-23, CPA-24, CPA-35): OI-MTQ-18 decides the source; a quotation freezes the
published pack in force; a newer publication blocks issuing an older draft; an issued quotation never changes.

Business user authors → reviewers review → approver approves → publisher publishes → a new quotation freezes it → the
customer proposal shows it → a later publication leaves the first quotation exactly as issued.

SYNTHETIC sites, card, policies, personas and content only. SYNTHETIC_VALIDATED.
"""

from __future__ import annotations

import copy

import pytest

from tests.support.commercial import Commercial, approved_estimate, install_full_policy, load_card, step
from tests.support.promise import AUTHORITY, BASE, SECTION_VALUES, Team, ok
from tests.support.proposal import FLAGS, SYNTHETIC_PACK, SYNTHETIC_PREP, customer, share
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.customer_promise import binding
from veda.modules.customer_promise.models import CustomerPromisePack

pytestmark = pytest.mark.settings(**FLAGS, customer_proposal_enabled=True, customer_promise_admin_enabled=True)


def _quote(c: Commercial, key: str) -> dict:
    _, est = approved_estimate(c, key)
    q = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    q["cost_estimate_id"] = est["id"]
    return q


def _choose_contact(c: Commercial, q: dict) -> None:
    cur = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{q['id']}"))
    ok(c.as_(c.estimator).patch(f"/api/v1/quotations/{q['id']}", {"customer_information": {
        "contact_code": "SYN_QUOTE_DESK"}}, if_match=cur["version"]))  # fmt: skip


def _issue(c: Commercial, q: dict, code: int = 200):
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    return step(c, q, "issue", c.manager, code=code)


def _v2(team: Team, p: dict) -> dict:
    """The four changes of the E2E scenario: support contact, a readiness statement, a warranty exclusion, a stage."""
    contacts = copy.deepcopy(SECTION_VALUES["CONTACTS"])
    contacts["contacts"][1]["display_name"] = "SYNTHETIC Support Desk v2"
    p = team.save(p, "CONTACTS", contacts)
    readiness = copy.deepcopy(SECTION_VALUES["SITE_READINESS"])
    readiness["site_readiness"][0]["text"] = "SYNTHETIC v2: flooring finished and cured."
    p = team.save(p, "SITE_READINESS", readiness)
    p = team.save(p, "EXCLUSIONS", {"warranty_exclusions": [*SECTION_VALUES["EXCLUSIONS"]["warranty_exclusions"],
                                                              {"code": "SYN_WATER", "text": "SYNTHETIC v2: water damage."}]})  # fmt: skip
    steps = copy.deepcopy(SECTION_VALUES["NEXT_STEPS"])
    steps["next_steps"][1]["label"] = "SYNTHETIC v2 confirmation"
    return team.save(p, "NEXT_STEPS", steps)


def test_q1_keeps_v1_forever_and_q2_carries_v2(api, factory):
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP, OI_MTQ_18=AUTHORITY)
    load_card()
    c, t = Commercial(api, factory), Team(api, factory)
    page = ok(t.as_(t.viewer).get(BASE))
    assert page["authority"]["state"] == "DELEGATED_TO_CUSTOMER_PROMISE"
    assert all(a["customer_sees"] == "TO_BE_CONFIRMED" for a in page["areas"] if a["section"])  # nothing published

    v1 = t.publish_new(change_summary="SYNTHETIC v1")
    page = ok(t.as_(t.viewer).get(BASE))
    assert all(a["owner_approved_content"] for a in page["areas"] if a["section"])

    # Q1, drafted and issued under v1
    q1 = _quote(c, "2BHK")
    _choose_contact(c, q1)
    q1 = ok(_issue(c, q1))
    doc1 = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q1['id']}/document"))
    assert doc1["document"]["customer_information"]["content_version"] == "CPP-1"
    g1 = share(c, q1)
    seen1 = customer(api, g1).get().data["proposal"]
    assert seen1["information"]["content_version"] == "CPP-1"
    assert [x["display_name"] for x in seen1["information"]["contacts"]["support"]] == ["SYNTHETIC Support"]
    assert seen1["information"]["contacts"]["quotation"]["display_name"] == "SYNTHETIC Quotation Desk"

    # a draft under v1 that is not issued before v2 is published
    qx = _quote(c, "3BHK")
    _choose_contact(c, qx)

    v2 = t.publish_new(mutate=_v2, change_summary="SYNTHETIC v2")
    assert ok(t.as_(t.viewer).get(f"{BASE}/versions/{v1['id']}"))["status"] == "SUPERSEDED"
    history = {h["version_no"]: h for h in ok(t.as_(t.viewer).get(f"{BASE}/versions"))}
    assert history[1]["quotations"] == {"ISSUED": 1, "DRAFT": 1} and history[2]["quotations"] == {}

    # the v1 draft cannot be issued any more: it must take the current pack
    refused = _issue(c, qx, code=409)
    assert "CUSTOMER_PROMISE_SUPERSEDED" in [b["code"] for b in refused.json["blockers"]]
    cur = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{qx['id']}"))
    q2 = ok(c.as_(c.estimator).post(f"/api/v1/quotations/{qx['id']}/versions",
                                    {"cost_estimate_id": qx["cost_estimate_id"]}, if_match=cur["version"]), 201)  # fmt: skip
    assert q2["customer_inputs"]["contact_code"] == "SYN_QUOTE_DESK"  # staff's choice carried over
    q2 = ok(_issue(c, q2))
    doc2 = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q2['id']}/document"))
    info2 = doc2["document"]["customer_information"]
    assert info2["content_version"] == "CPP-2"
    assert [x["display_name"] for x in info2["contacts"]["support"]] == ["SYNTHETIC Support Desk v2"]
    assert info2["site_readiness"][0]["text"] == "SYNTHETIC v2: flooring finished and cured."
    assert [x["code"] for x in info2["warranty_exclusions"]] == ["SYN_MISUSE", "SYN_WATER"]
    assert info2["next_steps"][1]["label"] == "SYNTHETIC v2 confirmation"
    seen2 = customer(api, share(c, q2)).get().data["proposal"]
    assert seen2["information"]["content_version"] == "CPP-2"

    # Q1 is exactly as issued: document, HTML and the customer's page
    again = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q1['id']}/document"))
    assert again["html"] == doc1["html"] and again["document"] == doc1["document"]
    assert customer(api, g1).get().data["proposal"] == seen1
    history = {h["version_no"]: h for h in ok(t.as_(t.viewer).get(f"{BASE}/versions"))}
    assert history[1]["quotations"]["ISSUED"] == 1 and history[2]["quotations"] == {"ISSUED": 1}

    # the staff preview of v2 is what Q2's customer sees, section for section
    pv = ok(t.as_(t.author).get(f"{BASE}/versions/{v2['id']}/preview"))
    assert pv["label"] == "PUBLISHED"
    for key in ("support_escalation", "project_inclusions", "site_readiness", "warranty_exclusions", "next_steps",
                "payment_safety", "manufacturer_warranty_note", "care", "handover"):  # fmt: skip
        if key == "site_readiness":
            assert [x["text"] for x in pv["information"][key]] == [x["text"] for x in seen2["information"][key]]
        else:
            assert pv["information"][key] == seen2["information"][key], key


def test_without_the_delegation_a_published_pack_reaches_no_quotation(api, factory):
    """OI-MTQ-18 not recorded, or recorded as a pack: publishing here does not change what quotations carry."""
    t = Team(api, factory)
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP)
    t.publish_new()
    with actor(system_context("CLI")), db.unit_of_work(write=False) as s:
        assert binding.for_quotation(s) == (None, None)
        assert binding.stale_blocker(s, {}) is None
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP, OI_MTQ_18=SYNTHETIC_PACK)
    with actor(system_context("CLI")), db.unit_of_work(write=False) as s:
        pack, ref = binding.for_quotation(s)
        assert pack["content_version"] == "SYN-C1" and ref is None
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP, OI_MTQ_18=AUTHORITY)
    with actor(system_context("CLI")), db.unit_of_work(write=False) as s:
        pack, ref = binding.for_quotation(s)
        assert pack["content_version"] == "CPP-1" and ref["version_no"] == 1
        assert ref["register_reference"] == AUTHORITY["register_reference"]


def test_a_draft_or_approved_pack_never_satisfies_the_decision(api, factory):
    t = Team(api, factory)
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP, OI_MTQ_18=AUTHORITY)
    p = t.full_draft()
    t.act(p, "submit", t.author)
    t.review_all(p)
    t.act(p, "approve", t.approver)
    with actor(system_context("CLI")), db.unit_of_work(write=False) as s:
        assert binding.for_quotation(s) == (None, None)


def test_a_tampered_published_pack_is_refused(api, factory):
    t = Team(api, factory)
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP, OI_MTQ_18=AUTHORITY)
    v = t.publish_new()
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        row = s.get(CustomerPromisePack, v["id"])
        row.published_content = {**row.published_content, "payment_safety": "SYNTHETIC tampered."}
    from veda.kernel.errors import ApiError

    with actor(system_context("CLI")), db.unit_of_work(write=False) as s, pytest.raises(ApiError) as err:
        binding.for_quotation(s)
    assert err.value.code == "CUSTOMER_PROMISE_INTEGRITY_FAILED"
