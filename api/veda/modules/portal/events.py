"""The portal's immutable event record and its one email (CPP-002, CPP-003).

``record`` appends a ``portal_event`` row: codes, ids and dates only, never an email address or free text, so a row
never needs erasing and can be immutable (migration 0209 triggers refuse update and delete).

The sign-in email is sent from the outbox like every other email: the payload names the sign-in row only, and the
handler derives the link from the row id (``derive_action_token``), so neither the outbox nor the log holds a token.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from veda.kernel import clock, outbox
from veda.platform.auth.crypto import derive_action_token
from veda.platform.notifications.handlers import app_link, handler, send
from veda.platform.notifications.models import OutboxEvent

from .models import PortalAccount, PortalEvent, PortalSignIn

_SAFE = re.compile(r"^[A-Za-z0-9_.:+-]{0,80}$")
SIGN_IN_LINK = "portal.sign_in_link"
EVENT_TYPES = (SIGN_IN_LINK,)
LINK_PATH = "/portal/sign-in"


def _check(value: Any, key: str) -> None:
    if value is None or isinstance(value, bool | int):
        return
    if isinstance(value, str) and _SAFE.match(value):
        return
    raise ValueError(f"portal_event detail {key!r} must be a code, id or date, never free text")


def record(s: Session, account_id: str, code: str, *, lead_id: str | None = None, **detail: Any) -> PortalEvent:
    clean = {k: v for k, v in detail.items() if v is not None}
    for k, v in clean.items():
        _check(v, k)
    e = PortalEvent(account_id=account_id, lead_id=lead_id, event_code=code, detail=clean)
    s.add(e)
    return e


def sign_in_token(row: PortalSignIn) -> str:
    return derive_action_token(row.id, f"PORTAL_{row.purpose}")


def link_for(row: PortalSignIn) -> str:
    return app_link(f"{LINK_PATH}#t={sign_in_token(row)}")


def notify_sign_in(s: Session, row: PortalSignIn) -> None:
    outbox.enqueue(s, SIGN_IN_LINK, "portal_account", row.account_id, sign_in_id=row.id)


@handler(SIGN_IN_LINK)
def _send_sign_in(s: Session, event: OutboxEvent) -> None:
    row = s.get(PortalSignIn, event.payload.get("sign_in_id"))
    account = s.get(PortalAccount, row.account_id) if row is not None else None
    if row is None or account is None or account.status != "ACTIVE":
        return
    if row.used_on is not None or row.invalidated_on is not None or row.expires_on <= clock.now():
        return  # superseded or spent before the worker ran: send nothing
    minutes = max(1, int((row.expires_on - row.created_on).total_seconds() // 60))
    send("portal_sign_in", [account.email_normalized], event, name=account.display_name, link=link_for(row),
         invitation=row.purpose == "INVITATION", expires_minutes=minutes)  # fmt: skip
