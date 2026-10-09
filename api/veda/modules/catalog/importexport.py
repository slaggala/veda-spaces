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
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from . import kinds, service
from .models import CatalogRecord, CatalogRelease

MAX_ROWS = 2000
COLUMNS = ("kind", "key", "document")


class ImportError_(ValueError):
    pass


@dataclass(frozen=True)
class ImportRow:
    """One row as read from the file; `document` is None when the row's JSON could not be read."""

    kind: str
    key: str
    document: dict[str, Any] | None


@dataclass
class RowReport:
    row: int
    kind: str
    key: str
    errors: list[str] = field(default_factory=list)
    change: str | None = None
    changed_fields: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {"row": self.row, "kind": self.kind, "key": self.key, "errors": self.errors, "change": self.change,
                "changed_fields": self.changed_fields}  # fmt: skip


def _row(kind: object, key: object, document: object) -> ImportRow:
    return ImportRow(
        kind=kind if isinstance(kind, str) else "",
        key=key if isinstance(key, str) else "",
        document=document if isinstance(document, dict) else None,
    )


def parse_rows(content: str, fmt: str) -> list[ImportRow]:
    rows: list[ImportRow] = []
    if fmt == "json":
        try:
            data = json.loads(content)
        except ValueError as err:
            raise ImportError_("the file is not valid JSON") from err
        records = data.get("records") if isinstance(data, dict) else None
        if not isinstance(records, list):
            raise ImportError_('a JSON import is {"records": [{"kind", "key", "document"}]}')
        for r in records:
            rows.append(
                _row(r.get("kind"), r.get("key"), r.get("document")) if isinstance(r, dict) else _row("", "", None)
            )
    elif fmt == "csv":
        reader = csv.DictReader(io.StringIO(content))
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ImportError_(f"the CSV header must be exactly {','.join(COLUMNS)}")
        for r in reader:
            try:
                document = json.loads(r["document"] or "")
            except ValueError:
                document = None
            rows.append(_row(r["kind"], r["key"], document))
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


def _check(s: Session, i: int, r: ImportRow, seen: set[tuple[str, str]], in_file: set[tuple[str, str]],
           can_price: bool) -> RowReport:  # fmt: skip
    report = RowReport(row=i, kind=r.kind, key=r.key)
    if r.kind not in kinds.SCHEMAS:
        report.errors.append("unknown kind")
        return report
    if r.kind == "pricing" and not can_price:
        report.errors.append("pricing rows need catalog.pricing.edit")
        return report
    if (r.kind, r.key) in seen:
        report.errors.append("duplicate kind and key in this file")
        return report
    seen.add((r.kind, r.key))
    if r.document is None:
        report.errors.append("the document is not a JSON object")
        return report
    try:
        model = service.validate(r.kind, r.document)
        if not service.KEY_RE.match(r.key):
            raise service.CatalogError("invalid key")
    except service.CatalogError as err:
        report.errors.append(str(err)[:300])
        return report
    for rkind, rkey in kinds.references(r.kind, model):
        if (rkind, rkey) not in in_file and _latest(s, rkind, rkey) is None:
            report.errors.append(f"refers to {rkind} {rkey}, which is neither in the file nor in the catalog")
    latest = _latest(s, r.kind, r.key)
    if latest is None:
        report.change = "new"
    elif latest.document_sha256 == service.sha(r.document):
        report.change = "unchanged"
    elif latest.status == "DRAFT":
        report.errors.append(f"version {latest.record_version} is an open draft; finish or archive it first")
    else:
        report.change = f"new version {latest.record_version + 1}"
        report.changed_fields = sorted(
            k for k in set(r.document) | set(latest.document) if r.document.get(k) != latest.document.get(k)
        )
    return report


def dry_run(s: Session, rows: list[ImportRow], *, can_price: bool) -> dict[str, object]:
    seen: set[tuple[str, str]] = set()
    in_file = {(r.kind, r.key) for r in rows}
    reports = [_check(s, i, r, seen, in_file, can_price) for i, r in enumerate(rows, start=1)]
    return {"ok": all(not r.errors for r in reports), "rows": [r.as_dict() for r in reports]}


def apply(s: Session, rows: list[ImportRow], *, can_price: bool) -> dict[str, object]:
    seen: set[tuple[str, str]] = set()
    in_file = {(r.kind, r.key) for r in rows}
    reports = [_check(s, i, r, seen, in_file, can_price) for i, r in enumerate(rows, start=1)]
    if any(r.errors for r in reports):
        raise ImportError_("the import has errors; correct them and run the dry run again")
    created: list[dict[str, object]] = []
    for r, report in zip(rows, reports, strict=True):
        if report.change == "unchanged" or r.document is None:
            continue
        row = service.create_record(s, r.kind, r.key, r.document)  # always DRAFT
        created.append({"kind": row.kind, "key": row.record_key, "version": row.record_version})
    service._event(s, "IMPORT_APPLIED", detail={"created": len(created), "rows": len(rows)})
    return {"created": created, "unchanged": sum(1 for r in reports if r.change == "unchanged")}


def export(s: Session, *, release_id: str | None = None, include_pricing: bool, fmt: str = "json") -> str:
    """A release's exact versions, or the latest version of every key. Pricing only with catalog.pricing.view."""
    if release_id:
        release = s.get(CatalogRelease, release_id)
        if release is None:
            raise ImportError_("no such release")
        rows = service.release_records(s, release)
        header: dict[str, str | None] = {"release": release.release_code, "manifest_sha256": release.manifest_sha256}
    else:
        latest: dict[tuple[str, str], CatalogRecord] = {}
        for r in s.execute(sa.select(CatalogRecord).where(CatalogRecord.is_deleted.is_(False))).scalars():
            k = (r.kind, r.record_key)
            if r.status != "ARCHIVED" and (k not in latest or r.record_version > latest[k].record_version):
                latest[k] = r
        rows = sorted(latest.values(), key=lambda r: (r.kind, r.record_key))
        header = {"release": None}
    rows = [r for r in rows if include_pricing or r.kind not in kinds.STAFF_ONLY_KINDS]
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(COLUMNS)
        for rec in rows:
            w.writerow([rec.kind, rec.record_key, json.dumps(rec.document, sort_keys=True, ensure_ascii=False)])
        return buf.getvalue()
    records = [{"kind": r.kind, "key": r.record_key, "version": r.record_version, "document": r.document} for r in rows]
    return json.dumps({"schema": "veda.catalog.export/1", **header, "records": records}, indent=2, sort_keys=True)
