"""0210_project_commercials: Project Commercials (decision log 42).

Nine tables (``veda.modules.commercials.models``): ``commercial_account`` (the commercial record of one accepted
quotation chain), ``commercial_baseline`` (the accepted base and each accepted variation, with digests; immutable:
database triggers refuse UPDATE and DELETE), ``payment_schedule`` and ``payment_instalment`` (schedule revisions; one
CURRENT per account), ``commercial_payment`` (payments recorded by staff, idempotent by client key),
``commercial_payment_reversal`` (the correction of a payment), ``commercial_receipt`` and ``commercial_invoice`` (frozen
documents with digests) and ``commercial_event`` (the immutable timeline). Number sequences ``INVOICE`` (``VS-I-``) and
``RECEIPT`` (``VS-R-``), yearly, padding 5. The six ``commercials.*`` staff permission codes and their default grants
(FOUNDER, SALES_MANAGER: ALL). No business content is seeded.

Expand-only and additive: no existing table, column or constraint changes. Inert while VEDA_PROJECT_COMMERCIALS_ENABLED
is off (the default everywhere; production refuses it).

Revision ID: 0210_project_commercials
Revises: 0209_customer_portal
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0210_project_commercials"
down_revision = "0209_customer_portal"
branch_labels = None
depends_on = None

CODES = (
    "commercials.view",
    "commercials.schedule.manage",
    "commercials.payment.record",
    "commercials.payment.reverse",
    "commercials.invoice.issue",
    "commercials.audit.view",
)
IMMUTABLE = ("commercial_baseline", "commercial_event")
SEQUENCES = (("INVOICE", "VS-I-"), ("RECEIPT", "VS-R-"))


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "commercial_account",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("quotation_number", sa.String(24), nullable=False),
        sa.Column("base_quotation_id", GUID(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("baseline_seq", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_account"),
        sa.ForeignKeyConstraint(
            ["base_quotation_id"],
            ["quotation.id"],
            name="fk_commercial_account__base_quotation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_commercial_account__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_commercial_account__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_commercial_account__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_commercial_account__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_commercial_account__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(base_quotation_id) = 32 AND base_quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(base_quotation_id, 13, 1) = '7' AND substr(base_quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_account__base_quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("baseline_seq >= 1", name="ck_commercial_account__baseline_seq"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_account__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("currency IN ('INR')", name="ck_commercial_account__currency"),
        sa.CheckConstraint("length(currency) <= 3", name="ck_commercial_account__currency_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_commercial_account__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_account__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_commercial_account__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_account__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_account__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(quotation_number) <= 24", name="ck_commercial_account__quotation_number_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_commercial_account__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_commercial_account__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_account__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_commercial_account__version_positive"),
    )
    op.create_index("ix_commercial_account__lead_id", "commercial_account", ["lead_id"])
    op.create_index(
        "ux_commercial_account__base_quotation",
        "commercial_account",
        ["base_quotation_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_commercial_account__property",
        "commercial_account",
        ["property_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_commercial_account__quotation_number",
        "commercial_account",
        ["quotation_number"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "commercial_baseline",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("previous_baseline_id", GUID(), nullable=True),
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("quotation_number", sa.String(24), nullable=False),
        sa.Column("variation_no", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("accepted_baseline_sha256", sa.String(64), nullable=False),
        sa.Column("accepted_total_minor", sa.BigInteger(), nullable=False),
        sa.Column("accepted_tax_minor", sa.BigInteger(), nullable=True),
        sa.Column("value_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=True),
        sa.Column("decided_on", UTCDateTime(), nullable=False),
        sa.Column("baseline_sha256", sa.String(64), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_baseline"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["commercial_account.id"], name="fk_commercial_baseline__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_commercial_baseline__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_commercial_baseline__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_commercial_baseline__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["previous_baseline_id"],
            ["commercial_baseline.id"],
            name="fk_commercial_baseline__previous_baseline_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotation.id"], name="fk_commercial_baseline__quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_commercial_baseline__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(accepted_baseline_sha256) = 64", name="ck_commercial_baseline__accepted_baseline_sha256_len"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_baseline__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(baseline_sha256) = 64", name="ck_commercial_baseline__baseline_sha256_len"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_baseline__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_commercial_baseline__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_baseline__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted = false AND version = 1", name="ck_commercial_baseline__immutable_contract"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_commercial_baseline__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("kind IN ('ORIGINAL', 'VARIATION')", name="ck_commercial_baseline__kind"),
        sa.CheckConstraint("length(kind) <= 10", name="ck_commercial_baseline__kind_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_baseline__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "sequence_no >= 1 AND (kind = 'ORIGINAL') = (sequence_no = 1) AND (sequence_no = 1) = (previous_baseline_id IS NULL) AND (kind = 'ORIGINAL') = (variation_no = 0)",
            name="ck_commercial_baseline__lineage",
        ),
        sa.CheckConstraint(
            "previous_baseline_id IS NULL OR (length(previous_baseline_id) = 32 AND previous_baseline_id NOT GLOB '*[^0-9a-f]*' AND substr(previous_baseline_id, 13, 1) = '7' AND substr(previous_baseline_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_commercial_baseline__previous_baseline_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_baseline__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_number) <= 24", name="ck_commercial_baseline__quotation_number_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(snapshot_sha256) = 64", name="ck_commercial_baseline__snapshot_sha256_len"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_commercial_baseline__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_commercial_baseline__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_baseline__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("value_minor >= 0", name="ck_commercial_baseline__value"),
        sa.CheckConstraint("version >= 1", name="ck_commercial_baseline__version_positive"),
    )
    op.create_index("ix_commercial_baseline__lead_id", "commercial_baseline", ["lead_id"])
    op.create_index("ix_commercial_baseline__previous", "commercial_baseline", ["previous_baseline_id"])
    op.create_index(
        "ux_commercial_baseline__quotation",
        "commercial_baseline",
        ["quotation_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_commercial_baseline__sequence",
        "commercial_baseline",
        ["account_id", "sequence_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "payment_schedule",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("basis_baseline_seq", sa.Integer(), nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("superseded_on", UTCDateTime(), nullable=True),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_payment_schedule"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["commercial_account.id"], name="fk_payment_schedule__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_payment_schedule__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_payment_schedule__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_payment_schedule__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_payment_schedule__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_schedule__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_schedule__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_payment_schedule__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_schedule__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_payment_schedule__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_schedule__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "revision_no >= 1 AND basis_baseline_seq >= 1 AND total_minor >= 0", name="ck_payment_schedule__numbers"
        ),
        sa.CheckConstraint("source = 'QUOTATION_MILESTONES' OR reason IS NOT NULL", name="ck_payment_schedule__reason"),
        sa.CheckConstraint("length(reason) <= 1000", name="ck_payment_schedule__reason_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_payment_schedule__soft_delete_consistent",
        ),
        sa.CheckConstraint("source IN ('QUOTATION_MILESTONES', 'REVISION')", name="ck_payment_schedule__source"),
        sa.CheckConstraint("length(source) <= 20", name="ck_payment_schedule__source_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("status IN ('CURRENT', 'SUPERSEDED')", name="ck_payment_schedule__status"),
        sa.CheckConstraint("length(status) <= 10", name="ck_payment_schedule__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(status = 'SUPERSEDED') = (superseded_on IS NOT NULL)", name="ck_payment_schedule__superseded"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_payment_schedule__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_schedule__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_payment_schedule__version_positive"),
    )
    op.create_index("ix_payment_schedule__lead_id", "payment_schedule", ["lead_id"])
    op.create_index(
        "ux_payment_schedule__current",
        "payment_schedule",
        ["account_id"],
        unique=True,
        sqlite_where=sa.text("status = 'CURRENT' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'CURRENT' AND is_deleted = false"),
    )
    op.create_index(
        "ux_payment_schedule__revision",
        "payment_schedule",
        ["account_id", "revision_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "payment_instalment",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("schedule_id", GUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("when_text", sa.String(200), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=True),
        sa.Column("share_bp", sa.Integer(), nullable=True),
        sa.Column("requested_on", UTCDateTime(), nullable=True),
        sa.Column("requested_by", GUID(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("carried_from_id", GUID(), nullable=True),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_payment_instalment"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["commercial_account.id"], name="fk_payment_instalment__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["carried_from_id"],
            ["payment_instalment.id"],
            name="fk_payment_instalment__carried_from_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_payment_instalment__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_payment_instalment__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_payment_instalment__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["app_user.id"], name="fk_payment_instalment__requested_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"], ["payment_schedule.id"], name="fk_payment_instalment__schedule_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_payment_instalment__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_instalment__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("position >= 1 AND amount_minor > 0", name="ck_payment_instalment__amount"),
        sa.CheckConstraint(
            "carried_from_id IS NULL OR (length(carried_from_id) = 32 AND carried_from_id NOT GLOB '*[^0-9a-f]*' AND substr(carried_from_id, 13, 1) = '7' AND substr(carried_from_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_payment_instalment__carried_from_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_instalment__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_payment_instalment__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_instalment__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_payment_instalment__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 120", name="ck_payment_instalment__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_instalment__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(requested_on IS NULL) = (requested_by IS NULL) AND (due_on IS NULL OR requested_on IS NOT NULL)",
            name="ck_payment_instalment__request",
        ),
        sa.CheckConstraint(
            "requested_by IS NULL OR (length(requested_by) = 32 AND requested_by NOT GLOB '*[^0-9a-f]*' AND substr(requested_by, 13, 1) = '7' AND substr(requested_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_payment_instalment__requested_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(schedule_id) = 32 AND schedule_id NOT GLOB '*[^0-9a-f]*' AND substr(schedule_id, 13, 1) = '7' AND substr(schedule_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_instalment__schedule_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("share_bp IS NULL OR share_bp BETWEEN 1 AND 10000", name="ck_payment_instalment__share"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_payment_instalment__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "tax_minor IS NULL OR (tax_minor >= 0 AND tax_minor <= amount_minor)", name="ck_payment_instalment__tax"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_payment_instalment__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_payment_instalment__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_payment_instalment__version_positive"),
        sa.CheckConstraint("length(when_text) <= 200", name="ck_payment_instalment__when_text_len").ddl_if(
            dialect="sqlite"
        ),
    )
    op.create_index("ix_payment_instalment__account_id", "payment_instalment", ["account_id"])
    op.create_index("ix_payment_instalment__carried_from", "payment_instalment", ["carried_from_id"])
    op.create_index("ix_payment_instalment__lead_id", "payment_instalment", ["lead_id"])
    op.create_index(
        "ux_payment_instalment__position",
        "payment_instalment",
        ["schedule_id", "position"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "commercial_payment",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("method_code", sa.String(16), nullable=False),
        sa.Column("external_reference", sa.String(100), nullable=True),
        sa.Column("reference_norm", sa.String(100), nullable=True),
        sa.Column("customer_note", sa.String(300), nullable=True),
        sa.Column("internal_note", sa.String(1000), nullable=True),
        sa.Column("client_key_sha256", sa.String(64), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("record_sha256", sa.String(64), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_payment"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["commercial_account.id"], name="fk_commercial_payment__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_commercial_payment__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_commercial_payment__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_commercial_payment__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_commercial_payment__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("amount_minor > 0", name="ck_commercial_payment__amount"),
        sa.CheckConstraint("length(client_key_sha256) = 64", name="ck_commercial_payment__client_key_sha256_len"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("currency IN ('INR')", name="ck_commercial_payment__currency"),
        sa.CheckConstraint("length(currency) <= 3", name="ck_commercial_payment__currency_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(customer_note) <= 300", name="ck_commercial_payment__customer_note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_commercial_payment__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(external_reference) <= 100", name="ck_commercial_payment__external_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(internal_note) <= 1000", name="ck_commercial_payment__internal_note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_commercial_payment__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "method_code IN ('BANK_TRANSFER', 'UPI', 'CHEQUE', 'CASH', 'OTHER')",
            name="ck_commercial_payment__method_code",
        ),
        sa.CheckConstraint("length(method_code) <= 16", name="ck_commercial_payment__method_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(record_sha256) = 64", name="ck_commercial_payment__record_sha256_len"),
        sa.CheckConstraint(
            "(external_reference IS NULL) = (reference_norm IS NULL)", name="ck_commercial_payment__reference"
        ),
        sa.CheckConstraint("length(reference_norm) <= 100", name="ck_commercial_payment__reference_norm_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(request_sha256) = 64", name="ck_commercial_payment__request_sha256_len"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_commercial_payment__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_commercial_payment__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_commercial_payment__version_positive"),
    )
    op.create_index("ix_commercial_payment__account", "commercial_payment", ["account_id", "received_on"])
    op.create_index("ix_commercial_payment__lead_id", "commercial_payment", ["lead_id"])
    op.create_index(
        "ix_commercial_payment__reference", "commercial_payment", ["account_id", "method_code", "reference_norm"]
    )
    op.create_index(
        "ux_commercial_payment__client_key",
        "commercial_payment",
        ["account_id", "client_key_sha256"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "commercial_payment_reversal",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("payment_id", GUID(), nullable=False),
        sa.Column("reason_code", sa.String(20), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_payment_reversal"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["commercial_account.id"],
            name="fk_commercial_payment_reversal__account_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_commercial_payment_reversal__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_commercial_payment_reversal__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_commercial_payment_reversal__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["commercial_payment.id"],
            name="fk_commercial_payment_reversal__payment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_commercial_payment_reversal__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment_reversal__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment_reversal__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_commercial_payment_reversal__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment_reversal__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_commercial_payment_reversal__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment_reversal__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(note) <= 500", name="ck_commercial_payment_reversal__note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(payment_id) = 32 AND payment_id NOT GLOB '*[^0-9a-f]*' AND substr(payment_id, 13, 1) = '7' AND substr(payment_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment_reversal__payment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "reason_code IN ('RECORDED_IN_ERROR', 'DUPLICATE', 'PAYMENT_RETURNED', 'OTHER')",
            name="ck_commercial_payment_reversal__reason_code",
        ),
        sa.CheckConstraint("length(reason_code) <= 20", name="ck_commercial_payment_reversal__reason_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_commercial_payment_reversal__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_commercial_payment_reversal__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_payment_reversal__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_commercial_payment_reversal__version_positive"),
    )
    op.create_index("ix_commercial_payment_reversal__account_id", "commercial_payment_reversal", ["account_id"])
    op.create_index("ix_commercial_payment_reversal__lead_id", "commercial_payment_reversal", ["lead_id"])
    op.create_index(
        "ux_commercial_payment_reversal__payment",
        "commercial_payment_reversal",
        ["payment_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "commercial_receipt",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("payment_id", GUID(), nullable=False),
        sa.Column("receipt_number", sa.String(24), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("issued_on", UTCDateTime(), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("snapshot", JSONType(), nullable=True),
        sa.Column("snapshot_sha256", sa.String(64), nullable=True),
        sa.Column("document_html", sa.Text(), nullable=True),
        sa.Column("document_sha256", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_receipt"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["commercial_account.id"], name="fk_commercial_receipt__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_commercial_receipt__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_commercial_receipt__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_commercial_receipt__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["payment_id"], ["commercial_payment.id"], name="fk_commercial_receipt__payment_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_commercial_receipt__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_receipt__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("amount_minor > 0", name="ck_commercial_receipt__amount"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_receipt__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_commercial_receipt__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "document_sha256 IS NULL OR length(document_sha256) = 64", name="ck_commercial_receipt__document_sha256_len"
        ),
        sa.CheckConstraint(
            "snapshot_sha256 IS NOT NULL AND document_sha256 IS NOT NULL", name="ck_commercial_receipt__frozen"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_receipt__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_commercial_receipt__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_receipt__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(payment_id) = 32 AND payment_id NOT GLOB '*[^0-9a-f]*' AND substr(payment_id, 13, 1) = '7' AND substr(payment_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_receipt__payment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(receipt_number) <= 24", name="ck_commercial_receipt__receipt_number_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "snapshot IS NULL OR json_valid(snapshot)", name="ck_commercial_receipt__snapshot_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64", name="ck_commercial_receipt__snapshot_sha256_len"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_commercial_receipt__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_commercial_receipt__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_receipt__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_commercial_receipt__version_positive"),
    )
    op.create_index("ix_commercial_receipt__account_id", "commercial_receipt", ["account_id"])
    op.create_index("ix_commercial_receipt__lead_id", "commercial_receipt", ["lead_id"])
    op.create_index(
        "ux_commercial_receipt__number",
        "commercial_receipt",
        ["receipt_number"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_commercial_receipt__payment",
        "commercial_receipt",
        ["payment_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "commercial_invoice",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("schedule_id", GUID(), nullable=False),
        sa.Column("instalment_id", GUID(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("invoice_number", sa.String(24), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("customer_note", sa.String(500), nullable=True),
        sa.Column("issued_on", UTCDateTime(), nullable=True),
        sa.Column("issued_by", GUID(), nullable=True),
        sa.Column("cancelled_on", UTCDateTime(), nullable=True),
        sa.Column("cancelled_by", GUID(), nullable=True),
        sa.Column("cancel_reason", sa.String(500), nullable=True),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("snapshot", JSONType(), nullable=True),
        sa.Column("snapshot_sha256", sa.String(64), nullable=True),
        sa.Column("document_html", sa.Text(), nullable=True),
        sa.Column("document_sha256", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_invoice"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["commercial_account.id"], name="fk_commercial_invoice__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by"], ["app_user.id"], name="fk_commercial_invoice__cancelled_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_commercial_invoice__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_commercial_invoice__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["instalment_id"],
            ["payment_instalment.id"],
            name="fk_commercial_invoice__instalment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["issued_by"], ["app_user.id"], name="fk_commercial_invoice__issued_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_commercial_invoice__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["schedule_id"], ["payment_schedule.id"], name="fk_commercial_invoice__schedule_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_commercial_invoice__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_invoice__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "amount_minor > 0 AND (tax_minor IS NULL OR (tax_minor >= 0 AND tax_minor <= amount_minor))",
            name="ck_commercial_invoice__amount",
        ),
        sa.CheckConstraint("length(cancel_reason) <= 500", name="ck_commercial_invoice__cancel_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(status = 'CANCELLED') = (cancelled_on IS NOT NULL AND cancelled_by IS NOT NULL AND cancel_reason IS NOT NULL)",
            name="ck_commercial_invoice__cancelled",
        ),
        sa.CheckConstraint(
            "cancelled_by IS NULL OR (length(cancelled_by) = 32 AND cancelled_by NOT GLOB '*[^0-9a-f]*' AND substr(cancelled_by, 13, 1) = '7' AND substr(cancelled_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_commercial_invoice__cancelled_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_invoice__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(customer_note) <= 500", name="ck_commercial_invoice__customer_note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_commercial_invoice__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "document_sha256 IS NULL OR length(document_sha256) = 64", name="ck_commercial_invoice__document_sha256_len"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_invoice__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(instalment_id) = 32 AND instalment_id NOT GLOB '*[^0-9a-f]*' AND substr(instalment_id, 13, 1) = '7' AND substr(instalment_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_invoice__instalment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(invoice_number) <= 24", name="ck_commercial_invoice__invoice_number_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_commercial_invoice__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "issued_by IS NULL OR (length(issued_by) = 32 AND issued_by NOT GLOB '*[^0-9a-f]*' AND substr(issued_by, 13, 1) = '7' AND substr(issued_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_commercial_invoice__issued_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(status = 'DRAFT' AND invoice_number IS NULL AND issued_on IS NULL AND snapshot_sha256 IS NULL) OR (status IN ('ISSUED', 'CANCELLED') AND invoice_number IS NOT NULL AND issued_on IS NOT NULL AND issued_by IS NOT NULL AND snapshot_sha256 IS NOT NULL AND document_sha256 IS NOT NULL)",
            name="ck_commercial_invoice__issued_frozen",
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_invoice__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(schedule_id) = 32 AND schedule_id NOT GLOB '*[^0-9a-f]*' AND substr(schedule_id, 13, 1) = '7' AND substr(schedule_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_invoice__schedule_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "snapshot IS NULL OR json_valid(snapshot)", name="ck_commercial_invoice__snapshot_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64", name="ck_commercial_invoice__snapshot_sha256_len"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_commercial_invoice__soft_delete_consistent",
        ),
        sa.CheckConstraint("status IN ('DRAFT', 'ISSUED', 'CANCELLED')", name="ck_commercial_invoice__status"),
        sa.CheckConstraint("length(status) <= 10", name="ck_commercial_invoice__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_commercial_invoice__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_invoice__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_commercial_invoice__version_positive"),
    )
    op.create_index("ix_commercial_invoice__account_id", "commercial_invoice", ["account_id"])
    op.create_index("ix_commercial_invoice__lead_id", "commercial_invoice", ["lead_id"])
    op.create_index("ix_commercial_invoice__schedule_id", "commercial_invoice", ["schedule_id"])
    op.create_index(
        "ux_commercial_invoice__live_instalment",
        "commercial_invoice",
        ["instalment_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('DRAFT', 'ISSUED') AND is_deleted = 0"),
        postgresql_where=sa.text("status IN ('DRAFT', 'ISSUED') AND is_deleted = false"),
    )
    op.create_index(
        "ux_commercial_invoice__number",
        "commercial_invoice",
        ["invoice_number"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "commercial_event",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("event_code", sa.String(24), nullable=False),
        sa.Column("detail", JSONType(), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_event"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["commercial_account.id"], name="fk_commercial_event__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_commercial_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_commercial_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_commercial_event__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_commercial_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_event__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_commercial_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("detail IS NULL OR json_valid(detail)", name="ck_commercial_event__detail_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "event_code IN ('ACCOUNT_OPENED', 'BASELINE_RECORDED', 'SCHEDULE_CREATED', 'SCHEDULE_REVISED', 'PAYMENT_REQUESTED', 'PAYMENT_RECORDED', 'RECEIPT_ISSUED', 'PAYMENT_REVERSED', 'INVOICE_DRAFTED', 'INVOICE_DISCARDED', 'INVOICE_ISSUED', 'INVOICE_CANCELLED', 'DOCUMENT_REDACTED')",
            name="ck_commercial_event__event_code",
        ),
        sa.CheckConstraint("length(event_code) <= 24", name="ck_commercial_event__event_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted = false AND version = 1", name="ck_commercial_event__immutable_contract"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_commercial_event__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_event__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_commercial_event__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_commercial_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_commercial_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_commercial_event__version_positive"),
    )
    op.create_index("ix_commercial_event__account", "commercial_event", ["account_id", "created_on"])
    op.create_index("ix_commercial_event__lead_id", "commercial_event", ["lead_id"])
    # --- end generated DDL ---
    bind = op.get_bind()
    for table in IMMUTABLE:
        ms.create_immutability_guards(bind, table)
    for key, prefix in SEQUENCES:
        ms.seed_sequence(bind, key, prefix, padding=5)
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
