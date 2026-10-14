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
from veda.kernel.http import Api, Req, ok, problem_response, request_reaches
from veda.modules.mtq_commercial import access
from veda.modules.mtq_commercial.models import Quotation

from . import grants, journey, projection, references
from . import schemas as S
from .models import ProposalAccessGrant

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
    if q.snapshot is not None or q.issued_html is not None:
        return ok({"frozen": True, "status": q.status, "proposal": projection.build(req.session, q)})
    doc = rendering.document_model(req.session, q)
    doc.pop("draft", None)
    return ok({"frozen": False, "status": q.status, "watermark": "Preview: not issued, not a customer document",
               "proposal": projection.build(req.session, q, doc)})  # fmt: skip


# --- customer: the proposal -------------------------------------------------------------------------------------------
@public_api.route("GET", "/proposal", rbx="RBX-009", auth="public", write=True, requirement="CQX-001",
                  limits=READ_LIMITS, summary="The customer's proposal, opened by its secure link (customer-safe)")  # fmt: skip
def view(req: Req):
    g, q = customer(req)
    page = journey.customer_view(req.session, g, q)  # built first: a refused document records no view
    grants.record_view(req.session, g)
    page["link"]["status"] = g.status
    return private(ok(page))


journey.register(references.contribute)

ALL_APIS = (staff_api, public_api, interaction_api, acceptance_api)
