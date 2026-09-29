"""The kernel ``before_flush`` hook (03 §2.8, 07 §3).

For each new, dirty or deleted ``AuditedBase`` object it:

1. requires an ActorContext (else ``AuditContextMissing`` → rollback);
2. stamps the contract columns from the single unit-of-work clock reading;
3. for FULL-policy tables, adds ``audit_log`` rows to the same session so
   business rows, contract columns and audit rows commit atomically.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from . import clock
from .audit_registry import ALWAYS_EXCLUDED, FULL, IMMUTABLE_STORE, policy_for
from .base import AuditedBase
from .context import AuditContextMissing, current_actor
from .db import transaction_id, tx_time
from .ids import new_id

REDACTED = "[REDACTED]"
_CONTRACT_STAMPS = frozenset({"created_on", "created_by", "updated_on", "updated_by", "version"})
_SOFT_DELETE_FIELDS = ("is_deleted", "deleted_on", "deleted_by")


class ImmutableRowError(RuntimeError):
    pass


def serialize(value: Any) -> Any:
    """Audit payload serialization (07 §4)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return clock.to_rfc3339(value, micros=True)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    return str(value)


def _column_keys(obj) -> list[str]:
    return [c.key for c in inspect(obj).mapper.column_attrs]


def _snapshot(obj, policy) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key in _column_keys(obj):
        if key in ALWAYS_EXCLUDED or key in policy.excluded:
            continue
        value = getattr(obj, key)
        data[key] = REDACTED if (key in policy.redacted and value is not None) else serialize(value)
    return data


def _changes(obj, policy) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    state = inspect(obj)
    old: dict[str, Any] = {}
    new: dict[str, Any] = {}
    changed: list[str] = []
    for attr in state.mapper.column_attrs:
        key = attr.key
        hist = state.attrs[key].history
        if not hist.has_changes():
            continue
        before = hist.deleted[0] if hist.deleted else None
        after = hist.added[0] if hist.added else None
        if before == after:
            continue
        if key in ALWAYS_EXCLUDED or key in policy.excluded:
            continue
        changed.append(key)
        if key in policy.redacted:
            old[key] = REDACTED if before is not None else None
            new[key] = REDACTED if after is not None else None
        else:
            old[key] = serialize(before)
            new[key] = serialize(after)
    return old, new, changed


def _history_value(obj, key):
    hist = inspect(obj).attrs[key].history
    before = hist.deleted[0] if hist.deleted else getattr(obj, key)
    after = hist.added[0] if hist.added else getattr(obj, key)
    return before, after


def build_audit_row(
    session: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    old_value=None,
    new_value=None,
    changed_fields=None,
    parent: tuple[str, str] | None = None,
):
    """Create an ``audit_log`` row stamped for this unit of work."""
    from veda.platform.audit.models import AuditLog

    ctx = current_actor()
    if ctx is None:
        raise AuditContextMissing("audit row without ActorContext")
    now = tx_time(session)
    row = AuditLog(
        id=new_id(),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        changed_fields=changed_fields,
        performed_by=ctx.actor_id,
        performed_on=now,
        performed_via=ctx.via,
        parent_entity_type=parent[0] if parent else None,
        parent_entity_id=parent[1] if parent else None,
        transaction_id=transaction_id(session),
        request_id=(ctx.request_id or None) and ctx.request_id[:64],
        session_id=ctx.session_id,
        ip_address=ctx.ip,
        user_agent=(ctx.user_agent or None) and ctx.user_agent[:500],
        reason=(ctx.reason or None) and ctx.reason[:500],
        payload_schema=1,
    )
    row.created_on = now
    row.updated_on = now
    row.created_by = ctx.actor_id
    row.updated_by = ctx.actor_id
    row.is_deleted = False
    row.version = 1
    row._veda_stamped = True
    return row


def _parent_of(obj, policy) -> tuple[str, str] | None:
    if not policy.parent:
        return None
    parent_type, fk_attr = policy.parent
    parent_id = getattr(obj, fk_attr, None)
    return (parent_type, parent_id) if parent_id else None


@event.listens_for(Session, "before_flush")
def _before_flush(session: Session, flush_context, instances) -> None:
    new_objs = [o for o in session.new if isinstance(o, AuditedBase)]
    dirty_objs = [
        o for o in session.dirty if isinstance(o, AuditedBase) and session.is_modified(o, include_collections=False)
    ]
    deleted_objs = [o for o in session.deleted if isinstance(o, AuditedBase)]
    if not (new_objs or dirty_objs or deleted_objs):
        return
    ctx = current_actor()
    if ctx is None:
        raise AuditContextMissing("write attempted without ActorContext (AUDIT-010)")
    now = tx_time(session)
    audit_rows = []
    versioned: set = session.info.setdefault("veda_versioned", set())

    for obj in new_objs:
        if getattr(obj, "_veda_stamped", False):
            continue
        if obj.id is None:
            obj.id = new_id()
        obj.created_on = now
        obj.updated_on = now
        obj.created_by = ctx.actor_id
        obj.updated_by = ctx.actor_id
        if obj.is_deleted is None:
            obj.is_deleted = False
        if obj.is_deleted:
            obj.deleted_on = obj.deleted_on or now
            obj.deleted_by = obj.deleted_by or ctx.actor_id
        obj.version = 1
        versioned.add((obj.__tablename__, obj.id))
        policy = policy_for(obj.__tablename__)
        if policy is None:
            raise RuntimeError(f"table {obj.__tablename__} not registered in the audit policy registry")
        if policy.policy == FULL:
            audit_rows.append(
                build_audit_row(
                    session,
                    entity_type=obj.__tablename__,
                    entity_id=obj.id,
                    action="CREATE",
                    old_value=None,
                    new_value=_snapshot(obj, policy),
                    changed_fields=sorted(k for k, v in _snapshot(obj, policy).items() if v is not None),
                    parent=_parent_of(obj, policy),
                )
            )

    for obj in dirty_objs:
        policy = policy_for(obj.__tablename__)
        if policy is None:
            raise RuntimeError(f"table {obj.__tablename__} not registered in the audit policy registry")
        if policy.policy == IMMUTABLE_STORE:
            raise ImmutableRowError(f"{obj.__tablename__} rows are immutable (EXC-001)")
        if inspect(obj).attrs["id"].history.has_changes():
            raise ImmutableRowError("id is immutable (ADR-002)")
        for key in ("created_on", "created_by"):
            if inspect(obj).attrs[key].history.deleted:
                raise ImmutableRowError(f"{key} is immutable (ADR-003)")
        was_deleted, is_deleted = _history_value(obj, "is_deleted")
        action = "UPDATE"
        if not was_deleted and is_deleted:
            action = "DELETE"
            if not policy.soft_delete:
                raise ImmutableRowError(f"{obj.__tablename__} is never soft-deleted (03 §2.9)")
            obj.deleted_on = obj.deleted_on or now
            obj.deleted_by = obj.deleted_by or ctx.actor_id
        elif was_deleted and not is_deleted:
            action = "RESTORE"
            obj.deleted_on = None
            obj.deleted_by = None
        obj.updated_on = now
        obj.updated_by = ctx.actor_id
        key = (obj.__tablename__, obj.id)
        if key not in versioned:  # exactly one increment per object per unit of work
            obj.version = (obj.version or 0) + 1
            versioned.add(key)
        if policy.policy != FULL:
            continue
        if action == "DELETE":
            audit_rows.append(
                build_audit_row(
                    session,
                    entity_type=obj.__tablename__,
                    entity_id=obj.id,
                    action="DELETE",
                    old_value={
                        "is_deleted": False,
                        "deleted_on": None,
                        "deleted_by": None,
                        "_snapshot": _snapshot(obj, policy),
                    },
                    new_value={
                        "is_deleted": True,
                        "deleted_on": serialize(obj.deleted_on),
                        "deleted_by": obj.deleted_by,
                    },
                    changed_fields=list(_SOFT_DELETE_FIELDS),
                    parent=_parent_of(obj, policy),
                )
            )
            continue
        if action == "RESTORE":
            audit_rows.append(
                build_audit_row(
                    session,
                    entity_type=obj.__tablename__,
                    entity_id=obj.id,
                    action="RESTORE",
                    old_value={"is_deleted": True},
                    new_value={"is_deleted": False, "deleted_on": None, "deleted_by": None},
                    changed_fields=list(_SOFT_DELETE_FIELDS),
                    parent=_parent_of(obj, policy),
                )
            )
            continue
        old, new, changed = _changes(obj, policy)
        if not changed:
            continue  # only excluded fields changed → no audit row (07 §2)
        if obj.id in (session.info.get("erasure_entities") or ()):
            # Erasure: the UPDATE row records the change with the old PII values redacted (07 §8.2 step 1).
            old = {k: ("[ERASED]" if k in policy.pii and v is not None else v) for k, v in old.items()}
        audit_rows.append(
            build_audit_row(
                session,
                entity_type=obj.__tablename__,
                entity_id=obj.id,
                action="UPDATE",
                old_value=old,
                new_value=new,
                changed_fields=changed,
                parent=_parent_of(obj, policy),
            )
        )

    for obj in deleted_objs:
        policy = policy_for(obj.__tablename__)
        if policy is None:
            raise RuntimeError(f"table {obj.__tablename__} not registered")
        if policy.policy == IMMUTABLE_STORE:
            raise ImmutableRowError(f"{obj.__tablename__} rows are immutable (EXC-001)")
        if policy.policy == FULL:
            if not policy.exceptions:
                raise ImmutableRowError(f"hard delete of {obj.__tablename__} is not allowed (03 §2.4)")
            audit_rows.append(
                build_audit_row(
                    session,
                    entity_type=obj.__tablename__,
                    entity_id=obj.id,
                    action="HARD_DELETE",
                    old_value=_snapshot(obj, policy),
                    new_value=None,
                    changed_fields=None,
                    parent=_parent_of(obj, policy),
                )
            )

    for row in audit_rows:
        session.add(row)


def soft_delete(obj: AuditedBase) -> None:
    """Soft-delete helper; the hook stamps ``deleted_on``/``deleted_by``."""
    obj.is_deleted = True


def restore(obj: AuditedBase) -> None:
    obj.is_deleted = False


def write_explicit_audit(
    session: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    new_value=None,
    old_value=None,
    changed_fields=None,
    parent=None,
) -> None:
    """Explicit audit rows for EXPORT / ANONYMIZE / summary HARD_DELETE (07 §4)."""
    session.add(
        build_audit_row(
            session,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            changed_fields=changed_fields,
            parent=parent,
        )
    )


def bulk_mutate(session: Session, statement: sa.Update | sa.Delete) -> None:  # pragma: no cover - guard
    raise RuntimeError("ORM bulk update()/delete() is banned in business code (07 §3); mutate through the ORM")


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_soft_rollback")
def _reset_versioned(session: Session, *args) -> None:
    session.info["veda_versioned"] = set()
