"""One application process per database (OPS-006, OPS-010, IR-35).

The in-process rate limiter, idempotency store, permission cache, throttles and Argon2 semaphore are
authoritative only when exactly one API process serves one database. This is enforced at runtime, not by
reading configuration text:

* ``check_gunicorn(cfg)`` rejects any effective configuration other than one gthread worker; it runs from the
  gunicorn ``on_starting`` hook and from ``veda deploy-check`` (which also applies GUNICORN_CMD_ARGS).
* ``acquire_lock(database_url)`` takes an exclusive, non-blocking lock beside the SQLite file; a second API
  instance on the same volume fails to start.
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path

_held: list[int] = []


class SingleInstanceError(RuntimeError):
    pass


def check_gunicorn(cfg) -> None:
    workers = cfg.workers
    worker_class = getattr(cfg, "worker_class_str", None) or str(cfg.worker_class)
    if workers != 1 or "gthread" not in worker_class.lower():
        raise SingleInstanceError(
            f"gunicorn must run exactly one gthread worker (workers={workers}, worker_class={worker_class})"
        )


def lock_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///") or database_url.endswith(":memory:"):
        return None
    return Path(database_url.removeprefix("sqlite:///") + ".api.lock")


def acquire_lock(database_url: str) -> Path | None:
    path = lock_path(database_url)
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise SingleInstanceError(f"another API instance holds {path}") from exc
    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode())
    _held.append(fd)
    return path


def release_all() -> None:
    while _held:
        fd = _held.pop()
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
