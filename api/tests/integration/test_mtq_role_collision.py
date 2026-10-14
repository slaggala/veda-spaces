"""0201_mtq_estimation seeds the ESTIMATOR and SALES_MANAGER system roles (PR #91 certification, pre-enablement D).

A database can already hold a custom role (created through the roles API) with one of those codes or names; until
PR #91, the platform's own role-CRUD test created a custom SALES_MANAGER. The migration must stop, naming the
conflict and changing nothing, rather than skip the custom role and grant it the new role's permissions."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support import pg
from veda.kernel import db
from veda.kernel import migration_support as ms
from veda.kernel.ids import new_id


def _cfg(url: str):
    from alembic.config import Config

    from tests.conftest import ROOT

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["skip_logging"] = True
    return cfg


@pytest.mark.parametrize(
    ("label", "tamper", "message"),
    [
        ("custom code", "UPDATE role SET is_system = :f WHERE code = 'SALES_MANAGER'",
         "custom role SALES_MANAGER uses the code of system role SALES_MANAGER"),
        ("custom name", "UPDATE role SET code = 'EST_CUSTOM', is_system = :f WHERE code = 'ESTIMATOR'",
         "role EST_CUSTOM uses the name of system role ESTIMATOR"),
    ],
)  # fmt: skip
def test_custom_role_collision_stops_the_migration(tmp_path, engine, app, label, tamper, message):
    from alembic import command

    if engine == "sqlite":
        url = f"sqlite:///{tmp_path / 'collide.db'}"
    else:
        name = f"veda_rc_{new_id()[-10:]}"
        pg.admin(f"CREATE DATABASE {name}")
        url = pg.url(name)
    cfg = _cfg(url)
    try:
        command.upgrade(cfg, "0204_mtq_self_service")
        eng = db.create_engine(url)
        with eng.begin() as conn:
            conn.execute(sa.text(tamper), {"f": False})  # what a custom role created through the API looks like
            grants_before = conn.execute(sa.text("SELECT count(*) FROM role_permission")).scalar()
        eng.dispose()
        with pytest.raises(RuntimeError) as err:
            command.upgrade(cfg, "head")
        assert message in str(err.value) and "nothing changed" in str(err.value), label
        eng = db.create_engine(url)
        with eng.begin() as conn:
            assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == "0204_mtq_self_service"
            assert "requirement" not in sa.inspect(conn).get_table_names()
            assert conn.execute(sa.text("SELECT count(*) FROM role_permission")).scalar() == grants_before
        eng.dispose()
    finally:
        if engine != "sqlite":
            db.dispose()
            pg.admin(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


def test_the_seeded_system_roles_pass(app):
    with db.engine().connect() as conn:
        ms.refuse_role_collisions(conn, ("ESTIMATOR", "SALES_MANAGER"))  # fresh database: the system roles, no error
