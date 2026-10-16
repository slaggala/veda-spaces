"""Work packages (PEX-010 … PEX-016): the body of work in each stage, with explicit commands only.

A package belongs to one stage of the pinned lifecycle and optionally one space of the property. Its status moves only
by command: start (in its own stage, the project's current one; its predecessor closed; no open gating blocker on it),
complete (started; the same conditions; an actual finish that has passed), reopen (completed work, with a reason, while
its stage is open), cancel (not completed, with a reason). BLOCKED is never stored: ``derived_state`` reports it from
the open gating blockers linked to the package. A completed package whose quality-check chain ends in FAIL, or with an
open snag on it, is CORRECTION_REQUIRED, never shown as finished.

Planned dates are an internal plan, never a commitment: a package without them is unscheduled. Setting the first date
is planning; changing a date already set is a **replan** that needs a reason, moves ``plan_revision`` and records the
previous and new dates on the timeline. Nothing is inferred from the calendar.
"""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.kernel.errors import ApiError, field_error

from . import access, events, lifecycle, quality, service
from . import vocab as V
from .models import Project, ProjectBlocker, ProjectSnag, ProjectWorkPackage


def rows(s: Session, p: Project) -> list[ProjectWorkPackage]:
    return list(s.execute(sa.select(ProjectWorkPackage).where(ProjectWorkPackage.project_id == p.id,
                                                              ProjectWorkPackage.is_deleted == sa.false())
                          .order_by(ProjectWorkPackage.package_no)).scalars())  # fmt: skip


def gating_blockers(s: Session, wp: ProjectWorkPackage) -> list[ProjectBlocker]:
    return list(s.execute(sa.select(ProjectBlocker).where(ProjectBlocker.related_work_package_id == wp.id,
                                                          ProjectBlocker.impact == "GATING",
                                                          ProjectBlocker.is_deleted == sa.false(),
                                                          ProjectBlocker.status.in_(V.BLOCKER_OPEN))).scalars())  # fmt: skip


def open_snags(s: Session, wp: ProjectWorkPackage) -> list[ProjectSnag]:
    return list(s.execute(sa.select(ProjectSnag).where(ProjectSnag.work_package_id == wp.id,
                                                       ProjectSnag.is_deleted == sa.false(),
                                                       ProjectSnag.status.in_(V.SNAG_OPEN))).scalars())  # fmt: skip


def derived_state(s: Session, wp: ProjectWorkPackage, checks=None) -> str:
    """NOT_STARTED, IN_PROGRESS, BLOCKED, COMPLETED, CORRECTION_REQUIRED or CANCELLED: what is true, never a pick."""
    if wp.status == "CANCELLED":
        return "CANCELLED"
    if wp.status == "COMPLETED":
        if checks is None:
            project = s.get(Project, wp.project_id)
            checks = quality.checks(s, project) if project is not None else []
        if quality.failed_heads_of(checks, wp.id) or open_snags(s, wp):
            return "CORRECTION_REQUIRED"
        return "COMPLETED"
    if gating_blockers(s, wp):
        return "BLOCKED"
    return wp.status


def _dates(start: date | None, finish: date | None) -> None:
    if start is not None and finish is not None and finish < start:
        raise ApiError(422, "VALIDATION_FAILED", "The planned finish cannot be before the planned start.",
                       errors=[field_error("planned_finish", "BEFORE_START", "On or after the planned start.")])  # fmt: skip


def _visible(label: str | None, visible: bool) -> None:
    if visible and not (label or "").strip():
        raise ApiError(422, "VALIDATION_FAILED", "Work shown to the customer needs a customer-safe label.",
                       errors=[field_error("customer_label", "REQUIRED", "Required when shown to the customer.")])  # fmt: skip


def _predecessor(s: Session, p: Project, wp: ProjectWorkPackage | None, stage: str, dep_id: str | None) -> str | None:
    """Finish-to-start: same or an earlier stage, never itself and never a cycle."""
    if dep_id is None:
        return None
    dep = service.child(s, ProjectWorkPackage, p, dep_id)
    d = lifecycle.get(p.lifecycle_version)
    if d.sequence(dep.stage_code) > d.sequence(stage):
        raise ApiError(422, "VALIDATION_FAILED", "Work can only follow work of the same or an earlier stage.",
                       errors=[field_error("depends_on_id", "LATER_STAGE", "Same or an earlier stage.")])  # fmt: skip
    seen = {wp.id} if wp is not None else set()
    cur: ProjectWorkPackage | None = dep
    while cur is not None:
        if cur.id in seen:
            raise ApiError(422, "VALIDATION_FAILED", "Work cannot depend on itself.",
                           errors=[field_error("depends_on_id", "CYCLE", "Dependency cycle.")])  # fmt: skip
        seen.add(cur.id)
        cur = s.get(ProjectWorkPackage, cur.depends_on_id) if cur.depends_on_id else None
    return dep.id


def _owner(s: Session, p: Project, user_id: str | None) -> str | None:
    if user_id is None:
        return None
    return service.eligible_user(s, p, user_id, "project.manage_work", "owner_user_id").id


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def add(s: Session, ctx, p: Project, body) -> ProjectWorkPackage:
    access.for_write(s, ctx, p, "project.manage_work", precondition=False)
    if lifecycle.get(p.lifecycle_version).stage(body.stage_code).terminal:
        raise ApiError(422, "VALIDATION_FAILED", "Handed over is not a stage that work is done in.",
                       errors=[field_error("stage_code", "TERMINAL_STAGE", "A stage before the handover.")])  # fmt: skip
    service.stage_open(p, body.stage_code)
    _dates(body.planned_start, body.planned_finish)
    _visible(body.customer_label, body.customer_visible)
    n = s.execute(sa.select(sa.func.max(ProjectWorkPackage.package_no))
                  .where(ProjectWorkPackage.project_id == p.id)).scalar() or 0  # fmt: skip
    wp = ProjectWorkPackage(project_id=p.id, lead_id=p.lead_id, package_no=n + 1, stage_code=body.stage_code,
                            space_id=service.space(s, p, body.space_id), title=body.title,
                            description=body.description, customer_label=body.customer_label,
                            customer_visible=body.customer_visible, owner_user_id=_owner(s, p, body.owner_user_id),
                            status="NOT_STARTED", planned_start=body.planned_start, planned_finish=body.planned_finish,
                            plan_revision=0)  # fmt: skip
    wp.depends_on_id = _predecessor(s, p, None, body.stage_code, body.depends_on_id)
    s.add(wp)
    s.flush()
    events.record(s, p, "WORK_PACKAGE_ADDED", stage=wp.stage_code, to=wp.status, work_package_id=wp.id,
                  package_no=wp.package_no, planned_start=_iso(wp.planned_start),
                  planned_finish=_iso(wp.planned_finish), owner=wp.owner_user_id)  # fmt: skip
    service.done(p, s)
    return wp


def update(s: Session, ctx, p: Project, wp: ProjectWorkPackage, body, if_match: int | None) -> ProjectWorkPackage:
    access.for_write(s, ctx, p, "project.manage_work", wp, if_match=if_match, match=wp)
    service.stage_open(p, wp.stage_code)
    if wp.status == "CANCELLED":
        raise ApiError(409, "INVALID_STATE", f"WP-{wp.package_no} is cancelled.")
    given = body.provided()
    before = (wp.planned_start, wp.planned_finish)
    start = body.planned_start if "planned_start" in given else wp.planned_start
    finish = body.planned_finish if "planned_finish" in given else wp.planned_finish
    _dates(start, finish)
    replanned = any(old is not None and new != old for old, new in zip(before, (start, finish), strict=True))
    if replanned:
        if wp.status == "COMPLETED":
            raise ApiError(409, "INVALID_STATE", "Completed work is not replanned.")
        why = service.reason(body.reason, "the plan changes")
    if "customer_label" in given:
        wp.customer_label = body.customer_label
    if "customer_visible" in given and body.customer_visible is not None:
        wp.customer_visible = body.customer_visible
    _visible(wp.customer_label, wp.customer_visible)
    for f in ("title", "description"):
        if f in given:
            if f == "title" and not body.title:
                raise ApiError(422, "VALIDATION_FAILED", "Work needs a title.",
                               errors=[field_error("title", "REQUIRED", "Required.")])  # fmt: skip
            setattr(wp, f, getattr(body, f))
    if "space_id" in given:
        wp.space_id = service.space(s, p, body.space_id)
    if "owner_user_id" in given:
        wp.owner_user_id = _owner(s, p, body.owner_user_id)
    if "depends_on_id" in given:
        wp.depends_on_id = _predecessor(s, p, wp, wp.stage_code, body.depends_on_id)
    wp.planned_start, wp.planned_finish = start, finish
    if replanned:
        wp.plan_revision += 1
        events.record(s, p, "WORK_PACKAGE_REPLANNED", stage=wp.stage_code, frm=wp.status, to=wp.status,
                      work_package_id=wp.id, revision=wp.plan_revision, previous_start=_iso(before[0]),
                      previous_finish=_iso(before[1]), planned_start=_iso(start), planned_finish=_iso(finish))  # fmt: skip
        wp.replan_reason = why
    events.record(s, p, "WORK_PACKAGE_CHANGED", stage=wp.stage_code, frm=wp.status, to=wp.status,
                  work_package_id=wp.id, fields=sorted(given - {"reason"}))  # fmt: skip
    service.done(p, s)
    return wp


def _can_progress(s: Session, p: Project, wp: ProjectWorkPackage) -> None:
    if wp.stage_code != p.stage_code:
        d = lifecycle.get(p.lifecycle_version)
        raise ApiError(409, "STAGE_NOT_CURRENT", f"WP-{wp.package_no} is work of {d.stage(wp.stage_code).label.lower()}"
                       f"; it is done while the project is in that stage.", extra={"stage": wp.stage_code})  # fmt: skip
    if wp.depends_on_id:
        dep = s.get(ProjectWorkPackage, wp.depends_on_id)
        if dep is not None and dep.status not in V.WORK_PACKAGE_CLOSED:
            raise ApiError(409, "DEPENDENCY_OPEN", f"WP-{dep.package_no}, which it follows, is not complete.",
                           extra={"work_package_id": dep.id})  # fmt: skip
    blocked = gating_blockers(s, wp)
    if blocked:
        raise ApiError(409, "WORK_PACKAGE_BLOCKED", "A gating blocker on this work is still open.",
                       extra={"blocker_id": blocked[0].id})  # fmt: skip


def _not_future(s: Session, value: date, field: str) -> None:
    if value > db.tx_time(s).date():
        raise ApiError(422, "VALIDATION_FAILED", "That date has not happened yet.",
                       errors=[field_error(field, "FUTURE_DATE", "Not after today.")])  # fmt: skip


def start(s: Session, ctx, p: Project, wp: ProjectWorkPackage, body, if_match: int | None) -> ProjectWorkPackage:
    access.for_write(s, ctx, p, "project.manage_work", wp, if_match=if_match, match=wp)
    if wp.status != "NOT_STARTED":
        raise ApiError(409, "INVALID_STATE", f"WP-{wp.package_no} is {wp.status.lower().replace('_', ' ')}.",
                       extra={"status": wp.status})  # fmt: skip
    _can_progress(s, p, wp)
    _not_future(s, body.actual_start, "actual_start")
    wp.status, wp.actual_start, wp.started_by = "IN_PROGRESS", body.actual_start, ctx.user.id
    events.record(s, p, "WORK_PACKAGE_STARTED", stage=wp.stage_code, frm="NOT_STARTED", to="IN_PROGRESS",
                  work_package_id=wp.id, actual_start=_iso(wp.actual_start))  # fmt: skip
    service.done(p, s)
    return wp


def complete(s: Session, ctx, p: Project, wp: ProjectWorkPackage, body, if_match: int | None) -> ProjectWorkPackage:
    access.for_write(s, ctx, p, "project.manage_work", wp, if_match=if_match, match=wp)
    if wp.status != "IN_PROGRESS":
        raise ApiError(409, "INVALID_STATE", f"WP-{wp.package_no} is {wp.status.lower().replace('_', ' ')}; work is "
                       "started before it is completed.", extra={"status": wp.status})  # fmt: skip
    _can_progress(s, p, wp)
    _not_future(s, body.actual_finish, "actual_finish")
    if wp.actual_start is not None and body.actual_finish < wp.actual_start:
        raise ApiError(422, "VALIDATION_FAILED", "Work cannot finish before it started.",
                       errors=[field_error("actual_finish", "BEFORE_START", "On or after the actual start.")])  # fmt: skip
    wp.evidence_attachment_id = service.evidence(s, p, body.evidence_attachment_id)
    wp.evidence_reference = body.evidence_reference
    wp.status, wp.actual_finish, wp.completed_by = "COMPLETED", body.actual_finish, ctx.user.id
    wp.completion_note = body.note
    events.record(s, p, "WORK_PACKAGE_COMPLETED", stage=wp.stage_code, frm="IN_PROGRESS", to="COMPLETED",
                  work_package_id=wp.id, actual_finish=_iso(wp.actual_finish),
                  evidence_attachment_id=wp.evidence_attachment_id)  # fmt: skip
    service.done(p, s)
    return wp


def reopen(
    s: Session, ctx, p: Project, wp: ProjectWorkPackage, reason: str, if_match: int | None
) -> ProjectWorkPackage:
    access.for_write(s, ctx, p, "project.manage_work", wp, if_match=if_match, match=wp)
    service.stage_open(p, wp.stage_code)
    if wp.status != "COMPLETED":
        raise ApiError(409, "INVALID_STATE", f"WP-{wp.package_no} is not completed.")
    previous = wp.actual_finish
    wp.reopen_reason = service.reason(reason, "completed work is reopened")
    wp.status, wp.actual_finish, wp.completed_by = "IN_PROGRESS", None, None
    events.record(s, p, "WORK_PACKAGE_REOPENED", stage=wp.stage_code, frm="COMPLETED", to="IN_PROGRESS",
                  work_package_id=wp.id, previous_finish=_iso(previous))  # fmt: skip
    service.done(p, s)
    return wp


def cancel(
    s: Session, ctx, p: Project, wp: ProjectWorkPackage, reason: str, if_match: int | None
) -> ProjectWorkPackage:
    access.for_write(s, ctx, p, "project.manage_work", wp, if_match=if_match, match=wp)
    service.stage_open(p, wp.stage_code)
    if wp.status in V.WORK_PACKAGE_CLOSED:
        raise ApiError(409, "INVALID_STATE", f"WP-{wp.package_no} is {wp.status.lower()}.")
    frm = wp.status
    wp.cancel_reason = service.reason(reason, "the work is cancelled")
    wp.status = "CANCELLED"
    events.record(s, p, "WORK_PACKAGE_CANCELLED", stage=wp.stage_code, frm=frm, to="CANCELLED",
                  work_package_id=wp.id)  # fmt: skip
    service.done(p, s)
    return wp


def gate(s: Session, p: Project, upto_stage: str) -> list[dict]:
    """WORK_COMPLETE (structural, review D4): every package of ``upto_stage`` and the stages before it is closed, and no
    completed one has a quality-check chain ending in FAIL. Open snags are the snag gate's."""
    d = lifecycle.get(p.lifecycle_version)
    seq = d.sequence(upto_stage)
    checks = quality.checks(s, p)
    out = []
    for wp in rows(s, p):
        if d.sequence(wp.stage_code) > seq:
            continue
        if wp.status not in V.WORK_PACKAGE_CLOSED:
            out.append({"gate": "WORK_COMPLETE", "code": "WORK_PACKAGE_OPEN", "message": f"WP-{wp.package_no} "
                        f"({d.stage(wp.stage_code).label.lower()}) is {wp.status.lower().replace('_', ' ')}.",
                        "responsible_party": "VEDA", "entity": {"type": "work_package", "id": wp.id}})  # fmt: skip
        elif wp.status == "COMPLETED" and quality.failed_heads_of(checks, wp.id):
            out.append({"gate": "WORK_COMPLETE", "code": "WORK_PACKAGE_QC_FAILED", "message": f"WP-{wp.package_no}"
                        " failed its quality check; correct it and recheck.", "responsible_party": "VEDA",
                        "entity": {"type": "work_package", "id": wp.id}})  # fmt: skip
    return out
