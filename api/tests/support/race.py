"""Coordination for the paused-request race tests.

A race test holds one request (the held request) at a chosen point, runs a second request (the other request), then
resumes the first. The held request resumes on an explicit signal, never after a fixed time:

- ``completed``: the other request returned (it committed, or was refused, while the held request waited), or
- ``lock_wait``: the other request is waiting for a lock the held request owns, so it can make no progress until the
  held request commits. On SQLite that is the database write lock, which the held request owns from its
  ``BEGIN IMMEDIATE``: the other request has issued its own. On PostgreSQL it is a row lock: the server reports the
  held request's backend in ``pg_blocking_pids`` of the other request's backend.

The previous fixed two-second hold spent two of the five seconds of the SQLite busy timeout the other request waits
under, and a stop-the-world collection of the long suite's heap landing in the remaining window turned the expected
result into a 503. ``Hold.racing`` also runs one full collection before the race and keeps automatic collection off
until the threads have joined, then restores the collector to its previous state.

Reaching ``HOLD_LIMIT`` fails the test: it means neither signal came.
"""

from __future__ import annotations

import contextlib
import gc
import threading
import time
from collections.abc import Iterator

from sqlalchemy import event

from veda.kernel import db

HOLD_LIMIT = 30.0  # seconds; a safety bound only
_PROBE_INTERVAL = 0.01  # seconds between PostgreSQL lock-wait checks while held


class Hold:
    def __init__(self) -> None:
        self.reached = threading.Event()  # the held request is at its hold point
        self.released_by: str | None = None  # "completed" | "lock_wait"
        self.timed_out = False
        self._release = threading.Event()
        self._held: threading.Thread | None = None
        self._other: threading.Thread | None = None
        self._held_owns_write_lock = False  # SQLite
        self._pids: dict[str, int] = {}  # PostgreSQL backend of each request's latest statement
        self._probe = None  # PostgreSQL connection that asks the server whether the other request is blocked

    def wait(self) -> None:
        """Call from the held request's thread at the hold point."""
        self.reached.set()
        deadline = time.monotonic() + HOLD_LIMIT
        while not self._release.wait(timeout=_PROBE_INTERVAL if self._probe is not None else HOLD_LIMIT):
            if self._probe is not None and self._other_blocked_by_held():
                self._set("lock_wait")
            elif time.monotonic() >= deadline:
                self.timed_out = True
                return

    def done(self) -> None:
        """Call from the other request's thread once its request has returned."""
        self._set("completed")

    def _set(self, reason: str) -> None:
        if not self._release.is_set():
            self.released_by = reason
            self._release.set()

    def _other_blocked_by_held(self) -> bool:
        held, other = self._pids.get("held"), self._pids.get("other")
        if held is None or other is None:
            return False
        with self._probe.cursor() as cur:
            cur.execute("SELECT %s = ANY(pg_blocking_pids(%s))", (held, other))
            return bool(cur.fetchone()[0])

    def _before_execute(self, conn, cursor, statement, parameters, context, executemany) -> None:
        me = threading.current_thread()
        role = "held" if me is self._held else "other" if me is self._other else None
        if role is None:
            return
        if self._probe is not None:
            self._pids[role] = conn.connection.dbapi_connection.info.backend_pid
        elif statement == "BEGIN IMMEDIATE":
            if role == "held":
                self._held_owns_write_lock = True
            elif self._held_owns_write_lock and self.reached.is_set():
                self._set("lock_wait")

    def _end(self, conn) -> None:
        if threading.current_thread() is self._held:
            self._held_owns_write_lock = False

    @contextlib.contextmanager
    def racing(self, held: threading.Thread, other: threading.Thread) -> Iterator[None]:
        """Wrap the threads' start and join."""
        self._held, self._other = held, other
        engine = db.engine()
        raw = None
        if not db.is_sqlite():
            raw = engine.raw_connection()  # statements on it bypass the engine events below
            self._probe = raw.driver_connection
            self._probe.autocommit = True
        listeners = (("before_cursor_execute", self._before_execute), ("commit", self._end), ("rollback", self._end))
        for name, fn in listeners:
            event.listen(engine, name, fn)
        gc.collect()
        collector_was_enabled = gc.isenabled()
        gc.disable()
        try:
            yield
        finally:
            if collector_was_enabled:
                gc.enable()
            for name, fn in listeners:
                event.remove(engine, name, fn)
            if raw is not None:
                self._probe.autocommit = False  # back to the pool as it came out
                raw.close()
        assert not self.timed_out, f"the held request was released by neither signal within {HOLD_LIMIT}s"
        assert self.released_by is not None, "the held request never reached its hold point"
