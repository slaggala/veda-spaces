"""Stage gates (PLB-06, PLB-07, PLB-19, PLB-25, PLB-28): may this project move to its next stage, and if not, why.

``evaluate`` reads committed state only and never writes. It returns every gate that applies with its result and the
exact blockers: what stops the move, who must act (a responsible-party code), what the action is, and what it blocks.

Which gates apply:

- **Structural** (always): the target is the next stage of the pinned definition and the project is active, with no
  other transition awaiting approval (TRANSITION_ALLOWED); the baseline verifies and records every accepted variation
  (BASELINE_VALID); no open GATING blocker targets this stage or an earlier one (NO_GATING_BLOCKERS). For a HIGH-risk
  transition, the owner's decisions PLB-OD-01 (definition approved), PLB-OD-02 (its gates) and PLB-OD-03 (four-eyes)
  must be recorded (POLICY_RECORDED): until they are, it is refused (fail closed, PLB-07).
- **Configurable**: the owner's gates for the transition (PLB-OD-02), else the definition's strict defaults.

An informational blocker never stops anything (PLB-19); it is listed so staff see it.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from . import baseline, lifecycle, policy
from . import vocab as V
from .lifecycle import GATES, Definition, Transition
from .models import (
    Project,
    ProjectBlocker,
    ProjectChecklistItem,
    ProjectMember,
    ProjectMilestone,
    ProjectQcCheck,
    ProjectSiteReadiness,
    ProjectSnag,
    ProjectTransition,
)


def _b(gate: str, code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"gate": gate, "code": code, "message": message, **{k: v for k, v in extra.items() if v is not None}}


# --- policy reading ----------------------------------------------------------------------------------------------------
def lifecycle_approved(p: Project) -> bool:
    od = policy.decision("PLB-OD-01")
    return od is not None and od.lifecycle_version == p.lifecycle_version and od.lifecycle_sha256 == p.lifecycle_sha256


def owner_gates(p: Project, t: Transition) -> tuple[str, ...] | None:
    od = policy.decision("PLB-OD-02")
    if od is None or od.lifecycle_version != p.lifecycle_version:
        return None
    return od.transitions.get(t.key)


def four_eyes(p: Project, t: Transition) -> bool | None:
    od = policy.decision("PLB-OD-03")
    if od is None or od.lifecycle_version != p.lifecycle_version:
        return None
    return t.key in od.transitions


def optional_items(p: Project, stage: str) -> set[str]:
    od = policy.decision("PLB-OD-07")
    if od is None or od.lifecycle_version != p.lifecycle_version:
        return set()
    return set(od.items.get(stage, ()))


def required_qc(p: Project) -> tuple[str, ...]:
    od = policy.decision("PLB-OD-08")
    return tuple(od.required_categories) if od is not None else tuple(c for c in V.QC_CATEGORIES if c != "OTHER")


def handover_requirements() -> tuple[bool, bool, str]:
    od = policy.decision("PLB-OD-09")
    if od is None:
        return True, True, "DEFAULT"
    return od.acknowledgement_required, od.evidence_required, "OWNER_DECISION"


def required_owners(p: Project, d: Definition, stage: str) -> tuple[str, ...]:
    od = policy.decision("PLB-OD-04")
    if od is not None and stage in od.stages:
        return tuple(od.stages[stage])
    return (d.stage(stage).owner,)


# --- the gates ---------------------------------------------------------------------------------------------------------
def _checklist(s: Session, p: Project, frm: str) -> list[dict[str, Any]]:
    optional = optional_items(p, frm)
    d = lifecycle.get(p.lifecycle_version)
    labels = {i.code: i.label for i in d.stage(frm).checklist}
    rows = s.execute(sa.select(ProjectChecklistItem).where(ProjectChecklistItem.project_id == p.id,
                                                           ProjectChecklistItem.stage_code == frm)).scalars()  # fmt: skip
    return [_b("CHECKLIST_COMPLETE", "CHECKLIST_ITEM_OPEN", f"Checklist item not complete: {labels.get(r.item_code, r.item_code)}.",
               responsible_party="VEDA", entity={"type": "checklist_item", "id": r.id}, item_code=r.item_code)
            for r in rows if r.state == "OPEN" and r.item_code not in optional]  # fmt: skip


def owner_eligible(s: Session, m: ProjectMember) -> bool:
    """S1: whether an assigned owner can still act, re-read from the authoritative account and grants: an active person
    who still holds project.view and the responsibility's capability. The assignment itself is never removed here."""
    from veda.platform.identity.models import User
    from veda.platform.rbac.resolver import load_grants

    from .permissions import RESPONSIBILITY_CAPABILITY

    u = s.get(User, m.user_id)
    if u is None or u.is_deleted or u.status != "ACTIVE" or u.user_type != "HUMAN":
        return False
    granted = load_grants(s, u.id).granted
    return (
        granted.get("project.view") is not None and granted.get(RESPONSIBILITY_CAPABILITY[m.responsibility]) is not None
    )


def _owners(s: Session, p: Project, d: Definition, to: str) -> list[dict[str, Any]]:
    holders = {m.responsibility: m for m in s.execute(sa.select(ProjectMember).where(
        ProjectMember.project_id == p.id, ProjectMember.is_active == sa.true(),
        ProjectMember.responsibility != "MEMBER")).scalars()}  # fmt: skip
    out = []
    for r in required_owners(p, d, to):
        m = holders.get(r)
        if m is None:
            out.append(_b("OWNER_ASSIGNED", "OWNER_MISSING", f"No {r.lower()} owner is assigned for "
                          f"{d.stage(to).label.lower()}.", responsible_party="VEDA", responsibility=r))  # fmt: skip
        elif not owner_eligible(s, m):
            out.append(_b("OWNER_ASSIGNED", "OWNER_INELIGIBLE", f"The {r.lower()} owner can no longer act on this "
                          "project (account not active, or the capability was withdrawn); reassign the responsibility.",
                          responsible_party="VEDA", responsibility=r, entity={"type": "member", "id": m.id}))  # fmt: skip
    return out


def _site(s: Session, p: Project) -> list[dict[str, Any]]:
    rows = list(s.execute(sa.select(ProjectSiteReadiness).where(ProjectSiteReadiness.project_id == p.id)
                          .order_by(ProjectSiteReadiness.kind, ProjectSiteReadiness.item_code)).scalars())  # fmt: skip
    if not rows:
        return [_b("SITE_READY", "SITE_READINESS_NOT_ASSESSED", "No site-readiness item is recorded for this project.",
                   responsible_party="VEDA")]  # fmt: skip
    return [_b("SITE_READY", f"SITE_{r.status}", f"Site readiness {r.category.lower().replace('_', ' ')} is "
               f"{r.status.lower().replace('_', ' ')}.", responsible_party=r.responsible_party,
               entity={"type": "site_readiness", "id": r.id}, item_code=r.item_code)
            for r in rows if r.status not in V.READINESS_SATISFIED]  # fmt: skip


def _variations(s: Session, p: Project) -> list[dict[str, Any]]:
    from veda.modules.mtq_commercial import quotations

    return [_b("VARIATIONS_CLOSED", "VARIATION_OPEN", f"Variation {quotations.number_label(q)} is "
               f"{q.status.lower().replace('_', ' ')}; it must be accepted or closed through the commercial route.",
               responsible_party="CUSTOMER" if q.status == "ISSUED" else "VEDA",
               entity={"type": "quotation", "id": q.id})
            for q in baseline.open_variations(s, p.quotation_number)]  # fmt: skip


def _milestones(s: Session, p: Project, frm: str) -> list[dict[str, Any]]:
    rows = s.execute(sa.select(ProjectMilestone).where(ProjectMilestone.project_id == p.id,
                                                       ProjectMilestone.stage_code == frm)).scalars()  # fmt: skip
    return [_b("MILESTONES_COMPLETE", "MILESTONE_OPEN", f"A {m.milestone_code.lower().replace('_', ' ')} milestone of "
               f"this stage is {m.status.lower().replace('_', ' ')}.",
               responsible_party="VEDA", entity={"type": "milestone", "id": m.id})
            for m in rows if m.status not in V.MILESTONE_CLOSED]  # fmt: skip


def latest_qc(s: Session, p: Project) -> dict[str, ProjectQcCheck]:
    out: dict[str, ProjectQcCheck] = {}
    for r in s.execute(sa.select(ProjectQcCheck).where(ProjectQcCheck.project_id == p.id)
                       .order_by(ProjectQcCheck.created_on, ProjectQcCheck.id)).scalars():  # fmt: skip
        out[r.category] = r
    return out


def _qc(s: Session, p: Project, *, passed: bool) -> list[dict[str, Any]]:
    gate = "QC_PASSED" if passed else "QC_RECORDED"
    latest = latest_qc(s, p)
    out = []
    for cat in required_qc(p):
        r = latest.get(cat)
        label = cat.lower().replace("_", " ")
        if r is None or r.result == "TO_BE_CONFIRMED":
            out.append(_b(gate, "QC_NOT_RECORDED", f"Quality check {label} has no result.", responsible_party="VEDA",
                          category=cat))  # fmt: skip
        elif passed and r.result == "FAIL":
            out.append(_b(gate, "QC_FAILED", f"Quality check {label} failed; fix and recheck it.",
                          responsible_party="VEDA", entity={"type": "qc_check", "id": r.id}, category=cat))  # fmt: skip
    if passed:  # a failed result in any category (required or not) is never ready for handover
        out += [_b(gate, "QC_FAILED", f"Quality check {cat.lower().replace('_', ' ')} failed; fix and recheck it.",
                   responsible_party="VEDA", entity={"type": "qc_check", "id": r.id}, category=cat)
                for cat, r in latest.items() if r.result == "FAIL" and cat not in required_qc(p)]  # fmt: skip
    return out


def _snags(s: Session, p: Project) -> list[dict[str, Any]]:
    rows = s.execute(sa.select(ProjectSnag).where(ProjectSnag.project_id == p.id, ProjectSnag.is_blocking == sa.true(),
                                                  ProjectSnag.status.in_(V.SNAG_OPEN))
                     .order_by(ProjectSnag.snag_no)).scalars()  # fmt: skip
    return [_b("SNAGS_RESOLVED", "SNAG_OPEN", f"Snag {n.snag_no} ({n.category.lower().replace('_', ' ')}) is "
               f"{n.status.lower().replace('_', ' ')}.", responsible_party=n.responsible_party,
               entity={"type": "snag", "id": n.id})
            for n in rows]  # fmt: skip


def _handover(s: Session, p: Project, handover: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    """None: evaluated only when the handover is completed (its evidence is given with it)."""
    if handover is None:
        return None
    ack, evidence, _ = handover_requirements()
    out = []
    if ack and not (handover.get("acknowledgement_reference") or "").strip():
        out.append(_b("HANDOVER_EVIDENCE", "ACKNOWLEDGEMENT_MISSING", "The customer's handover acknowledgement "
                      "reference is required.", responsible_party="VEDA"))  # fmt: skip
    if evidence and not handover.get("evidence_attachment_id"):
        out.append(_b("HANDOVER_EVIDENCE", "EVIDENCE_MISSING", "Handover evidence (a scanned attachment of this "
                      "project) is required.", responsible_party="VEDA"))  # fmt: skip
    return out


def gating_blockers(s: Session, p: Project, d: Definition, to: str) -> list[ProjectBlocker]:
    seq = d.sequence(to)
    rows = s.execute(sa.select(ProjectBlocker).where(ProjectBlocker.project_id == p.id,
                                                     ProjectBlocker.impact == "GATING",
                                                     ProjectBlocker.status.in_(V.BLOCKER_OPEN))
                     .order_by(ProjectBlocker.created_on)).scalars()  # fmt: skip
    return [b for b in rows if b.blocks_stage_code and d.sequence(b.blocks_stage_code) <= seq]


def _gating(s: Session, p: Project, d: Definition, to: str) -> list[dict[str, Any]]:
    # recorded evaluations carry codes, never staff text: the title is shown from the blocker itself
    return [_b("NO_GATING_BLOCKERS", "GATING_BLOCKER_OPEN", f"An open gating blocker ({b.category.lower().replace('_', ' ')}"
               f") stops {d.stage(b.blocks_stage_code or to).label.lower()}.",
               responsible_party=b.responsible_party, entity={"type": "blocker", "id": b.id},
               blocks=b.blocks_stage_code, category=b.category)
            for b in gating_blockers(s, p, d, to)]  # fmt: skip


def pending(s: Session, p: Project) -> ProjectTransition | None:
    return s.execute(sa.select(ProjectTransition).where(ProjectTransition.project_id == p.id,
                                                        ProjectTransition.outcome == "AWAITING_APPROVAL")
                     ).scalar_one_or_none()  # fmt: skip


# --- evaluation --------------------------------------------------------------------------------------------------------
def evaluate(s: Session, p: Project, to: str | None = None, *, command: str = "STAGE",
             handover: dict[str, Any] | None = None, approving: ProjectTransition | None = None) -> dict[str, Any]:  # fmt: skip
    """The gate evaluation of moving ``p`` to ``to`` (default: its next stage). Read-only."""
    d = lifecycle.get(p.lifecycle_version)
    frm = p.stage_code
    t = d.next_transition(frm) if to is None else d.transition(frm, to)
    to = t.to if t is not None else to
    gates: list[dict[str, Any]] = []

    def gate(code: str, source: str, found: list[dict[str, Any]] | None) -> None:
        gates.append({"code": code, "label": GATES[code], "source": source,
                      "passed": None if found is None else not found, "blockers": found or []})  # fmt: skip

    allowed: list[dict[str, Any]] = []
    if p.status != "ACTIVE":
        allowed.append(_b("TRANSITION_ALLOWED", "PROJECT_NOT_ACTIVE", f"{p.project_number} is handed over."))
    elif t is None:
        allowed.append(_b("TRANSITION_ALLOWED", "NOT_NEXT_STAGE", f"{to or 'That stage'} is not the next stage after "
                          f"{d.stage(frm).label.lower()}; stages are completed in order."))  # fmt: skip
    elif t.command != command:
        allowed.append(_b("TRANSITION_ALLOWED", "USE_HANDOVER" if t.command == "HANDOVER" else "NOT_A_HANDOVER",
                          "The handover is completed with its evidence through Complete handover."
                          if t.command == "HANDOVER" else "Only the last stage is reached by a handover."))  # fmt: skip
    waiting = pending(s, p)
    if waiting is not None and (approving is None or waiting.id != approving.id):
        allowed.append(_b("TRANSITION_ALLOWED", "TRANSITION_AWAITING_APPROVAL", "Another transition is waiting for "
                          "approval; approve, reject or withdraw it first.",
                          entity={"type": "transition", "id": waiting.id}))  # fmt: skip
    gate("TRANSITION_ALLOWED", "STRUCTURAL", allowed)
    gate("BASELINE_VALID", "STRUCTURAL", [_b("BASELINE_VALID", x["code"], x["message"], responsible_party="VEDA")
                                          for x in baseline.problems(s, p)])  # fmt: skip
    if t is None:
        return _result(p, d, frm, to, None, gates, False)
    gate("NO_GATING_BLOCKERS", "STRUCTURAL", _gating(s, p, d, t.to))
    chosen = owner_gates(p, t)
    approval = four_eyes(p, t)
    if t.risk == "HIGH":
        missing = []
        if not lifecycle_approved(p):
            missing.append(_b("POLICY_RECORDED", "OWNER_DECISION_REQUIRED", **_required("PLB-OD-01")))
        if chosen is None:
            missing.append(_b("POLICY_RECORDED", "OWNER_DECISION_REQUIRED", **_required("PLB-OD-02", t.key)))
        if approval is None:
            missing.append(_b("POLICY_RECORDED", "OWNER_DECISION_REQUIRED", **_required("PLB-OD-03", t.key)))
        gate("POLICY_RECORDED", "STRUCTURAL", missing)
    source = "OWNER_DECISION" if chosen is not None else "DEFAULT"
    for code in chosen if chosen is not None else t.default_gates:
        found = {
            "CHECKLIST_COMPLETE": lambda: _checklist(s, p, frm),
            "OWNER_ASSIGNED": lambda: _owners(s, p, d, t.to),
            "SITE_READY": lambda: _site(s, p),
            "VARIATIONS_CLOSED": lambda: _variations(s, p),
            "MILESTONES_COMPLETE": lambda: _milestones(s, p, frm),
            "QC_RECORDED": lambda: _qc(s, p, passed=False),
            "QC_PASSED": lambda: _qc(s, p, passed=True),
            "SNAGS_RESOLVED": lambda: _snags(s, p),
            "HANDOVER_EVIDENCE": lambda: _handover(s, p, handover),
        }[code]()
        gate(code, source, found)
    return _result(p, d, frm, t.to, t, gates, bool(approval))


def next_evaluation(s: Session, p: Project) -> dict[str, Any] | None:
    """The evaluation of the project's next step, through that step's own command (None once handed over)."""
    if p.status != "ACTIVE":
        return None
    t = lifecycle.get(p.lifecycle_version).next_transition(p.stage_code)
    return evaluate(s, p, command=t.command if t is not None else "STAGE")


def _required(code: str, key: str | None = None) -> dict[str, Any]:
    r = policy.required(code)
    return {"message": r["message"] + (f" ({key})" if key else ""), "decision": code, "responsible_party": "VEDA"}


def _result(p: Project, d: Definition, frm: str, to: str | None, t: Transition | None, gates: list[dict[str, Any]],
            approval: bool) -> dict[str, Any]:  # fmt: skip
    blockers = [b for g in gates for b in g["blockers"]]
    return {
        "from": frm, "to": to, "transition": t.key if t else None, "risk": t.risk if t else None,
        "command": t.command if t else None,
        "lifecycle": {"version": d.version, "sha256": d.sha256, "status": "APPROVED" if lifecycle_approved(p)
                      else d.status},
        "policy": {"version": policy.current().version, "sha256": policy.sha256()},
        "independent_approval": approval, "gates": gates, "blockers": blockers,
        "allowed": not blockers,
    }  # fmt: skip


def handover_readiness(s: Session, p: Project) -> dict[str, Any]:
    """PLB-28: what still stands between the project and its handover, whatever its current stage: the configurable
    gates of the two handover transitions plus the structural ones (evidence is given at the handover itself)."""
    d = lifecycle.get(p.lifecycle_version)
    if p.status == "HANDED_OVER":
        return {"ready": True, "handed_over": True, "blockers": []}
    found: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for t in (d.transition("SNAGGING", "READY_FOR_HANDOVER"), d.transition("READY_FOR_HANDOVER", "HANDED_OVER")):
        if t is None:
            continue
        chosen = owner_gates(p, t)
        for code in chosen if chosen is not None else t.default_gates:
            res = {
                "QC_PASSED": lambda: _qc(s, p, passed=True),
                "SNAGS_RESOLVED": lambda: _snags(s, p),
                "VARIATIONS_CLOSED": lambda: _variations(s, p),
            }.get(code, lambda: [])()
            for b in res:
                k = (b["code"], str(b.get("entity")), b.get("category"))
                if k not in seen:
                    seen.add(k)
                    found.append(b)
    found += _gating(s, p, d, "HANDED_OVER")
    found += [_b("BASELINE_VALID", x["code"], x["message"]) for x in baseline.problems(s, p)]
    stage_open = d.sequence(p.stage_code) < d.sequence("READY_FOR_HANDOVER")
    return {"ready": not found and not stage_open, "handed_over": False, "stage_reached": not stage_open,
            "blockers": found}  # fmt: skip
