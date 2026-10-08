"""Estimator rate card: the versioned, validated pricing data of the Budgetary Estimate (ADR-012 §3.4).

A rate card is a JSON document. It is loaded from a private file into the database (`veda estimator load-card`),
never committed: the repository is public and the rates are commercial. Tests use a synthetic card.

All money is integer paise. A package level (ESSENTIAL, PREMIUM, LUXURY) is offered only when the card enables it, and
an enabled package must price every line it can reach: rates are never inferred from another package.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA = "veda.estimator.rate-card/1"
PACKAGES = ("ESSENTIAL", "PREMIUM", "LUXURY")
HOME_SIZES = ("1BHK", "2BHK", "3BHK", "4BHK", "CUSTOM")
PROPERTY_TYPES = ("APARTMENT", "VILLA")
UOMS = ("SFT", "RFT", "NOS", "LUMP")
INPUT_KINDS = ("length", "area", "count")
Code = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]
Text = Annotated[str, Field(min_length=1, max_length=300)]
Minor = Annotated[int, Field(ge=0, le=10_000_000_000)]  # up to ₹10 crore per amount
Pct = Annotated[float, Field(ge=0, le=100)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Bounds(_Model):
    min: float = Field(ge=0)
    max: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.min > self.max:
            raise ValueError("min must not exceed max")
        return self


class InputSpec(_Model):
    """A customer measurement of a product. `typical` gives the value used when the customer chooses the typical size,
    by home size (with an optional `DEFAULT`)."""

    name: Code
    label: Text
    kind: Literal["length", "area", "count"]
    typical: dict[str, float]

    @model_validator(mode="after")
    def _typical(self):
        unknown = set(self.typical) - set(HOME_SIZES) - {"DEFAULT"}
        if unknown:
            raise ValueError(f"typical sizes for unknown home sizes: {sorted(unknown)}")
        if "DEFAULT" not in self.typical:
            raise ValueError("typical sizes need a DEFAULT")
        return self


class OptionSpec(_Model):
    """A preference of a product: a yes/no switch or a choice."""

    name: Code
    label: Text
    choices: tuple[Code, ...] = ("YES", "NO")
    default: Code

    @model_validator(mode="after")
    def _default_in_choices(self):
        if self.default not in self.choices:
            raise ValueError(f"default {self.default} is not a choice")
        return self


class Quantity(_Model):
    """How a line's quantity is computed. `area`: width input × (height input or constant). `direct`: an input as
    entered (a length or an area). `count`: an input or a constant. `lump`: 1. A factor multiplies the result (two
    sides, lights per sq ft)."""

    kind: Literal["area", "direct", "count", "lump"]
    input: Code | None = None
    height_input: Code | None = None
    height: float | None = Field(default=None, gt=0, le=20)
    count: float | None = Field(default=None, ge=0, le=100)
    factor: float = Field(default=1, gt=0, le=100)

    @model_validator(mode="after")
    def _shape(self):
        k = self.kind
        if k == "area" and not (self.input and (self.height_input or self.height)):
            raise ValueError("an area needs input and height_input or height")
        if k == "direct" and not self.input:
            raise ValueError("a direct quantity needs input")
        if k == "count" and not (self.input or self.count is not None):
            raise ValueError("a count needs input or count")
        if k == "lump" and (self.input or self.height_input or self.height or self.count is not None):
            raise ValueError("a lump takes no quantity fields")
        return self


class When(_Model):
    option: Code
    is_: tuple[Code, ...] = Field(alias="in")

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class LineSpec(_Model):
    code: Code
    label: Text
    uom: Literal["SFT", "RFT", "NOS", "LUMP"]
    quantity: Quantity
    rates: dict[str, Minor]
    when: tuple[When, ...] = ()


class ProductSpec(_Model):
    code: Code
    label: Text
    category: Literal["CARPENTRY", "CEILING", "FINISH", "OPTIONAL"]
    area: Literal["KITCHEN", "BEDROOM", "LIVING", "WHOLE_HOME"]  # for the lead's project type
    has_electrical: bool = False  # brings the electrical warranty line
    rooms: tuple[Code, ...]
    inputs: tuple[InputSpec, ...] = ()
    options: tuple[OptionSpec, ...] = ()
    lines: tuple[LineSpec, ...] = Field(min_length=1)
    max_instances: int = Field(default=6, ge=1, le=12)

    @model_validator(mode="after")
    def _references(self):
        inputs = {i.name for i in self.inputs}
        options = {o.name: set(o.choices) for o in self.options}
        for line in self.lines:
            q = line.quantity
            for ref in (q.input, q.height_input):
                if ref and ref not in inputs:
                    raise ValueError(f"{self.code}.{line.code}: unknown input {ref}")
            for w in line.when:
                if w.option not in options:
                    raise ValueError(f"{self.code}.{line.code}: unknown option {w.option}")
                if set(w.is_) - options[w.option]:
                    raise ValueError(
                        f"{self.code}.{line.code}: {w.option} has no choice {sorted(set(w.is_) - options[w.option])}"
                    )
        if len({line.code for line in self.lines}) != len(self.lines):
            raise ValueError(f"{self.code}: duplicate line codes")
        return self


class PrepComponent(_Model):
    """A Project Preparation & Protection component. Shown to customers only as part of the grouped package (its
    `inclusion` text); its amount by home size stays internal."""

    code: Code
    label: Text
    inclusion: Text
    amounts: dict[str, Minor]
    villa_factor: float = Field(default=1, gt=0, le=5)
    applies_to: tuple[Literal["CARPENTRY", "CEILING", "FINISH", "OPTIONAL"], ...] = ("CARPENTRY",)

    @model_validator(mode="after")
    def _sizes(self):
        # A home size without an approved amount is simply not offered (no amount is ever inferred).
        unknown = set(self.amounts) - set(HOME_SIZES)
        if unknown or not self.amounts:
            raise ValueError(f"{self.code}: amounts need approved home sizes (unknown {sorted(unknown)})")
        return self


class RangeBand(_Model):
    low_pct: Pct
    high_pct: Pct


class Ranges(_Model):
    measured: RangeBand
    typical: RangeBand
    round_to_minor: Minor = Field(gt=0)

    @model_validator(mode="after")
    def _typical_wider(self):
        if self.typical.low_pct < self.measured.low_pct or self.typical.high_pct < self.measured.high_pct:
            raise ValueError("the typical-size band must be at least as wide as the measured band")
        return self


class TimelineBand(_Model):
    up_to_minor: Minor | None  # None: the last, open band
    label: Text
    min_days: int = Field(ge=1, le=1000)
    max_days: int = Field(ge=1, le=1000)


class RateCard(_Model):
    schema_: Literal["veda.estimator.rate-card/1"] = Field(alias="schema")
    description: Annotated[str, Field(max_length=500)] | None = None
    version: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")]
    effective_on: date
    currency: Literal["INR"]
    packages: dict[str, bool]
    gst_pct: Pct
    validity_days: int = Field(ge=1, le=90)
    ranges: Ranges
    bounds: dict[Literal["length", "area", "count"], Bounds]
    products: tuple[ProductSpec, ...] = Field(min_length=1)
    project_preparation: tuple[PrepComponent, ...]
    timeline: tuple[TimelineBand, ...] = Field(min_length=1)
    exclusions: tuple[Text, ...]
    client_scope: tuple[Text, ...]

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @model_validator(mode="after")
    def _consistent(self):
        if set(self.packages) != set(PACKAGES):
            raise ValueError(f"packages must list exactly {list(PACKAGES)}")
        if not self.packages["ESSENTIAL"]:
            raise ValueError("ESSENTIAL must be enabled")
        if set(self.bounds) != set(INPUT_KINDS):
            raise ValueError(f"bounds must cover {list(INPUT_KINDS)}")
        codes = [p.code for p in self.products]
        if len(set(codes)) != len(codes):
            raise ValueError("duplicate product codes")
        enabled = [p for p in PACKAGES if self.packages[p]]
        for product in self.products:
            for line in product.lines:
                unknown = set(line.rates) - set(PACKAGES)
                if unknown:
                    raise ValueError(f"{product.code}.{line.code}: unknown packages {sorted(unknown)}")
                missing = [p for p in enabled if p not in line.rates]
                if missing:
                    raise ValueError(f"{product.code}.{line.code}: no rate for enabled package(s) {missing}")
            for spec in product.inputs:
                bound = self.bounds[spec.kind]
                for size, value in spec.typical.items():
                    if not bound.min <= value <= bound.max:
                        raise ValueError(f"{product.code}.{spec.name}: typical {size} {value} outside bounds")
        if [b.up_to_minor for b in self.timeline][-1] is not None:
            raise ValueError("the last timeline band must be open (up_to_minor null)")
        uppers = [b.up_to_minor for b in self.timeline[:-1]]
        bounded = [u for u in uppers if u is not None]
        if len(bounded) != len(uppers) or bounded != sorted(bounded):
            raise ValueError("timeline bands must be in ascending order")
        return self

    def product(self, code: str) -> ProductSpec | None:
        return next((p for p in self.products if p.code == code), None)

    def enabled_packages(self) -> tuple[str, ...]:
        return tuple(p for p in PACKAGES if self.packages[p])

    def available_home_sizes(self) -> tuple[str, ...]:
        """Home sizes every preparation component has an approved amount for."""
        return tuple(h for h in HOME_SIZES if all(h in c.amounts for c in self.project_preparation))


def parse(document: dict) -> RateCard:
    """Validate a rate card document (raises pydantic.ValidationError)."""
    return RateCard.model_validate(document)
