"""Coverage decisions (WSV-012): explicit, by an assessor, on an authoritative basis, as of the reported date; the
manufacturer, chargeable, inspection and information paths; closure rules; verification and reopening; the customer's
withdrawal and rejection. SYNTHETIC data only, both engines."""

from __future__ import annotations

import pytest

from tests.support.commercial import ok
from tests.support.project import install, no_four_eyes
from tests.support.warranty import FLAGS, Service, coverage, india_today, policy

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


def _new(t: Service, key: str = "2BHK", email: str = "c@example.test", **handover):
    prop, p, me = t.handed_over(key, email, **handover)
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.do(rid, "triage", {"priority": "NORMAL"})
    return prop, p, me, rid


def _assess(t: Service, rid: str, status: int = 200, **body):
    return t.do(rid, "assessments", {**ASSESS, **body}, status=status)


def test_covered_needs_an_authoritative_basis_never_a_manufacturer_note_or_an_exclusion(team):
    t = team
    _prop, _p, _me, rid = _new(t)
    r = _assess(t, rid, 422, outcome="COVERED")
    assert r.json["errors"][0]["code"] == "BASIS_REQUIRED"
    r = _assess(t, rid, 422, outcome="COVERED", basis_path="sources/0/warranty/0")
    assert r.json["errors"][0]["field"] == "period_basis"  # no structured period: the assessor must say why
    r = _assess(t, rid, 422, outcome="COVERED", basis_path="sources/0/warranty/9", period_basis="Within the year.")
    assert r.json["errors"][0]["code"] == "UNKNOWN_SOURCE"
    d = _assess(t, rid, outcome="COVERED", basis_path="sources/0/warranty/0", period_basis="Within the first year.")
    a = d["assessments"][-1]
    assert (a["basis_kind"], a["service_class"], a["as_of"]) == ("WARRANTY_STATEMENT", "WARRANTY", d["reported_on"])
    assert len(a["basis_text_sha256"]) == 64 and d["status"] == "ASSESSED"


def test_coverage_is_judged_as_of_the_reported_date_from_the_handover(team):
    t = team
    policy(coverage(12))
    _prop, _p, _me, rid = _new(t, days_ago=400)  # handed over 400 days ago: a 12-month class has expired
    r = _assess(t, rid, 422, outcome="COVERED", coverage_class="WORKMANSHIP")
    assert r.code == "COVERAGE_NOT_ACTIVE" and r.json["coverage_status"] == "EXPIRED"
    d = _assess(
        t, rid, outcome="OUTSIDE_WARRANTY_PERIOD", coverage_class="WORKMANSHIP", service_class="NOT_SERVICEABLE"
    )
    assert d["assessments"][-1]["coverage_status"] == "EXPIRED"
    _prop2, _p2, _me2, rid2 = _new(t, "3BHK", "d@example.test", days_ago=5)
    r = _assess(
        t, rid2, 422, outcome="OUTSIDE_WARRANTY_PERIOD", coverage_class="WORKMANSHIP", service_class="CHARGEABLE"
    )
    assert r.code == "COVERAGE_NOT_EXPIRED"  # a fact, not an opinion
    d = _assess(t, rid2, outcome="COVERED", coverage_class="WORKMANSHIP")
    assert d["assessments"][-1]["basis_kind"] == "COVERAGE_CLASS"


def test_manufacturer_warranty_is_a_referral_never_veda_work(team):
    t = team
    prop, _p, me, rid = _new(t)
    r = _assess(t, rid, 422, outcome="MANUFACTURER_WARRANTY", basis_path="sources/0/warranty/0")
    assert r.json["errors"][0]["code"] == "BASIS_NOT_ALLOWED"
    _assess(t, rid, outcome="MANUFACTURER_WARRANTY")
    t.do(rid, "assign", {"owner_user_id": t.tech.id})
    r = t.do(rid, "visits", {"kind": "SERVICE", "planned_on": india_today()}, user=t.tech, status=409)
    assert r.code == "COVERAGE_NOT_DECIDED"
    r = t.do(rid, "close", {"closure_code": "NOT_COVERED", "explanation": "This is for the manufacturer to warrant."},
             status=409)  # fmt: skip
    assert r.code == "ASSESSMENT_REQUIRED"  # the closure code must match the decision
    d = t.do(rid, "close", {"closure_code": "REFERRED_TO_MANUFACTURER",
                            "explanation": "This is covered by the appliance maker's own warranty."})  # fmt: skip
    assert d["status"] == "CLOSED" and d["closure_code"] == "REFERRED_TO_MANUFACTURER"
    v = ok(me.property(prop["id"]))["warranty"]["projects"][0]["requests"][0]
    assert v["status_label"] == "Closed: for the manufacturer's warranty"


def test_chargeable_work_fails_closed_at_the_commercial_agreement(team):
    t = team
    prop, _p, me, rid = _new(t)
    r = _assess(t, rid, 422, outcome="NOT_COVERED")
    assert r.json["errors"][0]["field"] == "service_class"
    d = _assess(t, rid, outcome="NOT_COVERED", service_class="CHARGEABLE", basis_path="sources/0/warranty/0")
    assert d["status"] == "AWAITING_COMMERCIAL_AGREEMENT" and d["service_class"] == "CHARGEABLE"
    t.do(rid, "assign", {"owner_user_id": t.tech.id})
    r = t.do(rid, "visits", {"kind": "SERVICE", "planned_on": india_today()}, user=t.tech, status=409)
    assert r.code == "INVALID_STATE"  # never silently free work
    v = ok(me.property(prop["id"]))["warranty"]["projects"][0]["requests"][0]
    assert (
        v["status_label"] == "Not covered by your warranty" and "nothing is charged" in v["coverage"]["chargeable_note"]
    )
    assert v["can_withdraw"] is True
    d = t.do(rid, "close", {"closure_code": "CHARGEABLE_NOT_AGREED", "explanation": "You chose not to go ahead."})
    assert d["closure_code"] == "CHARGEABLE_NOT_AGREED"


def test_inspection_then_a_new_assessment_and_information_from_the_customer(team):
    t = team
    prop, _p, me, rid = _new(t)
    _assess(t, rid, outcome="INSPECTION_REQUIRED")
    t.do(rid, "assign", {"owner_user_id": t.tech.id})
    r = t.do(rid, "visits", {"kind": "SERVICE", "planned_on": india_today()}, user=t.tech, status=409)
    assert r.code == "COVERAGE_NOT_DECIDED"
    r = _assess(t, rid, 409, outcome="COVERED", basis_path="sources/0/warranty/0", period_basis="Within the year.")
    assert r.code == "INSPECTION_NOT_DONE"
    d = t.do(rid, "visits", {"kind": "INSPECTION", "planned_on": india_today()}, user=t.tech, status=201)
    v = d["visits"][-1]
    t.do(rid, f"visits/{v['id']}/done", {"done_on": india_today(), "internal_note": "Swollen edge."},
         user=t.tech)  # fmt: skip
    # Veda asks the customer something during the work; the answer returns the request where it was
    t.do(rid, "information-requests", {"question": "When did you first notice the swelling near the sink?"})
    view = ok(me.property(prop["id"]))
    assert any(a["kind"] == "SERVICE_ACTION" for a in view["attention"])
    r = t.customer(me, prop, rid, "information", {"text": "About two weeks ago, after the rains."})
    assert r.status == 200 and r.data["request"]["status"] == "IN_PROGRESS"
    d = _assess(t, rid, outcome="COVERED", basis_path="sources/0/warranty/0", period_basis="Within the first year.")
    assert d["status"] == "ASSESSED" and [a["outcome"] for a in d["assessments"]] == ["INSPECTION_REQUIRED", "COVERED"]


def test_insufficient_information_asks_the_customer(team):
    t = team
    prop, _p, me, rid = _new(t)
    d = _assess(t, rid, outcome="INSUFFICIENT_INFORMATION",
                explanation="Please send a photo of the drawer from the front.")  # fmt: skip
    assert d["status"] == "INFORMATION_REQUESTED"
    v = ok(me.property(prop["id"]))["warranty"]["projects"][0]["requests"][0]
    assert v["messages"][-1]["text"] == "Please send a photo of the drawer from the front." and v["can_add_photos"]


def test_rejection_is_limited_verification_is_independent_and_reopening_needs_a_new_decision(team):
    t = team
    prop, _p, me, rid = _new(t)
    t.covered(rid)
    t.do(rid, "assign", {"owner_user_id": t.tech.id})

    def resolve():
        d = t.do(rid, "visits", {"kind": "SERVICE", "planned_on": india_today()}, user=t.tech, status=201)
        v = [x for x in d["visits"] if x["status"] == "PLANNED"][-1]
        t.do(rid, f"visits/{v['id']}/done", {"done_on": india_today()}, user=t.tech)
        return t.do(rid, "resolve", {"summary": "Re-aligned the drawer channel and tested it."}, user=t.tech)

    resolve()
    for n in (1, 2):
        r = t.customer(me, prop, rid, "reject", {"reason": "The drawer still sticks when it is full."})
        assert r.status == 200 and r.data["request"]["status"] == "IN_PROGRESS", n
        resolve()
    r = t.customer(me, prop, rid, "reject", {"reason": "The drawer still sticks when it is full."})
    assert r.status == 409 and r.code == "REJECTION_LIMIT_REACHED"
    d = t.req(rid, t.checker)
    assert [x["outcome"] for x in d["resolutions"]] == ["REJECTED", "REJECTED", "PENDING"]  # history kept
    t.factory.grant(t.tech, "warranty.service.verify")
    r = t.do(rid, "verify", user=t.tech, status=403)
    assert r.code == "SEPARATION_OF_DUTIES"
    d = t.do(rid, "verify", user=t.checker)
    assert d["status"] == "CLOSED" and d["verified_by_kind"] == "STAFF"
    d = t.do(rid, "reopen", {"reason": "The customer called: it sticks again."}, user=t.checker)
    assert (d["status"], d["cycle"], d["closure_code"]) == ("TRIAGED", 2, None)
    r = t.do(rid, "reopen", {"reason": "Clicked twice by mistake."}, user=t.checker, status=409)
    assert r.code == "INVALID_STATE"  # a repeated reopen changes nothing
    t.do(rid, "assign", {"owner_user_id": t.tech.id})
    r = t.do(rid, "visits", {"kind": "SERVICE", "planned_on": india_today()}, user=t.tech, status=409)
    assert r.code == "COVERAGE_NOT_DECIDED"  # a new cycle needs a new coverage decision


def test_withdrawal_and_closure_rules(team):
    t = team
    prop, p, me, rid = _new(t)
    r = t.customer(me, prop, rid, "withdraw", {"reason": "It fixed itself."})
    assert r.status == 200 and r.data["request"]["status_label"] == "Withdrawn"
    assert t.customer(me, prop, rid, "withdraw", {}).status == 200  # repeated: no change
    rid2 = t.submit(me, prop, p, key="req-key-0002").data["request"]["id"]
    r = t.do(rid2, "close", {"closure_code": "DUPLICATE", "explanation": "You told us about this already."}, status=422)
    assert r.json["errors"][0]["field"] == "duplicate_of_id"
    d = t.do(rid2, "close", {"closure_code": "DUPLICATE", "duplicate_of_id": rid,
                             "explanation": "You told us about this already."})  # fmt: skip
    assert d["duplicate_of_id"] == rid
    rid3 = t.submit(me, prop, p, key="req-key-0003").data["request"]["id"]
    r = t.do(
        rid3, "close", {"closure_code": "CANNOT_SERVICE", "explanation": "We cannot service this item."}, status=422
    )
    assert r.json["errors"][0]["field"] == "internal_reason"
