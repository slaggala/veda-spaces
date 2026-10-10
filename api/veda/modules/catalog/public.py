"""The V3 public payloads and their content policy (canonical customer-copy and B1-B3 policy closures).

Every V3 response a customer receives is an explicit, strict, bounded DTO: unknown fields are refused, every string
and container has a maximum size, and nothing is typed `Any`, `object` or an unbounded dictionary or list.

**Payloads.** `PublicCatalog` is built from typed catalog records; `PublicEstimate` from the engine's stored result
and the release's card.

**Content policy.** Every field of every DTO has exactly one policy in PUBLIC_FIELD_POLICIES (eleven policies). A test
enumerates the fields and fails on an unpoliced field or a weak type; the inventory document is generated from the
registry. The primary controls are structural:
- Money appears only in ENGINE_GENERATED_AMOUNT fields: integers computed by the engine from the approved card, whose
  version the estimate names. No prose field may carry money, a rate or internal commercial wording.
- Measurements and typical-size assumptions are structured (a number, a unit enum and a type), never prose, so a
  quantity cannot be read as a rate.
- A claim is shown only as a GOVERNED_CLAIM_REFERENCE to an approved claim (or promise) record, checked for validity
  every time it is served (`claims.problems`).
- Estimator wording is CONTROLLED_LEGAL_COPY from an allowlist; card text is structured exclusion, client-scope or
  timeline copy from the versioned card.

**One checker.** `check_payload` applies each field's policy, with the canonical checks of `text` as defence in
depth, in release validation and in every serialiser at serve time.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from typing import Annotated, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from veda.modules.estimator import engine

from . import kinds, text

# --- content policies -------------------------------------------------------------------------------------------------
FACTUAL_TEXT = "FACTUAL_TEXT"  # descriptive prose: no claim, promise, money, duration or contact detail
GOVERNED_CLAIM_REFERENCE = "GOVERNED_CLAIM_REFERENCE"  # the approved text of a valid claim or promise record
ENGINE_GENERATED_AMOUNT = "ENGINE_GENERATED_AMOUNT"  # an integer computed by the engine from the approved card
STRUCTURED_MEASUREMENT = "STRUCTURED_MEASUREMENT"  # a number, a unit enum or a measurement type
STRUCTURED_TIMELINE = "STRUCTURED_TIMELINE"  # day ranges and the card's versioned timeline wording
STRUCTURED_ASSUMPTION = "STRUCTURED_ASSUMPTION"  # a typical-size assumption's parts (rendered by the page)
STRUCTURED_EXCLUSION = "STRUCTURED_EXCLUSION"  # the card's versioned exclusion items
STRUCTURED_CLIENT_SCOPE = "STRUCTURED_CLIENT_SCOPE"  # the card's versioned client-scope items
CONTROLLED_LEGAL_COPY = "CONTROLLED_LEGAL_COPY"  # allowlisted estimator wording or an approved non-claim copy record
STAFF_ONLY = "STAFF_ONLY"  # never in a public DTO (the registry holds none; a test proves it)
IDENTIFIER = "IDENTIFIER"  # keys, codes, enums, flags, ordering, hashes, dates, URLs: not prose
POLICIES = (FACTUAL_TEXT, GOVERNED_CLAIM_REFERENCE, ENGINE_GENERATED_AMOUNT, STRUCTURED_MEASUREMENT,
            STRUCTURED_TIMELINE, STRUCTURED_ASSUMPTION, STRUCTURED_EXCLUSION, STRUCTURED_CLIENT_SCOPE,
            CONTROLLED_LEGAL_COPY, STAFF_ONLY, IDENTIFIER)  # fmt: skip
STRUCTURED_TEXT = (STRUCTURED_TIMELINE, STRUCTURED_ASSUMPTION, STRUCTURED_EXCLUSION, STRUCTURED_CLIENT_SCOPE)
TEXT_POLICIES = (FACTUAL_TEXT, GOVERNED_CLAIM_REFERENCE, CONTROLLED_LEGAL_COPY, *STRUCTURED_TEXT)
# The estimator wording a V3 estimate may carry (CONTROLLED_LEGAL_COPY): exactly these engine texts.
CONTROLLED_ESTIMATOR_TEXT = frozenset({engine.TITLE, engine.DISCLAIMER, engine.PREP_PACKAGE, engine.PREP_DESCRIPTION,
                                       engine.ALLOWANCE, engine.ALLOWANCE_DESCRIPTION})  # fmt: skip
# Measurement types (Phase 3): only the first four may be public; a rate or total amount is never a measurement.
MEASUREMENT_TYPES = ("QUANTITY", "DIMENSION", "AREA", "LENGTH", "RATE", "TOTAL_AMOUNT")
PublicMeasurementType = Literal["QUANTITY", "DIMENSION", "AREA", "LENGTH"]
PublicUnit = Literal["FT", "SQ_FT", "NOS"]
_ENGINE_UNITS: dict[str, tuple[PublicMeasurementType, PublicUnit]] = {
    "ft": ("LENGTH", "FT"),
    "sq ft": ("AREA", "SQ_FT"),
    "nos": ("QUANTITY", "NOS"),
}
# Claim categories as served (a closed set; a test proves it equals text.CATEGORIES).
ClaimTag = Literal[
    "ranking", "price", "popularity", "recommendation", "quality", "certification", "award", "warranty", "service",
    "durability", "environmental", "promotional", "urgency",
]  # fmt: skip

S30 = Annotated[str, Field(max_length=30)]
S60 = Annotated[str, Field(max_length=60)]
S120 = Annotated[str, Field(max_length=120)]
S300 = Annotated[str, Field(max_length=300)]
S500 = Annotated[str, Field(max_length=500)]
K = Annotated[str, Field(max_length=100, pattern=r"^[a-z][a-z0-9_.-]{1,99}$")]
CODE = Annotated[str, Field(max_length=40, pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]
SHA = Annotated[str, Field(max_length=64, pattern=r"^[0-9a-f]{64}$")]
URL = Annotated[str, Field(max_length=300)]
HomeSize = Literal["1BHK", "2BHK", "3BHK", "4BHK", "CUSTOM"]
ProjectKind = Literal["NEW_HOME", "RENOVATION"]
PackageCode = Literal["ESSENTIAL", "PREMIUM", "LUXURY"]
Sort = Annotated[int, Field(ge=0, le=100000)]
Minor = Annotated[int, Field(ge=0, le=10_000_000_000)]


class _Dto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


# --- the public catalog ---------------------------------------------------------------------------------------------
class PublicAvailability(_Dto):
    project_kinds: tuple[ProjectKind, ...] = Field(default=(), max_length=2)


class PublicPropertyType(_Dto):
    name: S120
    code: Literal["APARTMENT", "VILLA"]
    sort: Sort


class PublicRoomSlot(_Dto):
    room_template: K
    default_selected: bool


class PublicHome(_Dto):
    name: S120
    description: S500 | None = None
    property_type: K
    home_size: HomeSize
    rooms: tuple[PublicRoomSlot, ...] = Field(max_length=20)
    packages: tuple[K, ...] = Field(max_length=6)
    availability: PublicAvailability
    sort: Sort


class PublicProductSlot(_Dto):
    product: K
    variant: K
    options: dict[K, K] = Field(max_length=10)
    removable: bool


class _Described(_Dto):
    name: S120
    description: S500 | None = None
    what_is_this: S500 | None = None
    typically_used_for: S500 | None = None
    sort: Sort


class PublicRoom(_Described):
    room_code: CODE
    image: K | None = None
    gallery: K | None = None
    included: tuple[PublicProductSlot, ...] = Field(max_length=12)
    extras: tuple[K, ...] = Field(max_length=12)


class PublicMeasurement(_Dto):
    input: CODE
    label: S120
    unit: Literal["ft", "sqft"]
    min: float
    max: float
    hint: S500 | None = None


class PublicChoice(_Described):
    key: K
    materials: tuple[K, ...] = Field(max_length=6)
    media: tuple[K, ...] = Field(max_length=6)


class PublicOptionGroup(_Dto):
    key: K
    name: S120
    description: S500 | None = None
    default: K
    choices: tuple[PublicChoice, ...] = Field(max_length=12)


class PublicVariant(_Described):
    key: K
    media: tuple[K, ...] = Field(max_length=6)
    option_groups: tuple[PublicOptionGroup, ...] = Field(max_length=6)
    measurements: tuple[PublicMeasurement, ...] = Field(max_length=6)


class PublicFamily(_Described):
    pass


class PublicProduct(_Described):
    family: K
    media: tuple[K, ...] = Field(max_length=12)
    variants: tuple[PublicVariant, ...] = Field(max_length=8)


class PublicExtra(_Described):
    kind: Literal["room_extra", "product_extra", "package_extra"]
    quantity: Literal["fixed", "count", "measured"]
    max_count: Annotated[int, Field(ge=1, le=10)]
    default_selected: bool
    media: tuple[K, ...] = Field(max_length=6)
    measurements: tuple[PublicMeasurement, ...] = Field(default=(), max_length=6)


class PublicPackage(_Described):
    engine_package: PackageCode
    public_summary: K
    badge: K | None = None
    recommended: bool
    consultation_only: bool
    included_products: tuple[K, ...] = Field(max_length=200)
    optional_products: tuple[K, ...] = Field(max_length=200)
    included_extras: tuple[K, ...] = Field(max_length=200)
    excluded_extras: tuple[K, ...] = Field(max_length=200)


class PublicMaterial(_Described):
    statements: tuple[K, ...] = Field(max_length=6)
    finish: S120 | None = None
    colour_family: S120 | None = None
    texture: S120 | None = None


class PublicHardware(_Described):
    statements: tuple[K, ...] = Field(max_length=6)


class PublicMediaUrls(_Dto):
    thumb: URL | None = None
    mobile: URL | None = None
    desktop: URL | None = None


class PublicMedia(_Dto):
    type: Literal["IMAGE", "GALLERY", "EXTERNAL_EMBED"]  # 3D and video never reach customers
    title: S120
    alt: S500 | None = None
    caption: S500 | None = None
    label: Literal["Design reference", "Illustrative example"]
    attribution: S120
    items: tuple[K, ...] = Field(max_length=24)
    embed_url: URL | None = None
    urls: PublicMediaUrls
    sort: Sort


CopyCategory = Literal["description", "package", "allowance", "warranty", "material", "hardware", "inclusion",
                       "exclusion", "assumption", "disclaimer", "next_step", "label", "badge"]  # fmt: skip


class PublicCopy(_Dto):
    """An approved copy record that makes no claim (factual or controlled legal copy)."""

    statement: S500
    category: CopyCategory


class PublicClaim(_Dto):
    """An approved, currently valid governed claim (a claim record or a promise record)."""

    statement: S500
    category: CopyCategory
    claim_categories: tuple[ClaimTag, ...] = Field(max_length=13)


class PublicCondition(_Dto):
    property_types: tuple[Literal["APARTMENT", "VILLA"], ...] = Field(default=(), max_length=2)
    home_sizes: tuple[HomeSize, ...] = Field(default=(), max_length=5)
    project_kinds: tuple[ProjectKind, ...] = Field(default=(), max_length=2)
    packages: tuple[PackageCode, ...] = Field(default=(), max_length=3)


# The authoritative reference-path pattern (kinds.RefPath), bounded for the public DTO.
REF = Annotated[str, Field(max_length=310, pattern=kinds.REF_PATH_PATTERN)]
Bound = Annotated[float, Field(gt=0, le=10000)]


class PublicRule(_Dto):
    type: Literal["requires", "excludes", "compatible_with", "available_only_for", "hidden_when", "default_when",
                  "measurement_bounds", "requires_consultation", "unavailable_online"]  # fmt: skip
    subject: REF
    objects: tuple[REF, ...] = Field(max_length=12)
    condition: PublicCondition | None = None
    input: CODE | None = None
    min: Bound | None = None
    max: Bound | None = None
    message: K | None = None


class PublicCatalog(_Dto):
    release: S60
    manifest_sha256: SHA
    property_type: dict[K, PublicPropertyType] = Field(max_length=10)
    home_config: dict[K, PublicHome] = Field(max_length=50)
    room_template: dict[K, PublicRoom] = Field(max_length=200)
    product_family: dict[K, PublicFamily] = Field(max_length=200)
    product: dict[K, PublicProduct] = Field(max_length=1000)
    extra: dict[K, PublicExtra] = Field(max_length=1000)
    material: dict[K, PublicMaterial] = Field(max_length=1000)
    hardware: dict[K, PublicHardware] = Field(max_length=1000)
    package: dict[K, PublicPackage] = Field(max_length=10)
    media: dict[K, PublicMedia] = Field(max_length=2000)
    copy_: dict[K, PublicCopy] = Field(max_length=2000, alias="copy")
    claim: dict[K, PublicClaim] = Field(max_length=500)
    rule: dict[K, PublicRule] = Field(max_length=1000)

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, populate_by_name=True)


# --- the public estimate --------------------------------------------------------------------------------------------
class PublicRange(_Dto):
    low_minor: Minor
    high_minor: Minor
    currency: Literal["INR"]


class PublicGst(_Dto):
    pct: Annotated[float, Field(ge=0, le=100)]
    low_minor: Minor
    high_minor: Minor


class PublicRoomTotal(_Dto):
    room: CODE
    label: S120
    amount_minor: Minor


class PublicPreparation(_Dto):
    label: S120
    description: S500
    amount_minor: Minor
    inclusions: tuple[S500, ...] = Field(max_length=24)


class PublicAllowance(_Dto):
    label: S120
    description: S500
    low_minor: Minor
    high_minor: Minor


class PublicTimeline(_Dto):
    label: S120
    min_days: Annotated[int, Field(ge=1, le=1000)]
    max_days: Annotated[int, Field(ge=1, le=1000)]


class PublicAssumption(_Dto):
    """A typical size the estimate assumed, as structured parts: the page renders "Living room – TV unit: typical
    TV wall width assumed: 8 ft". A quantity or area can never be read as a rate."""

    room: CODE
    room_label: S60
    item: CODE
    item_label: S120
    instance: Annotated[int, Field(ge=1, le=12)]
    measurement: CODE
    measurement_label: S120
    measurement_type: PublicMeasurementType
    value: Annotated[float, Field(ge=0, le=100000)]
    unit: PublicUnit
    basis: Literal["TYPICAL_ASSUMPTION"]


class PublicSpecification(_Dto):
    spec_code: S60
    name: S120


class PublicEstimate(_Dto):
    title: S120
    disclaimer: S500
    package: PackageCode
    property_type: Literal["APARTMENT", "VILLA"]
    home_size: HomeSize
    range: PublicRange
    gst: PublicGst
    rooms: tuple[PublicRoomTotal, ...] = Field(max_length=40)
    project_preparation: PublicPreparation
    custom_features_allowance: PublicAllowance
    timeline: PublicTimeline
    assumptions: tuple[PublicAssumption, ...] = Field(max_length=200)
    exclusions: tuple[S500, ...] = Field(max_length=80)
    client_scope: tuple[S500, ...] = Field(max_length=80)
    pricing_card_version: S60  # the approved card every amount and the scope copy come from
    validity_days: Annotated[int, Field(ge=1, le=90)]
    expires_on: S30
    reference: S30
    configuration_reference: S30
    catalog_release: S60
    specification: PublicSpecification | None = None


# Every field of every public DTO (declaring class, field) -> its one content policy. The inventory and tests read it.
PUBLIC_FIELD_POLICIES: dict[tuple[str, str], str] = {
    ("_Described", "name"): FACTUAL_TEXT,
    ("_Described", "description"): FACTUAL_TEXT,
    ("_Described", "what_is_this"): FACTUAL_TEXT,
    ("_Described", "typically_used_for"): FACTUAL_TEXT,
    ("_Described", "sort"): IDENTIFIER,
    ("PublicAvailability", "project_kinds"): IDENTIFIER,
    ("PublicPropertyType", "name"): FACTUAL_TEXT,
    ("PublicPropertyType", "code"): IDENTIFIER,
    ("PublicPropertyType", "sort"): IDENTIFIER,
    ("PublicRoomSlot", "room_template"): IDENTIFIER,
    ("PublicRoomSlot", "default_selected"): IDENTIFIER,
    ("PublicHome", "name"): FACTUAL_TEXT,
    ("PublicHome", "description"): FACTUAL_TEXT,
    ("PublicHome", "property_type"): IDENTIFIER,
    ("PublicHome", "home_size"): IDENTIFIER,
    ("PublicHome", "rooms"): IDENTIFIER,
    ("PublicHome", "packages"): IDENTIFIER,
    ("PublicHome", "availability"): IDENTIFIER,
    ("PublicHome", "sort"): IDENTIFIER,
    ("PublicProductSlot", "product"): IDENTIFIER,
    ("PublicProductSlot", "variant"): IDENTIFIER,
    ("PublicProductSlot", "options"): IDENTIFIER,
    ("PublicProductSlot", "removable"): IDENTIFIER,
    ("PublicRoom", "room_code"): IDENTIFIER,
    ("PublicRoom", "image"): IDENTIFIER,
    ("PublicRoom", "gallery"): IDENTIFIER,
    ("PublicRoom", "included"): IDENTIFIER,
    ("PublicRoom", "extras"): IDENTIFIER,
    ("PublicMeasurement", "input"): IDENTIFIER,
    ("PublicMeasurement", "label"): FACTUAL_TEXT,
    ("PublicMeasurement", "unit"): STRUCTURED_MEASUREMENT,
    ("PublicMeasurement", "min"): STRUCTURED_MEASUREMENT,
    ("PublicMeasurement", "max"): STRUCTURED_MEASUREMENT,
    ("PublicMeasurement", "hint"): FACTUAL_TEXT,
    ("PublicChoice", "key"): IDENTIFIER,
    ("PublicChoice", "materials"): IDENTIFIER,
    ("PublicChoice", "media"): IDENTIFIER,
    ("PublicOptionGroup", "key"): IDENTIFIER,
    ("PublicOptionGroup", "name"): FACTUAL_TEXT,
    ("PublicOptionGroup", "description"): FACTUAL_TEXT,
    ("PublicOptionGroup", "default"): IDENTIFIER,
    ("PublicOptionGroup", "choices"): IDENTIFIER,
    ("PublicVariant", "key"): IDENTIFIER,
    ("PublicVariant", "media"): IDENTIFIER,
    ("PublicVariant", "option_groups"): IDENTIFIER,
    ("PublicVariant", "measurements"): IDENTIFIER,
    ("PublicProduct", "family"): IDENTIFIER,
    ("PublicProduct", "media"): IDENTIFIER,
    ("PublicProduct", "variants"): IDENTIFIER,
    ("PublicExtra", "kind"): IDENTIFIER,
    ("PublicExtra", "quantity"): IDENTIFIER,
    ("PublicExtra", "max_count"): STRUCTURED_MEASUREMENT,
    ("PublicExtra", "default_selected"): IDENTIFIER,
    ("PublicExtra", "media"): IDENTIFIER,
    ("PublicExtra", "measurements"): IDENTIFIER,
    ("PublicPackage", "engine_package"): IDENTIFIER,
    ("PublicPackage", "public_summary"): IDENTIFIER,
    ("PublicPackage", "badge"): IDENTIFIER,
    ("PublicPackage", "recommended"): IDENTIFIER,
    ("PublicPackage", "consultation_only"): IDENTIFIER,
    ("PublicPackage", "included_products"): IDENTIFIER,
    ("PublicPackage", "optional_products"): IDENTIFIER,
    ("PublicPackage", "included_extras"): IDENTIFIER,
    ("PublicPackage", "excluded_extras"): IDENTIFIER,
    ("PublicMaterial", "statements"): IDENTIFIER,
    ("PublicMaterial", "finish"): FACTUAL_TEXT,
    ("PublicMaterial", "colour_family"): FACTUAL_TEXT,
    ("PublicMaterial", "texture"): FACTUAL_TEXT,
    ("PublicHardware", "statements"): IDENTIFIER,
    ("PublicMediaUrls", "thumb"): IDENTIFIER,
    ("PublicMediaUrls", "mobile"): IDENTIFIER,
    ("PublicMediaUrls", "desktop"): IDENTIFIER,
    ("PublicMedia", "type"): IDENTIFIER,
    ("PublicMedia", "title"): FACTUAL_TEXT,
    ("PublicMedia", "alt"): FACTUAL_TEXT,
    ("PublicMedia", "caption"): FACTUAL_TEXT,
    ("PublicMedia", "label"): IDENTIFIER,
    ("PublicMedia", "attribution"): FACTUAL_TEXT,
    ("PublicMedia", "items"): IDENTIFIER,
    ("PublicMedia", "embed_url"): IDENTIFIER,
    ("PublicMedia", "urls"): IDENTIFIER,
    ("PublicMedia", "sort"): IDENTIFIER,
    ("PublicCopy", "statement"): CONTROLLED_LEGAL_COPY,
    ("PublicCopy", "category"): IDENTIFIER,
    ("PublicClaim", "statement"): GOVERNED_CLAIM_REFERENCE,
    ("PublicClaim", "category"): IDENTIFIER,
    ("PublicClaim", "claim_categories"): IDENTIFIER,
    ("PublicCondition", "property_types"): IDENTIFIER,
    ("PublicCondition", "home_sizes"): IDENTIFIER,
    ("PublicCondition", "project_kinds"): IDENTIFIER,
    ("PublicCondition", "packages"): IDENTIFIER,
    ("PublicRule", "type"): IDENTIFIER,
    ("PublicRule", "subject"): IDENTIFIER,
    ("PublicRule", "objects"): IDENTIFIER,
    ("PublicRule", "condition"): IDENTIFIER,
    ("PublicRule", "input"): IDENTIFIER,
    ("PublicRule", "min"): STRUCTURED_MEASUREMENT,
    ("PublicRule", "max"): STRUCTURED_MEASUREMENT,
    ("PublicRule", "message"): IDENTIFIER,
    ("PublicCatalog", "release"): IDENTIFIER,
    ("PublicCatalog", "manifest_sha256"): IDENTIFIER,
    ("PublicCatalog", "property_type"): IDENTIFIER,
    ("PublicCatalog", "home_config"): IDENTIFIER,
    ("PublicCatalog", "room_template"): IDENTIFIER,
    ("PublicCatalog", "product_family"): IDENTIFIER,
    ("PublicCatalog", "product"): IDENTIFIER,
    ("PublicCatalog", "extra"): IDENTIFIER,
    ("PublicCatalog", "material"): IDENTIFIER,
    ("PublicCatalog", "hardware"): IDENTIFIER,
    ("PublicCatalog", "package"): IDENTIFIER,
    ("PublicCatalog", "media"): IDENTIFIER,
    ("PublicCatalog", "copy_"): IDENTIFIER,
    ("PublicCatalog", "claim"): IDENTIFIER,
    ("PublicCatalog", "rule"): IDENTIFIER,
    ("PublicRange", "low_minor"): ENGINE_GENERATED_AMOUNT,
    ("PublicRange", "high_minor"): ENGINE_GENERATED_AMOUNT,
    ("PublicRange", "currency"): IDENTIFIER,
    ("PublicGst", "pct"): IDENTIFIER,
    ("PublicGst", "low_minor"): ENGINE_GENERATED_AMOUNT,
    ("PublicGst", "high_minor"): ENGINE_GENERATED_AMOUNT,
    ("PublicRoomTotal", "room"): IDENTIFIER,
    ("PublicRoomTotal", "label"): FACTUAL_TEXT,
    ("PublicRoomTotal", "amount_minor"): ENGINE_GENERATED_AMOUNT,
    ("PublicPreparation", "label"): CONTROLLED_LEGAL_COPY,
    ("PublicPreparation", "description"): CONTROLLED_LEGAL_COPY,
    ("PublicPreparation", "amount_minor"): ENGINE_GENERATED_AMOUNT,
    ("PublicPreparation", "inclusions"): FACTUAL_TEXT,
    ("PublicAllowance", "label"): CONTROLLED_LEGAL_COPY,
    ("PublicAllowance", "description"): CONTROLLED_LEGAL_COPY,
    ("PublicAllowance", "low_minor"): ENGINE_GENERATED_AMOUNT,
    ("PublicAllowance", "high_minor"): ENGINE_GENERATED_AMOUNT,
    ("PublicTimeline", "label"): STRUCTURED_TIMELINE,
    ("PublicTimeline", "min_days"): STRUCTURED_TIMELINE,
    ("PublicTimeline", "max_days"): STRUCTURED_TIMELINE,
    ("PublicAssumption", "room"): IDENTIFIER,
    ("PublicAssumption", "room_label"): FACTUAL_TEXT,
    ("PublicAssumption", "item"): IDENTIFIER,
    ("PublicAssumption", "item_label"): STRUCTURED_ASSUMPTION,
    ("PublicAssumption", "instance"): STRUCTURED_ASSUMPTION,
    ("PublicAssumption", "measurement"): IDENTIFIER,
    ("PublicAssumption", "measurement_label"): STRUCTURED_ASSUMPTION,
    ("PublicAssumption", "measurement_type"): STRUCTURED_MEASUREMENT,
    ("PublicAssumption", "value"): STRUCTURED_MEASUREMENT,
    ("PublicAssumption", "unit"): STRUCTURED_MEASUREMENT,
    ("PublicAssumption", "basis"): STRUCTURED_ASSUMPTION,
    ("PublicSpecification", "spec_code"): IDENTIFIER,
    ("PublicSpecification", "name"): FACTUAL_TEXT,
    ("PublicEstimate", "title"): CONTROLLED_LEGAL_COPY,
    ("PublicEstimate", "disclaimer"): CONTROLLED_LEGAL_COPY,
    ("PublicEstimate", "package"): IDENTIFIER,
    ("PublicEstimate", "property_type"): IDENTIFIER,
    ("PublicEstimate", "home_size"): IDENTIFIER,
    ("PublicEstimate", "range"): IDENTIFIER,
    ("PublicEstimate", "gst"): IDENTIFIER,
    ("PublicEstimate", "rooms"): IDENTIFIER,
    ("PublicEstimate", "project_preparation"): IDENTIFIER,
    ("PublicEstimate", "custom_features_allowance"): IDENTIFIER,
    ("PublicEstimate", "timeline"): IDENTIFIER,
    ("PublicEstimate", "assumptions"): IDENTIFIER,
    ("PublicEstimate", "exclusions"): STRUCTURED_EXCLUSION,
    ("PublicEstimate", "client_scope"): STRUCTURED_CLIENT_SCOPE,
    ("PublicEstimate", "pricing_card_version"): IDENTIFIER,
    ("PublicEstimate", "validity_days"): IDENTIFIER,
    ("PublicEstimate", "expires_on"): IDENTIFIER,
    ("PublicEstimate", "reference"): IDENTIFIER,
    ("PublicEstimate", "configuration_reference"): IDENTIFIER,
    ("PublicEstimate", "catalog_release"): IDENTIFIER,
    ("PublicEstimate", "specification"): IDENTIFIER,
}
PUBLIC_FIELD_CLASSES = PUBLIC_FIELD_POLICIES  # the earlier name
ROOTS: tuple[type[BaseModel], ...] = (PublicCatalog, PublicEstimate)


def fields(roots: Iterable[type[BaseModel]] = ROOTS) -> set[tuple[str, str]]:
    """Every (declaring DTO, field) under the roots: all fields, not only text."""
    found: set[tuple[str, str]] = set()
    seen: set[type[BaseModel]] = set()
    pending = list(roots)
    while pending:
        cls = pending.pop()
        if cls in seen:
            continue
        seen.add(cls)
        for name, info in cls.model_fields.items():
            found.add((text.declaring_class(cls, name), name))
            pending.extend(text._models(info.annotation))
    return found


def policy_of(model: BaseModel, name: str) -> str:
    key = (text.declaring_class(type(model), name), name)
    if key not in PUBLIC_FIELD_POLICIES:
        raise KeyError(f"public field {key} has no content policy")  # fails closed (and the inventory test fails first)
    return PUBLIC_FIELD_POLICIES[key]


def values(model: BaseModel, prefix: str = "") -> Iterator[tuple[str, object, str]]:
    """(path, value, policy) for every scalar in a public DTO."""
    for name in type(model).model_fields:
        value = getattr(model, name)
        if value is None:
            continue
        path = f"{prefix}{name}"
        children = value.values() if isinstance(value, dict) else value if isinstance(value, tuple) else [value]
        keys = list(value) if isinstance(value, dict) else range(len(value)) if isinstance(value, tuple) else [None]
        for k, child in zip(keys, children, strict=True):
            sub = path if k is None else f"{path}.{k}"
            if isinstance(child, BaseModel):
                yield from values(child, f"{sub}.")
            else:
                yield sub, child, policy_of(model, name)


def strings(model: BaseModel, prefix: str = "") -> Iterator[tuple[str, str, str]]:
    """(path, text, policy) for every string in a public DTO."""
    for where, value, policy in values(model, prefix):
        if isinstance(value, str):
            yield where, value, policy


# --- the one checker --------------------------------------------------------------------------------------------------
def _claims_problem(where: str, value: str) -> str | None:
    claims = text.claims_in(value)
    return f"{where}: makes a {', '.join(claims)} claim; it must reference a governed claim record" if claims else None


def check_text(where: str, value: str, policy: str, *, records: dict[str, kinds.Copy] | None = None,
               copy_key: str | None = None) -> list[str]:  # fmt: skip
    """The checks for one customer-visible string under its content policy. Messages name the field, never the text."""
    if policy not in TEXT_POLICIES:
        return [] if policy in (IDENTIFIER, STRUCTURED_MEASUREMENT) else [f"{where}: text in a {policy} field"]
    problems = []
    if text.invisible_chars(value):
        problems.append(f"{where}: contains invisible or formatting characters")
    if text.mixed_script_words(value):
        problems.append(f"{where}: contains words that mix scripts")
    record = (records or {}).get(copy_key or "") if copy_key else None
    effective = policy
    if policy == CONTROLLED_LEGAL_COPY and record is not None and record.policy == "FACTUAL_TEXT":
        effective = FACTUAL_TEXT  # a factual copy record is held to the factual rule wherever it is shown
    what = text.forbidden_in(value) if effective == FACTUAL_TEXT else text.leak_in(value)
    if what:
        problems.append(f"{where}: contains {what}; no money in customer prose")
    if effective == FACTUAL_TEXT:
        if text.promise_in(value):
            problems.append(f"{where}: factual text makes a promise")
        problem = _claims_problem(where, value)
        if problem:
            problems.append(problem)
    elif policy in (CONTROLLED_LEGAL_COPY, *STRUCTURED_TEXT):
        problem = _claims_problem(where, value)
        if problem:
            problems.append(problem)
    if policy == CONTROLLED_LEGAL_COPY:
        if copy_key is None:
            if value not in CONTROLLED_ESTIMATOR_TEXT:
                problems.append(f"{where}: estimator wording that is not on the controlled allowlist")
        elif record is None or record.claim is not None or record.promise:
            problems.append(f"{where}: not an approved non-claim copy record of this release")
        elif text.canonical(record.statement) != text.canonical(value):
            problems.append(f"{where}: the served text is not the approved copy")
    if policy == GOVERNED_CLAIM_REFERENCE:
        if record is None or not (record.claim is not None or record.promise):
            problems.append(f"{where}: not a governed claim record of this release")
        elif text.canonical(record.statement) != text.canonical(value):
            problems.append(f"{where}: the served text is not the approved claim text")
    return problems


def check_payload(model: BaseModel, *, records: dict[str, kinds.Copy] | None = None) -> list[str]:
    """Every value of a public DTO under its content policy (amounts are integers; text passes `check_text`)."""
    problems = []
    for where, value, policy in values(model):
        if policy == ENGINE_GENERATED_AMOUNT:
            if not isinstance(value, int) or isinstance(value, bool):
                problems.append(f"{where}: an amount that is not an engine-generated integer")
            continue
        if policy == STAFF_ONLY:
            problems.append(f"{where}: staff-only content in a public payload")
            continue
        if not isinstance(value, str):
            continue
        copy_key = None
        for prefix in ("copy_.", "claim."):
            if where.startswith(prefix):
                copy_key = where[len(prefix) : -len(".statement")]
        problems.extend(check_text(where, value, policy, records=records, copy_key=copy_key))
    return problems


def digest(payloads: Iterable[BaseModel]) -> str:
    """The SHA-256 of the canonical JSON of the payloads, recorded in the release and rechecked at activation."""
    blob = [p.model_dump(mode="json", by_alias=True) for p in payloads]
    return hashlib.sha256(json.dumps(blob, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# --- builders ---------------------------------------------------------------------------------------------------------
def _described(d: kinds.Described) -> dict:
    return {"name": d.name, "description": d.description, "what_is_this": d.what_is_this,
            "typically_used_for": d.typically_used_for, "sort": d.sort}  # fmt: skip


def _measures(prompts) -> tuple[PublicMeasurement, ...]:
    return tuple(PublicMeasurement(input=m.input, label=m.label, unit=m.unit, min=m.min, max=m.max, hint=m.hint)
                 for m in prompts)  # fmt: skip


def build_catalog(cat) -> PublicCatalog:  # cat: compile.Catalog (imported lazily to avoid a cycle)
    """The public catalog DTO from typed records: staff-only things removed with every reference to them, no pricing,
    no staff or specification fields, no 3D or video, only reachable media, copy reduced to its statement."""
    from . import compile as cc

    hidden = cc.hidden_paths(cat)

    def shown(prefix: str, key: str) -> bool:
        return f"{prefix}:{key}" not in hidden

    products: dict[str, PublicProduct] = {}
    for key, p in sorted(cat.of(kinds.Product).items()):
        if not shown("product", key):
            continue
        variants = []
        for v in p.variants:
            if cc._variant_hidden(hidden, key, v.key):
                continue
            groups = []
            for g in v.option_groups:
                choices = tuple(
                    PublicChoice(**_described(c), key=c.key, materials=tuple(c.materials), media=tuple(c.media))
                    for c in g.choices if not cc._choice_hidden(hidden, key, v.key, g.key, c.key)
                )  # fmt: skip
                if choices:
                    groups.append(PublicOptionGroup(key=g.key, name=g.name, description=g.description,
                                                    default=g.default, choices=choices))  # fmt: skip
            measures = _measures(v.measurements)
            variants.append(PublicVariant(**_described(v), key=v.key, media=tuple(v.media), option_groups=tuple(groups),
                                          measurements=measures))  # fmt: skip
        if variants:
            products[key] = PublicProduct(**_described(p), family=p.family, media=tuple(p.media),
                                          variants=tuple(variants))  # fmt: skip
    extras = {
        k: PublicExtra(
            **_described(e),
            kind=e.kind,
            quantity=e.quantity,
            max_count=e.max_count,
            default_selected=e.default_selected,
            media=tuple(e.media),
            measurements=_measures(e.measurements),
        )  # fmt: skip
        for k, e in sorted(cat.of(kinds.Extra).items())
        if shown("extra", k)
    }
    rooms = {
        k: PublicRoom(
            **_described(r),
            room_code=r.room_code,
            image=r.image,
            gallery=r.gallery,
            included=tuple(
                PublicProductSlot(product=s.product, variant=s.variant, options=dict(s.options), removable=s.removable)
                for s in r.included
                if s.product in products
            ),
            extras=tuple(x for x in r.extras if x in extras),
        )  # fmt: skip
        for k, r in sorted(cat.of(kinds.RoomTemplate).items())
        if shown("room", k)
    }
    packages = {
        k: PublicPackage(
            **_described(pk),
            engine_package=pk.engine_package,
            public_summary=pk.public_summary,
            badge=pk.badge,
            recommended=pk.recommended,
            consultation_only=pk.consultation_only,
            included_products=tuple(x for x in pk.included_products if x in products),
            optional_products=tuple(x for x in pk.optional_products if x in products),
            included_extras=tuple(x for x in pk.included_extras if x in extras),
            excluded_extras=tuple(x for x in pk.excluded_extras if x in extras),
        )  # fmt: skip
        for k, pk in sorted(cat.of(kinds.Package).items())
        if shown("package", k)
    }
    homes = {
        k: PublicHome(
            name=h.name,
            description=h.description,
            property_type=h.property_type,
            home_size=h.home_size,
            rooms=tuple(
                PublicRoomSlot(room_template=s.room_template, default_selected=s.default_selected)
                for s in h.rooms
                if s.room_template in rooms
            ),
            packages=tuple(x for x in h.packages if x in packages),
            availability=PublicAvailability(project_kinds=tuple(h.availability.project_kinds)),
            sort=h.sort,
        )  # fmt: skip
        for k, h in sorted(cat.of(kinds.HomeConfig).items())
        if shown("home", k)
    }
    view_for_reach = {
        "room_template": {k: {"image": r.image, "gallery": r.gallery} for k, r in rooms.items()},
        "product": {k: {"media": list(p.media), "variants": [{"media": list(v.media), "option_groups": [
            {"choices": [{"media": list(c.media)} for c in g.choices]} for g in v.option_groups]} for v in p.variants]}
            for k, p in products.items()},
        "extra": {k: {"media": list(e.media)} for k, e in extras.items()},
    }  # fmt: skip
    reachable = cc._reachable_media(cat, view_for_reach)
    media = {}
    for k, m in sorted(cat.of(kinds.Media).items()):
        if k not in reachable or m.type not in ("IMAGE", "GALLERY", "EXTERNAL_EMBED"):
            continue
        urls = {name: f"{cc.PUBLIC_MEDIA_PATH}{sha}" for name, sha in m.objects.variants.items()
                if name in ("thumb", "mobile", "desktop")}  # fmt: skip
        media[k] = PublicMedia(type=m.type, title=m.title, alt=m.alt, caption=m.caption, label=m.label,
                               attribution=m.attribution or m.rights.owner, items=tuple(m.items), embed_url=m.embed_url,
                               urls=PublicMediaUrls(**urls), sort=m.sort)  # fmt: skip
    # Media keys no longer shown are dropped from what refers to them (3D, video, unreachable).
    products = {k: p.model_copy(update={"media": tuple(x for x in p.media if x in media)}) for k, p in products.items()}
    extras = {k: e.model_copy(update={"media": tuple(x for x in e.media if x in media)}) for k, e in extras.items()}

    def described(kind: type[kinds.Described], cls: type[_Described], **extra_fields) -> dict:
        return {k: cls(**_described(m), **{f: fn(m) for f, fn in extra_fields.items()})
                for k, m in sorted(cat.of(kind).items()) if m.visibility == "customer"}  # fmt: skip

    return PublicCatalog(
        release=cat.release_code,
        manifest_sha256=cat.manifest_sha256,
        property_type={
            k: PublicPropertyType(name=m.name, code=m.code, sort=m.sort)
            for k, m in sorted(cat.of(kinds.PropertyType).items())
            if m.visibility == "customer"
        },  # fmt: skip
        home_config=homes,
        room_template=rooms,
        product_family=described(kinds.ProductFamily, PublicFamily),
        product=products,
        extra=extras,
        material=described(
            kinds.Material,
            PublicMaterial,
            statements=lambda m: tuple(m.statements),
            finish=lambda m: m.finish,
            colour_family=lambda m: m.colour_family,
            texture=lambda m: m.texture,
        ),  # fmt: skip
        hardware=described(kinds.Hardware, PublicHardware, statements=lambda m: tuple(m.statements)),
        package=packages,
        media=media,
        copy={
            k: PublicCopy(statement=m.statement, category=m.category)
            for k, m in sorted(cat.of(kinds.Copy).items())
            if m.claim is None and not m.promise
        },
        claim={
            k: PublicClaim(
                statement=m.statement,
                category=m.category,
                claim_categories=cast("tuple[ClaimTag, ...]", tuple(text.claims_in(m.statement))),
            )
            for k, m in sorted(cat.of(kinds.Copy).items())
            if m.claim is not None or m.promise
        },
        rule={
            k: PublicRule(
                type=r.type,
                subject=r.subject,
                objects=tuple(r.objects),
                condition=PublicCondition(
                    property_types=tuple(r.condition.property_types),
                    home_sizes=tuple(r.condition.home_sizes),
                    project_kinds=tuple(r.condition.project_kinds),
                    packages=tuple(r.condition.packages),
                )
                if r.condition
                else None,
                input=r.input,
                min=r.min,
                max=r.max,
                message=r.message,
            )
            for k, r in sorted(cat.of(kinds.Rule).items())
            if r.type != "staff_only" and r.subject not in hidden
        },  # fmt: skip
    )


def _assumptions(result: dict, card) -> tuple[PublicAssumption, ...]:
    """Structured typical-size assumptions from the engine's assumption details (never its prose)."""
    labels = {p.code: (p.label, {i.name: i.label for i in p.inputs}) for p in card.products}
    out = []
    for a in result.get("assumption_details", []):
        item_label, inputs = labels.get(a["product"], (a["product"], {}))
        kind, unit = _ENGINE_UNITS[a["unit"]]
        out.append(PublicAssumption(room=a["room"], room_label=engine.ROOMS.get(a["room"], a["room"]),
                                    item=a["product"], item_label=item_label, instance=int(a["instance"]),
                                    measurement=a["input"], measurement_label=inputs.get(a["input"], a["input"]),
                                    measurement_type=kind, value=float(a["value"]), unit=unit,
                                    basis="TYPICAL_ASSUMPTION"))  # fmt: skip
    return tuple(out)


def build_estimate(result: dict, *, card, reference: str, expires_on: str, configuration_reference: str,
                   catalog_release: str, specification: dict | None) -> PublicEstimate:  # fmt: skip
    """The public estimate DTO from the engine's stored result (the staff view) and the card that priced it: customer
    fields only, amounts as engine integers (room amounts rounded for customers), assumptions structured, nothing else
    (no line, rate, component amount, warranty block or workflow state)."""
    prep, allowance, timeline = result["project_preparation"], result["custom_features_allowance"], result["timeline"]
    return PublicEstimate(
        title=result["title"], disclaimer=result["disclaimer"], package=result["package"],
        property_type=result["property_type"], home_size=result["home_size"],
        range=PublicRange(low_minor=result["range"]["low_minor"], high_minor=result["range"]["high_minor"],
                          currency=result["range"]["currency"]),
        gst=PublicGst(pct=float(result["gst"]["pct"]), low_minor=result["gst"]["low_minor"],
                      high_minor=result["gst"]["high_minor"]),
        rooms=tuple(PublicRoomTotal(room=r["room"], label=r["label"], amount_minor=engine.customer_amount(r["amount_minor"]))
                    for r in result["rooms"]),
        project_preparation=PublicPreparation(label=prep["label"], description=prep["description"],
                                              amount_minor=prep["amount_minor"], inclusions=tuple(prep["inclusions"])),
        custom_features_allowance=PublicAllowance(label=allowance["label"], description=allowance["description"],
                                                  low_minor=allowance["low_minor"], high_minor=allowance["high_minor"]),
        timeline=PublicTimeline(label=timeline["label"], min_days=timeline["min_days"], max_days=timeline["max_days"]),
        assumptions=_assumptions(result, card), exclusions=tuple(result["exclusions"]),
        client_scope=tuple(result["client_scope"]), pricing_card_version=card.version,
        validity_days=result["validity_days"],
        expires_on=expires_on, reference=reference, configuration_reference=configuration_reference,
        catalog_release=catalog_release,
        specification=PublicSpecification(spec_code=specification["spec_code"], name=specification["name"])
        if specification else None,
    )  # fmt: skip


def card_texts(card) -> Iterator[tuple[str, str, str]]:
    """Customer-visible text kept in a (staff-only) pricing card, with its policy: governed although the card is
    private (no money, no claim)."""
    for i, value in enumerate(card.exclusions):
        yield f"card.exclusions.{i}", value, STRUCTURED_EXCLUSION
    for i, value in enumerate(card.client_scope):
        yield f"card.client_scope.{i}", value, STRUCTURED_CLIENT_SCOPE
    for i, band in enumerate(card.timeline):
        yield f"card.timeline.{i}.label", band.label, STRUCTURED_TIMELINE
    for c in card.project_preparation:
        yield f"card.project_preparation.{c.code}.inclusion", c.inclusion, FACTUAL_TEXT
        yield f"card.project_preparation.{c.code}.label", c.label, FACTUAL_TEXT
    for p in card.products:
        yield f"card.products.{p.code}.label", p.label, STRUCTURED_ASSUMPTION
        for i in p.inputs:
            yield f"card.products.{p.code}.inputs.{i.name}.label", i.label, STRUCTURED_ASSUMPTION
