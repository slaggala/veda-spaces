"""Regression tests for the independent implementation review of WSV (record §Independent review): H1 a recorded class
always decides over a statement citation; H2 visits belong to their cycle and only work done after the current decision
or rejection counts; M1 closing cancels planned visits; M3 more competing operations; L1 no photo completes on a request
the customer is no longer describing; L2 one canonical citation path; L7 a repeated citation never changes silently.
SYNTHETIC data only, both engines."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.portal import PUBLIC
from tests.support.project import install, no_four_eyes, race
from tests.support.warranty import FLAGS, SERVICE, WARRANTY, Service, coverage, india_today, policy
from veda.modules.warranty.models import WarrantyEntitlement

pytestmark = pytest.mark.settings(**FLAGS)
ASSESS = {
    "explanation": "We have looked at what you reported carefully.",
    "internal_reason": "Reviewed against the terms.",
}


@pytest.fixture
def team(api, factory):
    install(no_four_eyes())
    t = Service(api, factory)
    yield t
    install(None)
    policy(None)


def _new(t: Service, key: str = "2BHK", email: str = "rf@example.test", **handover):
    prop, p, me = t.handed_over(key, email, **handover)
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.do(rid, "triage", {"priority": "NORMAL"})
    return prop, p, me, rid


def _today() -> str:
    return india_today()


def test_h1_a_recorded_class_decides_never_a_statement(team):
    t = team
    policy(coverage(1))
    _prop, _p, _me, rid = _new(t, days_ago=400)  # the 1-month class expired long ago
    r = t.do(rid, "assessments", {**ASSESS, "outcome": "COVERED", "basis_path": "sources/0/warranty/0",
                                  "period_basis": "Within the year."}, status=422)  # fmt: skip
    assert r.json["errors"][0]["code"] == "CLASS_REQUIRED"
    _prop2, _p2, _me2, rid2 = _new(t, "3BHK", "rf2@example.test", days_ago=2)  # the class is ACTIVE
    r = t.do(rid2, "assessments", {**ASSESS, "outcome": "OUTSIDE_WARRANTY_PERIOD", "basis_path": "sources/0/warranty/0",
                                   "period_basis": "Long ago.", "service_class": "CHARGEABLE"}, status=422)  # fmt: skip
    assert r.json["errors"][0]["code"] == "CLASS_REQUIRED"


def _resolve_once(t: Service, rid: str) -> None:
    d = t.do(rid, "visits", {"kind": "SERVICE", "planned_on": _today()}, user=t.tech, status=201)
    v = [x for x in d["visits"] if x["status"] == "PLANNED"][-1]
    t.do(rid, f"visits/{v['id']}/done", {"done_on": _today()}, user=t.tech)
    t.do(rid, "resolve", {"summary": "Re-aligned the drawer channel and tested it."}, user=t.tech)


def test_h2_earlier_work_never_satisfies_a_new_decision_or_a_rejected_resolution(team):
    t = team
    prop, _p, me, rid = _new(t)
    t.covered(rid)
    t.do(rid, "assign", {"owner_user_id": t.tech.id})
    _resolve_once(t, rid)
    assert t.customer(me, prop, rid, "reject", {"reason": "The drawer still sticks when it is full."}).status == 200
    r = t.do(rid, "resolve", {"summary": "Re-aligned the drawer channel again."}, user=t.tech, status=409)
    assert r.code == "SERVICE_NOT_RECORDED"  # the first visit came before the rejection
    _resolve_once(t, rid)
    t.do(rid, "verify", user=t.checker)
    t.do(rid, "reopen", {"reason": "The customer called: it sticks again."}, user=t.checker)
    t.covered(rid)
    t.do(rid, "visits", {"kind": "SERVICE", "planned_on": _today()}, user=t.tech, status=201)  # planned, not done
    r = t.do(rid, "resolve", {"summary": "Nothing new was done here."}, user=t.tech, status=409)
    assert r.code == "SERVICE_NOT_RECORDED"  # a previous cycle's visit never counts


def test_h2_an_inspection_counts_once_for_the_decision_that_asked_for_it(team):
    t = team
    _prop, _p, _me, rid = _new(t)
    t.do(rid, "assessments", {**ASSESS, "outcome": "INSPECTION_REQUIRED"})
    t.do(rid, "assign", {"owner_user_id": t.tech.id})
    d = t.do(rid, "visits", {"kind": "INSPECTION", "planned_on": _today()}, user=t.tech, status=201)
    t.do(rid, f"visits/{d['visits'][-1]['id']}/done", {"done_on": _today()}, user=t.tech)
    t.do(rid, "assessments", {**ASSESS, "outcome": "INSPECTION_REQUIRED"})  # a second inspection is needed
    r = t.do(rid, "assessments", {**ASSESS, "outcome": "NOT_COVERED", "service_class": "NOT_SERVICEABLE"}, status=409)
    assert r.code == "INSPECTION_NOT_DONE"  # the first inspection answered the first decision only


def test_m1_closing_cancels_planned_visits(team):
    t = team
    prop, _p, me, rid = _new(t)
    t.do(rid, "assessments", {**ASSESS, "outcome": "INSPECTION_REQUIRED"})
    t.do(rid, "assign", {"owner_user_id": t.tech.id})
    t.do(rid, "visits", {"kind": "INSPECTION", "planned_on": _today()}, user=t.tech, status=201)
    d = t.do(rid, "close", {"closure_code": "CANNOT_SERVICE", "explanation": "We cannot service this item, sorry.",
                            "internal_reason": "Third-party appliance outside our scope."})  # fmt: skip
    assert [v["status"] for v in d["visits"]] == ["CANCELLED"]
    v = me.property(prop["id"]).data["warranty"]["projects"][0]["requests"][0]
    assert v["visits"] == []


def test_l1_l2_l7_photos_after_withdrawal_canonical_paths_and_repeated_citations(team):
    import base64
    import hashlib

    from tests.support.mtq import jpeg, photo

    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    data = jpeg()
    body = {"mime_type": "image/jpeg", "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    pid = t.customer(me, prop, rid, "photos", body, **{"Idempotency-Key": "late-photo-01"}).data["photo_id"]
    t.customer(me, prop, rid, "withdraw", {})
    base = f"{PUBLIC}/properties/{prop['id']}/service-requests/{rid}/photos/{pid}"
    assert me.call("PUT", f"{base}/content", {"data_base64": base64.b64encode(data).decode()}).status == 409
    assert me.call("POST", f"{base}/complete", {}).status == 409
    rid2 = t.submit(me, prop, p, key="req-key-0099").data["request"]["id"]
    t.do(rid2, "triage", {"priority": "NORMAL"})
    for path in ("sources/-1/warranty/-1", "sources/00/warranty/0", "sources/0/warranty/0_0", "sources/0/warranty/01"):
        r = t.do(rid2, "assessments", {**ASSESS, "outcome": "COVERED", "basis_path": path, "period_basis": "x" * 10},
                 status=422)  # fmt: skip
        assert r.json["errors"][0]["code"] == "UNKNOWN_SOURCE", path
    t.factory.grant(t.care, "warranty.service.resolve")
    att = photo(t.as_(t.founder), "property", p["property"]["id"])
    t.do(rid2, "evidence", {"attachment_id": att["id"]})
    r = t.do(rid2, "evidence", {"attachment_id": att["id"], "customer_visible": True, "caption": "After"}, status=409)
    assert r.code == "EVIDENCE_ALREADY_CITED"


# --- M3: more competing operations (paused-request harness, no sleeps) ------------------------------------------------------
def test_confirmation_against_rejection(team, app, monkeypatch):
    from veda.modules.warranty import access as waccess

    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.resolved(rid)
    url = f"{PUBLIC}/properties/{prop['id']}/service-requests/{rid}"
    first, second = race(app, monkeypatch, None,
                         lambda c: c.call("POST", f"{url}/reject", {"reason": "Still sticks when the drawer is full."},
                                          headers={"X-Veda-Portal": me.token}, anonymous=True),
                         lambda: t.customer(me, prop, rid, "confirm"), module=waccess, name="lock")  # fmt: skip
    d = t.req(rid, t.checker)
    outcomes = [x["outcome"] for x in d["resolutions"]]
    assert outcomes in (["CONFIRMED"], ["REJECTED"]), (first, second, outcomes)  # one decision, never both
    assert d["status"] == ("CLOSED" if outcomes == ["CONFIRMED"] else "IN_PROGRESS")


def test_two_reopens(team, app, monkeypatch):
    from veda.modules.warranty import access as waccess

    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.customer(me, prop, rid, "withdraw", {})
    version = t.req(rid)["version"]
    body = {"reason": "The customer called again about it."}
    first, second = race(app, monkeypatch, t.token(t.checker),
                         lambda c: c.post(f"{SERVICE}/{rid}/reopen", body, if_match=version),
                         lambda: t.as_(t.founder).post(f"{SERVICE}/{rid}/reopen", body, if_match=version), module=waccess)  # fmt: skip
    assert sorted((first.status, second.status))[0] == 200 and sorted((first.status, second.status))[1] in (409, 412)
    assert t.req(rid)["cycle"] == 2


def test_the_subscriber_against_the_staff_command_and_a_failing_subscriber(team, app, monkeypatch):
    from veda.kernel import db
    from veda.kernel.context import actor, system_context
    from veda.modules.project import access as paccess
    from veda.modules.project import hooks
    from veda.modules.project.models import Project
    from veda.modules.warranty import access as waccess

    t = team
    monkeypatch.setattr(waccess, "staff_enabled", lambda: False)
    _prop, p, _me = t.handed_over()
    monkeypatch.undo()

    def subscriber():
        with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
            hooks.run_after_handover(s, s.get(Project, p["id"]), {})
        return 200

    first, second = race(app, monkeypatch, t.token(t.care),
                         lambda c: c.post(f"{WARRANTY}/entitlements", {"project_id": p["id"]}), subscriber,
                         module=paccess, name="lock")  # fmt: skip
    assert first.status in (200, 201)
    assert dbh.scalar(sa.select(sa.func.count(WarrantyEntitlement.id))) == 1
    # a failing subscriber never raises into the handover's handler
    calls = []
    monkeypatch.setattr(hooks, "AFTER_HANDOVER", [lambda s, proj, payload: calls.append(1) or 1 / 0])
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        hooks.run_after_handover(s, s.get(Project, p["id"]), {})
    assert calls == [1]


def test_rereview_an_inspection_before_the_first_decision_leads_to_a_decision(team):
    """Re-review (Medium): an inspection planned from TRIAGED, before any coverage decision, is followed by one."""
    t = team
    _prop, _p, _me, rid = _new(t)
    t.do(rid, "assign", {"owner_user_id": t.tech.id})
    d = t.do(rid, "visits", {"kind": "INSPECTION", "planned_on": _today()}, user=t.tech, status=201)
    r = t.do(rid, "assessments", {**ASSESS, "outcome": "NOT_COVERED", "service_class": "NOT_SERVICEABLE"}, status=409)
    assert r.code == "INSPECTION_NOT_DONE"  # planned, not done yet
    t.do(rid, f"visits/{d['visits'][-1]['id']}/done", {"done_on": _today()}, user=t.tech)
    d = t.do(rid, "assessments", {**ASSESS, "outcome": "NOT_COVERED", "service_class": "NOT_SERVICEABLE"})
    assert d["status"] == "ASSESSED"
