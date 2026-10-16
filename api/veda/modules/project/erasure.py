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

PEX adds: work-package titles, descriptions, customer labels and notes; QC-plan labels and withdrawal reasons; snag fix
notes; blocker customer summaries; customer reports (the customer's own words, the area and the staff response). A
handover package is redacted, never re-sealed under its original digest: its text leaves become ``[erased]``,
``redacted_sha256`` records the redacted content's digest, ``content_sha256`` keeps the digest the acknowledgement and
the handover were bound to, and a HANDOVER_PACKAGE_REDACTED event names both (review D10).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import (
    Project,
    ProjectBlocker,
    ProjectChecklistItem,
    ProjectCustomerReport,
    ProjectHandoverPackage,
    ProjectMember,
    ProjectMilestone,
    ProjectQcCheck,
    ProjectQcPoint,
    ProjectSiteReadiness,
    ProjectSnag,
    ProjectTransition,
    ProjectWorkPackage,
)

ERASED = "[erased]"
TEXT_FIELDS: list[tuple] = [
    (ProjectBlocker, ("title", "description", "customer_action", "resolution", "customer_summary")),
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
            "fix_note",
        ),
    ),
    (ProjectTransition, ("reason", "decision_reason", "acknowledgement_reference", "observations")),
    (ProjectMember, ("removal_reason",)),
    (
        ProjectWorkPackage,
        (
            "title",
            "description",
            "customer_label",
            "completion_note",
            "reopen_reason",
            "cancel_reason",
            "evidence_reference",
            "replan_reason",
        ),
    ),
    (ProjectQcPoint, ("label", "withdrawn_reason")),
    (ProjectCustomerReport, ("description", "area", "response")),
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
    from . import events, handover

    for pkg in _rows(s, ProjectHandoverPackage, lead.id):
        erasure.add(pkg.id)
        if pkg.redacted:
            continue
        pkg.content = handover.redact(pkg.content, ERASED)
        pkg.redacted, pkg.redacted_sha256 = True, handover.digest(pkg.content)
        p = s.get(Project, pkg.project_id)
        if p is not None:
            events.record(s, p, "HANDOVER_PACKAGE_REDACTED", stage=p.stage_code, package_id=pkg.id,
                          content_sha256=pkg.content_sha256, redacted_sha256=pkg.redacted_sha256)  # fmt: skip
        touched += 1
    s.flush()
    return touched


def audit_ids_for_lead(s: Session, lead_id: str) -> list[str]:
    return [row.id for model, _ in TEXT_FIELDS for row in _rows(s, model, lead_id)] + [
        row.id for row in _rows(s, ProjectHandoverPackage, lead_id)
    ]
