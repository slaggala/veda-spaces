"""Structured JSON logging (02 §9, LOG-001, LOG-003).

Log line: ts, level, logger, event, request_id, session_id, user_id, method,
route (templated), status, duration_ms, ip (/24). Bodies, tokens, cookies and
Authorization headers are never logged; emails and phones are masked.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
import time
import traceback
from typing import Any

import structlog

_EMAIL = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+)")
_PHONE = re.compile(r"(?<![\w:.-])\+?\d(?:\s?\d){9,14}(?![\w:.-])")
DENYLIST = ("password", "token", "authorization", "cookie", "secret", "code", "recovery")


def _mask(value: str) -> str:
    value = _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", value)
    return _PHONE.sub(lambda m: m.group(0)[:3] + "******" + m.group(0)[-4:], value)


_SAFE_KEYS = frozenset({"ts", "request_id", "session_id", "user_id", "route", "method", "level", "logger"})


def _scrub(_, __, event_dict):
    from veda.kernel.metrics import exempt_metric_keys

    metric_keys = exempt_metric_keys(event_dict)  # approved numeric metric values only (FC-02)
    for key in list(event_dict):
        if key in _SAFE_KEYS or key in metric_keys:
            continue
        if any(d in key.lower() for d in DENYLIST):
            event_dict[key] = "[REDACTED]"
        elif isinstance(event_dict[key], str):
            event_dict[key] = _mask(event_dict[key])
    return event_dict


def error_fingerprint(exc_type: type, tb) -> tuple[str, list[str]]:
    """Stable id of an error (type + code path) and its stack frames; never the message (IR-27)."""
    frames = traceback.extract_tb(tb)
    stack = [f"{f.filename.rsplit('/veda/', 1)[-1]}:{f.lineno} {f.name}" for f in frames]
    return hashlib.sha256((exc_type.__name__ + "|" + "|".join(stack)).encode()).hexdigest()[:16], stack


def error_summary(exc: BaseException) -> str:
    """A PII-free description of an error for storage (RR-13): type, the provider's error code when it has one,
    and the fingerprint that the matching log line carries, so the full stack can be found in the logs."""
    code = None
    response = getattr(exc, "response", None)
    if isinstance(response, dict):  # botocore ClientError (SES, S3): a machine code, never the message
        code = (response.get("Error") or {}).get("Code")
    fingerprint, _ = error_fingerprint(type(exc), exc.__traceback__)
    label = type(exc).__name__ + (f"[{code}]" if isinstance(code, str) and code.isidentifier() else "")
    return f"{label} #{fingerprint}"


def _safe_exception(_, __, event_dict):
    """Exceptions are logged as type, fingerprint and stack frames only. The message is dropped: database errors
    carry bound values and failing rows (names, phones, messages) that masking cannot recognise (IR-27, LOG-003)."""
    exc_info = event_dict.pop("exc_info", None)
    if exc_info is True:
        exc_info = sys.exc_info()
    if isinstance(exc_info, BaseException):
        exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
    if exc_info and exc_info[0] is not None:
        fingerprint, stack = error_fingerprint(exc_info[0], exc_info[2])
        event_dict["error_type"] = exc_info[0].__name__
        event_dict["error_fingerprint"] = fingerprint
        event_dict["stack"] = stack[-15:]
    event_dict.pop("exception", None)
    return event_dict


def _emf(_, __, event_dict):
    """Metric lines (veda.kernel.metrics) carry an EMF document that must sit at the JSON root (IR-12)."""
    record = event_dict.get("_record")
    payload = getattr(record, "emf", None) if record is not None else event_dict.pop("emf", None)
    if payload:
        event_dict.update(payload)
    return event_dict


SHARED: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
]


class _StdoutHandler(logging.StreamHandler):
    """Writes to whatever sys.stdout is when the record is emitted, never to a stream captured at start-up that
    may since have been replaced or closed (test runners, reloaders)."""

    def __init__(self) -> None:
        self._override = None
        super().__init__(sys.stdout)

    @property
    def stream(self):
        return self._override or sys.stdout

    @stream.setter
    def stream(self, value) -> None:
        self._override = None if value is sys.stdout else value


def configure_logging(level: str = "INFO") -> None:
    """Every record, structlog or stdlib (Flask, gunicorn, SQLAlchemy, the worker), leaves as one masked JSON line."""
    handler = _StdoutHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[*SHARED, _emf, _safe_exception],
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                _scrub,
                structlog.processors.JSONRenderer(),
            ],
        )
    )
    handler._veda = True  # type: ignore[attr-defined]  # marker attribute on a stdlib handler
    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, "_veda", False):  # replace our own handler only (re-configuration, tests)
            root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger("alembic").setLevel(logging.WARNING)
    structlog.configure(
        processors=[*SHARED, _safe_exception, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


_URL_QUERY = re.compile(r"(https?://[^\s?#]+)[?#]\S*")
# Span attributes worth keeping: what ran and how long, never what it was asked for (RR-13).
_SPAN_DATA_KEEP = frozenset(
    {"db.system", "db.operation", "http.method", "http.request.method", "http.response.status_code", "thread.id",
     "thread.name", "server.address"}
)  # fmt: skip


def _strip_query(url):
    return url.split("?", 1)[0].split("#", 1)[0] if isinstance(url, str) else url


def _scrub_request(request) -> None:
    """Request context: method and path only. The query string is dropped, not masked: it is URL-encoded
    (``q=priya%40example.com``), so pattern masking cannot recognise what it carries (RR-13)."""
    if not isinstance(request, dict):
        return
    for key in ("data", "cookies", "query_string", "env"):
        request.pop(key, None)
    request["url"] = _strip_query(request.get("url"))
    request["headers"] = {
        k: v
        for k, v in (request.get("headers") or {}).items()
        if k.lower() in ("user-agent", "x-request-id", "content-type")
    }


def _scrub_breadcrumbs(event) -> None:
    for crumb in (event.get("breadcrumbs") or {}).get("values", []) or []:
        if isinstance(crumb.get("message"), str):
            crumb["message"] = _mask(_URL_QUERY.sub(r"\1", crumb["message"]))
        crumb.pop("data", None)


def _scrub_span(span) -> None:
    if not isinstance(span, dict):
        return
    if isinstance(span.get("description"), str):
        span["description"] = _mask(_URL_QUERY.sub(r"\1", span["description"]))
    data = span.get("data")
    if isinstance(data, dict):
        span["data"] = {k: v for k, v in data.items() if k in _SPAN_DATA_KEEP}


def sentry_before_send(event, _hint):
    """Sentry receives exception types and frames only: values, request bodies, query strings, cookies, headers
    and local variables are removed (IR-27, LOG-004, RR-13)."""
    for exc in (event.get("exception") or {}).get("values", []) or []:
        exc["value"] = "[omitted]"
        for frame in (exc.get("stacktrace") or {}).get("frames", []) or []:
            frame.pop("vars", None)
    _scrub_request(event.get("request"))
    event.pop("user", None)
    if isinstance(event.get("logentry"), dict):
        event["logentry"]["message"] = _mask(str(event["logentry"].get("message", "")))
        event["logentry"].pop("params", None)
    _scrub_breadcrumbs(event)
    return event


def sentry_before_send_transaction(event, _hint):
    """Performance transactions get the same treatment as errors (RR-13): they carry the request context too, and
    before_send never sees them. Spans keep their operation and timing, not their parameters."""
    _scrub_request(event.get("request"))
    event.pop("user", None)
    _scrub_breadcrumbs(event)
    trace = (event.get("contexts") or {}).get("trace")
    if isinstance(trace, dict):
        _scrub_span(trace)
    for span in event.get("spans") or []:
        _scrub_span(span)
    return event


def sentry_before_send_span(span, _hint=None):
    """Streamed spans (span-first mode) are scrubbed like the spans inside a transaction."""
    _scrub_span(span)
    return span


def sentry_options(settings) -> dict[str, Any]:
    """The one Sentry configuration (create_app); the PII probe in the tests uses it as is."""
    return {
        "dsn": settings.sentry_dsn,
        "send_default_pii": False,
        "traces_sample_rate": 0.1,
        "environment": settings.env,
        "include_local_variables": False,
        "max_request_body_size": "never",
        "before_send": sentry_before_send,
        "before_send_transaction": sentry_before_send_transaction,
        "before_send_span": sentry_before_send_span,
    }


def _truncate_ip(ip: str | None) -> str | None:
    from veda.kernel import net

    return net.network_of(ip) if ip else None


def log_request(resp, started: float | None) -> None:
    from flask import g, request

    from veda.kernel import metrics, net
    from veda.kernel.context import current_actor

    ctx = current_actor()
    rule = request.url_rule.rule if request.url_rule else "unmatched"
    duration_ms = round((time.perf_counter() - started) * 1000, 1) if started else 0.0
    # The request line doubles as the request-count / latency / status metric (EMF, LOG-006).
    emf = metrics.emf(
        {"Requests": (1, "Count"), "Latency": (duration_ms, "Milliseconds")},
        {"Route": rule, "StatusClass": f"{resp.status_code // 100}xx"},
    )
    structlog.get_logger("veda.http").info(
        "request",
        request_id=g.get("request_id"),
        method=request.method,
        route=rule,
        status=resp.status_code,
        duration_ms=duration_ms,
        **emf,
        ip=_truncate_ip(net.client_ip(request.remote_addr, request.headers.get("CF-Connecting-IP"))),
        user_id=ctx.actor_id if ctx else None,
        session_id=ctx.session_id if ctx else None,
    )
