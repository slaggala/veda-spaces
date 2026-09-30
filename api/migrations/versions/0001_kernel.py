"""0001_kernel: no tables. Records the engine requirements (02 §8.3).

SQLite connections are opened with journal_mode=WAL, foreign_keys=ON,
busy_timeout=5000 and synchronous=NORMAL (03 §1). SQLite >= 3.35 is required
for UPDATE ... RETURNING (03 §12).

Revision ID: 0001_kernel
Revises:
"""

from alembic import op

from veda.kernel import migration_support as ms  # noqa: F401
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0001_kernel"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        fk = bind.exec_driver_sql("PRAGMA foreign_keys").scalar()
        if int(fk or 0) != 1:
            raise RuntimeError("PRAGMA foreign_keys must be ON (DATA-010)")


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
