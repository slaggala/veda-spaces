"""CQX endpoints. Four blueprints, each behind its own flag (every route answers 404 before authentication while off):

- ``cqx_staff`` (VEDA_CUSTOMER_PROPOSAL_ENABLED): staff share, rotate, revoke and preview; review customer requests.
- ``cqx_public`` (VEDA_CUSTOMER_PROPOSAL_ENABLED): the customer's proposal, opened by its link (RBX-009).
- ``cqx_interaction`` (…_INTERACTION_ENABLED): optional-item choices, questions, change requests, acknowledgements.
- ``cqx_acceptance`` (VEDA_CUSTOMER_QUOTATION_ACCEPTANCE_ENABLED): the customer's digital acceptance or decline.

Customer routes are ``auth="public"`` RBX-009 exceptions: no staff session, no cookie. The link's token travels only in
the ``X-Veda-Proposal`` header and is resolved to one grant and one quotation version on every request (server-side
authorisation every time; nothing is cached). Without cookies there is no ambient credential for a cross-site request
to ride on (no CSRF surface); the custom header also forces a CORS preflight, which only the app origin passes.
Responses are ``no-store`` and ``noindex``; errors are the safe messages of ``grants`` (no identifier, no stack trace).
"""

from __future__ import annotations

import hashlib

from flask import request

from veda.config import settings
from veda.kernel.errors import ApiError
from veda.kernel.http import PUBLIC_MAX_BODY, Api, Req, ok, problem_response, request_reaches
from veda.modules.mtq_commercial import access
from veda.modules.mtq_commercial.models import Quotation

from . import (
    acceptance,
    acknowledgements,
    comparison,
    grants,
    journey,
    pricing,
    projection,
    references,
    requests,
    selections,
    trust,
)
from . import schemas as S
from .models import CustomerProposalRequest, ProposalAccessGrant

staff_api = Api("cqx_staff", "/api/v1", tags=("customer-proposal",))
public_api = Api("cqx_public", "/api/v1/public", tags=("customer-proposal",))
interaction_api = Api("cqx_interaction", "/api/v1/public", tags=("customer-proposal",))
acceptance_api = Api("cqx_acceptance", "/api/v1/public", tags=("customer-proposal",))

STAFF_PREFIXES = ("/api/v1/proposal-access-grants", "/api/v1/customer-requests")
PUBLIC_PREFIXES = ("/api/v1/public/proposal",)


def _off() -> object:
    return problem_response(ApiError(404, "NOT_FOUND", "Not found."))


@staff_api.blueprint.before_app_request
def _gate():
    """Every CQX blueprint answers 404 while its flag (or one it needs) is off: every method and routed spelling."""
    cfg = settings()
    if not cfg.customer_proposal_enabled and request_reaches(("cqx_staff", "cqx_public", "cqx_interaction",
                                                               "cqx_acceptance"), STAFF_PREFIXES + PUBLIC_PREFIXES):  # fmt: skip
        return _off()
    if not cfg.customer_proposal_interaction_enabled and request_reaches(("cqx_interaction", "cqx_acceptance"), ()):
        return _off()
    if not cfg.customer_quotation_acceptance_enabled and request_reaches(("cqx_acceptance",), ()):
        return _off()
    return None


# --- rate limits (customer routes) -------------------------------------------------------------------------------------
def _ip(prefix: str):
    def key():
        from veda.kernel.ratelimit import ip_key

        return f"{prefix}:ip:" + ip_key()

    return key


def _link(prefix: str):
    """Per link: the token's digest (never the token) or, without a well-formed token, the address."""

    def key():
        from veda.kernel.ratelimit import ip_key

        token = request.headers.get(grants.HEADER, "")
        if grants.TOKEN_RE.match(token):
            return f"{prefix}:link:" + hashlib.sha256(token.encode()).hexdigest()[:32]
        return f"{prefix}:nolink:" + ip_key()

    return key


def _refused(response) -> bool:
    return response.status_code in (404, 410)


# A failed link (unknown, malformed, revoked, expired) costs its own small budget per address: guessing a 256-bit token
# is hopeless anyway; this keeps a scanner from loading the database (CQX-13 brute force, denial of service).
READ_LIMITS = [("120 per minute", _ip("cqx-read")), ("2000 per hour", _ip("cqx-read")),
               ("60 per minute", _link("cqx-read")),
               ("20 per minute", _ip("cqx-refused"), {"deduct_when": _refused})]  # fmt: skip
WRITE_LIMITS = [("20 per minute", _ip("cqx-write")), ("200 per hour", _ip("cqx-write")),
                ("10 per minute", _link("cqx-write")), ("300 per day", _link("cqx-write")),
                ("20 per minute", _ip("cqx-refused"), {"deduct_when": _refused})]  # fmt: skip


def customer(req: Req) -> tuple[ProposalAccessGrant, Quotation]:
    return grants.resolve(req.session, req.headers.get(grants.HEADER) if req.headers is not None else None)


def private(result):
    result.headers["Cache-Control"] = "no-store, max-age=0"
    result.headers["Pragma"] = "no-cache"
    result.headers["X-Robots-Tag"] = "noindex, nofollow"
    return result


# --- staff: sharing ---------------------------------------------------------------------------------------------------
def _quotation(req: Req, quotation_id: str, permission: str) -> Quotation:
    return access.row_visible(req.session, req.ctx, Quotation, quotation_id, permission)


def _grant(req: Req, grant_id: str, permission: str) -> ProposalAccessGrant:
    return access.row_visible(req.session, req.ctx, ProposalAccessGrant, grant_id, permission)


def _issued(issued: grants.Issued) -> dict:
    # The token and link are returned once, here, and never again (only the digest is stored).
    return {**grants.present(issued.grant), "token": issued.token, "link": grants.link_for(issued.token)}


@staff_api.route("POST", "/quotations/<quotation_id>/access-grants", permission="proposal.share", body=S.ShareIn,
                 status=201, idempotent_create=True, requirement="CQX-002",
                 summary="Share an issued quotation version: a secure link for one recipient (token shown once)")  # fmt: skip
def share(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id, "proposal.share")
    access.for_write(req.session, req.ctx, q.lead_id, q.property_id, "proposal.share", q)
    issued = grants.share(req.session, req.ctx, q, req.body)
    req.session.flush()
    return ok(_issued(issued), status=201)


@staff_api.route("GET", "/quotations/<quotation_id>/access-grants", permission="proposal.share", write=False,
                 requirement="CQX-002", summary="Every link shared for a quotation version, with its state and views")  # fmt: skip
def list_grants(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id, "proposal.share")
    return ok([grants.present(g) for g in grants.for_quotation(req.session, q.id)])


@staff_api.route("POST", "/proposal-access-grants/<grant_id>/rotate", permission="proposal.share", status=201,
                 if_match=True, idempotent_create=True, requirement="CQX-002",
                 summary="Replace a live link with a new one (the old link stops at once)")  # fmt: skip
def rotate(req: Req, grant_id: str):
    g = _grant(req, grant_id, "proposal.share")
    access.for_write(req.session, req.ctx, g.lead_id, g.property_id, "proposal.share", g)
    req.require_version(g.version)
    issued = grants.rotate(req.session, req.ctx, g)
    req.session.flush()
    return ok(_issued(issued), status=201)


@staff_api.route("POST", "/proposal-access-grants/<grant_id>/revoke", permission="proposal.access.revoke",
                 if_match=True, requirement="CQX-003", summary="Revoke a link; it stops serving on the next request")  # fmt: skip
def revoke(req: Req, grant_id: str):
    g = _grant(req, grant_id, "proposal.access.revoke")
    access.for_write(req.session, req.ctx, g.lead_id, g.property_id, "proposal.access.revoke", g)
    req.require_version(g.version)
    grants.revoke(req.session, req.ctx, g)
    req.session.flush()
    return ok(grants.present(g))


# --- staff: preview ---------------------------------------------------------------------------------------------------
@staff_api.route("GET", "/quotations/<quotation_id>/proposal-preview", permission="proposal.preview", write=False,
                 requirement="CQX-001",
                 summary="The quotation exactly as its customer sees it (frozen once issued; a marked preview before)")  # fmt: skip
def preview(req: Req, quotation_id: str):
    from veda.modules.mtq_commercial import rendering

    q = _quotation(req, quotation_id, "proposal.preview")
    # CTB-18: whether a customer could answer every basic question from this proposal (staff guidance; never a block)
    spec = references.specifications(req.session, q)
    if q.snapshot is not None or q.issued_html is not None:
        proposal = projection.build(req.session, q)
        return ok({"frozen": True, "status": q.status, "proposal": proposal,
                   "trust_checklist": trust.checklist(proposal, spec)})  # fmt: skip
    doc = rendering.document_model(req.session, q)
    doc.pop("draft", None)
    proposal = projection.build(req.session, q, doc)
    return ok({"frozen": False, "status": q.status, "watermark": "Preview: not issued, not a customer document",
               "proposal": proposal, "trust_checklist": trust.checklist(proposal, spec)})  # fmt: skip


# --- customer: the proposal -------------------------------------------------------------------------------------------
@public_api.route("GET", "/proposal", rbx="RBX-009", auth="public", write=True, requirement="CQX-001",
                  limits=READ_LIMITS, summary="The customer's proposal, opened by its secure link (customer-safe)")  # fmt: skip
def view(req: Req):
    g, q = customer(req)
    page = journey.customer_view(req.session, g, q)  # built first: a refused document records no view
    grants.record_view(req.session, g)
    page["link"]["status"] = g.status
    return private(ok(page))


@public_api.route("GET", "/proposal/comparison", rbx="RBX-009", auth="public", write=False, requirement="CQX-008",
                  limits=READ_LIMITS, summary="This version beside the version issued before it (frozen documents only)")  # fmt: skip
def compare_versions(req: Req):
    _g, q = customer(req)
    return private(ok({"comparison": comparison.version_comparison(req.session, q)}))


@staff_api.route("GET", "/quotations/<quotation_id>/variation-preview", permission="proposal.preview", write=False,
                 requirement="CQX-008",
                 summary="A variation beside the accepted baseline, as the customer would see it (staff preview)")  # fmt: skip
def variation_preview(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id, "proposal.preview")
    return ok(comparison.variation_preview(req.session, q))


# --- customer: interaction --------------------------------------------------------------------------------------------
@interaction_api.route("POST", "/proposal/selections", rbx="RBX-009", auth="public", body=S.SelectionIn,
                       max_body=PUBLIC_MAX_BODY, requirement="CQX-006", limits=WRITE_LIMITS,
                       summary="Choose, drop or ask about an optional item (a proposal to staff; the quotation never changes)")  # fmt: skip
def choose_optional(req: Req):
    g, q = customer(req)
    selections.choose(req.session, g, q, req.body.line_ref, req.body.state)
    return private(ok(selections.summary(req.session, q)))


@interaction_api.route("POST", "/proposal/requests", rbx="RBX-009", auth="public", body=S.RequestIn, status=201,
                       max_body=PUBLIC_MAX_BODY, requirement="CQX-007", limits=WRITE_LIMITS,
                       summary="Ask a question or request a change (sent to staff; it never changes the quotation)")  # fmt: skip
def submit_request(req: Req):
    g, q = customer(req)
    requests.submit(req.session, g, q, req.body, req.headers.get("Idempotency-Key"))
    return private(ok(requests.for_customer(req.session, g), status=201))


@interaction_api.route("POST", "/proposal/acknowledgements", rbx="RBX-009", auth="public", body=S.AcknowledgeIn,
                       status=201, max_body=PUBLIC_MAX_BODY, requirement="CQX-009", limits=WRITE_LIMITS,
                       summary="Acknowledge one section of this version, bound to the digest of the text shown")  # fmt: skip
def acknowledge(req: Req):
    g, q = customer(req)
    acknowledgements.acknowledge(req.session, g, q, req.body.section, req.body.section_sha256)
    return private(
        ok({"terms": acknowledgements.view(req.session, g, q, projection.build(req.session, q))}, status=201)
    )


@interaction_api.route("GET", "/proposal/requests", rbx="RBX-009", auth="public", write=False, requirement="CQX-007",
                       limits=READ_LIMITS, summary="The customer's own questions and change requests, with answers")  # fmt: skip
def list_requests(req: Req):
    g, _q = customer(req)
    return private(ok(requests.for_customer(req.session, g)))


# --- customer: decision -----------------------------------------------------------------------------------------------
@acceptance_api.route("POST", "/proposal/decision", rbx="RBX-009", auth="public", body=S.DecisionIn,
                      max_body=PUBLIC_MAX_BODY, requirement="CQX-010", limits=WRITE_LIMITS,
                      summary="Accept or decline exactly this version, as shown (bound to its version and digest)")  # fmt: skip
def decide(req: Req):
    g, q = customer(req)
    acceptance.decide(req.session, g, q, req.body, req.headers.get("Idempotency-Key"), ip=req.ip,
                      user_agent=req.user_agent, request_trace=req.request_id)  # fmt: skip
    page = journey.customer_view(req.session, g, q)
    return private(ok({"state": page["state"], "decision": page["decision"]}))


# --- staff: what the customer did -------------------------------------------------------------------------------------
@staff_api.route("GET", "/quotations/<quotation_id>/customer-activity", permission="proposal.request.review",
                 write=False, requirement="CQX-004",
                 summary="The customer's optional-item choices, questions, change requests and acknowledgements")  # fmt: skip
def customer_activity(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id, "proposal.request.review")
    return ok({"selections": selections.staff_view(req.session, q), "summary": selections.summary(req.session, q),
               "requests": requests.staff_view(req.session, q),
               "acknowledgements": acknowledgements.staff_view(req.session, q)})  # fmt: skip


@staff_api.route("GET", "/quotations/<quotation_id>/acceptance-evidence", permission="proposal.acceptance.review",
                 write=False, requirement="CQX-005",
                 summary="The evidence of the customer's digital decision (verified), or what still blocks one")  # fmt: skip
def acceptance_evidence(req: Req, quotation_id: str):
    q = _quotation(req, quotation_id, "proposal.acceptance.review")
    kinds = {g.id: g.recipient_kind for g in grants.for_quotation(req.session, q.id)}
    return ok(acceptance.staff_view(req.session, kinds, q))


def _request(req: Req, request_id: str) -> CustomerProposalRequest:
    r = access.row_visible(req.session, req.ctx, CustomerProposalRequest, request_id, "proposal.request.review")
    access.for_write(req.session, req.ctx, r.lead_id, r.property_id, "proposal.request.review", r)
    req.require_version(r.version)
    return r


def _request_out(req: Req, r: CustomerProposalRequest) -> dict:
    req.session.flush()
    q = req.session.get(Quotation, r.quotation_id)
    assert q is not None  # FK
    return next(x for x in requests.staff_view(req.session, q) if x["id"] == r.id)


@staff_api.route("POST", "/customer-requests/<request_id>/respond", permission="proposal.request.review",
                 body=S.RespondIn, if_match=True, requirement="CQX-004",
                 summary="Answer a customer question or change request (the answer is shown to the customer)")  # fmt: skip
def respond_request(req: Req, request_id: str):
    r = _request(req, request_id)
    requests.respond(req.session, req.ctx, r, req.body.status, req.body.response)
    return ok(_request_out(req, r))


@staff_api.route("POST", "/customer-requests/<request_id>/link", permission="proposal.request.review",
                 body=S.LinkRequestIn, if_match=True, requirement="CQX-004",
                 summary="Link the revised version or variation that answers a change request")  # fmt: skip
def link_request(req: Req, request_id: str):
    r = _request(req, request_id)
    target = _quotation(req, req.body.resulting_quotation_id, "quotation.read")
    requests.link(req.session, req.ctx, r, target, req.body.response)
    return ok(_request_out(req, r))


journey.register(references.contribute)
journey.register(pricing.contribute)
journey.register(selections.contribute)
journey.register(requests.contribute)
journey.register(comparison.contribute)
journey.register(acknowledgements.contribute)
journey.register(acceptance.contribute)
journey.PAGE_FIELDS.update(acceptance.PAGE_FIELDS)
journey.PAGE_FIELDS.update(acknowledgements.PAGE_FIELDS)
journey.PAGE_FIELDS.update(comparison.PAGE_FIELDS)
journey.PAGE_FIELDS.update(requests.PAGE_FIELDS)
journey.PAGE_FIELDS.update(pricing.PAGE_FIELDS)
journey.PAGE_FIELDS.update(selections.PAGE_FIELDS)

ALL_APIS = (staff_api, public_api, interaction_api, acceptance_api)
