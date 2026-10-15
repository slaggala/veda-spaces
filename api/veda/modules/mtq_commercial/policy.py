"""The owner's commercial decisions for MTQ B2-B4, as one versioned record (owner-decision register OI-MTQ-03…18).

``fixtures/commercial-policy.json`` holds a slot per register row. Every slot is null today: nothing has been decided.
A null slot never becomes a default. Instead:

| Register row | What it governs | While null |
|---|---|---|
| OI-MTQ-03 / 04 | Scope rules and quantity derivations approved | Scopes carry the PROPOSED ruleset; not customer-issuable |
| OI-MTQ-05 | Premium / Luxury staff tiers; finish-variant rates; NEW LINE rates | Those tiers refused (RATE_CARD_NOT_APPROVED); finish variants and unmapped items unpriced |
| OI-MTQ-06 | Discount authority (self limit, maximum, approver) | Discount actions disabled |
| OI-MTQ-07 | GST treatment | No tax computed (GST_POLICY_REQUIRED); not customer-issuable |
| OI-MTQ-08 | Quotation validity | No validity date; not customer-issuable |
| OI-MTQ-09 | Terms, payment milestones, warranty, assumptions, exclusions, change-order and cancellation terms | Not customer-issuable |
| OI-MTQ-10 | Whether unit rates are shown to customers | Never shown |
| OI-MTQ-11 | How acceptance is recorded | Acceptance cannot be recorded |
| OI-MTQ-13 | Variation (change-order) policy | Variations draftable, not issuable |
| OI-MTQ-15 | Preparation-package drivers (5 BHK, independent house) | Those charges unpriced; not customer-issuable |
| OI-MTQ-18 | Customer information pack: business contacts, responsibilities, site readiness, site-dependent work, warranty exclusions, service guidance, handover, care, next steps, payment safety (``customer_pack``) | Every section shown "to be confirmed"; not an issuance blocker (a real-customer gate: CQX trust checklist) |

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

from .customer_pack import CustomerPack

FIXTURE = Path(__file__).with_name("fixtures") / "commercial-policy.json"
SYNTHETIC = "SYNTHETIC_TEST_ONLY"
DECISION_LABELS = {
    "OI-MTQ-03": "scope rules",
    "OI-MTQ-04": "quantity derivations, rounding, wastage and clearances",
    "OI-MTQ-05": "Premium/Luxury staff rates and finish-variant rates",
    "OI-MTQ-06": "discount authority",
    "OI-MTQ-07": "GST treatment",
    "OI-MTQ-08": "quotation validity",
    "OI-MTQ-09": "terms, payment milestones, warranty, assumptions and exclusions",
    "OI-MTQ-10": "showing unit rates to customers",
    "OI-MTQ-11": "customer acceptance mechanism",
    "OI-MTQ-13": "variation (change-order) policy",
    "OI-MTQ-14": "provisional sums",
    "OI-MTQ-15": "preparation-package drivers for 5 BHK and independent houses",
    "OI-MTQ-18": "customer information pack (contacts, responsibilities, site readiness, service, handover, next steps)",
}
BP = Annotated[int, Field(ge=0, le=10_000)]
Text = Annotated[str, Field(min_length=1, max_length=2000)]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Rules(_Closed):  # OI-MTQ-03 / OI-MTQ-04
    ruleset_version: str
    ruleset_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Rates(_Closed):  # OI-MTQ-05
    staff_tiers: tuple[Literal["PREMIUM", "LUXURY"], ...] = ()
    # finish → "PRODUCT.LINE" → rate in paise per unit, by tier
    finish_rates: dict[str, dict[str, dict[str, Annotated[int, Field(ge=0)]]]] = Field(default_factory=dict)


class Discounts(_Closed):  # OI-MTQ-06
    self_limit_bp: BP  # a proposer may apply up to this share of the subtotal on their own authority
    max_bp: BP  # nothing above this, whoever approves
    four_eyes: bool = True  # an approval is never by the proposer

    @model_validator(mode="after")
    def _order(self):
        if self.self_limit_bp > self.max_bp:
            raise ValueError("self_limit_bp must not exceed max_bp")
        return self


class Tax(_Closed):  # OI-MTQ-07
    mode: Literal["SINGLE_RATE"]
    rate_bp: BP
    discount_allocation: Literal["PRO_RATA"]


class Validity(_Closed):  # OI-MTQ-08
    validity_days: Annotated[int, Field(ge=1, le=180)]


class Milestone(_Closed):
    label: Annotated[str, Field(min_length=1, max_length=120)]
    share_bp: Annotated[int, Field(ge=1, le=10_000)]
    trigger: Annotated[str, Field(min_length=1, max_length=200)]


class Terms(_Closed):  # OI-MTQ-09 (legal review recorded with the decision)
    terms_version: Annotated[str, Field(min_length=1, max_length=20)]
    payment_milestones: tuple[Milestone, ...] = Field(min_length=1)
    warranty: tuple[Text, ...] = Field(min_length=1)
    # Veda Spaces' own service support (CQX-09), kept apart from the warranty text: both are shown, never merged.
    service_support: tuple[Text, ...] = ()
    assumptions: tuple[Text, ...] = ()
    exclusions: tuple[Text, ...] = Field(min_length=1)
    change_order_terms: Text
    cancellation_terms: Text
    general_terms: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def _schedule(self):
        if sum(m.share_bp for m in self.payment_milestones) != 10_000:
            raise ValueError("payment milestones must add up to 100 %")
        return self


class Presentation(_Closed):  # OI-MTQ-10
    show_unit_rates: bool


class Acceptance(_Closed):  # OI-MTQ-11
    # CUSTOMER_DIGITAL: the customer accepts or declines through their secure proposal link (CQX-10); it also needs
    # the customer-proposal decisions CQX-D01, D03 and D04 (customer_proposal.policy).
    methods: tuple[Literal["STAFF_RECORDED", "SIGNED_COPY", "CUSTOMER_DIGITAL"], ...] = Field(min_length=1)


class Variations(_Closed):  # OI-MTQ-13
    allowed: bool
    rate_changes_allowed: bool


class PrepDrivers(_Closed):  # OI-MTQ-15
    # bedroom count → the card's preparation key (e.g. {"5": "4BHK"} or a new key the card carries)
    home_size_by_bedrooms: dict[str, str] = Field(default_factory=dict)
    independent_house_factor_bp: Annotated[int | None, Field(ge=1, le=50_000)] = None


SHAPES: dict[str, type[BaseModel]] = {
    "OI-MTQ-03": Rules,
    "OI-MTQ-04": Rules,
    "OI-MTQ-05": Rates,
    "OI-MTQ-06": Discounts,
    "OI-MTQ-07": Tax,
    "OI-MTQ-08": Validity,
    "OI-MTQ-09": Terms,
    "OI-MTQ-10": Presentation,
    "OI-MTQ-11": Acceptance,
    "OI-MTQ-13": Variations,
    "OI-MTQ-14": Presentation,  # placeholder shape: provisional sums are not implemented while undecided
    "OI-MTQ-15": PrepDrivers,
    "OI-MTQ-18": CustomerPack,
}


class Policy(_Closed):
    schema_: Literal["veda.mtq.commercial-policy/1"] = Field(alias="schema")
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
        raise RuntimeError("a SYNTHETIC commercial policy is refused outside the test environment")
    return found


def current() -> Policy:
    return _current()[0]


def sha256() -> str:
    return _current()[1]


def decision(code: str) -> Any:
    return current().get(code)


def required(code: str) -> dict[str, Any]:
    """The issuance blocker for an undecided register row."""
    return {"code": "OWNER_DECISION_REQUIRED", "decision": code, "message": f"Owner decision {code} "
            f"({DECISION_LABELS[code]}) is not recorded.", "severity": "BLOCKING"}  # fmt: skip


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
    return {
        "version": p.version,
        "status": p.status,
        "sha256": sha256(),
        "decisions": {
            code: {"label": DECISION_LABELS[code], "decided": p.decisions.get(code) is not None} for code in SHAPES
        },  # fmt: skip
    }
