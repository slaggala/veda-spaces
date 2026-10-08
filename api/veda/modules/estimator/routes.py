"""Estimator routes (ADR-011/012).

Public (RBX-007): exactly `POST /api/v1/public/estimates` and `POST /api/v1/public/enquiries`. Both answer 404 while the
estimator is disabled (the default), require Turnstile, and are rate-limited per source network, per browser token,
and in aggregate. Responses carry only customer-safe fields: a customer reference, never an internal identifier,
duplicate status, assignment, workflow state or volume.

Staff: estimate views and actions, always within the scope of the linked lead.
"""

from __future__ import annotations

import re

from flask import request
from pydantic import ValidationError

from veda.config import settings
from veda.kernel import turnstile
from veda.kernel.errors import ApiError, field_error
from veda.kernel.http import PUBLIC_MAX_BODY, Api, Req, ok
from veda.platform.auth import security_events

from . import engine, service
from . import schemas as S

public_api = Api("estimator_public", "/api/v1/public", tags=("estimator",))
api = Api("estimator", "/api/v1", tags=("estimator",))

_CLIENT_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


# --- layered rate-limit keys ------------------------------------------------------------------------------------------


def _ip(prefix: str):
    def key():
        from veda.kernel.ratelimit import ip_key

        return f"{prefix}:ip:" + ip_key()

    return key


def _network(prefix: str):
    def key():
        from veda.kernel.ratelimit import wide_network_key

        return f"{prefix}:" + wide_network_key()

    return key


def _client(prefix: str):
    """The browser token the wizard sends (X-Veda-Client, random per browser session); the IP when absent."""

    def key():
        from veda.kernel.ratelimit import ip_key

        token = request.headers.get("X-Veda-Client", "")
        return f"{prefix}:client:" + (token if _CLIENT_RE.match(token) else "ip:" + ip_key())

    return key


def _all(prefix: str):
    def key():
        return f"{prefix}:all"

    return key


def _limits(prefix: str, per_ip: tuple[str, str], per_network: str, per_client: str, aggregate: str) -> list:
    return [
        (per_ip[0], _ip(prefix)),
        (per_ip[1], _ip(prefix)),
        (per_network, _network(prefix)),
        (per_client, _client(prefix)),
        (aggregate, _all(prefix)),
    ]


def _enabled() -> None:
    if not settings().estimator_enabled:
        raise ApiError(404, "NOT_FOUND", "Not found.")


def _captcha(token, ip) -> None:
    if not turnstile.verify(token if isinstance(token, str) else None, ip):
        security_events.defer(
            "PUBLIC_INTAKE_BLOCKED", "BLOCKED", failure_reason="CAPTCHA_FAILED", detail={"reason": "captcha"}
        )
        raise ApiError(422, "CAPTCHA_FAILED", "We couldn't verify this request.")


# --- public: estimate --------------------------------------------------------------------------------------------------


def _estimate_prepare(req: Req):
    _enabled()
    if settings().estimate_turnstile_required:
        req.session.rollback()  # no transaction stays open across the siteverify call
        _captcha(req.body.turnstile_token, req.ip)
    return {"captcha": True}


@public_api.route(
    "POST",
    "/estimates",
    rbx="RBX-007",
    auth="public",
    body=S.PublicEstimateIn,
    status=201,
    max_body=PUBLIC_MAX_BODY,
    requirement="EST-001",
    prepare=_estimate_prepare,
    limits=_limits("estimate", ("10 per minute", "60 per hour"), "120 per hour", "6 per minute", "600 per hour"),
    summary="Preliminary Budgetary Estimate (anonymous; no personal data; Turnstile-gated; not a quotation)",
)
def create_estimate(req: Req):
    raw = {k: v for k, v in (req.raw or {}).items() if k != "turnstile_token"}
    try:
        estimate_request = engine.EstimateRequest.model_validate(raw)
    except ValidationError as err:
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "Some estimate inputs need attention.",
            errors=[
                field_error(".".join(str(p) for p in e["loc"]) or "body", "INVALID", e["msg"][:200])
                for e in err.errors()[:20]
            ],
        ) from err
    data = service.create_public(req.session, estimate_request, ip=req.ip, ua=req.user_agent, request_id=req.request_id)
    result = ok(data, status=201)
    result.headers["Cache-Control"] = "no-store"
    return result


# --- public: enquiry linked to an estimate -------------------------------------------------------------------------------


def _enquiry_prepare(req: Req):
    _enabled()
    from veda.modules.crm.leads.routes import _public_lead_prepare

    return _public_lead_prepare(req)  # idempotency replay first, then Turnstile (as the website enquiry)


@public_api.route(
    "POST",
    "/enquiries",
    rbx="RBX-007",
    auth="public",
    body=S.PublicEnquiryIn,
    status=201,
    max_body=PUBLIC_MAX_BODY,
    requirement="EST-004",
    prepare=_enquiry_prepare,
    limits=_limits("enquiry", ("5 per minute", "30 per hour"), "60 per hour", "3 per minute", "300 per hour"),
    summary="Enquiry after a Budgetary Estimate (anonymous, consented, Turnstile-gated); links the estimate",
)
def create_enquiry(req: Req):
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.routes import _replay

    key, fingerprint = req.prepared["key"], req.prepared["fingerprint"]
    replay = _replay(req, key, fingerprint)
    if replay is not None:
        return replay
    body = req.body
    estimate, problem = service.usable_for_enquiry(req.session, body.estimate_reference)
    preferred = body.preferred_contact if body.preferred_contact in ("PHONE", "WHATSAPP", "EMAIL") else None
    luxury = body.consultation == "LUXURY_DESIGN"  # any other value is ignored, never an error
    defaults = {}
    if estimate is not None:
        if body.project_type_code in (None, ""):
            defaults["project_type_code"] = estimate.project_type_code
        if body.budget_range_code in (None, ""):
            defaults["budget_range_code"] = estimate.budget_range_code
    lead_body = S.PublicLeadIn.model_validate(
        {
            **body.model_dump(exclude={"estimate_reference", "preferred_contact", "consultation"}, exclude_unset=True),
            **defaults,
        }
    )
    unmapped = {"estimate_reference": f"{problem}:{str(body.estimate_reference)[:40]}"} if problem else None

    def on_created(s, lead):
        if estimate is not None:
            policy = lead.consent_policy_version
            service.link(s, estimate, lead, policy_version=policy, preferred_contact=preferred)
        if luxury:
            service.request_luxury_consultation(s, lead, preferred_contact=preferred)

    data = lead_service.create_public(
        req.session,
        lead_body,
        key=key,
        fingerprint=fingerprint,
        ip=req.ip,
        ua=req.user_agent,
        request_id=req.request_id,
        on_created=on_created,
        extra_unmapped=unmapped,
    )
    result = ok(data, status=201)
    result.headers["Cache-Control"] = "no-store"
    return result


# --- staff ------------------------------------------------------------------------------------------------------------


@api.route("GET", "/leads/<lead_id>/estimates", permission="estimate.read", write=False, requirement="EST-005")
def lead_estimates(req: Req, lead_id: str):
    rows = service.for_lead(req.session, req.ctx, lead_id)
    return ok(
        [
            {
                "id": r.id,
                "reference": r.public_reference,
                "created_on": r.created_on.isoformat(),
                "origin": r.origin,
                "package": r.package,
                "range": {"low_minor": r.range_low_minor, "high_minor": r.range_high_minor},
                "rate_card_version": r.rate_card_version,
                "site_measurement_required": r.site_measurement_required,
            }
            for r in rows
        ]
    )


@api.route("GET", "/estimates/<estimate_id>", permission="estimate.read", write=False, requirement="EST-005")
def get_estimate(req: Req, estimate_id: str):
    row, lead = service.get_for_staff(req.session, req.ctx, estimate_id)
    return ok(service.staff_view(req.session, row, lead))


@api.route(
    "POST", "/estimates/<estimate_id>/duplicate", permission="estimate.manage", status=201, requirement="EST-005"
)
def duplicate_estimate(req: Req, estimate_id: str):
    source, lead = service.get_for_staff(req.session, req.ctx, estimate_id)
    row = service.derive(req.session, req.ctx, source, package=None, selections=None)
    return ok(service.staff_view(req.session, row, lead), status=201)


@api.route(
    "POST",
    "/estimates/<estimate_id>/revisions",
    permission="estimate.manage",
    body=S.EstimateRevisionIn,
    status=201,
    requirement="EST-005",
)
def revise_estimate(req: Req, estimate_id: str):
    source, lead = service.get_for_staff(req.session, req.ctx, estimate_id)
    if req.body.package is None and req.body.selections is None:
        raise ApiError(422, "VALIDATION_FAILED", "Change the package or the selections.")
    row = service.derive(req.session, req.ctx, source, package=req.body.package, selections=req.body.selections)
    return ok(service.staff_view(req.session, row, lead), status=201)


@api.route("POST", "/estimates/<estimate_id>/consultation-copy", permission="estimate.manage", requirement="EST-005")
def consultation_copy(req: Req, estimate_id: str):
    row, _ = service.get_for_staff(req.session, req.ctx, estimate_id)
    return ok(service.consultation_copy(req.session, row))


@api.route("POST", "/estimates/<estimate_id>/site-measurement", permission="estimate.manage", requirement="EST-005")
def site_measurement(req: Req, estimate_id: str):
    row, lead = service.get_for_staff(req.session, req.ctx, estimate_id)
    service.mark_site_measurement(req.session, row, lead)
    return ok(service.staff_view(req.session, row, lead))


@api.route("POST", "/estimates/<estimate_id>/quotation-process", permission="estimate.manage", requirement="EST-005")
def quotation_process(req: Req, estimate_id: str):
    row, lead = service.get_for_staff(req.session, req.ctx, estimate_id)
    service.start_quotation_process(req.session, row, lead)
    return ok({"started": True, "message": "Recorded on the lead. The official quotation is prepared separately."})
