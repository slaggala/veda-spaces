"""Project-scoped access and locking (PLB-33, PLB-36).

Every ``project.*`` code is scoped. ALL reaches every project; OWN reaches a project while the actor is an active
member of its team. A project outside the actor's read scope answers 404 (its existence is not disclosed: no guessed
id reveals anything); a visible project whose action is outside the action's scope answers 403. A project whose lead
was erased is closed to writes.

Every write takes the project's row lock first (PostgreSQL ``SELECT … FOR UPDATE``; SQLite write units of work already
run under BEGIN IMMEDIATE) and then re-reads the project and the rows it will change, so a transition, a checklist
update, a new blocker, a variation acceptance or a handover on one project run one after the other and each decides on
committed state. If-Match is compared with the re-read version, never with what was read before the lock.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError, not_found
from veda.kernel.http import check_version
from veda.modules.crm.leads.models import Lead

from .models import Project, ProjectMember


def member_project_ids(user_id: str):
    return sa.select(ProjectMember.project_id).where(
        ProjectMember.user_id == user_id, ProjectMember.is_active == sa.true(), ProjectMember.is_deleted == sa.false()
    )


def condition(ctx, permission: str, project_id_column=None) -> sa.ColumnElement[bool]:
    column = Project.id if project_id_column is None else project_id_column
    scope = ctx.scope(permission)
    if scope == "ALL":
        return sa.true()
    if scope == "OWN":
        return column.in_(member_project_ids(ctx.user.id))
    return sa.false()


def is_member(s: Session, project_id: str, user_id: str) -> bool:
    return s.execute(member_project_ids(user_id).where(ProjectMember.project_id == project_id)).first() is not None


def visible(s: Session, ctx, project_id: str, permission: str = "project.view") -> Project:
    if ctx.scope(permission) is None:
        from veda.platform.auth.request_auth import deny

        deny(ctx, permission)
    p = s.execute(sa.select(Project).where(Project.id == project_id, condition(ctx, permission))).scalar_one_or_none()
    if p is None:
        raise not_found()
    return p


def can(s: Session, ctx, p: Project, permission: str) -> bool:
    scope = ctx.scope(permission)
    return scope == "ALL" or (scope == "OWN" and is_member(s, p.id, ctx.user.id))


def require(s: Session, ctx, p: Project, permission: str) -> None:
    """The action's capability, in scope for this project (403 when the project is visible but out of scope)."""
    scope = ctx.scope(permission)
    if scope is None:
        from veda.platform.auth.request_auth import deny

        deny(ctx, permission)
    if scope == "OWN" and not is_member(s, p.id, ctx.user.id):
        raise ApiError(403, "PERMISSION_DENIED", f"Requires {permission} on this project (you are not on its team).",
                       extra={"permission": permission})  # fmt: skip


def lock(s: Session, p: Project, *rows) -> Project:
    """Take the project's row lock and re-read the project and ``rows`` under it."""
    if s.get_bind().dialect.name == "postgresql":
        s.execute(sa.select(Project.id).where(Project.id == p.id).with_for_update())
    s.refresh(p)
    for row in rows:
        s.refresh(row)
    return p


def writable(s: Session, p: Project) -> None:
    lead = s.get(Lead, p.lead_id)
    if lead is None or lead.anonymized_on is not None:
        raise ApiError(409, "INVALID_STATE", "This project's customer record was erased; the project can no longer "
                       "change.")  # fmt: skip
    if p.status != "ACTIVE":
        raise ApiError(409, "PROJECT_HANDED_OVER", f"{p.project_number} is handed over; its history is closed.",
                       extra={"status": p.status})  # fmt: skip


def for_write(s: Session, ctx, p: Project, permission: str, *rows, if_match: int | None = None, match=None,
              precondition: bool = True) -> Project:  # fmt: skip
    """Scope check, project lock, re-read, then If-Match against the re-read version of ``match`` (default: the
    project; for a change to one child row, that row). A new child row (``precondition=False``) needs no If-Match:
    it changes nothing anyone saw, and its creation is replay-safe through the Idempotency-Key."""
    require(s, ctx, p, permission)
    lock(s, p, *rows)
    writable(s, p)
    if precondition:
        check_version(if_match, (p if match is None else match).version)
    return p


def touch(s: Session, p: Project) -> None:
    """Move the project's version on any change under it, so a screen showing the earlier state cannot act on it."""
    from veda.kernel import db

    p.updated_on = db.tx_time(s)
