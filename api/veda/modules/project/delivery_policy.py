"""The owner's project-delivery decisions (PEX), as one versioned record: ``fixtures/delivery-policy.json``.

A register separate from PLB-OD-01…13 (never read or written here), CPP-D01…06 and PCM-D01/D02. A null slot never
becomes a default; while one is null the code fails closed for exactly the operation it governs:

| Slot | Governs | While null |
|---|---|---|
| PEX-D01 | Whether customers may, in the portal, (a) report an issue on their project and (b) acknowledge a handover package | Both portal writes are refused (OWNER_DECISION_REQUIRED) and the portal offers neither. Staff record a customer's report on their behalf, and the signed handover form's reference at the handover |
| PEX-D02 | The commercial condition a handover needs: COMMERCIAL_OBLIGATION_SATISFIED (decided: Project Commercials says the obligation is satisfied), or for tests NONE, NO_AMOUNT_DUE, FULLY_PAID | The COMMERCIAL_CONDITION gate refuses READY_FOR_HANDOVER and the handover; the position is shown for information |

Tests may install a record marked SYNTHETIC (``install_for_tests``); the loader refuses that marker anywhere but the
test environment.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from veda.config import settings

FIXTURE = Path(__file__).with_name("fixtures") / "delivery-policy.json"
SYNTHETIC = "SYNTHETIC_TEST_ONLY"
LABELS = {
    "PEX-D01": "customer actions in the portal (report an issue; acknowledge a handover)",
    "PEX-D02": "the commercial condition for handover",
}
CONDITIONS = ("NONE", "NO_AMOUNT_DUE", "FULLY_PAID", "COMMERCIAL_OBLIGATION_SATISFIED")
Reference = Annotated[str, Field(min_length=1, max_length=200)]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CustomerActions(_Closed):  # PEX-D01
    issue_reports: bool
    handover_acknowledgement: bool
    reference: Reference


class CommercialCondition(_Closed):  # PEX-D02
    condition: Literal["NONE", "NO_AMOUNT_DUE", "FULLY_PAID", "COMMERCIAL_OBLIGATION_SATISFIED"]
    reference: Reference


SHAPES: dict[str, type[BaseModel]] = {"PEX-D01": CustomerActions, "PEX-D02": CommercialCondition}


class Policy(_Closed):
    schema_: Literal["veda.project.delivery-policy/1"] = Field(alias="schema")
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
        d02 = self.decisions.get("PEX-D02")
        if self.status != SYNTHETIC and d02 is not None and d02.get("condition") != "COMMERCIAL_OBLIGATION_SATISFIED":
            # decision log 46: the other conditions exist for tests only; a real record never relaxes the gate
            raise ValueError("PEX-D02 is the commercial obligation gate (COMMERCIAL_OBLIGATION_SATISFIED)")
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
        raise RuntimeError("a SYNTHETIC delivery policy is refused outside the test environment")
    return found


def current() -> Policy:
    return _current()[0]


def sha256() -> str:
    return _current()[1]


def decision(code: str) -> Any:
    return current().get(code)


def required(code: str, **extra: Any) -> dict[str, Any]:
    return {"code": "OWNER_DECISION_REQUIRED", "decision": code,
            "message": f"Owner decision {code} ({LABELS[code]}) is not recorded.", **extra}  # fmt: skip


def customer_may(action: str) -> bool:
    """PEX-D01: whether the portal may offer ``action`` (``issue_reports`` or ``handover_acknowledgement``)."""
    od = decision("PEX-D01")
    return bool(od is not None and getattr(od, action))


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
            "decisions": {c: {"label": LABELS[c], "decided": p.decisions.get(c) is not None} for c in SHAPES}}  # fmt: skip
