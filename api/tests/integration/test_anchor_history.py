"""FC-01: verification checks every retained anchor, not only the latest one (SEVT-006, SEVT-007, 05 §9.6).

The attacker modelled here holds the host, the database and the chain key (T1/T1b of the final targeted check): they
rewrite an old row, recompute every later hash, and post a fresh anchor for the forged head. A latest-anchor-only
check accepts that; an earlier anchor, already in write-once storage, contradicts it."""

from __future__ import annotations

from datetime import timedelta

import sqlalchemy as sa

from tests.integration.test_chain_integrity import FakeS3, _activity
from veda import config
from veda.kernel import clock, db, migration_support
from veda.platform import anchor_store, maintenance
from veda.platform.auth import security_events
from veda.platform.auth.models import SecurityEventLog


def _rewrite_history_from(seq: int) -> None:
    """Tamper with row ``seq`` and recompute the chain from it to the head with the real chain key."""
    keys = config.settings().chain_keys
    with db.unit_of_work(write=False) as s:
        rows = list(
            s.execute(
                sa.select(SecurityEventLog)
                .where(SecurityEventLog.chain_seq >= seq)
                .order_by(SecurityEventLog.chain_seq)
            ).scalars()
        )
        prev = s.execute(sa.select(SecurityEventLog.row_hash).where(SecurityEventLog.chain_seq == seq - 1)).scalar()
        updates = []
        for i, row in enumerate(rows):
            if i == 0:
                row.ip_address = "6.6.6.6"
            row.prev_hash = prev
            row.row_hash = security_events.compute_row_hash(row, keys[row.chain_key_label])
            updates.append({"seq": row.chain_seq, "ip": row.ip_address, "prev": row.prev_hash, "hash": row.row_hash})
            prev = row.row_hash
        s.expunge_all()
    with db.engine().begin() as conn:
        migration_support.drop_immutability_guards(conn, "security_event_log")
        for u in updates:
            conn.execute(
                sa.text(
                    "UPDATE security_event_log SET ip_address = :ip, prev_hash = :prev, row_hash = :hash"
                    " WHERE chain_seq = :seq"
                ),
                u,
            )
        migration_support.restore_immutability_guards(conn, "security_event_log")


def _three_anchors(api, factory) -> list[dict]:
    anchors = []
    for _ in range(3):
        _activity(api, factory)
        anchors.append(maintenance.anchor_chain())
    _activity(api, factory)
    return anchors


def test_FC01_rewritten_history_with_a_fresh_anchor_is_detected(api, factory):
    first, second, _ = _three_anchors(api, factory)
    assert maintenance.verify_chain().ok
    _rewrite_history_from(first["chain_seq"] - 1)  # an old row, below every anchor
    maintenance.anchor_chain()  # the attacker's anchor for the forged head is now the latest
    report = maintenance.verify_chain()
    assert not report.ok and report.problem == "anchor mismatch"
    assert report.at_seq == first["chain_seq"], "the earliest contradicted anchor is reported"


def test_FC01_rewrite_between_anchors_is_detected_by_the_next_older_anchor(api, factory):
    first, second, third = _three_anchors(api, factory)
    _rewrite_history_from(second["chain_seq"])  # leaves the first anchor intact, contradicts the second
    maintenance.anchor_chain()
    report = maintenance.verify_chain()
    assert not report.ok and report.problem == "anchor mismatch" and report.at_seq == second["chain_seq"]


def test_FC01_every_anchor_is_checked_through_the_s3_store(api, factory):
    anchor_store.use_store(anchor_store.S3AnchorStore("veda-anchors", client=FakeS3()))
    try:
        first, _, _ = _three_anchors(api, factory)
        assert maintenance.verify_chain().ok
        _rewrite_history_from(first["chain_seq"])
        maintenance.anchor_chain()
        report = maintenance.verify_chain()
        assert not report.ok and report.problem == "anchor mismatch" and report.at_seq == first["chain_seq"]
    finally:
        anchor_store.use_store(None)


def test_FC01_anchors_inside_an_archived_range_are_checked_against_the_export(api, factory, tmp_path):
    first, second, _ = _three_anchors(api, factory)
    clock.advance(timedelta(days=2))
    config.settings().security_event_online_retention_days = 1
    assert maintenance.archive_security_events(str(tmp_path))["archived"]
    _activity(api, factory)
    assert maintenance.verify_chain().ok, "every anchor, archived or online, matches: no false alarm"
    archived = anchor_store.store().all("archive")[0]
    assert archived["last_seq"] >= second["chain_seq"], "both older anchors now fall inside the export"


def test_FC01_many_anchors_and_appends_verify_cleanly(api, factory):
    for _ in range(6):
        _activity(api, factory, 1)
        maintenance.anchor_chain()
    assert len(anchor_store.store().all("anchor")) == 6
    assert maintenance.verify_chain().ok
