"""Booking an accepted quotation as a project (PLB-01, PLB-02, PLB-03, PLB-45, PLB-46). SYNTHETIC data only."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ok, step
from tests.support.project import BASE, ON, Projects
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.mtq_commercial.models import Quotation, QuotationEvent
from veda.modules.project.models import Project, ProjectBaseline, ProjectChecklistItem, ProjectEvent, ProjectStage

pytestmark = ON


def _quotation_row(qid: str) -> dict:
    with db.unit_of_work(write=False) as s:
        q = s.get(Quotation, qid)
        return {"version": q.version, "updated_on": q.updated_on, "status": q.status,
                "snapshot_sha256": q.snapshot_sha256, "accepted_baseline_sha256": q.accepted_baseline_sha256,
                "accepted_total_minor": q.accepted_total_minor}  # fmt: skip


def test_an_accepted_quotation_is_booked_as_one_project_referencing_its_baseline(api, factory):
    t = Projects(api, factory)
    prop, est, q = t.accepted()
    before = _quotation_row(q["id"])
    p = t.book(q, prop)
    assert p["project_number"].startswith("VS-P-") and p["status"] == "ACTIVE"
    assert p["stage"]["code"] == "BOOKED" and p["stage"]["sequence"] == 1 and p["stage"]["of"] == 12
    assert p["quotation_number"] == q["quotation_number"] and p["source_quotation_id"] == q["id"]
    assert p["property"]["property_number"] == prop["property_number"]
    assert p["lifecycle"]["status"] == "PROPOSED"  # PLB-OD-01 undecided in the shipped record
    b = p["baseline"]
    assert b["verified"] is True and b["current_seq"] == 1 and len(b["lineage"]) == 1
    original = b["lineage"][0]
    assert original["kind"] == "ORIGINAL" and original["quotation_id"] == q["id"]
    assert original["accepted_total_minor"] == before["accepted_total_minor"]  # the manager sees amounts
    assert original["accepted_baseline_sha256"] == before["accepted_baseline_sha256"]
    assert original["snapshot_sha256"] == before["snapshot_sha256"]
    assert original["lineage"]["estimate_revision_no"] == est["revision_no"]
    # stages, checklists and the timeline are seeded; nothing commercial is copied or written
    assert [x["status"] for x in p["stages"]] == ["ACTIVE"] + ["NOT_STARTED"] * 11
    assert sum(g["total"] for g in p["checklist"]) == dbh.scalar(
        sa.select(sa.func.count()).select_from(ProjectChecklistItem)
    )
    assert [e["code"] for e in p["timeline"]] == ["PROJECT_CREATED", "BASELINE_RECORDED"]
    assert _quotation_row(q["id"]) == before  # PLB-03: booking never touches the quotation


def test_booking_is_idempotent_and_one_project_per_accepted_baseline(api, factory):
    t = Projects(api, factory)
    prop, _, q = t.accepted()
    key = "a" * 32
    first = t.book(q, prop, **{"Idempotency-Key": key})
    replay = t.book(q, prop, **{"Idempotency-Key": key})
    assert replay["id"] == first["id"]
    again = t.book(q, prop, status=409)
    assert again.code == "PROJECT_EXISTS" and again.json["project_id"] == first["id"]
    assert dbh.scalar(sa.select(sa.func.count()).select_from(Project)) == 1


def test_nothing_but_a_legitimately_accepted_base_quotation_is_booked(api, factory):
    t = Projects(api, factory)
    prop, _, q = t.quotation()  # DRAFT
    r = t.book(q, prop, status=409)
    assert r.code == "NOT_BOOKABLE" and {x["code"] for x in r.json["problems"]} == {"QUOTATION_NOT_ACCEPTED"}
    step(t.c, q, "submit", t.c.estimator)  # INTERNAL_REVIEW
    assert t.book(q, prop, status=409).json["problems"][0]["status"] == "INTERNAL_REVIEW"
    step(t.c, q, "approve", t.c.manager)  # APPROVED, never accepted
    assert t.book(q, prop, status=409).json["problems"][0]["status"] == "APPROVED"
    q = ok(step(t.c, q, "issue", t.c.manager))  # ISSUED: the customer has not decided
    assert t.book(q, prop, status=409).json["problems"][0]["status"] == "ISSUED"
    rejected = ok(step(t.c, q, "decision", t.c.sales, {"decision": "REJECTED", "method": "SIGNED_COPY"}))
    assert t.book(rejected, prop, status=409).json["problems"][0]["status"] == "REJECTED"
    assert dbh.scalar(sa.select(sa.func.count()).select_from(Project)) == 0


def test_a_superseded_version_and_a_variation_are_refused(api, factory):
    t = Projects(api, factory)
    prop, est, q = t.issued()
    v2 = ok(step(t.c, q, "versions", t.c.estimator, {"cost_estimate_id": est["id"]}, code=201))
    old = ok(t.as_(t.manager).get(f"/api/v1/quotations/{q['id']}"))
    assert t.book(old, prop, status=409).json["problems"][0]["status"] in ("SUPERSEDED", "ISSUED")
    step(t.c, v2, "submit", t.c.estimator)
    step(t.c, v2, "approve", t.c.manager)
    v2 = ok(step(t.c, v2, "issue", t.c.manager))
    base = ok(step(t.c, v2, "decision", t.c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY"}))
    var = t.variation(base, prop)
    var = t.accept_variation(var)
    r = t.book(var, prop, status=422)
    assert "QUOTATION_IS_VARIATION" in {x["code"] for x in r.json["problems"]}


def test_another_property_context_is_refused(api, factory):
    t = Projects(api, factory)
    prop, _, q = t.accepted("2BHK")
    other, _, _ = t.quotation("3BHK")
    r = t.book(q, other, status=422)
    assert {x["code"] for x in r.json["problems"]} == {"CONTEXT_MISMATCH"}


def test_a_tampered_or_unverifiable_acceptance_is_refused(api, factory):
    t = Projects(api, factory)
    prop, _, q = t.accepted()
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        row = s.get(Quotation, q["id"])
        row.accepted_baseline = [*(row.accepted_baseline or []), {"key": "forged"}]
    r = t.book(q, prop, status=409)
    assert "BASELINE_INTEGRITY_FAILED" in {x["code"] for x in r.json["problems"]}

    prop2, _, q2 = t.accepted("3BHK")
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        row = s.get(Quotation, q2["id"])
        row.snapshot = {**row.snapshot, "title": "forged"}
    assert "SNAPSHOT_INTEGRITY_FAILED" in {x["code"] for x in t.book(q2, prop2, status=409).json["problems"]}


def test_an_acceptance_without_its_decision_record_is_refused(api, factory):
    t = Projects(api, factory)
    prop, _, q = t.accepted()
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.execute(sa.update(QuotationEvent).where(QuotationEvent.quotation_id == q["id"],
                                                  QuotationEvent.event_code == "ACCEPTED")
                  .values(detail={"method": "SIGNED_COPY", "accepted_baseline_sha256": "0" * 64}))  # fmt: skip
    r = t.book(q, prop, status=409)
    assert {x["code"] for x in r.json["problems"]} == {"ACCEPTANCE_EVIDENCE_MISSING"}


def test_booking_needs_the_capability_in_scope(api, factory):
    t = Projects(api, factory)
    prop, _, q = t.accepted()
    assert t.book(q, prop, user=t.designer, status=403).code == "PERMISSION_DENIED"
    # an individually granted OWN booker sees only quotations of leads they own: anything else is not disclosed
    booker = factory.user("ESTIMATOR")
    factory.grant(booker, "project.create_from_acceptance", scope="OWN")
    assert t.book(q, prop, user=booker, status=404).code == "NOT_FOUND"
    assert t.book({"id": "0" * 12 + "7" + "0" * 3 + "8" + "0" * 15}, prop, status=404).code == "NOT_FOUND"


@pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
                      project_lifecycle_enabled=False)  # fmt: skip
def test_every_route_answers_404_while_the_flag_is_off(api, factory):
    t = Projects(api, factory)
    prop, _, q = t.accepted()
    api = t.as_(t.founder)
    assert api.get("/api/v1/auth/me").data["features"]["project_lifecycle"] is False
    for method, path in (("GET", BASE), ("POST", BASE), ("GET", f"{BASE}/vocabulary"), ("GET", f"{BASE}/x"),
                         ("POST", f"{BASE}/x/transitions"), ("PATCH", f"{BASE}/x/blockers/y"), ("DELETE", BASE)):  # fmt: skip
        r = api.call(method, path, {"quotation_id": q["id"], "property_id": prop["id"]} if method != "GET" else None)
        assert r.status == 404 and r.code == "NOT_FOUND", (method, path, r)


def test_variations_already_accepted_join_the_lineage_in_order(api, factory):
    t = Projects(api, factory)
    prop, _, base = t.accepted()
    v = t.accept_variation(t.variation(base, prop))
    p = t.book(base, prop)
    lineage = p["baseline"]["lineage"]
    assert [(x["kind"], x["quotation_id"]) for x in lineage] == [("ORIGINAL", base["id"]), ("VARIATION", v["id"])]
    assert lineage[1]["cumulative_value_minor"] == (lineage[0]["accepted_total_minor"]
                                                    + lineage[1]["accepted_total_minor"])  # fmt: skip
    assert lineage[1]["current"] is True and p["baseline"]["verified"] is True
    with db.unit_of_work(write=False) as s:
        rows = s.execute(sa.select(ProjectBaseline).order_by(ProjectBaseline.sequence_no)).scalars().all()
        assert rows[1].previous_baseline_id == rows[0].id
        assert s.execute(sa.select(sa.func.count()).select_from(ProjectStage)).scalar() == 12
        assert {e.event_code for e in s.execute(sa.select(ProjectEvent)).scalars()} == {"PROJECT_CREATED",
                                                                                        "BASELINE_RECORDED"}  # fmt: skip


def test_the_booking_queue_lists_accepted_quotations_awaiting_a_project(api, factory):
    t = Projects(api, factory)
    prop, _, q = t.accepted()
    data = ok(t.as_(t.manager).get(BASE))
    assert [b["quotation_id"] for b in data["bookable"]] == [q["id"]] and data["bookable"][0]["problems"] == []
    t.book(q, prop)
    data = ok(t.as_(t.manager).get(BASE))
    assert data["bookable"] == [] and len(data["projects"]) == 1
    assert ok(t.as_(t.designer).get(BASE))["bookable"] == []  # no booking capability: no queue
