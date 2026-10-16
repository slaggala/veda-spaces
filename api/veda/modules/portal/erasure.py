"""Customer Project Portal lead-erasure cascade (07 §8.2).

Erasing a lead revokes every ACTIVE portal access to it (LEAD_ERASED). An account left with no ACTIVE access is
erased too: its email and name are replaced, it is disabled and its sessions end. An account that still has access to
another enquiry keeps its email; if its name was copied from the erased enquiry it is renamed (``_rename``, never to
another person's name) and joins the erasure set, so its audit history loses that name too. The erased enquiry's access
list no longer shows who had access (``routes._present``). The event record holds codes and ids only.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.modules.crm.leads.models import Lead

from . import events, identity
from .models import PortalAccess, PortalAccount

ERASED_NAME = "[erased]"
NEUTRAL_NAME = "Customer"


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
            if account.name_source_lead_id == lead.id:
                _rename(s, account, remaining)
                erasure.add(account.id)  # its audit history loses the erased enquiry's name
                touched += 1
            continue
        account.email_normalized = f"erased+{account.id}@invalid"
        account.email_hash = identity.email_hash(account.email_normalized)
        account.display_name, account.name_source_lead_id = ERASED_NAME, None
        account.status, account.erased_on = "DISABLED", db.tx_time(s)
        identity.end_sessions(s, account.id, "LEAD_ERASED")
        events.record(s, account.id, "ACCOUNT_ERASED", lead_id=lead.id)
        erasure.add(account.id)
        touched += 1
    s.flush()
    return touched


def _rename(s: Session, account: PortalAccount, remaining: list[PortalAccess]) -> None:
    """The account was named from the erased enquiry. Its new name is that of an enquiry it holds as the primary
    customer (its own record), else a neutral one: never the name of an enquiry it joined as someone else's relative,
    co-owner or contact. A name staff chose, or one taken from another enquiry, is never touched."""
    own = next((a for a in remaining if a.relationship == "PRIMARY_CUSTOMER"), None)
    lead = s.get(Lead, own.lead_id) if own is not None else None
    if lead is not None:
        account.display_name, account.name_source_lead_id = lead.name[:150], lead.id
    else:
        account.display_name, account.name_source_lead_id = NEUTRAL_NAME, None


def audit_ids_for_lead(s: Session, lead_id: str) -> list[str]:
    rows = s.execute(sa.select(PortalAccess).where(PortalAccess.lead_id == lead_id)
                     .execution_options(include_deleted=True)).scalars().all()  # fmt: skip
    return [a.id for a in rows] + sorted({a.account_id for a in rows})
