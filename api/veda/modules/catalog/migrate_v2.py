"""V2 → catalog migration (idempotent; V2 stays authoritative).

Inputs: a V2 rate card document (the operator supplies it; it is never committed), the V2 room bundles
(`v2_bundles.json`, extracted from estimate-v2.js and kept in step by a test) and the V2 customer copy
(estimate-v2-copy.js). Output: DRAFT catalog records. Nothing is approved, released or activated, so V1 and V2 are
unchanged. Running it again creates nothing new unless an input changed (then a new DRAFT version, never an edit of
reviewed content).

Equivalence (ADR-013 D1): the migrated pricing compiles back to the V2 card (canonical JSON, version aside), and the
migrated rooms resolve to exactly the selections the V2 page sends for the same choices.
"""

from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.modules.estimator import activation, ratecard

from . import service
from .models import CatalogRecord

BUNDLES_FILE = Path(__file__).resolve().parent / "v2_bundles.json"
UNASSIGNED = "UNASSIGNED"
_PACKAGE_LABEL = {"ESSENTIAL": "Essential", "PREMIUM": "Premium", "LUXURY": "Luxury"}


def bundles() -> dict:
    return json.loads(BUNDLES_FILE.read_text())


def _key(text: str) -> str:
    return text.lower().replace("_", "-")


def _blocked_governance(note: str) -> dict:
    # Owners are never invented: a migrated promise stays BLOCKED until the business assigns and confirms it.
    return {"owner": UNASSIGNED, "backup": UNASSIGNED, "quotation_mapping": note, "verification": UNASSIGNED,
            "warranty_source": UNASSIGNED, "status": "BLOCKED"}  # fmt: skip


def records(card_document: dict, bundle: dict | None = None, copy: dict | None = None, home_size: str = "3BHK"):
    """The catalog records for a V2 card and bundle, as (kind, key, document), in dependency order."""
    card = ratecard.parse(card_document)
    bundle = bundle or bundles()
    copy = copy or activation.customer_copy() or {"promise": {"items": {}}, "ui": {"rooms": {}, "refine": {}}}
    labels, room_labels = copy["promise"].get("items", {}), copy["ui"].get("rooms", {})
    out: list[tuple[str, str, dict]] = []

    # Pricing: the card, split into its settings and one record per engine product (order kept by position).
    settings_body = {k: v for k, v in card_document.items() if k != "products" and k in _settings_fields()}
    out.append(("pricing", "card-settings", {"scope": "settings", "body": settings_body, "note": "Migrated from V2"}))
    for i, product in enumerate(card_document["products"]):
        out.append(("pricing", f"engine.{_key(product['code'])}", {
            "scope": "product", "engine_product": product["code"], "body": product, "position": (i + 1) * 10,
        }))  # fmt: skip

    # Homes, packages and their copy.
    for ptype in card.available_property_types():
        out.append(("property_type", _key(ptype), {"name": ptype.title(), "code": ptype}))
    for code in ratecard.PACKAGES:
        priced = card.packages[code] and code != "LUXURY"
        summary = f"package.{_key(code)}.summary"
        if code == "ESSENTIAL" and copy["promise"].get("packageSubtitle"):
            out.append(("copy", summary, {
                "statement": copy["promise"]["packageSubtitle"], "category": "package", "promise": True,
                "governance": _blocked_governance("V2 package subtitle (promise matrix)"),
                "matrix_row": "package-subtitle",
            }))  # fmt: skip
        else:
            text = (
                f"{_PACKAGE_LABEL[code]} package"
                if priced
                else f"{_PACKAGE_LABEL[code]}: discussed in a design consultation"
            )
            out.append(("copy", summary, {"statement": text, "category": "label", "promise": False}))
        out.append(("package", _key(code), {
            "name": _PACKAGE_LABEL[code], "engine_package": code, "public_summary": summary,
            "consultation_only": not priced, "recommended": code == "ESSENTIAL",
        }))  # fmt: skip
    out.append(("product_family", "v2", {"name": "Migrated V2 items", "category": "v2"}))

    items, refine = bundle["items"], bundle["refine"]
    prompts: dict[str, list[dict]] = {}
    for f in refine:
        spec = _priced(card, items[f["item"]]["product"])
        inp = next(i for i in spec.inputs if i.name == f["input"])
        prompts.setdefault(f["item"], []).append({
            "input": f["input"], "label": f"{_label(labels, f['item'])}: {inp.label.lower()}", "unit": f["unit"],
            "min": f["min"], "max": f["max"],
        })  # fmt: skip
    rooms = bundle["rooms_by_size"][home_size]
    included_ids = {i for r in rooms for i in r["includes"]}
    for item_id in sorted(included_ids):
        item = items[item_id]
        spec = _priced(card, item["product"])
        variant: dict[str, object] = {"key": "standard", "name": _label(labels, item_id), "engine_product": item["product"],
                   "engine_options": item["options"], "measurements": prompts.get(item_id, [])}  # fmt: skip
        if item_id == "pooja":
            variant["option_groups"] = [{"key": "asta", "name": _label(labels, "asta"), "default": "no", "choices": [
                {"key": "no", "name": "Without"}, {"key": "yes", "name": "With", "engine_options": {"ASTA_CHAKRA": "YES"}},
            ]}]  # fmt: skip
        out.append(("product", item_id.replace("_", "-"), {
            "name": _label(labels, item_id), "family": "v2", "variants": [variant], "default_variant": "standard",
            "rooms": sorted({r["room"] for r in rooms if item_id in r["includes"]} & set(spec.rooms)),
            "packages": [p for p in ratecard.PACKAGES if card.packages[p] and p != "LUXURY"],
        }))  # fmt: skip
    extra_ids = {(r["id"], x["id"]): x for r in rooms for x in r["extras"]}
    seen_extras: set[str] = set()
    for (_room_id, extra_id), x in sorted(extra_ids.items()):
        key = extra_id.replace("_", "-")
        if key in seen_extras:
            continue
        seen_extras.add(key)
        item = items[extra_id]
        doc: dict[str, object] = {"name": _label(labels, extra_id), "kind": "room_extra",
               "rooms": sorted({f"v2.{r['id']}" for r in rooms if any(e['id'] == extra_id for e in r['extras'])})}  # fmt: skip
        if item["product"] is None:  # the asta chakra: an option of the pooja unit
            doc["set_option"] = {"product": "pooja", "group": "asta", "choice": "yes"}
            doc["kind"] = "product_extra"
        else:
            doc["add"] = {"engine_product": item["product"], "engine_options": item["options"]}
        if x["count"]:
            doc.update(quantity="count", max_count=x["count"])
        out.append(("extra", key, doc))
    for r in rooms:
        out.append(("room_template", f"v2.{r['id']}", {
            "name": room_labels.get(r["id"], r["id"].title()), "room_code": r["room"],
            "included": [{"product": i.replace("_", "-"), "variant": "standard"} for i in r["includes"]],
            "extras": [x["id"].replace("_", "-") for x in r["extras"]],
        }))  # fmt: skip
    out.append(("home_config", f"{_key(card.available_property_types()[0])}.{home_size.lower()}", {
        "name": f"{home_size[:-3]} BHK {card.available_property_types()[0].title()}",
        "property_type": _key(card.available_property_types()[0]), "home_size": home_size,
        "rooms": [{"room_template": f"v2.{r['id']}"} for r in rooms],
        "packages": [_key(p) for p in ratecard.PACKAGES],
    }))  # fmt: skip
    return out


class MigrationError(ValueError):
    """The V2 inputs do not fit together (a bundle item the card does not price)."""


def _priced(card: ratecard.RateCard, code: str) -> ratecard.ProductSpec:
    spec = card.product(code)
    if spec is None:
        raise MigrationError(f"the V2 bundles use {code}, which the card does not price")
    return spec


def _label(labels: dict, item_id: str) -> str:
    return labels.get(item_id) or item_id.replace("_", " ").capitalize()


def _settings_fields():
    from .kinds import SETTINGS_FIELDS

    return SETTINGS_FIELDS


def apply(
    s: Session, card_document: dict, bundle: dict | None = None, copy: dict | None = None, *, dry_run: bool = False
) -> dict[str, list[str]]:
    """Create a DRAFT for every record that is new or changed; report the rest. Idempotent."""
    report: dict[str, list[str]] = {"created": [], "unchanged": [], "draft_pending": []}
    for kind, key, document in records(card_document, bundle, copy):
        existing = (
            s.execute(
                sa.select(CatalogRecord)
                .where(CatalogRecord.kind == kind, CatalogRecord.record_key == key, CatalogRecord.is_deleted.is_(False))
                .order_by(CatalogRecord.record_version.desc())
            )
            .scalars()
            .first()
        )
        if existing is not None and existing.document_sha256 == service.sha(document):
            report["unchanged"].append(f"{kind}:{key}")
            continue
        if existing is not None and existing.status == "DRAFT":
            report["draft_pending"].append(f"{kind}:{key}")
            continue
        if not dry_run:
            service.create_record(s, kind, key, document)
        report["created"].append(f"{kind}:{key}")
    return report
