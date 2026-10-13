"""Measurement sets and revisions (MTQ B1-T06; blueprint §6.2; B1-SCOPE §2.3, §2.7, §2.9.3).

- A set is one revision of a property's measurements: DRAFT → SUBMITTED → VERIFIED → SUPERSEDED, or SUBMITTED →
  REJECTED. Only a DRAFT changes; a submitted revision is immutable. At most one DRAFT per property (database index).
- A correction or re-measure is a new revision (n+1) copied from an earlier one; the earlier one never changes.
- ``property_space.id`` is the join key across revisions (B1-SCOPE §2.7); walls keep their ids while a space is edited
  in a draft (matched by ``wall_index``), so photos stay attached to the wall they show.
- Two surveyors work on one draft by claiming spaces (B1-SCOPE §2.9.3). A claim lasts ``CLAIM_TTL`` from the holder's
  last write and can be released; an expired or released claim is taken over only explicitly (``take_over``).
- No last-write-wins: every write to an existing space names the version it edited (``base_version``); a stale write
  is refused with ``VERSION_CONFLICT`` and the fields that differ, and the client resolves it explicitly.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError, field_error, not_found

from . import scope
from .models import (
    MeasurementNote,
    MeasurementSet,
    MeasurementVisit,
    Property,
    PropertySpace,
    SpaceMeasurement,
    SpaceOpening,
    SpaceWall,
)

CLAIM_TTL = timedelta(hours=4)
MEASUREMENT_FIELDS = (
    "shape_code",
    "length_mm",
    "width_mm",
    "ceiling_height_mm",
    "beam_bottom_height_mm",
    "floor_to_lintel_mm",
    "stated_floor_area_sqft_centi",
    "polygon",
    "flooring_code",
    "existing_condition_code",
    "confidence_code",
    "is_complete",
    "attributes",
)
WALL_FIELDS = (
    "label",
    "length_mm",
    "height_mm",
    "wall_type_code",
    "is_external",
    "is_proposed",
    "usable_for_code",
    "obstructions",
    "client_ref",
)
OPENING_FIELDS = (
    "opening_type_code",
    "width_mm",
    "height_mm",
    "sill_height_mm",
    "offset_from_wall_start_mm",
    "swing_code",
    "deducts_from_wall_area",
    "purpose_code",
    "depth_mm",
    "is_existing",
)
# Hooks run after a space's walls are written (B1-T08 adds electrical points) and when a revision is copied.
AFTER_SPACE_WRITE: list = []
COPY_HOOKS: list = []


# --- access ------------------------------------------------------------------------------------------------------------
def _set_condition(ctx, permission: str):
    cond = scope.condition(ctx, permission, Property.lead_id)
    if ctx.scope(permission) is not None:
        cond = sa.or_(cond, MeasurementSet.captured_by == ctx.user.id)
    return cond


def get_visible(s: Session, ctx, set_id: str, permission: str = "measurement.read") -> tuple[MeasurementSet, Property]:
    row = s.execute(
        sa.select(MeasurementSet, Property)
        .join(Property, Property.id == MeasurementSet.property_id)
        .where(MeasurementSet.id == set_id, _set_condition(ctx, permission))
    ).first()
    if row is None:
        raise not_found()
    return row[0], row[1]


def require_draft(mset: MeasurementSet) -> None:
    if mset.status != "DRAFT":
        raise ApiError(409, "SET_FROZEN", f"This revision is {mset.status.lower()}; it can no longer change.",
                       extra={"status": mset.status})  # fmt: skip


def _require_capture(s: Session, ctx, prop: Property) -> None:
    scope.require_in_scope(s, ctx, prop.lead_id, "measurement.capture")


# --- create ------------------------------------------------------------------------------------------------------------
def _latest(s: Session, property_id: str, *statuses: str) -> MeasurementSet | None:
    return s.execute(
        sa.select(MeasurementSet)
        .where(MeasurementSet.property_id == property_id, MeasurementSet.status.in_(statuses))
        .order_by(MeasurementSet.revision_no.desc())
        .limit(1)
    ).scalar_one_or_none()


def _new_set(s: Session, ctx, prop: Property, *, visit: MeasurementVisit | None, body, level: str) -> MeasurementSet:
    draft = _latest(s, prop.id, "DRAFT")
    if draft is not None:
        raise ApiError(409, "DRAFT_EXISTS", "This property already has a draft revision; continue that one.",
                       extra={"measurement_set_id": draft.id})  # fmt: skip
    verified = _latest(s, prop.id, "VERIFIED")
    if verified is not None and verified.survey_level_code == "FULL" and level == "LITE":
        raise ApiError(422, "LITE_AFTER_FULL", "A Lite survey never supersedes a verified Full survey.")
    top = s.execute(
        sa.select(sa.func.max(MeasurementSet.revision_no))
        .where(MeasurementSet.property_id == prop.id)
        .execution_options(include_deleted=True)
    ).scalar()
    mset = MeasurementSet(
        property_id=prop.id,
        measurement_visit_id=visit.id if visit else None,
        revision_no=int(top or 0) + 1,
        supersedes_set_id=verified.id if verified else None,
        status="DRAFT",
        survey_level_code=level,
        method_code=body.method_code,
        unit_system_code=body.unit_system_code,
        captured_by=ctx.user.id,
        summary={},
        property_capture={},
        device_info=body.device_info.model_dump(exclude_none=True) if body.device_info else None,
    )
    s.add(mset)
    s.flush()
    if body.copy_from_set_id:
        source = s.get(MeasurementSet, body.copy_from_set_id)
        if source is None or source.property_id != prop.id or source.status == "DRAFT":
            raise ApiError(422, "VALIDATION_FAILED", "Copy from a submitted, verified or rejected revision of this property.",
                           errors=[field_error("copy_from_set_id", "INVALID", "Not a closed revision here.")])  # fmt: skip
        copy_revision(s, source, mset, ctx.user.id)
    return mset


def create_for_visit(s: Session, ctx, visit: MeasurementVisit, body) -> MeasurementSet:
    prop = s.get(Property, visit.property_id)
    if prop is None:
        raise not_found()
    _require_capture(s, ctx, prop)
    if visit.status != "IN_PROGRESS":
        raise ApiError(409, "VISIT_NOT_STARTED", "Start the visit before capturing measurements.")
    if ctx.scope("measurement.capture") != "ALL" and visit.assigned_to != ctx.user.id:
        raise ApiError(403, "PERMISSION_DENIED", "Only the assigned surveyor opens the visit's measurement set.",
                       extra={"permission": "measurement.capture"})  # fmt: skip
    return _new_set(s, ctx, prop, visit=visit, body=body, level=body.survey_level_code or visit.survey_level_code)


def create_from_plan(s: Session, ctx, prop: Property, body) -> MeasurementSet:
    """A paper or drawing pre-measure keyed in by staff: method PLAN_DRAWING, LITE, no visit (B1-SCOPE §4.2)."""
    _require_capture(s, ctx, prop)
    return _new_set(s, ctx, prop, visit=None, body=body, level="LITE")


def copy_revision(s: Session, source: MeasurementSet, target: MeasurementSet, actor_id: str) -> int:
    """Copy every live space measurement of ``source`` into the DRAFT ``target`` (new rows; the source is untouched).
    The copier holds every claim of the copy; property_capture travels too."""
    target.property_capture = dict(source.property_capture or {})
    n = 0
    for sm in s.execute(sa.select(SpaceMeasurement).where(SpaceMeasurement.measurement_set_id == source.id)).scalars():
        new = SpaceMeasurement(
            measurement_set_id=target.id,
            space_id=sm.space_id,
            captured_by=actor_id,
            client_ref=sm.client_ref,
            **{f: getattr(sm, f) for f in MEASUREMENT_FIELDS},
        )
        s.add(new)
        s.flush()
        for wall in s.execute(sa.select(SpaceWall).where(SpaceWall.space_measurement_id == sm.id)).scalars():
            nw = SpaceWall(space_measurement_id=new.id, wall_index=wall.wall_index,
                           **{f: getattr(wall, f) for f in WALL_FIELDS})  # fmt: skip
            s.add(nw)
            s.flush()
            for op in s.execute(sa.select(SpaceOpening).where(SpaceOpening.space_wall_id == wall.id)).scalars():
                s.add(SpaceOpening(space_wall_id=nw.id, client_ref=op.client_ref,
                                   **{f: getattr(op, f) for f in OPENING_FIELDS}))  # fmt: skip
        for hook in COPY_HOOKS:
            hook(s, sm, new)
        n += 1
    s.flush()
    return n


# --- capture -----------------------------------------------------------------------------------------------------------
def _claim_active(sm: SpaceMeasurement, now) -> bool:
    return sm.claim_expires_on is not None and sm.claim_expires_on > now


def _space_of(s: Session, mset: MeasurementSet, space_id: str) -> PropertySpace:
    sp = s.get(PropertySpace, space_id)
    if sp is None or sp.is_deleted or sp.property_id != mset.property_id:
        raise not_found()
    return sp


def _measurement(s: Session, mset: MeasurementSet, space_id: str) -> SpaceMeasurement | None:
    return s.execute(
        sa.select(SpaceMeasurement).where(
            SpaceMeasurement.measurement_set_id == mset.id, SpaceMeasurement.space_id == space_id
        )
    ).scalar_one_or_none()


def server_state(s: Session, sm: SpaceMeasurement) -> dict[str, Any]:
    return present_measurement(s, sm)


def _differences(server: dict[str, Any], payload) -> list[str]:
    mine = payload.model_dump(exclude={"base_version", "take_over", "client_ref"})
    out = [f for f in MEASUREMENT_FIELDS if f in mine and _norm(mine[f]) != _norm(server.get(f))]
    walls_mine = {w["wall_index"]: w for w in mine.get("walls", [])}
    walls_server = {w["wall_index"]: w for w in server.get("walls", [])}
    for idx in sorted(set(walls_mine) | set(walls_server)):
        a, b = walls_mine.get(idx), walls_server.get(idx)
        if a is None or b is None:
            out.append(f"walls[{idx}]")
            continue
        for f in ("length_mm", "height_mm", "wall_type_code", "is_external", "is_proposed", "usable_for_code",
                  "obstructions", "label"):  # fmt: skip
            if _norm(a.get(f)) != _norm(b.get(f)):
                out.append(f"walls[{idx}].{f}")
        mine_openings = {o["client_ref"]: _norm({k: o.get(k) for k in OPENING_FIELDS}) for o in a.get("openings", [])}
        server_openings = {o["client_ref"]: _norm({k: o.get(k) for k in OPENING_FIELDS}) for o in b.get("openings", [])}
        if mine_openings != server_openings:
            out.append(f"walls[{idx}].openings")
    return out


def _norm(value):
    if isinstance(value, dict):
        return {k: _norm(v) for k, v in sorted(value.items()) if v is not None and v != [] and v != {}}
    if isinstance(value, (list, tuple)):
        return [_norm(v) for v in value]
    return value


def upsert_space(
    s: Session, ctx, mset: MeasurementSet, prop: Property, space_id: str, payload
) -> tuple[SpaceMeasurement, bool]:
    """Write one space's measurement, walls and openings. Returns (measurement, created)."""
    require_draft(mset)
    _require_capture(s, ctx, prop)
    _space_of(s, mset, space_id)
    now = db.tx_time(s)
    sm = _measurement(s, mset, space_id)
    actor = ctx.user.id
    created = sm is None
    if sm is None:
        if payload.base_version is not None:
            raise ApiError(409, "VERSION_CONFLICT", "This space has no measurement on the server yet.",
                           extra={"current_version": None})  # fmt: skip
        sm = SpaceMeasurement(measurement_set_id=mset.id, space_id=space_id, captured_by=actor,
                              client_ref=payload.client_ref)  # fmt: skip
        s.add(sm)
    else:
        privileged = actor == mset.captured_by or ctx.scope("measurement.capture") == "ALL"
        if sm.captured_by != actor and not privileged:
            if _claim_active(sm, now):
                raise ApiError(409, "SPACE_CLAIMED", "Another surveyor is measuring this space.",
                               extra={"claimed_by": sm.captured_by,
                                      "claim_expires_on": clock.to_rfc3339(sm.claim_expires_on)})  # fmt: skip
            if not payload.take_over:
                raise ApiError(409, "CLAIM_TAKE_OVER_REQUIRED",
                               "The previous surveyor's claim has lapsed; take it over explicitly to continue.",
                               extra={"claimed_by": sm.captured_by})  # fmt: skip
            sm.captured_by = actor
        if payload.base_version is None:
            raise ApiError(428, "PRECONDITION_REQUIRED", "Send base_version: the version of this space you edited.")
        if payload.base_version != sm.version:
            current = server_state(s, sm)
            raise ApiError(409, "VERSION_CONFLICT", "This space changed after you loaded it; review and resend.",
                           extra={"current_version": sm.version, "server": current,
                                  "conflicting_fields": _differences(current, payload)})  # fmt: skip
    for f in MEASUREMENT_FIELDS:
        value = getattr(payload, f)
        if f == "attributes":
            value = value.model_dump(exclude_none=True)
        elif f == "polygon" and value is not None:
            value = [list(v) for v in value]
        setattr(sm, f, value)
    sm.claim_expires_on = now + CLAIM_TTL
    s.flush()
    _write_walls(s, sm, payload.walls)
    for hook in AFTER_SPACE_WRITE:
        hook(s, sm, payload)
    s.flush()
    return sm, created


def _write_walls(s: Session, sm: SpaceMeasurement, walls_in) -> None:
    existing = {
        w.wall_index: w
        for w in s.execute(sa.select(SpaceWall).where(SpaceWall.space_measurement_id == sm.id)).scalars()
    }
    keep: set[int] = set()
    for w in walls_in:
        keep.add(w.wall_index)
        row = existing.get(w.wall_index)
        values = {
            "label": w.label,
            "length_mm": w.length_mm,
            "height_mm": w.height_mm,
            "wall_type_code": w.wall_type_code,
            "is_external": w.is_external,
            "is_proposed": w.is_proposed,
            "usable_for_code": list(w.usable_for_code),
            "obstructions": [o.model_dump(exclude_none=True) for o in w.obstructions],
            "client_ref": w.client_ref,
        }
        if row is None:
            row = SpaceWall(space_measurement_id=sm.id, wall_index=w.wall_index, **values)
            s.add(row)
            s.flush()
        else:
            for k, v in values.items():
                if getattr(row, k) != v:
                    setattr(row, k, v)
        _write_openings(s, row, w.openings)
    for idx, row in existing.items():
        if idx not in keep:
            for op in s.execute(sa.select(SpaceOpening).where(SpaceOpening.space_wall_id == row.id)).scalars():
                op.is_deleted = True
            row.is_deleted = True


def _write_openings(s: Session, wall: SpaceWall, openings_in) -> None:
    existing = {
        o.client_ref: o
        for o in s.execute(sa.select(SpaceOpening).where(SpaceOpening.space_wall_id == wall.id)).scalars()
    }
    keep = set()
    for o in openings_in:
        keep.add(o.client_ref)
        values = {f: getattr(o, f) for f in OPENING_FIELDS}
        row = existing.get(o.client_ref)
        if row is None:
            s.add(SpaceOpening(space_wall_id=wall.id, client_ref=o.client_ref, **values))
        else:
            for k, v in values.items():
                if getattr(row, k) != v:
                    setattr(row, k, v)
    for ref, row in existing.items():
        if ref not in keep:
            row.is_deleted = True


def release_claim(s: Session, ctx, mset: MeasurementSet, prop: Property, space_id: str) -> SpaceMeasurement:
    require_draft(mset)
    _require_capture(s, ctx, prop)
    sm = _measurement(s, mset, space_id)
    if sm is None:
        raise not_found()
    if sm.captured_by != ctx.user.id and ctx.user.id != mset.captured_by and ctx.scope("measurement.capture") != "ALL":
        raise ApiError(403, "PERMISSION_DENIED", "Only the claim holder or the lead surveyor releases a claim.")
    sm.claim_expires_on = db.tx_time(s)
    return sm


def update_set(s: Session, ctx, mset: MeasurementSet, prop: Property, body) -> MeasurementSet:
    require_draft(mset)
    _require_capture(s, ctx, prop)
    provided = body.provided()
    if "property_capture" in provided and body.property_capture is not None:
        mset.property_capture = body.property_capture.model_dump(exclude_none=True)
    if "unit_system_code" in provided and body.unit_system_code:
        mset.unit_system_code = body.unit_system_code
    return mset


# --- notes -------------------------------------------------------------------------------------------------------------
def add_note(s: Session, ctx, mset: MeasurementSet, prop: Property, body) -> tuple[MeasurementNote, bool]:
    require_draft(mset)
    _require_capture(s, ctx, prop)
    if body.client_ref:
        existing = s.execute(
            sa.select(MeasurementNote).where(
                MeasurementNote.measurement_set_id == mset.id, MeasurementNote.client_ref == body.client_ref
            )
        ).scalar_one_or_none()
        if existing is not None:
            if (existing.body, existing.note_type_code, existing.space_id) != (
                body.body,
                body.note_type_code,
                body.space_id,
            ):
                raise ApiError(409, "CLIENT_REF_REUSED", "This client_ref was used for a different note.")
            return existing, False
    if body.space_id is not None:
        _space_of(s, mset, body.space_id)
    if body.note_type_code == "RISK_ACK":
        raise ApiError(422, "VALIDATION_FAILED", "Risk acknowledgements are written by the verifier at verification.")
    note = MeasurementNote(measurement_set_id=mset.id, space_id=body.space_id, note_type_code=body.note_type_code,
                           body=body.body, attachment_id=body.attachment_id, client_ref=body.client_ref)  # fmt: skip
    s.add(note)
    s.flush()
    return note, True


def delete_note(s: Session, ctx, mset: MeasurementSet, prop: Property, note: MeasurementNote) -> None:
    require_draft(mset)
    _require_capture(s, ctx, prop)
    if note.created_by != ctx.user.id and ctx.user.id != mset.captured_by and ctx.scope("measurement.capture") != "ALL":
        raise ApiError(403, "PERMISSION_DENIED", "Only the note's author or the lead surveyor deletes a note.")
    note.is_deleted = True


# --- submit, reject ----------------------------------------------------------------------------------------------------
def submit(s: Session, ctx, mset: MeasurementSet, prop: Property) -> MeasurementSet:
    from . import verification

    require_draft(mset)
    _require_capture(s, ctx, prop)
    if ctx.user.id != mset.captured_by and ctx.scope("measurement.capture") != "ALL":
        raise ApiError(403, "PERMISSION_DENIED", "The lead surveyor submits the set.")
    problems = verification.completeness(s, mset)
    if problems:
        raise ApiError(422, "MEASUREMENT_INCOMPLETE", "Some in-scope spaces are not complete yet.",
                       extra={"pointers": problems})  # fmt: skip
    now = db.tx_time(s)
    mset.status, mset.submitted_on, mset.submitted_by = "SUBMITTED", now, ctx.user.id
    for sm in s.execute(sa.select(SpaceMeasurement).where(SpaceMeasurement.measurement_set_id == mset.id)).scalars():
        sm.claim_expires_on = None  # claims end with the draft
    mset.summary = verification.summary(s, mset)
    return mset


def reject(s: Session, ctx, mset: MeasurementSet, prop: Property, reason: str) -> MeasurementSet:
    """SUBMITTED → REJECTED with the verifier's reason; the correction is a new DRAFT revision copied from it and
    handed back to the same lead surveyor (blueprint §6.2)."""
    if mset.status != "SUBMITTED":
        raise ApiError(409, "INVALID_STATE", "Only a submitted revision can be returned for correction.")
    scope.require_in_scope(s, ctx, prop.lead_id, "measurement.verify")
    if ctx.user.id == mset.captured_by:
        raise ApiError(403, "FOUR_EYES_REQUIRED", "Someone other than the surveyor reviews the set.")
    now = db.tx_time(s)
    mset.status, mset.rejected_on, mset.rejected_by, mset.rejection_reason = "REJECTED", now, ctx.user.id, reason
    s.flush()
    top = s.execute(
        sa.select(sa.func.max(MeasurementSet.revision_no))
        .where(MeasurementSet.property_id == prop.id)
        .execution_options(include_deleted=True)
    ).scalar()
    correction = MeasurementSet(
        property_id=prop.id,
        measurement_visit_id=mset.measurement_visit_id,
        revision_no=int(top or 0) + 1,
        supersedes_set_id=mset.supersedes_set_id,
        status="DRAFT",
        survey_level_code=mset.survey_level_code,
        method_code=mset.method_code,
        unit_system_code=mset.unit_system_code,
        captured_by=mset.captured_by,
        summary={},
        property_capture={},
    )
    s.add(correction)
    s.flush()
    copy_revision(s, mset, correction, mset.captured_by)
    return correction


# --- read --------------------------------------------------------------------------------------------------------------
def present_measurement(s: Session, sm: SpaceMeasurement) -> dict[str, Any]:
    walls = []
    for w in s.execute(
        sa.select(SpaceWall).where(SpaceWall.space_measurement_id == sm.id).order_by(SpaceWall.wall_index)
    ).scalars():
        openings = [
            {"id": o.id, "client_ref": o.client_ref, **{f: getattr(o, f) for f in OPENING_FIELDS}}
            for o in s.execute(
                sa.select(SpaceOpening).where(SpaceOpening.space_wall_id == w.id).order_by(SpaceOpening.client_ref)
            ).scalars()
        ]
        walls.append({"id": w.id, "wall_index": w.wall_index, **{f: getattr(w, f) for f in WALL_FIELDS},
                      "openings": openings})  # fmt: skip
    out = {
        "id": sm.id,
        "version": sm.version,
        "space_id": sm.space_id,
        "client_ref": sm.client_ref,
        **{f: getattr(sm, f) for f in MEASUREMENT_FIELDS},
        "derived_floor_area_sqft_centi": sm.derived_floor_area_sqft_centi,
        "derived_perimeter_mm": sm.derived_perimeter_mm,
        "derived_wall_area_gross_sqft_centi": sm.derived_wall_area_gross_sqft_centi,
        "derived_wall_area_net_sqft_centi": sm.derived_wall_area_net_sqft_centi,
        "captured_by": sm.captured_by,
        "claim_expires_on": clock.to_rfc3339(sm.claim_expires_on) if sm.claim_expires_on else None,
        "walls": walls,
    }
    for hook in PRESENT_HOOKS:
        hook(s, sm, out)
    return out


PRESENT_HOOKS: list = []


def present(s: Session, mset: MeasurementSet, *, full: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": mset.id,
        "version": mset.version,
        "property_id": mset.property_id,
        "measurement_visit_id": mset.measurement_visit_id,
        "revision_no": mset.revision_no,
        "supersedes_set_id": mset.supersedes_set_id,
        "status": mset.status,
        "survey_level_code": mset.survey_level_code,
        "method_code": mset.method_code,
        "unit_system_code": mset.unit_system_code,
        "captured_by": mset.captured_by,
        "submitted_on": clock.to_rfc3339(mset.submitted_on) if mset.submitted_on else None,
        "verified_on": clock.to_rfc3339(mset.verified_on) if mset.verified_on else None,
        "verified_by": mset.verified_by,
        "rejected_on": clock.to_rfc3339(mset.rejected_on) if mset.rejected_on else None,
        "rejection_reason": mset.rejection_reason,
        "summary": mset.summary or {},
        "snapshot_sha256": mset.snapshot_sha256,
        "property_capture": mset.property_capture or {},
        "created_on": clock.to_rfc3339(mset.created_on),
    }
    if full:
        out["spaces"] = [
            present_measurement(s, sm)
            for sm in s.execute(
                sa.select(SpaceMeasurement)
                .where(SpaceMeasurement.measurement_set_id == mset.id)
                .order_by(SpaceMeasurement.space_id)
            ).scalars()
        ]
        out["notes"] = [
            {
                "id": n.id,
                "version": n.version,
                "client_ref": n.client_ref,
                "space_id": n.space_id,
                "note_type_code": n.note_type_code,
                "body": n.body,
                "attachment_id": n.attachment_id,
                "created_by": n.created_by,
                "created_on": clock.to_rfc3339(n.created_on),
            }  # fmt: skip
            for n in s.execute(
                sa.select(MeasurementNote)
                .where(MeasurementNote.measurement_set_id == mset.id)
                .order_by(MeasurementNote.created_on)
            ).scalars()
        ]
    return out


DIFF_FIELDS = ("shape_code", "length_mm", "width_mm", "ceiling_height_mm", "floor_to_lintel_mm",
               "derived_floor_area_sqft_centi", "derived_perimeter_mm")  # fmt: skip


def diff(s: Session, a: MeasurementSet, b: MeasurementSet) -> dict[str, Any]:
    """Per-space deltas between two revisions of one property, keyed by the stable space id (B1-SCOPE §2.7)."""
    if a.property_id != b.property_id:
        raise ApiError(422, "VALIDATION_FAILED", "Both revisions must belong to the same property.")

    def by_space(m: MeasurementSet) -> dict[str, dict]:
        return {
            sm.space_id: present_measurement(s, sm)
            for sm in s.execute(
                sa.select(SpaceMeasurement).where(SpaceMeasurement.measurement_set_id == m.id)
            ).scalars()
        }

    left, right = by_space(a), by_space(b)
    spaces: list[dict[str, Any]] = []
    for sid in sorted(set(left) | set(right)):
        la, rb = left.get(sid), right.get(sid)
        if la is None or rb is None:
            spaces.append({"space_id": sid, "change": "ADDED" if la is None else "REMOVED"})
            continue
        fields = {f: {"from": la.get(f), "to": rb.get(f)} for f in DIFF_FIELDS if la.get(f) != rb.get(f)}
        lw = {w["wall_index"]: w["length_mm"] for w in la["walls"]}
        rw = {w["wall_index"]: w["length_mm"] for w in rb["walls"]}
        walls = {
            str(i): {"from": lw.get(i), "to": rw.get(i)} for i in sorted(set(lw) | set(rw)) if lw.get(i) != rw.get(i)
        }
        if fields or walls:
            spaces.append({"space_id": sid, "change": "CHANGED", "fields": fields, "walls": walls})
    return {"from_set_id": a.id, "to_set_id": b.id, "from_revision": a.revision_no, "to_revision": b.revision_no,
            "spaces": spaces}  # fmt: skip
