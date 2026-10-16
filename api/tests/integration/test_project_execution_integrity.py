"""Project execution integrity (PEX): forced interleavings on both engines (no sleeps: ``tests.support.race``), lead
erasure of execution records and the handover package, and staff notifications. SYNTHETIC data only."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.api import ApiClient
from tests.support.commercial import ok
from tests.support.portal import PUBLIC, Portal
from tests.support.project import BASE, advance_to, delivery, install, no_four_eyes, race
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.modules.project.models import (
    ProjectCustomerReport,
    ProjectEvent,
    ProjectHandoverPackage,
    ProjectQcCheck,
    ProjectWorkPackage,
)
from veda.platform.notifications.models import Notification

pytestmark = pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
                                  customer_portal_enabled=True, project_lifecycle_enabled=True,
                                  project_delivery_portal_enabled=True)  # fmt: skip


@pytest.fixture
def team(api, factory):
    t = Portal(api, factory)
    install(no_four_eyes())
    yield t
    install(None)


def _today() -> str:
    return clock.now().date().isoformat()


def _booked(t: Portal, key: str = "2BHK") -> tuple[dict, dict]:
    prop, _, q = t.accepted(key)
    p = t.book(q, prop)
    t.staff(p)
    return prop, t.get(p)


def _client(app, t: Portal, user) -> ApiClient:
    c = ApiClient(app.test_client())
    c.token = t.token(user)
    return c


def _count(model, *where) -> int:
    return dbh.scalar(sa.select(sa.func.count()).select_from(model).where(*where))


# --- races ---------------------------------------------------------------------------------------------------------------
def test_two_simultaneous_rechecks_of_one_failure_land_once(team, app, monkeypatch):
    t = team
    _, p = _booked(t)
    p = advance_to(t, p, "QUALITY_CHECK", qc=())
    d = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/qc-checks", {"category": "FINISH_AND_SURFACES", "result": "FAIL",
                                                            "observation": "Gap"}), 201)  # fmt: skip
    failed = d["qc"]["history"][0]
    body = {"category": "FINISH_AND_SURFACES", "result": "PASS", "recheck_of_id": failed["id"]}
    b = _client(app, t, t.founder)
    first, second = race(app, monkeypatch, t.token(t.quality), lambda c: c.post(f"{BASE}/{p['id']}/qc-checks", body),
                         lambda: b.post(f"{BASE}/{p['id']}/qc-checks", body))  # fmt: skip
    assert sorted((first.status, second.status)) == [201, 409]
    assert {r.code for r in (first, second) if r.status == 409} == {"RECHECK_NOT_LATEST"}
    assert _count(ProjectQcCheck, ProjectQcCheck.recheck_of_id == failed["id"]) == 1


def test_verifying_a_fix_while_another_verifier_fails_it_decides_once(team, app, monkeypatch):
    t = team
    _, p = _booked(t)
    p = advance_to(t, p, "SNAGGING")
    sn = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/snags", {"category": "FINISH", "customer_title": "Chip",
                                                          "owner_user_id": t.ops.id}), 201)["snags"][0]  # fmt: skip
    sn = t.snag_through(p, sn["id"], to="READY_FOR_RECHECK")
    url = f"{BASE}/{p['id']}/snags/{sn['id']}/status"
    b = _client(app, t, t.founder)
    first, second = race(app, monkeypatch, t.token(t.quality),
                         lambda c: c.post(url, {"status": "RESOLVED", "note": "Verified smooth"}, if_match=sn["version"]),
                         lambda: b.post(url, {"status": "IN_PROGRESS", "note": "Still rough"}, if_match=sn["version"]))  # fmt: skip
    assert sorted((first.status, second.status)) == [200, 409]
    loser = first if first.status == 409 else second
    assert loser.code == "VERSION_CONFLICT"  # never a lost update: the second decided on a state it had not seen
    final = next(x for x in t.get(p)["snags"] if x["id"] == sn["id"])
    assert final["status"] == ("RESOLVED" if first.status == 200 else "IN_PROGRESS")


def test_two_simultaneous_package_preparations_leave_one_package(team, app, monkeypatch):
    t = team
    _, p = _booked(t)
    p = advance_to(t, p, "READY_FOR_HANDOVER")
    t.checklist(p)
    cur = t.get(p)
    b = _client(app, t, t.founder)
    url = f"{BASE}/{p['id']}/handover-package"
    first, second = race(app, monkeypatch, t.token(t.ops), lambda c: c.post(url, {}, if_match=cur["version"]),
                         lambda: b.post(url, {}, if_match=cur["version"]))  # fmt: skip
    assert sorted((first.status, second.status)) == [201, 409]
    assert _count(ProjectHandoverPackage) == 1


def test_work_completed_while_a_gating_blocker_is_raised_on_it_is_decided_on_committed_state(team, app, monkeypatch):
    t = team
    _, p = _booked(t)
    wp = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/work-packages", {"stage_code": "BOOKED", "title": "Survey"}),
            201)["work_packages"][0]  # fmt: skip
    wp = next(w for w in ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/work-packages/{wp['id']}/start",
                                              {"actual_start": _today()}, if_match=wp["version"]))["work_packages"])  # fmt: skip
    b = _client(app, t, t.founder)
    blocker = {"category": "SITE", "impact": "GATING", "title": "Site closed", "responsible_party": "VEDA",
               "blocks_stage_code": "DESIGN_FINALISATION", "related_work_package_id": wp["id"]}  # fmt: skip
    first, second = race(app, monkeypatch, t.token(t.ops),
                         lambda c: c.post(f"{BASE}/{p['id']}/work-packages/{wp['id']}/complete",
                                          {"actual_finish": _today()}, if_match=wp["version"]),
                         lambda: b.post(f"{BASE}/{p['id']}/blockers", blocker))  # fmt: skip
    assert second.status == 201
    row = dbh.rows(sa.select(ProjectWorkPackage).where(ProjectWorkPackage.id == wp["id"]))[0]
    if first.status == 200:  # completed first: the blocker then concerns completed work
        assert row.status == "COMPLETED"
    else:
        assert first.status == 409 and first.code == "WORK_PACKAGE_BLOCKED" and row.status == "IN_PROGRESS"


def _customer_ready(t: Portal):
    delivery({"issue_reports": True, "handover_acknowledgement": True})
    prop, p = _booked(t)
    me = t.invite(prop["lead_id"], "race@example.test")
    return prop, p, me


def test_a_double_portal_acknowledgement_records_one(team, app, monkeypatch):
    t = team
    prop, p, me = _customer_ready(t)
    p = advance_to(t, p, "READY_FOR_HANDOVER")
    t.checklist(p)
    pkg = t.package(p)["handover_packages"][-1]
    url = f"{PUBLIC}/properties/{prop['id']}/projects/{p['id']}/handover/acknowledge"
    body = {"package_id": pkg["id"], "content_sha256": pkg["content_sha256"]}
    other = ApiClient(app.test_client())

    def ack(c):
        return c.call("POST", url, body, headers={"X-Veda-Portal": me.token}, anonymous=True)

    first, second = race(app, monkeypatch, "", ack, lambda: ack(other), name="lock")
    assert (first.status, second.status) == (200, 200)
    assert _count(ProjectEvent, ProjectEvent.event_code == "HANDOVER_ACKNOWLEDGED") == 1


def test_a_report_retried_while_the_first_is_in_flight_is_one_report(team, app, monkeypatch):
    t = team
    prop, p, me = _customer_ready(t)
    url = f"{PUBLIC}/properties/{prop['id']}/projects/{p['id']}/reports"
    other = ApiClient(app.test_client())

    def send(c):
        return c.call("POST", url, {"description": "Bathroom vanity door hits the wall"},
                      headers={"X-Veda-Portal": me.token, "Idempotency-Key": "race-key-0001"}, anonymous=True)  # fmt: skip

    first, second = race(app, monkeypatch, "", send, lambda: send(other), name="lock")
    assert sorted((first.status, second.status)) == [200, 201]
    assert _count(ProjectCustomerReport) == 1


# --- erasure -------------------------------------------------------------------------------------------------------------
def test_erasure_redacts_execution_text_and_the_package_but_keeps_its_original_digest(team):
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead

    t = team
    prop, p, me = _customer_ready(t)
    api = t.as_(t.ops)
    ok(api.post(f"{BASE}/{p['id']}/work-packages", {"stage_code": "BOOKED", "title": "Rao kitchen survey",
                                                   "customer_label": "Mrs Rao's kitchen", "customer_visible": True}), 201)  # fmt: skip
    ok(api.post(f"{BASE}/{p['id']}/customer-reports", {"description": "Mrs Rao says the drawer sticks"}), 201)
    p = t.get(p)
    wp = p["work_packages"][0]
    for cmd, body in (("start", {"actual_start": _today()}), ("complete", {"actual_finish": _today()})):
        cur = next(w for w in t.get(p)["work_packages"] if w["id"] == wp["id"])
        ok(api.post(f"{BASE}/{p['id']}/work-packages/{wp['id']}/{cmd}", body, if_match=cur["version"]))
    rep = t.get(p)["customer_reports"][0]
    ok(api.post(f"{BASE}/{p['id']}/customer-reports/{rep['id']}/triage",
                {"outcome": "DECLINED", "decline_code": "DUPLICATE", "response": "Already being fixed with snag 1"},
                if_match=rep["version"]))  # fmt: skip
    p = advance_to(t, p, "READY_FOR_HANDOVER")
    t.checklist(p)
    pkg = t.package(p)["handover_packages"][-1]
    assert "Mrs Rao's kitchen" in str(pkg["content"])
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, prop["lead_id"]), legal_basis="SYNTHETIC erasure test", request_ref=None)
    w = dbh.rows(sa.select(ProjectWorkPackage))[0]
    assert (w.title, w.customer_label) == ("[erased]", "[erased]") and w.status == "COMPLETED"
    r = dbh.rows(sa.select(ProjectCustomerReport))[0]
    assert (r.description, r.response) == ("[erased]", "[erased]") and r.decline_code == "DUPLICATE"
    row = dbh.rows(sa.select(ProjectHandoverPackage))[0]
    assert row.redacted and row.content_sha256 == pkg["content_sha256"] and row.redacted_sha256 != row.content_sha256
    assert "Rao" not in str(row.content)
    redacted = dbh.rows(sa.select(ProjectEvent).where(ProjectEvent.event_code == "HANDOVER_PACKAGE_REDACTED"))
    assert len(redacted) == 1 and redacted[0].detail["content_sha256"] == pkg["content_sha256"]


# --- notifications -------------------------------------------------------------------------------------------------------
def test_a_customer_report_notifies_the_project_team_in_app_once(team):
    from veda.platform.notifications import worker

    t = team
    prop, p, me = _customer_ready(t)
    r = me.api.call("POST", f"{PUBLIC}/properties/{prop['id']}/projects/{p['id']}/reports",
                    {"description": "The study table wobbles a little"},
                    headers={"X-Veda-Portal": me.token, "Idempotency-Key": "notify-key-01"}, anonymous=True)  # fmt: skip
    assert r.status == 201
    worker.drain_all()
    worker.drain_all()
    notes = [n for n in dbh.rows(sa.select(Notification)) if n.notification_type == "PROJECT_CUSTOMER_REPORT"]
    assert {n.recipient_user_id for n in notes} == {t.ops.id} and len(notes) == 1
    assert "wobbles" not in notes[0].title
