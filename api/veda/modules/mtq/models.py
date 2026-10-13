"""MTQ B1 site tables (migration 0200_mtq_site; blueprint §4.1, B1-SCOPE §2, blocker closure AR rows).

Raw measurements are integer millimetres (``*_mm``); derived areas are integer hundredths of a square foot
(``*_sqft_centi``), never floats. BHK is never a column: bedroom, toilet and level counts are derived from the space
tree. ``property_space.id`` never changes across measurement revisions (B1-SCOPE §2.7); a re-measure writes new
``space_measurement`` rows for the same space. Photos attach through ``attachment`` (ATT), not a link table.
"""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, Bool, in_check, live_where, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

from . import vocab as V


def _fk(target: str):
    return ForeignKey(target, ondelete="RESTRICT")


def _positive(table: str, *cols: str) -> list[CheckConstraint]:
    return [CheckConstraint(f"{c} IS NULL OR {c} > 0", name=f"ck_{table}__{c}_pos") for c in cols]


def _non_negative(table: str, *cols: str) -> list[CheckConstraint]:
    return [CheckConstraint(f"{c} IS NULL OR {c} >= 0", name=f"ck_{table}__{c}_nn") for c in cols]


class Property(AuditedBase):
    __tablename__ = "property"

    property_number: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_type_code: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    usage_code: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="RESIDENTIAL")
    project_kind_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    configuration_label: Mapped[str | None] = mapped_column(sa.String(40))  # as the customer says it; display only
    built_up_area_sqft_centi: Mapped[int | None] = mapped_column(sa.Integer)
    carpet_area_sqft_centi: Mapped[int | None] = mapped_column(sa.Integer)
    plot_area_sqft_centi: Mapped[int | None] = mapped_column(sa.Integer)
    floor_count: Mapped[int | None] = mapped_column(sa.Integer)
    derived_bedroom_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default="0")
    derived_toilet_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default="0")
    derived_level_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default="1")
    derived_measured_floor_area_sqft_centi: Mapped[int | None] = mapped_column(sa.Integer)
    address_line_1: Mapped[str | None] = mapped_column(sa.String(200))
    address_line_2: Mapped[str | None] = mapped_column(sa.String(200))
    locality: Mapped[str | None] = mapped_column(sa.String(100))
    city: Mapped[str | None] = mapped_column(sa.String(100))
    state: Mapped[str | None] = mapped_column(sa.String(100))
    pincode: Mapped[str | None] = mapped_column(sa.String(10))
    # Microdegrees (blueprint DECIMAL(9,6) as an exact integer: no floating point anywhere, DATA-016).
    geo_lat_e6: Mapped[int | None] = mapped_column(sa.Integer)
    geo_lng_e6: Mapped[int | None] = mapped_column(sa.Integer)
    possession_status_code: Mapped[str | None] = mapped_column(sa.String(20))
    possession_on: Mapped[date | None] = mapped_column(sa.Date)
    floor_plan_attachment_id: Mapped[str | None] = mapped_column(GUID(), _fk("attachment.id"))
    template_key: Mapped[str | None] = mapped_column(sa.String(40))  # property template that seeded the tree
    template_version: Mapped[str | None] = mapped_column(sa.String(20))
    notes: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        in_check("property", "property_type_code", V.PROPERTY_TYPES),
        in_check("property", "usage_code", V.USAGES),
        in_check("property", "project_kind_code", V.PROJECT_KINDS),
        in_check("property", "possession_status_code", V.POSSESSION_STATUSES, nullable=True),
        *_non_negative(
            "property",
            "built_up_area_sqft_centi",
            "carpet_area_sqft_centi",
            "plot_area_sqft_centi",
            "derived_bedroom_count",
            "derived_toilet_count",
            "derived_measured_floor_area_sqft_centi",
        ),
        *_positive("property", "floor_count", "derived_level_count"),
        CheckConstraint("geo_lat_e6 IS NULL OR geo_lat_e6 BETWEEN -90000000 AND 90000000", name="ck_property__lat"),
        CheckConstraint("geo_lng_e6 IS NULL OR geo_lng_e6 BETWEEN -180000000 AND 180000000", name="ck_property__lng"),
        CheckConstraint("(geo_lat_e6 IS NULL) = (geo_lng_e6 IS NULL)", name="ck_property__geo_pair"),
        Index("ux_property__property_number", "property_number", unique=True, **live_where()),
        Index("ix_property__lead_id", "lead_id"),
        Index("ix_property__city", "city"),
    )


class PropertySpace(AuditedBase):
    __tablename__ = "property_space"

    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    parent_space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    space_type_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    custom_type_label: Mapped[str | None] = mapped_column(sa.String(60))
    label: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    instance_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default="1")
    level_index: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default="0")
    zone_code: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="INDOOR")
    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    is_in_scope: Mapped[bool] = mapped_column(Bool(), nullable=False, default=True, server_default=sa.true())
    space_template_key: Mapped[str | None] = mapped_column(sa.String(80))
    template_version: Mapped[str | None] = mapped_column(sa.String(20))  # B1+: the code-fixture version (B1-06)
    attributes: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)

    __table_args__ = (
        in_check("property_space", "space_type_code", V.SPACE_TYPES),
        in_check("property_space", "zone_code", V.ZONES),
        CheckConstraint(
            "space_type_code <> 'CUSTOM' OR custom_type_label IS NOT NULL", name="ck_property_space__custom_label"
        ),
        CheckConstraint("instance_no >= 1", name="ck_property_space__instance_no"),
        CheckConstraint("level_index BETWEEN -3 AND 10", name="ck_property_space__level_index"),
        CheckConstraint("parent_space_id IS NULL OR parent_space_id <> id", name="ck_property_space__not_own_parent"),
        Index(
            "ux_property_space__property_type_instance",
            "property_id",
            "space_type_code",
            "instance_no",
            unique=True,
            **live_where(),
        ),
        Index("ix_property_space__property_order", "property_id", "level_index", "sort_order"),
        Index("ix_property_space__parent_space_id", "parent_space_id"),
    )


class MeasurementVisit(AuditedBase):
    __tablename__ = "measurement_visit"

    visit_number: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    visit_type_code: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="INITIAL")
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="REQUESTED")
    survey_level_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)  # B1+: planned level
    status_changed_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    scheduled_start_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    scheduled_end_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    started_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    assigned_to: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    lead_activity_id: Mapped[str | None] = mapped_column(GUID(), _fk("lead_activity.id"))
    customer_contact_name: Mapped[str | None] = mapped_column(sa.String(150))
    customer_contact_phone: Mapped[str | None] = mapped_column(sa.String(16))
    access_notes: Mapped[str | None] = mapped_column(sa.Text)
    cancel_reason: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        in_check("measurement_visit", "visit_type_code", V.VISIT_TYPES),
        in_check("measurement_visit", "status", V.VISIT_STATUSES),
        in_check("measurement_visit", "survey_level_code", V.SURVEY_LEVELS),
        CheckConstraint(
            "scheduled_end_on IS NULL OR scheduled_start_on IS NULL OR scheduled_end_on > scheduled_start_on",
            name="ck_measurement_visit__schedule_order",
        ),
        CheckConstraint(
            "status NOT IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED') OR scheduled_start_on IS NOT NULL",
            name="ck_measurement_visit__scheduled_has_start",
        ),
        CheckConstraint(
            "status <> 'CANCELLED' OR cancel_reason IS NOT NULL", name="ck_measurement_visit__cancel_reason"
        ),
        Index("ux_measurement_visit__visit_number", "visit_number", unique=True, **live_where()),
        Index("ix_measurement_visit__property_id", "property_id"),
        Index("ix_measurement_visit__lead_id", "lead_id"),
        Index("ix_measurement_visit__assigned_status", "assigned_to", "status"),
    )


class MeasurementSet(AuditedBase):
    __tablename__ = "measurement_set"

    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    measurement_visit_id: Mapped[str | None] = mapped_column(GUID(), _fk("measurement_visit.id"))
    revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    supersedes_set_id: Mapped[str | None] = mapped_column(GUID(), _fk("measurement_set.id"))
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="DRAFT")
    survey_level_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)  # B1+: actual level
    method_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    unit_system_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)  # default entry unit (AR-16)
    captured_by: Mapped[str] = mapped_column(GUID(), _fk("app_user.id"), nullable=False)  # the lead surveyor
    submitted_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    submitted_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    verified_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    verified_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    rejected_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    rejected_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    rejection_reason: Mapped[str | None] = mapped_column(sa.Text)
    summary: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    snapshot_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    device_info: Mapped[dict | None] = mapped_column(JSONType())
    property_capture: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)  # B1+

    __table_args__ = (
        in_check("measurement_set", "status", V.SET_STATUSES),
        in_check("measurement_set", "survey_level_code", V.SURVEY_LEVELS),
        in_check("measurement_set", "method_code", V.MEASUREMENT_METHODS),
        in_check("measurement_set", "unit_system_code", V.UNIT_SYSTEMS),
        CheckConstraint("revision_no >= 1", name="ck_measurement_set__revision_no"),
        CheckConstraint(
            "snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64", name="ck_measurement_set__snapshot_len"
        ),
        CheckConstraint(
            "status NOT IN ('SUBMITTED', 'VERIFIED', 'SUPERSEDED', 'REJECTED') OR submitted_on IS NOT NULL",
            name="ck_measurement_set__submitted_on",
        ),
        CheckConstraint(
            "status <> 'VERIFIED' OR (verified_on IS NOT NULL AND verified_by IS NOT NULL AND snapshot_sha256 IS NOT NULL)",
            name="ck_measurement_set__verified_sealed",
        ),
        CheckConstraint(
            "status <> 'REJECTED' OR (rejected_on IS NOT NULL AND rejection_reason IS NOT NULL)",
            name="ck_measurement_set__rejected_reason",
        ),
        CheckConstraint(
            "supersedes_set_id IS NULL OR supersedes_set_id <> id", name="ck_measurement_set__not_self_superseding"
        ),
        Index("ux_measurement_set__property_revision", "property_id", "revision_no", unique=True, **live_where()),
        Index(
            "ux_measurement_set__one_verified",
            "property_id",
            unique=True,
            **where("status = 'VERIFIED' AND is_deleted = 0", "status = 'VERIFIED' AND is_deleted = false"),
        ),
        Index(
            "ux_measurement_set__one_draft",
            "property_id",
            unique=True,
            **where("status = 'DRAFT' AND is_deleted = 0", "status = 'DRAFT' AND is_deleted = false"),
        ),
        Index("ix_measurement_set__visit", "measurement_visit_id"),
        Index("ix_measurement_set__supersedes_set_id", "supersedes_set_id"),
    )


class SpaceMeasurement(AuditedBase):
    __tablename__ = "space_measurement"

    measurement_set_id: Mapped[str] = mapped_column(GUID(), _fk("measurement_set.id"), nullable=False)
    space_id: Mapped[str] = mapped_column(GUID(), _fk("property_space.id"), nullable=False)
    shape_code: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="RECTANGULAR")
    length_mm: Mapped[int | None] = mapped_column(sa.Integer)
    width_mm: Mapped[int | None] = mapped_column(sa.Integer)
    ceiling_height_mm: Mapped[int | None] = mapped_column(sa.Integer)
    beam_bottom_height_mm: Mapped[int | None] = mapped_column(sa.Integer)
    floor_to_lintel_mm: Mapped[int | None] = mapped_column(sa.Integer)
    stated_floor_area_sqft_centi: Mapped[int | None] = mapped_column(sa.Integer)
    derived_floor_area_sqft_centi: Mapped[int | None] = mapped_column(sa.Integer)
    derived_perimeter_mm: Mapped[int | None] = mapped_column(sa.Integer)
    derived_wall_area_gross_sqft_centi: Mapped[int | None] = mapped_column(sa.Integer)
    derived_wall_area_net_sqft_centi: Mapped[int | None] = mapped_column(sa.Integer)
    polygon: Mapped[list | None] = mapped_column(JSONType())  # ordered [x_mm, y_mm] vertices for POLYGON
    flooring_code: Mapped[str | None] = mapped_column(sa.String(30))
    existing_condition_code: Mapped[str | None] = mapped_column(sa.String(30))
    is_complete: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    confidence_code: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="HIGH", server_default="HIGH")
    attributes: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)  # B1+, closed per space type
    captured_by: Mapped[str] = mapped_column(GUID(), _fk("app_user.id"), nullable=False)  # B1+: the claim holder
    claim_expires_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    client_ref: Mapped[str | None] = mapped_column(sa.String(64))

    __table_args__ = (
        in_check("space_measurement", "shape_code", V.SHAPES),
        in_check("space_measurement", "confidence_code", V.CONFIDENCES),
        in_check("space_measurement", "flooring_code", V.FLOORINGS, nullable=True),
        in_check("space_measurement", "existing_condition_code", V.EXISTING_CONDITIONS, nullable=True),
        *_positive(
            "space_measurement",
            "length_mm",
            "width_mm",
            "ceiling_height_mm",
            "beam_bottom_height_mm",
            "floor_to_lintel_mm",
            "stated_floor_area_sqft_centi",
        ),
        *_non_negative(
            "space_measurement",
            "derived_floor_area_sqft_centi",
            "derived_perimeter_mm",
            "derived_wall_area_gross_sqft_centi",
            "derived_wall_area_net_sqft_centi",
        ),
        CheckConstraint(
            "shape_code <> 'FREEFORM' OR stated_floor_area_sqft_centi IS NOT NULL",
            name="ck_space_measurement__freeform_area",
        ),
        Index("ux_space_measurement__set_space", "measurement_set_id", "space_id", unique=True, **live_where()),
        Index("ix_space_measurement__space_id", "space_id"),
        Index(
            "ux_space_measurement__client_ref",
            "measurement_set_id",
            "client_ref",
            unique=True,
            **where("client_ref IS NOT NULL AND is_deleted = 0", "client_ref IS NOT NULL AND is_deleted = false"),
        ),
    )


class SpaceWall(AuditedBase):
    __tablename__ = "space_wall"

    space_measurement_id: Mapped[str] = mapped_column(GUID(), _fk("space_measurement.id"), nullable=False)
    wall_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # 0 = an OPEN entry edge; W1 = 1, clockwise
    label: Mapped[str | None] = mapped_column(sa.String(40))
    length_mm: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    height_mm: Mapped[int | None] = mapped_column(sa.Integer)
    wall_type_code: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="MASONRY")
    is_external: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    is_proposed: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())  # AR-02
    usable_for_code: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)  # WALL_TAG values
    obstructions: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)  # closed schema, bounded
    client_ref: Mapped[str | None] = mapped_column(sa.String(64))

    __table_args__ = (
        in_check("space_wall", "wall_type_code", V.WALL_TYPES),
        CheckConstraint("wall_index BETWEEN 0 AND 64", name="ck_space_wall__wall_index"),
        CheckConstraint("length_mm > 0", name="ck_space_wall__length_positive"),
        *_positive("space_wall", "height_mm"),
        CheckConstraint(
            "is_proposed = false OR wall_type_code = 'PARTITION'", name="ck_space_wall__proposed_partition"
        ),
        Index("ux_space_wall__measurement_index", "space_measurement_id", "wall_index", unique=True, **live_where()),
    )


class SpaceOpening(AuditedBase):
    __tablename__ = "space_opening"

    space_wall_id: Mapped[str] = mapped_column(GUID(), _fk("space_wall.id"), nullable=False)
    opening_type_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    width_mm: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    height_mm: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    sill_height_mm: Mapped[int | None] = mapped_column(sa.Integer)
    offset_from_wall_start_mm: Mapped[int | None] = mapped_column(sa.Integer)
    swing_code: Mapped[str | None] = mapped_column(sa.String(10))
    deducts_from_wall_area: Mapped[bool] = mapped_column(Bool(), nullable=False, default=True, server_default=sa.true())
    purpose_code: Mapped[str | None] = mapped_column(sa.String(20))  # B1+: NICHE purpose
    depth_mm: Mapped[int | None] = mapped_column(sa.Integer)  # B1+: niche and recess depth (REQ for NICHE)
    is_existing: Mapped[bool] = mapped_column(Bool(), nullable=False, default=True, server_default=sa.true())
    client_ref: Mapped[str | None] = mapped_column(sa.String(64))

    __table_args__ = (
        in_check("space_opening", "opening_type_code", V.OPENING_TYPES),
        in_check("space_opening", "swing_code", V.SWINGS, nullable=True),
        in_check("space_opening", "purpose_code", V.NICHE_PURPOSES, nullable=True),
        CheckConstraint("width_mm > 0 AND height_mm > 0", name="ck_space_opening__size_positive"),
        *_non_negative("space_opening", "sill_height_mm", "offset_from_wall_start_mm"),
        *_positive("space_opening", "depth_mm"),
        CheckConstraint("opening_type_code <> 'NICHE' OR depth_mm IS NOT NULL", name="ck_space_opening__niche_depth"),
        CheckConstraint(
            "purpose_code IS NULL OR opening_type_code = 'NICHE'", name="ck_space_opening__purpose_niche_only"
        ),
        Index("ix_space_opening__space_wall_id", "space_wall_id"),
    )


class SpaceElectricalPoint(AuditedBase):
    __tablename__ = "space_electrical_point"

    space_measurement_id: Mapped[str] = mapped_column(GUID(), _fk("space_measurement.id"), nullable=False)
    space_wall_id: Mapped[str | None] = mapped_column(GUID(), _fk("space_wall.id"))  # NULL for ceiling points
    point_type_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    status_code: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="EXISTING")
    from_offset_mm: Mapped[int | None] = mapped_column(sa.Integer)
    from_height_mm: Mapped[int | None] = mapped_column(sa.Integer)
    to_wall_id: Mapped[str | None] = mapped_column(GUID(), _fk("space_wall.id"))
    to_offset_mm: Mapped[int | None] = mapped_column(sa.Integer)
    to_height_mm: Mapped[int | None] = mapped_column(sa.Integer)
    sensor_type_code: Mapped[str | None] = mapped_column(sa.String(10))
    switching_code: Mapped[str | None] = mapped_column(sa.String(10))
    location_code: Mapped[str | None] = mapped_column(sa.String(20))
    quantity: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default="1")
    reason_code: Mapped[str | None] = mapped_column(sa.String(20))
    notes: Mapped[str | None] = mapped_column(sa.Text)
    attachment_id: Mapped[str | None] = mapped_column(GUID(), _fk("attachment.id"))
    client_ref: Mapped[str | None] = mapped_column(sa.String(64))

    __table_args__ = (
        in_check("space_electrical_point", "point_type_code", V.ELECTRICAL_POINT_TYPES),
        in_check("space_electrical_point", "status_code", V.ELECTRICAL_STATUSES),
        in_check("space_electrical_point", "sensor_type_code", V.SENSOR_TYPES, nullable=True),
        in_check("space_electrical_point", "switching_code", V.SWITCHINGS, nullable=True),
        in_check("space_electrical_point", "location_code", V.ELECTRICAL_LOCATIONS, nullable=True),
        in_check("space_electrical_point", "reason_code", V.ELECTRICAL_REASONS, nullable=True),
        CheckConstraint("quantity BETWEEN 1 AND 99", name="ck_space_electrical_point__quantity"),
        *_non_negative("space_electrical_point", "from_offset_mm", "from_height_mm", "to_offset_mm", "to_height_mm"),
        CheckConstraint(
            "point_type_code <> 'SENSOR_LIGHT' OR sensor_type_code IS NOT NULL",
            name="ck_space_electrical_point__sensor_type",
        ),
        CheckConstraint(
            "status_code <> 'SHIFT' OR (from_offset_mm IS NOT NULL AND to_offset_mm IS NOT NULL)",
            name="ck_space_electrical_point__shift_positions",
        ),
        CheckConstraint(
            "status_code <> 'NEW' OR to_offset_mm IS NOT NULL", name="ck_space_electrical_point__new_position"
        ),
        Index("ix_space_electrical_point__space_measurement_id", "space_measurement_id"),
        Index("ix_space_electrical_point__space_wall_id", "space_wall_id"),
        Index("ix_space_electrical_point__to_wall_id", "to_wall_id"),
    )


class MeasurementNote(AuditedBase):
    __tablename__ = "measurement_note"

    measurement_set_id: Mapped[str] = mapped_column(GUID(), _fk("measurement_set.id"), nullable=False)
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))  # NULL: property-level
    note_type_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    attachment_id: Mapped[str | None] = mapped_column(GUID(), _fk("attachment.id"))
    client_ref: Mapped[str | None] = mapped_column(sa.String(64))

    __table_args__ = (
        in_check("measurement_note", "note_type_code", V.NOTE_TYPES),
        Index("ix_measurement_note__set_space", "measurement_set_id", "space_id"),
        Index("ix_measurement_note__space_id", "space_id"),
        Index(
            "ux_measurement_note__client_ref",
            "measurement_set_id",
            "client_ref",
            unique=True,
            **where("client_ref IS NOT NULL AND is_deleted = 0", "client_ref IS NOT NULL AND is_deleted = false"),
        ),
    )


TABLES = (
    "property",
    "property_space",
    "measurement_visit",
    "measurement_set",
    "space_measurement",
    "space_wall",
    "space_opening",
    "space_electrical_point",
    "measurement_note",
)
