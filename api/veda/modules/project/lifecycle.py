"""The project lifecycle definition (PLB-04, PLB-05, PLB-15): stages, their checklists and the allowed transitions.

A definition is reviewed code, not user configuration: there is no workflow editor (PLB-04). Each definition has a
version and a SHA-256 over its canonical form; a project pins the version and digest it was created under, and is
always interpreted with that definition. A change to stages, checklists or transitions is a **new** version added
here; earlier versions stay, so a completed project is never reinterpreted by a later edit (PLB-05).

The labels, checklist items and default gates below are a PROPOSAL derived from the workstream instruction
(PLB-21 … PLB-29), not Veda policy: owner decision PLB-OD-01 approves a definition version, and until it does the
workspace shows the definition as PROPOSED and high-risk transitions stay refused (``gates.py``).

Transitions only move forward, one stage at a time. Each has a risk class: HIGH for the transitions the instruction
names as high-risk (scope freeze, production release, start of installation, ready for handover, handover; PLB-34),
STANDARD otherwise. Each has **default gates**, the strictest reasonable set, applied while the owner has not decided
the transition's gates (PLB-OD-02); an owner decision replaces the configurable gates, never the structural ones.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from veda.kernel.errors import ApiError
from veda.kernel.jcs import canonical_bytes

# --- gates -------------------------------------------------------------------------------------------------------------
# Structural gates always apply (they are the lifecycle's own invariants, not policy).
STRUCTURAL_GATES = {
    "TRANSITION_ALLOWED": "The target is the next stage of this project's lifecycle definition",
    "BASELINE_VALID": "The project's commercial baseline verifies and records every accepted variation",
    "NO_GATING_BLOCKERS": "No open gating blocker stops this stage or an earlier one",
    "POLICY_RECORDED": "A HIGH-risk transition needs the owner's lifecycle, gate and approval decisions recorded",
}
# Configurable gates: the owner decides which apply to each transition (PLB-OD-02); until then the defaults below.
CONFIGURABLE_GATES = {
    "CHECKLIST_COMPLETE": "Every required checklist item of the current stage is done or marked not applicable",
    "OWNER_ASSIGNED": "The responsibility that owns the next stage has an active owner",
    "SITE_READY": "Every site-readiness item is ready or not applicable",
    "VARIATIONS_CLOSED": "No variation (change order) on the quotation is still open",
    "MILESTONES_COMPLETE": "Every milestone of the current stage is completed, cancelled or not applicable",
    "QC_RECORDED": "Every required quality-check category has a result",
    "QC_PASSED": "Every required quality-check category's latest result is PASS or NOT_APPLICABLE",
    "SNAGS_RESOLVED": "No blocking snag is open",
    "HANDOVER_EVIDENCE": "The handover acknowledgement and evidence the policy requires are given",
}
GATES = {**STRUCTURAL_GATES, **CONFIGURABLE_GATES}


@dataclass(frozen=True)
class ChecklistItem:
    code: str
    label: str
    ref: str  # the instruction paragraph the item is derived from


@dataclass(frozen=True)
class Stage:
    code: str
    label: str
    description: str
    customer_stage: str  # the Customer Promise stage code a future portal may show (customer_pack.STAGES)
    owner: str  # the responsibility that owns the work of this stage (vocab.RESPONSIBILITIES)
    checklist: tuple[ChecklistItem, ...] = ()
    terminal: bool = False


@dataclass(frozen=True)
class Transition:
    frm: str
    to: str
    risk: str  # STANDARD | HIGH
    default_gates: tuple[str, ...]
    command: str = "STAGE"  # STAGE (request a transition) | HANDOVER (complete the handover, PLB-29)

    @property
    def key(self) -> str:
        return f"{self.frm}>{self.to}"


@dataclass(frozen=True)
class Definition:
    version: str
    status: str  # PROPOSED until owner decision PLB-OD-01 approves this version and digest
    stages: tuple[Stage, ...]
    transitions: tuple[Transition, ...]
    _by_code: dict[str, Stage] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_by_code", {s.code: s for s in self.stages})

    def stage(self, code: str) -> Stage:
        found = self._by_code.get(code)
        if found is None:
            raise ApiError(422, "VALIDATION_FAILED", f"{code} is not a stage of lifecycle {self.version}.")
        return found

    def sequence(self, code: str) -> int:
        return [s.code for s in self.stages].index(code) + 1

    def next_transition(self, frm: str) -> Transition | None:
        return next((t for t in self.transitions if t.frm == frm), None)

    def transition(self, frm: str, to: str) -> Transition | None:
        return next((t for t in self.transitions if t.frm == frm and t.to == to), None)

    def document(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "stages": [{"code": s.code, "label": s.label, "description": s.description,
                        "customer_stage": s.customer_stage, "owner": s.owner, "terminal": s.terminal,
                        "checklist": [{"code": i.code, "label": i.label, "ref": i.ref} for i in s.checklist]}
                       for s in self.stages],
            "transitions": [{"from": t.frm, "to": t.to, "risk": t.risk, "default_gates": list(t.default_gates),
                             "command": t.command} for t in self.transitions],
        }  # fmt: skip

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical_bytes(self.document())).hexdigest()


def _items(*rows: tuple[str, str, str]) -> tuple[ChecklistItem, ...]:
    return tuple(ChecklistItem(code, label, ref) for code, label, ref in rows)


_C, _O, _M = "CHECKLIST_COMPLETE", "OWNER_ASSIGNED", "MILESTONES_COMPLETE"

PLB_2026_10_1 = Definition(
    version="PLB-2026.10.1",
    status="PROPOSED",
    stages=(
        Stage("BOOKED", "Booked", "The accepted commercial baseline is booked as a project.",
              "VEDA_CONFIRMATION", "PROJECT",
              _items(("BASELINE_REVIEWED", "Accepted commercial baseline reviewed by the project team", "PLB-03"),
                     ("CUSTOMER_PROMISE_REVIEWED", "Customer Promise commitments in the accepted quotation reviewed",
                      "PLB-16"))),
        Stage("DESIGN_FINALISATION", "Design finalisation", "Design decisions and approvals are completed.",
              "SCOPE_DESIGN_FINALISATION", "DESIGN",
              _items(("DESIGN_DECISIONS_COMPLETE", "Design decisions complete", "PLB-21"),
                     ("DESIGN_APPROVALS_RECORDED", "Required design approvals recorded", "PLB-21"),
                     ("APPROVED_DESIGN_REFERENCE", "Approved design reference recorded", "PLB-21"))),
        Stage("SCOPE_FROZEN", "Scope frozen", "The execution scope is the accepted (or varied) commercial baseline.",
              "SCOPE_DESIGN_FINALISATION", "PROJECT",
              _items(("SCOPE_MATCHES_BASELINE", "Execution scope matches the current effective commercial baseline",
                      "PLB-22"),
                     ("DESIGN_SCOPE_RECONCILED", "Design reconciled with the accepted scope (no unpriced additions)",
                      "PLB-22"))),
        Stage("SITE_READINESS", "Site readiness", "The site satisfies what production and installation depend on.",
              "SITE_READINESS", "SITE",
              _items(("SITE_READINESS_REVIEWED", "Site readiness items reviewed with the customer", "PLB-17"),)),
        Stage("PRODUCTION_READINESS", "Production readiness", "Everything needed to release work into production.",
              "PRODUCTION_READINESS", "PROJECT",
              _items(("DESIGN_FROZEN", "Design frozen", "PLB-23"),
                     ("DIMENSIONS_VERIFIED", "Dimensions verified", "PLB-23"),
                     ("MATERIAL_DECISIONS_COMPLETE", "Material and specification decisions complete", "PLB-23"))),
        Stage("IN_PRODUCTION", "In production", "Work is released to production (high-level status only).",
              "PRODUCTION_READINESS", "PROJECT",
              _items(("PRODUCTION_COMPLETE", "Production complete for installation", "PLB-24"),)),
        Stage("READY_FOR_INSTALLATION", "Ready for installation", "Production is complete; installation is prepared.",
              "INSTALLATION", "SITE",
              _items(("INSTALLATION_ACCESS_CONFIRMED", "Site access for installation confirmed", "PLB-25"),
                     ("INSTALLATION_DATE_CONFIRMED", "Installation date confirmed with the customer", "PLB-25"))),
        Stage("INSTALLATION", "Installation", "Installation on site.", "INSTALLATION", "SITE",
              _items(("INSTALLATION_COMPLETE", "Installation complete", "PLB-25"),)),
        Stage("QUALITY_CHECK", "Quality check", "Veda's quality check of the installed work.", "INSTALLATION",
              "QUALITY", _items(("QC_INSPECTION_DONE", "Quality inspection carried out", "PLB-26"),)),
        Stage("SNAGGING", "Snagging", "Snags found are fixed and rechecked.", "JOINT_INSPECTION", "QUALITY",
              _items(("SNAG_WALKTHROUGH_DONE", "Snag walkthrough done", "PLB-27"),)),
        Stage("READY_FOR_HANDOVER", "Ready for handover", "Every handover prerequisite is satisfied.",
              "JOINT_INSPECTION", "HANDOVER",
              _items(("HANDOVER_DOCUMENTS_READY", "Handover documents prepared", "PLB-28"),
                     ("HANDOVER_WALKTHROUGH_SCHEDULED", "Joint handover walkthrough scheduled", "PLB-28"))),
        Stage("HANDED_OVER", "Handed over", "The project is handed over to the customer.", "HANDOVER", "HANDOVER",
              terminal=True),
    ),
    transitions=(
        Transition("BOOKED", "DESIGN_FINALISATION", "STANDARD", (_C, _O, _M)),
        Transition("DESIGN_FINALISATION", "SCOPE_FROZEN", "HIGH", (_C, _O, "VARIATIONS_CLOSED", _M)),
        Transition("SCOPE_FROZEN", "SITE_READINESS", "STANDARD", (_C, _O, _M)),
        Transition("SITE_READINESS", "PRODUCTION_READINESS", "STANDARD", (_C, _O, "SITE_READY", _M)),
        Transition("PRODUCTION_READINESS", "IN_PRODUCTION", "HIGH", (_C, _O, "VARIATIONS_CLOSED", "SITE_READY", _M)),
        Transition("IN_PRODUCTION", "READY_FOR_INSTALLATION", "STANDARD", (_C, _O, _M)),
        Transition("READY_FOR_INSTALLATION", "INSTALLATION", "HIGH", (_C, _O, "SITE_READY", "VARIATIONS_CLOSED", _M)),
        Transition("INSTALLATION", "QUALITY_CHECK", "STANDARD", (_C, _O, _M)),
        Transition("QUALITY_CHECK", "SNAGGING", "STANDARD", (_C, _O, "QC_RECORDED", _M)),
        Transition("SNAGGING", "READY_FOR_HANDOVER", "HIGH",
                   (_C, _O, "QC_PASSED", "SNAGS_RESOLVED", "VARIATIONS_CLOSED", _M)),
        Transition("READY_FOR_HANDOVER", "HANDED_OVER", "HIGH",
                   (_C, "QC_PASSED", "SNAGS_RESOLVED", "VARIATIONS_CLOSED", "HANDOVER_EVIDENCE", _M),
                   command="HANDOVER"),
    ),
)  # fmt: skip

DEFINITIONS: dict[str, Definition] = {PLB_2026_10_1.version: PLB_2026_10_1}
CURRENT = PLB_2026_10_1.version


def current() -> Definition:
    return DEFINITIONS[CURRENT]


def get(version: str) -> Definition:
    found = DEFINITIONS.get(version)
    if found is None:  # a pinned version that is no longer in the code: refuse rather than reinterpret
        raise ApiError(409, "LIFECYCLE_DEFINITION_UNKNOWN", f"Lifecycle definition {version} is not available.")
    return found


def validate() -> list[str]:
    """Structural rules every definition obeys (asserted by the unit tests)."""
    from veda.modules.mtq_commercial import customer_pack as CP

    from . import vocab as V

    problems: list[str] = []
    for d in DEFINITIONS.values():
        codes = [s.code for s in d.stages]
        if len(set(codes)) != len(codes) or any(c not in V.STAGES for c in codes):
            problems.append(f"{d.version}: stage codes must be unique and in vocab.STAGES")
        if [s for s in d.stages if s.terminal] != [d.stages[-1]]:
            problems.append(f"{d.version}: exactly the last stage is terminal")
        for a, b in zip(codes, codes[1:], strict=False):
            if d.transition(a, b) is None:
                problems.append(f"{d.version}: no transition {a}>{b}")
        for t in d.transitions:
            if d.sequence(t.to) != d.sequence(t.frm) + 1:
                problems.append(f"{d.version}: {t.key} is not a forward step of one stage")
            if t.risk not in ("STANDARD", "HIGH") or any(g not in CONFIGURABLE_GATES for g in t.default_gates):
                problems.append(f"{d.version}: {t.key} has an unknown risk or gate")
        for s in d.stages:
            if s.customer_stage not in CP.STAGES:
                problems.append(
                    f"{d.version}: {s.code} customer stage {s.customer_stage} is not a Customer Promise stage"
                )
            if s.owner not in V.OWNER_RESPONSIBILITIES:
                problems.append(f"{d.version}: {s.code} owner {s.owner} is not an ownership responsibility")
            item_codes = [i.code for i in s.checklist]
            if len(set(item_codes)) != len(item_codes):
                problems.append(f"{d.version}: {s.code} has duplicate checklist items")
    return problems
