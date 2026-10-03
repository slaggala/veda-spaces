"""External anchor store for the security-event chain (05 §9.6, SEVT-007).

Objects are written once and never overwritten (an identical re-write is accepted, so retries are idempotent):

* ``anchor``: the chain head (``chain_seq``, ``row_hash``, key label) written daily.
* ``export``: the archived segment itself (JSON lines), written before the segment is deleted.
* ``pending``: the manifest of a segment about to be deleted (first/last sequence, count, SHA-256 of the export,
  last archived row hash), written before the database transaction that deletes it.

  Exports and pending manifests are keyed by ``(first_seq, last_seq, run id)`` (FC-13), so an abandoned attempt
  can never occupy the key of a later, different segment that happens to end at the same sequence. The manifest
  names its export (``export_id``); manifests written before FC-13 name it by ``last_seq`` alone.
* ``archive``: the same manifest, written only after that transaction committed. Verification counts only
  ``archive`` manifests, checks them against the ``export`` objects and the SECURITY_LOG_ARCHIVED events, and
  treats a ``pending`` manifest whose rows are still online as an abandoned attempt (RR-05, RR-06).

Production uses an S3 bucket with Object Lock in COMPLIANCE mode (write-only role for the writer, read-only
role for verification). Local and test use a directory of JSON files with the same layout. Verification reads
the store, not the database host, so an attacker who controls the host cannot move the anchor (IR-03).
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from veda.config import settings
from veda.kernel import clock

PREFIX = "security-log"
RETENTION = timedelta(days=3650)


def _key(kind: str, ident: int | str, ext: str = "json") -> str:
    name = f"{ident:012d}" if isinstance(ident, int) else ident
    return f"{PREFIX}/{kind}s/{name}.{ext}"


def segment_id(first_seq: int, last_seq: int, run_id: str) -> str:
    """Object name of one archival run's export and pending manifest (FC-13); sorts by first sequence."""
    return f"{first_seq:012d}-{last_seq:012d}-{run_id}"


def export_id(manifest: dict) -> int | str:
    """The export a manifest describes: its own ``export_id``, or ``last_seq`` for a pre-FC-13 manifest."""
    return manifest.get("export_id") or manifest["last_seq"]


class LocalAnchorStore:
    def __init__(self, root: Path):
        self.root = root

    def put(self, kind: str, seq: int | str, body: dict) -> None:
        path = self.root / _key(kind, seq)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(body, sort_keys=True)
        if path.exists():  # write-once, like Object Lock
            if path.read_text() == data:
                return
            raise RuntimeError(f"anchor object {path.name} already exists")
        path.write_text(data)

    def put_blob(self, kind: str, seq: int | str, data: bytes) -> None:
        path = self.root / _key(kind, seq, "jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() == data:
                return
            raise RuntimeError(f"anchor object {path.name} already exists")
        path.write_bytes(data)

    def get_blob(self, kind: str, seq: int | str) -> bytes | None:
        path = self.root / _key(kind, seq, "jsonl")
        return path.read_bytes() if path.exists() else None

    def _all(self, kind: str) -> list[dict]:
        folder = self.root / PREFIX / f"{kind}s"
        return [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))] if folder.exists() else []

    def latest(self, kind: str) -> dict | None:
        items = self._all(kind)
        return items[-1] if items else None

    def all(self, kind: str) -> list[dict]:
        return self._all(kind)


class S3AnchorStore:
    """Object Lock bucket. ``client`` is a boto3 S3 client (injected in tests)."""

    def __init__(self, bucket: str, client=None):
        self.bucket = bucket
        if client is None:  # pragma: no cover - AWS
            import boto3

            client = boto3.client("s3", region_name=settings().aws_region)
        self.client = client

    def put(self, kind: str, seq: int | str, body: dict) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=_key(kind, seq),
            Body=json.dumps(body, sort_keys=True).encode(),
            ObjectLockMode="COMPLIANCE",
            ObjectLockRetainUntilDate=clock.now() + RETENTION,
            ContentType="application/json",
        )

    def put_blob(self, kind: str, seq: int | str, data: bytes) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=_key(kind, seq, "jsonl"),
            Body=data,
            ObjectLockMode="COMPLIANCE",
            ObjectLockRetainUntilDate=clock.now() + RETENTION,
            ContentType="application/x-ndjson",
        )

    def get_blob(self, kind: str, seq: int | str) -> bytes | None:
        key = _key(kind, seq, "jsonl")
        if key not in self._keys(kind, ext="jsonl"):
            return None
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def _keys(self, kind: str, ext: str = "json") -> list[str]:
        keys: list[str] = []
        token = None
        while True:
            kwargs = {"Bucket": self.bucket, "Prefix": f"{PREFIX}/{kind}s/"}
            if token:
                kwargs["ContinuationToken"] = token
            page = self.client.list_objects_v2(**kwargs)
            keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(f".{ext}")]
            if not page.get("IsTruncated"):
                return sorted(keys)
            token = page.get("NextContinuationToken")

    def _get(self, key: str) -> dict:
        return json.loads(self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read())

    def latest(self, kind: str) -> dict | None:
        keys = self._keys(kind)
        return self._get(keys[-1]) if keys else None

    def all(self, kind: str) -> list[dict]:
        return [self._get(k) for k in self._keys(kind)]


_override = None


def use_store(store) -> None:
    global _override
    _override = store


def store():
    if _override is not None:
        return _override
    s = settings()
    if s.anchor_bucket:  # pragma: no cover - AWS
        return S3AnchorStore(s.anchor_bucket)
    return LocalAnchorStore(Path(s.anchor_dir or "var/anchors"))
