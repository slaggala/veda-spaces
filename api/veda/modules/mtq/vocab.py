"""Frozen B1 vocabularies (MTQ B1-SCOPE §2, blocker closure §3 and AR rows; PR #84 00-conventions §2–§4).

One source for the CHECK constraints, the request schemas and the 0200 lookup seed (the migration carries its own
copy, which a test keeps equal to this module). Values are only ever added by a later migration, never renamed.
"""

from __future__ import annotations

# B1 supports residential apartments and independent houses only (B1-01). Duplex, villa and commercial are deferred.
PROPERTY_TYPES = ("APARTMENT", "INDEPENDENT_HOUSE")
USAGES = ("RESIDENTIAL",)
PROJECT_KINDS = ("NEW", "RENOVATION", "PARTIAL")
POSSESSION_STATUSES = ("UNDER_CONSTRUCTION", "READY", "OCCUPIED")
ZONES = ("INDOOR", "SEMI_OPEN", "OUTDOOR")

# SPACE_TYPE, the residential B1 subset (B1-SCOPE §2.1). (code, label, category, attributes)
SPACE_TYPE_ROWS: tuple[tuple[str, str, str, dict], ...] = (
    ("LIVING", "Living room", "LIVING", {}),
    ("DINING", "Dining", "LIVING", {}),
    ("LIVING_DINING", "Living and dining", "LIVING", {}),
    ("FAMILY_LOUNGE", "Family lounge", "LIVING", {}),
    ("FOYER", "Foyer", "LIVING", {}),
    ("PASSAGE", "Passage", "LIVING", {}),
    ("STAIRCASE", "Staircase", "LIVING", {}),
    ("POOJA", "Pooja room", "LIVING", {}),
    ("MASTER_BEDROOM", "Master bedroom", "SLEEPING", {"counts_as_bedroom": True}),
    ("BEDROOM", "Bedroom", "SLEEPING", {"counts_as_bedroom": True}),
    ("CHILDREN_BEDROOM", "Children's bedroom", "SLEEPING", {"counts_as_bedroom": True}),
    ("GUEST_BEDROOM", "Guest bedroom", "SLEEPING", {"counts_as_bedroom": True}),
    ("PARENTS_BEDROOM", "Parents' bedroom", "SLEEPING", {"counts_as_bedroom": True}),
    ("SERVANT_ROOM", "Servant room", "SLEEPING", {"counts_as_bedroom": False}),  # not a bedroom (B1-SCOPE §2.9.4)
    ("DRESSING", "Dressing", "ATTACHED", {}),
    ("WALK_IN_CLOSET", "Walk-in closet", "ATTACHED", {}),
    ("TOILET", "Toilet", "ATTACHED", {"counts_as_toilet": True, "wet_area": True}),
    ("POWDER_ROOM", "Powder room", "ATTACHED", {"wet_area": True}),
    ("STUDY", "Study", "WORK", {}),  # not a bedroom (B1-SCOPE §2.9.4)
    ("HOME_OFFICE", "Home office", "WORK", {}),
    ("MEDIA_ROOM", "Media room", "LIVING", {}),
    ("KITCHEN", "Kitchen", "SERVICE", {"wet_area": True}),
    ("UTILITY", "Utility", "SERVICE", {"wet_area": True}),
    ("STORE", "Store", "SERVICE", {}),
    ("LAUNDRY", "Laundry", "SERVICE", {"wet_area": True}),
    ("BALCONY", "Balcony", "OUTDOOR", {"default_zone": "SEMI_OPEN"}),
    ("TERRACE", "Terrace", "OUTDOOR", {"default_zone": "OUTDOOR"}),
    ("SIT_OUT", "Sit-out", "OUTDOOR", {"default_zone": "SEMI_OPEN"}),
    ("PORCH", "Porch", "OUTDOOR", {"default_zone": "SEMI_OPEN"}),
    ("PARKING", "Parking", "OUTDOOR", {"default_zone": "SEMI_OPEN"}),
    ("GARDEN", "Garden", "OUTDOOR", {"default_zone": "OUTDOOR"}),
    ("CUSTOM", "Custom space", "OTHER", {"label_required": True}),
)
SPACE_TYPES = tuple(r[0] for r in SPACE_TYPE_ROWS)
BEDROOM_TYPES = tuple(r[0] for r in SPACE_TYPE_ROWS if r[3].get("counts_as_bedroom"))
TOILET_TYPES = tuple(r[0] for r in SPACE_TYPE_ROWS if r[3].get("counts_as_toilet"))

VISIT_TYPES = ("INITIAL", "RE_MEASURE", "VERIFICATION", "DESIGN_CHECK")
VISIT_STATUSES = ("REQUESTED", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "NO_SHOW")
SURVEY_LEVELS = ("LITE", "FULL")
SET_STATUSES = ("DRAFT", "SUBMITTED", "VERIFIED", "SUPERSEDED", "REJECTED")
MEASUREMENT_METHODS = ("TAPE", "LASER", "PLAN_DRAWING", "LIDAR_SCAN", "TYPICAL")
UNIT_SYSTEMS = ("FT_IN", "MM")
SHAPES = ("RECTANGULAR", "L_SHAPE", "POLYGON", "FREEFORM")
CONFIDENCES = ("HIGH", "MEDIUM", "LOW")
WALL_TYPES = ("MASONRY", "RCC", "PARTITION", "GLASS", "OPEN")
# WALL_TAG, frozen for B2 rules (B1-04, B1-SCOPE §2.6): seventeen values.
WALL_TAGS = (
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
)
# PR #84 00 §4 obstruction kinds, plus ARCHITRAVE (AR-11) and AC_DRAIN (AR-13). NONE is the explicit "no obstructions"
# marker the FULL verification rule asks for (B1-SCOPE §2.3); it stands alone.
OBSTRUCTION_KINDS = (
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
)
OPENING_TYPES = (
    "DOOR",
    "WINDOW",
    "FRENCH_WINDOW",
    "ARCH",
    "NICHE",
    "VENTILATOR",
    "AC_SLEEVE",
    "SHAFT",
    "DUCT",
    "CUSTOM",
)
SWINGS = ("IN", "OUT", "SLIDING", "NONE")
NICHE_PURPOSES = ("FRIDGE", "APPLIANCE", "STORAGE", "WASH", "OTHER")
FLOORINGS = ("VITRIFIED", "MARBLE", "GRANITE", "WOOD", "CEMENT", "TILE_CERAMIC", "NONE_BARE")
EXISTING_CONDITIONS = ("BARE_SHELL", "FINISHED_NEW", "OCCUPIED_GOOD", "OCCUPIED_WORN", "DAMP", "CRACKED")
ELECTRICAL_POINT_TYPES = (
    "LIGHT_POINT",
    "SENSOR_LIGHT",
    "FAN_POINT",
    "SWITCHBOARD",
    "SOCKET_5A",
    "SOCKET_15A",
    "AC_POINT",
    "DB_BOX",
    "TV_POINT",
    "DATA_POINT",
    "GEYSER_POINT",
    "EXHAUST_POINT",
    "CHIMNEY_POINT",
    "APPLIANCE_POINT",
    "PROFILE_LIGHT_FEED",
    "CUSTOM",
)
ELECTRICAL_STATUSES = ("EXISTING", "SHIFT", "NEW", "REMOVE")
SENSOR_TYPES = ("PIR", "MICROWAVE", "NONE")
SWITCHINGS = ("SENSOR", "MANUAL", "BOTH")
ELECTRICAL_LOCATIONS = ("CEILING", "WALL", "IN_WARDROBE", "UNDER_CABINET", "FOYER_ENTRY", "TOILET", "STAIRCASE")
ELECTRICAL_REASONS = ("FURNITURE_CLASH", "CEILING_DESIGN", "CUSTOMER_REQUEST", "SAFETY")
NOTE_TYPES = ("OBSERVATION", "RISK", "CUSTOMER_REQUEST", "VOICE_TRANSCRIPT", "RISK_ACK")


def _rows(values: tuple[str, ...]) -> tuple[tuple[str, str, dict | None], ...]:
    return tuple((v, v.replace("_", " ").capitalize(), None) for v in values)


# The lookup categories 0200 seeds (module "mtq"). Labels are display text only.
LOOKUPS: tuple[tuple[str, str, str, tuple[tuple[str, str, dict | None], ...]], ...] = (
    (
        "SPACE_TYPE",
        "Space type",
        "Residential space types of the B1 property model (MTQ)",
        tuple((code, label, {"category": cat, **attrs}) for code, label, cat, attrs in SPACE_TYPE_ROWS),
    ),
    ("OPENING_TYPE", "Opening type", "Doors, windows, niches and other openings in a wall (MTQ)", _rows(OPENING_TYPES)),
    ("MEASUREMENT_METHOD", "Measurement method", "How a measurement set was taken (MTQ)", _rows(MEASUREMENT_METHODS)),
    (
        "ELECTRICAL_POINT_TYPE",
        "Electrical point type",
        "Electrical points captured on site (MTQ)",
        _rows(ELECTRICAL_POINT_TYPES),
    ),  # fmt: skip
    ("SENSOR_TYPE", "Sensor type", "Sensor of a sensor light (MTQ)", _rows(SENSOR_TYPES)),
    ("WALL_TAG", "Wall tag", "What a wall can carry; frozen for scope rules (MTQ B1-04)", _rows(WALL_TAGS)),
    ("FLOORING", "Existing flooring", "Existing flooring of a space (MTQ)", _rows(FLOORINGS)),
    ("EXISTING_CONDITION", "Existing condition", "Condition of a space as found (MTQ)", _rows(EXISTING_CONDITIONS)),
)
