"""RFC 9457 problem details and the stable error code catalog (08 §2.4, §11)."""

from __future__ import annotations

from typing import Any

TITLES: dict[str, str] = {
    "MALFORMED_JSON": "Malformed JSON",
    "INVALID_ID": "Invalid identifier",
    "INVALID_DATETIME": "Invalid date-time",
    "MFA_CODE_INVALID": "Verification code is incorrect",
    "MFA_CHALLENGE_INVALID": "Verification request is no longer valid",
    "MFA_RECOVERY_INVALID": "Password or recovery code is incorrect",
    "ENROLLMENT_PROOF_INVALID": "Enrollment proof is invalid",
    "STEP_UP_REQUIRED": "Confirm it's you",
    "RECOVERY_SESSION_RESTRICTED": "Recovery session is restricted",
    "COOLING_OFF": "Security cooling-off in effect",
    "FOUNDER_PROTECTED": "Founder accounts use the Founder workflow",
    "FOUNDER_GOVERNANCE_REQUIRED": "Founder governance required",
    "APPROVER_NOT_ELIGIBLE": "Not eligible to decide this request",
    "REQUEST_ALREADY_OPEN": "A request is already open",
    "FOUNDER_STATE_INCONSISTENT": "Founder state inconsistent",
    "MFA_ALREADY_ENROLLED": "Two-step verification already enrolled",
    "MFA_REQUIRED_BY_POLICY": "Two-step verification is required by policy",
    "RESET_TOKEN_INVALID": "This link has expired or was already used",
    "INVITE_TOKEN_INVALID": "This invitation has expired or was already used",
    "EMAIL_TOKEN_INVALID": "This link has expired or was already used",
    "AUTH_REQUIRED": "Authentication required",
    "TOKEN_EXPIRED": "Access token expired",
    "SESSION_INVALID": "Session is no longer valid",
    "INVALID_CREDENTIALS": "Email or password is incorrect",
    "PERMISSION_DENIED": "You don't have access",
    "PASSWORD_CHANGE_REQUIRED": "Password change required",
    "CSRF_REJECTED": "Request rejected",
    "ESCALATION_DENIED": "Includes permissions you don't have",
    "SELF_MODIFICATION_DENIED": "You can't change your own access",
    "NOT_FOUND": "Not found",
    "METHOD_NOT_ALLOWED": "Method not allowed",
    "VERSION_CONFLICT": "This record was changed by someone else",
    "DUPLICATE": "Already exists",
    "LAST_ADMINISTRATOR": "The last recovery administrator cannot be removed",
    "LAST_FOUNDER": "The last Founder cannot be removed",
    "SYSTEM_OBJECT": "System objects cannot be changed this way",
    "ROLE_IN_USE": "Role is assigned to users",
    "INVALID_STATE": "Invalid state for this action",
    "PAYLOAD_TOO_LARGE": "Payload too large",
    "UNSUPPORTED_MEDIA_TYPE": "Unsupported media type",
    "VALIDATION_FAILED": "Validation failed",
    "INVALID_STATUS_TRANSITION": "Status change not allowed",
    "NO_OP_TRANSITION": "Lead is already in this status",
    "LOST_REASON_REQUIRED": "A lost reason is required",
    "COMMENT_REQUIRED": "A comment is required",
    "SAME_AS_CURRENT": "Same as current",
    "CONSENT_WITHDRAWN": "Consent to contact was withdrawn",
    "ERASURE_BLOCKED": "Erasure blocked",
    "TIME_BOUND_GRANTS_NOT_ENABLED": "Time-bound grants are not enabled",
    "UNKNOWN_POLICY_VERSION": "Unknown privacy policy version",
    "PASSWORD_POLICY": "Password does not meet the policy",
    "PASSWORD_REUSED": "Choose a different password",
    "CAPTCHA_FAILED": "Verification failed",
    "CONSENT_REQUIRED": "Consent is required",
    "REASON_REQUIRED": "A reason is required",
    "SCOPE_NOT_SUPPORTED": "Scope not supported",
    "FIELD_NOT_UPDATABLE": "Field cannot be updated here",
    "IMMUTABLE_FIELD": "Field is immutable",
    "INVALID_QUERY_PARAM": "Invalid query parameter",
    "IDEMPOTENCY_KEY_REUSED": "Idempotency key reused with a different request",
    "PRECONDITION_REQUIRED": "If-Match header required",
    "IDEMPOTENCY_KEY_REQUIRED": "Idempotency-Key header required",
    "RATE_LIMITED": "Too many requests",
    "INTERNAL_ERROR": "Something went wrong",
    "SERVICE_UNAVAILABLE": "Service unavailable",
    "SOURCE_NOT_ALLOWED": "Source not allowed",
    "INVALID_ASSIGNEE": "Invalid assignee",
    "NO_OP_ASSIGNMENT": "Lead is already assigned this way",
    "VISIBILITY_NOT_SUPPORTED": "Visibility not supported",
    "SYSTEM_TYPE_NOT_ALLOWED": "System activity types cannot be created",
    "SCHEDULE_REQUIRED": "A schedule is required",
    "INVALID_OWNER": "Invalid owner",
    "LEAD_CLOSED": "Lead is closed",
    "SYSTEM_ACTIVITY_READ_ONLY": "System activities are read-only",
    "INVALID_ACTIVITY_STATE": "Invalid activity state",
    "INVALID_LOOKUP": "Unknown value",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str | None = None, *, errors: list[dict] | None = None,
                 extra: dict[str, Any] | None = None, headers: dict[str, str] | None = None, title: str | None = None):
        super().__init__(f"{status} {code}: {detail or ''}")
        self.status = status
        self.code = code
        self.detail = detail
        self.errors = errors
        self.extra = extra or {}
        self.headers = headers or {}
        self.title = title


def field_error(field: str, code: str, message: str) -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


def validation_failed(errors: list[dict], code: str = "VALIDATION_FAILED", status: int = 422) -> ApiError:
    n = len(errors)
    return ApiError(status, code, f"{n} field{'s are' if n != 1 else ' is'} invalid.", errors=errors)


def not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "The resource does not exist or is not visible to you.")


def problem_body(err: ApiError, request_id: str | None) -> dict[str, Any]:
    slug = err.code.lower().replace("_", "-")
    body: dict[str, Any] = {
        "type": f"https://api.vedaspaces.com/problems/{slug}",
        "title": err.title or TITLES.get(err.code, err.code.replace("_", " ").capitalize()),
        "status": err.status,
        "code": err.code,
    }
    if err.detail:
        body["detail"] = err.detail
    body["request_id"] = request_id
    if err.errors is not None:
        body["errors"] = err.errors
    body.update(err.extra)
    return body
