"""0215_sales_acquisition: Sales & Customer Acquisition Experience (SCA, decision log 48).

One new table (``veda.modules.sales.models``): ``acquisition_event_daily``, a count per day, event and acquisition
channel of the site's anonymous funnel beacons (no person, no page, no address). Three ``sales.*`` codes:
``sales.pipeline.view`` (FOUNDER, ADMIN, SALES_MANAGER at ALL; SALES at OWN), ``sales.funnel.view`` and
``sales.demo.view``, as ``veda.modules.sales.permissions`` lists them. One lookup value, ``LOST_REASON`` /
``NOT_PROVIDED``, so a lost lead never needs an invented reason.

Expand-only: nothing is removed or narrowed. Inert while VEDA_SALES_EXPERIENCE_ENABLED is off (the default
everywhere; production refuses it). The sales pipeline and funnel read the lead, estimator, MTQ, proposal and project
tables as they are: no column is added to any of them.

Revision ID: 0215_sales_acquisition
Revises: 0214_warranty_service
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0215_sales_acquisition"
down_revision = "0214_warranty_service"
branch_labels = None
depends_on = None

CODES = ("sales.pipeline.view", "sales.funnel.view", "sales.demo.view")
LOOKUPS = (
    (
        "LOST_REASON",
        "Lost reason",
        "Why a lead was lost",
        (("NOT_PROVIDED", "Not provided", None),),
    ),
)


def upgrade() -> None:
    bind = op.get_bind()
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "acquisition_event_daily",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("day", sa.String(10), nullable=False),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_acquisition_event_daily"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_acquisition_event_daily__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_acquisition_event_daily__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_acquisition_event_daily__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "channel IN ('REFERRAL', 'DIRECT', 'SOCIAL', 'PAID', 'ORGANIC_SEARCH', 'OTHER', 'UNKNOWN')",
            name="ck_acquisition_event_daily__channel",
        ),
        sa.CheckConstraint("length(channel) <= 20", name="ck_acquisition_event_daily__channel_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("count >= 0", name="ck_acquisition_event_daily__count"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_acquisition_event_daily__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(day) <= 10", name="ck_acquisition_event_daily__day_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_acquisition_event_daily__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "event IN ('site_visit', 'estimator_started', 'enquiry_started', 'journey_viewed')",
            name="ck_acquisition_event_daily__event",
        ),
        sa.CheckConstraint("length(event) <= 30", name="ck_acquisition_event_daily__event_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_acquisition_event_daily__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_acquisition_event_daily__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_acquisition_event_daily__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_acquisition_event_daily__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_acquisition_event_daily__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_acquisition_event_daily__version_positive"),
    )
    op.create_index(
        "ux_acquisition_event_daily__key",
        "acquisition_event_daily",
        ["day", "event", "channel"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    # --- end generated DDL ---
    ms.seed_lookups(bind, LOOKUPS, module="sales")
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
