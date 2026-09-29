"""FC-02: approved metric names survive the log scrubber; recovery secrets and identifiers do not (LOG-003, LOG-006)."""

import io
import json
import logging
import re
from pathlib import Path

import structlog

from veda.kernel import logging as vlog
from veda.kernel import metrics

ROOT = Path(__file__).resolve().parents[2]
SECRETS = (
    "ABCD-EFGH-2345",
    "JBSWY3DPEHPK3PXP",
    "rt_0123456789abcdef0123456789abcdef",
    "01a0ed45-6227-73c9-9636-c98f4d8bfb30",
)


def _capture(fn) -> list[dict]:
    vlog.configure_logging("INFO")
    stream = io.StringIO()
    next(h for h in logging.getLogger().handlers if getattr(h, "_veda", False)).stream = stream
    try:
        fn()
    finally:
        structlog.reset_defaults()
        vlog.configure_logging("INFO")
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def _metric_lines(lines):
    return [line for line in lines if "_aws" in line]


def test_FC02_no_effective_recovery_admin_survives_redaction():
    lines = _capture(
        lambda: metrics.emit_many(
            {"GovernanceInvariantFailures": (0.0, "Count"), "NoEffectiveRecoveryAdmin": (1.0, "Count")}
        )
    )
    [line] = _metric_lines(lines)
    assert line["NoEffectiveRecoveryAdmin"] == 1.0 and line["GovernanceInvariantFailures"] == 0.0
    # What the CloudWatch agent consumes: the declared metric and a numeric value at the root.
    declared = {m["Name"] for m in line["_aws"]["CloudWatchMetrics"][0]["Metrics"]}
    assert "NoEffectiveRecoveryAdmin" in declared and isinstance(line["NoEffectiveRecoveryAdmin"], float)
    assert set(line) - {"_aws", "event", "level", "logger", "ts"} == {
        "NoEffectiveRecoveryAdmin",
        "GovernanceInvariantFailures",
    }


def test_FC02_recovery_secrets_and_identifiers_are_still_redacted():
    def run():
        log = structlog.get_logger("veda.test")
        log.info(
            "recovery_attempt",
            recovery_code=SECRETS[0],
            recovery_token=SECRETS[2],
            recovery_session_id=SECRETS[3],
            totp_secret=SECRETS[1],
            RecoveryHint="ask the founder",
            new_recovery_field=SECRETS[0],
        )
        logging.getLogger("veda.test").info("stdlib", extra={"recovery_code": SECRETS[0]})

    lines = _capture(run)
    text = json.dumps(lines)
    for secret in SECRETS:
        assert secret not in text
    first = lines[0]
    for key in (
        "recovery_code",
        "recovery_token",
        "recovery_session_id",
        "totp_secret",
        "RecoveryHint",
        "new_recovery_field",
    ):
        assert first[key] == "[REDACTED]", key


def test_FC02_only_approved_numeric_metrics_are_exempt():
    def run():
        # An unapproved metric name with a denylisted word is still redacted.
        metrics.emit("RecoveryCodesIssued", 3)
        # An approved name carrying a non-numeric value is still redacted.
        structlog.get_logger("veda.test").info(
            "spoof",
            **metrics.emf({"NoEffectiveRecoveryAdmin": (1.0, "Count")}) | {"NoEffectiveRecoveryAdmin": SECRETS[0]},
        )

    lines = _metric_lines(_capture(run))
    assert lines[0]["RecoveryCodesIssued"] == "[REDACTED]"
    assert lines[1]["NoEffectiveRecoveryAdmin"] == "[REDACTED]"
    assert SECRETS[0] not in json.dumps(lines)


def test_FC02_metric_lines_carry_no_identifiers():
    lines = _capture(lambda: metrics.emit("NoEffectiveRecoveryAdmin", 1))
    [line] = _metric_lines(lines)
    text = json.dumps(line)
    assert not re.search(r"[0-9a-f]{32}|@|user_id|email|custodian", text), text


def test_FC02_every_emitted_and_alarmed_metric_is_approved():
    emitted = set()
    for path in (ROOT / "veda").rglob("*.py"):
        for m in re.finditer(r'"([A-Z][A-Za-z]+)": \(', path.read_text()):
            emitted.add(m.group(1))
        for m in re.finditer(r'metrics\.emit\("([A-Za-z]+)"', path.read_text()):
            emitted.add(m.group(1))
    emitted &= {n for n in emitted if not n.isupper()}
    assert emitted - metrics.APPROVED_METRICS == set()
    runbook = (ROOT.parent / "docs/operations/api-runbooks.md").read_text()
    section = runbook.split("## 9. Metrics and alerts", 1)[1].split("## 10.", 1)[0]
    alarmed = set(re.findall(r"`([A-Z][a-z][A-Za-z]+)`", section)) - {
        "Route",
        "StatusClass",
        "EventType",
        "Outcome",
        "Job",
    }
    assert alarmed <= metrics.APPROVED_METRICS, alarmed - metrics.APPROVED_METRICS
