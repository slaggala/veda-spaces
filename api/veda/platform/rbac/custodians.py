"""Break-glass custodian identity (06 §7.5 items 2 and 4).

The acting principal is derived from AWS STS ``GetCallerIdentity`` for the credentials of the SSM session
that runs the CLI, never from an argument (IR-06). ``--principal-arn`` may still be passed, but only as an
assertion that must match the derived identity. The full STS ARN (which for an assumed role carries the
session name) is stored on the request as the external reference, so the evidence names the session.

``VEDA_BREAK_GLASS_IDENTITY=asserted`` trusts the argument instead; configuration refuses it outside local
and test (config.validate_environment).

RR-09: the CLI runs inside the API container on the host, where boto3's default chain would fall back to the
host's instance role, so STS would name the machine instead of the custodian. The identity is therefore resolved
from credentials the custodian brought (environment, assumed role, SSO, profile) with the instance-metadata and
container-role providers removed; an EC2 instance-profile session is refused even if one is supplied; and any
missing-credential or STS error is a refusal with a ``BREAK_GLASS_*`` FAILURE event, never an unhandled crash.
"""

from __future__ import annotations

import re

from veda.config import settings
from veda.kernel.errors import ApiError

_ASSUMED_ROLE = re.compile(r"^arn:(aws[a-z-]*):sts::(\d{12}):assumed-role/([^/]+)/(.+)$")
# EC2 names the session of an instance-profile role after the instance (i-0123456789abcdef0).
_INSTANCE_SESSION = re.compile(r"^i-[0-9a-f]{8,17}$")
# botocore providers that yield the host's or the container's own identity, never a custodian's.
HOST_CREDENTIAL_PROVIDERS = ("iam-role", "container-role")


def custodian_session():
    """A boto3 session that can only use credentials the custodian supplied (RR-09)."""
    import boto3
    import botocore.session

    core = botocore.session.Session()
    resolver = core.get_component("credential_provider")
    for name in HOST_CREDENTIAL_PROVIDERS:
        resolver.remove(name)
    return boto3.Session(botocore_session=core, region_name=settings().aws_region)


def caller_arn() -> str:  # pragma: no cover - AWS call; replaced in tests
    return custodian_session().client("sts").get_caller_identity()["Arn"]


def is_host_identity(arn: str) -> bool:
    """An EC2 instance-profile session: the machine, not a person."""
    m = _ASSUMED_ROLE.match(arn or "")
    return bool(m and _INSTANCE_SESSION.match(m.group(4)))


def _refuse(action: str, reason: str, message: str) -> ApiError:
    from veda.platform.auth import security_events

    event = "BREAK_GLASS_REQUESTED" if action == "request" else "BREAK_GLASS_APPROVED"
    security_events.defer(event, "FAILURE", failure_reason="POLICY", detail={"reason": reason})
    return ApiError(403, "APPROVER_NOT_ELIGIBLE", message)


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
    try:
        arn = caller_arn()
    except Exception as exc:  # botocore NoCredentialsError, ClientError, EndpointConnectionError, ...
        raise _refuse(
            action,
            "NO_CUSTODIAN_CREDENTIALS",
            "No custodian AWS credentials: run the CLI with your own short-lived session (runbook §7).",
        ) from exc
    if is_host_identity(arn):
        raise _refuse(action, "HOST_IDENTITY", "The host's instance role can never act as a custodian.")
    if asserted and asserted not in principal_keys(arn):
        raise _refuse(action, "PRINCIPAL_MISMATCH", "The supplied principal is not the caller's identity.")
    return arn
