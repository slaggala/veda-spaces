"""The attachment table (ATT, migration 0106; MTQ B1-SCOPE §2.8, blocker closure §6).

One row per uploaded photo, sketch or floor-plan image. Each row belongs to a lead (scope and retention) and to one
owning record through the polymorphic ``entity_type`` / ``entity_id`` pair (registered FK-less identifier, EXC-011).
Bytes never live in the database: the client uploads to the object store under a content-hash key, the server
verifies, scans and re-encodes, and keeps only the re-encoded variants. The row and its hashes outlive the bytes
(withdrawal, erasure and purge delete bytes and keep the evidence).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, in_check, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

ENTITY_TYPES = (
    "property",
    "property_space",
    "measurement_set",
    "space_wall",
    "space_opening",
    "space_electrical_point",
    "measurement_note",
)
CATEGORIES = ("SITE_PHOTO", "LASER_READING", "SKETCH", "FLOOR_PLAN", "OTHER")
UPLOAD_STATUSES = ("AWAITING_UPLOAD", "RECEIVED", "REJECTED")
SCAN_STATUSES = ("PENDING", "CLEAN", "INFECTED", "FAILED", "WITHDRAWN")
VARIANT_STATUSES = ("NONE", "READY", "FAILED")
RETENTION_STATES = ("ACTIVE", "WITHDRAWN", "ERASED", "PURGED")
VISIBILITIES = ("STANDARD", "INTERNAL")
BACKENDS = ("local", "s3")

MAX_OBJECT_BYTES = 15 * 1024 * 1024  # 15 MiB per object (closure §6.1)


class Attachment(AuditedBase):
    __tablename__ = "attachment"

    lead_id: Mapped[str] = mapped_column(GUID(), ForeignKey("lead.id", ondelete="RESTRICT"), nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(GUID(), nullable=False)  # FK-less, polymorphic (EXC-011)
    category_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    caption: Mapped[str | None] = mapped_column(sa.String(200))
    original_filename: Mapped[str | None] = mapped_column(sa.String(120))  # display only, sanitised; never a key
    declared_mime_type: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(sa.String(40))  # sniffed from the bytes on completion
    byte_size: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    width: Mapped[int | None] = mapped_column(sa.Integer)
    height: Mapped[int | None] = mapped_column(sa.Integer)
    storage_backend: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    upload_key: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    upload_status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default="AWAITING_UPLOAD", server_default="AWAITING_UPLOAD"
    )
    rejection_reason: Mapped[str | None] = mapped_column(sa.String(60))
    scan_status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="PENDING", server_default="PENDING")
    scanned_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    variant_status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="NONE", server_default="NONE")
    variants: Mapped[dict | None] = mapped_column(JSONType())  # {name: {sha256, width, height, byte_size}}, server-set
    uploaded_by: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    uploaded_on: Mapped[datetime | None] = mapped_column(UTCDateTime())  # bytes received and verified
    withdrawn_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    withdrawn_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    withdrawal_reason: Mapped[str | None] = mapped_column(sa.String(200))
    retention_state: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    bytes_deleted_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    visibility_code: Mapped[str] = mapped_column(
        sa.String(10), nullable=False, default="STANDARD", server_default="STANDARD"
    )
    client_ref: Mapped[str | None] = mapped_column(sa.String(64))

    __table_args__ = (
        in_check("attachment", "entity_type", ENTITY_TYPES),
        in_check("attachment", "category_code", CATEGORIES),
        in_check("attachment", "upload_status", UPLOAD_STATUSES),
        in_check("attachment", "scan_status", SCAN_STATUSES),
        in_check("attachment", "variant_status", VARIANT_STATUSES),
        in_check("attachment", "retention_state", RETENTION_STATES),
        in_check("attachment", "visibility_code", VISIBILITIES),
        in_check("attachment", "storage_backend", BACKENDS),
        CheckConstraint("length(sha256) = 64", name="ck_attachment__sha256_len64"),
        CheckConstraint(f"byte_size BETWEEN 1 AND {MAX_OBJECT_BYTES}", name="ck_attachment__byte_size"),
        CheckConstraint(
            "(width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)", name="ck_attachment__dimensions"
        ),
        CheckConstraint(
            "(withdrawn_on IS NULL AND withdrawn_by IS NULL) OR (withdrawn_on IS NOT NULL AND withdrawn_by IS NOT NULL)",
            name="ck_attachment__withdrawal_pair",
        ),
        CheckConstraint(
            "scan_status <> 'WITHDRAWN' OR retention_state <> 'ACTIVE'", name="ck_attachment__withdrawn_not_active"
        ),
        Index("ix_attachment__entity", "entity_type", "entity_id"),
        Index("ix_attachment__lead_id", "lead_id"),
        Index("ix_attachment__sha256", "sha256"),
        Index("ix_attachment__scan_status", "scan_status", "upload_status"),
        Index(
            "ux_attachment__lead_client_ref",
            "lead_id",
            "client_ref",
            unique=True,
            **where("client_ref IS NOT NULL AND is_deleted = 0", "client_ref IS NOT NULL AND is_deleted = false"),
        ),
    )
