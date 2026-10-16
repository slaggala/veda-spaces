"""What the workspace shows (PLB-10, PLB-11, PLB-37, PLB-40, PLB-41): dashboard rows and the project page.

Shaped for the questions staff ask, not as raw rows: the hero (reference, property, stage, owner, next milestone,
readiness, blocking issues), then what needs attention and the next actions, then the sections. Commercial amounts and
digests appear only with ``project.view_commercial_baseline``; the full transition evaluations and audit history only
with ``project.view_audit``. ``actions`` are hints for the page; the server checks every action again.
"""

from __future__ import annotations

from datetime import date
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.modules.mtq.models import Property, PropertySpace
from veda.modules.mtq_commercial import quotations
from veda.modules.mtq_commercial.models import Quotation
from veda.platform.identity.models import User

from . import (
    access,
    baseline,
    classification,
    delivery_policy,
    events,
    gates,
    handover,
    lifecycle,
    policy,
    quality,
    reports,
    service,
    work,
)
from . import vocab as V
from .models import (
    Project,
    ProjectBlocker,
    ProjectChecklistItem,
    ProjectEvent,
    ProjectMember,
    ProjectMilestone,
    ProjectQcCheck,
    ProjectSiteReadiness,
    ProjectSnag,
    ProjectStage,
    ProjectTransition,
)


def _when(value) -> str | None:
    return clock.to_rfc3339(value) if value else None


def _day(value: date | None) -> str | None:
    return value.isoformat() if value else None


class People:
    def __init__(self, s: Session):
        self.s = s
        self.cache: dict[str, dict[str, Any]] = {}

    def __call__(self, uid: str | None) -> dict[str, Any] | None:
        if not uid:
            return None
        if uid not in self.cache:
            u = self.s.get(User, uid)
            self.cache[uid] = {"id": uid, "display_name": u.display_name if u else None}
        return self.cache[uid]


def _label(code: str | None) -> str | None:
    return code.lower().replace("_", " ").capitalize() if code else None


# --- shared pieces -----------------------------------------------------------------------------------------------------
def _milestones(s: Session, p: Project) -> list[ProjectMilestone]:
    return list(s.execute(sa.select(ProjectMilestone).where(ProjectMilestone.project_id == p.id)
                          .order_by(ProjectMilestone.planned_date.is_(None), ProjectMilestone.planned_date,
                                    ProjectMilestone.created_on)).scalars())  # fmt: skip


def _next_milestone(rows: list[ProjectMilestone], today: date) -> dict[str, Any] | None:
    for m in rows:
        if m.status not in V.MILESTONE_CLOSED:
            return {"id": m.id, "label": m.label, "code": m.milestone_code, "stage_code": m.stage_code,
                    "status": m.status, "planned_date": _day(m.planned_date),
                    "overdue": bool(m.planned_date and m.planned_date < today)}  # fmt: skip
    return None


def _blockers(s: Session, p: Project) -> list[ProjectBlocker]:
    return list(s.execute(sa.select(ProjectBlocker).where(ProjectBlocker.project_id == p.id)
                          .order_by(ProjectBlocker.created_on)).scalars())  # fmt: skip


def _owners(s: Session, p: Project) -> dict[str, ProjectMember]:
    return {m.responsibility: m for m in service.members(s, p) if m.responsibility != "MEMBER"}


def _last_material(s: Session, p: Project) -> str | None:
    found = s.execute(sa.select(sa.func.max(ProjectEvent.created_on)).where(
        ProjectEvent.project_id == p.id, ProjectEvent.event_code.in_(V.MATERIAL_EVENTS))).scalar()  # fmt: skip
    return _when(found)


def _property(s: Session, p: Project) -> dict[str, Any]:
    prop = s.get(Property, p.property_id)
    assert prop is not None
    return {"id": prop.id, "property_number": prop.property_number, "configuration_label": prop.configuration_label,
            "locality": prop.locality, "city": prop.city}  # fmt: skip


# --- dashboard ---------------------------------------------------------------------------------------------------------
def summary(s: Session, ctx, p: Project, people: People) -> dict[str, Any]:
    d = lifecycle.get(p.lifecycle_version)
    today = db.tx_time(s).date()
    owners = _owners(s, p)
    stage = d.stage(p.stage_code)
    rows = _milestones(s, p)
    blockers = [b for b in _blockers(s, p) if b.status in V.BLOCKER_OPEN]
    site = list(
        s.execute(sa.select(ProjectSiteReadiness.status).where(ProjectSiteReadiness.project_id == p.id)).scalars()
    )
    ev = gates.next_evaluation(s, p)
    waiting = gates.pending(s, p)
    handover = gates.handover_readiness(s, p)
    target = next((m for m in rows if m.milestone_code == "HANDOVER" and m.status not in ("CANCELLED", "NOT_APPLICABLE")),
                  None)  # fmt: skip
    next_owner = owners.get(stage.owner)
    return {
        "id": p.id, "version": p.version, "project_number": p.project_number, "status": p.status,
        "property": _property(s, p), "quotation_number": p.quotation_number,
        "stage": {"code": p.stage_code, "label": stage.label, "sequence": d.sequence(p.stage_code),
                  "of": len(d.stages), "entered_on": _when(p.stage_entered_on)},
        "owner": people(owners["PROJECT"].user_id) if "PROJECT" in owners else None,
        "next_action_owner": {"responsibility": stage.owner,
                              "person": people(next_owner.user_id) if next_owner else None},
        "next_milestone": _next_milestone(rows, today),
        "readiness": None if ev is None else {
            "next_stage": ev["to"], "next_stage_label": d.stage(ev["to"]).label if ev["to"] else None,
            "allowed": ev["allowed"], "blocker_count": len(ev["blockers"]), "risk": ev["risk"],
            "independent_approval": ev["independent_approval"], "awaiting_approval": waiting is not None},
        "blockers": {"gating": sum(1 for b in blockers if b.impact == "GATING"),
                     "informational": sum(1 for b in blockers if b.impact == "INFORMATIONAL"),
                     "customer_actions": sum(1 for b in blockers if b.responsible_party == "CUSTOMER"),
                     "assigned_to_me": sum(1 for b in blockers if b.assigned_to == ctx.user.id)},
        "site_ready": bool(site) and all(x in V.READINESS_SATISFIED for x in site),
        "site_actions": sum(1 for x in site if x in ("NOT_READY", "CUSTOMER_ACTION_REQUIRED", "VEDA_ACTION_REQUIRED")),
        "handover_ready": handover["ready"],
        "target_date": _day(target.planned_date) if target else None,
        "last_material_change": _last_material(s, p),
        "member": access.is_member(s, p.id, ctx.user.id),
    }  # fmt: skip


def _matches(row: dict[str, Any], query, today: str) -> bool:
    view = query.view
    stage = row["stage"]["code"]
    readiness = row["readiness"] or {}
    if view == "mine" and not row["member"]:
        return False
    if view == "blocked" and not row["blockers"]["gating"]:
        return False
    if view == "action_required" and not (readiness.get("awaiting_approval") or row["blockers"]["assigned_to_me"]
                                          or row["blockers"]["customer_actions"] or row["site_actions"]):  # fmt: skip
        return False
    if view == "site_readiness" and not (stage == "SITE_READINESS" or (row["status"] == "ACTIVE" and not
                                         row["site_ready"] and row["stage"]["sequence"] < 6)):  # fmt: skip
        return False
    if view == "installation" and stage not in ("READY_FOR_INSTALLATION", "INSTALLATION"):
        return False
    if view == "handover" and stage not in ("QUALITY_CHECK", "SNAGGING", "READY_FOR_HANDOVER"):
        return False
    if query.stage and stage != query.stage:
        return False
    if query.owner and (row["owner"] or {}).get("id") != query.owner:
        return False
    if query.q:
        needle = query.q.casefold()
        hay = " ".join(x or "" for x in (row["project_number"], row["quotation_number"],
                                          row["property"]["property_number"])).casefold()  # fmt: skip
        if needle not in hay:
            return False
    if query.blocker == "gating" and not row["blockers"]["gating"]:
        return False
    if query.blocker == "any" and not (row["blockers"]["gating"] or row["blockers"]["informational"]):
        return False
    if query.blocker == "none" and (row["blockers"]["gating"] or row["blockers"]["informational"]):
        return False
    if query.readiness == "ready" and not readiness.get("allowed"):
        return False
    if query.readiness == "blocked" and (not readiness or readiness.get("allowed")):
        return False
    if query.readiness == "awaiting_approval" and not readiness.get("awaiting_approval"):
        return False
    nm = row["next_milestone"]
    if query.milestone == "overdue" and not (nm and nm["overdue"]):
        return False
    if query.milestone == "planned" and not (nm and nm["planned_date"]):
        return False
    if query.milestone == "none" and nm:
        return False
    if query.handover == "ready" and not row["handover_ready"]:
        return False
    return not (query.handover == "not_ready" and row["handover_ready"])


def dashboard(s: Session, ctx, query) -> dict[str, Any]:
    from . import creation

    people = People(s)
    projects = s.execute(sa.select(Project).where(access.condition(ctx, "project.view"))
                         .order_by(Project.created_on.desc())).scalars().all()  # fmt: skip
    rows = [summary(s, ctx, p, people) for p in projects]
    today = db.tx_time(s).date().isoformat()
    shown = [r for r in rows if _matches(r, query, today)]
    counts = {v: sum(1 for r in rows if _matches(r, type(query)(view=v), today)) for v in
              ("all", "mine", "blocked", "action_required", "site_readiness", "installation", "handover")}  # fmt: skip
    bookable = []
    if ctx.scope(creation.PERMISSION):
        bookable = [{"quotation_id": q.id, "quotation_number": q.quotation_number, "label": quotations.number_label(q),
                     "property_id": q.property_id, "decided_on": _when(q.decided_on),
                     "problems": [{"code": x["code"], "message": x["message"]} for x in found]}
                    for q, found in creation.bookable(s, ctx)]  # fmt: skip
    return {"projects": shown, "counts": counts, "bookable": bookable,
            "lifecycle": {"version": lifecycle.CURRENT, "status": lifecycle.current().status},
            "policy": policy.public_view()}  # fmt: skip


# --- the project page --------------------------------------------------------------------------------------------------
def _promise_texts(s: Session, p: Project) -> dict[tuple[str, str], dict[str, Any]]:
    q = s.get(Quotation, p.source_quotation_id)
    info = ((q.snapshot if q else None) or {}).get("customer_information") or {}
    out = {}
    for kind, key in (("READINESS", "site_readiness"), ("RESPONSIBILITY", "client_responsibilities")):
        for item in info.get(key) or []:
            out[(kind, item["code"])] = {"text": item.get("text"), "quoted_status": item.get("status")}
    return out


def _evidence(row) -> dict[str, Any] | None:
    if not (row.evidence_attachment_id or row.evidence_reference):
        return None
    return {"attachment_id": row.evidence_attachment_id, "reference": row.evidence_reference}


def _stages(s: Session, p: Project, d, people: People) -> list[dict[str, Any]]:
    rows = {
        r.stage_code: r for r in s.execute(sa.select(ProjectStage).where(ProjectStage.project_id == p.id)).scalars()
    }
    out = []
    for st in d.stages:
        r = rows.get(st.code)
        t = d.next_transition(st.code)
        out.append({"code": st.code, "label": st.label, "description": st.description, "sequence": d.sequence(st.code),
                    "customer_stage": st.customer_stage, "owner_responsibility": st.owner, "terminal": st.terminal,
                    "status": r.status if r else "NOT_STARTED", "entered_on": _when(r.entered_on) if r else None,
                    "entered_by": people(r.entered_by) if r else None,
                    "completed_on": _when(r.completed_on) if r else None,
                    "completed_by": people(r.completed_by) if r else None,
                    "exit": {"to": t.to, "risk": t.risk, "default_gates": list(t.default_gates)} if t else None})  # fmt: skip
    return out


def _checklist(s: Session, p: Project, d, people: People) -> list[dict[str, Any]]:
    rows = {(r.stage_code, r.item_code): r for r in s.execute(
        sa.select(ProjectChecklistItem).where(ProjectChecklistItem.project_id == p.id)).scalars()}  # fmt: skip
    out = []
    for st in d.stages:
        if not st.checklist:
            continue
        optional = gates.optional_items(p, st.code)
        items = []
        for it in st.checklist:
            r = rows.get((st.code, it.code))
            if r is None:
                continue
            items.append({"id": r.id, "version": r.version, "code": it.code, "label": it.label, "ref": it.ref,
                          "required": it.code not in optional, "state": r.state,
                          "completed_by": people(r.completed_by), "completed_on": _when(r.completed_on),
                          "note": r.note, "not_applicable_reason": r.not_applicable_reason,
                          "reopen_reason": r.reopen_reason, "evidence": _evidence(r)})  # fmt: skip
        out.append({"stage_code": st.code, "stage_label": st.label, "current": st.code == p.stage_code,
                    "closed": d.sequence(st.code) < d.sequence(p.stage_code),
                    "done": sum(1 for i in items if i["state"] != "OPEN"), "total": len(items), "items": items})  # fmt: skip
    return out


def _blocker(b: ProjectBlocker, d, people: People) -> dict[str, Any]:
    return {"id": b.id, "version": b.version, "category": b.category, "source": b.source, "impact": b.impact,
            "title": b.title, "description": b.description, "customer_action": b.customer_action,
            "responsible_party": b.responsible_party, "assigned_to": people(b.assigned_to),
            "target_date": _day(b.target_date), "status": b.status,
            "blocks": {"code": b.blocks_stage_code, "label": d.stage(b.blocks_stage_code).label}
            if b.blocks_stage_code else None,
            "resolution": b.resolution, "resolved_on": _when(b.resolved_on), "resolved_by": people(b.resolved_by),
            "raised_on": _when(b.created_on), "raised_by": people(b.created_by),
            "related": {"milestone_id": b.related_milestone_id, "checklist_item_id": b.related_checklist_item_id,
                        "site_readiness_id": b.related_site_readiness_id, "quotation_id": b.related_quotation_id,
                        "work_package_id": b.related_work_package_id},
            "customer_summary": b.customer_summary}  # fmt: skip


def _milestone(m: ProjectMilestone, today: date) -> dict[str, Any]:
    return {"id": m.id, "version": m.version, "code": m.milestone_code, "label": m.label,
            "customer_label": m.customer_label, "description": m.description, "stage_code": m.stage_code,
            "status": m.status, "status_reason": m.status_reason, "planned_date": _day(m.planned_date),
            "actual_date": _day(m.actual_date), "customer_promised_date": _day(m.customer_promised_date),
            "overdue": bool(m.planned_date and m.planned_date < today and m.status not in V.MILESTONE_CLOSED),
            "depends_on_milestone_id": m.depends_on_milestone_id, "owner_responsibility": m.owner_responsibility,
            "evidence": _evidence(m)}  # fmt: skip


def _readiness(s: Session, p: Project, people: People) -> list[dict[str, Any]]:
    texts = _promise_texts(s, p)
    rows = s.execute(sa.select(ProjectSiteReadiness).where(ProjectSiteReadiness.project_id == p.id)
                     .order_by(ProjectSiteReadiness.kind, ProjectSiteReadiness.item_code)).scalars()  # fmt: skip
    out = []
    for r in rows:
        promised = texts.get((r.kind, r.item_code), {})
        out.append({"id": r.id, "version": r.version, "kind": r.kind, "source": r.source, "item_code": r.item_code,
                    "category": r.category, "label": r.label or promised.get("text"),
                    "promise": {"content_version": r.promise_content_version, "text": promised.get("text"),
                                "quoted_status": promised.get("quoted_status")} if r.source == "CUSTOMER_PROMISE"
                    else None,
                    "status": r.status, "satisfied": r.status in V.READINESS_SATISFIED,
                    "responsible_party": r.responsible_party, "action": r.action, "customer_action": r.customer_action,
                    "due_date": _day(r.due_date), "note": r.note, "evidence": _evidence(r),
                    "resolved_on": _when(r.resolved_on), "resolved_by": people(r.resolved_by),
                    "updated_on": _when(r.updated_on)})  # fmt: skip
    return out


def _spaces(s: Session, p: Project) -> dict[str, str]:
    return {sp.id: sp.label for sp in s.execute(sa.select(PropertySpace).where(
        PropertySpace.property_id == p.property_id)).scalars()}  # fmt: skip


def _qc(s: Session, p: Project, people: People, spaces: dict[str, str]) -> dict[str, Any]:
    rows = quality.checks(s, p)
    latest = gates.latest_qc(s, p)
    required = gates.required_qc(p)
    chains = quality.chains(rows)

    def row(c: ProjectQcCheck) -> dict[str, Any]:
        return {"id": c.id, "category": c.category, "result": c.result, "space": spaces.get(c.space_id or ""),
                "space_id": c.space_id, "observation": c.observation, "evidence": _evidence(c),
                "recheck_of_id": c.recheck_of_id, "qc_point_id": c.qc_point_id, "work_package_id": c.work_package_id,
                "checked_by": people(c.created_by), "checked_on": _when(c.created_on)}  # fmt: skip

    points = []
    for pt in quality.points(s, p, active=False):
        head = quality.point_head(rows, pt.id)
        points.append({"id": pt.id, "version": pt.version, "point_no": pt.point_no, "category": pt.category,
                       "label": pt.label, "space": spaces.get(pt.space_id or ""), "space_id": pt.space_id,
                       "work_package_id": pt.work_package_id, "evidence_required": pt.evidence_required,
                       "status": pt.status, "withdrawn_reason": pt.withdrawn_reason,
                       "result": head.result if head else None, "head_id": head.id if head else None})  # fmt: skip
    return {"required_categories": list(required),
            "categories": [{"category": cat, "required": cat in required,
                            "latest": row(latest[cat]) if cat in latest else None} for cat in V.QC_CATEGORIES],
            "points": points,
            "chains": [{"head": row(c[-1]), "length": len(c), "ever_failed": quality.ever_failed(c),
                        "root_id": c[0].id} for c in chains],
            "history": [row(c) for c in sorted(rows, key=lambda r: (r.created_on, r.id), reverse=True)]}  # fmt: skip


def _snag(n: ProjectSnag, people: People, spaces: dict[str, str]) -> dict[str, Any]:
    return {"id": n.id, "version": n.version, "snag_no": n.snag_no, "category": n.category,
            "customer_title": n.customer_title, "description": n.description, "space": spaces.get(n.space_id or ""),
            "space_id": n.space_id, "item_reference": n.item_reference, "is_blocking": n.is_blocking,
            "classification_reason": n.classification_reason,
            "owner": people(n.owner_user_id), "responsible_party": n.responsible_party, "status": n.status,
            "allowed_next": list(service.SNAG_FLOW[n.status]), "target_date": _day(n.target_date),
            "evidence": _evidence(n), "resolution_note": n.resolution_note, "resolved_on": _when(n.resolved_on),
            "resolved_by": people(n.resolved_by), "closed_on": _when(n.closed_on), "closed_by": people(n.closed_by),
            "qc_check_id": n.qc_check_id, "raised_on": _when(n.created_on), "raised_by": people(n.created_by),
            "work_package_id": n.work_package_id, "source": n.source, "priority": n.priority,
            "customer_visible": n.customer_visible, "fixed_by": people(n.fixed_by), "fixed_on": _when(n.fixed_on),
            "fix_note": n.fix_note, "closure_code": n.closure_code,
            "resolution_evidence": {"attachment_id": n.resolution_evidence_attachment_id}
            if n.resolution_evidence_attachment_id else None}  # fmt: skip


def _work(s: Session, p: Project, people: People, spaces: dict[str, str], today: date) -> list[dict[str, Any]]:
    checks = quality.checks(s, p)
    return [{"id": w.id, "version": w.version, "package_no": w.package_no, "stage_code": w.stage_code,
             "space": spaces.get(w.space_id or ""), "space_id": w.space_id, "title": w.title,
             "description": w.description, "customer_label": w.customer_label, "customer_visible": w.customer_visible,
             "owner": people(w.owner_user_id), "depends_on_id": w.depends_on_id, "status": w.status,
             "state": work.derived_state(s, w, checks), "scheduled": bool(w.planned_start or w.planned_finish),
             "planned_start": _day(w.planned_start), "planned_finish": _day(w.planned_finish),
             "plan_revision": w.plan_revision, "replan_reason": w.replan_reason,
             "past_planned_finish": bool(w.planned_finish and w.planned_finish < today
                                         and w.status not in V.WORK_PACKAGE_CLOSED),
             "actual_start": _day(w.actual_start), "actual_finish": _day(w.actual_finish),
             "started_by": people(w.started_by), "completed_by": people(w.completed_by),
             "completion_note": w.completion_note, "reopen_reason": w.reopen_reason, "cancel_reason": w.cancel_reason,
             "evidence": _evidence(w)} for w in work.rows(s, p)]  # fmt: skip


def _reports(s: Session, p: Project, people: People) -> list[dict[str, Any]]:
    return [{"id": r.id, "version": r.version, "report_no": r.report_no, "channel": r.channel,
             "description": r.description, "area": r.area, "status": r.status, "snag_id": r.snag_id,
             "decline_code": r.decline_code, "response": r.response, "reported_on": _when(r.created_on),
             "recorded_by": people(r.created_by) if r.channel == "STAFF" else None,
             "triaged_by": people(r.triaged_by), "triaged_on": _when(r.triaged_on)} for r in reports.rows(s, p)]  # fmt: skip


def _packages(s: Session, p: Project, people: People) -> list[dict[str, Any]]:
    out = []
    for pkg in handover.packages(s, p):
        item = handover.present(pkg)
        item["prepared_by"] = people(pkg.created_by)
        item["superseded_by"] = people(pkg.superseded_by)
        item["stale"] = handover.staleness(s, p, pkg) if pkg.status == "PREPARED" else None
        out.append(item)
    return out


def _baseline(s: Session, ctx, p: Project) -> dict[str, Any]:
    """PLB-03, PLB-31: the lineage. Amounts and digests only for project.view_commercial_baseline."""
    full = access.can(s, ctx, p, "project.view_commercial_baseline")
    chain = baseline.rows(s, p.id)
    problems = baseline.problems(s, p)
    lineage = []
    for r in chain:
        q = s.get(Quotation, r.quotation_id)
        item = {"id": r.id, "sequence_no": r.sequence_no, "kind": r.kind, "current": r.sequence_no == p.baseline_seq,
                "quotation_id": r.quotation_id, "label": quotations.number_label(q) if q else None,
                "variation_no": r.variation_no, "decided_on": _when(r.decided_on), "decision_method": r.decision_method,
                "recorded_on": _when(r.created_on)}  # fmt: skip
        if full:
            item.update({"accepted_total_minor": r.accepted_total_minor,
                         "cumulative_value_minor": r.cumulative_value_minor,
                         "selected_optional_count": r.selected_optional_count,
                         "snapshot_sha256": r.snapshot_sha256, "accepted_baseline_sha256": r.accepted_baseline_sha256,
                         "estimate_snapshot_sha256": r.estimate_snapshot_sha256, "baseline_sha256": r.baseline_sha256,
                         "previous_baseline_id": r.previous_baseline_id, "customer_promise": r.customer_promise,
                         "lineage": {"measurement_revision_no": r.measurement_revision_no,
                                     "scope_revision_no": r.scope_revision_no, "boq_revision_no": r.boq_revision_no,
                                     "estimate_revision_no": r.estimate_revision_no}})  # fmt: skip
        lineage.append(item)
    variations = [{"quotation_id": q.id, "label": quotations.number_label(q), "status": q.status,
                   **({"total_minor": q.total_minor} if full else {})}
                  for q in s.execute(sa.select(Quotation).where(Quotation.quotation_number == p.quotation_number,
                                                                Quotation.variation_no > 0)
                                     .order_by(Quotation.variation_no, Quotation.version_no)).scalars()]  # fmt: skip
    return {"full": full, "verified": not problems, "problems": problems, "current_seq": p.baseline_seq,
            "lineage": lineage, "variations": variations,
            "open_variations": [v for v in variations if v["status"] in ("DRAFT", "INTERNAL_REVIEW", "APPROVED", "ISSUED")]}  # fmt: skip


def _transition(t: ProjectTransition, people: People, full: bool) -> dict[str, Any]:
    out = {"id": t.id, "version": t.version, "kind": t.kind, "from_stage": t.from_stage, "to_stage": t.to_stage,
           "outcome": t.outcome, "independent_approval": t.independent_approval,
           "requested_by": people(t.created_by), "requested_on": _when(t.created_on), "reason": t.reason,
           "decided_by": people(t.decided_by), "decided_on": _when(t.decided_on), "decision_reason": t.decision_reason,
           "blockers": list((t.evaluation or {}).get("blockers", [])),  # codes and ids only (never staff text)
           "handover": {"handover_on": _day(t.handover_on), "acknowledgement_reference": t.acknowledgement_reference,
                        "evidence_attachment_id": t.evidence_attachment_id, "observations": t.observations}
           if t.kind == "HANDOVER" else None}  # fmt: skip
    if full:
        out["evaluation"], out["evaluation_sha256"] = t.evaluation, t.evaluation_sha256
    return out


def _timeline(s: Session, p: Project, people: People) -> list[dict[str, Any]]:
    return [{"id": e.id, "code": e.event_code, "stage_code": e.stage_code, "from": e.from_state, "to": e.to_state,
             "detail": e.detail, "by": people(e.created_by), "on": _when(e.created_on)}
            for e in events.timeline(s, p.id)]  # fmt: skip


def _attention(ev: dict[str, Any] | None, blockers: list[dict[str, Any]], site: list[dict[str, Any]],
               snags: list[dict[str, Any]], milestones: list[dict[str, Any]], waiting,
               work_rows: Sequence[dict[str, Any]] = (), report_rows: Sequence[dict[str, Any]] = ()) -> list[dict[str, Any]]:  # fmt: skip
    """PLB-40/41: what needs attention, gating first, each saying who acts, what to do and what it blocks."""
    out: list[dict[str, Any]] = []
    if waiting is not None:
        out.append({"severity": "ACTION", "kind": "APPROVAL", "title": "A stage transition is waiting for approval",
                    "who": "VEDA", "action": "An approver other than the requester approves or rejects it",
                    "blocks": waiting.to_stage, "entity": {"type": "transition", "id": waiting.id}})  # fmt: skip
    for b in blockers:
        if b["status"] in V.BLOCKER_OPEN:
            out.append({"severity": "GATING" if b["impact"] == "GATING" else "INFORMATIONAL", "kind": "BLOCKER",
                        "title": b["title"], "who": b["responsible_party"],
                        "action": b["customer_action"] if b["responsible_party"] == "CUSTOMER" else b["description"],
                        "blocks": (b["blocks"] or {}).get("code"), "entity": {"type": "blocker", "id": b["id"]}})  # fmt: skip
    for r in site:
        if not r["satisfied"] and r["status"] != "TO_BE_CONFIRMED":
            out.append({"severity": "SITE", "kind": "SITE_READINESS", "title": r["label"] or _label(r["category"]),
                        "who": r["responsible_party"],
                        "action": r["customer_action"] if r["responsible_party"] == "CUSTOMER" else r["action"],
                        "blocks": None, "entity": {"type": "site_readiness", "id": r["id"]}})  # fmt: skip
    for n in snags:
        if n["status"] in V.SNAG_OPEN and n["is_blocking"]:
            out.append({"severity": "GATING", "kind": "SNAG", "title": f"Snag {n['snag_no']}: {n['customer_title']}",
                        "who": n["responsible_party"], "action": "Fix and recheck", "blocks": "READY_FOR_HANDOVER",
                        "entity": {"type": "snag", "id": n["id"]}})  # fmt: skip
    for w in work_rows:
        if w["state"] in ("BLOCKED", "CORRECTION_REQUIRED"):
            out.append({"severity": "GATING", "kind": "WORK", "title": f"WP-{w['package_no']}: {w['title']}",
                        "who": "VEDA", "action": "Clear its blocker" if w["state"] == "BLOCKED"
                        else "Correct it and recheck", "blocks": w["stage_code"],
                        "entity": {"type": "work_package", "id": w["id"]}})  # fmt: skip
    for r in report_rows:
        if r["status"] == "SUBMITTED":
            out.append({"severity": "ACTION", "kind": "CUSTOMER_REPORT", "title": f"Customer report {r['report_no']} "
                        "is waiting for review", "who": "VEDA", "action": "Raise a snag, link one, or reply",
                        "blocks": "READY_FOR_HANDOVER", "entity": {"type": "customer_report", "id": r["id"]}})  # fmt: skip
    for m in milestones:
        if m["overdue"]:
            out.append({"severity": "INFORMATIONAL", "kind": "MILESTONE", "title": f"{m['label']} is past its planned "
                        "date", "who": "VEDA", "action": "Re-plan or complete it", "blocks": None,
                        "entity": {"type": "milestone", "id": m["id"]}})  # fmt: skip
    order = {"ACTION": 0, "GATING": 1, "SITE": 2, "INFORMATIONAL": 3}
    return sorted(out, key=lambda x: order[x["severity"]])


def _next_actions(ev: dict[str, Any] | None) -> list[dict[str, Any]]:
    if ev is None:
        return []
    seen, out = set(), []
    for b in ev["blockers"]:
        key = (b["gate"], b["code"], b.get("responsible_party"))
        if key in seen:
            continue
        seen.add(key)
        out.append({"gate": b["gate"], "code": b["code"], "who": b.get("responsible_party") or "VEDA",
                    "message": b["message"], "entity": b.get("entity")})  # fmt: skip
    return out


def _owner_can(s: Session, ctx, p: Project, code: str, attr: str) -> bool:
    """Whether the owner's decision ``code`` is recorded and names a capability the person holds here."""
    od = policy.decision(code)
    capability = getattr(od, attr, None) if od is not None else None
    return p.status == "ACTIVE" and capability is not None and access.can(s, ctx, p, capability)


def _actions(s: Session, ctx, p: Project, waiting) -> dict[str, bool]:
    active = p.status == "ACTIVE"

    def can(code: str) -> bool:
        return active and access.can(s, ctx, p, code)

    return {"request_transition": can("project.manage_stage"), "complete_handover": can("project.complete_handover"),
            "approve_transition": bool(waiting) and can("project.approve_transition")
            and waiting.created_by != ctx.user.id,
            "assign_team": can("project.assign_team"), "complete_checklist": can("project.complete_checklist"),
            "checklist_not_applicable": can("project.checklist.not_applicable"),
            "manage_milestone": can("project.manage_milestone"), "raise_blocker": can("project.raise_blocker"),
            "resolve_blocker": can("project.resolve_blocker"),
            "manage_site_readiness": can("project.manage_site_readiness"), "manage_qc": can("project.manage_qc"),
            "manage_snag": can("project.manage_snag"), "manage_work": can("project.manage_work"),
            "verify_snag": can("project.verify_snag"),
            "prepare_handover_package": can("project.complete_handover") and p.stage_code == "READY_FOR_HANDOVER",
            "record_promised_date": _owner_can(s, ctx, p, "PLB-OD-13", "capability"),
            "reclassify_snag": _owner_can(s, ctx, p, "PLB-OD-06", "snag_reclassification_capability"),
            "qc_required_not_applicable": _owner_can(s, ctx, p, "PLB-OD-08", "not_applicable_capability"),
            "view_commercial_baseline": access.can(s, ctx, p, "project.view_commercial_baseline"),
            "view_audit": access.can(s, ctx, p, "project.view_audit")}  # fmt: skip


EVIDENCE_CODES = ("project.complete_checklist", "project.manage_milestone", "project.manage_site_readiness",
                  "project.manage_qc", "project.manage_snag", "project.complete_handover", "project.manage_work")  # fmt: skip


def evidence_options(s: Session, ctx, p: Project) -> list[dict[str, Any]]:
    """PLB-39: the scanned, available attachments of this project's customer record that may be cited as evidence
    (references only: category, what it is attached to and when; never a URL or the file)."""
    from veda.modules.attachments import service as att
    from veda.modules.attachments.models import Attachment

    if p.status != "ACTIVE" or not any(access.can(s, ctx, p, c) for c in EVIDENCE_CODES):
        return []
    rows = s.execute(sa.select(Attachment).where(Attachment.lead_id == p.lead_id, Attachment.scan_status == "CLEAN")
                     .order_by(Attachment.created_on.desc()).limit(100)).scalars()  # fmt: skip
    return [{"id": a.id, "category": a.category_code, "attached_to": a.entity_type, "uploaded_on": _when(a.created_on)}
            for a in rows if att.is_available(a)]  # fmt: skip


def candidates(s: Session, p: Project) -> list[dict[str, Any]]:
    """PLB-08: active people who may hold each responsibility on this project (the capability it needs, and
    project.view). Names only; the assignment is validated again by the server."""
    from veda.platform.rbac.resolver import holders_of, load_grants

    from .permissions import RESPONSIBILITY_CAPABILITY

    people = People(s)
    out = []
    for uid in holders_of(s, "project.view"):
        granted = load_grants(s, uid).granted
        fits = [r for r, code in RESPONSIBILITY_CAPABILITY.items() if granted.get(code) is not None]
        if fits:
            out.append({**(people(uid) or {}), "responsibilities": fits})
    return sorted(out, key=lambda x: (x.get("display_name") or "").casefold())


def detail(s: Session, ctx, p: Project) -> dict[str, Any]:
    people = People(s)
    d = lifecycle.get(p.lifecycle_version)
    today = db.tx_time(s).date()
    owners = _owners(s, p)
    stage = d.stage(p.stage_code)
    ev = gates.next_evaluation(s, p)  # the handover's own evidence is given when completing it
    waiting = gates.pending(s, p)
    blockers = [_blocker(b, d, people) for b in _blockers(s, p)]
    milestones = [_milestone(m, today) for m in _milestones(s, p)]
    site = _readiness(s, p, people)
    spaces = _spaces(s, p)
    snags = [_snag(n, people, spaces) for n in s.execute(sa.select(ProjectSnag).where(ProjectSnag.project_id == p.id)
                                                         .order_by(ProjectSnag.snag_no)).scalars()]  # fmt: skip
    audit = access.can(s, ctx, p, "project.view_audit")
    transitions = s.execute(sa.select(ProjectTransition).where(ProjectTransition.project_id == p.id)
                            .order_by(ProjectTransition.created_on.desc())).scalars().all()  # fmt: skip
    members_all = service.members(s, p, active=None)
    unsatisfied = [r for r in site if not r["satisfied"]]
    work_rows = _work(s, p, people, spaces, today)
    report_rows = _reports(s, p, people)
    return {
        "id": p.id, "version": p.version, "project_number": p.project_number, "status": p.status,
        "source": p.source, "property": _property(s, p), "quotation_number": p.quotation_number,
        "source_quotation_id": p.source_quotation_id, "created_on": _when(p.created_on),
        "created_by": people(p.created_by), "handed_over_on": _when(p.handed_over_on),
        "handed_over_by": people(p.handed_over_by),
        "lifecycle": {"version": d.version, "sha256": d.sha256,
                      "status": "APPROVED" if gates.lifecycle_approved(p) else d.status},
        "stage": {"code": p.stage_code, "label": stage.label, "description": stage.description,
                  "sequence": d.sequence(p.stage_code), "of": len(d.stages), "entered_on": _when(p.stage_entered_on),
                  "owner_responsibility": stage.owner, "customer_stage": stage.customer_stage},
        "owner": people(owners["PROJECT"].user_id) if "PROJECT" in owners else None,
        "next_milestone": _next_milestone(_milestones(s, p), today),
        "readiness": ev, "awaiting_approval": _transition(waiting, people, audit) if waiting else None,
        "handover_readiness": gates.handover_readiness(s, p),
        "site_readiness_state": "NOT_ASSESSED" if not site else ("READY" if not unsatisfied else "BLOCKED"
                                if any(r["status"] != "TO_BE_CONFIRMED" for r in unsatisfied) else "TO_BE_CONFIRMED"),
        "attention": _attention(ev, blockers, site, snags, milestones, waiting, work_rows, report_rows),
        "next_actions": _next_actions(ev),
        "team": [{"id": m.id, "version": m.version, "user": people(m.user_id), "responsibility": m.responsibility,
                  "active": m.is_active, "eligible": m.is_active and gates.owner_eligible(s, m),
                  "assigned_on": _when(m.created_on), "assigned_by": people(m.created_by),
                  "removed_on": _when(m.removed_on), "removed_by": people(m.removed_by),
                  "removal_reason": m.removal_reason} for m in members_all],
        "stages": _stages(s, p, d, people), "checklist": _checklist(s, p, d, people), "blockers": blockers,
        "needs_reassignment": sorted(m.responsibility for m in members_all if m.is_active
                                     and m.responsibility != "MEMBER" and not gates.owner_eligible(s, m)),
        "milestones": milestones, "site_readiness": site, "qc": _qc(s, p, people, spaces), "snags": snags,
        "work_packages": work_rows, "customer_reports": report_rows, "handover_packages": _packages(s, p, people),
        "delivery_policy": delivery_policy.public_view(),
        "baseline": _baseline(s, ctx, p),
        "transitions": [_transition(t, people, audit) for t in transitions],
        "timeline": _timeline(s, p, people),
        "spaces": [{"id": k, "label": v} for k, v in spaces.items()],
        "evidence_options": evidence_options(s, ctx, p),
        "actions": _actions(s, ctx, p, waiting),
        "policy": policy.public_view(),
        "classification": classification.public_view(),
        "last_material_change": _last_material(s, p),
    }  # fmt: skip


def vocabulary() -> dict[str, Any]:
    d = lifecycle.current()
    return {"stages": [{"code": st.code, "label": st.label} for st in d.stages], "responsibilities": V.RESPONSIBILITIES,
            "responsible_parties": V.RESPONSIBLE_PARTIES, "milestone_types": V.MILESTONE_TYPES,
            "milestone_states": V.MILESTONE_STATES, "blocker_categories": V.BLOCKER_CATEGORIES,
            "blocker_impacts": V.BLOCKER_IMPACTS, "blocker_statuses": V.BLOCKER_STATUSES,
            "readiness_kinds": V.READINESS_KINDS, "readiness_categories": V.READINESS_CATEGORIES,
            "readiness_statuses": V.READINESS_STATUSES, "qc_categories": V.QC_CATEGORIES, "qc_results": V.QC_RESULTS,
            "snag_categories": V.SNAG_CATEGORIES, "snag_statuses": V.SNAG_STATUSES,
            "snag_priorities": V.SNAG_PRIORITIES, "snag_closure_codes": V.SNAG_CLOSED_WITHOUT_FIX,
            "work_package_states": V.WORK_PACKAGE_STATES, "report_decline_codes": V.REPORT_DECLINE_CODES,
            "gates": [{"code": k, "label": v, "structural": k in lifecycle.STRUCTURAL_GATES}
                      for k, v in lifecycle.GATES.items()],
            "lifecycle": d.document() | {"sha256": d.sha256, "status": d.status}}  # fmt: skip
