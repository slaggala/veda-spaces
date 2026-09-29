"""Read helpers for assertions: rows are detached with their loaded state."""

from __future__ import annotations

import sqlalchemy as sa

from veda.kernel import db


def rows(stmt, *, include_deleted: bool = True) -> list:
    with db.unit_of_work(write=False) as s:
        result = s.execute(stmt.execution_options(include_deleted=include_deleted)).scalars().all()
        s.expunge_all()
        return result


def one(stmt, **kw):
    result = rows(stmt, **kw)
    return result[0] if result else None


def scalar(stmt):
    with db.unit_of_work(write=False) as s:
        return s.execute(stmt).scalar()


def get(model, id_):
    return one(sa.select(model).where(model.id == id_))


def events(event_type=None, **filters) -> list:
    from veda.platform.auth.models import SecurityEventLog

    q = sa.select(SecurityEventLog).order_by(SecurityEventLog.chain_seq)
    if event_type:
        q = q.where(SecurityEventLog.event_type == event_type)
    for k, v in filters.items():
        q = q.where(getattr(SecurityEventLog, k) == v)
    return rows(q)


def audits(entity_id=None, **filters) -> list:
    from veda.platform.audit.models import AuditLog

    q = sa.select(AuditLog).order_by(AuditLog.performed_on, AuditLog.id)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    for k, v in filters.items():
        q = q.where(getattr(AuditLog, k) == v)
    return rows(q)
