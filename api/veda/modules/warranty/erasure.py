"""Lead erasure for warranty and service (WSV-070): redact, never delete.

Every free-text field written by the customer or by staff about the customer's home is replaced with ``[erased]``:
the request's description and area, notes, assessment explanations, reasons and period bases, visit notes, resolution
summaries and notes, evidence captions. Rows, codes, dates, states and digests stay, so the history keeps its shape;
the timeline holds no text and is never touched. The entitlement's frozen statements are the accepted quotation's
contract terms and are retained (as the quotation module retains its terms); they name no person. Photos are erased by
the attachment module (bytes deleted, rows kept). No retention period is invented: nothing is purged here.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import (
    ServiceAssessment,
    ServiceEvidence,
    ServiceNote,
    ServiceRequest,
    ServiceResolution,
    ServiceVisit,
    WarrantyEntitlement,
)

ERASED = "[erased]"
TEXT_FIELDS = [
    (ServiceRequest, ("description", "area")),
    (ServiceNote, ("text",)),
    (ServiceAssessment, ("explanation", "internal_reason", "period_basis")),
    (ServiceVisit, ("customer_note", "internal_note", "cancel_reason")),
    (ServiceResolution, ("summary", "internal_note")),
    (ServiceEvidence, ("caption",)),
]


def _rows(s: Session, model, lead_id: str):
    return (
        s.execute(sa.select(model).where(model.lead_id == lead_id).execution_options(include_deleted=True))
        .scalars()
        .all()
    )


def erase_for_lead(s: Session, lead) -> int:
    erasure = s.info.setdefault("erasure_entities", set())
    touched = 0
    for model, fields in TEXT_FIELDS:
        for row in _rows(s, model, lead.id):
            erasure.add(row.id)
            for f in fields:
                if getattr(row, f):
                    setattr(row, f, ERASED)
            touched += 1
    s.flush()
    return touched


def audit_ids_for_lead(s: Session, lead_id: str) -> list[str]:
    return [row.id for model, _ in TEXT_FIELDS for row in _rows(s, model, lead_id)] + [
        row.id for row in _rows(s, WarrantyEntitlement, lead_id)
    ]
