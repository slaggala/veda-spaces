"""Account scope and locking (PCM-020, PCM-040).

Every ``commercials.*`` code is scoped through the account's lead (``mtq.scope``). An account outside the actor's read
scope answers 404 (a guessed id discloses nothing); a visible account whose action is outside that action's scope
answers 403.

Every financial write takes the account's row lock first (PostgreSQL ``SELECT … FOR UPDATE``; SQLite write units of
work already hold the database write lock from ``BEGIN IMMEDIATE``) and then re-reads the account and the rows it will
change, so two payments, an issue and a revision on one account run one after the other and each decides on committed
state (the balance it checks is the balance at that moment). If-Match is compared with the re-read version.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.kernel.errors import ApiError, not_found
from veda.kernel.http import check_version
from veda.modules.crm.leads.models import Lead
from veda.modules.mtq import scope as lead_scope

from .models import CommercialAccount


def condition(ctx, permission: str, lead_column=None) -> sa.ColumnElement[bool]:
    return lead_scope.condition(ctx, permission, CommercialAccount.lead_id if lead_column is None else lead_column)


def _deny(ctx, permission: str) -> None:
    from veda.platform.auth.request_auth import deny

    deny(ctx, permission)


def visible(s: Session, ctx, account_id: str, permission: str = "commercials.view") -> CommercialAccount:
    if ctx.scope(permission) is None:
        _deny(ctx, permission)
    a = s.execute(sa.select(CommercialAccount).where(CommercialAccount.id == account_id,
                                                      condition(ctx, permission))).scalar_one_or_none()  # fmt: skip
    if a is None:
        raise not_found()
    lead = s.get(Lead, a.lead_id)
    if lead is None or lead.is_deleted:
        raise not_found()
    return a


def can(s: Session, ctx, account: CommercialAccount, permission: str) -> bool:
    scope = ctx.scope(permission)
    if scope == "ALL":
        return True
    if scope != "OWN":
        return False
    return s.execute(lead_scope.owned_lead_ids(ctx.user.id).where(Lead.id == account.lead_id)).first() is not None


def require(s: Session, ctx, account: CommercialAccount, permission: str) -> None:
    if ctx.scope(permission) is None:
        _deny(ctx, permission)
    if not can(s, ctx, account, permission):
        raise ApiError(403, "PERMISSION_DENIED", f"Requires {permission} for this customer.",
                       extra={"permission": permission})  # fmt: skip


def lock(s: Session, account: CommercialAccount, *rows) -> CommercialAccount:
    if s.get_bind().dialect.name == "postgresql":
        s.execute(sa.select(CommercialAccount.id).where(CommercialAccount.id == account.id).with_for_update())
    s.refresh(account)
    for row in rows:
        s.refresh(row)
    return account


def writable(s: Session, account: CommercialAccount) -> None:
    lead = s.get(Lead, account.lead_id)
    if lead is None or lead.is_deleted or lead.anonymized_on is not None:
        raise ApiError(409, "INVALID_STATE", "This customer record was erased or removed; its commercial record can no "
                       "longer change.")  # fmt: skip


def for_write(s: Session, ctx, account: CommercialAccount, permission: str, *rows, if_match: int | None = None,
              match=None, precondition: bool = True) -> CommercialAccount:  # fmt: skip
    """Scope check, account lock, re-read, then If-Match against the re-read version of ``match`` (default: the account).
    A new financial record (``precondition=False``) needs no If-Match: it is made replay-safe by its client key."""
    require(s, ctx, account, permission)
    lock(s, account, *rows)
    writable(s, account)
    if precondition:
        check_version(if_match, (account if match is None else match).version)
    return account


def touch(s: Session, account: CommercialAccount) -> None:
    """Move the account's version on any change under it, so a screen showing the earlier state cannot act on it."""
    account.updated_on = db.tx_time(s)
