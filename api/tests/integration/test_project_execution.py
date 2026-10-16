"""Project execution (PEX): work packages, the QC plan and check chains, independent snag verification, customer reports
(staff channel), the handover package and the structural gates. SYNTHETIC data only, both engines."""

from __future__ import annotations

from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ok
from tests.support.mtq import photo
from tests.support.project import BASE, ON, Projects, advance_to, delivery, install, no_four_eyes, synthetic_policy
from veda.kernel import clock
from veda.modules.project import lifecycle
from veda.modules.project import permissions as P
from veda.modules.project.models import ProjectEvent

pytestmark = ON


@pytest.fixture
def team(api, factory):
    t = Projects(api, factory)
    install(no_four_eyes())
    yield t
    install(None)


def _today(days: int = 0) -> str:
    return (clock.now().date() + timedelta(days=days)).isoformat()


def _booked(t: Projects) -> dict:
    prop, _, q = t.accepted()
    p = t.book(q, prop)
    t.staff(p)
    p = t.get(p)
    p["_prop"] = prop
    return p


def _wp(t: Projects, p: dict, user=None, status: int = 201, **body):
    base = {"stage_code": t.get(p)["stage"]["code"], "title": "Kitchen carcass assembly"}
    r = t.as_(user or t.ops).post(f"{BASE}/{p['id']}/work-packages", {**base, **body})
    assert r.status == status, r
    return r.data["work_packages"][-1] if status == 201 else r


def _w(t: Projects, p: dict, wp_id: str) -> dict:
    return next(w for w in t.get(p)["work_packages"] if w["id"] == wp_id)


def _cmd(t: Projects, p: dict, wp_id: str, cmd: str, body: dict, user=None, status: int = 200):
    r = t.as_(user or t.ops).post(f"{BASE}/{p['id']}/work-packages/{wp_id}/{cmd}", body,
                                  if_match=_w(t, p, wp_id)["version"])  # fmt: skip
    assert r.status == status, r
    return r if status != 200 else next(w for w in r.data["work_packages"] if w["id"] == wp_id)


def _events(p: dict, code: str) -> list[ProjectEvent]:
    return dbh.rows(sa.select(ProjectEvent).where(ProjectEvent.project_id == p["id"], ProjectEvent.event_code == code))


# --- RBAC ----------------------------------------------------------------------------------------------------------------
def test_the_new_capabilities_are_the_founders_and_the_accountant_has_no_project_code(api, factory):
    for code in ("project.manage_work", "project.verify_snag"):
        assert P.MATRIX[code] == {"FOUNDER": "A"}, code
    from veda.platform.rbac import registry

    assert not [c for c, g in registry.MATRIX.items() if c.startswith("project.") and "ACCOUNTANT" in g]
    t = Projects(api, factory)
    p = _booked(t)
    acc = factory.user("ACCOUNTANT", mfa=True)
    for method, path in (("GET", f"{BASE}/{p['id']}"), ("POST", f"{BASE}/{p['id']}/work-packages"),
                         ("POST", f"{BASE}/{p['id']}/handover-package")):  # fmt: skip
        assert api.call(method, path, {} if method == "POST" else None, token=t.token(acc)).status == 403
    # a designer on no team neither sees the project nor learns that it exists
    assert api.get(f"{BASE}/{p['id']}", token=t.token(t.outsider)).status == 404
    assert t.as_(t.designer).post(f"{BASE}/{p['id']}/work-packages", {"stage_code": "BOOKED", "title": "Not mine"}
                                  ).status == 403  # fmt: skip


# --- work packages -------------------------------------------------------------------------------------------------------
def test_work_is_planned_honestly_and_moves_only_by_command(team):
    t = team
    p = _booked(t)
    wp = _wp(t, p)
    assert wp["status"] == "NOT_STARTED" and wp["scheduled"] is False and wp["planned_start"] is None  # unscheduled
    r = _wp(t, p, status=422, planned_start=_today(5), planned_finish=_today(1))
    assert r.json["errors"][0]["field"] == "planned_finish"
    assert _wp(t, p, status=422, customer_visible=True).json["errors"][0]["field"] == "customer_label"
    assert _wp(t, p, status=422, owner_user_id=t.outsider.id).json["errors"][0]["field"] == "owner_user_id"
    api = t.as_(t.ops)
    r = api.patch(f"{BASE}/{p['id']}/work-packages/{wp['id']}", {"status": "COMPLETED"}, if_match=wp["version"])
    assert r.status == 422  # never a status picker
    # the first planned dates are planning; changing one already set is a replan with a reason
    wp = next(w for w in ok(api.patch(f"{BASE}/{p['id']}/work-packages/{wp['id']}",
                                      {"planned_start": _today(2), "planned_finish": _today(9)},
                                      if_match=wp["version"]))["work_packages"])  # fmt: skip
    assert wp["plan_revision"] == 0 and wp["scheduled"]
    r = api.patch(f"{BASE}/{p['id']}/work-packages/{wp['id']}", {"planned_finish": _today(12)}, if_match=wp["version"])
    assert r.status == 422 and r.json["errors"][0]["field"] == "reason"
    wp = next(w for w in ok(api.patch(f"{BASE}/{p['id']}/work-packages/{wp['id']}",
                                      {"planned_finish": _today(12), "reason": "Laminate delivery moved"},
                                      if_match=wp["version"]))["work_packages"])  # fmt: skip
    assert wp["plan_revision"] == 1 and wp["replan_reason"] == "Laminate delivery moved"
    replan = _events(p, "WORK_PACKAGE_REPLANNED")[0].detail
    assert replan["previous_finish"] == _today(9) and replan["planned_finish"] == _today(12)
    # a planned date passing changes nothing: no completion is inferred
    assert (
        _cmd(t, p, wp["id"], "start", {"actual_start": _today(1)}, status=422).json["errors"][0]["field"]
        == "actual_start"
    )
    wp = _cmd(t, p, wp["id"], "start", {"actual_start": _today()})
    assert wp["status"] == "IN_PROGRESS" and wp["started_by"]["id"] == t.ops.id
    assert _cmd(t, p, wp["id"], "start", {"actual_start": _today()}, status=409).code == "INVALID_STATE"
    wp = _cmd(t, p, wp["id"], "complete", {"actual_finish": _today(), "note": "Assembled and aligned"})
    assert wp["status"] == "COMPLETED" and wp["state"] == "COMPLETED" and wp["actual_finish"] == _today()
    assert _cmd(t, p, wp["id"], "reopen", {"reason": "x"}, status=422).status == 422
    wp = _cmd(t, p, wp["id"], "reopen", {"reason": "Hinge side to be swapped"})
    assert wp["status"] == "IN_PROGRESS" and wp["actual_finish"] is None
    assert _events(p, "WORK_PACKAGE_REOPENED")[0].detail["previous_finish"] == _today()
    other = _wp(t, p, title="Loft shutters")
    assert _cmd(t, p, other["id"], "cancel", {"reason": "Lofts removed from the scope"})["status"] == "CANCELLED"
    assert _cmd(t, p, other["id"], "start", {"actual_start": _today()}, status=409).code == "INVALID_STATE"


def test_dependencies_stages_and_gating_blockers_decide_when_work_may_move(team):
    t = team
    p = _booked(t)
    first = _wp(t, p, title="Site survey for carcass")
    later = _wp(t, p, title="Wardrobe installation", stage_code="INSTALLATION")
    r = _wp(t, p, status=422, title="Follows later work", depends_on_id=later["id"])  # same or an earlier stage only
    assert r.json["errors"][0]["field"] == "depends_on_id"
    second = _wp(t, p, title="Carcass assembly", depends_on_id=first["id"])
    api = t.as_(t.ops)
    r = api.patch(f"{BASE}/{p['id']}/work-packages/{first['id']}", {"depends_on_id": second["id"]},
                  if_match=first["version"])  # fmt: skip
    assert r.status == 422 and r.json["errors"][0]["code"] == "CYCLE"
    assert _cmd(t, p, second["id"], "start", {"actual_start": _today()}, status=409).code == "DEPENDENCY_OPEN"
    assert _cmd(t, p, later["id"], "start", {"actual_start": _today()}, status=409).code == "STAGE_NOT_CURRENT"
    ok(api.post(f"{BASE}/{p['id']}/blockers", {"category": "SITE", "impact": "GATING", "title": "No power on site",
                                              "responsible_party": "CUSTOMER", "customer_action": "Restore power",
                                              "blocks_stage_code": "INSTALLATION", "related_work_package_id": first["id"],
                                              "customer_summary": "Work is paused until power is restored"}), 201)  # fmt: skip
    assert _w(t, p, first["id"])["state"] == "BLOCKED"  # derived, never stored
    assert _cmd(t, p, first["id"], "start", {"actual_start": _today()}, status=409).code == "WORK_PACKAGE_BLOCKED"
    # open work keeps its stage from completing (structural, whatever the owner's gate list says)
    t.checklist(p)
    r = t.transition(p, "DESIGN_FINALISATION")
    assert r["outcome"] == "REFUSED" and {"WORK_PACKAGE_OPEN"} <= {b["code"] for b in r["transition"]["blockers"]}
    gate = next(g for g in r["transition"]["blockers"] if g["code"] == "WORK_PACKAGE_OPEN")
    assert gate["gate"] == "WORK_COMPLETE"
    b = t.get(p)["blockers"][0]
    ok(
        api.post(
            f"{BASE}/{p['id']}/blockers/{b['id']}/resolve", {"resolution": "Power restored"}, if_match=b["version"]
        )
    )
    for wp in (first, second):
        _cmd(t, p, wp["id"], "start", {"actual_start": _today()})
        _cmd(t, p, wp["id"], "complete", {"actual_finish": _today()})
    assert t.transition(p, "DESIGN_FINALISATION")["outcome"] == "COMPLETED"
    # the completed stage's work is its record
    assert _cmd(t, p, first["id"], "reopen", {"reason": "Too late now"}, status=409).code == "STAGE_COMPLETED"


# --- quality control -----------------------------------------------------------------------------------------------------
def _qc(t: Projects, p: dict, user=None, status: int = 201, **body):
    r = t.as_(user or t.ops).post(f"{BASE}/{p['id']}/qc-checks", body)
    assert r.status == status, r
    return r


def test_a_pass_in_one_room_never_hides_a_failure_in_another(team):
    t = team
    p = _booked(t)
    p = advance_to(t, p, "QUALITY_CHECK", qc=())
    spaces = [s["id"] for s in t.get(p)["spaces"]]
    fail = _qc(t, p, category="FINISH_AND_SURFACES", result="FAIL", observation="Scratch", space_id=spaces[0])
    _qc(t, p, category="FINISH_AND_SURFACES", result="PASS", space_id=spaces[1])  # another room, a newer result
    _qc(t, p, category="DIMENSIONS_AND_ALIGNMENT", result="PASS")
    t.checklist(p)
    assert t.transition(p, "SNAGGING")["outcome"] == "COMPLETED"
    codes = [b["code"] for b in t.get(p)["handover_readiness"]["blockers"]]
    assert codes.count("QC_FAILED") == 1  # the kitchen failure is still the head of its own chain
    failed = (
        fail.data["qc"]["history"][-1]
        if fail.data["qc"]["history"][-1]["result"] == "FAIL"
        else next(h for h in fail.data["qc"]["history"] if h["result"] == "FAIL")
    )
    # D1: a failure is never parked as to-be-confirmed; a recheck records a result
    r = _qc(t, p, user=t.quality, status=422, category="FINISH_AND_SURFACES", result="TO_BE_CONFIRMED",
            recheck_of_id=failed["id"])  # fmt: skip
    assert r.json["errors"][0]["code"] == "RECHECK_NEEDS_RESULT"
    # D12: a recheck keeps its chain's space
    r = _qc(t, p, user=t.quality, status=422, category="FINISH_AND_SURFACES", result="PASS",
            recheck_of_id=failed["id"], space_id=spaces[1])  # fmt: skip
    assert r.json["errors"][0]["code"] == "RECHECK_SCOPE"
    _qc(t, p, user=t.quality, category="FINISH_AND_SURFACES", result="PASS", recheck_of_id=failed["id"])
    assert "QC_FAILED" not in {b["code"] for b in t.get(p)["handover_readiness"]["blockers"]}
    chain = next(c for c in t.get(p)["qc"]["chains"] if c["root_id"] == failed["id"])
    assert chain["length"] == 2 and chain["ever_failed"] and chain["head"]["result"] == "PASS"


def test_the_qc_plan_needs_evidence_where_required_and_is_never_waived_by_not_applicable(team):
    t = team
    p = _booked(t)
    p = advance_to(t, p, "QUALITY_CHECK", qc=())
    api = t.as_(t.ops)
    d = ok(api.post(f"{BASE}/{p['id']}/qc-points", {"category": "HARDWARE_AND_OPERATION", "label": "Soft-close hinges",
                                                   "evidence_required": True}), 201)  # fmt: skip
    pt = d["qc"]["points"][-1]
    spare = ok(api.post(f"{BASE}/{p['id']}/qc-points", {"category": "OTHER", "label": "Spare check"}), 201)["qc"][
        "points"
    ][-1]
    r = api.post(
        f"{BASE}/{p['id']}/qc-points/{spare['id']}/withdraw", {"reason": "Duplicate"}, if_match=spare["version"]
    )
    assert ok(r)["qc"]["points"][-1]["status"] == "WITHDRAWN"
    for cat in ("DIMENSIONS_AND_ALIGNMENT", "FINISH_AND_SURFACES"):
        _qc(t, p, category=cat, result="PASS")
    t.checklist(p)
    r = t.transition(p, "SNAGGING")
    assert r["outcome"] == "REFUSED" and {b["code"] for b in r["transition"]["blockers"]} == {"QC_POINT_NOT_RECORDED"}
    r = _qc(t, p, status=422, category="HARDWARE_AND_OPERATION", result="PASS", qc_point_id=pt["id"])
    assert r.json["errors"][0]["code"] == "EVIDENCE_REQUIRED"
    r = _qc(t, p, status=409, category="HARDWARE_AND_OPERATION", result="NOT_APPLICABLE", qc_point_id=pt["id"],
            observation="Hinges not fitted here")  # fmt: skip
    assert r.code == "NOT_APPLICABLE_ON_PLANNED_CHECK"  # D2
    att = photo(t.as_(t.founder), "property", p["property"]["id"])
    _qc(t, p, category="HARDWARE_AND_OPERATION", result="PASS", qc_point_id=pt["id"], evidence_attachment_id=att["id"])
    r = api.post(
        f"{BASE}/{p['id']}/qc-points/{pt['id']}/withdraw",
        {"reason": "Not needed"},
        if_match=t.get(p)["qc"]["points"][0]["version"],
    )
    assert r.status == 409 and r.code == "QC_POINT_HAS_RESULT"
    assert t.transition(p, "SNAGGING")["outcome"] == "COMPLETED"


def test_failed_work_is_correction_required_and_stops_the_stage_until_rechecked(team):
    t = team
    p = _booked(t)
    p = advance_to(t, p, "INSTALLATION")
    wp = _wp(t, p, title="Wardrobe installation", customer_label="Wardrobes", customer_visible=True)
    r = _qc(t, p, status=409, category="FINISH_AND_SURFACES", result="PASS", work_package_id=wp["id"])
    assert r.code == "WORK_NOT_COMPLETED"  # work is checked once it is done
    _cmd(t, p, wp["id"], "start", {"actual_start": _today()})
    _cmd(t, p, wp["id"], "complete", {"actual_finish": _today()})
    d = _qc(
        t, p, category="FINISH_AND_SURFACES", result="FAIL", observation="Shutter gap", work_package_id=wp["id"]
    ).data
    failed = next(h for h in d["qc"]["history"] if h["result"] == "FAIL")
    assert _w(t, p, wp["id"])["state"] == "CORRECTION_REQUIRED"
    t.checklist(p)
    r = t.transition(p, "QUALITY_CHECK")
    assert r["outcome"] == "REFUSED" and {b["code"] for b in r["transition"]["blockers"]} == {"WORK_PACKAGE_QC_FAILED"}
    _qc(t, p, user=t.quality, category="FINISH_AND_SURFACES", result="PASS", recheck_of_id=failed["id"])
    assert _w(t, p, wp["id"])["state"] == "COMPLETED"
    assert t.transition(p, "QUALITY_CHECK")["outcome"] == "COMPLETED"


# --- snags ---------------------------------------------------------------------------------------------------------------
def _snag(t: Projects, p: dict, **body) -> dict:
    d = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/snags", {"category": "FINISH", "customer_title": "Chipped edge", **body}),
           201)  # fmt: skip
    return d["snags"][-1]


def _move(t: Projects, p: dict, snag_id: str, user, expect: int = 200, **body):
    cur = next(x for x in t.get(p)["snags"] if x["id"] == snag_id)
    r = t.as_(user).post(f"{BASE}/{p['id']}/snags/{snag_id}/status", body, if_match=cur["version"])
    assert r.status == expect, r
    return r


def test_no_one_verifies_a_fix_they_made_in_any_fix_cycle_or_a_snag_they_own(team):
    t = team
    p = _booked(t)
    p = advance_to(t, p, "SNAGGING")
    sn = _snag(t, p)
    assert _move(t, p, sn["id"], t.ops, 409, status="IN_PROGRESS").code == "SNAG_UNASSIGNED"
    ok(t.as_(t.ops).patch(f"{BASE}/{p['id']}/snags/{sn['id']}", {"owner_user_id": t.ops.id}, if_match=sn["version"]))
    _move(t, p, sn["id"], t.ops, status="IN_PROGRESS")
    _move(t, p, sn["id"], t.ops, status="READY_FOR_RECHECK", note="Edge filled")
    t.factory.grant(t.ops, "project.verify_snag", scope="OWN")  # even holding the capability
    t.ops.token = None
    assert _move(t, p, sn["id"], t.ops, 409, status="RESOLVED", note="Fine").code == "SEGREGATION_REQUIRED"
    _move(t, p, sn["id"], t.quality, status="IN_PROGRESS", note="Edge still rough")  # the recheck failed
    assert _events(p, "SNAG_RECHECK_FAILED")
    # a second fix cycle, owned and fixed by someone else: the first fixer still never verifies, nor does the owner
    ok(t.as_(t.ops).patch(f"{BASE}/{p['id']}/snags/{sn['id']}", {"owner_user_id": t.founder.id},
                          if_match=next(x for x in t.get(p)["snags"] if x["id"] == sn["id"])["version"]))  # fmt: skip
    _move(t, p, sn["id"], t.founder, status="READY_FOR_RECHECK", note="Edge refilled and sanded")
    assert _move(t, p, sn["id"], t.ops, 409, status="RESOLVED", note="Fine").code == "SEGREGATION_REQUIRED"
    assert _move(t, p, sn["id"], t.founder, 409, status="RESOLVED", note="Fine").code == "SEGREGATION_REQUIRED"
    d = _move(t, p, sn["id"], t.quality, status="RESOLVED", note="Rechecked: smooth").data
    assert next(x for x in d["snags"] if x["id"] == sn["id"])["resolved_by"]["id"] == t.quality.id
    fixers = {e.created_by for e in _events(p, "SNAG_FIXED")}
    assert fixers == {t.ops.id, t.founder.id}  # every fix stays on the immutable timeline


def test_a_snag_is_closed_without_a_fix_only_for_a_reason_by_a_verifier(team):
    t = team
    p = _booked(t)
    p = advance_to(t, p, "SNAGGING")
    sn = _snag(t, p, owner_user_id=t.ops.id)
    assert _move(t, p, sn["id"], t.ops, 403, status="CLOSED", note="Not real").status == 403
    r = _move(t, p, sn["id"], t.quality, 422, status="CLOSED", note="Not real")
    assert r.json["errors"][0]["field"] == "closure_code"
    d = _move(t, p, sn["id"], t.quality, status="CLOSED", note="Same as snag 1", closure_code="NOT_A_DEFECT").data
    assert d["snags"][-1]["closure_code"] == "NOT_A_DEFECT" and d["snags"][-1]["status"] == "CLOSED"
    assert _events(p, "SNAG_CLOSED")[0].detail["closure_code"] == "NOT_A_DEFECT"


# --- customer reports (staff channel) ------------------------------------------------------------------------------------
def test_a_customer_report_is_triaged_never_assumed_and_holds_the_handover_until_reviewed(team):
    t = team
    p = _booked(t)
    p = advance_to(t, p, "SNAGGING")
    api = t.as_(t.ops)
    d = ok(api.post(f"{BASE}/{p['id']}/customer-reports", {"description": "The bedroom wardrobe door rubs the floor",
                                                          "area": "Bedroom 1"}), 201)  # fmt: skip
    rep = d["customer_reports"][-1]
    assert rep["status"] == "SUBMITTED" and rep["channel"] == "STAFF" and d["snags"] == []  # not a defect yet
    assert {b["code"] for b in t.get(p)["handover_readiness"]["blockers"]} >= {"CUSTOMER_REPORT_UNTRIAGED"}
    url = f"{BASE}/{p['id']}/customer-reports/{rep['id']}/triage"
    r = api.post(
        url, {"outcome": "DECLINED", "decline_code": "NOT_A_DEFECT", "response": "short"}, if_match=rep["version"]
    )
    assert r.status == 422 and r.json["errors"][0]["field"] == "response"
    d = ok(api.post(url, {"outcome": "NEW_SNAG", "snag": {"category": "ALIGNMENT", "customer_title": "Wardrobe door "
                                                          "rubbing the floor", "owner_user_id": t.ops.id}},
                    if_match=rep["version"]))  # fmt: skip
    sn = d["snags"][-1]
    assert sn["source"] == "CUSTOMER" and sn["customer_visible"] is True
    assert d["customer_reports"][-1]["status"] == "ACCEPTED" and d["customer_reports"][-1]["snag_id"] == sn["id"]
    assert api.post(url, {"outcome": "DECLINED", "decline_code": "DUPLICATE", "response": "Already recorded"},
                    if_match=d["customer_reports"][-1]["version"]).code == "INVALID_STATE"  # fmt: skip
    r = api.patch(f"{BASE}/{p['id']}/snags/{sn['id']}", {"customer_visible": False}, if_match=sn["version"])
    assert r.status == 409 and r.code == "CUSTOMER_REPORTED"  # the customer keeps following what they reported
    assert "CUSTOMER_REPORT_UNTRIAGED" not in {b["code"] for b in t.get(p)["handover_readiness"]["blockers"]}


# --- commercial condition ------------------------------------------------------------------------------------------------
def test_the_commercial_condition_fails_closed_until_decided_and_when_unverifiable(team):
    t = team
    p = _booked(t)
    delivery(pex_d02=None)
    blockers = t.get(p)["handover_readiness"]["blockers"]
    assert {(b["code"], b.get("decision")) for b in blockers if b["gate"] == "COMMERCIAL_CONDITION"} == {
        ("OWNER_DECISION_REQUIRED", "PEX-D02")
    }
    delivery(pex_d02="FULLY_PAID")  # Project Commercials is off in this module
    assert {b["code"] for b in t.get(p)["handover_readiness"]["blockers"]} >= {"COMMERCIAL_POSITION_UNAVAILABLE"}
    delivery(pex_d02="NONE")
    assert not [b for b in t.get(p)["handover_readiness"]["blockers"] if b["gate"] == "COMMERCIAL_CONDITION"]


# --- handover package ----------------------------------------------------------------------------------------------------
def test_the_handover_package_is_prepared_only_when_ready_frozen_and_rechecked_at_approval(team):
    t = team
    p = _booked(t)
    wp = _wp(t, p, title="Kitchen fit-out", customer_label="Kitchen", customer_visible=True)
    _cmd(t, p, wp["id"], "start", {"actual_start": _today()})
    _cmd(t, p, wp["id"], "complete", {"actual_finish": _today()})
    hidden = _wp(t, p, title="Internal electrical rework")
    _cmd(t, p, hidden["id"], "start", {"actual_start": _today()})
    _cmd(t, p, hidden["id"], "complete", {"actual_finish": _today()})
    assert t.package(p, status=409).code == "INVALID_STATE"  # not before READY_FOR_HANDOVER
    p = advance_to(t, p, "READY_FOR_HANDOVER")
    r = t.package(p, status=409)
    assert r.code == "HANDOVER_NOT_READY" and {b["code"] for b in r.json["blockers"]} == {"CHECKLIST_ITEM_OPEN"}
    t.checklist(p)
    d = t.package(p)
    pkg = d["handover_packages"][-1]
    c = pkg["content"]
    assert [w["label"] for w in c["work"]["completed"]] == ["Kitchen"] and c["work"]["completed_count"] == 2
    assert c["documents"] == [] and set(c["warranty"]) == {"source", "quotation_id", "quotation_number"}
    assert "Internal electrical rework" not in str(c)
    assert len(t.package(p, status=200)["handover_packages"]) == 1  # nothing changed: the same package
    # D5: four-eyes on the handover; the package changes before the approval, so the approval is refused
    install(synthetic_policy(PLB_OD_03={"lifecycle_version": lifecycle.current().version,
                                        "transitions": ["READY_FOR_HANDOVER>HANDED_OVER"]}))  # fmt: skip
    att = photo(t.as_(t.founder), "property", p["property"]["id"])
    body = {"handover_on": _today(), "acknowledgement_reference": "HS-9", "evidence_attachment_id": att["id"]}
    r = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/handover", body, if_match=t.get(p)["version"]), 201)
    assert r["outcome"] == "AWAITING_APPROVAL"
    tr = r["transition"]
    _snag(t, p, is_blocking=False, customer_visible=True, customer_title="Touch-up on the skirting")
    r = t.as_(t.approver).post(f"{BASE}/{p['id']}/transitions/{tr['id']}/approve", {},
                               if_match=next(x for x in t.get(p)["transitions"] if x["id"] == tr["id"])["version"])  # fmt: skip
    assert r.status == 409 and r.code == "GATES_NOT_SATISFIED"
    assert {b["code"] for b in r.json["blockers"]} == {"HANDOVER_PACKAGE_STALE"}
    assert t.get(p)["handover_packages"][-1]["stale"] == "HANDOVER_PACKAGE_STALE"
    w = next(x for x in t.get(p)["transitions"] if x["id"] == tr["id"])
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/transitions/{tr['id']}/withdraw", {"reason": "Package changed"},
                         if_match=w["version"]))  # fmt: skip
    d = t.package(p)
    assert [x["status"] for x in d["handover_packages"]] == ["SUPERSEDED", "PREPARED"]
    assert d["handover_packages"][-1]["content"]["snags"]["open_non_blocking"] == [
        {"number": 1, "title": "Touch-up on the skirting"}
    ]
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/handover", body, if_match=t.get(p)["version"]), 201)
    tr = t.get(p)["awaiting_approval"]
    r = ok(t.as_(t.approver).post(f"{BASE}/{p['id']}/transitions/{tr['id']}/approve", {}, if_match=tr["version"]))
    assert r["outcome"] == "COMPLETED" and r["project"]["handover_packages"][-1]["status"] == "COMPLETED"
