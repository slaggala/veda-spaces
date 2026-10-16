"""Regression tests for the independent implementation review of PEX (record §Independent review): M1 a snag a customer
reported is never hidden from them; M2 no report accepted against a closed snag; M3 every branch of the commercial
condition (PEX-D02); L1 no work in the terminal stage; L2 the only identifiers a customer's delivery view carries are
their project's and package's; L3 an unchanged package preparation answers 200. SYNTHETIC data only, both engines."""

from __future__ import annotations

import json

import pytest

from tests.support.commercial import ok
from tests.support.commercials import Commercials, install_policy
from tests.support.portal import Portal
from tests.support.project import BASE, Projects, advance_to, delivery, install, no_four_eyes

FLAGS = dict(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True, customer_portal_enabled=True,
             project_lifecycle_enabled=True)  # fmt: skip
pytestmark = pytest.mark.settings(**FLAGS)


@pytest.fixture
def policy(app):
    install(no_four_eyes())
    yield
    install(None)


def _booked(t: Projects) -> dict:
    prop, _, q = t.accepted()
    p = t.book(q, prop)
    t.staff(p)
    return t.get(p)


def test_m1_a_snag_linked_to_a_customer_report_cannot_be_hidden(api, factory, policy):
    t = Projects(api, factory)
    p = advance_to(t, _booked(t), "SNAGGING")
    sn = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/snags", {"category": "FINISH", "customer_title": "Door rubs the floor"}),
            201)["snags"][-1]  # fmt: skip
    rep = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/customer-reports", {"description": "The bedroom door rubs the floor"}),
             201)["customer_reports"][-1]  # fmt: skip
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/customer-reports/{rep['id']}/triage",
                         {"outcome": "EXISTING_SNAG", "snag_id": sn["id"]}, if_match=rep["version"]))  # fmt: skip
    cur = next(x for x in t.get(p)["snags"] if x["id"] == sn["id"])
    assert cur["customer_visible"] is True and cur["source"] == "STAFF"
    r = t.as_(t.ops).patch(f"{BASE}/{p['id']}/snags/{sn['id']}", {"customer_visible": False}, if_match=cur["version"])
    assert r.status == 409 and r.code == "CUSTOMER_REPORTED"


def test_m2_a_report_is_never_accepted_against_a_closed_snag(api, factory, policy):
    t = Projects(api, factory)
    p = advance_to(t, _booked(t), "SNAGGING")
    sn = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/snags", {"category": "FINISH", "customer_title": "Duplicate entry"}),
            201)["snags"][-1]  # fmt: skip
    ok(t.as_(t.quality).post(f"{BASE}/{p['id']}/snags/{sn['id']}/status", {"status": "CLOSED", "closure_code": "DUPLICATE",
                                                                         "note": "Logged twice"}, if_match=sn["version"]))  # fmt: skip
    rep = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/customer-reports", {"description": "The skirting has a chip near the door"}),
             201)["customer_reports"][-1]  # fmt: skip
    r = t.as_(t.ops).post(f"{BASE}/{p['id']}/customer-reports/{rep['id']}/triage",
                          {"outcome": "EXISTING_SNAG", "snag_id": sn["id"]}, if_match=rep["version"])  # fmt: skip
    assert r.status == 409 and r.code == "SNAG_CLOSED"
    assert t.get(p)["customer_reports"][-1]["status"] == "SUBMITTED"


def test_l1_no_work_is_added_to_the_terminal_stage(api, factory, policy):
    t = Projects(api, factory)
    p = _booked(t)
    r = t.as_(t.ops).post(f"{BASE}/{p['id']}/work-packages", {"stage_code": "HANDED_OVER", "title": "After handover"})
    assert r.status == 422 and r.json["errors"][0]["code"] == "TERMINAL_STAGE"


def test_l3_an_unchanged_package_preparation_answers_200_with_the_same_package(api, factory, policy):
    t = Projects(api, factory)
    p = advance_to(t, _booked(t), "READY_FOR_HANDOVER")
    t.checklist(p)
    first = t.as_(t.ops).post(f"{BASE}/{p['id']}/handover-package", {}, if_match=t.get(p)["version"])
    again = t.as_(t.ops).post(f"{BASE}/{p['id']}/handover-package", {}, if_match=t.get(p)["version"])
    assert (first.status, again.status) == (201, 200)
    assert [x["id"] for x in again.data["handover_packages"]] == [first.data["handover_packages"][0]["id"]]


@pytest.mark.settings(**FLAGS, project_delivery_portal_enabled=True)
def test_l2_the_delivery_view_carries_only_the_customers_own_project_and_package_ids(api, factory, policy):
    t = Portal(api, factory)
    prop, _, q = t.accepted()
    p = t.book(q, prop)
    t.staff(p)
    p = advance_to(t, t.get(p), "READY_FOR_HANDOVER")
    t.checklist(p)
    pkg = t.package(p)["handover_packages"][-1]
    me = t.invite(prop["lead_id"], "ids@example.test")
    view = ok(me.property(prop["id"]))
    d = view["delivery"]["projects"][0]
    assert d["id"] == p["id"] and d["package"]["id"] == pkg["id"]  # what the two customer writes are addressed to
    text = json.dumps(d)
    detail = t.get(p)
    internal = [detail["source_quotation_id"], *(w["id"] for w in detail["work_packages"]), *(s["id"] for s in detail["snags"]),
                *(m["user"]["id"] for m in detail["team"] if m["user"]), *(x["id"] for x in detail["transitions"])]  # fmt: skip
    assert not [x for x in internal if x in text]
    assert p["project_number"] not in text  # the internal reference is never shown (VS-P overlap, CPP)


# --- M3: the commercial condition, every branch ------------------------------------------------------------------------
def _project_detail(t: Commercials, pid: str) -> dict:
    return ok(t.api.get(f"{BASE}/{pid}", token=t.tok(t.founder)))


def _commercial(t: Commercials, pid: str) -> set[str]:
    return {
        b["code"]
        for b in _project_detail(t, pid)["handover_readiness"]["blockers"]
        if b["gate"] == "COMMERCIAL_CONDITION"
    }


@pytest.mark.settings(**FLAGS, project_commercials_enabled=True)
def test_m3_the_commercial_condition_reads_the_projects_own_record_and_fails_closed(api, factory, policy):
    t = Commercials(api, factory)
    install_policy()
    prop, q, acc = t.opened()
    p = t.book(q, prop)
    # a second project on a chain with no commercial record: never "the latest record of the property"
    prop2, _, q2 = t.accepted("3BHK")
    p2 = t.book(q2, prop2)
    delivery(pex_d02="FULLY_PAID")
    assert _commercial(t, p2["id"]) == {"COMMERCIAL_RECORD_MISSING"}
    assert _commercial(t, p["id"]) == {"AMOUNT_OUTSTANDING"}
    delivery(pex_d02="NO_AMOUNT_DUE")
    assert _commercial(t, p["id"]) == set()  # a schedule in balance and nothing requested: nothing is due
    first = acc["schedule"]["lines"][0]
    t.request(acc, first["id"])
    assert _commercial(t, p["id"]) == {"AMOUNT_DUE"}
    t.pay(acc, first["amount_minor"] - 1)
    assert _commercial(t, p["id"]) == {"AMOUNT_DUE"}  # requested and part paid: still due
    t.pay(acc, 1)
    assert _commercial(t, p["id"]) == set()
    position = _project_detail(t, p["id"])["handover_readiness"]["commercial_position"]
    assert position["account_id"] == acc["id"] and position["lines_due"] == 0
    delivery(pex_d02="FULLY_PAID")
    rest = sum(x["amount_minor"] for x in t.get(acc)["schedule"]["lines"][1:])
    t.pay(acc, rest)
    assert _commercial(t, p["id"]) == set()
    delivery(pex_d02="NONE")
    assert _commercial(t, p2["id"]) == set()


@pytest.mark.settings(**FLAGS, project_commercials_enabled=True)
def test_m3_an_unsound_or_unbalanced_record_fails_closed(api, factory, policy, monkeypatch):
    from veda.modules.commercials import baseline as cbase
    from veda.modules.commercials import position as cpos

    t = Commercials(api, factory)
    prop, q, acc = t.opened()
    p = t.book(q, prop)
    delivery(pex_d02="NO_AMOUNT_DUE")
    real = cpos.compute

    def unbalanced(s, account, **kw):
        x = real(s, account, **kw)
        x.schedule_state = "REVISION_REQUIRED"
        return x

    monkeypatch.setattr(cpos, "compute", unbalanced)
    assert _commercial(t, p["id"]) == {"COMMERCIAL_SCHEDULE_NOT_IN_BALANCE"}
    monkeypatch.setattr(cpos, "compute", real)
    monkeypatch.setattr(cbase, "problems", lambda s, account: [{"code": "DIGEST_MISMATCH", "message": "SYNTHETIC"}])
    assert _commercial(t, p["id"]) == {"COMMERCIAL_RECORD_UNSOUND"}
