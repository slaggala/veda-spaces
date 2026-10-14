"""CQX lead-erasure cascade (07 §8.2) and its retention boundary.

Erased with the lead: every live link is revoked (LEAD_ERASED) so it stops serving at once; the text a customer typed
(request bodies, requested quantities), staff responses, recipient labels and any network/device evidence of an
acceptance. Customer messages are not kept after erasure.

Retained (commercial and audit record, describing the proposal, not a person): link states and dates, view counts,
choice states, request categories and statuses, acknowledged sections with their digests, and the acceptance evidence
digests, method, version and totals (the accepted quotation itself follows the B4 retention rules). Every touched row
joins the transaction's erasure set so the erasure-audit job rewrites its audit payloads.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from . import grants
from .models import (
    CustomerOptionalSelection,
    CustomerProposalRequest,
    ProposalAccessGrant,
    ProposalEvent,
    QuotationAcceptanceEvidence,
    QuotationAcknowledgement,
)

ERASED = "[erased]"
TEXT_FIELDS: list[tuple] = [
    (ProposalAccessGrant, ("recipient_label",)),
    (ProposalEvent, ()),
    (CustomerOptionalSelection, ()),
    (CustomerProposalRequest, ("body", "staff_response", "requested_quantity")),
    (QuotationAcknowledgement, ()),
    (QuotationAcceptanceEvidence, ()),  # + network
]


def _rows(s: Session, model, lead_id: str):
    return (
        s.execute(sa.select(model).where(model.lead_id == lead_id).execution_options(include_deleted=True))
        .scalars()
        .all()
    )


def erase_for_lead(s: Session, lead) -> int:
    grants.revoke_all_for_lead(s, lead.id, "LEAD_ERASED")
    s.flush()
    erasure = s.info.setdefault("erasure_entities", set())
    touched = 0
    for model, fields in TEXT_FIELDS:
        for row in _rows(s, model, lead.id):
            erasure.add(row.id)
            for f in fields:
                if getattr(row, f):
                    setattr(row, f, ERASED)
            if isinstance(row, QuotationAcceptanceEvidence) and row.network:
                row.network = None
            touched += 1
    s.flush()
    return touched


def audit_ids_for_lead(s: Session, lead_id: str) -> list[str]:
    return [row.id for model, _ in TEXT_FIELDS for row in _rows(s, model, lead_id)]
