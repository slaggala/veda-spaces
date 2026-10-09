"""Catalog import and export (CSV or JSON). Import is a dry run first; applying it creates DRAFT records only.

A spreadsheet never approves, releases or activates anything (owner instruction). CSV columns: `kind,key,document`,
where `document` is the record's JSON. XLSX waits for an approved library (ADR-013 owner decision); export a sheet as
CSV meanwhile.

The dry run reports, per row: schema errors, duplicates within the file, references that resolve neither in the file
nor in the catalog, and the change (new key, new version, or unchanged).
"""

from __future__ import annotations

import csv
import io
import json

import sqlalchemy as sa
from sqlalchemy.orm import Session

from . import kinds, service
from .models import CatalogRecord, CatalogRelease

MAX_ROWS = 2000
COLUMNS = ("kind", "key", "document")


class ImportError_(ValueError):
    pass


def parse_rows(content: str, fmt: str) -> list[dict]:
    if fmt == "json":
        try:
            data = json.loads(content)
        except ValueError as err:
            raise ImportError_("the file is not valid JSON") from err
        rows = data.get("records") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise ImportError_('a JSON import is {"records": [{"kind", "key", "document"}]}')
    elif fmt == "csv":
        reader = csv.DictReader(io.StringIO(content))
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ImportError_(f"the CSV header must be exactly {','.join(COLUMNS)}")
        rows = []
        for i, r in enumerate(reader, start=2):
            try:
                rows.append({"kind": r["kind"], "key": r["key"], "document": json.loads(r["document"] or "")})
            except ValueError:
                rows.append({"kind": r["kind"], "key": r["key"], "document": None, "line": i})
    else:
        raise ImportError_("the format is csv or json (XLSX awaits an approved library)")
    if len(rows) > MAX_ROWS:
        raise ImportError_(f"at most {MAX_ROWS} rows per import")
    return rows


def _latest(s: Session, kind: str, key: str) -> CatalogRecord | None:
    return (
        s.execute(
            sa.select(CatalogRecord)
            .where(CatalogRecord.kind == kind, CatalogRecord.record_key == key, CatalogRecord.is_deleted.is_(False))
            .order_by(CatalogRecord.record_version.desc())
        )
        .scalars()
        .first()
    )


def dry_run(s: Session, rows: list[dict], *, can_price: bool) -> dict:
    out = []
    seen: set[tuple[str, str]] = set()
    in_file = {(r.get("kind"), r.get("key")) for r in rows}
    for i, r in enumerate(rows, start=1):
        kind, key, document = r.get("kind"), r.get("key"), r.get("document")
        row = {"row": i, "kind": kind, "key": key, "errors": [], "change": None}
        out.append(row)
        if kind not in kinds.SCHEMAS:
            row["errors"].append("unknown kind")
            continue
        if kind == "pricing" and not can_price:
            row["errors"].append("pricing rows need catalog.pricing.edit")
            continue
        if (kind, key) in seen:
            row["errors"].append("duplicate kind and key in this file")
            continue
        seen.add((kind, key))
        if not isinstance(document, dict):
            row["errors"].append("the document is not a JSON object")
            continue
        try:
            model = service.validate(kind, document)
            if not service.KEY_RE.match(key or ""):
                raise service.CatalogError("invalid key")
        except service.CatalogError as err:
            row["errors"].append(str(err)[:300])
            continue
        for rkind, rkey in kinds.references(kind, model):
            if (rkind, rkey) not in in_file and _latest(s, rkind, rkey) is None:
                row["errors"].append(f"refers to {rkind} {rkey}, which is neither in the file nor in the catalog")
        latest = _latest(s, kind, key)
        if latest is None:
            row["change"] = "new"
        elif latest.document_sha256 == service.sha(document):
            row["change"] = "unchanged"
        elif latest.status == "DRAFT":
            row["errors"].append(f"version {latest.record_version} is an open draft; finish or archive it first")
        else:
            row["change"] = f"new version {latest.record_version + 1}"
            row["changed_fields"] = sorted(
                k for k in set(document) | set(latest.document) if document.get(k) != latest.document.get(k)
            )
    return {"ok": all(not r["errors"] for r in out), "rows": out}


def apply(s: Session, rows: list[dict], *, can_price: bool) -> dict:
    report = dry_run(s, rows, can_price=can_price)
    if not report["ok"]:
        raise ImportError_("the import has errors; correct them and run the dry run again")
    created = []
    for r, result in zip(rows, report["rows"], strict=True):
        if result["change"] == "unchanged":
            continue
        row = service.create_record(s, r["kind"], r["key"], r["document"])  # always DRAFT
        created.append({"kind": row.kind, "key": row.record_key, "version": row.record_version})
    service._event(s, "IMPORT_APPLIED", detail={"created": len(created), "rows": len(rows)})
    return {"created": created, "unchanged": sum(1 for r in report["rows"] if r["change"] == "unchanged")}


def export(s: Session, *, release_id: str | None = None, include_pricing: bool, fmt: str = "json") -> str:
    """A release's exact versions, or the latest version of every key. Pricing only with catalog.pricing.view."""
    if release_id:
        release = s.get(CatalogRelease, release_id)
        if release is None:
            raise ImportError_("no such release")
        rows = service.release_records(s, release)
        header = {"release": release.release_code, "manifest_sha256": release.manifest_sha256}
    else:
        latest: dict[tuple[str, str], CatalogRecord] = {}
        for r in s.execute(sa.select(CatalogRecord).where(CatalogRecord.is_deleted.is_(False))).scalars():
            k = (r.kind, r.record_key)
            if r.status != "ARCHIVED" and (k not in latest or r.record_version > latest[k].record_version):
                latest[k] = r
        rows = sorted(latest.values(), key=lambda r: (r.kind, r.record_key))
        header = {"release": None}
    rows = [r for r in rows if include_pricing or r.kind not in kinds.STAFF_ONLY_KINDS]
    records = [{"kind": r.kind, "key": r.record_key, "version": r.record_version, "document": r.document} for r in rows]
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(COLUMNS)
        for r in records:
            w.writerow([r["kind"], r["key"], json.dumps(r["document"], sort_keys=True, ensure_ascii=False)])
        return buf.getvalue()
    return json.dumps({"schema": "veda.catalog.export/1", **header, "records": records}, indent=2, sort_keys=True)
