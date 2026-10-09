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

from veda.config import settings
from veda.modules.estimator import engine, promise_matrix, ratecard

from . import compile as catalog_compile
from . import kinds, public, rules, text
from .models import CatalogMediaObject, CatalogRelease

CHECKS = (
    "schema", "references", "pricing", "measurements", "defaults", "promises", "copy", "media", "three_d", "rules",
    "card", "public_payload",
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
    _copy(cat, errors["copy"], today)
    _media(s, cat, errors["media"], errors["three_d"], warnings, today)
    errors["rules"].extend(rules.contradictions(cat))
    for key, rule in sorted(cat.of(kinds.Rule).items()):
        for path in (rule.subject, *rule.objects):
            problem = rules.path_problem(cat, path)
            if problem:
                errors["rules"].append(f"rule {key}: {path}: {problem}")
    errors["references"].extend(_hidden_defaults(cat))
    if not cat.of(kinds.HomeConfig):
        errors["references"].append("the release has no home configuration")
    _warnings(cat, warnings)
    payload_sha = _public_payload(s, cat, card, errors["public_payload"]) if card is not None else None
    compiled = None
    if card is not None and not any(errors.values()):
        view = catalog_compile.customer_view(cat)
        compiled = {
            "card_version": card.version,
            "card_sha256": _digest(catalog_compile.card_document(cat)),
            "view_sha256": _digest(view),
            "public_payload_sha256": payload_sha,
        }
    return _report(errors, warnings, compiled)


# --- the final resolved public payload (canonical customer-copy closure, Phase 7) -----------------------------------
# Representative estimates carry fixed placeholder identifiers so their digest depends only on the content.
_PLACEHOLDER = {"reference": "E-RELEASE-CHECK", "expires_on": "2000-01-01", "configuration_reference": "C00000000"}


def representative_configurations(cat) -> list[dict]:
    """Every home's default under each online package and project kind, then each customer extra added to and each
    other customer variant chosen in a default room: the estimate texts each of them produces are what is checked."""
    hidden = catalog_compile.hidden_paths(cat)
    out = []
    for hkey, home in sorted(cat.of(kinds.HomeConfig).items()):
        for pkey in home.packages:
            package = cat.one(kinds.Package, pkey)
            if package is None or package.consultation_only or package.engine_package == "LUXURY":
                continue
            for project_kind in home.availability.project_kinds or ("NEW_HOME",):
                base = {**default_configuration(cat, hkey, pkey), "project_kind": project_kind}
                out.append(base)
                for i, room in enumerate(base["rooms"]):
                    template = cat.one(kinds.RoomTemplate, room["room"])
                    if template is None:
                        continue
                    for ekey in template.extras:
                        if f"extra:{ekey}" not in hidden and ekey not in room["extras"]:
                            out.append(_with(base, i, extras={**room["extras"], ekey: {}}))
                    for slot in template.included:
                        product = cat.one(kinds.Product, slot.product)
                        for v in product.variants if product else ():
                            if v.key != slot.variant and not catalog_compile._variant_hidden(
                                hidden, slot.product, v.key
                            ):
                                out.append(_with(base, i, products={slot.product: {"variant": v.key}}))
    return out


def _with(base: dict, i: int, **room) -> dict:
    rooms = [dict(r) for r in base["rooms"]]
    rooms[i] = {**rooms[i], **room}
    return {**base, "rooms": rooms}


def _public_payload(s: Session, cat, card, out: list[str]) -> str | None:
    """Build the complete public catalog payload and the representative estimate payloads exactly as they would be
    served, traverse every string through the one canonical checker, check the card's customer-visible text (the card
    is staff-only; its text is not), and return the digest of everything checked. Unclassified fields, weak types
    and payloads that do not build fail closed."""
    from veda.modules.estimator import service as estimator_service

    payloads: list = []
    try:
        dto = public.build_catalog(cat)
    except (ValueError, KeyError) as err:
        out.append(f"the public catalog payload does not build: {str(err).splitlines()[0][:200]}")
        return None
    # The digest covers customer content: the release's own identifiers are neutralised, so a rollback that restores
    # exactly what customers saw has the same digest as the release it restores.
    payloads.append(
        dto.model_copy(update={"release": _PLACEHOLDER["configuration_reference"], "manifest_sha256": "0" * 64})
    )
    out.extend(public.check_payload(dto, governed=cat.of(kinds.Copy)))
    for where, value in public.card_texts(card):
        out.extend(public.check_text(where, value, public.PROMISE_GOVERNED_COPY))
    seen = set()
    for config in representative_configurations(cat):
        try:
            resolved = catalog_compile.resolve(cat, config)
            est = engine.calculate(card, resolved.request)
        except (catalog_compile.CompileError, engine.EstimateError):
            continue  # an unsupported combination is refused to customers too; the defaults check covers the rest
        result = json.loads(json.dumps(est.staff_view(), default=str))
        spec_row = estimator_service.active_spec(s, est.package)
        spec = customer_spec_view(spec_row)
        try:
            estimate = public.build_estimate(result, catalog_release="RELEASE", specification=spec, **_PLACEHOLDER)
        except (ValueError, KeyError) as err:
            out.append(f"the estimate payload for {config['home']} / {config['package']} does not build: "
                       f"{str(err).splitlines()[0][:200]}")  # fmt: skip
            continue
        key = estimate.model_dump_json()
        if key in seen:
            continue
        seen.add(key)
        payloads.append(estimate)
        for problem in public.check_payload(estimate):
            out.append(f"estimate {config['home']} / {config['package']}: {problem}")
    out[:] = list(dict.fromkeys(out))
    return public.digest(payloads)


def customer_spec_view(row) -> dict | None:
    from veda.modules.estimator import customer_spec

    return customer_spec.customer_view(row.document) if row is not None else None


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


def _hidden_defaults(cat: catalog_compile.Catalog) -> list[str]:
    """A room's preset (variant or choice) that customers cannot see would make its default configuration
    unpriceable for them: refuse it at validation rather than at the customer."""
    hidden = catalog_compile.hidden_paths(cat)
    out = []
    for key, room in sorted(cat.of(kinds.RoomTemplate).items()):
        for slot in room.included:
            if catalog_compile._variant_hidden(hidden, slot.product, slot.variant):
                out.append(f"room_template {key}: its default {slot.product} variant {slot.variant} is staff-only")
            for gkey, ckey in slot.options.items():
                if catalog_compile._choice_hidden(hidden, slot.product, slot.variant, gkey, ckey):
                    out.append(f"room_template {key}: its preset {slot.product} {gkey}={ckey} is staff-only")
    return out


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
            out.extend(_same_price_choices(cat, key, v))
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


def _consultation_only(cat: catalog_compile.Catalog, pkey: str, vkey: str, gkey: str, ckey: str) -> bool:
    paths = {f"product:{pkey}@{gkey}={ckey}", f"product:{pkey}#{vkey}@{gkey}={ckey}"}
    return any(r.type == "requires_consultation" and r.condition is None and r.subject in paths
               for r in cat.of(kinds.Rule).values())  # fmt: skip


def _same_price_choices(cat: catalog_compile.Catalog, pkey: str, v: kinds.Variant) -> list[str]:
    """Choices that would be priced identically must be declared so (price_neutral), or all but one must be
    consultation-only: an unpriced alternative is never silently priced as another (veneer as laminate, R14)."""
    out = []
    for g in v.option_groups:
        if g.price_neutral:
            continue
        priced: dict[tuple[tuple[str, str], ...], list[str]] = {}
        for c in g.choices:
            if not _consultation_only(cat, pkey, v.key, g.key, c.key):
                priced.setdefault(tuple(sorted(c.engine_options.items())), []).append(c.key)
        for same in priced.values():
            if len(same) > 1:
                out.append(f"product {pkey}#{v.key}@{g.key}: choices {', '.join(same)} price identically; give each "
                           "its own engine option, mark the group price-neutral, or make one consultation-only")  # fmt: skip
    return out


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


MATRIX_SPEC = "ESSENTIAL-1.1"  # the specification whose reviewed promise matrix catalog promises are linked to


def matrix() -> dict | None:
    """The packaged, reviewed customer-promise matrix (never a file supplied at run time)."""
    return promise_matrix.load(MATRIX_SPEC)


def _promises(cat: catalog_compile.Catalog, out: list[str], warnings: list[str]) -> None:
    """A promise is customer-visible only as a copy record that is registered text of a promise-matrix row whose owner,
    backup and verification are named and operationally confirmed, with its own governance confirmed and its products,
    rooms or packages in the release (R2/R3, the M3 rule of the V2 closure). Non-promise copy cannot carry promise
    wording at all (refused when saved)."""
    reviewed = matrix()
    rows = {r["id"]: r for r in (reviewed or {}).get("rows", [])}
    for key, copy in sorted(cat.of(kinds.Copy).items()):
        if not copy.promise:
            continue
        row = rows.get(copy.matrix_row or "")
        if row is None:
            out.append(f"copy {key}: promise is not linked to a row of the {MATRIX_SPEC} promise matrix")
        else:
            if copy.statement not in row.get("statements", []):
                out.append(f"copy {key}: promise is not registered text of matrix row {row['id']}")
            if (
                row.get("status") != promise_matrix.READY
                or not all(promise_matrix._named(row.get(f)) for f in ("accountable_owner", "backup_owner"))
                or not row.get("confirmed_on")
            ):
                out.append(
                    f"copy {key}: matrix row {row['id']} is {row.get('status')} (owner, backup and confirmation needed)"
                )
        g = copy.governance
        if g is None:  # the schema requires it for a promise
            out.append(f"copy {key}: promise has no governance")
            continue
        named = all(promise_matrix._named(x) for x in (g.owner, g.backup, g.verification, g.quotation_mapping,
                                                       g.warranty_source))  # fmt: skip
        if not named:
            out.append(f"copy {key}: promise has an unassigned owner, backup or verification path")
        if g.status != "OPERATIONALLY_CONFIRMED" or g.confirmed_on is None:
            out.append(f"copy {key}: promise is not operationally confirmed")
    specified: list[tuple[str, str, kinds.Material | kinds.Hardware]] = [
        *(("material", k, m) for k, m in cat.of(kinds.Material).items()),
        *(("hardware", k, h) for k, h in cat.of(kinds.Hardware).items()),
    ]
    for kind, key, item in specified:
        if not any(cat.one(kinds.Copy, s) is not None for s in item.statements):
            out.append(f"{kind} {key}: no registered statement")
    for key, package in cat.of(kinds.Package).items():
        badge = cat.one(kinds.Copy, package.badge)
        if package.badge and (badge is None or badge.category != "badge"):
            out.append(f"package {key}: its badge must be a badge copy record in the release")
        if package.warranty_copy is None and not package.consultation_only:
            warnings.append(f"package {key}: no warranty statement")


def _copy(cat: catalog_compile.Catalog, out: list[str], today: date) -> None:
    """The text gate (customer-safety closure). Every customer-visible string in the release is checked by the current
    rules, so a record saved before a rule existed cannot reach a new release. Every claim must be approved, owned,
    sourced, in effect and, when absolute, independently substantiated."""
    for kind, models in sorted(cat.models.items()):
        for key, model in sorted(models.items()):
            out.extend(f"{kind} {key}: {p}" for p in kinds.text_problems(kind, model))
    env = settings().env
    for key, copy in sorted(cat.of(kinds.Copy).items()):
        c = copy.claim
        if c is None:
            continue
        if c.status != "APPROVED":
            out.append(f"copy {key}: claim is {c.status}, not approved")
        if not promise_matrix._named(c.owner):
            out.append(f"copy {key}: claim has no responsible owner")
        if not promise_matrix._named(c.approver):
            out.append(f"copy {key}: claim has no approver")
        absolute = text.absolute_in(copy.statement) or set(c.categories) & {"ranking", "price"}
        if absolute and not promise_matrix._named(c.backup_owner):
            out.append(f"copy {key}: an absolute, ranking or price claim needs a backup owner")
        if c.effective_from > today:
            out.append(f"copy {key}: claim is not in effect until {c.effective_from.isoformat()}")
        if c.review_by is not None and c.review_by < today:
            out.append(f"copy {key}: claim review date {c.review_by.isoformat()} has passed")
        if env not in c.environments:
            out.append(f"copy {key}: claim is not approved for the {env} environment")


def _objects(s: Session, shas: set[str]) -> dict[str, CatalogMediaObject]:
    if not shas:
        return {}
    rows = s.execute(
        sa.select(CatalogMediaObject).where(
            CatalogMediaObject.object_sha256.in_(sorted(shas)), CatalogMediaObject.role == "VARIANT"
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
            elif obj.withdrawn_on is not None or obj.purged_on is not None:
                out.append(f"media {key}: {name} file was withdrawn or purged")
            elif obj.scan_status != "CLEAN":
                out.append(f"media {key}: {name} file is {obj.scan_status}")
        if m.type in kinds.THREE_D_TYPES:
            # R12: 3D is planned but disabled. No release may contain a 3D object until 3D is approved, which needs a
            # reviewed change here; until then this check refuses every one.
            out3d.append(f"media {key}: 3D media is disabled; no release may contain it")
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
