"""0214_warranty_service: warranty entitlements and after-sales service requests (WSV, decision log 47).

Nine new tables (``veda.modules.warranty.models``): ``warranty_entitlement`` (one per handed-over project, frozen from
its HANDOVER transition), ``service_request`` and its rows (``service_request_photo``, ``service_assessment``,
``service_visit``, ``service_resolution``, ``service_evidence``, ``service_note``) and ``service_event`` (the
immutable timeline: UPDATE and DELETE refused by triggers on both engines). The attachment entity-type CHECK is
widened with ``service_request`` (SQLite: the exact 0106 definition is required and the stored table definition is
rewritten in place, as 0212 did for ``project_event``; PostgreSQL: the constraint is replaced, added NOT VALID then
validated). Sequence ``VS-SR-``. Nine ``warranty.*`` codes for FOUNDER.

Expand-only: nothing is removed or narrowed. Inert while VEDA_WARRANTY_SERVICE_ENABLED is off (the default
everywhere; production refuses it).

Revision ID: 0214_warranty_service
Revises: 0213_customer_documents
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0214_warranty_service"
down_revision = "0213_customer_documents"
branch_labels = None
depends_on = None

CODES = (
    "warranty.view",
    "warranty.manage",
    "warranty.service.view",
    "warranty.service.triage",
    "warranty.service.assess",
    "warranty.service.assign",
    "warranty.service.resolve",
    "warranty.service.verify",
    "warranty.service.audit",
)
SEQUENCES = (("SERVICE_REQUEST", "VS-SR-"),)
IMMUTABLE = ("service_event",)
OLD_TYPES = "entity_type IN ('property', 'property_space', 'measurement_set', 'space_wall', 'space_opening', 'space_electrical_point', 'measurement_note')"
NEW_TYPES = "entity_type IN ('property', 'property_space', 'measurement_set', 'space_wall', 'space_opening', 'space_electrical_point', 'measurement_note', 'service_request')"


def _widen_attachment_entity_types(bind) -> None:
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_attachment__entity_type", "attachment", type_="check")
        bind.exec_driver_sql(
            f"ALTER TABLE attachment ADD CONSTRAINT ck_attachment__entity_type CHECK ({NEW_TYPES}) NOT VALID"
        )
        bind.exec_driver_sql("ALTER TABLE attachment VALIDATE CONSTRAINT ck_attachment__entity_type")
        return
    stored = bind.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'attachment'").scalar()
    if stored.count(OLD_TYPES) != 1:
        raise RuntimeError("attachment's entity-type CHECK is not the 0106 definition; refusing to change it")
    version = int(bind.exec_driver_sql("PRAGMA schema_version").scalar())
    bind.exec_driver_sql("PRAGMA writable_schema = ON")
    try:
        bind.exec_driver_sql(
            "UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = 'attachment'",
            (stored.replace(OLD_TYPES, NEW_TYPES),),
        )
        bind.exec_driver_sql(f"PRAGMA schema_version = {version + 1}")
    finally:
        bind.exec_driver_sql("PRAGMA writable_schema = OFF")
    result = bind.exec_driver_sql("PRAGMA integrity_check").scalar()
    if result != "ok":
        raise RuntimeError(f"integrity check failed after widening the attachment entity-type CHECK: {result}")


def upgrade() -> None:
    bind = op.get_bind()
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "warranty_entitlement",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("handover_transition_id", GUID(), nullable=False),
        sa.Column("handover_on", sa.Date(), nullable=False),
        sa.Column("terms", JSONType(), nullable=False),
        sa.Column("terms_sha256", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("registered_via", sa.String(16), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_warranty_entitlement"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_warranty_entitlement__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_warranty_entitlement__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["handover_transition_id"],
            ["project_transition.id"],
            name="fk_warranty_entitlement__handover_transition_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_warranty_entitlement__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_warranty_entitlement__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_warranty_entitlement__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_warranty_entitlement__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_warranty_entitlement__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_warranty_entitlement__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(handover_transition_id) = 32 AND handover_transition_id NOT GLOB '*[^0-9a-f]*' AND substr(handover_transition_id, 13, 1) = '7' AND substr(handover_transition_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_warranty_entitlement__handover_transition_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_warranty_entitlement__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_warranty_entitlement__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_warranty_entitlement__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(policy_sha256) = 64", name="ck_warranty_entitlement__policy_sha256_len"),
        sa.CheckConstraint("length(policy_version) <= 40", name="ck_warranty_entitlement__policy_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_warranty_entitlement__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_warranty_entitlement__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "registered_via IN ('HANDOVER_EVENT', 'STAFF')", name="ck_warranty_entitlement__registered_via"
        ),
        sa.CheckConstraint("length(registered_via) <= 16", name="ck_warranty_entitlement__registered_via_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_warranty_entitlement__soft_delete_consistent",
        ),
        sa.CheckConstraint("terms IS NULL OR json_valid(terms)", name="ck_warranty_entitlement__terms_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(terms_sha256) = 64", name="ck_warranty_entitlement__terms_sha256_len"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_warranty_entitlement__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_warranty_entitlement__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_warranty_entitlement__version_positive"),
    )
    op.create_index("ix_warranty_entitlement__lead_id", "warranty_entitlement", ["lead_id"])
    op.create_index("ix_warranty_entitlement__property", "warranty_entitlement", ["property_id"])
    op.create_index("ix_warranty_entitlement__transition", "warranty_entitlement", ["handover_transition_id"])
    op.create_index(
        "ux_warranty_entitlement__project",
        "warranty_entitlement",
        ["project_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "service_request",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("request_number", sa.String(24), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("entitlement_id", GUID(), nullable=True),
        sa.Column("related_request_id", GUID(), nullable=True),
        sa.Column("duplicate_of_id", GUID(), nullable=True),
        sa.Column("channel", sa.String(8), nullable=False),
        sa.Column("account_id", GUID(), nullable=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("area", sa.String(120), nullable=True),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("noticed_on", sa.Date(), nullable=True),
        sa.Column("reported_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("return_state", sa.String(32), nullable=True),
        sa.Column("priority", sa.String(8), nullable=False, server_default="NORMAL"),
        sa.Column("owner_user_id", GUID(), nullable=True),
        sa.Column("cycle", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("rejections", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("service_class", sa.String(16), nullable=True),
        sa.Column("closure_code", sa.String(32), nullable=True),
        sa.Column("closed_on", UTCDateTime(), nullable=True),
        sa.Column("verified_by_kind", sa.String(8), nullable=True),
        sa.Column("client_key_sha256", sa.String(64), nullable=True),
        sa.Column("request_sha256", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_service_request"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["portal_account.id"], name="fk_service_request__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_service_request__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_service_request__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"], ["service_request.id"], name="fk_service_request__duplicate_of_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["entitlement_id"],
            ["warranty_entitlement.id"],
            name="fk_service_request__entitlement_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_service_request__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["app_user.id"], name="fk_service_request__owner_user_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_service_request__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_service_request__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["related_request_id"],
            ["service_request.id"],
            name="fk_service_request__related_request_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_service_request__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_service_request__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("(channel = 'PORTAL') = (account_id IS NOT NULL)", name="ck_service_request__account"),
        sa.CheckConstraint(
            "account_id IS NULL OR (length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_request__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(area) <= 120", name="ck_service_request__area_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "category IN ('DOOR_OR_DRAWER', 'HARDWARE', 'SURFACE_OR_FINISH', 'ALIGNMENT_OR_GAP', 'WATER_OR_DAMP', 'LIGHT_OR_ELECTRICAL_FITTING', 'APPLIANCE', 'OTHER')",
            name="ck_service_request__category",
        ),
        sa.CheckConstraint("length(category) <= 32", name="ck_service_request__category_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("channel IN ('PORTAL', 'STAFF')", name="ck_service_request__channel"),
        sa.CheckConstraint("length(channel) <= 8", name="ck_service_request__channel_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "client_key_sha256 IS NULL OR length(client_key_sha256) = 64",
            name="ck_service_request__client_key_sha256_len",
        ),
        sa.CheckConstraint(
            "(status = 'CLOSED') = (closure_code IS NOT NULL AND closed_on IS NOT NULL)",
            name="ck_service_request__closed",
        ),
        sa.CheckConstraint(
            "closure_code IS NULL OR closure_code IN ('SERVICED', 'DUPLICATE', 'NOT_COVERED', 'REFERRED_TO_MANUFACTURER', 'CHARGEABLE_NOT_AGREED', 'CUSTOMER_WITHDREW', 'CANNOT_SERVICE')",
            name="ck_service_request__closure_code",
        ),
        sa.CheckConstraint("length(closure_code) <= 32", name="ck_service_request__closure_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("cycle >= 1 AND rejections >= 0", name="ck_service_request__counters"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_request__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 2000", name="ck_service_request__description_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "closure_code IS NULL OR closure_code <> 'DUPLICATE' OR duplicate_of_id IS NOT NULL",
            name="ck_service_request__duplicate",
        ),
        sa.CheckConstraint(
            "duplicate_of_id IS NULL OR (length(duplicate_of_id) = 32 AND duplicate_of_id NOT GLOB '*[^0-9a-f]*' AND substr(duplicate_of_id, 13, 1) = '7' AND substr(duplicate_of_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_request__duplicate_of_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "entitlement_id IS NULL OR (length(entitlement_id) = 32 AND entitlement_id NOT GLOB '*[^0-9a-f]*' AND substr(entitlement_id, 13, 1) = '7' AND substr(entitlement_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_request__entitlement_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(status = 'INFORMATION_REQUESTED') = (return_state IS NOT NULL)",
            name="ck_service_request__information_return",
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_service_request__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(client_key_sha256 IS NULL) = (request_sha256 IS NULL)", name="ck_service_request__key_pair"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "owner_user_id IS NULL OR (length(owner_user_id) = 32 AND owner_user_id NOT GLOB '*[^0-9a-f]*' AND substr(owner_user_id, 13, 1) = '7' AND substr(owner_user_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_request__owner_user_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("priority IN ('HIGH', 'NORMAL', 'LOW')", name="ck_service_request__priority"),
        sa.CheckConstraint("length(priority) <= 8", name="ck_service_request__priority_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "related_request_id IS NULL OR (length(related_request_id) = 32 AND related_request_id NOT GLOB '*[^0-9a-f]*' AND substr(related_request_id, 13, 1) = '7' AND substr(related_request_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_request__related_request_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(request_number) <= 24", name="ck_service_request__request_number_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "request_sha256 IS NULL OR length(request_sha256) = 64", name="ck_service_request__request_sha256_len"
        ),
        sa.CheckConstraint(
            "return_state IS NULL OR return_state IN ('REPORTED', 'TRIAGED', 'ASSESSED', 'IN_PROGRESS')",
            name="ck_service_request__return_state",
        ),
        sa.CheckConstraint("length(return_state) <= 32", name="ck_service_request__return_state_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "service_class IS NULL OR service_class IN ('WARRANTY', 'CHARGEABLE', 'NOT_SERVICEABLE')",
            name="ck_service_request__service_class",
        ),
        sa.CheckConstraint("length(service_class) <= 16", name="ck_service_request__service_class_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_service_request__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_request__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status IN ('REPORTED', 'INFORMATION_REQUESTED', 'TRIAGED', 'ASSESSED', 'AWAITING_COMMERCIAL_AGREEMENT', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')",
            name="ck_service_request__status",
        ),
        sa.CheckConstraint("length(status) <= 32", name="ck_service_request__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_service_request__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(closure_code = 'SERVICED') = (verified_by_kind IS NOT NULL)", name="ck_service_request__verified"
        ),
        sa.CheckConstraint(
            "verified_by_kind IS NULL OR verified_by_kind IN ('CUSTOMER', 'STAFF')",
            name="ck_service_request__verified_by_kind",
        ),
        sa.CheckConstraint("length(verified_by_kind) <= 8", name="ck_service_request__verified_by_kind_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("version >= 1", name="ck_service_request__version_positive"),
    )
    op.create_index("ix_service_request__account", "service_request", ["account_id"])
    op.create_index("ix_service_request__duplicate_of", "service_request", ["duplicate_of_id"])
    op.create_index("ix_service_request__entitlement", "service_request", ["entitlement_id"])
    op.create_index("ix_service_request__lead_id", "service_request", ["lead_id"])
    op.create_index("ix_service_request__owner", "service_request", ["owner_user_id"])
    op.create_index("ix_service_request__project", "service_request", ["project_id", "status"])
    op.create_index("ix_service_request__property", "service_request", ["property_id", "status"])
    op.create_index("ix_service_request__related", "service_request", ["related_request_id"])
    op.create_index("ix_service_request__space", "service_request", ["space_id"])
    op.create_index("ix_service_request__status", "service_request", ["status", "created_on"])
    op.create_index(
        "ux_service_request__client_key",
        "service_request",
        ["account_id", "client_key_sha256"],
        unique=True,
        sqlite_where=sa.text("client_key_sha256 IS NOT NULL AND is_deleted = 0"),
        postgresql_where=sa.text("client_key_sha256 IS NOT NULL AND is_deleted = false"),
    )
    op.create_index(
        "ux_service_request__number",
        "service_request",
        ["request_number"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "service_request_photo",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("attachment_id", GUID(), nullable=False),
        sa.Column("channel", sa.String(8), nullable=False),
        sa.Column("account_id", GUID(), nullable=True),
        sa.Column("request_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_service_request_photo"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["portal_account.id"], name="fk_service_request_photo__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["attachment_id"], ["attachment.id"], name="fk_service_request_photo__attachment_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_service_request_photo__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_service_request_photo__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_service_request_photo__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_request.id"], name="fk_service_request_photo__request_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_service_request_photo__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("(channel = 'PORTAL') = (account_id IS NOT NULL)", name="ck_service_request_photo__account"),
        sa.CheckConstraint(
            "account_id IS NULL OR (length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_request_photo__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(attachment_id) = 32 AND attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(attachment_id, 13, 1) = '7' AND substr(attachment_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request_photo__attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("channel IN ('PORTAL', 'STAFF')", name="ck_service_request_photo__channel"),
        sa.CheckConstraint("length(channel) <= 8", name="ck_service_request_photo__channel_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request_photo__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_request_photo__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request_photo__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_service_request_photo__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request_photo__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(request_id) = 32 AND request_id NOT GLOB '*[^0-9a-f]*' AND substr(request_id, 13, 1) = '7' AND substr(request_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request_photo__request_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_service_request_photo__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_service_request_photo__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_request_photo__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_service_request_photo__version_positive"),
    )
    op.create_index("ix_service_request_photo__account", "service_request_photo", ["account_id"])
    op.create_index("ix_service_request_photo__lead_id", "service_request_photo", ["lead_id"])
    op.create_index("ix_service_request_photo__request", "service_request_photo", ["request_id"])
    op.create_index(
        "ux_service_request_photo__attachment",
        "service_request_photo",
        ["attachment_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "service_assessment",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("service_class", sa.String(16), nullable=True),
        sa.Column("basis_kind", sa.String(32), nullable=True),
        sa.Column("basis_path", sa.String(120), nullable=True),
        sa.Column("basis_text_sha256", sa.String(64), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("coverage_status", sa.String(16), nullable=True),
        sa.Column("explanation", sa.String(1000), nullable=False),
        sa.Column("internal_reason", sa.String(2000), nullable=False),
        sa.Column("period_basis", sa.String(1000), nullable=True),
        sa.Column("assessed_by", GUID(), nullable=False),
        sa.Column("assessed_on", UTCDateTime(), nullable=False),
        sa.Column("request_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_service_assessment"),
        sa.ForeignKeyConstraint(
            ["assessed_by"], ["app_user.id"], name="fk_service_assessment__assessed_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_service_assessment__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_service_assessment__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_service_assessment__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_request.id"], name="fk_service_assessment__request_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_service_assessment__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(assessed_by) = 32 AND assessed_by NOT GLOB '*[^0-9a-f]*' AND substr(assessed_by, 13, 1) = '7' AND substr(assessed_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_assessment__assessed_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("(basis_kind IS NULL) = (basis_path IS NULL)", name="ck_service_assessment__basis"),
        sa.CheckConstraint(
            "basis_kind IS NULL OR basis_kind IN ('COVERAGE_CLASS', 'WARRANTY_STATEMENT', 'SERVICE_SUPPORT_STATEMENT', 'EXCLUSION', 'MANUFACTURER_NOTE', 'ASSESSMENT')",
            name="ck_service_assessment__basis_kind",
        ),
        sa.CheckConstraint("length(basis_kind) <= 32", name="ck_service_assessment__basis_kind_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(basis_path) <= 120", name="ck_service_assessment__basis_path_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "basis_text_sha256 IS NULL OR length(basis_text_sha256) = 64",
            name="ck_service_assessment__basis_text_sha256_len",
        ),
        sa.CheckConstraint(
            "coverage_status IS NULL OR coverage_status IN ('ACTIVE', 'EXPIRED', 'NOT_STARTED', 'NOT_RECORDED')",
            name="ck_service_assessment__coverage_status",
        ),
        sa.CheckConstraint("length(coverage_status) <= 16", name="ck_service_assessment__coverage_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "outcome <> 'COVERED' OR (service_class = 'WARRANTY' AND basis_kind IN ('COVERAGE_CLASS', 'WARRANTY_STATEMENT', 'SERVICE_SUPPORT_STATEMENT'))",
            name="ck_service_assessment__covered",
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_assessment__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("cycle >= 1", name="ck_service_assessment__cycle"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_assessment__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(explanation) <= 1000", name="ck_service_assessment__explanation_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_assessment__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(internal_reason) <= 2000", name="ck_service_assessment__internal_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_service_assessment__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_assessment__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "outcome IN ('COVERED', 'NOT_COVERED', 'OUTSIDE_WARRANTY_PERIOD', 'MANUFACTURER_WARRANTY', 'INSPECTION_REQUIRED', 'INSUFFICIENT_INFORMATION')",
            name="ck_service_assessment__outcome",
        ),
        sa.CheckConstraint("length(outcome) <= 32", name="ck_service_assessment__outcome_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(period_basis) <= 1000", name="ck_service_assessment__period_basis_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(request_id) = 32 AND request_id NOT GLOB '*[^0-9a-f]*' AND substr(request_id, 13, 1) = '7' AND substr(request_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_assessment__request_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "service_class IS NULL OR service_class IN ('WARRANTY', 'CHARGEABLE', 'NOT_SERVICEABLE')",
            name="ck_service_assessment__service_class",
        ),
        sa.CheckConstraint("length(service_class) <= 16", name="ck_service_assessment__service_class_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_service_assessment__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_service_assessment__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_assessment__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_service_assessment__version_positive"),
    )
    op.create_index("ix_service_assessment__assessed_by", "service_assessment", ["assessed_by"])
    op.create_index("ix_service_assessment__lead_id", "service_assessment", ["lead_id"])
    op.create_index("ix_service_assessment__request", "service_assessment", ["request_id", "created_on"])

    op.create_table(
        "service_visit",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("visit_no", sa.Integer(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("planned_on", sa.Date(), nullable=False),
        sa.Column("done_on", sa.Date(), nullable=True),
        sa.Column("customer_note", sa.String(1000), nullable=True),
        sa.Column("internal_note", sa.String(2000), nullable=True),
        sa.Column("cancel_reason", sa.String(300), nullable=True),
        sa.Column("done_by", GUID(), nullable=True),
        sa.Column("request_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_service_visit"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_service_visit__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_service_visit__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["done_by"], ["app_user.id"], name="fk_service_visit__done_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_service_visit__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_request.id"], name="fk_service_visit__request_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_service_visit__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("length(cancel_reason) <= 300", name="ck_service_visit__cancel_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("(status = 'CANCELLED') = (cancel_reason IS NOT NULL)", name="ck_service_visit__cancelled"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_visit__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(customer_note) <= 1000", name="ck_service_visit__customer_note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_visit__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(status = 'DONE') = (done_on IS NOT NULL AND done_by IS NOT NULL)", name="ck_service_visit__done"
        ),
        sa.CheckConstraint(
            "done_by IS NULL OR (length(done_by) = 32 AND done_by NOT GLOB '*[^0-9a-f]*' AND substr(done_by, 13, 1) = '7' AND substr(done_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_visit__done_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_visit__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(internal_note) <= 2000", name="ck_service_visit__internal_note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_service_visit__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("kind IN ('INSPECTION', 'SERVICE')", name="ck_service_visit__kind"),
        sa.CheckConstraint("length(kind) <= 12", name="ck_service_visit__kind_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_visit__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(request_id) = 32 AND request_id NOT GLOB '*[^0-9a-f]*' AND substr(request_id, 13, 1) = '7' AND substr(request_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_visit__request_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_service_visit__soft_delete_consistent",
        ),
        sa.CheckConstraint("status IN ('PLANNED', 'DONE', 'CANCELLED')", name="ck_service_visit__status"),
        sa.CheckConstraint("length(status) <= 12", name="ck_service_visit__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_service_visit__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_visit__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_service_visit__version_positive"),
        sa.CheckConstraint("visit_no >= 1 AND cycle >= 1", name="ck_service_visit__visit_no"),
    )
    op.create_index("ix_service_visit__done_by", "service_visit", ["done_by"])
    op.create_index("ix_service_visit__lead_id", "service_visit", ["lead_id"])
    op.create_index(
        "ux_service_visit__number",
        "service_visit",
        ["request_id", "visit_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "service_resolution",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("internal_note", sa.String(2000), nullable=True),
        sa.Column("resolved_by", GUID(), nullable=False),
        sa.Column("resolved_on", UTCDateTime(), nullable=False),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("decided_on", UTCDateTime(), nullable=True),
        sa.Column("decided_by", GUID(), nullable=True),
        sa.Column("decided_account_id", GUID(), nullable=True),
        sa.Column("request_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_service_resolution"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_service_resolution__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["decided_account_id"],
            ["portal_account.id"],
            name="fk_service_resolution__decided_account_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["app_user.id"], name="fk_service_resolution__decided_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_service_resolution__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_service_resolution__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_request.id"], name="fk_service_resolution__request_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["app_user.id"], name="fk_service_resolution__resolved_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_service_resolution__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_resolution__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "outcome NOT IN ('CONFIRMED', 'REJECTED') OR decided_account_id IS NOT NULL",
            name="ck_service_resolution__customer",
        ),
        sa.CheckConstraint("cycle >= 1", name="ck_service_resolution__cycle"),
        sa.CheckConstraint("(outcome = 'PENDING') = (decided_on IS NULL)", name="ck_service_resolution__decided"),
        sa.CheckConstraint(
            "decided_account_id IS NULL OR (length(decided_account_id) = 32 AND decided_account_id NOT GLOB '*[^0-9a-f]*' AND substr(decided_account_id, 13, 1) = '7' AND substr(decided_account_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_resolution__decided_account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "decided_by IS NULL OR (length(decided_by) = 32 AND decided_by NOT GLOB '*[^0-9a-f]*' AND substr(decided_by, 13, 1) = '7' AND substr(decided_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_resolution__decided_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_resolution__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_resolution__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(internal_note) <= 2000", name="ck_service_resolution__internal_note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_service_resolution__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_resolution__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "outcome IN ('PENDING', 'CONFIRMED', 'VERIFIED', 'REJECTED', 'SUPERSEDED')",
            name="ck_service_resolution__outcome",
        ),
        sa.CheckConstraint("length(outcome) <= 10", name="ck_service_resolution__outcome_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(request_id) = 32 AND request_id NOT GLOB '*[^0-9a-f]*' AND substr(request_id, 13, 1) = '7' AND substr(request_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_resolution__request_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(resolved_by) = 32 AND resolved_by NOT GLOB '*[^0-9a-f]*' AND substr(resolved_by, 13, 1) = '7' AND substr(resolved_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_resolution__resolved_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_service_resolution__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(summary) <= 1000", name="ck_service_resolution__summary_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_service_resolution__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_resolution__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("outcome <> 'VERIFIED' OR decided_by IS NOT NULL", name="ck_service_resolution__verified"),
        sa.CheckConstraint("version >= 1", name="ck_service_resolution__version_positive"),
    )
    op.create_index("ix_service_resolution__account", "service_resolution", ["decided_account_id"])
    op.create_index("ix_service_resolution__decided_by", "service_resolution", ["decided_by"])
    op.create_index("ix_service_resolution__lead_id", "service_resolution", ["lead_id"])
    op.create_index("ix_service_resolution__request", "service_resolution", ["request_id", "created_on"])
    op.create_index("ix_service_resolution__resolved_by", "service_resolution", ["resolved_by"])
    op.create_index(
        "ux_service_resolution__pending",
        "service_resolution",
        ["request_id"],
        unique=True,
        sqlite_where=sa.text("outcome = 'PENDING' AND is_deleted = 0"),
        postgresql_where=sa.text("outcome = 'PENDING' AND is_deleted = false"),
    )

    op.create_table(
        "service_evidence",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("attachment_id", GUID(), nullable=False),
        sa.Column("visit_id", GUID(), nullable=True),
        sa.Column("resolution_id", GUID(), nullable=True),
        sa.Column("customer_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("caption", sa.String(160), nullable=True),
        sa.Column("request_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_service_evidence"),
        sa.ForeignKeyConstraint(
            ["attachment_id"], ["attachment.id"], name="fk_service_evidence__attachment_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_service_evidence__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_service_evidence__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_service_evidence__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_request.id"], name="fk_service_evidence__request_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resolution_id"], ["service_resolution.id"], name="fk_service_evidence__resolution_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_service_evidence__updated_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["visit_id"], ["service_visit.id"], name="fk_service_evidence__visit_id", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(attachment_id) = 32 AND attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(attachment_id, 13, 1) = '7' AND substr(attachment_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_evidence__attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(caption) <= 160", name="ck_service_evidence__caption_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_evidence__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("customer_visible IN (0, 1)", name="ck_service_evidence__customer_visible_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_evidence__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_evidence__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_service_evidence__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_evidence__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(request_id) = 32 AND request_id NOT GLOB '*[^0-9a-f]*' AND substr(request_id, 13, 1) = '7' AND substr(request_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_evidence__request_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "resolution_id IS NULL OR (length(resolution_id) = 32 AND resolution_id NOT GLOB '*[^0-9a-f]*' AND substr(resolution_id, 13, 1) = '7' AND substr(resolution_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_evidence__resolution_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_service_evidence__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_service_evidence__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_evidence__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_service_evidence__version_positive"),
        sa.CheckConstraint(
            "visit_id IS NULL OR (length(visit_id) = 32 AND visit_id NOT GLOB '*[^0-9a-f]*' AND substr(visit_id, 13, 1) = '7' AND substr(visit_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_evidence__visit_id_format",
        ).ddl_if(dialect="sqlite"),
    )
    op.create_index("ix_service_evidence__attachment", "service_evidence", ["attachment_id"])
    op.create_index("ix_service_evidence__lead_id", "service_evidence", ["lead_id"])
    op.create_index("ix_service_evidence__resolution", "service_evidence", ["resolution_id"])
    op.create_index("ix_service_evidence__visit", "service_evidence", ["visit_id"])
    op.create_index(
        "ux_service_evidence__attachment",
        "service_evidence",
        ["request_id", "attachment_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "service_note",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("visibility", sa.String(8), nullable=False),
        sa.Column("text", sa.String(2000), nullable=False),
        sa.Column("account_id", GUID(), nullable=True),
        sa.Column("request_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_service_note"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["portal_account.id"], name="fk_service_note__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_service_note__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_service_note__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_service_note__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_request.id"], name="fk_service_note__request_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_service_note__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "account_id IS NULL OR (length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_note__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_note__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("account_id IS NULL OR visibility = 'CUSTOMER'", name="ck_service_note__customer"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_note__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_note__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("kind <> 'INTERNAL' OR visibility = 'INTERNAL'", name="ck_service_note__internal"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_service_note__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "kind IN ('INFORMATION_REQUEST', 'CUSTOMER_INFORMATION', 'INTERNAL', 'REJECTION', 'REOPEN', 'CLOSURE', 'WITHDRAWAL')",
            name="ck_service_note__kind",
        ),
        sa.CheckConstraint("length(kind) <= 24", name="ck_service_note__kind_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_note__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(request_id) = 32 AND request_id NOT GLOB '*[^0-9a-f]*' AND substr(request_id, 13, 1) = '7' AND substr(request_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_note__request_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_service_note__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(text) <= 2000", name="ck_service_note__text_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_service_note__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_note__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_service_note__version_positive"),
        sa.CheckConstraint("visibility IN ('CUSTOMER', 'INTERNAL')", name="ck_service_note__visibility"),
        sa.CheckConstraint("length(visibility) <= 8", name="ck_service_note__visibility_len").ddl_if(dialect="sqlite"),
    )
    op.create_index("ix_service_note__account", "service_note", ["account_id"])
    op.create_index("ix_service_note__lead_id", "service_note", ["lead_id"])
    op.create_index("ix_service_note__request", "service_note", ["request_id", "created_on"])

    op.create_table(
        "service_event",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("event_code", sa.String(32), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=True),
        sa.Column("to_state", sa.String(32), nullable=True),
        sa.Column("account_id", GUID(), nullable=True),
        sa.Column("detail", JSONType(), nullable=False),
        sa.Column("request_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_service_event"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["portal_account.id"], name="fk_service_event__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_service_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_service_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_service_event__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_request.id"], name="fk_service_event__request_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_service_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "account_id IS NULL OR (length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_event__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_service_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("detail IS NULL OR json_valid(detail)", name="ck_service_event__detail_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "event_code IN ('SUBMITTED', 'INFORMATION_REQUESTED', 'INFORMATION_ADDED', 'TRIAGED', 'ASSESSED', 'ASSIGNED', 'VISIT_PLANNED', 'VISIT_DONE', 'VISIT_CANCELLED', 'PHOTO_ADDED', 'EVIDENCE_ADDED', 'RESOLVED', 'RESOLUTION_REJECTED', 'VERIFIED', 'CLOSED', 'WITHDRAWN', 'REOPENED', 'NOTE_ADDED')",
            name="ck_service_event__event_code",
        ),
        sa.CheckConstraint("length(event_code) <= 32", name="ck_service_event__event_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(from_state) <= 32", name="ck_service_event__from_state_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted = false AND version = 1", name="ck_service_event__immutable_contract"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_service_event__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_event__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(request_id) = 32 AND request_id NOT GLOB '*[^0-9a-f]*' AND substr(request_id, 13, 1) = '7' AND substr(request_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_event__request_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_service_event__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(to_state) <= 32", name="ck_service_event__to_state_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_service_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_service_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_service_event__version_positive"),
    )
    op.create_index("ix_service_event__account", "service_event", ["account_id"])
    op.create_index("ix_service_event__lead_id", "service_event", ["lead_id"])
    op.create_index("ix_service_event__request", "service_event", ["request_id", "created_on"])
    # --- end generated DDL ---
    for table in IMMUTABLE:
        ms.create_immutability_guards(bind, table)
    _widen_attachment_entity_types(bind)
    for key, prefix in SEQUENCES:
        ms.seed_sequence(bind, key, prefix)
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
