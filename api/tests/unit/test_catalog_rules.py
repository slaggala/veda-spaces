"""ADR-013 D8: catalog rules are data, evaluated server-side; unsupported combinations are refused."""

from types import SimpleNamespace

import pytest

from veda.modules.catalog import compile as catalog_compile
from veda.modules.catalog import kinds, rules
from veda.modules.catalog.permissions import MATRIX, PERMISSIONS, edit_permission

CTX = rules.Context(property_type="APARTMENT", home_size="3BHK", project_kind="NEW_HOME", package="ESSENTIAL",
                    market="Hyderabad")  # fmt: skip


def catalog(*records):
    rows = [SimpleNamespace(kind=k, record_key=key, record_version=1, document=d) for k, key, d in records]
    return catalog_compile.load(rows, "T", "0" * 64)


def rule(key, **doc):
    return ("rule", key, doc)


PRODUCT = ("product", "tv", {"name": "TV unit", "family": "f1", "rooms": ["LIVING"], "default_variant": "va",
                             "variants": [{"key": "va", "name": "A", "engine_product": "TV_UNIT"}]})  # fmt: skip


@pytest.mark.parametrize(
    "doc,active,code",
    [
        ({"type": "requires", "subject": "extra:x1", "objects": ["product:tv#vb"]}, {"extra:x1"}, "REQUIRES"),
        ({"type": "excludes", "subject": "extra:x1", "objects": ["extra:x2"]}, {"extra:x1", "extra:x2"}, "EXCLUDES"),
        ({"type": "compatible_with", "subject": "extra:x1", "objects": ["product:tv#vb"]}, {"extra:x1", "product:tv#va"},
         "INCOMPATIBLE"),
        ({"type": "available_only_for", "subject": "extra:x1", "condition": {"home_sizes": ["2BHK"]}}, {"extra:x1"},
         "UNAVAILABLE"),
        ({"type": "hidden_when", "subject": "extra:x1", "condition": {"markets": ["hyderabad"]}}, {"extra:x1"},
         "UNAVAILABLE"),
        ({"type": "requires_consultation", "subject": "extra:x1"}, {"extra:x1"}, "CONSULTATION_REQUIRED"),
        ({"type": "unavailable_online", "subject": "extra:x1"}, {"extra:x1"}, "UNAVAILABLE_ONLINE"),
        ({"type": "staff_only", "subject": "extra:x1"}, {"extra:x1"}, "UNAVAILABLE"),
    ],
)  # fmt: skip
def test_each_rule_type_refuses(doc, active, code):
    extras = [("extra", k, {"name": k.upper(), "kind": "room_extra", "add": {"engine_product": "TV_UNIT"}})
              for k in ("x1", "x2")]  # fmt: skip
    cat = catalog(PRODUCT, *extras, rule("r1", **doc))
    assert code in {e["code"] for e in rules.evaluate(cat, CTX, {"product:tv", *active}, {})}


def test_rules_do_not_fire_when_not_selected_and_staff_may_price_online_only_items():
    cat = catalog(PRODUCT, rule("r1", type="unavailable_online", subject="product:tv"),
                  rule("r2", type="requires", subject="extra:x9", objects=["product:tv#vb"]))  # fmt: skip
    assert rules.evaluate(cat, rules.Context(**{**CTX.__dict__, "public": False}), {"product:tv"}, {}) == []


def test_measurement_bounds_and_default_when():
    cat = catalog(PRODUCT, rule("r1", type="measurement_bounds", subject="product:tv", input="WIDTH", min=3, max=20),
                  rule("r2", type="default_when", subject="product:tv", condition={"home_sizes": ["3BHK"]}))  # fmt: skip
    assert [e["code"] for e in rules.evaluate(cat, CTX, {"product:tv"}, {"product:tv": {"WIDTH": 25}})] == [
        "OUT_OF_RANGE"
    ]
    assert rules.evaluate(cat, CTX, {"product:tv"}, {"product:tv": {"WIDTH": 12}}) == []
    assert rules.defaults(cat, CTX) == {"product:tv"}


def test_availability_is_an_implicit_rule():
    doc = {**PRODUCT[2], "availability": {"home_sizes": ["2BHK"]}}
    cat = catalog(("product", "tv", doc))
    assert [e["code"] for e in rules.evaluate(cat, CTX, {"product:tv"}, {})] == ["UNAVAILABLE"]


def test_contradictory_rules_are_found():
    cat = catalog(
        PRODUCT,
        rule("r1", type="requires", subject="extra:a1", objects=["extra:b1"]),
        rule("r2", type="excludes", subject="extra:a1", objects=["extra:b1"]),
        rule("r3", type="requires", subject="extra:c1", objects=["extra:d1", "extra:e1"]),
        rule("r4", type="excludes", subject="extra:d1", objects=["extra:e1"]),
        rule("r5", type="requires", subject="extra:f1", objects=["extra:f1"]),
    )
    found = rules.contradictions(cat)
    assert any("both requires and excludes" in f for f in found)
    assert any("exclude each other" in f for f in found)
    assert any("own subject" in f for f in found)


def test_three_d_needs_a_preview_and_a_fallback_and_never_prices():
    base = {"type": "GLB", "title": "TV 3D", "alt": "A 3D view", "rights": {"owner": "x1", "licence": "x1",
            "usage": "owned"}, "objects": {"variants": {"web": "a" * 64}}}  # fmt: skip
    with pytest.raises(ValueError, match="3D description"):
        kinds.parse("media", base)
    model = kinds.parse("media", {**base, "three_d": {"model_version": "1", "preview_image": "img.p",
                                                      "fallback_gallery": "gal.f"}})  # fmt: skip
    assert ("media", "img.p") in kinds.references("media", model)
    assert "engine" not in json_keys(model.model_dump()), "no price input lives in a 3D description"


def json_keys(o):
    if isinstance(o, dict):
        return set(o) | set().union(*(json_keys(v) for v in o.values()))
    if isinstance(o, list | tuple):
        return set().union(*(json_keys(v) for v in o)) if o else set()
    return set()


def test_permissions_are_least_privilege():
    codes = {p.code for p in PERMISSIONS}
    assert codes == set(MATRIX)
    assert {c for c, roles in MATRIX.items() if "ADMIN" in roles} == {"catalog.view"}
    assert not any("SALES" in roles for roles in MATRIX.values())
    sensitive = {p.code for p in PERMISSIONS if p.sensitivity_class}
    assert {"catalog.pricing.view", "catalog.pricing.edit", "catalog.approve", "catalog.admin"} <= sensitive
    assert edit_permission("pricing") == "catalog.pricing.edit" and edit_permission("media") == "catalog.media.edit"
    assert edit_permission("copy") == "catalog.spec.edit" and edit_permission("product") == "catalog.edit"
