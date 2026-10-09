"""Release validation (ADR-013 D7). Activation, release approval and submission all re-run it, and any error refuses.

The report names records and checks, never rates. `compiled` holds the digests of the compiled artefacts; the card
itself is stored only when the release is activated.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.modules.estimator import engine, promise_matrix, ratecard

from . import compile as catalog_compile
from . import kinds, rules
from .models import CatalogMediaObject, CatalogRelease

CHECKS = (
    "schema", "references", "pricing", "measurements", "defaults", "promises", "media", "three_d", "rules", "card",
)  # fmt: skip
_UNIT = {"length": "ft", "area": "sqft"}


def _digest(document) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(s: Session, release: CatalogRelease, *, today: date | None = None) -> dict:
    errors: dict[str, list[str]] = {c: [] for c in CHECKS}
    warnings: list[str] = []
    today = today or date.today()
    try:
        cat = catalog_compile.load_release(s, release)
    except Exception as err:  # noqa: BLE001 — any schema or integrity failure refuses the release
        errors["schema"].append(str(err).splitlines()[0][:300])
        return _report(errors, warnings, None)
    _references(cat, errors["references"])
    card = None
    try:
        card = catalog_compile.compile_card(cat)
    except catalog_compile.CompileError as err:
        errors["card"].append(str(err)[:300])
    if card is not None:
        _pricing(cat, card, errors["pricing"], errors["measurements"])
        _defaults(cat, card, errors["defaults"], today)
    _promises(cat, errors["promises"], warnings)
    _media(s, cat, errors["media"], errors["three_d"], warnings, today)
    errors["rules"].extend(rules.contradictions(cat))
    if not cat.of(kinds.HomeConfig):
        errors["references"].append("the release has no home configuration")
    _warnings(cat, warnings)
    compiled = None
    if card is not None and not any(errors.values()):
        view = catalog_compile.customer_view(cat)
        compiled = {
            "card_version": card.version,
            "card_sha256": _digest(catalog_compile.card_document(cat)),
            "view_sha256": _digest(view),
        }
    return _report(errors, warnings, compiled)


def _report(errors: dict[str, list[str]], warnings: list[str], compiled) -> dict:
    flat = [f"{check}: {e}" for check, es in errors.items() for e in es]
    return {
        "ok": not flat,
        "checks": {c: ("fail" if errors[c] else "pass") for c in CHECKS},
        "errors": flat,
        "warnings": sorted(set(warnings)),
        "compiled": compiled,
    }


def _references(cat, out: list[str]) -> None:
    for kind, models in sorted(cat.models.items()):
        for key, model in sorted(models.items()):
            for rkind, rkey in kinds.references(kind, model):
                if cat.model(rkind, rkey) is None:
                    out.append(f"{kind} {key} refers to {rkind} {rkey}, which is not in the release")
    for key, room in cat.of(kinds.RoomTemplate).items():
        for slot in room.included:
            product = cat.one(kinds.Product, slot.product)
            if product is None:
                continue
            variant = next((v for v in product.variants if v.key == slot.variant), None)
            if variant is None:
                out.append(f"room_template {key}: {slot.product} has no variant {slot.variant}")
                continue
            groups = {g.key: g for g in variant.option_groups}
            for gkey, ckey in slot.options.items():
                if gkey not in groups or ckey not in {c.key for c in groups[gkey].choices}:
                    out.append(f"room_template {key}: {slot.product} has no choice {gkey}={ckey}")
            if room.room_code not in product.rooms:
                out.append(f"room_template {key}: {slot.product} is not offered in {room.room_code}")
        for ekey in room.extras:
            extra = cat.one(kinds.Extra, ekey)
            if extra is not None and extra.set_option is not None:
                if extra.set_option.product not in {slot.product for slot in room.included}:
                    out.append(
                        f"room_template {key}: extra {ekey} upgrades {extra.set_option.product}, not in the room"
                    )
    for key, extra in cat.of(kinds.Extra).items():
        if extra.set_option is None:
            continue
        product = cat.one(kinds.Product, extra.set_option.product)
        found = product is not None and any(
            g.key == extra.set_option.group and extra.set_option.choice in {c.key for c in g.choices}
            for v in product.variants
            for g in v.option_groups
        )
        if not found:
            out.append(f"extra {key}: {extra.set_option.product} has no choice "
                       f"{extra.set_option.group}={extra.set_option.choice}")  # fmt: skip
    for key, media in cat.of(kinds.Media).items():
        if media.type == "GALLERY":
            for item in media.items:
                m = cat.one(kinds.Media, item)
                if m is not None and m.type in ("GALLERY", "EXTERNAL_EMBED"):
                    out.append(f"media {key}: gallery item {item} is a {m.type}")
    for key, room in cat.of(kinds.RoomTemplate).items():
        for attr, want in (("image", ("IMAGE",)), ("gallery", ("GALLERY",))):
            m = cat.one(kinds.Media, getattr(room, attr))
            if m is not None and m.type not in want:
                out.append(f"room_template {key}: its {attr} must be a {want[0]} media record")


def _engine_options_ok(spec: ratecard.ProductSpec, options: dict, where: str, out: list[str]) -> None:
    by_name = {o.name: o for o in spec.options}
    for name, choice in options.items():
        if name not in by_name or choice not in by_name[name].choices:
            out.append(f"{where}: {spec.code} has no option {name}={choice}")


def _pricing(cat, card: ratecard.RateCard, out: list[str], mout: list[str]) -> None:
    """Every selectable item resolves to an engine product and options that the compiled card prices."""
    for key, product in cat.of(kinds.Product).items():
        if not set(product.packages) & set(card.enabled_packages()):
            out.append(f"product {key}: none of its packages is priced")
        for v in product.variants:
            spec = card.product(v.engine_product)
            where = f"product {key}#{v.key}"
            if spec is None:
                out.append(f"{where}: engine product {v.engine_product} is not priced")
                continue
            missing_rooms = set(product.rooms) - set(spec.rooms)
            if missing_rooms:
                out.append(f"{where}: {v.engine_product} is not priced in {sorted(missing_rooms)}")
            _engine_options_ok(spec, v.engine_options, where, out)
            for g in v.option_groups:
                for c in g.choices:
                    _engine_options_ok(spec, c.engine_options, f"{where}@{g.key}={c.key}", out)
            inputs = {i.name: i for i in spec.inputs}
            for prompt in v.measurements:
                _prompt_ok(card, inputs, prompt, where, mout)
    for key, extra in cat.of(kinds.Extra).items():
        if extra.add is None:
            continue
        spec = card.product(extra.add.engine_product)
        if spec is None:
            out.append(f"extra {key}: engine product {extra.add.engine_product} is not priced")
            continue
        _engine_options_ok(spec, extra.add.engine_options, f"extra {key}", out)
        inputs = {i.name: i for i in spec.inputs}
        for prompt in extra.measurements:
            _prompt_ok(card, inputs, prompt, f"extra {key}", mout)
        for rkey in extra.rooms:
            room = cat.one(kinds.RoomTemplate, rkey)
            if room is not None and room.room_code not in spec.rooms:
                out.append(f"extra {key}: {extra.add.engine_product} is not priced in {room.room_code}")
    for key, package in cat.of(kinds.Package).items():
        if not package.consultation_only and package.engine_package not in card.enabled_packages():
            out.append(f"package {key}: {package.engine_package} is not priced (mark it consultation-only)")
        if package.engine_package == "LUXURY" and not package.consultation_only:
            out.append(f"package {key}: Luxury is never priced online (ADR-012 D2); mark it consultation-only")


def _prompt_ok(card, inputs, prompt, where, out) -> None:
    spec = inputs.get(prompt.input)
    if spec is None or spec.kind == "count":
        out.append(f"{where}: measurement {prompt.input} is not a length or area input of the priced product")
        return
    if _UNIT[spec.kind] != prompt.unit:
        out.append(f"{where}: measurement {prompt.input} is a {spec.kind}, asked in {prompt.unit}")
    bound = card.bounds[spec.kind]
    if prompt.min < bound.min or prompt.max > bound.max or prompt.max < prompt.min:
        out.append(f"{where}: measurement {prompt.input} range is outside the card's bounds")


def default_configuration(cat, home_key: str, package_key: str) -> dict:
    home = cat.one(kinds.HomeConfig, home_key)
    rooms = []
    for slot in home.rooms:
        if not slot.default_selected:
            continue
        room = cat.one(kinds.RoomTemplate, slot.room_template)
        extras: dict[str, dict[str, object]] = {}
        for ekey in room.extras if room else ():
            extra = cat.one(kinds.Extra, ekey)
            if extra is not None and extra.default_selected:
                extras[ekey] = {}
        rooms.append({"room": slot.room_template, "products": {}, "extras": extras})
    return {"home": home_key, "package": package_key, "project_kind": "NEW_HOME", "rooms": rooms}


def _defaults(cat, card, out: list[str], today: date) -> None:
    """Every home's default configuration resolves and prices, under every package it offers online."""
    for hkey, home in sorted(cat.of(kinds.HomeConfig).items()):
        ptype = cat.one(kinds.PropertyType, home.property_type)
        if ptype is None:
            continue
        for pkey in home.packages:
            package = cat.one(kinds.Package, pkey)
            if package is None or package.consultation_only:
                continue
            config = default_configuration(cat, hkey, pkey)
            for project_kind in home.availability.project_kinds or ("NEW_HOME",):
                config["project_kind"] = project_kind
                try:
                    resolved = catalog_compile.resolve(cat, config)
                    engine.calculate(card, resolved.request)
                except catalog_compile.CompileError as err:
                    out.append(
                        f"home {hkey} / {pkey}: the default configuration is refused ({err.errors[0]['message']})"
                    )
                except engine.EstimateError as err:
                    out.append(
                        f"home {hkey} / {pkey}: the default configuration does not price ({err.errors[0]['code']})"
                    )


def _promises(cat, out: list[str], warnings: list[str]) -> None:
    """Every customer statement is a registered copy record; a promise needs its owner, backup, verification path and
    operational confirmation (the M3 rule of the V2 closure, applied to catalog copy)."""
    for key, copy in sorted(cat.of(kinds.Copy).items()):
        if not copy.promise:
            continue
        g = copy.governance
        named = all(promise_matrix._named(x) for x in (g.owner, g.backup, g.verification, g.quotation_mapping,
                                                       g.warranty_source))  # fmt: skip
        if not named:
            out.append(f"copy {key}: promise has an unassigned owner, backup or verification path")
        if g.status != "OPERATIONALLY_CONFIRMED" or g.confirmed_on is None:
            out.append(f"copy {key}: promise is not operationally confirmed")
    for kind in ("material", "hardware"):
        for key, m in cat.models_of(kind).items():
            if not any(cat.one(kinds.Copy, s) is not None for s in m.statements):
                out.append(f"{kind} {key}: no registered statement")
    for key, package in cat.of(kinds.Package).items():
        if package.warranty_copy is None and not package.consultation_only:
            warnings.append(f"package {key}: no warranty statement")


def _objects(s: Session, shas: set[str]) -> dict[str, CatalogMediaObject]:
    if not shas:
        return {}
    rows = s.execute(
        sa.select(CatalogMediaObject).where(
            CatalogMediaObject.object_sha256.in_(sorted(shas)), CatalogMediaObject.is_deleted.is_(False)
        )
    ).scalars()
    return {r.object_sha256: r for r in rows}


def _media(s: Session, cat, out: list[str], out3d: list[str], warnings: list[str], today: date) -> None:
    shas = {sha for m in cat.of(kinds.Media).values() for sha in m.objects.variants.values()}
    found = _objects(s, shas)
    for key, m in sorted(cat.of(kinds.Media).items()):
        if m.rights.expires and m.rights.expires < today:
            out.append(f"media {key}: usage rights expired on {m.rights.expires.isoformat()}")
        if m.objects.source and m.objects.source in set(m.objects.variants.values()):
            out.append(f"media {key}: the private source is listed as a delivery variant")
        for name, sha in sorted(m.objects.variants.items()):
            obj = found.get(sha)
            if obj is None:
                out.append(f"media {key}: {name} file is not stored")
            elif obj.role != "VARIANT":
                out.append(f"media {key}: {name} is not a generated delivery variant")
            elif obj.scan_status != "CLEAN":
                out.append(f"media {key}: {name} file is {obj.scan_status}")
        if m.type in ("GLB", "GLTF", "USDZ"):
            t = m.three_d
            preview, fallback = cat.one(kinds.Media, t.preview_image), cat.one(kinds.Media, t.fallback_gallery)
            if preview is None or preview.type != "IMAGE":
                out3d.append(f"media {key}: the 3D preview must be an IMAGE in the release")
            if fallback is None or fallback.type != "GALLERY":
                out3d.append(f"media {key}: the 3D fallback must be a GALLERY in the release")
            web = found.get(m.objects.variants.get("web"))
            if web is not None and web.media_kind not in ("GLB", "GLTF", "USDZ"):
                out3d.append(f"media {key}: the web file is not a validated 3D model")
            for vkey in t.variant_map:
                if not any(vkey == v.key for p in cat.of(kinds.Product).values() for v in p.variants):
                    out3d.append(f"media {key}: variant_map names unknown variant {vkey}")
            for mkey in t.finish_map:
                if cat.one(kinds.Material, mkey) is None:
                    out3d.append(f"media {key}: finish_map names material {mkey}, not in the release")


def _warnings(cat, warnings: list[str]) -> None:
    for key, p in cat.of(kinds.Product).items():
        if not p.media and not any(v.media for v in p.variants):
            warnings.append(f"product {key}: no image")
    for key, e in cat.of(kinds.Extra).items():
        if not e.what_is_this:
            warnings.append(f"extra {key}: no 'What is this?' explanation")
        if not e.media:
            warnings.append(f"extra {key}: no image")
    for key, room in cat.of(kinds.RoomTemplate).items():
        if room.image is None:
            warnings.append(f"room_template {key}: no representative image")
    referenced = {(k, x) for kind, ms in cat.models.items() for m in ms.values() for k, x in kinds.references(kind, m)}
    for kind in ("product", "extra", "material", "hardware", "media", "copy"):
        for key in cat.models_of(kind):
            if (kind, key) not in referenced:
                warnings.append(f"{kind} {key}: not used by anything in the release")
