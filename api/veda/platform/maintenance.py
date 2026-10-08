"""Maintenance jobs (03 §2.10, 04 §14, 05 §9.4, §9.6, 06 §7.3, 07 §8).

Run as SYSTEM from the maintenance CLI or the scheduler. Only the maintenance
process lifts the evidence-store immutability guards, inside the same
transaction as the change it makes (A-02). Retention jobs refuse to run until
owner-approved values are configured (OWNER-INPUT-002).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db, metrics, migration_support, outbox
from veda.kernel.audit_hook import write_explicit_audit
from veda.kernel.audit_registry import policy_for
from veda.kernel.context import actor, system_context
from veda.kernel.ids import SYSTEM_USER_ID, new_id
from veda.platform import anchor_store
from veda.platform.audit.models import AuditLog
from veda.platform.auth import security_events
from veda.platform.auth.models import (
    MfaChallenge,
    RefreshToken,
    SecurityEventLog,
    UserActionToken,
    UserSession,
)
from veda.platform.identity.models import User
from veda.platform.notifications.models import Notification, OutboxEvent

log = logging.getLogger("veda.maintenance")


def _summary(s, job: str, table: str | None, count: int, enabled: bool = True) -> None:
    security_events.record(
        s, "MAINTENANCE_PURGE", "SUCCESS", detail={"job": job, "table": table, "count": count, "enabled": enabled}
    )


# --- purge (03 §2.10) --------------------------------------------------------------------------


def purge() -> dict:
    cfg = settings()
    result: dict = {}
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        now = db.tx_time(s)
        # 1 mfa_challenge: expires_on older than 1 day
        rows = (
            s.execute(sa.select(MfaChallenge).where(MfaChallenge.expires_on < now - timedelta(days=1))).scalars().all()
        )
        for r in rows:
            s.delete(r)
        s.flush()
        result["mfa_challenge"] = len(rows)
        _summary(s, "purge", "mfa_challenge", len(rows))
        if cfg.token_retention_days is not None:
            cutoff = now - timedelta(days=cfg.token_retention_days)
            # 2 user_action_token
            rows = (
                s.execute(
                    sa.select(UserActionToken).where(
                        sa.or_(
                            UserActionToken.used_on < cutoff,
                            UserActionToken.invalidated_on < cutoff,
                            UserActionToken.expires_on < cutoff,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for r in rows:
                s.delete(r)
            s.flush()
            result["user_action_token"] = len(rows)
            _summary(s, "purge", "user_action_token", len(rows))
        if cfg.user_session_retention_days is not None:
            cutoff = now - timedelta(days=cfg.user_session_retention_days)
            purgeable = sa.select(UserSession.id).where(
                sa.or_(UserSession.revoked_on < cutoff, UserSession.absolute_expires_on < cutoff)
            )
            # 3 refresh_token: its session is purgeable, or expired past token retention
            token_cutoff = now - timedelta(days=cfg.token_retention_days or cfg.user_session_retention_days)
            rows = (
                s.execute(
                    sa.select(RefreshToken).where(
                        sa.or_(RefreshToken.session_id.in_(purgeable), RefreshToken.expires_on < token_cutoff)
                    )
                )
                .scalars()
                .all()
            )
            for r in rows:
                s.delete(r)
            s.flush()
            result["refresh_token"] = len(rows)
            _summary(s, "purge", "refresh_token", len(rows))
            # 4 user_session with no remaining refresh_token or mfa_challenge rows
            sessions = s.execute(sa.select(UserSession).where(UserSession.id.in_(purgeable))).scalars().all()
            n = 0
            for us in sessions:
                has_rt = s.execute(sa.select(RefreshToken.id).where(RefreshToken.session_id == us.id)).first()
                has_ch = s.execute(sa.select(MfaChallenge.id).where(MfaChallenge.session_id == us.id)).first()
                if not has_rt and not has_ch:
                    s.delete(us)
                    n += 1
            s.flush()
            result["user_session"] = n
            _summary(s, "purge", "user_session", n)
        if cfg.notification_read_retention_days is not None and cfg.notification_unread_retention_days is not None:
            # 5 notification (must precede outbox)
            read_cut = now - timedelta(days=cfg.notification_read_retention_days)
            unread_cut = now - timedelta(days=cfg.notification_unread_retention_days)
            rows = (
                s.execute(
                    sa.select(Notification)
                    .where(
                        sa.or_(
                            sa.and_(Notification.read_on.is_not(None), Notification.read_on < read_cut),
                            sa.and_(Notification.read_on.is_(None), Notification.created_on < unread_cut),
                        )
                    )
                    .execution_options(include_deleted=True)
                )
                .scalars()
                .all()
            )
            for r in rows:
                s.delete(r)
            s.flush()
            result["notification"] = len(rows)
            _summary(s, "purge", "notification", len(rows))
        if cfg.outbox_retention_days is not None:
            # 6 outbox_event: DONE, old, and not referenced by a notification
            cut = now - timedelta(days=cfg.outbox_retention_days)
            referenced = (
                sa.select(Notification.source_event_id)
                .where(Notification.source_event_id.is_not(None))
                .execution_options(include_deleted=True)
            )
            rows = (
                s.execute(
                    sa.select(OutboxEvent).where(
                        OutboxEvent.status == "DONE", OutboxEvent.processed_on < cut, OutboxEvent.id.not_in(referenced)
                    )
                )
                .scalars()
                .all()
            )
            for r in rows:
                s.delete(r)
            s.flush()
            result["outbox_event"] = len(rows)
            _summary(s, "purge", "outbox_event", len(rows))
        # Expired email-change proposals are cleared (05 §8.6 step 8).
        expired = 0
        for user in s.execute(sa.select(User).where(User.proposed_email.is_not(None))).scalars():
            open_tok = s.execute(
                sa.select(UserActionToken.id).where(
                    UserActionToken.user_id == user.id,
                    UserActionToken.purpose == "EMAIL_VERIFICATION",
                    UserActionToken.used_on.is_(None),
                    UserActionToken.invalidated_on.is_(None),
                    UserActionToken.expires_on > now,
                )
            ).first()
            if not open_tok:
                from veda.platform.auth.service import clear_proposal

                clear_proposal(s, user)
                security_events.record(s, "EMAIL_CHANGE_EXPIRED", "SUCCESS", subject_user_id=user.id)
                expired += 1
        result["email_change_expired"] = expired
    return result


# --- erasure: rewrite historical audit payloads (07 §8.2 steps 2, 4, 5, 6, 7) -------------------------


def _erase_payload(value, pii: frozenset[str]):
    if not isinstance(value, dict):
        return value
    out = {}
    for k, v in value.items():
        if k == "_snapshot" and isinstance(v, dict):
            out[k] = _erase_payload(v, pii)
        elif k in pii and v is not None and v not in ("[REDACTED]", "[ERASED]"):
            out[k] = "[ERASED]"
        else:
            out[k] = v
    return out


def run_erasure_audit() -> int:
    """Process pending lead.erasure_requested events. Only this process lifts the audit guard."""
    from veda.modules.crm.leads.models import Lead, LeadActivity, LeadNote

    done = 0
    with db.unit_of_work(write=False) as s:
        pending = (
            s.execute(
                sa.select(OutboxEvent.id).where(
                    OutboxEvent.event_type == "lead.erasure_requested", OutboxEvent.status.in_(("PENDING", "FAILED"))
                )
            )
            .scalars()
            .all()
        )
    for event_id in pending:
        with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
            ev = s.get(OutboxEvent, event_id)
            lead_id = ev.payload["lead_id"]
            lead = s.get(Lead, lead_id, execution_options={"include_deleted": True})
            child_ids = [
                r
                for (r,) in s.execute(
                    sa.select(LeadNote.id).where(LeadNote.lead_id == lead_id).execution_options(include_deleted=True)
                )
            ]
            child_ids += [
                r
                for (r,) in s.execute(
                    sa.select(LeadActivity.id)
                    .where(LeadActivity.lead_id == lead_id)
                    .execution_options(include_deleted=True)
                )
            ]
            ids = [lead_id, *child_ids]
            conn = s.connection()
            migration_support.drop_immutability_guards(conn, "audit_log")
            rows = s.execute(
                sa.select(AuditLog.id, AuditLog.entity_type, AuditLog.old_value, AuditLog.new_value).where(
                    sa.or_(AuditLog.entity_id.in_(ids), AuditLog.parent_entity_id == lead_id)
                )
            ).all()
            table = AuditLog.__table__
            rewritten = 0
            for rid, etype, old, new in rows:
                policy = policy_for(etype)
                pii = policy.pii if policy else frozenset()
                if not pii:
                    continue
                new_old, new_new = _erase_payload(old, pii), _erase_payload(new, pii)
                if new_old != old or new_new != new:
                    s.execute(table.update().where(table.c.id == rid).values(old_value=new_old, new_value=new_new))
                    rewritten += 1
            migration_support.restore_immutability_guards(conn, "audit_log")
            # 4. operational rows for the lead are purged (notifications, then their outbox events)
            for n in s.execute(
                sa.select(Notification)
                .where(Notification.entity_type == "lead", Notification.entity_id == lead_id)
                .execution_options(include_deleted=True)
            ).scalars():
                s.delete(n)
            s.flush()
            # 7. verification: no PII value remains for the lead or its children
            for _rid, etype, old, new in s.execute(
                sa.select(AuditLog.id, AuditLog.entity_type, AuditLog.old_value, AuditLog.new_value).where(
                    sa.or_(AuditLog.entity_id.in_(ids), AuditLog.parent_entity_id == lead_id)
                )
            ).all():
                pii = policy_for(etype).pii if policy_for(etype) else frozenset()
                for payload in (old or {}, new or {}, (old or {}).get("_snapshot") or {}):
                    for k in pii:
                        if payload.get(k) not in (
                            None,
                            "[ERASED]",
                            "[REDACTED]",
                            "",
                            "Anonymized lead",
                            "[anonymized]",
                        ):
                            raise RuntimeError("erasure verification failed: PII remains in audit_log")
            write_explicit_audit(
                s,
                entity_type="lead",
                entity_id=lead_id,
                action="ANONYMIZE",
                new_value={
                    "stage": "audit_history",
                    "rows_rewritten": rewritten,
                    "request_ref": None,
                    "legal_basis": "erasure",
                },
                changed_fields=None,
            )
            ev.status, ev.processed_on = "DONE", db.tx_time(s)
            done += 1
            del lead
    return done


# --- closed-lead retention (04 §14.1) ------------------------------------------------------------


def lead_retention() -> dict:
    cfg = settings()
    if not cfg.lead_retention_enabled or not cfg.lead_retention_days:
        return {"enabled": False, "anonymized": 0}
    from veda.modules.crm.leads.models import Lead
    from veda.modules.crm.leads.service import anonymize

    count = 0
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        cutoff = db.tx_time(s) - timedelta(days=cfg.lead_retention_days)
        leads = (
            s.execute(
                sa.select(Lead)
                .where(
                    sa.or_(Lead.status.in_(("WON", "LOST")), Lead.spam_status == "CONFIRMED_SPAM"),
                    Lead.status_changed_on < cutoff,
                    Lead.anonymized_on.is_(None),
                )
                .execution_options(include_deleted=True)
            )
            .scalars()
            .all()
        )
        for lead in leads:
            anonymize(s, lead, legal_basis="retention", request_ref=None)
            outbox.enqueue(s, "lead.erasure_requested", "lead", lead.id, lead_id=lead.id)
            count += 1
        _summary(s, "lead_retention", "lead", count)
    return {"enabled": True, "anonymized": count}


# --- security log chain (05 §9.6) ---------------------------------------------------------------


def latest_anchor() -> dict | None:
    return anchor_store.store().latest("anchor")


def _archived_through(archives: list[dict]) -> tuple[int, str | None]:
    """Highest archived sequence and the row hash it ends with, from the stored manifests (0, None if none)."""
    last = max(archives, key=lambda a: a["last_seq"], default=None)
    return (last["last_seq"], last["last_row_hash"]) if last else (0, None)


def _archived_events_online(s: Session) -> set[tuple[int, str]]:
    found: set[tuple[int, str]] = set()
    detail: dict[str, Any] | None
    for detail in s.execute(
        sa.select(SecurityEventLog.detail).where(
            SecurityEventLog.event_type == "SECURITY_LOG_ARCHIVED", SecurityEventLog.outcome == "SUCCESS"
        )
    ).scalars():
        if detail and "through_seq" in detail:
            found.add((int(detail["through_seq"]), str(detail.get("anchor"))))
    return found


def _verify_archives(
    store, s: Session, anchors: dict[int, dict]
) -> tuple[int, str | None, str | None, int, int | None]:
    """Check the finalised archive manifests against the write-once exports (RR-05).

    Manifests must be contiguous from sequence 1; each export must match its manifest's SHA-256, count and range,
    and its rows must recompute to a chain that starts where the previous segment ended and ends at the
    manifest's last row hash; each manifest must be announced by its SECURITY_LOG_ARCHIVED event; every anchor that
    falls inside the archived range must match the exported row (FC-01). Returns (through, through_hash, problem, at_seq,
    unannounced_first_seq); the announcement is reported by the caller after the online checks, which name a
    removed announcement row more precisely.
    """
    keys = settings().chain_keys
    manifests = sorted(store.all("archive"), key=lambda m: m["first_seq"])
    expected, prev_hash = 1, None
    announced: set[tuple[int, str]] = set()
    for m in manifests:
        if m["first_seq"] != expected or m["last_seq"] < m["first_seq"]:
            return expected - 1, prev_hash, "archive manifests not contiguous", expected, None
        blob = store.get_blob("export", anchor_store.export_id(m))
        if blob is None:
            return expected - 1, prev_hash, "archive export missing", m["first_seq"], None
        if hashlib.sha256(blob).hexdigest() != m["sha256"]:
            return expected - 1, prev_hash, "archive export hash mismatch", m["first_seq"], None
        lines = blob.decode().splitlines()
        if len(lines) != m["count"] or m["count"] != m["last_seq"] - m["first_seq"] + 1:
            return expected - 1, prev_hash, "archive export count mismatch", m["first_seq"], None
        for offset, line in enumerate(lines):
            row = json.loads(line)
            seq = m["first_seq"] + offset
            key = keys.get(row.get("chain_key_label"))
            rep = {k: v for k, v in row.items() if k not in ("row_hash", "prev_hash")}
            if row.get("chain_seq") != seq or row.get("prev_hash") != prev_hash or key is None:
                return expected - 1, prev_hash, "archive export chain broken", seq, None
            if not hmac.compare_digest(security_events.hash_representation(rep, prev_hash, key), row["row_hash"]):
                return expected - 1, prev_hash, "archive export chain broken", seq, None
            anchored = anchors.get(seq)
            if anchored is not None and row["row_hash"] != anchored["row_hash"]:
                return expected - 1, prev_hash, "anchor mismatch", seq, None
            if row.get("event_type") == "SECURITY_LOG_ARCHIVED" and row.get("outcome") == "SUCCESS":
                detail = row.get("detail") or {}
                announced.add((int(detail.get("through_seq", 0)), str(detail.get("anchor"))))
            prev_hash = row["row_hash"]
        if prev_hash != m["last_row_hash"]:
            return expected - 1, prev_hash, "archive export chain broken", m["last_seq"], None
        expected = m["last_seq"] + 1
    announced |= _archived_events_online(s)
    for m in manifests:
        if (m["last_seq"], m["sha256"][:16]) not in announced:
            return expected - 1, prev_hash, None, 0, m["first_seq"]
    return expected - 1, prev_hash, None, 0, None


def verify_chain() -> security_events.ChainReport:
    """Verify the online chain against the external anchor store (IR-03, RR-05).

    Detects: a modified row (hash), a removed row (gap), removal of the oldest rows (the first online row must
    follow the last archived segment and chain to its last hash), a forged, altered or unannounced archive
    manifest or export, a deletion committed without its manifest being finalised, removal of the anchored row
    unless a verified export covers it, and truncation below the latest anchor (head < anchored sequence). An
    unreadable anchor store is itself a verification failure (RR-07).

    Every retained anchor is checked, not only the latest (FC-01): someone holding the chain key can rewrite
    history, recompute every later hash and post a new anchor for the forged head, but the anchors already in
    write-once storage still name the original hashes. The earliest contradicted anchor is reported."""
    store = anchor_store.store()
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        report = None
        try:
            anchors = {a["chain_seq"]: a for a in store.all("anchor")}
            anchor = anchors[max(anchors)] if anchors else None
            through, through_hash, problem, at_seq, unannounced = _verify_archives(store, s, anchors)
            pending = store.all("pending")
        except Exception:
            log.critical("security_log_anchor_store_unavailable", exc_info=True)
            anchors, anchor, through, through_hash, pending = {}, None, 0, None, []
            problem, at_seq, unannounced = "anchor store unavailable", 0, None
        first_seq, head_seq = s.execute(
            sa.select(sa.func.min(SecurityEventLog.chain_seq), sa.func.max(SecurityEventLog.chain_seq))
        ).one()
        # A pending manifest whose rows are gone was committed but never finalised: a durable failure that the next
        # archival run repairs. One whose rows are still online is an abandoned attempt and is ignored (RR-06).
        stranded = [p for p in pending if p["last_seq"] > through and (first_seq is None or first_seq > p["last_seq"])]
        if problem:
            report = security_events.ChainReport(False, 0, through, through_hash, problem, at_seq)
        elif stranded:
            p = min(stranded, key=lambda m: m["first_seq"])
            report = security_events.ChainReport(
                False, 0, through, through_hash, "archive not finalised", p["first_seq"]
            )
        elif first_seq is None:
            if anchor is not None or through:
                report = security_events.ChainReport(False, 0, 0, None, "online log empty below anchor", 1)
        elif first_seq != through + 1:
            report = security_events.ChainReport(False, 0, first_seq - 1, None, "prefix removed", through + 1)
        elif anchor is not None and head_seq < anchor["chain_seq"]:
            report = security_events.ChainReport(False, 0, head_seq, None, "truncated below anchor", head_seq + 1)
        if report is None and first_seq is not None:
            report = security_events.verify_chain(
                s, from_seq=first_seq, anchor_hash=through_hash, from_genesis=through == 0
            )
            online_anchors = sorted(seq for seq in anchors if seq > through)
            if report.ok and online_anchors:
                online_hashes = dict(
                    s.execute(
                        sa.select(SecurityEventLog.chain_seq, SecurityEventLog.row_hash).where(
                            SecurityEventLog.chain_seq.in_(online_anchors)
                        )
                    ).all()
                )
                for seq in online_anchors:  # ascending: the earliest contradiction is reported
                    if seq not in online_hashes:
                        problem = "anchored row missing"
                    elif online_hashes[seq] != anchors[seq]["row_hash"]:
                        problem = "anchor mismatch"
                    else:
                        continue
                    report = security_events.ChainReport(
                        False, report.checked, report.head_seq, report.head_hash, problem, seq
                    )
                    break
        if unannounced is not None and (report is None or report.ok):
            report = security_events.ChainReport(
                False, 0, through, through_hash, "archive not announced by SECURITY_LOG_ARCHIVED", unannounced
            )
        report = report or security_events.ChainReport(True, 0, 0, None)
        metrics.emit("ChainVerificationFailed", 0 if report.ok else 1)
        if not report.ok:
            security_events.record(
                s, "SECURITY_LOG_CHAIN_BROKEN", "FAILURE", detail={"at_seq": report.at_seq, "problem": report.problem}
            )
            log.critical("security_log_chain_broken at_seq=%s problem=%s", report.at_seq, report.problem)
    return report


def anchor_chain() -> dict | None:
    """Write the chain head to the external anchor store (S3 Object Lock in production). The store is written
    outside any database transaction, so the write lock is never held across network I/O."""
    with db.unit_of_work(write=False) as s:
        head = s.execute(
            sa.select(SecurityEventLog).order_by(SecurityEventLog.chain_seq.desc()).limit(1)
        ).scalar_one_or_none()
        if head is None:
            return None
        anchor: dict[str, Any] = {
            "kind": "anchor",
            "chain_seq": head.chain_seq,
            "row_hash": head.row_hash,
            "chain_key_label": head.chain_key_label,
            "anchored_on": clock.to_rfc3339(clock.now(), micros=True),
        }
    with actor(system_context("CLI")), security_events.deferred_scope():
        try:
            anchor_store.store().put("anchor", anchor["chain_seq"], anchor)
        except Exception:
            # Failure to anchor is an alert, never silent (SEVT-007, SEVT-009).
            log.critical("security_log_anchor_failed head_seq=%s", anchor["chain_seq"], exc_info=True)
            metrics.emit("ChainAnchorFailed", 1)
            security_events.defer(
                "SECURITY_LOG_CHAIN_ANCHORED",
                "FAILURE",
                failure_reason="POLICY",
                detail={"head_seq": anchor["chain_seq"]},
            )
            raise
        with db.unit_of_work(write=True) as s:
            security_events.record(
                s,
                "SECURITY_LOG_CHAIN_ANCHORED",
                "SUCCESS",
                detail={"head_seq": anchor["chain_seq"], "anchor": anchor["row_hash"][:16]},
            )
    return anchor


def _finalise_committed_archives(store) -> int:
    """Finalise pending manifests whose deletion committed (rows gone, SECURITY_LOG_ARCHIVED recorded): the
    recovery step for a failure between the commit and the final write (RR-06). Idempotent.

    Several pending manifests can end at the same sequence (an abandoned attempt, a concurrent loser, FC-13);
    only the one whose export the committed run announced is finalised, and only once."""
    finalised = {m["last_seq"] for m in store.all("archive")}
    done = 0
    with db.unit_of_work(write=False) as s:
        first_online = s.execute(sa.select(sa.func.min(SecurityEventLog.chain_seq))).scalar()
        announced = _archived_events_online(s)
    for p in sorted(store.all("pending"), key=lambda m: m["first_seq"]):
        if p["last_seq"] in finalised:  # a committed segment ends here; any other pending for it was abandoned
            continue
        gone = first_online is None or first_online > p["last_seq"]
        if gone and (p["last_seq"], p["sha256"][:16]) in announced:
            store.put("archive", p["last_seq"], p)
            finalised.add(p["last_seq"])
            done += 1
    return done


def archive_security_events(export_dir: str | None = None) -> dict:
    """Monthly archival (05 §9.4): export, verify, record, delete, finalise. Refuses without approved retention.

    The segment is the contiguous chain-sequence prefix whose rows are all older than the cutoff (IR-26). Ordering
    (RR-06): the export and a *pending* manifest go to write-once storage, then one database transaction appends
    SECURITY_LOG_ARCHIVED and deletes exactly the exported range, and only after it commits is the *archive*
    manifest written. A failure before the commit leaves the rows online and the pending manifest is ignored; a
    failure after it is repaired by the next run (``_finalise_committed_archives``).

    No object-store I/O happens inside a write transaction (FC-14): the segment is read and verified in a read
    transaction, exported and staged with no transaction open, and the write transaction (on SQLite the
    database-wide write lock) only re-checks that the exported rows are still the online prefix, then records and
    deletes. Each run writes its export and pending manifest under its own ``(first_seq, last_seq, run id)`` key
    (FC-13), so an abandoned attempt or a concurrent run never blocks a later segment."""
    days = settings().security_event_online_retention_days
    if not days:
        raise RuntimeError("SECURITY_EVENT_ONLINE_RETENTION_DAYS is not configured (OWNER-INPUT-002); nothing archived")
    out_dir = Path(export_dir or "var/archive")
    out_dir.mkdir(parents=True, exist_ok=True)
    store = anchor_store.store()
    try:
        recovered = _finalise_committed_archives(store)
        through, through_hash = _archived_through(store.all("archive"))
        # 1. Read and verify the segment. A read transaction: nothing here blocks the application's writers.
        with actor(system_context("CLI")), db.unit_of_work(write=False) as s:
            cutoff = db.tx_time(s) - timedelta(days=days)
            rows = []
            for r in s.execute(sa.select(SecurityEventLog).order_by(SecurityEventLog.chain_seq)).scalars():
                if r.occurred_on >= cutoff:
                    break
                rows.append(r)
            if not rows:
                metrics.emit_many(
                    {"SecurityLogArchivedRows": (0.0, "Count"), "SecurityLogArchiveFailed": (0.0, "Count")}
                )
                return {"archived": 0, "recovered": recovered}
            first, last = rows[0], rows[-1]
            if first.chain_seq != through + 1 or last.chain_seq - first.chain_seq + 1 != len(rows):
                raise RuntimeError("archive segment is not contiguous with the previous archive")
            segment = security_events.verify_chain(
                s, from_seq=first.chain_seq, anchor_hash=through_hash, from_genesis=through == 0, to_seq=last.chain_seq
            )
            if not segment.ok:
                raise RuntimeError(f"refusing to archive a broken chain segment: {segment.problem} at {segment.at_seq}")
            lines = [
                json.dumps(
                    {**security_events.row_representation(r), "prev_hash": r.prev_hash, "row_hash": r.row_hash},
                    sort_keys=True,
                )
                for r in rows
            ]
            first_seq, last_seq, count = first.chain_seq, last.chain_seq, len(rows)
            last_row_hash, last_key_label = last.row_hash, last.chain_key_label
        blob = ("\n".join(lines) + "\n").encode()
        checksum = hashlib.sha256(blob).hexdigest()
        run = anchor_store.segment_id(first_seq, last_seq, new_id())
        # 2. Export and stage with no transaction open: object-store latency never holds the write lock.
        path = out_dir / f"security_event_log_{first_seq}_{last_seq}.jsonl"
        path.write_bytes(blob)
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksum or len(path.read_text().splitlines()) != count:
            raise RuntimeError("archive verification failed")
        manifest: dict[str, Any] = {
            "kind": "archive",
            "first_seq": first_seq,
            "last_seq": last_seq,
            "count": count,
            "sha256": checksum,
            "last_row_hash": last_row_hash,
            "chain_key_label": last_key_label,
            "file": path.name,
            "export_id": run,
        }
        store.put_blob("export", run, blob)
        store.put("pending", run, manifest)
        # 3. Record and delete in one short write transaction, after re-checking under the write lock that the
        #    exported rows are still exactly the online prefix (a concurrent run may have archived them meanwhile).
        with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
            table = cast(sa.Table, SecurityEventLog.__table__)
            online_first = s.execute(sa.select(sa.func.min(table.c.chain_seq))).scalar()
            if online_first != first_seq:
                log.info("security_log_archive_superseded first_seq=%s online_first=%s", first_seq, online_first)
                metrics.emit_many(
                    {"SecurityLogArchivedRows": (0.0, "Count"), "SecurityLogArchiveFailed": (0.0, "Count")}
                )
                return {"archived": 0, "recovered": recovered, "superseded": True}
            still, still_last_hash = s.execute(
                sa.select(sa.func.count(), sa.func.max(sa.case((table.c.chain_seq == last_seq, table.c.row_hash))))
                .select_from(table)
                .where(table.c.chain_seq.between(first_seq, last_seq))
            ).one()
            if still != count or still_last_hash != last_row_hash:
                raise RuntimeError("archive segment changed after it was exported")
            # Append the summary event first so the chain continues past the archived segment.
            security_events.record(
                s,
                "SECURITY_LOG_ARCHIVED",
                "SUCCESS",
                detail={"through_seq": last_seq, "count": count, "anchor": checksum[:16]},
            )
            conn = s.connection()
            migration_support.drop_immutability_guards(conn, "security_event_log")
            result = s.execute(sa.delete(table).where(table.c.chain_seq.between(first_seq, last_seq)))
            deleted = getattr(result, "rowcount", -1)
            migration_support.restore_immutability_guards(conn, "security_event_log")
            if deleted != count:
                raise RuntimeError(f"archival deleted {deleted} rows but exported {count}")
        # 4. Finalise after the commit.
        store.put("archive", last_seq, manifest)
    except Exception:
        log.critical("security_log_archive_failed", exc_info=True)
        metrics.emit("SecurityLogArchiveFailed", 1)
        raise
    metrics.emit_many({"SecurityLogArchivedRows": (float(count), "Count"), "SecurityLogArchiveFailed": (0.0, "Count")})
    return {"archived": count, "file": str(path), "sha256": checksum, "recovered": recovered}


# --- governance invariants (06 §7.3) ----------------------------------------------------------------


def check_invariants() -> dict:
    from veda.platform.rbac import guards

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        state = guards.evaluate(s)
        if not (state.i1 and state.i2 and state.i3):
            for problem in state.problems:
                security_events.record(
                    s,
                    "GOVERNANCE_INVARIANT_FAILED",
                    "FAILURE",
                    severity="CRITICAL",
                    detail={"invariant": problem[:2], "problem": problem},
                )
            log.critical("governance_invariant_failed problems=%s", state.problems)
        elif not state.i2_effective:
            log.error("no_effective_recovery_administrator")
        metrics.emit_many(
            {
                "GovernanceInvariantFailures": (float(len(state.problems)), "Count"),
                "NoEffectiveRecoveryAdmin": (0.0 if state.i2_effective else 1.0, "Count"),
            }
        )
        return {
            "i1": state.i1,
            "i2": state.i2,
            "i2_effective": state.i2_effective,
            "i3": state.i3,
            "problems": state.problems,
        }


# --- approvals, reminders, digests ----------------------------------------------------------------


def expire_approvals() -> int:
    from veda.platform.rbac import governance
    from veda.platform.rbac.models import AdminApprovalRequest

    count = 0
    with actor(system_context()), db.unit_of_work(write=True) as s:
        for req in s.execute(
            sa.select(AdminApprovalRequest).where(
                AdminApprovalRequest.status == "PENDING", AdminApprovalRequest.expires_on <= db.tx_time(s)
            )
        ).scalars():
            governance._expire_if_due(s, req)
            count += 1
    return count


def execute_due_break_glass() -> int:
    from veda.platform.rbac import governance
    from veda.platform.rbac.models import AdminApprovalRequest

    count = 0
    with db.unit_of_work(write=False) as s:
        due = (
            s.execute(
                sa.select(AdminApprovalRequest.id).where(
                    AdminApprovalRequest.channel == "BREAK_GLASS",
                    AdminApprovalRequest.status == "APPROVED",
                    AdminApprovalRequest.not_before <= clock.now(),
                )
            )
            .scalars()
            .all()
        )
    for rid in due:
        with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
            governance.break_glass_execute(s, s.get(AdminApprovalRequest, rid))
            count += 1
    return count


def follow_up_reminders(window_minutes: int = 15) -> int:
    from veda.modules.crm.leads.models import LeadActivity

    count = 0
    with actor(system_context()), db.unit_of_work(write=True) as s:
        horizon = db.tx_time(s) + timedelta(minutes=window_minutes)
        notified = sa.select(OutboxEvent.aggregate_id).where(OutboxEvent.event_type == "activity.follow_up_due")
        for act in s.execute(
            sa.select(LeadActivity).where(
                LeadActivity.activity_status == "PLANNED",
                LeadActivity.scheduled_on <= horizon,
                LeadActivity.id.not_in(notified),
            )
        ).scalars():
            outbox.enqueue(s, "activity.follow_up_due", "lead_activity", act.id, activity_id=act.id)
            count += 1
    return count


def spam_review() -> dict:
    from veda.modules.crm.leads.models import Lead

    with actor(system_context()), db.unit_of_work(write=True) as s:
        suspected = s.execute(sa.select(Lead.created_on).where(Lead.spam_status == "SUSPECTED")).scalars().all()
        if suspected:
            outbox.enqueue(s, "lead.spam_review_digest", "app_user", SYSTEM_USER_ID)
        age_limit = db.tx_time(s) - timedelta(hours=settings().spam_review_age_hours)
        stale = sum(1 for c in suspected if c < age_limit)
        if stale:
            log.error("spam_queue_ageing count=%s", stale)  # operational alert (N-A3)
        return {"suspected": len(suspected), "stale": stale}


# --- backups (OPS-002, OPS-009; IR-11) ------------------------------------------------------------


def snapshot() -> dict:
    from veda.platform import backups

    return backups.snapshot()


def restore_verify() -> dict:
    from veda.platform import backups

    return backups.restore_verify()


def disk_usage() -> dict:
    from veda.platform import backups

    return backups.disk_usage()


def estimate_retention() -> dict:
    """Soft-delete Budgetary Estimates never linked to a lead once expired beyond the retention period (ADR-012).
    They hold no personal data; linked estimates follow the lead."""
    from veda.modules.estimator.service import purge_expired

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        return {"removed": purge_expired(s), "retention_days": settings().estimate_retention_days}
