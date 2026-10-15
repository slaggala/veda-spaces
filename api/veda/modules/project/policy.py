"""The owner's project-lifecycle decisions (PLB-51), as one versioned record: ``fixtures/lifecycle-policy.json``.

Every slot is null: nothing has been decided. A null slot never becomes a decision. The engine reads these slots and,
while one is null, behaves as follows (the strict default fails closed; nothing is invented):

| Slot | Governs | While null |
|---|---|---|
| PLB-OD-01 | The lifecycle definition (stages, checklists, transitions) approved: version + digest | Shown PROPOSED; HIGH-risk transitions refused |
| PLB-OD-02 | Mandatory gates per transition (incl. scope-freeze, production-, installation-, handover-readiness) | The definition's strict default gates; HIGH-risk transitions refused |
| PLB-OD-03 | Transitions that need an independent (four-eyes) approval | No approval step on STANDARD transitions; HIGH-risk transitions refused |
| PLB-OD-04 | Ownership responsibilities required before a stage is entered | The stage's owning responsibility must be assigned |
| PLB-OD-07 | Checklist items that are optional | Every item is required (done, or not applicable with reason and permission) |
| PLB-OD-08 | Quality-check categories required | Every category except OTHER |
| PLB-OD-09 | Handover evidence required | Both an acknowledgement reference and an evidence attachment |

The other slots (PLB-OD-05, 06, 10 … 13) are recorded decisions the code does not read yet: milestone definitions,
which blockers are gating and who classifies them, how a project is triggered from acceptance, use of THIRD_PARTY
responsibility, rework/cancellation/on-hold, and customer-promised dates. They are listed so the register is
complete; see docs/implementation/project-lifecycle/PLB-owner-decisions.md.

Tests may install a record marked SYNTHETIC (``install_for_tests``); the loader refuses that marker anywhere but the
test environment, so a synthetic decision can never reach staging or production.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from veda.config import settings

from . import lifecycle as L
from . import vocab as V

FIXTURE = Path(__file__).with_name("fixtures") / "lifecycle-policy.json"
SYNTHETIC = "SYNTHETIC_TEST_ONLY"
LABELS = {
    "PLB-OD-01": "exact lifecycle stages (the lifecycle definition approved)",
    "PLB-OD-02": "mandatory stage gates per transition",
    "PLB-OD-03": "stage transitions that need an independent (four-eyes) approval",
    "PLB-OD-04": "required project roles (ownership responsibilities per stage)",
    "PLB-OD-05": "milestone definitions",
    "PLB-OD-06": "which blockers are gating, and who may classify them",
    "PLB-OD-07": "checklist items that are optional",
    "PLB-OD-08": "quality-check requirements",
    "PLB-OD-09": "handover evidence requirements",
    "PLB-OD-10": "how a project is created from an accepted quotation (trigger and acceptance evidence)",
    "PLB-OD-11": "use of the THIRD_PARTY responsibility",
    "PLB-OD-12": "rework (backward transitions), cancellation and on-hold",
    "PLB-OD-13": "who may record a customer-promised date and how it is governed",
}
CONSUMED = ("PLB-OD-01", "PLB-OD-02", "PLB-OD-03", "PLB-OD-04", "PLB-OD-07", "PLB-OD-08", "PLB-OD-09")
Hex64 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
TransitionKey = Annotated[str, Field(pattern=r"^[A-Z_]+>[A-Z_]+$")]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _member(values: tuple[str, ...]):
    def check(value: str) -> str:
        if value not in values:
            raise ValueError(f"{value} is not one of {', '.join(values)}")
        return value

    return check


class LifecycleApproval(_Closed):  # PLB-OD-01
    lifecycle_version: str
    lifecycle_sha256: Hex64
    reference: Annotated[str, Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def _known(self):
        d = L.DEFINITIONS.get(self.lifecycle_version)
        if d is None or d.sha256 != self.lifecycle_sha256:
            raise ValueError("PLB-OD-01 must name a lifecycle definition version and its exact digest")
        return self


class TransitionGates(_Closed):  # PLB-OD-02
    lifecycle_version: str
    transitions: dict[TransitionKey, tuple[str, ...]]

    @model_validator(mode="after")
    def _known(self):
        d = L.DEFINITIONS.get(self.lifecycle_version)
        if d is None:
            raise ValueError("PLB-OD-02 names an unknown lifecycle definition")
        keys = {t.key for t in d.transitions}
        for key, gates in self.transitions.items():
            if key not in keys or any(g not in L.CONFIGURABLE_GATES for g in gates):
                raise ValueError(f"PLB-OD-02: {key} is not a transition or names an unknown gate")
        return self


class IndependentApproval(_Closed):  # PLB-OD-03
    lifecycle_version: str
    transitions: tuple[TransitionKey, ...]

    @model_validator(mode="after")
    def _known(self):
        d = L.DEFINITIONS.get(self.lifecycle_version)
        if d is None or any(k not in {t.key for t in d.transitions} for k in self.transitions):
            raise ValueError("PLB-OD-03 names an unknown lifecycle definition or transition")
        return self


class RequiredRoles(_Closed):  # PLB-OD-04
    stages: dict[str, tuple[Annotated[str, AfterValidator(_member(V.OWNER_RESPONSIBILITIES))], ...]]

    @model_validator(mode="after")
    def _known(self):
        if any(s not in V.STAGES for s in self.stages):
            raise ValueError("PLB-OD-04 names an unknown stage")
        return self


class OptionalItems(_Closed):  # PLB-OD-07
    lifecycle_version: str
    items: dict[str, tuple[str, ...]]  # stage code -> optional checklist item codes

    @model_validator(mode="after")
    def _known(self):
        d = L.DEFINITIONS.get(self.lifecycle_version)
        if d is None:
            raise ValueError("PLB-OD-07 names an unknown lifecycle definition")
        for stage, codes in self.items.items():
            known = {i.code for i in d.stage(stage).checklist}
            if any(c not in known for c in codes):
                raise ValueError(f"PLB-OD-07: unknown checklist item in {stage}")
        return self


class QcRequirements(_Closed):  # PLB-OD-08
    required_categories: tuple[Annotated[str, AfterValidator(_member(V.QC_CATEGORIES))], ...]


class HandoverEvidence(_Closed):  # PLB-OD-09
    acknowledgement_required: bool
    evidence_required: bool


class Recorded(_Closed):  # the decisions the engine does not read yet: what was decided, and where
    decision: Annotated[str, Field(min_length=1, max_length=2000)]
    reference: Annotated[str, Field(min_length=1, max_length=200)]


SHAPES: dict[str, type[BaseModel]] = {
    "PLB-OD-01": LifecycleApproval,
    "PLB-OD-02": TransitionGates,
    "PLB-OD-03": IndependentApproval,
    "PLB-OD-04": RequiredRoles,
    "PLB-OD-05": Recorded,
    "PLB-OD-06": Recorded,
    "PLB-OD-07": OptionalItems,
    "PLB-OD-08": QcRequirements,
    "PLB-OD-09": HandoverEvidence,
    "PLB-OD-10": Recorded,
    "PLB-OD-11": Recorded,
    "PLB-OD-12": Recorded,
    "PLB-OD-13": Recorded,
}


class Policy(_Closed):
    schema_: Literal["veda.project.lifecycle-policy/1"] = Field(alias="schema")
    version: Annotated[str, Field(min_length=1, max_length=40)]
    status: str
    note: str
    decisions: dict[str, dict[str, Any] | None]

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @model_validator(mode="after")
    def _shapes(self):
        if set(self.decisions) != set(SHAPES):
            raise ValueError(f"decisions must name exactly {sorted(SHAPES)}")
        for code, value in self.decisions.items():
            if value is not None:
                SHAPES[code].model_validate(value)
        return self

    def get(self, code: str) -> Any:
        value = self.decisions.get(code)
        return None if value is None else SHAPES[code].model_validate(value)


_override: tuple[Policy, str] | None = None


@lru_cache(maxsize=1)
def _fixture() -> tuple[Policy, str]:
    raw = FIXTURE.read_bytes()
    return Policy.model_validate(json.loads(raw)), hashlib.sha256(raw).hexdigest()


def _current() -> tuple[Policy, str]:
    found = _override if _override is not None else _fixture()
    if found[0].status == SYNTHETIC and settings().env != "test":
        raise RuntimeError("a SYNTHETIC lifecycle policy is refused outside the test environment")
    return found


def current() -> Policy:
    return _current()[0]


def sha256() -> str:
    return _current()[1]


def decision(code: str) -> Any:
    return current().get(code)


def required(code: str, **extra: Any) -> dict[str, Any]:
    """The blocker for an undecided slot the action depends on."""
    return {"code": "OWNER_DECISION_REQUIRED", "decision": code,
            "message": f"Owner decision {code} ({LABELS[code]}) is not recorded.", **extra}  # fmt: skip


def install_for_tests(doc: dict | None) -> None:
    """Install (or, with None, remove) a record marked SYNTHETIC_TEST_ONLY. Test environment only."""
    global _override
    if doc is None:
        _override = None
        return
    if settings().env != "test" or doc.get("status") != SYNTHETIC:
        raise RuntimeError("only a SYNTHETIC_TEST_ONLY policy, and only in tests")
    raw = json.dumps(doc, sort_keys=True).encode()
    _override = (Policy.model_validate(doc), hashlib.sha256(raw).hexdigest())


def public_view() -> dict[str, Any]:
    p = current()
    return {"version": p.version, "status": p.status, "sha256": sha256(),
            "decisions": {code: {"label": LABELS[code], "decided": p.decisions.get(code) is not None,
                                 "read_by_engine": code in CONSUMED} for code in SHAPES}}  # fmt: skip
