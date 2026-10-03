"""RR-13: no personal data from URLs, query strings or provider errors reaches error tracking, performance tracing
or stored diagnostics (LOG-003, SEC-009).

The Sentry probe uses the real SDK with an in-memory transport and the production options (``sentry_options``), so
it checks the exact payloads that would leave the process."""

from __future__ import annotations

import json
import logging
import re
from datetime import timedelta
from urllib.parse import urlencode

import botocore.exceptions
import pytest
import sentry_sdk
import sqlalchemy as sa
from sentry_sdk.transport import Transport

from tests.integration.test_api_contract import founder  # noqa: F401  (fixture: staff to notify)
from tests.support.dbh import rows
from veda.kernel import clock
from veda.kernel.logging import _scrub_span, error_summary, sentry_options
from veda.platform.notifications import worker
from veda.platform.notifications.email import EmailProvider, use_provider
from veda.platform.notifications.models import OutboxEvent

EMAIL, PHONE, NAME = "priya.sharma@example.com", "+919876543210", "Priya Sharma"
# What a leak would look like in a payload: the value raw, URL-encoded or partly encoded.
LEAKS = re.compile(r"priya|sharma|9876543210|example\.com|%40", re.IGNORECASE)


class _Capture(Transport):
    sent: list[dict] = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            _Capture.sent.append(item.payload.json or {})


@pytest.fixture
def sentry(app):
    _Capture.sent = []
    options = {
        **sentry_options(type("S", (), {"sentry_dsn": "https://public@example.invalid/1", "env": "test"})()),
        "traces_sample_rate": 1.0,  # sample every request so the probe sees every transaction
        "transport": _Capture,
    }
    sentry_sdk.init(**options)
    yield _Capture.sent
    sentry_sdk.flush()
    sentry_sdk.init(dsn=None)


def test_RR13_lead_search_never_reaches_sentry_transactions(api, factory, sentry):
    token = factory.login(api, factory.user("SALES"))
    for term in (EMAIL, PHONE, NAME):
        assert api.get(f"/api/v1/leads?{urlencode({'q': term})}", token=token).status == 200
    sentry_sdk.flush()
    transactions = [e for e in sentry if e.get("type") == "transaction"]
    searches = [t for t in transactions if (t.get("request") or {}).get("url", "").endswith("/api/v1/leads")]
    assert len(searches) == 3, "the probe saw the search transactions"
    payload = json.dumps(sentry)
    assert not LEAKS.search(payload), LEAKS.search(payload)
    for t in transactions:
        request = t["request"]
        assert "query_string" not in request and "?" not in request["url"] and "env" not in request
        assert set(request.get("headers", {})) <= {"User-Agent", "X-Request-Id", "Content-Type"}
        for span in t.get("spans") or []:
            assert set(span.get("data") or {}) <= {
                "db.system", "db.operation", "http.method", "http.request.method", "http.response.status_code",
                "thread.id", "thread.name", "server.address",
            }  # fmt: skip


def test_RR13_error_events_drop_the_query_string_and_message(app, sentry):
    with app.test_request_context(f"/api/v1/leads?q={EMAIL}&phone={PHONE}", headers={"Referer": f"/x?q={EMAIL}"}):
        try:
            raise ValueError(f"lookup failed for {EMAIL}")
        except ValueError as exc:
            sentry_sdk.capture_exception(exc)
    sentry_sdk.flush()
    errors = [e for e in sentry if e.get("exception")]
    assert errors, "the probe saw the error event"
    assert not LEAKS.search(json.dumps(errors))
    assert errors[0]["exception"]["values"][0]["value"] == "[omitted]"


def test_RR13_create_app_installs_every_sentry_hook(database_url, monkeypatch):
    from tests.conftest import make_settings, reset_process_state
    from veda.app import create_app
    from veda.kernel import db

    seen = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: seen.update(kw))
    reset_process_state()
    try:
        create_app(make_settings(database_url, sentry_dsn="https://public@example.invalid/1"))
    finally:
        reset_process_state()
        db.dispose()
    assert seen["send_default_pii"] is False and seen["max_request_body_size"] == "never"
    assert seen["include_local_variables"] is False
    for hook in ("before_send", "before_send_transaction", "before_send_span"):
        assert callable(seen[hook]), hook


def test_RR13_spans_keep_timing_not_parameters():
    span = {
        "op": "http.client",
        "description": f"GET https://api.example.invalid/v1/contacts?email={EMAIL}&page=2",
        "data": {"url": f"https://api.example.invalid/v1/contacts?email={EMAIL}", "http.query": f"email={EMAIL}",
                 "http.method": "GET", "http.response.status_code": 200},
    }  # fmt: skip
    _scrub_span(span)
    assert span["description"] == "GET https://api.example.invalid/v1/contacts"
    assert span["data"] == {"http.method": "GET", "http.response.status_code": 200}
    sql = {"op": "db", "description": f"SELECT * FROM lead WHERE email = '{EMAIL}'", "data": {"db.params": [EMAIL]}}
    _scrub_span(sql)
    assert EMAIL not in json.dumps(sql)


# --- outbox_event.last_error ---------------------------------------------------------------------------------


class _RejectingProvider(EmailProvider):
    """An SES-style rejection whose message names the recipient, as real providers do."""

    name = "rejecting"

    def send(self, message):
        raise botocore.exceptions.ClientError(
            {"Error": {"Code": "MessageRejected", "Message": f"Email address is not verified: {EMAIL}"}}, "SendEmail"
        )


def test_RR13_outbox_last_error_has_no_recipient_but_stays_traceable(api, factory, founder, caplog):  # noqa: F811
    factory.public_lead(api)
    use_provider(_RejectingProvider())
    with caplog.at_level(logging.WARNING):
        worker.drain_all()
    ev = rows(sa.select(OutboxEvent).where(OutboxEvent.event_type == "lead.created"))[0]
    assert ev.status == "FAILED"
    assert not LEAKS.search(ev.last_error), ev.last_error
    assert re.fullmatch(r"ClientError\[MessageRejected\] #[0-9a-f]{16}", ev.last_error)
    # The same fingerprint is on the log line, which carries the stack (and never the message).
    fingerprint = ev.last_error.rsplit("#", 1)[1]
    assert any(getattr(r, "exc_info", None) for r in caplog.records if "outbox_handler_failed" in r.getMessage())
    record = next(r for r in caplog.records if "outbox_handler_failed" in r.getMessage())
    assert error_summary(record.exc_info[1]).endswith(fingerprint)
    clock.advance(timedelta(seconds=3))


def test_RR13_error_summary_never_contains_the_message():
    try:
        raise RuntimeError(f"insert failed: ('{NAME}', '{PHONE}', '{EMAIL}')")
    except RuntimeError as exc:
        summary = error_summary(exc)
    assert re.fullmatch(r"RuntimeError #[0-9a-f]{16}", summary) and not LEAKS.search(summary)
