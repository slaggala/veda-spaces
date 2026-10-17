"""Warranty and after-sales service (WSV, decision log 47): entitlements frozen at handover from authoritative records,
truthful coverage status, the controlled service workflow, explicit coverage decisions, the chargeable and
manufacturer paths, verification, reopening and the customer's view. SYNTHETIC data only, both engines."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.support.commercial import ok
from tests.support.project import install, no_four_eyes
from tests.support.warranty import FLAGS, WARRANTY, Service, coverage, india_today, policy
from veda.kernel import clock

pytestmark = pytest.mark.settings(**FLAGS)


@pytest.fixture
def team(api, factory):
    install(no_four_eyes())
    t = Service(api, factory)
    yield t
    install(None)
    policy(None)


def _today(days: int = 0) -> str:
    return (clock.now().date() + timedelta(days=days)).isoformat()


# --- entitlement ---------------------------------------------------------------------------------------------------------
def test_the_entitlement_is_frozen_from_the_handover_and_says_not_recorded_without_structured_terms(team):
    t = team
    prop, p, _me = t.handed_over(days_ago=3)
    e = t.register(p, status=200)  # already registered by the post-handover subscriber
    assert e["registered"] and e["registered_via"] == "HANDOVER_EVENT"
    assert e["handover_on"] == _today(-3)  # the handover date, never the registration time
    assert e["handover"]["date_check"] == "HANDOVER_DATE_BEFORE_PACKAGE"  # flagged for staff, never corrected
    assert e["status"] == "NOT_RECORDED" and e["coverage"] == []
    src = e["sources"][0]
    assert src["warranty"] == ["Synthetic warranty text for tests."] and src["terms_version"] == "SYN-T1"
    assert src["snapshot_sha256"] and src["quotation_number"] == p["quotation_number"]
    assert e["handover"]["transition_id"] and e["handover"]["package_sha256"]
    again = t.register(p, status=200)  # idempotent: the same entitlement
    assert again["id"] == e["id"] and again["terms_sha256"] == e["terms_sha256"]
    # a later policy never rewrites the frozen promise
    policy(coverage(12))
    assert t.register(p, status=200)["coverage"] == []


def test_structured_terms_apply_only_to_what_the_customer_accepted_and_status_is_computed_from_the_handover(team):
    t = team
    policy(coverage(12, terms_versions=("OTHER-TERMS",)))
    _prop, p, _me = t.handed_over("2BHK", "a@example.test")
    assert t.register(p, status=200)["coverage"] == []  # the accepted terms_version is not one the decision lists
    policy(coverage(12))
    _prop2, p2, _me2 = t.handed_over("3BHK", "b@example.test", days_ago=10)
    e = t.register(p2, status=200)
    (cls,) = e["coverage"]
    assert cls["status"] == "ACTIVE" and cls["starts_on"] == _today(-10)
    assert e["status"] == "ACTIVE" and e["status_label"] == "Active"


def test_a_project_handed_over_while_the_flag_was_off_is_registered_later_from_its_handover(team, monkeypatch):
    from veda.modules.warranty import access

    t = team
    monkeypatch.setattr(access, "staff_enabled", lambda: False)  # the subscriber does nothing while the flag is off
    _prop, p, _me = t.handed_over(days_ago=0)
    monkeypatch.undo()
    view = ok(t.as_(t.care).get(f"{WARRANTY}/projects/{p['id']}"))
    assert view["registered"] is False and view["can_register"] is True
    e = t.register(p)  # 201: registered now, from the handover record
    assert e["registered_via"] == "STAFF" and e["handover_on"] == p["handed_over_on"][:10]


def test_status_words_and_month_arithmetic():
    from veda.modules.warranty import entitlement

    assert entitlement.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert entitlement.add_months(date(2026, 10, 16), 12) == date(2027, 10, 16)


def test_a_project_not_handed_over_has_no_entitlement(team):
    t = team
    prop, _, q = t.accepted()
    p = t.book(q, prop)
    r = t.as_(t.care).post(f"{WARRANTY}/entitlements", {"project_id": p["id"]})
    assert r.status == 409 and r.code == "PROJECT_NOT_HANDED_OVER"


# --- the workflow --------------------------------------------------------------------------------------------------------
def test_the_happy_path_from_report_to_customer_confirmation(team):
    t = team
    prop, p, me = t.handed_over()
    r = t.submit(me, prop, p)
    assert r.status == 201
    req = r.data["request"]
    assert req["status"] == "REPORTED" and req["status_label"] == "Received" and req["coverage"] is None
    assert t.submit(me, prop, p).data["request"]["id"] == req["id"]  # the same key: the same request
    rid = req["id"]
    d = t.req(rid)
    assert d["channel"] == "PORTAL" and d["reported_on"] == india_today() and d["request_number"].startswith("VS-SR-")
    t.resolved(rid)
    view = ok(me.property(prop["id"]))["warranty"]["projects"][0]["requests"][0]
    assert view["status"] == "RESOLVED" and view["next"] == "YOU" and view["can_confirm"]
    assert view["coverage"]["label"] == "Covered by your warranty"
    assert "internal" not in str(view).lower() or "internal_reason" not in str(view)
    c = t.customer(me, prop, rid, "confirm")
    assert (
        c.status == 200 and c.data["request"]["status"] == "CLOSED" and c.data["request"]["status_label"] == "Resolved"
    )
    assert t.customer(me, prop, rid, "confirm").status == 200  # repeating it changes nothing
    d = t.req(rid, t.checker)
    assert d["verified_by_kind"] == "CUSTOMER" and d["resolutions"][0]["outcome"] == "CONFIRMED"
    codes = [e["code"] for e in d["timeline"]]
    assert codes[0] == "SUBMITTED" and codes[-1] == "CLOSED" and "ASSESSED" in codes and "RESOLVED" in codes
