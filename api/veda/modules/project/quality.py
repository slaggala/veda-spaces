"""Quality-check chains and the segregation of fixing from verifying (PEX).

A check without ``recheck_of_id`` starts a **chain**; a recheck targets the chain's head and a check is rechecked at most
once (a unique index), so every chain is a line and its **head** (the last check) is what counts. "Latest per category"
is gone: a PASS in one room can no longer hide a FAIL in another, because each FAIL stays the head of its own chain until
it is itself rechecked.

Who fixed what is read from the immutable timeline (every ``SNAG_FIXED`` event, all fix cycles), never from a column a
later fix overwrites. A person who fixed a snag, or owns it, never verifies it; the same holds for the recheck of a
failed quality check whose chain raised that snag (design review D1, D8).
"""

from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from . import vocab as V
from .models import Project, ProjectEvent, ProjectQcCheck, ProjectQcPoint, ProjectSnag


def checks(s: Session, p: Project) -> list[ProjectQcCheck]:
    return list(s.execute(sa.select(ProjectQcCheck).where(ProjectQcCheck.project_id == p.id,
                                                          ProjectQcCheck.is_deleted == sa.false())
                          .order_by(ProjectQcCheck.created_on, ProjectQcCheck.id)).scalars())  # fmt: skip


def chains(rows: list[ProjectQcCheck]) -> list[list[ProjectQcCheck]]:
    """Every chain, root first. A row whose target is missing (never expected) starts its own chain."""
    by_target = {r.recheck_of_id: r for r in rows if r.recheck_of_id}
    ids = {r.id for r in rows}
    out = []
    for root in (r for r in rows if not r.recheck_of_id or r.recheck_of_id not in ids):
        chain, cur = [root], root
        while cur.id in by_target:
            cur = by_target[cur.id]
            chain.append(cur)
        out.append(chain)
    return out


def chain_of(rows: list[ProjectQcCheck], check: ProjectQcCheck) -> list[ProjectQcCheck]:
    return next(c for c in chains(rows) if any(x.id == check.id for x in c))


def heads(s: Session, p: Project) -> list[ProjectQcCheck]:
    return [c[-1] for c in chains(checks(s, p))]


def ever_failed(chain: Iterable[ProjectQcCheck]) -> bool:
    return any(c.result == "FAIL" for c in chain)


def points(s: Session, p: Project, *, active: bool = True) -> list[ProjectQcPoint]:
    q = sa.select(ProjectQcPoint).where(ProjectQcPoint.project_id == p.id, ProjectQcPoint.is_deleted == sa.false())
    if active:
        q = q.where(ProjectQcPoint.status == "ACTIVE")
    return list(s.execute(q.order_by(ProjectQcPoint.point_no)).scalars())


def point_head(rows: list[ProjectQcCheck], point_id: str) -> ProjectQcCheck | None:
    """The head of the point's latest chain (a point normally has one chain)."""
    found = [c[-1] for c in chains(rows) if c[0].qc_point_id == point_id]
    return found[-1] if found else None


def failed_heads_of(rows: list[ProjectQcCheck], work_package_id: str) -> list[ProjectQcCheck]:
    return [c[-1] for c in chains(rows) if c[0].work_package_id == work_package_id and c[-1].result == "FAIL"]


def snags_from(s: Session, chain: list[ProjectQcCheck]) -> list[ProjectSnag]:
    ids = [c.id for c in chain]
    return list(s.execute(sa.select(ProjectSnag).where(ProjectSnag.qc_check_id.in_(ids),
                                                       ProjectSnag.is_deleted == sa.false())).scalars())  # fmt: skip


def fixers(s: Session, p: Project, snag_ids: Iterable[str]) -> set[str]:
    """Everyone who recorded a fix of these snags, in any fix cycle (from the immutable SNAG_FIXED events)."""
    wanted = set(snag_ids)
    if not wanted:
        return set()
    rows = s.execute(sa.select(ProjectEvent.created_by, ProjectEvent.detail).where(
        ProjectEvent.project_id == p.id, ProjectEvent.event_code == "SNAG_FIXED")).all()  # fmt: skip
    return {by for by, detail in rows if (detail or {}).get("snag_id") in wanted}


def conflicted(s: Session, p: Project, snags: list[ProjectSnag]) -> set[str]:
    """The people who may not verify these snags (or recheck the chain that raised them): their fixers and owners."""
    return fixers(s, p, [n.id for n in snags]) | {n.owner_user_id for n in snags if n.owner_user_id}


def open_snags(snags: list[ProjectSnag]) -> list[ProjectSnag]:
    return [n for n in snags if n.status in V.SNAG_OPEN]
