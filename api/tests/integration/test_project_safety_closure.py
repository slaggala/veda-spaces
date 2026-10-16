"""PR #101 final safety closure (VEDA-SPACES-PR101-FINAL-SAFETY-CLOSURE): M1 customer-promised dates, M2 snag gating
reclassification, S1 ineligible owners, S2 completed-stage milestones, S3 required QC NOT_APPLICABLE, and the targeted
forced interleavings A–D, on SQLite and PostgreSQL. SYNTHETIC data and SYNTHETIC lifecycle policies only; the shipped
policy record stays undecided."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ok
from tests.support.project import BASE, ON, Projects, advance_to, install, no_four_eyes, race
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.project.models import ProjectEvent, ProjectSnag
from veda.platform.audit.models import AuditLog
from veda.platform.identity.models import User

pytestmark = ON
OTHER_CAPABILITY = "project.approve_transition"  # a capability ops does not hold until a test grants it


@pytest.fixture
def team(api, factory):
    t = Projects(api, factory)
    prop, _, q = t.accepted()
    t.prop, t.q = prop, q  # type: ignore[attr-defined]
    t.p = t.book(q, prop)  # type: ignore[attr-defined]
    t.staff(t.p)
    yield t
    install(None)


def _policy(**decisions) -> None:
    doc = no_four_eyes()
    for k, v in decisions.items():
        doc["decisions"][k.replace("_", "-")] = v
    install(doc)


def _milestone(t: Projects, p: dict, **body) -> dict:
    d = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/milestones", {"milestone_code": "OTHER", "label": "Synthetic step",
                                                             "stage_code": "BOOKED", **body}), 201)  # fmt: skip
    return d["milestones"][-1]


# --- M1 ----------------------------------------------------------------------------------------------------------------
def test_m1_customer_promised_dates_are_refused_until_the_owner_decides_who_may_promise(team):
    t, p = team, team.p
    api = t.as_(t.ops)
    r = api.post(f"{BASE}/{p['id']}/milestones", {"milestone_code": "OTHER", "label": "Promised", "stage_code": "BOOKED",
                                                  "customer_promised_date": "2026-11-30"})  # fmt: skip
    assert r.status == 409 and r.code == "OWNER_DECISION_REQUIRED" and r.json["decision"] == "PLB-OD-13"
    m = _milestone(t, p, planned_date="2026-11-01")  # internal dates stay free
    r = api.patch(
        f"{BASE}/{p['id']}/milestones/{m['id']}", {"customer_promised_date": "2026-11-30"}, if_match=m["version"]
    )
    assert r.status == 409 and r.code == "OWNER_DECISION_REQUIRED"
    d = ok(api.patch(f"{BASE}/{p['id']}/milestones/{m['id']}", {"planned_date": "2026-11-05"}, if_match=m["version"]))
    m = d["milestones"][-1]
    assert m["planned_date"] == "2026-11-05" and m["customer_promised_date"] is None
    d = ok(
        api.post(
            f"{BASE}/{p['id']}/milestones/{m['id']}/complete", {"actual_date": "2026-10-15"}, if_match=m["version"]
        )
    )
    assert d["milestones"][-1]["actual_date"] == "2026-10-15"
    assert d["actions"]["record_promised_date"] is False


def test_m1_once_decided_only_the_named_capability_records_changes_or_clears_a_promise(team):
    t, p = team, team.p
    _policy(PLB_OD_13={"capability": OTHER_CAPABILITY, "reference": "SYNTHETIC"})
    api = t.as_(t.ops)
    m = _milestone(t, p)
    r = api.patch(
        f"{BASE}/{p['id']}/milestones/{m['id']}", {"customer_promised_date": "2026-11-30"}, if_match=m["version"]
    )
    assert r.status == 403 and r.json["permission"] == OTHER_CAPABILITY  # the decision names who; ops is not it
    t.factory.grant(t.ops, OTHER_CAPABILITY, scope="OWN")
    d = ok(api.patch(f"{BASE}/{p['id']}/milestones/{m['id']}", {"customer_promised_date": "2026-11-30"},
                     if_match=m["version"]))  # fmt: skip
    m = d["milestones"][-1]
    assert m["customer_promised_date"] == "2026-11-30" and d["actions"]["record_promised_date"] is True
    same = ok(api.patch(f"{BASE}/{p['id']}/milestones/{m['id']}", {"customer_promised_date": "2026-11-30",
                        "planned_date": "2026-11-20"}, if_match=m["version"]))  # an unchanged promise is not re-checked  # fmt: skip
    m = same["milestones"][-1]
    other = t.factory.user("ESTIMATOR")
    for code in ("project.view", "project.manage_milestone"):
        t.factory.grant(other, code)
    r = t.as_(other).patch(
        f"{BASE}/{p['id']}/milestones/{m['id']}", {"customer_promised_date": None}, if_match=m["version"]
    )
    assert r.status == 403  # clearing a promise is a promise change
    ok(
        t.as_(t.ops).patch(
            f"{BASE}/{p['id']}/milestones/{m['id']}", {"customer_promised_date": None}, if_match=m["version"]
        )
    )


# --- M2 ----------------------------------------------------------------------------------------------------------------
def _snag(t: Projects, p: dict, **body) -> dict:
    body = {"owner_user_id": t.ops.id, **body}  # PEX: a Veda snag is assigned before work starts on it
    d = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/snags", {"category": "FINISH", "customer_title": "Synthetic snag", **body}),
           201)  # fmt: skip
    return d["snags"][-1]


def _to_snagging(t: Projects, p: dict) -> dict:
    install(no_four_eyes())
    return advance_to(t, p, "SNAGGING")


def test_m2_gating_reclassification_is_refused_until_decided_then_authorised_reasoned_and_recorded(team):
    t, p = team, team.p
    p = _to_snagging(t, p)
    s = _snag(t, p)
    api = t.as_(t.ops)
    url = f"{BASE}/{p['id']}/snags/{s['id']}"
    r = api.patch(url, {"is_blocking": False}, if_match=s["version"])
    assert r.status == 422  # no longer a field of the ordinary edit
    r = api.post(f"{url}/classification", {"is_blocking": False, "reason": "Cosmetic only"}, if_match=s["version"])
    assert r.status == 409 and r.code == "OWNER_DECISION_REQUIRED" and r.json["decision"] == "PLB-OD-06"
    ok(api.post(f"{url}/status", {"status": "IN_PROGRESS"}, if_match=s["version"]))  # progress stays independent
    s = t.get(p)["snags"][-1]
    _policy(PLB_OD_06={"snag_reclassification_capability": OTHER_CAPABILITY, "reference": "SYNTHETIC"})
    r = api.post(f"{url}/classification", {"is_blocking": False, "reason": "Cosmetic only"}, if_match=s["version"])
    assert r.status == 403 and r.json["permission"] == OTHER_CAPABILITY
    t.factory.grant(t.ops, OTHER_CAPABILITY, scope="OWN")
    assert api.post(f"{url}/classification", {"is_blocking": False}, if_match=s["version"]).status == 422
    assert api.post(f"{url}/classification", {"is_blocking": True, "reason": "Still blocking"},
                    if_match=s["version"]).code == "NO_CHANGE"  # fmt: skip
    assert "SNAG_OPEN" in {b["code"] for b in t.get(p)["handover_readiness"]["blockers"]}
    d = ok(api.post(f"{url}/classification", {"is_blocking": False, "reason": "Cosmetic only; agreed on site"},
                    if_match=s["version"]))  # fmt: skip
    snag = d["snags"][-1]
    assert snag["is_blocking"] is False and snag["classification_reason"] == "Cosmetic only; agreed on site"
    assert "SNAG_OPEN" not in {b["code"] for b in d["handover_readiness"]["blockers"]}
    ev = next(e for e in d["timeline"] if e["code"] == "SNAG_RECLASSIFIED")
    assert (ev["from"], ev["to"], ev["by"]["id"]) == ("BLOCKING", "NON_BLOCKING", t.ops.id) and ev["on"]
    audit = dbh.rows(sa.select(AuditLog).where(AuditLog.entity_id == s["id"], AuditLog.action == "UPDATE"))
    assert any("is_blocking" in (a.changed_fields or []) and a.performed_by == t.ops.id for a in audit)


# --- S1 ----------------------------------------------------------------------------------------------------------------
def _disable(user_id: str) -> None:
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        u = s.get(User, user_id)
        u.status = "DISABLED"
        u.authz_version += 1


def test_s1_a_disabled_or_withdrawn_owner_no_longer_satisfies_the_owner_gate(team):
    t, p = team, team.p
    t.checklist(p)
    _disable(t.designer.id)
    r = t.transition(p, "DESIGN_FINALISATION")
    blockers = r["transition"]["blockers"]
    assert r["outcome"] == "REFUSED" and [(b["code"], b["responsibility"]) for b in blockers] == [
        ("OWNER_INELIGIBLE", "DESIGN")
    ]
    d = t.get(p)
    design = next(m for m in d["team"] if m["responsibility"] == "DESIGN" and m["active"])
    assert design["user"]["id"] == t.designer.id and design["eligible"] is False  # history kept, not removed
    assert d["needs_reassignment"] == ["DESIGN"]
    other = t.factory.user("DESIGNER")
    t.team(p, other, "DESIGN", reason="Previous designer's account is disabled")
    assert t.transition(p, "DESIGN_FINALISATION")["outcome"] == "COMPLETED"
    t.factory.grant(other, "project.complete_checklist", effect="DENY")  # the capability withdrawn
    assert t.get(p)["needs_reassignment"] == ["DESIGN"]


# --- S2 ----------------------------------------------------------------------------------------------------------------
def test_s2_a_completed_stages_milestones_are_immutable(team):
    t, p = team, team.p
    api = t.as_(t.ops)
    done = _milestone(t, p)
    ok(api.post(f"{BASE}/{p['id']}/milestones/{done['id']}/complete", {"actual_date": "2026-10-14"},
                if_match=done["version"]))  # fmt: skip
    na = _milestone(t, p)
    ok(api.patch(f"{BASE}/{p['id']}/milestones/{na['id']}", {"status": "NOT_APPLICABLE", "status_reason": "Merged"},
                 if_match=na["version"]))  # fmt: skip
    install(no_four_eyes())
    p = t.advance(p, "DESIGN_FINALISATION")
    na = next(m for m in t.get(p)["milestones"] if m["id"] == na["id"])
    for call in (lambda: api.patch(f"{BASE}/{p['id']}/milestones/{na['id']}", {"status": "PLANNED"}, if_match=na["version"]),
                 lambda: api.patch(f"{BASE}/{p['id']}/milestones/{na['id']}", {"planned_date": "2026-12-01"},
                                   if_match=na["version"]),
                 lambda: api.post(f"{BASE}/{p['id']}/milestones/{na['id']}/complete", {"actual_date": "2026-10-15"},
                                  if_match=na["version"])):  # fmt: skip
        r = call()
        assert r.status == 409 and r.code == "STAGE_COMPLETED", r
    after = next(m for m in t.get(p)["milestones"] if m["id"] == na["id"])
    assert (after["status"], after["status_reason"]) == ("NOT_APPLICABLE", "Merged")


# --- S3 ----------------------------------------------------------------------------------------------------------------
def test_s3_required_qc_not_applicable_is_refused_until_decided_then_authorised_with_a_reason(team):
    t, p = team, team.p
    install(no_four_eyes())
    p = advance_to(t, p, "QUALITY_CHECK")
    api = t.as_(t.ops)
    url = f"{BASE}/{p['id']}/qc-checks"
    r = api.post(url, {"category": "DIMENSIONS_AND_ALIGNMENT", "result": "NOT_APPLICABLE", "observation": "No units"})
    assert r.status == 409 and r.code == "OWNER_DECISION_REQUIRED" and r.json["decision"] == "PLB-OD-08"
    ok(api.post(url, {"category": "OTHER", "result": "NOT_APPLICABLE"}), 201)  # a category that is not required
    _policy(PLB_OD_08={"required_categories": ["DIMENSIONS_AND_ALIGNMENT", "FINISH_AND_SURFACES"],
                       "not_applicable_capability": OTHER_CAPABILITY})  # fmt: skip
    r = api.post(url, {"category": "DIMENSIONS_AND_ALIGNMENT", "result": "NOT_APPLICABLE", "observation": "No units"})
    assert r.status == 403 and r.json["permission"] == OTHER_CAPABILITY
    t.factory.grant(t.ops, OTHER_CAPABILITY, scope="OWN")
    r = api.post(url, {"category": "DIMENSIONS_AND_ALIGNMENT", "result": "NOT_APPLICABLE"})
    assert r.status == 422 and r.json["errors"][0]["field"] == "observation"
    d = ok(api.post(url, {"category": "DIMENSIONS_AND_ALIGNMENT", "result": "NOT_APPLICABLE",
                          "observation": "No fitted units in this job"}), 201)  # fmt: skip
    ev = [e for e in d["timeline"] if e["code"] == "QC_RECORDED"][-1]
    assert (
        ev["to"] == "NOT_APPLICABLE" and ev["detail"]["required_not_applicable"] is True and ev["by"]["id"] == t.ops.id
    )
    cat = next(c for c in d["qc"]["categories"] if c["category"] == "DIMENSIONS_AND_ALIGNMENT")
    assert cat["latest"]["observation"] == "No fitted units in this job"


# --- targeted concurrency A–D -------------------------------------------------------------------------------------------
def test_a_two_promised_date_writes_race_and_exactly_one_lands(team, app, monkeypatch):
    t, p = team, team.p
    _policy(PLB_OD_13={"capability": "project.manage_milestone", "reference": "SYNTHETIC"})
    m = _milestone(t, p)
    path = f"{BASE}/{p['id']}/milestones/{m['id']}"
    other = t.factory.user("ESTIMATOR")
    for code in ("project.view", "project.manage_milestone"):
        t.factory.grant(other, code)
    second_api = t.factory.login(t.api, other, set_default=False)
    from tests.support.api import ApiClient

    b = ApiClient(app.test_client())
    b.token = second_api
    first, second = race(app, monkeypatch, t.token(t.ops),
                         lambda c: c.patch(path, {"customer_promised_date": "2026-11-30"}, if_match=m["version"]),
                         lambda: b.patch(path, {"customer_promised_date": "2026-12-15"}, if_match=m["version"]))  # fmt: skip
    assert sorted((first.status, second.status)) == [200, 409]
    winner = "2026-11-30" if first.status == 200 else "2026-12-15"
    assert next(x for x in t.get(p)["milestones"] if x["id"] == m["id"])["customer_promised_date"] == winner


def test_b_a_snag_made_blocking_while_the_project_moves_is_never_bypassed(team, app, monkeypatch):
    t, p = team, team.p
    p = _to_snagging(t, p)
    s = _snag(t, p, is_blocking=False)
    t.checklist(p)
    _policy(PLB_OD_06={"snag_reclassification_capability": "project.manage_snag", "reference": "SYNTHETIC"})
    cur = t.get(p)
    from tests.support.api import ApiClient

    b = ApiClient(app.test_client())
    b.token = t.token(t.founder)
    first, second = race(app, monkeypatch, t.token(t.ops),
                         lambda c: c.post(f"{BASE}/{p['id']}/transitions", {"to_stage": "READY_FOR_HANDOVER"},
                                          if_match=cur["version"]),
                         lambda: b.post(f"{BASE}/{p['id']}/snags/{s['id']}/classification",
                                        {"is_blocking": True, "reason": "Visible scratch, must be fixed"},
                                        if_match=s["version"]))  # fmt: skip
    assert second.status == 200
    after = t.get(p)
    assert next(x for x in after["snags"] if x["id"] == s["id"])["is_blocking"] is True
    if after["stage"]["code"] == "READY_FOR_HANDOVER":  # the move committed first, with the snag non-blocking then
        assert first.status == 201 and first.data["outcome"] == "COMPLETED"
        assert "SNAG_OPEN" in {b["code"] for b in after["handover_readiness"]["blockers"]}  # caught before handover
    else:
        assert first.status == 409 and first.code == "VERSION_CONFLICT"
        assert "SNAG_OPEN" in {b["code"] for b in t.transition(p, "READY_FOR_HANDOVER")["transition"]["blockers"]}


def test_c_an_owner_disabled_while_the_project_moves_is_decided_on_committed_state(team, app, monkeypatch, engine):
    t, p = team, team.p
    cur = t.checklist(p)
    first, _ = race(app, monkeypatch, t.token(t.ops),
                    lambda c: c.post(f"{BASE}/{p['id']}/transitions", {"to_stage": "DESIGN_FINALISATION"},
                                     if_match=cur["version"]),
                    lambda: _disable(t.designer.id))  # fmt: skip
    assert first.status == 201
    if engine == "postgresql":  # the disable committed before the move took the lock: re-read, refused
        assert first.data["outcome"] == "REFUSED"
        assert {b["code"] for b in first.data["transition"]["blockers"]} == {"OWNER_INELIGIBLE"}
        assert t.get(p)["stage"]["code"] == "BOOKED"
    else:  # SQLite: the move held the write lock and committed first; the disable followed
        assert first.data["outcome"] == "COMPLETED"
    assert t.get(p)["needs_reassignment"] == ["DESIGN"]


def test_d_a_required_qc_not_applicable_racing_the_handover_readiness_move_is_deterministic(team, app, monkeypatch):
    t, p = team, team.p
    install(no_four_eyes())
    p = advance_to(t, p, "QUALITY_CHECK", qc=())
    api = t.as_(t.ops)
    ok(api.post(f"{BASE}/{p['id']}/qc-checks", {"category": "DIMENSIONS_AND_ALIGNMENT", "result": "PASS"}), 201)
    failed = ok(api.post(f"{BASE}/{p['id']}/qc-checks", {"category": "FINISH_AND_SURFACES", "result": "FAIL",
                                                        "observation": "Gap at the hinge"}), 201)["qc"]["history"][0]  # fmt: skip
    p = t.advance(p, "SNAGGING")
    t.checklist(p)
    _policy(PLB_OD_08={"required_categories": ["DIMENSIONS_AND_ALIGNMENT", "FINISH_AND_SURFACES"],
                       "not_applicable_capability": "project.manage_qc"})  # fmt: skip
    cur = t.get(p)
    from tests.support.api import ApiClient

    b = ApiClient(app.test_client())
    b.token = t.token(t.founder)
    first, second = race(app, monkeypatch, t.token(t.ops),
                         lambda c: c.post(f"{BASE}/{p['id']}/transitions", {"to_stage": "READY_FOR_HANDOVER"},
                                          if_match=cur["version"]),
                         lambda: b.post(f"{BASE}/{p['id']}/qc-checks", {"category": "FINISH_AND_SURFACES",
                                        "result": "NOT_APPLICABLE", "observation": "Finish replaced by customer supply",
                                        "recheck_of_id": failed["id"]}))  # fmt: skip
    assert second.status == 201
    if first.status == 201:  # evaluated before the override committed: refused on the failure, never passed
        assert first.data["outcome"] == "REFUSED" and {b["code"] for b in first.data["transition"]["blockers"]} == {
            "QC_FAILED"
        }
    else:
        assert first.status == 409 and first.code == "VERSION_CONFLICT"
    assert t.get(p)["stage"]["code"] == "SNAGGING"
    assert t.transition(p, "READY_FOR_HANDOVER")["outcome"] == "COMPLETED"  # once the override is committed
    assert dbh.scalar(sa.select(sa.func.count()).select_from(ProjectEvent).where(
        ProjectEvent.event_code == "QC_RECORDED")) >= 3  # fmt: skip
    assert dbh.scalar(sa.select(sa.func.count()).select_from(ProjectSnag)) == 0
