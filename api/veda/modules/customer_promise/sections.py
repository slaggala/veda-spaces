"""The twelve administration sections of a Customer Promise Pack and the content rules they share.

A pack's content is the customer information pack of PR #96 (``customer_pack.CustomerPack``, OI-MTQ-18), edited section
by section. Each section owns some of the pack's keys, names the capability that edits it and the one that reviews
it, and is either ordinary or *sensitive* (liability-bearing: what the customer must do, site-dependent work and its
approval rule, warranty statements and exclusions, payment safety, and the contact channels). Sensitive sections are reviewed only by holders of
``customer_promise.review.sensitive``. Four-eyes applies to every section: nobody reviews or approves a section they
saved or a version they submitted.

In a draft, a list entry may carry ``"active": false``: it is kept (and still checked by every copy rule) but is not
published. Order is the list order. The customer content of a version is its content with inactive entries removed,
validated as a ``CustomerPack``; a published version stores it, frozen, with its digest.

The fourteen customer-facing areas map onto these sections (``AREAS``). Veda Spaces' own service and workmanship
commitments are contract terms (OI-MTQ-09 ``service_support``, legal review with that decision); this portal never
authors them, so a manufacturer-warranty statement and a Veda Spaces commitment can never be merged here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from veda.modules.mtq_commercial.customer_pack import CustomerPack

LIST_KEYS = ("contacts", "project_inclusions", "client_responsibilities", "site_readiness", "warranty_exclusions",
             "handover", "care", "next_steps")  # fmt: skip
PACK_KEYS = tuple(k for k in CustomerPack.model_fields if k != "content_version")


@dataclass(frozen=True)
class Section:
    code: str
    title: str
    keys: tuple[str, ...]
    edit: str  # the capability that edits it
    sensitive: bool = False

    @property
    def review(self) -> str:
        return "customer_promise.review.sensitive" if self.sensitive else "customer_promise.review"


SECTIONS: tuple[Section, ...] = (
    # sensitive: the contacts and their allowed e-mail domains are where a customer is told to reach (and pay) Veda
    # Spaces; moving them is a payment-redirection risk, so the control review applies (independent review, PR #97)
    Section("CONTACTS", "Contact and support", ("email_domains", "contacts", "support_escalation"),
            "customer_promise.contacts.edit", sensitive=True),
    Section("INCLUSIONS", "Project inclusions", ("project_inclusions",), "customer_promise.edit"),
    Section("RESPONSIBILITIES", "Customer responsibilities", ("client_responsibilities",), "customer_promise.edit",
            sensitive=True),
    Section("SITE_READINESS", "Site readiness", ("site_readiness",), "customer_promise.edit"),
    Section("SITE_WORK", "Site-dependent work", ("site_dependent_work",), "customer_promise.edit", sensitive=True),
    Section("WARRANTY", "Warranty and service", ("manufacturer_warranty_note",), "customer_promise.warranty.edit",
            sensitive=True),
    Section("EXCLUSIONS", "Warranty exclusions", ("warranty_exclusions",), "customer_promise.warranty.edit",
            sensitive=True),
    Section("SERVICE", "Service guidance", ("service_guidance",), "customer_promise.contacts.edit"),
    Section("HANDOVER", "Handover", ("handover",), "customer_promise.edit"),
    Section("CARE", "Care guidance", ("care",), "customer_promise.edit"),
    Section("NEXT_STEPS", "What happens next", ("next_steps",), "customer_promise.edit"),
    Section("PAYMENT_SAFETY", "Payment safety", ("payment_safety",), "customer_promise.payment_safety.edit",
            sensitive=True),
)  # fmt: skip
BY_CODE = {s.code: s for s in SECTIONS}
CODES = tuple(BY_CODE)
assert sorted(k for s in SECTIONS for k in s.keys) == sorted(PACK_KEYS), "every pack key belongs to one section"


def section_of_key(key: str) -> Section:
    return next(s for s in SECTIONS if key in s.keys)


# --- the fourteen customer-facing areas (completeness) ---------------------------------------------------------------
@dataclass(frozen=True)
class Area:
    code: str
    title: str
    section: str | None  # None: governed elsewhere (OI-MTQ-09)


AREAS: tuple[Area, ...] = (
    Area("CONTACT", "Your Veda Spaces contact", "CONTACTS"),
    Area("INCLUSIONS", "Project inclusions", "INCLUSIONS"),
    Area("RESPONSIBILITIES", "Customer responsibilities", "RESPONSIBILITIES"),
    Area("SITE_READINESS", "Site readiness", "SITE_READINESS"),
    Area("SITE_WORK", "Site-dependent work", "SITE_WORK"),
    Area("MANUFACTURER_WARRANTY", "Manufacturer warranty", "WARRANTY"),
    Area("VEDA_SERVICE", "Veda Spaces service and workmanship support", None),
    Area("WARRANTY_EXCLUSIONS", "Warranty exclusions", "EXCLUSIONS"),
    Area("SERVICE_GUIDANCE", "How to request service", "SERVICE"),
    Area("HANDOVER", "Handover expectations", "HANDOVER"),
    Area("CARE", "Care guidance", "CARE"),
    Area("NEXT_STEPS", "What happens after approval", "NEXT_STEPS"),
    Area("PAYMENT_SAFETY", "Payment safety", "PAYMENT_SAFETY"),
    Area("SUPPORT", "Support and escalation", "CONTACTS"),
)


def area_value(code: str, content: dict[str, Any] | None) -> Any:
    """The part of a customer content that answers one area (None or empty: not answered)."""
    c = content or {}
    contacts = c.get("contacts") or []
    if code == "CONTACT":
        return [x for x in contacts if x.get("kind") == "QUOTATION"]
    if code == "SUPPORT":
        found = [x for x in contacts if x.get("kind") in ("SUPPORT", "SERVICE")]
        return {"contacts": found, "escalation": c.get("support_escalation")} if found or c.get("support_escalation") \
            else None  # fmt: skip
    key = {"INCLUSIONS": "project_inclusions", "RESPONSIBILITIES": "client_responsibilities",
           "SITE_READINESS": "site_readiness", "SITE_WORK": "site_dependent_work",
           "MANUFACTURER_WARRANTY": "manufacturer_warranty_note", "WARRANTY_EXCLUSIONS": "warranty_exclusions",
           "SERVICE_GUIDANCE": "service_guidance", "HANDOVER": "handover", "CARE": "care", "NEXT_STEPS": "next_steps",
           "PAYMENT_SAFETY": "payment_safety"}.get(code)  # fmt: skip
    return c.get(key) if key else None


# --- content -----------------------------------------------------------------------------------------------------------
def empty() -> dict[str, Any]:
    return {k: ([] if k in LIST_KEYS or k == "email_domains" else None) for k in PACK_KEYS}


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def section_value(content: dict[str, Any] | None, code: str) -> dict[str, Any]:
    c = content or empty()
    return {k: c.get(k) for k in BY_CODE[code].keys}


def section_digest(content: dict[str, Any] | None, code: str) -> str:
    return digest(section_value(content, code))


def _drop_inactive(rows: list[Any] | None, *, keep_inactive: bool) -> list[Any]:
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            out.append(row)
            continue
        if not keep_inactive and row.get("active") is False:
            continue
        out.append({k: v for k, v in row.items() if k != "active"})
    return out


class ContentError(ValueError):
    """Content that is refused; ``errors`` name the field path and the rule, never the submitted value."""

    def __init__(self, errors: list[dict[str, str]]):
        super().__init__("; ".join(f"{e['field']}: {e['message']}" for e in errors))
        self.errors = errors


def _flags(content: dict[str, Any]) -> list[dict[str, str]]:
    """``active`` is the only authoring key, and it is a boolean."""
    out = []
    lists = [(k, content.get(k)) for k in LIST_KEYS]
    sdw = content.get("site_dependent_work")
    if isinstance(sdw, dict):
        lists.append(("site_dependent_work.categories", sdw.get("categories")))
    for key, rows in lists:
        for i, row in enumerate(rows or []):
            if isinstance(row, dict) and "active" in row and not isinstance(row["active"], bool):
                out.append({"field": f"{key}[{i}].active", "code": "INVALID", "message": "active is true or false"})
    return out


def _strip(content: dict[str, Any], *, keep_inactive: bool) -> dict[str, Any]:
    out = {k: content.get(k) for k in PACK_KEYS}
    for k in LIST_KEYS:
        out[k] = _drop_inactive(out.get(k), keep_inactive=keep_inactive)
    sdw = out.get("site_dependent_work")
    if isinstance(sdw, dict):
        out["site_dependent_work"] = {
            **sdw,
            "categories": _drop_inactive(sdw.get("categories"), keep_inactive=keep_inactive),
        }
    return out


def _pydantic(err: ValidationError) -> list[dict[str, str]]:
    found = []
    for e in err.errors()[:20]:
        loc = ".".join(str(p) if not isinstance(p, int) else f"[{p}]" for p in e["loc"]).replace(".[", "[")
        msg = str(e["msg"]).removeprefix("Value error, ")
        if e["loc"] and e["loc"][-1] == "business_channel_approved":
            msg = "Confirm that this is a Veda Spaces business channel approved for publication."
        found.append({"field": loc or "content", "code": "INVALID", "message": msg})
    return found


def check(content: dict[str, Any]) -> None:
    """A draft's content is acceptable: known keys only, every entry (inactive ones too) passes every copy rule, and the
    content without its inactive entries is a valid customer pack. Raises ContentError."""
    unknown = sorted(set(content) - set(PACK_KEYS))
    if unknown:
        raise ContentError(
            [{"field": k, "code": "UNKNOWN_FIELD", "message": "not a customer pack field"} for k in unknown]
        )
    flags = _flags(content)
    if flags:
        raise ContentError(flags)
    for keep in (True, False):
        try:
            CustomerPack.model_validate({**_strip(content, keep_inactive=keep), "content_version": "DRAFT"})
        except ValidationError as err:
            raise ContentError(_pydantic(err)) from err


def customer_content(content: dict[str, Any], content_version: str) -> dict[str, Any]:
    """The customer pack a version publishes: its active entries, in order, as a validated CustomerPack."""
    pack = CustomerPack.model_validate({**_strip(content, keep_inactive=False), "content_version": content_version})
    return pack.model_dump(mode="json")


def changed_sections(old: dict[str, Any] | None, new: dict[str, Any]) -> list[str]:
    """Sections whose authoring value differs (an entry marked inactive is a change)."""
    return [s.code for s in SECTIONS if section_digest(old, s.code) != section_digest(new, s.code)]


def has_content(content: dict[str, Any] | None) -> bool:
    c = _strip(content or empty(), keep_inactive=False)
    return any(c.get(k) for k in PACK_KEYS if k != "email_domains")
