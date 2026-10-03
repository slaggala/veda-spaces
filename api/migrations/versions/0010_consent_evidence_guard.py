"""0010_consent_evidence_guard: database protection of the lead consent history (AM-4 option a, RR-12).

Adds triggers on lead_activity (no table or column change). A row whose metadata carries ``consent_event`` is
consent evidence: DELETE is refused, and UPDATE is refused except for the erasure rewrite of an anonymized lead
(07 §8.2), which may only anonymize the note, the location and the personal text of the superseded snapshot.
See ``veda.kernel.migration_support.create_consent_evidence_guard``.

Expand-only (02 §12.4): rows written before this revision are protected from now on. The N-1 image never updates
or deletes consent evidence except through erasure, whose rewrite the guard admits, so it runs unchanged on this
schema (declared through VEDA_SCHEMA_AHEAD_ACCEPTED for a rollback).

Revision ID: 0010_consent_evidence_guard
Revises: 0009_mfa_challenge_binding
"""

from alembic import op

from veda.kernel import migration_support as ms

revision = "0010_consent_evidence_guard"
down_revision = "0009_mfa_challenge_binding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ms.create_consent_evidence_guard(op.get_bind())


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
