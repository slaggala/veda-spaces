"""Document schemas for every catalog record kind (ADR-013 D2).

Each kind is a strict pydantic model (unknown fields refused). Records refer to each other by key. Customer-visible
text is checked like the customer specification (no amount, price wording, duration or contact detail). Descriptive
text may not carry a promise: a material, hardware, warranty, package, inclusion or exclusion promise must be a
registered `copy` record with its governance fields (ADR-013 D7, final pre-activation closure M3). Rates live only in
`pricing` records, which are staff-only.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from veda.modules.estimator import ratecard

from . import text

Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")]
Code = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]
Name = Annotated[str, Field(min_length=1, max_length=120)]
Text = Annotated[str, Field(min_length=1, max_length=500)]
RoomCode = Literal[
    "KITCHEN", "UTILITY", "LIVING", "DINING", "MASTER_BEDROOM", "BEDROOM_2", "BEDROOM_3", "BEDROOM_4",
    "KIDS_ROOM", "STUDY", "POOJA", "WHOLE_HOME",
]  # fmt: skip
HomeSize = Literal["1BHK", "2BHK", "3BHK", "4BHK", "CUSTOM"]
PropertyCode = Literal["APARTMENT", "VILLA"]
ProjectKind = Literal["NEW_HOME", "RENOVATION"]
PackageCode = Literal["ESSENTIAL", "PREMIUM", "LUXURY"]
Visibility = Literal["customer", "staff"]
# Promise and claim vocabularies, and the classification of every text field, live in `text` (customer-safety closure).
_PROMISE_WORDS = text.PROMISE


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# The engine has no market or city context yet, so a market condition could never be evaluated: a hidden_when would
# hide nothing, and a requires_consultation or unavailable_online rule would never fire (the item would be priced).
# Until market logic exists, such content is refused when it is saved rather than silently dropped.
MARKETS_UNSUPPORTED = "market or city conditions are not supported yet; remove them (they cannot be evaluated safely)"


class Availability(_Model):
    markets: tuple[Annotated[str, Field(min_length=2, max_length=60)], ...] = ()  # empty: every market
    property_types: tuple[PropertyCode, ...] = ()
    home_sizes: tuple[HomeSize, ...] = ()
    project_kinds: tuple[ProjectKind, ...] = ()
    effective_from: date | None = None
    effective_to: date | None = None

    @model_validator(mode="after")
    def _dates(self):
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to is before effective_from")
        if self.markets:
            raise ValueError(MARKETS_UNSUPPORTED)
        return self


class Described(_Model):
    """Customer-facing descriptive text (never a promise)."""

    name: Name
    description: Text | None = None
    what_is_this: Text | None = None
    typically_used_for: Text | None = None
    staff_note: Annotated[str, Field(max_length=1000)] | None = None  # staff-only, never shown to customers
    visibility: Visibility = "customer"
    sort: int = Field(default=100, ge=0, le=100000)
    availability: Availability = Availability()


# --- A. homes and spaces ------------------------------------------------------------------------------------------
class PropertyType(Described):
    code: PropertyCode


class RoomSlot(_Model):
    room_template: Key
    default_selected: bool = True


class HomeConfig(Described):
    property_type: Key
    home_size: HomeSize
    rooms: tuple[RoomSlot, ...] = Field(min_length=1)
    packages: tuple[Key, ...] = Field(min_length=1)


class ProductSlot(_Model):
    product: Key
    variant: Key
    options: dict[Key, Key] = Field(default_factory=dict)  # option group → choice
    removable: bool = False


class RoomTemplate(Described):
    room_code: RoomCode
    image: Key | None = None  # media record: the representative approved image
    gallery: Key | None = None
    included: tuple[ProductSlot, ...] = Field(min_length=1)
    extras: tuple[Key, ...] = ()


# --- B. products -----------------------------------------------------------------------------------------------------
class ProductFamily(Described):
    category: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")]


class MeasurementPrompt(_Model):
    input: Code  # the engine input it refines
    label: Name
    unit: Literal["ft", "sqft"]
    min: float = Field(gt=0)
    max: float = Field(gt=0)
    hint: Text | None = None


class Choice(Described):
    key: Key
    engine_options: dict[Code, Code] = Field(default_factory=dict)
    materials: tuple[Key, ...] = ()
    hardware: tuple[Key, ...] = ()
    media: tuple[Key, ...] = ()


class OptionGroup(_Model):
    key: Key
    name: Name
    description: Text | None = None
    # True only when the choices are deliberately priced alike (a colour, say). Otherwise two choices with the same
    # engine options fail validation unless one is consultation-only: veneer is never silently priced as laminate.
    price_neutral: bool = False
    choices: tuple[Choice, ...] = Field(min_length=1)
    default: Key

    @model_validator(mode="after")
    def _default(self):
        keys = [c.key for c in self.choices]
        if len(set(keys)) != len(keys) or self.default not in keys:
            raise ValueError(f"option group {self.key}: choices must be distinct and include the default")
        return self


class Variant(Described):
    key: Key
    engine_product: Code
    engine_options: dict[Code, Code] = Field(default_factory=dict)
    option_groups: tuple[OptionGroup, ...] = ()
    materials: tuple[Key, ...] = ()
    hardware: tuple[Key, ...] = ()
    media: tuple[Key, ...] = ()
    measurements: tuple[MeasurementPrompt, ...] = ()


class Product(Described):
    family: Key
    variants: tuple[Variant, ...] = Field(min_length=1)
    default_variant: Key
    rooms: tuple[RoomCode, ...] = Field(min_length=1)
    packages: tuple[PackageCode, ...] = ("ESSENTIAL",)
    media: tuple[Key, ...] = ()
    show_impact: bool = False  # an approved, rounded estimate-impact range may be shown

    @model_validator(mode="after")
    def _variants(self):
        keys = [v.key for v in self.variants]
        if len(set(keys)) != len(keys) or self.default_variant not in keys:
            raise ValueError("variants must be distinct and include the default variant")
        return self


# --- E. extras -------------------------------------------------------------------------------------------------------
class AddSelection(_Model):
    engine_product: Code
    engine_options: dict[Code, Code] = Field(default_factory=dict)


class SetOption(_Model):
    product: Key
    group: Key
    choice: Key


class Extra(Described):
    kind: Literal["room_extra", "product_extra", "package_extra"]
    quantity: Literal["fixed", "count", "measured"] = "fixed"
    max_count: int = Field(default=1, ge=1, le=10)
    default_selected: bool = False
    add: AddSelection | None = None  # adds an engine selection
    set_option: SetOption | None = None  # or changes an option of an included product
    rooms: tuple[Key, ...] = ()  # room templates it is offered in
    products: tuple[Key, ...] = ()
    media: tuple[Key, ...] = ()
    materials: tuple[Key, ...] = ()
    hardware: tuple[Key, ...] = ()
    measurements: tuple[MeasurementPrompt, ...] = ()  # a measured extra's inputs (engine inputs of `add`)
    show_impact: bool = False

    @model_validator(mode="after")
    def _effect(self):
        if (self.add is None) == (self.set_option is None):
            raise ValueError("an extra either adds a selection or sets an option, exactly one")
        if self.quantity == "fixed" and self.max_count != 1:
            raise ValueError("a fixed extra has max_count 1")
        if (self.quantity == "measured") != bool(self.measurements):
            raise ValueError("a measured extra, and only a measured extra, lists its measurements")
        if self.measurements and self.add is None:
            raise ValueError("only an extra that adds a selection is measured")
        return self


# --- C/D. materials and hardware ----------------------------------------------------------------------------------
class Material(Described):
    category: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    grade: Name | None = None
    thickness: tuple[Name, ...] = ()
    finish: Name | None = None
    colour_family: Name | None = None
    texture: Name | None = None
    brands: tuple[Name, ...] = ()
    wet_area: Literal["suitable", "not_suitable", "unspecified"] = "unspecified"
    rooms: tuple[RoomCode, ...] = ()
    products: tuple[Key, ...] = ()
    statements: tuple[Key, ...] = Field(min_length=1)  # copy records: the governed customer promise
    warranty_source: Text  # staff: where the warranty comes from


class Hardware(Described):
    category: Literal["hinge", "channel", "tandem", "pull_out", "basket", "handle", "mechanism"]
    soft_close: bool = False
    load_capacity_kg: float | None = Field(default=None, gt=0, le=500)  # only where approved
    compatible_families: tuple[Key, ...] = ()
    brands: tuple[Name, ...] = ()
    statements: tuple[Key, ...] = Field(min_length=1)
    warranty_source: Text


# --- F. media --------------------------------------------------------------------------------------------------------
class Rights(_Model):
    owner: Name
    licence: Name
    usage: Literal["owned", "licensed", "client_permission"]
    effective_from: date | None = None  # rights not yet in effect are never released or served
    review_by: date | None = None  # mandatory review of the rights basis (release validation refuses it once passed)
    expires: date | None = None
    consent_reference: Annotated[str, Field(max_length=80)] | None = (
        None  # the client's written permission, by reference
    )

    @model_validator(mode="after")
    def _consent(self):
        if self.usage == "client_permission" and not self.consent_reference:
            raise ValueError("a client's image needs the reference of their written permission")
        if self.effective_from and self.expires and self.expires < self.effective_from:
            raise ValueError("media rights expire after they take effect")
        return self


class Objects(_Model):
    source: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    variants: dict[
        Literal["thumb", "mobile", "desktop", "web", "poster"], Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    ] = Field(default_factory=dict)


class Hotspot(_Model):
    key: Key
    label: Name
    position: tuple[float, float, float]


class CameraPreset(_Model):
    key: Key
    label: Name
    orbit: Annotated[str, Field(max_length=60)]  # e.g. "0deg 75deg 2.5m"
    target: Annotated[str, Field(max_length=60)] | None = None


class ThreeD(_Model):
    model_version: Annotated[str, Field(pattern=r"^[0-9A-Za-z._-]{1,20}$")]
    preview_image: Key  # IMAGE media record shown first, before any model loads
    fallback_gallery: Key  # GALLERY media record shown when the model cannot load
    supported_devices: tuple[Literal["desktop", "mobile", "ar_ios", "ar_android"], ...] = ("desktop", "mobile")
    dimensions_mm: dict[Literal["w", "h", "d"], int] = Field(default_factory=dict)
    materials: tuple[Key, ...] = ()
    variant_map: dict[Key, Annotated[str, Field(max_length=80)]] = Field(default_factory=dict)
    finish_map: dict[Key, Annotated[str, Field(max_length=80)]] = Field(default_factory=dict)
    hotspots: tuple[Hotspot, ...] = ()
    camera_presets: tuple[CameraPreset, ...] = ()


EMBED_HOSTS = ("www.youtube-nocookie.com", "player.vimeo.com")
THREE_D_TYPES = frozenset({"GLB", "GLTF", "USDZ"})


class Media(_Model):
    type: Literal["IMAGE", "GALLERY", "VIDEO", "DEGREE_360", "GLB", "GLTF", "USDZ", "EXTERNAL_EMBED"]
    title: Name
    alt: Text | None = None  # required for every visual type
    caption: Text | None = None
    label: Literal["Design reference", "Illustrative example"] = "Illustrative example"
    attribution: Name | None = None
    rights: Rights
    objects: Objects = Objects()
    items: tuple[Key, ...] = ()  # GALLERY: its media records, in order
    embed_url: Annotated[str, Field(max_length=300)] | None = None
    three_d: ThreeD | None = None
    tags: dict[Literal["style", "material", "room", "product"], tuple[Key, ...]] = Field(default_factory=dict)
    rooms: tuple[RoomCode, ...] = ()
    products: tuple[Key, ...] = ()
    materials: tuple[Key, ...] = ()
    packages: tuple[PackageCode, ...] = ()
    sort: int = Field(default=100, ge=0, le=100000)

    @model_validator(mode="after")
    def _shape(self):
        visual = self.type != "GALLERY"
        if visual and not self.alt:
            raise ValueError("visual media needs alternate text")
        if self.type == "GALLERY" and not self.items:
            raise ValueError("a gallery lists its media items")
        if self.type in ("IMAGE", "VIDEO", "DEGREE_360") and not self.objects.variants:
            raise ValueError("an image or video needs its delivery variants")
        if self.type in ("GLB", "GLTF", "USDZ") and (self.three_d is None or "web" not in self.objects.variants):
            raise ValueError("a 3D asset needs its web-optimised file and its 3D description")
        if self.type in ("GLTF", "USDZ"):
            raise ValueError("glTF and USDZ are disabled; register a sanitised GLB")
        if self.type == "EXTERNAL_EMBED":
            host = re.match(r"^https://([^/]+)/", self.embed_url or "")
            if not host or host.group(1) not in EMBED_HOSTS:
                raise ValueError(f"an external embed must be https on {', '.join(EMBED_HOSTS)}")
        return self


# --- G. packages, pricing, rules, copy ---------------------------------------------------------------------------
class Package(Described):
    engine_package: PackageCode
    public_summary: Key  # copy record
    included_products: tuple[Key, ...] = ()
    optional_products: tuple[Key, ...] = ()
    included_extras: tuple[Key, ...] = ()
    excluded_extras: tuple[Key, ...] = ()
    material_promise: tuple[Key, ...] = ()  # copy records
    hardware_promise: tuple[Key, ...] = ()
    warranty_copy: Key | None = None
    badge: Key | None = None  # a badge-category copy record, never free text (R2/R3)
    recommended: bool = False
    consultation_only: bool = False


SETTINGS_FIELDS = (
    "schema", "description", "version", "effective_on", "currency", "packages", "property_types", "gst_pct",
    "validity_days", "ranges", "bounds", "project_preparation", "custom_features_allowance", "timeline",
    "exclusions", "client_scope",
)  # fmt: skip


class Pricing(_Model):
    """Staff-only commercial data: one engine product (its lines, rates, inputs and options) or the card settings."""

    scope: Literal["settings", "product"]
    engine_product: Code | None = None
    body: dict[str, Any]
    position: int = Field(default=100, ge=0, le=100000)  # the product's place in the compiled card
    note: Annotated[str, Field(max_length=500)] | None = None

    @model_validator(mode="after")
    def _body(self):
        if self.scope == "product":
            spec = ratecard.ProductSpec.model_validate(self.body)
            if spec.code != self.engine_product:
                raise ValueError("a product pricing record prices exactly its engine_product")
        else:
            if self.engine_product is not None or set(self.body) - set(SETTINGS_FIELDS):
                raise ValueError(f"settings pricing holds only card settings: {', '.join(SETTINGS_FIELDS)}")
        return self


RULE_TYPES = (
    "requires", "excludes", "compatible_with", "available_only_for", "hidden_when", "default_when",
    "measurement_bounds", "requires_consultation", "unavailable_online", "staff_only",
)  # fmt: skip
# A reference to a selectable thing: product:<key>[#<variant>][@<group>=<choice>] or extra:<key> or room:<key>.
REF_PATH_PATTERN = r"^(product:[a-z][a-z0-9_.-]{1,99}(#[a-z][a-z0-9_.-]{1,99})?(@[a-z][a-z0-9_.-]{1,99}=[a-z][a-z0-9_.-]{1,99})?|extra:[a-z][a-z0-9_.-]{1,99}|room:[a-z][a-z0-9_.-]{1,99})$"
RefPath = Annotated[str, Field(pattern=REF_PATH_PATTERN)]  # fmt: skip


class Condition(_Model):
    property_types: tuple[PropertyCode, ...] = ()
    home_sizes: tuple[HomeSize, ...] = ()
    project_kinds: tuple[ProjectKind, ...] = ()
    packages: tuple[PackageCode, ...] = ()
    markets: tuple[Annotated[str, Field(min_length=2, max_length=60)], ...] = ()

    @model_validator(mode="after")
    def _supported(self):
        if self.markets:
            raise ValueError(MARKETS_UNSUPPORTED)
        if not (self.property_types or self.home_sizes or self.project_kinds or self.packages):
            raise ValueError("a condition names at least one property type, home size, project kind or package")
        return self


class Rule(_Model):
    type: Literal[
        "requires", "excludes", "compatible_with", "available_only_for", "hidden_when", "default_when",
        "measurement_bounds", "requires_consultation", "unavailable_online", "staff_only",
    ]  # fmt: skip
    subject: RefPath
    objects: tuple[RefPath, ...] = ()
    condition: Condition | None = None
    input: Code | None = None  # measurement_bounds
    min: float | None = None
    max: float | None = None
    message: Key | None = None  # copy record shown when the rule blocks a choice
    note: Annotated[str, Field(max_length=300)] | None = None

    @model_validator(mode="after")
    def _shape(self):
        if self.type in ("requires", "excludes", "compatible_with") and not self.objects:
            raise ValueError(f"a {self.type} rule names its objects")
        if self.type in ("available_only_for", "hidden_when", "default_when") and self.condition is None:
            raise ValueError(f"a {self.type} rule has a condition")
        if self.type == "measurement_bounds" and (self.input is None or self.min is None or self.max is None):
            raise ValueError("a measurement_bounds rule names its input, min and max")
        if self.min is not None and self.max is not None and self.max < self.min:
            raise ValueError("max is below min")
        return self


class Governance(_Model):
    owner: Name  # an accountable role or person; UNASSIGNED blocks activation of a promise
    backup: Name
    quotation_mapping: Text
    verification: Text  # procurement or execution verification path
    warranty_source: Text
    status: Literal["OPERATIONALLY_CONFIRMED", "BLOCKED"] = "BLOCKED"
    confirmed_on: date | None = None


class AppliesTo(_Model):
    products: tuple[Key, ...] = ()
    rooms: tuple[Key, ...] = ()
    packages: tuple[Key, ...] = ()


_PLACEHOLDERS = frozenset({
    "x", "xx", "xxx", "yes", "no", "ok", "okay", "na", "n a", "none", "nil", "tbd", "tba", "todo", "internal", "approved",
    "test", "testing", "placeholder", "dummy", "sample", "evidence", "source", "see above", "same", "various", "data",
})  # fmt: skip


def substantive(value: str | None) -> bool:
    """A real reference, not a placeholder: at least 12 characters of letters after normalisation."""
    if not value:
        return False
    form = text.canonical(value)
    return form not in _PLACEHOLDERS and len(form) >= 12 and sum(ch.isalpha() for ch in form) >= 8


ClaimCategory = Literal[
    "factual_descriptor", "ranking", "price", "popularity", "recommendation", "quality", "certification", "award",
    "warranty", "service", "durability", "environmental", "promotional", "urgency",
]  # fmt: skip
TIME_BOXED = frozenset({"ranking", "price", "popularity", "award", "promotional", "urgency"})
# The content policy an author selects for a copy record (canonical customer-copy closure, B1-B3 policy).
CopyPolicy = Literal["FACTUAL_TEXT", "CONTROLLED_LEGAL_COPY", "GOVERNED_CLAIM_REFERENCE"]


class ClaimGovernance(_Model):
    """A marketing claim's governance (canonical customer-copy closure, Phase 5).

    The declared `categories` must equal the categories detected in the statement's canonical form. The record needs a
    supporting source and an evidence reference (not placeholders), a responsible owner, a named approver, allowed
    environments, an effective date, and either a review date or an explicit non-expiring policy decision. It must also
    carry the canonical digest of the approved display text.

    Category rules:
    - Absolute, ranking and price claims also need independent substantiation and a backup owner.
    - Ranking, price and popularity claims need the period the evidence covers.
    - Promotional and price claims must be time-boxed (a review date, never non-expiring).

    The approver attests the claim. The system approval is the record's four-eyes review, which refuses its author,
    editors and submitter."""

    categories: tuple[ClaimCategory, ...] = Field(min_length=1)
    status: Literal["APPROVED", "BLOCKED", "WITHDRAWN"] = "BLOCKED"
    approved_on: date  # when the approver attested the claim (the record's four-eyes approval is the system's)
    source: Text  # what the claim rests on (sales data, test report, approved policy)
    evidence_reference: Text  # where the evidence is kept (document, report or dataset reference)
    evidence_period: Annotated[str, Field(max_length=80)] | None = None  # the period the evidence covers
    owner: Name  # an accountable role or person; UNASSIGNED blocks
    backup_owner: Name | None = None
    approver: Name  # who attests the claim (distinct from the record's author: four-eyes)
    effective_from: date
    review_by: date | None = None  # expiry or mandatory review date
    non_expiring_policy: Text | None = None  # the explicit policy decision when there is no review date
    environments: tuple[Literal["local", "test", "staging", "production"], ...] = Field(min_length=1)
    substantiation: Text | None = None  # independent substantiation (absolute, ranking and price claims)
    canonical_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]  # of the approved display text

    @model_validator(mode="after")
    def _evidence(self):
        cats = set(self.categories)
        if (self.review_by is None) == (self.non_expiring_policy is None):
            raise ValueError("a claim has a review date or an explicit non-expiring policy decision, exactly one")
        for name in ("source", "evidence_reference", "substantiation", "non_expiring_policy"):
            value = getattr(self, name)
            if value is not None and not substantive(value):
                raise ValueError(f"claim {name} is a placeholder; give a real reference")
        if text.canonical(self.approver) in {text.canonical(self.owner), text.canonical(self.backup_owner or "")}:
            raise ValueError("a claim is not approved by its own owner (no self-approval)")
        if self.review_by is not None and self.review_by <= self.effective_from:
            raise ValueError("a claim's review date is after its effective date")
        if self.approved_on > self.effective_from:
            raise ValueError("a claim is approved on or before its effective date")
        if cats & TIME_BOXED and self.review_by is None:
            raise ValueError(
                "a ranking, price, popularity, award, promotional or urgency claim is time-boxed: it needs a review "
                "date (its evidence is valid only for a period)"
            )
        if cats & {"ranking", "price"} and not self.substantiation:
            raise ValueError("a ranking or price claim needs independent substantiation")
        if cats & {"ranking", "price"} and not self.backup_owner:
            raise ValueError("a ranking or price claim needs a backup owner")
        if cats & {"ranking", "price", "popularity"} and not self.evidence_period:
            raise ValueError("a ranking, price or popularity claim names the period its evidence covers")
        return self


class Copy(_Model):
    """A customer statement. A promise (`promise: true`) carries its governance, the promise-matrix row whose registered
    text it is, and the products, rooms or packages it applies to; release validation confirms all three."""

    statement: Text
    category: Literal[
        "description", "package", "allowance", "warranty", "material", "hardware", "inclusion", "exclusion",
        "assumption", "disclaimer", "next_step", "label", "badge",
    ]  # fmt: skip
    promise: bool = True
    governance: Governance | None = None
    matrix_row: Annotated[str, Field(max_length=60)] | None = None  # the customer-promise matrix row it is text of
    applies_to: AppliesTo | None = None
    claim: ClaimGovernance | None = None  # set when the statement makes a claim
    # The author's choice (required when authoring; derived for records saved before it existed): FACTUAL_TEXT (no
    # claim, promise or money), CONTROLLED_LEGAL_COPY (disclaimers, next steps, labels: no claim or money), or
    # GOVERNED_CLAIM_REFERENCE (a claim record, or a promise record linked to its confirmed promise-matrix row).
    content_policy: CopyPolicy | None = None

    @property
    def policy(self) -> str:
        if self.content_policy:
            return self.content_policy
        if self.claim is not None or self.promise:
            return "GOVERNED_CLAIM_REFERENCE"
        return "CONTROLLED_LEGAL_COPY" if self.category in ("disclaimer", "next_step") else "FACTUAL_TEXT"

    @model_validator(mode="after")
    def _governed(self):
        governed = self.claim is not None or self.promise
        if self.content_policy == "GOVERNED_CLAIM_REFERENCE" and not governed:
            raise ValueError("a governed claim reference is a claim record or a promise record")
        if self.content_policy in ("FACTUAL_TEXT", "CONTROLLED_LEGAL_COPY") and governed:
            raise ValueError("a claim or promise record has the GOVERNED_CLAIM_REFERENCE content policy")
        if self.promise and (self.governance is None or not self.matrix_row or self.applies_to is None):
            raise ValueError(
                "a promise statement carries its governance, its promise-matrix row and what it applies to"
            )
        if self.applies_to is not None and not (
            self.applies_to.products or self.applies_to.rooms or self.applies_to.packages
        ):
            raise ValueError("applies_to names at least one product, room or package")
        if self.category == "badge" and len(self.statement) > 30:
            raise ValueError("a badge is at most 30 characters")
        if self.claim is not None and self.applies_to is None:
            raise ValueError("a claim names the products, rooms or packages it applies to")
        return self


SCHEMAS: dict[str, type[_Model]] = {
    "property_type": PropertyType,
    "home_config": HomeConfig,
    "room_template": RoomTemplate,
    "product_family": ProductFamily,
    "product": Product,
    "extra": Extra,
    "material": Material,
    "hardware": Hardware,
    "media": Media,
    "package": Package,
    "pricing": Pricing,
    "rule": Rule,
    "copy": Copy,
}
KIND_OF: dict[type[_Model], str] = {cls: kind for kind, cls in SCHEMAS.items()}
STAFF_ONLY_KINDS = frozenset({"pricing"})


class KindError(ValueError):
    pass


def load_model(kind: str, document: dict) -> _Model:
    """Schema validation only: used to load released content, which is never re-judged after release (historical
    releases and snapshots are not altered). New content passes `parse`, and every release passes the text gate."""
    if kind not in SCHEMAS:
        raise KindError(f"unknown catalog kind {kind!r}")
    return SCHEMAS[kind].model_validate(document)


def parse(kind: str, document: dict) -> _Model:
    """Validate a document being authored or imported: its schema, the author's content policy for copy, and every
    customer-visible string."""
    model = load_model(kind, document)
    if kind == "copy" and not document.get("content_policy"):
        raise KindError(
            "select the copy's content policy: FACTUAL_TEXT, CONTROLLED_LEGAL_COPY or GOVERNED_CLAIM_REFERENCE"
        )
    problems = text_problems(kind, model, authoring=True)
    if problems:
        raise KindError(problems[0])
    return model


def text_problems(kind: str, model: _Model, *, authoring: bool = True) -> list[str]:
    """Why the customer-visible text of a document is not allowed under its content policy (empty when it is). Every
    check runs on the canonical forms (`text.canonical`, `text.numeric_form`); detection is defence in depth behind
    the policies themselves and four-eyes review.

    - Factual catalog text and FACTUAL_TEXT copy: no claim of any category, no promise wording, no money, pricing
      wording, duration or contact detail.
    - CONTROLLED_LEGAL_COPY: no claim, no money, no contact detail.
    - GOVERNED_CLAIM_REFERENCE: a claim record whose declared categories equal the detected ones and whose digest is
      the statement's (absolute claims substantiated), or a promise record linked to its matrix row whose detected
      categories are only warranty, service or durability.
    - Everywhere, new text (`authoring`) may not contain invisible characters or words mixing scripts."""
    if kind in STAFF_ONLY_KINDS:
        return []
    problems = []
    for where, value, cls in text.visible_text(model):
        if authoring:
            hidden = text.invisible_chars(value)
            if hidden:
                problems.append(f"{where} contains invisible or formatting characters ({', '.join(hidden)})")
            mixed = text.mixed_script_words(value)
            if mixed:
                problems.append(f"{where} has words that mix scripts ({len(mixed)}); use one script per word")
        policy = model.policy if isinstance(model, Copy) and cls == text.STATEMENT else "FACTUAL_TEXT"
        what = text.leak_in(value) if policy != "FACTUAL_TEXT" else text.forbidden_in(value)
        if what:
            problems.append(f"{where} contains {what}; customer text never states it")
            continue
        claims = text.claims_in(value)
        if policy == "FACTUAL_TEXT":
            if text.promise_in(value):
                problems.append(f"{where} makes a promise; only a governed promise or claim record may say it")
            if claims:
                problems.append(f"{where} makes a {', '.join(claims)} claim; it must reference a governed claim record")
        elif policy == "CONTROLLED_LEGAL_COPY":
            if claims:
                problems.append(f"{where} makes a {', '.join(claims)} claim; it must reference a governed claim record")
        elif isinstance(model, Copy):
            claim = model.claim
            if claim is None:  # a promise record: only promise-matrix categories
                beyond = sorted(set(claims) - set(text.PROMISE_CATEGORIES))
                if beyond:
                    problems.append(f"{where} makes a {', '.join(beyond)} claim; it needs a governed claim record")
                continue
            declared = set(claim.categories) - {"factual_descriptor"}
            if declared != set(claims):
                problems.append(f"{where}: declared claim categories {sorted(declared) or ['factual_descriptor']} "
                                f"do not match the detected {claims or ['none']}")  # fmt: skip
            if claim.canonical_sha256 != text.canonical_digest(value):
                problems.append(f"{where}: the claim's canonical digest is not the statement's")
            if text.absolute_in(value) and not (claim.substantiation and claim.backup_owner):
                problems.append(
                    f"{where} makes an absolute claim; it needs independent substantiation and a backup owner"
                )
    return problems


def customer_text(kind: str, model: _Model):
    """(where, text, governed) for every customer-visible string (kept for callers of the earlier interface)."""
    for where, value, cls in text.visible_text(model):
        yield where, value, cls == text.STATEMENT and isinstance(model, Copy) and model.promise


def title(kind: str, model: _Model) -> str:
    for attr in ("name", "title", "statement"):
        value = getattr(model, attr, None)
        if value:
            return str(value)[:160]
    if isinstance(model, Pricing):
        return f"Pricing: {model.engine_product or 'card settings'}"
    if isinstance(model, Rule):
        return f"Rule: {model.type} {model.subject}"
    return kind


def references(kind: str, model: _Model) -> list[tuple[str, str]]:
    """(kind, key) pairs this document refers to; release validation checks each is in the release."""
    out: list[tuple[str, str]] = []

    def add(k: str, keys) -> None:
        out.extend((k, x) for x in keys if x)

    if isinstance(model, HomeConfig):
        add("property_type", [model.property_type])
        add("room_template", [r.room_template for r in model.rooms])
        add("package", model.packages)
    elif isinstance(model, RoomTemplate):
        add("media", [model.image, model.gallery])
        add("product", [p.product for p in model.included])
        add("extra", model.extras)
    elif isinstance(model, Product):
        add("product_family", [model.family])
        add("media", model.media)
        for v in model.variants:
            add("material", v.materials)
            add("hardware", v.hardware)
            add("media", v.media)
            for g in v.option_groups:
                for c in g.choices:
                    add("material", c.materials)
                    add("hardware", c.hardware)
                    add("media", c.media)
    elif isinstance(model, Extra):
        add("room_template", model.rooms)
        add("product", model.products + ((model.set_option.product,) if model.set_option else ()))
        add("media", model.media)
        add("material", model.materials)
        add("hardware", model.hardware)
    elif isinstance(model, Material):
        add("product", model.products)
        add("copy", model.statements)
    elif isinstance(model, Hardware):
        add("product_family", model.compatible_families)
        add("copy", model.statements)
    elif isinstance(model, Media):
        add("media", model.items)
        add("product", model.products)
        add("material", model.materials)
        if model.three_d:
            add("media", [model.three_d.preview_image, model.three_d.fallback_gallery])
            add("material", model.three_d.materials)
    elif isinstance(model, Package):
        add("copy", [model.public_summary, model.warranty_copy, model.badge, *model.material_promise,
                     *model.hardware_promise])  # fmt: skip
        add("product", model.included_products + model.optional_products)
        add("extra", model.included_extras + model.excluded_extras)
    elif isinstance(model, Copy) and model.applies_to is not None:
        add("product", model.applies_to.products)
        add("room_template", model.applies_to.rooms)
        add("package", model.applies_to.packages)
    elif isinstance(model, Rule):
        add("copy", [model.message])
        for path in (model.subject, *model.objects):
            k, rest = path.split(":", 1)
            add({"product": "product", "extra": "extra", "room": "room_template"}[k], [re.split(r"[#@]", rest)[0]])
    return out
