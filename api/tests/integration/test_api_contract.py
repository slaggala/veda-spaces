"""API contract (12 §4.6), TD-F optimistic-concurrency conflict, notifications and the outbox (12 §4.10)."""

import threading
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support.dbh import audits, rows
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.modules.crm.leads.models import Lead
from veda.platform.notifications import worker
from veda.platform.notifications.email import CaptureEmailProvider, FailingEmailProvider, use_provider
from veda.platform.notifications.models import Notification, OutboxEvent


@pytest.fixture
def founder(api, factory):
    user = factory.user(founder=True)
    factory.login(api, user)
    return user


# --- envelopes and errors (API-002, API-003) ---------------------------------------------------------


def test_API_002_envelopes_and_headers(api, founder, factory):
    lead = factory.lead(api, founder.token)
    r = api.get(f"/api/v1/leads/{lead['id']}")
    assert set(r.json) == {"data"} and r.headers["ETag"] == f'"{r.data["version"]}"'
    assert r.headers["X-Request-ID"] and r.headers["X-Authz-Version"]
    assert r.headers["Cache-Control"] == "no-store" and r.headers["X-Content-Type-Options"] == "nosniff"
    assert "max-age" in r.headers["Strict-Transport-Security"]
    lst = api.get("/api/v1/leads?page=1&page_size=10")
    assert set(lst.json) == {"data", "meta", "links"} and set(lst.json["meta"]) >= {
        "page",
        "page_size",
        "total",
        "total_pages",
    }
    echo = api.get("/api/v1/leads", headers={"X-Request-ID": "trace-abc-123"})
    assert echo.headers["X-Request-ID"] == "trace-abc-123"


def test_API_003_problem_details(api, founder):
    r = api.get("/api/v1/leads/0192a4f1c3b27e8d9f10a2b3c4d5e6f7")
    assert r.status == 404 and r.raw.content_type == "application/problem+json"
    assert set(r.json) >= {"type", "title", "status", "code", "request_id"} and r.json["type"].endswith("/not-found")
    assert api.call("POST", "/api/v1/leads", raw_body=b"{not json").code == "MALFORMED_JSON"
    assert (
        api.call("POST", "/api/v1/leads", raw_body=b"name=x", content_type="application/x-www-form-urlencoded").status
        == 415
    )
    assert api.call("DELETE", "/api/v1/lookups").status == 405


@pytest.mark.parametrize(
    "bad",
    [
        "0192A4F1C3B27E8D9F10A2B3C4D5E6F7",
        "0192a4f1-c3b2-7e8d-9f10-a2b3c4d5e6f7",
        "0192a4f1c3b24e8d9f10a2b3c4d5e6f7",
        "123",
        "1",
    ],
)
def test_DATA_013_invalid_ids_rejected_before_lookup(api, founder, bad):
    r = api.get(f"/api/v1/leads/{bad}")
    assert r.status == 422 and r.code == "INVALID_ID"
    r = api.post("/api/v1/leads", {"name": "x y", "phone": "9876543210", "source_code": "PHONE", "assigned_to": bad})
    assert r.status == 422 and r.code == "INVALID_ID"


def test_API_006_if_match_required_and_checked(api, founder, factory):
    lead = factory.lead(api, founder.token)
    assert api.patch(f"/api/v1/leads/{lead['id']}", {"city": "Pune"}).code == "PRECONDITION_REQUIRED"
    assert (
        api.patch(f"/api/v1/leads/{lead['id']}", {"city": "Pune"}, if_match=lead["version"] + 5).code
        == "VERSION_CONFLICT"
    )
    assert (
        api.patch(
            f"/api/v1/leads/{lead['id']}", {"city": "Pune"}, headers={"If-Match": f'W/"{lead["version"]}"'}
        ).status
        == 200
    )


def test_SEC_004_closed_schemas_and_body_limits(api, founder):
    r = api.post("/api/v1/leads", {"name": "x y", "phone": "9876543210", "source_code": "PHONE", "is_admin": True})
    assert r.code == "VALIDATION_FAILED" and r.json["errors"][0]["code"] == "UNKNOWN_FIELD"
    big = b'{"name":"' + b"x" * (17 * 1024) + b'"}'
    assert (
        api.call(
            "POST", "/api/v1/public/leads", raw_body=big, anonymous=True, headers={"Idempotency-Key": "k" * 20}
        ).code
        == "PAYLOAD_TOO_LARGE"
    )


def test_API_007_authenticated_idempotency(api, founder):
    body = {"name": "Idem Lead", "phone": "9876500000", "source_code": "PHONE"}
    r1 = api.post("/api/v1/leads", body, headers={"Idempotency-Key": "create-lead-000001"})
    r2 = api.post("/api/v1/leads", body, headers={"Idempotency-Key": "create-lead-000001"})
    assert r1.status == r2.status == 201 and r1.data["id"] == r2.data["id"]
    assert len(rows(sa.select(Lead).where(Lead.name == "Idem Lead"))) == 1
    r3 = api.post("/api/v1/leads", {**body, "name": "Other"}, headers={"Idempotency-Key": "create-lead-000001"})
    assert r3.code == "IDEMPOTENCY_KEY_REUSED"


def test_SEC_002_cors_allowlist(client):
    r = client.options(
        "/api/v1/auth/login", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}
    )
    assert r.status_code == 204 and r.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert (
        r.headers["Access-Control-Allow-Credentials"] == "true"
        if "Access-Control-Allow-Credentials" in r.headers
        else True
    )
    r = client.options(
        "/api/v1/leads", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"}
    )
    assert "Access-Control-Allow-Origin" not in r.headers
    r = client.options(
        "/api/v1/public/leads", headers={"Origin": "http://localhost:8000", "Access-Control-Request-Method": "POST"}
    )
    assert r.headers["Access-Control-Allow-Origin"] == "http://localhost:8000"
    r = client.options(
        "/api/v1/leads", headers={"Origin": "http://localhost:8000", "Access-Control-Request-Method": "GET"}
    )
    assert "Access-Control-Allow-Origin" not in r.headers, "the public site origin reaches public endpoints only"


def _cors_headers(client, method, path, origin, **kw):
    if method == "OPTIONS":
        r = client.options(path, headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    else:
        r = client.post(path, json={}, headers={"Origin": origin}, **kw)
    return r.headers.get("Access-Control-Allow-Origin"), r.headers.get("Access-Control-Allow-Credentials")


@pytest.mark.parametrize("method", ["OPTIONS", "POST"])
def test_public_site_without_credentials_by_default(client, method):
    """Production behaviour: the public site reaches public routes without credentials."""
    assert _cors_headers(client, method, "/api/v1/public/leads", "http://localhost:8000") == (
        "http://localhost:8000",
        None,
    )


@pytest.mark.settings(public_site_credentials=True)
@pytest.mark.parametrize("method", ["OPTIONS", "POST"])
def test_staging_public_site_credentials(client, method):
    """Staging (behind Cloudflare Access): the approved site origin gets credentials on public routes only."""
    assert _cors_headers(client, method, "/api/v1/public/leads", "http://localhost:8000") == (
        "http://localhost:8000",
        "true",
    )
    # Non-approved origins get no CORS headers at all.
    for origin in ("https://evil.example", "http://localhost:8001", "https://staging.vedaspaces.com.evil.example"):
        assert _cors_headers(client, method, "/api/v1/public/leads", origin) == (None, None), origin
    # The public site still never reaches the workspace API.
    assert _cors_headers(client, method, "/api/v1/leads", "http://localhost:8000") == (None, None)


@pytest.mark.parametrize("app", [{}, {"public_site_credentials": True}], indirect=True)
def test_staff_app_cors_unchanged(client):
    """The staff application keeps credentialed CORS on every route, whatever the public-site setting."""
    for path in ("/api/v1/auth/login", "/api/v1/leads", "/api/v1/public/leads"):
        for method in ("OPTIONS", "POST"):
            assert _cors_headers(client, method, path, "http://localhost:5173") == ("http://localhost:5173", "true")


def test_LOG_005_health(client):
    assert client.get("/health/live").get_json() == {"status": "ok"}
    body = client.get("/health/ready").get_json()
    assert body["status"] == "ok" and body["checks"]["migrations"] == "head"


def test_API_008_openapi_generated(client):
    doc = client.get("/api/v1/openapi.json").get_json()
    assert doc["openapi"] == "3.1.0" and "/api/v1/leads/{lead_id}/status" in doc["paths"]
    op = doc["paths"]["/api/v1/leads/{lead_id}/status"]["post"]
    assert op["x-permission-any-of"] == ["lead.status.change", "lead.reopen"] and op["requestBody"]


@pytest.mark.settings(rate_limits_enabled=True)
def test_rate_limits_public_intake(api, factory):
    codes = [factory.public_lead(api).status for _ in range(22)]
    assert 429 in codes
    from tests.support.dbh import events

    assert events("PUBLIC_INTAKE_BLOCKED")


# --- TD-F: optimistic concurrency (API-006, DATA-006) -----------------------------------------------


def test_TD_F_two_writer_conflict(app, api, factory, founder):
    x, y = factory.user("ADMIN"), factory.user("ADMIN")
    lead = factory.lead(api, founder.token)
    tx, ty = factory.login(api, x, set_default=False), factory.login(api, y, set_default=False)
    version = lead["version"]
    barrier = threading.Barrier(2)
    results = {}

    def writer(name, token, body):
        client = app.test_client()
        from tests.support.api import ApiClient

        c = ApiClient(client)
        barrier.wait()
        results[name] = c.patch(f"/api/v1/leads/{lead['id']}", body, token=token, if_match=version)

    threads = [
        threading.Thread(target=writer, args=("x", tx, {"priority": "HIGH"})),
        threading.Thread(target=writer, args=("y", ty, {"city": "Pune"})),
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    statuses = sorted(r.status for r in results.values())
    assert statuses == [200, 409], {k: v.json for k, v in results.items()}
    winner = next(r for r in results.values() if r.status == 200)
    loser_name, loser = next((k, r) for k, r in results.items() if r.status == 409)
    assert loser.code == "VERSION_CONFLICT" and loser.json["current_version"] == winner.data["version"]
    retry_body = {"city": "Pune"} if loser_name == "y" else {"priority": "HIGH"}
    retry = api.patch(
        f"/api/v1/leads/{lead['id']}",
        retry_body,
        token=ty if loser_name == "y" else tx,
        if_match=winner.data["version"],
    )
    assert retry.status == 200 and retry.data["priority"] == "HIGH" and retry.data["city"] == "Pune"
    updates = audits(lead["id"], action="UPDATE")
    assert len(updates) == 2, "no audit row for the rejected write"


def test_R8_a_writer_that_loses_the_race_always_learns_the_current_version(app, api, factory, founder, monkeypatch):
    """Deterministic interleaving of the TD-F race: A passes its version check and pauses; B sends the same edit
    meanwhile. B must wait for A (the row is locked by the check) and get 409 with current_version. Without the lock,
    B commits first and A's flush fails as StaleDataError, a 409 without current_version (R8)."""
    import time

    from veda.modules.crm.leads import service

    x, y = factory.user("ADMIN"), factory.user("ADMIN")
    lead = factory.lead(api, founder.token)
    tx, ty = factory.login(api, x, set_default=False), factory.login(api, y, set_default=False)
    version = lead["version"]
    a_checked = threading.Event()
    real_update = service.update

    def update(s, ctx, row, body):
        if getattr(body, "priority", None) == "HIGH":  # writer A only
            a_checked.set()
            time.sleep(1.0)
        return real_update(s, ctx, row, body)

    monkeypatch.setattr(service, "update", update)
    results = {}

    def writer(name, token, body, wait=None):
        from tests.support.api import ApiClient

        if wait is not None:
            assert wait.wait(10)
        results[name] = ApiClient(app.test_client()).patch(
            f"/api/v1/leads/{lead['id']}", body, token=token, if_match=version
        )

    threads = [
        threading.Thread(target=writer, args=("a", tx, {"priority": "HIGH"})),
        threading.Thread(target=writer, args=("b", ty, {"city": "Pune"}, a_checked)),
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    a, b = results["a"], results["b"]
    assert a.status == 200, a.json
    assert b.status == 409 and b.code == "VERSION_CONFLICT", b.json
    assert b.json["current_version"] == a.data["version"]


def test_PLAT_010_sequence_allocation_under_concurrency(app, api, factory, founder):
    from tests.support.api import ApiClient

    barrier = threading.Barrier(4)
    numbers = []

    def create(i):
        c = ApiClient(app.test_client())
        barrier.wait()
        r = c.post(
            "/api/v1/leads",
            {"name": f"Parallel {i}", "phone": f"98765{i:05d}", "source_code": "PHONE"},
            token=founder.token,
        )
        numbers.append(r.data["lead_number"] if r.status == 201 else r.json)

    threads = [threading.Thread(target=create, args=(i,)) for i in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(set(numbers)) == 4 and all(str(n).startswith("VS-L-") for n in numbers), numbers


# --- notifications and outbox (NOTIF-*) -------------------------------------------------------------


def test_NOTIF_003_outbox_retry_backoff_dead_and_idempotency(api, factory, founder):
    factory.public_lead(api)
    use_provider(FailingEmailProvider())
    for attempt in range(1, 9):
        worker.drain_all()
        ev = rows(sa.select(OutboxEvent).where(OutboxEvent.event_type == "lead.created"))[0]
        assert ev.attempts == attempt
        if attempt < 8:
            assert ev.status == "FAILED" and "RuntimeError" in ev.last_error
            clock.advance(timedelta(seconds=2**attempt + 1))
    assert ev.status == "DEAD"
    notes = rows(sa.select(Notification).where(Notification.source_event_id == ev.id))
    assert len(notes) == 1, "in-app handler is idempotent across retries"


def test_NOTIF_003_stale_processing_rows_reclaimed(api, factory, founder):
    factory.public_lead(api)
    ids = worker.claim()
    assert ids and worker.claim() == []
    clock.advance(timedelta(minutes=6))
    assert worker.claim() == ids
    for i in ids:
        worker.process(i)
    assert rows(sa.select(OutboxEvent).where(OutboxEvent.id.in_(ids)))[0].status == "DONE"


def test_NOTIF_009_capture_adapter_and_templates(api, factory, founder):
    factory.public_lead(api, name="Kiran <script>")
    worker.drain_all()
    msg = next(m for m in CaptureEmailProvider.sent if founder.email in m.to)
    assert msg.subject.startswith("New enquiry: VS-L-") and msg.text and "<!doctype html>" in msg.html
    assert "&lt;script&gt;" in msg.html and "<script>" not in msg.html, "HTML is escaped"
    assert msg.headers["X-Veda-Event"] == "lead.created" and "X-Request-ID" in msg.headers


def test_security_notifications_only_to_verified_email(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)
    api.post("/api/v1/auth/reauth", {"password": sales.password})
    api.put("/api/v1/auth/me/email", {"new_email": "proposed@vedaspaces.test"})
    api.post("/api/v1/auth/password/forgot", {"email": sales.email}, anonymous=True)
    worker.drain_all()
    to_proposed = [m for m in CaptureEmailProvider.sent if "proposed@vedaspaces.test" in m.to]
    assert len(to_proposed) == 1 and "Confirm" in to_proposed[0].subject, "the proposed address gets only its link"
    assert any(sales.email in m.to and "Reset" in m.subject for m in CaptureEmailProvider.sent)


def test_scheduler_jobs_follow_up_and_spam_digest(api, factory, founder):
    from veda.platform import maintenance

    lead = factory.lead(api, founder.token)
    api.post(
        f"/api/v1/leads/{lead['id']}/activities",
        {
            "activity_type": "CALL",
            "activity_status": "PLANNED",
            "subject": "Call back",
            "scheduled_on": clock.to_rfc3339(clock.now() + timedelta(minutes=10)),
        },
    )
    assert maintenance.follow_up_reminders() == 1 and maintenance.follow_up_reminders() == 0
    factory.public_lead(api, company_website_url="bot")
    assert maintenance.spam_review()["suspected"] == 1
    worker.drain_all()
    types = {
        n.notification_type for n in rows(sa.select(Notification).where(Notification.recipient_user_id == founder.id))
    }
    assert {"FOLLOW_UP_DUE", "SPAM_REVIEW"} <= types
    with actor(system_context()), db.unit_of_work(write=True) as s:
        assert s.execute(sa.select(sa.func.count()).select_from(OutboxEvent)).scalar() >= 2
