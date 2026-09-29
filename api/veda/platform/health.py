"""Ops endpoints (08 §3, 02 §9, LOG-005, F-12).

/health/ready gates deploys and traffic: DB reachable, migrations at head,
foreign_keys=ON, immutability triggers present. Degraded signals (outbox lag,
email-provider errors) are reported but never fail readiness.
"""

from __future__ import annotations

import sqlalchemy as sa

from veda.kernel import db, migration_support
from veda.kernel.http import Api, Req, Result

api = Api("health", "", tags=("ops",))


def alembic_head() -> str | None:
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


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
        head = alembic_head()
        checks["migrations"] = "head" if current == head else "behind"
        ok &= current == head
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
        from veda.platform.notifications.worker import lag_seconds

        lag = lag_seconds()
        checks["outbox_lag_s"] = None if lag is None else int(lag)
    except Exception:
        checks["outbox_lag_s"] = None
    return Result(status=200 if ok else 503, raw_body={"status": "ok" if ok else "degraded", "checks": checks})
