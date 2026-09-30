"""Ops endpoints (08 §3, 02 §9, LOG-005, F-12).

/health/ready gates deploys and traffic: DB reachable, schema compatible with this
image, foreign_keys=ON, immutability triggers present. Degraded signals (outbox lag,
email-provider errors) are reported but never fail readiness.

Schema compatibility (IR-10; proposed amendment AM-6):

* ``head``: the database is at this image's head.
* ``behind``: the database is at an older revision this image knows: not ready.
* ``ahead``: the database is at a revision this image does not know (the N-1 image on a schema migrated by
  image N). Migrations are expand-only (02 §12.4), but the image cannot prove that for a revision it has
  never seen, so it is ready only when the operator has declared the revision compatible in
  ``VEDA_SCHEMA_AHEAD_ACCEPTED`` (the N-1 rollback runbook step). Otherwise not ready.

Check details are returned only to direct local callers (the deploy gate on the host); requests that arrive
through the Cloudflare edge get the status alone (IR-A17).
"""

from __future__ import annotations

import sqlalchemy as sa

from veda.config import settings
from veda.kernel import db, migration_support
from veda.kernel.http import Api, Req, Result

api = Api("health", "", tags=("ops",))


def _scripts():
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
    return ScriptDirectory.from_config(cfg)


def alembic_head() -> str | None:
    return _scripts().get_current_head()


def known_revisions() -> set[str]:
    return {r.revision for r in _scripts().walk_revisions()}


def current_revision() -> str | None:
    """The database revision, or None for a database that has never been migrated (first deployment)."""
    try:
        with db.engine().connect() as conn:
            return conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    except sa.exc.DBAPIError:
        return None


def schema_state(current: str | None) -> str:
    if current is not None and current == alembic_head():
        return "head"
    if current in known_revisions():
        return "behind"
    if current is not None and current in settings().schema_ahead_accepted:
        return "ahead"
    return "ahead_undeclared" if current is not None else "missing"


def _detail_allowed() -> bool:
    from flask import request

    from veda.kernel import net

    peer = net.parse(request.remote_addr)
    return request.headers.get("CF-Connecting-IP") is None and peer is not None and peer.is_loopback


@api.route("GET", "/health/live", rbx="RBX-006", auth="public", write=False, requirement="LOG-005")
def live(req: Req):
    return Result(status=200, raw_body={"status": "ok"})


@api.route("GET", "/health/ready", rbx="RBX-006", auth="public", write=False, requirement="LOG-005")
def ready(req: Req):
    checks: dict = {}
    ok = True
    try:
        conn = req.session.connection()
        conn.execute(sa.text("SELECT 1"))
        checks["db"] = "ok"
        current = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        state = schema_state(current)
        checks["migrations"] = state
        ok &= state in ("head", "ahead")
        if db.is_sqlite():
            fk = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
            checks["foreign_keys"] = "on" if int(fk or 0) == 1 else "off"
            ok &= int(fk or 0) == 1
        guards = migration_support.guards_present(conn)
        checks["immutability_guards"] = "present" if guards else "missing"
        ok &= guards
    except Exception:
        checks["db"] = "unavailable"
        ok = False
    try:
        from veda.platform.notifications.worker import outbox_stats

        stats = outbox_stats()
        # Degraded signals: reported and alerted, never a readiness failure (F-12).
        checks["outbox_lag_s"] = int(stats["oldest_age_s"]) if stats["depth"] else None
        checks["outbox_dead"] = int(stats["dead"])
    except Exception:
        checks["outbox_lag_s"] = None
    body: dict[str, object] = {"status": "ok" if ok else "degraded"}
    if _detail_allowed():
        body["checks"] = checks
    return Result(status=200 if ok else 503, raw_body=body)
