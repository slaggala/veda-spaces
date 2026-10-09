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

import hashlib
import re
import types
import typing
import unicodedata
from collections.abc import Iterator

from pydantic import BaseModel

from veda.modules.estimator import customer_spec

# --- canonical normalisation (canonical customer-copy closure) -----------------------------------------------------
# One normalisation for every check: claims, promises, rates, controlled-copy matching, release validation and the
# public serialisers' defence-in-depth check. The approved display text is never rewritten; newly authored text with
# invisible or formatting characters is refused (`invisible_chars`), and detection runs on the canonical forms.
_CONFUSABLES = str.maketrans({
    # Cyrillic and Greek letters that look like Latin ones (after case folding), and a few Latin lookalikes.
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c", "т": "t",
    "у": "y", "х": "x", "і": "i", "ї": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ӏ": "l", "һ": "h", "ԛ": "q", "ԝ": "w",
    "ɡ": "g", "ı": "i", "ℓ": "l", "ο": "o", "α": "a", "ν": "v", "ι": "i", "κ": "k", "ρ": "p", "τ": "t", "υ": "u",
    "χ": "x", "ε": "e", "β": "b", "η": "n", "μ": "u", "ς": "s", "σ": "o",
})  # fmt: skip
_SEPARATOR = re.compile(r"[\s_/\\.:|·•‧∙⁄,;!?¡¿\"“”„«»()\[\]{}*~^`+=<>]+")
_APOSTROPHE = re.compile(r"['’‘ʼ`´]")
_SPACED_LETTERS = re.compile(r"\b(?:[a-z0-9] ){2,}[a-z0-9]\b")  # "b e s t" → "best" (letter-spacing evasion)
# Factual compounds whose parts would otherwise read as claims (kept narrow on purpose).
_FACTUAL_COMPOUNDS = re.compile(
    r"\b(?:free ?standing|hands ?free|top ?hung|top ?mounted|best ?fit ?hinge|leading ?edges?)\b"
)


def _invisible(ch: str) -> bool:
    cp = ord(ch)
    return (
        (unicodedata.category(ch) in ("Cf", "Cc", "Co", "Cs", "Cn") and ch not in "\t\n\r")
        or 0xFE00 <= cp <= 0xFE0F
        or 0xE0100 <= cp <= 0xE01EF
        or 0x180B <= cp <= 0x180F
        or cp == 0x034F
    )


def invisible_chars(text: str) -> list[str]:
    """The invisible or formatting characters in a text (zero-width, joiners, word joiner, BOM, soft hyphen,
    directional controls, variation selectors and other format or control characters). New customer text with any of
    them is refused."""
    return sorted({f"U+{ord(ch):04X}" for ch in text if _invisible(ch)})


def _base(text: str) -> str:
    s = unicodedata.normalize("NFKC", text)  # fullwidth and compatibility forms, ligatures, non-breaking spaces
    s = "".join(ch for ch in s if not _invisible(ch)).casefold().translate(_CONFUSABLES)
    s = "".join(" " if unicodedata.category(ch) in ("Zs", "Zl", "Zp") else ch for ch in s)
    return s


_SLASHES = str.maketrans({"\u2044": "/", "\u2215": "/", "\u29f8": "/", "\uff0f": "/", "\u2216": "\\"})


def numeric_form(text: str) -> str:
    """Canonical form that keeps digits and punctuation (for amounts and rates)."""
    s = "".join("-" if unicodedata.category(ch) == "Pd" else ch for ch in _base(text)).translate(_SLASHES)
    s = re.sub(r"\bpercent\b|\bpct\b|\bper cent\b", "%", s)
    return re.sub(r"\s+", " ", s).strip()


def canonical(text: str) -> str:
    """The comparison form: NFKC, case-folded, invisible characters removed, lookalikes mapped, every separator
    (space, underscore, any dash, slash, backslash, dot, colon, pipe, punctuation) a single space, letter-spaced runs
    joined. Detection matches whole words and phrases in this form, never substrings."""
    s = "".join(" " if unicodedata.category(ch) == "Pd" else ch for ch in _base(text))
    s = _APOSTROPHE.sub("", s)
    s = _SEPARATOR.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = _SPACED_LETTERS.sub(lambda m: m.group(0).replace(" ", ""), s)
    return re.sub(r"\s+", " ", _FACTUAL_COMPOUNDS.sub(" ", s)).strip()


def canonical_digest(text: str) -> str:
    return hashlib.sha256(canonical(text).encode()).hexdigest()


def display_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# --- vocabulary (matched on the canonical form) -------------------------------------------------------------------
def _words(*alternatives: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alternatives) + r")(?![a-z0-9])")


# Promise wording (R2/R3): only a promise copy record linked to a confirmed promise-matrix row may say it. Warranty,
# service and delivery claims are promises: they are governed by the promise matrix.
PROMISE = _words(
    r"warrant\w*", r"guarantee\w*", r"assur\w*", r"certif\w*", r"lifetime", r"life ?long", r"free", r"complimentary",
    r"no cost", r"includ\w*", r"inclusive", r"exclud\w*", r"install\w*", r"deliver\w*", r"dispatch\w*", r"timeline\w*",
    r"on ?time", r"deadline\w*", r"\d+ ?(?:days?|weeks?|months?|years?|hours?|hrs?)", r"within \w+ (?:days?|hours?)",
    r"grade\w*", r"bwr", r"bwp", r"mr", r"e[0-2]", r"is ?\d+", r"marine", r"water ?proof", r"\w+ ?proof",
    r"termite\w*", r"borer\w*", r"brand\w*", r"genuine", r"original", r"hettich", r"hafele", r"hafele", r"blum", r"ebco",
    r"century", r"greenply", r"merino", r"greenlam", r"airolam", r"servic\w*", r"support\w*", r"after ?sales",
    r"maintenance(?: free)?", r"repair\w*", r"replac\w*", r"soft ?clos\w*", r"call ?back\w*", r"one ?day",
    r"24 ?(?:x ?)?7",
)  # fmt: skip

MARKETING = ("ranking", "price", "popularity", "recommendation", "quality", "promotional")  # need claim governance
CLAIMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ranking", _words(r"best", r"finest", r"no ?1", r"number ?(?:one|1)", r"# ?1", r"first choice", r"top (?:rated|ranked)",
                       r"leading", r"unbeatable", r"unmatched", r"world class", r"best in class", r"second to none",
                       r"(?:india|hyderabad|bengaluru|bangalore)s (?:best|leading|favou?rite|top)")),
    ("price", _words(r"cheapest", r"lowest", r"budget friendly", r"affordabl\w*", r"value for money", r"bargain\w*",
                     r"best price", r"price match\w*", r"most economical")),
    ("popularity", _words(r"best ?sell\w*", r"most (?:popular|chosen|loved|ordered|wanted|requested|booked)", r"popular",
                          r"trending", r"favou?rite\w*", r"top (?:choice|seller|selling)", r"in demand", r"hot ?selling")),
    ("recommendation", _words(r"recommend\w*", r"(?:our|editors|staff|designers|experts) (?:premium )?(?:pick|choice)",
                              r"premium (?:pick|choice)", r"luxury (?:pick|choice)", r"must ?have", r"top pick")),
    ("quality", _words(r"premium (?:quality|grade|finish|range|selection|materials?|look|feel)", r"our premium",
                       r"(?:high|highest|best|top|superior|finest|great|excellent|premium|world class) quality",
                       r"luxur\w* (?:finish|look|feel|quality|living)", r"superior", r"flawless", r"perfect\w*",
                       r"top notch", r"impeccable")),
    ("promotional", _words(r"free", r"limited (?:time|period|offer|stock|edition)", r"offer ends? soon", r"ends soon",
                           r"(?:special|exclusive|festive|launch|introductory|seasonal|today s) offers?", r"exclusiv\w*",
                           r"discount\w*", r"sale", r"deals?", r"bonus", r"gift\w*", r"save (?:up to|\d)", r"hurry",
                           r"today only", r"new arrivals?", r"\d+ ?% ?off", r"% ?off", r"cash ?back", r"coupon\w*",
                           r"promo\w*", r"flat \d+ ?%", r"up ?to \d+ ?%")),
    ("warranty", _words(r"lifetime", r"warrant\w*", r"guarantee\w*", r"certif\w*", r"\w+ ?proof", r"maintenance free",
                        r"water ?proof")),
    ("service", _words(r"(?:guaranteed |on ?time )?deliver\w*", r"one ?day call ?back", r"call ?back\w*",
                       r"free (?:service|consultation|visit|design)", r"24 ?(?:x ?)?7", r"after ?sales", r"servic\w*")),
)  # fmt: skip
# Claims that stay prohibited unless independently substantiated and explicitly approved.
ABSOLUTE = _words(r"best", r"no ?1", r"number ?(?:one|1)", r"# ?1", r"first choice", r"cheapest", r"lowest",
                  r"guarantee\w*", r"unbeatable", r"unmatched", r"finest", r"highest quality", r"leading")  # fmt: skip

# Rates and prices (matched on the numeric form). Public totals are numbers in their own fields, never text.
RATES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("a currency amount", re.compile(r"(?:₹|\brs\b\.?|\binr\b|\brupees?\b)\s*[\d.,]+")),
    ("an amount written with /-", re.compile(r"\d\s*/\s*-")),
    ("a grouped amount", re.compile(r"(?<![\d.])\d{1,3}(?:,\d{2,3})+(?![\d])")),
    ("a per-area rate", re.compile(
        r"\d[\d.,]*\s*k?\s*(?:/|per|an?|each)?\s*(?:sq\.?\s*f(?:ee)?t|sq\.?\s*ft\.?|sqft|sft|rft|r\.?\s*f\.?\s*t|"
        r"r\.?\s*ft|psf|p\.?s\.?f|sq\.?\s*m|sqm|running\s*f(?:oo|ee)t|rf|r\.?m|rmt)\b")),
    ("a per-unit rate", re.compile(r"\d[\d.,]*\s*k?\s*(?:/|per|each)\s*(?:unit|piece|pc|nos?|item)\b")),
    ("a rate per unit", re.compile(r"(?:/|\bper\b)\s*(?:sq\.?\s*f(?:ee)?t|sqft|sft|rft|psf|running\s*f(?:oo|ee)t|sq\.?\s*m)\b")),
    ("an amount in thousands", re.compile(r"(?<![\w.])\d+(?:\.\d+)?\s*k\b")),
    ("a percentage discount", re.compile(r"\d+(?:\.\d+)?\s*%\s*(?:off|discount|cash\s*back|less|saving)|"
                                         r"(?:flat|up\s*to|upto|extra)\s*\d+(?:\.\d+)?\s*%")),
    ("internal commercial wording", re.compile(
        r"\b(?:mrp|margins?|mark\s*-?\s*ups?|procurement|supplier|suppliers|dealer|wholesale|cost\s*price|"
        r"purchase\s*price|landed\s*cost|price\s*(?:cap|ceiling|list)|ceiling\s*price|cashback|emi)\b")),
)  # fmt: skip


def claims_in(text: str) -> list[str]:
    """The claim categories a text makes (empty for factual text), detected on its canonical form."""
    form = canonical(text)
    return sorted({category for category, pattern in CLAIMS if pattern.search(form)})


def marketing_claims_in(text: str) -> list[str]:
    return [c for c in claims_in(text) if c in MARKETING]


def promise_in(text: str) -> bool:
    return bool(PROMISE.search(canonical(text)))


def absolute_in(text: str) -> bool:
    return bool(ABSOLUTE.search(canonical(text)))


def rate_in(text: str) -> str | None:
    """Why a text could leak a rate or price (None when it cannot)."""
    form = numeric_form(text)
    for what, pattern in RATES:
        if pattern.search(form):
            return what
    return None


def forbidden_in(text: str) -> str | None:
    """Content never allowed in customer text: amounts and rates, pricing words, durations, contact details. Checked
    on both the original and the numeric form, so lookalikes and invisible characters do not hide it."""
    for candidate in (text, numeric_form(text), canonical(text)):
        for pattern, what in customer_spec._FORBIDDEN:
            if pattern.search(candidate):
                return what
    return rate_in(text)


def leak_in(text: str) -> str | None:
    """Content never allowed even in promise-governed estimator text (which may state a timeline or the word price):
    an amount of money, a rate or internal commercial wording, an email address or a phone number."""
    money, _words_, _duration, email, phone = customer_spec._FORBIDDEN
    for candidate in (text, numeric_form(text), canonical(text)):
        for pattern, what in (money, email, phone):
            if pattern.search(candidate):
                return what
    return rate_in(text)


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
    ("ClaimGovernance", "categories"): STAFF, ("ClaimGovernance", "status"): STAFF,
    ("ClaimGovernance", "source"): STAFF, ("ClaimGovernance", "evidence_reference"): STAFF,
    ("ClaimGovernance", "evidence_period"): STAFF, ("ClaimGovernance", "owner"): STAFF,
    ("ClaimGovernance", "backup_owner"): STAFF, ("ClaimGovernance", "approver"): STAFF,
    ("ClaimGovernance", "non_expiring_policy"): STAFF, ("ClaimGovernance", "environments"): STAFF,
    ("ClaimGovernance", "substantiation"): STAFF, ("ClaimGovernance", "canonical_sha256"): STAFF,
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
