"""In-app notifications (08 §7, NOTIF-001). Scope OWN: recipient = actor."""

from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from pydantic import Field

from veda.kernel import clock, db
from veda.kernel.dto import Query
from veda.kernel.errors import not_found
from veda.kernel.http import Api, Req, decode_cursor, encode_cursor, ok

from .models import Notification

api = Api("notifications", "/api/v1/notifications", tags=("notifications",))


class NotificationsQuery(Query):
    unread: bool | None = None
    cursor: str | None = None
    limit: Annotated[int, Field(ge=1, le=200)] = 50


def present(n: Notification) -> dict:
    return {
        "id": n.id,
        "notification_type": n.notification_type,
        "title": n.title,
        "body": n.body,
        "entity_type": n.entity_type,
        "entity_id": n.entity_id,
        "link_path": n.link_path,
        "read_on": clock.to_rfc3339(n.read_on),
        "created_on": clock.to_rfc3339(n.created_on),
    }


@api.route("GET", "", permission="notification.read", query=NotificationsQuery, write=False, requirement="NOTIF-001")
def list_notifications(req: Req):
    uid = req.ctx.user.id
    q = sa.select(Notification).where(Notification.recipient_user_id == uid)
    if req.query.unread:
        q = q.where(Notification.read_on.is_(None))
    cur = decode_cursor(req.query.cursor)
    if cur:
        t = clock.parse_rfc3339(cur[0])
        q = q.where(
            sa.or_(Notification.created_on < t, sa.and_(Notification.created_on == t, Notification.id < cur[1]))
        )
    rows = (
        req.session.execute(
            q.order_by(Notification.created_on.desc(), Notification.id.desc()).limit(req.query.limit + 1)
        )
        .scalars()
        .all()
    )
    has_more = len(rows) > req.query.limit
    rows = rows[: req.query.limit]
    unread = req.session.execute(
        sa.select(sa.func.count())
        .select_from(Notification)
        .where(Notification.recipient_user_id == uid, Notification.read_on.is_(None))
    ).scalar()
    next_cursor = encode_cursor(clock.to_rfc3339(rows[-1].created_on, micros=True), rows[-1].id) if has_more else None
    return ok(
        [present(n) for n in rows],
        meta={
            "limit": req.query.limit,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "unread_count": int(unread or 0),
        },
    )


@api.route("POST", "/<notification_id>/read", permission="notification.read", requirement="NOTIF-001")
def mark_read(req: Req, notification_id: str):
    n = req.session.get(Notification, notification_id)
    if n is None or n.recipient_user_id != req.ctx.user.id:
        raise not_found()
    if n.read_on is None:
        n.read_on = db.tx_time(req.session)
    return ok(present(n))


@api.route("POST", "/read-all", permission="notification.read", requirement="NOTIF-001")
def mark_all_read(req: Req):
    now = db.tx_time(req.session)
    count = 0
    for n in req.session.execute(
        sa.select(Notification).where(Notification.recipient_user_id == req.ctx.user.id, Notification.read_on.is_(None))
    ).scalars():
        n.read_on = now
        count += 1
    return ok({"marked": count})
