"""MTQ B2-B4 lead-erasure cascade (07 §8.2). Quantities, prices and decisions describe work, not a person, and stay;
free text that may describe the customer (notes, decision and override reasons) is replaced, and every row joins the
transaction's erasure set so the erasure-audit job rewrites its audit payloads. Later phases add their tables to
``TEXT_FIELDS`` (quotation cover notes and decision notes)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import Boq, BoqLine, CostEstimate, CostEstimateAdjustment, CostEstimateLine, Requirement, Scope, ScopeItem

ERASED = "[erased]"
# (model, lead column or None, parent (model, fk) when the row has no lead column, free-text fields)
TEXT_FIELDS: list[tuple] = [
    (Requirement, "lead_id", None, ("notes", "decision_reason")),
    (Scope, "lead_id", None, ("notes",)),
    (ScopeItem, None, (Scope, "scope_id"), ("notes", "override_reason")),
    (Boq, "lead_id", None, ()),
    (BoqLine, None, (Boq, "boq_id"), ("override_reason",)),
    (CostEstimate, "lead_id", None, ("notes",)),
    (CostEstimateLine, None, (CostEstimate, "estimate_id"), ()),
    (CostEstimateAdjustment, None, (CostEstimate, "estimate_id"), ("reason", "decision_note")),
]


def _rows(s: Session, model, lead_col, parent, lead_id: str):
    if lead_col is not None:
        stmt = sa.select(model).where(getattr(model, lead_col) == lead_id)
    else:
        pmodel, fk = parent
        stmt = sa.select(model).where(getattr(model, fk).in_(sa.select(pmodel.id).where(pmodel.lead_id == lead_id)))
    return s.execute(stmt.execution_options(include_deleted=True)).scalars().all()


def erase_for_lead(s: Session, lead) -> int:
    erasure = s.info.setdefault("erasure_entities", set())
    touched = 0
    for model, lead_col, parent, fields in TEXT_FIELDS:
        for row in _rows(s, model, lead_col, parent, lead.id):
            erasure.add(row.id)
            for f in fields:
                if getattr(row, f):
                    setattr(row, f, ERASED)
            touched += 1
    return touched


def audit_ids_for_lead(s: Session, lead_id: str) -> list[str]:
    ids: list[str] = []
    for model, lead_col, parent, _ in TEXT_FIELDS:
        ids += [row.id for row in _rows(s, model, lead_col, parent, lead_id)]
    return ids
