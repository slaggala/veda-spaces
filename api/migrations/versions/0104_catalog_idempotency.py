"""0104_catalog_idempotency: durable idempotency for public V3 estimates (customer-safety closure).

Two nullable columns on catalog_configuration and one partial unique index:
- idempotency_key: the browser's per-request key;
- request_fingerprint: the SHA-256 of the configuration that was sent.

A repeat of the same request with the same key returns the estimate already created instead of creating a second one.
The same key with different choices is refused. No personal data, no rates, no permission changes.

Expand-only (02 §12.4): nullable columns and an index, no data rewrite. The N-1 image never reads them, so a rollback
runs unchanged (VEDA_SCHEMA_AHEAD_ACCEPTED).

Revision ID: 0104_catalog_idempotency
Revises: 0103_catalog
"""

import sqlalchemy as sa
from alembic import op

revision = "0104_catalog_idempotency"
down_revision = "0103_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "ALTER TABLE catalog_configuration ADD COLUMN idempotency_key VARCHAR(64) "
            "CONSTRAINT ck_catalog_configuration__idempotency_key_len CHECK (length(idempotency_key) <= 64)"
        )
        op.execute(
            "ALTER TABLE catalog_configuration ADD COLUMN request_fingerprint VARCHAR(64) "
            "CONSTRAINT ck_catalog_configuration__request_fingerprint_len CHECK (length(request_fingerprint) <= 64)"
        )
    else:
        op.add_column("catalog_configuration", sa.Column("idempotency_key", sa.String(64), nullable=True))
        op.add_column("catalog_configuration", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    op.create_index(
        "ux_catalog_configuration__idempotency_key",
        "catalog_configuration",
        ["idempotency_key"],
        unique=True,
        sqlite_where=sa.text("idempotency_key IS NOT NULL AND is_deleted = 0"),
        postgresql_where=sa.text("idempotency_key IS NOT NULL AND is_deleted = false"),
    )


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
