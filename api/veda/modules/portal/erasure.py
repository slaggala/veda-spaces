"""Customer Project Portal lead-erasure cascade (07 §8.2).

Erasing a lead revokes every ACTIVE portal access to it (LEAD_ERASED). An account left with no ACTIVE access is
erased too: its email and name are replaced, it is disabled and its sessions end. An account that still has access to
another enquiry keeps its email, takes its name from that live enquiry (it may have been named from the erased one),
and the erased enquiry's access list no longer shows who it was (``routes._present``). Either way the account joins
the erasure set, so its audit history loses the earlier name too. The event record holds codes and ids only.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.modules.crm.leads.models import Lead

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
        if account is None or account.erased_on is not None:
            continue
        remaining = identity.active_access(s, account_id)
        if remaining:
            # The account may have been named from the erased enquiry: keep no trace of it. Its name now comes from
            # an enquiry it still has (that customer's own record), and the erased enquiry hides the account (routes).
            live = s.get(Lead, remaining[0].lead_id)
            account.display_name = (live.name if live is not None else ERASED_NAME)[:150]
            erasure.add(account.id)
            touched += 1
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
    return [a.id for a in rows] + sorted({a.account_id for a in rows})
