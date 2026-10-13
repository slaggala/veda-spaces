"""MTQ B1-T05: the measurement-visit state machine and lead synchronisation (blueprint §4.1, §12.3)."""

from __future__ import annotations

from datetime import timedelta

import pytest
import sqlalchemy as sa

from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.kernel.ids import SYSTEM_USER_ID
from veda.modules.crm.leads.models import Lead, LeadActivity
from veda.modules.mtq.models import MeasurementSet, MeasurementVisit
from veda.platform.audit.models import AuditLog

ON = pytest.mark.settings(mtq_site_enabled=True)


@pytest.fixture
def team(api, factory):
    sales = factory.user("SALES")
    surveyor = factory.user("SURVEYOR")
    other_surveyor = factory.user("SURVEYOR")
    designer = factory.user("DESIGNER")
    factory.login(api, sales)
    return {"sales": sales, "surveyor": surveyor, "other": other_surveyor, "designer": designer}


def setup_property(api) -> dict:
    lead = api.post("/api/v1/leads", {"name": "Kiran Das", "phone": "+91 90000 33333", "source_code": "PHONE"}).data
    prop = api.post("/api/v1/properties", {"lead_id": lead["id"], "property_type_code": "APARTMENT",
                                           "template_key": "APARTMENT_2BHK"}).data  # fmt: skip
    return {"lead": lead, "property": prop}


def when(hours=24):
    return clock.to_rfc3339(clock.now() + timedelta(hours=hours))


def status(api, visit, to, **extra):
    return api.post(f"/api/v1/measurement-visits/{visit['id']}/status", {"to_status": to, **extra},
                    if_match=visit["version"])  # fmt: skip


def test_routes_are_404_while_the_flag_is_off(api, team):
    zero = "0" * 32
    assert api.get("/api/v1/measurement-visits").status == 404
    assert api.post("/api/v1/measurement-visits", {}).status == 404
    assert api.post(f"/api/v1/measurement-visits/{zero}/status", {}).status == 404


@ON
def test_schedule_moves_the_lead_forward_through_the_lead_service_as_system(api, team):
    ctx = setup_property(api)
    r = api.post("/api/v1/measurement-visits", {"property_id": ctx["property"]["id"], "survey_level_code": "FULL",
                                                "scheduled_start_on": when(), "assigned_to": team["surveyor"].id,
                                                "customer_contact_name": "Kiran",
                                                "customer_contact_phone": "+91 90000 33333"})  # fmt: skip
    assert r.status == 201, r
    v = r.data
    assert v["status"] == "SCHEDULED" and v["visit_number"].startswith("VS-M-") and v["lead_activity_id"]
    assert v["customer_contact_phone"] == "+919000033333"
    lead = api.get(f"/api/v1/leads/{ctx['lead']['id']}").data
    assert lead["status"] == "SITE_VISIT"
    with db.unit_of_work(write=False) as s:
        acts = s.execute(sa.select(LeadActivity).where(LeadActivity.lead_id == ctx["lead"]["id"])).scalars().all()
        status_change = [a for a in acts if a.activity_type == "STATUS_CHANGE"]
        assert len(status_change) == 1 and status_change[0].to_status == "SITE_VISIT"
        assert status_change[0].owner_user_id == SYSTEM_USER_ID and status_change[0].created_by == SYSTEM_USER_ID
        visit_act = s.get(LeadActivity, v["lead_activity_id"])
        assert visit_act.is_system_generated and visit_act.metadata_["measurement_visit_id"] == v["id"]
        # The visit itself is stamped with the user who scheduled it, the lead change with SYSTEM.
        visit_row = s.get(MeasurementVisit, v["id"])
        assert visit_row.created_by == team["sales"].id
        lead_updates = s.execute(
            sa.select(AuditLog.performed_by).where(AuditLog.entity_type == "lead", AuditLog.entity_id == ctx["lead"]["id"],
                                                   AuditLog.action == "UPDATE")
        ).scalars().all()  # fmt: skip
        assert SYSTEM_USER_ID in lead_updates


@ON
def test_never_backward_and_never_on_a_closed_lead(api, team):
    ctx = setup_property(api)
    lead = ctx["lead"]
    for to in ("CONTACTED", "SITE_VISIT", "QUOTATION_SENT"):
        lead = api.post(f"/api/v1/leads/{lead['id']}/status", {"to_status": to}, if_match=lead["version"]).data
    v = api.post("/api/v1/measurement-visits", {"property_id": ctx["property"]["id"], "scheduled_start_on": when(),
                                                "assigned_to": team["surveyor"].id}).data  # fmt: skip
    assert api.get(f"/api/v1/leads/{lead['id']}").data["status"] == "QUOTATION_SENT"  # unchanged
    assert v["status"] == "SCHEDULED"
    lead = api.get(f"/api/v1/leads/{lead['id']}").data
    won = api.post(f"/api/v1/leads/{lead['id']}/status", {"to_status": "WON"}, if_match=lead["version"])
    assert won.status == 200, won
    refused = api.post("/api/v1/measurement-visits", {"property_id": ctx["property"]["id"], "scheduled_start_on": when(),
                                                      "assigned_to": team["surveyor"].id})  # fmt: skip
    assert refused.status == 422 and refused.code == "LEAD_CLOSED"


@ON
def test_only_capture_holders_can_be_assigned(api, team):
    ctx = setup_property(api)
    base = {"property_id": ctx["property"]["id"], "scheduled_start_on": when()}
    bad = api.post("/api/v1/measurement-visits", {**base, "assigned_to": team["sales"].id})
    assert bad.status == 422 and bad.code == "INVALID_ASSIGNEE"
    assert api.post("/api/v1/measurement-visits", {**base, "assigned_to": team["designer"].id}).status == 201
    no_one = api.post("/api/v1/measurement-visits", {**base})
    assert no_one.status == 422


@ON
def test_full_lifecycle_start_complete_and_terminal(api, factory, team):
    ctx = setup_property(api)
    v = api.post("/api/v1/measurement-visits", {"property_id": ctx["property"]["id"]}).data
    assert v["status"] == "REQUESTED" and "SCHEDULED" in v["allowed_transitions"]
    wrong = status(api, v, "IN_PROGRESS")
    assert wrong.status == 422 and wrong.code == "INVALID_STATUS_TRANSITION"
    v = status(api, v, "SCHEDULED", scheduled_start_on=when(), assigned_to=team["surveyor"].id).data
    assert status(api, v, "IN_PROGRESS").status == 403  # SALES does not capture
    factory.login(api, team["other"])
    assert api.get(f"/api/v1/measurement-visits/{v['id']}").status == 404  # not their visit, not their lead
    factory.login(api, team["surveyor"])
    mine = api.get("/api/v1/measurement-visits?assigned_to=me").data
    assert [x["id"] for x in mine] == [v["id"]]
    started = status(api, v, "IN_PROGRESS")
    assert started.status == 200 and started.data["started_on"]
    v = started.data
    early = status(api, v, "COMPLETED")
    assert early.status == 409 and early.code == "SET_NOT_SUBMITTED"
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.add(MeasurementSet(property_id=v["property_id"], measurement_visit_id=v["id"], revision_no=1, status="SUBMITTED",
                             survey_level_code="FULL", method_code="LASER", unit_system_code="MM",
                             captured_by=team["surveyor"].id, submitted_on=db.tx_time(s)))  # fmt: skip
    done = status(api, v, "COMPLETED")
    assert done.status == 200 and done.data["status"] == "COMPLETED" and done.data["allowed_transitions"] == []
    after = status(api, done.data, "CANCELLED", reason="late")
    assert after.status == 409


@ON
def test_cancel_needs_a_reason_and_no_show(api, team):
    ctx = setup_property(api)
    v = api.post("/api/v1/measurement-visits", {"property_id": ctx["property"]["id"], "scheduled_start_on": when(),
                                                "assigned_to": team["surveyor"].id}).data  # fmt: skip
    assert status(api, v, "CANCELLED").status == 422
    ns = status(api, v, "NO_SHOW")
    assert ns.status == 200 and ns.data["status"] == "NO_SHOW"
    v2 = api.post("/api/v1/measurement-visits", {"property_id": ctx["property"]["id"]}).data
    c = status(api, v2, "CANCELLED", reason="Customer postponed")
    assert c.status == 200 and c.data["cancel_reason"] == "Customer postponed"


@ON
def test_reschedule_records_an_activity_and_keeps_the_lead(api, team):
    ctx = setup_property(api)
    v = api.post("/api/v1/measurement-visits", {"property_id": ctx["property"]["id"], "scheduled_start_on": when(),
                                                "assigned_to": team["surveyor"].id}).data  # fmt: skip
    later = when(48)
    r = status(api, v, "SCHEDULED", scheduled_start_on=later, assigned_to=team["other"].id)
    assert r.status == 200 and r.data["scheduled_start_on"] == later and r.data["assigned_to"]["id"] == team["other"].id
    bad_window = status(api, r.data, "SCHEDULED", scheduled_start_on=later,
                        scheduled_end_on=clock.to_rfc3339(clock.now() + timedelta(hours=100)))  # fmt: skip
    assert bad_window.status == 422
    with db.unit_of_work(write=False) as s:
        events = [
            a.metadata_.get("event")
            for a in s.execute(sa.select(LeadActivity).where(LeadActivity.lead_id == ctx["lead"]["id"])).scalars()
            if a.metadata_ and "measurement_visit_id" in a.metadata_
        ]
    assert sorted(events) == ["reschedule", "schedule"]


@ON
def test_if_match_and_idempotency(api, team):
    ctx = setup_property(api)
    v = api.post("/api/v1/measurement-visits", {"property_id": ctx["property"]["id"]}).data
    no_match = api.post(f"/api/v1/measurement-visits/{v['id']}/status", {"to_status": "CANCELLED", "reason": "x"})
    assert no_match.status == 428
    stale = api.post(f"/api/v1/measurement-visits/{v['id']}/status", {"to_status": "CANCELLED", "reason": "x"},
                     if_match=v["version"] + 3)  # fmt: skip
    assert stale.status == 409
    key = {"Idempotency-Key": "visit-status-0001-abcdef"}
    body = {"to_status": "SCHEDULED", "scheduled_start_on": when(), "assigned_to": team["surveyor"].id}
    first = api.post(f"/api/v1/measurement-visits/{v['id']}/status", body, if_match=v["version"], headers=key)
    again = api.post(f"/api/v1/measurement-visits/{v['id']}/status", body, if_match=v["version"], headers=key)
    assert first.status == 200 and again.status == 200 and again.data == first.data
    with db.unit_of_work(write=False) as s:
        n = s.execute(
            sa.select(sa.func.count(LeadActivity.id)).where(
                LeadActivity.lead_id == ctx["lead"]["id"], LeadActivity.activity_type == "STATUS_CHANGE"
            )
        ).scalar()
    assert n == 1  # one transition, not two


@ON
def test_patch_contact_details_and_erasure(api, team):
    from veda.modules.crm.leads import service as lead_service

    ctx = setup_property(api)
    v = api.post("/api/v1/measurement-visits", {"property_id": ctx["property"]["id"], "access_notes": "Gate 2"}).data
    r = api.patch(f"/api/v1/measurement-visits/{v['id']}", {"customer_contact_name": "Kiran D"}, if_match=v["version"])
    assert r.status == 200 and r.data["customer_contact_name"] == "Kiran D"
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, ctx["lead"]["id"]), legal_basis="TEST", request_ref=None)
    gone = api.get(f"/api/v1/measurement-visits/{v['id']}").data
    assert gone["customer_contact_name"] is None and gone["access_notes"] is None
    assert api.patch(f"/api/v1/measurement-visits/{v['id']}", {"access_notes": "x"},
                     if_match=gone["version"]).status == 409  # fmt: skip
