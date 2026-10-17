"""Warranty and service integrity (WSV): photos through the portal only, competing writes decided on committed state
(paused-request harness, no sleeps), the immutable timeline, erasure that redacts but keeps history, and customer emails
that are few, content-free and never duplicated. SYNTHETIC data only, both engines."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ok
from tests.support.portal import PUBLIC
from tests.support.project import install, no_four_eyes, race
from tests.support.warranty import FLAGS, SERVICE, WARRANTY, Service, policy
from veda.modules.warranty.models import ServiceEvent, ServiceRequest, WarrantyEntitlement
from veda.platform.notifications import worker
from veda.platform.notifications.email import CaptureEmailProvider

pytestmark = pytest.mark.settings(**FLAGS)


@pytest.fixture
def team(api, factory):
    install(no_four_eyes())
    t = Service(api, factory)
    yield t
    install(None)
    policy(None)


# --- photos ----------------------------------------------------------------------------------------------------------------
def test_customer_photos_go_through_the_attachment_pipeline_within_limits(team):
    from veda.modules.attachments.models import Attachment

    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    first = t.photo(me, prop, rid, key="photo-key-001")
    assert first.status == 201
    reused = t.photo(me, prop, rid, key="photo-key-001", complete=False)  # the same key for other bytes: refused
    assert reused.status == 409 and reused.code == "CLIENT_REF_REUSED"
    import base64, hashlib  # noqa: E401, I001

    from tests.support.mtq import jpeg

    data = jpeg()
    body = {"mime_type": "image/jpeg", "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    one = t.customer(me, prop, rid, "photos", body, **{"Idempotency-Key": "photo-key-retry"})
    two = t.customer(me, prop, rid, "photos", body, **{"Idempotency-Key": "photo-key-retry"})
    assert (one.status, two.status) == (201, 200) and one.data["photo_id"] == two.data["photo_id"]  # a retry
    base = f"{PUBLIC}/properties/{prop['id']}/service-requests/{rid}/photos/{one.data['photo_id']}"
    assert me.call("PUT", f"{base}/content", {"data_base64": base64.b64encode(data).decode()}).status == 200
    assert me.call("POST", f"{base}/complete", {}).status == 200
    view = ok(me.property(prop["id"]))["warranty"]["projects"][0]["requests"][0]
    assert [(x["state"], x["added_by"]) for x in view["photos"]] == [("AVAILABLE", "YOU")] * 2
    url = (
        f"{PUBLIC}/properties/{prop['id']}/service-requests/{rid}/photos/{first.data['photo_id']}/content?variant=thumb"
    )
    img = me.call("GET", url)
    assert (
        img.status == 200 and img.headers["Content-Type"] == "image/webp" and "no-store" in img.headers["Cache-Control"]
    )
    att = dbh.one(sa.select(Attachment).where(Attachment.entity_type == "service_request", Attachment.entity_id == rid))
    assert att.scan_status == "CLEAN" and att.category_code == "SITE_PHOTO"
    for n in range(3, 7):
        assert t.photo(me, prop, rid, key=f"photo-key-00{n}").status == 201
    r = t.photo(me, prop, rid, key="photo-key-007")
    assert r.status == 409 and r.code == "PHOTO_LIMIT_REACHED"
    # the staff attachment routes refuse a portal session (no permission is granted to the public principal)
    assert me.api.call("POST", f"/api/v1/attachments/{att.id}/complete", {}, anonymous=True).status == 401


def test_photos_are_accepted_only_while_the_customer_is_describing_the_problem(team):
    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.do(rid, "triage", {"priority": "NORMAL"})
    r = t.photo(me, prop, rid, key="photo-key-late")
    assert r.status == 409 and r.code == "INVALID_STATE"
    t.do(rid, "information-requests", {"question": "Could you send a photo of the hinge, please?"})
    assert t.photo(me, prop, rid, key="photo-key-asked").status == 201


# --- races -----------------------------------------------------------------------------------------------------------------
def test_a_retried_submission_is_one_request(team, app, monkeypatch):
    from veda.modules.project import access as paccess

    t = team
    prop, p, me = t.handed_over()
    body = {"project_id": p["id"], "category": "HARDWARE", "description": "The wardrobe handle came loose today."}
    url = f"{PUBLIC}/properties/{prop['id']}/service-requests"
    hdr = {"X-Veda-Portal": me.token, "Idempotency-Key": "race-key-0001"}
    first, second = race(app, monkeypatch, None, lambda c: c.call("POST", url, body, headers=hdr, anonymous=True),
                         lambda: me.api.call("POST", url, body, headers=hdr, anonymous=True), module=paccess,
                         name="lock")  # fmt: skip
    assert sorted((first.status, second.status)) == [200, 201]
    assert first.data["request"]["id"] == second.data["request"]["id"]
    assert dbh.scalar(sa.select(sa.func.count(ServiceRequest.id))) == 1


def test_staff_verification_against_the_customers_confirmation(team, app, monkeypatch):
    from veda.modules.warranty import access as waccess

    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.resolved(rid)
    version = t.req(rid)["version"]
    first, second = race(app, monkeypatch, t.token(t.checker),
                         lambda c: c.post(f"{SERVICE}/{rid}/verify", {}, if_match=version),
                         lambda: t.customer(me, prop, rid, "confirm"), module=waccess)  # fmt: skip
    # decided on committed state, in whichever order the locks allowed: exactly one closes the request
    assert sorted((first.status, second.status)) == [200, 409], (first, second)
    d = t.req(rid, t.checker)
    assert d["status"] == "CLOSED" and len(d["resolutions"]) == 1
    assert (d["verified_by_kind"], d["resolutions"][0]["outcome"]) in (("CUSTOMER", "CONFIRMED"), ("STAFF", "VERIFIED"))


def test_a_coverage_decision_against_a_closure(team, app, monkeypatch):
    from veda.modules.warranty import access as waccess

    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.do(rid, "triage", {"priority": "NORMAL"})
    version = t.req(rid)["version"]
    body = {"outcome": "COVERED", "basis_path": "sources/0/warranty/0", "period_basis": "Within the first year.",
            "explanation": "This is covered by your warranty.", "internal_reason": "Within the cited statement."}  # fmt: skip
    first, second = race(app, monkeypatch, t.token(t.care),
                         lambda c: c.post(f"{SERVICE}/{rid}/assessments", body, if_match=version),
                         lambda: t.customer(me, prop, rid, "withdraw", {"reason": "It is fine now."}), module=waccess)  # fmt: skip
    # either the decision committed first and the withdrawal followed it, or the withdrawal won and the decision is
    # refused on the closed request; never a decision recorded on a request already closed
    d = t.req(rid)
    assert second.status == 200 and d["status"] == "CLOSED" and d["closure_code"] == "CUSTOMER_WITHDREW"
    assert (first.status, len(d["assessments"])) in ((200, 1), (409, 0)), first


def test_two_registrations_of_one_warranty(team, app, monkeypatch):
    from veda.modules.project import access as paccess
    from veda.modules.warranty import access as waccess

    t = team
    monkeypatch.setattr(waccess, "staff_enabled", lambda: False)
    _prop, p, _me = t.handed_over()
    monkeypatch.undo()
    url = f"{WARRANTY}/entitlements"
    first, second = race(app, monkeypatch, t.token(t.care), lambda c: c.post(url, {"project_id": p["id"]}),
                         lambda: t.as_(t.founder).post(url, {"project_id": p["id"]}), module=paccess, name="lock")  # fmt: skip
    assert sorted((first.status, second.status)) == [200, 201]
    assert first.data["id"] == second.data["id"]
    assert dbh.scalar(sa.select(sa.func.count(WarrantyEntitlement.id))) == 1


# --- history, erasure, notifications ---------------------------------------------------------------------------------------
def test_the_timeline_is_immutable_in_the_database(team, app):
    from veda.kernel import db

    t = team
    prop, p, me = t.handed_over()
    t.submit(me, prop, p)
    with pytest.raises(Exception):  # noqa: B017  (the database trigger refuses it; the driver's error class differs)
        with db.unit_of_work(write=True) as s:
            s.execute(sa.update(ServiceEvent).values(event_code="CLOSED"))
    with pytest.raises(Exception):  # noqa: B017
        with db.unit_of_work(write=True) as s:
            s.execute(sa.delete(ServiceEvent))


def test_erasure_redacts_text_keeps_rows_codes_and_the_frozen_statements(team):
    from veda.kernel import db
    from veda.kernel.context import actor, system_context
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead

    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.resolved(rid)
    before = len(dbh.rows(sa.select(ServiceEvent)))
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, prop["lead_id"]), legal_basis="SYNTHETIC erasure test", request_ref=None)
    r = dbh.get(ServiceRequest, rid)
    assert r.description == "[erased]" and r.status == "RESOLVED" and r.request_number.startswith("VS-SR-")
    assert len(dbh.rows(sa.select(ServiceEvent))) == before  # the timeline is untouched (it holds no text)
    e = dbh.one(sa.select(WarrantyEntitlement))
    assert e.terms["sources"][0]["warranty"] == ["Synthetic warranty text for tests."]  # contract terms retained


def test_customer_emails_are_content_free_and_never_duplicated(team):
    t = team
    CaptureEmailProvider.sent.clear()
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.submit(me, prop, p)  # a retry: nothing new is queued
    t.resolved(rid)
    worker.drain_all()
    worker.drain_all()
    mails = [m for m in CaptureEmailProvider.sent if m.template == "service_update" and me.email in m.to]
    subjects = [m.subject for m in mails]
    assert subjects.count("We have received your service request") == 1
    assert "Please confirm your service request is resolved" in subjects
    internal = t.req(rid, t.checker)["assessments"][0]["internal_reason"]
    assert not any(internal in m.text or "drawer" in m.text for m in mails)  # never the customer's words or a reason
