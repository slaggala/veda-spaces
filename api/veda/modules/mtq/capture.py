"""Capture payloads (MTQ B1-T06): what a surveyor's client sends for one space, closed and bounded.

One ``SpaceCaptureIn`` carries a space's measurement with its walls and their openings and obstructions. Every list is
bounded, every number is a positive integer of millimetres within site-plausible limits, every code comes from the
frozen vocabularies, and unknown keys are refused, so no JSON column ever receives free-form content. Electrical
points, staircase geometry and L-shape legs are added by B1-T08.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from veda.kernel.dto import Closed, Id, optional_text

from .schemas import HEIGHT, MM, OFFSET, ClientRef

Shape = Literal["RECTANGULAR", "L_SHAPE", "POLYGON", "FREEFORM"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
WallType = Literal["MASONRY", "RCC", "PARTITION", "GLASS", "OPEN"]
WallTag = Literal[
    "WARDROBE",
    "LOFT",
    "BED_HEAD",
    "TV_UNIT",
    "STUDY_UNIT",
    "CROCKERY_UNIT",
    "KITCHEN_RUN",
    "KITCHEN_WALL_RUN",
    "TALL_UNIT",
    "VANITY",
    "SHOE_RACK",
    "POOJA_UNIT",
    "FEATURE_WALL",
    "WINDOW_SEATING",
    "STORAGE_WALL",
    "PARTITION_EDGE",
    "NONE",
]  # fmt: skip  (equal to vocab.WALL_TAGS; tested)
ObstructionKind = Literal[
    "SWITCHBOARD",
    "AC_INDOOR",
    "AC_PIPE",
    "AC_DRAIN",
    "COLUMN",
    "BEAM_DROP",
    "PIPE",
    "GAS_LINE",
    "WINDOW_GRILL",
    "DB_BOX",
    "GEYSER",
    "ARCHITRAVE",
    "OTHER",
    "NONE",
]  # fmt: skip  (equal to vocab.OBSTRUCTION_KINDS; tested)
OpeningType = Literal[
    "DOOR", "WINDOW", "FRENCH_WINDOW", "ARCH", "NICHE", "VENTILATOR", "AC_SLEEVE", "SHAFT", "DUCT", "CUSTOM"
]
Swing = Literal["IN", "OUT", "SLIDING", "NONE"]
NichePurpose = Literal["FRIDGE", "APPLIANCE", "STORAGE", "WASH", "OTHER"]
Flooring = Literal["VITRIFIED", "MARBLE", "GRANITE", "WOOD", "CEMENT", "TILE_CERAMIC", "NONE_BARE"]
Condition = Literal["BARE_SHELL", "FINISHED_NEW", "OCCUPIED_GOOD", "OCCUPIED_WORN", "DAMP", "CRACKED"]
FURNITURE_TAGS = frozenset(
    {
        "WARDROBE",
        "LOFT",
        "BED_HEAD",
        "TV_UNIT",
        "STUDY_UNIT",
        "CROCKERY_UNIT",
        "KITCHEN_RUN",
        "KITCHEN_WALL_RUN",
        "TALL_UNIT",
        "VANITY",
        "SHOE_RACK",
        "POOJA_UNIT",
        "FEATURE_WALL",
        "WINDOW_SEATING",
        "STORAGE_WALL",
    }
)  # fmt: skip  (every tag except PARTITION_EDGE and NONE carries furniture or a treatment)


class Obstruction(Closed):
    kind: ObstructionKind
    offset_mm: OFFSET | None = None  # along the wall from its start corner
    width_mm: MM | None = None
    height_from_floor_mm: Annotated[int, Field(ge=0, le=20_000)] | None = None
    height_mm: HEIGHT | None = None

    @model_validator(mode="after")
    def _positioned(self):
        if self.kind != "NONE" and self.offset_mm is None:
            raise ValueError("an obstruction needs its offset from the wall's start corner")
        return self


class OpeningIn(Closed):
    client_ref: ClientRef
    opening_type_code: OpeningType
    width_mm: MM
    height_mm: HEIGHT
    sill_height_mm: Annotated[int, Field(ge=0, le=20_000)] | None = None
    offset_from_wall_start_mm: OFFSET | None = None
    swing_code: Swing | None = None
    deducts_from_wall_area: bool = True
    purpose_code: NichePurpose | None = None
    depth_mm: MM | None = None
    is_existing: bool = True

    @model_validator(mode="after")
    def _niche(self):
        if self.opening_type_code == "NICHE" and self.depth_mm is None:
            raise ValueError("a niche needs its depth (B1-SCOPE §2.9.5)")
        if self.purpose_code is not None and self.opening_type_code != "NICHE":
            raise ValueError("only a niche has a purpose")
        return self


class WallIn(Closed):
    wall_index: Annotated[int, Field(ge=0, le=64)]  # 0 = an OPEN entry edge; W1 = 1, clockwise
    client_ref: ClientRef | None = None
    label: Annotated[str | None, optional_text(40)] = None
    length_mm: MM
    height_mm: HEIGHT | None = None
    wall_type_code: WallType = "MASONRY"
    is_external: bool = False
    is_proposed: bool = False
    usable_for_code: Annotated[list[WallTag], Field(max_length=8)] = []
    obstructions: Annotated[list[Obstruction], Field(max_length=20)] = []
    openings: Annotated[list[OpeningIn], Field(max_length=12)] = []

    @model_validator(mode="after")
    def _rules(self):
        if len(set(self.usable_for_code)) != len(self.usable_for_code):
            raise ValueError("a tag appears twice")
        if "NONE" in self.usable_for_code and len(self.usable_for_code) > 1:
            raise ValueError("NONE stands alone")
        kinds = [o.kind for o in self.obstructions]
        if "NONE" in kinds and len(kinds) > 1:
            raise ValueError("the NONE obstruction marker stands alone")
        if self.is_proposed and self.wall_type_code != "PARTITION":
            raise ValueError("only a partition can be proposed")
        if self.wall_type_code == "OPEN" and (self.openings or self.obstructions or self.usable_for_code):
            raise ValueError("an open edge has no openings, obstructions or tags")
        refs = [o.client_ref for o in self.openings]
        if len(set(refs)) != len(refs):
            raise ValueError("opening client_ref values repeat")
        return self


class MeasurementAttributes(Closed):
    """space_measurement.attributes: survey readings per space (closed; B1-T08 adds staircase and L-shape)."""

    ac_type: Literal["SPLIT", "WINDOW", "CASSETTE", "DUCTED", "NONE"] | None = None
    ac_point_count: Annotated[int, Field(ge=0, le=20)] | None = None
    fan_point_count: Annotated[int, Field(ge=0, le=20)] | None = None
    has_gas_line: bool | None = None
    has_water_inlet: bool | None = None
    has_drain: bool | None = None
    counter_existing: bool | None = None
    has_loft_existing: bool | None = None
    has_false_ceiling_existing: bool | None = None
    ceiling_slab_type: Literal["FLAT", "SLOPED", "BEAM_GRID"] | None = None
    dado_height_mm: HEIGHT | None = None
    railing_height_mm: HEIGHT | None = None
    exposure_code: Literal["OPEN", "COVERED", "ENCLOSED"] | None = None


class SpaceCaptureIn(Closed):
    client_ref: ClientRef | None = None
    base_version: Annotated[int, Field(ge=1)] | None = None  # the version the client edited; absent = first write
    take_over: bool = False  # take an expired or released claim explicitly
    shape_code: Shape = "RECTANGULAR"
    length_mm: MM | None = None
    width_mm: MM | None = None
    ceiling_height_mm: HEIGHT | None = None
    beam_bottom_height_mm: HEIGHT | None = None
    floor_to_lintel_mm: HEIGHT | None = None
    stated_floor_area_sqft_centi: Annotated[int, Field(ge=1, le=100_000_00)] | None = None
    polygon: Annotated[list[tuple[OFFSET, OFFSET]], Field(min_length=3, max_length=64)] | None = None
    flooring_code: Flooring | None = None
    existing_condition_code: Condition | None = None
    confidence_code: Confidence = "HIGH"
    is_complete: bool = False
    attributes: MeasurementAttributes = MeasurementAttributes()
    walls: Annotated[list[WallIn], Field(max_length=64)] = []

    @model_validator(mode="after")
    def _rules(self):
        idx = [w.wall_index for w in self.walls]
        if len(set(idx)) != len(idx):
            raise ValueError("wall_index values repeat")
        refs = [o.client_ref for w in self.walls for o in w.openings]
        if len(set(refs)) != len(refs):
            raise ValueError("opening client_ref values repeat across walls")
        if self.shape_code == "FREEFORM":
            if self.stated_floor_area_sqft_centi is None:
                raise ValueError("a freeform space needs its stated area")
            if self.confidence_code != "LOW":
                raise ValueError("a freeform space has LOW confidence (00 §2 SA)")
        if self.shape_code == "POLYGON" and self.polygon is None:
            raise ValueError("a polygon space needs its vertices")
        if self.shape_code != "POLYGON" and self.polygon is not None:
            raise ValueError("vertices belong to polygon spaces only")
        return self


class MeasurementNoteIn(Closed):
    client_ref: ClientRef | None = None
    space_id: Id | None = None
    note_type_code: Literal["OBSERVATION", "RISK", "CUSTOMER_REQUEST", "VOICE_TRANSCRIPT", "RISK_ACK"]
    body: Annotated[str, Field(min_length=1, max_length=4000)]
    attachment_id: Id | None = None


class PropertyCaptureIn(Closed):
    """measurement_set.property_capture (PR #84 02 §0; Lite subset per B1-SCOPE §2.3). Free-text keys are erased
    with the lead (mtq/erasure.py CAPTURE_TEXT_KEYS)."""

    floor_number: Annotated[int, Field(ge=-3, le=150)] | None = None
    lift_available: bool | None = None
    lift_door_width_mm: MM | None = None
    lift_depth_mm: MM | None = None
    staircase_width_mm: MM | None = None
    main_door_width_mm: MM | None = None
    main_door_height_mm: HEIGHT | None = None
    narrowest_passage_mm: MM | None = None
    db_location: Annotated[str | None, optional_text(120)] = None
    electrical_phase: Literal["SINGLE", "THREE", "UNKNOWN"] | None = None
    occupancy: Literal["VACANT", "OCCUPIED"] | None = None
    working_hours_notes: Annotated[str | None, optional_text(500)] = None
    parking_notes: Annotated[str | None, optional_text(500)] = None
    access_notes: Annotated[str | None, optional_text(1000)] = None


class DeviceInfo(Closed):
    app_version: Annotated[str | None, Field(max_length=40, pattern=r"^[0-9A-Za-z._+-]*$")] = None
    platform: Annotated[str | None, Field(max_length=40, pattern=r"^[0-9A-Za-z ._/-]*$")] = None
    offline_capable: bool | None = None


class SetCreateIn(Closed):
    survey_level_code: Literal["LITE", "FULL"] | None = None  # default: the visit's planned level
    method_code: Literal["TAPE", "LASER", "PLAN_DRAWING", "LIDAR_SCAN"] = "LASER"
    unit_system_code: Literal["FT_IN", "MM"] = "FT_IN"
    copy_from_set_id: Id | None = None  # start a correction or re-measure from an earlier revision
    device_info: DeviceInfo | None = None


class PlanSetCreateIn(SetCreateIn):
    method_code: Literal["PLAN_DRAWING"] = "PLAN_DRAWING"
    survey_level_code: Literal["LITE"] = "LITE"


class SetPatchIn(Closed):
    property_capture: PropertyCaptureIn | None = None
    unit_system_code: Literal["FT_IN", "MM"] | None = None


class RejectIn(Closed):
    reason: Annotated[str, Field(min_length=1, max_length=2000)]
