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

# --- B3 estimate -------------------------------------------------------------------------------------------------------
ESTIMATE_STATUSES = ("DRAFT", "APPROVED", "SUPERSEDED")
PRICING_BASES = ("MEASURED", "MIXED")
# Approved cost/charge categories (instruction B3.5). The rate card's line rates are all-inclusive supply-and-install
# rates (ADR-012), so PRODUCT carries them; LABOUR and INSTALLATION exist for when a card prices them separately.
COMPONENTS = (
    "PRODUCT",
    "LABOUR",
    "INSTALLATION",
    "TRANSPORT",
    "SITE_PROTECTION",
    "ELECTRICAL_SHIFTING",
    "OTHER_SERVICE",
)
RATE_STATUSES = (
    "PRICED",
    "RATE_CARD_NOT_APPROVED",  # the tier has no approved staff rates (OI-MTQ-05)
    "FINISH_RATE_NOT_APPROVED",  # a finish variant without an approved rate (OI-MTQ-05)
    "CATALOGUE_MAPPING_MISSING",  # the item has no rate-card line (NEW LINE, OI-MTQ-05)
    "OWNER_DECISION_REQUIRED",  # e.g. the preparation package driver for 5 BHK or an independent house (OI-MTQ-15)
    "RATE_MISSING",  # the card in force has no such product, line or tier rate
    "QUANTITY_MISSING",
    "QUANTITY_BASIS_CHANGED",  # the pricing card measures this line differently from the BOQ's card
)
OWNER_DECISION_RATE_STATUSES = (
    "RATE_CARD_NOT_APPROVED",
    "FINISH_RATE_NOT_APPROVED",
    "CATALOGUE_MAPPING_MISSING",
    "OWNER_DECISION_REQUIRED",
)
TAX_STATUSES = ("GST_POLICY_REQUIRED", "APPLIED")
ADJUSTMENT_SCOPES = ("LINE", "CATEGORY", "PROJECT")
ADJUSTMENT_KINDS = ("PERCENT", "AMOUNT")
ADJUSTMENT_STATUSES = ("PROPOSED", "APPROVED", "REJECTED", "WITHDRAWN")
AUTHORITIES = ("WITHIN_LIMIT", "APPROVER")

# --- B4 quotation ------------------------------------------------------------------------------------------------------
# The instruction's lifecycle (B4.3); the blueprint's SENT is ISSUED here, and WITHDRAWN is not offered (no decision).
QUOTATION_STATUSES = (
    "DRAFT",
    "INTERNAL_REVIEW",
    "APPROVED",
    "ISSUED",
    "ACCEPTED",
    "REJECTED",
    "EXPIRED",
    "SUPERSEDED",
)
OPEN_QUOTATION_STATUSES = ("DRAFT", "INTERNAL_REVIEW", "APPROVED")  # still editable or about to be issued
QUOTATION_KINDS = ("BASE", "VARIATION")
SECTION_CODES = ("SPACE", "PROJECT", "OPTIONAL", "VARIATION")
CHANGE_CODES = (
    "NONE",
    "ADD",
    "OMIT",
    "CHANGE_QUANTITY",
    "CHANGE_MATERIAL",
    "CHANGE_FINISH",
    "CHANGE_RATE",
)
DECISION_METHODS = ("STAFF_RECORDED", "SIGNED_COPY")
QUOTATION_EVENTS = (
    "CREATED",
    "VERSION_CREATED",
    "VARIATION_CREATED",
    "EDITED",
    "SUBMITTED_FOR_REVIEW",
    "RETURNED_TO_DRAFT",
    "APPROVED",
    "ISSUED",
    "ACCEPTED",
    "REJECTED",
    "EXPIRED",
    "SUPERSEDED",
)
