"""Embedded PostgreSQL for the dual-engine suite (OPS-001)."""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(os.environ.get("VEDA_PG_DATA", Path(tempfile.gettempdir()) / "veda-pg-tests"))


@lru_cache(maxsize=1)
def available() -> bool:
    if os.environ.get("VEDA_TEST_DATABASE_URL_PG"):
        return True
    try:
        import pixeltable_pgserver  # noqa: F401
    except ImportError:
        return False
    try:
        server()
        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def server():
    import pixeltable_pgserver

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return pixeltable_pgserver.get_server(str(_DATA_DIR), cleanup_mode=None)


def _host() -> str:
    return server().get_uri().split("host=")[1]


def url(dbname: str) -> str:
    external = os.environ.get("VEDA_TEST_DATABASE_URL_PG")
    if external:
        return external.rsplit("/", 1)[0] + f"/{dbname}"
    return f"postgresql+psycopg://postgres@/{dbname}?host={_host()}"


def admin(sql: str) -> None:
    import sqlalchemy as sa

    engine = sa.create_engine(url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql(sql)
    finally:
        engine.dispose()
