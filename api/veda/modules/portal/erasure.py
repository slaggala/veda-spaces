"""Customer Project Portal lead-erasure cascade (07 §8.2).

Erasing a lead revokes every ACTIVE portal access to it (LEAD_ERASED). An account left with no ACTIVE access is
erased too: its email and name are replaced, it is disabled and its sessions end. An account that still has access to
another enquiry (another person's, or another of the same person's) keeps its identity; only this enquiry's access
ends. The event record holds codes and ids only and needs no change.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db

from . import events, identity
from .models import PortalAccess, PortalAccount

ERASED_NAME = "[erased]"


def erase_for_lead(s: Session, lead) -> int:
    erasure = s.info.setdefault("erasure_entities", set())
    touched = 0
    rows = s.execute(sa.select(PortalAccess).where(PortalAccess.lead_id == lead.id)
                     .execution_options(include_deleted=True)).scalars().all()  # fmt: skip
    for a in rows:
        erasure.add(a.id)
        if a.status == "ACTIVE":
            identity.revoke(s, None, a, "LEAD_ERASED")
            touched += 1
    for account_id in {a.account_id for a in rows}:
        account = s.get(PortalAccount, account_id)
        if account is None or account.erased_on is not None or identity.active_access(s, account_id):
            continue
        account.email_normalized = f"erased+{account.id}@invalid"
        account.display_name = ERASED_NAME
        account.status, account.erased_on = "DISABLED", db.tx_time(s)
        identity.end_sessions(s, account.id, "LEAD_ERASED")
        events.record(s, account.id, "ACCOUNT_ERASED", lead_id=lead.id)
        erasure.add(account.id)
        touched += 1
    s.flush()
    return touched


def audit_ids_for_lead(s: Session, lead_id: str) -> list[str]:
    rows = s.execute(sa.select(PortalAccess).where(PortalAccess.lead_id == lead_id)
                     .execution_options(include_deleted=True)).scalars().all()  # fmt: skip
    ids = [a.id for a in rows]
    for account_id in {a.account_id for a in rows}:
        account = s.get(PortalAccount, account_id)
        if account is not None and account.erased_on is not None:
            ids.append(account.id)
    return ids
