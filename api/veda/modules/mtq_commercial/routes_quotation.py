"""MTQ B4 endpoints: quotations, versions, lifecycle, the customer document, variations. Staff only, scoped by lead.

Every route answers 404, before authentication, unless VEDA_MTQ_QUOTATION_ENABLED is on (off by default; production
refuses it; it needs the estimation flag). There is no public (customer portal) route: the portal is out of scope.
"""

from __future__ import annotations

import sqlalchemy as sa

from veda.config import settings
from veda.kernel.errors import ApiError, not_found
from veda.kernel.http import Api, Req, ok, problem_response, request_reaches

from . import access, journey, quotations
from . import schemas as S
from .models import CostEstimate, Quotation, QuotationLine

api = Api("mtq_quotation", "/api/v1", tags=("mtq-commercial",))
GATED_PREFIXES = ("/api/v1/quotations", "/api/v1/quotation-lines")


@api.blueprint.before_app_request
def _quotation_enabled():
    if not settings().mtq_quotation_enabled and request_reaches(("mtq_quotation",), GATED_PREFIXES):
        return problem_response(ApiError(404, "NOT_FOUND", "Not found."))
    return None


def _estimate(req: Req, estimate_id: str, permission: str = "quotation.read") -> CostEstimate:
    return access.row_visible(req.session, req.ctx, CostEstimate, estimate_id, permission)


def _quotation(req: Req, quotation_id: str) -> Quotation:
    return access.row_visible(req.session, req.ctx, Quotation, quotation_id, "quotation.read")


def _for_write(req: Req, q: Quotation, permission: str) -> None:
    access.for_write(req.session, req.ctx, q.lead_id, q.property_id, permission, q)
    req.require_version(q.version)


def _out(req: Req, q: Quotation, status: int = 200):
    req.session.flush()
    return ok(quotations.present(req.session, q, req.ctx), status=status)


@api.route("POST", "/cost-estimates/<estimate_id>/quotations", permission="quotation.create",
           body=S.QuotationCreateIn, status=201, idempotent_create=True, requirement="QUOT-002",
           summary="Create quotation version 1 from an approved, current estimate (number from the QUOTATION sequence)")  # fmt: skip
def create_quotation(req: Req, estimate_id: str):
    est = _estimate(req, estimate_id)
    prop = access.property_visible(req.session, req.ctx, est.property_id, "quotation.read")
    access.for_write(req.session, req.ctx, est.lead_id, est.property_id, "quotation.create", est)
    q = quotations.create(req.session, req.ctx, est, prop, req.body or S.QuotationCreateIn())
    return _out(req, q, 201)


@api.route("GET", "/properties/<property_id>/quotations", permission="quotation.read", write=False,
           requirement="QUOT-001", summary="Every quotation version and variation of a property")  # fmt: skip
def list_quotations(req: Req, property_id: str):
    prop = access.property_visible(req.session, req.ctx, property_id, "quotation.read")
    rows = req.session.execute(
        sa.select(Quotation).where(Quotation.property_id == prop.id)
        .order_by(Quotation.quotation_number, Quotation.variation_no, Quotation.version_no.desc())
    ).scalars()  # fmt: skip
    return ok([quotations.present(req.session, q, req.ctx, full=False) for q in rows])


@api.route("GET", "/quotations/<quotation_id>", permission="quotation.read", write=False, requirement="QUOT-001",
           summary="One quotation version: sections, lines, lineage, blockers, lifecycle events")  # fmt: skip
def get_quotation(req: Req, quotation_id: str):
    return ok(quotations.present(req.session, _quotation(req, quotation_id), req.ctx))


@api.route("GET", "/quotation-lines/<line_id>/trace", permission="quotation.read", write=False,
           requirement="QUOT-001",
           summary="A quotation line walked back: estimate line, BOQ line, scope item, requirement, measurement")  # fmt: skip
def trace_line(req: Req, line_id: str):
    line = req.session.get(QuotationLine, line_id)
    if line is None or line.is_deleted:
        raise not_found()
    _quotation(req, line.quotation_id)
    return ok(quotations.trace(req.session, line))


@api.route("PATCH", "/quotations/<quotation_id>", permission="quotation.create", body=S.QuotationPatchIn,
           if_match=True, requirement="QUOT-002", summary="Edit a draft's title and customer cover note")  # fmt: skip
def patch_quotation(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id)
    _for_write(req, q, "quotation.create")
    quotations.edit(req.session, req.ctx, q, req.body)
    return _out(req, q)


@api.route("POST", "/quotations/<quotation_id>/versions", permission="quotation.create", body=S.QuotationVersionIn,
           status=201, if_match=True, idempotent_create=True, requirement="QUOT-002",
           summary="Create the next version from an approved estimate (never edits an issued version)")  # fmt: skip
def new_version(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id)
    _for_write(req, q, "quotation.create")
    est = _estimate(req, req.body.cost_estimate_id)
    prop = access.property_visible(req.session, req.ctx, q.property_id, "quotation.read")
    nq = quotations.new_version(req.session, req.ctx, q, est, prop, req.body)
    return _out(req, nq, 201)


@api.route("POST", "/quotations/<quotation_id>/submit", permission="quotation.create", if_match=True,
           idempotent_create=True, requirement="QUOT-002", summary="Submit a draft for internal review")  # fmt: skip
def submit(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id)
    _for_write(req, q, "quotation.create")
    quotations.submit(req.session, req.ctx, q)
    return _out(req, q)


@api.route("POST", "/quotations/<quotation_id>/return", any_of=("quotation.create", "quotation.approve"),
           body=S.ReturnIn, if_match=True, requirement="QUOT-002",
           summary="Return a version in review (or approved, not issued) to draft, with a reason")  # fmt: skip
def return_to_draft(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id)
    perm = "quotation.approve" if req.ctx.scope("quotation.approve") else "quotation.create"
    _for_write(req, q, perm)
    quotations.return_to_draft(req.session, req.ctx, q, req.body.reason)
    return _out(req, q)


@api.route("POST", "/quotations/<quotation_id>/approve", permission="quotation.approve", if_match=True,
           idempotent_create=True, requirement="QUOT-003",
           summary="Approve a version in review (four-eyes when discounted); issuance blockers stay visible")  # fmt: skip
def approve(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id)
    _for_write(req, q, "quotation.approve")
    quotations.approve(req.session, req.ctx, q)
    return _out(req, q)


@api.route("POST", "/quotations/<quotation_id>/issue", permission="quotation.issue", if_match=True,
           idempotent_create=True, requirement="QUOT-004",
           summary="Issue an approved, customer-issuable version: freezes the document, sets validity, syncs the lead")  # fmt: skip
def issue(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id)
    _for_write(req, q, "quotation.issue")
    quotations.issue(req.session, req.ctx, q)
    return _out(req, q)


@api.route("POST", "/quotations/<quotation_id>/decision", permission="quotation.decision.record", body=S.DecisionIn,
           if_match=True, idempotent_create=True, requirement="QUOT-005",
           summary="Record the customer's acceptance (with chosen optional items) or rejection")  # fmt: skip
def decide(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id)
    _for_write(req, q, "quotation.decision.record")
    quotations.decide(req.session, req.ctx, q, req.body)
    return _out(req, q)


def _journey_quotations(s, ctx, prop):
    if ctx.scope("quotation.read") is None or not settings().mtq_quotation_enabled:
        return "quotations", None
    rows = s.execute(
        sa.select(Quotation).where(Quotation.property_id == prop.id)
        .order_by(Quotation.quotation_number, Quotation.variation_no, Quotation.version_no.desc())
    ).scalars()  # fmt: skip
    return "quotations", [quotations.present(s, q, ctx, full=False) for q in rows]


journey.SECTIONS.append(_journey_quotations)
