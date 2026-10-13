"""Closed request schemas for the MTQ B1 API (unknown fields → 422 UNKNOWN_FIELD; no free-form JSON anywhere).

Every JSON column is written only through one of these models: unknown keys are refused, numbers are bounded,
codes come from the frozen vocabularies (vocab.py).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from veda.kernel.dto import CalendarDate, Closed, Id, Query, optional_text, text

MM = Annotated[int, Field(ge=1, le=100_000)]  # a length on site: 1 mm .. 100 m
HEIGHT = Annotated[int, Field(ge=1, le=20_000)]
OFFSET = Annotated[int, Field(ge=0, le=100_000)]
CENTI = Annotated[int, Field(ge=0, le=100_000_00)]  # up to 100,000 sq ft in hundredths
ClientRef = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")]

PropertyType = Literal["APARTMENT", "INDEPENDENT_HOUSE"]
ProjectKind = Literal["NEW", "RENOVATION", "PARTIAL"]
Possession = Literal["UNDER_CONSTRUCTION", "READY", "OCCUPIED"]
Zone = Literal["INDOOR", "SEMI_OPEN", "OUTDOOR"]
PropertyTemplateKey = Literal[
    "APARTMENT_2BHK", "APARTMENT_3BHK", "APARTMENT_4BHK", "APARTMENT_5BHK", "INDEPENDENT_HOUSE"
]
SpaceType = Literal[
    "LIVING",
    "DINING",
    "LIVING_DINING",
    "FAMILY_LOUNGE",
    "FOYER",
    "PASSAGE",
    "STAIRCASE",
    "POOJA",
    "MASTER_BEDROOM",
    "BEDROOM",
    "CHILDREN_BEDROOM",
    "GUEST_BEDROOM",
    "PARENTS_BEDROOM",
    "SERVANT_ROOM",
    "DRESSING",
    "WALK_IN_CLOSET",
    "TOILET",
    "POWDER_ROOM",
    "STUDY",
    "HOME_OFFICE",
    "MEDIA_ROOM",
    "KITCHEN",
    "UTILITY",
    "STORE",
    "LAUNDRY",
    "BALCONY",
    "TERRACE",
    "SIT_OUT",
    "PORCH",
    "PARKING",
    "GARDEN",
    "CUSTOM",
]  # fmt: skip  (equal to vocab.SPACE_TYPES; tested)


class SpaceAttributes(Closed):
    """property_space.attributes: static facts about a space (blueprint §4.1). Survey readings go on the
    measurement (space_measurement.attributes)."""

    wet_area: bool | None = None
    has_false_ceiling_existing: bool | None = None


class PropertyCreateIn(Closed):
    lead_id: Id
    property_type_code: PropertyType
    project_kind_code: ProjectKind | None = None
    template_key: PropertyTemplateKey | None = None
    include_optional: Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=40)] = []
    configuration_label: Annotated[str | None, optional_text(40)] = None
    built_up_area_sqft_centi: CENTI | None = None
    carpet_area_sqft_centi: CENTI | None = None
    plot_area_sqft_centi: CENTI | None = None
    floor_count: Annotated[int, Field(ge=1, le=10)] | None = None
    address_line_1: Annotated[str | None, optional_text(200)] = None
    address_line_2: Annotated[str | None, optional_text(200)] = None
    locality: Annotated[str | None, optional_text(100)] = None
    city: Annotated[str | None, optional_text(100)] = None
    state: Annotated[str | None, optional_text(100)] = None
    pincode: Annotated[str | None, Field(pattern=r"^[1-9][0-9]{5}$")] = None
    geo_lat_e6: Annotated[int, Field(ge=-90_000_000, le=90_000_000)] | None = None
    geo_lng_e6: Annotated[int, Field(ge=-180_000_000, le=180_000_000)] | None = None
    possession_status_code: Possession | None = None
    possession_on: CalendarDate | None = None
    notes: Annotated[str | None, optional_text(2000)] = None

    @model_validator(mode="after")
    def _rules(self):
        if (self.geo_lat_e6 is None) != (self.geo_lng_e6 is None):
            raise ValueError("geo_lat_e6 and geo_lng_e6 go together")
        if self.template_key and not self.template_key.startswith(
            "APARTMENT" if self.property_type_code == "APARTMENT" else "INDEPENDENT"
        ):
            raise ValueError("the template does not match the property type")
        return self


class PropertyPatchIn(Closed):
    project_kind_code: ProjectKind | None = None
    configuration_label: Annotated[str | None, optional_text(40)] = None
    built_up_area_sqft_centi: CENTI | None = None
    carpet_area_sqft_centi: CENTI | None = None
    plot_area_sqft_centi: CENTI | None = None
    floor_count: Annotated[int, Field(ge=1, le=10)] | None = None
    address_line_1: Annotated[str | None, optional_text(200)] = None
    address_line_2: Annotated[str | None, optional_text(200)] = None
    locality: Annotated[str | None, optional_text(100)] = None
    city: Annotated[str | None, optional_text(100)] = None
    state: Annotated[str | None, optional_text(100)] = None
    pincode: Annotated[str | None, Field(pattern=r"^[1-9][0-9]{5}$")] = None
    geo_lat_e6: Annotated[int, Field(ge=-90_000_000, le=90_000_000)] | None = None
    geo_lng_e6: Annotated[int, Field(ge=-180_000_000, le=180_000_000)] | None = None
    possession_status_code: Possession | None = None
    possession_on: CalendarDate | None = None
    floor_plan_attachment_id: Id | None = None
    notes: Annotated[str | None, optional_text(2000)] = None


class PropertyListQuery(Query):
    lead_id: Id | None = None
    city: Annotated[str | None, Field(max_length=100)] = None
    property_type_code: PropertyType | None = None
    page: Annotated[int, Field(ge=1, le=10_000)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25


class SpaceCreateIn(Closed):
    space_type_code: SpaceType
    label: Annotated[str, text(80, min_len=1)]
    custom_type_label: Annotated[str | None, optional_text(60)] = None
    parent_space_id: Id | None = None
    level_index: Annotated[int, Field(ge=-3, le=10)] = 0
    zone_code: Zone | None = None
    sort_order: Annotated[int, Field(ge=0, le=100_000)] | None = None
    is_in_scope: bool = True
    attributes: SpaceAttributes = SpaceAttributes()


class SpacePatchIn(Closed):
    label: Annotated[str | None, optional_text(80)] = None
    custom_type_label: Annotated[str | None, optional_text(60)] = None
    parent_space_id: Id | None = None
    level_index: Annotated[int, Field(ge=-3, le=10)] | None = None
    zone_code: Zone | None = None
    is_in_scope: bool | None = None
    attributes: SpaceAttributes | None = None


class SpaceOrderIn(Closed):
    space_ids: Annotated[list[Id], Field(min_length=1, max_length=200)]


class SpacesFromTemplateIn(Closed):
    template_key: PropertyTemplateKey
    include_optional: Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=40)] = []


class SpaceDeleteIn(Closed):
    reason: Annotated[str | None, optional_text(500)] = None
