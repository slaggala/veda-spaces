"""IR-27: no raw PII in logs (LOG-001, LOG-003, SEC-009)."""

import io
import json
import logging

import structlog

from veda.kernel import logging as vlog

PII = ("Kiran Rao", "kiran.rao@example.com", "+919812345678", "Flat 4B near the temple")


def _capture(fn) -> list[dict]:
    vlog.configure_logging("INFO")
    stream = io.StringIO()
    next(h for h in logging.getLogger().handlers if getattr(h, "_veda", False)).stream = stream
    try:
        fn()
    finally:
        structlog.reset_defaults()
        vlog.configure_logging("INFO")
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def _boom():
    raise ValueError(
        f'null value in column "phone" violates not-null constraint DETAIL: Failing row contains '
        f"({PII[0]}, {PII[1]}, {PII[2]}, {PII[3]})."
    )


def test_IR27_Q6_stdlib_exception_logs_carry_no_pii():
    def run():
        try:
            _boom()
        except ValueError:
            logging.getLogger("veda.app").exception("unhandled_error")

    lines = _capture(run)
    text = json.dumps(lines)
    for value in PII:
        assert value not in text, value
    assert lines[0]["error_type"] == "ValueError" and lines[0]["error_fingerprint"] and lines[0]["stack"]


def test_IR27_stdlib_messages_and_arguments_are_masked():
    lines = _capture(lambda: logging.getLogger("veda.worker").warning("sent to %s at %s", PII[1], PII[2]))
    assert PII[1] not in lines[0]["event"] and PII[2] not in lines[0]["event"]
    assert lines[0]["logger"] == "veda.worker" and lines[0]["level"] == "warning"


def test_IR27_structlog_exception_carries_no_message():
    def run():
        try:
            _boom()
        except ValueError:
            structlog.get_logger("veda.http").exception("request_failed")

    text = json.dumps(_capture(run))
    for value in PII:
        assert value not in text


def test_IR27_sentry_events_are_scrubbed():
    event = {
        "exception": {
            "values": [
                {
                    "type": "IntegrityError",
                    "value": f"Failing row contains ({PII[0]})",
                    "stacktrace": {"frames": [{"function": "create_public", "vars": {"name": PII[0]}}]},
                }
            ]
        },
        "request": {
            "data": {"name": PII[0]},
            "cookies": {"vs_rt": "secret"},
            "query_string": "email=" + PII[1],
            "headers": {"Authorization": "Bearer x", "User-Agent": "UA"},
        },
        "user": {"email": PII[1]},
        "breadcrumbs": {"values": [{"message": f"lead from {PII[1]}", "data": {"phone": PII[2]}}]},
    }
    text = json.dumps(vlog.sentry_before_send(event, {}))
    for value in (*PII[:3], "Bearer x", "secret"):
        assert value not in text


def test_IR27_engine_hides_bound_parameters():
    from veda.kernel import db

    engine = db.create_engine("sqlite://")
    assert engine.hide_parameters is True
