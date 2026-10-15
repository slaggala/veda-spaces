"""The owner's customer-proposal decisions (CQX-D01…D04), as one versioned record beside the commercial policy.

The commercial decisions a proposal depends on stay in the MTQ commercial policy (OI-MTQ-07 GST, OI-MTQ-08 validity,
OI-MTQ-09 terms, payment milestones and warranty, OI-MTQ-10 unit rates, OI-MTQ-11 acceptance mechanism, OI-MTQ-13
variations). This record holds only what is new to the customer experience. Every slot is null today, and a null slot
never becomes a default:

| Code | What it governs | While null |
|---|---|---|
| CQX-D01 | How the recipient of a link is verified before a digital decision | No digital acceptance or decline |
| CQX-D02 | Whether a customer sees a live total recalculated with their optional choices | "Price confirmation required" |
| CQX-D03 | Which sections must be acknowledged separately before acceptance | No digital acceptance |
| CQX-D04 | Which network/device evidence an acceptance may keep, and for how long | No digital acceptance |

Viewing never depends on these: a proposal is only ever the frozen, customer-safe document. Questions, change requests
and optional-item choices do not either: they are requests to staff and never change a quotation.

Tests may install a policy marked SYNTHETIC (``install_for_tests``); the loader refuses that marker anywhere but the
test environment, so a synthetic decision can never reach staging or production.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from veda.config import settings

from . import vocab as V

FIXTURE = Path(__file__).with_name("fixtures") / "proposal-policy.json"
SYNTHETIC = "SYNTHETIC_TEST_ONLY"
DECISION_LABELS = {
    "CQX-D01": "recipient verification before a digital decision",
    "CQX-D02": "live totals with optional-item choices",
    "CQX-D03": "sections acknowledged separately before acceptance",
    "CQX-D04": "network and device evidence kept with an acceptance",
}
# Verification methods the platform implements. EMAIL_OTP and SMS_OTP are listed so the owner can choose them, but no
# one-time-code channel exists yet: choosing one keeps digital decisions blocked until it is built and reviewed.
IMPLEMENTED_VERIFICATION = ("LINK_POSSESSION",)


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Verification(_Closed):  # CQX-D01
    method: Literal["LINK_POSSESSION", "EMAIL_OTP", "SMS_OTP"]


class OptionalTotals(_Closed):  # CQX-D02
    live_total: bool


class Acknowledgements(_Closed):  # CQX-D03
    required_sections: tuple[Literal[V.ACK_SECTIONS], ...] = Field(min_length=1)  # type: ignore[valid-type]  # literal from the frozen vocabulary


class EvidenceMetadata(_Closed):  # CQX-D04
    record_ip: bool
    record_user_agent: bool
    retention_days: Annotated[int, Field(ge=1, le=3650)]


SHAPES: dict[str, type[_Closed]] = {
    "CQX-D01": Verification,
    "CQX-D02": OptionalTotals,
    "CQX-D03": Acknowledgements,
    "CQX-D04": EvidenceMetadata,
}


class Policy(_Closed):
    schema_: Literal["veda.customer-proposal-policy/1"] = Field(alias="schema")
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
        raise RuntimeError("a SYNTHETIC customer-proposal policy is refused outside the test environment")
    return found


def current() -> Policy:
    return _current()[0]


def sha256() -> str:
    return _current()[1]


def decision(code: str) -> Any:
    return current().get(code)


def required(code: str) -> dict[str, Any]:
    return {"code": "OWNER_DECISION_REQUIRED", "decision": code, "message": f"Owner decision {code} "
            f"({DECISION_LABELS[code]}) is not recorded.", "severity": "BLOCKING", "kind": "OWNER_DECISION"}  # fmt: skip


def install_for_tests(doc: dict | None) -> None:
    """Install (or, with None, remove) a policy marked SYNTHETIC_TEST_ONLY. Test environment only."""
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
            "decisions": {code: {"label": DECISION_LABELS[code], "decided": p.decisions.get(code) is not None}
                          for code in SHAPES}}  # fmt: skip
