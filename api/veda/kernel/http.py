"""HTTP layer: route specs, enforcement pipeline, envelopes and pagination.

Every route declares a permission code (or codes) or an RBAC exception id
(06 §11). Startup fails if a non-public route lacks a declaration (06 §8
Layer 1). The pipeline per request is (02 §3.1, §3.4):

    request-id → authentication (JWT + uncached session read) → session-type
    gate (Layer 0) → permission gate (Layer 1) → closed DTO validation
    (Layer 4) → If-Match → ActorContext → service (Layers 2/3) → commit →
    envelope (+ ETag, X-Authz-Version)
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from flask import Blueprint, Response, g, request
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from veda.kernel import clock, db, net
from veda.kernel.context import ActorContext, reset_actor, set_actor
from veda.kernel.errors import ApiError, field_error, problem_body, validation_failed
from veda.kernel.ids import is_valid_id
from veda.kernel.jcs import canonical_bytes

JSON_MIME = "application/json; charset=utf-8"
PROBLEM_MIME = "application/problem+json"
DEFAULT_MAX_BODY = 1024 * 1024
PUBLIC_MAX_BODY = 16 * 1024

ROUTES: list[RouteSpec] = []


# bearer: authentication required; public: never authenticated (RBX-registered); optional: authenticated when an
# Authorization header is sent, otherwise anonymous (RBX-registered, no permission). Nothing else is valid (FC-06).
AUTH_MODES = frozenset({"bearer", "public", "optional"})


@dataclass
class RouteSpec:
    method: str
    rule: str
    endpoint: str
    blueprint: str
    handler: Callable
    auth: str  # one of AUTH_MODES
    permission: tuple[str, ...] = ()  # all required
    any_of: tuple[str, ...] = ()
    rbx: str | None = None
    body: type[BaseModel] | None = None
    query: type[BaseModel] | None = None
    if_match: bool = False
    status: int = 200
    write: bool = True
    recovery_allowed: bool = False
    pwd_change_allowed: bool = False
    max_body: int = DEFAULT_MAX_BODY
    idempotent_create: bool = False
    summary: str = ""
    tags: tuple[str, ...] = ()
    requirement: str | None = None
    response_description: str = ""
    # Public routes only: work that must not hold the database write lock (network I/O such as Turnstile
    # siteverify). Runs before the write transaction opens, with a read-only session (IR-02).
    prepare: Callable | None = None

    @property
    def declared(self) -> bool:
        return bool(self.permission or self.any_of or self.rbx)

    @property
    def openapi_path(self) -> str:
        return re.sub(r"<(?:[a-z]+:)?([a-z_]+)>", r"{\1}", self.rule)


@dataclass
class Req:
    """What a handler receives."""

    session: Session
    ctx: Any  # veda.platform.auth.request_auth.AuthContext | None
    body: Any
    query: Any
    raw: dict | None
    if_match: int | None
    request_id: str
    ip: str | None
    user_agent: str | None
    spec: RouteSpec
    headers: Any = None
    cookies: Any = None
    after_commit: list[Callable[[], None]] = field(default_factory=list)
    prepared: Any = None  # what the route's prepare step returned

    def require_version(self, current: int) -> None:
        check_version(self.if_match, current)


@dataclass
class Result:
    data: Any = None
    status: int = 200
    meta: dict | None = None
    links: dict | None = None
    etag: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    cookies: list[tuple[tuple, dict]] = field(default_factory=list)
    delete_cookies: list[tuple[tuple, dict]] = field(default_factory=list)
    raw_body: dict | None = None  # returned as-is (no envelope), e.g. JWKS


def ok(
    data: Any = None,
    *,
    status: int = 200,
    meta: dict | None = None,
    links: dict | None = None,
    etag: int | None = None,
    headers: dict | None = None,
) -> Result:
    if etag is None and isinstance(data, dict) and isinstance(data.get("version"), int):
        etag = data["version"]
    return Result(data=data, status=status, meta=meta, links=links, etag=etag, headers=headers or {})


def no_content() -> Result:
    return Result(status=204)


def check_version(if_match: int | None, current: int, *, conflict_extra: dict | None = None) -> None:
    if if_match is None:
        raise ApiError(428, "PRECONDITION_REQUIRED", "Send If-Match with the version you edited.")
    if if_match != current:
        raise ApiError(
            409,
            "VERSION_CONFLICT",
            "The record was changed after you loaded it.",
            extra={"current_version": current, **(conflict_extra or {})},
        )


# --- request helpers -----------------------------------------------------------

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def request_id() -> str:
    rid = getattr(g, "request_id", None)
    if rid:
        return rid
    incoming = request.headers.get("X-Request-ID") or request.headers.get("CF-Ray")
    rid = (
        incoming
        if incoming and _REQUEST_ID_RE.match(incoming)
        else binascii.hexlify(__import__("os").urandom(8)).decode()
    )
    g.request_id = rid
    return rid


def client_ip() -> str | None:
    # CF-Connecting-IP is honoured only from a configured trusted proxy (IR-35, 02 §11).
    return net.client_ip(request.remote_addr, request.headers.get("CF-Connecting-IP"))


def network_of(ip: str | None) -> str:
    """IPv4 /24 or IPv6 /64 (05 §4, A-01)."""
    return net.network_of(ip)


def mask_ip(ip: str | None) -> str | None:
    return net.mask(ip)


def _parse_if_match(value: str | None) -> int | None:
    if value is None:
        return None
    v = value.strip()
    if v.startswith("W/"):
        v = v[2:]
    v = v.strip('"')
    if not v.isdigit():
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "If-Match must be a version number.",
            errors=[field_error("If-Match", "INVALID", "Expected a quoted version number.")],
        )
    return int(v)


def pydantic_errors(exc: ValidationError) -> list[dict]:
    out = []
    for err in exc.errors(include_url=False):
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "__root__") or "body"
        etype = err.get("type", "")
        ctx = err.get("ctx") or {}
        if etype == "extra_forbidden":
            code = "UNKNOWN_FIELD"
            message = "This field is not accepted."
        elif etype == "missing":
            code, message = "REQUIRED", "This field is required."
        elif etype in ("string_too_long", "too_long"):
            code, message = "TOO_LONG", f"Must be at most {ctx.get('max_length', '')} characters.".replace("  ", " ")
        elif etype in ("string_too_short", "too_short"):
            code, message = "TOO_SHORT", "Too short."
        elif etype.isupper():
            code, message = etype, err.get("msg", "Invalid value.")
        else:
            code, message = "INVALID", err.get("msg", "Invalid value.")
        out.append(field_error(loc, code, message))
    return out


def _load_json_body(spec: RouteSpec) -> dict | None:
    length = request.content_length
    if length is not None and length > spec.max_body:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "The request body is too large.")
    raw = request.get_data(cache=True)
    if len(raw) > spec.max_body:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "The request body is too large.")
    if not raw.strip():
        return None
    ctype = (request.mimetype or "").lower()
    if ctype != "application/json":
        raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Send application/json.")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ApiError(400, "MALFORMED_JSON", "The body is not valid JSON.") from exc
    if not isinstance(data, dict):
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "The body must be a JSON object.",
            errors=[field_error("body", "INVALID", "Expected an object.")],
        )
    return data


def _validate_body(spec: RouteSpec, data: dict | None):
    if spec.body is None:
        if data:
            raise validation_failed([field_error(k, "UNKNOWN_FIELD", "This field is not accepted.") for k in data])
        return None
    immutable = [k for k in (data or {}) if k in getattr(spec.body, "__immutable__", frozenset())]
    if immutable:
        raise ApiError(
            422,
            "IMMUTABLE_FIELD",
            "These fields are immutable.",
            errors=[field_error(k, "IMMUTABLE_FIELD", "This field cannot be changed.") for k in immutable],
        )
    blocked = getattr(spec.body, "__not_updatable__", frozenset())
    hits = [k for k in (data or {}) if k in blocked]
    if hits:
        raise ApiError(
            422,
            "FIELD_NOT_UPDATABLE",
            "These fields have their own workflow.",
            errors=[field_error(k, "FIELD_NOT_UPDATABLE", "This field cannot be changed here.") for k in hits],
        )
    try:
        return spec.body.model_validate(data or {})
    except ValidationError as exc:
        errors = pydantic_errors(exc)
        for code, message in (
            ("INVALID_ID", "An identifier is not a canonical UUIDv7."),
            ("INVALID_DATETIME", "Datetimes need a UTC offset."),
        ):
            if any(e["code"] == code for e in errors):
                raise ApiError(422, code, message, errors=errors) from exc
        top = getattr(spec.body, "__top_level_codes__", {})
        for e in errors:
            if e["code"] in top:
                raise ApiError(422, e["code"], e["message"], errors=errors) from exc
        raise validation_failed(errors) from exc


def _validate_query(spec: RouteSpec):
    args: dict[str, Any] = {}
    for key in request.args.keys():
        values = request.args.getlist(key)
        args[key] = ",".join(values) if len(values) > 1 else values[0]
    if spec.query is None:
        if args:
            raise ApiError(
                422,
                "INVALID_QUERY_PARAM",
                "Unknown query parameters.",
                errors=[field_error(k, "INVALID_QUERY_PARAM", "Unknown parameter.") for k in args],
            )
        return None
    try:
        return spec.query.model_validate(args)
    except ValidationError as exc:
        errors = pydantic_errors(exc)
        for e in errors:
            if e["code"] in ("UNKNOWN_FIELD",):
                e["code"] = "INVALID_QUERY_PARAM"
        if any(e["code"] == "INVALID_ID" for e in errors):
            raise ApiError(422, "INVALID_ID", "An identifier is not a canonical UUIDv7.", errors=errors) from exc
        if any(e["code"] == "INVALID_DATETIME" for e in errors):
            raise ApiError(422, "INVALID_DATETIME", "Datetimes need an offset.", errors=errors) from exc
        raise ApiError(422, "INVALID_QUERY_PARAM", "Invalid query parameters.", errors=errors) from exc


# --- response building ---------------------------------------------------------


def json_response(body: Any, status: int, mimetype: str = JSON_MIME) -> Response:
    return Response(
        json.dumps(body, ensure_ascii=False, separators=(",", ":"), default=str),
        status=status,
        mimetype=mimetype.split(";")[0],
        content_type=mimetype,
    )


def problem_response(err: ApiError) -> Response:
    resp = Response(
        json.dumps(problem_body(err, request_id()), ensure_ascii=False), status=err.status, content_type=PROBLEM_MIME
    )
    for k, v in err.headers.items():
        resp.headers[k] = v
    return resp


def build_response(result: Result | Response | None, spec: RouteSpec) -> Response:
    if isinstance(result, Response):
        return result
    if result is None:
        result = no_content()
    if result.raw_body is not None:
        resp = json_response(result.raw_body, result.status)
    elif result.status == 204:
        resp = Response(status=204)
    else:
        body: dict[str, Any] = {"data": result.data}
        if result.meta is not None:
            body["meta"] = result.meta
        if result.links is not None:
            body["links"] = result.links
        resp = json_response(body, result.status)
    if result.etag is not None:
        resp.headers["ETag"] = f'"{result.etag}"'
    for k, v in result.headers.items():
        resp.headers[k] = v
    for args, kwargs in result.cookies:
        resp.set_cookie(*args, **kwargs)
    for args, kwargs in result.delete_cookies:
        resp.delete_cookie(*args, **kwargs)
    return resp


# --- pagination (08 §2.5) --------------------------------------------------------


def offset_meta(page: int, page_size: int, total: int, path: str, params: dict[str, Any]) -> tuple[dict, dict]:
    total_pages = max(1, -(-total // page_size)) if total else 0
    estimate = total > 10_000
    meta = {"page": page, "page_size": page_size, "total": min(total, 10_000), "total_pages": total_pages}
    if estimate:
        meta["total_is_estimate"] = True

    def link(p: int | None) -> str | None:
        if p is None:
            return None
        q = {k: v for k, v in params.items() if v not in (None, "") and k not in ("page", "page_size")}
        q.update(page=p, page_size=page_size)
        return path + "?" + "&".join(f"{k}={v}" for k, v in q.items())

    links = {
        "self": link(page),
        "next": link(page + 1) if page < total_pages else None,
        "prev": link(page - 1) if page > 1 else None,
    }
    return meta, links


def encode_cursor(sort_value: str, row_id: str) -> str:
    return base64.urlsafe_b64encode(json.dumps({"t": sort_value, "id": row_id}).encode()).rstrip(b"=").decode()


def decode_cursor(cursor: str | None) -> tuple[str, str] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        if not is_valid_id(data["id"]):
            raise ValueError
        return data["t"], data["id"]
    except Exception as exc:
        raise ApiError(
            422,
            "INVALID_QUERY_PARAM",
            "Invalid cursor.",
            errors=[field_error("cursor", "INVALID_QUERY_PARAM", "Invalid cursor.")],
        ) from exc


# --- authenticated idempotency store (08 §2.8) ---------------------------------------


class _IdemStore:
    TTL = 24 * 3600

    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict[tuple, tuple[float, str, int, dict]] = {}

    def get(self, key):
        with self._lock:
            item = self._data.get(key)
            if item and item[0] > time.monotonic():
                return item
            self._data.pop(key, None)
            return None

    def put(self, key, fingerprint, status, body):
        with self._lock:
            self._data[key] = (time.monotonic() + self.TTL, fingerprint, status, body)

    def clear(self):
        with self._lock:
            self._data.clear()


idempotency_store = _IdemStore()
IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def body_fingerprint(data: dict | None, exclude: tuple[str, ...] = ()) -> str:
    import hashlib

    payload = {k: v for k, v in (data or {}).items() if k not in exclude}
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


# --- the Api blueprint wrapper ------------------------------------------------------


class Api:
    def __init__(self, name: str, url_prefix: str = "", tags: tuple[str, ...] = ()):
        self.blueprint = Blueprint(name, __name__, url_prefix=url_prefix)
        self.name = name
        self.prefix = url_prefix
        self.tags = tags

    def route(
        self,
        method: str,
        rule: str,
        *,
        permission: str | tuple[str, ...] | None = None,
        any_of: tuple[str, ...] = (),
        rbx: str | None = None,
        auth: str = "bearer",
        body: type[BaseModel] | None = None,
        query: type[BaseModel] | None = None,
        if_match: bool = False,
        status: int = 200,
        write: bool | None = None,
        recovery_allowed: bool = False,
        pwd_change_allowed: bool = False,
        max_body: int = DEFAULT_MAX_BODY,
        idempotent_create: bool = False,
        summary: str = "",
        requirement: str | None = None,
        limits: list | None = None,
        limit_key: Callable | None = None,
        prepare: Callable | None = None,
    ):
        perms = (permission,) if isinstance(permission, str) else tuple(permission or ())
        if auth not in AUTH_MODES:  # exact, case-sensitive: an unknown mode never falls through to anonymous (FC-06)
            raise RuntimeError(f"route {method} {rule}: unknown auth mode {auth!r}; allowed: {sorted(AUTH_MODES)}")
        if prepare is not None and auth != "public":
            raise RuntimeError("prepare steps are for public routes only")

        def decorator(fn: Callable) -> Callable:
            spec = RouteSpec(
                method=method,
                rule=self.prefix + rule,
                endpoint=f"{self.name}.{fn.__name__}",
                blueprint=self.name,
                handler=fn,
                auth=auth,
                permission=perms,
                any_of=tuple(any_of),
                rbx=rbx,
                body=body,
                query=query,
                if_match=if_match,
                status=status,
                write=(method != "GET") if write is None else write,
                recovery_allowed=recovery_allowed,
                pwd_change_allowed=pwd_change_allowed,
                max_body=max_body,
                idempotent_create=idempotent_create,
                summary=summary or (fn.__doc__ or "").strip().split("\n")[0],
                tags=self.tags,
                requirement=requirement,
                prepare=prepare,
            )
            ROUTES.append(spec)

            def view(**kwargs):
                return dispatch(spec, kwargs)

            view.__name__ = fn.__name__
            if limits:
                from veda.kernel.ratelimit import limiter

                for limit in limits:
                    # A limit is "N per period", (value, key) or (value, key, options): options are passed to
                    # Flask-Limiter (e.g. deduct_when, so a bucket counts only some responses).
                    if not isinstance(limit, tuple):
                        limit = (limit, limit_key)
                    value, key, options = limit[0], limit[1], (limit[2] if len(limit) > 2 else {})
                    if key:
                        options = {**options, "key_func": key}
                    view = limiter.limit(value, **options)(view)
            self.blueprint.add_url_rule(rule, endpoint=fn.__name__, view_func=view, methods=[method])
            return fn

        return decorator


def dispatch(spec: RouteSpec, path_params: dict[str, Any]) -> Response:
    from veda.platform.auth import request_auth, security_events

    security_events.begin_request_scope()
    rid = request_id()
    session: Session | None = None
    token = None
    ctx = None
    try:
        for name, value in path_params.items():
            if name.endswith("_id") and not is_valid_id(value):
                raise ApiError(
                    422,
                    "INVALID_ID",
                    f"{name} is not a canonical identifier.",
                    errors=[field_error(name, "INVALID_ID", "Expected 32 lowercase hex characters (UUIDv7).")],
                )
        raw = _load_json_body(spec) if spec.method in ("POST", "PUT", "PATCH", "DELETE") else None
        if spec.method == "GET" and request.get_data(cache=True).strip():
            raise ApiError(422, "VALIDATION_FAILED", "GET requests take no body.")
        prepared = None
        if spec.prepare is not None:
            pre_ctx = ActorContext(
                actor_id=request_auth.anonymous_actor_id(),
                via="API",
                request_id=rid,
                ip=client_ip(),
                user_agent=(request.headers.get("User-Agent") or "")[:500] or None,
            )
            token = set_actor(pre_ctx)
            with db.unit_of_work(write=False) as read_session:
                pre = Req(
                    session=read_session,
                    ctx=None,
                    body=_validate_body(spec, raw),
                    query=None,
                    raw=raw,
                    if_match=None,
                    request_id=rid,
                    ip=pre_ctx.ip,
                    user_agent=pre_ctx.user_agent,
                    spec=spec,
                    headers=request.headers,
                    cookies=request.cookies,
                )
                prepared = spec.prepare(pre)
            reset_actor(token)
            token = None
            if isinstance(prepared, Result):
                return _finish(build_response(prepared, spec), None)
        if spec.auth not in AUTH_MODES:  # defence in depth for a spec built outside route()
            raise RuntimeError(f"unknown auth mode {spec.auth!r}")
        session = db.new_session(write=spec.write)
        if spec.auth == "bearer" or (spec.auth == "optional" and request.headers.get("Authorization")):
            ctx = request_auth.authenticate(session, spec)
            from veda.kernel.ratelimit import user_limit_retry_after

            retry = user_limit_retry_after(ctx.user.id)
            if retry is not None:
                raise ApiError(
                    429, "RATE_LIMITED", "Too many requests. Try again shortly.", headers={"Retry-After": str(retry)}
                )
        actor_ctx = ActorContext(
            actor_id=ctx.user.id if ctx else request_auth.anonymous_actor_id(),
            via="API",
            request_id=rid,
            session_id=ctx.session.id if ctx else None,
            ip=client_ip(),
            user_agent=(request.headers.get("User-Agent") or "")[:500] or None,
        )
        token = set_actor(actor_ctx)
        if ctx is not None:
            request_auth.enforce_gates(session, ctx, spec)
        body = _validate_body(spec, raw)
        query = _validate_query(spec)
        if_match = _parse_if_match(request.headers.get("If-Match"))
        if spec.if_match and if_match is None:
            raise ApiError(428, "PRECONDITION_REQUIRED", "Send If-Match with the version you edited.")
        req = Req(
            session=session,
            ctx=ctx,
            body=body,
            query=query,
            raw=raw,
            if_match=if_match,
            request_id=rid,
            ip=actor_ctx.ip,
            user_agent=actor_ctx.user_agent,
            spec=spec,
            headers=request.headers,
            cookies=request.cookies,
            prepared=prepared,
        )

        idem_key = None
        if spec.idempotent_create and ctx is not None and request.headers.get("Idempotency-Key"):
            key = request.headers["Idempotency-Key"]
            if not IDEMPOTENCY_KEY_RE.match(key):
                raise ApiError(
                    422,
                    "VALIDATION_FAILED",
                    "Invalid Idempotency-Key.",
                    errors=[field_error("Idempotency-Key", "INVALID", "16–64 characters [A-Za-z0-9_-].")],
                )
            idem_key = (ctx.user.id, spec.endpoint, key)
            fp = body_fingerprint(raw)
            hit = idempotency_store.get(idem_key)
            if hit:
                if hit[1] != fp:
                    raise ApiError(422, "IDEMPOTENCY_KEY_REUSED", "This key was used with a different request.")
                session.rollback()
                return _finish(json_response(hit[3], hit[2]), ctx)

        result = spec.handler(req, **path_params)
        if spec.write:
            session.commit()
        else:
            session.rollback()
        for fn in req.after_commit:
            fn()
        response = build_response(result, spec)
        if idem_key and response.status_code < 300:
            idempotency_store.put(idem_key, body_fingerprint(raw), response.status_code, response.get_json())
        return _finish(response, ctx)
    except ApiError as err:
        if session is not None:
            session.rollback()
        return _finish(problem_response(err), ctx, error=True)
    except Exception as exc:
        if session is not None:
            session.rollback()
        mapped = _map_db_error(exc)
        if mapped is not None:
            return _finish(problem_response(mapped), None)
        raise
    finally:
        if session is not None:
            session.close()
        if token is not None:
            reset_actor(token)
        security_events.flush_deferred()
        request_auth.run_post_request_writes()


def _finish(resp: Response, ctx, *, error: bool = False) -> Response:
    if ctx is not None:
        # After a rollback use the version resolved at authentication; never lazy-load from the session.
        version = ctx.res.authz_version if error else ctx.user.authz_version
        resp.headers["X-Authz-Version"] = str(version)
    return resp


def _map_db_error(exc: Exception) -> ApiError | None:
    from sqlalchemy.exc import IntegrityError, OperationalError
    from sqlalchemy.orm.exc import StaleDataError

    if isinstance(exc, StaleDataError):
        return ApiError(409, "VERSION_CONFLICT", "The record was changed by someone else.")
    if isinstance(exc, IntegrityError):
        text = str(exc.orig).lower()
        if "unique" in text or "duplicate key" in text:
            return ApiError(409, "DUPLICATE", "A record with the same key already exists.")
        return None
    if isinstance(exc, OperationalError) and ("locked" in str(exc).lower() or "busy" in str(exc).lower()):
        return ApiError(503, "SERVICE_UNAVAILABLE", "The database is busy. Try again.", headers={"Retry-After": "2"})
    return None


def now_iso() -> str:
    return clock.to_rfc3339(clock.now())
