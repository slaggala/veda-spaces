"""Measurement verification (MTQ B1-T07; blueprint §6.2; B1-SCOPE §2.3; blocker closure §2.3, AR rows).

Two gates, both fail closed, both returning problems with JSON pointers:

- **Submission** (``completeness``): the survey level's capture rules hold for every in-scope space.
  - LITE: shape and principal dimensions (or vertices, or a stated area), ceiling height for indoor and semi-open
    spaces, one overview photo, the surveyor's "complete" mark (B1-SCOPE §2.3).
  - FULL: LITE plus every wall (at least four for a rectangle, six for an L, three for a polygon), flooring and
    condition, at least one tagged wall (``NONE`` counts as the "no furniture here" marker), obstructions or the
    ``NONE`` marker on every furniture wall, offsets, swings and sills on furniture walls and on walls whose door or
    window bounds one (the trimmed Full capture), one photo per furniture wall, and the space template's machine
    requirements (tags, floor-to-lintel, service attributes, obstruction kinds, wall heights).
- **Verification** (``verify_problems``): submission rules, plus geometry (openings inside their walls, polygon
  closure within 50 mm), plausibility bounds that catch unit mistakes, every attachment CLEAN, Full property-level
  capture, four-eyes, and the ±25 % built-up check that only a verifier's acknowledgement (RISK_ACK) clears.

B1-T08 adds staircase, L-shape and electrical checks through ``EXTRA_SPACE_CHECKS``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.kernel.jcs import canonical_bytes

from . import derivation, templates, tolerance
from . import vocab as V
from .models import MeasurementNote, MeasurementSet, Property, PropertySpace, SpaceMeasurement, SpaceWall

SWING_TYPES = ("DOOR", "FRENCH_WINDOW", "WINDOW")
SILL_TYPES = ("WINDOW", "FRENCH_WINDOW", "VENTILATOR", "NICHE", "AC_SLEEVE")
BOUNDING_TYPES = ("DOOR", "WINDOW", "FRENCH_WINDOW")
MIN_WALLS = {"RECTANGULAR": 4, "L_SHAPE": 6, "POLYGON": 3, "FREEFORM": 0}
FULL_PROPERTY_CAPTURE = (
    "floor_number",
    "lift_available",
    "main_door_width_mm",
    "main_door_height_mm",
    "narrowest_passage_mm",
    "db_location",
    "occupancy",
)  # fmt: skip  (02 §0 REQ items)
LITE_PROPERTY_CAPTURE = ("floor_number", "lift_available")
ACKNOWLEDGEABLE = frozenset({"BUILT_UP_DEVIATION"})
# (space, measurement dict, level, context) -> problems; B1-T08 registers staircase, L-shape and electrical checks.
EXTRA_SPACE_CHECKS: list[Callable[..., list[dict[str, Any]]]] = []


def problem(pointer: str, code: str, message: str, **extra) -> dict[str, Any]:
    return {"pointer": pointer, "code": code, "message": message, **extra}


def in_scope_spaces(s: Session, mset: MeasurementSet) -> list[PropertySpace]:
    return list(
        s.execute(
            sa.select(PropertySpace)
            .where(PropertySpace.property_id == mset.property_id, PropertySpace.is_in_scope == sa.true())
            .order_by(PropertySpace.level_index, PropertySpace.sort_order)
        ).scalars()
    )


def measurements(s: Session, mset: MeasurementSet) -> dict[str, SpaceMeasurement]:
    return {
        sm.space_id: sm
        for sm in s.execute(sa.select(SpaceMeasurement).where(SpaceMeasurement.measurement_set_id == mset.id)).scalars()
    }


def _attachments(s: Session, entity_type: str, ids: list[str]) -> dict[str, list]:
    from veda.modules.attachments.models import Attachment

    out: dict[str, list] = {}
    if not ids:
        return out
    for a in s.execute(
        sa.select(Attachment).where(
            Attachment.entity_type == entity_type,
            Attachment.entity_id.in_(ids),
            Attachment.retention_state == "ACTIVE",
            Attachment.upload_status != "REJECTED",
        )
    ).scalars():
        out.setdefault(a.entity_id, []).append(a)
    return out


def derive_measurement(s: Session, sm: SpaceMeasurement, space_type_code: str | None = None) -> None:
    """Recompute the derived columns of one space measurement (called after every write and on copy)."""
    from .sets import present_measurement

    if space_type_code is None:
        sp = s.get(PropertySpace, sm.space_id)
        space_type_code = sp.space_type_code if sp else ""
    data = present_measurement(s, sm)
    for k, v in derivation.derive(data, data["walls"], space_type_code).items():
        if getattr(sm, k) != v:
            setattr(sm, k, v)


def _space_problems(
    sp: PropertySpace, m: dict[str, Any], level: str, photos: dict[str, list], wall_photos: dict[str, list]
) -> list[dict]:
    ptr = f"/spaces/{sp.id}"
    out: list[dict] = []
    shape = m["shape_code"]
    stair = sp.space_type_code == "STAIRCASE"
    if not stair:
        if shape in ("RECTANGULAR", "L_SHAPE") and not (m.get("length_mm") and m.get("width_mm")):
            out.append(problem(ptr, "DIMENSIONS_REQUIRED", "Length and width are required.", space=sp.label))
        if sp.zone_code != "OUTDOOR" and shape != "FREEFORM" and not m.get("ceiling_height_mm"):
            out.append(problem(ptr, "CEILING_HEIGHT_REQUIRED", "Ceiling height is required.", space=sp.label))
    if not photos.get(sp.id):
        out.append(
            problem(ptr, "OVERVIEW_PHOTO_REQUIRED", "One overview photo of the space is required.", space=sp.label)
        )
    if not m.get("is_complete"):
        out.append(problem(ptr, "NOT_COMPLETE", "The surveyor has not marked this space complete.", space=sp.label))
    if level == "FULL":
        out += _full_space_problems(sp, m, wall_photos)
    return out


def _full_space_problems(sp: PropertySpace, m: dict[str, Any], wall_photos: dict[str, list]) -> list[dict]:
    ptr = f"/spaces/{sp.id}"
    out: list[dict] = []
    walls = m["walls"]
    shape = m["shape_code"]
    if len(walls) < MIN_WALLS.get(shape, 0) and sp.space_type_code != "STAIRCASE":
        out.append(problem(ptr, "WALLS_REQUIRED", f"Every wall is required ({MIN_WALLS[shape]} or more for this shape).",
                           space=sp.label))  # fmt: skip
    if sp.zone_code != "OUTDOOR" and sp.space_type_code != "STAIRCASE":
        if not m.get("flooring_code"):
            out.append(problem(ptr, "FLOORING_REQUIRED", "Existing flooring is required.", space=sp.label))
        if not m.get("existing_condition_code"):
            out.append(problem(ptr, "CONDITION_REQUIRED", "Existing condition is required.", space=sp.label))
    solid = [w for w in walls if w["wall_type_code"] != "OPEN"]
    if solid and not any(w["usable_for_code"] for w in solid):
        out.append(problem(ptr, "NO_TAGGED_WALL", "Tag at least one wall (NONE when nothing goes on any wall).",
                           space=sp.label))  # fmt: skip
    from .capture import FURNITURE_TAGS

    by_index = {w["wall_index"]: w for w in solid}
    ordered = sorted(i for i in by_index if i >= 1)
    furniture = [w for w in solid if FURNITURE_TAGS & set(w["usable_for_code"])]
    detail: dict[int, dict] = {w["wall_index"]: w for w in furniture}
    for w in furniture:  # walls whose door or window bounds a furniture wall (cyclic neighbours)
        if w["wall_index"] in ordered:
            i = ordered.index(w["wall_index"])
            for j in (ordered[i - 1], ordered[(i + 1) % len(ordered)]):
                n = by_index[j]
                if any(o["opening_type_code"] in BOUNDING_TYPES for o in n["openings"]):
                    detail.setdefault(j, n)
    for w in furniture:
        wp = f"{ptr}/walls/{w['wall_index']}"
        if not w["obstructions"]:
            out.append(problem(wp, "OBSTRUCTIONS_REQUIRED", "Capture the obstructions on this furniture wall, or mark none.",
                               space=sp.label))  # fmt: skip
        if not wall_photos.get(w["id"]):
            out.append(
                problem(wp, "WALL_PHOTO_REQUIRED", "Photograph this furniture wall with its label.", space=sp.label)
            )
    for idx, w in sorted(detail.items()):
        for o in w["openings"]:
            op = f"{ptr}/walls/{idx}/openings/{o['client_ref']}"
            if o.get("offset_from_wall_start_mm") is None:
                out.append(problem(op, "OPENING_OFFSET_REQUIRED", "Give the opening's offset from the wall's start.",
                                   space=sp.label))  # fmt: skip
            if o["opening_type_code"] in SWING_TYPES and not o.get("swing_code"):
                out.append(problem(op, "OPENING_SWING_REQUIRED", "Give the opening's swing.", space=sp.label))
            if o["opening_type_code"] in SILL_TYPES and o.get("sill_height_mm") is None:
                out.append(problem(op, "SILL_REQUIRED", "Give the sill height.", space=sp.label))
    _, tpl = templates.space_template_for(sp.space_type_code)
    attrs = m.get("attributes") or {}
    for code in tpl.full_required:
        if code.startswith("TAG:"):
            tag = code[4:]
            if not any(tag in w["usable_for_code"] for w in solid):
                out.append(problem(ptr, "TAG_REQUIRED", f"Tag the {tag.replace('_', ' ').lower()} wall.", space=sp.label,
                                   tag=tag))  # fmt: skip
        elif code == "FL":
            if not m.get("floor_to_lintel_mm"):
                out.append(
                    problem(ptr, "FLOOR_TO_LINTEL_REQUIRED", "Floor to lintel is required here.", space=sp.label)
                )
        elif code.startswith("ATTR:"):
            key = code[5:]
            if attrs.get(key) is None:
                out.append(problem(ptr, "ATTRIBUTE_REQUIRED", f"Record {key.replace('_', ' ')}.", space=sp.label,
                                   attribute=key))  # fmt: skip
        elif code.startswith("OBS_KIND:"):
            kind = code[9:]
            if not any(o.get("kind") == kind for w in furniture for o in w["obstructions"]):
                out.append(problem(ptr, "OBSTRUCTION_KIND_REQUIRED", f"Locate the {kind.replace('_', ' ').lower()}.",
                                   space=sp.label, kind=kind))  # fmt: skip
        elif code == "WALL_HEIGHTS":
            for w in solid:
                if not w.get("height_mm"):
                    out.append(problem(f"{ptr}/walls/{w['wall_index']}", "WALL_HEIGHT_REQUIRED",
                                       "Give this wall its own height.", space=sp.label))  # fmt: skip
        # "STAIRCASE" is checked by the staircase rules (B1-T08)
    return out


def _tree(s: Session, mset: MeasurementSet):
    from .sets import present_measurement

    spaces = in_scope_spaces(s, mset)
    by_space = measurements(s, mset)
    data = {sid: present_measurement(s, sm) for sid, sm in by_space.items()}
    photos = _attachments(s, "property_space", [sp.id for sp in spaces])
    wall_ids = [w["id"] for d in data.values() for w in d["walls"]]
    wall_photos = _attachments(s, "space_wall", wall_ids)
    risks = dict(
        s.execute(
            sa.select(MeasurementNote.space_id, sa.func.count(MeasurementNote.id))
            .where(MeasurementNote.measurement_set_id == mset.id, MeasurementNote.note_type_code == "RISK")
            .group_by(MeasurementNote.space_id)
        ).all()
    )
    for sid, m in data.items():
        m["_risk_notes"] = int(risks.get(sid, 0))
    return spaces, data, photos, wall_photos


def completeness(s: Session, mset: MeasurementSet) -> list[dict[str, Any]]:
    from .sets import ensure_hooks

    ensure_hooks()
    spaces, data, photos, wall_photos = _tree(s, mset)
    out: list[dict] = []
    for sp in spaces:
        m = data.get(sp.id)
        if m is None:
            out.append(
                problem(f"/spaces/{sp.id}", "NOT_MEASURED", "This in-scope space has no measurement.", space=sp.label)
            )
            continue
        out += _space_problems(sp, m, mset.survey_level_code, photos, wall_photos)
        for check in EXTRA_SPACE_CHECKS:
            out += check(sp, m, mset.survey_level_code, "submit")
    return out


def verify_problems(s: Session, mset: MeasurementSet, verifier_id: str, acknowledged: set[str]) -> list[dict]:
    from veda.modules.attachments.models import Attachment

    out = completeness(s, mset)
    spaces, data, _, _ = _tree(s, mset)
    if verifier_id == mset.captured_by or verifier_id in {m["captured_by"] for m in data.values()}:
        out.append(problem("/", "FOUR_EYES_REQUIRED", "The verifier must not have captured any space of this set."))
    lo_ch, hi_ch = tolerance.CEILING_HEIGHT_MM
    lo_d, hi_d = tolerance.ROOM_DIMENSION_MM
    lo_w, hi_w = tolerance.WALL_LENGTH_MM
    for sp in spaces:
        m = data.get(sp.id)
        if m is None:
            continue
        ptr = f"/spaces/{sp.id}"
        ch = m.get("ceiling_height_mm")
        if ch and not lo_ch <= ch <= hi_ch:
            out.append(problem(ptr, "IMPLAUSIBLE_CEILING_HEIGHT", "The ceiling height is outside 1.8–9 m: check the units.",
                               space=sp.label))  # fmt: skip
        for f in ("length_mm", "width_mm"):
            v = m.get(f)
            if v and not lo_d <= v <= hi_d:
                out.append(problem(ptr, "IMPLAUSIBLE_DIMENSION", f"The {f[:-3]} is outside 0.6–30 m: check the units.",
                                   space=sp.label))  # fmt: skip
        for w in m["walls"]:
            wp = f"{ptr}/walls/{w['wall_index']}"
            if not lo_w <= w["length_mm"] <= hi_w:
                out.append(problem(wp, "IMPLAUSIBLE_WALL_LENGTH", "The wall length is outside 0.1–30 m: check the units.",
                                   space=sp.label))  # fmt: skip
            h = derivation.wall_height(w, ch, sp.space_type_code)
            for o in w["openings"]:
                op = f"{wp}/openings/{o['client_ref']}"
                off = o.get("offset_from_wall_start_mm") or 0
                if off + o["width_mm"] > w["length_mm"] or (h is not None and o["height_mm"] > h):
                    out.append(problem(op, "OPENING_EXCEEDS_WALL", "This opening does not fit inside its wall.",
                                       space=sp.label))  # fmt: skip
        if m["shape_code"] == "POLYGON" and m.get("polygon") and m["walls"]:
            gap = abs(derivation.polygon_perimeter_mm(m["polygon"]) - sum(w["length_mm"] for w in m["walls"]))
            if gap > tolerance.CLOSURE_MM:
                out.append(problem(ptr, "POLYGON_NOT_CLOSED", f"The walls differ from the outline by {gap} mm (50 mm allowed).",
                                   space=sp.label))  # fmt: skip
        for v in (m.get("derived_floor_area_sqft_centi"), m.get("derived_wall_area_net_sqft_centi")):
            if v is not None and v < 0:
                out.append(problem(ptr, "NEGATIVE_AREA", "A derived area is negative.", space=sp.label))
        for check in EXTRA_SPACE_CHECKS:
            out += check(sp, m, mset.survey_level_code, "verify")
    from .bindings import set_conditions

    space_ids = [sp.id for sp in spaces]
    not_clean = s.execute(
        sa.select(Attachment.id, Attachment.scan_status).where(
            sa.or_(
                *set_conditions(mset.id),
                sa.and_(Attachment.entity_type == "property_space", Attachment.entity_id.in_(space_ids)),
            ),  # fmt: skip
            Attachment.retention_state == "ACTIVE",
            Attachment.upload_status != "REJECTED",
            sa.or_(Attachment.scan_status != "CLEAN", Attachment.upload_status != "RECEIVED"),
        )
    ).all()
    infected = [a for a in not_clean if a.scan_status == "INFECTED"]
    if infected:
        out.append(problem("/attachments", "ATTACHMENT_INFECTED", "An attachment failed the malware scan; remove it first.",
                           count=len(infected)))  # fmt: skip
    elif not_clean:
        out.append(problem("/attachments", "ATTACHMENTS_NOT_CLEAN", "Some photos are still uploading or being scanned.",
                           count=len(not_clean)))  # fmt: skip
    capture = mset.property_capture or {}
    for key in FULL_PROPERTY_CAPTURE if mset.survey_level_code == "FULL" else LITE_PROPERTY_CAPTURE:
        if capture.get(key) is None:
            out.append(
                problem(f"/property_capture/{key}", "PROPERTY_CAPTURE_REQUIRED", f"Record {key.replace('_', ' ')}.")
            )
    prop = s.get(Property, mset.property_id)
    stated = (prop.built_up_area_sqft_centi or prop.carpet_area_sqft_centi) if prop else None
    total = sum((data[sp.id].get("derived_floor_area_sqft_centi") or 0) for sp in spaces if sp.id in data)
    if stated and total and abs(total - stated) * 10_000 > tolerance.BUILT_UP_DEVIATION_BP * stated:
        if "BUILT_UP_DEVIATION" not in acknowledged:
            out.append(problem("/", "BUILT_UP_DEVIATION", "The measured total differs from the stated area by more than "
                               "25 %; acknowledge it with a note to verify.", measured=total, stated=stated,
                               acknowledgeable=True))  # fmt: skip
    return out


def snapshot_sha256(s: Session, mset: MeasurementSet) -> str:
    """Canonical JSON (RFC 8785) of the sealed revision: values, not versions or claims (tamper evidence)."""
    from .sets import present

    tree = present(s, mset)
    for key in ("version", "status", "verified_on", "verified_by", "snapshot_sha256", "summary", "rejected_on",
                "rejection_reason"):  # fmt: skip
        tree.pop(key, None)
    for sp in tree.get("spaces", []):
        sp.pop("version", None)
        sp.pop("claim_expires_on", None)
    for n in tree.get("notes", []):
        n.pop("version", None)
    return hashlib.sha256(canonical_bytes(tree)).hexdigest()


def verify(s: Session, ctx, mset: MeasurementSet, prop: Property, acknowledgements: list) -> MeasurementSet:
    from veda.kernel.errors import ApiError

    from . import scope

    if mset.status != "SUBMITTED":
        raise ApiError(409, "INVALID_STATE", "Only a submitted revision can be verified.")
    scope.require_in_scope(s, ctx, prop.lead_id, "measurement.verify")
    for sm in measurements(s, mset).values():
        derive_measurement(s, sm)
    s.flush()
    acked = {a.code for a in acknowledgements if a.code in ACKNOWLEDGEABLE}
    problems = verify_problems(s, mset, ctx.user.id, acked)
    if problems:
        raise ApiError(
            422, "MEASUREMENT_INCOMPLETE", "The set does not pass verification.", extra={"pointers": problems}
        )
    for a in acknowledgements:
        if a.code in acked:
            s.add(MeasurementNote(measurement_set_id=mset.id, space_id=None, note_type_code="RISK_ACK",
                                  body=f"{a.code}: {a.note}"))  # fmt: skip
    previous = s.execute(
        sa.select(MeasurementSet).where(
            MeasurementSet.property_id == mset.property_id,
            MeasurementSet.status == "VERIFIED",
            MeasurementSet.id != mset.id,
        )
    ).scalar_one_or_none()
    if previous is not None:
        previous.status = "SUPERSEDED"
        s.flush()  # one VERIFIED per property (partial unique index): the old one steps aside first
    s.flush()
    mset.summary = summary(s, mset)
    mset.snapshot_sha256 = snapshot_sha256(s, mset)
    mset.status, mset.verified_on, mset.verified_by = "VERIFIED", db.tx_time(s), ctx.user.id
    spaces = {sp.id for sp in in_scope_spaces(s, mset)}
    prop.derived_measured_floor_area_sqft_centi = sum(
        sm.derived_floor_area_sqft_centi or 0 for sid, sm in measurements(s, mset).items() if sid in spaces
    )
    return mset


def summary(s: Session, mset: MeasurementSet) -> dict[str, Any]:
    from .models import SpaceOpening

    by_space = measurements(s, mset)
    ids = [sm.id for sm in by_space.values()]
    walls = s.execute(sa.select(sa.func.count(SpaceWall.id)).where(SpaceWall.space_measurement_id.in_(ids))).scalar()
    openings = s.execute(
        sa.select(sa.func.count(SpaceOpening.id))
        .join(SpaceWall, SpaceWall.id == SpaceOpening.space_wall_id)
        .where(SpaceWall.space_measurement_id.in_(ids))
    ).scalar()
    return {
        "survey_level": mset.survey_level_code,
        "spaces": len(by_space),
        "walls": int(walls or 0),
        "openings": int(openings or 0),
        "total_floor_area_sqft_centi": sum(sm.derived_floor_area_sqft_centi or 0 for sm in by_space.values()),
        "total_wall_area_net_sqft_centi": sum(sm.derived_wall_area_net_sqft_centi or 0 for sm in by_space.values()),
        "bedrooms": sum(
            1
            for sm in by_space.values()
            if (sp := s.get(PropertySpace, sm.space_id)) is not None and sp.space_type_code in V.BEDROOM_TYPES
        ),
    }


def readiness(s: Session, mset: MeasurementSet, viewer_id: str) -> dict[str, Any]:
    """What still blocks submission and verification (dry run), and the derived usable wall segments."""
    submit = completeness(s, mset)
    verify_ = verify_problems(s, mset, viewer_id, set()) if mset.status in ("DRAFT", "SUBMITTED") else []
    _, data, _, _ = _tree(s, mset)
    segments = {
        sid: {str(w["wall_index"]): derivation.usable_segments(w) for w in m["walls"] if w["wall_type_code"] != "OPEN"}
        for sid, m in data.items()
    }
    return {
        "survey_level": mset.survey_level_code,
        "ready_to_submit": not submit,
        "ready_to_verify": mset.status == "SUBMITTED" and not [p for p in verify_ if p["code"] != "FOUR_EYES_REQUIRED"],
        "submit_problems": submit,
        "verify_problems": verify_,
        "usable_segments": segments,
    }


def _register() -> None:
    from . import sets as _sets

    def after_write(s: Session, sm: SpaceMeasurement, payload) -> None:
        s.flush()
        derive_measurement(s, sm)

    def after_copy(s: Session, source: SpaceMeasurement, copy: SpaceMeasurement) -> None:
        s.flush()
        derive_measurement(s, copy)

    if after_write.__name__ not in {h.__name__ for h in _sets.AFTER_SPACE_WRITE}:
        _sets.AFTER_SPACE_WRITE.append(after_write)
        _sets.COPY_HOOKS.append(after_copy)


_register()
