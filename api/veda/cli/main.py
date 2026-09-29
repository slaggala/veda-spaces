"""Operations CLI (02 §3.2 ``cli/``): bootstrap, permission sync, worker, scheduler,
maintenance jobs, break-glass and conformance.

    python -m veda.cli migrate
    python -m veda.cli bootstrap-founder --email founder@vedaspaces.com --name "Founder Name"
    python -m veda.cli worker
    python -m veda.cli scheduler
    python -m veda.cli maintenance purge|erasure-audit|lead-retention|verify-chain|anchor-chain|invariants|archive-security-events
    python -m veda.cli break-glass request|approve|execute ...
    python -m veda.cli conformance
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _settings():
    from veda import config
    from veda.kernel import db

    s = config.settings()  # an in-process caller (tests) may have configured settings already
    problems = config.validate_environment(s)
    if problems:
        raise SystemExit(f"unsafe {s.env} configuration: " + "; ".join(problems))
    try:
        db.engine()
    except RuntimeError:
        db.configure(s.database_url)
    import veda.models  # noqa: F401
    from veda.modules.crm.leads import events  # noqa: F401  (handlers)

    return s


def cmd_migrate(args) -> int:
    from alembic import command
    from alembic.config import Config

    from veda import config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    s = config.load_settings()
    problems = config.validate_environment(s)
    if problems:  # migrations run with the same checks as the application (IR-09)
        raise SystemExit(f"unsafe {s.env} configuration: " + "; ".join(problems))
    cfg.attributes["url"] = s.database_url
    command.upgrade(cfg, "head")
    return 0


def cmd_bootstrap_founder(args) -> int:
    """AUTH-014: creates only the first Founder; refuses if any Founder exists or ever bootstrapped."""
    import sqlalchemy as sa

    from veda.kernel import db, outbox
    from veda.kernel.context import actor, system_context
    from veda.kernel.dto import normalize_email
    from veda.platform.auth import security_events
    from veda.platform.auth.models import SecurityEventLog
    from veda.platform.auth.service import create_action_token
    from veda.platform.identity.models import User, UserCredential
    from veda.platform.notifications.handlers import app_link
    from veda.platform.rbac.models import Role, UserRole

    _settings()
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        # Bootstrap mode: zero Founders have ever existed (06 §7.2.4) — soft-deleted Founders count as history.
        existing = s.execute(
            sa.select(User.id).where(User.protection_level == "FOUNDER").execution_options(include_deleted=True)
        ).first()
        prior = s.execute(
            sa.select(SecurityEventLog.id).where(SecurityEventLog.event_type == "BOOTSTRAP_FOUNDER")
        ).first()
        if existing or prior:
            print("refused: a Founder exists or bootstrap already ran (06 §7.2.4)", file=sys.stderr)
            return 2
        email_norm = normalize_email(args.email)
        if s.execute(sa.select(User.id).where(User.email_normalized == email_norm)).first():
            print("refused: a user with this email exists", file=sys.stderr)
            return 2
        now = db.tx_time(s)
        founder_role = s.execute(sa.select(Role).where(Role.grant_path == "FOUNDER_WORKFLOW_ONLY")).scalar_one()
        user = User(
            email=args.email.strip(),
            email_normalized=email_norm,
            full_name=args.name,
            user_type="HUMAN",
            status="INVITED",
            status_changed_on=now,
            timezone="Asia/Kolkata",
            locale="en-IN",
            protection_level="FOUNDER",
            mfa_required=False,
            authz_version=1,
        )
        s.add(user)
        s.flush()
        s.add(UserCredential(user_id=user.id, password_hash=None, must_change_password=False, failed_login_count=0))
        s.add(UserRole(user_id=user.id, role_id=founder_role.id, reason="Bootstrap"))
        tok, raw = create_action_token(s, user, "INVITE", ttl=timedelta(hours=1))
        s.flush()
        security_events.record(s, "BOOTSTRAP_FOUNDER", "SUCCESS", subject_user_id=user.id, detail={"channel": "cli"})
        if args.email_link:
            outbox.enqueue(s, "user.invited", "app_user", user.id, user_id=user.id, token_id=tok.id)
        print(
            json.dumps(
                {
                    "user_id": user.id,
                    "invite_link": app_link(f"/accept-invite#token={raw}"),
                    "expires_on": tok.expires_on.isoformat(),
                }
            )
        )
    return 0


def cmd_sync_permissions(args) -> int:
    from veda.kernel import db, migration_support

    _settings()
    with db.engine().begin() as conn:
        # Run by an operator, not by a migration: the audit rows say so (IR-A19).
        print(json.dumps(migration_support.sync_permissions(conn, audit=True, via="CLI")))
    return 0


def cmd_worker(args) -> int:
    from veda.platform.notifications import worker

    s = _settings()
    if args.once:
        print(json.dumps({"processed": worker.drain_all()}))
        return 0
    worker.run_forever(s.worker_poll_seconds)
    return 0


JOBS = {
    "purge": "purge",
    "erasure-audit": "run_erasure_audit",
    "lead-retention": "lead_retention",
    "verify-chain": "verify_chain",
    "anchor-chain": "anchor_chain",
    "invariants": "check_invariants",
    "archive-security-events": "archive_security_events",
    "expire-approvals": "expire_approvals",
    "break-glass-due": "execute_due_break_glass",
    "snapshot": "snapshot",
    "restore-verify": "restore_verify",
    "disk-usage": "disk_usage",
    "follow-up-reminders": "follow_up_reminders",
    "spam-review": "spam_review",
}


def cmd_maintenance(args) -> int:
    from veda.platform import maintenance

    _settings()
    result = getattr(maintenance, JOBS[args.job])()
    if hasattr(result, "__dataclass_fields__"):
        result = result.__dict__
    print(json.dumps(result, default=str))
    if args.job == "verify-chain" and not result.get("ok", True):
        return 3
    return 0


def cmd_scheduler(args) -> int:  # pragma: no cover - process loop
    """Periodic jobs. Jobs that lift evidence-store guards run as separate short-lived processes (A-02)."""
    import subprocess
    import time as _time
    from datetime import datetime
    from zoneinfo import ZoneInfo

    _settings()
    frequent = ["expire-approvals", "break-glass-due", "follow-up-reminders", "erasure-audit", "disk-usage"]
    daily = {
        "01:30": "snapshot",
        "02:00": "invariants",
        "02:30": "verify-chain",
        "03:00": "anchor-chain",
        "03:30": "purge",
        "04:00": "lead-retention",
        "05:00": "restore-verify",
        "09:00": "spam-review",
    }
    ran: set[str] = set()
    while True:
        for job in frequent:
            subprocess.run([sys.executable, "-m", "veda.cli", "maintenance", job], check=False)
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        for at, job in daily.items():
            key = f"{now.date()}:{job}"
            if now.strftime("%H:%M") >= at and key not in ran:
                subprocess.run([sys.executable, "-m", "veda.cli", "maintenance", job], check=False)
                ran.add(key)
        _time.sleep(300)


def cmd_break_glass(args) -> int:
    """06 §7.5: custodians act through SSM Session Manager; the principal ARN comes from the session identity."""
    from veda.kernel import db
    from veda.kernel.context import actor, system_context
    from veda.platform.identity.models import User
    from veda.platform.rbac import governance
    from veda.platform.rbac.models import AdminApprovalRequest

    _settings()
    from veda.kernel.errors import ApiError
    from veda.platform.auth import security_events
    from veda.platform.rbac import custodians

    # Failure events are written after the unit of work closes (SEVT-011).
    with security_events.deferred_scope():
        try:
            # The custodian is the caller's AWS identity, resolved before the write lock is taken (IR-06).
            principal = (
                custodians.resolve(args.principal_arn, action=args.action)
                if args.action in ("request", "approve")
                else ""
            )
            with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
                if args.action == "request":
                    target = s.get(User, args.target)
                    if target is None:
                        print("unknown target", file=sys.stderr)
                        return 2
                    payload = json.loads(args.payload) if args.payload else {}
                    req = governance.break_glass_request(
                        s,
                        action=args.founder_action,
                        target=target,
                        reason=args.reason,
                        principal_arn=principal,
                        payload=payload,
                    )
                else:
                    found = s.get(AdminApprovalRequest, args.request)
                    if found is None:
                        print("unknown request", file=sys.stderr)
                        return 2
                    req = found
                    if args.action == "approve":
                        governance.break_glass_approve(s, req, principal_arn=principal)
                    elif args.action == "execute":
                        governance.break_glass_execute(s, req)
                print(json.dumps({"approval_id": req.id, "status": req.status, "not_before": str(req.not_before)}))
        except ApiError as err:
            print(json.dumps({"error": err.code, "detail": err.detail}), file=sys.stderr)
            return 3
    return 0


def cmd_conformance(args) -> int:
    from veda.kernel import conformance, db

    _settings()
    with db.engine().connect() as conn:
        report = conformance.check(conn)
    for p in report.problems:
        print(p)
    print("conformance: OK" if report.ok else f"conformance: {len(report.problems)} problem(s)")
    return 0 if report.ok else 1


def cmd_openapi(args) -> int:
    from veda.app import create_app
    from veda.kernel.openapi import build_openapi

    create_app()
    Path(args.output).write_text(json.dumps(build_openapi(), indent=2))
    print(args.output)
    return 0


def cmd_deploy_check(args) -> int:
    """OPS-006 / OPS-010: the effective gunicorn configuration (file, then GUNICORN_CMD_ARGS) runs exactly one
    gthread worker (IR-35). The same check runs again at runtime in the on_starting hook."""
    import runpy

    from gunicorn.config import Config

    from veda.kernel import single_instance

    cfg = Config()
    for key, value in runpy.run_path(args.gunicorn_conf).items():
        if key in cfg.settings:
            cfg.set(key, value)
    env_args = cfg.parser().parse_args(cfg.get_cmd_args_from_env())
    for key, value in vars(env_args).items():
        if value is not None and key != "args" and key in cfg.settings:
            cfg.set(key, value)
    try:
        single_instance.check_gunicorn(cfg)
    except single_instance.SingleInstanceError as err:
        print(f"deploy-check: {err}")
        return 1
    print("deploy-check: OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="veda")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate").set_defaults(fn=cmd_migrate)
    p = sub.add_parser("bootstrap-founder")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--email-link", action="store_true", help="also email the invite link")
    p.set_defaults(fn=cmd_bootstrap_founder)
    sub.add_parser("sync-permissions").set_defaults(fn=cmd_sync_permissions)
    p = sub.add_parser("worker")
    p.add_argument("--once", action="store_true")
    p.set_defaults(fn=cmd_worker)
    sub.add_parser("scheduler").set_defaults(fn=cmd_scheduler)
    p = sub.add_parser("maintenance")
    p.add_argument("job", choices=sorted(JOBS))
    p.set_defaults(fn=cmd_maintenance)
    p = sub.add_parser("break-glass")
    p.add_argument("action", choices=["request", "approve", "execute"])
    p.add_argument("--principal-arn", default=None)
    p.add_argument("--request", default=None)
    p.add_argument("--target", default=None)
    p.add_argument("--founder-action", default=None)
    p.add_argument("--reason", default=None)
    p.add_argument("--payload", default=None)
    p.set_defaults(fn=cmd_break_glass)
    sub.add_parser("conformance").set_defaults(fn=cmd_conformance)
    p = sub.add_parser("openapi")
    p.add_argument("--output", default="openapi.json")
    p.set_defaults(fn=cmd_openapi)
    p = sub.add_parser("deploy-check")
    p.add_argument("--gunicorn-conf", default=str(ROOT / "deploy" / "gunicorn.conf.py"))
    p.set_defaults(fn=cmd_deploy_check)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
