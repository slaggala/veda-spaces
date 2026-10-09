"""Catalog lifecycle (ADR-013 D3): versioned records, immutable releases, four-eyes approval, activation, rollback.

Records: DRAFT → IN_REVIEW → APPROVED (then SCHEDULED, ACTIVE, RETIRED, ARCHIVED through releases). Only a DRAFT is
edited; changing reviewed, approved or active content creates a new DRAFT version. Releases: an immutable manifest of
exact record versions; DRAFT → IN_REVIEW → APPROVED → SCHEDULED → ACTIVE → RETIRED. Activation re-runs the whole
validation suite and fails closed; rollback restores the previous release's whole manifest as a new release.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import db
from veda.kernel.context import current_actor

from . import kinds
from .models import CatalogEvent, CatalogRecord, CatalogRelease

KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,99}$")
RELEASE_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,31}$")  # the card version is CATALOG-<code> (≤ 40)


class CatalogError(ValueError):
    """A refused catalog action; the message is safe to show to the staff member (no rates, no record contents)."""


def sha(document: dict) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _actor_id() -> str | None:
    ctx = current_actor()
    return ctx.actor_id if ctx else None


def _event(s: Session, event_type: str, *, record=None, release=None, detail=None) -> None:
    s.add(
        CatalogEvent(
            event_type=event_type,
            record_id=record.id if record is not None else None,
            release_id=release.id if release is not None else None,
            detail=detail,
        )
    )


def _four_eyes() -> bool:
    return settings().catalog_four_eyes


# --- records -----------------------------------------------------------------------------------------------------------
def get_record(s: Session, record_id: str) -> CatalogRecord:
    row = s.get(CatalogRecord, record_id)
    if row is None or row.is_deleted:
        raise CatalogError("no such catalog record")
    return row


def versions(s: Session, kind: str, key: str) -> list[CatalogRecord]:
    return list(
        s.execute(
            sa.select(CatalogRecord)
            .where(CatalogRecord.kind == kind, CatalogRecord.record_key == key, CatalogRecord.is_deleted.is_(False))
            .order_by(CatalogRecord.record_version)
        ).scalars()
    )


def validate(kind: str, document: dict) -> kinds._Model:
    try:
        return kinds.parse(kind, document)
    except kinds.KindError as err:
        raise CatalogError(str(err)) from err
    except ValueError as err:  # pydantic: say where, not the submitted values
        raise CatalogError(f"invalid {kind}: {_errors(err)}") from err


def _errors(err) -> str:
    if hasattr(err, "errors"):
        return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in err.errors()[:8])
    return str(err).splitlines()[0]


def _contribute(row: CatalogRecord) -> None:
    """Record the acting user as a contributor of this version (append-only; never removed)."""
    me = _actor_id()
    if me and me not in (row.contributors or []):
        row.contributors = [*(row.contributors or []), me]


def contributors(s: Session, row: CatalogRecord) -> set[str]:
    """Everyone who created, edited or submitted this version: the stored set, the row's creator and submitter, and
    the authors of its create/edit/submit events, so that clearing one source never clears the others."""
    found = set(row.contributors or [])
    found.update(x for x in (row.created_by, row.submitted_by) if x)  # not updated_by: a reviewer's action sets it
    found.update(
        s.execute(
            sa.select(CatalogEvent.created_by).where(
                CatalogEvent.record_id == row.id,
                CatalogEvent.event_type.in_(("RECORD_CREATED", "RECORD_UPDATED", "RECORD_SUBMITTED")),
            )
        ).scalars()
    )
    return found


def create_record(s: Session, kind: str, key: str, document: dict) -> CatalogRecord:
    """A new DRAFT: version 1 of a new key, or the next version of an existing key (one open draft at a time)."""
    if not KEY_RE.match(key or ""):
        raise CatalogError("a catalog key is lowercase letters, digits, '_', '.' or '-' (2–100 characters)")
    model = validate(kind, document)
    existing = versions(s, kind, key)
    if any(r.status == "DRAFT" for r in existing):
        raise CatalogError(f"{kind} {key} already has an open draft; edit it instead")
    row = CatalogRecord(
        kind=kind,
        record_key=key,
        record_version=(existing[-1].record_version + 1) if existing else 1,
        status="DRAFT",
        title=kinds.title(kind, model),
        document=document,
        document_sha256=sha(document),
        contributors=[],
    )
    _contribute(row)
    s.add(row)
    s.flush()
    _event(s, "RECORD_CREATED", record=row, detail={"kind": kind, "key": key, "version": row.record_version})
    return row


def new_version(s: Session, kind: str, key: str) -> CatalogRecord:
    """A DRAFT copy of the latest version, to change reviewed, approved or active content."""
    existing = versions(s, kind, key)
    if not existing:
        raise CatalogError(f"no {kind} {key}")
    return create_record(s, kind, key, existing[-1].document)


def clone(s: Session, record_id: str, new_key: str) -> CatalogRecord:
    source = get_record(s, record_id)
    if versions(s, source.kind, new_key):
        raise CatalogError(f"{source.kind} {new_key} already exists")
    return create_record(s, source.kind, new_key, source.document)


def update_draft(s: Session, record_id: str, document: dict) -> CatalogRecord:
    row = get_record(s, record_id)
    if row.status != "DRAFT":
        raise CatalogError(f"only a DRAFT is edited (this version is {row.status}); create a new version")
    model = validate(row.kind, document)
    row.document, row.document_sha256, row.title = document, sha(document), kinds.title(row.kind, model)
    row.review_note, row.reviewed_by, row.reviewed_on = None, None, None  # an earlier review no longer applies
    _contribute(row)
    _event(s, "RECORD_UPDATED", record=row, detail={"version": row.record_version})
    return row


def submit(s: Session, record_id: str) -> CatalogRecord:
    row = get_record(s, record_id)
    if row.status != "DRAFT":
        raise CatalogError(f"only a DRAFT is submitted (this version is {row.status})")
    validate(row.kind, row.document)
    if row.document_sha256 != sha(row.document):
        raise CatalogError("the stored document does not match its SHA-256; refusing")
    row.status, row.submitted_by, row.submitted_on = "IN_REVIEW", _actor_id(), db.tx_time(s)
    row.reviewed_by, row.reviewed_on = None, None
    _contribute(row)
    _event(s, "RECORD_SUBMITTED", record=row, detail={"version": row.record_version})
    return row


def approve_record(s: Session, record_id: str, note: str | None = None) -> CatalogRecord:
    row = get_record(s, record_id)
    if row.status != "IN_REVIEW":
        raise CatalogError(f"only a record IN_REVIEW is approved (this version is {row.status})")
    me = _actor_id()
    if _four_eyes() and (me is None or me in contributors(s, row)):
        raise CatalogError("four-eyes review: a record is approved by someone who did not create, edit or submit it")
    validate(row.kind, row.document)
    row.status, row.reviewed_by, row.reviewed_on = "APPROVED", me, db.tx_time(s)
    row.review_note = (note or "").strip()[:300] or None
    _event(s, "RECORD_APPROVED", record=row, detail={"version": row.record_version})
    return row


def reject_record(s: Session, record_id: str, note: str) -> CatalogRecord:
    row = get_record(s, record_id)
    if row.status != "IN_REVIEW":
        raise CatalogError(f"only a record IN_REVIEW is rejected (this version is {row.status})")
    if len((note or "").strip()) < 5:
        raise CatalogError("say why it is rejected (at least 5 characters)")
    row.status, row.reviewed_by, row.reviewed_on, row.review_note = "DRAFT", _actor_id(), db.tx_time(s), note[:300]
    _event(s, "RECORD_REJECTED", record=row, detail={"version": row.record_version})
    return row


def archive_record(s: Session, record_id: str) -> CatalogRecord:
    row = get_record(s, record_id)
    if row.status not in ("DRAFT", "RETIRED", "APPROVED"):
        raise CatalogError(f"a {row.status} record cannot be archived; retire it through a release first")
    if row.status == "APPROVED" and _in_unfinished_release(s, row):
        raise CatalogError("this version is part of a release in progress")
    row.status = "ARCHIVED"
    _event(s, "RECORD_ARCHIVED", record=row, detail={"version": row.record_version})
    return row


def _in_unfinished_release(s: Session, row: CatalogRecord) -> bool:
    for release in s.execute(
        sa.select(CatalogRelease).where(
            CatalogRelease.status.in_(("DRAFT", "IN_REVIEW", "APPROVED", "SCHEDULED")),
            CatalogRelease.is_deleted.is_(False),
        )
    ).scalars():
        if any(e["record_id"] == row.id for e in release.manifest["entries"]):
            return True
    return False


# --- releases ----------------------------------------------------------------------------------------------------------
def active_release(s: Session) -> CatalogRelease | None:
    return s.execute(
        sa.select(CatalogRelease).where(CatalogRelease.status == "ACTIVE", CatalogRelease.is_deleted.is_(False))
    ).scalar_one_or_none()


def get_release(s: Session, release_id: str) -> CatalogRelease:
    row = s.get(CatalogRelease, release_id)
    if row is None or row.is_deleted:
        raise CatalogError("no such catalog release")
    return row


def create_release(s: Session, code: str, *, exclude: tuple[tuple[str, str], ...] = ()) -> CatalogRelease:
    """A DRAFT manifest: for every key, its newest APPROVED version, otherwise its ACTIVE version. `exclude` retires
    keys. Nothing changes for customers until the release is approved and activated."""
    code = (code or "").strip().upper()
    if not RELEASE_CODE_RE.match(code):
        raise CatalogError("a release code is 3–32 capital letters, digits, '.', '_' or '-'")
    if s.execute(sa.select(CatalogRelease.id).where(CatalogRelease.release_code == code)).first():
        raise CatalogError(f"release {code} already exists")
    rows = s.execute(
        sa.select(CatalogRecord).where(
            CatalogRecord.status.in_(("APPROVED", "ACTIVE")), CatalogRecord.is_deleted.is_(False)
        )
    ).scalars()
    chosen: dict[tuple[str, str], CatalogRecord] = {}
    for row in rows:
        k = (row.kind, row.record_key)
        if k in set(exclude):
            continue
        current = chosen.get(k)
        rank = (row.status == "APPROVED", row.record_version)
        if current is None or rank > (current.status == "APPROVED", current.record_version):
            chosen[k] = row
    if not chosen:
        raise CatalogError("there is nothing approved or active to release")
    entries = [
        {
            "kind": r.kind,
            "key": r.record_key,
            "version": r.record_version,
            "sha256": r.document_sha256,
            "record_id": r.id,
        }
        for r in sorted(chosen.values(), key=lambda r: (r.kind, r.record_key))
    ]
    manifest = {"release_code": code, "entries": entries}
    previous = active_release(s)
    release = CatalogRelease(
        release_code=code,
        status="DRAFT",
        manifest=manifest,
        manifest_sha256=sha(manifest),
        previous_release_id=previous.id if previous else None,
        release_owner=_actor_id(),
    )
    s.add(release)
    s.flush()
    _event(s, "RELEASE_CREATED", release=release, detail={"code": code, "entries": len(entries)})
    return release


def release_records(s: Session, release: CatalogRelease) -> list[CatalogRecord]:
    """The manifest's records, each checked against the digest the manifest froze (fail closed on any drift)."""
    out = []
    for e in release.manifest["entries"]:
        row = s.get(CatalogRecord, e["record_id"])
        if (
            row is None
            or row.record_version != e["version"]
            or row.document_sha256 != e["sha256"]
            or sha(row.document) != e["sha256"]
        ):
            raise CatalogError(
                f"release {release.release_code}: {e['kind']} {e['key']} v{e['version']} changed; refusing"
            )
        out.append(row)
    if sha(release.manifest) != release.manifest_sha256:
        raise CatalogError(f"release {release.release_code}: the manifest does not match its SHA-256; refusing")
    return out


def validate_release(s: Session, release_id: str) -> dict:
    from . import validation

    release = get_release(s, release_id)
    report = validation.validate(s, release)
    release.validation = report
    release.compiled = report.get("compiled")
    _event(s, "RELEASE_VALIDATED", release=release, detail={"ok": report["ok"], "errors": len(report["errors"])})
    return report


def _require_valid(s: Session, release: CatalogRelease) -> dict:
    report = validate_release(s, release.id)
    if not report["ok"]:
        raise CatalogError(f"release {release.release_code} does not validate: {'; '.join(report['errors'][:5])}")
    return report


def _release_contributors(s: Session, release: CatalogRelease) -> set[str]:
    """Contributors to every record this release adds or changes against the active release (pricing, copy, rules,
    media mappings and everything else)."""
    changed = diff(s, release)
    keys = {(e["kind"], e["key"], e["version"]) for e in [*changed["added"], *changed["changed"]]}
    found: set[str] = set()
    for e in release.manifest["entries"]:
        if (e["kind"], e["key"], e["version"]) in keys:
            row = s.get(CatalogRecord, e["record_id"])
            if row is not None:
                found |= contributors(s, row)
    return found


def _release_four_eyes(s: Session, release: CatalogRelease, what: str, *also: str | None) -> str | None:
    me = _actor_id()
    if _four_eyes() and (me is None or me in {release.created_by, *also} or me in _release_contributors(s, release)):
        raise CatalogError(
            f"four-eyes review: the {what} is approved by someone who did not author the release or change its records"
        )
    return me


def approve_preview(s: Session, release_id: str) -> CatalogRelease:
    release = get_release(s, release_id)
    if release.status not in ("DRAFT", "IN_REVIEW"):
        raise CatalogError(f"the preview is approved before release approval (release is {release.status})")
    _require_valid(s, release)
    me = _release_four_eyes(s, release, "customer preview")
    release.preview_approved_by, release.preview_approved_on = me, db.tx_time(s)
    _event(s, "RELEASE_PREVIEW_APPROVED", release=release)
    return release


def submit_release(s: Session, release_id: str) -> CatalogRelease:
    release = get_release(s, release_id)
    if release.status != "DRAFT":
        raise CatalogError(f"only a DRAFT release is submitted (this one is {release.status})")
    _require_valid(s, release)
    if release.preview_approved_on is None:
        raise CatalogError("approve the customer preview first")
    release.status, release.submitted_by = "IN_REVIEW", _actor_id()
    _event(s, "RELEASE_SUBMITTED", release=release)
    return release


def approve_release(s: Session, release_id: str, approval_reference: str) -> CatalogRelease:
    release = get_release(s, release_id)
    if release.status != "IN_REVIEW":
        raise CatalogError(f"only a release IN_REVIEW is approved (this one is {release.status})")
    if len((approval_reference or "").strip()) < 10:
        raise CatalogError("approval needs an approval reference (at least 10 characters)")
    me = _release_four_eyes(s, release, "release", release.submitted_by)
    _require_valid(s, release)
    release.status, release.approved_by, release.approved_on = "APPROVED", me, db.tx_time(s)
    release.approval_reference = approval_reference.strip()[:200]
    _event(s, "RELEASE_APPROVED", release=release, detail={"approval_reference": release.approval_reference})
    return release


def reject_release(s: Session, release_id: str, note: str) -> CatalogRelease:
    """Send a release back to DRAFT: every approval, the schedule and any SCHEDULED record state are cleared in one
    step (nothing is left half-scheduled); the event keeps what was cleared."""
    release = get_release(s, release_id)
    if release.status not in ("IN_REVIEW", "APPROVED", "SCHEDULED"):
        raise CatalogError(f"a {release.status} release is not rejected")
    if len((note or "").strip()) < 5:
        raise CatalogError("say why it is rejected (at least 5 characters)")
    cleared = {
        "status": release.status,
        "preview_approved_by": release.preview_approved_by,
        "submitted_by": release.submitted_by,
        "approved_by": release.approved_by,
        "approval_reference": release.approval_reference,
        "scheduled_for": release.scheduled_for.isoformat() if release.scheduled_for else None,
    }
    for row in release_records(s, release):
        if row.status == "SCHEDULED":
            row.status = "APPROVED"  # approved content stays approved and editable through a new version
    release.status = "DRAFT"
    release.preview_approved_by = release.preview_approved_on = None
    release.submitted_by = release.approved_by = release.approved_on = None
    release.approval_reference = release.scheduled_for = None
    _event(s, "RELEASE_REJECTED", release=release, detail={"note": note.strip()[:300], "cleared": cleared})
    return release


def schedule_release(s: Session, release_id: str, at: datetime) -> CatalogRelease:
    release = get_release(s, release_id)
    if release.status != "APPROVED":
        raise CatalogError(f"only an APPROVED release is scheduled (this one is {release.status})")
    if at <= db.tx_time(s):
        raise CatalogError("schedule a time in the future, or activate now")
    release.status, release.scheduled_for = "SCHEDULED", at
    for row in release_records(s, release):
        if row.status == "APPROVED":
            row.status = "SCHEDULED"
    _event(s, "RELEASE_SCHEDULED", release=release, detail={"at": at.isoformat()})
    return release


def activate_release(s: Session, release_id: str, *, rollback: bool = False) -> CatalogRelease:
    """Make the release the one ACTIVE catalog (re-validated first; fails closed). Its records become ACTIVE, the
    previous release's records RETIRED (unless carried over), and its compiled card is stored for V3 pricing only."""
    from . import compile as catalog_compile

    release = get_release(s, release_id)
    if release.status not in ("APPROVED", "SCHEDULED"):
        raise CatalogError(f"a {release.status} release cannot be activated")
    if rollback != (release.rollback_of_id is not None):
        raise CatalogError("only a rollback release is activated as a rollback")
    if release.approved_on is None:
        raise CatalogError("the release has no approval")
    if release.status == "SCHEDULED" and release.scheduled_for and release.scheduled_for > db.tx_time(s):
        raise CatalogError("the release is scheduled for later")
    _require_valid(s, release)
    records = release_records(s, release)
    now = db.tx_time(s)
    current = active_release(s)
    keep = {r.id for r in records}
    if current is not None:
        current.status, current.deactivated_on = "RETIRED", now
        for row in release_records(s, current):
            if row.id not in keep and row.status == "ACTIVE":
                row.status = "RETIRED"
        _event(s, "RELEASE_RETIRED", release=current, detail={"by": release.release_code})
        s.flush()
    for row in records:
        others = s.execute(
            sa.select(CatalogRecord).where(
                CatalogRecord.kind == row.kind,
                CatalogRecord.record_key == row.record_key,
                CatalogRecord.status == "ACTIVE",
                CatalogRecord.id != row.id,
            )
        ).scalars()
        for other in others:
            other.status = "RETIRED"
    s.flush()
    for row in records:
        row.status = "ACTIVE"
    release.rate_card_id = catalog_compile.store_card(s, release).id
    release.status, release.activated_on, release.deactivated_on = "ACTIVE", now, None
    _event(
        s,
        "RELEASE_ROLLED_BACK" if rollback else "RELEASE_ACTIVATED",
        release=release,
        detail={"code": release.release_code, "manifest_sha256": release.manifest_sha256,
                "previous": current.release_code if current else None},
    )  # fmt: skip
    return release


def rollback(s: Session, reason: str) -> CatalogRelease:
    """Restore the previous release's exact manifest as a new release and activate it. No release row is reset or
    edited: the active one is retired as on any activation, and the restored one is a new, immutable record that
    names the release it restores (`rollback_of_id`). Validation runs again and fails closed."""
    if len((reason or "").strip()) < 10:
        raise CatalogError("a rollback needs its reason or approval reference (at least 10 characters)")
    current = active_release(s)
    if current is None or current.previous_release_id is None:
        raise CatalogError("there is no previous release to roll back to")
    target = get_release(s, current.previous_release_id)
    release_records(s, target)  # the restored manifest must still match its records exactly
    now = db.tx_time(s)
    code = f"RB{now:%Y%m%d%H%M%S}"
    manifest = {"release_code": code, "entries": [dict(e) for e in target.manifest["entries"]],
                "rollback_of": target.release_code}  # fmt: skip
    me = _actor_id()
    restored = CatalogRelease(
        release_code=code,
        status="APPROVED",
        manifest=manifest,
        manifest_sha256=sha(manifest),
        previous_release_id=current.id,
        rollback_of_id=target.id,
        release_owner=me,
        preview_approved_by=target.preview_approved_by,
        preview_approved_on=target.preview_approved_on,
        submitted_by=me,
        approved_by=me,
        approved_on=now,
        approval_reference=f"Rollback to {target.release_code}: {reason.strip()}"[:200],
    )
    s.add(restored)
    s.flush()
    _event(s, "RELEASE_CREATED", release=restored, detail={"code": code, "rollback_of": target.release_code})
    return activate_release(s, restored.id, rollback=True)


def run_scheduled(s: Session) -> list[str]:
    """Activate SCHEDULED releases whose time has come (scheduler job `catalog-activation`)."""
    due = s.execute(
        sa.select(CatalogRelease)
        .where(CatalogRelease.status == "SCHEDULED", CatalogRelease.scheduled_for <= db.tx_time(s))
        .order_by(CatalogRelease.scheduled_for)
    ).scalars()
    return [activate_release(s, r.id).release_code for r in due]


# --- review aids -------------------------------------------------------------------------------------------------------
def diff(s: Session, release: CatalogRelease, against: CatalogRelease | None = None) -> dict:
    """What the release changes against another (by default the ACTIVE release): keys added, removed, re-versioned."""
    against = against if against is not None else active_release(s)
    mine = {(e["kind"], e["key"]): e for e in release.manifest["entries"]}
    theirs = {(e["kind"], e["key"]): e for e in (against.manifest["entries"] if against else [])}

    def label(e):
        return {"kind": e["kind"], "key": e["key"], "version": e["version"]}

    return {
        "against": against.release_code if against else None,
        "added": [label(mine[k]) for k in sorted(set(mine) - set(theirs))],
        "removed": [label(theirs[k]) for k in sorted(set(theirs) - set(mine))],
        "changed": [
            {**label(mine[k]), "from_version": theirs[k]["version"]}
            for k in sorted(set(mine) & set(theirs))
            if mine[k]["sha256"] != theirs[k]["sha256"]
        ],
    }


def dashboard(s: Session, *, can_price: bool) -> dict:
    live = CatalogRecord.is_deleted.is_(False)
    counts = dict(
        s.execute(sa.select(CatalogRecord.status, sa.func.count()).where(live).group_by(CatalogRecord.status)).all()
    )
    active = active_release(s)
    latest_release = (
        s.execute(
            sa.select(CatalogRelease)
            .where(CatalogRelease.is_deleted.is_(False))
            .order_by(CatalogRelease.created_on.desc())
        )
        .scalars()
        .first()
    )
    report = (latest_release.validation or {}) if latest_release else {}
    warnings = report.get("warnings", [])
    errors = report.get("errors", [])
    if not can_price:
        errors = [e for e in errors if not e.startswith(("pricing:", "card:"))]
    scheduled = s.execute(
        sa.select(CatalogRelease).where(CatalogRelease.status == "SCHEDULED", CatalogRelease.is_deleted.is_(False))
    ).scalars()
    recent = s.execute(
        sa.select(CatalogEvent)
        .where(CatalogEvent.is_deleted.is_(False))
        .order_by(CatalogEvent.created_on.desc())
        .limit(15)
    ).scalars()
    return {
        "active_release": active.release_code if active else None,
        "drafts": counts.get("DRAFT", 0),
        "pending_review": counts.get("IN_REVIEW", 0),
        "approved_unreleased": counts.get("APPROVED", 0),
        "latest_release": latest_release.release_code if latest_release else None,
        "latest_release_status": latest_release.status if latest_release else None,
        "products_missing_images": [w for w in warnings if w.startswith("product ") and w.endswith("no image")],
        "extras_without_explanation": [w for w in warnings if "What is this" in w],
        "materials_without_specification": [e for e in errors if e.startswith("promises: material")],
        "unpriced_items": [e for e in errors if "is not priced" in e] if can_price else None,
        "unsupported_combinations": [e for e in errors if e.startswith("rules:")],
        "validation_errors": len(errors),
        "scheduled": [
            {"release": r.release_code, "at": r.scheduled_for.isoformat() if r.scheduled_for else None}
            for r in scheduled
        ],
        "recent": [{"event": e.event_type, "on": e.created_on.isoformat(), "by": e.created_by} for e in recent],
    }
