"""The customer information pack (owner-decision register OI-MTQ-18; CQX customer completeness, CTB-01…CTB-18).

What a customer needs beyond the priced scope, as owner-approved, versioned customer copy: the Veda Spaces business
contacts, project-level inclusions, what the customer arranges, site readiness, site-dependent work, the manufacturer
warranty note and warranty exclusions, how to request service, handover expectations, care guidance, the stages after
acceptance and a payment-safety statement. Every section is optional: an empty section is shown to the customer as
"to be confirmed", never filled with a default. Nothing here is decided by engineering.

The pack is copied into a quotation's terms snapshot when the version is drafted (``quotations.terms_snapshot``) and
frozen into the issued document (``rendering.freeze``); a later change to the pack never changes an issued version.
Per version, staff choose the quotation contact and the status of each responsibility and readiness item
(``quotation.customer_inputs``); the frozen document carries the result.

Copy governance: free text refuses money amounts, durations (a duration appears only in a next-step stage's own
``duration`` field, which recording approves), e-mail addresses and phone numbers outside the contact fields, bank,
IFSC, UPI or card details, and unsupported superlative claims. Contacts must be confirmed as Veda Spaces business
channels approved for publication; personal staff contact data is never a valid entry.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated, Any, Literal, get_args

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

_MONEY = re.compile(r"₹|\brs\.?\s*\d|\binr\b|\brupees?\b|\blakhs?\b|\bcrores?\b", re.I)
_DURATION = re.compile(r"\b\d+\s*[- ]?\s*(working\s+)?(hours?|hrs?|days?|weeks?|months?|years?|yrs?)\b", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(?:\+?\d[\d\s()-]{8,}\d)")
# Account details, not the words: an IFSC code, an account or card number, a UPI handle (an approved payment-safety
# statement may say which channels Veda Spaces recognises, but never carries the details themselves).
_BANK = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b|\b\d{9,19}\b|\ba/c\b|\b[\w.-]{2,}@(?:ok)?[a-z]{2,}\b(?!\.[a-z])", re.I)
_CLAIMS = re.compile(r"\b(no\.?\s*1\b|number\s+one\b|most\s+trusted\b|best\s+in\b|india'?s\s+(best|most)\b|"
                     r"lifetime\b|guaranteed?\b|100\s*%|free\s+service\b|world[- ]class\b|award[- ]winning\b)",
                     re.I)  # fmt: skip
_GUARDS = ((_MONEY, "an amount of money"), (_DURATION, "a time duration"), (_EMAIL, "an e-mail address"),
           (_PHONE, "a phone number"), (_BANK, "payment or bank details"), (_CLAIMS, "an unsupported claim"))  # fmt: skip


def _copy(value: str) -> str:
    """Customer copy: refused when it carries anything the copy rules keep out of free text."""
    for pattern, what in _GUARDS:
        if pattern.search(value):
            raise ValueError(f"customer copy must not contain {what}")
    return value


def _duration(value: str) -> str:
    """A next-step stage's approved duration: the one place a time may appear; no money, contacts or claims."""
    for pattern, what in _GUARDS:
        if pattern is not _DURATION and pattern.search(value):
            raise ValueError(f"a stage duration must not contain {what}")
    return value


Copy = Annotated[str, Field(min_length=1, max_length=600), AfterValidator(_copy)]
Label = Annotated[str, Field(min_length=1, max_length=80), AfterValidator(_copy)]
Code = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]

ResponsibilityCategory = Literal["CLIENT_SUPPLIED_ITEM", "APPLIANCE_MODEL", "APPLIANCE_DIMENSIONS", "ELECTRICITY",
                                 "WATER", "SERVICE_LIFT_ACCESS", "WORKING_ACCESS", "BUILDER_SOCIETY_PERMISSION",
                                 "CIVIL_READINESS", "PLUMBING_READINESS", "ELECTRICAL_READINESS", "OTHER"]  # fmt: skip
ResponsibilityStatus = Literal["REQUIRED", "NOT_REQUIRED", "TO_BE_CONFIRMED"]
ReadinessCategory = Literal["FLOORING", "PAINTING", "DOORS_WINDOWS", "ELECTRICAL_SUPPLY", "WATER", "ACCESS",
                            "SERVICE_LIFT", "WORK_AREA_CLEARANCE", "BUILDER_SOCIETY_APPROVAL", "APPLIANCE_INFORMATION",
                            "CIVIL_WORK", "PLUMBING_DEPENDENCIES", "ELECTRICAL_DEPENDENCIES", "OTHER"]  # fmt: skip
ReadinessStatus = Literal["READY", "NOT_READY", "CUSTOMER_ACTION_REQUIRED", "NOT_APPLICABLE", "TO_BE_CONFIRMED"]
SiteWorkCategory = Literal["ELECTRICAL", "PLUMBING", "CIVIL", "WALL_PREPARATION", "OPENING_CORRECTION", "APPLIANCE",
                           "BUILDER_SITE_RESTRICTION", "EXECUTION_DEPENDENCY"]  # fmt: skip
HandoverCategory = Literal["PROTECTION", "CLEANING", "FINAL_INSPECTION", "SNAG_OBSERVATIONS", "JOINT_HANDOVER",
                           "HANDOVER_EVIDENCE", "CUSTOMER_ACKNOWLEDGEMENT"]  # fmt: skip
CareCategory = Literal["FURNITURE_CLEANING", "LAMINATE_CARE", "HARDWARE_CARE", "WATER_EXPOSURE", "PEST_PREVENTION",
                       "PRODUCT_SPECIFIC", "MANUFACTURER_INSTRUCTIONS"]  # fmt: skip
# The stages after acceptance, in the project-lifecycle terminology already frozen in the MTQ blueprint (no lifecycle
# is implemented here: this is customer guidance).
StageCode = Literal["PROPOSAL_ACCEPTED", "VEDA_CONFIRMATION", "SCOPE_DESIGN_FINALISATION", "PRODUCTION_READINESS",
                    "SITE_READINESS", "INSTALLATION", "JOINT_INSPECTION", "HANDOVER"]  # fmt: skip
RESPONSIBILITY_STATUSES = get_args(ResponsibilityStatus)
READINESS_STATUSES = get_args(ReadinessStatus)
STAGES = get_args(StageCode)


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Contact(_Closed):
    """A Veda Spaces business contact approved for publication to customers (never a personal number or address)."""

    code: Code
    kind: Literal["QUOTATION", "SUPPORT", "SERVICE"]
    display_name: Label
    role: Label
    phone: Annotated[str, Field(pattern=r"^\+?[0-9][0-9 ()-]{5,19}$")] | None = None
    email: Annotated[str, Field(pattern=r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", max_length=120)] | None = (
        None
    )
    hours: Label | None = None
    channel_note: Copy | None = None  # e.g. how the channel is used; no promise of a response time
    business_channel_approved: Literal[True]  # the owner confirms a Veda Spaces business channel, approved to publish

    @model_validator(mode="after")
    def _reachable(self):
        if not (self.phone or self.email):
            raise ValueError("a contact needs a business phone or a business e-mail")
        return self


class Entry(_Closed):
    code: Code
    text: Copy


class Responsibility(_Closed):
    code: Code
    category: ResponsibilityCategory
    text: Copy
    default_status: ResponsibilityStatus = "TO_BE_CONFIRMED"


class Readiness(_Closed):
    code: Code
    category: ReadinessCategory
    text: Copy


class SiteWork(_Closed):
    code: Code
    category: SiteWorkCategory
    text: Copy


class SiteDependentWork(_Closed):
    intro: Copy  # why some needs become clear only after site and design validation
    approval_rule: Copy  # how such work is approved and priced (a variation the customer agrees to first)
    categories: tuple[SiteWork, ...] = ()


class ServiceGuidance(_Closed):
    contact_code: Code | None = None  # a SERVICE or SUPPORT contact
    what_to_provide: tuple[Copy, ...] = ()
    reference_process: Copy | None = None
    escalation: Copy | None = None


class HandoverEntry(_Closed):
    code: Code
    category: HandoverCategory
    text: Copy


class CareEntry(_Closed):
    code: Code
    category: CareCategory
    text: Copy


class Stage(_Closed):
    code: Code
    stage: StageCode
    label: Label
    text: Copy
    duration: Annotated[str, Field(min_length=1, max_length=80), AfterValidator(_duration)] | None = None


class CustomerPack(_Closed):  # OI-MTQ-18
    content_version: Annotated[str, Field(min_length=1, max_length=20)]
    contacts: tuple[Contact, ...] = ()
    support_escalation: Copy | None = None
    project_inclusions: tuple[Entry, ...] = ()
    client_responsibilities: tuple[Responsibility, ...] = ()
    site_readiness: tuple[Readiness, ...] = ()
    site_dependent_work: SiteDependentWork | None = None
    manufacturer_warranty_note: Copy | None = None
    warranty_exclusions: tuple[Entry, ...] = ()
    service_guidance: ServiceGuidance | None = None
    handover: tuple[HandoverEntry, ...] = ()
    care: tuple[CareEntry, ...] = ()
    next_steps: tuple[Stage, ...] = ()
    payment_safety: Copy | None = None

    @model_validator(mode="after")
    def _consistent(self):
        for name in ("contacts", "project_inclusions", "client_responsibilities", "site_readiness", "warranty_exclusions",
                     "handover", "care", "next_steps"):  # fmt: skip
            codes = [x.code for x in getattr(self, name)]
            if len(codes) != len(set(codes)):
                raise ValueError(f"{name}: codes must be unique")
        if self.site_dependent_work:
            codes = [x.code for x in self.site_dependent_work.categories]
            if len(codes) != len(set(codes)):
                raise ValueError("site_dependent_work.categories: codes must be unique")
        sg = self.service_guidance
        if sg and sg.contact_code and not any(c.code == sg.contact_code and c.kind in ("SERVICE", "SUPPORT")
                                              for c in self.contacts):  # fmt: skip
            raise ValueError("service_guidance.contact_code must name a SERVICE or SUPPORT contact")
        stages = [STAGES.index(x.stage) for x in self.next_steps]
        if stages != sorted(stages):
            raise ValueError("next_steps must follow the stage order")
        return self


# --- per-version staff inputs (quotation.customer_inputs) -------------------------------------------------------------
def validate_inputs(pack: dict[str, Any] | None, inputs: dict[str, Any]) -> dict[str, Any]:
    """Staff's choices for one version, checked against the pack frozen in its terms. Returns the stored form."""
    from veda.kernel.errors import ApiError

    if pack is None:
        raise ApiError(409, "CUSTOMER_PACK_NOT_DECIDED", "The customer information pack (owner decision OI-MTQ-18) is "
                       "not recorded for this version; there is nothing to choose yet.")  # fmt: skip
    errors: list[dict[str, str]] = []
    contact = inputs.get("contact_code")
    if contact is not None and not any(c["code"] == contact and c["kind"] == "QUOTATION" for c in pack["contacts"]):
        errors.append({"field": "contact_code", "code": "UNKNOWN_CONTACT",
                       "message": "Choose one of the approved quotation contacts."})  # fmt: skip
    for field, key in (("responsibilities", "client_responsibilities"), ("readiness", "site_readiness")):
        known = {x["code"] for x in pack[key]}
        for code in inputs.get(field) or {}:
            if code not in known:
                errors.append({"field": f"{field}.{code}", "code": "UNKNOWN_ITEM",
                               "message": f"{code} is not an item of the approved pack."})  # fmt: skip
    if errors:
        raise ApiError(422, "VALIDATION_FAILED", "Some choices are not part of the approved pack.", errors=errors)
    return {"contact_code": contact, "responsibilities": dict(inputs.get("responsibilities") or {}),
            "readiness": dict(inputs.get("readiness") or {})}  # fmt: skip


# --- the frozen document's customer information (rendering.document_model) --------------------------------------------
def _contact(c: dict[str, Any]) -> dict[str, Any]:
    return {k: c.get(k) for k in ("display_name", "role", "phone", "email", "hours", "channel_note")}


def information(pack: dict[str, Any] | None, inputs: dict[str, Any] | None) -> dict[str, Any]:
    """The customer-information block of the document: each section the approved copy, or None (to be confirmed)."""
    inputs = inputs or {}
    if pack is None:
        return {"content_version": None, "contacts": {"quotation": None, "support": [], "service": []},
                "support_escalation": None, "project_inclusions": None, "client_responsibilities": None,
                "site_readiness": None, "site_dependent_work": None, "manufacturer_warranty_note": None,
                "warranty_exclusions": None, "service_guidance": None, "handover": None, "care": None,
                "next_steps": None, "payment_safety": None}  # fmt: skip
    contacts = pack.get("contacts") or []
    chosen = next((c for c in contacts if c["code"] == inputs.get("contact_code") and c["kind"] == "QUOTATION"), None)
    resp = inputs.get("responsibilities") or {}
    ready = inputs.get("readiness") or {}

    def listed(key: str, fields: tuple[str, ...]) -> list[dict[str, Any]] | None:
        rows = pack.get(key) or []
        return [{k: x.get(k) for k in fields} for x in rows] or None

    sdw = pack.get("site_dependent_work")
    sg = pack.get("service_guidance")
    service_contact = None
    if sg and sg.get("contact_code"):
        service_contact = next((_contact(c) for c in contacts if c["code"] == sg["contact_code"]), None)
    return {
        "content_version": pack.get("content_version"),
        "contacts": {
            "quotation": _contact(chosen) if chosen else None,
            "support": [_contact(c) for c in contacts if c["kind"] == "SUPPORT"],
            "service": [_contact(c) for c in contacts if c["kind"] == "SERVICE"],
        },
        "support_escalation": pack.get("support_escalation"),
        "project_inclusions": listed("project_inclusions", ("code", "text")),
        "client_responsibilities": [
            {
                "code": x["code"],
                "category": x["category"],
                "text": x["text"],
                "status": resp.get(x["code"], x.get("default_status") or "TO_BE_CONFIRMED"),
            }
            for x in pack.get("client_responsibilities") or []
        ]
        or None,  # fmt: skip
        "site_readiness": [
            {
                "code": x["code"],
                "category": x["category"],
                "text": x["text"],
                "status": ready.get(x["code"], "TO_BE_CONFIRMED"),
            }
            for x in pack.get("site_readiness") or []
        ]
        or None,  # fmt: skip
        "site_dependent_work": (
            {
                "intro": sdw["intro"],
                "approval_rule": sdw["approval_rule"],
                "categories": [{k: x[k] for k in ("code", "category", "text")} for x in sdw.get("categories") or []],
            }
            if sdw
            else None
        ),  # fmt: skip
        "manufacturer_warranty_note": pack.get("manufacturer_warranty_note"),
        "warranty_exclusions": listed("warranty_exclusions", ("code", "text")),
        "service_guidance": (
            {
                "contact": service_contact,
                "what_to_provide": list(sg.get("what_to_provide") or []),
                "reference_process": sg.get("reference_process"),
                "escalation": sg.get("escalation"),
            }
            if sg
            else None
        ),  # fmt: skip
        "handover": listed("handover", ("code", "category", "text")),
        "care": listed("care", ("code", "category", "text")),
        "next_steps": listed("next_steps", ("code", "stage", "label", "text", "duration")),
        "payment_safety": pack.get("payment_safety"),
    }


# --- payment milestone amounts (CTB-09) --------------------------------------------------------------------------------
def milestone_amounts(total_minor: int | None, shares_bp: list[int]) -> list[int] | None:
    """Each milestone's amount in paise from the frozen total and the approved shares, reconciling exactly.

    Each share is first given its floor (total × share ÷ 10 000, rounded down to the paisa); the paise left over are
    given one each to the milestones with the largest remainders, the earlier milestone first on a tie. The amounts
    therefore always add up to the total, and the same inputs always give the same amounts. None when the total is not
    known (GST undecided) or the shares do not add up to 100 %.
    """
    if total_minor is None or not shares_bp or sum(shares_bp) != 10_000:
        return None
    raw = [(total_minor * bp) for bp in shares_bp]
    floors = [r // 10_000 for r in raw]
    left = total_minor - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] % 10_000), i))
    for i in order[:left]:
        floors[i] += 1
    return floors


def money(minor: int | None) -> str | None:
    return None if minor is None else f"{Decimal(minor) / 100:,.2f}"


# --- item dimensions (CTB-02) -----------------------------------------------------------------------------------------
# The rate-card inputs that are a size a customer recognises, with their customer label; counts (drawers, points) are
# quantities, not dimensions. Only verified sources are shown: a measured or derived value from the B1 measurement, or
# a staff value recorded with its reason. An assumed or missing input is "to be confirmed", never guessed.
DIMENSION_LABELS = {"WIDTH": "Width", "HEIGHT": "Height", "DEPTH": "Depth", "RUN": "Total run",
                    "WALL_UNIT_RUN": "Wall-unit run", "LENGTH": "Length", "DOOR_WIDTH": "Door width", "AREA": "Area",
                    "CARPET": "Floor area"}  # fmt: skip
VERIFIED_SOURCES = ("MEASURED", "DERIVED", "STAFF")


def _figure(value: str, unit: str) -> str:
    d = Decimal(value).quantize(Decimal("0.01")).normalize()
    return f"{d:f} {unit}"


def dimensions(formula_inputs: dict[str, Any] | None) -> tuple[list[dict[str, str]], str | None]:
    """(the line's customer dimensions, status) from its BOQ line's resolved inputs. Status is None when the line has
    no size (a count or a lump sum), "CONFIRMED" when every size input is verified, else "TO_BE_CONFIRMED" (only the
    verified ones are shown)."""
    inputs = (formula_inputs or {}).get("inputs") or {}
    shown: list[dict[str, str]] = []
    pending = False
    for name in DIMENSION_LABELS:
        d = inputs.get(name)
        if not isinstance(d, dict) or d.get("unit") not in ("ft", "sq ft"):
            continue
        if d.get("source") in VERIFIED_SOURCES and d.get("value") not in (None, ""):
            shown.append({"label": DIMENSION_LABELS[name], "value": _figure(str(d["value"]), d["unit"])})
        else:
            pending = True
    if not shown and not pending:
        return [], None
    return shown, ("TO_BE_CONFIRMED" if pending else "CONFIRMED")
