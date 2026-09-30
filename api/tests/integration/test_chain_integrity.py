"""Security-event chain integrity against the external anchor store (IR-03, IR-26; SEVT-004, SEVT-006, SEVT-007).

Q4 (deletion of the anchored prefix, tail truncation) and Q3 (archival boundary where event time and chain
order disagree) are the independent review's probes. Rows are removed the way an attacker with database access
would: with the immutability guards lifted.
"""

import io
import json
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support.dbh import events
from veda import config
from veda.kernel import clock, db, migration_support
from veda.platform import anchor_store, maintenance
from veda.platform.auth import security_events


def _delete(where: str) -> None:
    with db.engine().begin() as conn:
        migration_support.drop_immutability_guards(conn, "security_event_log")
        conn.execute(sa.text(f"DELETE FROM security_event_log WHERE {where}"))
        migration_support.restore_immutability_guards(conn, "security_event_log")


def _head() -> int:
    return max(e.chain_seq for e in events())


def _activity(api, factory, n=2):
    for _ in range(n):
        factory.login(api, factory.user("SALES"))


@pytest.fixture
def anchored(api, factory):
    _activity(api, factory)
    anchor = maintenance.anchor_chain()
    _activity(api, factory)
    assert maintenance.verify_chain().ok
    return anchor


def test_IR03_Q4_deleting_the_anchored_prefix_is_detected(anchored):
    _delete(f"chain_seq <= {anchored['chain_seq']}")
    report = maintenance.verify_chain()
    assert not report.ok and report.problem == "prefix removed"
    assert events("SECURITY_LOG_CHAIN_BROKEN")


def test_IR03_Q4_deleting_the_oldest_rows_only_is_detected(anchored):
    _delete("chain_seq <= 2")
    assert maintenance.verify_chain().problem == "prefix removed"


def test_IR03_Q4_truncating_the_tail_below_the_anchor_is_detected(anchored):
    _delete(f"chain_seq >= {anchored['chain_seq']}")
    report = maintenance.verify_chain()
    assert not report.ok and report.problem == "truncated below anchor"


def test_IR03_Q4_deleting_the_head_row_after_anchoring_it_is_detected(api, factory):
    _activity(api, factory)
    anchor = maintenance.anchor_chain()
    _delete(f"chain_seq >= {anchor['chain_seq']}")
    assert maintenance.verify_chain().problem == "truncated below anchor"


def test_IR03_removing_a_middle_row_is_a_gap(anchored):
    _delete(f"chain_seq = {anchored['chain_seq'] + 1}")
    assert maintenance.verify_chain().problem == "gap"


def test_IR03_modified_anchored_row_is_detected(anchored):
    with db.engine().begin() as conn:
        migration_support.drop_immutability_guards(conn, "security_event_log")
        conn.execute(
            sa.text(f"UPDATE security_event_log SET ip_address = '6.6.6.6' WHERE chain_seq = {anchored['chain_seq']}")
        )
        migration_support.restore_immutability_guards(conn, "security_event_log")
    assert not maintenance.verify_chain().ok


def test_IR03_emptied_log_with_an_anchor_is_detected(anchored):
    _delete("1 = 1")
    assert maintenance.verify_chain().problem == "online log empty below anchor"


def test_IR03_anchor_failure_raises_and_alerts(api, factory, caplog):
    _activity(api, factory, 1)

    class Broken:
        def put(self, *a, **k):
            raise ConnectionError("s3 unavailable")

        def latest(self, kind):
            return None

        def all(self, kind):
            return []

    anchor_store.use_store(Broken())
    try:
        with pytest.raises(ConnectionError):
            maintenance.anchor_chain()
    finally:
        anchor_store.use_store(None)
    assert any(r.levelname == "CRITICAL" and "anchor_failed" in r.getMessage() for r in caplog.records)
    assert any(e.outcome == "FAILURE" for e in events("SECURITY_LOG_CHAIN_ANCHORED"))


# --- IR-26: archival boundary ---------------------------------------------------------------------------------


def test_IR26_Q3_archival_never_deletes_an_unexported_row(api, factory, tmp_path):
    _activity(api, factory)
    old = clock.now()
    old_count = len(events())
    clock.advance(timedelta(days=2))
    factory.login(api, factory.user("SALES"))  # newer rows (after the cutoff)
    newer_seq = _head()
    # A deferred event that happened before the cutoff but was chained after the newer rows.
    security_events._write_now(
        [security_events.PendingEvent("LOGIN", "FAILURE", None, old, {"failure_reason": "BAD_PASSWORD"})]
    )
    late_old_seq = _head()
    assert late_old_seq > newer_seq
    config.settings().security_event_online_retention_days = 1
    result = maintenance.archive_security_events(str(tmp_path))
    assert result["archived"] == old_count, "only the contiguous old prefix is archived"
    exported = [json.loads(line)["chain_seq"] for line in open(result["file"])]
    assert exported == list(range(1, old_count + 1))
    online = {e.chain_seq for e in events()}
    assert newer_seq in online and late_old_seq in online, "nothing deleted that was not exported"
    assert maintenance.verify_chain().ok


def test_IR26_second_archive_continues_from_the_first(api, factory, tmp_path):
    config.settings().security_event_online_retention_days = 1
    _activity(api, factory)
    clock.advance(timedelta(days=2))
    first = maintenance.archive_security_events(str(tmp_path))
    _activity(api, factory)
    clock.advance(timedelta(days=2))
    second = maintenance.archive_security_events(str(tmp_path))
    assert first["archived"] and second["archived"]
    manifests = anchor_store.store().all("archive")
    assert manifests[1]["first_seq"] == manifests[0]["last_seq"] + 1
    assert maintenance.verify_chain().ok
    # Removing the first row after the archived segment is still detected.
    _activity(api, factory)
    _delete(f"chain_seq = {manifests[1]['last_seq'] + 1}")
    assert maintenance.verify_chain().problem == "prefix removed"


# --- S3 store (stubbed client) --------------------------------------------------------------------------------


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.put_args: list[dict] = []

    def put_object(self, **kw):
        self.put_args.append(kw)
        self.objects[kw["Key"]] = kw["Body"]

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        start = int(ContinuationToken or 0)
        page = keys[start : start + 2]
        more = start + 2 < len(keys)
        return {
            "Contents": [{"Key": k} for k in page],
            "IsTruncated": more,
            **({"NextContinuationToken": str(start + 2)} if more else {}),
        }

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}


def test_IR03_s3_store_writes_object_locked_and_reads_latest(api, factory):
    fake = FakeS3()
    anchor_store.use_store(anchor_store.S3AnchorStore("veda-anchors", client=fake))
    try:
        for _ in range(3):
            _activity(api, factory, 1)
            maintenance.anchor_chain()
        assert all(
            a["ObjectLockMode"] == "COMPLIANCE" and a["ObjectLockRetainUntilDate"] > clock.now() for a in fake.put_args
        )
        latest = anchor_store.store().latest("anchor")
        assert latest["chain_seq"] == max(json.loads(v)["chain_seq"] for v in fake.objects.values())
        assert maintenance.verify_chain().ok
        _delete(f"chain_seq >= {latest['chain_seq']}")
        assert maintenance.verify_chain().problem == "truncated below anchor"
    finally:
        anchor_store.use_store(None)
