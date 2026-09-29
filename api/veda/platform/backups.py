"""Nightly snapshot and automated restore verification (OPS-002, OPS-004, OPS-009; IR-11).

* ``snapshot``: ``VACUUM INTO`` a consistent copy of the live SQLite database, record its SHA-256 in a manifest,
  and, when ``VEDA_SNAPSHOT_BUCKET`` is set, upload both to the S3 bucket with Object Lock (COMPLIANCE). Local
  copies beyond ``VEDA_SNAPSHOT_KEEP`` are removed. Continuous replication is Litestream (deploy/litestream.yml).
* ``restore_verify``: restore the newest snapshot into a scratch file and prove it is usable: checksum,
  ``PRAGMA integrity_check`` and ``foreign_key_check``, schema at a revision this image knows, schema
  conformance (03 §2.7), and an intact security-event chain inside the copy.

Both emit metrics (SnapshotCompleted, SnapshotAge, RestoreVerified) that back the 02 §9 backup alerts. The
PostgreSQL target (PGM-1) uses managed snapshots instead; these jobs refuse to run against it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from veda.config import settings
from veda.kernel import clock, db, metrics

log = logging.getLogger("veda.backups")


def _db_path() -> Path:
    url = settings().database_url
    if not url.startswith("sqlite:///"):
        raise RuntimeError("snapshots and restore verification apply to the SQLite deployment only")
    return Path(url.removeprefix("sqlite:///"))


def _dir() -> Path:
    path = Path(settings().snapshot_dir or "var/snapshots")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot() -> dict:
    stamp = clock.now().strftime("%Y%m%dT%H%M%SZ")
    target = _dir() / f"veda-{stamp}.db"
    # VACUUM INTO writes a transactionally consistent copy while the application keeps running; it cannot run
    # inside a transaction, so it uses its own autocommit connection.
    raw = sqlite3.connect(_db_path(), isolation_level=None, timeout=30)
    try:
        raw.execute("VACUUM INTO ?", (str(target),))
    finally:
        raw.close()
    manifest: dict[str, Any] = {
        "file": target.name,
        "sha256": _sha256(target),
        "bytes": target.stat().st_size,
        "taken_on": clock.to_rfc3339(clock.now(), micros=True),
        "source": _db_path().name,
    }
    (target.with_suffix(".json")).write_text(json.dumps(manifest, sort_keys=True))
    bucket = settings().snapshot_bucket
    if bucket:  # pragma: no cover - AWS
        import boto3

        s3 = boto3.client("s3", region_name=settings().aws_region)
        retain = clock.now() + timedelta(days=settings().snapshot_lock_days)
        for path in (target, target.with_suffix(".json")):
            s3.upload_file(
                str(path),
                bucket,
                f"snapshots/{path.name}",
                ExtraArgs={"ObjectLockMode": "COMPLIANCE", "ObjectLockRetainUntilDate": retain},
            )
    snapshots = sorted(_dir().glob("veda-*.db"))
    for old in snapshots[: max(0, len(snapshots) - settings().snapshot_keep)]:
        old.unlink(missing_ok=True)
        old.with_suffix(".json").unlink(missing_ok=True)
    metrics.emit_many({"SnapshotCompleted": (1, "Count"), "SnapshotBytes": (float(manifest["bytes"]), "Bytes")})
    log.info("snapshot_completed file=%s bytes=%d", target.name, manifest["bytes"])
    return manifest


def latest_snapshot() -> tuple[Path, dict] | None:
    snapshots = sorted(_dir().glob("veda-*.db"))
    if not snapshots:
        return None
    path = snapshots[-1]
    return path, json.loads(path.with_suffix(".json").read_text())


def restore_verify() -> dict:
    """Restore the newest snapshot to a scratch file and verify it; raises (and alerts) on any failure."""
    from veda.kernel import conformance
    from veda.platform import health
    from veda.platform.auth import security_events

    found = latest_snapshot()
    try:
        if found is None:
            raise RuntimeError("no snapshot to verify")
        source, manifest = found
        if _sha256(source) != manifest["sha256"]:
            raise RuntimeError(f"snapshot {source.name} does not match its manifest checksum")
        with tempfile.TemporaryDirectory(prefix="veda-restore-") as tmp:
            restored = Path(tmp) / "restored.db"
            shutil.copyfile(source, restored)
            raw = sqlite3.connect(restored)
            try:
                integrity = raw.execute("PRAGMA integrity_check").fetchone()[0]
                fk_problems = raw.execute("PRAGMA foreign_key_check").fetchall()
            finally:
                raw.close()
            if integrity != "ok" or fk_problems:
                raise RuntimeError(
                    f"restored copy failed integrity checks: {integrity}, {len(fk_problems)} FK problems"
                )
            engine = db.create_engine(f"sqlite:///{restored}")
            try:
                with engine.connect() as conn:
                    revision = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
                    if revision not in health.known_revisions():
                        raise RuntimeError(f"restored schema at unknown revision {revision}")
                    report = conformance.check(conn)
                    if not report.ok:
                        raise RuntimeError(f"restored schema fails conformance: {report.problems[:3]}")
                    counts = {
                        t: conn.execute(sa.text(f"SELECT count(*) FROM {t}")).scalar()  # nosec B608
                        for t in ("app_user", "lead", "audit_log", "security_event_log")
                    }
                from sqlalchemy.orm import Session

                with Session(engine) as session:
                    first = session.execute(sa.text("SELECT min(chain_seq) FROM security_event_log")).scalar()
                    chain = security_events.verify_chain(session, from_seq=first or 1)
                if not chain.ok:
                    raise RuntimeError(f"restored security-event chain broken: {chain.problem} at {chain.at_seq}")
            finally:
                engine.dispose()
    except Exception:
        metrics.emit("RestoreVerified", 0)
        log.critical("restore_verification_failed", exc_info=True)
        raise
    metrics.emit("RestoreVerified", 1)
    log.info("restore_verification_passed file=%s", source.name)
    return {"file": source.name, "revision": revision, "counts": counts, "chain_rows": chain.checked}


def disk_usage() -> dict:
    """Disk use of the database volume (02 §9 alert: > 80 % used)."""
    usage = shutil.disk_usage(_db_path().parent)
    percent = usage.used / usage.total * 100 if usage.total else 0.0
    metrics.emit("DiskUsed", round(percent, 1), "Percent")
    return {"used_percent": round(percent, 1), "free_bytes": usage.free}
