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
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
log = logging.getLogger("veda.cli")


def _settings_env() -> str:
    from veda import config

    return config.settings().env


def _settings():
    from veda import config
    from veda.kernel import db
    from veda.kernel.logging import configure_logging

    s = config.settings()  # an in-process caller (tests) may have configured settings already
    problems = config.validate_environment(s)
    if problems:
        raise SystemExit(f"unsafe {s.env} configuration: " + "; ".join(problems))
    # CLI, worker and scheduler processes emit the same JSON log lines and EMF metrics as the API (RR-07).
    configure_logging(s.log_level)
    try:
        db.engine()
    except RuntimeError:
        db.configure(s.database_url)
    import veda.models  # noqa: F401
    from veda.modules.crm.leads import events  # noqa: F401  (handlers)
    from veda.modules.estimator import events as _estimate_events  # noqa: F401

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

    settings = _settings()
    # R1/R2: the invite link is a credential. The container's stdout is shipped to the log group, so a deployed
    # environment never prints it: it is emailed (--email-link) or written to a new 0600 file (--link-file).
    if not (args.email_link or args.link_file or _stdout_link_allowed(settings)):
        print(
            f"refused: in {settings.env} the invite link is never printed; use --email-link or --link-file",
            file=sys.stderr,
        )
        return 2
    try:
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
            security_events.record(
                s, "BOOTSTRAP_FOUNDER", "SUCCESS", subject_user_id=user.id, detail={"channel": "cli"}
            )
            if args.email_link:
                outbox.enqueue(s, "user.invited", "app_user", user.id, user_id=user.id, token_id=tok.id)
            out: dict[str, object] = {"user_id": user.id, "expires_on": tok.expires_on.isoformat()}
            link = app_link(f"/accept-invite#token={raw}")
            if args.link_file:
                _write_secret_file(args.link_file, link + "\n")  # fails closed: the transaction rolls back
                out["invite_link_file"] = args.link_file
            if args.email_link:
                out["invite"] = "emailed"
            if not (args.email_link or args.link_file):
                out["invite_link"] = link  # local and test only (checked above)
            print(json.dumps(out))
    except FileExistsError:
        print(f"refused: {args.link_file} exists; the invite link file is never overwritten", file=sys.stderr)
        return 2
    return 0


def _stdout_link_allowed(settings) -> bool:
    return settings.dev_keys_allowed


def _write_secret_file(path: str, content: str) -> None:
    """A new file, readable by its owner only; an existing file is never overwritten."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(content)


def cmd_outbox(args) -> int:
    """R3: list, retire or requeue dead-lettered outbox events (payloads are never shown)."""
    from veda.platform.notifications import dead_letters

    _settings()
    try:
        if args.action == "dead":
            print(json.dumps(dead_letters.list_dead()))
        elif not args.id:
            raise dead_letters.DeadLetterError("--id is required")
        elif args.action == "retire":
            print(json.dumps(dead_letters.retire(args.id, args.reason)))
        else:
            print(json.dumps(dead_letters.requeue(args.id, args.reason)))
    except dead_letters.DeadLetterError as err:
        print(f"refused: {err}", file=sys.stderr)
        return 2
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
    "estimate-retention": "estimate_retention",
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


def cmd_estimator(args) -> int:
    """Rate cards (operator only; no API exposes a card) and estimate retention (ADR-012 Part I).

    validate-card FILE       dry run: schema, business rules, no customer data; prints the version and SHA-256 only
    load-card FILE           store as DRAFT (a version is loaded once)
    activate-card VERSION    with --approval "<owner approval reference>"; the previous card is retired
    rollback-card            re-activate the most recently retired card, with --approval
    list-cards               versions, states and SHA-256 (never rates)
    """
    from veda.kernel import db
    from veda.kernel.context import actor, system_context
    from veda.modules.estimator import service

    _settings()
    if args.action.endswith("-spec") or args.action in ("list-specs", "activation-check"):
        return _estimator_spec(args)
    try:
        if args.action in ("validate-card", "load-card"):
            if not args.file:
                raise service.CardError("give the private rate-card file")
            document = json.loads(Path(args.file).read_text())
            if args.action == "validate-card":
                card = service.validate_document(document)
                print(json.dumps({"valid": True, "version": card.version, "sha256": service._sha(document)}))
                return 0
        out: dict[str, object]
        with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
            if args.action == "load-card":
                row = service.load_card(s, document)
                out = {"loaded": row.card_version, "status": row.status, "sha256": row.document_sha256}
            elif args.action == "activate-card":
                row = service.activate_card(s, args.version or "", args.approval or "")
                out = {"active": row.card_version}
            elif args.action == "rollback-card":
                row = service.rollback_card(s, args.approval or "")
                out = {"active": row.card_version, "rolled_back": True}
            else:
                out = {"cards": service.list_cards(s)}
        print(json.dumps(out))
        return 0
    except (service.CardError, OSError, ValueError) as err:
        print(f"refused: {str(err).splitlines()[0]}", file=sys.stderr)
        return 2


def _estimator_spec(args) -> int:
    """Customer specifications (ADR-012 T9): validate, load, activate, roll back, list. Prints codes, states and
    SHA-256 only."""
    from veda.kernel import db
    from veda.kernel.context import actor, system_context
    from veda.modules.estimator import service

    try:
        if args.matrix:
            raise service.SpecError(
                "an externally supplied matrix is not accepted: activation uses the reviewed matrix packaged with this "
                "release (veda/modules/estimator/approved/)"
            )
        operator = os.environ.get("SUDO_USER") or os.environ.get("USER") or None
        if args.action in ("validate-spec", "load-spec", "activation-check"):
            if not args.file:
                raise service.SpecError("give the customer specification file")
            document = json.loads(Path(args.file).read_text())
            if args.action == "validate-spec":
                spec = service.validate_spec(document)
                out: dict[str, object] = {"valid": True, "spec": spec.spec_code, "sha256": service._sha(document)}
                print(json.dumps(out))
                return 0
            if args.action == "activation-check":  # read-only: every activation guard in one report
                env = args.environment or (
                    _settings_env() if _settings_env() in ("staging", "production") else "staging"
                )
                with db.unit_of_work(write=False) as s:
                    report = service.activation_report(s, document, env=env, approval_reference=args.approval)
                    active = [x["spec"] for x in service.list_specs(s) if x["status"] == "ACTIVE"]
                blocked = report["blockers"]
                if args.expect_sha and args.expect_sha != report["evidence"]["specification_sha256"]:
                    blocked.insert(0, "the document SHA-256 is not the owner-approved digest")
                out = {
                    "spec": report["evidence"]["spec"],
                    "environment": env,
                    "sha256": report["evidence"]["specification_sha256"],
                    "digests": report["digests"],
                    "blockers": blocked,
                    "active_now": active,
                    "ready": not blocked,
                }
                print(json.dumps(out))
                return 0 if not blocked else 3
        with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
            if args.action == "load-spec":
                row = service.load_spec(s, document)
                out = {"loaded": row.spec_code, "status": row.status, "sha256": row.document_sha256}
            elif args.action == "activate-spec":
                row = service.activate_spec(
                    s,
                    args.spec or "",
                    args.approval or "",
                    ux_v1_confirmed=args.ux_v1_confirmed,
                    release=args.release,
                    operator=operator,
                )
                out = {"active": row.spec_code, "package": row.package}
            elif args.action == "rollback-spec":
                row = service.rollback_spec(
                    s,
                    args.package,
                    args.approval or "",
                    ux_v1_confirmed=args.ux_v1_confirmed,
                    release=args.release,
                    operator=operator,
                )
                out = {"active": row.spec_code, "package": row.package, "rolled_back": True}
            else:
                out = {"specs": service.list_specs(s)}
        print(json.dumps(out))
        return 0
    except (service.SpecError, OSError, ValueError) as err:
        print(f"refused: {str(err).splitlines()[0]}", file=sys.stderr)
        return 2


def cmd_maintenance(args) -> int:
    from veda.kernel import metrics
    from veda.platform import maintenance

    _settings()
    try:
        result = getattr(maintenance, JOBS[args.job])()
    except Exception:
        # A job that raises is a durable failure: a CRITICAL line and a metric the alarm watches (RR-07).
        log.critical("maintenance_job_failed job=%s", args.job, exc_info=True)
        metrics.emit("MaintenanceJobFailed", 1, dimensions={"Job": args.job})
        return 1
    if hasattr(result, "__dataclass_fields__"):
        result = result.__dict__
    print(json.dumps(result, default=str))
    failed = args.job == "verify-chain" and not result.get("ok", True)
    metrics.emit("MaintenanceJobFailed", 1 if failed else 0, dimensions={"Job": args.job})
    return 3 if failed else 0


JOB_TIMEOUT_SECONDS = 3600


def run_scheduled_job(job: str) -> int:
    """Run one maintenance job in its own process and record its exit status (RR-07): every run emits
    ScheduledJobFailed (0 or 1) per job, and a non-zero exit or timeout is logged at ERROR with the code."""
    import subprocess

    from veda.kernel import metrics

    try:
        code = subprocess.run(
            [sys.executable, "-m", "veda.cli", "maintenance", job], check=False, timeout=JOB_TIMEOUT_SECONDS
        ).returncode
    except subprocess.TimeoutExpired:
        code = -1
    except OSError:
        log.critical("scheduled_job_not_started job=%s", job, exc_info=True)
        code = -2
    metrics.emit("ScheduledJobFailed", 0 if code == 0 else 1, dimensions={"Job": job})
    if code != 0:
        log.error("scheduled_job_failed job=%s exit_code=%s", job, code)
    return code


def cmd_scheduler(args) -> int:  # pragma: no cover - process loop
    """Periodic jobs. Jobs that lift evidence-store guards run as separate short-lived processes (A-02)."""
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
        "04:15": "estimate-retention",
        "05:00": "restore-verify",
        "09:00": "spam-review",
    }
    ran: set[str] = set()
    while True:
        for job in frequent:
            run_scheduled_job(job)
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        for at, job in daily.items():
            key = f"{now.date()}:{job}"
            if now.strftime("%H:%M") >= at and key not in ran:
                run_scheduled_job(job)
                ran.add(key)
        _time.sleep(300)


def cmd_schema_status(args) -> int:
    """Database revision against this image, run inside the container by deploy.sh (RR-17): the readiness detail
    is not reachable from the host under the compose topology. ``--require-known REV`` exits 4 when this image
    does not know REV — how deploy.sh refuses a rollback target older than the release's rollback floor."""
    from veda.platform import health

    _settings()
    current = health.current_revision()
    known = health.known_revisions()
    from veda.release import RELEASE_SEQUENCE

    out: dict[str, object] = {
        "current": current,
        "image_head": health.alembic_head(),
        "state": health.schema_state(current),
        "release": RELEASE_SEQUENCE,
    }
    if args.require_known:
        out["floor"] = args.require_known
        out["floor_known"] = args.require_known in known
    print(json.dumps(out))
    return 4 if args.require_known and args.require_known not in known else 0


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
    p.add_argument("--email-link", action="store_true", help="email the invite link (never printed)")
    p.add_argument("--link-file", default=None, help="write the invite link to this new file (mode 0600)")
    p.set_defaults(fn=cmd_bootstrap_founder)
    p = sub.add_parser("estimator")
    p.add_argument(
        "action",
        choices=[
            "validate-card",
            "load-card",
            "activate-card",
            "rollback-card",
            "list-cards",
            "validate-spec",
            "load-spec",
            "activate-spec",
            "rollback-spec",
            "list-specs",
            "activation-check",
        ],
    )
    p.add_argument("file", nargs="?", default=None)
    p.add_argument("--version", default=None)
    p.add_argument("--spec", default=None, help="customer specification code, for example ESSENTIAL-1.0")
    p.add_argument("--package", default="ESSENTIAL", choices=["ESSENTIAL", "PREMIUM", "LUXURY"])
    p.add_argument("--matrix", default=None, help=argparse.SUPPRESS)  # refused: only the packaged matrix is used
    p.add_argument("--release", default=None, help="the deployed release commit, recorded with the activation")
    p.add_argument("--environment", default=None, choices=["staging", "production"], help="activation-check target")
    p.add_argument("--expect-sha", default=None, help="the owner-approved specification document SHA-256")
    p.add_argument(
        "--ux-v1-confirmed",
        action="store_true",
        help="STAGING_ESTIMATOR_UX=v1 is set and deployed (needed for a specification without room promises)",
    )
    p.add_argument("--approval", default=None)
    p.set_defaults(fn=cmd_estimator)
    p = sub.add_parser("outbox")
    p.add_argument("action", choices=["dead", "retire", "requeue"])
    p.add_argument("--id", default=None)
    p.add_argument("--reason", default=None)
    p.set_defaults(fn=cmd_outbox)
    sub.add_parser("sync-permissions").set_defaults(fn=cmd_sync_permissions)
    p = sub.add_parser("worker")
    p.add_argument("--once", action="store_true")
    p.set_defaults(fn=cmd_worker)
    sub.add_parser("scheduler").set_defaults(fn=cmd_scheduler)
    p = sub.add_parser("maintenance")
    p.add_argument("job", choices=sorted(JOBS))
    p.set_defaults(fn=cmd_maintenance)
    p = sub.add_parser("schema-status")
    p.add_argument("--require-known", default=None)
    p.set_defaults(fn=cmd_schema_status)
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
