"""Outbox handlers: notification catalog (02 §10.3).

Recipients are resolved by permission, never by role name (RBAC-002).
Security notifications always go to the verified email; a proposed address
only ever receives its verification link. Handlers are idempotent per
outbox event (in-app rows are unique per (source_event_id, recipient)).
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock
from veda.kernel.dto import mask_email
from veda.platform.auth.crypto import derive_action_token
from veda.platform.auth.models import UserActionToken
from veda.platform.identity.models import User
from veda.platform.rbac.resolver import holders_of

from . import email as email_mod
from .models import Notification, OutboxEvent
from .templates import render

HANDLERS: dict[str, Callable[[Session, OutboxEvent], None]] = {}
MAINTENANCE_ONLY = frozenset({"lead.erasure_requested"})


def handler(event_type: str):
    def decorator(fn):
        HANDLERS[event_type] = fn
        return fn

    return decorator


def app_link(path: str) -> str:
    return settings().app_base_url.rstrip("/") + path


def when(user: User | None) -> str:
    tz = ZoneInfo(user.timezone if user else "Asia/Kolkata")
    local = clock.now().astimezone(tz)
    return local.strftime("%d %b %Y, %I:%M %p ") + (local.tzname() or "")


# Emails are queued while the handler runs and sent after its in-app rows commit, so an email
# failure never undoes in-app delivery (02 §10.1 separate handlers, NOTIF-008).
_queued: ContextVar[list | None] = ContextVar("veda_queued_emails", default=None)


def begin_email_queue() -> None:
    _queued.set([])


def take_email_queue() -> list:
    items = _queued.get() or []
    _queued.set(None)
    return items


def send(template: str, to: list[str], event: OutboxEvent, **context) -> None:
    to = [t for t in dict.fromkeys(to) if t]
    if not to:
        return
    subject, text, html = render(template, **context)
    headers = {"X-Veda-Event": event.event_type, "X-Veda-Event-Id": event.id}
    if event.payload.get("request_id"):
        headers["X-Request-ID"] = str(event.payload["request_id"])
    message = email_mod.EmailMessage(to=to, subject=subject, text=text, html=html, template=template, headers=headers)
    queue = _queued.get()
    if queue is None:
        email_mod.provider().send(message)
    else:
        queue.append(message)


def notify_in_app(
    s: Session,
    event: OutboxEvent,
    recipients: list[str],
    *,
    notification_type: str,
    title: str,
    body: str | None = None,
    entity: tuple[str, str] | None = None,
    link_path: str | None = None,
) -> None:
    for rid in dict.fromkeys(recipients):
        exists = s.execute(
            sa.select(Notification.id).where(
                Notification.source_event_id == event.id, Notification.recipient_user_id == rid
            )
        ).first()
        if exists:
            continue
        s.add(
            Notification(
                recipient_user_id=rid,
                notification_type=notification_type,
                title=title[:200],
                body=(body or None) and body[:1000],
                entity_type=entity[0] if entity else None,
                entity_id=entity[1] if entity else None,
                link_path=link_path,
                source_event_id=event.id,
            )
        )
    s.flush()


def _user(s: Session, user_id: str | None) -> User | None:
    return s.get(User, user_id, execution_options={"include_deleted": True}) if user_id else None


def _token_link(s: Session, token_id: str, path: str) -> tuple[str, UserActionToken | None]:
    tok = s.get(UserActionToken, token_id)
    if tok is None:
        return "", None
    return app_link(f"{path}#token={derive_action_token(tok.id, tok.purpose)}"), tok


def _usable(tok: UserActionToken | None) -> bool:
    return tok is not None and tok.used_on is None and tok.invalidated_on is None and tok.expires_on > clock.now()


# --- identity & security emails -----------------------------------------------------------


@handler("user.invited")
def _invited(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    link, tok = _token_link(s, event.payload["token_id"], "/accept-invite")
    if user and _usable(tok):
        hours = max(1, int((tok.expires_on - tok.created_on).total_seconds() // 3600))
        send("user_invited", [user.email], event, name=user.full_name, link=link, expires_hours=hours)


@handler("auth.password_reset_requested")
def _reset(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    link, tok = _token_link(s, event.payload["token_id"], "/reset-password")
    if user and _usable(tok):
        send("password_reset", [user.email], event, name=user.display_name or user.full_name, link=link)


@handler("auth.password_changed")
def _changed(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    if user:
        send("password_changed", [user.email], event, name=user.display_name or user.full_name, when=when(user))


@handler("auth.mfa_enrollment_link")
def _enroll_link(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    link, tok = _token_link(s, event.payload["token_id"], "/mfa/enroll")
    if user and _usable(tok):
        send("mfa_enrollment_link", [user.email], event, name=user.display_name or user.full_name, link=link)


def _alert(
    s: Session, event: OutboxEvent, user: User, title: str, message: str, *, also_holders_of: str | None = None
) -> None:
    send(
        "security_alert",
        [user.email],
        event,
        name=user.display_name or user.full_name,
        title=title,
        message=message,
        when=when(user),
    )
    if also_holders_of:
        for hid in holders_of(s, also_holders_of, min_scope="ALL"):
            if hid == user.id:
                continue
            h = _user(s, hid)
            send(
                "security_alert",
                [h.email],
                event,
                name=h.display_name or h.full_name,
                title=title,
                message=f"{message} (Account: {user.full_name}.)",
                when=when(h),
            )


@handler("auth.refresh_reuse_detected")
def _reuse(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    if user:
        _alert(
            s,
            event,
            user,
            "Suspicious sign-in activity",
            "A stolen or replayed session token was detected and that session was signed out.",
            also_holders_of="user.session.revoke",
        )


@handler("auth.mfa_recovery_completed")
def _recovery(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    if user:
        _alert(
            s,
            event,
            user,
            "Account recovery used",
            "Your account was recovered with a recovery code. All other sessions were signed out.",
            also_holders_of="user.mfa.reset",
        )


@handler("auth.mfa_recovery_code_used")
def _code_used(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    if user:
        _alert(s, event, user, "Recovery code used", "One of your two-step verification recovery codes was used.")


@handler("auth.mfa_reset_completed")
def _mfa_reset(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    if user:
        _alert(
            s,
            event,
            user,
            "Two-step verification was reset",
            "An administrator reset your two-step verification. Use the setup link we send to set it up again.",
            also_holders_of="user.mfa.reset",
        )


@handler("auth.account_throttled")
def _throttled(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    if user:
        _alert(
            s,
            event,
            user,
            "Sign-in temporarily paused",
            "Repeated failed sign-ins from several networks paused password sign-in for 15 minutes.",
        )


@handler("auth.email_change_requested")
def _email_requested(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    if user is None or not user.proposed_email:
        return
    verify_link, vtok = _token_link(s, event.payload["verification_token_id"], "/verify-email")
    cancel_link, ctok = _token_link(s, event.payload["cancel_token_id"], "/cancel-email-change")
    requester = "you" if event.payload.get("requested_by") == user.id else "an administrator"
    if _usable(vtok):
        minutes = int((vtok.expires_on - vtok.created_on).total_seconds() // 60)
        # The proposed address receives only its verification link (05 §8.6).
        send(
            "email_change_verify",
            [user.proposed_email],
            event,
            name=user.display_name or user.full_name,
            link=verify_link,
            expires_minutes=minutes,
        )
    if _usable(ctok):
        send(
            "email_change_alert",
            [user.email],
            event,
            name=user.display_name or user.full_name,
            proposed=mask_email(user.proposed_email),
            requester=requester,
            link=cancel_link,
        )


@handler("auth.email_change_completed")
def _email_completed(s: Session, event: OutboxEvent) -> None:
    from veda.platform.audit.models import AuditLog

    user = _user(s, event.payload["user_id"])
    if user is None:
        return
    old = None
    if event.payload.get("audit_id"):
        row = s.get(AuditLog, event.payload["audit_id"])
        old = ((row.old_value or {}).get("email")) if row else None
    recipients = [user.email] + ([old] if old and old != "[ERASED]" else [])
    for address in recipients:
        send(
            "email_change_completed",
            [address],
            event,
            name=user.display_name or user.full_name,
            old=mask_email(old) or "your previous address",
            new=mask_email(user.email),
            when=when(user),
        )


@handler("invite.accepted")
def _invite_accepted(s: Session, event: OutboxEvent) -> None:
    user = _user(s, event.payload["user_id"])
    inviter = _user(s, user.created_by) if user else None
    if user is None or inviter is None or inviter.user_type != "HUMAN":
        return
    title = f"{user.full_name} accepted the invitation"
    notify_in_app(
        s,
        event,
        [inviter.id],
        notification_type="INVITE_ACCEPTED",
        title=title,
        entity=("app_user", user.id),
        link_path=f"/admin/users/{user.id}",
    )
    send(
        "digest",
        [inviter.email],
        event,
        name=inviter.display_name or inviter.full_name,
        title=title,
        message=f"{user.full_name} has joined Veda Workspace.",
        link=app_link(f"/admin/users/{user.id}"),
    )


@handler("rbac.sensitive_grant")
def _sensitive_grant(s: Session, event: OutboxEvent) -> None:
    subject = _user(s, event.payload.get("user_id")) if event.payload.get("user_id") else None
    what = f"{subject.full_name} received" if subject else "A role now grants"
    for hid in holders_of(s, "permission.manage", min_scope="ALL"):
        h = _user(s, hid)
        send(
            "security_alert",
            [h.email],
            event,
            name=h.display_name or h.full_name,
            title="Sensitive permission granted",
            message=f"{what} a sensitive permission.",
            when=when(h),
        )


# --- approvals -----------------------------------------------------------------------------------


@handler("approval.requested")
def _approval_requested(s: Session, event: OutboxEvent) -> None:
    from veda.platform.rbac import governance
    from veda.platform.rbac.models import AdminApprovalRequest

    req = s.get(AdminApprovalRequest, event.payload["approval_id"])
    if req is None:
        return
    target = _user(s, req.target_user_id)
    code = governance.permission_for(req)
    approvers = (
        []
        if req.channel == "BREAK_GLASS"
        else [uid for uid in holders_of(s, code, min_scope="ALL") if uid not in (req.requested_by, req.target_user_id)]
    )
    title = f"Approval needed: {req.action_type.replace('_', ' ').title()} for {target.full_name}"
    notify_in_app(
        s,
        event,
        approvers,
        notification_type="APPROVAL_REQUESTED",
        title=title,
        entity=("admin_approval_request", req.id),
        link_path="/approvals",
    )
    for uid in approvers:
        u = _user(s, uid)
        send(
            "approval",
            [u.email],
            event,
            name=u.display_name or u.full_name,
            title=title,
            message=f"{title}. Reason: {req.reason}",
            link=app_link("/approvals"),
        )
    if target and target.status == "ACTIVE":
        send(
            "security_alert",
            [target.email],
            event,
            name=target.display_name or target.full_name,
            title="An account change was requested",
            message=f"A {req.action_type.replace('_', ' ').lower()} was requested for your account and awaits approval.",
            when=when(target),
        )


@handler("approval.decided")
def _approval_decided(s: Session, event: OutboxEvent) -> None:
    from veda.platform.rbac.models import AdminApprovalRequest

    req = s.get(AdminApprovalRequest, event.payload["approval_id"])
    if req is None:
        return
    target = _user(s, req.target_user_id)
    title = f"Request {req.status.lower()}: {req.action_type.replace('_', ' ').title()}"
    recipients = [
        uid for uid in (req.requested_by, req.target_user_id) if _user(s, uid) and _user(s, uid).user_type == "HUMAN"
    ]
    notify_in_app(
        s,
        event,
        recipients,
        notification_type="APPROVAL_DECIDED",
        title=title,
        entity=("admin_approval_request", req.id),
        link_path="/approvals",
    )
    for uid in recipients:
        u = _user(s, uid)
        send(
            "approval",
            [u.email],
            event,
            name=u.display_name or u.full_name,
            title=title,
            message=f"{title} for {target.full_name if target else 'an account'}.",
            link=app_link("/approvals"),
        )


@handler("break_glass.requested")
def _break_glass(s: Session, event: OutboxEvent) -> None:
    from veda.platform.rbac.models import AdminApprovalRequest

    req = s.get(AdminApprovalRequest, event.payload["approval_id"])
    user = _user(s, event.payload["user_id"])
    link, tok = _token_link(s, event.payload["token_id"], "/approvals/cancel")
    if req is None or user is None or not _usable(tok):
        return
    target = _user(s, req.target_user_id)
    send(
        "break_glass_requested",
        [user.email],
        event,
        name=user.display_name or user.full_name,
        action=req.action_type,
        target=target.full_name if target else "an account",
        not_before=clock.to_rfc3339(req.not_before),
        link=link,
    )


def dispatch(s: Session, event: OutboxEvent) -> None:
    fn = HANDLERS.get(event.event_type)
    if fn is None:
        raise LookupError(f"no handler for {event.event_type}")
    fn(s, event)
