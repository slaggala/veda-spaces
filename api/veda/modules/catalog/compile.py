"""Compile a catalog release into the artefacts the existing estimator already uses (ADR-013 D1).

- `card_document`: the rate card (settings pricing record + product pricing records), validated by `ratecard.parse`.
- `customer_view`: what the customer page may show (no rate, no staff note, no governance detail, no source media).
- `resolve`: a customer configuration → an `engine.EstimateRequest` (the pricing inputs) plus the record versions used.

The ADR-012 engine prices the request unchanged; there is no second pricing engine. Geometry from 3D assets is never
an input: only the catalog's engine product, options and the customer's measurements reach the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.modules.estimator import engine, ratecard
from veda.modules.estimator import service as estimator_service
from veda.modules.estimator.models import EstimatorRateCard

from . import kinds, rules
from .models import CatalogRecord, CatalogRelease

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

    def get(self, kind: str, key: str | None):
        return self.models.get(kind, {}).get(key) if key else None

    def all(self, kind: str) -> dict[str, kinds._Model]:
        return self.models.get(kind, {})

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
    settings_rows = [m for m in cat.all("pricing").values() if m.scope == "settings"]
    if len(settings_rows) != 1:
        raise CompileError(f"a release holds exactly one card-settings pricing record (found {len(settings_rows)})")
    products = sorted(
        (m for m in cat.all("pricing").values() if m.scope == "product"), key=lambda m: (m.position, m.engine_product)
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


# --- the customer view -----------------------------------------------------------------------------------------------
_STAFF_FIELDS = {"staff_note", "warranty_source", "note", "visibility", "governance", "rights", "objects"}


def _public(model: kinds._Model) -> dict:
    data = model.model_dump(mode="json", exclude_none=True)
    return _strip(data)


def _strip(value):
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


def customer_view(cat: Catalog) -> dict:
    """Everything the V3 page may show for this release. Staff-only records, pricing and staff-only rules are left out;
    copy is reduced to its statement."""
    out: dict = {"release": cat.release_code, "manifest_sha256": cat.manifest_sha256}
    for kind in ("property_type", "home_config", "room_template", "product_family", "product", "extra", "material",
                 "hardware", "package"):  # fmt: skip
        out[kind] = {
            k: _public(m)
            for k, m in sorted(cat.all(kind).items())
            if getattr(m, "visibility", "customer") == "customer"
        }
    for p in out["product"].values():
        p["variants"] = [v for v in p["variants"] if v.get("visibility", "customer") == "customer"]
    out["media"] = {k: media_view(m) for k, m in sorted(cat.all("media").items())}
    out["copy"] = {k: {"statement": m.statement, "category": m.category} for k, m in sorted(cat.all("copy").items())}
    out["rule"] = {
        k: _public(m) for k, m in sorted(cat.all("rule").items()) if m.type != "staff_only"
    }  # mirrored in the browser for feedback only; the server is authoritative
    out["hidden"] = sorted(rules.staff_only_subjects(cat))
    return out


# --- configuration → engine request ---------------------------------------------------------------------------------
@dataclass
class Resolved:
    request: engine.EstimateRequest
    versions: dict[str, dict[str, int]]
    selections: dict


def _use(used: dict, cat: Catalog, kind: str, key: str | None) -> None:
    if key:
        used.setdefault(kind, {})[key] = cat.version(kind, key)
    model = cat.get(kind, key) if key else None
    if isinstance(model, (kinds.Material, kinds.Hardware)):  # the governed statements shown with it
        for statement in model.statements:
            _use(used, cat, "copy", statement)
    elif isinstance(model, kinds.Media):
        for item in model.items:
            _use(used, cat, "media", item)
        if model.three_d:
            _use(used, cat, "media", model.three_d.preview_image)
            _use(used, cat, "media", model.three_d.fallback_gallery)


def _use_all(used: dict, cat: Catalog, kind: str, keys) -> None:
    for key in keys:
        _use(used, cat, kind, key)


def resolve(cat: Catalog, config: dict, *, public: bool = True) -> Resolved:
    """Resolve a customer configuration to the engine request. Every unknown or unsupported choice fails closed.

    config = {home, project_kind, package, city?, rooms: [{room, products: {product: {variant?, options?, removed?,
    measurements?}}, extras: {extra: {count?, measurements?}}}]}
    """
    errors: list[dict] = []

    def fail(where: str, code: str, message: str) -> None:
        errors.append({"field": where, "code": code, "message": message})

    used: dict[str, dict[str, int]] = {}
    home = cat.get("home_config", config.get("home"))
    package = cat.get("package", config.get("package"))
    if home is None:
        raise CompileError([{"field": "home", "code": "UNKNOWN_HOME", "message": "Choose a home type."}])
    if package is None or config.get("package") not in home.packages:
        raise CompileError([{"field": "package", "code": "PACKAGE_UNAVAILABLE", "message": "Choose a package."}])
    ptype = cat.get("property_type", home.property_type)
    if ptype is None:
        raise CompileError("the home's property type is not in this release")
    _use(used, cat, "home_config", config["home"])
    _use(used, cat, "package", config["package"])
    _use(used, cat, "property_type", home.property_type)
    ctx = rules.Context(
        property_type=ptype.code,
        home_size=home.home_size,
        project_kind=config.get("project_kind", "NEW_HOME"),
        package=package.engine_package,
        market=config.get("city"),
        public=public,
    )
    if package.consultation_only:
        fail("package", "CONSULTATION_REQUIRED", "This package is priced after a design consultation.")
    _use(used, cat, "copy", package.public_summary)
    allowed_rooms = {slot.room_template for slot in home.rooms}
    active: set[str] = set()
    measures: dict[str, dict[str, float]] = {}
    selections: list[engine.Selection] = []
    rooms_in = config.get("rooms") or []
    seen_rooms: set[str] = set()
    for ri, room_in in enumerate(rooms_in):
        rkey = room_in.get("room")
        where = f"rooms[{ri}]"
        room = cat.get("room_template", rkey)
        if room is None or rkey not in allowed_rooms:
            fail(f"{where}.room", "ROOM_UNAVAILABLE", "This room is not offered for this home.")
            continue
        if rkey in seen_rooms:
            fail(f"{where}.room", "DUPLICATE_ROOM", "This room is listed twice.")
            continue
        seen_rooms.add(rkey)
        _use(used, cat, "room_template", rkey)
        _use_all(used, cat, "media", (room.image, room.gallery))
        active.add(f"room:{rkey}")
        products_in = room_in.get("products") or {}
        slots = {slot.product: slot for slot in room.included}
        for unknown in set(products_in) - set(slots):
            fail(f"{where}.products.{unknown}", "PRODUCT_UNAVAILABLE", "This item is not offered in this room.")
        extras_in = room_in.get("extras") or {}
        for unknown in set(extras_in) - set(room.extras):
            fail(f"{where}.extras.{unknown}", "EXTRA_UNAVAILABLE", "This extra is not offered in this room.")
        # Option changes requested by selected extras (set_option), applied to the room's included products.
        forced: dict[str, dict[str, str]] = {}
        for ekey in room.extras:
            if ekey not in extras_in:
                continue
            extra = cat.get("extra", ekey)
            if extra is not None and extra.set_option is not None:
                forced.setdefault(extra.set_option.product, {})[extra.set_option.group] = extra.set_option.choice
        for pkey, slot in slots.items():
            pin = products_in.get(pkey) or {}
            pwhere = f"{where}.products.{pkey}"
            if pin.get("removed"):
                if not slot.removable:
                    fail(pwhere, "NOT_REMOVABLE", "This item is part of the room.")
                continue
            sel = _product_selection(cat, room, slot, pin, forced.get(pkey, {}), ctx, pwhere, fail, used, active,
                                     measures)  # fmt: skip
            if sel is not None:
                selections.append(sel)
        for ekey in room.extras:  # the room's order, as the V2 page sends them
            if ekey not in extras_in:
                continue
            ein = extras_in[ekey]
            sel = _extra_selection(cat, room, ekey, ein or {}, slots, products_in, ctx, f"{where}.extras.{ekey}", fail,
                                   used, active, measures)  # fmt: skip
            selections.extend(sel)
    if not rooms_in:
        fail("rooms", "NO_ROOMS", "Choose at least one room.")
    errors.extend(rules.evaluate(cat, ctx, active, measures))
    for kind, keys in rules.rules_used(cat, active).items():
        for key in keys:
            _use(used, cat, kind, key)
    if errors:
        raise CompileError(errors)
    try:
        request = engine.EstimateRequest(
            property_type=ptype.code,
            home_size=home.home_size,
            project_kind=ctx.project_kind,
            city=config.get("city") or None,
            package=package.engine_package,
            selections=tuple(selections),
        )
    except ValueError as err:
        raise CompileError("the configuration cannot be priced (too many or invalid selections)") from err
    return Resolved(request=request, versions=used, selections=config)


def _measurements(prompts, given: dict, where: str, fail) -> dict[str, engine.Measurement]:
    out = {}
    by_input = {p.input: p for p in prompts}
    for name, value in (given or {}).items():
        prompt = by_input.get(name)
        if prompt is None:
            fail(f"{where}.measurements.{name}", "UNKNOWN_INPUT", "This measurement is not asked for this item.")
            continue
        if not isinstance(value, int | float) or isinstance(value, bool) or not prompt.min <= value <= prompt.max:
            fail(
                f"{where}.measurements.{name}",
                "OUT_OF_RANGE",
                f"Enter between {prompt.min:g} and {prompt.max:g} {prompt.unit}.",
            )
            continue
        out[name] = engine.Measurement(value=float(value), unit=prompt.unit)
    return out


def _product_selection(cat, room, slot, pin, forced, ctx, where, fail, used, active, measures):
    product = cat.get("product", slot.product)
    if product is None:
        fail(where, "PRODUCT_UNAVAILABLE", "This item is not available.")
        return None
    vkey = pin.get("variant") or slot.variant
    variant = next((v for v in product.variants if v.key == vkey), None)
    if variant is None or (ctx.public and variant.visibility != "customer"):
        fail(f"{where}.variant", "VARIANT_UNAVAILABLE", "This option is not available.")
        return None
    if room.room_code not in product.rooms:
        fail(where, "PRODUCT_UNAVAILABLE", "This item is not offered in this room.")
        return None
    if ctx.package not in product.packages:
        fail(where, "PACKAGE_UNAVAILABLE", "This item is not part of the chosen package.")
        return None
    _use(used, cat, "product", slot.product)
    _use(used, cat, "product_family", product.family)
    active.update({f"product:{slot.product}", f"product:{slot.product}#{vkey}"})
    options = dict(variant.engine_options)
    defaults = slot.options if vkey == slot.variant else {}  # the room's presets belong to its own variant
    chosen = {**defaults, **(pin.get("options") or {}), **forced}
    for gkey in set(chosen) - {g.key for g in variant.option_groups}:
        fail(f"{where}.options.{gkey}", "UNKNOWN_OPTION", "This choice is not offered for this item.")
    for group in variant.option_groups:
        ckey = chosen.get(group.key, group.default)
        choice = next((c for c in group.choices if c.key == ckey), None)
        if choice is None or (ctx.public and choice.visibility != "customer"):
            fail(f"{where}.options.{group.key}", "UNKNOWN_CHOICE", "This choice is not offered for this item.")
            continue
        options.update(choice.engine_options)
        active.add(f"product:{slot.product}#{vkey}@{group.key}={ckey}")
        active.add(f"product:{slot.product}@{group.key}={ckey}")
        _use_all(used, cat, "material", choice.materials)
        _use_all(used, cat, "hardware", choice.hardware)
        _use_all(used, cat, "media", choice.media)
    _use_all(used, cat, "material", variant.materials)
    _use_all(used, cat, "hardware", variant.hardware)
    _use_all(used, cat, "media", (*product.media, *variant.media))
    given = _measurements(variant.measurements, pin.get("measurements"), where, fail)
    measures[f"product:{slot.product}"] = {k: m.value for k, m in given.items()}
    return engine.Selection(room=room.room_code, product=variant.engine_product, measurements=given, options=options)


def _extra_selection(cat, room, ekey, ein, slots, products_in, ctx, where, fail, used, active, measures):
    extra = cat.get("extra", ekey)
    if extra is None or (ctx.public and extra.visibility != "customer"):
        fail(where, "EXTRA_UNAVAILABLE", "This extra is not available.")
        return []
    _use(used, cat, "extra", ekey)
    _use_all(used, cat, "material", extra.materials)
    _use_all(used, cat, "hardware", extra.hardware)
    _use_all(used, cat, "media", extra.media)
    active.add(f"extra:{ekey}")
    count = ein.get("count", 1)
    if extra.quantity == "fixed":
        count = 1
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= extra.max_count:
        fail(f"{where}.count", "OUT_OF_RANGE", f"Choose between 1 and {extra.max_count}.")
        return []
    if extra.set_option is not None:
        target = extra.set_option.product
        if target not in slots or (products_in.get(target) or {}).get("removed"):
            fail(where, "REQUIRES_ITEM", "This extra needs the item it upgrades.")
        return []
    given = _measurements(extra.measurements, ein.get("measurements"), where, fail)
    measures[f"extra:{ekey}"] = {k: m.value for k, m in given.items()}
    return [
        engine.Selection(
            room=room.room_code, product=extra.add.engine_product, measurements=given, options=extra.add.engine_options
        )
        for _ in range(count)
    ]
