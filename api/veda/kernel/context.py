"""Actor context (03 §2.8, 07 §3).

Every write happens under an ActorContext. The audit hook refuses to flush
without one (AUDIT-010). Payloads never supply actor columns (DATA-004).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass, replace

from .ids import ANONYMOUS_USER_ID, SYSTEM_USER_ID, WEB_INTAKE_USER_ID

VIA_VALUES = ("API", "PUBLIC_FORM", "SYSTEM_JOB", "MIGRATION", "CLI")


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    via: str = "API"
    request_id: str | None = None
    session_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    reason: str | None = None

    def with_reason(self, reason: str | None) -> ActorContext:
        return replace(self, reason=reason)

    def with_actor(self, actor_id: str) -> ActorContext:
        return replace(self, actor_id=actor_id)


_current: ContextVar[ActorContext | None] = ContextVar("veda_actor", default=None)


class AuditContextMissing(RuntimeError):
    """Raised when a write is flushed without an ActorContext (AUDIT-010)."""


def current_actor() -> ActorContext | None:
    return _current.get()


def require_actor() -> ActorContext:
    ctx = _current.get()
    if ctx is None:
        raise AuditContextMissing("no ActorContext for write")
    return ctx


def set_actor(ctx: ActorContext | None):
    return _current.set(ctx)


def reset_actor(token) -> None:
    _current.reset(token)


@contextlib.contextmanager
def actor(ctx: ActorContext) -> Iterator[ActorContext]:
    token = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)


@contextlib.contextmanager
def reason(text: str | None) -> Iterator[None]:
    ctx = require_actor()
    token = _current.set(ctx.with_reason(text))
    try:
        yield
    finally:
        _current.reset(token)


def system_context(via: str = "SYSTEM_JOB", request_id: str | None = None) -> ActorContext:
    return ActorContext(actor_id=SYSTEM_USER_ID, via=via, request_id=request_id)


def web_intake_context(request_id: str | None, ip: str | None, user_agent: str | None) -> ActorContext:
    return ActorContext(
        actor_id=WEB_INTAKE_USER_ID, via="PUBLIC_FORM", request_id=request_id, ip=ip, user_agent=user_agent
    )


def anonymous_context(request_id: str | None, ip: str | None, user_agent: str | None) -> ActorContext:
    return ActorContext(actor_id=ANONYMOUS_USER_ID, via="API", request_id=request_id, ip=ip, user_agent=user_agent)


@contextlib.contextmanager
def acting(session, ctx: ActorContext) -> Iterator[ActorContext]:
    """Act as ``ctx`` for writes made inside the block.

    Pending ORM changes are flushed before the previous context is restored, so the audit
    hook stamps them with this actor rather than the caller's (03 §2.8)."""
    token = _current.set(ctx)
    try:
        yield ctx
        session.flush()
    finally:
        _current.reset(token)
