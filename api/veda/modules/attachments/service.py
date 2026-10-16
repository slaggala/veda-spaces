"""Attachment service (ATT; MTQ blocker closure §6, B1-SCOPE §2.8).

Lifecycle of one attachment:

1. **Create** (``attachment.create``): the client declares the owning record, category, size, SHA-256 and MIME type.
   The server checks scope, the frozen limits and idempotency (``client_ref``), records the row (``AWAITING_UPLOAD``,
   scan ``PENDING``) and returns upload instructions for the content-hash key ``upload/<sha256>``. The API never
   proxies bytes in staging or production (pre-signed POST, exact length, exact type); the local backend
   (development and tests only) takes the bytes through the API.
2. **Complete**: the server reads the object back, checks the length and the hash, sniffs the type (images only),
   decodes it safely, scans it, re-encodes it without metadata into WebP variants (``att/<sha256>``) and deletes the
   uploaded bytes once they are CLEAN. Repeating a completion returns the current state (idempotent).
3. **Deliver**: only a CLEAN, ACTIVE attachment with ready variants is ever served (fail closed); the original upload is
   never served.
4. **Withdraw** / **erase** / **purge**: bytes are deleted, the row and its hashes stay (evidence), unless another live
   attachment holds the same bytes.
"""

from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db, metrics
from veda.kernel import media as km
from veda.kernel.errors import ApiError, field_error, not_found
from veda.modules.crm.leads.models import Lead
from veda.modules.crm.leads.repository import own_predicate

from . import registry
from .models import MAX_OBJECT_BYTES, Attachment

UPLOAD_PREFIX = "upload/"
OBJECT_PREFIX = "att/"
PREFIXES = (UPLOAD_PREFIX, OBJECT_PREFIX)
IMAGE_MIME = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
# Server variants (closure §6.2): the catalogue widths reused as-is, plus the re-encoded full-size source that replaces
# the uploaded bytes ("the re-encoded source is retained, the uploaded bytes are not").
VARIANT_WIDTHS = {"thumb": 320, "mobile": 768, "desktop": 1600, "full": km.MAX_IMAGE_SIDE}
WALL_SOFT_LIMIT, WALL_HARD_LIMIT = 6, 12
SPACE_SOFT_LIMIT = 40
SET_OBJECT_LIMIT, SET_BYTE_LIMIT = 800, 1024 * 1024 * 1024
QUARANTINE_DAYS = 30
ABANDONED_UPLOAD_HOURS = 24
# MC-2: after a withdrawal or an erasure, a pre-signed POST issued before it may still land (at most the upload TTL,
# 900 s). The purge sweep deletes such late objects for this long after the invalidation; the bucket lifecycle
# expires anything left under upload/ after 2 days as the last resort.
INVALIDATED_SWEEP_HOURS = 24
LIVE_STATES = ("ACTIVE",)
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


# --- storage -----------------------------------------------------------------------------------------------------------
def storage() -> km.ObjectStore:
    cfg = settings()
    if cfg.attachment_backend == "s3":
        return km.S3Storage(
            cfg.attachment_bucket or "", cfg.attachment_kms_key_arn, prefixes=PREFIXES, region=cfg.aws_region
        )
    return km.LocalStorage(cfg.attachment_dir, prefixes=PREFIXES)


def _fetch(key: str) -> bytes | None:
    try:
        return storage().get(key)
    except FileNotFoundError:
        return None
    except Exception as err:  # noqa: BLE001 - S3: a missing object is "not uploaded yet", anything else is an error
        code = str(getattr(err, "response", {}).get("Error", {}).get("Code", ""))
        if code in ("NoSuchKey", "404", "NotFound"):
            return None
        raise


def _delete(key: str) -> None:
    try:
        storage().delete(key)
    except FileNotFoundError:
        pass


# --- scope -------------------------------------------------------------------------------------------------------------
def _lead_ids_for(actor_id: str):
    return sa.select(Lead.id).where(sa.or_(own_predicate(actor_id), *registry.lead_access_predicates(actor_id)))


def scope_condition(ctx, permission: str):
    scope = ctx.scope(permission)
    if scope == "ALL":
        return sa.true()
    if scope == "OWN":
        actor = ctx.user.id
        return sa.or_(Attachment.uploaded_by == actor, Attachment.lead_id.in_(_lead_ids_for(actor)))
    return sa.false()


def require_lead_scope(s: Session, ctx, lead_id: str, permission: str) -> Lead:
    """The lead must exist, be live, not erased, and be within the actor's scope for ``permission``."""
    scope = ctx.scope(permission)
    if scope is None:
        from veda.platform.auth.request_auth import deny

        deny(ctx, permission)
    lead = s.get(Lead, lead_id)
    if lead is None or lead.is_deleted:
        raise not_found()
    if scope == "OWN":
        visible = s.execute(_lead_ids_for(ctx.user.id).where(Lead.id == lead_id)).first() is not None
        if not visible:
            raise not_found()
    if lead.anonymized_on is not None:
        raise ApiError(409, "INVALID_STATE", "This lead was erased; nothing can be attached to it.")
    return lead


def get_visible(s: Session, ctx, attachment_id: str, permission: str = "attachment.read") -> Attachment:
    att = s.execute(
        sa.select(Attachment).where(Attachment.id == attachment_id, scope_condition(ctx, permission))
    ).scalar_one_or_none()
    if att is None:
        raise not_found()
    return att


# --- helpers -----------------------------------------------------------------------------------------------------------
def safe_filename(raw: str | None) -> str | None:
    """A display name only: path parts, control characters and leading dots removed, NFKC-normalised, 120 chars."""
    if not raw:
        return None
    name = unicodedata.normalize("NFKC", raw).replace("\\", "/").split("/")[-1]
    name = _CONTROL.sub("", name).strip().lstrip(".").strip()
    return name[:120] or None


def _resolve(s: Session, entity_type: str, entity_id: str) -> registry.EntityContext:
    binding = registry.binding_for(entity_type)
    if binding is None:
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "Attachments are not accepted on this record type.",
            errors=[field_error("entity_type", "UNSUPPORTED", "No attachments for this record type.")],
        )
    found = binding.resolve(s, entity_id)
    if found is None:
        raise not_found()
    return found


def _locked(s: Session, entity_type: str, entity_id: str, target: registry.EntityContext) -> registry.EntityContext:
    """B1-PE-06: take the container's lock (MTQ: the property lock a set's submit takes) and re-resolve, so whether the
    record still accepts uploads, who may withdraw and the container limits are decided on the committed state."""
    binding = registry.binding_for(entity_type)
    if target.container_id and binding is not None and binding.container_lock is not None:
        binding.container_lock(s, target.container_id)
        return _resolve(s, entity_type, entity_id)
    return target


def _live(stmt):
    return stmt.where(
        Attachment.retention_state.in_(LIVE_STATES),
        Attachment.upload_status != "REJECTED",
        Attachment.is_deleted == sa.false(),
    )


def _count(s: Session, *conds) -> int:
    return int(s.execute(_live(sa.select(sa.func.count(Attachment.id)).where(*conds))).scalar() or 0)


def entity_usage(s: Session, entity_type: str, entity_id: str) -> int:
    return _count(s, Attachment.entity_type == entity_type, Attachment.entity_id == entity_id)


def _check_limits(s: Session, entity_type: str, target: registry.EntityContext, byte_size: int) -> list[dict]:
    warnings_: list[dict] = []
    if target.wall_id:
        on_wall = entity_usage(s, "space_wall", target.wall_id)
        if on_wall >= WALL_HARD_LIMIT:
            raise ApiError(
                422,
                "ATTACHMENT_LIMIT_EXCEEDED",
                f"A wall holds at most {WALL_HARD_LIMIT} photos.",
                extra={"limit": "WALL", "max": WALL_HARD_LIMIT},
            )
        if on_wall >= WALL_SOFT_LIMIT:
            warnings_.append({"code": "WALL_SOFT_LIMIT", "count": on_wall + 1, "soft_limit": WALL_SOFT_LIMIT})
    binding = registry.binding_for(entity_type)
    if target.container_id and binding is not None and binding.container_usage is not None:
        objects, size = binding.container_usage(s, target.container_id)
        if objects + 1 > SET_OBJECT_LIMIT or size + byte_size > SET_BYTE_LIMIT:
            raise ApiError(
                422,
                "ATTACHMENT_LIMIT_EXCEEDED",
                f"A measurement set holds at most {SET_OBJECT_LIMIT} attachments and 1 GiB.",
                extra={"limit": "MEASUREMENT_SET", "max_objects": SET_OBJECT_LIMIT, "max_bytes": SET_BYTE_LIMIT},
            )
    if target.space_id and target.extra.get("space_usage") is not None:
        in_space = int(target.extra["space_usage"](s))
        if in_space >= SPACE_SOFT_LIMIT:
            warnings_.append({"code": "SPACE_SOFT_LIMIT", "count": in_space + 1, "soft_limit": SPACE_SOFT_LIMIT})
    return warnings_


# --- uploadability (MC-2) ----------------------------------------------------------------------------------------------
def require_uploadable(s: Session, att: Attachment) -> None:
    """Bytes are accepted (instructions, local receipt, completion) only while every one of these still holds; each
    is checked again at completion, so a change after the instructions were issued refuses the completion."""
    if att.is_deleted:
        raise not_found()
    if att.retention_state != "ACTIVE":
        raise ApiError(409, "ATTACHMENT_NOT_ACTIVE", "This attachment was withdrawn or erased; it takes no bytes.",
                       extra={"retention_state": att.retention_state})  # fmt: skip
    lead = s.execute(
        sa.select(Lead).where(Lead.id == att.lead_id).execution_options(include_deleted=True)
    ).scalar_one_or_none()
    if lead is None or lead.is_deleted or lead.anonymized_on is not None:
        raise ApiError(409, "LEAD_ERASED", "The lead this attachment belongs to was erased.")
    binding = registry.binding_for(att.entity_type)
    if binding is None or binding.resolve(s, att.entity_id) is None:
        raise ApiError(409, "ATTACHMENT_OWNER_GONE", "The record this attachment belongs to no longer exists.")
    if att.storage_backend != settings().attachment_backend:
        raise ApiError(409, "STORAGE_CHANGED", "This upload was issued for another storage backend; upload again.")
    if att.upload_status != "AWAITING_UPLOAD":
        raise ApiError(409, "UPLOAD_STATE_STALE", "This attachment is no longer awaiting its bytes.",
                       extra={"upload_status": att.upload_status})  # fmt: skip
    if att.created_on < db.tx_time(s) - timedelta(hours=ABANDONED_UPLOAD_HOURS):
        raise ApiError(409, "UPLOAD_EXPIRED", "This upload was abandoned; declare the photo again.")


def _discard_upload(s: Session, att: Attachment) -> None:
    """Storage only: delete bytes that arrived for an attachment that may no longer take them, unless a live
    attachment still waits for or holds the same content-hash key. Survives the refusal's rollback."""
    if not _awaiting_same_bytes(s, att) and not _shared(s, att):
        _delete(att.upload_key)


def upload_instructions(att: Attachment) -> dict[str, Any]:
    cfg = settings()
    if att.upload_status != "AWAITING_UPLOAD" or att.retention_state != "ACTIVE" or att.is_deleted:
        return {"required": False}
    if att.storage_backend == "s3":
        store = storage()
        assert isinstance(store, km.S3Storage)
        post = store.presign_post(
            att.upload_key, att.declared_mime_type, att.byte_size, cfg.attachment_upload_ttl_seconds
        )
        return {"required": True, "method": "POST", **post, "then": f"/api/v1/attachments/{att.id}/complete"}
    return {
        "required": True,
        "method": "PUT",
        "url": f"/api/v1/attachments/{att.id}/content",
        "encoding": "base64-json",
        "then": f"/api/v1/attachments/{att.id}/complete",
    }


def is_available(att: Attachment) -> bool:
    """Fail closed: only CLEAN, ACTIVE, received attachments with ready variants are ever delivered."""
    return (
        att.scan_status == "CLEAN"
        and att.retention_state == "ACTIVE"
        and att.upload_status == "RECEIVED"
        and att.variant_status == "READY"
        and not att.is_deleted
    )


def present(att: Attachment) -> dict[str, Any]:
    variants = att.variants or {}
    return {
        "id": att.id,
        "version": att.version,
        "lead_id": att.lead_id,
        "entity_type": att.entity_type,
        "entity_id": att.entity_id,
        "category_code": att.category_code,
        "caption": att.caption,
        "filename": att.original_filename,
        "mime_type": att.mime_type,
        "byte_size": att.byte_size,
        "sha256": att.sha256,
        "width": att.width,
        "height": att.height,
        "upload_status": att.upload_status,
        "rejection_reason": att.rejection_reason,
        "scan_status": att.scan_status,
        "variant_status": att.variant_status,
        "variants": {k: {"width": v["width"], "height": v["height"]} for k, v in sorted(variants.items())},
        "retention_state": att.retention_state,
        "visibility_code": att.visibility_code,
        "client_ref": att.client_ref,
        "uploaded_by": att.uploaded_by,
        "uploaded_on": clock.to_rfc3339(att.uploaded_on) if att.uploaded_on else None,
        "withdrawn_on": clock.to_rfc3339(att.withdrawn_on) if att.withdrawn_on else None,
        "created_on": clock.to_rfc3339(att.created_on),
        "available": is_available(att),
    }


# --- create ------------------------------------------------------------------------------------------------------------
def create(s: Session, ctx, body) -> tuple[Attachment, bool, list[dict]]:
    """Returns (attachment, created, warnings). A repeated ``client_ref`` with the same content returns the original."""
    target = _resolve(s, body.entity_type, body.entity_id)
    require_lead_scope(s, ctx, target.lead_id, "attachment.create")
    if body.client_ref:
        existing = s.execute(
            sa.select(Attachment).where(Attachment.lead_id == target.lead_id, Attachment.client_ref == body.client_ref)
        ).scalar_one_or_none()
        if existing is not None:
            if (existing.sha256, existing.entity_type, existing.entity_id) != (
                body.sha256,
                body.entity_type,
                body.entity_id,
            ):
                raise ApiError(409, "CLIENT_REF_REUSED", "This client_ref was used for a different attachment.")
            return existing, False, []
    target = _locked(s, body.entity_type, body.entity_id, target)
    if not target.writable:
        raise ApiError(409, "ENTITY_FROZEN", "This record no longer accepts attachments.")
    warnings_ = _check_limits(s, body.entity_type, target, body.byte_size)
    cfg = settings()
    att = Attachment(
        lead_id=target.lead_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        category_code=body.category_code,
        caption=body.caption,
        original_filename=safe_filename(body.filename),
        declared_mime_type=body.mime_type,
        byte_size=body.byte_size,
        sha256=body.sha256,
        storage_backend=cfg.attachment_backend,
        upload_key=km.content_key(UPLOAD_PREFIX, body.sha256),
        uploaded_by=ctx.user.id,
        visibility_code="INTERNAL" if body.category_code == "FLOOR_PLAN" else body.visibility_code,
        client_ref=body.client_ref,
    )
    s.add(att)
    s.flush()
    metrics.emit("AttachmentCreated", 1)
    return att, True, warnings_


def create_for_portal(
    s: Session, *, entity_type: str, entity_id: str, body, client_ref: str
) -> tuple[Attachment, bool]:
    """A customer's photo through a portal route (WSV: ``service_request`` only). The calling route has authorised the
    portal session and the record; no permission is granted to any principal for this, and the staff attachment
    routes still refuse the public principal. ``uploaded_by`` is the principal the request runs as (the public one,
    as every portal write); the account is recorded by the caller on its own link row in the same transaction.
    A repeated ``client_ref`` with the same content returns the original."""
    from veda.kernel.context import require_actor

    if entity_type != "service_request":
        raise ApiError(422, "VALIDATION_FAILED", "Customers attach photos to service requests only.")
    target = _resolve(s, entity_type, entity_id)
    existing = s.execute(
        sa.select(Attachment).where(Attachment.lead_id == target.lead_id, Attachment.client_ref == client_ref)
    ).scalar_one_or_none()
    if existing is not None:
        if (existing.sha256, existing.entity_type, existing.entity_id) != (body.sha256, entity_type, entity_id):
            raise ApiError(409, "CLIENT_REF_REUSED", "This request key was used for a different photo.")
        return existing, False
    if not target.writable:
        raise ApiError(409, "ENTITY_FROZEN", "This request no longer accepts photos.")
    cfg = settings()
    att = Attachment(
        lead_id=target.lead_id,
        entity_type=entity_type,
        entity_id=entity_id,
        category_code="SITE_PHOTO",
        caption=None,
        original_filename=safe_filename(body.filename),
        declared_mime_type=body.mime_type,
        byte_size=body.byte_size,
        sha256=body.sha256,
        storage_backend=cfg.attachment_backend,
        upload_key=km.content_key(UPLOAD_PREFIX, body.sha256),
        uploaded_by=require_actor().actor_id,
        visibility_code="STANDARD",
        client_ref=client_ref,
    )
    s.add(att)
    s.flush()
    metrics.emit("AttachmentCreated", 1)
    return att, True


# --- bytes (local backend only) -------------------------------------------------------------------------------------
def receive_local(s: Session, att: Attachment, data_b64: str) -> None:
    if att.storage_backend != "local" or settings().attachment_backend != "local":
        raise ApiError(409, "DIRECT_UPLOAD_REQUIRED", "Upload to the pre-signed URL; the API does not take bytes here.")
    if att.upload_status != "AWAITING_UPLOAD":
        raise ApiError(409, "INVALID_STATE", "This attachment already has its bytes.")
    require_uploadable(s, att)
    try:
        data = base64.b64decode(data_b64, validate=True)
    except (binascii.Error, ValueError) as err:
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "The content is not valid base64.",
            errors=[field_error("data_base64", "INVALID", "Expected base64.")],
        ) from err
    if len(data) > MAX_OBJECT_BYTES:
        raise ApiError(422, "ATTACHMENT_TOO_LARGE", "An attachment is at most 15 MiB.")
    storage().put(att.upload_key, data, att.declared_mime_type)


# --- complete ----------------------------------------------------------------------------------------------------------
def _reject(att: Attachment, reason: str) -> None:
    att.upload_status = "REJECTED"
    att.rejection_reason = reason
    metrics.emit("AttachmentRejected", 1, dimensions={"Reason": reason})


def _shared(s: Session, att: Attachment, *, other_leads_only: bool = False) -> bool:
    """Another live attachment holds the same bytes (content-hash keys are shared)."""
    stmt = sa.select(Attachment.id).where(
        Attachment.sha256 == att.sha256,
        Attachment.id != att.id,
        Attachment.retention_state == "ACTIVE",
        Attachment.upload_status != "REJECTED",
    )
    if other_leads_only:
        stmt = stmt.where(Attachment.lead_id != att.lead_id)
    return s.execute(stmt.limit(1)).first() is not None


def _store_variants(att: Attachment, data: bytes) -> None:
    if att.retention_state != "ACTIVE":
        raise km.MediaError("variants are made only for an active attachment")
    variants, width, height = km.image_variants(data, VARIANT_WIDTHS)
    store = storage()
    made = {}
    for name, blob, w, h in variants:
        sha = km.sha256_hex(blob)
        store.put(km.content_key(OBJECT_PREFIX, sha), blob, km.VARIANT_MIME)
        made[name] = {"sha256": sha, "width": w, "height": h, "byte_size": len(blob)}
    att.variants = made
    att.width, att.height = width, height
    att.variant_status = "READY"


def complete(s: Session, att: Attachment) -> Attachment:
    if att.retention_state == "ACTIVE" and att.upload_status != "AWAITING_UPLOAD":
        return att  # idempotent: a repeated completion of a live attachment returns the current state
    try:
        require_uploadable(s, att)
    except ApiError:
        # MC-2: refused before anything is decoded, scanned or derived; bytes that already arrived are deleted now
        # (and again by the purge sweep, should a pre-signed POST land later). Every retry is refused the same way.
        _discard_upload(s, att)
        raise
    data = _fetch(att.upload_key)
    if data is None:
        raise ApiError(409, "UPLOAD_NOT_RECEIVED", "The upload has not arrived yet; upload, then complete.")
    now = db.tx_time(s)
    if len(data) != att.byte_size or km.sha256_hex(data) != att.sha256:
        _reject(att, "CHECKSUM_MISMATCH")
        _delete(att.upload_key)  # bytes that do not match their key are never kept
        return att
    try:
        kind = km.sniff_image(data)
    except km.MediaError:
        _reject(att, "UNSUPPORTED_TYPE")
        _delete(att.upload_key)
        return att
    try:
        km.image_variants(data, {"probe": km.MIN_IMAGE_SIDE})  # decode safely before the scanner sees it
    except km.MediaError:
        _reject(att, "IMAGE_REFUSED")
        _delete(att.upload_key)
        return att
    att.mime_type = km.IMAGE_FORMATS[kind]
    att.uploaded_on = now
    att.upload_status = "RECEIVED"
    _apply_scan(s, att, data)
    return att


def _scan(data: bytes) -> str:
    cfg = settings()
    mode = cfg.attachment_scanner
    return km.scan_outcome(
        data, mode=mode, address=cfg.attachment_clamd_address if mode == "clamd" else "", env=cfg.env
    )


def _apply_scan(s: Session, att: Attachment, data: bytes) -> None:
    if att.retention_state != "ACTIVE" or att.is_deleted:
        return  # MC-2: a withdrawn or erased attachment never becomes CLEAN and never gets variants
    status = _scan(data)
    att.scan_status = status
    if status in ("CLEAN", "INFECTED"):
        att.scanned_on = db.tx_time(s)
    if status == "INFECTED":
        # Quarantine: the uploaded bytes stay for investigation (30 days, then purged); nothing is derived or served.
        metrics.emit("AttachmentInfected", 1)
        _release_variants(s, att)
        att.variant_status = "NONE"
        return
    if att.variant_status != "READY":
        try:
            _store_variants(att, data)
        except km.MediaError:
            att.variant_status = "FAILED"
            _reject(att, "IMAGE_REFUSED")
            _delete(att.upload_key)
            return
    if status == "CLEAN" and not _awaiting_same_bytes(s, att):
        _delete(att.upload_key)  # the re-encoded variants replace the upload


def _awaiting_same_bytes(s: Session, att: Attachment) -> bool:
    return (
        s.execute(
            sa.select(Attachment.id)
            .where(
                Attachment.upload_key == att.upload_key,
                Attachment.id != att.id,
                sa.or_(
                    Attachment.upload_status == "AWAITING_UPLOAD",
                    sa.and_(Attachment.upload_status == "RECEIVED", Attachment.scan_status.in_(("PENDING", "FAILED"))),
                ),
            )
            .limit(1)
        ).first()
        is not None
    )


def rescan_pending(s: Session) -> int:
    """Scheduler: scan received attachments still PENDING or FAILED (their uploads are kept until then)."""
    rows = (
        s.execute(
            sa.select(Attachment).where(
                Attachment.upload_status == "RECEIVED",
                Attachment.scan_status.in_(("PENDING", "FAILED")),
                Attachment.retention_state == "ACTIVE",
            )
        )
        .scalars()
        .all()
    )
    n = 0
    for att in rows:
        data = _fetch(att.upload_key)
        if data is None or km.sha256_hex(data) != att.sha256:
            metrics.emit("AttachmentObjectMissing", 1)  # never skipped silently: the alarm sees it
            continue
        _apply_scan(s, att, data)
        n += 1
    return n


# --- deliver -----------------------------------------------------------------------------------------------------------
def variant_bytes(att: Attachment, variant: str) -> bytes:
    if not is_available(att):
        raise ApiError(409, "ATTACHMENT_NOT_AVAILABLE", "This attachment is not available.",
                       extra={"scan_status": att.scan_status, "retention_state": att.retention_state})  # fmt: skip
    meta = (att.variants or {}).get(variant)
    if meta is None:
        raise not_found()
    data = _fetch(km.content_key(OBJECT_PREFIX, meta["sha256"]))
    if data is None or km.sha256_hex(data) != meta["sha256"]:
        metrics.emit("AttachmentObjectMissing", 1)
        raise ApiError(409, "ATTACHMENT_NOT_AVAILABLE", "This attachment is not available.")
    return data


# --- withdraw, erase, purge ------------------------------------------------------------------------------------------
def _release_variants(s: Session, att: Attachment) -> None:
    if _shared(s, att):
        return
    for meta in (att.variants or {}).values():
        _delete(km.content_key(OBJECT_PREFIX, meta["sha256"]))


def _release_all(s: Session, att: Attachment, *, other_leads_only: bool = False) -> None:
    if _shared(s, att, other_leads_only=other_leads_only):
        return
    for meta in (att.variants or {}).values():
        _delete(km.content_key(OBJECT_PREFIX, meta["sha256"]))
    _delete(att.upload_key)
    att.bytes_deleted_on = db.tx_time(s)


def withdraw(s: Session, ctx, att: Attachment, reason: str | None) -> Attachment:
    if att.retention_state != "ACTIVE":
        raise ApiError(409, "INVALID_STATE", "This attachment was already withdrawn or erased.")
    target = _resolve(s, att.entity_type, att.entity_id)
    target = _locked(s, att.entity_type, att.entity_id, target)
    scope = ctx.scope("attachment.delete")
    if target.withdraw_rule == "VERIFIER_WITH_REASON":
        if not ctx.has(target.extra.get("verify_permission", "measurement.verify")):
            raise ApiError(403, "PERMISSION_DENIED", "Only a verifier may withdraw an attachment on a submitted set.")
        if not reason:
            raise ApiError(
                422,
                "REASON_REQUIRED",
                "Say why the attachment is withdrawn.",
                errors=[field_error("reason", "REQUIRED", "A reason is required.")],
            )
    elif scope != "ALL" and att.uploaded_by != ctx.user.id:
        raise ApiError(403, "PERMISSION_DENIED", "Only the uploader may withdraw this attachment.")
    _release_all(s, att)
    now = db.tx_time(s)
    _invalidate_upload(att)
    att.retention_state = "WITHDRAWN"
    att.scan_status = "WITHDRAWN"
    att.withdrawn_on, att.withdrawn_by, att.withdrawal_reason = now, ctx.user.id, reason
    if att.bytes_deleted_on is None:
        att.bytes_deleted_on = now
    metrics.emit("AttachmentWithdrawn", 1)
    return att


def _invalidate_upload(att: Attachment) -> None:
    """An upload that never completed can no longer complete (MC-2)."""
    if att.upload_status == "AWAITING_UPLOAD":
        att.upload_status = "REJECTED"
        att.rejection_reason = "INVALIDATED"


def erase_for_lead(s: Session, lead: Lead) -> int:
    """Lead erasure and lead retention (07 §8.2; closure §6.4): delete the bytes of every attachment on the lead, keep
    the rows and hashes, and remove the personal text (display filename, caption). Deleted, not anonymised."""
    erasure = s.info.setdefault("erasure_entities", set())
    rows = (
        s.execute(sa.select(Attachment).where(Attachment.lead_id == lead.id).execution_options(include_deleted=True))
        .scalars()
        .all()
    )
    for att in rows:
        erasure.add(att.id)
        if att.retention_state in ("ACTIVE", "WITHDRAWN") or att.bytes_deleted_on is None:
            _release_all(s, att, other_leads_only=True)
        _invalidate_upload(att)
        att.retention_state = "ERASED"
        if att.scan_status == "PENDING":
            att.scan_status = "WITHDRAWN"
        att.original_filename = None
        att.caption = None
        if att.bytes_deleted_on is None:
            att.bytes_deleted_on = db.tx_time(s)
    return len(rows)


def audit_ids_for_lead(s: Session, lead_id: str) -> list[str]:
    """Attachment ids of a lead, for the erasure-audit rewrite (their audit parent is the lead already)."""
    return list(
        s.execute(
            sa.select(Attachment.id).where(Attachment.lead_id == lead_id).execution_options(include_deleted=True)
        ).scalars()
    )


def purge(s: Session) -> dict[str, int]:
    """Scheduler: quarantined (INFECTED) uploads after 30 days, abandoned uploads after 24 hours."""
    now = db.tx_time(s)
    infected = (
        s.execute(
            sa.select(Attachment).where(
                Attachment.scan_status == "INFECTED",
                Attachment.retention_state == "ACTIVE",
                Attachment.scanned_on < now - timedelta(days=QUARANTINE_DAYS),
            )
        )
        .scalars()
        .all()
    )
    for att in infected:
        _delete(att.upload_key)
        att.retention_state = "PURGED"
        att.bytes_deleted_on = now
    abandoned = (
        s.execute(
            sa.select(Attachment).where(
                Attachment.upload_status == "AWAITING_UPLOAD",
                Attachment.created_on < now - timedelta(hours=ABANDONED_UPLOAD_HOURS),
            )
        )
        .scalars()
        .all()
    )
    for att in abandoned:
        _reject(att, "ABANDONED")
        if not _awaiting_same_bytes(s, att) and not _shared(s, att):
            _delete(att.upload_key)
        att.bytes_deleted_on = now
    # MC-2: withdrawn and erased attachments recently invalidated, whatever their upload state: delete any object a
    # late pre-signed POST may have written, and any variant or upload left behind (idempotent; missing is fine).
    invalidated = (
        s.execute(
            sa.select(Attachment)
            .where(
                Attachment.retention_state.in_(("WITHDRAWN", "ERASED")),
                sa.or_(
                    Attachment.bytes_deleted_on.is_(None),
                    Attachment.bytes_deleted_on >= now - timedelta(hours=INVALIDATED_SWEEP_HOURS),
                ),
            )
            .execution_options(include_deleted=True)
        )
        .scalars()
        .all()
    )
    for att in invalidated:
        _invalidate_upload(att)
        if not _shared(s, att, other_leads_only=att.retention_state == "ERASED"):
            for meta in (att.variants or {}).values():
                _delete(km.content_key(OBJECT_PREFIX, meta["sha256"]))
        if not _awaiting_same_bytes(s, att) and not _shared(s, att):
            _delete(att.upload_key)
        if att.bytes_deleted_on is None:
            att.bytes_deleted_on = now
    return {"infected_purged": len(infected), "abandoned": len(abandoned), "invalidated_swept": len(invalidated)}


def validate_sha256(value: str) -> str:
    if not _SHA_RE.match(value or ""):
        raise ValueError("expected 64 lowercase hex characters")
    return value


def sha256_b64(hex_digest: str) -> str:
    return base64.b64encode(bytes.fromhex(hex_digest)).decode()
