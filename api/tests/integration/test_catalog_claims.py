"""Customer-safety closure, Phase 2: marketing claims are governed in every customer-visible field.

A claim may be made only by a copy record with approved claim governance (category, owner, source, effective period,
and independent substantiation for an absolute claim). Factual fields may make no claim; factual words that merely
contain a claim-like substring are not claims. Synthetic data only."""

import copy

import pytest

from tests.integration.test_catalog import approve_all, seed_slice, tx
from tests.support import claims
from veda.kernel import db
from veda.modules.catalog import importexport, kinds, service

CLAIMS = [
    "Best seller TV unit", "Our premium pick", "Premium pick", "Most popular", "Recommended", "No. 1", "Best quality",
    "Guaranteed lowest price", "Lifetime warranty", "Free installation", "Limited-time offer", "Certified material",
    "Premium quality", "Exclusive", "Luxury choice",
    # aliases
    "No.1 choice", "#1 pick", "Number-one", "Best-selling unit", "Bestseller", "Top rated", "Most-loved", "Editor's pick",
    "Save up to 20", "Customer favourite", "Cheapest in town", "Best-in-class finish", "LIMITED TIME", "recommended for you",
]  # fmt: skip
FACTUAL = ["Premium", "Luxury", "Essential", "Table top shelf", "Countertop unit", "Space-saving drawers",
           "Offers open storage", "Top-hung shutters", "Matte laminate", "Wall panelling", "Top shelf", "Feature wall"]  # fmt: skip

BASE_PRODUCT = {"name": "TV unit", "family": "tv-units", "rooms": ["LIVING"], "default_variant": "va",
                "variants": [{"key": "va", "name": "Panelled", "engine_product": "TV_UNIT", "option_groups": [
                    {"key": "g1", "name": "Finish", "default": "c1", "choices": [{"key": "c1", "name": "Laminate"}]}],
                    "measurements": [{"input": "WIDTH", "label": "Width", "unit": "ft", "min": 1, "max": 9}]}]}  # fmt: skip
MEDIA = {"type": "EXTERNAL_EMBED", "title": "Tour", "alt": "A tour", "embed_url": "https://player.vimeo.com/v/1",
         "rights": {"owner": "Studio", "licence": "x1", "usage": "owned"}}  # fmt: skip


def placements(claim):
    """The claim in every customer-visible field the remediation lists, including nested ones."""

    def product(fn):
        d = copy.deepcopy(BASE_PRODUCT)
        fn(d)
        return ("product", d)

    v = lambda d: d["variants"][0]  # noqa: E731
    return [
        product(lambda d: d.update(name=claim)),
        product(lambda d: d.update(description=claim)),
        product(lambda d: d.update(what_is_this=claim)),
        product(lambda d: v(d).update(name=claim)),
        product(lambda d: v(d).update(description=claim)),
        product(lambda d: v(d)["option_groups"][0].update(name=claim)),
        product(lambda d: v(d)["option_groups"][0].update(description=claim)),
        product(lambda d: v(d)["option_groups"][0]["choices"][0].update(name=claim)),
        product(lambda d: v(d)["option_groups"][0]["choices"][0].update(description=claim)),
        product(lambda d: v(d)["measurements"][0].update(hint=claim)),
        ("extra", {"name": claim, "kind": "room_extra", "add": {"engine_product": "FEATURE_WALL"}}),
        ("extra", {"name": "Feature wall", "kind": "room_extra", "add": {"engine_product": "FEATURE_WALL"}, "description": claim}),
        ("room_template", {"name": claim, "room_code": "LIVING", "included": [{"product": "tv-unit", "variant": "va"}]}),
        ("room_template", {"name": "Living room", "room_code": "LIVING", "description": claim,
                           "included": [{"product": "tv-unit", "variant": "va"}]}),
        ("package", {"name": claim, "engine_package": "ESSENTIAL", "public_summary": "copy.x1"}),
        ("package", {"name": "Essential", "engine_package": "ESSENTIAL", "public_summary": "copy.x1", "description": claim}),
        ("media", {**MEDIA, "caption": claim}),
        ("media", {**MEDIA, "type": "GALLERY", "items": ["img.a1"], "caption": claim}),
        ("media", {**MEDIA, "rights": {**MEDIA["rights"], "owner": claim}}),
        ("copy", {"statement": claim, "category": "badge" if len(claim) <= 30 else "label", "promise": False}),
        ("copy", {"statement": claim, "category": "description", "promise": False}),
    ]  # fmt: skip


@pytest.mark.parametrize("claim", CLAIMS)
def test_a_claim_is_refused_in_every_customer_visible_field(claim):
    for kind, doc in placements(claim):
        with pytest.raises(ValueError):
            kinds.parse(kind, doc)


@pytest.mark.parametrize("words", FACTUAL)
def test_factual_words_are_not_claims(words):
    for kind, doc in placements(words):
        kinds.parse(kind, doc)


def test_3d_labels_are_checked():
    doc = {**MEDIA, "type": "GLB", "objects": {"variants": {"web": "a" * 64}},
           "three_d": {"model_version": "1", "preview_image": "img.p1", "fallback_gallery": "g.f1",
                       "hotspots": [{"key": "h1", "label": "Best finish", "position": [0, 0, 0]}]}}  # fmt: skip
    with pytest.raises(ValueError):
        kinds.parse("media", doc)
    doc["three_d"]["hotspots"] = []
    doc["three_d"]["camera_presets"] = [{"key": "c1", "label": "Our premium pick", "orbit": "0deg 80deg 3m"}]
    with pytest.raises(ValueError):
        kinds.parse("media", doc)


def claim_copy(statement, **over):
    return claims.claim_copy(statement, **over)


def test_a_claim_copy_needs_governance_and_what_it_applies_to():
    with pytest.raises(ValueError, match="claim governance"):
        kinds.parse("copy", {"statement": "Most chosen", "category": "badge", "promise": False})
    doc = claim_copy("Most chosen")
    del doc["applies_to"]
    with pytest.raises(ValueError, match="applies to"):
        kinds.parse("copy", doc)
    kinds.parse("copy", claim_copy("Most chosen"))


@pytest.mark.parametrize("statement", ["Best seller", "No. 1 choice", "Cheapest unit", "Top rated"])
def test_absolute_and_ranking_claims_need_independent_substantiation(statement):
    with pytest.raises(ValueError, match="substantiation"):
        kinds.parse("copy", claim_copy(statement, substantiation=None))
    kinds.parse("copy", claim_copy(statement))


def test_guaranteed_lowest_price_is_never_customer_text():
    with pytest.raises(ValueError, match="pricing wording"):
        kinds.parse("copy", claim_copy("Guaranteed lowest price"))


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


def _release_with_badge(people, doc, code="SLICE-C"):
    a, b = people
    seed_slice(a)
    tx(a, service.create_record, "copy", "copy.badge.claim", doc)
    with db.unit_of_work(write=False) as s:
        row = service.versions(s, "package", "slice.essential")[-1]
        rid, pkg = row.id, copy.deepcopy(row.document)
    pkg["badge"] = "copy.badge.claim"
    tx(a, service.update_draft, rid, pkg)
    approve_all(a, b)
    rel = tx(a, service.create_release, code)
    return a, b, rel, tx(a, service.validate_release, rel.id)


@pytest.mark.parametrize(
    "doc,problem",
    [
        (claim_copy("Most chosen", status="BLOCKED"), "not approved"),
        (claim_copy("Most chosen", owner="UNASSIGNED"), "no responsible owner"),
        (claim_copy("Most chosen", effective_from="2025-06-01", review_by="2026-01-01"), "review date"),
    ],
)
def test_unsupported_claims_block_release(people, doc, problem):
    _a, _b, _rel, report = _release_with_badge(people, doc)
    assert not report["ok"] and report["checks"]["copy"] == "fail"
    assert any(problem in e for e in report["errors"]), report["errors"]


def test_an_approved_claim_releases(people):
    a, b, rel, report = _release_with_badge(people, claim_copy("Most chosen"))
    assert report["ok"], report["errors"]


def test_a_record_saved_before_the_rule_cannot_reach_a_new_release(people):
    """Text written around authoring (for example under an older rule) is refused by the release gate."""
    a, b = people
    seed_slice(a)
    import sqlalchemy as sa

    from veda.kernel.context import actor, system_context
    from veda.modules.catalog.models import CatalogRecord

    approve_all(a, b)  # authored and approved under the rules (submission re-checks text too)
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        row = service.versions(s, "product", "tv-unit")[-1]
        doc = {**row.document, "description": "Our premium pick for the TV wall"}
        s.execute(sa.update(CatalogRecord).where(CatalogRecord.id == row.id).values(document=doc,
                                                                                     document_sha256=service.sha(doc)))  # fmt: skip
    rel = tx(a, service.create_release, "SLICE-OLD")
    report = tx(a, service.validate_release, rel.id)
    assert any("quality claim" in e or "recommendation claim" in e for e in report["errors"]), report["errors"]


def test_import_refuses_claims(people):
    a, _ = people
    rows = [importexport.ImportRow("product_family", "beds", {"name": "Best beds", "category": "beds"}),
            importexport.ImportRow("copy", "copy.c1", {"statement": "Most popular", "category": "badge", "promise": False})]  # fmt: skip
    with db.unit_of_work(write=False) as s:
        report = importexport.dry_run(s, rows, can_edit=lambda kind: True)
    assert not report["ok"] and all(r["errors"] for r in report["rows"])
