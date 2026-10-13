"""0200_mtq_site: the MTQ B1 site tables, lookups, sequences, roles and permissions (MTQ B1-SCOPE §2, §4; blocker
closure §4; decision log 26).

Nine new tables (no change to any existing table): property, property_space, measurement_visit, measurement_set,
space_measurement, space_wall, space_opening, space_electrical_point, measurement_note. Photos attach through the
0106 attachment table (polymorphic), so there is no MTQ link table. Lookups SPACE_TYPE (residential B1 subset),
OPENING_TYPE, MEASUREMENT_METHOD, ELECTRICAL_POINT_TYPE, SENSOR_TYPE, WALL_TAG (frozen), FLOORING and
EXISTING_CONDITION; sequences PROPERTY and MEASUREMENT; roles DESIGNER and SURVEYOR; permission registry sync and
grants (property.*, measurement.*, and attachment.* for the two new roles). PROPERTY_TYPE gains no value in B1: the
property types it would add (duplex, villa variants, commercial) are deferred, so the lead form is unchanged.

Expand-only (02 §12.4): the N-1 image never touches these tables. Every MTQ route answers 404 while
VEDA_MTQ_SITE_ENABLED is off (the default; production refuses it), so the tables are inert until then.
0201_mtq_estimation, 0202_mtq_commercial and 0203_mtq_knowledge stay reserved and untouched (closure §4).

Revision ID: 0200_mtq_site
Revises: 0106_attachment
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0200_mtq_site"
down_revision = "0106_attachment"
branch_labels = None
depends_on = None

ROLES = ("DESIGNER", "SURVEYOR")
CODES = (
    "property.read",
    "property.create",
    "property.update",
    "measurement.visit.read",
    "measurement.visit.create",
    "measurement.visit.schedule",
    "measurement.capture",
    "measurement.read",
    "measurement.verify",
    "attachment.read",
    "attachment.create",
    "attachment.delete",
)
SEQUENCES = (("PROPERTY", "VS-P-"), ("MEASUREMENT", "VS-M-"))

# Frozen seed (B1-SCOPE §2.1, §2.6; closure §3.1 and AR rows), copied from veda.modules.mtq.vocab when this revision
# was written; a test keeps them equal. Values are only ever added by later migrations, never edited.
LOOKUPS = (
    (
        "SPACE_TYPE",
        "Space type",
        "Residential space types of the B1 property model (MTQ)",
        (
            ("LIVING", "Living room", {"category": "LIVING"}),
            ("DINING", "Dining", {"category": "LIVING"}),
            ("LIVING_DINING", "Living and dining", {"category": "LIVING"}),
            ("FAMILY_LOUNGE", "Family lounge", {"category": "LIVING"}),
            ("FOYER", "Foyer", {"category": "LIVING"}),
            ("PASSAGE", "Passage", {"category": "LIVING"}),
            ("STAIRCASE", "Staircase", {"category": "LIVING"}),
            ("POOJA", "Pooja room", {"category": "LIVING"}),
            ("MASTER_BEDROOM", "Master bedroom", {"category": "SLEEPING", "counts_as_bedroom": True}),
            ("BEDROOM", "Bedroom", {"category": "SLEEPING", "counts_as_bedroom": True}),
            ("CHILDREN_BEDROOM", "Children's bedroom", {"category": "SLEEPING", "counts_as_bedroom": True}),
            ("GUEST_BEDROOM", "Guest bedroom", {"category": "SLEEPING", "counts_as_bedroom": True}),
            ("PARENTS_BEDROOM", "Parents' bedroom", {"category": "SLEEPING", "counts_as_bedroom": True}),
            ("SERVANT_ROOM", "Servant room", {"category": "SLEEPING", "counts_as_bedroom": False}),
            ("DRESSING", "Dressing", {"category": "ATTACHED"}),
            ("WALK_IN_CLOSET", "Walk-in closet", {"category": "ATTACHED"}),
            ("TOILET", "Toilet", {"category": "ATTACHED", "counts_as_toilet": True, "wet_area": True}),
            ("POWDER_ROOM", "Powder room", {"category": "ATTACHED", "wet_area": True}),
            ("STUDY", "Study", {"category": "WORK"}),
            ("HOME_OFFICE", "Home office", {"category": "WORK"}),
            ("MEDIA_ROOM", "Media room", {"category": "LIVING"}),
            ("KITCHEN", "Kitchen", {"category": "SERVICE", "wet_area": True}),
            ("UTILITY", "Utility", {"category": "SERVICE", "wet_area": True}),
            ("STORE", "Store", {"category": "SERVICE"}),
            ("LAUNDRY", "Laundry", {"category": "SERVICE", "wet_area": True}),
            ("BALCONY", "Balcony", {"category": "OUTDOOR", "default_zone": "SEMI_OPEN"}),
            ("TERRACE", "Terrace", {"category": "OUTDOOR", "default_zone": "OUTDOOR"}),
            ("SIT_OUT", "Sit-out", {"category": "OUTDOOR", "default_zone": "SEMI_OPEN"}),
            ("PORCH", "Porch", {"category": "OUTDOOR", "default_zone": "SEMI_OPEN"}),
            ("PARKING", "Parking", {"category": "OUTDOOR", "default_zone": "SEMI_OPEN"}),
            ("GARDEN", "Garden", {"category": "OUTDOOR", "default_zone": "OUTDOOR"}),
            ("CUSTOM", "Custom space", {"category": "OTHER", "label_required": True}),
        ),
    ),
    (
        "OPENING_TYPE",
        "Opening type",
        "Doors, windows, niches and other openings in a wall (MTQ)",
        (
            ("DOOR", "Door", None),
            ("WINDOW", "Window", None),
            ("FRENCH_WINDOW", "French window", None),
            ("ARCH", "Arch", None),
            ("NICHE", "Niche", None),
            ("VENTILATOR", "Ventilator", None),
            ("AC_SLEEVE", "Ac sleeve", None),
            ("SHAFT", "Shaft", None),
            ("DUCT", "Duct", None),
            ("CUSTOM", "Custom", None),
        ),
    ),
    (
        "MEASUREMENT_METHOD",
        "Measurement method",
        "How a measurement set was taken (MTQ)",
        (
            ("TAPE", "Tape", None),
            ("LASER", "Laser", None),
            ("PLAN_DRAWING", "Plan drawing", None),
            ("LIDAR_SCAN", "Lidar scan", None),
            ("TYPICAL", "Typical", None),
        ),
    ),
    (
        "ELECTRICAL_POINT_TYPE",
        "Electrical point type",
        "Electrical points captured on site (MTQ)",
        (
            ("LIGHT_POINT", "Light point", None),
            ("SENSOR_LIGHT", "Sensor light", None),
            ("FAN_POINT", "Fan point", None),
            ("SWITCHBOARD", "Switchboard", None),
            ("SOCKET_5A", "Socket 5a", None),
            ("SOCKET_15A", "Socket 15a", None),
            ("AC_POINT", "Ac point", None),
            ("DB_BOX", "Db box", None),
            ("TV_POINT", "Tv point", None),
            ("DATA_POINT", "Data point", None),
            ("GEYSER_POINT", "Geyser point", None),
            ("EXHAUST_POINT", "Exhaust point", None),
            ("CHIMNEY_POINT", "Chimney point", None),
            ("APPLIANCE_POINT", "Appliance point", None),
            ("PROFILE_LIGHT_FEED", "Profile light feed", None),
            ("CUSTOM", "Custom", None),
        ),
    ),
    (
        "SENSOR_TYPE",
        "Sensor type",
        "Sensor of a sensor light (MTQ)",
        (("PIR", "Pir", None), ("MICROWAVE", "Microwave", None), ("NONE", "None", None)),
    ),
    (
        "WALL_TAG",
        "Wall tag",
        "What a wall can carry; frozen for scope rules (MTQ B1-04)",
        (
            ("WARDROBE", "Wardrobe", None),
            ("LOFT", "Loft", None),
            ("BED_HEAD", "Bed head", None),
            ("TV_UNIT", "Tv unit", None),
            ("STUDY_UNIT", "Study unit", None),
            ("CROCKERY_UNIT", "Crockery unit", None),
            ("KITCHEN_RUN", "Kitchen run", None),
            ("KITCHEN_WALL_RUN", "Kitchen wall run", None),
            ("TALL_UNIT", "Tall unit", None),
            ("VANITY", "Vanity", None),
            ("SHOE_RACK", "Shoe rack", None),
            ("POOJA_UNIT", "Pooja unit", None),
            ("FEATURE_WALL", "Feature wall", None),
            ("WINDOW_SEATING", "Window seating", None),
            ("STORAGE_WALL", "Storage wall", None),
            ("PARTITION_EDGE", "Partition edge", None),
            ("NONE", "None", None),
        ),
    ),
    (
        "FLOORING",
        "Existing flooring",
        "Existing flooring of a space (MTQ)",
        (
            ("VITRIFIED", "Vitrified", None),
            ("MARBLE", "Marble", None),
            ("GRANITE", "Granite", None),
            ("WOOD", "Wood", None),
            ("CEMENT", "Cement", None),
            ("TILE_CERAMIC", "Tile ceramic", None),
            ("NONE_BARE", "None bare", None),
        ),
    ),
    (
        "EXISTING_CONDITION",
        "Existing condition",
        "Condition of a space as found (MTQ)",
        (
            ("BARE_SHELL", "Bare shell", None),
            ("FINISHED_NEW", "Finished new", None),
            ("OCCUPIED_GOOD", "Occupied good", None),
            ("OCCUPIED_WORN", "Occupied worn", None),
            ("DAMP", "Damp", None),
            ("CRACKED", "Cracked", None),
        ),
    ),
)


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "property",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("property_number", sa.String(20), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("property_type_code", sa.String(30), nullable=False),
        sa.Column("usage_code", sa.String(20), nullable=False),
        sa.Column("project_kind_code", sa.String(20), nullable=False),
        sa.Column("configuration_label", sa.String(40), nullable=True),
        sa.Column("built_up_area_sqft_centi", sa.Integer(), nullable=True),
        sa.Column("carpet_area_sqft_centi", sa.Integer(), nullable=True),
        sa.Column("plot_area_sqft_centi", sa.Integer(), nullable=True),
        sa.Column("floor_count", sa.Integer(), nullable=True),
        sa.Column("derived_bedroom_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("derived_toilet_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("derived_level_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("derived_measured_floor_area_sqft_centi", sa.Integer(), nullable=True),
        sa.Column("address_line_1", sa.String(200), nullable=True),
        sa.Column("address_line_2", sa.String(200), nullable=True),
        sa.Column("locality", sa.String(100), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("pincode", sa.String(10), nullable=True),
        sa.Column("geo_lat_e6", sa.Integer(), nullable=True),
        sa.Column("geo_lng_e6", sa.Integer(), nullable=True),
        sa.Column("possession_status_code", sa.String(20), nullable=True),
        sa.Column("possession_on", sa.Date(), nullable=True),
        sa.Column("floor_plan_attachment_id", GUID(), nullable=True),
        sa.Column("template_key", sa.String(40), nullable=True),
        sa.Column("template_version", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_property"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_property__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_property__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["floor_plan_attachment_id"],
            ["attachment.id"],
            name="fk_property__floor_plan_attachment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_property__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_property__updated_by", ondelete="RESTRICT"),
        sa.CheckConstraint("length(address_line_1) <= 200", name="ck_property__address_line_1_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(address_line_2) <= 200", name="ck_property__address_line_2_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "built_up_area_sqft_centi IS NULL OR built_up_area_sqft_centi >= 0",
            name="ck_property__built_up_area_sqft_centi_nn",
        ),
        sa.CheckConstraint(
            "carpet_area_sqft_centi IS NULL OR carpet_area_sqft_centi >= 0",
            name="ck_property__carpet_area_sqft_centi_nn",
        ),
        sa.CheckConstraint("length(city) <= 100", name="ck_property__city_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(configuration_label) <= 40", name="ck_property__configuration_label_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_property__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_property__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "derived_bedroom_count IS NULL OR derived_bedroom_count >= 0", name="ck_property__derived_bedroom_count_nn"
        ),
        sa.CheckConstraint(
            "derived_level_count IS NULL OR derived_level_count > 0", name="ck_property__derived_level_count_pos"
        ),
        sa.CheckConstraint(
            "derived_measured_floor_area_sqft_centi IS NULL OR derived_measured_floor_area_sqft_centi >= 0",
            name="ck_property__derived_measured_floor_area_sqft_centi_nn",
        ),
        sa.CheckConstraint(
            "derived_toilet_count IS NULL OR derived_toilet_count >= 0", name="ck_property__derived_toilet_count_nn"
        ),
        sa.CheckConstraint("floor_count IS NULL OR floor_count > 0", name="ck_property__floor_count_pos"),
        sa.CheckConstraint(
            "floor_plan_attachment_id IS NULL OR (length(floor_plan_attachment_id) = 32 AND floor_plan_attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(floor_plan_attachment_id, 13, 1) = '7' AND substr(floor_plan_attachment_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_property__floor_plan_attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("(geo_lat_e6 IS NULL) = (geo_lng_e6 IS NULL)", name="ck_property__geo_pair"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_property__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_property__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("geo_lat_e6 IS NULL OR geo_lat_e6 BETWEEN -90000000 AND 90000000", name="ck_property__lat"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_property__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "geo_lng_e6 IS NULL OR geo_lng_e6 BETWEEN -180000000 AND 180000000", name="ck_property__lng"
        ),
        sa.CheckConstraint("length(locality) <= 100", name="ck_property__locality_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(pincode) <= 10", name="ck_property__pincode_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "plot_area_sqft_centi IS NULL OR plot_area_sqft_centi >= 0", name="ck_property__plot_area_sqft_centi_nn"
        ),
        sa.CheckConstraint(
            "possession_status_code IS NULL OR possession_status_code IN ('UNDER_CONSTRUCTION', 'READY', 'OCCUPIED')",
            name="ck_property__possession_status_code",
        ),
        sa.CheckConstraint(
            "length(possession_status_code) <= 20", name="ck_property__possession_status_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "project_kind_code IN ('NEW', 'RENOVATION', 'PARTIAL')", name="ck_property__project_kind_code"
        ),
        sa.CheckConstraint("length(project_kind_code) <= 20", name="ck_property__project_kind_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(property_number) <= 20", name="ck_property__property_number_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "property_type_code IN ('APARTMENT', 'INDEPENDENT_HOUSE')", name="ck_property__property_type_code"
        ),
        sa.CheckConstraint("length(property_type_code) <= 30", name="ck_property__property_type_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_property__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(state) <= 100", name="ck_property__state_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(template_key) <= 40", name="ck_property__template_key_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(template_version) <= 20", name="ck_property__template_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_property__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_property__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("usage_code IN ('RESIDENTIAL')", name="ck_property__usage_code"),
        sa.CheckConstraint("length(usage_code) <= 20", name="ck_property__usage_code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_property__version_positive"),
    )
    op.create_index("ix_property__city", "property", ["city"])
    op.create_index("ix_property__lead_id", "property", ["lead_id"])
    op.create_index(
        "ux_property__property_number",
        "property",
        ["property_number"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "property_space",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("parent_space_id", GUID(), nullable=True),
        sa.Column("space_type_code", sa.String(40), nullable=False),
        sa.Column("custom_type_label", sa.String(60), nullable=True),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("instance_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("level_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("zone_code", sa.String(20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_in_scope", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("space_template_key", sa.String(80), nullable=True),
        sa.Column("template_version", sa.String(20), nullable=True),
        sa.Column("attributes", JSONType(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_property_space"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_property_space__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_property_space__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["parent_space_id"], ["property_space.id"], name="fk_property_space__parent_space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_property_space__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_property_space__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "attributes IS NULL OR json_valid(attributes)", name="ck_property_space__attributes_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_property_space__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "space_type_code <> 'CUSTOM' OR custom_type_label IS NOT NULL", name="ck_property_space__custom_label"
        ),
        sa.CheckConstraint("length(custom_type_label) <= 60", name="ck_property_space__custom_type_label_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_property_space__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_property_space__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("instance_no >= 1", name="ck_property_space__instance_no"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_property_space__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_in_scope IN (0, 1)", name="ck_property_space__is_in_scope_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 80", name="ck_property_space__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("level_index BETWEEN -3 AND 10", name="ck_property_space__level_index"),
        sa.CheckConstraint(
            "parent_space_id IS NULL OR parent_space_id <> id", name="ck_property_space__not_own_parent"
        ),
        sa.CheckConstraint(
            "parent_space_id IS NULL OR (length(parent_space_id) = 32 AND parent_space_id NOT GLOB '*[^0-9a-f]*' AND substr(parent_space_id, 13, 1) = '7' AND substr(parent_space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_property_space__parent_space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_property_space__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_property_space__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(space_template_key) <= 80", name="ck_property_space__space_template_key_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "space_type_code IN ('LIVING', 'DINING', 'LIVING_DINING', 'FAMILY_LOUNGE', 'FOYER', 'PASSAGE', 'STAIRCASE', 'POOJA', 'MASTER_BEDROOM', 'BEDROOM', 'CHILDREN_BEDROOM', 'GUEST_BEDROOM', 'PARENTS_BEDROOM', 'SERVANT_ROOM', 'DRESSING', 'WALK_IN_CLOSET', 'TOILET', 'POWDER_ROOM', 'STUDY', 'HOME_OFFICE', 'MEDIA_ROOM', 'KITCHEN', 'UTILITY', 'STORE', 'LAUNDRY', 'BALCONY', 'TERRACE', 'SIT_OUT', 'PORCH', 'PARKING', 'GARDEN', 'CUSTOM')",
            name="ck_property_space__space_type_code",
        ),
        sa.CheckConstraint("length(space_type_code) <= 40", name="ck_property_space__space_type_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(template_version) <= 20", name="ck_property_space__template_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_property_space__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_property_space__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_property_space__version_positive"),
        sa.CheckConstraint("zone_code IN ('INDOOR', 'SEMI_OPEN', 'OUTDOOR')", name="ck_property_space__zone_code"),
        sa.CheckConstraint("length(zone_code) <= 20", name="ck_property_space__zone_code_len").ddl_if(dialect="sqlite"),
    )
    op.create_index("ix_property_space__parent_space_id", "property_space", ["parent_space_id"])
    op.create_index("ix_property_space__property_order", "property_space", ["property_id", "level_index", "sort_order"])
    op.create_index(
        "ux_property_space__property_type_instance",
        "property_space",
        ["property_id", "space_type_code", "instance_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "measurement_visit",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("visit_number", sa.String(20), nullable=False),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("visit_type_code", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("survey_level_code", sa.String(10), nullable=False),
        sa.Column("status_changed_on", UTCDateTime(), nullable=False),
        sa.Column("scheduled_start_on", UTCDateTime(), nullable=True),
        sa.Column("scheduled_end_on", UTCDateTime(), nullable=True),
        sa.Column("started_on", UTCDateTime(), nullable=True),
        sa.Column("completed_on", UTCDateTime(), nullable=True),
        sa.Column("assigned_to", GUID(), nullable=True),
        sa.Column("lead_activity_id", GUID(), nullable=True),
        sa.Column("customer_contact_name", sa.String(150), nullable=True),
        sa.Column("customer_contact_phone", sa.String(16), nullable=True),
        sa.Column("access_notes", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_measurement_visit"),
        sa.ForeignKeyConstraint(
            ["assigned_to"], ["app_user.id"], name="fk_measurement_visit__assigned_to", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_measurement_visit__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_measurement_visit__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["lead_activity_id"],
            ["lead_activity.id"],
            name="fk_measurement_visit__lead_activity_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_measurement_visit__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_measurement_visit__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_measurement_visit__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "assigned_to IS NULL OR (length(assigned_to) = 32 AND assigned_to NOT GLOB '*[^0-9a-f]*' AND substr(assigned_to, 13, 1) = '7' AND substr(assigned_to, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_visit__assigned_to_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status <> 'CANCELLED' OR cancel_reason IS NOT NULL", name="ck_measurement_visit__cancel_reason"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_visit__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(customer_contact_name) <= 150", name="ck_measurement_visit__customer_contact_name_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(customer_contact_phone) <= 16", name="ck_measurement_visit__customer_contact_phone_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_visit__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_visit__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_measurement_visit__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "lead_activity_id IS NULL OR (length(lead_activity_id) = 32 AND lead_activity_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_activity_id, 13, 1) = '7' AND substr(lead_activity_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_visit__lead_activity_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_visit__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_visit__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "scheduled_end_on IS NULL OR scheduled_start_on IS NULL OR scheduled_end_on > scheduled_start_on",
            name="ck_measurement_visit__schedule_order",
        ),
        sa.CheckConstraint(
            "status NOT IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED') OR scheduled_start_on IS NOT NULL",
            name="ck_measurement_visit__scheduled_has_start",
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_measurement_visit__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'NO_SHOW')",
            name="ck_measurement_visit__status",
        ),
        sa.CheckConstraint("length(status) <= 20", name="ck_measurement_visit__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("survey_level_code IN ('LITE', 'FULL')", name="ck_measurement_visit__survey_level_code"),
        sa.CheckConstraint(
            "length(survey_level_code) <= 10", name="ck_measurement_visit__survey_level_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_measurement_visit__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_visit__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_measurement_visit__version_positive"),
        sa.CheckConstraint("length(visit_number) <= 20", name="ck_measurement_visit__visit_number_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "visit_type_code IN ('INITIAL', 'RE_MEASURE', 'VERIFICATION', 'DESIGN_CHECK')",
            name="ck_measurement_visit__visit_type_code",
        ),
        sa.CheckConstraint("length(visit_type_code) <= 20", name="ck_measurement_visit__visit_type_code_len").ddl_if(
            dialect="sqlite"
        ),
    )
    op.create_index("ix_measurement_visit__assigned_status", "measurement_visit", ["assigned_to", "status"])
    op.create_index("ix_measurement_visit__lead_id", "measurement_visit", ["lead_id"])
    op.create_index("ix_measurement_visit__property_id", "measurement_visit", ["property_id"])
    op.create_index(
        "ux_measurement_visit__visit_number",
        "measurement_visit",
        ["visit_number"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "measurement_set",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("measurement_visit_id", GUID(), nullable=True),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("supersedes_set_id", GUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("survey_level_code", sa.String(10), nullable=False),
        sa.Column("method_code", sa.String(20), nullable=False),
        sa.Column("unit_system_code", sa.String(10), nullable=False),
        sa.Column("captured_by", GUID(), nullable=False),
        sa.Column("submitted_on", UTCDateTime(), nullable=True),
        sa.Column("submitted_by", GUID(), nullable=True),
        sa.Column("verified_on", UTCDateTime(), nullable=True),
        sa.Column("verified_by", GUID(), nullable=True),
        sa.Column("rejected_on", UTCDateTime(), nullable=True),
        sa.Column("rejected_by", GUID(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("summary", JSONType(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=True),
        sa.Column("device_info", JSONType(), nullable=True),
        sa.Column("property_capture", JSONType(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_measurement_set"),
        sa.ForeignKeyConstraint(
            ["captured_by"], ["app_user.id"], name="fk_measurement_set__captured_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_measurement_set__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_measurement_set__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["measurement_visit_id"],
            ["measurement_visit.id"],
            name="fk_measurement_set__measurement_visit_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_measurement_set__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by"], ["app_user.id"], name="fk_measurement_set__rejected_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"], ["app_user.id"], name="fk_measurement_set__submitted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_set_id"],
            ["measurement_set.id"],
            name="fk_measurement_set__supersedes_set_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_measurement_set__updated_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["verified_by"], ["app_user.id"], name="fk_measurement_set__verified_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(captured_by) = 32 AND captured_by NOT GLOB '*[^0-9a-f]*' AND substr(captured_by, 13, 1) = '7' AND substr(captured_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_set__captured_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_set__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_set__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "device_info IS NULL OR json_valid(device_info)", name="ck_measurement_set__device_info_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_set__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_measurement_set__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "measurement_visit_id IS NULL OR (length(measurement_visit_id) = 32 AND measurement_visit_id NOT GLOB '*[^0-9a-f]*' AND substr(measurement_visit_id, 13, 1) = '7' AND substr(measurement_visit_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_set__measurement_visit_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "method_code IN ('TAPE', 'LASER', 'PLAN_DRAWING', 'LIDAR_SCAN', 'TYPICAL')",
            name="ck_measurement_set__method_code",
        ),
        sa.CheckConstraint("length(method_code) <= 20", name="ck_measurement_set__method_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "supersedes_set_id IS NULL OR supersedes_set_id <> id", name="ck_measurement_set__not_self_superseding"
        ),
        sa.CheckConstraint(
            "property_capture IS NULL OR json_valid(property_capture)", name="ck_measurement_set__property_capture_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_set__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "rejected_by IS NULL OR (length(rejected_by) = 32 AND rejected_by NOT GLOB '*[^0-9a-f]*' AND substr(rejected_by, 13, 1) = '7' AND substr(rejected_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_set__rejected_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status <> 'REJECTED' OR (rejected_on IS NOT NULL AND rejection_reason IS NOT NULL)",
            name="ck_measurement_set__rejected_reason",
        ),
        sa.CheckConstraint("revision_no >= 1", name="ck_measurement_set__revision_no"),
        sa.CheckConstraint(
            "snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64", name="ck_measurement_set__snapshot_len"
        ),
        sa.CheckConstraint("length(snapshot_sha256) <= 64", name="ck_measurement_set__snapshot_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_measurement_set__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'SUBMITTED', 'VERIFIED', 'SUPERSEDED', 'REJECTED')", name="ck_measurement_set__status"
        ),
        sa.CheckConstraint("length(status) <= 20", name="ck_measurement_set__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "submitted_by IS NULL OR (length(submitted_by) = 32 AND submitted_by NOT GLOB '*[^0-9a-f]*' AND substr(submitted_by, 13, 1) = '7' AND substr(submitted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_set__submitted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status NOT IN ('SUBMITTED', 'VERIFIED', 'SUPERSEDED', 'REJECTED') OR submitted_on IS NOT NULL",
            name="ck_measurement_set__submitted_on",
        ),
        sa.CheckConstraint("summary IS NULL OR json_valid(summary)", name="ck_measurement_set__summary_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "supersedes_set_id IS NULL OR (length(supersedes_set_id) = 32 AND supersedes_set_id NOT GLOB '*[^0-9a-f]*' AND substr(supersedes_set_id, 13, 1) = '7' AND substr(supersedes_set_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_set__supersedes_set_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("survey_level_code IN ('LITE', 'FULL')", name="ck_measurement_set__survey_level_code"),
        sa.CheckConstraint("length(survey_level_code) <= 10", name="ck_measurement_set__survey_level_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("unit_system_code IN ('FT_IN', 'MM')", name="ck_measurement_set__unit_system_code"),
        sa.CheckConstraint("length(unit_system_code) <= 10", name="ck_measurement_set__unit_system_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_measurement_set__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_set__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "verified_by IS NULL OR (length(verified_by) = 32 AND verified_by NOT GLOB '*[^0-9a-f]*' AND substr(verified_by, 13, 1) = '7' AND substr(verified_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_set__verified_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status <> 'VERIFIED' OR (verified_on IS NOT NULL AND verified_by IS NOT NULL AND snapshot_sha256 IS NOT NULL)",
            name="ck_measurement_set__verified_sealed",
        ),
        sa.CheckConstraint("version >= 1", name="ck_measurement_set__version_positive"),
    )
    op.create_index("ix_measurement_set__supersedes_set_id", "measurement_set", ["supersedes_set_id"])
    op.create_index("ix_measurement_set__visit", "measurement_set", ["measurement_visit_id"])
    op.create_index(
        "ux_measurement_set__one_draft",
        "measurement_set",
        ["property_id"],
        unique=True,
        sqlite_where=sa.text("status = 'DRAFT' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'DRAFT' AND is_deleted = false"),
    )
    op.create_index(
        "ux_measurement_set__one_verified",
        "measurement_set",
        ["property_id"],
        unique=True,
        sqlite_where=sa.text("status = 'VERIFIED' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'VERIFIED' AND is_deleted = false"),
    )
    op.create_index(
        "ux_measurement_set__property_revision",
        "measurement_set",
        ["property_id", "revision_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "space_measurement",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("measurement_set_id", GUID(), nullable=False),
        sa.Column("space_id", GUID(), nullable=False),
        sa.Column("shape_code", sa.String(20), nullable=False),
        sa.Column("length_mm", sa.Integer(), nullable=True),
        sa.Column("width_mm", sa.Integer(), nullable=True),
        sa.Column("ceiling_height_mm", sa.Integer(), nullable=True),
        sa.Column("beam_bottom_height_mm", sa.Integer(), nullable=True),
        sa.Column("floor_to_lintel_mm", sa.Integer(), nullable=True),
        sa.Column("stated_floor_area_sqft_centi", sa.Integer(), nullable=True),
        sa.Column("derived_floor_area_sqft_centi", sa.Integer(), nullable=True),
        sa.Column("derived_perimeter_mm", sa.Integer(), nullable=True),
        sa.Column("derived_wall_area_gross_sqft_centi", sa.Integer(), nullable=True),
        sa.Column("derived_wall_area_net_sqft_centi", sa.Integer(), nullable=True),
        sa.Column("polygon", JSONType(), nullable=True),
        sa.Column("flooring_code", sa.String(30), nullable=True),
        sa.Column("existing_condition_code", sa.String(30), nullable=True),
        sa.Column("is_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confidence_code", sa.String(10), nullable=False, server_default="HIGH"),
        sa.Column("attributes", JSONType(), nullable=False),
        sa.Column("captured_by", GUID(), nullable=False),
        sa.Column("claim_expires_on", UTCDateTime(), nullable=True),
        sa.Column("client_ref", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_space_measurement"),
        sa.ForeignKeyConstraint(
            ["captured_by"], ["app_user.id"], name="fk_space_measurement__captured_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_space_measurement__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_space_measurement__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["measurement_set_id"],
            ["measurement_set.id"],
            name="fk_space_measurement__measurement_set_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_space_measurement__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_space_measurement__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "attributes IS NULL OR json_valid(attributes)", name="ck_space_measurement__attributes_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "beam_bottom_height_mm IS NULL OR beam_bottom_height_mm > 0",
            name="ck_space_measurement__beam_bottom_height_mm_pos",
        ),
        sa.CheckConstraint(
            "length(captured_by) = 32 AND captured_by NOT GLOB '*[^0-9a-f]*' AND substr(captured_by, 13, 1) = '7' AND substr(captured_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_measurement__captured_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "ceiling_height_mm IS NULL OR ceiling_height_mm > 0", name="ck_space_measurement__ceiling_height_mm_pos"
        ),
        sa.CheckConstraint("length(client_ref) <= 64", name="ck_space_measurement__client_ref_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "confidence_code IN ('HIGH', 'MEDIUM', 'LOW')", name="ck_space_measurement__confidence_code"
        ),
        sa.CheckConstraint("length(confidence_code) <= 10", name="ck_space_measurement__confidence_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_measurement__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_space_measurement__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "derived_floor_area_sqft_centi IS NULL OR derived_floor_area_sqft_centi >= 0",
            name="ck_space_measurement__derived_floor_area_sqft_centi_nn",
        ),
        sa.CheckConstraint(
            "derived_perimeter_mm IS NULL OR derived_perimeter_mm >= 0",
            name="ck_space_measurement__derived_perimeter_mm_nn",
        ),
        sa.CheckConstraint(
            "derived_wall_area_gross_sqft_centi IS NULL OR derived_wall_area_gross_sqft_centi >= 0",
            name="ck_space_measurement__derived_wall_area_gross_sqft_centi_nn",
        ),
        sa.CheckConstraint(
            "derived_wall_area_net_sqft_centi IS NULL OR derived_wall_area_net_sqft_centi >= 0",
            name="ck_space_measurement__derived_wall_area_net_sqft_centi_nn",
        ),
        sa.CheckConstraint(
            "existing_condition_code IS NULL OR existing_condition_code IN ('BARE_SHELL', 'FINISHED_NEW', 'OCCUPIED_GOOD', 'OCCUPIED_WORN', 'DAMP', 'CRACKED')",
            name="ck_space_measurement__existing_condition_code",
        ),
        sa.CheckConstraint(
            "length(existing_condition_code) <= 30", name="ck_space_measurement__existing_condition_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "floor_to_lintel_mm IS NULL OR floor_to_lintel_mm > 0", name="ck_space_measurement__floor_to_lintel_mm_pos"
        ),
        sa.CheckConstraint(
            "flooring_code IS NULL OR flooring_code IN ('VITRIFIED', 'MARBLE', 'GRANITE', 'WOOD', 'CEMENT', 'TILE_CERAMIC', 'NONE_BARE')",
            name="ck_space_measurement__flooring_code",
        ),
        sa.CheckConstraint("length(flooring_code) <= 30", name="ck_space_measurement__flooring_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "shape_code <> 'FREEFORM' OR stated_floor_area_sqft_centi IS NOT NULL",
            name="ck_space_measurement__freeform_area",
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_measurement__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_complete IN (0, 1)", name="ck_space_measurement__is_complete_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_space_measurement__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length_mm IS NULL OR length_mm > 0", name="ck_space_measurement__length_mm_pos"),
        sa.CheckConstraint(
            "length(measurement_set_id) = 32 AND measurement_set_id NOT GLOB '*[^0-9a-f]*' AND substr(measurement_set_id, 13, 1) = '7' AND substr(measurement_set_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_measurement__measurement_set_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("polygon IS NULL OR json_valid(polygon)", name="ck_space_measurement__polygon_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "shape_code IN ('RECTANGULAR', 'L_SHAPE', 'POLYGON', 'FREEFORM')", name="ck_space_measurement__shape_code"
        ),
        sa.CheckConstraint("length(shape_code) <= 20", name="ck_space_measurement__shape_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_space_measurement__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_measurement__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "stated_floor_area_sqft_centi IS NULL OR stated_floor_area_sqft_centi > 0",
            name="ck_space_measurement__stated_floor_area_sqft_centi_pos",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_space_measurement__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_measurement__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_space_measurement__version_positive"),
        sa.CheckConstraint("width_mm IS NULL OR width_mm > 0", name="ck_space_measurement__width_mm_pos"),
    )
    op.create_index("ix_space_measurement__space_id", "space_measurement", ["space_id"])
    op.create_index(
        "ux_space_measurement__client_ref",
        "space_measurement",
        ["measurement_set_id", "client_ref"],
        unique=True,
        sqlite_where=sa.text("client_ref IS NOT NULL AND is_deleted = 0"),
        postgresql_where=sa.text("client_ref IS NOT NULL AND is_deleted = false"),
    )
    op.create_index(
        "ux_space_measurement__set_space",
        "space_measurement",
        ["measurement_set_id", "space_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "space_wall",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("space_measurement_id", GUID(), nullable=False),
        sa.Column("wall_index", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(40), nullable=True),
        sa.Column("length_mm", sa.Integer(), nullable=False),
        sa.Column("height_mm", sa.Integer(), nullable=True),
        sa.Column("wall_type_code", sa.String(20), nullable=False),
        sa.Column("is_external", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_proposed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("usable_for_code", JSONType(), nullable=False),
        sa.Column("obstructions", JSONType(), nullable=False),
        sa.Column("client_ref", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_space_wall"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_space_wall__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_space_wall__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["space_measurement_id"],
            ["space_measurement.id"],
            name="fk_space_wall__space_measurement_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_space_wall__updated_by", ondelete="RESTRICT"),
        sa.CheckConstraint("length(client_ref) <= 64", name="ck_space_wall__client_ref_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_wall__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_space_wall__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("height_mm IS NULL OR height_mm > 0", name="ck_space_wall__height_mm_pos"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_wall__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_space_wall__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_external IN (0, 1)", name="ck_space_wall__is_external_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_proposed IN (0, 1)", name="ck_space_wall__is_proposed_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(label) <= 40", name="ck_space_wall__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length_mm > 0", name="ck_space_wall__length_positive"),
        sa.CheckConstraint(
            "obstructions IS NULL OR json_valid(obstructions)", name="ck_space_wall__obstructions_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "is_proposed = false OR wall_type_code = 'PARTITION'", name="ck_space_wall__proposed_partition"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_space_wall__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "length(space_measurement_id) = 32 AND space_measurement_id NOT GLOB '*[^0-9a-f]*' AND substr(space_measurement_id, 13, 1) = '7' AND substr(space_measurement_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_wall__space_measurement_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_space_wall__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_wall__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "usable_for_code IS NULL OR json_valid(usable_for_code)", name="ck_space_wall__usable_for_code_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_space_wall__version_positive"),
        sa.CheckConstraint("wall_index BETWEEN 0 AND 64", name="ck_space_wall__wall_index"),
        sa.CheckConstraint(
            "wall_type_code IN ('MASONRY', 'RCC', 'PARTITION', 'GLASS', 'OPEN')", name="ck_space_wall__wall_type_code"
        ),
        sa.CheckConstraint("length(wall_type_code) <= 20", name="ck_space_wall__wall_type_code_len").ddl_if(
            dialect="sqlite"
        ),
    )
    op.create_index(
        "ux_space_wall__measurement_index",
        "space_wall",
        ["space_measurement_id", "wall_index"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "space_opening",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("space_wall_id", GUID(), nullable=False),
        sa.Column("opening_type_code", sa.String(20), nullable=False),
        sa.Column("width_mm", sa.Integer(), nullable=False),
        sa.Column("height_mm", sa.Integer(), nullable=False),
        sa.Column("sill_height_mm", sa.Integer(), nullable=True),
        sa.Column("offset_from_wall_start_mm", sa.Integer(), nullable=True),
        sa.Column("swing_code", sa.String(10), nullable=True),
        sa.Column("deducts_from_wall_area", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("purpose_code", sa.String(20), nullable=True),
        sa.Column("depth_mm", sa.Integer(), nullable=True),
        sa.Column("is_existing", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("client_ref", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_space_opening"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_space_opening__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_space_opening__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["space_wall_id"], ["space_wall.id"], name="fk_space_opening__space_wall_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_space_opening__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("length(client_ref) <= 64", name="ck_space_opening__client_ref_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_opening__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deducts_from_wall_area IN (0, 1)", name="ck_space_opening__deducts_from_wall_area_bool"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_space_opening__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("depth_mm IS NULL OR depth_mm > 0", name="ck_space_opening__depth_mm_pos"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_opening__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_space_opening__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_existing IN (0, 1)", name="ck_space_opening__is_existing_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "opening_type_code <> 'NICHE' OR depth_mm IS NOT NULL", name="ck_space_opening__niche_depth"
        ),
        sa.CheckConstraint(
            "offset_from_wall_start_mm IS NULL OR offset_from_wall_start_mm >= 0",
            name="ck_space_opening__offset_from_wall_start_mm_nn",
        ),
        sa.CheckConstraint(
            "opening_type_code IN ('DOOR', 'WINDOW', 'FRENCH_WINDOW', 'ARCH', 'NICHE', 'VENTILATOR', 'AC_SLEEVE', 'SHAFT', 'DUCT', 'CUSTOM')",
            name="ck_space_opening__opening_type_code",
        ),
        sa.CheckConstraint("length(opening_type_code) <= 20", name="ck_space_opening__opening_type_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "purpose_code IS NULL OR purpose_code IN ('FRIDGE', 'APPLIANCE', 'STORAGE', 'WASH', 'OTHER')",
            name="ck_space_opening__purpose_code",
        ),
        sa.CheckConstraint("length(purpose_code) <= 20", name="ck_space_opening__purpose_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "purpose_code IS NULL OR opening_type_code = 'NICHE'", name="ck_space_opening__purpose_niche_only"
        ),
        sa.CheckConstraint("sill_height_mm IS NULL OR sill_height_mm >= 0", name="ck_space_opening__sill_height_mm_nn"),
        sa.CheckConstraint("width_mm > 0 AND height_mm > 0", name="ck_space_opening__size_positive"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_space_opening__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "length(space_wall_id) = 32 AND space_wall_id NOT GLOB '*[^0-9a-f]*' AND substr(space_wall_id, 13, 1) = '7' AND substr(space_wall_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_opening__space_wall_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "swing_code IS NULL OR swing_code IN ('IN', 'OUT', 'SLIDING', 'NONE')", name="ck_space_opening__swing_code"
        ),
        sa.CheckConstraint("length(swing_code) <= 10", name="ck_space_opening__swing_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_space_opening__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_opening__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_space_opening__version_positive"),
    )
    op.create_index("ix_space_opening__space_wall_id", "space_opening", ["space_wall_id"])

    op.create_table(
        "space_electrical_point",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("space_measurement_id", GUID(), nullable=False),
        sa.Column("space_wall_id", GUID(), nullable=True),
        sa.Column("point_type_code", sa.String(20), nullable=False),
        sa.Column("status_code", sa.String(10), nullable=False),
        sa.Column("from_offset_mm", sa.Integer(), nullable=True),
        sa.Column("from_height_mm", sa.Integer(), nullable=True),
        sa.Column("to_wall_id", GUID(), nullable=True),
        sa.Column("to_offset_mm", sa.Integer(), nullable=True),
        sa.Column("to_height_mm", sa.Integer(), nullable=True),
        sa.Column("sensor_type_code", sa.String(10), nullable=True),
        sa.Column("switching_code", sa.String(10), nullable=True),
        sa.Column("location_code", sa.String(20), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reason_code", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attachment_id", GUID(), nullable=True),
        sa.Column("client_ref", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_space_electrical_point"),
        sa.ForeignKeyConstraint(
            ["attachment_id"], ["attachment.id"], name="fk_space_electrical_point__attachment_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_space_electrical_point__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_space_electrical_point__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["space_measurement_id"],
            ["space_measurement.id"],
            name="fk_space_electrical_point__space_measurement_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["space_wall_id"], ["space_wall.id"], name="fk_space_electrical_point__space_wall_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["to_wall_id"], ["space_wall.id"], name="fk_space_electrical_point__to_wall_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_space_electrical_point__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "attachment_id IS NULL OR (length(attachment_id) = 32 AND attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(attachment_id, 13, 1) = '7' AND substr(attachment_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_space_electrical_point__attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(client_ref) <= 64", name="ck_space_electrical_point__client_ref_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_electrical_point__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_space_electrical_point__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "from_height_mm IS NULL OR from_height_mm >= 0", name="ck_space_electrical_point__from_height_mm_nn"
        ),
        sa.CheckConstraint(
            "from_offset_mm IS NULL OR from_offset_mm >= 0", name="ck_space_electrical_point__from_offset_mm_nn"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_electrical_point__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_space_electrical_point__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "location_code IS NULL OR location_code IN ('CEILING', 'WALL', 'IN_WARDROBE', 'UNDER_CABINET', 'FOYER_ENTRY', 'TOILET', 'STAIRCASE')",
            name="ck_space_electrical_point__location_code",
        ),
        sa.CheckConstraint("length(location_code) <= 20", name="ck_space_electrical_point__location_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "status_code <> 'NEW' OR to_offset_mm IS NOT NULL", name="ck_space_electrical_point__new_position"
        ),
        sa.CheckConstraint(
            "point_type_code IN ('LIGHT_POINT', 'SENSOR_LIGHT', 'FAN_POINT', 'SWITCHBOARD', 'SOCKET_5A', 'SOCKET_15A', 'AC_POINT', 'DB_BOX', 'TV_POINT', 'DATA_POINT', 'GEYSER_POINT', 'EXHAUST_POINT', 'CHIMNEY_POINT', 'APPLIANCE_POINT', 'PROFILE_LIGHT_FEED', 'CUSTOM')",
            name="ck_space_electrical_point__point_type_code",
        ),
        sa.CheckConstraint(
            "length(point_type_code) <= 20", name="ck_space_electrical_point__point_type_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("quantity BETWEEN 1 AND 99", name="ck_space_electrical_point__quantity"),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code IN ('FURNITURE_CLASH', 'CEILING_DESIGN', 'CUSTOMER_REQUEST', 'SAFETY')",
            name="ck_space_electrical_point__reason_code",
        ),
        sa.CheckConstraint("length(reason_code) <= 20", name="ck_space_electrical_point__reason_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "point_type_code <> 'SENSOR_LIGHT' OR sensor_type_code IS NOT NULL",
            name="ck_space_electrical_point__sensor_type",
        ),
        sa.CheckConstraint(
            "sensor_type_code IS NULL OR sensor_type_code IN ('PIR', 'MICROWAVE', 'NONE')",
            name="ck_space_electrical_point__sensor_type_code",
        ),
        sa.CheckConstraint(
            "length(sensor_type_code) <= 10", name="ck_space_electrical_point__sensor_type_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status_code <> 'SHIFT' OR (from_offset_mm IS NOT NULL AND to_offset_mm IS NOT NULL)",
            name="ck_space_electrical_point__shift_positions",
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_space_electrical_point__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "length(space_measurement_id) = 32 AND space_measurement_id NOT GLOB '*[^0-9a-f]*' AND substr(space_measurement_id, 13, 1) = '7' AND substr(space_measurement_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_electrical_point__space_measurement_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "space_wall_id IS NULL OR (length(space_wall_id) = 32 AND space_wall_id NOT GLOB '*[^0-9a-f]*' AND substr(space_wall_id, 13, 1) = '7' AND substr(space_wall_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_space_electrical_point__space_wall_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status_code IN ('EXISTING', 'SHIFT', 'NEW', 'REMOVE')", name="ck_space_electrical_point__status_code"
        ),
        sa.CheckConstraint("length(status_code) <= 10", name="ck_space_electrical_point__status_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "switching_code IS NULL OR switching_code IN ('SENSOR', 'MANUAL', 'BOTH')",
            name="ck_space_electrical_point__switching_code",
        ),
        sa.CheckConstraint("length(switching_code) <= 10", name="ck_space_electrical_point__switching_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "to_height_mm IS NULL OR to_height_mm >= 0", name="ck_space_electrical_point__to_height_mm_nn"
        ),
        sa.CheckConstraint(
            "to_offset_mm IS NULL OR to_offset_mm >= 0", name="ck_space_electrical_point__to_offset_mm_nn"
        ),
        sa.CheckConstraint(
            "to_wall_id IS NULL OR (length(to_wall_id) = 32 AND to_wall_id NOT GLOB '*[^0-9a-f]*' AND substr(to_wall_id, 13, 1) = '7' AND substr(to_wall_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_space_electrical_point__to_wall_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_space_electrical_point__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_space_electrical_point__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_space_electrical_point__version_positive"),
    )
    op.create_index(
        "ix_space_electrical_point__space_measurement_id", "space_electrical_point", ["space_measurement_id"]
    )
    op.create_index("ix_space_electrical_point__space_wall_id", "space_electrical_point", ["space_wall_id"])
    op.create_index("ix_space_electrical_point__to_wall_id", "space_electrical_point", ["to_wall_id"])

    op.create_table(
        "measurement_note",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("measurement_set_id", GUID(), nullable=False),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("note_type_code", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("attachment_id", GUID(), nullable=True),
        sa.Column("client_ref", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_measurement_note"),
        sa.ForeignKeyConstraint(
            ["attachment_id"], ["attachment.id"], name="fk_measurement_note__attachment_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_measurement_note__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_measurement_note__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["measurement_set_id"],
            ["measurement_set.id"],
            name="fk_measurement_note__measurement_set_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_measurement_note__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_measurement_note__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "attachment_id IS NULL OR (length(attachment_id) = 32 AND attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(attachment_id, 13, 1) = '7' AND substr(attachment_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_note__attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(client_ref) <= 64", name="ck_measurement_note__client_ref_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_note__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_note__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_note__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_measurement_note__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(measurement_set_id) = 32 AND measurement_set_id NOT GLOB '*[^0-9a-f]*' AND substr(measurement_set_id, 13, 1) = '7' AND substr(measurement_set_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_note__measurement_set_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "note_type_code IN ('OBSERVATION', 'RISK', 'CUSTOMER_REQUEST', 'VOICE_TRANSCRIPT', 'RISK_ACK')",
            name="ck_measurement_note__note_type_code",
        ),
        sa.CheckConstraint("length(note_type_code) <= 20", name="ck_measurement_note__note_type_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_measurement_note__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_measurement_note__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_measurement_note__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_measurement_note__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_measurement_note__version_positive"),
    )
    op.create_index("ix_measurement_note__set_space", "measurement_note", ["measurement_set_id", "space_id"])
    op.create_index("ix_measurement_note__space_id", "measurement_note", ["space_id"])
    op.create_index(
        "ux_measurement_note__client_ref",
        "measurement_note",
        ["measurement_set_id", "client_ref"],
        unique=True,
        sqlite_where=sa.text("client_ref IS NOT NULL AND is_deleted = 0"),
        postgresql_where=sa.text("client_ref IS NOT NULL AND is_deleted = false"),
    )
    # --- end generated DDL ---
    bind = op.get_bind()
    ms.seed_lookups(bind, LOOKUPS, module="mtq")
    for key, prefix in SEQUENCES:
        ms.seed_sequence(bind, key, prefix)
    ms.sync_permissions(bind, audit=True)
    ms.seed_missing_roles(bind, ROLES, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
