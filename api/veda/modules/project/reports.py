"""Customer reports (PEX-035 … PEX-038): an issue the customer reports, in their own words, never a defect by itself.

A report is SUBMITTED, then triaged by staff with ``project.manage_snag``: ACCEPTED as a new snag (raised with
source CUSTOMER and shown to the customer), ACCEPTED against an existing snag (which becomes visible to the customer),
or DECLINED with a code and a response the customer reads. An untriaged report stops handover readiness (the structural
CUSTOMER_REPORTS_TRIAGED gate).

Two channels:

- **Portal** (``submit``): only while owner decision PEX-D01 allows issue reports, on an active project of a property
  the account is authorised for (the caller resolves both). An Idempotency-Key is required and stored only as a digest
  with the request digest: the same key and body give back the same report; the same key with another body is
  refused. At most ``MAX_OPEN`` untriaged reports per project and account. Rate limits are per account (routes).
- **Staff** (``record``): a report the customer gave by phone or on site, recorded on their behalf.
"""

from __future__ import annotations

import hashlib

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.kernel.errors import ApiError, field_error, not_found
from veda.kernel.jcs import canonical_bytes

from . import access, events, notices, service
from . import vocab as V
from .models import Project, ProjectCustomerReport, ProjectSnag

MAX_OPEN = 10


def rows(s: Session, p: Project, account_id: str | None = None) -> list[ProjectCustomerReport]:
    q = sa.select(ProjectCustomerReport).where(ProjectCustomerReport.project_id == p.id,
                                               ProjectCustomerReport.is_deleted == sa.false())  # fmt: skip
    if account_id is not None:
        q = q.where(ProjectCustomerReport.account_id == account_id)
    return list(s.execute(q.order_by(ProjectCustomerReport.report_no)).scalars())


def untriaged(s: Session, p: Project) -> list[ProjectCustomerReport]:
    return [r for r in rows(s, p) if r.status == "SUBMITTED"]


def _next_no(s: Session, p: Project) -> int:
    n = s.execute(sa.select(sa.func.max(ProjectCustomerReport.report_no))
                  .where(ProjectCustomerReport.project_id == p.id)).scalar()  # fmt: skip
    return (n or 0) + 1


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def submit(s: Session, account_id: str, p: Project, body, key: str | None) -> tuple[ProjectCustomerReport, bool]:
    """(report, created). The caller has checked the flags, PEX-D01 and the account's access to the property."""
    if not key or not 8 <= len(key) <= 128:
        raise ApiError(400, "IDEMPOTENCY_KEY_REQUIRED", "Send an Idempotency-Key header (8 to 128 characters).")
    access.lock(s, p)
    from veda.modules.crm.leads.models import Lead

    lead = s.get(Lead, p.lead_id)
    if lead is None or lead.anonymized_on is not None:
        raise not_found()
    key_sha = _sha(key)
    request_sha = hashlib.sha256(canonical_bytes({"description": body.description, "area": body.area,
                                                  "project_id": p.id})).hexdigest()  # fmt: skip
    found = s.execute(sa.select(ProjectCustomerReport).where(ProjectCustomerReport.account_id == account_id,
                                                             ProjectCustomerReport.client_key_sha256 == key_sha,
                                                             ProjectCustomerReport.is_deleted == sa.false())
                      ).scalar_one_or_none()  # fmt: skip
    if found is not None:
        if found.request_sha256 != request_sha:
            raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "This request key was already used for a different report.")
        return found, False
    if p.status != "ACTIVE":
        raise ApiError(409, "PROJECT_HANDED_OVER", "Your home has been handed over. Please contact Veda Spaces about "
                       "anything you have noticed since.")  # fmt: skip
    mine = [r for r in rows(s, p, account_id) if r.status == "SUBMITTED"]
    if len(mine) >= MAX_OPEN:
        raise ApiError(409, "REPORT_LIMIT_REACHED", f"You have {len(mine)} reports waiting for review. Veda Spaces will "
                       "look at those first; please speak to your contact if something is urgent.")  # fmt: skip
    r = ProjectCustomerReport(project_id=p.id, lead_id=p.lead_id, report_no=_next_no(s, p), channel="PORTAL",
                              account_id=account_id, description=body.description, area=body.area, status="SUBMITTED",
                              client_key_sha256=key_sha, request_sha256=request_sha)  # fmt: skip
    s.add(r)
    s.flush()
    events.record(s, p, "CUSTOMER_REPORT_SUBMITTED", stage=p.stage_code, to="SUBMITTED", report_id=r.id,
                  report_no=r.report_no, channel="PORTAL", account_id=account_id)  # fmt: skip
    notices.customer(s, p, notices.REPORT_RECEIVED, report_id=r.id)
    notices.staff(s, p, notices.REPORT_SUBMITTED, report_id=r.id)
    access.touch(s, p)
    s.flush()
    return r, True


def record(s: Session, ctx, p: Project, body) -> ProjectCustomerReport:
    access.for_write(s, ctx, p, "project.manage_snag", precondition=False)
    r = ProjectCustomerReport(project_id=p.id, lead_id=p.lead_id, report_no=_next_no(s, p), channel="STAFF",
                              account_id=None, description=body.description, area=body.area, status="SUBMITTED")  # fmt: skip
    s.add(r)
    s.flush()
    events.record(s, p, "CUSTOMER_REPORT_SUBMITTED", stage=p.stage_code, to="SUBMITTED", report_id=r.id,
                  report_no=r.report_no, channel="STAFF")  # fmt: skip
    service.done(p, s)
    return r


def triage(s: Session, ctx, p: Project, r: ProjectCustomerReport, body, if_match: int | None) -> ProjectCustomerReport:
    access.for_write(s, ctx, p, "project.manage_snag", r, if_match=if_match, match=r)
    if r.status != "SUBMITTED":
        raise ApiError(409, "INVALID_STATE", f"Report {r.report_no} is already {r.status.lower()}.",
                       extra={"status": r.status})  # fmt: skip
    if body.outcome == "NEW_SNAG":
        if not body.snag:
            raise ApiError(422, "VALIDATION_FAILED", "Describe the snag to raise.",
                           errors=[field_error("snag", "REQUIRED", "Required for a new snag.")])  # fmt: skip
        sn = service.raise_snag(s, ctx, p, body.snag, source="CUSTOMER")
        r.snag_id, r.status = sn.id, "ACCEPTED"
    elif body.outcome == "EXISTING_SNAG":
        if not body.snag_id:
            raise ApiError(422, "VALIDATION_FAILED", "Say which snag this report is.",
                           errors=[field_error("snag_id", "REQUIRED", "Required.")])  # fmt: skip
        sn = service.child(s, ProjectSnag, p, body.snag_id)
        sn.customer_visible = True  # the customer reported it: they follow it
        r.snag_id, r.status = sn.id, "ACCEPTED"
    else:
        if body.decline_code not in V.REPORT_DECLINE_CODES:
            raise ApiError(422, "VALIDATION_FAILED", "Say why the report is declined.",
                           errors=[field_error("decline_code", "REQUIRED", "Duplicate, not a defect or not in "
                                               "scope.")])  # fmt: skip
        if len((body.response or "").strip()) < 10:
            raise ApiError(422, "VALIDATION_FAILED", "Tell the customer why, in words they will read.",
                           errors=[field_error("response", "REQUIRED", "At least 10 characters.")])  # fmt: skip
        r.status, r.decline_code = "DECLINED", body.decline_code
    if body.response:
        r.response = body.response.strip()
    r.triaged_by, r.triaged_on = ctx.user.id, db.tx_time(s)
    events.record(s, p, "CUSTOMER_REPORT_ACCEPTED" if r.status == "ACCEPTED" else "CUSTOMER_REPORT_DECLINED",
                  stage=p.stage_code, frm="SUBMITTED", to=r.status, report_id=r.id, snag_id=r.snag_id,
                  decline_code=r.decline_code)  # fmt: skip
    service.done(p, s)
    return r


def gate(s: Session, p: Project) -> list[dict]:
    """CUSTOMER_REPORTS_TRIAGED (structural for the handover moves, review D6)."""
    return [{"gate": "CUSTOMER_REPORTS_TRIAGED", "code": "CUSTOMER_REPORT_UNTRIAGED", "message": f"Customer report "
             f"{r.report_no} has not been reviewed.", "responsible_party": "VEDA",
             "entity": {"type": "customer_report", "id": r.id}} for r in untriaged(s, p)]  # fmt: skip
