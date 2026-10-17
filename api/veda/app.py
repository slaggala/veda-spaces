"""Application factory (02 §3.1).

Edge middleware order: request-id → security headers → CORS → body-size
limit → JSON parse → authentication → actor context → rate limit. The last
four run inside ``veda.kernel.http.dispatch`` per route.
"""

from __future__ import annotations

import logging
import time

from flask import Flask, g, request
from flask_limiter.errors import RateLimitExceeded
from werkzeug.exceptions import HTTPException

from veda import config as config_mod
from veda.kernel import db, http
from veda.kernel.errors import ApiError
from veda.kernel.logging import configure_logging, log_request

log = logging.getLogger("veda.app")


def _register_modules(app: Flask) -> None:
    from veda.modules.attachments.routes import api as attachments_api
    from veda.modules.catalog.routes import api as catalog_api
    from veda.modules.catalog.routes import public_api as catalog_public_api
    from veda.modules.commercials import events as _commercial_events  # noqa: F401  (registers the email handlers)
    from veda.modules.commercials.routes import api as commercials_api
    from veda.modules.crm.leads import events as _lead_events  # noqa: F401  (registers handlers/resolvers)
    from veda.modules.crm.leads.routes import api as leads_api
    from veda.modules.customer_promise.routes import api as customer_promise_api
    from veda.modules.customer_proposal import events as _proposal_events  # noqa: F401  (registers handlers)
    from veda.modules.customer_proposal.routes import ALL_APIS as cqx_apis
    from veda.modules.estimator import events as _estimate_events  # noqa: F401  (registers resolvers)
    from veda.modules.estimator.routes import api as estimator_api
    from veda.modules.estimator.routes import public_api as estimator_public_api
    from veda.modules.mtq.routes import api as mtq_api
    from veda.modules.mtq_commercial.routes_estimation import api as mtq_estimation_api
    from veda.modules.mtq_commercial.routes_quotation import api as mtq_quotation_api
    from veda.modules.portal import events as _portal_events  # noqa: F401  (registers the email handler)
    from veda.modules.portal.routes import customer_api as portal_customer_api
    from veda.modules.portal.routes import staff_api as portal_staff_api
    from veda.modules.project import events as _project_events  # noqa: F401  (registers handlers)
    from veda.modules.project import notices as _project_notices  # noqa: F401  (registers the delivery handlers)
    from veda.modules.project.routes import api as project_api
    from veda.modules.sales.routes import api as sales_api
    from veda.modules.sales.routes import public_api as sales_public_api
    from veda.modules.warranty import events as _warranty_events  # noqa: F401  (registers handlers and the subscriber)
    from veda.modules.warranty import photos as _warranty_photos  # noqa: F401  (binds the service_request entity)
    from veda.modules.warranty.routes import api as warranty_api
    from veda.platform.audit.routes import api as audit_api
    from veda.platform.auth.routes import api as auth_api
    from veda.platform.health import api as health_api
    from veda.platform.lookups.routes import api as lookups_api
    from veda.platform.notifications.routes import api as notifications_api
    from veda.platform.rbac.routes import approvals_api, permissions_api, roles_api, users_api

    for api in (
        health_api,
        auth_api,
        users_api,
        approvals_api,
        roles_api,
        permissions_api,
        lookups_api,
        notifications_api,
        audit_api,
        leads_api,
        estimator_public_api,
        estimator_api,
        catalog_public_api,
        catalog_api,
        attachments_api,
        mtq_api,
        mtq_estimation_api,
        mtq_quotation_api,
        *cqx_apis,
        customer_promise_api,
        project_api,
        portal_customer_api,
        portal_staff_api,
        commercials_api,
        warranty_api,
        sales_public_api,
        sales_api,
    ):
        if api.name not in app.blueprints:
            app.register_blueprint(api.blueprint)


# The RBX exception register (06 §11), as (method, path) per exception. A route may use an RBX exception only if
# it is listed here (IR-A05). The cancel-link row is DEV-005, proposed for RBX-003 by amendment AM-5.
RBX_REGISTER: dict[str, frozenset[tuple[str, str]]] = {
    "RBX-001": frozenset(
        {("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/mfa/verify"), ("POST", "/api/v1/auth/mfa/recovery")}
    ),
    "RBX-002": frozenset(
        {("POST", "/api/v1/auth/refresh"), ("POST", "/api/v1/auth/logout"), ("POST", "/api/v1/auth/logout-all")}
    ),
    "RBX-003": frozenset(
        {
            ("POST", "/api/v1/auth/password/forgot"),
            ("POST", "/api/v1/auth/password/reset"),
            ("POST", "/api/v1/auth/invite/accept"),
            ("POST", "/api/v1/auth/email/verify"),
            ("POST", "/api/v1/auth/email/cancel"),
            ("POST", "/api/v1/approvals/cancel-link"),
        }
    ),
    "RBX-004": frozenset(
        {
            ("POST", "/api/v1/auth/password/change"),
            ("POST", "/api/v1/auth/reauth"),
            ("POST", "/api/v1/auth/mfa/step-up"),
            ("POST", "/api/v1/auth/mfa/enroll/start"),
            ("POST", "/api/v1/auth/mfa/enroll/confirm"),
            ("POST", "/api/v1/auth/mfa/recovery-codes"),
            ("DELETE", "/api/v1/auth/mfa/factor"),
            ("PUT", "/api/v1/auth/me/email"),
        }
    ),
    "RBX-005": frozenset({("POST", "/api/v1/public/leads")}),
    # ADR-011/012: the only anonymous estimator endpoints (default deny, exact paths, feature-flagged off).
    "RBX-007": frozenset({("POST", "/api/v1/public/estimates"), ("POST", "/api/v1/public/enquiries")}),
    # ADR-013: the catalog-driven estimator (V3); flagged off by default and refused in production.
    "RBX-008": frozenset(
        {
            ("GET", "/api/v1/public/catalog"),
            ("POST", "/api/v1/public/catalog/estimates"),
            ("GET", "/api/v1/public/catalog/media/<sha>"),
            ("POST", "/api/v1/public/catalog/events"),
        }
    ),
    # CQX-01 (decision log 35): the customer's proposal, opened by its secure link; every route flagged off by default
    # and refused in production. The token travels only in the X-Veda-Proposal header (never the URL).
    "RBX-009": frozenset(
        {
            ("GET", "/api/v1/public/proposal"),
            ("GET", "/api/v1/public/proposal/comparison"),
            ("POST", "/api/v1/public/proposal/selections"),
            ("POST", "/api/v1/public/proposal/requests"),
            ("GET", "/api/v1/public/proposal/requests"),
            ("POST", "/api/v1/public/proposal/acknowledgements"),
            ("POST", "/api/v1/public/proposal/decision"),
        }
    ),
    # CPP (decision log 41): the Customer Project Portal. Sign-in and the session exchange are anonymous; every other
    # route resolves the customer's portal session from the X-Veda-Portal header. Flagged off and refused in production.
    "RBX-010": frozenset(
        {
            ("POST", "/api/v1/public/portal/sign-in"),
            ("POST", "/api/v1/public/portal/session"),
            ("POST", "/api/v1/public/portal/sign-out"),
            ("GET", "/api/v1/public/portal/home"),
            ("GET", "/api/v1/public/portal/properties/<property_id>"),
            ("GET", "/api/v1/public/portal/quotations/<quotation_id>"),
            # Project Commercials (decision log 44): the customer's invoices and receipts, through the same session and
            # access rows; 404 unless VEDA_PROJECT_COMMERCIALS_ENABLED is also on.
            ("GET", "/api/v1/public/portal/invoices/<invoice_id>"),
            ("GET", "/api/v1/public/portal/receipts/<receipt_id>"),
            # Project delivery (decision log 45): the customer's two writes, through the same session and access rows;
            # 404 unless VEDA_PROJECT_DELIVERY_PORTAL_ENABLED (and the lifecycle flag) is on, refused while owner
            # decision PEX-D01 does not allow them, rate limited, idempotent.
            ("POST", "/api/v1/public/portal/properties/<property_id>/projects/<project_id>/reports"),
            ("POST", "/api/v1/public/portal/properties/<property_id>/projects/<project_id>/handover/acknowledge"),
            # Customer documents (decision log 46, CPP-D04): an image staff explicitly published, only through the
            # account's authorised property; 404 unless the delivery view is on.
            ("GET", "/api/v1/public/portal/properties/<property_id>/documents/<document_id>/content"),
            # Warranty and after-sales service (decision log 47): the customer's requests and photos, only through the
            # account's authorised property; 404 unless VEDA_WARRANTY_SERVICE_ENABLED (and the lifecycle) is on.
            ("POST", "/api/v1/public/portal/properties/<property_id>/service-requests"),
            ("POST", "/api/v1/public/portal/properties/<property_id>/service-requests/<request_id>/information"),
            ("POST", "/api/v1/public/portal/properties/<property_id>/service-requests/<request_id>/confirm"),
            ("POST", "/api/v1/public/portal/properties/<property_id>/service-requests/<request_id>/reject"),
            ("POST", "/api/v1/public/portal/properties/<property_id>/service-requests/<request_id>/withdraw"),
            ("POST", "/api/v1/public/portal/properties/<property_id>/service-requests/<request_id>/photos"),
            (
                "PUT",
                "/api/v1/public/portal/properties/<property_id>/service-requests/<request_id>/photos/<photo_id>/content",
            ),
            (
                "POST",
                "/api/v1/public/portal/properties/<property_id>/service-requests/<request_id>/photos/<photo_id>/complete",
            ),
            (
                "GET",
                "/api/v1/public/portal/properties/<property_id>/service-requests/<request_id>/photos/<photo_id>/content",
            ),
            (
                "GET",
                "/api/v1/public/portal/properties/<property_id>/service-requests/<request_id>/evidence/<evidence_id>/content",
            ),
        }
    ),
    # Sales & Customer Acquisition (decision log 48): the site's anonymous funnel beacon, counted once per browser
    # session, event and day; 404 unless VEDA_SALES_EXPERIENCE_ENABLED; 1 KiB body, closed schema, per-IP limits; it
    # stores a count per day, event and channel and nothing about the person.
    "RBX-011": frozenset({("POST", "/api/v1/public/acquisition/events")}),
    "RBX-006": frozenset(
        {("GET", "/health/live"), ("GET", "/health/ready"), ("GET", "/api/v1/auth/.well-known/jwks.json")}
    ),
}


def check_route_declarations(app: Flask) -> None:
    """Startup fails if a route lacks a permission or RBX declaration, declares a permission code the registry
    does not define (FC-A04), uses an RBX exception it is not registered for, or is public or optional-auth yet declares a permission that would never be enforced or has no RBX
    registration (06 §8 Layer 1, 06 §11; IR-A05)."""
    from veda.platform.rbac.registry import REGISTRY

    known_codes = {entry.code for entry in REGISTRY}
    declared = {spec.endpoint: spec for spec in http.ROUTES}
    for rule in app.url_map.iter_rules():
        if rule.endpoint in ("static", "openapi"):
            continue
        spec = declared.get(rule.endpoint)
        if spec is None or not spec.declared:
            raise RuntimeError(f"route {rule.rule} ({rule.endpoint}) has no permission or RBX declaration")
        if spec.auth not in http.AUTH_MODES:
            raise RuntimeError(f"route {spec.method} {spec.rule} has an unknown auth mode {spec.auth!r}")
        # A code missing from the registry is never granted, so the route would deny everyone (FC-A04).
        unknown = sorted(c for c in (*spec.permission, *spec.any_of) if c not in known_codes)
        if unknown:
            raise RuntimeError(f"route {spec.method} {spec.rule} declares unknown permission codes {unknown}")
        if spec.rbx and (spec.method, spec.rule) not in RBX_REGISTER.get(spec.rbx, frozenset()):
            raise RuntimeError(f"route {spec.method} {spec.rule} is not in the {spec.rbx} register (06 §11)")
        # Without a signed-in principal (public, or optional auth used anonymously) no permission is ever checked,
        # so such a route must not declare one and must be a registered RBX exception (IR-A05).
        if spec.auth in ("public", "optional") and (spec.permission or spec.any_of):
            raise RuntimeError(
                f"{spec.auth} route {spec.method} {spec.rule} declares a permission that cannot be enforced"
            )
        if spec.auth in ("public", "optional") and not spec.rbx:
            raise RuntimeError(f"{spec.auth} route {spec.method} {spec.rule} is not an RBX-registered exception")


def create_app(settings: config_mod.Settings | None = None) -> Flask:
    settings = settings or config_mod.load_settings()
    problems = config_mod.validate_environment(settings)
    if problems:  # refused before the settings become process-wide
        raise RuntimeError(f"unsafe {settings.env} configuration: " + "; ".join(problems))
    config_mod.use_settings(settings)
    configure_logging(settings.log_level)
    if settings.sentry_dsn:  # pragma: no cover - external service
        import sentry_sdk

        from veda.kernel.logging import sentry_options

        sentry_sdk.init(**sentry_options(settings))

    app = Flask("veda")
    app.config["MAX_CONTENT_LENGTH"] = http.DEFAULT_MAX_BODY
    app.config["RATELIMIT_ENABLED"] = settings.rate_limits_enabled
    app.config["RATELIMIT_HEADERS_ENABLED"] = True
    app.config["RATELIMIT_HEADER_LIMIT"] = "RateLimit-Limit"
    app.config["RATELIMIT_HEADER_REMAINING"] = "RateLimit-Remaining"
    app.config["RATELIMIT_HEADER_RESET"] = "RateLimit-Reset"
    app.json.ensure_ascii = False

    db.configure(settings.database_url)
    if db.is_sqlite():
        with db.engine().connect() as conn:
            info = db.verify_sqlite_runtime(conn)
            if info["foreign_keys"] != 1:
                raise RuntimeError("PRAGMA foreign_keys is not ON (DATA-010)")

    from veda.kernel.ratelimit import limiter

    limiter.init_app(app)
    limiter.enabled = settings.rate_limits_enabled
    _register_modules(app)
    check_route_declarations(app)

    if not settings.is_production:
        from veda.kernel.openapi import build_openapi

        @app.get("/api/v1/openapi.json", endpoint="openapi")
        def openapi():
            return http.json_response(build_openapi(), 200)

    @app.before_request
    def _start():
        g.started = time.perf_counter()
        http.request_id()
        if request.method == "OPTIONS":
            return _preflight()
        return None

    @app.after_request
    def _headers(resp):
        resp.headers["X-Request-ID"] = http.request_id()
        resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/api/") and "Cache-Control" not in resp.headers:
            resp.headers["Cache-Control"] = "no-store"
        _cors(resp)
        log_request(resp, g.get("started"))
        return resp

    @app.errorhandler(RateLimitExceeded)
    def _rate_limited(exc):
        if request.path.startswith("/api/v1/public/"):
            from veda.platform.auth import security_events

            security_events.defer(
                "PUBLIC_INTAKE_BLOCKED", "BLOCKED", failure_reason="RATE_LIMITED", detail={"reason": "rate_limit"}
            )
            security_events.flush_deferred()
        retry = str(max(1, int(getattr(exc, "retry_after", 60) or 60)))
        return http.problem_response(
            ApiError(429, "RATE_LIMITED", "Too many requests. Try again shortly.", headers={"Retry-After": retry})
        )

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        codes = {
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            413: "PAYLOAD_TOO_LARGE",
            415: "UNSUPPORTED_MEDIA_TYPE",
            400: "MALFORMED_JSON",
        }
        code = codes.get(exc.code or 500, "INTERNAL_ERROR")
        return http.problem_response(ApiError(exc.code or 500, code, None))

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):
        log.exception("unhandled_error", extra={"request_id": http.request_id()})
        return http.problem_response(ApiError(500, "INTERNAL_ERROR", "Something went wrong. Quote the request id."))

    return app


def _allowed_origin() -> tuple[str | None, bool]:
    s = config_mod.settings()
    origin = request.headers.get("Origin")
    if not origin:
        return None, False
    if origin == s.app_origin:
        return origin, True
    if origin in s.public_site_origins and request.path.startswith("/api/v1/public/"):
        # Credentials only where the public site itself is behind Cloudflare Access (staging; production refuses).
        return origin, s.public_site_credentials
    return None, False


def _cors(resp) -> None:
    origin, credentials = _allowed_origin()
    if origin is None:
        return
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Vary"] = "Origin"
    if credentials:
        resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Expose-Headers"] = (
        "ETag, X-Request-ID, X-Authz-Version, Retry-After, RateLimit-Limit, RateLimit-Remaining, RateLimit-Reset"
    )


def _preflight():
    from flask import Response

    resp = Response(status=204)
    origin, credentials = _allowed_origin()
    if origin is not None:
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        # X-Veda-Client: the estimator wizard's per-browser token (rate-limit key, ADR-012). X-Veda-Proposal: a
        # customer proposal link's token (CQX-01), sent as a header so it never appears in a URL. X-Veda-Portal: a
        # customer's portal session token (CPP-001), likewise.
        resp.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, If-Match, Idempotency-Key, X-Request-ID, X-Requested-With, X-Veda-Client, "
            "X-Veda-Proposal, X-Veda-Portal"
        )
        resp.headers["Access-Control-Max-Age"] = "600"
    return resp
