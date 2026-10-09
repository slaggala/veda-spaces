"""Compile a catalog release into the artefacts the existing estimator already uses (ADR-013 D1).

- `card_document`: the rate card (settings pricing record + product pricing records), validated by `ratecard.parse`.
- `customer_view`: what the customer page may show (no rate, no staff note, no governance detail, no source media).
- `resolve`: a customer configuration → an `engine.EstimateRequest` (the pricing inputs) plus the record versions used.

The ADR-012 engine prices the request unchanged; there is no second pricing engine. Geometry from 3D assets is never
an input: only the catalog's engine product, options and the customer's measurements reach the engine.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, TypeVar

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.modules.estimator import engine, ratecard
from veda.modules.estimator import service as estimator_service
from veda.modules.estimator.models import EstimatorRateCard

from . import configuration, kinds, rules
from .models import CatalogRecord, CatalogRelease

M = TypeVar("M", bound=kinds._Model)
CARD_PREFIX = "CATALOG-"
PUBLIC_MEDIA_PATH = "/api/v1/public/catalog/media/"


class CompileError(ValueError):
    """The release cannot be compiled or the configuration cannot be resolved (fail closed)."""

    def __init__(self, errors: list[dict] | str):
        self.errors = [{"field": "", "code": "INVALID", "message": errors}] if isinstance(errors, str) else errors
        super().__init__("; ".join(e["message"] for e in self.errors))


@dataclass
class Catalog:
    """The parsed records of one release, by kind and key."""

    release_code: str
    manifest_sha256: str
    records: dict[str, dict[str, CatalogRecord]] = field(default_factory=dict)
    models: dict[str, dict[str, kinds._Model]] = field(default_factory=dict)

    def model(self, kind: str, key: str | None) -> kinds._Model | None:
        """Any record by kind and key (for kind-generic checks such as reference integrity)."""
        return self.models.get(kind, {}).get(key) if key else None

    def models_of(self, kind: str) -> dict[str, kinds._Model]:
        return self.models.get(kind, {})

    def one(self, cls: type[M], key: str | None) -> M | None:
        """The record of `cls`'s kind with this key, typed."""
        found = self.model(kinds.KIND_OF[cls], key)
        return found if isinstance(found, cls) else None

    def of(self, cls: type[M]) -> dict[str, M]:
        """Every record of `cls`'s kind, by key, typed."""
        return {k: m for k, m in self.models_of(kinds.KIND_OF[cls]).items() if isinstance(m, cls)}

    def version(self, kind: str, key: str) -> int:
        return self.records[kind][key].record_version


def load(rows: list[CatalogRecord], release_code: str, manifest_sha256: str) -> Catalog:
    cat = Catalog(release_code=release_code, manifest_sha256=manifest_sha256)
    for row in rows:
        cat.records.setdefault(row.kind, {})[row.record_key] = row
        cat.models.setdefault(row.kind, {})[row.record_key] = kinds.parse(row.kind, row.document)
    return cat


def load_release(s: Session, release: CatalogRelease) -> Catalog:
    from . import service

    return load(service.release_records(s, release), release.release_code, release.manifest_sha256)


# --- the rate card ---------------------------------------------------------------------------------------------------
def card_document(cat: Catalog) -> dict:
    """The compiled rate card document. Exactly one settings pricing record; products in (position, product) order."""
    settings_rows = [m for m in cat.of(kinds.Pricing).values() if m.scope == "settings"]
    if len(settings_rows) != 1:
        raise CompileError(f"a release holds exactly one card-settings pricing record (found {len(settings_rows)})")
    products = sorted(
        (m for m in cat.of(kinds.Pricing).values() if m.scope == "product"),
        key=lambda m: (m.position, m.engine_product),
    )
    codes = [m.engine_product for m in products]
    if len(set(codes)) != len(codes):
        raise CompileError("two pricing records price the same engine product")
    document = dict(settings_rows[0].body)
    document["version"] = f"{CARD_PREFIX}{cat.release_code}"
    document["products"] = [m.body for m in products]
    return document


def compile_card(cat: Catalog) -> ratecard.RateCard:
    try:
        return estimator_service.validate_document(card_document(cat))
    except estimator_service.CardError as err:
        raise CompileError(str(err).splitlines()[0]) from err


def store_card(s: Session, release: CatalogRelease) -> EstimatorRateCard:
    """The release's compiled card as a CATALOG-<code> card row (DRAFT forever: it never becomes the V1/V2 card)."""
    document = card_document(load_release(s, release))
    version = document["version"]
    row = s.execute(sa.select(EstimatorRateCard).where(EstimatorRateCard.card_version == version)).scalar_one_or_none()
    if row is not None:
        if row.document_sha256 != estimator_service._sha(document):
            raise CompileError(f"card {version} exists with different content; refusing")
        return row
    return estimator_service.load_card(s, document)


# --- visibility (R4) -------------------------------------------------------------------------------------------------
def hidden_paths(cat: Catalog) -> set[str]:
    """Every reference path no customer may see or select: records, variants and choices with staff visibility, and the
    subjects of staff_only rules. Applied to the customer view before serialisation and to every public configuration."""
    out = set(rules.staff_only_subjects(cat))
    for key, p in cat.of(kinds.Product).items():
        if p.visibility == "staff":
            out.add(f"product:{key}")
        for v in p.variants:
            if v.visibility == "staff":
                out.add(f"product:{key}#{v.key}")
            for g in v.option_groups:
                for c in g.choices:
                    if c.visibility == "staff":
                        out.add(f"product:{key}#{v.key}@{g.key}={c.key}")
    for kind, prefix in (
        ("extra", "extra"),
        ("room_template", "room"),
        ("package", "package"),
        ("home_config", "home"),
    ):
        for key, m in cat.models_of(kind).items():
            if getattr(m, "visibility", "customer") == "staff":
                out.add(f"{prefix}:{key}")
    return out


def _variant_hidden(hidden: set[str], pkey: str, vkey: str) -> bool:
    return bool({f"product:{pkey}", f"product:{pkey}#{vkey}"} & hidden)


def _choice_hidden(hidden: set[str], pkey: str, vkey: str, gkey: str, ckey: str) -> bool:
    return _variant_hidden(hidden, pkey, vkey) or bool(
        {f"product:{pkey}#{vkey}@{gkey}={ckey}", f"product:{pkey}@{gkey}={ckey}"} & hidden
    )


# --- the customer view -----------------------------------------------------------------------------------------------
# Staff-only fields, and material and hardware specification fields: a grade, a thickness, a brand, a load capacity or
# a soft-close capability is a promise, shown only through a governed copy statement (R2/R3).
_STAFF_FIELDS = {
    "staff_note", "warranty_source", "note", "visibility", "governance", "rights", "objects", "brands", "grade",
    "thickness", "load_capacity_kg", "soft_close", "compatible_families", "matrix_row", "applies_to",
}  # fmt: skip


def _public(model: kinds._Model) -> dict[str, Any]:
    stripped = _strip(model.model_dump(mode="json", exclude_none=True))
    return stripped if isinstance(stripped, dict) else {}


def _strip(value: object) -> object:
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in _STAFF_FIELDS}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def media_view(m: kinds.Media) -> dict:
    view = _public(m)
    # Delivery variants only, by content hash (immutable, versioned URLs); the private source is never exposed.
    view["urls"] = {name: f"{PUBLIC_MEDIA_PATH}{sha}" for name, sha in sorted(m.objects.variants.items())}
    view["attribution"] = m.attribution or m.rights.owner
    return view


def _product_view(key: str, p: kinds.Product, hidden: set[str]) -> dict:
    view = _public(p)
    variants = []
    for v, vview in zip(p.variants, view["variants"], strict=True):
        if _variant_hidden(hidden, key, v.key):
            continue
        groups = []
        for g, gview in zip(v.option_groups, vview.get("option_groups", []), strict=True):
            choices = [cv for c, cv in zip(g.choices, gview["choices"], strict=True)
                       if not _choice_hidden(hidden, key, v.key, g.key, c.key)]  # fmt: skip
            if choices:
                groups.append({**gview, "choices": choices})
        variants.append({**vview, "option_groups": groups})
    view["variants"] = variants
    return view


def customer_view(cat: Catalog) -> dict:
    """Everything the V3 page may show for this release, filtered before serialisation: no staff-only record, variant,
    choice, extra, room, package or home; no pricing; no staff or specification field; copy reduced to its statement;
    references to hidden things removed."""
    hidden = hidden_paths(cat)

    def shown(prefix: str, key: str) -> bool:
        return f"{prefix}:{key}" not in hidden

    out: dict = {"release": cat.release_code, "manifest_sha256": cat.manifest_sha256}
    out["product"] = {
        k: _product_view(k, p, hidden) for k, p in sorted(cat.of(kinds.Product).items()) if shown("product", k)
    }
    out["product"] = {k: v for k, v in out["product"].items() if v["variants"]}
    out["extra"] = {k: _public(e) for k, e in sorted(cat.of(kinds.Extra).items()) if shown("extra", k)}
    rooms = {}
    for k, r in sorted(cat.of(kinds.RoomTemplate).items()):
        if not shown("room", k):
            continue
        view = _public(r)
        view["included"] = [s for s in view["included"] if s["product"] in out["product"]]
        view["extras"] = [x for x in view["extras"] if x in out["extra"]]
        rooms[k] = view
    out["room_template"] = rooms
    out["package"] = {}
    for k, pk in sorted(cat.of(kinds.Package).items()):
        if shown("package", k):
            view = _public(pk)
            for f in ("included_products", "optional_products"):
                view[f] = [x for x in view.get(f, []) if x in out["product"]]
            for f in ("included_extras", "excluded_extras"):
                view[f] = [x for x in view.get(f, []) if x in out["extra"]]
            out["package"][k] = view
    out["home_config"] = {}
    for k, h in sorted(cat.of(kinds.HomeConfig).items()):
        if shown("home", k):
            view = _public(h)
            view["rooms"] = [r for r in view["rooms"] if r["room_template"] in rooms]
            view["packages"] = [x for x in view["packages"] if x in out["package"]]
            out["home_config"][k] = view
    for kind in ("property_type", "product_family", "material", "hardware"):
        out[kind] = {k: _public(m) for k, m in sorted(cat.models_of(kind).items())
                     if getattr(m, "visibility", "customer") == "customer"}  # fmt: skip
    out["media"] = {k: media_view(m) for k, m in sorted(cat.of(kinds.Media).items())}
    out["copy"] = {k: {"statement": m.statement, "category": m.category} for k, m in sorted(cat.of(kinds.Copy).items())}
    # Rules are mirrored in the browser for feedback only (the server is authoritative); staff-only ones never are.
    out["rule"] = {k: _public(m) for k, m in sorted(cat.of(kinds.Rule).items())
                   if m.type != "staff_only" and m.subject not in hidden}  # fmt: skip
    return out


# --- configuration → engine request (R6) ------------------------------------------------------------------------------
@dataclass
class Resolved:
    request: engine.EstimateRequest
    versions: dict[str, dict[str, int]]
    configuration: configuration.Configuration  # the normal form: exactly what was priced, as stored in the snapshot


def _use(used: dict[str, dict[str, int]], cat: Catalog, kind: str, key: str | None) -> None:
    if not key:
        return
    used.setdefault(kind, {})[key] = cat.version(kind, key)
    model = cat.model(kind, key)
    if isinstance(model, (kinds.Material, kinds.Hardware)):  # the governed statements shown with it
        for statement in model.statements:
            _use(used, cat, "copy", statement)
    elif isinstance(model, kinds.Media):
        for item in model.items:
            _use(used, cat, "media", item)
        if model.three_d:
            _use(used, cat, "media", model.three_d.preview_image)
            _use(used, cat, "media", model.three_d.fallback_gallery)


def _use_all(used: dict[str, dict[str, int]], cat: Catalog, kind: str, keys: Iterable[str | None]) -> None:
    for key in keys:
        _use(used, cat, kind, key)


@dataclass
class _Planned:
    """One engine selection, decided but not yet built (built only when the whole configuration is valid)."""

    room_code: str
    engine_product: str
    options: dict[str, str]
    measurements: dict[str, engine.Measurement]


@dataclass
class _Plan:
    errors: list[dict] = field(default_factory=list)
    active: set[str] = field(default_factory=set)
    measures: dict[str, dict[str, float]] = field(default_factory=dict)
    used: dict[str, dict[str, int]] = field(default_factory=dict)
    selections: list[_Planned] = field(default_factory=list)
    rooms: list[configuration.RoomChoice] = field(default_factory=list)

    def fail(self, where: str, code: str, message: str) -> None:
        self.errors.append({"field": where, "code": code, "message": message})


def resolve(cat: Catalog, raw: object, *, public: bool = True) -> Resolved:
    """Resolve a customer configuration to the engine request, failing closed on anything unknown or unsupported.

    The phases run in a fixed order:
    1. Schema: the strict allowlist.
    2. Plan: home, package and room availability, visibility, package filtering, applicability, options and
       measurement bounds.
    3. Rules: compatibility and dependencies.
    4. Only if nothing failed, the engine request and the normal form are built.

    The selections priced are therefore exactly the normalised configuration that is stored, and re-resolving the
    normal form gives the same request.
    """
    try:
        config = raw if isinstance(raw, configuration.Configuration) else configuration.parse(raw)
    except configuration.ConfigurationError as err:
        raise CompileError(err.errors) from None
    hidden = hidden_paths(cat) if public else set()
    home = cat.one(kinds.HomeConfig, config.home)
    package = cat.one(kinds.Package, config.package)
    if home is None or f"home:{config.home}" in hidden:
        raise CompileError([{"field": "home", "code": "UNKNOWN_HOME", "message": "Choose a home type."}])
    if package is None or config.package not in home.packages or f"package:{config.package}" in hidden:
        raise CompileError([{"field": "package", "code": "PACKAGE_UNAVAILABLE", "message": "Choose a package."}])
    ptype = cat.one(kinds.PropertyType, home.property_type)
    if ptype is None:
        raise CompileError("the home's property type is not in this release")
    plan = _Plan()
    _use(plan.used, cat, "home_config", config.home)
    _use(plan.used, cat, "package", config.package)
    _use(plan.used, cat, "property_type", home.property_type)
    _use(plan.used, cat, "copy", package.public_summary)
    ctx = rules.Context(property_type=ptype.code, home_size=home.home_size, project_kind=config.project_kind,
                        package=package.engine_package, public=public)  # fmt: skip
    if package.consultation_only:
        plan.fail("package", "CONSULTATION_REQUIRED", "This package is priced after a design consultation.")
    allowed_products = set(package.included_products) | set(package.optional_products)  # empty: every product
    allowed_rooms = {slot.room_template for slot in home.rooms}
    seen_rooms: set[str] = set()
    for ri, room_in in enumerate(config.rooms):
        where = f"rooms.{ri}"
        room = cat.one(kinds.RoomTemplate, room_in.room)
        if room is None or room_in.room not in allowed_rooms or f"room:{room_in.room}" in hidden:
            plan.fail(f"{where}.room", "ROOM_UNAVAILABLE", "This room is not offered for this home.")
            continue
        if room_in.room in seen_rooms:
            plan.fail(f"{where}.room", "DUPLICATE_ROOM", "This room is listed twice.")
            continue
        seen_rooms.add(room_in.room)
        _plan_room(cat, plan, ctx, hidden, package, allowed_products, room_in, room, where)
    plan.errors.extend(rules.evaluate(cat, ctx, plan.active, plan.measures))
    for kind, keys in rules.rules_used(cat, plan.active).items():
        _use_all(plan.used, cat, kind, keys)
    if plan.errors:
        raise CompileError(plan.errors)
    try:
        request = engine.EstimateRequest(
            property_type=ptype.code,
            home_size=home.home_size,
            project_kind=config.project_kind,
            package=package.engine_package,
            selections=tuple(
                engine.Selection(
                    room=x.room_code, product=x.engine_product, options=x.options, measurements=x.measurements
                )  # fmt: skip
                for x in plan.selections
            ),
        )
    except ValueError as err:
        raise CompileError(
            [{"field": "rooms", "code": "TOO_MANY", "message": "Too many items for one estimate."}]
        ) from err
    normal = configuration.Configuration(home=config.home, package=config.package, project_kind=config.project_kind,
                                         rooms=plan.rooms)  # fmt: skip
    return Resolved(request=request, versions=plan.used, configuration=normal)


def _plan_room(cat: Catalog, plan: _Plan, ctx: rules.Context, hidden: set[str], package: kinds.Package,
               allowed_products: set[str], room_in: configuration.RoomChoice, room: kinds.RoomTemplate,
               where: str) -> None:  # fmt: skip
    _use(plan.used, cat, "room_template", room_in.room)
    _use_all(plan.used, cat, "media", (room.image, room.gallery))
    plan.active.add(f"room:{room_in.room}")
    slots = {slot.product: slot for slot in room.included}
    for unknown in sorted(set(room_in.products) - set(slots)):
        plan.fail(f"{where}.products.{unknown}", "PRODUCT_UNAVAILABLE", "This item is not offered in this room.")
    for unknown in sorted(set(room_in.extras) - set(room.extras)):
        plan.fail(f"{where}.extras.{unknown}", "EXTRA_UNAVAILABLE", "This extra is not offered in this room.")
    forced: dict[str, dict[str, str]] = {}  # option changes made by selected set_option extras
    for ekey in room.extras:
        extra = cat.one(kinds.Extra, ekey)
        if ekey in room_in.extras and extra is not None and extra.set_option is not None:
            forced.setdefault(extra.set_option.product, {})[extra.set_option.group] = extra.set_option.choice
    products: dict[str, configuration.ProductChoice] = {}
    for pkey, slot in slots.items():
        pin = room_in.products.get(pkey, configuration.ProductChoice())
        pwhere = f"{where}.products.{pkey}"
        if pin.removed:
            if not slot.removable:
                plan.fail(pwhere, "NOT_REMOVABLE", "This item is part of the room.")
            products[pkey] = configuration.ProductChoice(removed=True)
            continue
        if f"product:{pkey}" in hidden or (allowed_products and pkey not in allowed_products):
            plan.fail(pwhere, "PACKAGE_EXCLUDED", "This item is not part of the chosen package.")
            continue
        chosen = _plan_product(cat, plan, ctx, hidden, room, slot, pin, forced.get(pkey, {}), pwhere)
        if chosen is not None:
            products[pkey] = chosen
    extras: dict[str, configuration.ExtraChoice] = {}
    for ekey in room.extras:  # the room's order, as the V2 page sends them
        if ekey in room_in.extras:
            chosen_extra = _plan_extra(cat, plan, hidden, package, room, ekey, room_in.extras[ekey], products,
                                       f"{where}.extras.{ekey}")  # fmt: skip
            if chosen_extra is not None:
                extras[ekey] = chosen_extra
    plan.rooms.append(configuration.RoomChoice(room=room_in.room, products=products, extras=extras))


def _measurements(plan: _Plan, prompts: tuple[kinds.MeasurementPrompt, ...], given: dict[str, float | int],
                  where: str) -> dict[str, engine.Measurement]:  # fmt: skip
    out = {}
    by_input = {p.input: p for p in prompts}
    for name, value in given.items():
        prompt = by_input.get(name)
        if prompt is None:
            plan.fail(f"{where}.measurements.{name}", "UNKNOWN_INPUT", "This measurement is not asked for this item.")
            continue
        if not prompt.min <= value <= prompt.max:
            plan.fail(f"{where}.measurements.{name}", "OUT_OF_RANGE",
                      f"Enter between {prompt.min:g} and {prompt.max:g} {prompt.unit}.")  # fmt: skip
            continue
        out[name] = engine.Measurement(value=float(value), unit=prompt.unit)
    return out


def _plan_product(cat: Catalog, plan: _Plan, ctx: rules.Context, hidden: set[str], room: kinds.RoomTemplate,
                  slot: kinds.ProductSlot, pin: configuration.ProductChoice, forced: dict[str, str],
                  where: str) -> configuration.ProductChoice | None:  # fmt: skip
    product = cat.one(kinds.Product, slot.product)
    if product is None:
        plan.fail(where, "PRODUCT_UNAVAILABLE", "This item is not available.")
        return None
    vkey = pin.variant or slot.variant
    variant = next((v for v in product.variants if v.key == vkey), None)
    if variant is None or _variant_hidden(hidden, slot.product, vkey):
        plan.fail(f"{where}.variant", "VARIANT_UNAVAILABLE", "This option is not available.")
        return None
    if room.room_code not in product.rooms:
        plan.fail(where, "PRODUCT_UNAVAILABLE", "This item is not offered in this room.")
        return None
    if ctx.package not in product.packages:
        plan.fail(where, "PACKAGE_EXCLUDED", "This item is not part of the chosen package.")
        return None
    _use(plan.used, cat, "product", slot.product)
    _use(plan.used, cat, "product_family", product.family)
    plan.active.update({f"product:{slot.product}", f"product:{slot.product}#{vkey}"})
    options = dict(variant.engine_options)
    presets = slot.options if vkey == slot.variant else {}  # the room's presets belong to its own variant
    wanted = {**presets, **pin.options, **forced}
    for gkey in sorted(set(wanted) - {g.key for g in variant.option_groups}):
        plan.fail(f"{where}.options.{gkey}", "UNKNOWN_OPTION", "This choice is not offered for this item.")
    chosen: dict[str, str] = {}
    for group in variant.option_groups:
        ckey = wanted.get(group.key, group.default)
        choice = next((c for c in group.choices if c.key == ckey), None)
        if choice is None or _choice_hidden(hidden, slot.product, vkey, group.key, ckey):
            plan.fail(f"{where}.options.{group.key}", "UNKNOWN_CHOICE", "This choice is not offered for this item.")
            continue
        chosen[group.key] = ckey
        options.update(choice.engine_options)
        plan.active.update(
            {f"product:{slot.product}#{vkey}@{group.key}={ckey}", f"product:{slot.product}@{group.key}={ckey}"}
        )
        _use_all(plan.used, cat, "material", choice.materials)
        _use_all(plan.used, cat, "hardware", choice.hardware)
        _use_all(plan.used, cat, "media", choice.media)
    _use_all(plan.used, cat, "material", variant.materials)
    _use_all(plan.used, cat, "hardware", variant.hardware)
    _use_all(plan.used, cat, "media", (*product.media, *variant.media))
    given = _measurements(plan, variant.measurements, pin.measurements, where)
    plan.measures[f"product:{slot.product}"] = {k: m.value for k, m in given.items()}
    plan.selections.append(_Planned(room.room_code, variant.engine_product, options, given))
    return configuration.ProductChoice(
        variant=vkey, options=chosen, measurements={k: m.value for k, m in given.items()}
    )


def _plan_extra(cat: Catalog, plan: _Plan, hidden: set[str], package: kinds.Package, room: kinds.RoomTemplate,
                ekey: str, ein: configuration.ExtraChoice, products: dict[str, configuration.ProductChoice],
                where: str) -> configuration.ExtraChoice | None:  # fmt: skip
    extra = cat.one(kinds.Extra, ekey)
    if extra is None or f"extra:{ekey}" in hidden:
        plan.fail(where, "EXTRA_UNAVAILABLE", "This extra is not available.")
        return None
    if ekey in package.excluded_extras:
        plan.fail(where, "PACKAGE_EXCLUDED", "This extra is not part of the chosen package.")
        return None
    count = 1 if extra.quantity == "fixed" else ein.count
    if not 1 <= count <= extra.max_count:
        plan.fail(f"{where}.count", "OUT_OF_RANGE", f"Choose between 1 and {extra.max_count}.")
        return None
    _use(plan.used, cat, "extra", ekey)
    _use_all(plan.used, cat, "material", extra.materials)
    _use_all(plan.used, cat, "hardware", extra.hardware)
    _use_all(plan.used, cat, "media", extra.media)
    plan.active.add(f"extra:{ekey}")
    if extra.set_option is not None:
        target = products.get(extra.set_option.product)
        if target is None or target.removed:
            plan.fail(where, "REQUIRES_ITEM", "This extra needs the item it upgrades.")
            return None
        return configuration.ExtraChoice(count=1)
    if extra.add is None:  # the schema requires exactly one of add and set_option; refuse rather than assume
        plan.fail(where, "EXTRA_UNAVAILABLE", "This extra is not available.")
        return None
    given = _measurements(plan, extra.measurements, ein.measurements, where)
    plan.measures[f"extra:{ekey}"] = {k: m.value for k, m in given.items()}
    for _ in range(count):
        plan.selections.append(
            _Planned(room.room_code, extra.add.engine_product, dict(extra.add.engine_options), given)
        )
    return configuration.ExtraChoice(count=count, measurements={k: m.value for k, m in given.items()})
