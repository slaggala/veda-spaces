"""Closed request schemas for the MTQ B2-B4 API (unknown fields → 422 UNKNOWN_FIELD; no free-form JSON).

Codes come from the frozen vocabularies (vocab.py); card option and input names are checked against the ruleset and
the rate card by the services, because they are data, not code.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field

from veda.kernel.dto import Closed, Id, optional_text, text

Code = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]
Tier = Literal["ESSENTIAL", "PREMIUM", "LUXURY"]
Necessity = Literal["MANDATORY", "RECOMMENDED", "OPTIONAL"]
Finish = Literal["LAMINATE", "ACRYLIC", "VENEER", "PU", "GLASS", "MEMBRANE", "CUSTOM"]
RequirementType = Literal[
    "WARDROBE", "TV_UNIT", "CROCKERY_UNIT", "STUDY_UNIT", "VANITY", "DRESSER", "KITCHEN", "KITCHEN_TALL_UNIT",
    "UTILITY_UNIT", "BED", "SIDE_TABLE", "STORAGE_UNIT", "FALSE_CEILING", "PROFILE_LIGHTING", "WALL_PANELLING",
    "MIRROR_PANEL", "CURTAIN_PELMET", "PARTITION", "POOJA_UNIT", "WINDOW_SEATING", "PAINTING", "ELECTRICAL",
    "ELECTRICAL_SHIFTING", "SENSOR_LIGHTING", "CUSTOM",
]  # fmt: skip
Reason = Annotated[str, text(500, min_len=3)]
OptionalReason = Annotated[str | None, optional_text(500)]
Notes = Annotated[str | None, optional_text(2000)]
InputValue = Annotated[Decimal, Field(ge=0, le=100_000, max_digits=12, decimal_places=4)]


class Preferences(Closed):
    options: dict[Code, Code] | None = Field(default=None, max_length=10)
    finish_code: Finish | None = None
    material_key: Annotated[str | None, Field(max_length=80, pattern=r"^[a-z][a-z0-9_.-]{1,79}$")] = None


class RequirementCreateIn(Closed):
    space_id: Id | None = None
    requirement_type_code: RequirementType
    custom_label: Annotated[str | None, optional_text(120)] = None
    necessity_code: Necessity = "RECOMMENDED"
    source_code: Literal["STAFF_SELECTION", "CUSTOMER_REQUEST", "MANUAL"]
    anchor_wall_index: Annotated[int | None, Field(ge=1, le=64)] = None
    preferences: Preferences | None = None
    notes: Notes = None
    reason: OptionalReason = None


class RequirementPatchIn(Closed):
    necessity_code: Necessity | None = None
    custom_label: Annotated[str | None, optional_text(120)] = None
    preferences: Preferences | None = None
    notes: Notes = None


class RequirementDecisionIn(Closed):
    status: Literal["ACCEPTED", "EXCLUDED", "NOT_APPLICABLE", "PROPOSED"]
    reason: OptionalReason = None


class ScopeCreateIn(Closed):
    tier_code: Tier = "ESSENTIAL"
    notes: Notes = None


class ScopeItemPatchIn(Closed):
    options: dict[Code, Code] | None = Field(default=None, max_length=10)
    finish_code: Finish | None = None
    material_key: Annotated[str | None, Field(max_length=80, pattern=r"^[a-z][a-z0-9_.-]{1,79}$")] = None
    inclusion_code: Literal["INCLUDED", "OPTIONAL", "EXCLUDED"] | None = None
    label: Annotated[str | None, optional_text(120)] = None
    notes: Notes = None
    dimension_overrides: dict[Code, InputValue] | None = Field(default=None, max_length=10)
    override_reason: OptionalReason = None


class ScopeItemCreateIn(RequirementCreateIn):
    """A manual or customer-requested item added straight to a draft: it is a requirement (accepted) plus its item."""


class BoqOverrideIn(Closed):
    quantity_centi: Annotated[int, Field(ge=0, le=10_000_000_00)]
    reason: Reason
