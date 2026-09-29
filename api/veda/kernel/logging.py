"""Structured JSON logging (02 §9, LOG-001, LOG-003).

Log line: ts, level, logger, event, request_id, session_id, user_id, method,
route (templated), status, duration_ms, ip (/24). Bodies, tokens, cookies and
Authorization headers are never logged; emails and phones are masked.
"""

from __future__ import annotations

import logging
import re
import sys
import time

import structlog

_EMAIL = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+)")
_PHONE = re.compile(r"(?<![\w:.-])\+?\d(?:\s?\d){9,14}(?![\w:.-])")
DENYLIST = ("password", "token", "authorization", "cookie", "secret", "code", "recovery")


def _mask(value: str) -> str:
    value = _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", value)
    return _PHONE.sub(lambda m: m.group(0)[:3] + "******" + m.group(0)[-4:], value)


_SAFE_KEYS = frozenset({"ts", "request_id", "session_id", "user_id", "route", "method", "level", "logger"})


def _scrub(_, __, event_dict):
    for key in list(event_dict):
        if key in _SAFE_KEYS:
            continue
        if any(d in key.lower() for d in DENYLIST):
            event_dict[key] = "[REDACTED]"
        elif isinstance(event_dict[key], str):
            event_dict[key] = _mask(event_dict[key])
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=getattr(logging, level.upper(), logging.INFO))
    logging.getLogger("alembic").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            _scrub,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _truncate_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    if ":" in ip:
        return ":".join(ip.split(":")[:4]) + "::/64"
    parts = ip.split(".")
    return ".".join(parts[:3]) + ".0/24" if len(parts) == 4 else ip


def log_request(resp, started: float | None) -> None:
    from flask import g, request

    from veda.kernel.context import current_actor

    ctx = current_actor()
    rule = request.url_rule.rule if request.url_rule else "unmatched"
    structlog.get_logger("veda.http").info(
        "request",
        request_id=g.get("request_id"),
        method=request.method,
        route=rule,
        status=resp.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 1) if started else None,
        ip=_truncate_ip(request.headers.get("CF-Connecting-IP") or request.remote_addr),
        user_id=ctx.actor_id if ctx else None,
        session_id=ctx.session_id if ctx else None,
    )
