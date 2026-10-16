"""Warranty entitlements (WSV-001 … WSV-005): what was promised about warranty for a handed-over project, frozen.

Registered from the project's completed HANDOVER transition, never from a creation or deployment time:

- after the handover commits, by the ``project.handed_over`` subscriber (``project.hooks``) while the flag is on;
- for a project handed over while the flag was off, by the staff command (``warranty.manage``).

Both take the project's row lock, return the existing entitlement if there is one (unique per project; a lost race
returns the winner) and refuse a project that is not handed over or has no completed HANDOVER transition.

``terms`` is built only from authoritative records and never re-derived:

- ``sources``: each accepted quotation of the lineage handed over (the project's baselines recorded up to the handover),
  with its number, version, ``terms_version`` and original snapshot digest, and its verbatim ``warranty`` and
  ``service_support`` statements, manufacturer-warranty note and warranty exclusions. Nothing is parsed, summarised or
  merged: a manufacturer note stays the manufacturer's, Veda Spaces' service support stays apart from the warranty;
- ``handover``: the transition, its date (the start of every HANDOVER-trigger class), its decision time, the package and
  its digest, and the date the customer acknowledged it in the portal (if they did);
- ``coverage``: the structured classes of owner decision WSV-D01 that apply to what the customer accepted (their base
  quotation's ``terms_version`` is listed by the decision); none while WSV-D01 is null. A class marked as conflicting
  with the statements is frozen as not recorded.

Coverage status is computed on read for a date (India's calendar), never stored: NOT_RECORDED (no structured class),
NOT_STARTED, ACTIVE, EXPIRED. It is never a statement that a particular problem is covered: that is an assessment.
"""

from __future__ import annotations

import calendar
import hashlib
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.kernel.errors import ApiError
from veda.kernel.jcs import canonical_bytes

from . import policy
from . import vocab as V
from .models import WarrantyEntitlement

SCHEMA = "veda.warranty.entitlement/1"


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def for_project(s: Session, project_id: str) -> WarrantyEntitlement | None:
    return s.execute(sa.select(WarrantyEntitlement).where(WarrantyEntitlement.project_id == project_id,
                                                          WarrantyEntitlement.is_deleted == sa.false())
                     ).scalar_one_or_none()  # fmt: skip


def _handover(s: Session, p):
    from veda.modules.project.models import ProjectTransition

    return s.execute(sa.select(ProjectTransition).where(ProjectTransition.project_id == p.id,
                                                        ProjectTransition.kind == "HANDOVER",
                                                        ProjectTransition.outcome == "COMPLETED")
                     .order_by(ProjectTransition.created_on.desc())).scalars().first()  # fmt: skip


def _source(s: Session, b) -> dict[str, Any]:
    from veda.modules.customer_proposal import projection
    from veda.modules.mtq_commercial.models import Quotation

    q = s.get(Quotation, b.quotation_id)
    if q is None or q.snapshot_sha256 != b.snapshot_sha256:
        raise ApiError(409, "QUOTATION_INTEGRITY_FAILED", f"The accepted quotation {b.quotation_number} no longer "
                       "matches the digest recorded when it was accepted; the warranty cannot be registered.")  # fmt: skip
    doc = projection.frozen_document(q)  # verified; refuses a document that does not verify
    info = projection.information(doc)
    return {
        "quotation_id": q.id, "quotation_number": b.quotation_number, "kind": b.kind, "version_no": b.version_no,
        "variation_no": b.variation_no, "terms_version": doc.get("terms_version"), "snapshot_sha256": b.snapshot_sha256,
        "warranty": [str(x) for x in doc.get("warranty") or []],
        "service_support": [str(x) for x in doc.get("service_support") or []],
        "manufacturer_warranty_note": info.get("manufacturer_warranty_note"),
        "warranty_exclusions": [{"code": x.get("code"), "text": x.get("text")} for x in info.get("warranty_exclusions") or []],
    }  # fmt: skip


def _coverage(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    d01 = policy.decision("WSV-D01")
    base = sources[0] if sources else None
    if d01 is None or base is None or base.get("terms_version") not in d01.applies_to_terms_versions:
        return []
    return [{"code": c.code, "label": c.label, "covers": c.covers, "exclusions": list(c.exclusions),
             "duration_months": None if c.conflicts_with_statements else c.duration_months, "trigger": c.trigger,
             "conflict": c.conflicts_with_statements, "policy_version": d01.policy_version,
             "policy_text_sha256": d01.policy_text_sha256} for c in d01.classes]  # fmt: skip


def build(s: Session, p, t) -> dict[str, Any]:
    from veda.modules.project import baseline as pbase
    from veda.modules.project.models import ProjectHandoverPackage

    cutoff = t.decided_on or t.created_on
    lineage = [b for b in pbase.rows(s, p.id) if b.created_on <= cutoff]
    if not lineage:
        raise ApiError(409, "BASELINE_MISSING", "The project has no accepted baseline at its handover.")
    pkg = s.get(ProjectHandoverPackage, t.handover_package_id) if t.handover_package_id else None
    sources = [_source(s, b) for b in lineage]
    return {
        "schema": SCHEMA,
        "project": {"id": p.id, "project_number": p.project_number, "property_id": p.property_id},
        "sources": sources,
        "handover": {"transition_id": t.id, "handover_on": t.handover_on.isoformat(),
                     # the staff-entered date is the record; a date before the package was prepared is flagged for staff
                     "date_check": "HANDOVER_DATE_BEFORE_PACKAGE" if pkg and t.handover_on < local_date(pkg.created_on)
                     else None,
                     "decided_on": clock.to_rfc3339(cutoff), "package_id": pkg.id if pkg else None,
                     "package_sha256": t.handover_package_sha256,
                     "acknowledged_on": clock.to_rfc3339(pkg.acknowledged_on) if pkg and pkg.acknowledged_on else None},
        "coverage": _coverage(sources),
        "policy": {"version": policy.current().version, "sha256": policy.sha256()},
    }  # fmt: skip


def register(s: Session, p, via: str) -> tuple[WarrantyEntitlement, bool]:
    """(entitlement, created). The caller holds the project's lock; ``via`` is HANDOVER_EVENT or STAFF."""
    found = for_project(s, p.id)
    if found is not None:
        return found, False
    if p.status != "HANDED_OVER":
        raise ApiError(409, "PROJECT_NOT_HANDED_OVER", "A warranty is registered from the project's handover; this "
                       "project has not been handed over.")  # fmt: skip
    t = _handover(s, p)
    if t is None or t.handover_on is None:
        raise ApiError(409, "HANDOVER_NOT_RECORDED", "The project's completed handover could not be found.")
    terms = build(s, p, t)
    row = WarrantyEntitlement(project_id=p.id, lead_id=p.lead_id, property_id=p.property_id,
                              handover_transition_id=t.id, handover_on=t.handover_on, terms=terms,
                              terms_sha256=digest(terms), policy_version=terms["policy"]["version"],
                              policy_sha256=terms["policy"]["sha256"], registered_via=via)  # fmt: skip
    try:
        with s.begin_nested():
            s.add(row)
            s.flush()
    except IntegrityError:
        winner = for_project(s, p.id)
        if winner is None:
            raise
        return winner, False
    return row, True


def local_date(instant) -> date:
    from zoneinfo import ZoneInfo

    return instant.astimezone(ZoneInfo("Asia/Kolkata")).date()


def today(s: Session) -> date:
    from veda.kernel import db

    return local_date(db.tx_time(s))


# --- coverage status ---------------------------------------------------------------------------------------------------
def add_months(start: date, months: int) -> date:
    y, m = divmod(start.month - 1 + months, 12)
    year, month = start.year + y, m + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def class_status(e: WarrantyEntitlement | None, cls: dict[str, Any], on: date) -> tuple[str, date | None, date | None]:
    """(status, starts, ends) of one coverage class as of ``on``; ends is exclusive."""
    if e is None or cls.get("conflict") or not cls.get("duration_months") or cls.get("trigger") != "HANDOVER":
        return V.NOT_RECORDED, None, None
    start = e.handover_on
    end = add_months(start, int(cls["duration_months"]))
    if on < start:
        return V.NOT_STARTED, start, end
    return (V.ACTIVE if on < end else V.EXPIRED), start, end


def statuses(e: WarrantyEntitlement | None, on: date) -> list[dict[str, Any]]:
    out = []
    for cls in ((e.terms or {}).get("coverage") or []) if e else []:
        status, start, end = class_status(e, cls, on)
        out.append({"code": cls["code"], "label": cls["label"], "covers": cls["covers"],
                    "exclusions": cls.get("exclusions") or [], "status": status,
                    "starts_on": start.isoformat() if start else None,
                    "ends_on": end.isoformat() if end else None, "conflict": bool(cls.get("conflict"))})  # fmt: skip
    return out


def overall(e: WarrantyEntitlement | None, on: date) -> str:
    """The entitlement's headline status: ACTIVE only when a recorded class is active; never "covered"."""
    found = [x["status"] for x in statuses(e, on)]
    for status in (V.ACTIVE, V.NOT_STARTED, V.EXPIRED):
        if status in found:
            return status
    return V.NOT_RECORDED


def cited(e: WarrantyEntitlement, path: str) -> tuple[str, str] | None:
    """(basis kind, text) of a citable statement path ``sources/<i>/warranty/<j>`` or ``sources/<i>/service_support/<j>``
    or ``sources/<i>/warranty_exclusions/<j>`` or ``sources/<i>/manufacturer_warranty_note``; None if it does not exist."""
    import re

    if not re.fullmatch(r"sources/\d{1,3}/(manufacturer_warranty_note|(warranty|service_support|warranty_exclusions)/\d{1,3})", path) \
            or any(len(x) > 1 and x.startswith("0") for x in path.split("/") if x.isdigit()):  # fmt: skip
        return None  # one canonical spelling per statement (review L2)
    parts = path.split("/")
    try:
        src = (e.terms or {})["sources"][int(parts[1])] if len(parts) >= 3 and parts[0] == "sources" else None
    except (IndexError, ValueError, KeyError):
        return None
    if src is None:
        return None
    kinds = {"warranty": "WARRANTY_STATEMENT", "service_support": "SERVICE_SUPPORT_STATEMENT",
             "warranty_exclusions": "EXCLUSION"}  # fmt: skip
    if len(parts) == 3 and parts[2] == "manufacturer_warranty_note":
        note = src.get("manufacturer_warranty_note")
        return ("MANUFACTURER_NOTE", note) if note else None
    if len(parts) != 4 or parts[2] not in kinds:
        return None
    try:
        item = src[parts[2]][int(parts[3])]
    except (IndexError, ValueError, KeyError, TypeError):
        return None
    text = item["text"] if isinstance(item, dict) else item
    return (kinds[parts[2]], text) if text else None
