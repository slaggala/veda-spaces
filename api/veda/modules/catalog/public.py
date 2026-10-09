"""The V3 public payloads (canonical customer-copy closure, Phases 1, 2 and 7).

Every V3 response a customer receives is an explicit, strict, bounded DTO: unknown fields are refused, every string
and container has a maximum size, and nothing is typed `Any`, `object` or an unbounded dictionary or list.

**Payloads:**
- `PublicCatalog` is built from typed catalog records.
- `PublicEstimate` is built from the engine's stored result.

**Field inventory.** Every field of every DTO is classified in PUBLIC_FIELD_CLASSES (eight classes). A test enumerates
the DTOs' fields and fails on an unclassified field or a weak type, and the inventory document is generated from this
registry.

**One checker.** `check_payload` walks a payload by its classification and applies the same canonical checks
everywhere: catalog serialisation, estimate serialisation, and release validation (the resolved catalog payload and
representative estimate payloads). It covers claims, promises, rates and invisible characters, and the release gate
also checks controlled copy, expiry and ownership.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from veda.modules.estimator import engine

from . import kinds, text

# --- classification ---------------------------------------------------------------------------------------------------
FACTUAL_CUSTOMER_COPY = "FACTUAL_CUSTOMER_COPY"  # catalog descriptive text: no promise, no claim, no rate
CONTROLLED_CUSTOMER_COPY = "CONTROLLED_CUSTOMER_COPY"  # a copy record's statement (its own governance applies)
PROMISE_GOVERNED_COPY = "PROMISE_GOVERNED_COPY"  # estimator, card and specification text under the promise matrix
MARKETING_CLAIM_COPY = "MARKETING_CLAIM_COPY"  # a governed claim (a copy record with claim governance)
PRICE_OR_RATE_COPY = "PRICE_OR_RATE_COPY"  # an engine-generated public total or range (a number, never text)
STAFF_ONLY = "STAFF_ONLY"
IDENTIFIER = "IDENTIFIER"
NOT_CUSTOMER_VISIBLE = "NOT_CUSTOMER_VISIBLE"
CLASSES = (FACTUAL_CUSTOMER_COPY, CONTROLLED_CUSTOMER_COPY, PROMISE_GOVERNED_COPY, MARKETING_CLAIM_COPY,
           PRICE_OR_RATE_COPY, STAFF_ONLY, IDENTIFIER, NOT_CUSTOMER_VISIBLE)  # fmt: skip

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


class PublicCopy(_Dto):
    statement: S500
    category: S30


class PublicCondition(_Dto):
    property_types: tuple[Literal["APARTMENT", "VILLA"], ...] = Field(default=(), max_length=2)
    home_sizes: tuple[HomeSize, ...] = Field(default=(), max_length=5)
    project_kinds: tuple[ProjectKind, ...] = Field(default=(), max_length=2)
    packages: tuple[PackageCode, ...] = Field(default=(), max_length=3)


class PublicRule(_Dto):
    type: Literal["requires", "excludes", "compatible_with", "available_only_for", "hidden_when", "default_when",
                  "measurement_bounds", "requires_consultation", "unavailable_online"]  # fmt: skip
    subject: S300
    objects: tuple[S300, ...] = Field(max_length=12)
    condition: PublicCondition | None = None
    input: CODE | None = None
    min: float | None = None
    max: float | None = None
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
    label: S60
    amount_minor: Minor


class PublicPreparation(_Dto):
    label: S120
    description: S500
    amount_minor: Minor
    inclusions: tuple[S300, ...] = Field(max_length=12)


class PublicAllowance(_Dto):
    label: S120
    description: S500
    low_minor: Minor
    high_minor: Minor


class PublicTimeline(_Dto):
    label: S120
    min_days: Annotated[int, Field(ge=1, le=1000)]
    max_days: Annotated[int, Field(ge=1, le=1000)]


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
    assumptions: tuple[S300, ...] = Field(max_length=60)
    exclusions: tuple[S300, ...] = Field(max_length=40)
    client_scope: tuple[S300, ...] = Field(max_length=40)
    validity_days: Annotated[int, Field(ge=1, le=90)]
    expires_on: S30
    reference: S30
    configuration_reference: S30
    catalog_release: S60
    specification: PublicSpecification | None = None


# Every field of every public DTO (declaring class, field) -> classification. Generated inventory and tests read this.
_DESCRIBED = {("_Described", "name"): FACTUAL_CUSTOMER_COPY, ("_Described", "description"): FACTUAL_CUSTOMER_COPY,
              ("_Described", "what_is_this"): FACTUAL_CUSTOMER_COPY,
              ("_Described", "typically_used_for"): FACTUAL_CUSTOMER_COPY, ("_Described", "sort"): NOT_CUSTOMER_VISIBLE}  # fmt: skip
PUBLIC_FIELD_CLASSES: dict[tuple[str, str], str] = {
    **_DESCRIBED,
    ("PublicAvailability", "project_kinds"): IDENTIFIER,
    ("PublicPropertyType", "name"): FACTUAL_CUSTOMER_COPY, ("PublicPropertyType", "code"): IDENTIFIER,
    ("PublicPropertyType", "sort"): NOT_CUSTOMER_VISIBLE,
    ("PublicRoomSlot", "room_template"): IDENTIFIER, ("PublicRoomSlot", "default_selected"): IDENTIFIER,
    ("PublicHome", "name"): FACTUAL_CUSTOMER_COPY, ("PublicHome", "description"): FACTUAL_CUSTOMER_COPY,
    ("PublicHome", "property_type"): IDENTIFIER, ("PublicHome", "home_size"): IDENTIFIER,
    ("PublicHome", "rooms"): IDENTIFIER, ("PublicHome", "packages"): IDENTIFIER,
    ("PublicHome", "availability"): IDENTIFIER, ("PublicHome", "sort"): NOT_CUSTOMER_VISIBLE,
    ("PublicProductSlot", "product"): IDENTIFIER, ("PublicProductSlot", "variant"): IDENTIFIER,
    ("PublicProductSlot", "options"): IDENTIFIER, ("PublicProductSlot", "removable"): IDENTIFIER,
    ("PublicRoom", "room_code"): IDENTIFIER, ("PublicRoom", "image"): IDENTIFIER, ("PublicRoom", "gallery"): IDENTIFIER,
    ("PublicRoom", "included"): IDENTIFIER, ("PublicRoom", "extras"): IDENTIFIER,
    ("PublicMeasurement", "input"): IDENTIFIER, ("PublicMeasurement", "label"): FACTUAL_CUSTOMER_COPY,
    ("PublicMeasurement", "unit"): IDENTIFIER, ("PublicMeasurement", "min"): IDENTIFIER,
    ("PublicMeasurement", "max"): IDENTIFIER, ("PublicMeasurement", "hint"): FACTUAL_CUSTOMER_COPY,
    ("PublicChoice", "key"): IDENTIFIER, ("PublicChoice", "materials"): IDENTIFIER, ("PublicChoice", "media"): IDENTIFIER,
    ("PublicOptionGroup", "key"): IDENTIFIER, ("PublicOptionGroup", "name"): FACTUAL_CUSTOMER_COPY,
    ("PublicOptionGroup", "description"): FACTUAL_CUSTOMER_COPY, ("PublicOptionGroup", "default"): IDENTIFIER,
    ("PublicOptionGroup", "choices"): IDENTIFIER,
    ("PublicVariant", "key"): IDENTIFIER, ("PublicVariant", "media"): IDENTIFIER,
    ("PublicVariant", "option_groups"): IDENTIFIER, ("PublicVariant", "measurements"): IDENTIFIER,
    ("PublicProduct", "family"): IDENTIFIER, ("PublicProduct", "media"): IDENTIFIER,
    ("PublicProduct", "variants"): IDENTIFIER,
    ("PublicExtra", "kind"): IDENTIFIER, ("PublicExtra", "quantity"): IDENTIFIER, ("PublicExtra", "max_count"): IDENTIFIER,
    ("PublicExtra", "default_selected"): IDENTIFIER, ("PublicExtra", "media"): IDENTIFIER,
    ("PublicExtra", "measurements"): IDENTIFIER,
    ("PublicPackage", "engine_package"): IDENTIFIER, ("PublicPackage", "public_summary"): IDENTIFIER,
    ("PublicPackage", "badge"): IDENTIFIER, ("PublicPackage", "recommended"): NOT_CUSTOMER_VISIBLE,
    ("PublicPackage", "consultation_only"): IDENTIFIER, ("PublicPackage", "included_products"): IDENTIFIER,
    ("PublicPackage", "optional_products"): IDENTIFIER, ("PublicPackage", "included_extras"): IDENTIFIER,
    ("PublicPackage", "excluded_extras"): IDENTIFIER,
    ("PublicMaterial", "statements"): IDENTIFIER, ("PublicMaterial", "finish"): FACTUAL_CUSTOMER_COPY,
    ("PublicMaterial", "colour_family"): FACTUAL_CUSTOMER_COPY, ("PublicMaterial", "texture"): FACTUAL_CUSTOMER_COPY,
    ("PublicHardware", "statements"): IDENTIFIER,
    ("PublicMediaUrls", "thumb"): IDENTIFIER, ("PublicMediaUrls", "mobile"): IDENTIFIER,
    ("PublicMediaUrls", "desktop"): IDENTIFIER,
    ("PublicMedia", "type"): IDENTIFIER, ("PublicMedia", "title"): FACTUAL_CUSTOMER_COPY,
    ("PublicMedia", "alt"): FACTUAL_CUSTOMER_COPY, ("PublicMedia", "caption"): FACTUAL_CUSTOMER_COPY,
    ("PublicMedia", "label"): IDENTIFIER, ("PublicMedia", "attribution"): FACTUAL_CUSTOMER_COPY,
    ("PublicMedia", "items"): IDENTIFIER, ("PublicMedia", "embed_url"): IDENTIFIER, ("PublicMedia", "urls"): IDENTIFIER,
    ("PublicMedia", "sort"): NOT_CUSTOMER_VISIBLE,
    ("PublicCopy", "statement"): CONTROLLED_CUSTOMER_COPY, ("PublicCopy", "category"): IDENTIFIER,
    ("PublicCondition", "property_types"): IDENTIFIER, ("PublicCondition", "home_sizes"): IDENTIFIER,
    ("PublicCondition", "project_kinds"): IDENTIFIER, ("PublicCondition", "packages"): IDENTIFIER,
    ("PublicRule", "type"): IDENTIFIER, ("PublicRule", "subject"): IDENTIFIER, ("PublicRule", "objects"): IDENTIFIER,
    ("PublicRule", "condition"): IDENTIFIER, ("PublicRule", "input"): IDENTIFIER, ("PublicRule", "min"): IDENTIFIER,
    ("PublicRule", "max"): IDENTIFIER, ("PublicRule", "message"): IDENTIFIER,
    ("PublicCatalog", "release"): IDENTIFIER, ("PublicCatalog", "manifest_sha256"): IDENTIFIER,
    ("PublicCatalog", "property_type"): IDENTIFIER, ("PublicCatalog", "home_config"): IDENTIFIER,
    ("PublicCatalog", "room_template"): IDENTIFIER, ("PublicCatalog", "product_family"): IDENTIFIER,
    ("PublicCatalog", "product"): IDENTIFIER, ("PublicCatalog", "extra"): IDENTIFIER,
    ("PublicCatalog", "material"): IDENTIFIER, ("PublicCatalog", "hardware"): IDENTIFIER,
    ("PublicCatalog", "package"): IDENTIFIER, ("PublicCatalog", "media"): IDENTIFIER,
    ("PublicCatalog", "copy_"): IDENTIFIER, ("PublicCatalog", "rule"): IDENTIFIER,
    ("PublicRange", "low_minor"): PRICE_OR_RATE_COPY, ("PublicRange", "high_minor"): PRICE_OR_RATE_COPY,
    ("PublicRange", "currency"): IDENTIFIER,
    ("PublicGst", "pct"): PRICE_OR_RATE_COPY, ("PublicGst", "low_minor"): PRICE_OR_RATE_COPY,
    ("PublicGst", "high_minor"): PRICE_OR_RATE_COPY,
    ("PublicRoomTotal", "room"): IDENTIFIER, ("PublicRoomTotal", "label"): PROMISE_GOVERNED_COPY,
    ("PublicRoomTotal", "amount_minor"): PRICE_OR_RATE_COPY,
    ("PublicPreparation", "label"): PROMISE_GOVERNED_COPY, ("PublicPreparation", "description"): PROMISE_GOVERNED_COPY,
    ("PublicPreparation", "amount_minor"): PRICE_OR_RATE_COPY, ("PublicPreparation", "inclusions"): PROMISE_GOVERNED_COPY,
    ("PublicAllowance", "label"): PROMISE_GOVERNED_COPY, ("PublicAllowance", "description"): PROMISE_GOVERNED_COPY,
    ("PublicAllowance", "low_minor"): PRICE_OR_RATE_COPY, ("PublicAllowance", "high_minor"): PRICE_OR_RATE_COPY,
    ("PublicTimeline", "label"): PROMISE_GOVERNED_COPY, ("PublicTimeline", "min_days"): IDENTIFIER,
    ("PublicTimeline", "max_days"): IDENTIFIER,
    ("PublicSpecification", "spec_code"): IDENTIFIER, ("PublicSpecification", "name"): PROMISE_GOVERNED_COPY,
    ("PublicEstimate", "title"): PROMISE_GOVERNED_COPY, ("PublicEstimate", "disclaimer"): PROMISE_GOVERNED_COPY,
    ("PublicEstimate", "package"): IDENTIFIER, ("PublicEstimate", "property_type"): IDENTIFIER,
    ("PublicEstimate", "home_size"): IDENTIFIER, ("PublicEstimate", "range"): IDENTIFIER,
    ("PublicEstimate", "gst"): IDENTIFIER, ("PublicEstimate", "rooms"): IDENTIFIER,
    ("PublicEstimate", "project_preparation"): IDENTIFIER, ("PublicEstimate", "custom_features_allowance"): IDENTIFIER,
    ("PublicEstimate", "timeline"): IDENTIFIER, ("PublicEstimate", "assumptions"): PROMISE_GOVERNED_COPY,
    ("PublicEstimate", "exclusions"): PROMISE_GOVERNED_COPY, ("PublicEstimate", "client_scope"): PROMISE_GOVERNED_COPY,
    ("PublicEstimate", "validity_days"): IDENTIFIER, ("PublicEstimate", "expires_on"): IDENTIFIER,
    ("PublicEstimate", "reference"): IDENTIFIER, ("PublicEstimate", "configuration_reference"): IDENTIFIER,
    ("PublicEstimate", "catalog_release"): IDENTIFIER, ("PublicEstimate", "specification"): IDENTIFIER,
}  # fmt: skip
ROOTS: tuple[type[BaseModel], ...] = (PublicCatalog, PublicEstimate)
TEXT_CLASSES = (FACTUAL_CUSTOMER_COPY, CONTROLLED_CUSTOMER_COPY, PROMISE_GOVERNED_COPY, MARKETING_CLAIM_COPY)


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


def _class_of(model: BaseModel, name: str) -> str:
    key = (text.declaring_class(type(model), name), name)
    if key not in PUBLIC_FIELD_CLASSES:
        raise KeyError(f"public field {key} is not classified")  # fails closed (and the inventory test fails first)
    return PUBLIC_FIELD_CLASSES[key]


def strings(model: BaseModel, prefix: str = "") -> Iterator[tuple[str, str, str]]:
    """(path, text, class) for every string in a public DTO, by its classification."""
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
                yield from strings(child, f"{sub}.")
            elif isinstance(child, str):
                yield sub, child, _class_of(model, name)


# --- the one checker --------------------------------------------------------------------------------------------------
def check_text(where: str, value: str, cls: str, *, governed: dict[str, kinds.Copy] | None = None,
               copy_key: str | None = None) -> list[str]:  # fmt: skip
    """The canonical checks for one customer-visible string of the given class."""
    if cls not in TEXT_CLASSES:
        return []
    problems = []
    if text.invisible_chars(value):
        problems.append(f"{where}: contains invisible or formatting characters")
    what = text.leak_in(value) if cls == PROMISE_GOVERNED_COPY else text.forbidden_in(value)
    if what:
        problems.append(f"{where}: contains {what}")
    marketing = text.marketing_claims_in(value)
    if cls == FACTUAL_CUSTOMER_COPY:
        if text.promise_in(value):
            problems.append(f"{where}: factual text makes a promise")
        if marketing:
            problems.append(f"{where}: factual text makes a {', '.join(marketing)} claim")
    elif cls == PROMISE_GOVERNED_COPY:
        if marketing:  # estimator, card and specification text may state governed scope, never marketing claims
            problems.append(f"{where}: estimator text makes a {', '.join(marketing)} claim")
    elif cls == CONTROLLED_CUSTOMER_COPY:
        record = (governed or {}).get(copy_key or "")
        if record is None:
            problems.append(f"{where}: copy that is not a record of this release")
        else:
            if text.canonical(record.statement) != text.canonical(value):
                problems.append(f"{where}: the served text is not the approved copy")
            if marketing and record.claim is None:
                problems.append(f"{where}: copy makes a {', '.join(marketing)} claim without claim governance")
            if text.promise_in(value) and not record.promise:
                problems.append(f"{where}: copy makes a promise but is not a promise record")
    return problems


def check_payload(model: BaseModel, *, governed: dict[str, kinds.Copy] | None = None) -> list[str]:
    """Every string of a public DTO, through `check_text` by its classification."""
    problems = []
    for where, value, cls in strings(model):
        copy_key = where[len("copy_.") : -len(".statement")] if where.startswith("copy_.") else None
        problems.extend(check_text(where, value, cls, governed=governed, copy_key=copy_key))
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
            k: PublicCopy(statement=m.statement, category=m.category) for k, m in sorted(cat.of(kinds.Copy).items())
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


def build_estimate(result: dict, *, reference: str, expires_on: str, configuration_reference: str,
                   catalog_release: str, specification: dict | None) -> PublicEstimate:  # fmt: skip
    """The public estimate DTO from the engine's stored result (the staff view): customer fields only, room amounts
    rounded for customers, nothing else (no line, rate, component amount, warranty block or workflow state)."""
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
        assumptions=tuple(result["assumptions"]), exclusions=tuple(result["exclusions"]),
        client_scope=tuple(result["client_scope"]), validity_days=result["validity_days"],
        expires_on=expires_on, reference=reference, configuration_reference=configuration_reference,
        catalog_release=catalog_release,
        specification=PublicSpecification(spec_code=specification["spec_code"], name=specification["name"])
        if specification else None,
    )  # fmt: skip


def card_texts(card) -> Iterator[tuple[str, str]]:
    """Customer-visible text that lives in a (staff-only) pricing card: governed even though the card is private."""
    for i, value in enumerate(card.exclusions):
        yield f"card.exclusions.{i}", value
    for i, value in enumerate(card.client_scope):
        yield f"card.client_scope.{i}", value
    for band in card.timeline:
        yield f"card.timeline.{band.label}", band.label
    for c in card.project_preparation:
        yield f"card.project_preparation.{c.code}.inclusion", c.inclusion
        yield f"card.project_preparation.{c.code}.label", c.label
    for p in card.products:
        yield f"card.products.{p.code}.label", p.label
        for i in p.inputs:
            yield f"card.products.{p.code}.inputs.{i.name}.label", i.label
