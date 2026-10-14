"""The versioned B2 scope ruleset (blueprint §8.1; a tracked deviation like B1-06: a code fixture until Catalogue V3
administration is active, then ``scope_rule`` records).

``fixtures/scope-rules-<version>.json`` holds:

- **item types**: what each requirement type is quoted as: the rate-card product it maps to (or none, for items the
  card has no line for yet), options fixed by the type, how each card input is derived from verified measurements,
  and option rules;
- **rules**: which requirements a space (or the project) gets, from its type and from measured facts (a tagged wall,
  a captured electrical point, a proposed partition), with a recommendation strength and an origin.

The content is the owner's to decide (OI-MTQ-03, OI-MTQ-04). Until the register records both, the file's ``status`` is
PROPOSED and every scope built from it carries that status; quotations built on it are not customer-issuable. The
file is validated strictly at import, and its SHA-256 is pinned on every scope.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from veda.modules.mtq import vocab as SV

from . import vocab as V

RULESET_VERSION = "2026.10.2"
FIXTURE = Path(__file__).with_name("fixtures") / f"scope-rules-{RULESET_VERSION}.json"
APPROVED_STATUS = "APPROVED"

INPUT_KINDS = (
    "wall_run",  # the longest stretch of the anchor (or first tagged) wall clear of openings
    "tagged_run_total",  # Σ stretches clear of openings over every wall with the tag
    "window_span",  # the span across the listed window openings of the anchor (or first tagged) wall
    "lintel_capped",  # min(floor to lintel, cap); the cap when the lintel was not captured (ASSUMED)
    "wall_height",  # the tagged wall's own height, else the ceiling height
    "floor_area",  # the space's derived floor area
    "perimeter",  # the space's derived perimeter
    "door_width",  # the one door of a space of the listed types (its own door frame); elsewhere a staff entry
    "partition_length",  # Σ proposed partition walls
    "partition_height",  # the proposed partition's height, else the ceiling height
    "property_floor_area",  # Σ floor area of in-scope spaces in the listed zones
    "property_net_wall_area",  # Σ net wall area of in-scope spaces in the listed zones
    "electrical_count",  # Σ captured electrical points of the listed types and statuses
    "staff",  # no derivation: staff enter it (with a reason) on the scope item
)


# Opening types that are above the floor by definition: a base (counter) run continues beneath them unless B1 recorded
# the opening at floor level (sill 0). Every other opening type (doors, French windows, arches, shafts...) cuts it.
ABOVE_FLOOR_OPENINGS = ("WINDOW", "VENTILATOR", "AC_SLEEVE")
DEDUCTIONS = ("all_openings", "floor_openings")


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InputRule(_Closed):
    kind: str
    tag: str | None = None
    cap_mm: int | None = Field(default=None, gt=0, le=6000)
    zones: tuple[str, ...] = ()
    types: tuple[str, ...] | None = None
    statuses: tuple[str, ...] = ()
    deduct: str = "all_openings"  # which openings cut a run (wall_run, tagged_run_total)
    opening_types: tuple[str, ...] = ()  # window_span: the openings spanned
    space_types: tuple[str, ...] = ()  # door_width: the space types whose own door it is
    explain: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.kind not in INPUT_KINDS:
            raise ValueError(f"unknown input kind {self.kind}")
        if self.deduct not in DEDUCTIONS:
            raise ValueError(f"unknown deduction {self.deduct}")
        if self.deduct != "all_openings" and self.kind not in ("wall_run", "tagged_run_total"):
            raise ValueError("only a run takes a deduction mode")
        if self.kind == "window_span" and (not self.opening_types or self.tag is None):
            raise ValueError("window_span needs a tag and opening types")
        for o in self.opening_types:
            if o not in SV.OPENING_TYPES:
                raise ValueError(f"unknown opening type {o}")
        if self.kind == "door_width" and not self.space_types:
            raise ValueError("door_width names the space types whose own door it is")
        for st in self.space_types:
            if st not in SV.SPACE_TYPES:
                raise ValueError(f"unknown space type {st}")
        if self.tag is not None and self.tag not in SV.WALL_TAGS:
            raise ValueError(f"unknown wall tag {self.tag}")
        if self.kind == "lintel_capped" and self.cap_mm is None:
            raise ValueError("lintel_capped needs cap_mm")
        for z in self.zones:
            if z not in SV.ZONES:
                raise ValueError(f"unknown zone {z}")
        for t in self.types or ():
            if t not in SV.ELECTRICAL_POINT_TYPES:
                raise ValueError(f"unknown electrical point type {t}")
        for st in self.statuses:
            if st not in SV.ELECTRICAL_STATUSES:
                raise ValueError(f"unknown electrical status {st}")
        return self


class OptionRule(_Closed):
    kind: Literal["ceiling_clearance"]
    above_mm: int = Field(gt=0)
    at_least_mm: int = Field(gt=0)
    then: str
    else_: str = Field(alias="else")

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class MeasuredCount(_Closed):
    """A count of captured electrical points. A point of the counted type and status that lacks a listed sensor type
    or switching is not counted: it is reported as unresolved (never guessed into the count)."""

    types: tuple[str, ...] | None = None
    statuses: tuple[str, ...] = ()
    sensor_types: tuple[str, ...] = ()
    switchings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self):
        for st in self.sensor_types:
            if st not in SV.SENSOR_TYPES:
                raise ValueError(f"unknown sensor type {st}")
        for sw in self.switchings:
            if sw not in SV.SWITCHINGS:
                raise ValueError(f"unknown switching {sw}")
        return self


class ItemType(_Closed):
    label: str = Field(min_length=1, max_length=120)
    card_product: str | None
    project: bool = False
    fixed_options: dict[str, str] = Field(default_factory=dict)
    inputs: dict[str, InputRule] = Field(default_factory=dict)
    option_rules: dict[str, OptionRule] = Field(default_factory=dict)
    measured_count: MeasuredCount | None = None
    unmapped_reason: str | None = None

    @model_validator(mode="after")
    def _mapping(self):
        if self.card_product is None and not self.unmapped_reason:
            raise ValueError("an item type without a card product states why")
        if self.card_product is None and (self.inputs or self.fixed_options or self.option_rules):
            raise ValueError("inputs and options need a card product")
        return self


class Rule(_Closed):
    key: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    item: str
    necessity: Literal["MANDATORY", "RECOMMENDED", "OPTIONAL"]
    origin: Literal["AUTO", "RECOMMENDED"]
    project: bool = False
    space_types: tuple[str, ...] | None = None  # None: every space type
    per: Literal["tagged_wall", "any_tagged_wall", "once"] | None = None
    tag: str | None = None
    when: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self):
        if self.item not in V.REQUIREMENT_TYPES:
            raise ValueError(f"{self.key}: unknown item {self.item}")
        for t in self.space_types or ():
            if t not in SV.SPACE_TYPES:
                raise ValueError(f"{self.key}: unknown space type {t}")
        if self.per in ("tagged_wall", "any_tagged_wall") and self.tag not in SV.WALL_TAGS:
            raise ValueError(f"{self.key}: per {self.per} needs a known tag")
        if self.project and (self.space_types or self.per in ("tagged_wall", "any_tagged_wall")):
            raise ValueError(f"{self.key}: a project rule has no space condition")
        unknown = set(self.when) - {"proposed_partition", "opening_types", "electrical"}
        if unknown:
            raise ValueError(f"{self.key}: unknown conditions {sorted(unknown)}")
        return self


class Ruleset(_Closed):
    schema_: Literal["veda.mtq.scope-rules/1"] = Field(alias="schema")
    ruleset_version: str
    status: str
    status_note: str
    sources: tuple[str, ...]
    parameters_note: str
    item_types: dict[str, ItemType]
    rules: tuple[Rule, ...]

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @model_validator(mode="after")
    def _consistent(self):
        if set(self.item_types) != set(V.REQUIREMENT_TYPES):
            raise ValueError("item_types must cover exactly the requirement types")
        keys = [r.key for r in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate rule keys")
        for r in self.rules:
            if r.project != self.item_types[r.item].project:
                raise ValueError(f"{r.key}: project rules emit project items and space rules space items")
        return self

    @property
    def approved(self) -> bool:
        return self.status == APPROVED_STATUS


@lru_cache(maxsize=1)
def _load() -> tuple[Ruleset, str]:
    raw = FIXTURE.read_bytes()
    rs = Ruleset.model_validate(json.loads(raw))
    if rs.ruleset_version != RULESET_VERSION:
        raise RuntimeError(f"fixture {FIXTURE.name} declares {rs.ruleset_version}")
    return rs, hashlib.sha256(raw).hexdigest()


def load() -> Ruleset:
    return _load()[0]


def sha256() -> str:
    return _load()[1]


def item_type(code: str) -> ItemType:
    return load().item_types[code]


def public_view() -> dict[str, Any]:
    rs = load()
    return {
        "ruleset_version": rs.ruleset_version,
        "ruleset_sha256": sha256(),
        "status": effective_status(),
        "fixture_status": rs.status,
        "status_note": rs.status_note,
        "item_types": {
            k: {
                "label": t.label,
                "card_product": t.card_product,
                "project": t.project,
                "fixed_options": t.fixed_options,
                "inputs": {n: i.model_dump(exclude_none=True) for n, i in t.inputs.items()},
                "unmapped_reason": t.unmapped_reason,
            }
            for k, t in rs.item_types.items()
        },
        "rules": [r.model_dump(exclude_none=True) for r in rs.rules],
    }


def effective_status() -> str:
    """APPROVED only when the owner has recorded OI-MTQ-03 (rules) and OI-MTQ-04 (derivations) for exactly this ruleset
    version and digest in the commercial policy; otherwise the fixture's own status (PROPOSED)."""
    from . import policy

    for code in ("OI-MTQ-03", "OI-MTQ-04"):
        d = policy.decision(code)
        if d is None or d.ruleset_version != RULESET_VERSION or d.ruleset_sha256 != sha256():
            return load().status
    return APPROVED_STATUS
