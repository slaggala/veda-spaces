"""The project's commercial baseline (PLB-01, PLB-03, PLB-31, PLB-48).

A project executes one accepted commercial chain (a quotation number). Its baseline is a lineage, never a copy:

    Original accepted baseline (the base quotation) → Variation 1 → Variation 2 → current effective baseline

Each ``project_baseline`` row references one ACCEPTED quotation version (base or variation) with the digests that make
it reproducible (the frozen document, the effective accepted baseline frozen at acceptance, the estimate it was priced
from) and its lineage (measurement, scope, BOQ, estimate revisions), the Customer Promise pack it froze, the cumulative
accepted value, and a SHA-256 over that reference which also covers the previous row's digest: a chain that cannot be
edited without detection. Rows are only ever appended.

Nothing here changes a quotation. The Project Lifecycle never prices, never issues a variation and never adds scope:
a variation is raised, priced, issued and accepted through the existing B4/CQX route, and its acceptance (in the same
transaction, ``on_quotation_accepted``) appends the next baseline row. Operational work (checklists, stages, snags)
has no path to any quotation amount.
"""

from __future__ import annotations

import hashlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.kernel.jcs import canonical_bytes
from veda.modules.mtq_commercial import quotations
from veda.modules.mtq_commercial.models import CostEstimate, Quotation

from . import events
from .models import Project, ProjectBaseline


def _promise(q: Quotation) -> dict[str, Any] | None:
    terms = q.terms or {}
    ref = terms.get("customer_promise") or {}
    pack = terms.get("customer_pack") or {}
    if not ref and not pack:
        return None
    return {"pack_id": ref.get("pack_id"), "version_no": ref.get("version_no"), "sha256": ref.get("sha256"),
            "content_version": pack.get("content_version")}  # fmt: skip


def reference(row: ProjectBaseline, previous_sha256: str | None) -> dict[str, Any]:
    """The canonical reference document a baseline row's digest is computed over."""
    return {
        "kind": row.kind, "sequence_no": row.sequence_no, "previous_baseline_sha256": previous_sha256,
        "quotation_id": row.quotation_id, "quotation_number": row.quotation_number, "variation_no": row.variation_no,
        "version_no": row.version_no, "snapshot_sha256": row.snapshot_sha256,
        "accepted_baseline_sha256": row.accepted_baseline_sha256, "accepted_total_minor": row.accepted_total_minor,
        "cumulative_value_minor": row.cumulative_value_minor, "decision_method": row.decision_method,
        "decided_on": clock.to_rfc3339(row.decided_on), "selected_optional_count": row.selected_optional_count,
        "measurement_set_id": row.measurement_set_id, "measurement_revision_no": row.measurement_revision_no,
        "scope_id": row.scope_id, "scope_revision_no": row.scope_revision_no, "boq_id": row.boq_id,
        "boq_revision_no": row.boq_revision_no, "cost_estimate_id": row.cost_estimate_id,
        "estimate_revision_no": row.estimate_revision_no, "estimate_snapshot_sha256": row.estimate_snapshot_sha256,
        "customer_promise": row.customer_promise,
    }  # fmt: skip


def digest(row: ProjectBaseline, previous_sha256: str | None) -> str:
    return hashlib.sha256(canonical_bytes(reference(row, previous_sha256))).hexdigest()


def accepted_baseline_verifies(q: Quotation) -> bool:
    return (
        q.accepted_baseline is not None
        and q.accepted_baseline_sha256 is not None
        and hashlib.sha256(canonical_bytes(q.accepted_baseline)).hexdigest() == q.accepted_baseline_sha256
    )


def rows(s: Session, project_id: str) -> list[ProjectBaseline]:
    return list(s.execute(sa.select(ProjectBaseline).where(ProjectBaseline.project_id == project_id)
                          .order_by(ProjectBaseline.sequence_no)).scalars())  # fmt: skip


def current(s: Session, p: Project) -> ProjectBaseline:
    found = s.execute(
        sa.select(ProjectBaseline).where(
            ProjectBaseline.project_id == p.id, ProjectBaseline.sequence_no == p.baseline_seq
        )  # fmt: skip
    ).scalar_one_or_none()
    assert found is not None  # the project is created with its original baseline
    return found


def append(s: Session, p: Project, q: Quotation, previous: ProjectBaseline | None) -> ProjectBaseline:
    """Record ``q`` (ACCEPTED) as the project's next baseline. The caller holds the project lock."""
    est = s.get(CostEstimate, q.cost_estimate_id)
    assert est is not None and q.decided_on is not None and q.decision_method is not None
    assert q.accepted_total_minor is not None and q.accepted_baseline_sha256 and q.snapshot_sha256
    value = (previous.cumulative_value_minor if previous else 0) + int(q.accepted_total_minor)
    row = ProjectBaseline(
        project_id=p.id, lead_id=p.lead_id, sequence_no=(previous.sequence_no + 1) if previous else 1,
        kind="ORIGINAL" if previous is None else "VARIATION", previous_baseline_id=previous.id if previous else None,
        quotation_id=q.id, quotation_number=q.quotation_number, variation_no=q.variation_no, version_no=q.version_no,
        snapshot_sha256=q.snapshot_sha256, accepted_baseline_sha256=q.accepted_baseline_sha256,
        accepted_total_minor=int(q.accepted_total_minor), cumulative_value_minor=value,
        decision_method=q.decision_method, decided_on=q.decided_on,
        selected_optional_count=len(q.selected_optional_line_ids or []),
        measurement_set_id=q.measurement_set_id, measurement_revision_no=q.measurement_revision_no,
        scope_id=q.scope_id, scope_revision_no=q.scope_revision_no, boq_id=q.boq_id,
        boq_revision_no=q.boq_revision_no, cost_estimate_id=q.cost_estimate_id,
        estimate_revision_no=q.estimate_revision_no, estimate_snapshot_sha256=q.estimate_snapshot_sha256,
        customer_promise=_promise(q),
    )  # fmt: skip
    row.baseline_sha256 = digest(row, previous.baseline_sha256 if previous else None)
    s.add(row)
    s.flush()
    p.baseline_seq = row.sequence_no
    return row


def accepted_chain(s: Session, number: str) -> list[Quotation]:
    """Every ACCEPTED version of the chain: the base, then each accepted variation in order."""
    return list(s.execute(sa.select(Quotation).where(Quotation.quotation_number == number,
                                                     Quotation.status == "ACCEPTED")
                          .order_by(Quotation.variation_no, Quotation.version_no)).scalars())  # fmt: skip


def open_variations(s: Session, number: str) -> list[Quotation]:
    """Variations still being decided (drafted, in review, approved or issued to the customer)."""
    return list(s.execute(sa.select(Quotation).where(
        Quotation.quotation_number == number, Quotation.variation_no > 0,
        Quotation.status.in_(("DRAFT", "INTERNAL_REVIEW", "APPROVED", "ISSUED")),
    ).order_by(Quotation.variation_no, Quotation.version_no)).scalars())  # fmt: skip


def problems(s: Session, p: Project) -> list[dict[str, Any]]:
    """Why the project's baseline does not verify (empty when it does). Fail closed: any mismatch is a problem."""
    from veda.modules.crm.leads.models import Lead
    from veda.modules.mtq_commercial import rendering

    lead = s.get(Lead, p.lead_id)
    if lead is not None and lead.anonymized_on is not None:  # erasure re-seals the frozen documents (by design)
        return [{"code": "BASELINE_ERASED", "message": "The customer record was erased; the baseline documents were "
                 "redacted and re-sealed, and the project is closed."}]  # fmt: skip
    out: list[dict[str, Any]] = []
    chain = rows(s, p.id)
    previous: str | None = None
    for n, row in enumerate(chain, start=1):
        label = f"baseline {row.sequence_no}"
        if row.sequence_no != n or digest(row, previous) != row.baseline_sha256:
            out.append({"code": "BASELINE_TAMPERED", "message": f"The reference of {label} does not match its digest.",
                        "baseline_id": row.id})  # fmt: skip
        q = s.get(Quotation, row.quotation_id)
        if (q is None or q.status != "ACCEPTED" or q.snapshot_sha256 != row.snapshot_sha256
                or q.accepted_baseline_sha256 != row.accepted_baseline_sha256 or not accepted_baseline_verifies(q)
                or not rendering.integrity(q)):  # fmt: skip
            out.append({"code": "QUOTATION_INTEGRITY_FAILED", "message": f"The accepted quotation of {label} no longer "
                        "matches its sealed digests.", "baseline_id": row.id, "quotation_id": row.quotation_id})  # fmt: skip
        previous = row.baseline_sha256
    if not chain or chain[-1].sequence_no != p.baseline_seq:
        out.append({"code": "BASELINE_POINTER_INVALID", "message": "The current effective baseline is not the latest "
                    "recorded one."})  # fmt: skip
    recorded = {r.quotation_id for r in chain}
    for q in accepted_chain(s, p.quotation_number):
        if q.id not in recorded:
            out.append({"code": "VARIATION_NOT_RECORDED", "message": f"Accepted {quotations.number_label(q)} "
                        "is not in the project's baseline.", "quotation_id": q.id})  # fmt: skip
    return out


def on_quotation_accepted(s: Session, q: Quotation) -> None:
    """Called by the B4 decision service when a quotation is accepted (same transaction). A variation accepted on a
    chain that has a project becomes the project's next effective baseline, under the project lock, with its timeline
    event. The base acceptance creates nothing: a project is booked explicitly (PLB-01)."""
    from . import access

    if q.quotation_kind != "VARIATION":
        return
    p = s.execute(sa.select(Project).where(Project.quotation_number == q.quotation_number)).scalar_one_or_none()
    if p is None:
        return
    access.lock(s, p)
    if s.execute(sa.select(ProjectBaseline.id).where(ProjectBaseline.quotation_id == q.id)).first() is not None:
        return  # already recorded (idempotent)
    previous = current(s, p)
    row = append(s, p, q, previous)
    events.record(s, p, "VARIATION_ACCEPTED", stage=p.stage_code, quotation_id=q.id, variation_no=q.variation_no,
                  version_no=q.version_no, baseline_id=row.id, baseline_seq=row.sequence_no,
                  previous_baseline_sha256=previous.baseline_sha256, baseline_sha256=row.baseline_sha256)  # fmt: skip
    access.touch(s, p)
