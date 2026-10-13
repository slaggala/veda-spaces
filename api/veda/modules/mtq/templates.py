"""B1 template fixtures (B1-06, B1-SCOPE §4.4): versioned, read-only JSON in the API module.

``fixtures/templates-<version>.json`` holds the accepted OI-MTQ-02 content (blocker closure §3.1) in two parts:

- **space templates**: per space type, the FULL-survey requirements the verification engine enforces (machine
  codes) and the survey checklist shown to the surveyor;
- **property templates**: the seed of a space tree for a 2, 3, 4 or 5 BHK apartment or an independent house.

BHK is never stored: a template is only a starting tree, and every count is derived from the spaces that exist. The
file is validated strictly at import; a malformed fixture stops the process rather than seeding a wrong tree.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import vocab as V

TEMPLATE_VERSION = "2026.10.1"
FIXTURE = Path(__file__).with_name("fixtures") / f"templates-{TEMPLATE_VERSION}.json"

# Machine codes a space template may require for a FULL survey (see verification.py for their meaning).
_CODE = re.compile(
    r"^(FL|STAIRCASE|WALL_HEIGHTS|TAG:(?P<tag>[A-Z_]+)|ATTR:(?P<attr>[a-z_]+)|OBS_KIND:(?P<kind>[A-Z_]+))$"
)
ATTRIBUTE_KEYS = (
    "ac_type",
    "ac_point_count",
    "fan_point_count",
    "has_gas_line",
    "has_water_inlet",
    "has_drain",
    "counter_existing",
    "railing_height_mm",
    "exposure_code",
)


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SpaceTemplate(_Closed):
    space_types: tuple[str, ...] = Field(min_length=1)
    default_label: str = Field(min_length=1, max_length=80)
    full_required: tuple[str, ...] = ()
    checklist: tuple[str, ...] = Field(min_length=1)
    source: str

    @model_validator(mode="after")
    def _codes(self):
        for t in self.space_types:
            if t not in V.SPACE_TYPES:
                raise ValueError(f"unknown space type {t}")
        for code in self.full_required:
            m = _CODE.match(code)
            if not m:
                raise ValueError(f"unknown requirement code {code}")
            if m.group("tag") and m.group("tag") not in V.WALL_TAGS:
                raise ValueError(f"unknown wall tag in {code}")
            if m.group("attr") and m.group("attr") not in ATTRIBUTE_KEYS:
                raise ValueError(f"unknown attribute in {code}")
            if m.group("kind") and m.group("kind") not in V.OBSTRUCTION_KINDS:
                raise ValueError(f"unknown obstruction kind in {code}")
        return self


class SeedSpace(_Closed):
    space_type_code: str
    label: str = Field(min_length=1, max_length=80)
    instance_no: int = Field(ge=1, le=20)
    zone_code: Literal["INDOOR", "SEMI_OPEN", "OUTDOOR"]
    template: str | None
    level_index: int = Field(ge=-3, le=10)
    parent: str | None = None  # "<SPACE_TYPE>#<instance_no>" of an earlier seed space
    optional: bool = False

    @property
    def ref(self) -> str:
        return f"{self.space_type_code}#{self.instance_no}"


class PropertyTemplate(_Closed):
    property_type_code: str
    configuration_label: str | None
    expected_bedrooms: int | None
    levels: int | None
    default_project_kind: Literal["NEW", "RENOVATION", "PARTIAL"] = "NEW"
    source: str
    spaces: tuple[SeedSpace, ...] = Field(min_length=1)
    notes: tuple[str, ...] = ()


class TemplateSet(_Closed):
    template_version: str
    status: str
    space_templates: dict[str, SpaceTemplate]
    property_templates: dict[str, PropertyTemplate]

    @model_validator(mode="after")
    def _consistent(self):
        covered: dict[str, str] = {}
        for key, tpl in self.space_templates.items():
            for t in tpl.space_types:
                if t in covered:
                    raise ValueError(f"space type {t} is in both {covered[t]} and {key}")
                covered[t] = key
        missing = set(V.SPACE_TYPES) - set(covered)
        if missing:
            raise ValueError(f"space types without a template: {sorted(missing)}")
        for key, prop in self.property_templates.items():
            if prop.property_type_code not in V.PROPERTY_TYPES:
                raise ValueError(f"{key}: property type {prop.property_type_code} is not supported in B1")
            seen: set[str] = set()
            for sp in prop.spaces:
                if sp.space_type_code not in V.SPACE_TYPES:
                    raise ValueError(f"{key}: unknown space type {sp.space_type_code}")
                if sp.template is not None and sp.template not in self.space_templates:
                    raise ValueError(f"{key}: unknown space template {sp.template}")
                if sp.template is not None and sp.space_type_code not in self.space_templates[sp.template].space_types:
                    raise ValueError(f"{key}: {sp.template} does not cover {sp.space_type_code}")
                if sp.parent is not None and sp.parent not in seen:
                    raise ValueError(f"{key}: parent {sp.parent} of {sp.ref} is not an earlier space")
                if sp.ref in seen:
                    raise ValueError(f"{key}: duplicate {sp.ref}")
                seen.add(sp.ref)
            if prop.expected_bedrooms is not None:
                beds = sum(1 for sp in prop.spaces if sp.space_type_code in V.BEDROOM_TYPES and not sp.optional)
                if beds != prop.expected_bedrooms:
                    raise ValueError(f"{key}: {beds} bedrooms seeded, {prop.expected_bedrooms} expected")
        return self


@lru_cache(maxsize=1)
def load() -> TemplateSet:
    data = json.loads(FIXTURE.read_text())
    tpl = TemplateSet.model_validate(data)
    if tpl.template_version != TEMPLATE_VERSION:
        raise RuntimeError(f"fixture {FIXTURE.name} declares {tpl.template_version}")
    return tpl


def space_template_for(space_type_code: str) -> tuple[str, SpaceTemplate]:
    for key, tpl in load().space_templates.items():
        if space_type_code in tpl.space_types:
            return key, tpl
    raise KeyError(space_type_code)  # unreachable: every type has a template (validated)


def property_template(key: str) -> PropertyTemplate:
    found = load().property_templates.get(key)
    if found is None:
        raise KeyError(key)
    return found


def public_view() -> dict:
    """What the staff UI shows when it offers a template: keys, labels and the seed space lists."""
    t = load()
    return {
        "template_version": t.template_version,
        "property_templates": {
            k: {
                "property_type_code": p.property_type_code,
                "configuration_label": p.configuration_label,
                "default_project_kind": p.default_project_kind,
                "spaces": [s.model_dump() | {"ref": s.ref} for s in p.spaces],
                "notes": list(p.notes),
            }
            for k, p in t.property_templates.items()
        },
        "space_templates": {
            k: {
                "space_types": list(s.space_types),
                "full_required": list(s.full_required),
                "checklist": list(s.checklist),
            }
            for k, s in t.space_templates.items()
        },
    }
