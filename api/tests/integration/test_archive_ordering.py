"""Archive manifests and maintenance observability (targeted re-review RR-05, RR-06, RR-07; SEVT-004/006/007/009).

* RR-05 (probe C11): a forged manifest written with the host credential no longer hides a deleted prefix.
* RR-06 (probe C12): a failure between the write-once objects and the database commit neither raises a false
  tamper alarm nor wedges archival; a failure after the commit is a durable, alarmed state that the next run repairs.
* RR-07: CLI and scheduler processes configure logging, so every job emits its EMF metric; failures and non-zero
  exits are recorded.

Object Lock behaviour itself is not exercised here (stub S3 client); staging evidence is still required.
"""

import json
import logging
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from tests.integration.test_chain_integrity import FakeS3, _activity, _delete
from tests.support.dbh import events
from veda import config
from veda.kernel import clock, migration_support
from veda.platform import anchor_store, maintenance

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def retention():
    config.settings().security_event_online_retention_days = 1


def _age(api, factory):
    _activity(api, factory)
    clock.advance(timedelta(days=2))


def _emf(caplog, name):
    return [
        r.emf
        for r in caplog.records
        if getattr(r, "emf", None) and any(m["Name"] == name for m in r.emf["_aws"]["CloudWatchMetrics"][0]["Metrics"])
    ]


# --- RR-05: forged manifests ---------------------------------------------------------------------------------


def _forge_prefix_deletion(store, anchor, **fields):
    manifest = {
        "kind": "archive",
        "first_seq": 1,
        "last_seq": anchor["chain_seq"] + 1,
        "count": anchor["chain_seq"] + 1,
        "sha256": "0" * 64,
        "last_row_hash": "f" * 64,
        "chain_key_label": "dev-2026",
        "file": "nonexistent.jsonl",
        **fields,
    }
    store.put("archive", manifest["last_seq"], manifest)
    _delete(f"chain_seq <= {manifest['last_seq']}")
    return manifest


def test_RR05_C11_forged_manifest_without_export_is_detected(api, factory):
    _activity(api, factory)
    anchor = maintenance.anchor_chain()
    _activity(api, factory)
    _forge_prefix_deletion(anchor_store.store(), anchor)
    report = maintenance.verify_chain()
    assert not report.ok and report.problem == "archive export missing", report
    assert events("SECURITY_LOG_CHAIN_BROKEN")


def test_RR05_forged_export_that_drops_rows_is_detected(api, factory, retention, tmp_path):
    """The host attacker also writes an export: without recomputing every later hash (which the anchor pins),
    the doctored export does not chain."""
    _age(api, factory)
    store = anchor_store.store()
    maintenance.archive_security_events(str(tmp_path))
    real = store.all("archive")[0]
    blob = store.get_blob("export", real["last_seq"]).decode().splitlines()
    doctored = ("\n".join(blob[:1] + blob[2:]) + "\n").encode()  # drop the second archived row
    import hashlib

    forged = {**real, "last_seq": real["last_seq"] + 1000, "sha256": hashlib.sha256(doctored).hexdigest()}
    store.put_blob("export", forged["last_seq"], doctored)
    anchor_store.use_store(ForgedView(store, forged))
    try:
        report = maintenance.verify_chain()
    finally:
        anchor_store.use_store(None)
    assert not report.ok and report.problem in ("archive export count mismatch", "archive export chain broken")


class ForgedView:
    """The store as an attacker would leave it: the genuine manifest replaced by a forged one."""

    def __init__(self, store, forged):
        self.store, self.forged = store, forged

    def all(self, kind):
        return [self.forged] if kind == "archive" else self.store.all(kind)

    def latest(self, kind):
        return self.store.latest(kind)

    def get_blob(self, kind, seq):
        return self.store.get_blob(kind, seq)


def test_RR05_unannounced_manifest_is_detected(api, factory, retention, tmp_path):
    _age(api, factory)
    maintenance.archive_security_events(str(tmp_path))
    announcement = next(e for e in events("SECURITY_LOG_ARCHIVED"))
    _activity(api, factory)
    assert maintenance.verify_chain().ok
    # Remove the announcement together with everything after the archive: the online prefix check fires first.
    _delete(f"chain_seq = {announcement.chain_seq}")
    report = maintenance.verify_chain()
    assert not report.ok and report.problem == "prefix removed"


def test_RR05_forgery_through_the_s3_store_is_detected(api, factory):
    fake = FakeS3()
    anchor_store.use_store(anchor_store.S3AnchorStore("veda-anchors", client=fake))
    try:
        _activity(api, factory)
        anchor = maintenance.anchor_chain()
        _activity(api, factory)
        _forge_prefix_deletion(anchor_store.store(), anchor)
        report = maintenance.verify_chain()
        assert not report.ok and report.problem == "archive export missing"
    finally:
        anchor_store.use_store(None)


def test_RR05_genuine_archives_verify_through_the_s3_store(api, factory, retention, tmp_path):
    fake = FakeS3()
    anchor_store.use_store(anchor_store.S3AnchorStore("veda-anchors", client=fake))
    try:
        _age(api, factory)
        maintenance.anchor_chain()
        first = maintenance.archive_security_events(str(tmp_path))
        _age(api, factory)
        second = maintenance.archive_security_events(str(tmp_path))
        assert first["archived"] and second["archived"]
        assert all(a["ObjectLockMode"] == "COMPLIANCE" for a in fake.put_args)
        kinds = sorted({k.split("/")[1] for k in fake.objects})
        assert kinds == ["anchors", "archives", "exports", "pendings"]
        assert maintenance.verify_chain().ok
    finally:
        anchor_store.use_store(None)


# --- RR-06: ordering between the store and the database -----------------------------------------------------------


def test_RR06_C12_database_failure_after_the_pending_manifest_is_not_an_alarm(
    api, factory, retention, tmp_path, monkeypatch, caplog
):
    _age(api, factory)
    online_before = len(events())

    def fail(conn, table):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(migration_support, "drop_immutability_guards", fail)
    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError):
        maintenance.archive_security_events(str(tmp_path))
    assert _emf(caplog, "SecurityLogArchiveFailed")
    monkeypatch.undo()
    assert len(events()) == online_before, "nothing deleted"
    assert anchor_store.store().all("pending") and not anchor_store.store().all("archive")
    report = maintenance.verify_chain()
    assert report.ok, report  # no false 'prefix removed'
    # The retry re-writes identical objects (idempotent) and completes.
    result = maintenance.archive_security_events(str(tmp_path))
    assert result["archived"] and maintenance.verify_chain().ok
    assert len(anchor_store.store().all("archive")) == 1


def test_RR06_failure_after_commit_is_alarmed_and_repaired(api, factory, retention, tmp_path, monkeypatch):
    _age(api, factory)
    real_put = anchor_store.LocalAnchorStore.put

    def put(self, kind, seq, body):
        if kind == "archive":
            raise ConnectionError("object store unavailable")
        return real_put(self, kind, seq, body)

    monkeypatch.setattr(anchor_store.LocalAnchorStore, "put", put)
    with pytest.raises(ConnectionError):
        maintenance.archive_security_events(str(tmp_path))
    monkeypatch.undo()
    report = maintenance.verify_chain()
    assert not report.ok and report.problem == "archive not finalised", "a durable failure state is alarmed"
    result = maintenance.archive_security_events(str(tmp_path))
    assert result["recovered"] == 1
    assert maintenance.verify_chain().ok, "no stranded processing"


def test_RR06_anchor_store_outage_during_verification_is_a_failure(api, factory, caplog):
    _activity(api, factory)

    class Down:
        def latest(self, kind):
            raise ConnectionError("store down")

        all = latest

    anchor_store.use_store(Down())
    try:
        with caplog.at_level(logging.INFO):
            report = maintenance.verify_chain()
    finally:
        anchor_store.use_store(None)
    assert not report.ok and report.problem == "anchor store unavailable"
    assert any(r.levelname == "CRITICAL" for r in caplog.records)
    assert events("SECURITY_LOG_CHAIN_BROKEN")
    metric = _emf(caplog, "ChainVerificationFailed")
    assert metric and metric[-1]["ChainVerificationFailed"] == 1


# --- RR-07: CLI processes emit metrics; the scheduler records exit codes ---------------------------------------------


def _cli(database_url, *args):
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("VEDA_")},
        "VEDA_ENV": "test",
        "VEDA_DATABASE_URL": database_url,
        "VEDA_ANCHOR_DIR": config.settings().anchor_dir,
        "VEDA_SNAPSHOT_DIR": str(Path(config.settings().anchor_dir) / "snapshots"),
    }
    return subprocess.run(
        [sys.executable, "-m", "veda.cli", *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120
    )


def _metric_lines(stdout):
    out = {}
    for line in stdout.splitlines():
        if '"_aws"' in line:
            data = json.loads(line)
            for m in data["_aws"]["CloudWatchMetrics"][0]["Metrics"]:
                out[m["Name"]] = data[m["Name"]]
    return out


@pytest.mark.parametrize(
    "job,metric",
    [
        ("disk-usage", "DiskUsed"),
        ("verify-chain", "ChainVerificationFailed"),
        ("invariants", "GovernanceInvariantFailures"),
        ("snapshot", "MaintenanceJobFailed"),
    ],
)
def test_RR07_cli_jobs_emit_their_metrics(app, database_url, engine, job, metric):
    if engine != "sqlite" and job in ("snapshot", "disk-usage"):
        pytest.skip("snapshots and the database-volume check are SQLite-only (the P0 production engine)")
    r = _cli(database_url, "maintenance", job)
    metrics = _metric_lines(r.stdout)
    assert metric in metrics, (r.returncode, r.stdout[-2000:], r.stderr[-2000:])
    assert "MaintenanceJobFailed" in metrics


def test_RR07_failing_job_exits_non_zero_with_an_alarm_metric(app, database_url):
    r = _cli(database_url, "maintenance", "archive-security-events")  # no approved retention → refuses
    assert r.returncode == 1
    metrics = _metric_lines(r.stdout)
    assert metrics.get("MaintenanceJobFailed") == 1
    assert '"level": "critical"' in r.stdout or '"level":"critical"' in r.stdout


def test_RR07_scheduler_records_exit_codes(monkeypatch, caplog):
    from veda.cli import main as cli

    codes = iter([0, 3])

    def fake_run(cmd, check, timeout):
        return subprocess.CompletedProcess(cmd, next(codes))

    monkeypatch.setattr(subprocess, "run", fake_run)
    with caplog.at_level(logging.INFO):
        assert cli.run_scheduled_job("disk-usage") == 0
        assert cli.run_scheduled_job("verify-chain") == 3
    values = [(r.emf["Job"], r.emf["ScheduledJobFailed"]) for r in caplog.records if getattr(r, "emf", None)]
    assert ("disk-usage", 0) in values and ("verify-chain", 1) in values
    assert any("scheduled_job_failed" in r.getMessage() and "exit_code=3" in r.getMessage() for r in caplog.records)

    def timeout(cmd, check, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert cli.run_scheduled_job("snapshot") == -1


# --- RR-17: deploy.sh reads the schema state inside the container and enforces the rollback floor --------------------


def test_RR17_schema_status_and_rollback_floor(app, capsys):
    from veda.cli.main import main

    assert main(["schema-status", "--require-known", "0009_mfa_challenge_binding"]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["state"] == "head" and out["current"] == out["image_head"] and out["floor_known"] is True
    # An image that does not know the floor (e.g. one built before IR-01) is refused as a rollback target.
    assert main(["schema-status", "--require-known", "0009_not_in_this_image"]) == 4
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["floor_known"] is False


def test_RR17_deploy_script_rollback_floor_is_the_ir01_revision():
    script = (ROOT / "deploy" / "deploy.sh").read_text()
    assert 'ROLLBACK_FLOOR="0009_mfa_challenge_binding"' in script
    assert "schema-status --require-known" in script and "exec -T api python" in script
    assert "grep -q '^VEDA_SCHEMA_AHEAD_ACCEPTED=' /etc/veda/api.env" not in script, "the declared value is checked"
