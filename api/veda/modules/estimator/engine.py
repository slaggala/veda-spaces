"""Budgetary Estimate pricing engine (ADR-012 §3). Pure: no database, no clock, no I/O.

    quantity × rate(item, package)          per quotation-style line, in paise (hardware in its product)
  + Custom Features Allowance              room work × the card's band (its midpoint in the base)
  + Project Preparation & Protection Package (by home size and property type)
  + selected optional items (painting, electrical and lighting)
  = base estimate  →  range (measured or typical-size band per line, plus the allowance band)  →  GST, timeline,
    warranty, assumptions

The same inputs and rate card always give the same result (`CALCULATION_VERSION` names these rules). The result has a
customer view (no rates, no line amounts) and a staff view (every line and every preparation component).
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .ratecard import ProductSpec, RateCard

CALCULATION_VERSION = "2026.10.2"
TITLE = "VEDA SPACES PRELIMINARY BUDGETARY ESTIMATE"
DISCLAIMER = (
    "This is a preliminary budgetary estimate for planning purposes and is not a final quotation or contractual offer."
)
SUBJECT_TO = (
    "physical site measurement",
    "approved design and drawings",
    "selected materials and brands",
    "hardware choices",
    "site conditions",
    "actual executed quantities",
    "client-supplied items",
    "applicable taxes",
    "final scope confirmation",
)
PREP_PACKAGE = "Project Preparation & Protection Package"
PREP_DESCRIPTION = (
    "Includes the site preparation, material handling, protection and completion activities required to execute and "
    "hand over the selected work safely and professionally."
)
PREP_NOTE = (
    "Shown as one grouped value for clarity. It is part of the estimate total, and the detailed final quotation shows "
    "every component."
)
ALLOWANCE = "Custom Features Allowance"
ALLOWANCE_DESCRIPTION = (
    "Bespoke details usually added during design, such as extra drawers, mirrors, pelmets, lighting sensors and "
    "material upgrades. It is part of the estimate total; the detailed quotation replaces it with the actual items."
)
# Customer-facing subtotals are rounded to ₹1,000 so that a single response does not expose an exact line rate (the
# staff view keeps exact amounts). The range itself is rounded to the card's step.
CUSTOMER_ROUND_MINOR = 100_000
ROOMS = OrderedDict(
    [
        ("KITCHEN", "Kitchen"),
        ("UTILITY", "Utility"),
        ("LIVING", "Living room"),
        ("DINING", "Dining"),
        ("MASTER_BEDROOM", "Master bedroom"),
        ("BEDROOM_2", "Bedroom 2"),
        ("BEDROOM_3", "Bedroom 3"),
        ("BEDROOM_4", "Bedroom 4"),
        ("KIDS_ROOM", "Kids' room"),
        ("STUDY", "Study"),
        ("POOJA", "Pooja room"),
        ("WHOLE_HOME", "Whole home"),
    ]
)
UNITS = {
    "length": {"ft": 1.0, "in": 1 / 12, "m": 3.280839895, "cm": 0.03280839895},
    "area": {"sqft": 1.0, "sqm": 10.7639104},
}
WARRANTY = (
    ("PLYWOOD", "CARPENTRY", "Plywood: warranty depends on the selected material and the manufacturer's terms."),
    ("TANDEMS", "KITCHEN", "Kitchen tandems: up to 3 years against manufacturing defects."),
    ("CHANNELS_HINGES", "CARPENTRY", "Channels and hinges: up to 5 years against manufacturing defects."),
    ("ELECTRICAL", "ELECTRICAL", "Electrical items: up to 1 year, or the documented manufacturer period."),
    ("FREE_SERVICE", "ANY", "One year of free service after handover for applicable workmanship or fitment issues."),
)
WARRANTY_NOTE = (
    "Manufacturer warranties are the manufacturer's and do not extend Veda Spaces workmanship or free-service "
    "obligations. Exclusions apply; see the Warranty, Service & Customer Care Policy."
)
# The existing BUDGET_RANGE lookups (lakh = 100,000 rupees = 10,000,000 paise).
_L = 10_000_000
BUDGET_RANGES = (
    (5 * _L, "UNDER_5L"),
    (10 * _L, "5L_10L"),
    (20 * _L, "10L_20L"),
    (35 * _L, "20L_35L"),
    (50 * _L, "35L_50L"),
)
PROJECT_TYPES = {"KITCHEN": "MODULAR_KITCHEN", "BEDROOM": "BEDROOM_WARDROBE", "LIVING": "LIVING_DINING"}


# --- request ------------------------------------------------------------------------------------------------------


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Code = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]


class Measurement(_Model):
    value: float = Field(ge=0, le=100_000)  # 0 only passes for counts (the card bounds lengths and areas)
    unit: Literal["ft", "in", "m", "cm", "sqft", "sqm", "nos"]


class Selection(_Model):
    room: Code
    product: Code
    measurements: dict[Code, Measurement] = Field(default_factory=dict, max_length=10)  # absent → typical size
    options: dict[Code, Code] = Field(default_factory=dict, max_length=10)


class EstimateRequest(_Model):
    """Everything the estimate needs. No personal data: no name, phone, email or address."""

    property_type: Literal["APARTMENT", "VILLA"]
    home_size: Literal["1BHK", "2BHK", "3BHK", "4BHK", "CUSTOM"]
    project_kind: Literal["NEW_HOME", "RENOVATION"]
    city: Annotated[str, Field(min_length=1, max_length=60, pattern=r"^[\w .,'()-]+$")] | None = None
    package: Literal["ESSENTIAL", "PREMIUM", "LUXURY"]
    selections: tuple[Selection, ...] = Field(min_length=1, max_length=40)  # a full 3 BHK needs up to ~37


class EstimateError(ValueError):
    """Invalid input; `errors` lists {field, code, message} like the API's field errors."""

    def __init__(self, errors: list[dict]):
        super().__init__("; ".join(f"{e['field']}: {e['code']}" for e in errors))
        self.errors = errors


# --- result -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    room: str
    instance: int
    product: str
    code: str
    label: str
    uom: str
    quantity: Decimal
    rate_minor: int
    amount_minor: int
    typical: bool
    optional: bool


@dataclass(frozen=True)
class Assumption:
    room: str
    instance: int
    product: str
    input: str
    text: str
    value: float
    unit: str


@dataclass(frozen=True)
class PrepComponentAmount:
    code: str
    label: str
    inclusion: str
    amount_minor: int


@dataclass
class Estimate:
    rate_card_version: str
    calculation_version: str
    package: str
    property_type: str
    home_size: str
    project_kind: str
    city: str | None
    lines: list[Line] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    prep: list[PrepComponentAmount] = field(default_factory=list)
    allowance_basis_minor: int = 0  # the room work the allowance applies to
    allowance_low_pct: float = 0
    allowance_high_pct: float = 0
    allowance_minor: int = 0  # the band's midpoint, part of the base
    allowance_low_minor: int = 0
    allowance_high_minor: int = 0
    base_minor: int = 0
    low_minor: int = 0
    high_minor: int = 0
    gst_pct: float = 0
    gst_low_minor: int = 0
    gst_high_minor: int = 0
    timeline: dict = field(default_factory=dict)
    warranty: list[dict] = field(default_factory=list)
    exclusions: tuple[str, ...] = ()
    client_scope: tuple[str, ...] = ()
    validity_days: int = 0
    budget_range_code: str = ""
    project_type_code: str = ""

    # Totals derived from lines (never stored separately from them).
    def room_totals(self) -> list[dict]:
        totals: OrderedDict[str, int] = OrderedDict()
        for line in self.lines:
            if not line.optional:
                totals[line.room] = totals.get(line.room, 0) + line.amount_minor
        return [{"room": r, "label": ROOMS.get(r, r), "amount_minor": a} for r, a in totals.items()]

    @property
    def prep_minor(self) -> int:
        return sum(c.amount_minor for c in self.prep)

    @property
    def optional_minor(self) -> int:
        return sum(line.amount_minor for line in self.lines if line.optional)

    def customer_view(self) -> dict:
        """What the customer sees: totals, the grouped package and the explanations; never a rate or a line amount."""
        return {
            "title": TITLE,
            "disclaimer": DISCLAIMER,
            "subject_to": list(SUBJECT_TO),
            "package": self.package,
            "property_type": self.property_type,
            "home_size": self.home_size,
            "range": {"low_minor": self.low_minor, "high_minor": self.high_minor, "currency": "INR"},
            "gst": {"pct": self.gst_pct, "low_minor": self.gst_low_minor, "high_minor": self.gst_high_minor},
            "rooms": [dict(r, amount_minor=_nearest(r["amount_minor"])) for r in self.room_totals()],
            "project_preparation": {
                "label": PREP_PACKAGE,
                "description": PREP_DESCRIPTION,
                "note": PREP_NOTE,
                "amount_minor": self.prep_minor,
                "inclusions": list(OrderedDict.fromkeys(c.inclusion for c in self.prep)),
            },
            "custom_features_allowance": {
                "label": ALLOWANCE,
                "description": ALLOWANCE_DESCRIPTION,
                "low_minor": _round(Decimal(self.allowance_low_minor), CUSTOMER_ROUND_MINOR, ROUND_FLOOR),
                "high_minor": _round(Decimal(self.allowance_high_minor), CUSTOMER_ROUND_MINOR, ROUND_CEILING),
            },
            "optional_items_minor": self.optional_minor,
            "timeline": self.timeline,
            "assumptions": [a.text for a in self.assumptions],
            "exclusions": list(self.exclusions),
            "client_scope": list(self.client_scope),
            "warranty": {"items": [w["text"] for w in self.warranty], "note": WARRANTY_NOTE},
            "rate_card_version": self.rate_card_version,
            "validity_days": self.validity_days,
        }

    def staff_view(self) -> dict:
        view = self.customer_view()
        view["calculation_version"] = self.calculation_version
        view["base_minor"] = self.base_minor
        view["project_kind"] = self.project_kind
        view["city"] = self.city
        view["lines"] = [
            {
                "room": line.room,
                "instance": line.instance,
                "product": line.product,
                "code": line.code,
                "label": line.label,
                "uom": line.uom,
                "quantity": str(line.quantity),
                "rate_minor": line.rate_minor,
                "amount_minor": line.amount_minor,
                "typical": line.typical,
                "optional": line.optional,
            }
            for line in self.lines
        ]
        view["project_preparation"]["components"] = [
            {"code": c.code, "label": c.label, "inclusion": c.inclusion, "amount_minor": c.amount_minor}
            for c in self.prep
        ]
        view["rooms"] = self.room_totals()  # exact for staff
        view["custom_features_allowance"].update(
            exact_low_minor=self.allowance_low_minor,
            exact_high_minor=self.allowance_high_minor,
            amount_minor=self.allowance_minor,
            basis_minor=self.allowance_basis_minor,
            low_pct=self.allowance_low_pct,
            high_pct=self.allowance_high_pct,
        )
        view["assumption_details"] = [a.__dict__ for a in self.assumptions]
        view["budget_range_code"] = self.budget_range_code
        view["project_type_code"] = self.project_type_code
        return view


# --- computation --------------------------------------------------------------------------------------------------


def _ft(value: float, unit: str, kind: str) -> float | None:
    if kind == "count":
        return value if unit == "nos" else None
    factor = UNITS[kind].get(unit)
    return value * factor if factor is not None else None


def _q(value: Decimal | float, places: str = "0.01") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _paise(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _nearest(minor: int) -> int:
    return _round(Decimal(minor), CUSTOMER_ROUND_MINOR, ROUND_HALF_UP)


def _round(minor: Decimal, step: int, rounding) -> int:
    return int((minor / step).quantize(Decimal(1), rounding=rounding)) * step


def calculate(card: RateCard, request: EstimateRequest) -> Estimate:
    """Compute a Budgetary Estimate. Raises EstimateError with every input problem found."""
    errors: list[dict] = []
    if request.home_size not in card.available_home_sizes():
        errors.append(
            {"field": "home_size", "code": "HOME_SIZE_UNAVAILABLE", "message": "This home size is not offered yet."}
        )
    if request.property_type not in card.available_property_types():
        errors.append(
            {
                "field": "property_type",
                "code": "PROPERTY_TYPE_UNAVAILABLE",
                "message": "This property type is not offered yet.",
            }
        )
    if request.package not in card.enabled_packages():
        errors.append(
            {"field": "package", "code": "PACKAGE_UNAVAILABLE", "message": f"{request.package} is not offered yet."}
        )
    est = Estimate(
        rate_card_version=card.version,
        calculation_version=CALCULATION_VERSION,
        package=request.package,
        property_type=request.property_type,
        home_size=request.home_size,
        project_kind=request.project_kind,
        city=request.city,
        gst_pct=card.gst_pct,
        exclusions=card.exclusions,
        client_scope=card.client_scope,
        validity_days=card.validity_days,
    )
    instances: dict[str, int] = {}
    room_instances: dict[tuple[str, str], int] = {}
    selected: list[ProductSpec] = []
    for i, sel in enumerate(request.selections):
        path = f"selections[{i}]"
        product = card.product(sel.product)
        if product is None:
            errors.append({"field": f"{path}.product", "code": "UNKNOWN_PRODUCT", "message": "Unknown product."})
            continue
        if sel.room not in ROOMS:
            errors.append({"field": f"{path}.room", "code": "UNKNOWN_ROOM", "message": "Unknown room."})
            continue
        if sel.room not in product.rooms:
            errors.append(
                {
                    "field": f"{path}.room",
                    "code": "ROOM_NOT_ALLOWED",
                    "message": f"{product.label} is not offered here.",
                }
            )
            continue
        instances[product.code] = instances.get(product.code, 0) + 1
        if instances[product.code] > product.max_instances:
            errors.append({"field": path, "code": "TOO_MANY", "message": f"At most {product.max_instances}."})
            continue
        key = (sel.room, product.code)
        room_instances[key] = room_instances.get(key, 0) + 1
        instance = room_instances[key]
        _price(card, request, product, sel, instance, path, est, errors)
        selected.append(product)
    if errors:
        raise EstimateError(errors)
    _project_preparation(card, request, selected, est)
    _allowance(card, est)
    _totals(card, est)
    est.warranty = _warranty(selected)
    est.project_type_code = _project_type(selected)
    return est


def _price(card, request, product, sel, instance, path, est, errors) -> None:
    values: dict[str, float] = {}
    typical: set[str] = set()
    pending: dict[str, Assumption] = {}  # recorded only if a priced line uses the measurement
    for name in sel.measurements:
        if name not in {s.name for s in product.inputs}:
            errors.append(
                {"field": f"{path}.measurements.{name}", "code": "UNKNOWN_INPUT", "message": "Unknown measurement."}
            )
    for spec in product.inputs:
        m = sel.measurements.get(spec.name)
        if m is None:
            value = spec.typical.get(request.home_size, spec.typical["DEFAULT"])
            values[spec.name] = value
            typical.add(spec.name)
            unit = {"length": "ft", "area": "sq ft", "count": ""}[spec.kind]
            pending[spec.name] = Assumption(
                room=sel.room,
                instance=instance,
                product=product.code,
                input=spec.name,
                value=value,
                unit=unit.strip() or "nos",
                text=f"{ROOMS[sel.room]} – {product.label}{_nth(instance)}: {spec.label.lower()} assumed "
                f"{_fmt(value)} {unit}".rstrip()
                + f" (typical for {request.home_size.replace('BHK', ' BHK').lower() if request.home_size != 'CUSTOM' else 'a home of this kind'}).",
            )
            continue
        converted = _ft(m.value, m.unit, spec.kind)
        field_path = f"{path}.measurements.{spec.name}"
        if converted is None:
            errors.append(
                {"field": field_path, "code": "INVALID_UNIT", "message": f"{m.unit} is not a {spec.kind} unit."}
            )
            continue
        bound = card.bounds[spec.kind]
        if spec.kind == "count" and converted != int(converted):
            errors.append({"field": field_path, "code": "OUT_OF_BOUNDS", "message": "Must be a whole number."})
            continue
        if not bound.min <= converted <= bound.max:
            errors.append(
                {
                    "field": field_path,
                    "code": "OUT_OF_BOUNDS",
                    "message": f"Must be between {bound.min} and {bound.max}.",
                }
            )
            continue
        values[spec.name] = converted
    options = {}
    for name, choice in sel.options.items():
        spec = next((o for o in product.options if o.name == name), None)
        if spec is None:
            errors.append({"field": f"{path}.options.{name}", "code": "UNKNOWN_OPTION", "message": "Unknown option."})
        elif choice not in spec.choices:
            errors.append({"field": f"{path}.options.{name}", "code": "INVALID_CHOICE", "message": "Unknown choice."})
        else:
            options[name] = choice
    if errors:
        return
    for spec in product.options:
        options.setdefault(spec.name, spec.default)
    used: set[str] = set()
    for line in product.lines:
        if any(options.get(w.option) not in w.is_ for w in line.when):
            continue
        q = line.quantity
        if q.kind == "area":
            height = values[q.height_input] if q.height_input else q.height
            qty = Decimal(str(values[q.input])) * Decimal(str(height))
            if qty > Decimal(str(card.bounds["area"].max)):  # width × height is bounded like an entered area
                errors.append(
                    {
                        "field": path,
                        "code": "OUT_OF_BOUNDS",
                        "message": f"{product.label} is larger than {card.bounds['area'].max:g} sq ft.",
                    }
                )
                return
        elif q.kind == "direct":
            qty = Decimal(str(values[q.input]))
        elif q.kind == "count":
            qty = Decimal(str(values[q.input] if q.input else q.count))
        else:
            qty = Decimal(1)
        qty = _q(qty * Decimal(str(q.factor)))
        if qty <= 0:
            continue
        used.update(n for n in (q.input, q.height_input) if n)
        rate = line.rates[request.package] if request.package in line.rates else 0
        est.lines.append(
            Line(
                room=sel.room,
                instance=instance,
                product=product.code,
                code=line.code,
                label=line.label,
                uom=line.uom,
                quantity=qty,
                rate_minor=rate,
                amount_minor=_paise(qty * rate),
                typical=bool({q.input, q.height_input} & typical),
                optional=product.category == "OPTIONAL",
            )
        )
    est.assumptions.extend(pending[s.name] for s in product.inputs if s.name in pending and s.name in used)


def _project_preparation(card: RateCard, request: EstimateRequest, selected: list[ProductSpec], est: Estimate) -> None:
    categories = {p.category for p in selected}
    for comp in card.project_preparation:
        if not categories & set(comp.applies_to):
            continue  # this component does not apply to the selected scope
        amount = Decimal(comp.amounts[request.home_size])
        if request.property_type == "VILLA":
            amount *= Decimal(str(comp.villa_factor))
        est.prep.append(PrepComponentAmount(comp.code, comp.label, comp.inclusion, _paise(amount)))


def _allowance(card: RateCard, est: Estimate) -> None:
    """The Custom Features Allowance: a disclosed band on the room work of the card's categories (never hidden inside
    another amount). The midpoint is part of the base; the band widens the range."""
    spec = card.custom_features_allowance
    categories = {p.code: p.category for p in card.products}
    basis = sum(line.amount_minor for line in est.lines if categories[line.product] in spec.applies_to)
    low, high = Decimal(str(spec.low_pct)) / 100, Decimal(str(spec.high_pct)) / 100
    est.allowance_basis_minor = basis
    est.allowance_low_pct, est.allowance_high_pct = spec.low_pct, spec.high_pct
    est.allowance_low_minor = _paise(basis * low)
    est.allowance_high_minor = _paise(basis * high)
    est.allowance_minor = _paise(basis * (low + high) / 2)


def _totals(card: RateCard, est: Estimate) -> None:
    measured, typical = card.ranges.measured, card.ranges.typical
    base = sum(line.amount_minor for line in est.lines) + est.allowance_minor + est.prep_minor
    low = high = Decimal(0)
    for line in est.lines:
        band = typical if line.typical else measured
        low += line.amount_minor * (1 - Decimal(str(band.low_pct)) / 100)
        high += line.amount_minor * (1 + Decimal(str(band.high_pct)) / 100)
    low += est.prep_minor * (1 - Decimal(str(measured.low_pct)) / 100)
    high += est.prep_minor * (1 + Decimal(str(measured.high_pct)) / 100)
    low += est.allowance_low_minor
    high += est.allowance_high_minor
    step = card.ranges.round_to_minor
    est.base_minor = base
    est.low_minor = max(0, _round(low, step, ROUND_FLOOR))
    est.high_minor = _round(high, step, ROUND_CEILING)
    gst = Decimal(str(card.gst_pct)) / 100
    est.gst_low_minor = _paise(est.low_minor * gst)
    est.gst_high_minor = _paise(est.high_minor * gst)
    tb = next(b for b in card.timeline if b.up_to_minor is None or est.high_minor <= b.up_to_minor)
    est.timeline = {"label": tb.label, "min_days": tb.min_days, "max_days": tb.max_days}
    mid = (est.low_minor + est.high_minor) // 2
    est.budget_range_code = next((code for upper, code in BUDGET_RANGES if mid < upper), "ABOVE_50L")


def _warranty(selected: list[ProductSpec]) -> list[dict]:
    present = {"ANY"} | {p.category for p in selected} | {p.area for p in selected}
    if any(p.has_electrical for p in selected):
        present.add("ELECTRICAL")
    return [{"code": code, "text": text} for code, when, text in WARRANTY if when in present]


def _project_type(selected: list[ProductSpec]) -> str:
    areas = {p.area for p in selected if p.category != "OPTIONAL"}
    if len(areas) == 1 and (area := next(iter(areas))) in PROJECT_TYPES:
        return PROJECT_TYPES[area]
    return "FULL_HOME"


def _fmt(value: float) -> str:
    return f"{value:g}"


def _nth(instance: int) -> str:
    return "" if instance == 1 else f" {instance}"
