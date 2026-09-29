"""The security-event writer and keyed hash chain (ADR-004, 05 §9, SEVT-*).

* Success events are written in the business transaction (``record``).
* Failure and denial events are queued (``defer``) and written after the
  request transaction ends, in their own short transaction, so they survive
  rollbacks (SEVT-011) without contending for SQLite's single write lock.
* ``detail`` keys are allow-listed per event type; values are capped at 200
  characters; secrets never enter the log (SEVT-003).
* ``row_hash = HMAC-SHA-256(K[label], prev_hash ‖ JCS(row))`` (05 §9.6).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db
from veda.kernel.context import ActorContext, actor, current_actor
from veda.kernel.ids import ANONYMOUS_USER_ID, SYSTEM_USER_ID, new_id
from veda.kernel.jcs import canonical_bytes

from .models import SecurityEventLog

log = logging.getLogger("veda.security_events")

_A, _S, _P, _M, _AC, _Z, _PI = "AUTHENTICATION", "SESSION", "PASSWORD", "MFA", "ACCOUNT", "AUTHORIZATION", "PUBLIC_INTAKE"

# event_type → (category, severity on success, severity otherwise)
CATALOG: dict[str, tuple[str, str, str]] = {
    "LOGIN": (_A, "INFO", "WARNING"),
    "TOKEN_REFRESH": (_S, "INFO", "WARNING"),
    "REFRESH_REUSE_DETECTED": (_S, "CRITICAL", "CRITICAL"),
    "LOGOUT": (_S, "INFO", "INFO"),
    "SESSION_REVOKED": (_S, "INFO", "WARNING"),
    "PASSWORD_RESET_REQUESTED": (_P, "INFO", "WARNING"),
    "PASSWORD_RESET_COMPLETED": (_P, "INFO", "WARNING"),
    "PASSWORD_CHANGED": (_P, "INFO", "WARNING"),
    "INVITE_SENT": (_AC, "INFO", "INFO"),
    "INVITE_ACCEPTED": (_AC, "INFO", "INFO"),
    "EMAIL_CHANGE_REQUESTED": (_AC, "WARNING", "WARNING"),
    "EMAIL_CHANGE_VERIFIED": (_AC, "WARNING", "WARNING"),
    "EMAIL_CHANGE_COMPLETED": (_AC, "WARNING", "WARNING"),
    "EMAIL_CHANGE_CANCELLED": (_AC, "WARNING", "WARNING"),
    "EMAIL_CHANGE_EXPIRED": (_AC, "WARNING", "WARNING"),
    "MFA_ENROLLMENT_EMAIL_SENT": (_M, "INFO", "WARNING"),
    "MFA_ENROLLMENT_STARTED": (_M, "INFO", "WARNING"),
    "MFA_ENROLLMENT_COMPLETED": (_M, "INFO", "WARNING"),
    "MFA_CHALLENGE": (_M, "INFO", "WARNING"),
    "MFA_RECOVERY_INITIATED": (_M, "WARNING", "CRITICAL"),
    "MFA_RECOVERY_FAILED": (_M, "WARNING", "WARNING"),
    "MFA_RECOVERY_COMPLETED": (_M, "CRITICAL", "CRITICAL"),
    "MFA_RECOVERY_CODE_CONSUMED": (_M, "WARNING", "WARNING"),
    "MFA_AUTHENTICATOR_RE_ENROLLED": (_M, "WARNING", "WARNING"),
    "MFA_RECOVERY_CODES_REGENERATED": (_M, "WARNING", "WARNING"),
    "MFA_FACTOR_REMOVED": (_M, "WARNING", "WARNING"),
    "ADMIN_MFA_RESET_REQUESTED": (_M, "CRITICAL", "CRITICAL"),
    "ADMIN_MFA_RESET_APPROVED": (_M, "CRITICAL", "CRITICAL"),
    "ADMIN_MFA_RESET_DENIED": (_M, "CRITICAL", "CRITICAL"),
    "ADMIN_MFA_RESET_COMPLETED": (_M, "CRITICAL", "CRITICAL"),
    "APPROVAL_REQUESTED": (_Z, "WARNING", "WARNING"),
    "APPROVAL_APPROVED": (_Z, "WARNING", "WARNING"),
    "APPROVAL_DENIED": (_Z, "WARNING", "WARNING"),
    "APPROVAL_EXPIRED": (_Z, "WARNING", "WARNING"),
    "APPROVAL_CANCELLED": (_Z, "WARNING", "WARNING"),
    "BREAK_GLASS_REQUESTED": (_Z, "CRITICAL", "CRITICAL"),
    "BREAK_GLASS_APPROVED": (_Z, "CRITICAL", "CRITICAL"),
    "BREAK_GLASS_CANCELLED": (_Z, "CRITICAL", "CRITICAL"),
    "BREAK_GLASS_EXECUTED": (_Z, "CRITICAL", "CRITICAL"),
    "FOUNDER_TRANSITION": (_AC, "CRITICAL", "CRITICAL"),
    "FOUNDER_ACTION_REQUESTED": (_Z, "CRITICAL", "CRITICAL"),
    "FOUNDER_ACTION_APPROVED": (_Z, "CRITICAL", "CRITICAL"),
    "FOUNDER_ACTION_DENIED": (_Z, "CRITICAL", "CRITICAL"),
    "FOUNDER_ACTION_CANCELLED": (_Z, "CRITICAL", "CRITICAL"),
    "FOUNDER_ACTION_EXECUTED": (_Z, "CRITICAL", "CRITICAL"),
    "FOUNDER_ACTION_FAILED": (_Z, "CRITICAL", "CRITICAL"),
    "FOUNDER_GOVERNANCE_BYPASS_BLOCKED": (_Z, "CRITICAL", "CRITICAL"),
    "BOOTSTRAP_FOUNDER": (_AC, "CRITICAL", "CRITICAL"),
    "FOUNDER_POLICY_CHANGED": (_AC, "CRITICAL", "CRITICAL"),
    "MFA_RECOVERY_SESSION_EXPIRED": (_M, "WARNING", "WARNING"),
    "MFA_CHALLENGE_REPLAY_BLOCKED": (_M, "WARNING", "WARNING"),
    "ACCOUNT_THROTTLED": (_AC, "WARNING", "WARNING"),
    "ACCOUNT_UNTHROTTLED": (_AC, "WARNING", "WARNING"),
    "PERMISSION_DENIED": (_Z, "WARNING", "WARNING"),
    "PERMISSION_SUSPENDED": (_Z, "WARNING", "WARNING"),
    "PERMISSION_REACTIVATED": (_Z, "WARNING", "WARNING"),
    "SENSITIVE_ACTION": (_Z, "WARNING", "WARNING"),
    "SENSITIVE_READ": (_Z, "INFO", "INFO"),
    "RECOVERY_SESSION_BLOCKED": (_Z, "WARNING", "WARNING"),
    "PUBLIC_INTAKE_BLOCKED": (_PI, "INFO", "INFO"),
    "PUBLIC_INTAKE_QUARANTINED": (_PI, "INFO", "INFO"),
    "SECURITY_LOG_ARCHIVED": (_AC, "INFO", "CRITICAL"),
    "SECURITY_LOG_CHAIN_ANCHORED": (_AC, "INFO", "CRITICAL"),
    "SECURITY_LOG_CHAIN_BROKEN": (_AC, "CRITICAL", "CRITICAL"),
    # Summary events for maintenance jobs (03 §2.10 "each purge writes a summary security event").
    "MAINTENANCE_PURGE": (_AC, "INFO", "WARNING"),
    "GOVERNANCE_INVARIANT_FAILED": (_Z, "CRITICAL", "CRITICAL"),
}

FAILURE_REASONS = frozenset({
    "BAD_PASSWORD", "UNKNOWN_USER", "THROTTLED", "DISABLED", "INVITED", "NOT_HUMAN", "RATE_LIMITED", "TOKEN_INVALID",
    "TOKEN_EXPIRED", "TOKEN_REUSED", "SESSION_REVOKED", "CODE_INVALID", "CODE_REPLAYED", "RECOVERY_CODE_INVALID",
    "CHALLENGE_EXPIRED", "CHALLENGE_EXHAUSTED", "POLICY", "CAPTCHA_FAILED", "ESCALATION_DENIED", "STEP_UP_REQUIRED",
    "MFA_REQUIRED", "COOLING_OFF", "FOUNDER_PROTECTED", "APPROVAL_REQUIRED",
})

_COMMON_KEYS = frozenset({"reason", "method", "stage", "scope", "count", "action", "channel", "status", "route"})
DETAIL_KEYS: dict[str, frozenset[str]] = {
    "LOGIN": frozenset({"method", "network", "captcha"}),
    "SESSION_REVOKED": frozenset({"reason", "scope", "count"}),
    "LOGOUT": frozenset({"scope"}),
    "EMAIL_CHANGE_REQUESTED": frozenset({"proposed_email", "requested_by", "approval_id"}),
    "EMAIL_CHANGE_COMPLETED": frozenset({"previous_email", "new_email"}),
    "EMAIL_CHANGE_CANCELLED": frozenset({"proposed_email"}),
    "EMAIL_CHANGE_EXPIRED": frozenset({"proposed_email"}),
    "EMAIL_CHANGE_VERIFIED": frozenset({"new_email"}),
    "PERMISSION_DENIED": frozenset({"reason", "route"}),
    "PERMISSION_SUSPENDED": frozenset({"reason", "codes"}),
    "PERMISSION_REACTIVATED": frozenset({"codes"}),
    "SENSITIVE_ACTION": frozenset({"action", "sensitivity_class", "reason"}),
    "SENSITIVE_READ": frozenset({"sensitivity_class", "route"}),
    "ACCOUNT_THROTTLED": frozenset({"scope", "until", "networks"}),
    "ACCOUNT_UNTHROTTLED": frozenset({"scope"}),
    "PUBLIC_INTAKE_BLOCKED": frozenset({"reason"}),
    "PUBLIC_INTAKE_QUARANTINED": frozenset({"reason"}),
    "MAINTENANCE_PURGE": frozenset({"job", "table", "count", "enabled"}),
    "SECURITY_LOG_CHAIN_ANCHORED": frozenset({"head_seq", "anchor"}),
    "SECURITY_LOG_CHAIN_BROKEN": frozenset({"at_seq", "problem"}),
    "SECURITY_LOG_ARCHIVED": frozenset({"through_seq", "count", "anchor"}),
    "GOVERNANCE_INVARIANT_FAILED": frozenset({"invariant", "problem"}),
    "BOOTSTRAP_FOUNDER": frozenset({"channel"}),
}

_MAX_DETAIL_VALUE = 200
PROHIBITED_DETAIL_KEYS = frozenset({
    "password", "token", "access_token", "refresh_token", "code", "otp", "secret", "recovery_code", "cookie",
    "authorization", "mfa_token", "hash", "body",
})


class SecurityEventError(RuntimeError):
    pass


@dataclass
class PendingEvent:
    event_type: str
    outcome: str
    ctx: ActorContext | None
    occurred_on: datetime
    fields: dict[str, Any] = field(default_factory=dict)


def _validate_detail(event_type: str, detail: dict | None) -> dict | None:
    if not detail:
        return None
    allowed = DETAIL_KEYS.get(event_type, frozenset()) | _COMMON_KEYS
    clean: dict[str, Any] = {}
    for key, value in detail.items():
        if key in PROHIBITED_DETAIL_KEYS or key not in allowed:
            raise SecurityEventError(f"detail key {key!r} not allowed for {event_type}")
        if isinstance(value, str) and len(value) > _MAX_DETAIL_VALUE:
            raise SecurityEventError(f"detail value for {key!r} longer than {_MAX_DETAIL_VALUE}")
        if isinstance(value, list):
            value = [str(v)[:_MAX_DETAIL_VALUE] for v in value][:50]
        clean[key] = value
    return clean


def email_attempt_hash(email_normalized: str) -> str:
    return hmac.new(settings().email_hash_hmac_key, email_normalized.encode(), hashlib.sha256).hexdigest()


def row_representation(row: SecurityEventLog) -> dict[str, Any]:
    """Application-level representation of every non-hash column (05 §9.6)."""
    rep: dict[str, Any] = {}
    for column in SecurityEventLog.__table__.columns:
        if column.name in ("row_hash", "prev_hash"):
            continue
        value = getattr(row, column.key)
        if isinstance(value, datetime):
            value = clock.to_rfc3339(value, micros=True)
        rep[column.name] = value
    return rep


def compute_row_hash(row: SecurityEventLog, key: bytes) -> str:
    message = (row.prev_hash or "").encode("ascii") + canonical_bytes(row_representation(row))
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _chain_head(session: Session) -> tuple[int, str | None]:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(sa.text("SELECT pg_advisory_xact_lock(7845120001)"))  # A-13
    head = session.execute(
        sa.select(SecurityEventLog.chain_seq, SecurityEventLog.row_hash)
        .order_by(SecurityEventLog.chain_seq.desc()).limit(1)
        .execution_options(include_deleted=True)
    ).first()
    if head is None:
        return 0, None
    return int(head[0]), head[1]


def _build(session: Session, event_type: str, outcome: str, ctx: ActorContext | None, occurred_on: datetime,
           **fields: Any) -> SecurityEventLog:
    if event_type not in CATALOG:
        raise SecurityEventError(f"unknown event type {event_type}")
    if outcome not in ("SUCCESS", "FAILURE", "BLOCKED"):
        raise SecurityEventError(f"bad outcome {outcome}")
    category, sev_ok, sev_other = CATALOG[event_type]
    severity = fields.pop("severity", None) or (sev_ok if outcome == "SUCCESS" else sev_other)
    failure_reason = fields.pop("failure_reason", None)
    if failure_reason is not None and failure_reason not in FAILURE_REASONS:
        raise SecurityEventError(f"failure_reason {failure_reason} not in the controlled vocabulary")
    detail = _validate_detail(event_type, fields.pop("detail", None))
    target = fields.pop("target", None)
    subject_user_id = fields.pop("subject_user_id", None)
    email_hash = fields.pop("email_attempted_hash", None)
    permission_code = fields.pop("permission_code", None)
    session_id = fields.pop("session_id", None)
    if fields:
        raise SecurityEventError(f"unexpected fields {sorted(fields)}")
    ctx = ctx or current_actor()
    actor_id = ctx.actor_id if ctx else SYSTEM_USER_ID
    now = db.tx_time(session)
    seq, prev = _chain_head(session)
    label = settings().chain_key_label
    row = SecurityEventLog(
        id=new_id(), event_type=event_type, event_category=category, outcome=outcome, severity=severity,
        subject_user_id=subject_user_id, session_id=session_id or (ctx.session_id if ctx else None),
        email_attempted_hash=email_hash, failure_reason=failure_reason, permission_code=permission_code,
        target_entity_type=target[0] if target else None, target_entity_id=target[1] if target else None,
        occurred_on=occurred_on, ip_address=ctx.ip if ctx else None,
        user_agent=(ctx.user_agent[:500] if ctx and ctx.user_agent else None),
        request_id=(ctx.request_id[:64] if ctx and ctx.request_id else None), detail=detail,
        chain_seq=seq + 1, prev_hash=prev, chain_key_label=label,
    )
    row.created_on = now
    row.updated_on = now
    row.created_by = actor_id
    row.updated_by = actor_id
    row.is_deleted = False
    row.deleted_on = None
    row.deleted_by = None
    row.version = 1
    row.row_hash = compute_row_hash(row, settings().chain_keys[label])
    row._veda_stamped = True
    return row


def record(session: Session, event_type: str, outcome: str = "SUCCESS", **fields: Any) -> SecurityEventLog:
    """Write an event in the caller's transaction (success path; fail closed)."""
    row = _build(session, event_type, outcome, current_actor(), clock.now(), **fields)
    session.add(row)
    session.flush()
    return row


# --- deferred (own-transaction) events ---------------------------------------

_pending: ContextVar[list[PendingEvent] | None] = ContextVar("veda_pending_events", default=None)


def begin_request_scope() -> None:
    _pending.set([])


def defer(event_type: str, outcome: str, **fields: Any) -> None:
    """Queue a failure/denial event; written after the request transaction ends."""
    if fields.get("dedupe_key") is not None:
        key, window = fields.pop("dedupe_key"), fields.pop("dedupe_seconds", 60)
        if not _dedupe(key, window):
            return
    fields.pop("dedupe_seconds", None)
    pending = _pending.get()
    event = PendingEvent(event_type, outcome, current_actor(), clock.now(), fields)
    if pending is None:
        _write_now([event])
    else:
        pending.append(event)


def flush_deferred() -> None:
    pending = _pending.get()
    if not pending:
        return
    events = list(pending)
    pending.clear()
    _write_now(events)


def _write_now(events: list[PendingEvent]) -> None:
    try:
        ctx = events[0].ctx or ActorContext(actor_id=ANONYMOUS_USER_ID)
        with actor(ctx), db.unit_of_work(write=True) as session:
            for ev in events:
                row = _build(session, ev.event_type, ev.outcome, ev.ctx or ctx, ev.occurred_on, **dict(ev.fields))
                session.add(row)
                session.flush()
    except Exception:  # pragma: no cover - alerting path (SEVT-011)
        log.critical("security_event_writer_failed", exc_info=True)


# --- de-duplication (PERMISSION_DENIED per minute, SENSITIVE_READ per 15 min) --

_dedupe_lock = threading.Lock()
_dedupe_seen: dict[str, float] = {}


def _dedupe(key: str, window_seconds: int) -> bool:
    now = clock.now().timestamp()
    with _dedupe_lock:
        if len(_dedupe_seen) > 10_000:
            for k in [k for k, v in _dedupe_seen.items() if v <= now]:
                _dedupe_seen.pop(k, None)
        expiry = _dedupe_seen.get(key)
        if expiry is not None and expiry > now:
            return False
        _dedupe_seen[key] = now + window_seconds
        return True


def reset_dedupe() -> None:
    with _dedupe_lock:
        _dedupe_seen.clear()


def record_deduped(session: Session, key: str, window_seconds: int, event_type: str, outcome: str = "SUCCESS", **fields):
    if _dedupe(key, window_seconds):
        return record(session, event_type, outcome, **fields)
    return None


# --- verification (SEVT-006) ---------------------------------------------------

@dataclass
class ChainReport:
    ok: bool
    checked: int
    head_seq: int
    head_hash: str | None
    problem: str | None = None
    at_seq: int | None = None


def verify_chain(session: Session, *, from_seq: int = 1, anchor_hash: str | None = None) -> ChainReport:
    keys = settings().chain_keys
    rows = session.execute(
        sa.select(SecurityEventLog).where(SecurityEventLog.chain_seq >= from_seq)
        .order_by(SecurityEventLog.chain_seq).execution_options(include_deleted=True)
    ).scalars()
    expected_seq = from_seq
    prev = anchor_hash
    checked = 0
    first = True
    for row in rows:
        if row.chain_seq != expected_seq:
            return ChainReport(False, checked, expected_seq - 1, prev, "gap", expected_seq)
        # Without an anchor hash, a verification starting mid-chain trusts the first row's prev_hash.
        if not (first and anchor_hash is None and from_seq > 1) and row.prev_hash != prev:
            return ChainReport(False, checked, row.chain_seq - 1, prev, "prev_hash mismatch", row.chain_seq)
        key = keys.get(row.chain_key_label)
        if key is None:
            return ChainReport(False, checked, row.chain_seq - 1, prev, "unknown key label", row.chain_seq)
        if not hmac.compare_digest(compute_row_hash(row, key), row.row_hash):
            return ChainReport(False, checked, row.chain_seq - 1, prev, "row_hash mismatch", row.chain_seq)
        prev = row.row_hash
        expected_seq += 1
        checked += 1
        first = False
    return ChainReport(True, checked, expected_seq - 1, prev)
