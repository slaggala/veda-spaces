"""``audit_log``: the platform-wide entity change journal (03 §7, 07)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, in_check, sqlite_check, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

AUDIT_ACTIONS = ("CREATE", "UPDATE", "DELETE", "RESTORE", "HARD_DELETE", "EXPORT", "ANONYMIZE")
PERFORMED_VIA = ("API", "PUBLIC_FORM", "SYSTEM_JOB", "MIGRATION", "CLI")


class AuditLog(AuditedBase):
    __tablename__ = "audit_log"

    entity_type: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    entity_id: Mapped[str] = mapped_column(GUID(), nullable=False)  # registered FK-less (EXC-011)
    action: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONType())
    new_value: Mapped[dict | None] = mapped_column(JSONType())
    changed_fields: Mapped[list | None] = mapped_column(JSONType())
    performed_by: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    performed_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    performed_via: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    parent_entity_type: Mapped[str | None] = mapped_column(sa.String(60))
    parent_entity_id: Mapped[str | None] = mapped_column(GUID())  # registered FK-less (EXC-011)
    transaction_id: Mapped[str] = mapped_column(GUID(), nullable=False)  # registered FK-less group id (EXC-011)
    request_id: Mapped[str | None] = mapped_column(sa.String(64))
    session_id: Mapped[str | None] = mapped_column(GUID())  # non-FK correlation (EXC-009)
    ip_address: Mapped[str | None] = mapped_column(sa.String(45))
    user_agent: Mapped[str | None] = mapped_column(sa.String(500))
    reason: Mapped[str | None] = mapped_column(sa.String(500))
    payload_schema: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=1, server_default=sa.text("1"))

    __table_args__ = (
        in_check("audit_log", "action", AUDIT_ACTIONS),
        in_check("audit_log", "performed_via", PERFORMED_VIA),
        CheckConstraint("(parent_entity_type IS NULL) = (parent_entity_id IS NULL)", name="ck_audit_log__parent_pair"),
        CheckConstraint(
            "performed_by = created_by AND performed_on = created_on", name="ck_audit_log__performed_matches_contract"
        ),
        CheckConstraint("is_deleted = false AND version = 1", name="ck_audit_log__immutable_contract"),
        sqlite_check(
            "length(entity_type) BETWEEN 2 AND 60 AND entity_type NOT GLOB '*[^a-z0-9_]*' "
            "AND substr(entity_type, 1, 1) BETWEEN 'a' AND 'z'",
            "ck_audit_log__entity_type_pattern",
        ),
        CheckConstraint("entity_type ~ '^[a-z][a-z0-9_]{1,59}$'", name="ck_audit_log__entity_type_pattern").ddl_if(
            dialect="postgresql"
        ),
        Index("ix_audit_log__entity", "entity_type", "entity_id", sa.text("performed_on DESC")),
        Index(
            "ix_audit_log__parent",
            "parent_entity_type",
            "parent_entity_id",
            sa.text("performed_on DESC"),
            **where("parent_entity_id IS NOT NULL"),
        ),
        Index("ix_audit_log__performed_by", "performed_by", sa.text("performed_on DESC")),
        Index("ix_audit_log__performed_on", sa.text("performed_on DESC")),
        Index("ix_audit_log__transaction_id", "transaction_id"),
    )
