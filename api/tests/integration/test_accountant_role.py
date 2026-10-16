"""0211_accountant_role (PCM-D01): the ACCOUNTANT role and the withdrawal of SALES_MANAGER's commercial mutations.

A database migrated before 0211 holds the temporary mapping of decision log 44 (SALES_MANAGER: every ``commercials.*``
code) and no ACCOUNTANT grants. Upgrading must leave SALES_MANAGER with ``commercials.view`` only (each withdrawal a soft
delete with an audit row), give ACCOUNTANT its codes, and move every account's authz_version.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support import pg
from veda.kernel import clock, db
from veda.kernel import migration_support as ms
from veda.kernel.ids import SYSTEM_USER_ID, new_id
from veda.modules.commercials import permissions as P

GRANTS = (
    "SELECT p.code FROM role_permission rp JOIN role r ON r.id = rp.role_id JOIN permission p ON p.id = rp.permission_id"
    " WHERE r.code = :role AND rp.is_deleted = :f AND p.code LIKE 'commercials.%' ORDER BY p.code"
)


def _cfg(url: str):
    from alembic.config import Config

    from tests.conftest import ROOT

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["skip_logging"] = True
    return cfg


def _hex(value) -> str:
    return value.hex if hasattr(value, "hex") and not isinstance(value, str) else value  # PostgreSQL returns UUIDs


def _codes(conn, role: str) -> list[str]:
    return [c for (c,) in conn.execute(sa.text(GRANTS), {"role": role, "f": False})]


def test_upgrading_withdraws_the_temporary_mapping_and_grants_the_accountant(tmp_path, engine, app):
    from alembic import command

    if engine == "sqlite":
        url = f"sqlite:///{tmp_path / 'accountant.db'}"
    else:
        name = f"veda_acc_{new_id()[-10:]}"
        pg.admin(f"CREATE DATABASE {name}")
        url = pg.url(name)
    cfg = _cfg(url)
    try:
        command.upgrade(cfg, "0210_project_commercials")
        eng = db.create_engine(url)
        now = clock.now()
        with eng.begin() as conn:  # what a database migrated before 0211 holds
            role = {r: _hex(i) for r, i in conn.execute(sa.text("SELECT code, id FROM role"))}
            perms = {
                c: _hex(i)
                for c, i in conn.execute(sa.text("SELECT code, id FROM permission WHERE code LIKE 'commercials.%'"))
            }
            conn.execute(sa.text("DELETE FROM role_permission WHERE role_id = :r"), {"r": role["ACCOUNTANT"]})
            held = set(_codes(conn, "SALES_MANAGER"))
            for code in P.CODES:
                if code not in held:
                    conn.execute(ms.ROLE_PERMISSION.insert().values(**ms.contract(SYSTEM_USER_ID, now),
                                                                    role_id=role["SALES_MANAGER"],
                                                                    permission_id=perms[code], scope="ALL"))  # fmt: skip
            assert _codes(conn, "SALES_MANAGER") == sorted(P.CODES)
            versions = dict(
                conn.execute(sa.text("SELECT id, authz_version FROM app_user WHERE user_type = 'HUMAN'")).all()
            )
        eng.dispose()
        command.upgrade(cfg, "head")
        eng = db.create_engine(url)
        with eng.begin() as conn:
            assert _codes(conn, "SALES_MANAGER") == ["commercials.view"]
            assert _codes(conn, "ACCOUNTANT") == sorted(P.CODES)
            mfa = conn.execute(sa.text("SELECT mfa_required FROM role WHERE code = 'ACCOUNTANT'")).scalar()
            assert bool(mfa) is True
            audits = conn.execute(sa.text("SELECT reason FROM audit_log WHERE entity_type = 'role_permission' AND "
                                          "action = 'DELETE' AND performed_via = 'MIGRATION'")).scalars().all()  # fmt: skip
            assert sorted(a.split(" ")[0] for a in audits) == sorted(P.WITHDRAWN_FROM_SALES_MANAGER)
            after = dict(
                conn.execute(sa.text("SELECT id, authz_version FROM app_user WHERE user_type = 'HUMAN'")).all()
            )
            assert all(after[u] > v for u, v in versions.items())  # sessions lose the codes at once
        eng.dispose()
    finally:
        if engine != "sqlite":
            db.dispose()
            pg.admin(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


def test_a_grant_the_matrix_still_lists_is_never_withdrawn(app):
    with db.engine().begin() as conn:
        with pytest.raises(RuntimeError, match="still grants"):
            ms.withdraw_role_grants(conn, "SALES_MANAGER", ("commercials.view",), audit=True)
        assert ms.withdraw_role_grants(conn, "SALES_MANAGER", P.WITHDRAWN_FROM_SALES_MANAGER, audit=True) == 0
