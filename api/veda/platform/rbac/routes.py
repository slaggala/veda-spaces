"""Users, approvals, Founder actions, roles and permissions (08 §5, §6)."""

from __future__ import annotations

from typing import Annotated, Literal

import sqlalchemy as sa
from pydantic import Field

from veda.kernel import clock
from veda.kernel.dto import Closed, Email, Id, Instant, Query, Reason, TimeZone, csv, optional_text, text
from veda.kernel.errors import ApiError, field_error, not_found
from veda.kernel.http import Api, Req, no_content, offset_meta, ok
from veda.platform.identity import service as identity
from veda.platform.identity.models import User

from . import governance, roles, users
from .models import AdminApprovalRequest, Permission, Role

users_api = Api("users", "/api/v1/users", tags=("users",))
approvals_api = Api("approvals", "/api/v1", tags=("approvals",))
roles_api = Api("roles", "/api/v1/roles", tags=("roles",))
permissions_api = Api("permissions", "/api/v1/permissions", tags=("permissions",))

MASS_ASSIGNMENT_FIELDS = frozenset(
    {
        "email",
        "proposed_email",
        "password",
        "status",
        "roles",
        "permissions",
        "mfa_required",
        "protection_level",
        "is_founder",
    }
)


class Paging(Query):
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25


# --- users ------------------------------------------------------------------------------------


class UsersQuery(Paging):
    q: str | None = None
    status: str | None = None
    role_id: Id | None = None
    protection_level: Literal["STANDARD", "FOUNDER"] | None = None
    mfa: Literal["enrolled", "required_not_enrolled", "none"] | None = None
    include_deleted: bool = False
    sort: str | None = None


@users_api.route("GET", "", permission="user.read", query=UsersQuery, write=False, requirement="USER-001")
def list_users(req: Req):
    q = req.query
    if q.include_deleted and not req.ctx.has("user.restore"):
        raise ApiError(403, "PERMISSION_DENIED", "Requires user.restore.", extra={"permission": "user.restore"})
    stmt = sa.select(User).where(User.user_type == "HUMAN").execution_options(include_deleted=q.include_deleted)
    if q.q:
        for token in q.q.lower().split():
            like = f"%{token}%"
            stmt = stmt.where(sa.or_(sa.func.lower(User.full_name).like(like), User.email_normalized.like(like)))
    if q.status:
        stmt = stmt.where(User.status.in_(csv(q.status)))
    if q.protection_level:
        stmt = stmt.where(User.protection_level == q.protection_level)
    if q.role_id:
        from .models import UserRole

        stmt = stmt.where(User.id.in_(sa.select(UserRole.user_id).where(UserRole.role_id == q.role_id)))
    sorts = {
        "full_name": User.full_name.asc(),
        "-full_name": User.full_name.desc(),
        "-created_on": User.created_on.desc(),
        "created_on": User.created_on.asc(),
        "-last_login_on": User.last_login_on.desc(),
    }
    if q.sort and q.sort not in sorts:
        raise ApiError(
            422,
            "INVALID_QUERY_PARAM",
            "Unsupported sort.",
            errors=[field_error("sort", "INVALID_QUERY_PARAM", "Unsupported sort.")],
        )
    rows = req.session.execute(stmt.order_by(sorts.get(q.sort or "full_name"), User.id)).scalars().all()
    items = [identity.user_list_item(req.session, u) for u in rows]
    if q.mfa:
        items = [
            i
            for i in items
            if (q.mfa == "enrolled" and i["mfa"]["enrolled"])
            or (q.mfa == "required_not_enrolled" and i["mfa"]["required"] and not i["mfa"]["enrolled"])
            or (q.mfa == "none" and not i["mfa"]["required"] and not i["mfa"]["enrolled"])
        ]
    total = len(items)
    page = items[(q.page - 1) * q.page_size : q.page * q.page_size]
    meta, links = offset_meta(q.page, q.page_size, total, "/api/v1/users", q.model_dump())
    return ok(page, meta=meta, links=links)


class InviteIn(Closed):
    email: Email
    full_name: Annotated[str, text(150, min_len=1)]
    display_name: Annotated[str | None, optional_text(80)] = None
    phone: Annotated[str | None, optional_text(30)] = None
    timezone: TimeZone | None = None
    role_ids: list[Id] = []


@users_api.route(
    "POST",
    "",
    permission="user.create",
    body=InviteIn,
    status=201,
    idempotent_create=True,
    requirement="USER-001",
    summary="Invite a user",
)
def invite(req: Req):
    user = users.invite(req.session, req.ctx, req.body)
    req.session.flush()
    return ok(identity.user_detail(req.session, user), status=201)


def _target(req: Req, user_id: str, *, include_deleted: bool = False) -> User:
    return users.load_target(req.session, user_id, include_deleted=include_deleted)


class UserGetQuery(Query):
    include_deleted: bool = False


@users_api.route("GET", "/<user_id>", permission="user.read", query=UserGetQuery, write=False, requirement="USER-001")
def get_user(req: Req, user_id: str):
    include = req.query.include_deleted and req.ctx.has("user.restore")
    return ok(identity.user_detail(req.session, _target(req, user_id, include_deleted=include)))


class UserProfilePatch(Closed):
    __not_updatable__ = MASS_ASSIGNMENT_FIELDS
    full_name: Annotated[str | None, text(150, min_len=1)] = None
    display_name: Annotated[str | None, optional_text(80)] = None
    phone: Annotated[str | None, optional_text(30)] = None
    timezone: TimeZone | None = None
    locale: Annotated[str | None, text(10, min_len=2)] = None


@users_api.route(
    "PATCH",
    "/<user_id>",
    permission="user.profile.update",
    body=UserProfilePatch,
    if_match=True,
    requirement="RBAC-019",
    summary="Edit another user's profile fields only",
)
def patch_user(req: Req, user_id: str):
    target = _target(req, user_id)
    req.require_version(target.version)
    users.update_profile(req.session, req.ctx, target, req.body)
    req.session.flush()
    return ok(identity.user_detail(req.session, target))


class EmailChangeAdminIn(Closed):
    new_email: Email
    reason: Reason


@users_api.route(
    "POST",
    "/<user_id>/email-change",
    permission="user.email.change",
    body=EmailChangeAdminIn,
    if_match=True,
    status=202,
    requirement="USER-007",
)
def email_change(req: Req, user_id: str):
    target = _target(req, user_id)
    req.require_version(target.version)
    return ok(users.admin_email_change(req.session, req.ctx, target, req.body.new_email, req.body.reason), status=202)


class StatusIn(Closed):
    status: Literal["DISABLED", "ACTIVE"]
    reason: Reason


@users_api.route(
    "POST", "/<user_id>/status", permission="user.status.manage", body=StatusIn, if_match=True, requirement="RBAC-019"
)
def set_status(req: Req, user_id: str):
    target = _target(req, user_id)
    req.require_version(target.version)
    users.change_status(req.session, req.ctx, target, req.body.status, req.body.reason)
    req.session.flush()
    return ok(identity.user_detail(req.session, target))


@users_api.route("POST", "/<user_id>/unlock", permission="user.status.manage", requirement="AUTH-010")
def unlock(req: Req, user_id: str):
    target = _target(req, user_id)
    users.unlock(req.session, req.ctx, target)
    return ok(identity.user_detail(req.session, target))


class DeleteIn(Closed):
    reason: Reason


@users_api.route("DELETE", "/<user_id>", permission="user.delete", body=DeleteIn, if_match=True, requirement="USER-001")
def delete_user(req: Req, user_id: str):
    target = _target(req, user_id)
    req.require_version(target.version)
    users.delete_user(req.session, req.ctx, target, req.body.reason)
    return no_content()


@users_api.route("POST", "/<user_id>/restore", permission="user.restore", requirement="USER-001")
def restore_user(req: Req, user_id: str):
    target = _target(req, user_id, include_deleted=True)
    users.restore_user(req.session, req.ctx, target)
    req.session.flush()
    return ok(identity.user_detail(req.session, target))


@users_api.route("POST", "/<user_id>/invite/resend", permission="user.create", requirement="AUTH-011")
def resend_invite(req: Req, user_id: str):
    users.resend_invite(req.session, req.ctx, _target(req, user_id))
    return no_content()


@users_api.route("POST", "/<user_id>/password-reset", permission="user.password.reset", requirement="AUTH-008")
def admin_password_reset(req: Req, user_id: str):
    users.send_password_reset(req.session, req.ctx, _target(req, user_id))
    return no_content()


class RevokeIn(Closed):
    reason: Reason


@users_api.route(
    "POST", "/<user_id>/sessions/revoke", permission="user.session.revoke", body=RevokeIn, requirement="AUTH-016"
)
def revoke_sessions(req: Req, user_id: str):
    count = users.revoke_sessions(req.session, req.ctx, _target(req, user_id), req.body.reason)
    return ok({"revoked": count})


@users_api.route("GET", "/<user_id>/roles", permission="user.read", write=False, requirement="RBAC-008")
def get_roles(req: Req, user_id: str):
    return ok(users.present_roles(req.session, _target(req, user_id))["items"])


class RoleItem(Closed):
    role_id: Id
    valid_from: Instant | None = None
    valid_until: Instant | None = None


class RolesIn(Closed):
    roles: list[RoleItem]
    reason: Reason


@users_api.route("PUT", "/<user_id>/roles", permission="user.role.manage", body=RolesIn, requirement="RBAC-009")
def put_roles(req: Req, user_id: str):
    data = users.set_roles(req.session, req.ctx, _target(req, user_id), req.body.roles, req.body.reason)
    return ok(data["items"], meta={"authz_version": data["authz_version"]})


@users_api.route("GET", "/<user_id>/permissions", permission="user.read", write=False, requirement="RBAC-006")
def get_permissions(req: Req, user_id: str):
    return ok(users.present_permissions(req.session, _target(req, user_id)))


class GrantIn(Closed):
    permission_code: Annotated[str, text(100, min_len=1)]
    effect: Literal["GRANT", "DENY"] = "GRANT"
    scope: Literal["ALL", "TEAM", "OWN"] = "ALL"
    reason: Reason
    valid_from: Instant | None = None
    valid_until: Instant | None = None

    __top_level_codes__ = {"REASON_REQUIRED"}


@users_api.route(
    "POST",
    "/<user_id>/permissions",
    permission="user.permission.manage",
    body=GrantIn,
    status=201,
    requirement="RBAC-006",
)
def add_permission(req: Req, user_id: str):
    target = _target(req, user_id)
    row = users.add_permission(req.session, req.ctx, target, req.body)
    req.session.flush()
    return ok(next(p for p in users.present_permissions(req.session, target) if p["id"] == row.id), status=201)


@users_api.route(
    "DELETE", "/<user_id>/permissions/<grant_id>", permission="user.permission.manage", requirement="RBAC-006"
)
def delete_permission(req: Req, user_id: str, grant_id: str):
    users.remove_permission(req.session, req.ctx, _target(req, user_id), grant_id)
    return no_content()


@users_api.route(
    "GET",
    "/<user_id>/effective-permissions",
    permission=("user.read", "permission.read"),
    write=False,
    requirement="RBAC-016",
)
def effective(req: Req, user_id: str):
    return ok(users.effective_permissions(req.session, _target(req, user_id)))


class MfaResetIn(Closed):
    reason: Reason


@users_api.route(
    "POST", "/<user_id>/mfa/reset", permission="user.mfa.reset", body=MfaResetIn, if_match=True, requirement="MFA-007"
)
def mfa_reset(req: Req, user_id: str):
    target = _target(req, user_id)
    req.require_version(target.version)
    outcome = users.mfa_reset(req.session, req.ctx, target, req.body.reason)
    return no_content() if outcome is None else ok(outcome, status=202)


class MfaRequirementIn(Closed):
    mfa_required: bool
    reason: Reason


@users_api.route(
    "PUT",
    "/<user_id>/mfa-requirement",
    permission="user.mfa.require",
    body=MfaRequirementIn,
    if_match=True,
    requirement="MFA-003",
)
def mfa_requirement(req: Req, user_id: str):
    target = _target(req, user_id)
    req.require_version(target.version)
    users.set_mfa_requirement(req.session, req.ctx, target, req.body.mfa_required, req.body.reason)
    req.session.flush()
    return ok(identity.user_detail(req.session, target))


# --- approvals and Founder actions (08 §5.11) ------------------------------------------------------


class ApprovalsQuery(Query):
    status: str | None = None
    role: Literal["approver", "requester"] | None = None


def _visible(req: Req, r: AdminApprovalRequest) -> bool:
    if r.requested_by == req.ctx.user.id:
        return True
    code = governance.permission_for(r)
    return (
        req.ctx.has(code)
        and r.target_user_id != req.ctx.user.id
        and (r.action_class == "STANDARD" or governance.structurally_eligible(req.session, req.ctx.user, code))
    )


@approvals_api.route(
    "GET",
    "/approvals",
    any_of=("user.mfa.reset", "user.email.change", "user.founder.manage"),
    query=ApprovalsQuery,
    write=False,
    requirement="RBAC-021",
)
def list_approvals(req: Req):
    stmt = sa.select(AdminApprovalRequest).order_by(
        AdminApprovalRequest.created_on.desc(), AdminApprovalRequest.id.desc()
    )
    if req.query.status:
        stmt = stmt.where(AdminApprovalRequest.status.in_(csv(req.query.status)))
    rows = [r for r in req.session.execute(stmt).scalars() if _visible(req, r)]
    if req.query.role == "requester":
        rows = [r for r in rows if r.requested_by == req.ctx.user.id]
    elif req.query.role == "approver":
        rows = [r for r in rows if r.requested_by != req.ctx.user.id]
    data = [governance.present(req.session, r, req.ctx.user.id) for r in rows]
    return ok(data, meta={"pending_for_me": sum(1 for d in data if d["can_decide"])})


def _approval(req: Req, approval_id: str) -> AdminApprovalRequest:
    r = req.session.get(AdminApprovalRequest, approval_id)
    if r is None or not _visible(req, r):
        raise not_found()
    return r


@approvals_api.route(
    "GET",
    "/approvals/<approval_id>",
    any_of=("user.mfa.reset", "user.email.change", "user.founder.manage"),
    write=False,
    requirement="RBAC-021",
)
def get_approval(req: Req, approval_id: str):
    return ok(governance.present(req.session, _approval(req, approval_id), req.ctx.user.id))


class DecisionIn(Closed):
    reason: Reason


@approvals_api.route(
    "POST",
    "/approvals/<approval_id>/approve",
    any_of=("user.mfa.reset", "user.email.change", "user.founder.manage"),
    body=DecisionIn,
    requirement="RBAC-021",
)
def approve(req: Req, approval_id: str):
    # 08 §4 and 12 TD-G G9 specify 403 APPROVER_NOT_ELIGIBLE here although GET answers 404 for an invisible request.
    # The resulting existence oracle (IR-A07) is left for an owner decision rather than changed silently.
    r = req.session.get(AdminApprovalRequest, approval_id)
    if r is None:
        raise not_found()
    governance.approve(req.session, req.ctx, r, req.body.reason)
    return ok(governance.present(req.session, r, req.ctx.user.id))


@approvals_api.route(
    "POST",
    "/approvals/<approval_id>/deny",
    any_of=("user.mfa.reset", "user.email.change", "user.founder.manage"),
    body=DecisionIn,
    requirement="RBAC-021",
)
def deny(req: Req, approval_id: str):
    # 08 §4 and 12 TD-G G9 specify 403 APPROVER_NOT_ELIGIBLE here although GET answers 404 for an invisible request.
    # The resulting existence oracle (IR-A07) is left for an owner decision rather than changed silently.
    r = req.session.get(AdminApprovalRequest, approval_id)
    if r is None:
        raise not_found()
    governance.deny(req.session, req.ctx, r, req.body.reason)
    return ok(governance.present(req.session, r, req.ctx.user.id))


@approvals_api.route(
    "POST",
    "/approvals/<approval_id>/cancel",
    any_of=("user.mfa.reset", "user.email.change", "user.founder.manage"),
    requirement="RBAC-021",
)
def cancel(req: Req, approval_id: str):
    r = _approval(req, approval_id)
    governance.cancel(req.session, req.ctx, r)
    return ok(governance.present(req.session, r, req.ctx.user.id))


class CancelLinkIn(Closed):
    token: Annotated[str, Field(min_length=10, max_length=200)]


@approvals_api.route(
    "POST",
    "/approvals/cancel-link",
    rbx="RBX-003",
    auth="public",
    body=CancelLinkIn,
    requirement="RBAC-021",
    summary="Cancel a break-glass request via its signed link (06 §7.5)",
)
def cancel_link(req: Req):
    governance.cancel_by_link(req.session, req.body.token)
    return no_content()


class FounderActionIn(Closed):
    action: Literal[
        "GRANT_FOUNDER", "REVOKE_FOUNDER", "FOUNDER_MFA_RESET", "FOUNDER_STATUS_CHANGE", "FOUNDER_EMAIL_CHANGE"
    ]
    target_user_id: Id
    reason: Reason
    status: Literal["DISABLED", "ACTIVE", "UNLOCK", "DELETE", "DELETED"] | None = None
    new_email: Email | None = None
    post_roles: list[Id] | None = None

    __top_level_codes__ = {"REASON_REQUIRED"}


@approvals_api.route(
    "POST",
    "/founder-actions",
    permission="user.founder.manage",
    body=FounderActionIn,
    status=202,
    requirement="RBAC-021",
)
def founder_action(req: Req):
    from veda.platform.auth.request_auth import record_sensitive_action, require_step_up

    target = users.load_target(req.session, req.body.target_user_id)
    require_step_up(req.ctx)
    status = "DELETE" if req.body.status == "DELETED" else req.body.status
    payload = {
        k: v
        for k, v in {"status": status, "new_email": req.body.new_email, "post_roles": req.body.post_roles}.items()
        if v is not None
    }
    r = governance.request_founder_action(req.session, req.ctx, req.body.action, target, req.body.reason, payload)
    record_sensitive_action(
        req.session,
        req.ctx,
        "user.founder.manage",
        action=f"request:{req.body.action}",
        target=("app_user", target.id),
        subject_user_id=target.id,
    )
    data = {"approval_id": r.id, "channel": r.channel}
    if r.not_before:
        data["not_before"] = clock.to_rfc3339(r.not_before)
    return ok(data, status=202)


# --- roles (08 §6.1) ------------------------------------------------------------------------------------


@roles_api.route("GET", "", permission="role.read", query=Paging, write=False, requirement="RBAC-008")
def list_roles(req: Req):
    rows = req.session.execute(sa.select(Role).order_by(Role.sort_order, Role.name)).scalars().all()
    data = [roles.present_role(req.session, r) for r in rows]
    q = req.query
    meta, links = offset_meta(q.page, q.page_size, len(data), "/api/v1/roles", q.model_dump())
    return ok(data[(q.page - 1) * q.page_size : q.page * q.page_size], meta=meta, links=links)


@roles_api.route("GET", "/<role_id>", permission="role.read", write=False, requirement="RBAC-008")
def get_role(req: Req, role_id: str):
    role = roles.load_role(req.session, role_id)
    return ok({**roles.present_role(req.session, role), "permissions": roles.role_permissions(req.session, role)})


@roles_api.route("GET", "/<role_id>/permissions", permission="role.read", write=False, requirement="RBAC-008")
def get_role_permissions(req: Req, role_id: str):
    return ok(roles.role_permissions(req.session, roles.load_role(req.session, role_id)))


@roles_api.route("GET", "/<role_id>/users", permission=("role.read", "user.read"), write=False, requirement="RBAC-008")
def get_role_users(req: Req, role_id: str):
    from .models import UserRole

    roles.load_role(req.session, role_id)
    rows = (
        req.session.execute(
            sa.select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(UserRole.role_id == role_id)
            .order_by(User.full_name)
        )
        .scalars()
        .all()
    )
    return ok(
        [
            {"id": u.id, "display_name": u.display_name or u.full_name, "email": u.email, "status": u.status}
            for u in rows
        ]
    )


class RoleCreateIn(Closed):
    code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,49}$")]
    name: Annotated[str, text(100, min_len=1)]
    description: Annotated[str | None, optional_text(500)] = None
    copy_from_role_id: Id | None = None


@roles_api.route("POST", "", permission="role.manage", body=RoleCreateIn, status=201, requirement="RBAC-008")
def create_role(req: Req):
    role = roles.create_role(req.session, req.ctx, req.body)
    req.session.flush()
    return ok(
        {**roles.present_role(req.session, role), "permissions": roles.role_permissions(req.session, role)}, status=201
    )


class RolePatch(Closed):
    __immutable__ = frozenset({"code", "is_system", "grant_path"})
    name: Annotated[str | None, text(100, min_len=1)] = None
    description: Annotated[str | None, optional_text(500)] = None
    is_assignable: bool | None = None
    mfa_required: bool | None = None


@roles_api.route("PATCH", "/<role_id>", permission="role.manage", body=RolePatch, if_match=True, requirement="RBAC-008")
def patch_role(req: Req, role_id: str):
    role = roles.load_role(req.session, role_id)
    req.require_version(role.version)
    roles.update_role(req.session, req.ctx, role, req.body)
    req.session.flush()
    return ok(roles.present_role(req.session, role))


@roles_api.route("DELETE", "/<role_id>", permission="role.manage", if_match=True, requirement="RBAC-008")
def delete_role(req: Req, role_id: str):
    role = roles.load_role(req.session, role_id)
    req.require_version(role.version)
    roles.delete_role(req.session, req.ctx, role)
    return no_content()


class GrantItem(Closed):
    permission_code: Annotated[str, text(100, min_len=1)]
    scope: Literal["ALL", "TEAM", "OWN"] = "ALL"


class RolePermissionsIn(Closed):
    permissions: list[GrantItem]
    reason: Reason

    __top_level_codes__ = {"REASON_REQUIRED"}


@roles_api.route(
    "PUT", "/<role_id>/permissions", permission="role.manage", body=RolePermissionsIn, requirement="RBAC-009"
)
def put_role_permissions(req: Req, role_id: str):
    role = roles.load_role(req.session, role_id)
    if req.if_match is not None:
        req.require_version(role.version)
    data = roles.replace_permissions(req.session, req.ctx, role, req.body.permissions, req.body.reason)
    return ok(data["permissions"], meta={**data["diff"], "diff": data["diff"]})


# --- permissions (08 §6.2) ---------------------------------------------------------------------------


class PermissionsQuery(Paging):
    module: str | None = None
    resource: str | None = None
    q: str | None = None
    sensitive: bool | None = None

    def model_post_init(self, _ctx):
        if self.page_size == 25:
            self.page_size = 100


@permissions_api.route(
    "GET", "", permission="permission.read", query=PermissionsQuery, write=False, requirement="RBAC-004"
)
def list_permissions(req: Req):
    q = req.query
    stmt = sa.select(Permission).order_by(Permission.module, Permission.resource, Permission.code)
    if q.module:
        stmt = stmt.where(Permission.module.in_(csv(q.module)))
    if q.resource:
        stmt = stmt.where(Permission.resource.in_(csv(q.resource)))
    if q.sensitive is not None:
        stmt = stmt.where(Permission.is_sensitive == q.sensitive)
    if q.q:
        like = f"%{q.q.lower()}%"
        stmt = stmt.where(sa.or_(Permission.code.like(like), sa.func.lower(Permission.name).like(like)))
    rows = req.session.execute(stmt).scalars().all()
    data = [roles.present_permission(req.session, p) for p in rows]
    meta, links = offset_meta(q.page, q.page_size, len(data), "/api/v1/permissions", q.model_dump())
    return ok(data[(q.page - 1) * q.page_size : q.page * q.page_size], meta=meta, links=links)


def _perm(req: Req, permission_id: str) -> Permission:
    p = req.session.get(Permission, permission_id)
    if p is None:
        raise not_found()
    return p


@permissions_api.route("GET", "/<permission_id>", permission="permission.read", write=False, requirement="RBAC-004")
def get_permission(req: Req, permission_id: str):
    p = _perm(req, permission_id)
    return ok(
        {**roles.present_permission(req.session, p), "direct_exceptions": roles.direct_exceptions(req.session, p)}
    )


class PermissionPatch(Closed):
    __immutable__ = frozenset(
        {
            "code",
            "module",
            "resource",
            "action",
            "supports_scope",
            "is_sensitive",
            "sensitivity_class",
            "grant_path",
            "is_system",
            "requirement_ref",
        }
    )
    name: Annotated[str | None, text(120, min_len=1)] = None
    description: Annotated[str | None, optional_text(500)] = None


@permissions_api.route(
    "PATCH",
    "/<permission_id>",
    permission="permission.manage",
    body=PermissionPatch,
    if_match=True,
    requirement="RBAC-004",
)
def patch_permission(req: Req, permission_id: str):
    p = _perm(req, permission_id)
    req.require_version(p.version)
    roles.update_permission(req.session, req.ctx, p, req.body)
    req.session.flush()
    return ok(roles.present_permission(req.session, p))


@permissions_api.route(
    "GET", "/<permission_id>/holders", permission=("permission.read", "user.read"), write=False, requirement="RBAC-016"
)
def permission_holders(req: Req, permission_id: str):
    return ok(roles.holders(req.session, _perm(req, permission_id)))
