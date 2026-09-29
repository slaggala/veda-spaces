"""Maintenance jobs (03 §2.10, 04 §14, 05 §9.4, §9.6, 06 §7.3, 07 §8).

Run as SYSTEM from the maintenance CLI or the scheduler. Only the maintenance
process lifts the evidence-store immutability guards, inside the same
transaction as the change it makes (A-02). Retention jobs refuse to run until
owner-approved values are configured (OWNER-INPUT-002).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from pathlib import Path

import sqlalchemy as sa

from veda.config import settings
from veda.kernel import clock, db, migration_support, outbox
from veda.kernel.audit_hook import write_explicit_audit
from veda.kernel.audit_registry import policy_for
from veda.kernel.context import actor, system_context
from veda.kernel.ids import SYSTEM_USER_ID
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
    security_events.record(s, "MAINTENANCE_PURGE", "SUCCESS", detail={"job": job, "table": table, "count": count,
                                                                        "enabled": enabled})


# --- purge (03 §2.10) --------------------------------------------------------------------------

def purge() -> dict:
    cfg = settings()
    result: dict = {}
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        now = db.tx_time(s)
        # 1 mfa_challenge: expires_on older than 1 day
        rows = s.execute(sa.select(MfaChallenge).where(MfaChallenge.expires_on < now - timedelta(days=1))).scalars().all()
        for r in rows:
            s.delete(r)
        s.flush()
        result["mfa_challenge"] = len(rows)
        _summary(s, "purge", "mfa_challenge", len(rows))
        if cfg.token_retention_days is not None:
            cutoff = now - timedelta(days=cfg.token_retention_days)
            # 2 user_action_token
            rows = s.execute(sa.select(UserActionToken).where(sa.or_(
                UserActionToken.used_on < cutoff, UserActionToken.invalidated_on < cutoff,
                UserActionToken.expires_on < cutoff))).scalars().all()
            for r in rows:
                s.delete(r)
            s.flush()
            result["user_action_token"] = len(rows)
            _summary(s, "purge", "user_action_token", len(rows))
        if cfg.user_session_retention_days is not None:
            cutoff = now - timedelta(days=cfg.user_session_retention_days)
            purgeable = sa.select(UserSession.id).where(sa.or_(UserSession.revoked_on < cutoff,
                                                               UserSession.absolute_expires_on < cutoff))
            # 3 refresh_token: its session is purgeable, or expired past token retention
            token_cutoff = now - timedelta(days=cfg.token_retention_days or cfg.user_session_retention_days)
            rows = s.execute(sa.select(RefreshToken).where(sa.or_(RefreshToken.session_id.in_(purgeable),
                                                                  RefreshToken.expires_on < token_cutoff))).scalars().all()
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
            rows = s.execute(sa.select(Notification).where(sa.or_(
                sa.and_(Notification.read_on.is_not(None), Notification.read_on < read_cut),
                sa.and_(Notification.read_on.is_(None), Notification.created_on < unread_cut)))
                .execution_options(include_deleted=True)).scalars().all()
            for r in rows:
                s.delete(r)
            s.flush()
            result["notification"] = len(rows)
            _summary(s, "purge", "notification", len(rows))
        if cfg.outbox_retention_days is not None:
            # 6 outbox_event: DONE, old, and not referenced by a notification
            cut = now - timedelta(days=cfg.outbox_retention_days)
            referenced = sa.select(Notification.source_event_id).where(Notification.source_event_id.is_not(None)).execution_options(
                include_deleted=True)
            rows = s.execute(sa.select(OutboxEvent).where(
                OutboxEvent.status == "DONE", OutboxEvent.processed_on < cut, OutboxEvent.id.not_in(referenced))).scalars().all()
            for r in rows:
                s.delete(r)
            s.flush()
            result["outbox_event"] = len(rows)
            _summary(s, "purge", "outbox_event", len(rows))
        # Expired email-change proposals are cleared (05 §8.6 step 8).
        expired = 0
        for user in s.execute(sa.select(User).where(User.proposed_email.is_not(None))).scalars():
            open_tok = s.execute(sa.select(UserActionToken.id).where(
                UserActionToken.user_id == user.id, UserActionToken.purpose == "EMAIL_VERIFICATION",
                UserActionToken.used_on.is_(None), UserActionToken.invalidated_on.is_(None),
                UserActionToken.expires_on > now)).first()
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
        pending = s.execute(sa.select(OutboxEvent.id).where(OutboxEvent.event_type == "lead.erasure_requested",
                                                            OutboxEvent.status.in_(("PENDING", "FAILED")))).scalars().all()
    for event_id in pending:
        with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
            ev = s.get(OutboxEvent, event_id)
            lead_id = ev.payload["lead_id"]
            lead = s.get(Lead, lead_id, execution_options={"include_deleted": True})
            child_ids = [r for (r,) in s.execute(sa.select(LeadNote.id).where(LeadNote.lead_id == lead_id)
                                                 .execution_options(include_deleted=True))]
            child_ids += [r for (r,) in s.execute(sa.select(LeadActivity.id).where(LeadActivity.lead_id == lead_id)
                                                  .execution_options(include_deleted=True))]
            ids = [lead_id, *child_ids]
            conn = s.connection()
            migration_support.drop_immutability_guards(conn, "audit_log")
            rows = s.execute(sa.select(AuditLog.id, AuditLog.entity_type, AuditLog.old_value, AuditLog.new_value)
                             .where(sa.or_(AuditLog.entity_id.in_(ids), AuditLog.parent_entity_id == lead_id))).all()
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
            for n in s.execute(sa.select(Notification).where(Notification.entity_type == "lead", Notification.entity_id == lead_id)
                               .execution_options(include_deleted=True)).scalars():
                s.delete(n)
            s.flush()
            # 7. verification: no PII value remains for the lead or its children
            for _rid, etype, old, new in s.execute(sa.select(AuditLog.id, AuditLog.entity_type, AuditLog.old_value,
                                                             AuditLog.new_value).where(sa.or_(
                                                                 AuditLog.entity_id.in_(ids), AuditLog.parent_entity_id == lead_id))).all():
                pii = policy_for(etype).pii if policy_for(etype) else frozenset()
                for payload in (old or {}, new or {}, (old or {}).get("_snapshot") or {}):
                    for k in pii:
                        if payload.get(k) not in (None, "[ERASED]", "[REDACTED]", "", "Anonymized lead", "[anonymized]"):
                            raise RuntimeError("erasure verification failed: PII remains in audit_log")
            write_explicit_audit(s, entity_type="lead", entity_id=lead_id, action="ANONYMIZE",
                                 new_value={"stage": "audit_history", "rows_rewritten": rewritten,
                                            "request_ref": None, "legal_basis": "erasure"},
                                 changed_fields=None)
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
        leads = s.execute(sa.select(Lead).where(
            sa.or_(Lead.status.in_(("WON", "LOST")), Lead.spam_status == "CONFIRMED_SPAM"),
            Lead.status_changed_on < cutoff, Lead.anonymized_on.is_(None)).execution_options(include_deleted=True)).scalars().all()
        for lead in leads:
            anonymize(s, lead, legal_basis="retention", request_ref=None)
            outbox.enqueue(s, "lead.erasure_requested", "lead", lead.id, lead_id=lead.id)
            count += 1
        _summary(s, "lead_retention", "lead", count)
    return {"enabled": True, "anonymized": count}


# --- security log chain (05 §9.6) ---------------------------------------------------------------

def _anchor_dir() -> Path:
    return Path(settings().anchor_dir or "var/anchors")


def latest_anchor() -> dict | None:
    path = _anchor_dir() / "anchors.jsonl"
    if not path.exists():
        return None
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return json.loads(lines[-1]) if lines else None


def verify_chain() -> security_events.ChainReport:
    anchor = latest_anchor()
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        if anchor:
            # Recompute from the last external anchor (05 §9.6). The anchored row may have been archived.
            anchored = s.execute(sa.select(SecurityEventLog.row_hash).where(
                SecurityEventLog.chain_seq == anchor["chain_seq"])).scalar()
            if anchored is not None and anchored != anchor["row_hash"]:
                report = security_events.ChainReport(False, 0, anchor["chain_seq"], None, "anchor mismatch",
                                                     anchor["chain_seq"])
            else:
                report = security_events.verify_chain(s, from_seq=anchor["chain_seq"] + 1, anchor_hash=anchor["row_hash"])
        else:
            report = security_events.verify_chain(s)
        if not report.ok:
            security_events.record(s, "SECURITY_LOG_CHAIN_BROKEN", "FAILURE",
                                   detail={"at_seq": report.at_seq, "problem": report.problem})
            log.critical("security_log_chain_broken at_seq=%s problem=%s", report.at_seq, report.problem)
    return report


def anchor_chain() -> dict | None:
    """Write the chain head to the anchor store. Production: S3 Object Lock bucket via a write-only role."""
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        head = s.execute(sa.select(SecurityEventLog).order_by(SecurityEventLog.chain_seq.desc()).limit(1)).scalar_one_or_none()
        if head is None:
            return None
        anchor = {"chain_seq": head.chain_seq, "row_hash": head.row_hash, "chain_key_label": head.chain_key_label,
                  "anchored_on": clock.to_rfc3339(clock.now(), micros=True)}
        if settings().anchor_bucket:  # pragma: no cover - AWS
            import boto3

            boto3.client("s3", region_name=settings().aws_region).put_object(
                Bucket=settings().anchor_bucket, Key=f"security-log/{head.chain_seq:012d}.json",
                Body=json.dumps(anchor).encode(), ObjectLockMode="COMPLIANCE",
                ObjectLockRetainUntilDate=clock.now() + timedelta(days=3650))
        else:
            path = _anchor_dir()
            path.mkdir(parents=True, exist_ok=True)
            with (path / "anchors.jsonl").open("a") as fh:
                fh.write(json.dumps(anchor) + "\n")
        security_events.record(s, "SECURITY_LOG_CHAIN_ANCHORED", "SUCCESS",
                               detail={"head_seq": head.chain_seq, "anchor": anchor["row_hash"][:16]})
        return anchor


def archive_security_events(export_dir: str | None = None) -> dict:
    """Monthly archival (05 §9.4): export, verify, anchor, delete. Refuses without approved retention."""
    days = settings().security_event_online_retention_days
    if not days:
        raise RuntimeError("SECURITY_EVENT_ONLINE_RETENTION_DAYS is not configured (OWNER-INPUT-002); nothing archived")
    out_dir = Path(export_dir or "var/archive")
    out_dir.mkdir(parents=True, exist_ok=True)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        cutoff = db.tx_time(s) - timedelta(days=days)
        rows = s.execute(sa.select(SecurityEventLog).where(SecurityEventLog.occurred_on < cutoff)
                         .order_by(SecurityEventLog.chain_seq)).scalars().all()
        if not rows:
            return {"archived": 0}
        lines = [json.dumps({**security_events.row_representation(r), "prev_hash": r.prev_hash, "row_hash": r.row_hash},
                            sort_keys=True) for r in rows]
        blob = ("\n".join(lines) + "\n").encode()
        checksum = hashlib.sha256(blob).hexdigest()
        path = out_dir / f"security_event_log_{rows[0].chain_seq}_{rows[-1].chain_seq}.jsonl"
        path.write_bytes(blob)
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksum or len(path.read_text().splitlines()) != len(rows):
            raise RuntimeError("archive verification failed")
        last = rows[-1]
        anchor_path = _anchor_dir()
        anchor_path.mkdir(parents=True, exist_ok=True)
        with (anchor_path / "anchors.jsonl").open("a") as fh:
            fh.write(json.dumps({"chain_seq": last.chain_seq, "row_hash": last.row_hash,
                                 "chain_key_label": last.chain_key_label, "archive": path.name}) + "\n")
        # Append the summary event first so the chain continues past the archived segment.
        security_events.record(s, "SECURITY_LOG_ARCHIVED", "SUCCESS",
                               detail={"through_seq": last.chain_seq, "count": len(rows), "anchor": checksum[:16]})
        conn = s.connection()
        migration_support.drop_immutability_guards(conn, "security_event_log")
        table = SecurityEventLog.__table__
        s.execute(table.delete().where(table.c.chain_seq <= last.chain_seq))
        migration_support.restore_immutability_guards(conn, "security_event_log")
    return {"archived": len(rows), "file": str(path), "sha256": checksum}


# --- governance invariants (06 §7.3) ----------------------------------------------------------------

def check_invariants() -> dict:
    from veda.platform.rbac import guards

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        state = guards.evaluate(s)
        if not (state.i1 and state.i2 and state.i3):
            for problem in state.problems:
                security_events.record(s, "GOVERNANCE_INVARIANT_FAILED", "FAILURE", severity="CRITICAL",
                                       detail={"invariant": problem[:2], "problem": problem})
            log.critical("governance_invariant_failed problems=%s", state.problems)
        elif not state.i2_effective:
            log.error("no_effective_recovery_administrator")
        return {"i1": state.i1, "i2": state.i2, "i2_effective": state.i2_effective, "i3": state.i3,
                "problems": state.problems}


# --- approvals, reminders, digests ----------------------------------------------------------------

def expire_approvals() -> int:
    from veda.platform.rbac import governance
    from veda.platform.rbac.models import AdminApprovalRequest

    count = 0
    with actor(system_context()), db.unit_of_work(write=True) as s:
        for req in s.execute(sa.select(AdminApprovalRequest).where(
                AdminApprovalRequest.status == "PENDING", AdminApprovalRequest.expires_on <= db.tx_time(s))).scalars():
            governance._expire_if_due(s, req)
            count += 1
    return count


def execute_due_break_glass() -> int:
    from veda.platform.rbac import governance
    from veda.platform.rbac.models import AdminApprovalRequest

    count = 0
    with db.unit_of_work(write=False) as s:
        due = s.execute(sa.select(AdminApprovalRequest.id).where(
            AdminApprovalRequest.channel == "BREAK_GLASS", AdminApprovalRequest.status == "APPROVED",
            AdminApprovalRequest.not_before <= clock.now())).scalars().all()
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
        for act in s.execute(sa.select(LeadActivity).where(
                LeadActivity.activity_status == "PLANNED", LeadActivity.scheduled_on <= horizon,
                LeadActivity.id.not_in(notified))).scalars():
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
