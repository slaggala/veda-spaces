"""Security-log archival: per-run segment keys (FC-13) and no write lock across object-store I/O (FC-14)."""

from __future__ import annotations

import sqlite3
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.integration.test_chain_integrity import _activity
from tests.support.dbh import events
from veda import config
from veda.kernel import clock, db, migration_support
from veda.platform import anchor_store, maintenance


def _retention(days: int) -> None:
    config.settings().security_event_online_retention_days = days


def _abandoned_attempt(monkeypatch, tmp_path) -> None:
    """An attempt that staged its export and pending manifest, then failed before the database commit."""

    def fail(conn, table):
        raise RuntimeError("simulated failure before commit")

    monkeypatch.setattr(migration_support, "drop_immutability_guards", fail)
    with pytest.raises(RuntimeError):
        maintenance.archive_security_events(str(tmp_path))
    monkeypatch.undo()


def test_FC13_abandoned_attempt_and_retention_change_do_not_block_a_later_segment(api, factory, tmp_path, monkeypatch):
    """Reviewer case F3b: abandoned 1..L, then retention lengthened (archive 1..M, M < L), then segment M+1..L ends
    at the abandoned L. With last_seq-only keys this collided ('already exists') and archival failed until a later
    segment ended elsewhere."""
    _activity(api, factory)
    clock.advance(timedelta(days=20))
    _activity(api, factory)
    clock.advance(timedelta(days=10))
    _retention(1)
    _abandoned_attempt(monkeypatch, tmp_path)
    abandoned = anchor_store.store().all("pending")
    assert len(abandoned) == 1 and not anchor_store.store().all("archive")
    abandoned_last = abandoned[0]["last_seq"]

    _retention(15)  # retention lengthened: only the older batch (1..M) is archived
    first = maintenance.archive_security_events(str(tmp_path))
    archived = anchor_store.store().all("archive")
    assert first["archived"] and archived[0]["last_seq"] < abandoned_last

    _retention(1)  # the next segment, M+1..L, ends exactly where the abandoned attempt did
    second = maintenance.archive_security_events(str(tmp_path))
    manifests = sorted(anchor_store.store().all("archive"), key=lambda m: m["first_seq"])
    assert second["archived"], "the later segment is archived despite the abandoned objects"
    assert manifests[-1]["last_seq"] == abandoned_last, "the collision case is what this test exercises"
    assert manifests[-1]["export_id"] != abandoned[0]["export_id"]
    assert len({m["export_id"] for m in anchor_store.store().all("pending")}) == 3, "one key per run"
    assert maintenance.verify_chain().ok


def test_FC13_exports_and_pending_manifests_are_keyed_per_run(api, factory, tmp_path):
    _activity(api, factory)
    clock.advance(timedelta(days=2))
    _retention(1)
    maintenance.archive_security_events(str(tmp_path))
    (manifest,) = anchor_store.store().all("archive")
    first, last, run = manifest["export_id"].split("-")
    assert (int(first), int(last)) == (manifest["first_seq"], manifest["last_seq"])
    assert len(run) == 32
    assert anchor_store.store().get_blob("export", manifest["export_id"]) is not None
    assert anchor_store.store().get_blob("export", manifest["last_seq"]) is None, "no last_seq-only key"


def test_FC13_pre_fc13_manifests_still_verify(api, factory, tmp_path):
    """A store written before FC-13 names exports by last_seq; verification still finds them."""
    _activity(api, factory)
    clock.advance(timedelta(days=2))
    _retention(1)
    maintenance.archive_security_events(str(tmp_path))
    store = anchor_store.store()
    (manifest,) = store.all("archive")
    legacy = {k: v for k, v in manifest.items() if k != "export_id"}
    blob = store.get_blob("export", manifest["export_id"])
    root = store.root / anchor_store.PREFIX
    for kind in ("archives", "pendings"):
        for path in (root / kind).glob("*.json"):
            path.unlink()
    store.put_blob("export", legacy["last_seq"], blob)
    store.put("archive", legacy["last_seq"], legacy)
    assert maintenance.verify_chain().ok


def _sqlite_write_lock_free(database_url: str) -> bool:
    conn = sqlite3.connect(database_url.split("sqlite:///", 1)[1], timeout=0, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("ROLLBACK")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def test_FC14_object_store_io_runs_without_the_sqlite_write_lock(
    api, factory, tmp_path, monkeypatch, engine, database_url
):
    if engine != "sqlite":
        pytest.skip("FC-14 is the SQLite database-wide write lock (BEGIN IMMEDIATE)")
    _activity(api, factory)
    clock.advance(timedelta(days=2))
    _retention(1)
    seen: list[tuple[str, bool]] = []
    real_put, real_put_blob = anchor_store.LocalAnchorStore.put, anchor_store.LocalAnchorStore.put_blob

    def put(self, kind, ident, body):
        seen.append((kind, _sqlite_write_lock_free(database_url)))
        return real_put(self, kind, ident, body)

    def put_blob(self, kind, ident, data):
        seen.append((kind, _sqlite_write_lock_free(database_url)))
        return real_put_blob(self, kind, ident, data)

    monkeypatch.setattr(anchor_store.LocalAnchorStore, "put", put)
    monkeypatch.setattr(anchor_store.LocalAnchorStore, "put_blob", put_blob)
    assert maintenance.archive_security_events(str(tmp_path))["archived"]
    kinds = [k for k, _ in seen]
    assert kinds == ["export", "pending", "archive"]
    assert all(free for _, free in seen), f"write lock held during object-store I/O: {seen}"


def test_FC14_a_run_superseded_during_its_upload_stands_down_without_alarm(api, factory, tmp_path, monkeypatch, caplog):
    """Another archiver completes while this run uploads (possible only because the upload holds no lock). This run
    must notice under the write lock that its rows are gone and stand down: one announcement, one archive."""
    _activity(api, factory)
    clock.advance(timedelta(days=2))
    _retention(1)
    real_put_blob = anchor_store.LocalAnchorStore.put_blob
    nested: list[dict] = []

    def put_blob(self, kind, ident, data):
        real_put_blob(self, kind, ident, data)
        if not nested:  # the concurrent run, started from inside this run's upload
            nested.append({})
            nested[0] = maintenance.archive_security_events(str(tmp_path / "other"))

    monkeypatch.setattr(anchor_store.LocalAnchorStore, "put_blob", put_blob)
    outer = maintenance.archive_security_events(str(tmp_path))
    monkeypatch.undo()
    assert nested[0]["archived"] and outer == {"archived": 0, "recovered": 0, "superseded": True}
    assert len(events("SECURITY_LOG_ARCHIVED")) == 1
    assert len(anchor_store.store().all("archive")) == 1
    assert not [r for r in caplog.records if "security_log_archive_failed" in r.getMessage()]
    assert maintenance.verify_chain().ok
    # The loser's pending manifest stays as an abandoned attempt and never blocks or alarms later runs.
    _activity(api, factory)
    clock.advance(timedelta(days=2))
    assert maintenance.archive_security_events(str(tmp_path))["archived"]
    assert maintenance.verify_chain().ok


def test_FC14_segment_changed_after_export_is_refused(api, factory, tmp_path, monkeypatch):
    """The write transaction re-checks the exported rows; a change between export and delete is refused."""
    _activity(api, factory)
    clock.advance(timedelta(days=2))
    _retention(1)
    real_put = anchor_store.LocalAnchorStore.put

    def put(self, kind, ident, body):
        real_put(self, kind, ident, body)
        if kind == "pending":
            with db.engine().begin() as conn:
                migration_support.drop_immutability_guards(conn, "security_event_log")
                conn.execute(
                    sa.text("UPDATE security_event_log SET row_hash = 'x' WHERE chain_seq = :seq"),
                    {"seq": body["last_seq"]},
                )
                migration_support.restore_immutability_guards(conn, "security_event_log")

    monkeypatch.setattr(anchor_store.LocalAnchorStore, "put", put)
    online = len(events())
    with pytest.raises(RuntimeError, match="changed after it was exported"):
        maintenance.archive_security_events(str(tmp_path))
    assert len(events()) == online, "nothing deleted"
