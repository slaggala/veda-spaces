"""Customer Project Portal endpoints. Every route answers 404, before authentication, unless
VEDA_CUSTOMER_PORTAL_ENABLED is on (off by default; production refuses it).

Customer routes (RBX-010, ``auth="public"``): no staff token is read. Sign-in and the session exchange are anonymous;
every other customer route resolves the portal session from the ``X-Veda-Portal`` header on every request and reaches
data only through the account's ACTIVE access rows (``projection``). Responses are ``no-store``.

Staff routes (bearer, ``portal.access.*``, lead scope): who has portal access to an enquiry; invite; revoke.
"""

from __future__ import annotations

import hashlib

import sqlalchemy as sa
from flask import request

from veda.config import settings
from veda.kernel import clock
from veda.kernel.errors import ApiError, not_found
from veda.kernel.http import PUBLIC_MAX_BODY, Api, Req, ok, problem_response, request_reaches
from veda.modules.crm.leads.models import Lead
from veda.modules.mtq import scope as lead_scope
from veda.platform.identity.models import User

from . import identity, projection
from . import schemas as S
from .models import PortalAccess, PortalAccount

customer_api = Api("portal_customer", "/api/v1/public", tags=("customer-portal",))
staff_api = Api("portal_staff", "/api/v1", tags=("customer-portal",))
CUSTOMER_PREFIXES = ("/api/v1/public/portal",)
STAFF_PREFIXES = ("/api/v1/portal-access",)


@customer_api.blueprint.before_app_request
def _gate():
    if not settings().customer_portal_enabled and request_reaches(
        ("portal_customer", "portal_staff"), CUSTOMER_PREFIXES + STAFF_PREFIXES
    ):
        return problem_response(ApiError(404, "NOT_FOUND", "Not found."))
    return None


# --- rate limits (customer routes) -------------------------------------------------------------------------------------
def _ip(prefix: str):
    def key():
        from veda.kernel.ratelimit import ip_key

        return f"{prefix}:ip:" + ip_key()

    return key


def _email(prefix: str):
    def key():
        from veda.kernel.ratelimit import body_email_key

        return f"{prefix}:" + body_email_key()

    return key


def _session(prefix: str):
    """Per session: the token's digest (never the token) or, without a well-formed token, the address."""

    def key():
        from veda.kernel.ratelimit import ip_key

        token = request.headers.get(identity.HEADER, "")
        if identity.SESSION_RE.match(token):
            return f"{prefix}:session:" + hashlib.sha256(token.encode()).hexdigest()[:32]
        return f"{prefix}:nosession:" + ip_key()

    return key


def _refused(response) -> bool:
    return response.status_code in (400, 401, 404)


SIGN_IN_LIMITS = [("5 per minute", _ip("portal-sign-in")), ("30 per hour", _ip("portal-sign-in")),
                  ("3 per 10 minutes", _email("portal-sign-in")), ("10 per day", _email("portal-sign-in"))]  # fmt: skip
SESSION_LIMITS = [("10 per minute", _ip("portal-session")), ("60 per hour", _ip("portal-session"))]
READ_LIMITS = [("120 per minute", _ip("portal-read")), ("60 per minute", _session("portal-read")),
               ("20 per minute", _ip("portal-refused"), {"deduct_when": _refused})]  # fmt: skip


def private(result):
    result.headers["Cache-Control"] = "no-store, max-age=0"
    result.headers["Pragma"] = "no-cache"
    result.headers["X-Robots-Tag"] = "noindex, nofollow"
    return result


def principal(req: Req) -> identity.Principal:
    return identity.resolve(req.session, req.headers.get(identity.HEADER) if req.headers is not None else None)


# --- customer: sign-in -------------------------------------------------------------------------------------------------
@customer_api.route("POST", "/portal/sign-in", rbx="RBX-010", auth="public", body=S.SignInIn, status=202,
                    max_body=PUBLIC_MAX_BODY, limits=SIGN_IN_LIMITS, requirement="CPP-001",
                    summary="Email a sign-in link to a customer with portal access (the answer never says whether)")  # fmt: skip
def sign_in(req: Req):
    identity.request_sign_in(req.session, req.body.email)
    return private(ok({"sent": True, "message": "If this email has access to a Veda Spaces project portal, a sign-in "
                       "link is on its way. It works once and expires in 15 minutes."}, status=202))  # fmt: skip


@customer_api.route("POST", "/portal/session", rbx="RBX-010", auth="public", body=S.SessionIn, status=201,
                    max_body=PUBLIC_MAX_BODY, limits=SESSION_LIMITS, requirement="CPP-001",
                    summary="Exchange a sign-in link for a portal session (the token is returned once)")  # fmt: skip
def start_session(req: Req):
    session, raw = identity.start_session(req.session, req.body.token)
    return private(ok({"token": raw, "header": identity.HEADER,
                       "idle_expires_on": clock.to_rfc3339(session.idle_expires_on),
                       "expires_on": clock.to_rfc3339(session.absolute_expires_on)}, status=201))  # fmt: skip


@customer_api.route("POST", "/portal/sign-out", rbx="RBX-010", auth="public", max_body=PUBLIC_MAX_BODY,
                    limits=READ_LIMITS, requirement="CPP-001", summary="End this portal session")  # fmt: skip
def sign_out(req: Req):
    identity.sign_out(req.session, principal(req))
    return private(ok({"signed_out": True}))


# --- customer: the portal ----------------------------------------------------------------------------------------------
@customer_api.route("GET", "/portal/home", rbx="RBX-010", auth="public", write=False, limits=READ_LIMITS,
                    requirement="CPP-004", summary="The customer's portal home: their enquiries and properties")  # fmt: skip
def home(req: Req):
    p = principal(req)
    return private(ok(projection.home(req.session, p.account)))


@customer_api.route("GET", "/portal/properties/<property_id>", rbx="RBX-010", auth="public", write=False,
                    limits=READ_LIMITS, requirement="CPP-005",
                    summary="One property's project: status, journey, attention, quotation, commitments, documents")  # fmt: skip
def property_detail(req: Req, property_id: str):
    p = principal(req)
    prop, lead = projection.property_for(req.session, p.account.id, property_id)
    return private(ok(projection.property_view(req.session, p.account.id, prop, lead, full=True)))


@customer_api.route("GET", "/portal/quotations/<quotation_id>", rbx="RBX-010", auth="public", write=False,
                    limits=READ_LIMITS, requirement="CPP-007",
                    summary="One issued quotation version, customer-safe and read-only (the CQX projection)")  # fmt: skip
def quotation(req: Req, quotation_id: str):
    p = principal(req)
    q = projection.quotation_for(req.session, p.account.id, quotation_id)
    return private(ok(projection.quotation_page(req.session, q)))


# --- staff: access -----------------------------------------------------------------------------------------------------
def _present(s, a: PortalAccess, *, erased: bool = False) -> dict:
    acc = s.get(PortalAccount, a.account_id)

    def name(uid):
        u = s.get(User, uid) if uid else None
        return {"id": uid, "display_name": (u.display_name or u.full_name) if u else None} if uid else None

    return {"id": a.id, "version": a.version, "relationship": a.relationship, "status": a.status,
            # an erased enquiry never shows who had access to it (the account may still exist for another enquiry)
            "account": {"display_name": "[erased]", "email": None, "status": None, "last_signed_in_on": None} if erased
            else {"display_name": acc.display_name, "email": acc.email_normalized, "status": acc.status,
                  "last_signed_in_on": clock.to_rfc3339(acc.last_signed_in_on) if acc.last_signed_in_on else None},
            "granted_on": clock.to_rfc3339(a.created_on), "granted_by": name(a.created_by),
            "revoked_on": clock.to_rfc3339(a.revoked_on) if a.revoked_on else None, "revoked_by": name(a.revoked_by),
            "revoke_reason_code": a.revoke_reason_code}  # fmt: skip


def _listing(s, lead_id: str) -> list[dict]:
    lead = s.get(Lead, lead_id, execution_options={"include_deleted": True})
    erased = lead is None or lead.anonymized_on is not None
    rows = s.execute(sa.select(PortalAccess).where(PortalAccess.lead_id == lead_id)
                     .order_by(PortalAccess.status, PortalAccess.created_on.desc())).scalars()  # fmt: skip
    return [_present(s, a, erased=erased) for a in rows]


@staff_api.route("GET", "/leads/<lead_id>/portal-access", permission="portal.access.view", write=False,
                 requirement="CPP-002", summary="Who has customer portal access to this enquiry")  # fmt: skip
def list_access(req: Req, lead_id: str):
    lead_scope.require_lead(req.session, req.ctx, lead_id, "portal.access.view", write=False)
    return ok(_listing(req.session, lead_id))


@staff_api.route("POST", "/leads/<lead_id>/portal-access", permission="portal.access.grant", body=S.GrantIn,
                 status=201, idempotent_create=True, requirement="CPP-002",
                 summary="Give a customer portal access to this enquiry and email them a sign-in link")  # fmt: skip
def grant(req: Req, lead_id: str):
    lead = lead_scope.require_lead(req.session, req.ctx, lead_id, "portal.access.grant")
    identity.grant(req.session, req.ctx, lead, req.body)
    req.session.flush()
    return ok(_listing(req.session, lead_id), status=201)


@staff_api.route("POST", "/portal-access/<access_id>/revoke", permission="portal.access.revoke", if_match=True,
                 requirement="CPP-002", summary="End a customer's portal access to this enquiry at once")  # fmt: skip
def revoke(req: Req, access_id: str):
    from veda.kernel.http import check_version

    a = req.session.get(PortalAccess, access_id)
    if a is None or a.is_deleted:
        raise not_found()
    # Within the lead's scope, even while the lead is soft-deleted (its access would otherwise return on restore).
    scope = req.ctx.scope("portal.access.revoke")
    owned = req.session.execute(lead_scope.owned_lead_ids(req.ctx.user.id).where(Lead.id == a.lead_id),
                                execution_options={"include_deleted": True}).first()  # fmt: skip
    if scope is None or (scope == "OWN" and owned is None):
        raise not_found()
    check_version(req.if_match, a.version)
    identity.revoke(req.session, req.ctx, a)
    req.session.flush()
    return ok(_listing(req.session, a.lead_id))
