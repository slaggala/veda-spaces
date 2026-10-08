"""Customer-facing material specification (ADR-012 T9): `veda.estimator.customer-spec/1`.

A specification says what a package is made of, in customer language, per material category: the material
requirement, grade, thickness and finish, approved brand **examples**, the rule for an approved equivalent, and the
point at which the final selection is confirmed (the detailed quotation). It is public text: it carries **no amount,
price limit, cost, margin or rate**, and **no warranty duration** (owner decision T7: durations stay in the approved
warranty policy until the specification and the policy are reconciled). The validator refuses all of these.

**Room promises** (trust finalisation, Phase 3) are never generic: a category applies to a room only through what the
estimate actually priced there (`applies_to.lines`, as `PRODUCT.LINE` or `PRODUCT.*`), so a room without a soft-close
line is never told it has soft-close hardware, and a gypsum ceiling is never called plywood. `room_materials` builds each
room's one-line promise from the snapshot and the priced lines: one phrase per `line_group` (the first applicable
category of the group, in specification order), worded per product where `phrases` says so. Specifications without
line or product applicability (ESSENTIAL-1.0) give no room line.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA = "veda.estimator.customer-spec/1"
RoomCode = Literal[
    "KITCHEN",
    "UTILITY",
    "LIVING",
    "DINING",
    "MASTER_BEDROOM",
    "BEDROOM_2",
    "BEDROOM_3",
    "BEDROOM_4",
    "KIDS_ROOM",
    "STUDY",
    "POOJA",
    "WHOLE_HOME",
]
ROOMS = get_args(RoomCode)
Code = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
ProductCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]
LineRef = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}\.([A-Z][A-Z0-9_]{1,39}|\*)$")]
PhraseKey = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}(\.[A-Z][A-Z0-9_]{1,39})?$")]
Text = Annotated[str, Field(min_length=1, max_length=300)]
Short = Annotated[str, Field(min_length=1, max_length=160)]

# Public text never states money, prices or warranty periods (T4, T7).
_FORBIDDEN = (
    (re.compile(r"₹|\brs\.?\s*\d|\binr\b|\brupees?\b|\blakh", re.I), "an amount of money"),
    (
        # "ceiling" alone is a room feature (false ceiling); a price ceiling is caught by "price".
        re.compile(r"\b(price|prices|priced|cost|costs|margin|margins|rate|rates|credit|per sheet)\b", re.I),
        "pricing wording",
    ),
    (re.compile(r"\b\d+\s*[- ]?\s*(year|years|yr|yrs|month|months)\b", re.I), "a warranty or time duration"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "an email address"),
    (re.compile(r"(?:\+?91[\s-]?)?[6-9]\d{9}\b"), "a phone number"),
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Applicability(_Model):
    rooms: tuple[RoomCode, ...] = Field(min_length=1)
    products: tuple[ProductCode, ...] = ()
    lines: tuple[LineRef, ...] = ()  # the priced lines that carry this promise; takes precedence over products


class Category(_Model):
    code: Code
    label: Annotated[str, Field(min_length=1, max_length=80)]
    summary: Short  # the one-line material summary on a room card
    requirement: Text  # the material requirement (what is promised)
    grade: Short | None = None
    thickness: tuple[Short, ...] = ()
    finish: Short | None = None
    brand_examples: tuple[Annotated[str, Field(min_length=1, max_length=60)], ...] = ()
    equivalent_rule: Text
    final_selection: Text
    hardware_category: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    warranty_summary: Text
    applies_to: Applicability
    details: tuple[Text, ...] = ()
    line_group: Code | None = None  # shown in a room's one-line promise, once per group
    phrases: dict[PhraseKey, Short] = Field(default_factory=dict)  # room-line wording per PRODUCT or PRODUCT.LINE

    @model_validator(mode="after")
    def _phrases_follow_applicability(self):
        scope = {ref.split(".")[0] for ref in self.applies_to.lines} | set(self.applies_to.products)
        for key in self.phrases:
            if key.split(".")[0] not in scope:
                raise ValueError(f"phrase {key} names a product this category does not apply to")
        if self.phrases and self.line_group is None:
            raise ValueError("phrases are room-line wording; give the category a line_group")
        return self


class CustomerSpec(_Model):
    schema_: Literal["veda.estimator.customer-spec/1"] = Field(alias="schema")
    spec_code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9-]{1,30}-\d+\.\d+$")]
    version: Annotated[str, Field(pattern=r"^\d+\.\d+$")]
    package: Literal["ESSENTIAL", "PREMIUM", "LUXURY"]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    summary: Text
    effective_on: date
    equivalent_policy: Text
    final_selection: Text
    warranty_summary: Text
    categories: tuple[Category, ...] = Field(min_length=1, max_length=20)

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @model_validator(mode="after")
    def _consistent(self):
        if not self.spec_code.endswith(f"-{self.version}"):
            raise ValueError("spec_code must end with the version (for example ESSENTIAL-1.0)")
        codes = [c.code for c in self.categories]
        if len(set(codes)) != len(codes):
            raise ValueError("duplicate category codes")
        for where, text in _texts(self):
            for pattern, what in _FORBIDDEN:
                if pattern.search(text):
                    raise ValueError(f"{where} contains {what}; customer specifications never state it")
        return self


def _texts(spec: CustomerSpec):
    yield "name", spec.name
    yield "summary", spec.summary
    yield "equivalent_policy", spec.equivalent_policy
    yield "final_selection", spec.final_selection
    yield "warranty_summary", spec.warranty_summary
    for c in spec.categories:
        base = f"categories.{c.code}"
        for field in (
            "label",
            "summary",
            "requirement",
            "grade",
            "finish",
            "equivalent_rule",
            "final_selection",
            "hardware_category",
            "warranty_summary",
        ):
            value = getattr(c, field)
            if value:
                yield f"{base}.{field}", value
        for i, value in enumerate((*c.thickness, *c.brand_examples, *c.details, *c.phrases.values())):
            yield f"{base}[{i}]", value


def parse(document: dict) -> CustomerSpec:
    """Validate a customer specification document (raises pydantic.ValidationError)."""
    return CustomerSpec.model_validate(document)


def customer_view(document: dict) -> dict:
    """What the estimate response carries: the stored document's customer fields (it holds nothing else)."""
    spec = parse(document)
    return {
        "spec_code": spec.spec_code,
        "version": spec.version,
        "package": spec.package,
        "name": spec.name,
        "summary": spec.summary,
        "equivalent_policy": spec.equivalent_policy,
        "final_selection": spec.final_selection,
        "warranty_summary": spec.warranty_summary,
        "categories": [
            {
                "code": c.code,
                "label": c.label,
                "summary": c.summary,
                "requirement": c.requirement,
                "grade": c.grade,
                "thickness": list(c.thickness),
                "finish": c.finish,
                "brand_examples": list(c.brand_examples),
                "equivalent_rule": c.equivalent_rule,
                "final_selection": c.final_selection,
                "warranty_summary": c.warranty_summary,
                "rooms": list(c.applies_to.rooms),
                "details": list(c.details),
            }
            for c in spec.categories
        ],
    }


def _applies(category: Category, room: str, priced: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The priced (product, line) pairs in `room` that carry this category's promise ([] when it does not apply)."""
    scope = category.applies_to
    if room not in scope.rooms:
        return []
    if scope.lines:
        refs = set(scope.lines)
        return [(p, ln) for p, ln in priced if f"{p}.{ln}" in refs or f"{p}.*" in refs]
    if scope.products:
        return [(p, ln) for p, ln in priced if p in scope.products]
    return list(priced)


def room_materials(document: dict, priced: dict[str, list[tuple[str, str]]]) -> dict[str, dict]:
    """Each room's material promise, from the specification snapshot and the lines the estimate priced in that room.

    `priced` maps a room code to its (product, line) pairs. Returns {room: {"line": str | None, "categories": [code]}}:
    `categories` lists every category that applies (for the room's material details) and `line` joins one phrase per
    line group. A phrase is the product- or line-specific wording when every priced line of the category in the room
    agrees on it, and the category summary otherwise. Deterministic: the same snapshot and lines give the same text.
    """
    spec = parse(document)
    out: dict[str, dict] = {}
    for room, lines in priced.items():
        applicable: list[tuple[Category, list[tuple[str, str]]]] = []
        for c in spec.categories:
            matched = _applies(c, room, lines)
            if matched:
                applicable.append((c, matched))
        groups: dict[str, str] = {}
        for c, matched in applicable:
            if c.line_group is None or c.line_group in groups:
                continue
            words = list(
                dict.fromkeys(c.phrases.get(f"{p}.{ln}") or c.phrases.get(p) or c.summary for p, ln in matched)
            )
            groups[c.line_group] = words[0] if len(words) == 1 else c.summary
        out[room] = {"line": " · ".join(groups.values()) or None, "categories": [c.code for c, _ in applicable]}
    return out
