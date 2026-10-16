"""Veda Spaces' Project Commercials business configuration, as one versioned, reviewed record
(``fixtures/commercials-policy.json``).

Owner decision PCM-D01 (2026-10-16, decision log 45) settled two things: the ACCOUNTANT role operates commercials
(``permissions.py``), and invoice particulars come from this authoritative business configuration, never from code
defaults or a person's entry. The slot keeps its register code:

| Slot | What it holds | While null |
|---|---|---|
| PCM-D01 | Invoice issuer particulars: the issuer's legal name and address, the GSTIN and SAC code where they apply, the footer | Invoices can be drafted and previewed; issuing one fails closed (INVOICE_PARTICULARS_NOT_CONFIGURED). Schedules, payments, receipts and the portal are unaffected |

No particulars are configured: the repository holds no legal entity, address or GSTIN, and none is invented.

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

FIXTURE = Path(__file__).with_name("fixtures") / "commercials-policy.json"
SYNTHETIC = "SYNTHETIC_TEST_ONLY"
LABELS = {"PCM-D01": "invoice issuer particulars (business configuration: legal name, address, GSTIN, SAC)"}
PARTICULARS = "PCM-D01"  # the configuration slot an invoice's issuer particulars are read from
REQUIRED_PARTICULARS = ("legal_name", "address_lines")  # the fields an issued invoice cannot go without
Line = Annotated[str, Field(min_length=1, max_length=200)]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InvoiceParticulars(_Closed):  # PCM-D01
    # Only "Invoice": the document does not carry what a GST tax invoice needs (the customer's address and GSTIN,
    # place of supply, taxable value, rate and the CGST/SGST/IGST split). Allowing "Tax invoice" is a code change
    # that adds those fields with the owner's decision (review M4).
    document_title: Literal["Invoice"]
    legal_name: Line
    address_lines: tuple[Line, ...] = Field(min_length=1, max_length=6)
    gstin: Annotated[str | None, Field(pattern=r"^[0-9]{2}[A-Z0-9]{13}$")] = None
    sac_code: Annotated[str | None, Field(pattern=r"^[0-9]{4,8}$")] = None
    footer: tuple[Line, ...] = ()


SHAPES: dict[str, type[BaseModel]] = {"PCM-D01": InvoiceParticulars}


class Policy(_Closed):
    schema_: Literal["veda.commercials.policy/1"] = Field(alias="schema")
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
        raise RuntimeError("a SYNTHETIC commercials policy is refused outside the test environment")
    return found


def current() -> Policy:
    return _current()[0]


def decision(code: str) -> Any:
    return current().get(code)


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


def view() -> dict[str, Any]:
    p = current()
    return {"version": p.version, "status": p.status,
            "decisions": {c: {"label": LABELS[c], "decided": p.decisions.get(c) is not None} for c in SHAPES}}  # fmt: skip
