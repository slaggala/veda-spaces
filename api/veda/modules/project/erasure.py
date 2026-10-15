"""Project lifecycle lead-erasure cascade (07 §8.2) and its retention boundary.

Erased with the lead: every free-text field staff wrote about the project, any of which may describe the customer:
blocker titles, descriptions, customer actions and resolutions; site-readiness labels, actions, customer actions and
notes; checklist notes and reasons; milestone labels, customer labels, descriptions and reasons; quality-check
observations; snag titles, descriptions, item references and resolution notes; transition reasons, decision reasons,
handover acknowledgement references and observations; evidence references; member removal reasons.

Retained (operational and audit record, describing work, not a person): codes, statuses, stages, dates, actor ids,
counts, digests and the commercial-baseline lineage. The timeline (``project_event``) holds no free text, so it is
neither changed nor needed to be. Every touched row joins the transaction's erasure set so the erasure-audit job
rewrites its audit payloads. After erasure the project is closed to writes (``access.writable``).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import (
    ProjectBlocker,
    ProjectChecklistItem,
    ProjectMember,
    ProjectMilestone,
    ProjectQcCheck,
    ProjectSiteReadiness,
    ProjectSnag,
    ProjectTransition,
)

ERASED = "[erased]"
TEXT_FIELDS: list[tuple] = [
    (ProjectBlocker, ("title", "description", "customer_action", "resolution")),
    (ProjectSiteReadiness, ("label", "action", "customer_action", "note", "evidence_reference")),
    (ProjectChecklistItem, ("note", "not_applicable_reason", "reopen_reason", "evidence_reference")),
    (ProjectMilestone, ("label", "customer_label", "description", "status_reason", "evidence_reference")),
    (ProjectQcCheck, ("observation", "evidence_reference")),
    (
        ProjectSnag,
        (
            "customer_title",
            "description",
            "item_reference",
            "resolution_note",
            "classification_reason",
            "evidence_reference",
        ),
    ),
    (ProjectTransition, ("reason", "decision_reason", "acknowledgement_reference", "observations")),
    (ProjectMember, ("removal_reason",)),
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
    return [row.id for model, _ in TEXT_FIELDS for row in _rows(s, model, lead_id)]
