"""Break-glass custodian identity (06 §7.5 items 2 and 4).

The acting principal is derived from AWS STS ``GetCallerIdentity`` for the credentials of the SSM session
that runs the CLI, never from an argument (IR-06). ``--principal-arn`` may still be passed, but only as an
assertion that must match the derived identity. The full STS ARN (which for an assumed role carries the
session name) is stored on the request as the external reference, so the evidence names the session.

``VEDA_BREAK_GLASS_IDENTITY=asserted`` trusts the argument instead; configuration refuses it outside local
and test (config.validate_environment).
"""

from __future__ import annotations

import re

from veda.config import settings
from veda.kernel.errors import ApiError

_ASSUMED_ROLE = re.compile(r"^arn:(aws[a-z-]*):sts::(\d{12}):assumed-role/([^/]+)/(.+)$")


def caller_arn() -> str:  # pragma: no cover - AWS call; replaced in tests
    import boto3

    return boto3.client("sts", region_name=settings().aws_region).get_caller_identity()["Arn"]


def principal_keys(arn: str) -> list[str]:
    """Register keys an ARN may be listed under: the ARN itself and, for an assumed-role session, its role."""
    m = _ASSUMED_ROLE.match(arn or "")
    if m:
        return [arn, f"arn:{m.group(1)}:iam::{m.group(2)}:role/{m.group(3)}"]
    return [arn]


def human_for(arn: str | None) -> str | None:
    register = settings().break_glass_custodians
    for key in principal_keys(arn or ""):
        if key in register:
            return register[key]
    return None


def resolve(asserted: str | None, *, action: str = "approve") -> str:
    """The acting principal ARN for a break-glass CLI command."""
    if settings().break_glass_identity == "asserted":
        if not settings().dev_keys_allowed:
            raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "Asserted custodian identity is not allowed here.")
        if not asserted:
            raise ApiError(422, "VALIDATION_FAILED", "--principal-arn is required.")
        return asserted
    arn = caller_arn()
    if asserted and asserted not in principal_keys(arn):
        from veda.platform.auth import security_events

        event = "BREAK_GLASS_REQUESTED" if action == "request" else "BREAK_GLASS_APPROVED"
        security_events.defer(event, "FAILURE", failure_reason="POLICY", detail={"reason": "PRINCIPAL_MISMATCH"})
        raise ApiError(403, "APPROVER_NOT_ELIGIBLE", "The supplied principal is not the caller's identity.")
    return arn
