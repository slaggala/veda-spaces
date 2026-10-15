"""Semantic differences between two pack versions (CPA-19), in words a reviewer reads, never a raw JSON diff.

Entries are matched by their code: an entry is added, removed, changed (naming each changed field with its before and
after), deactivated or reactivated; a list whose shared entries changed order is reordered. Single values (the
escalation route, the manufacturer-warranty note, the payment-safety wording, the site-dependent-work explanation)
are added, changed or removed.
"""

from __future__ import annotations

from typing import Any

from . import sections as SEC

ENTRY = {"contacts": "Contact", "project_inclusions": "Project inclusion",
         "client_responsibilities": "Customer responsibility", "site_readiness": "Site-readiness requirement",
         "warranty_exclusions": "Warranty exclusion", "handover": "Handover item", "care": "Care item",
         "next_steps": "Next-step stage", "site_dependent_work.categories": "Site-dependent work category"}  # fmt: skip
VALUE = {"support_escalation": "Escalation route", "manufacturer_warranty_note": "Manufacturer-warranty note",
         "payment_safety": "Payment-safety wording", "site_dependent_work.intro": "Site-dependent work explanation",
         "site_dependent_work.approval_rule": "Site-dependent work approval rule",
         "service_guidance.contact_code": "Service contact", "service_guidance.reference_process": "Service process",
         "service_guidance.escalation": "Service escalation",
         "service_guidance.what_to_provide": "What the customer provides when asking for service"}  # fmt: skip
FIELD = {"text": "wording", "category": "category", "kind": "contact type", "display_name": "name", "role": "role",
         "phone": "phone", "email": "e-mail", "hours": "hours", "channel_note": "channel note",
         "default_status": "default status", "stage": "stage", "label": "name", "duration": "approved duration",
         "business_channel_approved": "business-channel approval"}  # fmt: skip


def _change(section: str, kind: str, subject: str, message: str, before: Any = None, after: Any = None,
            item: str | None = None) -> dict[str, Any]:  # fmt: skip
    return {"section": section, "change": kind, "subject": subject, "item": item, "message": message,
            "before": before, "after": after}  # fmt: skip


def _entries(section: str, key: str, old: list | None, new: list | None) -> list[dict[str, Any]]:
    label = ENTRY[key]
    before = {x["code"]: x for x in old or [] if isinstance(x, dict) and "code" in x}
    after = {x["code"]: x for x in new or [] if isinstance(x, dict) and "code" in x}
    out = []
    for code, x in after.items():
        if code not in before:
            state = " (inactive)" if x.get("active") is False else ""
            out.append(_change(section, "ADDED", label, f"{label} added: {code}{state}", None, _shown(x), code))
            continue
        y = before[code]
        if (y.get("active") is not False) != (x.get("active") is not False):
            kind = "DEACTIVATED" if x.get("active") is False else "REACTIVATED"
            out.append(_change(section, kind, label, f"{label} {kind.lower()}: {code}", None, None, code))
        for field in sorted(set(x) | set(y)):
            if field in ("code", "active") or x.get(field) == y.get(field):
                continue
            name = FIELD.get(field, field.replace("_", " "))
            out.append(_change(section, "CHANGED", label, f"{label} {code}: {name} changed", y.get(field),
                               x.get(field), code))  # fmt: skip
    for code, y in before.items():
        if code not in after:
            out.append(_change(section, "REMOVED", label, f"{label} removed: {code}", _shown(y), None, code))
    shared_old = [c for c in before if c in after]
    shared_new = [c for c in after if c in before]
    if shared_old != shared_new:
        out.append(_change(section, "REORDERED", label, f"{label}s reordered", shared_old, shared_new))
    return out


def _shown(x: dict[str, Any]) -> str | None:
    return x.get("text") or x.get("label") or x.get("display_name")


def _value(section: str, key: str, old: Any, new: Any) -> list[dict[str, Any]]:
    if old == new or (not old and not new):
        return []
    label = VALUE[key]
    kind = "ADDED" if not old else ("REMOVED" if not new else "CHANGED")
    return [_change(section, kind, label, f"{label} {kind.lower()}", old or None, new or None)]


def diff(old: dict[str, Any] | None, new: dict[str, Any]) -> list[dict[str, Any]]:
    o, n = old or SEC.empty(), new
    out: list[dict[str, Any]] = []
    for s in SEC.SECTIONS:
        for key in s.keys:
            a, b = o.get(key), n.get(key)
            if key in ENTRY:
                out += _entries(s.code, key, a, b)
            elif key == "email_domains":
                for d in sorted(set(b or []) - set(a or [])):
                    out.append(_change(s.code, "ADDED", "Business e-mail domain", f"Business e-mail domain added: {d}",
                                       None, d))  # fmt: skip
                for d in sorted(set(a or []) - set(b or [])):
                    out.append(_change(s.code, "REMOVED", "Business e-mail domain",
                                       f"Business e-mail domain removed: {d}", d, None))  # fmt: skip
            elif key in ("site_dependent_work", "service_guidance"):
                a, b = a or {}, b or {}
                if bool(a) != bool(b):
                    title = "Site-dependent work policy" if key == "site_dependent_work" else "Service guidance"
                    out.append(
                        _change(s.code, "ADDED" if b else "REMOVED", title, f"{title} {'added' if b else 'removed'}")
                    )
                for field in sorted(set(a) | set(b)):
                    if field == "categories":
                        out += _entries(s.code, "site_dependent_work.categories", a.get(field), b.get(field))
                    elif a and b:
                        out += _value(s.code, f"{key}.{field}", a.get(field), b.get(field))
            else:
                out += _value(s.code, key, a, b)
    return out
