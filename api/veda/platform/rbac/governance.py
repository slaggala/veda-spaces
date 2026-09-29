"""Dual control (06 §7.4) and the canonical Founder-governance workflow (06 §7.2, §7.5).

Eligibility is evaluated at request time, at approval time and again at
execution time inside the executing transaction, under the write lock.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db, outbox
from veda.kernel.context import ActorContext, acting, current_actor
from veda.kernel.dto import mask_email
from veda.kernel.errors import ApiError
from veda.kernel.ids import SYSTEM_USER_ID
from veda.platform.auth import mfa as mfa_flows
from veda.platform.auth import security_events
from veda.platform.auth import service as auth_service
from veda.platform.auth.models import UserMfaFactor
from veda.platform.identity.models import User

from . import custodians, guards, registry, resolver
from .models import FOUNDER_ACTIONS, AdminApprovalRequest, Role, UserRole

ACTION_PERMISSION = {"MFA_RESET": "user.mfa.reset", "EMAIL_CHANGE": "user.email.change"}
FOUNDER_PERMISSION = "user.founder.manage"


def permission_for(req: AdminApprovalRequest) -> str:
    return FOUNDER_PERMISSION if req.action_class == "FOUNDER" else ACTION_PERMISSION[req.action_type]


def _has_active_factor(s: Session, user_id: str) -> bool:
    return bool(
        s.execute(
            sa.select(sa.func.count())
            .select_from(UserMfaFactor)
            .where(UserMfaFactor.user_id == user_id, UserMfaFactor.status == "ACTIVE")
        ).scalar()
    )


def structurally_eligible(s: Session, user: User | None, code: str, *, now: datetime | None = None) -> bool:
    """Session-independent parts of 'permission effective': ACTIVE HUMAN, granted, ACTIVE factor, not cooling off."""
    now = now or clock.now()
    if user is None or user.is_deleted or user.status != "ACTIVE" or user.user_type != "HUMAN":
        return False
    if code not in resolver.load_grants(s, user.id).granted:
        return False
    if registry.sensitivity(code) and not _has_active_factor(s, user.id):
        return False
    if user.security_cooling_off_until is not None and user.security_cooling_off_until > now:
        return False
    if code == FOUNDER_PERMISSION and not guards.is_founder(s, user):
        return False
    return True


def eligible_founders(s: Session, *, exclude: set[str]) -> list[User]:
    return [
        u for u in guards.active_founders(s) if u.id not in exclude and structurally_eligible(s, u, FOUNDER_PERMISSION)
    ]


def _expire_if_due(s: Session, req: AdminApprovalRequest) -> None:
    if req.status == "PENDING" and req.expires_on <= db.tx_time(s):
        req.status = "EXPIRED"
        req.status_reason = None
        security_events.record(
            s,
            "APPROVAL_EXPIRED",
            "SUCCESS",
            subject_user_id=req.target_user_id,
            target=("admin_approval_request", req.id),
        )


def _open_request_guard(s: Session, target_id: str, action_type: str, *, founder: bool) -> None:
    q = (
        sa.select(sa.func.count())
        .select_from(AdminApprovalRequest)
        .where(
            AdminApprovalRequest.target_user_id == target_id, AdminApprovalRequest.status.in_(("PENDING", "APPROVED"))
        )
    )
    q = (
        q.where(AdminApprovalRequest.action_class == "FOUNDER")
        if founder
        else q.where(AdminApprovalRequest.action_type == action_type)
    )
    if s.execute(q).scalar():
        raise ApiError(409, "REQUEST_ALREADY_OPEN", "A request for this account is already open.")


# --- governance class (OD-3) -----------------------------------------------------------------
#
# STANDARD_CONTROL < DUAL_CONTROL (holds a sensitive permission, 06 §7.4) < FOUNDER_GOVERNANCE (06 §7.2). Anything
# authorised under a weaker class than the target now holds fails closed when it is executed or completed.

STANDARD_CONTROL, DUAL_CONTROL, FOUNDER_GOVERNANCE = "STANDARD_CONTROL", "DUAL_CONTROL", "FOUNDER_GOVERNANCE"
GOVERNANCE_RANK = {STANDARD_CONTROL: 0, DUAL_CONTROL: 1, FOUNDER_GOVERNANCE: 2}


def governance_class(s: Session, user: User) -> str:
    if user.protection_level == "FOUNDER":
        return FOUNDER_GOVERNANCE
    return DUAL_CONTROL if resolver.is_privileged(s, user.id) else STANDARD_CONTROL


def proposal_authorised_class(s: Session, user: User) -> str | None:
    """The class under which the pending email proposal was authorised; None when self-requested.

    An approved request starts the change in the transaction that executes it, so the proposal's
    requested_on equals that request's executed_on."""
    if user.proposed_email_requested_by == user.id:
        return None
    kinds = set(
        s.execute(
            sa.select(AdminApprovalRequest.action_type).where(
                AdminApprovalRequest.target_user_id == user.id,
                AdminApprovalRequest.status == "EXECUTED",
                AdminApprovalRequest.action_type.in_(("EMAIL_CHANGE", "FOUNDER_EMAIL_CHANGE")),
                AdminApprovalRequest.requested_by == user.proposed_email_requested_by,
                AdminApprovalRequest.executed_on == user.proposed_email_requested_on,
            )
        ).scalars()
    )
    if "FOUNDER_EMAIL_CHANGE" in kinds:
        return FOUNDER_GOVERNANCE
    return DUAL_CONTROL if "EMAIL_CHANGE" in kinds else STANDARD_CONTROL


def proposal_still_authorised(s: Session, user: User) -> bool:
    authorised = proposal_authorised_class(s, user)
    return authorised is None or GOVERNANCE_RANK[authorised] >= GOVERNANCE_RANK[governance_class(s, user)]


def revalidate_after_escalation(s: Session, user: User, before: str, reason: str) -> None:
    """Called after any change that can raise the target's governance class (promotion, roles, permissions):
    work authorised under the weaker class is withdrawn in the same transaction (OD-3, RR-03)."""
    after = governance_class(s, user)
    if GOVERNANCE_RANK[after] <= GOVERNANCE_RANK[before]:
        return
    if after == FOUNDER_GOVERNANCE:
        cancel_open_standard_requests(s, user.id, reason)
    if user.proposed_email and not proposal_still_authorised(s, user):
        proposed = user.proposed_email
        auth_service.clear_proposal(s, user)
        security_events.record(
            s,
            "EMAIL_CHANGE_CANCELLED",
            "SUCCESS",
            subject_user_id=user.id,
            detail={"proposed_email": mask_email(proposed), "reason": reason, "status": f"{before}->{after}"},
        )


# --- standard dual control (06 §7.4) ----------------------------------------------------------


def request_standard(
    s: Session, ctx, target: User, action_type: str, reason: str, payload: dict
) -> AdminApprovalRequest:
    now = db.tx_time(s)
    _open_request_guard(s, target.id, action_type, founder=False)
    req = AdminApprovalRequest(
        action_class="STANDARD",
        action_type=action_type,
        channel="IN_APP",
        target_user_id=target.id,
        requested_by=ctx.user.id,
        request_payload=payload,
        reason=reason,
        status="PENDING",
        expires_on=now + settings().approval_expiry,
    )
    s.add(req)
    s.flush()
    security_events.record(
        s,
        "APPROVAL_REQUESTED",
        "SUCCESS",
        subject_user_id=target.id,
        permission_code=ACTION_PERMISSION[action_type],
        target=("admin_approval_request", req.id),
        detail={"action": action_type},
    )
    if action_type == "MFA_RESET":
        security_events.record(
            s,
            "ADMIN_MFA_RESET_REQUESTED",
            "SUCCESS",
            subject_user_id=target.id,
            target=("admin_approval_request", req.id),
        )
    outbox.enqueue(s, "approval.requested", "admin_approval_request", req.id, approval_id=req.id)
    return req


def standard_still_permitted(s: Session, req: AdminApprovalRequest) -> User:
    """G11 and the requester's G9 are re-evaluated when a STANDARD request is decided and executed (06 §7.4):
    a target promoted to Founder after the request was raised is governed by the Founder workflow only (IR-04)."""
    target = s.get(User, req.target_user_id, execution_options={"include_deleted": True})
    if target is None or target.is_deleted:
        raise ApiError(409, "INVALID_STATE", "The target account no longer exists.")
    guards.g11_not_founder(target)
    requester = resolver.load_grants(s, req.requested_by)
    # G9 compares against what the requester is granted (suspension ignored), like any account-control check.
    guards.g9_not_stronger(
        s,
        resolver.Resolution(
            user_id=req.requested_by, authz_version=requester.authz_version, effective=dict(requester.granted)
        ),
        target.id,
    )
    return target


def cancel_open_standard_requests(s: Session, target_id: str, reason: str) -> None:
    """A new Founder has no open STANDARD requests: they would bypass the Founder workflow (IR-04)."""
    now = db.tx_time(s)
    for req in s.execute(
        sa.select(AdminApprovalRequest).where(
            AdminApprovalRequest.target_user_id == target_id,
            AdminApprovalRequest.action_class == "STANDARD",
            AdminApprovalRequest.status.in_(("PENDING", "APPROVED")),
        )
    ).scalars():
        req.status, req.status_reason, req.decided_on = "CANCELLED", reason, now
        security_events.record(
            s,
            "APPROVAL_CANCELLED",
            "SUCCESS",
            subject_user_id=target_id,
            target=("admin_approval_request", req.id),
            detail={"reason": reason},
        )


def _execute_standard(s: Session, req: AdminApprovalRequest) -> None:
    target = standard_still_permitted(s, req)
    if req.action_type == "MFA_RESET":
        mfa_flows.admin_reset(s, target)
        security_events.record(
            s,
            "ADMIN_MFA_RESET_COMPLETED",
            "SUCCESS",
            subject_user_id=target.id,
            target=("admin_approval_request", req.id),
        )
        outbox.enqueue(s, "auth.mfa_reset_completed", "app_user", target.id, user_id=target.id)
    elif req.action_type == "EMAIL_CHANGE":
        auth_service.start_email_change(s, target, req.request_payload["new_email"], requested_by=req.requested_by)


# --- Founder-level requests (06 §7.2) ----------------------------------------------------------


def is_restore(action: str, payload: dict | None) -> bool:
    return action == "FOUNDER_STATUS_CHANGE" and (payload or {}).get("status") == "RESTORE"


def _refuse_break_glass_restore(action: str, payload: dict) -> None:
    """OD-2: restoring a deleted Founder needs two distinct eligible Founders in-app. The approved break-glass
    policy (06 §7.5) does not cover restoration, so neither break-glass channel may carry it (RR-02)."""
    if is_restore(action, payload):
        raise ApiError(
            409, "SECOND_FOUNDER_REQUIRED", "Restoring a Founder needs a second eligible Founder to approve in-app."
        )


def _validate_founder_action(s: Session, action: str, target: User, payload: dict) -> None:
    founders = guards.active_founders(s)
    is_target_founder = guards.is_founder(s, target)
    # Only a restore acts on a deleted account; every other action requires a live one (OD-2, OD-3).
    if target.is_deleted != is_restore(action, payload):
        raise ApiError(
            409,
            "INVALID_STATE",
            "The target account no longer exists." if target.is_deleted else "The target account is not deleted.",
        )
    if action == "GRANT_FOUNDER":
        if is_target_founder:
            raise ApiError(409, "INVALID_STATE", "This user is already a Founder.")
        if target.status != "ACTIVE" or target.user_type != "HUMAN":
            raise ApiError(409, "INVALID_STATE", "Only active staff can become Founders.")
        return
    if not is_target_founder:
        raise ApiError(409, "INVALID_STATE", "The target is not a Founder.")
    last = len(founders) == 1 and founders[0].id == target.id
    if action == "REVOKE_FOUNDER" and last:
        raise ApiError(409, "LAST_FOUNDER", "The last Founder cannot be removed.")
    if action == "FOUNDER_STATUS_CHANGE":
        status = payload.get("status")
        if status not in ("DISABLED", "ACTIVE", "UNLOCK", "DELETE", "RESTORE"):
            raise ApiError(422, "VALIDATION_FAILED", "status must be DISABLED, ACTIVE, UNLOCK, DELETE or RESTORE.")
        if status in ("DISABLED", "DELETE") and last:
            raise ApiError(409, "LAST_FOUNDER", "The last Founder cannot be deactivated or deleted.")
    if action == "FOUNDER_EMAIL_CHANGE" and not payload.get("new_email"):
        raise ApiError(422, "VALIDATION_FAILED", "new_email is required.")


def request_founder_action(
    s: Session, ctx, action: str, target: User, reason: str, payload: dict
) -> AdminApprovalRequest:
    if action not in FOUNDER_ACTIONS:
        raise ApiError(422, "VALIDATION_FAILED", "Unknown Founder action.")
    if not structurally_eligible(s, ctx.user, FOUNDER_PERMISSION) or not ctx.has(FOUNDER_PERMISSION):
        raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "Only an eligible Founder can request Founder-level actions.")
    guards.lock_governance(s)
    _validate_founder_action(s, action, target, payload)  # LAST_FOUNDER is reported first (TD-G G11)
    if target.id == ctx.user.id and action != "REVOKE_FOUNDER":
        raise ApiError(403, "SELF_MODIFICATION_DENIED", "Only a self step-down (REVOKE_FOUNDER) may target yourself.")
    _open_request_guard(s, target.id, action, founder=True)
    now = db.tx_time(s)
    approvers = eligible_founders(s, exclude={ctx.user.id, target.id})
    channel = "IN_APP" if approvers else "BREAK_GLASS"
    if channel == "BREAK_GLASS":
        _refuse_break_glass_restore(action, payload)
    req = AdminApprovalRequest(
        action_class="FOUNDER",
        action_type=action,
        channel=channel,
        target_user_id=target.id,
        requested_by=ctx.user.id,
        request_payload=payload,
        reason=reason,
        status="PENDING",
        expires_on=now + (settings().approval_expiry if channel == "IN_APP" else settings().break_glass_delay * 3),
        not_before=None if channel == "IN_APP" else now + settings().break_glass_delay,
    )
    s.add(req)
    s.flush()
    security_events.record(
        s,
        "FOUNDER_ACTION_REQUESTED",
        "SUCCESS",
        subject_user_id=target.id,
        permission_code=FOUNDER_PERMISSION,
        target=("admin_approval_request", req.id),
        detail={"action": action, "channel": channel},
    )
    if channel == "BREAK_GLASS":
        security_events.record(
            s,
            "BREAK_GLASS_REQUESTED",
            "SUCCESS",
            subject_user_id=target.id,
            target=("admin_approval_request", req.id),
            detail={"action": action, "stage": "single_founder"},
        )
        _issue_cancel_links(s, req)
    outbox.enqueue(s, "approval.requested", "admin_approval_request", req.id, approval_id=req.id)
    return req


def _issue_cancel_links(s: Session, req: AdminApprovalRequest) -> None:
    """Every ACTIVE Founder and the target get a signed cancel link (06 §7.5 step 5)."""
    notified = {u.id: u for u in guards.active_founders(s)}
    target = s.get(User, req.target_user_id)
    if target is not None and target.status == "ACTIVE":
        notified[target.id] = target
    for user in notified.values():
        tok, _ = auth_service.create_action_token(
            s, user, "APPROVAL_CANCEL", ttl=settings().break_glass_delay, expires_on=req.expires_on
        )
        s.flush()
        outbox.enqueue(
            s,
            "break_glass.requested",
            "admin_approval_request",
            req.id,
            approval_id=req.id,
            user_id=user.id,
            token_id=tok.id,
        )


def requester_still_eligible(s: Session, req: AdminApprovalRequest) -> bool:
    if req.channel == "BREAK_GLASS" and req.requested_by == SYSTEM_USER_ID:
        return True  # custodian-requested (full break-glass); separation checked by the CLI
    requester = s.get(User, req.requested_by)
    return structurally_eligible(s, requester, permission_for(req))


def _execute_founder(s: Session, req: AdminApprovalRequest) -> None:
    target = s.get(User, req.target_user_id, execution_options={"include_deleted": True})
    payload = req.request_payload or {}
    now = db.tx_time(s)
    inv = guards.InvariantGuard(s)
    if target is None:
        raise ApiError(409, "INVALID_STATE", "The target account no longer exists.")
    # The action must still make sense against the current state, not the state when it was requested.
    _validate_founder_action(s, req.action_type, target, payload)
    if req.channel == "BREAK_GLASS":
        _refuse_break_glass_restore(req.action_type, payload)
    if req.channel == "BREAK_GLASS" and req.requested_by == SYSTEM_USER_ID:
        require_break_glass_mode(s, target.id)
    founder_roles = s.execute(sa.select(Role).where(Role.grant_path == registry.FOUNDER_WORKFLOW_ONLY)).scalars().all()
    if req.action_type == "GRANT_FOUNDER":
        before = governance_class(s, target)
        target.protection_level = "FOUNDER"
        for role in founder_roles:
            if not s.execute(
                sa.select(UserRole).where(UserRole.user_id == target.id, UserRole.role_id == role.id)
            ).first():
                s.add(UserRole(user_id=target.id, role_id=role.id, reason=req.reason[:500]))
        resolver.bump_authz_version(target)
        s.flush()
        revalidate_after_escalation(s, target, before, "TARGET_BECAME_FOUNDER")
        security_events.record(
            s, "FOUNDER_TRANSITION", "SUCCESS", subject_user_id=target.id, detail={"action": "GRANT"}
        )
    elif req.action_type == "REVOKE_FOUNDER":
        for ur in s.execute(
            sa.select(UserRole).where(
                UserRole.user_id == target.id, UserRole.role_id.in_([r.id for r in founder_roles])
            )
        ).scalars():
            ur.is_deleted = True
        target.protection_level = "STANDARD"
        for role_id in payload.get("post_roles") or []:
            role = s.get(Role, role_id)
            if role is None or role.grant_path == registry.FOUNDER_WORKFLOW_ONLY or not role.is_assignable:
                raise ApiError(422, "VALIDATION_FAILED", "post_roles contains an invalid role.")
            if not s.execute(
                sa.select(UserRole).where(UserRole.user_id == target.id, UserRole.role_id == role_id)
            ).first():
                s.add(UserRole(user_id=target.id, role_id=role_id, reason=req.reason[:500]))
        resolver.bump_authz_version(target)
        security_events.record(
            s, "FOUNDER_TRANSITION", "SUCCESS", subject_user_id=target.id, detail={"action": "REVOKE"}
        )
    elif req.action_type == "FOUNDER_MFA_RESET":
        mfa_flows.admin_reset(s, target)
        outbox.enqueue(s, "auth.mfa_reset_completed", "app_user", target.id, user_id=target.id)
    elif req.action_type == "FOUNDER_STATUS_CHANGE":
        from .users import apply_status, restore_effects

        if payload["status"] == "RESTORE":
            restore_effects(s, target)
            security_events.record(
                s,
                "FOUNDER_TRANSITION",
                "SUCCESS",
                subject_user_id=target.id,
                target=("admin_approval_request", req.id),
                detail={"action": "RESTORE"},
            )
        else:
            apply_status(s, target, payload["status"], reason=req.reason)
    elif req.action_type == "FOUNDER_EMAIL_CHANGE":
        auth_service.start_email_change(s, target, payload["new_email"], requested_by=req.requested_by)
    inv.check()
    req.executed_on = now


def execute(s: Session, req: AdminApprovalRequest) -> None:
    """Run the approved action in this transaction; FAILED (nothing applied) on ineligibility or invariant breach."""
    if not requester_still_eligible(s, req):
        req.status, req.status_reason, req.decided_on = "FAILED", "REQUESTER_INELIGIBLE", db.tx_time(s)
        return
    savepoint = s.begin_nested()
    try:
        if req.action_class == "FOUNDER":
            _execute_founder(s, req)
        else:
            _execute_standard(s, req)
        savepoint.commit()
    except ApiError as err:
        savepoint.rollback()
        req.status = "FAILED"
        req.status_reason = err.code[:30]
        security_events.record(
            s,
            "FOUNDER_ACTION_FAILED" if req.action_class == "FOUNDER" else "APPROVAL_DENIED",
            "FAILURE",
            subject_user_id=req.target_user_id,
            target=("admin_approval_request", req.id),
            detail={"reason": err.code},
        )
        return
    req.status = "EXECUTED"
    req.executed_on = db.tx_time(s)
    if req.action_class == "FOUNDER":
        security_events.record(
            s,
            "FOUNDER_ACTION_EXECUTED",
            "SUCCESS",
            subject_user_id=req.target_user_id,
            target=("admin_approval_request", req.id),
            detail={"action": req.action_type},
        )
    outbox.enqueue(s, "approval.decided", "admin_approval_request", req.id, approval_id=req.id)


def approve(s: Session, ctx, req: AdminApprovalRequest, reason: str) -> AdminApprovalRequest:
    from veda.platform.auth.request_auth import record_sensitive_action, require_step_up

    guards.lock_governance(s)
    # The row was read before the lock; a concurrent decision or promotion may have changed it meanwhile.
    s.refresh(req)
    _expire_if_due(s, req)
    if req.status != "PENDING":
        raise ApiError(409, "INVALID_STATE", "This request can no longer be decided.")
    code = permission_for(req)
    if ctx.user.id in (req.requested_by, req.target_user_id):
        raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "You can't decide a request you made or that is about you.")
    if req.channel == "BREAK_GLASS":
        raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "This request is approved by a break-glass custodian.")
    if not ctx.has(code) or not structurally_eligible(s, ctx.user, code):
        raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "You are not eligible to decide this request.")
    try:
        guards.g9_not_stronger(s, ctx.res, req.target_user_id)
    except ApiError as err:
        raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "The target holds permissions you don't have.") from err
    require_step_up(ctx)
    now = db.tx_time(s)
    if not requester_still_eligible(s, req):
        req.status, req.status_reason, req.decided_on = "CANCELLED", "REQUESTER_INELIGIBLE", now
        security_events.record(
            s,
            "FOUNDER_ACTION_CANCELLED" if req.action_class == "FOUNDER" else "APPROVAL_CANCELLED",
            "SUCCESS",
            subject_user_id=req.target_user_id,
            target=("admin_approval_request", req.id),
            detail={"reason": "REQUESTER_INELIGIBLE"},
        )
        return req
    req.status = "APPROVED"
    req.approver_user_id = ctx.user.id
    req.decided_on = now
    req.decision_reason = reason
    s.flush()
    if req.action_class == "FOUNDER":
        security_events.record(
            s,
            "FOUNDER_ACTION_APPROVED",
            "SUCCESS",
            subject_user_id=req.target_user_id,
            permission_code=code,
            target=("admin_approval_request", req.id),
        )
    else:
        security_events.record(
            s,
            "APPROVAL_APPROVED",
            "SUCCESS",
            subject_user_id=req.target_user_id,
            permission_code=code,
            target=("admin_approval_request", req.id),
        )
        if req.action_type == "MFA_RESET":
            security_events.record(
                s,
                "ADMIN_MFA_RESET_APPROVED",
                "SUCCESS",
                subject_user_id=req.target_user_id,
                target=("admin_approval_request", req.id),
            )
    record_sensitive_action(
        s,
        ctx,
        code,
        action=f"approve:{req.action_type}",
        target=("app_user", req.target_user_id),
        subject_user_id=req.target_user_id,
    )
    execute(s, req)
    return req


def deny(s: Session, ctx, req: AdminApprovalRequest, reason: str) -> AdminApprovalRequest:
    from veda.platform.auth.request_auth import record_sensitive_action, require_step_up

    guards.lock_governance(s)
    s.refresh(req)
    _expire_if_due(s, req)
    if req.status != "PENDING":
        raise ApiError(409, "INVALID_STATE", "This request can no longer be decided.")
    code = permission_for(req)
    if (
        ctx.user.id in (req.requested_by, req.target_user_id)
        or not ctx.has(code)
        or not structurally_eligible(s, ctx.user, code)
    ):
        raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "You are not eligible to decide this request.")
    require_step_up(ctx)
    req.status, req.approver_user_id, req.decided_on, req.decision_reason = "DENIED", ctx.user.id, db.tx_time(s), reason
    record_sensitive_action(
        s,
        ctx,
        code,
        action=f"deny:{req.action_type}",
        target=("app_user", req.target_user_id),
        subject_user_id=req.target_user_id,
    )
    event = "FOUNDER_ACTION_DENIED" if req.action_class == "FOUNDER" else "APPROVAL_DENIED"
    security_events.record(
        s,
        event,
        "SUCCESS",
        subject_user_id=req.target_user_id,
        permission_code=code,
        target=("admin_approval_request", req.id),
    )
    if req.action_type == "MFA_RESET":
        security_events.record(
            s,
            "ADMIN_MFA_RESET_DENIED",
            "SUCCESS",
            subject_user_id=req.target_user_id,
            target=("admin_approval_request", req.id),
        )
    outbox.enqueue(s, "approval.decided", "admin_approval_request", req.id, approval_id=req.id)
    return req


def cancel(s: Session, ctx, req: AdminApprovalRequest) -> AdminApprovalRequest:
    _expire_if_due(s, req)
    if req.requested_by != ctx.user.id:
        raise ApiError(403, "PERMISSION_DENIED", "Only the requester can cancel this request.")
    if req.status not in ("PENDING", "APPROVED"):
        raise ApiError(409, "INVALID_STATE", "This request can no longer be cancelled.")
    req.status, req.decided_on = "CANCELLED", db.tx_time(s)
    from veda.platform.auth.request_auth import record_sensitive_action

    record_sensitive_action(
        s,
        ctx,
        permission_for(req),
        action=f"cancel:{req.action_type}",
        target=("app_user", req.target_user_id),
        subject_user_id=req.target_user_id,
    )
    event = "FOUNDER_ACTION_CANCELLED" if req.action_class == "FOUNDER" else "APPROVAL_CANCELLED"
    security_events.record(
        s, event, "SUCCESS", subject_user_id=req.target_user_id, target=("admin_approval_request", req.id)
    )
    auth_service_invalidate_cancel_links(s, req)
    return req


def cancel_by_link(s: Session, raw_token: str) -> AdminApprovalRequest:
    """A notified Founder or the target cancels a break-glass request through its signed link (06 §7.5)."""
    tok = auth_service.consume_action_token(s, raw_token, "APPROVAL_CANCEL", "EMAIL_TOKEN_INVALID")
    # Cancel links are issued in the request's transaction with expires_on = the request's expires_on.
    candidates = (
        s.execute(
            sa.select(AdminApprovalRequest).where(
                AdminApprovalRequest.channel == "BREAK_GLASS",
                AdminApprovalRequest.status.in_(("PENDING", "APPROVED")),
                AdminApprovalRequest.expires_on == tok.expires_on,
            )
        )
        .scalars()
        .all()
    )
    req = next((c for c in candidates if _token_belongs(s, c, tok.id)), None)
    if req is None:
        raise ApiError(400, "EMAIL_TOKEN_INVALID", "This link has expired or was already used.")
    with acting(
        s,
        ActorContext(
            actor_id=tok.user_id,
            via="API",
            request_id=current_actor().request_id,
            ip=current_actor().ip,
            user_agent=current_actor().user_agent,
        ),
    ):
        tok.used_on = db.tx_time(s)
        req.status, req.status_reason, req.decided_on = "CANCELLED", "CANCELLED_BY_NOTIFIED_PARTY", db.tx_time(s)
        security_events.record(
            s,
            "BREAK_GLASS_CANCELLED",
            "SUCCESS",
            subject_user_id=req.target_user_id,
            target=("admin_approval_request", req.id),
        )
        auth_service_invalidate_cancel_links(s, req)
    return req


def _token_belongs(s: Session, req: AdminApprovalRequest, token_id: str) -> bool:
    from veda.platform.notifications.models import OutboxEvent

    rows = (
        s.execute(
            sa.select(OutboxEvent.payload).where(
                OutboxEvent.event_type == "break_glass.requested", OutboxEvent.aggregate_id == req.id
            )
        )
        .scalars()
        .all()
    )
    return any((p or {}).get("token_id") == token_id for p in rows)


def auth_service_invalidate_cancel_links(s: Session, req: AdminApprovalRequest) -> None:
    from veda.platform.auth.models import UserActionToken
    from veda.platform.notifications.models import OutboxEvent

    token_ids = [
        (p or {}).get("token_id")
        for p in s.execute(
            sa.select(OutboxEvent.payload).where(
                OutboxEvent.event_type == "break_glass.requested", OutboxEvent.aggregate_id == req.id
            )
        ).scalars()
    ]
    now = db.tx_time(s)
    for tid in filter(None, token_ids):
        tok = s.get(UserActionToken, tid)
        if tok and tok.used_on is None and tok.invalidated_on is None:
            tok.invalidated_on = now


# --- break-glass (CLI, 06 §7.5) ----------------------------------------------------------------


def custodian_human(arn: str) -> str:
    human = custodians.human_for(arn)
    if not human:
        raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "This principal is not a registered break-glass custodian.")
    return human


def require_break_glass_mode(s: Session, target_id: str) -> None:
    """Custodian break-glass exists only for the case where no eligible Founder other than the target can act
    (06 §7.2.2, §7.2.4). While one exists, the in-app Founder workflow is the only path (IR-05)."""
    if eligible_founders(s, exclude={target_id}):
        raise ApiError(
            409,
            "INVALID_STATE",
            "An eligible Founder can act in the app; custodian break-glass is not available.",
            extra={"reason": "FOUNDER_AVAILABLE"},
        )


def break_glass_request(
    s: Session, *, action: str, target: User, reason: str, principal_arn: str, payload: dict
) -> AdminApprovalRequest:
    human = custodian_human(principal_arn)
    if human == target.id:
        raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "A custodian cannot act on a request targeting themselves.")
    guards.lock_governance(s)
    try:
        require_break_glass_mode(s, target.id)
    except ApiError:
        security_events.defer(
            "BREAK_GLASS_REQUESTED",
            "FAILURE",
            subject_user_id=target.id,
            failure_reason="POLICY",
            detail={"action": action, "reason": "FOUNDER_AVAILABLE"},
        )
        raise
    _validate_founder_action(s, action, target, payload)
    _refuse_break_glass_restore(action, payload)
    _open_request_guard(s, target.id, action, founder=True)
    now = db.tx_time(s)
    req = AdminApprovalRequest(
        action_class="FOUNDER",
        action_type=action,
        channel="BREAK_GLASS",
        target_user_id=target.id,
        requested_by=SYSTEM_USER_ID,
        request_payload=payload,
        reason=reason,
        status="PENDING",
        external_requester_ref=principal_arn,
        expires_on=now + settings().break_glass_delay * 3,
        not_before=now + settings().break_glass_delay,
    )
    s.add(req)
    s.flush()
    security_events.record(
        s,
        "BREAK_GLASS_REQUESTED",
        "SUCCESS",
        subject_user_id=target.id,
        target=("admin_approval_request", req.id),
        detail={"action": action, "stage": "custodian"},
    )
    _issue_cancel_links(s, req)
    outbox.enqueue(s, "approval.requested", "admin_approval_request", req.id, approval_id=req.id)
    return req


def break_glass_approve(s: Session, req: AdminApprovalRequest, *, principal_arn: str) -> AdminApprovalRequest:
    _expire_if_due(s, req)
    if req.channel != "BREAK_GLASS" or req.status != "PENDING":
        raise ApiError(409, "INVALID_STATE", "This request is not awaiting a custodian.")
    human = custodian_human(principal_arn)
    if req.requested_by == SYSTEM_USER_ID:
        guards.lock_governance(s)
        require_break_glass_mode(s, req.target_user_id)
    requester_human = (
        custodians.human_for(req.external_requester_ref) if req.external_requester_ref else req.requested_by
    )
    if human in (requester_human, req.target_user_id) or principal_arn == req.external_requester_ref:
        security_events.record(
            s,
            "BREAK_GLASS_APPROVED",
            "FAILURE",
            subject_user_id=req.target_user_id,
            target=("admin_approval_request", req.id),
            detail={"reason": "SAME_HUMAN"},
        )
        raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "Requester and approver must be different humans.")
    req.status = "APPROVED"
    req.external_approver_ref = principal_arn
    req.external_approver_human = human[:200]
    req.decided_on = db.tx_time(s)
    security_events.record(
        s,
        "BREAK_GLASS_APPROVED",
        "SUCCESS",
        subject_user_id=req.target_user_id,
        target=("admin_approval_request", req.id),
    )
    return req


def break_glass_execute(s: Session, req: AdminApprovalRequest) -> AdminApprovalRequest:
    now = db.tx_time(s)
    if req.channel != "BREAK_GLASS" or req.status != "APPROVED":
        raise ApiError(409, "INVALID_STATE", "This request is not approved.")
    if req.not_before is not None and now < req.not_before:
        raise ApiError(409, "INVALID_STATE", f"Executes no earlier than {clock.to_rfc3339(req.not_before)}.")
    guards.lock_governance(s)
    execute(s, req)
    if req.status == "EXECUTED":
        security_events.record(
            s,
            "BREAK_GLASS_EXECUTED",
            "SUCCESS",
            subject_user_id=req.target_user_id,
            target=("admin_approval_request", req.id),
        )
    return req


# --- presentation ---------------------------------------------------------------------------------


def present(s: Session, req: AdminApprovalRequest, viewer_id: str | None = None) -> dict:
    target = s.get(User, req.target_user_id, execution_options={"include_deleted": True})
    requester = s.get(User, req.requested_by, execution_options={"include_deleted": True})
    approver = (
        s.get(User, req.approver_user_id, execution_options={"include_deleted": True}) if req.approver_user_id else None
    )
    payload = dict(req.request_payload or {})
    if "new_email" in payload:
        payload = {**payload, "new_email": mask_email(payload["new_email"])}
    can_decide = False
    if (
        viewer_id
        and req.status == "PENDING"
        and req.channel == "IN_APP"
        and viewer_id not in (req.requested_by, req.target_user_id)
    ):
        viewer = s.get(User, viewer_id)
        can_decide = structurally_eligible(s, viewer, permission_for(req))
    return {
        "id": req.id,
        "action_class": req.action_class,
        "action_type": req.action_type,
        "channel": req.channel,
        "status": req.status,
        "status_reason": req.status_reason,
        "target": {
            "id": target.id,
            "display_name": target.display_name or target.full_name,
            "email": mask_email(target.email),
        }
        if target
        else None,
        "target_user": {
            "id": target.id,
            "display_name": target.display_name or target.full_name,
            "email": mask_email(target.email),
        }
        if target
        else None,
        "requested_by": {"id": requester.id, "display_name": requester.display_name or requester.full_name}
        if requester
        else None,
        "approver": {"id": approver.id, "display_name": approver.display_name or approver.full_name}
        if approver
        else None,
        "reason": req.reason,
        "decision_reason": req.decision_reason,
        "request_payload": payload,
        "not_before": clock.to_rfc3339(req.not_before),
        "expires_on": clock.to_rfc3339(req.expires_on),
        "decided_on": clock.to_rfc3339(req.decided_on),
        "executed_on": clock.to_rfc3339(req.executed_on),
        "created_on": clock.to_rfc3339(req.created_on),
        "can_decide": can_decide,
        "version": req.version,
    }
