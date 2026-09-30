"""Nightly snapshot and restore verification (IR-11; OPS-002, OPS-009). SQLite deployment only."""

import pytest

from veda import config
from veda.platform import backups, maintenance


@pytest.fixture
def snapshots(engine, tmp_path, api, factory):
    if engine != "sqlite":
        pytest.skip("snapshots apply to the SQLite deployment; PostgreSQL uses managed snapshots")
    config.settings().snapshot_dir = str(tmp_path / "snapshots")
    config.settings().snapshot_keep = 2
    factory.login(api, factory.user("SALES"))  # some data and chained security events
    return tmp_path / "snapshots"


def test_IR11_snapshot_is_consistent_and_checksummed(snapshots):
    manifest = maintenance.snapshot()
    path = snapshots / manifest["file"]
    assert path.exists() and backups._sha256(path) == manifest["sha256"] and manifest["bytes"] > 0


def test_IR11_restore_verification_passes_on_a_good_snapshot(snapshots):
    maintenance.snapshot()
    result = maintenance.restore_verify()
    assert result["counts"]["app_user"] >= 4 and result["chain_rows"] >= 1


def test_IR11_restore_verification_fails_on_a_corrupted_snapshot(snapshots, caplog):
    manifest = maintenance.snapshot()
    path = snapshots / manifest["file"]
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(RuntimeError, match="checksum"):
        maintenance.restore_verify()
    assert any("restore_verification_failed" in r.getMessage() for r in caplog.records)


def test_IR11_restore_verification_fails_without_a_snapshot(snapshots):
    with pytest.raises(RuntimeError, match="no snapshot"):
        maintenance.restore_verify()


def test_IR11_old_local_snapshots_are_pruned(snapshots):
    from datetime import timedelta

    from veda.kernel import clock

    for _ in range(3):
        maintenance.snapshot()
        clock.advance(timedelta(seconds=2))
    assert len(list(snapshots.glob("veda-*.db"))) == 2


def test_IR11_disk_usage_metric(snapshots):
    assert 0 <= maintenance.disk_usage()["used_percent"] <= 100
