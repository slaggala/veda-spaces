"""The handover package (PEX-040 … PEX-044): what is handed over, frozen with a SHA-256, and the customer's
acknowledgement of exactly that.

``content`` is built from authoritative records only, and only from customer-safe fields (``classification``):

- ``scope``: the accepted quotation chain and the current effective baseline (sequence and digest) being handed over;
- ``work``: the customer-visible work packages completed (their customer labels and dates), and counts of all work;
- ``quality``: counts of quality-check chains passed, and confirmation that none ends in a failure;
- ``snags``: counts by outcome; open non-blocking snags listed only when customer-visible (review D9);
- ``documents``: none. No customer-visible document class is approved (CPP-D04); nothing is published here;
- ``warranty``: a pointer to the accepted quotation's own warranty section. No warranty term is written here.

Preparing needs READY_FOR_HANDOVER and a handover evaluation with no blocker other than the owner's policy gate and
the evidence given at completion (review D7). Preparing again supersedes the current package (one PREPARED at a time);
preparing when nothing changed returns the current package. The handover is bound to the current package and digest
(``service.complete_handover``); the structural HANDOVER_PACKAGE gate re-verifies, at completion and at any approval,
that it is still the current one and still what the records say (review D5).
"""

from __future__ import annotations

import hashlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError, not_found
from veda.kernel.jcs import canonical_bytes

from . import access, baseline, events, gates, quality, service, work
from . import vocab as V
from .models import Project, ProjectHandoverPackage, ProjectSnag

SCHEMA = "veda.project.handover-package/1"
TEXT_KEYS = ("label", "title")  # the only free text in a package (customer labels and customer titles)


def digest(content: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(content)).hexdigest()


def redact(content: Any, erased: str) -> Any:
    if isinstance(content, dict):
        return {k: (erased if k in TEXT_KEYS and isinstance(v, str) else redact(v, erased)) for k, v in content.items()}
    if isinstance(content, list):
        return [redact(v, erased) for v in content]
    return content


def current(s: Session, p: Project) -> ProjectHandoverPackage | None:
    return s.execute(sa.select(ProjectHandoverPackage).where(ProjectHandoverPackage.project_id == p.id,
                                                             ProjectHandoverPackage.status == "PREPARED",
                                                             ProjectHandoverPackage.is_deleted == sa.false())
                     ).scalar_one_or_none()  # fmt: skip


def packages(s: Session, p: Project) -> list[ProjectHandoverPackage]:
    return list(s.execute(sa.select(ProjectHandoverPackage).where(ProjectHandoverPackage.project_id == p.id,
                                                                  ProjectHandoverPackage.is_deleted == sa.false())
                          .order_by(ProjectHandoverPackage.package_no)).scalars())  # fmt: skip


def portal_reference(pkg: ProjectHandoverPackage) -> str:
    return f"PORTAL-ACKNOWLEDGED package {pkg.package_no} ({pkg.content_sha256[:12]})"


def _day(value) -> str | None:
    return value.isoformat() if value else None


def build(s: Session, p: Project) -> dict[str, Any]:
    """The package content as the records say now. Deterministic: rebuilt to detect staleness."""
    base = baseline.current(s, p)
    rows = work.rows(s, p)
    checks = quality.checks(s, p)
    chains = quality.chains(checks)
    snags = list(s.execute(sa.select(ProjectSnag).where(ProjectSnag.project_id == p.id,
                                                        ProjectSnag.is_deleted == sa.false())
                           .order_by(ProjectSnag.snag_no)).scalars())  # fmt: skip
    open_nb = [n for n in snags if n.status in V.SNAG_OPEN and not n.is_blocking]
    return {
        "schema": SCHEMA,
        "scope": {"quotation_number": p.quotation_number, "source_quotation_id": p.source_quotation_id,
                  "baseline_seq": base.sequence_no, "baseline_sha256": base.baseline_sha256,
                  "accepted_quotation_ids": [r.quotation_id for r in baseline.rows(s, p.id)]},
        "work": {
            "completed": [{"label": wp.customer_label, "finished_on": _day(wp.actual_finish)}
                          for wp in rows if wp.customer_visible and wp.status == "COMPLETED"],
            "completed_count": sum(1 for wp in rows if wp.status == "COMPLETED"),
            "cancelled_count": sum(1 for wp in rows if wp.status == "CANCELLED"),
        },
        "quality": {"checks_passed": sum(1 for c in chains if c[-1].result == "PASS"),
                    "checks_not_applicable": sum(1 for c in chains if c[-1].result == "NOT_APPLICABLE"),
                    "corrected_after_failure": sum(1 for c in chains if quality.ever_failed(c) and c[-1].result == "PASS"),
                    "failed": sum(1 for c in chains if c[-1].result == "FAIL")},
        "snags": {"fixed_and_verified": sum(1 for n in snags if n.closure_code == "FIXED" or n.status == "RESOLVED"),
                  "closed_without_fix": sum(1 for n in snags if n.closure_code in V.SNAG_CLOSED_WITHOUT_FIX),
                  "open_non_blocking": [{"number": n.snag_no, "title": n.customer_title}
                                        for n in open_nb if n.customer_visible],
                  "open_non_blocking_count": len(open_nb)},
        "documents": [],
        "documents_note": "CPP-D04",
        "warranty": {"source": "ACCEPTED_QUOTATION", "quotation_id": base.quotation_id,
                     "quotation_number": base.quotation_number},
    }  # fmt: skip


def staleness(s: Session, p: Project, pkg: ProjectHandoverPackage) -> str | None:
    """None when the package is the current one and still what the records say; else a blocker code."""
    if pkg.status != "PREPARED":
        return "HANDOVER_PACKAGE_SUPERSEDED"
    if digest(pkg.content) != pkg.content_sha256:
        return "HANDOVER_PACKAGE_ALTERED"
    if digest(build(s, p)) != pkg.content_sha256:
        return "HANDOVER_PACKAGE_STALE"
    return None


ALLOWED_WHILE_PREPARING = ("POLICY_RECORDED", "HANDOVER_EVIDENCE", "HANDOVER_PACKAGE")


def prepare(s: Session, ctx, p: Project, if_match: int | None) -> ProjectHandoverPackage:
    access.for_write(s, ctx, p, "project.complete_handover", if_match=if_match)
    if p.stage_code != "READY_FOR_HANDOVER":
        raise ApiError(409, "INVALID_STATE", "The handover package is prepared once the project is ready for handover.")
    if gates.pending(s, p) is not None:
        raise ApiError(409, "TRANSITION_AWAITING_APPROVAL", "A handover is waiting for approval; approve, reject or "
                       "withdraw it before preparing a new package.")  # fmt: skip
    ev = gates.evaluate(s, p, "HANDED_OVER", command="HANDOVER")
    stops = [b for b in ev["blockers"] if b["gate"] not in ALLOWED_WHILE_PREPARING]
    if stops:
        raise ApiError(409, "HANDOVER_NOT_READY", f"{len(stops)} item(s) stand between the project and its handover.",
                       extra={"blockers": stops})  # fmt: skip
    content = build(s, p)
    sha = digest(content)
    cur = current(s, p)
    if cur is not None and cur.content_sha256 == sha and not cur.redacted:
        return cur  # nothing changed: the same package (a repeated request is safe)
    now = db.tx_time(s)
    if cur is not None:
        cur.status, cur.superseded_on, cur.superseded_by = "SUPERSEDED", now, ctx.user.id
        events.record(s, p, "HANDOVER_PACKAGE_SUPERSEDED", stage=p.stage_code, frm="PREPARED", to="SUPERSEDED",
                      package_id=cur.id, package_sha256=cur.content_sha256)  # fmt: skip
        s.flush()  # one PREPARED package per project (ux_project_handover_package__one_current)
    n = s.execute(sa.select(sa.func.max(ProjectHandoverPackage.package_no))
                  .where(ProjectHandoverPackage.project_id == p.id)).scalar() or 0  # fmt: skip
    pkg = ProjectHandoverPackage(project_id=p.id, lead_id=p.lead_id, package_no=n + 1, status="PREPARED",
                                 content=content, content_sha256=sha, redacted=False)  # fmt: skip
    s.add(pkg)
    s.flush()
    events.record(s, p, "HANDOVER_PACKAGE_PREPARED", stage=p.stage_code, to="PREPARED", package_id=pkg.id,
                  package_no=pkg.package_no, package_sha256=sha)  # fmt: skip
    from . import notices

    notices.customer(s, p, notices.HANDOVER_PACKAGE_READY, package_id=pkg.id)
    service.done(p, s)
    return pkg


def acknowledge(
    s: Session, account_id: str, p: Project, package_id: str, sha: str
) -> tuple[ProjectHandoverPackage, bool]:
    """The customer's acknowledgement of one package by id and digest (PEX-D01 allows it; the caller checks the flags,
    the decision and the customer's access). Repeating it returns the same acknowledgement and records nothing."""
    access.lock(s, p)
    pkg = s.get(ProjectHandoverPackage, package_id)
    if pkg is None or pkg.project_id != p.id or pkg.is_deleted:
        raise not_found()
    s.refresh(pkg)
    if pkg.content_sha256 != sha:
        raise ApiError(409, "HANDOVER_PACKAGE_CHANGED", "This handover summary has changed since you opened it. Please "
                       "review the current one.")  # fmt: skip
    if pkg.status == "SUPERSEDED":  # an earlier acknowledgement never answers for a package that was replaced
        raise ApiError(409, "HANDOVER_PACKAGE_CHANGED", "This handover summary has been replaced. Please review the "
                       "current one.")  # fmt: skip
    if pkg.acknowledged_on is not None:
        return pkg, False
    if pkg.status != "PREPARED" or staleness(s, p, pkg) is not None:
        raise ApiError(409, "HANDOVER_PACKAGE_CHANGED", "Veda Spaces is updating your handover summary. Please check "
                       "again shortly.")  # fmt: skip
    from veda.modules.crm.leads.models import Lead

    lead = s.get(Lead, p.lead_id)
    if lead is None or lead.anonymized_on is not None or p.status != "ACTIVE":
        raise not_found()
    pkg.acknowledged_on, pkg.acknowledged_account_id = db.tx_time(s), account_id
    events.record(s, p, "HANDOVER_ACKNOWLEDGED", stage=p.stage_code, package_id=pkg.id,
                  package_sha256=pkg.content_sha256, account_id=account_id)  # fmt: skip
    from . import notices

    notices.staff(s, p, notices.HANDOVER_ACKNOWLEDGED, package_id=pkg.id)
    access.touch(s, p)
    s.flush()
    return pkg, True


def gate(s: Session, p: Project, handover: dict[str, Any]) -> list[dict[str, Any]]:
    """HANDOVER_PACKAGE (structural for the handover command): the bound package is the current one and unchanged."""
    pid, sha = handover.get("handover_package_id"), handover.get("handover_package_sha256")
    if not pid:
        return [{"gate": "HANDOVER_PACKAGE", "code": "HANDOVER_PACKAGE_MISSING", "message": "Prepare the handover "
                 "package first.", "responsible_party": "VEDA"}]  # fmt: skip
    pkg = s.get(ProjectHandoverPackage, pid)
    code = "HANDOVER_PACKAGE_SUPERSEDED" if pkg is None or pkg.content_sha256 != sha else staleness(s, p, pkg)
    if code is None:
        return []
    return [{"gate": "HANDOVER_PACKAGE", "code": code, "message": "The handover package is no longer current; prepare "
             "it again (and have it acknowledged again).", "responsible_party": "VEDA",
             "entity": {"type": "handover_package", "id": pid}}]  # fmt: skip


def acknowledged(s: Session, handover: dict[str, Any]) -> bool:
    pid = handover.get("handover_package_id")
    pkg = s.get(ProjectHandoverPackage, pid) if pid else None
    return bool(pkg is not None and pkg.acknowledged_on is not None
                and pkg.content_sha256 == handover.get("handover_package_sha256"))  # fmt: skip


def present(pkg: ProjectHandoverPackage) -> dict[str, Any]:
    return {"id": pkg.id, "version": pkg.version, "package_no": pkg.package_no, "status": pkg.status,
            "content": pkg.content, "content_sha256": pkg.content_sha256, "redacted": pkg.redacted,
            "prepared_on": clock.to_rfc3339(pkg.created_on), "prepared_by": pkg.created_by,
            "acknowledged_on": clock.to_rfc3339(pkg.acknowledged_on) if pkg.acknowledged_on else None,
            "completed_on": clock.to_rfc3339(pkg.completed_on) if pkg.completed_on else None,
            "superseded_on": clock.to_rfc3339(pkg.superseded_on) if pkg.superseded_on else None}  # fmt: skip
