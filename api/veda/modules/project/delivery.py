"""The customer's view of project delivery (PEX-060 … PEX-066), built from an allow-list of customer-safe fields.

Shown only while VEDA_PROJECT_DELIVERY_PORTAL_ENABLED, the portal's flag and the Project Lifecycle's flag are all on,
and only for a property the portal already authorised (the caller resolves it; anything else is 404). Every field
read here is classified SAFE or CUSTOMER_ACTION (``classification``; asserted below). Never read: internal titles,
descriptions, notes, reasons, people, owners, planned dates, QC observations, evidence, amounts or audit detail.

What it says, and how it stays honest:

- **Work**: only packages staff marked customer-visible with customer wording. COMPLETED only when completed with no
  failed check and no open snag on it (else "being corrected"); BLOCKED from an open gating blocker (ACTION REQUIRED
  when the customer must act); UPCOMING when not started. Counts, never a percentage.
- **Dates**: only a customer-promised milestone date (PLB-OD-13 governs recording one). Planned dates are internal.
- **Paused**: an open blocker staff gave a customer summary; "waiting on Veda Spaces" is never an action for the
  customer.
- **Quality**: counts of checks passed and being corrected. No finding is described.
- **Snags**: customer-visible snags and their state, in customer words. **Reports**: the account's own reports, their
  words back, the outcome and Veda's reply.
- **Handover**: readiness from the one computation (``gates.handover_readiness``), as the number of remaining items in
  customer categories; the current package's customer summary and its acknowledgement.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.modules.portal import vocab as PV

from . import classification as C
from . import delivery_policy, gates, handover, lifecycle, notices, quality, reports, work
from .models import Project, ProjectBlocker, ProjectMilestone, ProjectSnag

BLOCKED = "BLOCKED"
PHASES = {
    "PROPOSAL_ACCEPTED": "Getting started", "VEDA_CONFIRMATION": "Getting started",
    "SCOPE_DESIGN_FINALISATION": "Finalising your design and scope", "SITE_READINESS": "Getting your site ready",
    "PRODUCTION_READINESS": "Preparing and making your interiors", "INSTALLATION": "Installing your interiors",
    "JOINT_INSPECTION": "Inspection and finishing touches", "HANDOVER": "Handover",
}  # fmt: skip
SNAG_WORDS = {"OPEN": "Noted", "IN_PROGRESS": "Being fixed", "READY_FOR_RECHECK": "Fixed, waiting for our check",
              "RESOLVED": "Fixed and checked"}  # fmt: skip
CLOSED_WORDS = {"FIXED": "Fixed and checked", "DUPLICATE": "Closed: already recorded",
                "NOT_A_DEFECT": "Closed: checked, no fix needed", "RAISED_IN_ERROR": "Closed: recorded in error"}  # fmt: skip
REPORT_WORDS = {"SUBMITTED": "Received, being reviewed", "ACCEPTED": "Accepted: being fixed", "DECLINED": "Reviewed"}
DECLINE_WORDS = {"DUPLICATE": "Already recorded", "NOT_A_DEFECT": "Checked: no fix needed",
                 "NOT_IN_SCOPE": "Not part of the agreed work"}  # fmt: skip
# What a remaining handover item is, in customer words. Anything internal is "final checks by Veda Spaces".
READINESS_WORDS = {"WORK_COMPLETE": "Work still to finish", "QC_PASSED": "Quality checks", "QC_RECORDED": "Quality checks",
                   "SNAGS_RESOLVED": "Snags to fix", "CUSTOMER_REPORTS_TRIAGED": "Your reports under review",
                   "VARIATIONS_CLOSED": "Changes to the agreed work", "NO_GATING_BLOCKERS": "Items on hold"}  # fmt: skip
FINAL_CHECKS = "Final checks by Veda Spaces"
READS = (("project_work_package", ("customer_label", "customer_visible", "status", "actual_finish", "stage_code")),
         ("project_blocker", ("customer_summary", "customer_action", "responsible_party", "status", "impact")),
         ("project_snag", ("snag_no", "customer_title", "status", "customer_visible", "closure_code")),
         ("project_customer_report", ("report_no", "description", "area", "status", "decline_code", "response")),
         ("project_handover_package", ("package_no", "status", "content", "content_sha256", "acknowledged_on")),
         ("project_milestone", ("customer_label", "customer_promised_date", "status")),
         ("project_qc_check", ("result",)))  # fmt: skip


def enabled() -> bool:
    return notices.delivery_enabled()


def projects(s: Session, property_id: str) -> list[Project]:
    return list(s.execute(sa.select(Project).where(Project.property_id == property_id, Project.is_deleted == sa.false())
                          .order_by(Project.created_on)).scalars())  # fmt: skip


def project_for(s: Session, property_id: str, project_id: str) -> Project | None:
    p = s.get(Project, project_id)
    return p if p is not None and not p.is_deleted and p.property_id == property_id else None


def _day(v) -> str | None:
    return v.isoformat() if v else None


def _work(s: Session, p: Project, checks) -> list[dict[str, Any]]:
    out = []
    for wp in work.rows(s, p):
        if not wp.customer_visible or not wp.customer_label or wp.status == "CANCELLED":
            continue
        state = work.derived_state(s, wp, checks)
        if state == "BLOCKED":
            waits_on_customer = any(b.responsible_party == "CUSTOMER" and b.customer_action
                                    for b in work.gating_blockers(s, wp))  # fmt: skip
            shown, detail = (
                (PV.ACTION_REQUIRED, "Waiting for something from you") if waits_on_customer else (BLOCKED, "On hold")
            )
        elif state == "COMPLETED":
            shown, detail = PV.COMPLETED, "Completed"
        elif state == "CORRECTION_REQUIRED":
            shown, detail = PV.IN_PROGRESS, "Being corrected"
        elif state == "IN_PROGRESS":
            shown, detail = PV.IN_PROGRESS, "In progress"
        else:
            shown, detail = PV.UPCOMING, "Not started yet"
        out.append({"label": wp.customer_label, "state": shown, "detail": detail,
                    "completed_on": _day(wp.actual_finish) if shown == PV.COMPLETED else None})  # fmt: skip
    return out


def _paused(s: Session, p: Project) -> list[dict[str, Any]]:
    rows = s.execute(sa.select(ProjectBlocker).where(ProjectBlocker.project_id == p.id,
                                                     ProjectBlocker.is_deleted == sa.false(),
                                                     ProjectBlocker.customer_summary.is_not(None),
                                                     ProjectBlocker.status.in_(("OPEN", "IN_PROGRESS", "WAITING_CUSTOMER",
                                                                                "WAITING_VEDA")))
                     .order_by(ProjectBlocker.created_on)).scalars()  # fmt: skip
    out = []
    for b in rows:
        customer = b.responsible_party == "CUSTOMER" and b.status != "WAITING_VEDA"
        out.append({"text": b.customer_summary, "state": PV.ACTION_REQUIRED if customer else BLOCKED,
                    "who": "YOU" if customer else "VEDA_SPACES"})  # fmt: skip
    return out


def _next_date(s: Session, p: Project) -> dict[str, Any] | None:
    today = db.tx_time(s).date()
    m = s.execute(sa.select(ProjectMilestone).where(ProjectMilestone.project_id == p.id,
                                                    ProjectMilestone.is_deleted == sa.false(),
                                                    ProjectMilestone.customer_promised_date.is_not(None),
                                                    ProjectMilestone.customer_promised_date >= today,
                                                    ProjectMilestone.status.notin_(("COMPLETED", "CANCELLED",
                                                                                    "NOT_APPLICABLE")))
                  .order_by(ProjectMilestone.customer_promised_date).limit(1)).scalar_one_or_none()  # fmt: skip
    if m is None:
        return None
    return {"label": m.customer_label or "Next milestone", "date": _day(m.customer_promised_date)}


def _snags(s: Session, p: Project) -> list[dict[str, Any]]:
    rows = s.execute(sa.select(ProjectSnag).where(ProjectSnag.project_id == p.id, ProjectSnag.is_deleted == sa.false(),
                                                  ProjectSnag.customer_visible == sa.true())
                     .order_by(ProjectSnag.snag_no)).scalars()  # fmt: skip
    out = []
    for n in rows:
        words = CLOSED_WORDS.get(n.closure_code or "", "Closed") if n.status == "CLOSED" else SNAG_WORDS[n.status]
        done = n.status == "RESOLVED" or n.closure_code == "FIXED"
        out.append({"number": n.snag_no, "title": n.customer_title, "status": words,
                    "state": PV.COMPLETED if done or n.status == "CLOSED" else PV.IN_PROGRESS})  # fmt: skip
    return out


def _reports(s: Session, p: Project, account_id: str) -> list[dict[str, Any]]:
    snag_no = {
        n.id: n.snag_no for n in s.execute(sa.select(ProjectSnag).where(ProjectSnag.project_id == p.id)).scalars()
    }
    return [{"number": r.report_no, "description": r.description, "area": r.area, "status": REPORT_WORDS[r.status],
             "outcome": DECLINE_WORDS.get(r.decline_code or "") if r.status == "DECLINED" else None,
             "response": r.response, "snag_number": snag_no.get(r.snag_id or "")}
            for r in reports.rows(s, p, account_id)]  # fmt: skip


def _remaining(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for b in blockers:
        if b["gate"] == "COMMERCIAL_CONDITION" and b["code"] in ("AMOUNT_DUE", "AMOUNT_OUTSTANDING"):
            words = "Payment due"
        else:
            words = READINESS_WORDS.get(b["gate"], FINAL_CHECKS)
        counts[words] = counts.get(words, 0) + 1
    return [{"label": k, "count": v} for k, v in counts.items()]


def _package(s: Session, p: Project) -> dict[str, Any] | None:
    pkgs = [x for x in handover.packages(s, p) if x.status in ("PREPARED", "COMPLETED")]
    if not pkgs:
        return None
    pkg = pkgs[-1]
    c = pkg.content or {}
    current = pkg.status == "PREPARED" and handover.staleness(s, p, pkg) is None
    can_ack = (current and pkg.acknowledged_on is None and p.status == "ACTIVE"
               and delivery_policy.customer_may("handover_acknowledgement"))  # fmt: skip
    return {
        "id": pkg.id, "number": pkg.package_no, "content_sha256": pkg.content_sha256,
        "status": "HANDED_OVER" if pkg.status == "COMPLETED" else ("READY_TO_REVIEW" if current else "BEING_UPDATED"),
        "work_completed": [{"label": w.get("label"), "finished_on": w.get("finished_on")}
                           for w in (c.get("work") or {}).get("completed") or []],
        "quality": {k: (c.get("quality") or {}).get(k) for k in ("checks_passed", "corrected_after_failure")},
        "snags": {"fixed_and_verified": (c.get("snags") or {}).get("fixed_and_verified"),
                  "open_minor": [{"number": x.get("number"), "title": x.get("title")}
                                 for x in (c.get("snags") or {}).get("open_non_blocking") or []]},
        "documents": [], "documents_note": "Handover documents are not shown in your portal yet. Your Veda Spaces "
        "contact will give them to you.",
        "warranty_note": "Warranty is as set out in your accepted quotation.",
        "acknowledged_on": clock.to_rfc3339(pkg.acknowledged_on) if pkg.acknowledged_on else None,
        "can_acknowledge": bool(can_ack),
    }  # fmt: skip


def project_view(s: Session, account_id: str, p: Project) -> dict[str, Any]:
    for table, cols in READS:  # the allow-list this view is built from
        for col in cols:
            assert C.column_class(table, col) in (C.SAFE, C.CUSTOMER_ACTION), (table, col)
    d = lifecycle.get(p.lifecycle_version)
    stage = d.stage(p.stage_code)
    checks = quality.checks(s, p)
    chains = quality.chains(checks)
    items = _work(s, p, checks)
    counts = {k: sum(1 for w in items if w["state"] == k) for k in (PV.COMPLETED, PV.IN_PROGRESS, PV.ACTION_REQUIRED,
                                                                    BLOCKED, PV.UPCOMING)}  # fmt: skip
    readiness = gates.handover_readiness(s, p)
    handover_state: dict[str, Any]
    if p.status == "HANDED_OVER":
        handover_state = {"state": PV.COMPLETED, "label": "Handed over",
                          "date": _day(p.handed_over_on.date()) if p.handed_over_on else None, "remaining": []}  # fmt: skip
    elif readiness["stage_reached"] and readiness["ready"]:
        handover_state = {"state": PV.IN_PROGRESS, "label": "Ready for handover", "date": None, "remaining": []}
    else:
        handover_state = {"state": PV.UPCOMING, "label": "Not ready for handover yet", "date": None,
                          "remaining": _remaining(readiness["blockers"])}  # fmt: skip
    return {
        "id": p.id, "status": "HANDED_OVER" if p.status == "HANDED_OVER" else "ACTIVE",
        "phase": {"code": stage.customer_stage, "label": PHASES.get(stage.customer_stage, "In progress")},
        "work": {"items": items, "counts": counts},
        "paused": _paused(s, p),
        "next_date": _next_date(s, p),
        "quality": {"checks_passed": sum(1 for c in chains if c[-1].result == "PASS"),
                    "being_corrected": sum(1 for c in chains if c[-1].result == "FAIL")},
        "snags": _snags(s, p),
        "reports": _reports(s, p, account_id),
        "can_report": p.status == "ACTIVE" and delivery_policy.customer_may("issue_reports"),
        "handover": handover_state,
        "package": _package(s, p),
    }  # fmt: skip


def view(s: Session, account_id: str, property_id: str) -> dict[str, Any] | None:
    if not enabled():
        return None
    return {"available": True, "projects": [project_view(s, account_id, p) for p in projects(s, property_id)]}
