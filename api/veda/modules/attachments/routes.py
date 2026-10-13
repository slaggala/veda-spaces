"""Attachment endpoints (ATT; MTQ B1). Staff only, bearer-authenticated, scoped by the attachment's lead.

Every route answers 404, before authentication, unless VEDA_MTQ_SITE_ENABLED is on (off by default; production
refuses it). There is no public route.
"""

from __future__ import annotations

import sqlalchemy as sa
from flask import Response

from veda.config import settings
from veda.kernel.errors import ApiError
from veda.kernel.http import Api, Req, ok, problem_response
from veda.kernel.ratelimit import ip_key

from . import schemas as S
from . import service
from .models import Attachment

api = Api("attachments", "/api/v1", tags=("attachments",))
CONTENT_MAX_BODY = 21 * 1024 * 1024  # 15 MiB base64-encoded, local backend only
UPLOAD_LIMITS = [("600 per minute", ip_key)]


GATED_PREFIXES = ("/api/v1/attachments",)


@api.blueprint.before_app_request
def _site_enabled():
    """MC-3: app-wide, before routing errors are raised, so every method on every gated path (including methods no
    route accepts, which would otherwise be 405) answers 404 while VEDA_MTQ_SITE_ENABLED is off."""
    from flask import request

    path = request.path.rstrip("/")
    if not settings().mtq_site_enabled and any(path == p or path.startswith(p + "/") for p in GATED_PREFIXES):
        return problem_response(ApiError(404, "NOT_FOUND", "Not found."))
    return None


@api.route(
    "POST",
    "/attachments",
    permission="attachment.create",
    body=S.AttachmentCreateIn,
    status=201,
    idempotent_create=True,
    limits=UPLOAD_LIMITS,
    requirement="ATT-002",
    summary="Register an attachment and get its upload instructions",
)
def create_attachment(req: Req):
    att, created, warnings = service.create(req.session, req.ctx, req.body)
    req.session.flush()
    meta = {"warnings": warnings} if warnings else None
    return ok(
        {**service.present(att), "upload": service.upload_instructions(att)},
        status=201 if created else 200,
        meta=meta,
    )


@api.route(
    "GET",
    "/attachments",
    permission="attachment.read",
    query=S.AttachmentListQuery,
    write=False,
    requirement="ATT-001",
    summary="List the attachments of one record",
)
def list_attachments(req: Req):
    q = req.query
    stmt = sa.select(Attachment).where(
        Attachment.entity_type == q.entity_type,
        Attachment.entity_id == q.entity_id,
        service.scope_condition(req.ctx, "attachment.read"),
    )
    if not q.include_withdrawn:
        stmt = stmt.where(Attachment.retention_state == "ACTIVE", Attachment.upload_status != "REJECTED")
    rows = req.session.execute(stmt.order_by(Attachment.created_on, Attachment.id).limit(200)).scalars().all()
    return ok([service.present(a) for a in rows])


@api.route(
    "GET",
    "/attachments/<attachment_id>",
    permission="attachment.read",
    write=False,
    requirement="ATT-001",
    summary="One attachment's record and state",
)
def get_attachment(req: Req, attachment_id: str):
    att = service.get_visible(req.session, req.ctx, attachment_id)
    return ok({**service.present(att), "upload": service.upload_instructions(att)})


@api.route(
    "PUT",
    "/attachments/<attachment_id>/content",
    permission="attachment.create",
    body=S.AttachmentContentIn,
    max_body=CONTENT_MAX_BODY,
    limits=UPLOAD_LIMITS,
    requirement="ATT-002",
    summary="Local backend only: send the bytes (base64); staging and production use the pre-signed upload",
)
def put_content(req: Req, attachment_id: str):
    att = service.get_visible(req.session, req.ctx, attachment_id, "attachment.create")
    service.receive_local(req.session, att, req.body.data_base64)
    return ok({**service.present(att), "upload": {"required": False, "received": True}})


@api.route(
    "POST",
    "/attachments/<attachment_id>/complete",
    permission="attachment.create",
    limits=UPLOAD_LIMITS,
    requirement="ATT-002",
    summary="Verify, scan and re-encode an uploaded attachment (idempotent)",
)
def complete_attachment(req: Req, attachment_id: str):
    att = service.get_visible(req.session, req.ctx, attachment_id, "attachment.create")
    service.complete(req.session, att)
    req.session.flush()
    return ok(service.present(att))


@api.route(
    "GET",
    "/attachments/<attachment_id>/content",
    permission="attachment.read",
    query=S.AttachmentContentQuery,
    write=False,
    requirement="ATT-001",
    summary="Download a re-encoded variant (CLEAN and ACTIVE only; fail closed)",
)
def get_content(req: Req, attachment_id: str):
    att = service.get_visible(req.session, req.ctx, attachment_id)
    data = service.variant_bytes(att, req.query.variant)
    resp = Response(data, status=200, mimetype="image/webp")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["Content-Disposition"] = f'inline; filename="{att.id}-{req.query.variant}.webp"'
    resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return resp


@api.route(
    "POST",
    "/attachments/<attachment_id>/withdraw",
    permission="attachment.delete",
    body=S.AttachmentWithdrawIn,
    if_match=True,
    requirement="ATT-003",
    summary="Withdraw an attachment: delete its bytes, keep its record and hashes",
)
def withdraw_attachment(req: Req, attachment_id: str):
    att = service.get_visible(req.session, req.ctx, attachment_id, "attachment.delete")
    req.require_version(att.version)
    service.withdraw(req.session, req.ctx, att, req.body.reason if req.body else None)
    req.session.flush()
    return ok(service.present(att))
