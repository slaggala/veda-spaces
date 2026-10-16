"""Project lifecycle: explicit transitions, stage gates, fail-closed policy, four-eyes, ownership and project scope
(PLB-04 … PLB-09, PLB-19, PLB-32 … PLB-35). SYNTHETIC data and SYNTHETIC lifecycle policy only."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ok
from tests.support.project import BASE, ON, Projects, install, synthetic_policy
from veda.modules.project.models import ProjectTransition

pytestmark = ON


@pytest.fixture
def team(api, factory):
    t = Projects(api, factory)
    prop, _, q = t.accepted()
    t.p = t.book(q, prop)  # type: ignore[attr-defined]  # the booked project, for each test
    t.prop, t.q = prop, q  # type: ignore[attr-defined]
    yield t
    install(None)


def _codes(r: dict) -> set[str]:
    return {b["code"] for b in r["transition"]["blockers"]}


# --- explicit commands and fail-closed policy ---------------------------------------------------------------------------
def test_without_owner_policy_a_standard_move_uses_strict_defaults_and_high_risk_is_refused(team):
    t, p = team, team.p
    t.staff(p)
    r = t.transition(p, "DESIGN_FINALISATION")
    assert r["outcome"] == "REFUSED" and _codes(r) == {"CHECKLIST_ITEM_OPEN"}  # strict default: every item required
    p = t.advance(p, "DESIGN_FINALISATION")
    assert p["stage"]["code"] == "DESIGN_FINALISATION"
    t.checklist(p)
    r = t.transition(p, "SCOPE_FROZEN")  # HIGH risk: PLB-OD-01/02/03 undecided -> refused, named exactly
    assert r["outcome"] == "REFUSED"
    decisions = {b.get("decision") for b in r["project"]["transitions"][0]["blockers"]} - {None}
    policy_blockers = [b for b in r["transition"]["blockers"] if b["gate"] == "POLICY_RECORDED"]
    assert len(policy_blockers) == 3 and all(b["code"] == "OWNER_DECISION_REQUIRED" for b in policy_blockers)
    assert not decisions or decisions <= {"PLB-OD-01", "PLB-OD-02", "PLB-OD-03"}
    assert r["project"]["stage"]["code"] == "DESIGN_FINALISATION"
    assert r["project"]["lifecycle"]["status"] == "PROPOSED"


def test_a_refused_request_is_recorded_with_its_exact_blockers(team):
    t, p = team, team.p
    t.staff(p)
    r = t.transition(p, "DESIGN_FINALISATION", reason="Trying early")
    assert r["outcome"] == "REFUSED"
    rows = dbh.rows(sa.select(ProjectTransition))
    assert len(rows) == 1 and rows[0].outcome == "REFUSED" and rows[0].reason == "Trying early"
    assert len(rows[0].evaluation_sha256) == 64
    assert {b["code"] for b in rows[0].evaluation["blockers"]} == {"CHECKLIST_ITEM_OPEN"}
    assert "TRANSITION_REFUSED" in [e["code"] for e in r["project"]["timeline"]]


def test_stages_move_only_forward_one_at_a_time_and_never_by_editing(team):
    t, p = team, team.p
    t.staff(p)
    t.checklist(p)
    r = t.transition(p, "SCOPE_FROZEN")  # skipping a stage
    assert r["outcome"] == "REFUSED" and _codes(r) == {"NOT_NEXT_STAGE"}
    r = t.transition(p, "HANDED_OVER")
    assert r["outcome"] == "REFUSED" and "NOT_NEXT_STAGE" in _codes(r)
    api = t.as_(t.ops)
    cur = t.get(p)
    for method in ("PATCH", "PUT"):  # there is no "set the status" route
        assert api.call(
            method, f"{BASE}/{p['id']}", {"stage_code": "INSTALLATION"}, if_match=cur["version"]
        ).status in (404, 405)
    assert t.transition(p, "NOT_A_STAGE", status=422).code == "VALIDATION_FAILED"
    assert t.get(p)["stage"]["code"] == "BOOKED"


def test_a_stale_screen_cannot_move_the_project(team):
    t, p = team, team.p
    t.staff(p)
    t.checklist(p)
    stale = t.get(p)["version"]
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/blockers", {"category": "OTHER", "impact": "INFORMATIONAL",
                                                       "title": "Note for the team", "responsible_party": "VEDA"}), 201)  # fmt: skip
    r = t.as_(t.ops).post(f"{BASE}/{p['id']}/transitions", {"to_stage": "DESIGN_FINALISATION"}, if_match=stale)
    assert r.status == 409 and r.code == "VERSION_CONFLICT"
    assert t.as_(t.ops).post(f"{BASE}/{p['id']}/transitions", {"to_stage": "DESIGN_FINALISATION"}).status == 428


# --- gates -------------------------------------------------------------------------------------------------------------
def test_the_owner_of_the_next_stage_must_be_assigned(team):
    t, p = team, team.p
    t.team(p, t.ops, "PROJECT")
    t.checklist(p)
    r = t.transition(p, "DESIGN_FINALISATION")
    assert r["outcome"] == "REFUSED"
    assert [b["responsibility"] for b in r["transition"]["blockers"] if b["code"] == "OWNER_MISSING"] == ["DESIGN"]


def test_informational_issues_never_block_and_gating_blockers_do_until_resolved(team):
    t, p = team, team.p
    t.staff(p)
    t.checklist(p)
    api = t.as_(t.ops)
    ok(api.post(f"{BASE}/{p['id']}/blockers", {"category": "OTHER", "impact": "INFORMATIONAL", "title": "FYI only",
                                               "responsible_party": "VEDA"}), 201)  # fmt: skip
    gate = {"category": "CUSTOMER_DECISION", "impact": "GATING", "title": "Appliance specifications required",
            "responsible_party": "CUSTOMER", "blocks_stage_code": "DESIGN_FINALISATION"}  # fmt: skip
    r = api.post(f"{BASE}/{p['id']}/blockers", gate)
    assert r.status == 422 and r.json["errors"][0]["field"] == "customer_action"
    r = api.post(f"{BASE}/{p['id']}/blockers", {**gate, "impact": "GATING", "blocks_stage_code": None,
                                                "customer_action": "Share the appliance models"})  # fmt: skip
    assert r.status == 422 and r.json["errors"][0]["field"] == "blocks_stage_code"
    d = ok(api.post(f"{BASE}/{p['id']}/blockers", {**gate, "customer_action": "Share the appliance models"}), 201)
    blocker = next(b for b in d["blockers"] if b["impact"] == "GATING")
    attention = d["attention"][0]
    assert attention["severity"] == "GATING" and attention["who"] == "CUSTOMER"
    assert attention["action"] == "Share the appliance models" and attention["blocks"] == "DESIGN_FINALISATION"
    r = t.transition(p, "DESIGN_FINALISATION")
    assert r["outcome"] == "REFUSED" and _codes(r) == {"GATING_BLOCKER_OPEN"}
    assert "Appliance" not in str(dbh.rows(sa.select(ProjectTransition))[-1].evaluation)  # no staff text recorded
    cur = t.get(p)
    b = next(x for x in cur["blockers"] if x["id"] == blocker["id"])
    assert (
        t.as_(t.ops)
        .post(f"{BASE}/{p['id']}/blockers/{b['id']}/resolve", {"resolution": "ok"}, if_match=b["version"])
        .status
        == 422
    )  # a resolution says how (5+ characters)
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/blockers/{b['id']}/resolve", {"resolution": "Models received"},
                         if_match=b["version"]))  # fmt: skip
    assert t.transition(p, "DESIGN_FINALISATION")["outcome"] == "COMPLETED"


def test_a_gating_blocker_for_an_earlier_stage_still_stops_every_later_move(team):
    t, p = team, team.p
    t.staff(p)
    p = t.advance(p, "DESIGN_FINALISATION")
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/blockers", {"category": "SITE", "impact": "GATING",
                                                       "title": "Wall dampness found", "responsible_party": "VEDA",
                                                       "blocks_stage_code": "BOOKED"}), 201)  # fmt: skip
    t.checklist(p)
    install(synthetic_policy())
    assert "GATING_BLOCKER_OPEN" in _codes(t.transition(p, "SCOPE_FROZEN"))


def test_checklist_items_need_a_reason_and_the_permission_to_be_not_applicable(team):
    t, p = team, team.p
    t.staff(p)
    p = t.advance(p, "DESIGN_FINALISATION")
    item = next(g for g in t.get(p)["checklist"] if g["stage_code"] == "DESIGN_FINALISATION")["items"][0]
    url = f"{BASE}/{p['id']}/checklist/{item['id']}"
    designer = t.as_(t.designer)  # the design owner (OWN): may complete, may not waive a required item
    r = designer.post(f"{url}/complete", {"state": "NOT_APPLICABLE", "not_applicable_reason": "No design here"},
                      if_match=item["version"])  # fmt: skip
    assert r.status == 403 and r.json["permission"] == "project.checklist.not_applicable"
    r = t.as_(t.ops).post(f"{url}/complete", {"state": "NOT_APPLICABLE"}, if_match=item["version"])
    assert r.status == 422 and r.json["errors"][0]["field"] == "not_applicable_reason"
    d = ok(t.as_(t.ops).post(f"{url}/complete", {"state": "NOT_APPLICABLE", "not_applicable_reason": "Kitchen only "
                                                 "job; no design approvals"}, if_match=item["version"]))  # fmt: skip
    done = next(i for g in d["checklist"] for i in g["items"] if i["id"] == item["id"])
    assert done["state"] == "NOT_APPLICABLE" and done["completed_by"]["id"] == t.ops.id
    assert t.as_(t.ops).post(f"{url}/reopen", {"reason": "x"}, if_match=done["version"]).status == 422
    d = ok(t.as_(t.designer).post(f"{url}/reopen", {"reason": "Approval did happen after all"},
                                  if_match=done["version"]))  # fmt: skip
    again = next(i for g in d["checklist"] for i in g["items"] if i["id"] == item["id"])
    assert again["state"] == "OPEN" and again["reopen_reason"] == "Approval did happen after all"
    codes = [e["code"] for e in d["timeline"]]
    assert "CHECKLIST_ITEM_NOT_APPLICABLE" in codes and codes[-1] == "CHECKLIST_ITEM_REOPENED"
    booked = next(g for g in d["checklist"] if g["stage_code"] == "BOOKED")["items"][0]
    r = t.as_(t.ops).post(f"{BASE}/{p['id']}/checklist/{booked['id']}/reopen", {"reason": "Change history"},
                          if_match=booked["version"])  # fmt: skip
    assert r.status == 409 and r.code == "STAGE_COMPLETED"  # a completed stage's record is closed


def test_milestones_keep_planned_actual_and_promised_dates_apart_and_complete_explicitly(team):
    t, p = team, team.p
    # a customer-promised date needs owner decision PLB-OD-13 (M1): a SYNTHETIC one naming the milestone capability
    install(synthetic_policy(PLB_OD_13={"capability": "project.manage_milestone", "reference": "SYNTHETIC"}))
    t.staff(p)
    api = t.as_(t.ops)
    d = ok(api.post(f"{BASE}/{p['id']}/milestones", {"milestone_code": "DESIGN_SIGN_OFF", "label": "Design sign-off",
                                                    "stage_code": "BOOKED", "planned_date": "2026-01-10",
                                                    "customer_promised_date": "2026-01-20"}), 201)  # fmt: skip
    m = d["milestones"][0]
    assert m["status"] == "PLANNED" and m["overdue"] is True and m["actual_date"] is None  # never inferred complete
    assert m["planned_date"] != m["customer_promised_date"] and d["next_milestone"]["overdue"] is True
    t.checklist(p)
    r = t.transition(p, "DESIGN_FINALISATION")
    assert _codes(r) == {"MILESTONE_OPEN"}
    url = f"{BASE}/{p['id']}/milestones/{m['id']}"
    assert api.post(f"{url}/complete", {"actual_date": "2999-01-01"}, if_match=m["version"]).status == 422
    d = ok(api.post(f"{BASE}/{p['id']}/milestones", {"milestone_code": "OTHER", "label": "Second step",
                                                    "stage_code": "BOOKED", "depends_on_milestone_id": m["id"]}), 201)  # fmt: skip
    second = next(x for x in d["milestones"] if x["label"] == "Second step")
    r = api.post(f"{BASE}/{p['id']}/milestones/{second['id']}/complete", {"actual_date": "2026-01-11"},
                 if_match=second["version"])  # fmt: skip
    assert r.status == 409 and r.code == "DEPENDENCY_OPEN"
    r = api.patch(f"{BASE}/{p['id']}/milestones/{second['id']}", {"status": "NOT_APPLICABLE"},
                  if_match=second["version"])  # fmt: skip
    assert r.status == 422 and r.json["errors"][0]["field"] == "status_reason"
    ok(api.patch(f"{BASE}/{p['id']}/milestones/{second['id']}", {"status": "NOT_APPLICABLE",
                 "status_reason": "Merged into sign-off"}, if_match=second["version"]))  # fmt: skip
    cur = next(x for x in t.get(p)["milestones"] if x["id"] == m["id"])
    d = ok(api.post(f"{url}/complete", {"actual_date": "2026-01-12"}, if_match=cur["version"]))
    done = next(x for x in d["milestones"] if x["id"] == m["id"])
    assert done["status"] == "COMPLETED" and done["actual_date"] == "2026-01-12"
    assert done["customer_promised_date"] == "2026-01-20" and done["planned_date"] == "2026-01-10"
    assert t.transition(p, "DESIGN_FINALISATION")["outcome"] == "COMPLETED"


# --- four-eyes ---------------------------------------------------------------------------------------------------------
def _to_snagging(t: Projects, p: dict) -> dict:
    install(synthetic_policy(PLB_OD_03={"lifecycle_version": t.get(p)["lifecycle"]["version"], "transitions": []}))
    t.staff(p)
    for to in ("DESIGN_FINALISATION", "SCOPE_FROZEN", "SITE_READINESS"):
        p = t.advance(p, to)
    t.ready_site(p)
    for to in ("PRODUCTION_READINESS", "IN_PRODUCTION", "READY_FOR_INSTALLATION", "INSTALLATION", "QUALITY_CHECK"):
        p = t.advance(p, to)
    api = t.as_(t.ops)
    for cat in ("DIMENSIONS_AND_ALIGNMENT", "FINISH_AND_SURFACES"):
        ok(api.post(f"{BASE}/{p['id']}/qc-checks", {"category": cat, "result": "PASS"}), 201)
    p = t.advance(p, "SNAGGING")
    install(synthetic_policy())  # four-eyes on SNAGGING>READY_FOR_HANDOVER
    return p


def test_a_high_risk_move_waits_for_an_independent_approval_and_is_re_evaluated(team):
    t, p = team, team.p
    p = _to_snagging(t, p)
    t.checklist(p)
    r = t.transition(p, "READY_FOR_HANDOVER")
    assert r["outcome"] == "AWAITING_APPROVAL" and r["project"]["stage"]["code"] == "SNAGGING"
    tr = r["transition"]
    url = f"{BASE}/{p['id']}/transitions/{tr['id']}"
    assert t.transition(p, "READY_FOR_HANDOVER")["outcome"] == "REFUSED"  # one pending request at a time
    tr = next(x for x in t.get(p)["transitions"] if x["id"] == tr["id"])
    founder_requested = t.as_(t.ops).post(f"{url}/approve", {}, if_match=tr["version"])
    assert founder_requested.status == 403  # ops lacks the approval capability
    t.factory.grant(t.ops, "project.approve_transition")
    r = t.as_(t.ops).post(f"{url}/approve", {}, if_match=tr["version"])
    assert r.status == 409 and r.code == "FOUR_EYES_REQUIRED"
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/snags", {"category": "FINISH", "customer_title": "Chipped shutter edge"}),
       201)  # a blocking snag appears after the request  # fmt: skip
    r = t.as_(t.approver).post(f"{url}/approve", {}, if_match=tr["version"])
    assert (
        r.status == 409 and r.code == "GATES_NOT_SATISFIED" and {b["code"] for b in r.json["blockers"]} == {"SNAG_OPEN"}
    )
    snag = t.get(p)["snags"][0]
    surl = f"{BASE}/{p['id']}/snags/{snag['id']}"
    # closing a snag without a fix is a verification: a reason code, a note, and the verify capability (PEX)
    r = t.as_(t.ops).post(f"{surl}/status", {"status": "CLOSED", "note": "Logged twice by mistake"},
                          if_match=snag["version"])  # fmt: skip
    assert r.status == 403
    r = t.as_(t.quality).post(f"{surl}/status", {"status": "CLOSED", "note": "Logged twice by mistake"},
                              if_match=snag["version"])  # fmt: skip
    assert r.status == 422 and r.json["errors"][0]["field"] == "closure_code"
    ok(t.as_(t.quality).post(f"{surl}/status", {"status": "CLOSED", "note": "Logged twice by mistake",
                                                "closure_code": "DUPLICATE"}, if_match=snag["version"]))  # fmt: skip
    r = ok(t.as_(t.approver).post(f"{url}/approve", {"reason": "Checked on site"}, if_match=tr["version"]))
    assert r["outcome"] == "COMPLETED" and r["project"]["stage"]["code"] == "READY_FOR_HANDOVER"
    assert r["transition"]["decided_by"]["id"] == t.approver.id and r["transition"]["requested_by"]["id"] == t.ops.id
    entered = [e for e in r["project"]["timeline"] if e["code"] == "STAGE_ENTERED"][-1]
    assert entered["detail"]["approved_by"] == t.approver.id
    assert "HANDOVER_READY" in [e["code"] for e in r["project"]["timeline"]]


def test_a_pending_approval_can_be_rejected_or_withdrawn_with_a_reason(team):
    t, p = team, team.p
    p = _to_snagging(t, p)
    t.checklist(p)
    tr = t.transition(p, "READY_FOR_HANDOVER")["transition"]
    url = f"{BASE}/{p['id']}/transitions/{tr['id']}"
    assert t.as_(t.approver).post(f"{url}/reject", {"reason": "no"}, if_match=tr["version"]).status == 422
    r = ok(t.as_(t.approver).post(f"{url}/reject", {"reason": "Walkthrough not yet done"}, if_match=tr["version"]))
    assert r["outcome"] == "REJECTED" and r["project"]["stage"]["code"] == "SNAGGING"
    tr = t.transition(p, "READY_FOR_HANDOVER")["transition"]
    r = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/transitions/{tr['id']}/withdraw", {"reason": "Raised too early"},
                             if_match=tr["version"]))  # fmt: skip
    assert r["outcome"] == "WITHDRAWN"
    r = t.as_(t.approver).post(
        f"{BASE}/{p['id']}/transitions/{tr['id']}/approve", {}, if_match=r["transition"]["version"]
    )
    assert r.status == 409 and r.code == "INVALID_STATE"


# --- ownership, team and project scope ---------------------------------------------------------------------------------
def test_owners_are_validated_unique_per_responsibility_and_audited(team):
    t, p = team, team.p
    r = t.team(p, t.surveyor, "QUALITY", status=422)  # a surveyor cannot record quality checks
    assert r.json["errors"][0]["code"] == "NOT_ELIGIBLE"
    t.team(p, t.ops, "PROJECT")
    other = t.factory.user("ESTIMATOR")
    for code in ("project.view", "project.manage_stage"):
        t.factory.grant(other, code, scope="OWN")
    assert t.team(p, other, "PROJECT", status=422).json["errors"][0]["field"] == "reason"  # replacing needs a reason
    d = t.team(p, other, "PROJECT", reason="Ops lead changed for this site")
    owners = [m for m in d["team"] if m["responsibility"] == "PROJECT"]
    assert [(m["user"]["id"], m["active"]) for m in owners] == [(t.ops.id, False), (other.id, True)]
    assert d["owner"]["id"] == other.id
    assert t.team(p, other, "PROJECT", status=409).code == "ALREADY_ASSIGNED"
    codes = [e["code"] for e in d["timeline"]]
    assert codes.count("OWNER_ASSIGNED") == 2 and "MEMBER_REMOVED" in codes
    assert t.team(p, t.designer, "MEMBER", by=t.designer, status=403).code == "PERMISSION_DENIED"


def test_project_scope_needs_both_the_capability_and_team_membership(team):
    t, p = team, team.p
    # OWN holders see only projects whose team they are on; a guessed or known id discloses nothing
    for user in (t.ops, t.outsider, t.designer):
        assert t.as_(user).get(f"{BASE}/{p['id']}").status == 404
        assert ok(t.as_(user).get(BASE))["projects"] == []
    t.staff(p)
    assert t.as_(t.designer).get(f"{BASE}/{p['id']}").status == 200
    assert t.as_(t.outsider).get(f"{BASE}/{p['id']}").status == 404
    # membership grants no capability: the surveyor (member) cannot complete checklists
    item = t.get(p)["checklist"][0]["items"][0]
    r = t.as_(t.surveyor).post(f"{BASE}/{p['id']}/checklist/{item['id']}/complete", {"state": "DONE"},
                               if_match=item["version"])  # fmt: skip
    assert r.status == 403
    # an id of another project's row is not found through this project (no cross-project update)
    prop2, _, q2 = t.accepted("3BHK")
    p2 = t.book(q2, prop2)
    t.team(p2, t.ops, "PROJECT")
    other_item = t.get(p2)["checklist"][0]["items"][0]
    r = t.as_(t.ops).post(f"{BASE}/{p['id']}/checklist/{other_item['id']}/complete", {"state": "DONE"},
                          if_match=other_item["version"])  # fmt: skip
    assert r.status == 404
    # an ended assignment ends the access
    m = next(x for x in t.get(p)["team"] if x["user"]["id"] == t.designer.id)
    ok(t.as_(t.manager).post(f"{BASE}/{p['id']}/team/{m['id']}/remove", {"reason": "Moved to another site"},
                             if_match=m["version"]))  # fmt: skip
    assert t.as_(t.designer).get(f"{BASE}/{p['id']}").status == 404


def test_commercial_amounts_and_the_audit_trail_need_their_own_capabilities(team):
    t, p = team, team.p
    t.staff(p)
    designer_view = t.get(p, t.designer)
    lineage = designer_view["baseline"]["lineage"][0]
    assert designer_view["baseline"]["full"] is False
    assert "accepted_total_minor" not in lineage and "baseline_sha256" not in lineage
    assert "evaluation" not in str(designer_view["transitions"])
    assert t.as_(t.designer).get(f"{BASE}/{p['id']}/history").status == 403
    history = ok(t.as_(t.ops).get(f"{BASE}/{p['id']}/history"))
    assert {h["entity_type"] for h in history} >= {"project", "project_member", "project_stage", "project_baseline"}
    assert all(set(h) == {"entity_type", "entity_id", "action", "changed_fields", "by", "on", "via"} for h in history)
    assert t.get(p, t.ops)["baseline"]["lineage"][0]["accepted_total_minor"] > 0


def test_team_candidates_and_evidence_options_stay_within_the_project(team):
    from tests.support.mtq import photo

    t, p = team, team.p
    cands = ok(t.as_(t.manager).get(f"{BASE}/{p['id']}/team/candidates"))
    by_id = {c["id"]: c for c in cands}
    assert set(by_id[t.ops.id]["responsibilities"]) >= {"PROJECT", "SITE", "QUALITY", "HANDOVER", "MEMBER"}
    assert by_id[t.designer.id]["responsibilities"] == ["DESIGN", "MEMBER"]
    assert set(by_id[t.ops.id]) == {"id", "display_name", "responsibilities"}  # names only
    assert t.as_(t.designer).get(f"{BASE}/{p['id']}/team/candidates").status == 403
    t.staff(p)
    att = photo(t.as_(t.founder), "property", t.prop["id"])
    options = t.get(p, t.ops)["evidence_options"]
    assert options[0]["id"] == att["id"]  # newest first; the site's measurement photos are citable too
    assert all(set(o) == {"id", "category", "attached_to", "uploaded_on"} for o in options)
    assert t.get(p, t.surveyor)["evidence_options"] == [o for o in options]  # a member who records site readiness
    assert t.as_(t.c.sales).get(f"{BASE}/{p['id']}").status == 404  # owns the lead, not on the team: not disclosed
    assert t.get(p, t.approver)["evidence_options"] == []  # sees every project, records no evidence
