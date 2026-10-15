"""0206_customer_completeness: per-version customer information choices (CQX customer completeness, OI-MTQ-18).

One nullable column on ``quotation``: ``customer_inputs``, staff's choices for a draft version against the customer
information pack frozen in its terms (the quotation contact, and the status of each customer responsibility and
site-readiness item). It is read when the version is issued and its customer document frozen; an issued document never
reads it again. No personal data: a contact is chosen by its code from the owner-approved business contacts.

Expand-only (02 §12.4): a nullable column, no data rewrite. The N-1 image never reads it, and rows it writes carry NULL
(every item "to be confirmed"). The issued-document template changes separately (``mtq-quotation-html/3``): an image
without that template cannot render documents issued with it (api-runbooks §2.4: roll forward only).

Revision ID: 0206_customer_completeness
Revises: 0205_customer_proposal
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel.types import JSONType

revision = "0206_customer_completeness"
down_revision = "0205_customer_proposal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "ALTER TABLE quotation ADD COLUMN customer_inputs TEXT "
            "CONSTRAINT ck_quotation__customer_inputs_json CHECK (customer_inputs IS NULL OR json_valid(customer_inputs))"
        )
        return
    op.add_column("quotation", sa.Column("customer_inputs", JSONType(), nullable=True))


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
