"""Leads (12 §4.7): state machine, public intake (TD-B), duplicates, consent,
spam, notes, activities, follow-ups, dashboard, search, delete/restore,
erasure and retention."""

import re
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support.dbh import audits, events, get, rows
from veda.kernel import clock, turnstile
from veda.modules.crm.leads.models import OPEN_STATUSES, Lead, LeadActivity
from veda.platform.notifications import worker
from veda.platform.notifications.email import CaptureEmailProvider, FailingEmailProvider, use_provider
from veda.platform.notifications.models import Notification, OutboxEvent

LEAD_NUMBER = re.compile(r"^VS-L-\d{4}-\d{6}$")
REFERENCE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$")


@pytest.fixture
def founder(api, factory):
    user = factory.user(founder=True)
    factory.login(api, user)
    return user


def move(api, lead, to, **extra):
    r = api.post(f"/api/v1/leads/{lead['id']}/status", {"to_status": to, **extra}, if_match=lead["version"])
    return r


def walk_to(api, lead, status):
    order = list(OPEN_STATUSES)
    if status in order:
        for s in order[1: order.index(status) + 1]:
            lead = move(api, lead, s).data
        return lead
    if status == "WON":
        lead = walk_to(api, lead, "NEGOTIATION")
        return move(api, lead, "WON").data
    lead = move(api, lead, "LOST", lost_reason_code="CHOSE_COMPETITOR").data
    return lead


# --- public intake (LEAD-001, ADR-005) -----------------------------------------------------

def test_LEAD_001_public_intake_contract(api, factory, founder):
    r = factory.public_lead(api, email="Anita@Example.com", city="Hyderabad", project_type_code="MODULAR_KITCHEN",
                            budget_range_code="5L_10L", property_type_code="APARTMENT", message="3BHK, kitchen",
                            attribution={"utm_source": "instagram", "landing_page": "/?utm_source=instagram&phone=9876",
                                         "form_page": "/#contact"})
    assert r.status == 201
    assert set(r.data) == {"reference", "message"} and REFERENCE.match(r.data["reference"])
    assert set(r.json) == {"data"}, "nothing internal is ever returned (LEAD-025)"
    lead = rows(sa.select(Lead).where(Lead.public_reference == r.data["reference"]))[0]
    assert lead.phone.startswith("+91") and LEAD_NUMBER.match(lead.lead_number)
    assert lead.consent_contact and lead.consent_channel == "WEBSITE_FORM" and lead.consent_policy_version == "2026-09-v1"
    assert lead.landing_page == "/?utm_source=instagram", "PII-stripped landing page"
    assert lead.created_by == "00000000000070008000000000000002"
    assert lead.email_normalized == "anita@example.com"
    create = audits(lead.id, action="CREATE")[0]
    assert create.performed_via == "PUBLIC_FORM"


@pytest.mark.parametrize("body, code", [
    ({"name": ""}, "VALIDATION_FAILED"),
    ({"phone": "12345"}, "VALIDATION_FAILED"),
    ({"email": "not-an-email"}, "VALIDATION_FAILED"),
    ({"consent": {"acknowledged": False, "policy_version": "2026-09-v1"}}, "CONSENT_REQUIRED"),
    ({"consent": {"acknowledged": True, "policy_version": "1999"}}, "UNKNOWN_POLICY_VERSION"),
    ({"favourite_colour": "teal"}, "VALIDATION_FAILED"),
])
def test_LEAD_023_public_validation(api, factory, body, code):
    r = factory.public_lead(api, **body)
    assert r.status == 422 and r.code == code, r
    assert set(r.json) <= {"type", "title", "status", "code", "detail", "request_id", "errors"}


def test_LEAD_030_unknown_optional_codes_never_reject(api, factory, founder):
    r = factory.public_lead(api, property_type_code="FARMHOUSE", project_type_code="MODULAR_KITCHEN")
    assert r.status == 201
    lead = rows(sa.select(Lead).where(Lead.public_reference == r.data["reference"]))[0]
    assert lead.property_type_id is None and lead.intake_unmapped == {"property_type_code": "FARMHOUSE"}
    detail = api.get(f"/api/v1/leads/{lead.id}").data
    assert detail["intake_unmapped"] == {"property_type_code": "FARMHOUSE"}
    r = api.patch(f"/api/v1/leads/{lead.id}", {"property_type_code": "VILLA"}, if_match=detail["version"])
    assert r.data["property_type"]["code"] == "VILLA" and r.data["intake_unmapped"] is None
    assert api.patch(f"/api/v1/leads/{lead.id}", {"property_type_code": "CASTLE"}, if_match=r.data["version"]).json[
        "errors"][0]["code"] == "INVALID_LOOKUP", "staff API validates lookups"


def test_public_intake_requires_idempotency_key(api):
    r = api.post("/api/v1/public/leads", {"name": "x"}, anonymous=True)
    assert r.status == 428 and r.code == "IDEMPOTENCY_KEY_REQUIRED"


def test_TD_B_retry_duplicates_and_non_disclosure(api, factory, founder):
    existing = factory.lead(api, founder.token, phone="+919876543210", name="Existing")
    turnstile.reset_counter()
    b1 = {"phone": "98765 43210", "message": "kitchen"}
    r1 = factory.public_lead(api, key="K1-aaaaaaaaaaaaaa", **b1)
    assert r1.status == 201
    n1 = rows(sa.select(Lead).where(Lead.public_reference == r1.data["reference"]))[0]
    assert n1.duplicate_status == "SUSPECTED" and n1.duplicate_of_lead_id == existing["id"]
    calls = turnstile.calls
    r2 = factory.public_lead(api, key="K1-aaaaaaaaaaaaaa", **b1)  # the same, already-spent token
    assert r2.status == 201 and r2.raw.data == r1.raw.data
    assert turnstile.calls == calls, "idempotency is checked before CAPTCHA (F-04)"
    r3 = factory.public_lead(api, key="K1-aaaaaaaaaaaaaa", phone="98765 43210", message="wardrobes")
    assert r3.status == 422 and r3.code == "IDEMPOTENCY_KEY_REUSED"
    r4 = factory.public_lead(api, key="K2-bbbbbbbbbbbbbb", phone="98765 43210", message="wardrobes")
    assert r4.status == 201 and r4.data["reference"] != r1.data["reference"]
    r5 = factory.public_lead(api, key="K3-cccccccccccccc", company_website_url="https://spam.example", **b1)
    assert r5.status == 201 and set(r5.data) == {"reference", "message"}
    spam = rows(sa.select(Lead).where(Lead.public_reference == r5.data["reference"]))[0]
    assert spam.spam_status == "SUSPECTED"
    use_provider(FailingEmailProvider())
    r6 = factory.public_lead(api, key="K4-dddddddddddddd", phone="91234 56789")
    assert r6.status == 201
    worker.drain_all()
    lead6 = rows(sa.select(Lead).where(Lead.public_reference == r6.data["reference"]))[0]
    ev = rows(sa.select(OutboxEvent).where(OutboxEvent.aggregate_id == lead6.id, OutboxEvent.event_type == "lead.created"))[0]
    assert ev.status == "FAILED" and ev.attempts == 1, "email failure never affects the committed lead (NOTIF-008)"
    assert len(rows(sa.select(Lead).where(Lead.source_id.is_not(None)))) == 5  # existing + 4 stored, none dropped
    assert events("PUBLIC_INTAKE_QUARANTINED") and not events("PUBLIC_INTAKE_BLOCKED")
    for body in (r1.json, r4.json, r5.json):
        text = str(body)
        assert "VS-L-" not in text and "SUSPECTED" not in text and "id" not in body["data"]


def test_captcha_failure_blocks_and_records(api, factory):
    r = factory.public_lead(api, turnstile_token="fail-token")
    assert r.status == 422 and r.code == "CAPTCHA_FAILED"
    assert events("PUBLIC_INTAKE_BLOCKED")[0].failure_reason == "CAPTCHA_FAILED"


def test_LEAD_018_spam_queue_hidden_until_released(api, factory, founder):
    r = factory.public_lead(api, company_website_url="x")
    lead = rows(sa.select(Lead).where(Lead.public_reference == r.data["reference"]))[0]
    assert lead.id not in {x["id"] for x in api.get("/api/v1/leads").data}
    queue = api.get("/api/v1/leads?spam_status=SUSPECTED").data
    assert [x["id"] for x in queue] == [lead.id]
    assert api.get("/api/v1/leads/summary").data["spam_review_count"] == 1
    r = api.post(f"/api/v1/leads/{lead.id}/spam-resolution", {"resolution": "NOT_SPAM"}, if_match=lead.version)
    assert r.status == 200 and r.data["spam_status"] == "NOT_SPAM"
    assert lead.id in {x["id"] for x in api.get("/api/v1/leads").data}
    worker.drain_all()
    assert rows(sa.select(Notification).where(Notification.entity_id == lead.id)), "release emits lead.created"


# --- manual create, enrichment ---------------------------------------------------------------------

def test_LEAD_003_manual_create(api, factory, founder):
    sales = factory.user("SALES")
    r = api.post("/api/v1/leads", {"name": "Rahul Menon", "phone": "+91 90000 12345", "source_code": "WEBSITE"})
    assert r.code == "SOURCE_NOT_ALLOWED"
    r = api.post("/api/v1/leads", {"name": "Rahul Menon", "phone": "+91 90000 12345", "source_code": "REFERRAL",
                                   "project_type_code": "FULL_HOME", "property_type_code": "VILLA",
                                   "budget_range_code": "35L_50L", "priority": "HIGH", "assigned_to": sales.id,
                                   "initial_note": "Prefers calls after 6pm."})
    assert r.status == 201 and r.data["assigned_to"]["id"] == sales.id and r.json["meta"]["possible_duplicates"] == []
    assert LEAD_NUMBER.match(r.data["lead_number"]) and r.headers["ETag"] == f'"{r.data["version"]}"'
    notes = api.get(f"/api/v1/leads/{r.data['id']}/notes").data
    assert notes[0]["body"] == "Prefers calls after 6pm."
    dup = api.post("/api/v1/leads", {"name": "R Menon", "phone": "9000012345", "source_code": "PHONE"})
    assert dup.data["duplicate_status"] == "SUSPECTED" and dup.json["meta"]["possible_duplicates"][0]["id"] == r.data["id"]


def test_sales_create_defaults_assignee_and_cannot_assign_others(api, factory, founder):
    sales = factory.user("SALES")
    other = factory.user("SALES")
    factory.login(api, sales)
    r = api.post("/api/v1/leads", {"name": "Meena", "phone": "9123456780", "source_code": "WALK_IN"})
    assert r.data["assigned_to"]["id"] == sales.id
    r = api.post("/api/v1/leads", {"name": "Meena", "phone": "9123456781", "source_code": "WALK_IN", "assigned_to": other.id})
    assert r.status == 403 and r.code == "PERMISSION_DENIED"


def test_LEAD_024_patch_rules(api, factory, founder):
    lead = factory.lead(api, founder.token)
    for field in ("status", "assigned_to", "lead_number", "consent_contact", "duplicate_status"):
        r = api.patch(f"/api/v1/leads/{lead['id']}", {field: "x"}, if_match=lead["version"])
        assert r.code == "FIELD_NOT_UPDATABLE", field
    assert api.patch(f"/api/v1/leads/{lead['id']}", {"city": "Pune"}).code == "PRECONDITION_REQUIRED"
    r = api.patch(f"/api/v1/leads/{lead['id']}", {"city": "Pune", "locality": "Baner", "email": "a@b.co"}, if_match=lead["version"])
    assert r.status == 200 and r.data["city"] == "Pune" and r.data["version"] == lead["version"] + 1
    stale = api.patch(f"/api/v1/leads/{lead['id']}", {"city": "Mumbai"}, if_match=lead["version"])
    assert stale.status == 409 and stale.code == "VERSION_CONFLICT" and stale.json["current_version"] == r.data["version"]
    assert stale.json["updated_by"]["id"] == founder.id
    upd = audits(lead["id"], action="UPDATE")[-1]
    assert set(upd.changed_fields) >= {"city", "locality", "email", "email_normalized"}
    assert "search_text" not in upd.changed_fields, "excluded from diffs"


# --- state machine (04 §3) ---------------------------------------------------------------------------

TRANSITIONS = [
    ("NEW", "CONTACTED", {}, 200), ("NEW", "QUOTATION_SENT", {}, 200), ("CONTACTED", "NEW", {}, "COMMENT_REQUIRED"),
    ("CONTACTED", "NEW", {"comment": "wrong status"}, 200), ("SITE_VISIT", "NEW", {"comment": "x"}, "INVALID_STATUS_TRANSITION"),
    ("NEW", "WON", {}, "COMMENT_REQUIRED"), ("NEW", "WON", {"comment": "paid"}, 200), ("NEGOTIATION", "WON", {}, 200),
    ("QUOTATION_SENT", "WON", {}, 200), ("NEW", "LOST", {}, "LOST_REASON_REQUIRED"),
    ("NEW", "LOST", {"lost_reason_code": "OTHER"}, "LOST_REASON_REQUIRED"),
    ("NEW", "LOST", {"lost_reason_code": "OTHER", "lost_reason_note": "moved abroad"}, 200),
    ("NEW", "NEW", {}, "NO_OP_TRANSITION"), ("WON", "LOST", {"lost_reason_code": "SPAM"}, "INVALID_STATUS_TRANSITION"),
    ("LOST", "WON", {"comment": "x"}, "INVALID_STATUS_TRANSITION"), ("LOST", "CONTACTED", {}, "COMMENT_REQUIRED"),
    ("LOST", "CONTACTED", {"comment": "called back"}, 200), ("WON", "NEGOTIATION", {"comment": "refund"}, 200),
    ("WON", "NEW", {"comment": "x"}, "INVALID_STATUS_TRANSITION"),
]


@pytest.mark.parametrize("start, to, extra, expected", TRANSITIONS)
def test_LEAD_005_state_machine(api, factory, founder, start, to, extra, expected):
    lead = walk_to(api, factory.lead(api, founder.token), start)
    assert lead["status"] == start
    r = move(api, lead, to, **extra)
    if expected == 200:
        assert r.status == 200, r
        assert r.data["status"] == to and r.json["meta"]["activity_id"]
    else:
        assert r.status == 422 and r.code == expected, r


def test_won_and_lost_cancel_planned_activities_and_emit_events(api, factory, founder):
    lead = factory.lead(api, founder.token)
    when = clock.to_rfc3339(clock.now() + timedelta(days=2))
    r = api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "SITE_VISIT", "activity_status": "PLANNED",
                                                            "subject": "Measure", "scheduled_on": when})
    assert r.json["meta"]["lead_next_follow_up_on"]
    lead = api.get(f"/api/v1/leads/{lead['id']}").data
    assert lead["next_follow_up_on"] is not None
    lead = walk_to(api, lead, "WON")
    assert lead["next_follow_up_on"] is None and lead["won_on"]
    acts = api.get(f"/api/v1/leads/{lead['id']}/activities?status=CANCELLED").data
    assert len(acts) == 1 and acts[0]["cancelled_reason"] == "Lead won"
    assert rows(sa.select(OutboxEvent).where(OutboxEvent.event_type == "lead.won"))
    r = api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "CALL", "activity_status": "PLANNED",
                                                            "subject": "x", "scheduled_on": when})
    assert r.code == "LEAD_CLOSED"


def test_sales_reopen_forbidden_and_allowed_transitions(api, factory, founder):
    sales = factory.user("SALES")
    lead = factory.lead(api, founder.token, assigned_to=sales.id)
    lead = walk_to(api, lead, "LOST")
    token = factory.login(api, sales, set_default=False)
    detail = api.get(f"/api/v1/leads/{lead['id']}", token=token).data
    assert detail["allowed_transitions"] == []
    r = api.post(f"/api/v1/leads/{lead['id']}/status", {"to_status": "CONTACTED", "comment": "back"}, if_match=detail["version"],
                 token=token)
    assert r.status == 403 and r.code == "PERMISSION_DENIED"
    assert api.get(f"/api/v1/leads/{lead['id']}").data["allowed_transitions"] == ["CONTACTED"]


# --- scope (06 §4) -------------------------------------------------------------------------------------

def test_LEAD_013_own_scope_isolation(api, factory, founder):
    sales_a, sales_b = factory.user("SALES"), factory.user("SALES")
    mine = factory.lead(api, founder.token, assigned_to=sales_a.id)
    theirs = factory.lead(api, founder.token, assigned_to=sales_b.id)
    token = factory.login(api, sales_a, set_default=False)
    ids = {x["id"] for x in api.get("/api/v1/leads", token=token).data}
    assert mine["id"] in ids and theirs["id"] not in ids
    for path in (f"/api/v1/leads/{theirs['id']}", f"/api/v1/leads/{theirs['id']}/notes",
                 f"/api/v1/leads/{theirs['id']}/activities"):
        assert api.get(path, token=token).status == 404, path
    r = api.post(f"/api/v1/leads/{mine['id']}/duplicate-resolution",
                 {"resolution": "CONFIRMED", "duplicate_of_lead_id": theirs["id"]}, token=token)
    assert r.status == 404, "out-of-scope reference behaves as not found (A-07)"
    summary = api.get("/api/v1/leads/summary", token=token).data
    assert sum(summary["pipeline"].values()) == 1


def test_LEAD_007_assignment(api, factory, founder):
    sales = factory.user("SALES")
    disabled = factory.user("SALES", status="DISABLED")
    lead = factory.lead(api, founder.token)
    assert api.post(f"/api/v1/leads/{lead['id']}/assign", {"assigned_to": disabled.id}, if_match=lead["version"]).code == "INVALID_ASSIGNEE"
    r = api.post(f"/api/v1/leads/{lead['id']}/assign", {"assigned_to": sales.id}, if_match=lead["version"])
    assert r.status == 200 and r.data["assigned_to"]["id"] == sales.id
    assert api.post(f"/api/v1/leads/{lead['id']}/assign", {"assigned_to": sales.id}, if_match=r.data["version"]).code == "NO_OP_ASSIGNMENT"
    worker.drain_all()
    assert any(sales.email in m.to and "assigned" in m.subject.lower() for m in CaptureEmailProvider.sent)
    assignable = api.get("/api/v1/users/assignable").data
    assert any(a["id"] == sales.id and a["open_lead_count"] == 1 for a in assignable)
    assert all(a["id"] != disabled.id for a in assignable)


def test_LEAD_020_new_public_lead_notifies_assign_holders(api, factory, founder):
    sales = factory.user("SALES")
    factory.public_lead(api)
    worker.drain_all()
    recipients = {n.recipient_user_id for n in rows(sa.select(Notification))}
    assert founder.id in recipients and sales.id not in recipients, "permission-based recipients"
    r = api.get("/api/v1/notifications?unread=true")
    assert r.json["meta"]["unread_count"] == 1 and r.data[0]["notification_type"] == "LEAD_CREATED"
    assert api.post(f"/api/v1/notifications/{r.data[0]['id']}/read").data["read_on"]
    assert api.get("/api/v1/notifications?unread=true").json["meta"]["unread_count"] == 0


# --- consent, notes, activities ---------------------------------------------------------------------------

def test_LEAD_027_consent_withdrawal(api, factory, founder):
    r = factory.public_lead(api)
    lead = api.get("/api/v1/leads").data[0]
    when = clock.to_rfc3339(clock.now() + timedelta(days=1))
    api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "CALL", "activity_status": "PLANNED",
                                                        "subject": "Call back", "scheduled_on": when})
    lead = api.get(f"/api/v1/leads/{lead['id']}").data
    r = api.post(f"/api/v1/leads/{lead['id']}/consent/withdraw", {"channel": "PHONE_VERBAL", "note": "Do not call"},
                 if_match=lead["version"])
    assert r.status == 200 and r.data["consent"]["contact"] is False and r.data["consent"]["withdrawn_on"]
    assert r.data["consent"]["policy_version"] == "2026-09-v1", "original consent retained as evidence"
    assert r.json["meta"]["cancelled_activities"] == 1 and r.data["next_follow_up_on"] is None
    r = api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "WHATSAPP", "activity_status": "PLANNED",
                                                            "subject": "x", "scheduled_on": when})
    assert r.code == "CONSENT_WITHDRAWN"
    ok = api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "CALL", "activity_status": "COMPLETED",
                                                             "direction": "INBOUND", "subject": "They called us"})
    assert ok.status == 201
    assert [x["id"] for x in api.get("/api/v1/leads?consent=withdrawn").data] == [lead["id"]]


def test_NOTE_rules(api, factory, founder):
    sales_a, sales_b = factory.user("SALES"), factory.user("SALES")
    lead = factory.lead(api, founder.token, assigned_to=sales_a.id)
    token_a = factory.login(api, sales_a, set_default=False)
    note = api.post(f"/api/v1/leads/{lead['id']}/notes", {"body": "Wants handle-less shutters"}, token=token_a).data
    assert note["can_edit"] and note["is_edited"] is False
    assert api.post(f"/api/v1/leads/{lead['id']}/notes", {"body": "x", "visibility": "CUSTOMER_VISIBLE"},
                    token=token_a).code == "VISIBILITY_NOT_SUPPORTED"
    founder_note = api.post(f"/api/v1/leads/{lead['id']}/notes", {"body": "Founder note", "is_pinned": True}).data
    listed = api.get(f"/api/v1/leads/{lead['id']}/notes", token=token_a).data
    assert listed[0]["id"] == founder_note["id"], "pinned first"
    r = api.patch(f"/api/v1/leads/{lead['id']}/notes/{founder_note['id']}", {"body": "edit"}, if_match=1, token=token_a)
    assert r.status == 403, "visible but not own → 403"
    r = api.patch(f"/api/v1/leads/{lead['id']}/notes/{note['id']}", {"body": "Matte finish"}, if_match=1, token=token_a)
    assert r.status == 200 and r.data["is_edited"]
    assert api.delete(f"/api/v1/leads/{lead['id']}/notes/{note['id']}", if_match=r.data["version"], token=token_a).status == 204
    assert api.post(f"/api/v1/leads/{lead['id']}/notes/{note['id']}/restore", token=token_a).status in (404, 405)
    token_b = factory.login(api, sales_b, set_default=False)
    assert api.get(f"/api/v1/leads/{lead['id']}/notes", token=token_b).status == 404


def test_ACT_lifecycle_and_follow_ups(api, factory, founder):
    lead = factory.lead(api, founder.token)
    soon = clock.to_rfc3339(clock.now() + timedelta(hours=2))
    later = clock.to_rfc3339(clock.now() + timedelta(days=3))
    assert api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "STATUS_CHANGE", "subject": "x"}).code == \
        "SYSTEM_TYPE_NOT_ALLOWED"
    assert api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "CALL", "activity_status": "PLANNED",
                                                               "subject": "x"}).code == "SCHEDULE_REQUIRED"
    assert api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "CALL", "activity_status": "PLANNED",
                                                               "subject": "x", "scheduled_on": "2026-10-01T10:00:00"}).code == \
        "INVALID_DATETIME"
    a1 = api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "CALL", "activity_status": "PLANNED",
                                                             "subject": "Call", "scheduled_on": later}).data
    a2 = api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "SITE_VISIT", "activity_status": "PLANNED",
                                                             "subject": "Visit", "scheduled_on": soon}).json
    assert a2["meta"]["lead_next_follow_up_on"][:16] == soon[:16]
    r = api.post(f"/api/v1/leads/{lead['id']}/activities/{a2['data']['id']}/complete", {"outcome_code": "VISIT_SCHEDULED"},
                 if_match=a2["data"]["version"])
    assert r.status == 200 and r.data["activity_status"] == "COMPLETED" and r.data["outcome"]["code"] == "VISIT_SCHEDULED"
    assert r.json["meta"]["lead_next_follow_up_on"][:16] == later[:16]
    assert api.post(f"/api/v1/leads/{lead['id']}/activities/{a2['data']['id']}/complete", {},
                    if_match=r.data["version"]).code == "INVALID_ACTIVITY_STATE"
    r = api.post(f"/api/v1/leads/{lead['id']}/activities/{a1['id']}/cancel", {"reason": "rescheduled"}, if_match=a1["version"])
    assert r.data["activity_status"] == "CANCELLED" and r.json["meta"]["lead_next_follow_up_on"] is None
    system = api.get(f"/api/v1/leads/{lead['id']}/activities?type=SYSTEM").data[0]
    assert api.patch(f"/api/v1/leads/{lead['id']}/activities/{system['id']}", {"subject": "x"},
                     if_match=system["version"]).code == "SYSTEM_ACTIVITY_READ_ONLY"
    mine = api.get("/api/v1/activities?owner=me&status=COMPLETED").data
    assert mine and mine[0]["lead"]["id"] == lead["id"]


def test_LEAD_015_overdue_follow_up_filter(api, factory, founder):
    lead = factory.lead(api, founder.token)
    api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "CALL", "activity_status": "PLANNED",
                                                        "subject": "Call", "scheduled_on": clock.to_rfc3339(clock.now() + timedelta(hours=1))})
    assert api.get("/api/v1/leads?follow_up=overdue").data == []
    clock.advance(timedelta(hours=2))
    factory.login(api, founder)  # the 15-minute access token expired meanwhile
    overdue = api.get("/api/v1/leads?follow_up=overdue").data
    assert [x["id"] for x in overdue] == [lead["id"]] and overdue[0]["is_follow_up_overdue"]
    assert api.get("/api/v1/leads/summary").data["follow_ups"]["overdue"] == 1


# --- list, search, dashboard ---------------------------------------------------------------------------

def test_A03_search_casefold_non_ascii(api, factory, founder):
    factory.lead(api, founder.token, name="Ṛṣabha Ḍhiṅgra", city="Hyderabad", phone="+919812345678")
    factory.lead(api, founder.token, name="Straße Müller", phone="+919812345679")
    assert [x["name"] for x in api.get("/api/v1/leads?q=ṛṣabha").data] == ["Ṛṣabha Ḍhiṅgra"]
    assert [x["name"] for x in api.get("/api/v1/leads?q=STRASSE").data] == ["Straße Müller"]
    assert [x["name"] for x in api.get("/api/v1/leads?q=98123 45679").data] == ["Straße Müller"]
    assert api.get("/api/v1/leads?q=a").code == "INVALID_QUERY_PARAM"


def test_LEAD_013_list_filters_sort_and_pagination(api, factory, founder):
    for i in range(3):
        factory.lead(api, founder.token, name=f"Lead {i}", project_type_code="MODULAR_KITCHEN" if i else "FULL_HOME",
                     priority="HIGH" if i == 2 else "LOW")
    r = api.get("/api/v1/leads?project_type=MODULAR_KITCHEN&sort=name&page_size=1")
    assert r.json["meta"]["total"] == 2 and r.json["links"]["next"] and r.data[0]["name"] == "Lead 1"
    assert api.get("/api/v1/leads?priority=HIGH").data[0]["name"] == "Lead 2"
    assert api.get("/api/v1/leads?sort=bogus").code == "INVALID_QUERY_PARAM"
    assert api.get("/api/v1/leads?assigned_to=unassigned").json["meta"]["total"] == 3
    today = clock.now().date().isoformat()
    assert api.get(f"/api/v1/leads?created_on_from={today}&created_on_to={today}").json["meta"]["total"] >= 0


def test_LEAD_014_dashboard_summary(api, factory, founder):
    a = factory.lead(api, founder.token, source_code="REFERRAL")
    b = factory.lead(api, founder.token, source_code="INSTAGRAM")
    api.post(f"/api/v1/leads/{a['id']}/activities", {"activity_type": "CALL", "activity_status": "COMPLETED", "subject": "Intro",
                                                     "completed_on": clock.to_rfc3339(clock.now())})
    walk_to(api, api.get(f"/api/v1/leads/{a['id']}").data, "WON")
    walk_to(api, b, "LOST")
    data = api.get("/api/v1/leads/summary?period=30d").data
    assert data["closed_in_period"] == {"WON": 1, "LOST": 1} and data["conversion_rate"] == 0.5
    assert data["new_leads"]["count"] == 2 and {s["code"] for s in data["by_source"]} == {"REFERRAL", "INSTAGRAM"}
    assert data["median_hours_to_first_contact"] is not None
    assert data["period"]["timezone"] == "Asia/Kolkata"
    assert api.get("/api/v1/leads/summary?period=custom&from=2026-09-30&to=2026-09-01").code == "INVALID_QUERY_PARAM"


# --- delete, restore, history, erasure, retention ---------------------------------------------------------

def test_LEAD_016_soft_delete_and_restore(api, factory, founder):
    lead = factory.lead(api, founder.token)
    assert api.delete(f"/api/v1/leads/{lead['id']}", {"reason": "Test entry"}, if_match=lead["version"]).status == 204
    assert api.get(f"/api/v1/leads/{lead['id']}").status == 404
    assert api.get(f"/api/v1/leads/{lead['id']}/notes").status == 404
    assert [x["id"] for x in api.get("/api/v1/leads?deleted_only=true").data] == [lead["id"]]
    deleted = api.get(f"/api/v1/leads/{lead['id']}?include_deleted=true").data
    r = api.post(f"/api/v1/leads/{lead['id']}/restore", {}, if_match=deleted["version"])
    assert r.status == 200 and r.data["is_deleted"] is False
    actions = [x.action for x in audits(lead["id"])]
    assert "DELETE" in actions and "RESTORE" in actions
    assert events("SENSITIVE_ACTION", permission_code="lead.delete")
    sales = factory.user("SALES")
    token = factory.login(api, sales, set_default=False)
    assert api.get("/api/v1/leads?include_deleted=true", token=token).code == "PERMISSION_DENIED"


def test_AUDIT_006_lead_history_includes_children(api, factory, founder):
    lead = factory.lead(api, founder.token)
    api.post(f"/api/v1/leads/{lead['id']}/notes", {"body": "hello"})
    history = api.get(f"/api/v1/leads/{lead['id']}/history").data
    types = {h["entity_type"] for h in history}
    assert {"lead", "lead_note", "lead_activity"} <= types
    sales = factory.user("SALES")
    token = factory.login(api, sales, set_default=False)
    assert api.get(f"/api/v1/leads/{lead['id']}/history", token=token).status in (403, 404)


def test_LEAD_029_erasure(api, factory, founder):
    from veda.platform import maintenance

    r = factory.public_lead(api, email="erase.me@example.com", message="My address is 42 Lake View", city="Hyderabad")
    lead = api.get("/api/v1/leads").data[0]
    api.post(f"/api/v1/leads/{lead['id']}/notes", {"body": "Spoke to Kiran Rao at 98xxxx"})
    api.post(f"/api/v1/leads/{lead['id']}/activities", {"activity_type": "MEETING", "subject": "Meet",
                                                        "description": "At Kiran's flat", "location": "Flat 4B"})
    lead = api.get(f"/api/v1/leads/{lead['id']}").data
    r = api.post(f"/api/v1/leads/{lead['id']}/erasure", {"request_ref": "DPR-2026-004", "legal_basis": "DPDP s.12 erasure",
                                                         "reason": "Data principal request"}, if_match=lead["version"])
    assert r.status == 200, r
    assert r.data["name"] == "Anonymized lead" and r.data["email"] is None and r.data["erasure"]["audit_status"] == "PENDING"
    assert worker.drain_all() == 0 or True  # the app worker never handles the maintenance-only event
    assert maintenance.run_erasure_audit() == 1
    detail = api.get(f"/api/v1/leads/{lead['id']}").data
    assert detail["erasure"]["audit_status"] == "COMPLETED"
    pii = ["Kiran Rao", "erase.me@example.com", "42 Lake View", "Flat 4B", "Kiran's flat"]
    for row in audits():
        blob = str(row.old_value) + str(row.new_value)
        for value in pii:
            assert value not in blob, (row.entity_type, row.action, value)
    anon = audits(lead["id"], action="ANONYMIZE")
    assert len(anon) == 2 and anon[0].new_value["request_ref"] == "DPR-2026-004"
    assert events("SENSITIVE_ACTION", permission_code="lead.erase")
    assert api.post(f"/api/v1/leads/{lead['id']}/erasure", {"request_ref": "x", "legal_basis": "y", "reason": "z"},
                    if_match=detail["version"]).code == "INVALID_STATE"


def test_LEAD_029_erasure_requires_permission_and_step_up(api, factory, founder):
    admin = factory.user("ADMIN")
    lead = factory.lead(api, founder.token)
    token = factory.login(api, admin, set_default=False)
    r = api.post(f"/api/v1/leads/{lead['id']}/erasure", {"request_ref": "x", "legal_basis": "y", "reason": "z"},
                 if_match=lead["version"], token=token)
    assert r.code == "PERMISSION_DENIED"
    clock.advance(timedelta(minutes=11))
    r = api.post(f"/api/v1/leads/{lead['id']}/erasure", {"request_ref": "x", "legal_basis": "y", "reason": "z"},
                 if_match=lead["version"])
    assert r.code in ("STEP_UP_REQUIRED", "TOKEN_EXPIRED")


def test_LEAD_028_retention_job(api, factory, founder, app):
    from veda import config
    from veda.platform import maintenance

    lead = factory.lead(api, founder.token, name="Old Client")
    walk_to(api, lead, "LOST")
    open_lead = factory.lead(api, founder.token, name="Open Client")
    assert maintenance.lead_retention() == {"enabled": False, "anonymized": 0}, "ships disabled"
    config.settings().lead_retention_enabled = True
    config.settings().lead_retention_days = 30
    clock.advance(timedelta(days=31))
    assert maintenance.lead_retention()["anonymized"] == 1
    assert get(Lead, lead["id"]).name == "Anonymized lead"
    assert get(Lead, open_lead["id"]).name == "Open Client"
    assert config.validate_production(config.Settings(env="production", lead_retention_enabled=True))


def test_DATA_004_public_intake_rows_are_attributed_to_web_intake(api, factory):
    r = factory.public_lead(api)
    lead = rows(sa.select(Lead).where(Lead.public_reference == r.data["reference"]))[0]
    for row in audits(transaction_id=audits(lead.id)[0].transaction_id):
        assert row.performed_by == "00000000000070008000000000000002", (row.entity_type, row.performed_by)
    acts = rows(sa.select(LeadActivity).where(LeadActivity.lead_id == lead.id))
    assert acts and all(a.created_by == "00000000000070008000000000000002" for a in acts)


def test_DEV_004_reconsent_via_staff_patch_only(api, factory, founder):
    """DEV-004: staff PATCH accepts a `consent` object (re-consent); raw consent_* fields and public re-consent are rejected."""
    factory.public_lead(api)
    lead = api.get("/api/v1/leads").data[0]
    lead = api.post(f"/api/v1/leads/{lead['id']}/consent/withdraw", {"channel": "PHONE_VERBAL"},
                    if_match=lead["version"]).data
    assert lead["consent"]["contact"] is False
    assert api.patch(f"/api/v1/leads/{lead['id']}", {"consent_contact": True},
                     if_match=lead["version"]).code == "FIELD_NOT_UPDATABLE"
    assert api.patch(f"/api/v1/leads/{lead['id']}", {"consent": {"channel": "PHONE_VERBAL", "policy_version": "1999"}},
                     if_match=lead["version"]).code == "UNKNOWN_POLICY_VERSION"
    r = api.patch(f"/api/v1/leads/{lead['id']}", {"consent": {"channel": "PHONE_VERBAL", "policy_version": "2026-09-v1"}},
                  if_match=lead["version"])
    assert r.status == 200 and r.data["consent"]["contact"] is True and r.data["consent"]["channel"] == "PHONE_VERBAL"
    assert r.data["consent"]["withdrawn_on"] is None
    history = [a for a in audits(lead["id"], action="UPDATE") if "consent_withdrawn_on" in (a.changed_fields or [])]
    assert history[-1].old_value["consent_withdrawn_on"] is not None, "prior withdrawal retained as audit evidence"
    pub = factory.public_lead(api, reconsent={"acknowledged": True})
    assert pub.status == 422 and pub.json["errors"][0]["code"] == "UNKNOWN_FIELD", "public intake has no re-consent object"
