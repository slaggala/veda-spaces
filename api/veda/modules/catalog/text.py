"""Customer-visible text governance (V3 customer-safety closure).

**Field classes.** Every string-bearing field of every catalog document model is classified in FIELD_CLASSES:

| Class | Meaning |
|---|---|
| `factual` | Free text a customer can read (a name, description, label or caption). It may carry no promise wording, no marketing claim and none of the always-forbidden content: amounts, pricing words, durations, contact details |
| `statement` | A copy record's statement, the only place a promise or claim may be made. A promise needs its promise-matrix row (ESSENTIAL-1.1); a claim needs its claim governance; otherwise it is held to the factual rule |
| `staff` | Never sent to customers (stripped from the customer view) |
| `identifier` | A key, code, closed choice, hash, URL or date; not prose |

`tests/unit/test_catalog_text_inventory.py` enumerates the models' fields by type and fails when a string-bearing field is
missing from FIELD_CLASSES, so a new customer-visible field cannot ship unclassified. The inventory document
(`docs/implementation/catalog/CATALOG-V3-customer-text-inventory.md`) is generated from this registry and checked to
be current.

**Claims** are matched as words and phrases, never substrings. "Premium" or "Luxury" alone name a package tier (a
fact); "premium pick", "premium quality" and "luxury choice" are claims. "Top shelf", "countertop" and
"space-saving" are facts; "top rated", "save up to" and "best" are claims.
"""

from __future__ import annotations

import re
import types
import typing
from collections.abc import Iterator

from pydantic import BaseModel

from veda.modules.estimator import customer_spec

# --- vocabulary ---------------------------------------------------------------------------------------------------
# Promise wording (R2/R3): only a promise copy record linked to a confirmed promise-matrix row may say it.
PROMISE = re.compile(
    r"\b("
    r"warrant\w*|guarantee\w*|assur\w*|certif\w*|lifetime|life-long|"
    r"free|complimentary|no[- ]cost|includ\w*|inclusive|exclud\w*|"
    r"install\w*|deliver\w*|dispatch\w*|timeline\w*|on[- ]time|deadline\w*|\d+\s*(?:days?|weeks?|months?|years?)|"
    r"grade\w*|BWR|BWP|MR|E[0-2]|IS[ :-]?\d+|marine|waterproof|termite\w*|borer\w*|"
    r"brand\w*|genuine|original|hettich|hafele|häfele|blum|ebco|century|greenply|merino|greenlam|airolam|"
    r"servic\w*|support\w*|after[- ]sales|maintenance|repair\w*|replac\w*|"
    r"soft[- ]clos\w*"
    r")\b",
    re.I,
)

_S = r"[\s-]*"  # space or hyphen between the words of a phrase
CLAIMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ranking",
        re.compile(
            rf"\bbest\b|\bno\.?{_S}1\b|#{_S}1\b|\bnumber{_S}one\b|\bunbeatable\b|\bunmatched\b|"
            rf"\btop{_S}(?:rated|ranked|sell\w*|pick|choice|quality|brand|class)\b|\bworld{_S}class\b|"
            rf"\bleading\b|\b(?:india|hyderabad)'?s{_S}(?:best|favourite|favorite|leading)\b",
            re.I,
        ),
    ),
    (
        "price",
        re.compile(
            rf"\bcheapest\b|\blowest\b|\bunbeatable\b|\bbudget{_S}friendly\b|\baffordabl\w*\b|"
            rf"\bvalue{_S}for{_S}money\b|\bbargain\w*\b",
            re.I,
        ),
    ),
    (
        "popularity",
        re.compile(
            rf"\bmost{_S}(?:popular|chosen|loved|ordered|wanted|requested)\b|\bpopular\b|"
            rf"\bbest{_S}?sell\w*\b|\btrending\b|\bfavou?rite\b|\bcustomer{_S}favou?rite\b",
            re.I,
        ),
    ),
    (
        "recommendation",
        re.compile(
            rf"\brecommend\w*\b|\b(?:our|editor'?s|staff|designer'?s){_S}(?:premium{_S})?pick\b|"
            rf"\bmust{_S}have\b",
            re.I,
        ),
    ),
    (
        "quality",
        re.compile(
            rf"\bpremium{_S}(?:pick|choice|quality|grade|finish|range|selection|materials?|look|feel)\b|"
            rf"\bour{_S}premium\b|\b(?:high|best|top|superior|finest|great|excellent|premium){_S}quality\b|"
            rf"\bluxur\w*{_S}(?:choice|pick|finish|look|feel|quality|living)\b|\bfinest\b|\bsuperior\b|"
            rf"\bflawless\b|\bperfect\w*\b|\bbest{_S}in{_S}class\b",
            re.I,
        ),
    ),
    (
        "promotional",
        re.compile(
            rf"\blimited{_S}(?:time|period|offer|stock|edition)\b|"
            rf"\b(?:special|exclusive|festive|launch|introductory|seasonal){_S}offers?\b|"
            rf"\bexclusiv\w*\b|\bdiscount\w*\b|\bsale\b|\bdeals?\b|\bbonus\b|\bgift\w*\b|"
            rf"\bsave{_S}(?:up{_S}to|\d)|\bhurry\b|\btoday{_S}only\b|\bnew{_S}arrival\w*\b",
            re.I,
        ),
    ),
)
# Claims that stay prohibited unless independently substantiated and explicitly approved.
ABSOLUTE = re.compile(
    rf"\bbest\b|\bno\.?{_S}1\b|#{_S}1\b|\bnumber{_S}one\b|\bcheapest\b|\blowest\b|\bguarantee\w*\b|"
    rf"\bunbeatable\b|\bunmatched\b",
    re.I,
)


def claims_in(text: str) -> list[str]:
    """The claim categories a text makes (empty for factual text)."""
    return sorted({category for category, pattern in CLAIMS if pattern.search(text)})


def forbidden_in(text: str) -> str | None:
    """Content never allowed in customer text (amounts, pricing words, durations, contact details)."""
    for pattern, what in customer_spec._FORBIDDEN:
        if pattern.search(text):
            return what
    return None


# --- field inventory ----------------------------------------------------------------------------------------------
FACTUAL, STATEMENT, STAFF, IDENTIFIER = "factual", "statement", "staff", "identifier"
# (model that declares the field, field) -> class. Inherited fields are keyed by the declaring base (Described).
FIELD_CLASSES: dict[tuple[str, str], str] = {
    # Described: every customer-facing record
    ("Described", "name"): FACTUAL, ("Described", "description"): FACTUAL,
    ("Described", "what_is_this"): FACTUAL, ("Described", "typically_used_for"): FACTUAL,
    ("Described", "staff_note"): STAFF, ("Described", "visibility"): IDENTIFIER,
    ("Availability", "markets"): IDENTIFIER, ("Availability", "property_types"): IDENTIFIER,
    ("Availability", "home_sizes"): IDENTIFIER, ("Availability", "project_kinds"): IDENTIFIER,
    ("PropertyType", "code"): IDENTIFIER,
    ("RoomSlot", "room_template"): IDENTIFIER,
    ("HomeConfig", "property_type"): IDENTIFIER, ("HomeConfig", "home_size"): IDENTIFIER,
    ("HomeConfig", "packages"): IDENTIFIER,
    ("ProductSlot", "product"): IDENTIFIER, ("ProductSlot", "variant"): IDENTIFIER, ("ProductSlot", "options"): IDENTIFIER,
    ("RoomTemplate", "room_code"): IDENTIFIER, ("RoomTemplate", "image"): IDENTIFIER,
    ("RoomTemplate", "gallery"): IDENTIFIER, ("RoomTemplate", "extras"): IDENTIFIER,
    ("ProductFamily", "category"): IDENTIFIER,
    ("MeasurementPrompt", "input"): IDENTIFIER, ("MeasurementPrompt", "label"): FACTUAL,
    ("MeasurementPrompt", "unit"): IDENTIFIER, ("MeasurementPrompt", "hint"): FACTUAL,
    ("Choice", "key"): IDENTIFIER, ("Choice", "engine_options"): IDENTIFIER, ("Choice", "materials"): IDENTIFIER,
    ("Choice", "hardware"): IDENTIFIER, ("Choice", "media"): IDENTIFIER,
    ("OptionGroup", "key"): IDENTIFIER, ("OptionGroup", "name"): FACTUAL, ("OptionGroup", "description"): FACTUAL,
    ("OptionGroup", "default"): IDENTIFIER,
    ("Variant", "key"): IDENTIFIER, ("Variant", "engine_product"): IDENTIFIER, ("Variant", "engine_options"): IDENTIFIER,
    ("Variant", "materials"): IDENTIFIER, ("Variant", "hardware"): IDENTIFIER, ("Variant", "media"): IDENTIFIER,
    ("Product", "family"): IDENTIFIER, ("Product", "default_variant"): IDENTIFIER, ("Product", "rooms"): IDENTIFIER,
    ("Product", "packages"): IDENTIFIER, ("Product", "media"): IDENTIFIER,
    ("AddSelection", "engine_product"): IDENTIFIER, ("AddSelection", "engine_options"): IDENTIFIER,
    ("SetOption", "product"): IDENTIFIER, ("SetOption", "group"): IDENTIFIER, ("SetOption", "choice"): IDENTIFIER,
    ("Extra", "kind"): IDENTIFIER, ("Extra", "quantity"): IDENTIFIER, ("Extra", "rooms"): IDENTIFIER,
    ("Extra", "products"): IDENTIFIER, ("Extra", "media"): IDENTIFIER, ("Extra", "materials"): IDENTIFIER,
    ("Extra", "hardware"): IDENTIFIER,
    ("Material", "category"): IDENTIFIER, ("Material", "grade"): STAFF, ("Material", "thickness"): STAFF,
    ("Material", "finish"): FACTUAL, ("Material", "colour_family"): FACTUAL, ("Material", "texture"): FACTUAL,
    ("Material", "brands"): STAFF, ("Material", "wet_area"): IDENTIFIER, ("Material", "rooms"): IDENTIFIER,
    ("Material", "products"): IDENTIFIER, ("Material", "statements"): IDENTIFIER, ("Material", "warranty_source"): STAFF,
    ("Hardware", "category"): IDENTIFIER, ("Hardware", "compatible_families"): STAFF, ("Hardware", "brands"): STAFF,
    ("Hardware", "statements"): IDENTIFIER, ("Hardware", "warranty_source"): STAFF,
    ("Rights", "owner"): FACTUAL,  # shown as the attribution when the media has none
    ("Rights", "licence"): STAFF, ("Rights", "usage"): STAFF, ("Rights", "consent_reference"): STAFF,
    ("Objects", "source"): STAFF, ("Objects", "variants"): IDENTIFIER,
    ("Hotspot", "key"): IDENTIFIER, ("Hotspot", "label"): FACTUAL,
    ("CameraPreset", "key"): IDENTIFIER, ("CameraPreset", "label"): FACTUAL, ("CameraPreset", "orbit"): FACTUAL,
    ("CameraPreset", "target"): FACTUAL,
    ("ThreeD", "model_version"): IDENTIFIER, ("ThreeD", "preview_image"): IDENTIFIER,
    ("ThreeD", "fallback_gallery"): IDENTIFIER, ("ThreeD", "supported_devices"): IDENTIFIER,
    ("ThreeD", "dimensions_mm"): IDENTIFIER, ("ThreeD", "materials"): IDENTIFIER, ("ThreeD", "variant_map"): FACTUAL,
    ("ThreeD", "finish_map"): FACTUAL,
    ("Media", "type"): IDENTIFIER, ("Media", "title"): FACTUAL, ("Media", "alt"): FACTUAL, ("Media", "caption"): FACTUAL,
    ("Media", "label"): IDENTIFIER, ("Media", "attribution"): FACTUAL, ("Media", "items"): IDENTIFIER,
    ("Media", "embed_url"): IDENTIFIER, ("Media", "tags"): IDENTIFIER, ("Media", "rooms"): IDENTIFIER,
    ("Media", "products"): IDENTIFIER, ("Media", "materials"): IDENTIFIER, ("Media", "packages"): IDENTIFIER,
    ("Package", "engine_package"): IDENTIFIER, ("Package", "public_summary"): IDENTIFIER,
    ("Package", "included_products"): IDENTIFIER, ("Package", "optional_products"): IDENTIFIER,
    ("Package", "included_extras"): IDENTIFIER, ("Package", "excluded_extras"): IDENTIFIER,
    ("Package", "material_promise"): IDENTIFIER, ("Package", "hardware_promise"): IDENTIFIER,
    ("Package", "warranty_copy"): IDENTIFIER, ("Package", "badge"): IDENTIFIER,
    ("Pricing", "scope"): STAFF, ("Pricing", "engine_product"): STAFF, ("Pricing", "body"): STAFF, ("Pricing", "note"): STAFF,
    ("Condition", "property_types"): IDENTIFIER, ("Condition", "home_sizes"): IDENTIFIER,
    ("Condition", "project_kinds"): IDENTIFIER, ("Condition", "packages"): IDENTIFIER, ("Condition", "markets"): IDENTIFIER,
    ("Rule", "type"): IDENTIFIER, ("Rule", "subject"): IDENTIFIER, ("Rule", "objects"): IDENTIFIER,
    ("Rule", "input"): IDENTIFIER, ("Rule", "message"): IDENTIFIER, ("Rule", "note"): STAFF,
    ("Governance", "owner"): STAFF, ("Governance", "backup"): STAFF, ("Governance", "quotation_mapping"): STAFF,
    ("Governance", "verification"): STAFF, ("Governance", "warranty_source"): STAFF, ("Governance", "status"): STAFF,
    ("AppliesTo", "products"): IDENTIFIER, ("AppliesTo", "rooms"): IDENTIFIER, ("AppliesTo", "packages"): IDENTIFIER,
    ("ClaimGovernance", "category"): STAFF, ("ClaimGovernance", "status"): STAFF, ("ClaimGovernance", "source"): STAFF,
    ("ClaimGovernance", "owner"): STAFF, ("ClaimGovernance", "substantiation"): STAFF,
    ("Copy", "statement"): STATEMENT, ("Copy", "category"): IDENTIFIER, ("Copy", "matrix_row"): STAFF,
}  # fmt: skip
# Fields the remediation instruction names that the catalog does not have (and so cannot carry text).
NOT_IN_SCHEMA = ("product short name", "product subtitle", "recommendation label", "ribbon", "promotional label",
                 "customer confirmation message")  # fmt: skip


def _has_str(annotation: object) -> bool:
    origin = typing.get_origin(annotation)
    if annotation is str:
        return True
    if origin is typing.Literal:
        return any(isinstance(a, str) for a in typing.get_args(annotation))
    if origin in (typing.Annotated,):
        return _has_str(typing.get_args(annotation)[0])
    return (
        any(_has_str(a) for a in typing.get_args(annotation))
        if origin is not None or isinstance(annotation, types.UnionType)
        else False
    )


def _models(annotation: object) -> Iterator[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
    for arg in typing.get_args(annotation):
        yield from _models(arg)


def declaring_class(cls: type[BaseModel], field: str) -> str:
    for klass in cls.__mro__:
        if field in klass.__dict__.get("__annotations__", {}):
            return klass.__name__
    return cls.__name__


def string_fields(roots: typing.Iterable[type[BaseModel]]) -> set[tuple[str, str]]:
    """Every (declaring model, field) holding text anywhere under the given models, found by type."""
    found: set[tuple[str, str]] = set()
    seen: set[type[BaseModel]] = set()
    pending = list(roots)
    while pending:
        cls = pending.pop()
        if cls in seen:
            continue
        seen.add(cls)
        for name, info in cls.model_fields.items():
            if _has_str(info.annotation):
                found.add((declaring_class(cls, name), name))
            pending.extend(_models(info.annotation))
    return found


def field_class(model: BaseModel, field: str) -> str:
    key = (declaring_class(type(model), field), field)
    if key not in FIELD_CLASSES:
        raise KeyError(f"customer-text field {key} is not classified")  # fails closed; the inventory test catches it
    return FIELD_CLASSES[key]


def _strings(value: object) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield "", value
    elif isinstance(value, (tuple, list)):
        for i, v in enumerate(value):
            for sub, text in _strings(v):
                yield f"[{i}]{sub}", text
    elif isinstance(value, dict):
        for k, v in value.items():
            for sub, text in _strings(v):
                yield f".{k}{sub}", text


def visible_text(model: BaseModel, prefix: str = "") -> Iterator[tuple[str, str, str]]:
    """(path, text, class) for every factual or statement string a customer can read in this document, walking nested
    models; staff-only records, variants and choices are skipped (no customer sees them)."""
    if getattr(model, "visibility", "customer") == "staff":
        return
    for name in type(model).model_fields:
        value = getattr(model, name)
        if value is None:
            continue
        path = f"{prefix}{name}"
        nested = [v for v in (value if isinstance(value, (tuple, list)) else [value]) if isinstance(v, BaseModel)]
        if nested:
            for i, child in enumerate(nested):
                yield from visible_text(child, f"{path}[{i}]." if isinstance(value, (tuple, list)) else f"{path}.")
            continue
        if isinstance(value, dict) and any(isinstance(v, BaseModel) for v in value.values()):
            for k, child in value.items():
                if isinstance(child, BaseModel):
                    yield from visible_text(child, f"{path}.{k}.")
            continue
        if not _has_str(type(model).model_fields[name].annotation):
            continue
        cls = field_class(model, name)
        if cls in (FACTUAL, STATEMENT):
            for sub, text in _strings(value):
                yield f"{path}{sub}", text, cls
