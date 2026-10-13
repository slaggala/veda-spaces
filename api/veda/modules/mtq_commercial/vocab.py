"""Frozen MTQ B2-B4 vocabularies (blueprint §4.2, §4.3; owner instruction VEDA-SPACES-MTQ-B2-B3-B4-END-TO-END).

One source for the CHECK constraints and the request schemas; the migrations carry their own copy, which a test keeps
equal to this module. Values are only ever added by a later migration, never renamed.
"""

from __future__ import annotations

TIERS = ("ESSENTIAL", "PREMIUM", "LUXURY")  # the rate card's package codes (customer labels are copy)

# --- B2 requirements ---------------------------------------------------------------------------------------------------
# What a requirement asks for. Each value maps to a catalogue-backed scope item type (rules.ITEM_TYPES); CUSTOM is a
# staff-described item with no catalogue mapping.
REQUIREMENT_TYPES = (
    "WARDROBE",
    "TV_UNIT",
    "CROCKERY_UNIT",
    "STUDY_UNIT",
    "VANITY",
    "DRESSER",
    "KITCHEN",
    "KITCHEN_TALL_UNIT",
    "UTILITY_UNIT",
    "BED",
    "SIDE_TABLE",
    "STORAGE_UNIT",
    "FALSE_CEILING",
    "PROFILE_LIGHTING",
    "WALL_PANELLING",
    "MIRROR_PANEL",
    "CURTAIN_PELMET",
    "PARTITION",
    "POOJA_UNIT",
    "WINDOW_SEATING",
    "PAINTING",
    "ELECTRICAL",
    "ELECTRICAL_SHIFTING",
    "SENSOR_LIGHTING",
    "CUSTOM",
)
# MANDATORY / RECOMMENDED / OPTIONAL is the recommendation strength; customer-requested is a source, excluded and
# not-applicable are decisions (status).
NECESSITIES = ("MANDATORY", "RECOMMENDED", "OPTIONAL")
REQUIREMENT_STATUSES = ("PROPOSED", "ACCEPTED", "EXCLUDED", "NOT_APPLICABLE")
REQUIREMENT_SOURCES = ("SURVEY_TEMPLATE", "MEASUREMENT_RULE", "STAFF_SELECTION", "CUSTOMER_REQUEST", "MANUAL")

# --- B2 scope ----------------------------------------------------------------------------------------------------------
SCOPE_STATUSES = ("DRAFT", "CONFIRMED", "SUPERSEDED")
# AUTO: a rule fired from measured facts (a tagged wall, a captured point). RECOMMENDED: a template recommendation.
# CUSTOMER_REQUESTED / MANUAL: added by staff. None of them is ever accepted without a staff decision.
ITEM_ORIGINS = ("AUTO", "RECOMMENDED", "CUSTOMER_REQUESTED", "MANUAL")
INCLUSIONS = ("INCLUDED", "OPTIONAL", "EXCLUDED")
DIMENSION_SOURCES = ("MEASURED", "DERIVED", "ASSUMED", "STAFF")
FINISHES = ("LAMINATE", "ACRYLIC", "VENEER", "PU", "GLASS", "MEMBRANE", "CUSTOM")

# --- B2 BOQ ------------------------------------------------------------------------------------------------------------
BOQ_STATUSES = ("GENERATED", "REVIEWED", "SUPERSEDED")
UOMS = ("SFT", "RFT", "NOS", "LUMP")  # the rate card's units (estimator UOMS); SQM/RMT are display conversions
# How a line's quantity was obtained: the rate card's own quantity spec (area / direct / count / lump), or a measured
# count when the item has no card line yet (UNMAPPED lines are kept and reported, never dropped).
FORMULA_KINDS = ("CARD_AREA", "CARD_DIRECT", "CARD_COUNT", "CARD_LUMP", "MEASURED_COUNT", "UNMAPPED")
LINE_STATUSES = ("OK", "ISSUE")
