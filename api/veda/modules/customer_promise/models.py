"""Customer Promise tables (migration 0207_customer_promise).

- ``customer_promise_pack``: one version of the Customer Promise Pack. Only a DRAFT is edited; a submitted, approved,
  published or superseded version never changes its content (a change is a new version). One version is PUBLISHED at a
  time and at most one version is open (DRAFT, IN_REVIEW or APPROVED). Rows are never deleted: a draft that is not
  wanted is DISCARDED.
- ``customer_promise_review``: a reviewer's decision on one section of one submission round, bound to the digest of
  the section as reviewed (append-only; an edit to the section makes the review stale, never rewrites it).
- ``customer_promise_event``: the pack's own append-only history (drafts, section saves, submissions, reviews,
  approvals, publication, supersession, previews).

No personal data beyond what the owner approves for publication: a contact is a Veda Spaces business channel
(``customer_pack.Contact``); no customer, lead or quotation data is stored here.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, in_check, live_where, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

from . import sections as SEC

STATUSES = ("DRAFT", "IN_REVIEW", "APPROVED", "PUBLISHED", "SUPERSEDED", "DISCARDED")
OPEN_STATUSES = ("DRAFT", "IN_REVIEW", "APPROVED")
ORIGINS = ("NEW", "REVISION", "ROLLBACK")
DECISIONS = ("APPROVED", "CHANGES_REQUESTED")
EVENTS = ("DRAFT_CREATED", "SECTION_UPDATED", "SUMMARY_UPDATED", "DRAFT_DISCARDED", "SUBMITTED", "SECTION_APPROVED",
          "CHANGES_REQUESTED", "RETURNED_TO_DRAFT", "APPROVED", "PUBLISHED", "SUPERSEDED", "PREVIEWED")  # fmt: skip


def _fk(target: str):
    return ForeignKey(target, ondelete="RESTRICT")


def _sha(table: str, col: str) -> CheckConstraint:
    return CheckConstraint(f"{col} IS NULL OR length({col}) = 64", name=f"ck_{table}__{col}_len")


class CustomerPromisePack(AuditedBase):
    """One version of the Customer Promise Pack. ``content`` is the authoring document (the customer pack's sections,
    entries possibly marked inactive); ``published_content`` is the customer content frozen at publication."""

    __tablename__ = "customer_promise_pack"

    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="DRAFT")
    origin: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="NEW")
    based_on_pack_id: Mapped[str | None] = mapped_column(GUID(), _fk("customer_promise_pack.id"))
    change_summary: Mapped[str | None] = mapped_column(sa.String(500))
    content: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    content_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # {section code: [user id, ...]}: everyone who saved the section in this version (append-only; four-eyes also reads
    # the event trail)
    contributors: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    review_round: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default="0")
    submitted_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    submitted_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    approved_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    approved_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    approved_sha256: Mapped[str | None] = mapped_column(sa.String(64))  # the content digest the approval was given to
    published_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    published_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    published_content: Mapped[dict | None] = mapped_column(JSONType())
    published_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    superseded_by_pack_id: Mapped[str | None] = mapped_column(GUID(), _fk("customer_promise_pack.id"))
    superseded_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    discarded_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("customer_promise_pack", "status", STATUSES),
        in_check("customer_promise_pack", "origin", ORIGINS),
        CheckConstraint("version_no >= 1", name="ck_customer_promise_pack__version_no"),
        CheckConstraint("review_round >= 0", name="ck_customer_promise_pack__review_round"),
        CheckConstraint("length(content_sha256) = 64", name="ck_customer_promise_pack__content_sha256_len"),
        _sha("customer_promise_pack", "approved_sha256"),
        _sha("customer_promise_pack", "published_sha256"),
        CheckConstraint(
            "status NOT IN ('PUBLISHED', 'SUPERSEDED') OR (published_on IS NOT NULL AND published_by IS NOT NULL "
            "AND published_content IS NOT NULL AND published_sha256 IS NOT NULL)",
            name="ck_customer_promise_pack__published_complete",
        ),
        CheckConstraint("status <> 'SUPERSEDED' OR superseded_on IS NOT NULL",
                        name="ck_customer_promise_pack__superseded_complete"),  # fmt: skip
        Index("ux_customer_promise_pack__version_no", "version_no", unique=True, **live_where()),
        Index("ux_customer_promise_pack__one_published", "status", unique=True,
              **where("status = 'PUBLISHED' AND is_deleted = 0", "status = 'PUBLISHED' AND is_deleted = false")),
        # at most one version in progress: concurrent "new draft" requests cannot both succeed (every open row has the
        # same is_deleted value, so the unique partial index admits one)
        Index("ux_customer_promise_pack__one_open", "is_deleted", unique=True,
              **where("status IN ('DRAFT', 'IN_REVIEW', 'APPROVED') AND is_deleted = 0",
                      "status IN ('DRAFT', 'IN_REVIEW', 'APPROVED') AND is_deleted = false")),
    )  # fmt: skip


class CustomerPromiseReview(AuditedBase):
    """A reviewer's decision (``created_by``) on one section in one submission round, bound to the section digest."""

    __tablename__ = "customer_promise_review"

    pack_id: Mapped[str] = mapped_column(GUID(), _fk("customer_promise_pack.id"), nullable=False)
    review_round: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    section_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    decision: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    section_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    comment: Mapped[str | None] = mapped_column(sa.String(1000))

    __table_args__ = (
        in_check("customer_promise_review", "section_code", SEC.CODES),
        in_check("customer_promise_review", "decision", DECISIONS),
        CheckConstraint("review_round >= 1", name="ck_customer_promise_review__review_round"),
        CheckConstraint("length(section_sha256) = 64", name="ck_customer_promise_review__section_sha256_len"),
        CheckConstraint(
            "decision <> 'CHANGES_REQUESTED' OR comment IS NOT NULL",
            name="ck_customer_promise_review__comment_required",
        ),  # fmt: skip
        Index("ix_customer_promise_review__pack", "pack_id", "review_round", "section_code", **live_where()),
    )


class CustomerPromiseEvent(AuditedBase):
    """What happened to a pack version and who did it (``created_by``). Details carry digests and codes, not copy."""

    __tablename__ = "customer_promise_event"

    pack_id: Mapped[str] = mapped_column(GUID(), _fk("customer_promise_pack.id"), nullable=False)
    event_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    section_code: Mapped[str | None] = mapped_column(sa.String(20))
    from_status: Mapped[str | None] = mapped_column(sa.String(12))
    to_status: Mapped[str | None] = mapped_column(sa.String(12))
    reason: Mapped[str | None] = mapped_column(sa.String(1000))
    detail: Mapped[dict | None] = mapped_column(JSONType())

    __table_args__ = (
        in_check("customer_promise_event", "event_code", EVENTS),
        in_check("customer_promise_event", "section_code", SEC.CODES, nullable=True),
        Index("ix_customer_promise_event__pack", "pack_id", "created_on", **live_where()),
    )
