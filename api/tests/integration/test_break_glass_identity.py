"""RR-09: break-glass custodian identity in the deployed topology (06 §7.5 items 2 and 4, RBAC-021).

The CLI runs inside the API container on the host. STS must name the custodian who brought credentials, never the
host's instance role, and a missing or broken credential is a refusal with a FAILURE event, not a crash."""

from __future__ import annotations

import json

import botocore.exceptions
import pytest

from tests.support.dbh import events
from veda.platform.rbac import custodians

K1 = "arn:aws:iam::111111111111:role/custodian-a"
HOST_ROLE = "arn:aws:iam::111111111111:role/veda-host"
HOST_SESSION = "arn:aws:sts::111111111111:assumed-role/veda-host/i-0a1b2c3d4e5f60718"


def _cli(args):
    from veda.cli.main import main

    return main(["break-glass", *args])


def _request(target_id: str):
    return _cli(["request", "--target", target_id, "--founder-action", "GRANT_FOUNDER", "--reason", "lost access"])


def _failures(reason: str) -> list:
    return [
        e
        for e in events("BREAK_GLASS_REQUESTED")
        if e.outcome == "FAILURE" and (e.detail or {}).get("reason") == reason
    ]


@pytest.mark.settings(
    break_glass_custodians={K1: "external:Auditor-1", HOST_ROLE: "external:misregistered"}, break_glass_identity="sts"
)
def test_RR09_host_instance_role_is_never_a_custodian(api, factory, monkeypatch, capsys):
    """Even registered by mistake, the machine's identity cannot request or approve (two-person control would
    otherwise collapse to whoever can open a shell on the host)."""
    factory.user(founder=True, mfa=False)
    target = factory.user("ADMIN")
    monkeypatch.setattr(custodians, "caller_arn", lambda: HOST_SESSION)
    assert _request(target.id) == 3
    assert "APPROVER_NOT_ELIGIBLE" in capsys.readouterr().err
    assert _failures("HOST_IDENTITY")
    assert not events("BREAK_GLASS_REQUESTED", outcome="SUCCESS")


@pytest.mark.settings(break_glass_custodians={K1: "external:Auditor-1"}, break_glass_identity="sts")
@pytest.mark.parametrize(
    "error",
    [
        botocore.exceptions.NoCredentialsError(),
        botocore.exceptions.EndpointConnectionError(endpoint_url="https://sts.ap-south-1.amazonaws.com"),
        botocore.exceptions.ClientError({"Error": {"Code": "ExpiredToken", "Message": "expired"}}, "GetCallerIdentity"),
    ],
    ids=["no-credentials", "sts-unreachable", "expired-token"],
)
def test_RR09_missing_or_broken_credentials_are_refused_with_a_failure_event(api, factory, monkeypatch, capsys, error):
    factory.user(founder=True, mfa=False)
    target = factory.user("ADMIN")

    def fail():
        raise error

    monkeypatch.setattr(custodians, "caller_arn", fail)
    assert _request(target.id) == 3, "a clean refusal, not an unhandled exception"
    assert json.loads(capsys.readouterr().err.strip().splitlines()[-1])["error"] == "APPROVER_NOT_ELIGIBLE"
    assert _failures("NO_CUSTODIAN_CREDENTIALS")


@pytest.mark.settings(break_glass_custodians={K1: "external:Auditor-1"}, break_glass_identity="sts")
def test_RR09_a_custodian_session_still_works(api, factory, monkeypatch, capsys):
    factory.user(founder=True, mfa=False)
    target = factory.user("ADMIN")
    session = "arn:aws:sts::111111111111:assumed-role/custodian-a/auditor-1-20261003"
    monkeypatch.setattr(custodians, "caller_arn", lambda: session)
    assert _request(target.id) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["status"] == "PENDING"


def test_RR09_identity_helpers():
    assert custodians.is_host_identity(HOST_SESSION)
    assert not custodians.is_host_identity("arn:aws:sts::111111111111:assumed-role/custodian-a/i-am-auditor-1")
    assert not custodians.is_host_identity(K1)
    assert not custodians.is_host_identity("arn:aws:iam::111111111111:user/auditor")


def test_RR09_custodian_session_cannot_reach_host_credentials(monkeypatch, tmp_path):
    """The session the CLI uses has no instance-metadata or container-role provider, so without credentials the
    custodian brought there are none at all, even on an EC2 host."""
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "none"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "none"))
    session = custodians.custodian_session()
    methods = [p.METHOD for p in session._session.get_component("credential_provider").providers]
    assert "env" in methods and not set(custodians.HOST_CREDENTIAL_PROVIDERS) & set(methods)
    assert session.get_credentials() is None
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ASIAEXAMPLECUSTODIAN")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "example-secret")  # pragma: allowlist secret
    monkeypatch.setenv("AWS_SESSION_TOKEN", "example-token")
    creds = custodians.custodian_session().get_credentials()
    assert creds is not None and creds.access_key == "ASIAEXAMPLECUSTODIAN" and creds.method == "env"
