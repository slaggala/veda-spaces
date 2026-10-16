"""The owner's warranty and service decisions (WSV), as one versioned record: ``fixtures/warranty-policy.json``.

A register separate from PLB-OD, CPP, PCM and PEX. A null slot never becomes a default; while one is null the code fails
closed for exactly what it governs:

| Slot | Governs | While null |
|---|---|---|
| WSV-D01 | Structured warranty coverage terms, for example adopting the published Warranty, Service & Customer Care Policy: the policy version and text digest, per coverage class a label, the customer description, exclusions, a duration in months and a start trigger (HANDOVER), and the quotation ``terms_version`` values whose accepted documents carry them | No coverage period is recorded: entitlements show "not recorded in your portal"; a coverage decision cites a statement of the accepted quotation with a recorded period basis |

Chargeable post-handover service is not an owner slot: it needs a commercial agreement mechanism the repository does
not have (a missing integration, see the implementation record). A request classed CHARGEABLE is therefore never
started or resolved; it waits or is closed CHARGEABLE_NOT_AGREED.

A recorded WSV-D01 applies only to entitlements whose accepted base quotation carries one of its
``applies_to_terms_versions``: bound to what the customer accepted, never to a date, so a later configuration never
rewrites an earlier promise. A class the owner marks ``conflicts_with_statements`` is frozen as not recorded. The entitlement
freezes the version and digest it used. Tests may install a record marked SYNTHETIC (``install_for_tests``); the loader
refuses that marker anywhere but the test environment.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from veda.config import settings

FIXTURE = Path(__file__).with_name("fixtures") / "warranty-policy.json"
SYNTHETIC = "SYNTHETIC_TEST_ONLY"
LABELS = {
    "WSV-D01": "structured warranty coverage terms (period, start trigger, coverage and exclusions)",
}
Text = Annotated[str, Field(min_length=1, max_length=600)]
Reference = Annotated[str, Field(min_length=1, max_length=200)]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CoverageClass(_Closed):
    code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]
    label: Annotated[str, Field(min_length=1, max_length=120)]
    covers: Text  # customer wording
    exclusions: tuple[Text, ...] = ()
    duration_months: Annotated[int, Field(ge=1, le=600)]
    trigger: Literal["HANDOVER"]
    conflicts_with_statements: bool = False  # frozen as NOT_RECORDED with a CONFLICT note for staff


class CoverageTerms(_Closed):  # WSV-D01
    policy_version: Annotated[str, Field(min_length=1, max_length=60)]
    policy_text_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    applies_to_terms_versions: tuple[Annotated[str, Field(min_length=1, max_length=40)], ...] = Field(min_length=1)
    classes: tuple[CoverageClass, ...] = Field(min_length=1)
    reference: Reference

    @model_validator(mode="after")
    def _unique(self):
        codes = [c.code for c in self.classes]
        if len(codes) != len(set(codes)):
            raise ValueError("coverage class codes must be unique")
        return self


SHAPES: dict[str, type[BaseModel]] = {"WSV-D01": CoverageTerms}


class Policy(_Closed):
    schema_: Literal["veda.warranty.policy/1"] = Field(alias="schema")
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
        raise RuntimeError("a SYNTHETIC warranty policy is refused outside the test environment")
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
