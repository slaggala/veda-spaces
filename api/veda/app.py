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
    from veda.modules.crm.leads import events as _lead_events  # noqa: F401  (registers handlers/resolvers)
    from veda.modules.crm.leads.routes import api as leads_api
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
    "RBX-006": frozenset(
        {("GET", "/health/live"), ("GET", "/health/ready"), ("GET", "/api/v1/auth/.well-known/jwks.json")}
    ),
}


def check_route_declarations(app: Flask) -> None:
    """Startup fails if a route lacks a permission or RBX declaration, uses an RBX exception it is not registered
    for, or is public yet declares a permission that would never be enforced (06 §8 Layer 1, 06 §11; IR-A05)."""
    declared = {spec.endpoint: spec for spec in http.ROUTES}
    for rule in app.url_map.iter_rules():
        if rule.endpoint in ("static", "openapi"):
            continue
        spec = declared.get(rule.endpoint)
        if spec is None or not spec.declared:
            raise RuntimeError(f"route {rule.rule} ({rule.endpoint}) has no permission or RBX declaration")
        if spec.rbx and (spec.method, spec.rule) not in RBX_REGISTER.get(spec.rbx, frozenset()):
            raise RuntimeError(f"route {spec.method} {spec.rule} is not in the {spec.rbx} register (06 §11)")
        if spec.auth == "public" and (spec.permission or spec.any_of):
            raise RuntimeError(f"public route {spec.method} {spec.rule} declares a permission that cannot be enforced")


def create_app(settings: config_mod.Settings | None = None) -> Flask:
    settings = settings or config_mod.load_settings()
    problems = config_mod.validate_environment(settings)
    if problems:  # refused before the settings become process-wide
        raise RuntimeError(f"unsafe {settings.env} configuration: " + "; ".join(problems))
    config_mod.use_settings(settings)
    configure_logging(settings.log_level)
    if settings.sentry_dsn:  # pragma: no cover - external service
        import sentry_sdk

        from veda.kernel.logging import sentry_before_send

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            send_default_pii=False,
            traces_sample_rate=0.1,
            environment=settings.env,
            include_local_variables=False,
            max_request_body_size="never",
            before_send=sentry_before_send,
        )

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
        return origin, False
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
        resp.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, If-Match, Idempotency-Key, X-Request-ID, X-Requested-With"
        )
        resp.headers["Access-Control-Max-Age"] = "600"
    return resp
