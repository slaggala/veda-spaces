"""B1-PE-08: a user holding only SURVEYOR or DESIGNER loads the workspace (migration 0204_mtq_self_service).

The site roles get the platform self-service rows the shell needs (own profile, reference lists, own notifications)
and nothing beyond them: no lead access, no profile edits, no session management.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support import pg
from veda.kernel import conformance, db
from veda.kernel.ids import new_id

SITE_ROLES = ("SURVEYOR", "DESIGNER")
SHELL = {("SURVEYOR", "profile.read", "ALL"), ("SURVEYOR", "lookup.read", "ALL"),
         ("SURVEYOR", "notification.read", "OWN"), ("DESIGNER", "profile.read", "ALL"),
         ("DESIGNER", "lookup.read", "ALL"), ("DESIGNER", "notification.read", "OWN")}  # fmt: skip


@pytest.mark.parametrize("role", SITE_ROLES)
def test_a_bare_site_role_loads_the_shell(api, factory, role):
    factory.login(api, factory.user(role))
    me = api.get("/api/v1/auth/me")
    assert me.status == 200, me
    assert [r["code"] for r in me.data["roles"]] == [role]
    assert {"profile.read", "lookup.read", "notification.read"} <= set(me.data["permissions"])
    assert api.get("/api/v1/auth/mfa").status == 200
    assert api.get("/api/v1/lookups").status == 200
    assert api.get("/api/v1/notifications").status == 200


@pytest.mark.parametrize("role", SITE_ROLES)
def test_a_bare_site_role_still_cannot_reach_leads_or_self_management(api, factory, role):
    sales = factory.user("SALES")
    token = factory.login(api, sales)
    lead = factory.lead(api, token)
    factory.login(api, factory.user(role))
    for path in ("/api/v1/leads", f"/api/v1/leads/{lead['id']}", "/api/v1/auth/sessions", "/api/v1/users"):
        r = api.get(path)
        assert r.status == 403 and r.code == "PERMISSION_DENIED", (role, path, r)
    version = api.get("/api/v1/auth/me").data["version"]
    r = api.patch("/api/v1/auth/me", {"display_name": "Site"}, if_match=version)
    assert r.status == 403 and r.code == "PERMISSION_DENIED", r  # profile.update stays with the V1 roles


def _grants(conn) -> set:
    return set(
        conn.execute(
            sa.text(
                "SELECT r.code, p.code, rp.scope FROM role_permission rp JOIN role r ON r.id = rp.role_id "
                "JOIN permission p ON p.id = rp.permission_id WHERE rp.is_deleted = :f"
            ),
            {"f": False},
        ).all()
    )


def test_fresh_database_holds_the_shell_grants(app):
    with db.engine().connect() as conn:
        grants = _grants(conn)
    assert grants >= SHELL
    site = {(r, c) for r, c, _ in grants if r in SITE_ROLES}
    for code in ("profile.update", "session.read", "session.revoke", "lead.read"):
        assert not any((r, code) in site for r in SITE_ROLES), code


def test_upgrade_from_0200_grants_the_shell_rows(tmp_path, engine, app):
    """A database at 0200 seeded before this fix has the site roles without the shell rows; 0204 adds exactly them,
    bumps authz_version and leaves every other grant as it was."""
    from alembic import command
    from alembic.config import Config

    from tests.conftest import ROOT
    from veda.kernel import migration_support as ms

    if engine == "sqlite":
        url = f"sqlite:///{tmp_path / 'from0200.db'}"
    else:
        name = f"veda_up_{new_id()[-10:]}"
        pg.admin(f"CREATE DATABASE {name}")
        url = pg.url(name)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["skip_logging"] = True
    try:
        command.upgrade(cfg, "0200_mtq_site")
        eng = db.create_engine(url)
        with eng.begin() as conn:
            # 0003 seeds from the live registry; remove what the 0200-era registry never granted.
            conn.execute(
                sa.text(
                    "DELETE FROM role_permission WHERE role_id IN (SELECT id FROM role WHERE code IN ('SURVEYOR', 'DESIGNER')) "
                    "AND permission_id IN (SELECT id FROM permission WHERE code IN ('profile.read', 'lookup.read', "
                    "'notification.read'))"
                )
            )
            before = _grants(conn)
        eng.dispose()
        assert not (before & SHELL)
        command.upgrade(cfg, "head")
        eng = db.create_engine(url)
        with eng.begin() as conn:
            after = _grants(conn)
            assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == "0204_mtq_self_service"
            assert conformance.check(conn).ok
            assert ms.grant_new_codes(conn, ("profile.read", "lookup.read", "notification.read"), audit=False) == 0
        eng.dispose()
        assert after - before == SHELL and before <= after
    finally:
        if engine != "sqlite":
            db.dispose()
            pg.admin(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
