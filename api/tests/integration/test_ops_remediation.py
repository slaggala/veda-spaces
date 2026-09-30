"""Readiness and rollback boundary (IR-10, IR-A17; LOG-005, OPS-004, 02 §12.4)."""

import sqlalchemy as sa

from veda import config
from veda.kernel import db
from veda.platform import health

N_MINUS_1_HEAD = "0100_crm_leads"


def _as_n_minus_1_image(monkeypatch):
    """The previous image: its script directory ends one revision earlier than the database."""
    known = health.known_revisions() - {health.alembic_head()}
    monkeypatch.setattr(health, "alembic_head", lambda: N_MINUS_1_HEAD)
    monkeypatch.setattr(health, "known_revisions", lambda: known)


def test_IR10_current_image_on_its_own_head_is_ready(client):
    body = client.get("/health/ready").get_json()
    assert body["status"] == "ok" and body["checks"]["migrations"] == "head"


def test_IR10_n_minus_1_image_on_migrated_schema_needs_the_operator_declaration(client, monkeypatch):
    _as_n_minus_1_image(monkeypatch)
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.get_json()["checks"]["migrations"] == "ahead_undeclared"
    config.settings().schema_ahead_accepted = ["0009_mfa_challenge_binding"]
    try:
        r = client.get("/health/ready")
        assert r.status_code == 200 and r.get_json()["checks"]["migrations"] == "ahead"
    finally:
        config.settings().schema_ahead_accepted = []


def test_IR10_schema_behind_the_image_is_not_ready(client):
    with db.engine().begin() as conn:
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '0008_account_security'"))
    try:
        r = client.get("/health/ready")
        assert r.status_code == 503 and r.get_json()["checks"]["migrations"] == "behind"
    finally:
        with db.engine().begin() as conn:
            conn.execute(sa.text(f"UPDATE alembic_version SET version_num = '{health.alembic_head()}'"))


def test_IR10_unknown_revision_is_never_accepted_implicitly(client):
    with db.engine().begin() as conn:
        conn.execute(sa.text("UPDATE alembic_version SET version_num = 'zz_divergent'"))
    try:
        assert client.get("/health/ready").status_code == 503
    finally:
        with db.engine().begin() as conn:
            conn.execute(sa.text(f"UPDATE alembic_version SET version_num = '{health.alembic_head()}'"))


def test_IR10_downgrade_is_refused_and_leaves_the_schema_at_head(app):
    import pytest
    from alembic import command
    from alembic.config import Config

    from tests.conftest import ROOT

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = str(db.engine().url.render_as_string(hide_password=False))
    cfg.attributes["skip_logging"] = True
    with pytest.raises(NotImplementedError):
        command.downgrade(cfg, "-1")
    with db.engine().connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == health.alembic_head()


def test_IRA17_edge_requests_get_status_only(client):
    body = client.get("/health/ready", headers={"CF-Connecting-IP": "49.205.10.1"}).get_json()
    assert body == {"status": "ok"}
