"""Engine, connections and the unit of work (03 §1, §2.8, 02 §8).

SQLite connections get ``journal_mode=WAL``, ``foreign_keys=ON``,
``busy_timeout=5000`` and ``synchronous=NORMAL`` on every connect. Write units
of work start with ``BEGIN IMMEDIATE`` so the write lock is taken up front.
PostgreSQL uses READ COMMITTED plus optimistic ``version`` checks.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from collections.abc import Iterator

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from . import clock
from .ids import new_id

SQLITE_PRAGMAS = (
    ("journal_mode", "WAL"),
    ("foreign_keys", "ON"),
    ("busy_timeout", "5000"),
    ("synchronous", "NORMAL"),
)

_engine: Engine | None = None
_session_factory: sessionmaker | None = None
_lock = threading.Lock()


def _install_sqlite_hooks(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _record):
        # Take manual control of transactions so BEGIN IMMEDIATE can be issued.
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        for name, value in SQLITE_PRAGMAS:
            cursor.execute(f"PRAGMA {name}={value}")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn):
        if conn.get_execution_options().get("veda_write"):
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            conn.exec_driver_sql("BEGIN")


def create_engine(url: str, *, echo: bool = False) -> Engine:
    if url.startswith("sqlite"):
        engine = sa.create_engine(
            url,
            echo=echo,
            connect_args={"check_same_thread": False, "timeout": 5.0},
            pool_pre_ping=False,
            hide_parameters=True,  # bound values (PII) never appear in exception messages or logs (IR-27)
        )
        _install_sqlite_hooks(engine)
    else:
        engine = sa.create_engine(url, echo=echo, pool_pre_ping=True, future=True, hide_parameters=True)
    return engine


def configure(url: str, *, echo: bool = False) -> Engine:
    global _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(url, echo=echo)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=True)
        from . import audit_hook  # noqa: F401  (registers the before_flush hook)

        return _engine


def engine() -> Engine:
    if _engine is None:
        raise RuntimeError("database not configured")
    return _engine


def dispose() -> None:
    global _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _session_factory = None


def is_sqlite() -> bool:
    return engine().dialect.name == "sqlite"


def new_session(*, write: bool) -> Session:
    if _session_factory is None:
        raise RuntimeError("database not configured")
    session = _session_factory()
    begin_unit_of_work(session, write=write)
    return session


def begin_unit_of_work(session: Session, *, write: bool) -> None:
    """One clock reading and one transaction id per unit of work (03 §2.8)."""
    session.info["tx_time"] = clock.now()
    session.info["transaction_id"] = new_id()
    session.info["write"] = write
    session.info["veda_versioned"] = set()
    session.info["governance_locked"] = False
    # Bind the connection now so BEGIN IMMEDIATE is issued before any read.
    session.connection(execution_options={"veda_write": write})


@contextlib.contextmanager
def unit_of_work(*, write: bool = True) -> Iterator[Session]:
    session = new_session(write=write)
    try:
        yield session
        if write:
            session.commit()
        else:
            session.rollback()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def tx_time(session: Session):
    value = session.info.get("tx_time")
    if value is None:
        value = clock.now()
        session.info["tx_time"] = value
    return value


def transaction_id(session: Session) -> str:
    value = session.info.get("transaction_id")
    if value is None:
        value = new_id()
        session.info["transaction_id"] = value
    return value


def verify_sqlite_runtime(conn) -> dict[str, object]:
    """Startup check: SQLite ≥ 3.35 for UPDATE … RETURNING, pragmas applied."""
    version = sqlite3.sqlite_version_info
    if version < (3, 35, 0):
        raise RuntimeError(f"SQLite >= 3.35 required, found {sqlite3.sqlite_version}")
    fk = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
    journal = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
    return {
        "foreign_keys": int(fk or 0),
        "journal_mode": str(journal).lower(),
        "sqlite_version": sqlite3.sqlite_version,
    }
