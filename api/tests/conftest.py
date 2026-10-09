"""Test fixtures (12 §3). Database-dependent suites run on SQLite and PostgreSQL
(OPS-001). Each test gets a fresh, fully migrated database: SQLite copies a
migrated template file; PostgreSQL clones a migrated template database.

Select engines with VEDA_TEST_ENGINES=sqlite,postgresql (default: both when
the embedded PostgreSQL server is available).
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

from tests.support import pg

ROOT = Path(__file__).resolve().parents[1]


def _engines() -> list[str]:
    raw = os.environ.get("VEDA_TEST_ENGINES")
    if raw:
        return [e.strip() for e in raw.split(",") if e.strip()]
    return ["sqlite", "postgresql"] if pg.available() else ["sqlite"]


def pytest_generate_tests(metafunc):
    if "engine" in metafunc.fixturenames:
        metafunc.parametrize("engine", _engines(), scope="session")


def migrate(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["skip_logging"] = True
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def _tmp_root():
    path = Path(tempfile.mkdtemp(prefix="veda-tests-"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="session")
def template_url(engine, _tmp_root):
    if engine == "sqlite":
        path = _tmp_root / "template.db"
        migrate(f"sqlite:///{path}")
        from veda.kernel import db

        db.dispose()
        return str(path)
    name = "veda_template"
    pg.admin(f"DROP DATABASE IF EXISTS {name}")
    pg.admin(f"CREATE DATABASE {name}")
    migrate(pg.url(name))
    from veda.kernel import db

    db.dispose()
    return name


@pytest.fixture
def database_url(engine, template_url, _tmp_root):
    if engine == "sqlite":
        path = _tmp_root / f"t-{uuid.uuid4().hex}.db"
        shutil.copyfile(template_url, path)
        yield f"sqlite:///{path}"
        for suffix in ("", "-wal", "-shm"):
            Path(str(path) + suffix).unlink(missing_ok=True)
        return
    name = f"veda_t_{uuid.uuid4().hex[:12]}"
    pg.admin(f"CREATE DATABASE {name} TEMPLATE {template_url}")
    yield pg.url(name)
    from veda.kernel import db

    db.dispose()
    pg.admin(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


def make_settings(database_url: str, **overrides):
    from veda import config

    base = dict(
        env="test",
        database_url=database_url,
        argon2_memory_kib=1024,
        argon2_time_cost=1,
        argon2_parallelism=1,
        cookie_secure=False,
        rate_limits_enabled=False,
        email_provider="capture",
        turnstile_mode="dev",
        app_origin="http://localhost:5173",
        public_site_origins=["http://localhost:8000"],
        anchor_dir=str(Path(tempfile.mkdtemp(prefix="veda-anchor-"))),
        catalog_media_dir=str(Path(tempfile.mkdtemp(prefix="veda-catalog-media-"))),
        testing=True,
    )
    base.update(overrides)
    return config.load_settings(**base)


def reset_process_state() -> None:
    from veda.kernel import clock, http, turnstile
    from veda.platform.auth import crypto, security_events, throttle
    from veda.platform.notifications.email import CaptureEmailProvider, use_provider
    from veda.platform.rbac import resolver

    clock.reset()
    resolver.clear_cache()
    throttle.reset()
    security_events.reset_dedupe()
    http.idempotency_store.clear()
    turnstile.reset_counter()
    crypto.reset_provider()
    CaptureEmailProvider.clear()
    use_provider(None)


@pytest.fixture
def app(database_url, request):
    from veda.app import create_app

    reset_process_state()
    overrides = getattr(request, "param", None) or {}
    marker = request.node.get_closest_marker("settings")
    if marker:
        overrides = {**overrides, **marker.kwargs}
    application = create_app(make_settings(database_url, **overrides))
    application.testing = True
    yield application
    reset_process_state()
    from veda.kernel import db

    db.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def api(client):
    from tests.support.api import ApiClient

    return ApiClient(client)


@pytest.fixture
def factory(app):
    from tests.support.factory import Factory

    return Factory()


def pytest_configure(config):
    config.addinivalue_line("markers", "settings(**kwargs): override Settings for the app fixture")
