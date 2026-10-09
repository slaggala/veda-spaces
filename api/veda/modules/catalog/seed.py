"""The representative vertical slice (owner instruction): Living Room → TV Unit, synthetic and DRAFT only.

- Room: living room, with a representative image and a gallery.
- Product: TV unit, two variants (wall-panelled; box) mapped to the engine's TV_UNIT styles.
- Options: laminate or veneer panelling (materials), soft-close storage on the box variant (hardware).
- Extras: a feature wall (adds the engine's FEATURE_WALL, measured) and soft-close storage (sets the box option).
- Media: generated placeholder images labelled "Illustrative example", a gallery, an optional 3D model (a generated
  GLB) with a preview image first and the gallery as its fallback. The model never prices anything.
- Rules: soft-close storage requires the box variant; TV wall width online is 3–20 ft.
- Copy: descriptive statements (no promise words). The soft-close statement is a promise: its owner is UNASSIGNED
  and it is BLOCKED, so no release containing it can activate until the business assigns and confirms it. No person
  is named anywhere.

Pricing is not seeded: a release compiles only with pricing records, which come from a card (`migrate_v2`) supplied
by the operator; tests use the synthetic card. The images are drawn here, so no third-party or customer image is used.
"""

from __future__ import annotations

import io
import json
import struct

import sqlalchemy as sa
from sqlalchemy.orm import Session

from . import media, service
from .models import CatalogRecord

PLACEHOLDER = "Illustrative example"
RIGHTS = {"owner": "Veda Spaces", "licence": "Generated placeholder (synthetic)", "usage": "owned"}
UNASSIGNED = "UNASSIGNED"


def _image(title: str, colour: tuple[int, int, int], accent: tuple[int, int, int]) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1600, 1000), colour)
    d = ImageDraw.Draw(img)
    d.rectangle((420, 520, 1180, 760), fill=accent)  # a unit
    d.rectangle((560, 230, 1040, 500), outline=(30, 30, 30), width=8)  # a screen
    d.text((60, 60), f"{title} - {PLACEHOLDER}", fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _glb() -> bytes:
    """A minimal valid binary glTF 2.0: one triangle, one material, no external references."""
    positions = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    doc = {
        "asset": {"version": "2.0", "generator": "veda-catalog-seed"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "Panel"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "material": 0}]}],
        "materials": [{"name": "Laminate"}],
        "buffers": [{"byteLength": len(positions)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(positions)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0, 0, 0],
                       "max": [1, 1, 0]}],
    }  # fmt: skip
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    bin_ = positions + b"\0" * (-len(positions) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bin_
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


def _media_records(s: Session) -> list[tuple[str, str, dict]]:
    out = []

    def image(key, title, alt, colour, accent, **extra):
        up = media.upload(s, _image(title, colour, accent))
        out.append(("media", key, {"type": "IMAGE", "title": title, "alt": alt, "label": PLACEHOLDER,
                                   "rights": RIGHTS, "objects": {"variants": up.objects()["variants"],
                                                                 "source": up.objects()["source"]}, **extra}))  # fmt: skip

    image("img.living-room", "Living room", "A living room with a TV unit on the main wall", (232, 226, 214),
          (150, 120, 90), rooms=["LIVING"])  # fmt: skip
    image("img.tv-laminate", "TV unit, laminate panelling", "A TV unit with matte laminate wall panelling",
          (236, 233, 228), (120, 110, 100), products=["tv-unit"], materials=["laminate.matte"])  # fmt: skip
    image("img.tv-veneer", "TV unit, veneer panelling", "A TV unit with natural wood veneer wall panelling",
          (236, 230, 220), (140, 95, 60), products=["tv-unit"], materials=["veneer.natural"])  # fmt: skip
    image("img.feature-wall", "Feature wall", "A panelled feature wall behind a TV unit", (226, 222, 214),
          (110, 90, 80))  # fmt: skip
    image("img.soft-close", "Storage drawers", "Closed storage drawers below a TV unit", (230, 230, 230),
          (90, 90, 90))  # fmt: skip
    image("img.tv-preview", "TV unit, 3D preview", "A still preview of the TV unit model", (240, 240, 236),
          (130, 110, 95), products=["tv-unit"])  # fmt: skip
    out.append(("media", "gallery.tv-unit", {
        "type": "GALLERY", "title": "TV unit ideas", "label": PLACEHOLDER, "rights": RIGHTS,
        "items": ["img.tv-laminate", "img.tv-veneer", "img.feature-wall"], "products": ["tv-unit"],
    }))  # fmt: skip
    out.append(("media", "gallery.living-room", {
        "type": "GALLERY", "title": "Living room ideas", "label": PLACEHOLDER, "rights": RIGHTS,
        "items": ["img.living-room", "img.tv-laminate", "img.feature-wall"], "rooms": ["LIVING"],
    }))  # fmt: skip
    model = media.upload(s, _glb())
    out.append(("media", "model.tv-unit", {
        "type": "GLB", "title": "TV unit, 3D view", "alt": "An interactive 3D view of the TV unit",
        "label": PLACEHOLDER, "rights": RIGHTS, "objects": model.objects(), "products": ["tv-unit"],
        "three_d": {
            "model_version": "1", "preview_image": "img.tv-preview", "fallback_gallery": "gallery.tv-unit",
            "dimensions_mm": {"w": 2400, "h": 2100, "d": 450},
            "variant_map": {"panelled": "node:Panel"},
            "finish_map": {"laminate.matte": "material:Laminate", "veneer.natural": "material:Veneer"},
            "hotspots": [{"key": "panel", "label": "Wall panelling", "position": [0.5, 0.6, 0.0]}],
            "camera_presets": [{"key": "front", "label": "Front", "orbit": "0deg 80deg 3m"}],
        },
    }))  # fmt: skip
    return out


def records(s: Session) -> list[tuple[str, str, dict]]:
    copy = [
        ("copy.laminate", "A decorative laminate surface bonded to the panel, in a matte finish.", "material"),
        ("copy.veneer", "A thin layer of natural wood on the panel, so the grain varies from piece to piece.", "material"),
        ("copy.slice.essential", "Essential package", "label"),
        ("copy.rule.tv-width", "Online estimates cover TV walls from 3 to 20 feet wide.", "assumption"),
        ("copy.rule.soft-close", "Storage drawers are offered with the box TV unit.", "assumption"),
        ("copy.disclaimer", "This is a preliminary budgetary estimate for planning purposes and is not a final quotation "
         "or contractual offer.", "disclaimer"),
        ("copy.next-step", "Measurements can be added later; our team confirms them at a site visit.", "next_step"),
    ]  # fmt: skip
    out: list[tuple[str, str, dict]] = [
        ("copy", key, {"statement": text, "category": cat, "promise": False}) for key, text, cat in copy
    ]
    out.append(("copy", "copy.soft-close.promise", {
        "statement": "Soft-close hinges and channels on storage shutters and drawers.", "category": "hardware",
        "promise": True,
        "governance": {"owner": UNASSIGNED, "backup": UNASSIGNED, "quotation_mapping": "Hardware line of the quotation",
                       "verification": UNASSIGNED, "warranty_source": UNASSIGNED, "status": "BLOCKED"},
    }))  # fmt: skip
    out += [
        ("material", "laminate.matte", {
            "name": "Matte laminate", "category": "laminate", "finish": "Matte", "thickness": ["1 mm"],
            "colour_family": "Neutral", "texture": "Smooth", "rooms": ["LIVING"], "products": ["tv-unit"],
            "statements": ["copy.laminate"], "warranty_source": "Not shown to customers in this slice",
        }),
        ("material", "veneer.natural", {
            "name": "Natural wood veneer", "category": "veneer", "finish": "Natural", "texture": "Wood grain",
            "rooms": ["LIVING"], "products": ["tv-unit"], "statements": ["copy.veneer"],
            "warranty_source": "Not shown to customers in this slice",
        }),
        ("hardware", "hinge.soft-close", {
            "name": "Soft-close hinges and channels", "category": "hinge", "soft_close": True,
            "compatible_families": ["tv-units"], "statements": ["copy.soft-close.promise"],
            "warranty_source": UNASSIGNED,
        }),
    ]  # fmt: skip
    out += _media_records(s)
    out += [
        ("property_type", "apartment", {"name": "Apartment", "code": "APARTMENT"}),
        ("product_family", "tv-units", {"name": "TV units", "category": "media_units"}),
        ("product", "tv-unit", {
            "name": "TV unit", "family": "tv-units", "rooms": ["LIVING"], "packages": ["ESSENTIAL"],
            "description": "A unit for the TV wall, with panelling or a simple box and optional storage.",
            "what_is_this": "The cabinet and wall finish around your TV.",
            "media": ["img.tv-laminate", "gallery.tv-unit", "model.tv-unit"], "default_variant": "panelled",
            "variants": [
                {"key": "panelled", "name": "With wall panelling", "engine_product": "TV_UNIT",
                 "engine_options": {"STYLE": "PANELLED"}, "media": ["img.tv-laminate"],
                 "measurements": [{"input": "WIDTH", "label": "TV wall width", "unit": "ft", "min": 3, "max": 20,
                                   "hint": "Measure the wall the TV unit sits on, end to end."}],
                 "option_groups": [{"key": "panel-finish", "name": "Panelling finish", "default": "laminate",
                                    "choices": [
                                        {"key": "laminate", "name": "Laminate", "materials": ["laminate.matte"],
                                         "media": ["img.tv-laminate"]},
                                        {"key": "veneer", "name": "Veneer", "materials": ["veneer.natural"],
                                         "media": ["img.tv-veneer"]},
                                    ]}]},
                {"key": "box", "name": "Box unit", "engine_product": "TV_UNIT", "engine_options": {"STYLE": "BOX"},
                 "measurements": [{"input": "WIDTH", "label": "TV wall width", "unit": "ft", "min": 3, "max": 20}],
                 "option_groups": [{"key": "storage", "name": "Storage", "default": "open",
                                    "choices": [
                                        {"key": "open", "name": "Open shelves"},
                                        {"key": "soft-close", "name": "Soft-close storage drawers",
                                         "engine_options": {"STYLE": "BOX_STORAGE"}, "hardware": ["hinge.soft-close"],
                                         "media": ["img.soft-close"]},
                                    ]}]},
            ],
        }),
        ("extra", "feature-wall", {
            "name": "Feature wall", "kind": "room_extra", "quantity": "measured", "rooms": ["living-room"],
            "what_is_this": "A wall finished in panels to frame the TV unit and the seating.",
            "typically_used_for": "The TV wall or the wall behind the sofa.",
            "add": {"engine_product": "FEATURE_WALL", "engine_options": {"FINISH": "PANELLING"}},
            "measurements": [{"input": "WIDTH", "label": "Feature wall width", "unit": "ft", "min": 3, "max": 30}],
            "media": ["img.feature-wall"],
        }),
        ("extra", "tv-soft-close-storage", {
            "name": "Soft-close storage", "kind": "product_extra", "rooms": ["living-room"], "products": ["tv-unit"],
            "what_is_this": "Closed drawers below the TV unit that shut gently.",
            "set_option": {"product": "tv-unit", "group": "storage", "choice": "soft-close"},
            "hardware": ["hinge.soft-close"], "media": ["img.soft-close"],
        }),
        ("room_template", "living-room", {
            "name": "Living room", "room_code": "LIVING", "image": "img.living-room", "gallery": "gallery.living-room",
            "description": "The TV wall and the space around your seating.",
            "included": [{"product": "tv-unit", "variant": "panelled", "options": {"panel-finish": "laminate"}}],
            "extras": ["feature-wall", "tv-soft-close-storage"],
        }),
        ("package", "slice.essential", {
            "name": "Essential", "engine_package": "ESSENTIAL", "public_summary": "copy.slice.essential",
            "included_products": ["tv-unit"], "recommended": True,
        }),
        ("home_config", "slice.apartment-3bhk", {
            "name": "3 BHK Apartment (living room slice)", "property_type": "apartment", "home_size": "3BHK",
            "rooms": [{"room_template": "living-room"}], "packages": ["slice.essential"],
        }),
        ("rule", "rule.soft-close-needs-box", {
            "type": "requires", "subject": "extra:tv-soft-close-storage", "objects": ["product:tv-unit#box"],
            "message": "copy.rule.soft-close",
        }),
        ("rule", "rule.tv-width", {
            "type": "measurement_bounds", "subject": "product:tv-unit", "input": "WIDTH", "min": 3, "max": 20,
            "message": "copy.rule.tv-width",
        }),
    ]  # fmt: skip
    return out


def apply(s: Session) -> dict:
    """Create the slice as DRAFTs (idempotent: unchanged records are skipped)."""
    created, unchanged = [], []
    for kind, key, document in records(s):
        latest = (
            s.execute(
                sa.select(CatalogRecord)
                .where(CatalogRecord.kind == kind, CatalogRecord.record_key == key, CatalogRecord.is_deleted.is_(False))
                .order_by(CatalogRecord.record_version.desc())
            )
            .scalars()
            .first()
        )
        if latest is not None and latest.document_sha256 == service.sha(document):
            unchanged.append(f"{kind}:{key}")
            continue
        if latest is not None and latest.status == "DRAFT":
            service.update_draft(s, latest.id, document)
        else:
            service.create_record(s, kind, key, document)
        created.append(f"{kind}:{key}")
    return {"created": len(created), "unchanged": len(unchanged)}
