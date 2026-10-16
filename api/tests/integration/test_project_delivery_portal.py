"""Project delivery in the Customer Project Portal (PEX-060 … PEX-066): honest, customer-safe progress; customer
isolation; the customer's reports and handover acknowledgement (owner decision PEX-D01). SYNTHETIC data only."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ok
from tests.support.mtq import photo
from tests.support.portal import PUBLIC, Portal, keys
from tests.support.project import BASE, advance_to, delivery, install, no_four_eyes
from veda.kernel import clock
from veda.modules.project.models import ProjectCustomerReport, ProjectEvent
from veda.platform.notifications import worker
from veda.platform.notifications.email import CaptureEmailProvider

FLAGS = dict(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
             customer_portal_enabled=True, project_lifecycle_enabled=True)  # fmt: skip
pytestmark = pytest.mark.settings(**FLAGS, project_delivery_portal_enabled=True)
ACTIONS = {"issue_reports": True, "handover_acknowledgement": True}
INTERNAL_KEYS = {"title", "description_internal", "owner", "planned_start", "planned_finish", "observation",
                 "fix_note", "evidence", "evidence_attachment_id", "account_id", "triaged_by", "created_by",
                 "lead_id", "is_blocking", "priority", "percent", "percentage"}  # fmt: skip


@pytest.fixture
def team(api, factory):
    t = Portal(api, factory)
    install(no_four_eyes())
    yield t
    install(None)


def _today(days: int = 0) -> str:
    return (clock.now().date() + timedelta(days=days)).isoformat()


def _project(t: Portal, key: str = "2BHK", email: str = "delivery@example.test"):
    prop, _, q = t.accepted(key)
    p = t.book(q, prop)
    t.staff(p)
    me = t.invite(prop["lead_id"], email)
    return prop, t.get(p), me


def _view(me, prop: dict) -> dict:
    return ok(me.property(prop["id"]))["delivery"]["projects"][0]


def _wp(t: Portal, p: dict, **body) -> dict:
    d = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/work-packages", {"stage_code": t.get(p)["stage"]["code"], **body}), 201)
    return d["work_packages"][-1]


def _run(t: Portal, p: dict, wp: dict, *cmds: str) -> None:
    for cmd in cmds:
        cur = next(w for w in t.get(p)["work_packages"] if w["id"] == wp["id"])
        body = {"actual_start": _today()} if cmd == "start" else {"actual_finish": _today()}
        ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/work-packages/{wp['id']}/{cmd}", body, if_match=cur["version"]))


def _report(me, prop: dict, project_id: str, body: dict | None = None, key: str | None = "report-key-0001"):
    headers = {"X-Veda-Portal": me.token, **({"Idempotency-Key": key} if key else {})}
    return me.api.call("POST", f"{PUBLIC}/properties/{prop['id']}/projects/{project_id}/reports",
                       body or {"description": "The kitchen drawer does not close fully", "area": "Kitchen"},
                       headers=headers, anonymous=True)  # fmt: skip


# --- what the customer sees ----------------------------------------------------------------------------------------------
def test_the_customer_sees_honest_states_in_customer_words_and_nothing_internal(team):
    t = team
    prop, p, me = _project(t)
    done = _wp(t, p, title="Kitchen carcass INTERNAL-T1", customer_label="Kitchen cabinets", customer_visible=True)
    _run(t, p, done, "start", "complete")
    paused = _wp(t, p, title="Wardrobe INTERNAL-T2", customer_label="Wardrobes", customer_visible=True)
    waiting = _wp(t, p, title="Loft INTERNAL-T3", customer_label="Lofts", customer_visible=True)
    _wp(t, p, title="Electrical rework INTERNAL-T4")  # internal work: never shown
    _wp(t, p, title="TV unit INTERNAL-T5", customer_label="TV unit", customer_visible=True,
        planned_start=_today(211), planned_finish=_today(233))  # fmt: skip
    api = t.as_(t.ops)
    ok(api.post(f"{BASE}/{p['id']}/blockers", {"category": "MATERIAL_SPECIFICATION", "impact": "GATING",
                                              "title": "Supplier short of laminate INTERNAL-B1", "responsible_party": "VEDA",
                                              "blocks_stage_code": "INSTALLATION", "related_work_package_id": paused["id"],
                                              "customer_summary": "We are waiting for a material delivery"}), 201)  # fmt: skip
    ok(api.post(f"{BASE}/{p['id']}/blockers", {"category": "CUSTOMER_DECISION", "impact": "GATING",
                                              "title": "Loft finish INTERNAL-B2", "responsible_party": "CUSTOMER",
                                              "customer_action": "Please choose the loft shutter finish",
                                              "blocks_stage_code": "INSTALLATION",
                                              "related_work_package_id": waiting["id"]}), 201)  # fmt: skip
    view = _view(me, prop)
    states = {w["label"]: w["state"] for w in view["work"]["items"]}
    assert states == {"Kitchen cabinets": "COMPLETED", "Wardrobes": "BLOCKED", "Lofts": "ACTION_REQUIRED",
                      "TV unit": "UPCOMING"}  # fmt: skip
    assert view["work"]["counts"] == {
        "COMPLETED": 1,
        "IN_PROGRESS": 0,
        "ACTION_REQUIRED": 1,
        "BLOCKED": 1,
        "UPCOMING": 1,
    }
    assert view["paused"] == [
        {"text": "We are waiting for a material delivery", "state": "BLOCKED", "who": "VEDA_SPACES"}
    ]
    text = json.dumps(ok(me.property(prop["id"])))
    assert _today(211) not in text and _today(233) not in text  # no internal plan
    assert "INTERNAL-" not in text, text[max(text.index("INTERNAL-") - 300, 0) : text.index("INTERNAL-") + 100]
    assert not (keys(view) & INTERNAL_KEYS)
    assert view["next_date"] is None  # only a customer-promised date would be shown
    # the customer's action is in Action Required; Veda's wait is never presented as theirs
    attention = ok(me.property(prop["id"]))["attention"]
    assert [a["text"] for a in attention if a["kind"] == "PROJECT_ACTION"] == ["Please choose the loft shutter finish"]


def test_quality_and_snags_are_shown_as_counts_and_customer_visible_snags_only(team):
    t = team
    prop, p, me = _project(t)
    p = advance_to(t, p, "SNAGGING")
    api = t.as_(t.ops)
    ok(api.post(f"{BASE}/{p['id']}/snags", {"category": "FINISH", "customer_title": "Touch-up on the skirting",
                                           "customer_visible": True, "owner_user_id": t.ops.id}), 201)  # fmt: skip
    ok(api.post(f"{BASE}/{p['id']}/snags", {"category": "DAMAGE", "customer_title": "INTERNAL-S2 supplier damage",
                                           "owner_user_id": t.ops.id}), 201)  # fmt: skip
    view = _view(me, prop)
    assert view["quality"] == {"checks_passed": 2, "being_corrected": 0}
    assert view["snags"] == [
        {"number": 1, "title": "Touch-up on the skirting", "status": "Noted", "state": "IN_PROGRESS"}
    ]
    sn = t.get(p)["snags"][0]
    assert t.snag_through(p, sn["id"], to="RESOLVED")["status"] == "RESOLVED"
    assert _view(me, prop)["snags"][0]["status"] == "Fixed and checked"
    assert "INTERNAL-S2" not in json.dumps(ok(me.property(prop["id"])))


@pytest.mark.settings(**FLAGS, project_delivery_portal_enabled=False)
def test_with_the_delivery_flag_off_nothing_is_shown_and_no_customer_write_exists(team):
    t = team
    prop, p, me = _project(t)
    delivery({"issue_reports": True, "handover_acknowledgement": True})
    assert ok(me.property(prop["id"]))["delivery"] is None and ok(me.home())["delivery_available"] is False
    assert _report(me, prop, p["id"]).status == 404
    r = me.call("POST", f"{PUBLIC}/properties/{prop['id']}/projects/{p['id']}/handover/acknowledge",
                {"package_id": p["id"], "content_sha256": "0" * 64})  # fmt: skip
    assert r.status == 404


# --- isolation -----------------------------------------------------------------------------------------------------------
def test_customer_b_reaches_nothing_of_customer_a_and_guessed_ids_disclose_nothing(team):
    t = team
    delivery(ACTIONS)
    prop_a, p_a, me_a = _project(t, "2BHK", "alpha@example.test")
    prop_b, p_b, me_b = _project(t, "3BHK", "bravo@example.test")
    ok(_report(me_a, prop_a, p_a["id"]), 201)
    assert me_b.property(prop_a["id"]).status == 404
    from veda.kernel.ids import new_id

    missing = new_id()  # well-formed, but nobody's
    for prop, pid in ((prop_a, p_a["id"]), (prop_b, p_a["id"]), (prop_b, missing)):
        r = _report(me_b, prop, pid, key=f"bravo-key-{pid[-6:]}-{prop['id'][-4:]}")
        assert r.status == 404 and r.code == "NOT_FOUND", (prop["id"], pid)
    r = me_b.call("POST", f"{PUBLIC}/properties/{prop_b['id']}/projects/{p_a['id']}/handover/acknowledge",
                  {"package_id": missing, "content_sha256": "0" * 64})  # fmt: skip
    assert r.status == 404
    text_b = json.dumps(ok(me_b.property(prop_b["id"])))
    assert "kitchen drawer" not in text_b and p_a["id"] not in text_b
    # without a portal session (or with a staff token) nothing is reached
    anon = me_a.api.call("POST", f"{PUBLIC}/properties/{prop_a['id']}/projects/{p_a['id']}/reports",
                         {"description": "Anonymous attempt here"}, headers={"Idempotency-Key": "anon-key-001"},
                         anonymous=True)  # fmt: skip
    assert anon.status == 401
    staff = me_a.api.call("GET", f"{PUBLIC}/properties/{prop_a['id']}", token=t.token(t.founder))
    assert staff.status == 401


# --- customer reports ----------------------------------------------------------------------------------------------------
def test_reports_wait_for_the_owner_decision_then_are_idempotent_limited_and_triaged_in_view(team):
    t = team
    prop, p, me = _project(t)
    r = _report(me, prop, p["id"])
    assert r.status == 409 and r.code == "OWNER_DECISION_REQUIRED" and r.json["decision"] == "PEX-D01"
    assert _view(me, prop)["can_report"] is False
    delivery({"issue_reports": True, "handover_acknowledgement": False})
    assert _view(me, prop)["can_report"] is True
    assert _report(me, prop, p["id"], key=None).status == 400
    first = _report(me, prop, p["id"])
    assert first.status == 201 and first.data["reference"] == "Report 1"
    again = _report(me, prop, p["id"])
    assert again.status == 200 and again.data["reference"] == "Report 1"  # a retry is the same report
    other = _report(me, prop, p["id"], body={"description": "A different issue entirely"})
    assert other.status == 409 and other.code == "IDEMPOTENCY_KEY_REUSED"
    assert dbh.scalar(sa.select(sa.func.count()).select_from(ProjectCustomerReport)) == 1
    staff_view = t.get(p)["customer_reports"]
    assert [(r["status"], r["channel"]) for r in staff_view] == [("SUBMITTED", "PORTAL")]
    assert _view(me, prop)["reports"][0]["status"] == "Received, being reviewed"
    # the customer's acknowledgement email says only that it was received
    worker.drain_all()
    mails = [m for m in CaptureEmailProvider.sent if me.email in m.to and m.template == "project_update"]
    assert len(mails) == 1 and "drawer" not in mails[0].text and "INTERNAL" not in mails[0].text
    worker.drain_all()
    assert len([m for m in CaptureEmailProvider.sent if m.template == "project_update"]) == 1  # never twice
    # a second person on the same enquiry never sees the first person's reports
    partner = t.invite(prop["lead_id"], "partner@example.test", relationship="CO_OWNER")
    assert ok(partner.property(prop["id"]))["delivery"]["projects"][0]["reports"] == []
    # at most ten waiting per account and project
    for n in range(2, 11):
        assert _report(me, prop, p["id"], body={"description": f"Issue number {n} in the home"},
                       key=f"report-key-{n:04d}").status == 201  # fmt: skip
    r = _report(me, prop, p["id"], body={"description": "One more issue in the home"}, key="report-key-0099")
    assert r.status == 409 and r.code == "REPORT_LIMIT_REACHED"
    # Veda's reply reaches the customer in customer words
    rep = t.get(p)["customer_reports"][0]
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/customer-reports/{rep['id']}/triage",
                         {"outcome": "DECLINED", "decline_code": "NOT_IN_SCOPE",
                          "response": "Drawer soft-close was not part of the agreed kitchen."}, if_match=rep["version"]))  # fmt: skip
    mine = _view(me, prop)["reports"][0]
    assert mine["outcome"] == "Not part of the agreed work" and mine["response"].startswith("Drawer soft-close")


# --- handover ------------------------------------------------------------------------------------------------------------
def _ready(t: Portal, p: dict) -> dict:
    p = advance_to(t, p, "READY_FOR_HANDOVER")
    t.checklist(p)
    return t.package(p)["handover_packages"][-1]


def _ack(me, prop: dict, p: dict, pkg: dict, sha: str | None = None):
    return me.call("POST", f"{PUBLIC}/properties/{prop['id']}/projects/{p['id']}/handover/acknowledge",
                   {"package_id": pkg["id"], "content_sha256": sha or pkg["content_sha256"]})  # fmt: skip


def test_the_customer_acknowledges_exactly_the_package_once_and_the_handover_uses_it(team):
    t = team
    prop, p, me = _project(t)
    pkg = _ready(t, p)
    view = _view(me, prop)
    assert view["handover"]["label"] == "Ready for handover" and view["package"]["status"] == "READY_TO_REVIEW"
    assert view["package"]["can_acknowledge"] is False and view["package"]["documents"] == []
    assert view["package"]["warranty_note"] == "Warranty is as set out in your accepted quotation."
    assert _ack(me, prop, p, pkg).code == "OWNER_DECISION_REQUIRED"
    delivery({"issue_reports": False, "handover_acknowledgement": True})
    assert any(a["kind"] == "HANDOVER_ACKNOWLEDGEMENT" for a in ok(me.property(prop["id"]))["attention"])
    assert _ack(me, prop, p, pkg, sha="f" * 64).code == "HANDOVER_PACKAGE_CHANGED"
    first = ok(_ack(me, prop, p, pkg))
    second = ok(_ack(me, prop, p, pkg))
    assert first["acknowledged_on"] == second["acknowledged_on"]
    assert dbh.scalar(sa.select(sa.func.count()).select_from(ProjectEvent).where(
        ProjectEvent.event_code == "HANDOVER_ACKNOWLEDGED")) == 1  # fmt: skip
    assert not any(a["kind"] == "HANDOVER_ACKNOWLEDGEMENT" for a in ok(me.property(prop["id"]))["attention"])
    # the portal acknowledgement satisfies the acknowledgement requirement of PLB-OD-09 for this package
    att = photo(t.as_(t.founder), "property", prop["id"])
    r = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/handover", {"handover_on": _today(), "evidence_attachment_id": att["id"]},
                             if_match=t.get(p)["version"]), 201)  # fmt: skip
    assert r["outcome"] == "COMPLETED" and r["transition"]["handover"]["acknowledgement_reference"].startswith(
        "PORTAL-ACKNOWLEDGED"
    )
    view = _view(me, prop)
    assert view["handover"]["state"] == "COMPLETED" and view["package"]["status"] == "HANDED_OVER"
    assert _report(me, prop, p["id"]).status in (404, 409)  # no portal report after handover


def test_an_acknowledgement_never_carries_over_to_a_changed_package(team):
    t = team
    delivery({"issue_reports": False, "handover_acknowledgement": True})
    prop, p, me = _project(t)
    pkg = _ready(t, p)
    ok(_ack(me, prop, p, pkg))
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/snags", {"category": "FINISH", "customer_title": "Touch-up on the door",
                                                    "is_blocking": False, "customer_visible": True}), 201)  # fmt: skip
    assert _view(me, prop)["package"]["status"] == "BEING_UPDATED"
    new = t.package(p)["handover_packages"][-1]
    assert new["id"] != pkg["id"] and new["acknowledged_on"] is None
    att = photo(t.as_(t.founder), "property", prop["id"])
    r = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/handover", {"handover_on": _today(), "evidence_attachment_id": att["id"]},
                             if_match=t.get(p)["version"]), 201)  # fmt: skip
    assert r["outcome"] == "REFUSED" and {b["code"] for b in r["transition"]["blockers"]} == {"ACKNOWLEDGEMENT_MISSING"}
    assert _ack(me, prop, p, pkg).code == "HANDOVER_PACKAGE_CHANGED"  # the superseded one can no longer be acknowledged
    worker.drain_all()
    ready = [m for m in CaptureEmailProvider.sent if m.template == "project_update" and "handover summary" in m.text]
    assert len(ready) == 1  # the superseded package's email was never sent; the current one's once
