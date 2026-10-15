"""Project lifecycle commands. Each is an explicit command with its own capability, checked in the project's scope;
each takes the project lock and re-reads before deciding (``access.for_write``), and each appends to the timeline.

Stage progression is never "pick another status": ``request_transition`` asks for the next stage, the gates decide
(``gates.evaluate``), and the request is recorded whatever the outcome (REFUSED with its exact blockers, AWAITING an
independent approval, or COMPLETED). An approval re-evaluates every gate on committed state, so a checklist reopened,
a blocker raised, a variation issued or a snag found after the request still stops the move.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.kernel.errors import ApiError, field_error, not_found
from veda.kernel.jcs import canonical_bytes
from veda.modules.attachments.models import Attachment
from veda.modules.mtq.models import PropertySpace
from veda.platform.identity.models import User
from veda.platform.rbac.resolver import load_grants

from . import access, baseline, events, gates, lifecycle, policy
from . import vocab as V
from .models import (
    Project,
    ProjectBlocker,
    ProjectChecklistItem,
    ProjectMember,
    ProjectMilestone,
    ProjectQcCheck,
    ProjectSiteReadiness,
    ProjectSnag,
    ProjectStage,
    ProjectTransition,
)
from .permissions import RESPONSIBILITY_CAPABILITY


# --- helpers -----------------------------------------------------------------------------------------------------------
def child[T](s: Session, model: type[T], p: Project, row_id: str) -> T:
    row = s.get(model, row_id)
    if row is None or row.project_id != p.id or row.is_deleted:  # type: ignore[attr-defined]  # project rows
        raise not_found()
    return row


def _reason(text: str | None, what: str, field: str = "reason") -> str:
    value = (text or "").strip()
    if len(value) < 5:
        raise ApiError(422, "VALIDATION_FAILED", f"Say why {what} (at least 5 characters).",
                       errors=[field_error(field, "REASON_REQUIRED", "At least 5 characters.")])  # fmt: skip
    return value


def evidence(s: Session, p: Project, attachment_id: str | None, field: str = "evidence_attachment_id") -> str | None:
    """PLB-39: an existing attachment of this project's customer record, scanned clean and available."""
    if attachment_id is None:
        return None
    from veda.modules.attachments import service as att

    a = s.get(Attachment, attachment_id)
    if a is None or a.lead_id != p.lead_id or not att.is_available(a):
        raise ApiError(422, "EVIDENCE_NOT_AVAILABLE", "Evidence must be a scanned, available attachment of this "
                       "project's property.", errors=[field_error(field, "NOT_AVAILABLE", "Not an available "
                                                                  "attachment of this project.")])  # fmt: skip
    return a.id


def _space(s: Session, p: Project, space_id: str | None) -> str | None:
    if space_id is None:
        return None
    sp = s.get(PropertySpace, space_id)
    if sp is None or sp.property_id != p.property_id or sp.is_deleted:
        raise ApiError(422, "VALIDATION_FAILED", "The space is not part of this project's property.",
                       errors=[field_error("space_id", "UNKNOWN_SPACE", "Not a space of this property.")])  # fmt: skip
    return sp.id


def eligible_user(s: Session, p: Project, user_id: str, code: str, field: str) -> User:
    """An active person who holds ``code`` for this project (ALL, or OWN while a team member)."""
    u = s.get(User, user_id)
    scope = load_grants(s, user_id).granted.get(code) if u is not None else None
    if u is None or u.status != "ACTIVE" or u.user_type != "HUMAN" or scope is None or (
            scope == "OWN" and not access.is_member(s, p.id, user_id)):  # fmt: skip
        raise ApiError(422, "VALIDATION_FAILED", f"That person cannot act on this project (needs {code}).",
                       errors=[field_error(field, "NOT_ELIGIBLE", f"Needs {code} on this project.")])  # fmt: skip
    return u


def owner_controlled(s: Session, ctx, p: Project, code: str, capability: str | None, what: str) -> None:
    """An action the owner governs: refused while the decision ``code`` is unrecorded (or names no capability), then
    allowed exactly to the capability the decision names, in this project's scope. No persona is assumed."""
    if capability is None:
        r = policy.required(code)
        raise ApiError(409, "OWNER_DECISION_REQUIRED", f"{r['message']} Until it is, {what} is refused.",
                       extra={"decision": code})  # fmt: skip
    access.require(s, ctx, p, capability)


def _stage_open(p: Project, stage_code: str) -> None:
    d = lifecycle.get(p.lifecycle_version)
    if d.sequence(stage_code) < d.sequence(p.stage_code):
        raise ApiError(409, "STAGE_COMPLETED", f"{d.stage(stage_code).label} is completed; its record is closed.")


def _done(p: Project, s: Session) -> None:
    access.touch(s, p)
    s.flush()


# --- team (PLB-08, PLB-09) ---------------------------------------------------------------------------------------------
def members(s: Session, p: Project, *, active: bool | None = True) -> list[ProjectMember]:
    q = sa.select(ProjectMember).where(ProjectMember.project_id == p.id)
    if active is not None:
        q = q.where(ProjectMember.is_active == sa.true() if active else ProjectMember.is_active == sa.false())
    return list(s.execute(q.order_by(ProjectMember.created_on)).scalars())


def assign(s: Session, ctx, p: Project, body, if_match: int | None) -> ProjectMember:
    access.for_write(s, ctx, p, "project.assign_team", if_match=if_match)
    resp = body.responsibility
    u = s.get(User, body.user_id)
    if u is None or u.status != "ACTIVE" or u.user_type != "HUMAN":
        raise ApiError(422, "VALIDATION_FAILED", "Only an active person can join a project team.",
                       errors=[field_error("user_id", "NOT_ELIGIBLE", "Not an active person.")])  # fmt: skip
    cap = RESPONSIBILITY_CAPABILITY[resp]
    grants = load_grants(s, u.id).granted
    if grants.get("project.view") is None or grants.get(cap) is None:
        raise ApiError(422, "VALIDATION_FAILED", f"A {resp.lower()} owner must hold {cap}.",
                       errors=[field_error("user_id", "NOT_ELIGIBLE", f"Needs {cap}.")])  # fmt: skip
    current = members(s, p)
    if any(m.user_id == u.id and m.responsibility == resp for m in current):
        raise ApiError(409, "ALREADY_ASSIGNED", f"That person already holds {resp.lower()} on this project.")
    replaced = next((m for m in current if resp != "MEMBER" and m.responsibility == resp), None)
    now = db.tx_time(s)
    if replaced is not None:
        why = _reason(body.reason, f"the {resp.lower()} owner changes")
        replaced.is_active, replaced.removed_on, replaced.removed_by = False, now, ctx.user.id
        replaced.removal_reason = why
        s.flush()  # one active owner per responsibility (ux_project_member__owner)
        events.record(s, p, "MEMBER_REMOVED", stage=p.stage_code, member_id=replaced.id, user_id=replaced.user_id,
                      responsibility=resp, replaced=True)  # fmt: skip
    m = ProjectMember(project_id=p.id, lead_id=p.lead_id, user_id=u.id, responsibility=resp, is_active=True)
    s.add(m)
    s.flush()
    events.record(s, p, "OWNER_ASSIGNED" if resp != "MEMBER" else "MEMBER_ASSIGNED", stage=p.stage_code,
                  member_id=m.id, user_id=u.id, responsibility=resp,
                  previous_user_id=replaced.user_id if replaced else None)  # fmt: skip
    _done(p, s)
    return m


def remove(s: Session, ctx, p: Project, m: ProjectMember, reason: str, if_match: int | None) -> ProjectMember:
    access.for_write(s, ctx, p, "project.assign_team", m, if_match=if_match, match=m)
    if not m.is_active:
        raise ApiError(409, "INVALID_STATE", "That assignment has already ended.")
    m.is_active, m.removed_on, m.removed_by = False, db.tx_time(s), ctx.user.id
    m.removal_reason = _reason(reason, "the assignment ends")
    events.record(s, p, "MEMBER_REMOVED", stage=p.stage_code, member_id=m.id, user_id=m.user_id,
                  responsibility=m.responsibility)  # fmt: skip
    _done(p, s)
    return m


# --- transitions (PLB-06, PLB-07, PLB-34) ------------------------------------------------------------------------------
def _sealed(evaluation: dict[str, Any]) -> tuple[dict[str, Any], str]:
    return evaluation, hashlib.sha256(canonical_bytes(evaluation)).hexdigest()


def _transition_row(s: Session, p: Project, kind: str, ev: dict[str, Any], outcome: str, reason: str | None,
                    handover: dict[str, Any] | None = None, decided_by: str | None = None) -> ProjectTransition:  # fmt: skip
    evaluation, sha = _sealed(ev)
    t = ProjectTransition(project_id=p.id, lead_id=p.lead_id, kind=kind, from_stage=p.stage_code,
                          to_stage=ev["to"], lifecycle_version=p.lifecycle_version, outcome=outcome,
                          evaluation=evaluation, evaluation_sha256=sha,
                          independent_approval=bool(ev["independent_approval"]), reason=reason,
                          decided_by=decided_by, decided_on=db.tx_time(s) if decided_by else None,
                          **(handover or {}))  # fmt: skip
    s.add(t)
    s.flush()
    return t


def _decide(s: Session, ctx, p: Project, kind: str, to: str | None, reason: str | None,
            handover: dict[str, Any] | None) -> ProjectTransition:  # fmt: skip
    if to is not None:
        lifecycle.get(p.lifecycle_version).stage(to)  # an unknown stage code is a 422, not a refusal
    ev = gates.evaluate(s, p, to, command=kind, handover=handover)
    if ev["to"] is None:
        raise ApiError(409, "INVALID_STATE", "This project has no next stage.")
    if ev["blockers"]:
        t = _transition_row(s, p, kind, ev, "REFUSED", reason, handover)
        events.record(s, p, "TRANSITION_REFUSED", stage=p.stage_code, frm=p.stage_code, to=ev["to"],
                      transition_id=t.id, blockers=[b["code"] for b in ev["blockers"]][:40],
                      evaluation_sha256=t.evaluation_sha256)  # fmt: skip
        s.flush()
        return t
    if ev["independent_approval"]:
        t = _transition_row(s, p, kind, ev, "AWAITING_APPROVAL", reason, handover)
        events.record(s, p, "TRANSITION_AWAITING_APPROVAL", stage=p.stage_code, frm=p.stage_code, to=ev["to"],
                      transition_id=t.id, evaluation_sha256=t.evaluation_sha256)  # fmt: skip
        events.notify(s, p, events.AWAITING_APPROVAL, transition_id=t.id, requested_by=ctx.user.id)
        _done(p, s)
        return t
    t = _transition_row(s, p, kind, ev, "COMPLETED", reason, handover, decided_by=ctx.user.id)
    _apply(s, ctx, p, t)
    return t


def request_transition(s: Session, ctx, p: Project, to: str, reason: str | None,
                       if_match: int | None) -> ProjectTransition:  # fmt: skip
    access.for_write(s, ctx, p, "project.manage_stage", if_match=if_match)
    return _decide(s, ctx, p, "STAGE", to, reason, None)


def complete_handover(s: Session, ctx, p: Project, body, if_match: int | None) -> ProjectTransition:
    """PLB-29: the handover, with the operational evidence the policy requires, through the same gates."""
    access.for_write(s, ctx, p, "project.complete_handover", if_match=if_match)
    if body.handover_on > db.tx_time(s).date():
        raise ApiError(422, "VALIDATION_FAILED", "A handover date cannot be in the future.",
                       errors=[field_error("handover_on", "FUTURE_DATE", "Not after today.")])  # fmt: skip
    handover = {"handover_on": body.handover_on, "acknowledgement_reference": body.acknowledgement_reference,
                "evidence_attachment_id": evidence(s, p, body.evidence_attachment_id),
                "observations": body.observations}  # fmt: skip
    return _decide(s, ctx, p, "HANDOVER", "HANDED_OVER", body.reason, handover)


def _pending(s: Session, ctx, p: Project, t: ProjectTransition, permission: str, if_match: int | None) -> None:
    access.for_write(s, ctx, p, permission, t, if_match=if_match, match=t)
    if t.outcome != "AWAITING_APPROVAL":
        raise ApiError(409, "INVALID_STATE", f"This transition is {t.outcome.lower().replace('_', ' ')}.",
                       extra={"outcome": t.outcome})  # fmt: skip


def approve(s: Session, ctx, p: Project, t: ProjectTransition, note: str | None,
            if_match: int | None) -> ProjectTransition:  # fmt: skip
    _pending(s, ctx, p, t, "project.approve_transition", if_match)
    if ctx.user.id == t.created_by:
        raise ApiError(409, "FOUR_EYES_REQUIRED", "You requested this transition; someone else approves it.")
    handover = {"acknowledgement_reference": t.acknowledgement_reference,
                "evidence_attachment_id": t.evidence_attachment_id} if t.kind == "HANDOVER" else None  # fmt: skip
    if t.from_stage != p.stage_code:
        raise ApiError(409, "INVALID_STATE", "The project moved on since this transition was requested.")
    if handover is not None and handover["evidence_attachment_id"]:
        evidence(s, p, handover["evidence_attachment_id"])
    ev = gates.evaluate(s, p, t.to_stage, command=t.kind, handover=handover, approving=t)
    if ev["blockers"]:
        raise ApiError(409, "GATES_NOT_SATISFIED", f"{len(ev['blockers'])} gate blocker(s) appeared since the "
                       "request; resolve them, or reject or withdraw the request.",
                       extra={"blockers": ev["blockers"], "gates": ev["gates"]})  # fmt: skip
    t.outcome, t.decided_by, t.decided_on = "COMPLETED", ctx.user.id, db.tx_time(s)
    t.decision_reason = (note or "").strip()[:1000] or None
    t.evaluation, t.evaluation_sha256 = _sealed({**ev, "approved_evaluation": True})
    _apply(s, ctx, p, t)
    return t


def reject(s: Session, ctx, p: Project, t: ProjectTransition, reason: str, if_match: int | None) -> ProjectTransition:
    _pending(s, ctx, p, t, "project.approve_transition", if_match)
    if ctx.user.id == t.created_by:
        raise ApiError(409, "FOUR_EYES_REQUIRED", "You requested this transition; withdraw it instead.")
    t.outcome, t.decided_by, t.decided_on = "REJECTED", ctx.user.id, db.tx_time(s)
    t.decision_reason = _reason(reason, "the transition is rejected")
    events.record(s, p, "TRANSITION_REJECTED", stage=p.stage_code, frm=t.from_stage, to=t.to_stage,
                  transition_id=t.id)  # fmt: skip
    _done(p, s)
    return t


def withdraw(s: Session, ctx, p: Project, t: ProjectTransition, reason: str, if_match: int | None) -> ProjectTransition:
    permission = "project.complete_handover" if t.kind == "HANDOVER" else "project.manage_stage"
    _pending(s, ctx, p, t, permission, if_match)
    t.outcome, t.decided_by, t.decided_on = "WITHDRAWN", ctx.user.id, db.tx_time(s)
    t.decision_reason = _reason(reason, "the transition is withdrawn")
    events.record(s, p, "TRANSITION_WITHDRAWN", stage=p.stage_code, frm=t.from_stage, to=t.to_stage,
                  transition_id=t.id)  # fmt: skip
    _done(p, s)
    return t


def _stage_row(s: Session, p: Project, code: str) -> ProjectStage:
    row = s.execute(sa.select(ProjectStage).where(ProjectStage.project_id == p.id,
                                                  ProjectStage.stage_code == code)).scalar_one()  # fmt: skip
    return row


def _apply(s: Session, ctx, p: Project, t: ProjectTransition) -> None:
    """Move the project: the current stage COMPLETED, the next one ACTIVE (or, for the handover, the project closed)."""
    now = db.tx_time(s)
    frm, to = _stage_row(s, p, t.from_stage), _stage_row(s, p, t.to_stage)
    frm.status, frm.completed_on, frm.completed_by = "COMPLETED", now, ctx.user.id
    events.record(s, p, "STAGE_COMPLETED", stage=frm.stage_code, frm="ACTIVE", to="COMPLETED", transition_id=t.id)
    s.flush()  # one ACTIVE stage per project (ux_project_stage__one_active)
    to.status, to.entered_on, to.entered_by = "ACTIVE", now, ctx.user.id
    p.stage_code, p.stage_entered_on = t.to_stage, now
    events.record(s, p, "STAGE_ENTERED", stage=to.stage_code, frm=t.from_stage, to=t.to_stage, transition_id=t.id,
                  approved_by=t.decided_by if t.independent_approval else None,
                  evaluation_sha256=t.evaluation_sha256)  # fmt: skip
    if t.to_stage == "READY_FOR_HANDOVER":
        events.record(s, p, "HANDOVER_READY", stage=t.to_stage, transition_id=t.id)
        events.notify(s, p, events.READY_FOR_HANDOVER, transition_id=t.id)
    if t.kind == "HANDOVER":
        to.status, to.completed_on, to.completed_by = "COMPLETED", now, ctx.user.id
        p.status, p.handed_over_on, p.handed_over_by = "HANDED_OVER", now, ctx.user.id
        current = baseline.current(s, p)
        events.record(s, p, "HANDED_OVER", stage=t.to_stage, transition_id=t.id, baseline_id=current.id,
                      baseline_seq=current.sequence_no, baseline_sha256=current.baseline_sha256,
                      handover_on=t.handover_on.isoformat() if t.handover_on else None)  # fmt: skip
        events.notify(s, p, events.HANDED_OVER, transition_id=t.id, baseline_id=current.id, lead_id=p.lead_id,
                      property_id=p.property_id, source_quotation_id=p.source_quotation_id)  # fmt: skip
    else:
        events.notify(s, p, events.STAGE_ENTERED, transition_id=t.id)
    _done(p, s)


# --- checklist (PLB-15) ------------------------------------------------------------------------------------------------
def complete_item(s: Session, ctx, p: Project, item: ProjectChecklistItem, body,
                  if_match: int | None) -> ProjectChecklistItem:  # fmt: skip
    access.for_write(s, ctx, p, "project.complete_checklist", item, if_match=if_match, match=item)
    _stage_open(p, item.stage_code)
    if item.state != "OPEN":
        raise ApiError(409, "INVALID_STATE", "This item is already completed; reopen it first.")
    ev_id = evidence(s, p, body.evidence_attachment_id)
    if body.state == "NOT_APPLICABLE":
        required = item.item_code not in gates.optional_items(p, item.stage_code)
        if required:
            access.require(s, ctx, p, "project.checklist.not_applicable")
        item.not_applicable_reason = _reason(body.not_applicable_reason, "the item does not apply",
                                             "not_applicable_reason")  # fmt: skip
    item.state, item.completed_by, item.completed_on = body.state, ctx.user.id, db.tx_time(s)
    item.note, item.evidence_attachment_id, item.evidence_reference = body.note, ev_id, body.evidence_reference
    code = "CHECKLIST_ITEM_COMPLETED" if body.state == "DONE" else "CHECKLIST_ITEM_NOT_APPLICABLE"
    events.record(s, p, code, stage=item.stage_code, frm="OPEN", to=item.state, item_id=item.id,
                  item_code=item.item_code, evidence_attachment_id=ev_id)  # fmt: skip
    _done(p, s)
    return item


def reopen_item(s: Session, ctx, p: Project, item: ProjectChecklistItem, reason: str,
                if_match: int | None) -> ProjectChecklistItem:  # fmt: skip
    access.for_write(s, ctx, p, "project.complete_checklist", item, if_match=if_match, match=item)
    _stage_open(p, item.stage_code)
    if item.state == "OPEN":
        raise ApiError(409, "INVALID_STATE", "This item is open.")
    frm = item.state
    item.reopen_reason = _reason(reason, "the item is reopened")
    item.state, item.completed_by, item.completed_on, item.not_applicable_reason = "OPEN", None, None, None
    events.record(s, p, "CHECKLIST_ITEM_REOPENED", stage=item.stage_code, frm=frm, to="OPEN", item_id=item.id,
                  item_code=item.item_code)  # fmt: skip
    _done(p, s)
    return item


# --- milestones (PLB-13, PLB-14) ---------------------------------------------------------------------------------------
def _dependency(s: Session, p: Project, m: ProjectMilestone | None, depends_on: str | None) -> str | None:
    if depends_on is None:
        return None
    dep = child(s, ProjectMilestone, p, depends_on)
    seen = {m.id} if m is not None else set()
    cur: ProjectMilestone | None = dep
    while cur is not None:  # no cycle
        if cur.id in seen:
            raise ApiError(422, "VALIDATION_FAILED", "A milestone cannot depend on itself.",
                           errors=[field_error("depends_on_milestone_id", "CYCLE", "Dependency cycle.")])  # fmt: skip
        seen.add(cur.id)
        cur = s.get(ProjectMilestone, cur.depends_on_milestone_id) if cur.depends_on_milestone_id else None
    return dep.id


def _promised_date(s: Session, ctx, p: Project) -> None:
    """PLB-13/M1: a customer-promised date is a customer commitment, governed by owner decision PLB-OD-13."""
    od = policy.decision("PLB-OD-13")
    owner_controlled(s, ctx, p, "PLB-OD-13", od.capability if od else None, "recording a customer-promised date")


def add_milestone(s: Session, ctx, p: Project, body) -> ProjectMilestone:
    access.for_write(s, ctx, p, "project.manage_milestone", precondition=False)
    lifecycle.get(p.lifecycle_version).stage(body.stage_code)
    _stage_open(p, body.stage_code)
    if body.customer_promised_date is not None:
        _promised_date(s, ctx, p)
    m = ProjectMilestone(project_id=p.id, lead_id=p.lead_id, milestone_code=body.milestone_code, label=body.label,
                         customer_label=body.customer_label, description=body.description,
                         stage_code=body.stage_code, status="PLANNED" if body.planned_date else "NOT_STARTED",
                         planned_date=body.planned_date, customer_promised_date=body.customer_promised_date,
                         owner_responsibility=body.owner_responsibility)  # fmt: skip
    m.depends_on_milestone_id = _dependency(s, p, None, body.depends_on_milestone_id)
    s.add(m)
    s.flush()
    events.record(s, p, "MILESTONE_ADDED", stage=body.stage_code, to=m.status, milestone_id=m.id,
                  milestone_code=m.milestone_code, planned_date=_iso(m.planned_date))  # fmt: skip
    _done(p, s)
    return m


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def update_milestone(s: Session, ctx, p: Project, m: ProjectMilestone, body,
                     if_match: int | None) -> ProjectMilestone:  # fmt: skip
    access.for_write(s, ctx, p, "project.manage_milestone", m, if_match=if_match, match=m)
    _stage_open(p, m.stage_code)  # S2: a completed stage's milestones are its record
    if m.status == "COMPLETED":
        raise ApiError(409, "INVALID_STATE", "A completed milestone is not changed.")
    given = body.provided()
    if "customer_promised_date" in given and body.customer_promised_date != m.customer_promised_date:
        _promised_date(s, ctx, p)  # recording, changing and clearing a promise are all the owner's to govern
    frm = m.status
    for f in ("label", "customer_label", "description", "planned_date", "customer_promised_date",
              "owner_responsibility"):  # fmt: skip
        if f in given:
            if f == "label" and not body.label:
                raise ApiError(422, "VALIDATION_FAILED", "A milestone needs a label.",
                               errors=[field_error("label", "REQUIRED", "Required.")])  # fmt: skip
            setattr(m, f, getattr(body, f))
    if "depends_on_milestone_id" in given:
        m.depends_on_milestone_id = _dependency(s, p, m, body.depends_on_milestone_id)
    if "status" in given and body.status is not None:
        if body.status in ("CANCELLED", "NOT_APPLICABLE"):
            m.status_reason = _reason(body.status_reason, "the milestone no longer applies", "status_reason")
        else:
            m.status_reason = None
        m.status = body.status
    events.record(s, p, "MILESTONE_CHANGED", stage=m.stage_code, frm=frm, to=m.status, milestone_id=m.id,
                  planned_date=_iso(m.planned_date), customer_promised_date=_iso(m.customer_promised_date),
                  fields=sorted(given))  # fmt: skip
    _done(p, s)
    return m


def complete_milestone(s: Session, ctx, p: Project, m: ProjectMilestone, body,
                       if_match: int | None) -> ProjectMilestone:  # fmt: skip
    """PLB-14: completion is explicit, with its actual date; never inferred from the calendar."""
    access.for_write(s, ctx, p, "project.manage_milestone", m, if_match=if_match, match=m)
    _stage_open(p, m.stage_code)
    if m.status in V.MILESTONE_CLOSED:
        raise ApiError(409, "INVALID_STATE", f"This milestone is {m.status.lower().replace('_', ' ')}.")
    if body.actual_date > db.tx_time(s).date():
        raise ApiError(422, "VALIDATION_FAILED", "A milestone is completed on a date that has passed.",
                       errors=[field_error("actual_date", "FUTURE_DATE", "Not after today.")])  # fmt: skip
    if m.depends_on_milestone_id:
        dep = s.get(ProjectMilestone, m.depends_on_milestone_id)
        if dep is not None and dep.status not in V.MILESTONE_CLOSED:
            raise ApiError(409, "DEPENDENCY_OPEN", f"Milestone {dep.label} it depends on is not complete.")
    gating = s.execute(sa.select(ProjectBlocker.id).where(ProjectBlocker.related_milestone_id == m.id,
                                                          ProjectBlocker.impact == "GATING",
                                                          ProjectBlocker.status.in_(V.BLOCKER_OPEN))).first()  # fmt: skip
    if gating is not None:
        raise ApiError(409, "MILESTONE_BLOCKED", "A gating blocker on this milestone is still open.",
                       extra={"blocker_id": gating[0]})  # fmt: skip
    frm = m.status
    m.status, m.actual_date = "COMPLETED", body.actual_date
    m.evidence_attachment_id = evidence(s, p, body.evidence_attachment_id)
    m.evidence_reference = body.evidence_reference
    events.record(s, p, "MILESTONE_CHANGED", stage=m.stage_code, frm=frm, to="COMPLETED", milestone_id=m.id,
                  actual_date=_iso(m.actual_date), evidence_attachment_id=m.evidence_attachment_id)  # fmt: skip
    _done(p, s)
    return m


# --- blockers (PLB-18 … PLB-20, PLB-41) --------------------------------------------------------------------------------
def raise_blocker(s: Session, ctx, p: Project, body, source: str = "STAFF") -> ProjectBlocker:
    access.for_write(s, ctx, p, "project.raise_blocker", precondition=False)
    if body.impact == "GATING" and body.blocks_stage_code is None:
        raise ApiError(422, "VALIDATION_FAILED", "Say which stage a gating blocker stops.",
                       errors=[field_error("blocks_stage_code", "REQUIRED", "Required for a gating blocker.")])  # fmt: skip
    if body.blocks_stage_code is not None:
        lifecycle.get(p.lifecycle_version).stage(body.blocks_stage_code)
    if body.responsible_party == "CUSTOMER" and not body.customer_action:
        raise ApiError(422, "VALIDATION_FAILED", "Say what the customer needs to do (customer-safe words).",
                       errors=[field_error("customer_action", "REQUIRED", "Required when the customer acts.")])  # fmt: skip
    if body.assigned_to:
        eligible_user(s, p, body.assigned_to, "project.view", "assigned_to")
    b = ProjectBlocker(project_id=p.id, lead_id=p.lead_id, category=body.category, source=source, impact=body.impact,
                       title=body.title, description=body.description, customer_action=body.customer_action,
                       responsible_party=body.responsible_party, assigned_to=body.assigned_to,
                       target_date=body.target_date, blocks_stage_code=body.blocks_stage_code, status="OPEN")  # fmt: skip
    if body.related_milestone_id:
        b.related_milestone_id = child(s, ProjectMilestone, p, body.related_milestone_id).id
    if body.related_checklist_item_id:
        b.related_checklist_item_id = child(s, ProjectChecklistItem, p, body.related_checklist_item_id).id
    if body.related_site_readiness_id:
        b.related_site_readiness_id = child(s, ProjectSiteReadiness, p, body.related_site_readiness_id).id
    if body.related_quotation_id:
        from veda.modules.mtq_commercial.models import Quotation

        q = s.get(Quotation, body.related_quotation_id)
        if q is None or q.quotation_number != p.quotation_number or q.variation_no == 0:
            raise ApiError(422, "VALIDATION_FAILED", "Only a variation of this project's quotation can be linked.",
                           errors=[field_error("related_quotation_id", "NOT_A_VARIATION", "Not a variation of "
                                               "this project.")])  # fmt: skip
        b.related_quotation_id = q.id
    s.add(b)
    s.flush()
    events.record(s, p, "BLOCKER_RAISED", stage=p.stage_code, to="OPEN", blocker_id=b.id, category=b.category,
                  impact=b.impact, responsible_party=b.responsible_party, blocks=b.blocks_stage_code,
                  assigned_to=b.assigned_to)  # fmt: skip
    if b.assigned_to:
        events.notify(s, p, events.BLOCKER_ASSIGNED, blocker_id=b.id, assigned_to=b.assigned_to)
    if b.responsible_party == "CUSTOMER":
        events.notify(s, p, events.CUSTOMER_ACTION_REQUIRED, blocker_id=b.id)
    _done(p, s)
    return b


def update_blocker(s: Session, ctx, p: Project, b: ProjectBlocker, body, if_match: int | None) -> ProjectBlocker:
    access.for_write(s, ctx, p, "project.resolve_blocker", b, if_match=if_match, match=b)
    if b.status not in V.BLOCKER_OPEN:
        raise ApiError(409, "INVALID_STATE", f"This blocker is {b.status.lower()}.")
    given = body.provided()
    frm = b.status
    before_assignee = b.assigned_to
    if "assigned_to" in given and body.assigned_to:
        eligible_user(s, p, body.assigned_to, "project.view", "assigned_to")
    for f in ("description", "customer_action", "responsible_party", "assigned_to", "target_date"):
        if f in given:
            setattr(b, f, getattr(body, f))
    if "status" in given and body.status is not None:
        b.status = body.status
    if b.responsible_party == "CUSTOMER" and not b.customer_action:
        raise ApiError(422, "VALIDATION_FAILED", "Say what the customer needs to do (customer-safe words).",
                       errors=[field_error("customer_action", "REQUIRED", "Required when the customer acts.")])  # fmt: skip
    events.record(s, p, "BLOCKER_UPDATED", stage=p.stage_code, frm=frm, to=b.status, blocker_id=b.id,
                  responsible_party=b.responsible_party, assigned_to=b.assigned_to, fields=sorted(given))  # fmt: skip
    if b.assigned_to and b.assigned_to != before_assignee:
        events.notify(s, p, events.BLOCKER_ASSIGNED, blocker_id=b.id, assigned_to=b.assigned_to)
    _done(p, s)
    return b


def close_blocker(s: Session, ctx, p: Project, b: ProjectBlocker, outcome: str, resolution: str,
                  if_match: int | None) -> ProjectBlocker:  # fmt: skip
    access.for_write(s, ctx, p, "project.resolve_blocker", b, if_match=if_match, match=b)
    if b.status not in V.BLOCKER_OPEN:
        raise ApiError(409, "INVALID_STATE", f"This blocker is {b.status.lower()}.")
    frm = b.status
    b.status, b.resolved_on, b.resolved_by = outcome, db.tx_time(s), ctx.user.id
    b.resolution = _reason(resolution, "the blocker is closed", "resolution")
    events.record(s, p, "BLOCKER_RESOLVED" if outcome == "RESOLVED" else "BLOCKER_CANCELLED", stage=p.stage_code,
                  frm=frm, to=outcome, blocker_id=b.id, impact=b.impact)  # fmt: skip
    _done(p, s)
    return b


# --- site readiness (PLB-16, PLB-17) -----------------------------------------------------------------------------------
def add_readiness(s: Session, ctx, p: Project, body) -> ProjectSiteReadiness:
    access.for_write(s, ctx, p, "project.manage_site_readiness", precondition=False)
    n = s.execute(sa.select(sa.func.count()).select_from(ProjectSiteReadiness).where(
        ProjectSiteReadiness.project_id == p.id, ProjectSiteReadiness.source == "STAFF")).scalar() or 0  # fmt: skip
    r = ProjectSiteReadiness(project_id=p.id, lead_id=p.lead_id, kind=body.kind, source="STAFF",
                             item_code=f"STAFF_{n + 1:03d}", category=body.category, label=body.label,
                             status="TO_BE_CONFIRMED", responsible_party="TO_BE_CONFIRMED")  # fmt: skip
    s.add(r)
    s.flush()
    events.record(s, p, "SITE_READINESS_ADDED", stage=p.stage_code, to=r.status, item_id=r.id, item_code=r.item_code,
                  category=r.category)  # fmt: skip
    _done(p, s)
    return r


ACTIONABLE = {"CUSTOMER_ACTION_REQUIRED": "CUSTOMER", "VEDA_ACTION_REQUIRED": "VEDA"}


def update_readiness(s: Session, ctx, p: Project, r: ProjectSiteReadiness, body,
                     if_match: int | None) -> ProjectSiteReadiness:  # fmt: skip
    access.for_write(s, ctx, p, "project.manage_site_readiness", r, if_match=if_match, match=r)
    given = body.provided()
    frm = r.status
    if "evidence_attachment_id" in given:
        r.evidence_attachment_id = evidence(s, p, body.evidence_attachment_id)
    for f in ("responsible_party", "action", "customer_action", "due_date", "note", "evidence_reference"):
        if f in given:
            setattr(r, f, getattr(body, f))
    if "status" in given and body.status is not None:
        r.status = body.status
        party = ACTIONABLE.get(r.status)
        if party is not None and "responsible_party" not in given:
            r.responsible_party = party
    party = ACTIONABLE.get(r.status)
    if party is not None:
        if r.responsible_party != party:
            raise ApiError(422, "VALIDATION_FAILED", f"{r.status.lower().replace('_', ' ')} is for {party.lower()}.",
                           errors=[field_error("responsible_party", "MISMATCH", f"Must be {party}.")])  # fmt: skip
        if not r.action:
            raise ApiError(422, "VALIDATION_FAILED", "Say what action is needed.",
                           errors=[field_error("action", "REQUIRED", "Required for an action.")])  # fmt: skip
        if party == "CUSTOMER" and not r.customer_action:
            raise ApiError(422, "VALIDATION_FAILED", "Say what the customer needs to do (customer-safe words).",
                           errors=[field_error("customer_action", "REQUIRED", "Required.")])  # fmt: skip
    if r.status in V.READINESS_SATISFIED:
        if r.resolved_on is None:
            r.resolved_on, r.resolved_by = db.tx_time(s), ctx.user.id
    else:
        r.resolved_on = r.resolved_by = None
    events.record(s, p, "SITE_READINESS_UPDATED", stage=p.stage_code, frm=frm, to=r.status, item_id=r.id,
                  item_code=r.item_code, responsible_party=r.responsible_party,
                  evidence_attachment_id=r.evidence_attachment_id)  # fmt: skip
    if r.status == "CUSTOMER_ACTION_REQUIRED" and frm != r.status:
        events.notify(s, p, events.CUSTOMER_ACTION_REQUIRED, site_readiness_id=r.id)
    _done(p, s)
    return r


# --- quality check (PLB-26) --------------------------------------------------------------------------------------------
def record_qc(s: Session, ctx, p: Project, body) -> ProjectQcCheck:
    access.for_write(s, ctx, p, "project.manage_qc", precondition=False)
    d = lifecycle.get(p.lifecycle_version)
    if d.sequence(p.stage_code) < d.sequence("QUALITY_CHECK"):
        raise ApiError(409, "INVALID_STATE", "Quality checks are recorded from the quality-check stage on.")
    if body.result == "FAIL" and not body.observation:
        raise ApiError(422, "VALIDATION_FAILED", "Describe what failed.",
                       errors=[field_error("observation", "REQUIRED", "Required for a failed check.")])  # fmt: skip
    override = body.result == "NOT_APPLICABLE" and body.category in gates.required_qc(p)
    if override:  # S3: never a silent bypass of handover readiness
        od = policy.decision("PLB-OD-08")
        owner_controlled(s, ctx, p, "PLB-OD-08", od.not_applicable_capability if od else None,
                         "marking a required quality-check category not applicable")  # fmt: skip
        _reason(body.observation, "a required category does not apply", "observation")
    recheck = None
    if body.recheck_of_id:
        recheck = child(s, ProjectQcCheck, p, body.recheck_of_id)
        if recheck.category != body.category:
            raise ApiError(422, "VALIDATION_FAILED", "A recheck is of the same category.",
                           errors=[field_error("recheck_of_id", "CATEGORY_MISMATCH", "Same category.")])  # fmt: skip
    c = ProjectQcCheck(project_id=p.id, lead_id=p.lead_id, category=body.category, result=body.result,
                       space_id=_space(s, p, body.space_id), observation=body.observation,
                       evidence_attachment_id=evidence(s, p, body.evidence_attachment_id),
                       evidence_reference=body.evidence_reference, recheck_of_id=recheck.id if recheck else None)  # fmt: skip
    s.add(c)
    s.flush()
    events.record(s, p, "QC_RECORDED", stage=p.stage_code, to=c.result, qc_check_id=c.id, category=c.category,
                  recheck_of_id=c.recheck_of_id, evidence_attachment_id=c.evidence_attachment_id,
                  required_not_applicable=override or None)  # fmt: skip
    _done(p, s)
    return c


# --- snags (PLB-27) ----------------------------------------------------------------------------------------------------
SNAG_FLOW = {
    "OPEN": ("IN_PROGRESS", "CLOSED"),
    "IN_PROGRESS": ("READY_FOR_RECHECK", "CLOSED"),
    "READY_FOR_RECHECK": ("IN_PROGRESS", "RESOLVED", "CLOSED"),
    "RESOLVED": ("CLOSED",),
    "CLOSED": (),
}


def raise_snag(s: Session, ctx, p: Project, body) -> ProjectSnag:
    access.for_write(s, ctx, p, "project.manage_snag", precondition=False)
    if body.owner_user_id:
        eligible_user(s, p, body.owner_user_id, "project.manage_snag", "owner_user_id")
    qc = child(s, ProjectQcCheck, p, body.qc_check_id) if body.qc_check_id else None
    n = s.execute(sa.select(sa.func.max(ProjectSnag.snag_no)).where(ProjectSnag.project_id == p.id)).scalar() or 0
    sn = ProjectSnag(project_id=p.id, lead_id=p.lead_id, snag_no=n + 1, space_id=_space(s, p, body.space_id),
                     item_reference=body.item_reference, category=body.category, customer_title=body.customer_title,
                     description=body.description, is_blocking=body.is_blocking, owner_user_id=body.owner_user_id,
                     responsible_party=body.responsible_party, status="OPEN", target_date=body.target_date,
                     qc_check_id=qc.id if qc else None,
                     evidence_attachment_id=evidence(s, p, body.evidence_attachment_id),
                     evidence_reference=body.evidence_reference)  # fmt: skip
    s.add(sn)
    s.flush()
    events.record(s, p, "SNAG_RAISED", stage=p.stage_code, to="OPEN", snag_id=sn.id, snag_no=sn.snag_no,
                  category=sn.category, blocking=sn.is_blocking, qc_check_id=sn.qc_check_id)  # fmt: skip
    _done(p, s)
    return sn


def update_snag(s: Session, ctx, p: Project, sn: ProjectSnag, body, if_match: int | None) -> ProjectSnag:
    access.for_write(s, ctx, p, "project.manage_snag", sn, if_match=if_match, match=sn)
    if sn.status in ("RESOLVED", "CLOSED"):
        raise ApiError(409, "INVALID_STATE", f"Snag {sn.snag_no} is {sn.status.lower()}.")
    given = body.provided()
    if "owner_user_id" in given and body.owner_user_id:
        eligible_user(s, p, body.owner_user_id, "project.manage_snag", "owner_user_id")
    if "evidence_attachment_id" in given:
        sn.evidence_attachment_id = evidence(s, p, body.evidence_attachment_id)
    for f in ("description", "owner_user_id", "responsible_party", "target_date", "evidence_reference"):
        if f in given:
            setattr(sn, f, getattr(body, f))
    events.record(s, p, "SNAG_UPDATED", stage=p.stage_code, frm=sn.status, to=sn.status, snag_id=sn.id,
                  snag_no=sn.snag_no, fields=sorted(given))  # fmt: skip
    _done(p, s)
    return sn


def _gating(blocking: bool) -> str:
    return "BLOCKING" if blocking else "NON_BLOCKING"


def reclassify_snag(s: Session, ctx, p: Project, sn: ProjectSnag, body, if_match: int | None) -> ProjectSnag:
    """M2: moving a snag between blocking and non-blocking changes handover-readiness gating. Its own command, governed
    by owner decision PLB-OD-06 (refused while unrecorded), with a reason and an immutable SNAG_RECLASSIFIED event
    (previous and new classification; the actor and time are the event's)."""
    access.for_write(s, ctx, p, "project.manage_snag", sn, if_match=if_match, match=sn)
    if sn.status in ("RESOLVED", "CLOSED"):
        raise ApiError(409, "INVALID_STATE", f"Snag {sn.snag_no} is {sn.status.lower()}.")
    if body.is_blocking == sn.is_blocking:
        raise ApiError(
            409, "NO_CHANGE", f"Snag {sn.snag_no} is already {_gating(sn.is_blocking).lower().replace('_', '-')}."
        )
    od = policy.decision("PLB-OD-06")
    owner_controlled(s, ctx, p, "PLB-OD-06", od.snag_reclassification_capability if od else None,
                     "changing whether a snag blocks the handover")  # fmt: skip
    frm, to = _gating(sn.is_blocking), _gating(body.is_blocking)
    sn.classification_reason = _reason(body.reason, "the classification changes")[:500]
    sn.is_blocking = body.is_blocking
    events.record(s, p, "SNAG_RECLASSIFIED", stage=p.stage_code, frm=frm, to=to, snag_id=sn.id, snag_no=sn.snag_no)
    _done(p, s)
    return sn


def snag_status(s: Session, ctx, p: Project, sn: ProjectSnag, body, if_match: int | None) -> ProjectSnag:
    access.for_write(s, ctx, p, "project.manage_snag", sn, if_match=if_match, match=sn)
    frm, to = sn.status, body.status
    if to not in SNAG_FLOW[frm]:
        raise ApiError(409, "INVALID_STATE", f"Snag {sn.snag_no} cannot go from {frm.lower().replace('_', ' ')} to "
                       f"{to.lower().replace('_', ' ')}.", extra={"status": frm, "allowed": list(SNAG_FLOW[frm])})  # fmt: skip
    now = db.tx_time(s)
    if to == "RESOLVED":
        sn.resolution_note = _reason(body.note, "the recheck passed", "note")
        sn.resolved_on, sn.resolved_by = now, ctx.user.id
    if to == "CLOSED":
        if frm != "RESOLVED":
            sn.resolution_note = _reason(body.note, "the snag is closed without a fix", "note")
        sn.closed_on, sn.closed_by = now, ctx.user.id
    sn.status = to
    code = {"RESOLVED": "SNAG_RESOLVED", "CLOSED": "SNAG_CLOSED"}.get(to, "SNAG_UPDATED")
    events.record(s, p, code, stage=p.stage_code, frm=frm, to=to, snag_id=sn.id, snag_no=sn.snag_no)
    _done(p, s)
    return sn
