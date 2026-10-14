"""MTQ B2-B4 lead-erasure cascade (07 §8.2) and its retention boundary.

Erased: every free-text field that may describe the customer: requirement notes and decision reasons, scope and scope
item notes, override reasons (applied and carried), BOQ override reasons, estimate notes, discount reasons and decision
notes, quotation titles, cover notes and decision notes, and the reasons and notes in quotation lifecycle events (a
return-to-draft reason). In a frozen (issued) customer document the customer's name, the subject and the cover note are
redacted and the document re-sealed (``rendering.redact``, event SNAPSHOT_REDACTED with the previous digests).

Retained (commercial and audit record, describing work, not a person): quantities, derivations and measurement
references, rates, amounts, discounts, tax, decisions and their methods, statuses, dates, actor ids, digests, the
quotation number, the property reference, configuration and city, terms, assumptions and exclusions. Every touched row
joins the transaction's erasure set so the erasure-audit job rewrites its audit payloads.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import (
    Boq,
    BoqLine,
    CostEstimate,
    CostEstimateAdjustment,
    CostEstimateLine,
    Quotation,
    QuotationEvent,
    QuotationLine,
    QuotationSection,
    Requirement,
    Scope,
    ScopeItem,
)

ERASED = "[erased]"
# (model, lead column or None, parent (model, fk) when the row has no lead column, free-text fields)
TEXT_FIELDS: list[tuple] = [
    (Requirement, "lead_id", None, ("notes", "decision_reason")),
    (Scope, "lead_id", None, ("notes",)),
    (ScopeItem, None, (Scope, "scope_id"), ("notes", "override_reason")),  # + carried_overrides.reason
    (Boq, "lead_id", None, ()),
    (BoqLine, None, (Boq, "boq_id"), ("override_reason",)),
    (CostEstimate, "lead_id", None, ("notes",)),
    (CostEstimateLine, None, (CostEstimate, "estimate_id"), ()),
    (CostEstimateAdjustment, None, (CostEstimate, "estimate_id"), ("reason", "decision_note")),
    (Quotation, "lead_id", None, ("title", "cover_note", "decision_note")),  # + the frozen document
    (QuotationSection, None, (Quotation, "quotation_id"), ()),
    (QuotationLine, None, (Quotation, "quotation_id"), ()),
    (QuotationEvent, None, (Quotation, "quotation_id"), ()),  # + free-text keys of detail
]
EVENT_TEXT_KEYS = ("reason", "note", "comment")


def _rows(s: Session, model, lead_col, parent, lead_id: str):
    if lead_col is not None:
        stmt = sa.select(model).where(getattr(model, lead_col) == lead_id)
    else:
        pmodel, fk = parent
        stmt = sa.select(model).where(getattr(model, fk).in_(sa.select(pmodel.id).where(pmodel.lead_id == lead_id)))
    return s.execute(stmt.execution_options(include_deleted=True)).scalars().all()


def erase_for_lead(s: Session, lead) -> int:
    from . import rendering

    erasure = s.info.setdefault("erasure_entities", set())
    touched = 0
    for model, lead_col, parent, fields in TEXT_FIELDS:
        for row in _rows(s, model, lead_col, parent, lead.id):
            erasure.add(row.id)
            for f in fields:
                if getattr(row, f):
                    setattr(row, f, ERASED)
            if isinstance(row, ScopeItem) and (row.carried_overrides or {}).get("reason"):
                row.carried_overrides = {**row.carried_overrides, "reason": ERASED}
            if isinstance(row, Quotation):
                rendering.redact(s, row)
            if isinstance(row, QuotationEvent) and any(row.detail.get(k) for k in EVENT_TEXT_KEYS):
                row.detail = {k: (ERASED if k in EVENT_TEXT_KEYS and v else v) for k, v in row.detail.items()}
            touched += 1
    s.flush()
    for row in _rows(s, QuotationEvent, None, (Quotation, "quotation_id"), lead.id):
        erasure.add(row.id)  # the SNAPSHOT_REDACTED events written above
    return touched


def audit_ids_for_lead(s: Session, lead_id: str) -> list[str]:
    ids: list[str] = []
    for model, lead_col, parent, _ in TEXT_FIELDS:
        ids += [row.id for row in _rows(s, model, lead_col, parent, lead_id)]
    return ids
