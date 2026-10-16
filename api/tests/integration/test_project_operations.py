"""Site readiness (reusing the frozen Customer Promise), quality checks, snags, handover, notifications, erasure and the
immutable timeline (PLB-12, PLB-16, PLB-17, PLB-26 … PLB-30, PLB-35, PLB-38, PLB-39). SYNTHETIC data only."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import install_full_policy, ok
from tests.support.mtq import photo
from tests.support.project import BASE, ON, Projects, install, synthetic_policy
from tests.support.proposal import SYNTHETIC_PACK
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.mtq_commercial.models import Quotation
from veda.modules.project.models import ProjectBlocker, ProjectEvent, ProjectSnag
from veda.platform.notifications.models import Notification, OutboxEvent

pytestmark = ON


@pytest.fixture
def team(api, factory):
    t = Projects(api, factory)
    install(synthetic_policy(PLB_OD_03={"lifecycle_version": "PLB-2026.10.1", "transitions": []}))
    yield t
    install(None)


def _booked(t: Projects, key: str = "2BHK") -> dict:
    prop, _, q = t.accepted(key)
    p = t.book(q, prop)
    p["_prop"], p["_q"] = prop, q
    return p


def _to(t: Projects, p: dict, stage: str) -> dict:
    order = ["DESIGN_FINALISATION", "SCOPE_FROZEN", "SITE_READINESS", "PRODUCTION_READINESS", "IN_PRODUCTION",
             "READY_FOR_INSTALLATION", "INSTALLATION", "QUALITY_CHECK", "SNAGGING", "READY_FOR_HANDOVER"]  # fmt: skip
    for to in order[order.index(t.get(p)["stage"]["code"]) + 1 if t.get(p)["stage"]["code"] in order else 0 :]:
        if to == "PRODUCTION_READINESS":
            t.ready_site(p)
        if to == "SNAGGING":
            for cat in ("DIMENSIONS_AND_ALIGNMENT", "FINISH_AND_SURFACES"):
                ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/qc-checks", {"category": cat, "result": "PASS"}), 201)
        p = t.advance(p, to)
        if to == stage:
            break
    return t.get(p)


# --- site readiness ----------------------------------------------------------------------------------------------------
def test_site_readiness_observes_the_frozen_promise_items_and_never_changes_the_quotation(api, factory):
    t = Projects(api, factory)
    install_full_policy(OI_MTQ_18=SYNTHETIC_PACK)
    install(synthetic_policy())
    try:
        p = _booked(t)
        q = p["_q"]
        with db.unit_of_work(write=False) as s:
            frozen = s.get(Quotation, q["id"])
            before = (frozen.version, frozen.snapshot_sha256)
        t.staff(p)
        items = t.get(p)["site_readiness"]
        assert {(r["kind"], r["item_code"]) for r in items} == {("READINESS", "SYN_FLOOR"), ("READINESS", "SYN_POWER"),
                                                                ("RESPONSIBILITY", "SYN_APPLIANCE"),
                                                                ("RESPONSIBILITY", "SYN_LIFT")}  # fmt: skip
        floor = next(r for r in items if r["item_code"] == "SYN_FLOOR")
        assert floor["status"] == "TO_BE_CONFIRMED" and floor["source"] == "CUSTOMER_PROMISE"
        assert (
            floor["promise"]["text"] == "SYNTHETIC: flooring complete." and floor["label"] == floor["promise"]["text"]
        )
        api = t.as_(t.surveyor)  # the surveyor is a member and manages site readiness (OWN)
        url = f"{BASE}/{p['id']}/site-readiness/{floor['id']}"
        r = api.patch(url, {"status": "CUSTOMER_ACTION_REQUIRED", "action": "Flooring not laid in Bedroom 2"},
                      if_match=floor["version"])  # fmt: skip
        assert r.status == 422 and r.json["errors"][0]["field"] == "customer_action"
        d = ok(api.patch(url, {"status": "CUSTOMER_ACTION_REQUIRED", "action": "Flooring not laid in Bedroom 2",
                               "customer_action": "Please complete the flooring in Bedroom 2",
                               "due_date": "2026-11-01"}, if_match=floor["version"]))  # fmt: skip
        floor = next(r for r in d["site_readiness"] if r["id"] == floor["id"])
        assert floor["responsible_party"] == "CUSTOMER" and floor["resolved_on"] is None
        assert d["site_readiness_state"] == "BLOCKED"
        assert any(a["kind"] == "SITE_READINESS" and a["who"] == "CUSTOMER" for a in d["attention"])
        r = api.patch(url, {"responsible_party": "VEDA"}, if_match=floor["version"])
        assert r.status == 422 and r.json["errors"][0]["field"] == "responsible_party"
        d = ok(api.patch(url, {"status": "READY", "note": "Seen on visit"}, if_match=floor["version"]))
        floor = next(r for r in d["site_readiness"] if r["id"] == floor["id"])
        assert floor["satisfied"] is True and floor["resolved_by"]["id"] == t.surveyor.id
        with db.unit_of_work(write=False) as s:
            frozen = s.get(Quotation, q["id"])
            assert (frozen.version, frozen.snapshot_sha256) == before  # PLB-16: the quotation never changes
        drained_types = {e.event_type for e in dbh.rows(sa.select(OutboxEvent))}
        assert "project.customer_action_required" in drained_types
    finally:
        install(None)


def test_site_readiness_blocks_production_readiness_until_every_item_is_satisfied(team):
    t = team
    p = _booked(t)
    t.staff(p)
    p = _to(t, p, "SITE_READINESS")
    t.checklist(p)
    r = t.transition(p, "PRODUCTION_READINESS")
    assert {b["code"] for b in r["transition"]["blockers"]} == {"SITE_READINESS_NOT_ASSESSED"}
    d = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/site-readiness", {"kind": "READINESS", "category": "ACCESS",
                                                                 "label": "Service lift booking"}), 201)  # fmt: skip
    item = d["site_readiness"][0]
    d = ok(t.as_(t.ops).patch(f"{BASE}/{p['id']}/site-readiness/{item['id']}",
                              {"status": "VEDA_ACTION_REQUIRED", "action": "Book the lift with the society office"},
                              if_match=item["version"]))  # fmt: skip
    assert d["site_readiness"][0]["responsible_party"] == "VEDA"
    r = t.transition(p, "PRODUCTION_READINESS")
    assert [(b["code"], b["responsible_party"]) for b in r["transition"]["blockers"]] == [
        ("SITE_VEDA_ACTION_REQUIRED", "VEDA")
    ]
    t.ready_site(p)
    assert t.transition(p, "PRODUCTION_READINESS")["outcome"] == "COMPLETED"


# --- quality check and snags -------------------------------------------------------------------------------------------
def test_quality_failures_and_open_snags_stop_handover_readiness_until_fixed_and_rechecked(team):
    t = team
    p = _booked(t)
    t.staff(p)
    api = t.as_(t.ops)
    assert api.post(f"{BASE}/{p['id']}/qc-checks", {"category": "FINISH_AND_SURFACES", "result": "PASS"}).status == 409
    p = _to(t, p, "QUALITY_CHECK")
    t.checklist(p)
    assert {b["code"] for b in t.transition(p, "SNAGGING")["transition"]["blockers"]} == {"QC_NOT_RECORDED"}
    r = api.post(f"{BASE}/{p['id']}/qc-checks", {"category": "FINISH_AND_SURFACES", "result": "FAIL"})
    assert r.status == 422 and r.json["errors"][0]["field"] == "observation"
    spaces = t.get(p)["spaces"]
    d = ok(api.post(f"{BASE}/{p['id']}/qc-checks", {"category": "FINISH_AND_SURFACES", "result": "FAIL",
                                                   "observation": "Edge banding lifting", "space_id": spaces[0]["id"]}),
           201)  # fmt: skip
    failed = d["qc"]["history"][0]
    ok(api.post(f"{BASE}/{p['id']}/qc-checks", {"category": "DIMENSIONS_AND_ALIGNMENT", "result": "PASS"}), 201)
    assert t.transition(p, "SNAGGING")["outcome"] == "COMPLETED"  # QC done (a failure is a result)
    readiness = t.get(p)["handover_readiness"]
    assert readiness["ready"] is False and {b["code"] for b in readiness["blockers"]} == {"QC_FAILED"}
    d = ok(api.post(f"{BASE}/{p['id']}/snags", {"category": "FINISH", "customer_title": "Shutter edge to be refinished",
                                               "description": "Edge banding lifting on the wardrobe",
                                               "space_id": spaces[0]["id"], "qc_check_id": failed["id"],
                                               "owner_user_id": t.ops.id}), 201)  # fmt: skip
    snag = d["snags"][0]
    assert snag["snag_no"] == 1 and snag["is_blocking"] and snag["status"] == "OPEN"
    t.checklist(p)
    blockers = {b["code"] for b in t.transition(p, "READY_FOR_HANDOVER")["transition"]["blockers"]}
    assert blockers == {"QC_FAILED", "SNAG_OPEN"}
    url = f"{BASE}/{p['id']}/snags/{snag['id']}"
    r = api.post(f"{url}/status", {"status": "RESOLVED", "note": "Fixed"}, if_match=snag["version"])
    assert r.status == 409 and r.json["allowed"] == ["IN_PROGRESS", "CLOSED"]
    snag = next(x for x in ok(api.post(f"{url}/status", {"status": "IN_PROGRESS"}, if_match=snag["version"]))["snags"])
    qa = t.as_(t.quality)
    recheck = {"category": "FINISH_AND_SURFACES", "result": "PASS", "recheck_of_id": failed["id"]}
    r = qa.post(f"{BASE}/{p['id']}/qc-checks", recheck)
    assert r.status == 409 and r.code == "REMEDIATION_OPEN"  # the failure is rechecked after its remediation
    api = t.as_(t.ops)
    r = api.post(f"{url}/status", {"status": "READY_FOR_RECHECK"}, if_match=snag["version"])
    assert r.status == 422  # the fixer says what was fixed
    snag = next(x for x in ok(api.post(f"{url}/status", {"status": "READY_FOR_RECHECK", "note": "Edge rebanded"},
                                       if_match=snag["version"]))["snags"])  # fmt: skip
    assert snag["fixed_by"]["id"] == t.ops.id and snag["fix_note"] == "Edge rebanded"
    r = api.post(f"{url}/status", {"status": "RESOLVED", "note": "Looks fine to me"}, if_match=snag["version"])
    assert r.status == 403  # the fixer holds no verify capability
    qa = t.as_(t.quality)
    r = qa.post(f"{url}/status", {"status": "RESOLVED"}, if_match=snag["version"])
    assert r.status == 422  # a recheck says what was found
    d = ok(qa.post(f"{url}/status", {"status": "RESOLVED", "note": "Rechecked: edge rebanded"},
                   if_match=snag["version"]))  # fmt: skip
    assert d["snags"][0]["status"] == "RESOLVED" and d["snags"][0]["resolved_by"]["id"] == t.quality.id
    r = t.as_(t.ops).post(f"{BASE}/{p['id']}/qc-checks", recheck)
    assert r.status == 409 and r.code == "SEGREGATION_REQUIRED"  # the fixer never rechecks their own fix
    d = ok(t.as_(t.quality).post(f"{BASE}/{p['id']}/qc-checks", recheck), 201)
    r = t.as_(t.quality).post(f"{BASE}/{p['id']}/qc-checks", recheck)
    assert r.status == 409 and r.code == "RECHECK_NOT_LATEST"  # one recheck per check
    assert d["handover_readiness"]["blockers"] == [] and d["handover_readiness"]["stage_reached"] is False
    assert t.transition(p, "READY_FOR_HANDOVER")["outcome"] == "COMPLETED"
    # one computation: in READY_FOR_HANDOVER readiness is the handover's own evaluation (its checklist included)
    readiness = t.get(p)["handover_readiness"]
    assert readiness["stage_reached"] and {b["code"] for b in readiness["blockers"]} == {"CHECKLIST_ITEM_OPEN"}
    t.checklist(p)
    assert t.get(p)["handover_readiness"]["ready"] is True


# --- handover ----------------------------------------------------------------------------------------------------------
def _handover_body(t: Projects, p: dict, **over) -> dict:
    att = photo(t.as_(t.founder), "property", p["_prop"]["id"])
    return {"handover_on": "2026-10-15", "acknowledgement_reference": "Handover sheet HS-001 signed",
            "evidence_attachment_id": att["id"], **over}  # fmt: skip


def test_handover_needs_its_evidence_closes_the_project_and_emits_the_domain_event(team):
    t = team
    p = _booked(t)
    t.staff(p)
    p = _to(t, p, "READY_FOR_HANDOVER")
    p["_prop"] = {"id": p["property"]["id"]}
    t.checklist(p)
    r = t.transition(p, "HANDED_OVER")  # the handover is not a plain stage move
    assert {b["code"] for b in r["transition"]["blockers"]} == {"USE_HANDOVER"}
    body = _handover_body(t, p)
    api = t.as_(t.ops)
    r = ok(api.post(f"{BASE}/{p['id']}/handover", body, if_match=t.get(p)["version"]), 201)
    assert r["outcome"] == "REFUSED" and {b["code"] for b in r["transition"]["blockers"]} == {"HANDOVER_PACKAGE_MISSING"}
    pkg = t.package(p)["handover_packages"][-1]
    assert pkg["status"] == "PREPARED" and pkg["content"]["documents"] == [] and pkg["stale"] is None
    assert t.package(p)["handover_packages"] == [pkg | {}] or len(t.get(p)["handover_packages"]) == 1  # unchanged: same
    api = t.as_(t.ops)
    cur = t.get(p)
    assert api.post(f"{BASE}/{p['id']}/handover", {**body, "handover_on": "2999-01-01"},
                    if_match=cur["version"]).status == 422  # fmt: skip
    r = ok(api.post(f"{BASE}/{p['id']}/handover", {**body, "acknowledgement_reference": None},
                    if_match=cur["version"]), 201)  # fmt: skip
    assert r["outcome"] == "REFUSED" and {b["code"] for b in r["transition"]["blockers"]} == {"ACKNOWLEDGEMENT_MISSING"}
    foreign = photo(t.as_(t.founder), "property", t.accepted("3BHK")[0]["id"])
    api = t.as_(t.ops)
    r = api.post(f"{BASE}/{p['id']}/handover", {**body, "evidence_attachment_id": foreign["id"]},
                 if_match=t.get(p)["version"])  # fmt: skip
    assert r.status == 422 and r.code == "EVIDENCE_NOT_AVAILABLE"
    r = ok(api.post(f"{BASE}/{p['id']}/handover", {**body, "observations": "Minor touch-up booked"},
                    if_match=t.get(p)["version"]), 201)  # fmt: skip
    assert r["outcome"] == "COMPLETED"
    d = r["project"]
    assert (
        d["status"] == "HANDED_OVER" and d["stage"]["code"] == "HANDED_OVER" and d["handed_over_by"]["id"] == t.ops.id
    )
    assert all(x["status"] == "COMPLETED" for x in d["stages"])
    assert d["readiness"] is None and not any(d["actions"][k] for k in ("request_transition", "complete_handover",
                                                                        "raise_blocker", "manage_snag"))  # fmt: skip
    handed = [e for e in d["timeline"] if e["code"] == "HANDED_OVER"]
    assert len(handed) == 1 and handed[0]["detail"]["baseline_seq"] == 1
    events = [e for e in dbh.rows(sa.select(OutboxEvent)) if e.event_type == "project.handed_over"]
    assert len(events) == 1 and set(events[0].payload) >= {"project_id", "baseline_id", "lead_id", "property_id",
                                                           "source_quotation_id", "transition_id", "handover_package_id",
                                                           "handover_package_sha256"}  # fmt: skip
    assert events[0].payload["handover_package_id"] == pkg["id"]
    assert [x["status"] for x in d["handover_packages"]] == ["COMPLETED"]
    assert not any(isinstance(v, str) and " " in v for v in events[0].payload.values())  # ids only
    # the history is closed: no further change, no second handover
    r = api.post(f"{BASE}/{p['id']}/blockers", {"category": "OTHER", "impact": "INFORMATIONAL", "title": "Late note",
                                                "responsible_party": "VEDA"})  # fmt: skip
    assert r.status == 409 and r.code == "PROJECT_HANDED_OVER"
    r = api.post(f"{BASE}/{p['id']}/handover", body, if_match=d["version"])
    assert r.status == 409 and r.code == "PROJECT_HANDED_OVER"


# --- notifications, timeline, erasure -----------------------------------------------------------------------------------
def test_staff_are_notified_in_app_and_no_customer_is(team, app):
    from veda.platform.notifications import worker

    t = team
    p = _booked(t)
    t.staff(p)
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/blockers", {"category": "CUSTOMER_DECISION", "impact": "GATING",
                                                       "title": "Handle finish not chosen", "responsible_party": "CUSTOMER",
                                                       "customer_action": "Choose the handle finish",
                                                       "blocks_stage_code": "PRODUCTION_READINESS",
                                                       "assigned_to": t.designer.id}), 201)  # fmt: skip
    worker.drain_all()
    notes = dbh.rows(sa.select(Notification))
    by_type = {}
    for n in notes:
        by_type.setdefault(n.notification_type, set()).add(n.recipient_user_id)
    assert by_type["PROJECT_BLOCKER_ASSIGNED"] == {t.designer.id}
    assert by_type["PROJECT_CUSTOMER_ACTION"] == {t.ops.id}
    assert all(n.link_path == f"/projects/{p['id']}" for n in notes)
    lead_id = p["_q"]["lead_id"] if "lead_id" in p["_q"] else None
    assert all(n.recipient_user_id != lead_id for n in notes)  # staff accounts only; customers have none


def test_the_timeline_is_immutable_and_carries_no_free_text(team):
    t = team
    p = _booked(t)
    t.staff(p)
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/blockers", {"category": "OTHER", "impact": "INFORMATIONAL",
                                                       "title": "Mrs Sharma prefers mornings",
                                                       "responsible_party": "VEDA"}), 201)  # fmt: skip
    events = dbh.rows(sa.select(ProjectEvent))
    assert events and "Sharma" not in str([e.detail for e in events])
    eid = events[0].id
    for stmt in (sa.update(ProjectEvent).where(ProjectEvent.id == eid).values(event_code="HANDED_OVER"),
                 sa.delete(ProjectEvent).where(ProjectEvent.id == eid)):  # fmt: skip
        with pytest.raises(Exception, match="immutable"):  # noqa: B017,PT011  (the engine's trigger error)
            with db.unit_of_work(write=True) as s:
                s.execute(stmt)
    assert dbh.rows(sa.select(ProjectEvent).where(ProjectEvent.id == eid))[0].event_code == "PROJECT_CREATED"


def test_erasing_the_customer_erases_project_free_text_and_closes_the_project(team):
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead

    t = team
    p = _booked(t)
    t.staff(p)
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/blockers", {"category": "SITE", "impact": "GATING",
                                                       "title": "Mr Rao's balcony door", "responsible_party": "CUSTOMER",
                                                       "customer_action": "Please call Mr Rao's office",
                                                       "description": "Personal detail", "blocks_stage_code": "SITE_READINESS"}),
       201)  # fmt: skip
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/snags", {"category": "OTHER", "customer_title": "Rao family note"}), 201)
    before = len(dbh.rows(sa.select(ProjectEvent)))
    with db.unit_of_work(write=False) as s:
        lead_id = s.execute(sa.select(Quotation.lead_id).where(Quotation.id == p["_q"]["id"])).scalar_one()
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, lead_id), legal_basis="SYNTHETIC erasure test", request_ref=None)
    b = dbh.rows(sa.select(ProjectBlocker))[0]
    assert (b.title, b.description, b.customer_action) == ("[erased]",) * 3 and b.category == "SITE"
    assert dbh.rows(sa.select(ProjectSnag))[0].customer_title == "[erased]"
    assert len(dbh.rows(sa.select(ProjectEvent))) == before  # the timeline holds no free text: untouched
    r = t.as_(t.ops).post(f"{BASE}/{p['id']}/blockers", {"category": "OTHER", "impact": "INFORMATIONAL",
                                                        "title": "After erasure", "responsible_party": "VEDA"})  # fmt: skip
    assert r.status == 409 and r.code == "INVALID_STATE"
