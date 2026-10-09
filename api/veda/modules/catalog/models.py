"""Catalog-driven estimator tables (ADR-013).

A catalog record is one version of one typed document (`kind`, `record_key`, `version`). Versions are immutable once
submitted: an edit to reviewed, approved or active content is a new DRAFT version. Only a catalog release, an
immutable manifest of exact record versions, makes anything customer-visible, and only while it is ACTIVE. No table
here holds personal data; media objects are stored under their content hash, never under an uploaded filename.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, in_check, live_where, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

KINDS = (
    "property_type",
    "home_config",
    "room_template",
    "product_family",
    "product",
    "extra",
    "material",
    "hardware",
    "media",
    "package",
    "pricing",
    "rule",
    "copy",
)
RECORD_STATUSES = ("DRAFT", "IN_REVIEW", "APPROVED", "SCHEDULED", "ACTIVE", "RETIRED", "ARCHIVED")
RELEASE_STATUSES = ("DRAFT", "IN_REVIEW", "APPROVED", "SCHEDULED", "ACTIVE", "RETIRED")
EVENT_TYPES = (
    "RECORD_CREATED",
    "RECORD_UPDATED",
    "RECORD_SUBMITTED",
    "RECORD_APPROVED",
    "RECORD_REJECTED",
    "RECORD_ARCHIVED",
    "RELEASE_CREATED",
    "RELEASE_VALIDATED",
    "RELEASE_PREVIEW_APPROVED",
    "RELEASE_SUBMITTED",
    "RELEASE_APPROVED",
    "RELEASE_REJECTED",
    "RELEASE_SCHEDULED",
    "RELEASE_ACTIVATED",
    "RELEASE_RETIRED",
    "RELEASE_ROLLED_BACK",
    "CONFIGURATION_PURGED",
    "MEDIA_UPLOADED",
    "MEDIA_SCANNED",
    "IMPORT_APPLIED",
)
MEDIA_KINDS = ("IMAGE", "VIDEO", "GLB", "GLTF", "USDZ")
MEDIA_ROLES = ("SOURCE", "VARIANT")
SCAN_STATUSES = ("PENDING_SCAN", "CLEAN", "INFECTED")
ANALYTICS_EVENTS = (
    "room_selected",
    "room_deselected",
    "extra_viewed",
    "extra_selected",
    "image_opened",
    "gallery_viewed",
    "preview_3d_started",
    "preview_3d_succeeded",
    "preview_3d_fallback",
    "estimate_reached",
    "estimate_refined",
    "quotation_requested",
)


class CatalogRecord(AuditedBase):
    """One version of one catalog document. `updated_by` is the last editor; `submitted_by` sent it for review."""

    __tablename__ = "catalog_record"

    kind: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    record_key: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    record_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="DRAFT", server_default="DRAFT")
    title: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    document: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    document_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    submitted_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    submitted_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reviewed_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    reviewed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    review_note: Mapped[str | None] = mapped_column(sa.String(300))
    # Everyone who created, edited or submitted this version (append-only; four-eyes also reads the event trail).
    contributors: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)

    __table_args__ = (
        in_check("catalog_record", "kind", KINDS),
        in_check("catalog_record", "status", RECORD_STATUSES),
        CheckConstraint("record_version >= 1", name="ck_catalog_record__record_version"),
        CheckConstraint("length(document_sha256) = 64", name="ck_catalog_record__sha_len"),
        Index(
            "ux_catalog_record__kind_key_version", "kind", "record_key", "record_version", unique=True, **live_where()
        ),
        Index(
            "ux_catalog_record__one_active",
            "kind",
            "record_key",
            unique=True,
            **where("status = 'ACTIVE' AND is_deleted = 0", "status = 'ACTIVE' AND is_deleted = false"),
        ),
        Index("ix_catalog_record__status", "status", "kind", **live_where()),
    )


class CatalogRelease(AuditedBase):
    """An immutable manifest of exact record versions; the only thing that makes catalog content customer-visible."""

    __tablename__ = "catalog_release"

    release_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="DRAFT", server_default="DRAFT")
    manifest: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    compiled: Mapped[dict | None] = mapped_column(JSONType())  # digests of the compiled artefacts
    validation: Mapped[dict | None] = mapped_column(JSONType())  # the last validation report
    rate_card_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("estimator_rate_card.id", ondelete="RESTRICT"))
    previous_release_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("catalog_release.id", ondelete="RESTRICT")
    )
    rollback_of_id: Mapped[str | None] = mapped_column(  # a rollback release restores this release's manifest
        GUID(), ForeignKey("catalog_release.id", ondelete="RESTRICT")
    )
    release_owner: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    preview_approved_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    preview_approved_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    submitted_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    approved_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    approved_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    approval_reference: Mapped[str | None] = mapped_column(sa.String(200))
    scheduled_for: Mapped[datetime | None] = mapped_column(UTCDateTime())
    activated_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    deactivated_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("catalog_release", "status", RELEASE_STATUSES),
        CheckConstraint("length(manifest_sha256) = 64", name="ck_catalog_release__sha_len"),
        Index("ux_catalog_release__code", "release_code", unique=True, **live_where()),
        Index(
            "ux_catalog_release__one_active",
            "status",
            unique=True,
            **where("status = 'ACTIVE' AND is_deleted = 0", "status = 'ACTIVE' AND is_deleted = false"),
        ),
    )


class CatalogEvent(AuditedBase):
    """What happened in the catalog and who did it (`created_by`). Details never hold rates."""

    __tablename__ = "catalog_event"

    event_type: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    record_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("catalog_record.id", ondelete="RESTRICT"))
    release_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("catalog_release.id", ondelete="RESTRICT"))
    detail: Mapped[dict | None] = mapped_column(JSONType())

    __table_args__ = (
        in_check("catalog_event", "event_type", EVENT_TYPES),
        Index("ix_catalog_event__record", "record_id", "created_on", **live_where()),
        Index("ix_catalog_event__release", "release_id", "created_on", **live_where()),
    )


class CatalogMediaObject(AuditedBase):
    """A stored media file: an uploaded source (private, never served publicly) or a generated delivery variant."""

    __tablename__ = "catalog_media_object"

    object_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    role: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    media_kind: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    variant: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # source, thumb, mobile, desktop, web
    mime_type: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    byte_size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(sa.Integer)
    height: Mapped[int | None] = mapped_column(sa.Integer)
    storage_key: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    scan_status: Mapped[str] = mapped_column(sa.String(15), nullable=False)
    scanned_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    source_object_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("catalog_media_object.id", ondelete="RESTRICT")
    )

    __table_args__ = (
        in_check("catalog_media_object", "role", MEDIA_ROLES),
        in_check("catalog_media_object", "media_kind", MEDIA_KINDS),
        in_check("catalog_media_object", "scan_status", SCAN_STATUSES),
        CheckConstraint("byte_size > 0", name="ck_catalog_media_object__size"),
        CheckConstraint("length(object_sha256) = 64", name="ck_catalog_media_object__sha_len"),
        Index("ux_catalog_media_object__sha", "object_sha256", unique=True, **live_where()),
    )


class CatalogConfiguration(AuditedBase):
    """The exact configuration a customer chose, frozen with the release and record versions it used."""

    __tablename__ = "catalog_configuration"

    configuration_reference: Mapped[str] = mapped_column(sa.String(9), nullable=False)
    release_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("catalog_release.id", ondelete="RESTRICT"), nullable=False
    )
    manifest_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    versions: Mapped[dict] = mapped_column(JSONType(), nullable=False)  # {kind: {key: version}} actually used
    selections: Mapped[dict] = mapped_column(JSONType(), nullable=False)  # what the customer chose
    resolved_request: Mapped[dict] = mapped_column(JSONType(), nullable=False)  # the engine input (pricing inputs)
    estimate_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("budget_estimate.id", ondelete="RESTRICT"))

    __table_args__ = (
        CheckConstraint("length(manifest_sha256) = 64", name="ck_catalog_configuration__sha_len"),
        Index("ux_catalog_configuration__reference", "configuration_reference", unique=True, **live_where()),
        Index("ix_catalog_configuration__estimate", "estimate_id", **live_where()),
    )


class CatalogAnalyticsDaily(AuditedBase):
    """Privacy-conscious staging analytics: a count per day, event and catalog subject. No person, no free text."""

    __tablename__ = "catalog_analytics_daily"

    day: Mapped[str] = mapped_column(sa.String(10), nullable=False)  # YYYY-MM-DD
    event: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    subject: Mapped[str] = mapped_column(sa.String(100), nullable=False)  # a catalog key, or "-"
    release_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    count: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    __table_args__ = (
        in_check("catalog_analytics_daily", "event", ANALYTICS_EVENTS),
        CheckConstraint("count >= 0", name="ck_catalog_analytics_daily__count"),
        Index(
            "ux_catalog_analytics_daily__key", "day", "event", "subject", "release_code", unique=True, **live_where()
        ),
    )
