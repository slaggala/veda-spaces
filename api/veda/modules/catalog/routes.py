"""Catalog routes (ADR-013).

Staff (`/api/v1/catalog/...`): least privilege per action (D10). The route declares the floor (`catalog.view`); the
handler requires the duty: the edit permission of the record's kind, `catalog.review`, `catalog.approve` or
`catalog.admin`. Pricing records are invisible without `catalog.pricing.view`.

Public (RBX-008, `/api/v1/public/catalog...`): answer 404 unless VEDA_CATALOG_ESTIMATOR_ENABLED (off by default;
production refuses it). The estimate endpoint is Turnstile-gated and rate-limited like the V2 one. Media delivery
serves only CLEAN variants of the ACTIVE release, by content hash.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Any

from flask import Response

from veda.config import settings
from veda.kernel.dto import Closed
from veda.kernel.errors import ApiError
from veda.kernel.http import PUBLIC_MAX_BODY, Api, Req, ok
from veda.modules.estimator import routes as estimator_routes

from . import configure, importexport, kinds, media, service
from .models import CatalogEvent, CatalogMediaObject, CatalogRecord, CatalogRelease
from .permissions import edit_permission

api = Api("catalog", "/api/v1/catalog", tags=("catalog",))
public_api = Api("catalog_public", "/api/v1/public", tags=("catalog",))

MEDIA_MAX_BODY = 36 * 1024 * 1024  # 25 MB of model or 15 MB of image, base64-encoded


class RecordIn(Closed):
    kind: str
    key: str
    document: dict


class DocumentIn(Closed):
    document: dict


class NoteIn(Closed):
    note: str | None = None


class KeyIn(Closed):
    key: str


class ReleaseIn(Closed):
    code: str
    exclude: list[str] = []  # "kind:key" entries to retire


class ApprovalIn(Closed):
    approval_reference: str


class ScheduleIn(Closed):
    at: datetime


class ConfigIn(Closed):
    configuration: dict
    staff: bool = False  # price as staff would (unavailable_online and staff_only allowed)


class MediaIn(Closed):
    data_base64: str


class ImportIn(Closed):
    format: str
    content: str
    apply: bool = False


class RecordsQuery(Closed):
    kind: str | None = None
    status: str | None = None
    key: str | None = None


class ExportQuery(Closed):
    release_id: str | None = None
    format: str = "json"


class PublicEstimateIn(Closed):
    configuration: Any = None
    turnstile_token: Any = None


class PublicEventIn(Closed):
    event: Any = None
    subject: Any = None


def _err(err: Exception) -> ApiError:
    return ApiError(422, "CATALOG_REFUSED", str(err)[:500])


def _can_price(req: Req) -> bool:
    return req.ctx.has("catalog.pricing.view")


def _record_view(req: Req, row: CatalogRecord, *, document: bool = True) -> dict:
    hidden = row.kind in kinds.STAFF_ONLY_KINDS and not _can_price(req)
    out = {
        "id": row.id, "kind": row.kind, "key": row.record_key, "version": row.record_version, "status": row.status,
        "title": "Pricing record" if hidden else row.title, "sha256": row.document_sha256,
        "updated_on": row.updated_on.isoformat(), "updated_by": row.updated_by, "submitted_by": row.submitted_by,
        "reviewed_by": row.reviewed_by, "review_note": row.review_note,
    }  # fmt: skip
    if document and not hidden:
        out["document"] = row.document
    return out


def _record(req: Req, record_id: str) -> CatalogRecord:
    try:
        row = service.get_record(req.session, record_id)
    except service.CatalogError as err:
        raise ApiError(404, "NOT_FOUND", "No such catalog record.") from err
    if row.kind in kinds.STAFF_ONLY_KINDS and not _can_price(req):
        raise ApiError(404, "NOT_FOUND", "No such catalog record.")
    return row


def _release_view(row: CatalogRelease, *, detail: bool = False) -> dict:
    out = {
        "id": row.id, "code": row.release_code, "status": row.status, "manifest_sha256": row.manifest_sha256,
        "entries": len(row.manifest["entries"]), "created_by": row.created_by, "created_on": row.created_on.isoformat(),
        "preview_approved_by": row.preview_approved_by, "submitted_by": row.submitted_by,
        "approved_by": row.approved_by, "approval_reference": row.approval_reference,
        "scheduled_for": row.scheduled_for.isoformat() if row.scheduled_for else None,
        "activated_on": row.activated_on.isoformat() if row.activated_on else None,
        "valid": (row.validation or {}).get("ok"),
    }  # fmt: skip
    if detail:
        out["manifest"] = [{k: e[k] for k in ("kind", "key", "version", "sha256")} for e in row.manifest["entries"]]
        out["validation"] = row.validation
        out["compiled"] = row.compiled
    return out


def _release(req: Req, release_id: str) -> CatalogRelease:
    try:
        return service.get_release(req.session, release_id)
    except service.CatalogError as err:
        raise ApiError(404, "NOT_FOUND", "No such catalog release.") from err


# --- staff: dashboard and records ------------------------------------------------------------------------------------
@api.route("GET", "/dashboard", permission="catalog.view", write=False, requirement="CAT-001")
def dashboard(req: Req):
    return ok(service.dashboard(req.session, can_price=_can_price(req)))


@api.route("GET", "/records", permission="catalog.view", write=False, query=RecordsQuery, requirement="CAT-001")
def list_records(req: Req):
    import sqlalchemy as sa

    q = sa.select(CatalogRecord).where(CatalogRecord.is_deleted.is_(False))
    if req.query.kind:
        q = q.where(CatalogRecord.kind == req.query.kind)
    if req.query.status:
        q = q.where(CatalogRecord.status == req.query.status)
    if req.query.key:
        q = q.where(CatalogRecord.record_key == req.query.key)
    if not _can_price(req):
        q = q.where(CatalogRecord.kind.not_in(sorted(kinds.STAFF_ONLY_KINDS)))
    rows = req.session.execute(
        q.order_by(CatalogRecord.kind, CatalogRecord.record_key, CatalogRecord.record_version).limit(2000)
    )
    return ok([_record_view(req, r, document=False) for r in rows.scalars()])


@api.route("GET", "/records/<record_id>", permission="catalog.view", write=False, requirement="CAT-001")
def get_record(req: Req, record_id: str):
    return ok(_record_view(req, _record(req, record_id)))


@api.route("POST", "/records", permission="catalog.view", body=RecordIn, status=201, requirement="CAT-002")
def create_record(req: Req):
    req.ctx.require(edit_permission(req.body.kind))
    try:
        row = service.create_record(req.session, req.body.kind, req.body.key, req.body.document)
    except service.CatalogError as err:
        raise _err(err) from err
    return ok(_record_view(req, row), status=201)


def _edit(req: Req, record_id: str, action, *args):
    row = _record(req, record_id)
    req.ctx.require(edit_permission(row.kind))
    try:
        return ok(_record_view(req, action(req.session, row.id, *args)))
    except service.CatalogError as err:
        raise _err(err) from err


@api.route("PUT", "/records/<record_id>", permission="catalog.view", body=DocumentIn, requirement="CAT-002")
def update_record(req: Req, record_id: str):
    return _edit(req, record_id, service.update_draft, req.body.document)


@api.route("POST", "/records/<record_id>/submit", permission="catalog.view", requirement="CAT-002")
def submit_record(req: Req, record_id: str):
    return _edit(req, record_id, service.submit)


@api.route("POST", "/records/<record_id>/archive", permission="catalog.view", requirement="CAT-002")
def archive_record(req: Req, record_id: str):
    return _edit(req, record_id, service.archive_record)


@api.route("POST", "/records/<record_id>/new-version", permission="catalog.view", status=201, requirement="CAT-002")
def new_version(req: Req, record_id: str):
    row = _record(req, record_id)
    req.ctx.require(edit_permission(row.kind))
    try:
        return ok(_record_view(req, service.new_version(req.session, row.kind, row.record_key)), status=201)
    except service.CatalogError as err:
        raise _err(err) from err


@api.route(
    "POST", "/records/<record_id>/clone", permission="catalog.view", body=KeyIn, status=201, requirement="CAT-002"
)
def clone_record(req: Req, record_id: str):
    row = _record(req, record_id)
    req.ctx.require(edit_permission(row.kind))
    try:
        return ok(_record_view(req, service.clone(req.session, row.id, req.body.key)), status=201)
    except service.CatalogError as err:
        raise _err(err) from err


@api.route("POST", "/records/<record_id>/approve", permission="catalog.review", body=NoteIn, requirement="CAT-006")
def approve_record(req: Req, record_id: str):
    row = _record(req, record_id)
    try:
        return ok(_record_view(req, service.approve_record(req.session, row.id, req.body.note)))
    except service.CatalogError as err:
        raise _err(err) from err


@api.route("POST", "/records/<record_id>/reject", permission="catalog.review", body=NoteIn, requirement="CAT-006")
def reject_record(req: Req, record_id: str):
    row = _record(req, record_id)
    try:
        return ok(_record_view(req, service.reject_record(req.session, row.id, req.body.note or "")))
    except service.CatalogError as err:
        raise _err(err) from err


@api.route("GET", "/records/<record_id>/events", permission="catalog.view", write=False, requirement="CAT-001")
def record_events(req: Req, record_id: str):
    import sqlalchemy as sa

    row = _record(req, record_id)
    events = req.session.execute(
        sa.select(CatalogEvent).where(CatalogEvent.record_id == row.id).order_by(CatalogEvent.created_on)
    ).scalars()
    return ok([{"event": e.event_type, "on": e.created_on.isoformat(), "by": e.created_by, "detail": e.detail}
               for e in events])  # fmt: skip


# --- staff: releases -------------------------------------------------------------------------------------------------
@api.route("GET", "/releases", permission="catalog.view", write=False, requirement="CAT-001")
def list_releases(req: Req):
    import sqlalchemy as sa

    rows = req.session.execute(
        sa.select(CatalogRelease).where(CatalogRelease.is_deleted.is_(False)).order_by(CatalogRelease.created_on.desc())
    ).scalars()
    return ok([_release_view(r) for r in rows])


@api.route("GET", "/releases/<release_id>", permission="catalog.view", write=False, requirement="CAT-001")
def get_release(req: Req, release_id: str):
    row = _release(req, release_id)
    view = _release_view(row, detail=True)
    if not _can_price(req) and view["validation"]:
        view["validation"] = {**view["validation"], "errors": [
            e for e in view["validation"]["errors"] if not e.startswith(("pricing:", "card:"))
        ]}  # fmt: skip
    view["diff"] = service.diff(req.session, row)
    return ok(view)


def _release_action(req: Req, release_id: str, action, *args):
    row = _release(req, release_id)
    try:
        return ok(_release_view(action(req.session, row.id, *args), detail=True))
    except service.CatalogError as err:
        raise _err(err) from err


@api.route("POST", "/releases", permission="catalog.admin", body=ReleaseIn, status=201, requirement="CAT-008")
def create_release(req: Req):
    exclude = tuple(tuple(x.split(":", 1)) for x in req.body.exclude if ":" in x)
    try:
        row = service.create_release(req.session, req.body.code, exclude=exclude)
    except service.CatalogError as err:
        raise _err(err) from err
    return ok(_release_view(row, detail=True), status=201)


@api.route("POST", "/releases/<release_id>/validate", permission="catalog.admin", requirement="CAT-008")
def validate_release(req: Req, release_id: str):
    row = _release(req, release_id)
    service.validate_release(req.session, row.id)
    return ok(_release_view(row, detail=True))


@api.route("POST", "/releases/<release_id>/preview-approval", permission="catalog.approve", requirement="CAT-007")
def approve_preview(req: Req, release_id: str):
    return _release_action(req, release_id, service.approve_preview)


@api.route("POST", "/releases/<release_id>/submit", permission="catalog.admin", requirement="CAT-008")
def submit_release(req: Req, release_id: str):
    return _release_action(req, release_id, service.submit_release)


@api.route(
    "POST", "/releases/<release_id>/approve", permission="catalog.approve", body=ApprovalIn, requirement="CAT-007"
)
def approve_release(req: Req, release_id: str):
    return _release_action(req, release_id, service.approve_release, req.body.approval_reference)


@api.route("POST", "/releases/<release_id>/reject", permission="catalog.approve", body=NoteIn, requirement="CAT-007")
def reject_release(req: Req, release_id: str):
    return _release_action(req, release_id, service.reject_release, req.body.note or "")


@api.route(
    "POST", "/releases/<release_id>/schedule", permission="catalog.admin", body=ScheduleIn, requirement="CAT-008"
)
def schedule_release(req: Req, release_id: str):
    return _release_action(req, release_id, service.schedule_release, req.body.at)


@api.route("POST", "/releases/<release_id>/activate", permission="catalog.admin", requirement="CAT-008")
def activate_release(req: Req, release_id: str):
    return _release_action(req, release_id, service.activate_release)


@api.route("POST", "/rollback", permission="catalog.admin", requirement="CAT-008")
def rollback(req: Req):
    try:
        return ok(_release_view(service.rollback(req.session), detail=True))
    except service.CatalogError as err:
        raise _err(err) from err


@api.route("GET", "/releases/<release_id>/customer-view", permission="catalog.view", write=False, requirement="CAT-001")
def release_customer_view(req: Req, release_id: str):
    from . import compile as catalog_compile

    row = _release(req, release_id)
    try:
        return ok(catalog_compile.customer_view(catalog_compile.load_release(req.session, row)))
    except Exception as err:  # noqa: BLE001 — an invalid release has no preview
        raise _err(err) from err


@api.route("POST", "/releases/<release_id>/preview-estimate", permission="catalog.view", body=ConfigIn,
           write=False, requirement="CAT-001")  # fmt: skip
def preview_estimate(req: Req, release_id: str):
    row = _release(req, release_id)
    return ok(configure.preview(req.session, row.id, req.body.configuration, public=not req.body.staff))


@api.route("GET", "/configurations/<reference>", permission="catalog.view", write=False, requirement="CAT-001")
def reopen_configuration(req: Req, reference: str):
    return ok(configure.reopen(req.session, reference))


# --- staff: media, import/export, analytics --------------------------------------------------------------------------
@api.route("POST", "/media", permission="catalog.media.edit", body=MediaIn, status=201, max_body=MEDIA_MAX_BODY,
           requirement="CAT-004")  # fmt: skip
def upload_media(req: Req):
    try:
        data = base64.b64decode(req.body.data_base64, validate=True)
    except (binascii.Error, ValueError) as err:
        raise ApiError(422, "CATALOG_REFUSED", "the upload is not valid base64") from err
    try:
        result = media.upload(req.session, data)
    except media.MediaError as err:
        raise _err(err) from err
    return ok({"objects": result.objects(), "scan_status": result.source.scan_status,
               "kind": result.source.media_kind}, status=201)  # fmt: skip


@api.route("GET", "/media", permission="catalog.view", write=False, requirement="CAT-001")
def list_media(req: Req):
    import sqlalchemy as sa

    rows = req.session.execute(
        sa.select(CatalogMediaObject).where(CatalogMediaObject.is_deleted.is_(False))
        .order_by(CatalogMediaObject.created_on.desc()).limit(500)
    ).scalars()  # fmt: skip
    return ok([{"sha256": r.object_sha256, "role": r.role, "kind": r.media_kind, "variant": r.variant,
                "mime": r.mime_type, "bytes": r.byte_size, "width": r.width, "height": r.height,
                "scan_status": r.scan_status, "created_on": r.created_on.isoformat()} for r in rows])  # fmt: skip


def _send(row: CatalogMediaObject, *, public: bool) -> Response:
    resp = Response(media.storage().get(row.storage_key), mimetype=row.mime_type)
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable" if public else "private, no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    resp.headers["Cross-Origin-Resource-Policy"] = "cross-origin" if public else "same-origin"
    return resp


@api.route("GET", "/media/<sha>", permission="catalog.view", write=False, requirement="CAT-001")
def staff_media(req: Req, sha: str):
    """Staff preview of a delivery variant (any scan status except INFECTED; sources are never served)."""
    import sqlalchemy as sa

    row = req.session.execute(
        sa.select(CatalogMediaObject).where(CatalogMediaObject.object_sha256 == sha)
    ).scalar_one_or_none()
    if row is None or row.role != "VARIANT" or row.scan_status == "INFECTED":
        raise ApiError(404, "NOT_FOUND", "Not found.")
    return _send(row, public=False)


@api.route("POST", "/import", permission="catalog.admin", body=ImportIn, max_body=8 * 1024 * 1024,
           requirement="CAT-008")  # fmt: skip
def import_records(req: Req):
    can_price = req.ctx.has("catalog.pricing.edit")
    try:
        rows = importexport.parse_rows(req.body.content, req.body.format)
        if req.body.apply:
            return ok(importexport.apply(req.session, rows, can_price=can_price))
        return ok(importexport.dry_run(req.session, rows, can_price=can_price))
    except (importexport.ImportError_, service.CatalogError) as err:
        raise _err(err) from err


@api.route("GET", "/export", permission="catalog.admin", write=False, query=ExportQuery, requirement="CAT-008")
def export_records(req: Req):
    try:
        body = importexport.export(req.session, release_id=req.query.release_id, include_pricing=_can_price(req),
                                   fmt=req.query.format)  # fmt: skip
    except importexport.ImportError_ as err:
        raise _err(err) from err
    resp = Response(body, mimetype="text/csv" if req.query.format == "csv" else "application/json")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@api.route("GET", "/analytics", permission="catalog.view", write=False, requirement="CAT-001")
def analytics(req: Req):
    return ok({"enabled": settings().catalog_analytics_enabled, "rows": configure.analytics(req.session)})


# --- public (RBX-008) ------------------------------------------------------------------------------------------------
def _enabled() -> None:
    if not configure.enabled():
        raise ApiError(404, "NOT_FOUND", "Not found.")


def _no_store(result):
    result.headers["Cache-Control"] = "no-store"
    return result


@public_api.route("GET", "/catalog", rbx="RBX-008", auth="public", write=False, requirement="CAT-009",
                  limits=[("120 per minute", estimator_routes._ip("catalog"))],
                  summary="The active estimator catalog (customer-safe; no rates)")  # fmt: skip
def public_catalog(req: Req):
    _enabled()
    result = ok(configure.public_catalog(req.session))
    result.headers["Cache-Control"] = "public, max-age=60"
    return result


def _estimate_prepare(req: Req):
    _enabled()
    if settings().estimate_turnstile_required:
        req.session.rollback()
        estimator_routes._captcha(req.body.turnstile_token, req.ip)
    return {"captcha": True}


@public_api.route(
    "POST", "/catalog/estimates", rbx="RBX-008", auth="public", body=PublicEstimateIn, status=201,
    max_body=PUBLIC_MAX_BODY, requirement="CAT-009", prepare=_estimate_prepare,
    limits=estimator_routes._limits("catalog-estimate", ("10 per minute", "60 per hour"), "120 per hour",
                                    "6 per minute", "600 per hour"),
    summary="Preliminary Budgetary Estimate from a catalog configuration (anonymous; not a quotation)",
)  # fmt: skip
def public_estimate(req: Req):
    data = configure.create_public(req.session, req.body.configuration, ip=req.ip, ua=req.user_agent,
                                   request_id=req.request_id)  # fmt: skip
    return _no_store(ok(data, status=201))


@public_api.route("GET", "/catalog/media/<sha>", rbx="RBX-008", auth="public", write=False, requirement="CAT-009",
                  limits=[("600 per minute", estimator_routes._ip("catalog-media"))],
                  summary="A delivery variant of the active catalog, by content hash")  # fmt: skip
def public_media(req: Req, sha: str):
    _enabled()
    row = media.deliverable(req.session, sha)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    return _send(row, public=True)


@public_api.route("POST", "/catalog/events", rbx="RBX-008", auth="public", body=PublicEventIn, status=204,
                  max_body=1024, requirement="CAT-010",
                  limits=[("60 per minute", estimator_routes._ip("catalog-events"))],
                  summary="Staging validation analytics: an event count (no person, no free text)")  # fmt: skip
def public_event(req: Req):
    _enabled()
    if not settings().catalog_analytics_enabled:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    configure.record_event(req.session, req.body.event, req.body.subject)
    return None
