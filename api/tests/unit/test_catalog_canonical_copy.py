"""Canonical customer-copy closure: one canonical form for every customer-visible V3 string.

- Phase 2: the public DTOs are strict and bounded, with no weak type.
- Phase 3: normalisation defeats invisible, fullwidth, lookalike and separator variants.
- Phase 4: marketing claims are detected on the canonical form without substring false positives.
- Phase 5: claim records are complete and consistent.
- Phase 6: rates and prices never leak.
- Phase 12: the reviewer's reproduced bypasses stay closed.

Synthetic text only; no rate from any real card."""

import types
import typing

import annotated_types
import pytest
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

from tests.support import claims
from veda.modules.catalog import kinds, public, text

ZW = "​"

# --- Phase 4: the required claim list, each in its governance route ---------------------------------------------------
MARKETING = {
    "ranking": ["No. 1", "Number 1", "Number one", "First choice", "Top rated", "Leading", "Best", "Finest"],
    "quality": ["Highest quality", "Premium quality"],
    "price": ["Cheapest", "Lowest price", "Guaranteed lowest price"],
    "popularity": ["Best seller", "Bestseller", "Most popular", "Customer favourite", "Top choice"],
    "recommendation": ["Premium pick", "Luxury choice", "Recommended"],
    "promotional": [
        "Free",
        "Free installation",
        "Limited-time offer",
        "Offer ends soon",
        "20% off",
        "Flat 10 percent discount",
    ],  # fmt: skip
}
PROMISES = ["Lifetime warranty", "Guaranteed", "Certified", "Maintenance free", "Waterproof", "Termite proof",
            "Scratch proof", "Guaranteed delivery", "Guaranteed on-time delivery", "One-day callback", "Free service",
            "Free consultation"]  # fmt: skip
FACTUAL = ["Premium", "Luxury", "Essential", "Countertop unit", "Space-saving drawers", "Top-hung shutters",
           "Free-standing unit", "Hands-free tap", "Leading edge trim", "Best-fit hinge", "Width 12 ft", "3 BHK",
           "2 drawers", "1 unit", "Bestow", "Freedom", "Topology", "Offering", "Leadlight panel", "Matte laminate",
           "Proofed edges"]  # fmt: skip


@pytest.mark.parametrize("category,phrase", [(c, p) for c, ps in MARKETING.items() for p in ps])
def test_every_listed_marketing_claim_is_detected(category, phrase):
    assert category in text.marketing_claims_in(phrase), (phrase, text.claims_in(phrase))


@pytest.mark.parametrize("phrase", PROMISES)
def test_warranty_quality_and_service_wording_is_promise_governed(phrase):
    assert text.promise_in(phrase), phrase


@pytest.mark.parametrize("phrase", FACTUAL)
def test_factual_words_are_not_claims(phrase):
    assert text.claims_in(phrase) == [] and not text.promise_in(phrase) and text.forbidden_in(phrase) is None


# --- Phase 3 / 12: canonical normalisation and the reproduced bypasses -------------------------------------------------
BYPASSES = [
    f"B{ZW}est seller", "Ｂｅｓｔ ｓｅｌｌｅｒ", "Bеst seller", "best_seller", "best–seller", "best—seller", "B.E.S.T seller",
    "b e s t seller", "Best seller", "Best️ seller", "Be­st seller", "﻿Best seller", "Best!!! seller",
    "Best⁠seller", "Best‍seller", "Best‌seller", "Best‮seller", "BEST/SELLER", "best\\seller",
    "best:seller", "best|seller", "Тop rated", "ＦＲＥＥ installation", "Most—popular", "Recommended‌", "No.1", "#1",
]  # fmt: skip


@pytest.mark.parametrize("variant", BYPASSES)
def test_reproduced_bypasses_are_detected(variant):
    assert text.marketing_claims_in(variant), variant


@pytest.mark.parametrize("variant", [f"B{ZW}est", "Be­st", "﻿Best", "Best️", "Best‮", "Best⁠"])
def test_invisible_and_format_characters_are_reported(variant):
    assert text.invisible_chars(variant)
    with pytest.raises(ValueError, match="invisible"):
        kinds.parse("product_family", {"name": variant.replace("Best", "TV units"), "category": "media_units"})


def test_canonical_form_is_stable_and_separate_from_display_text():
    variants = ["Best seller", "BEST_SELLER", "Ｂｅｓｔ ｓｅｌｌｅｒ", f"B{ZW}est–seller"]
    assert {text.canonical(v) for v in variants} == {"best seller"}
    assert len({text.canonical_digest(v) for v in variants}) == 1
    assert len({text.display_digest(v) for v in variants}) == len(variants), "the display text is kept distinct"
    for v in variants:
        assert text.canonical(text.canonical(v)) == text.canonical(v)


# --- Phase 6: rates and prices -------------------------------------------------------------------------------------
RATES = ["₹1200", "₹ 1200", "Rs 1200", "Rs.1200", "Rs1200", "INR 1200", "rupees 1200", "12 lakh", "1200/-", "1,200",
         "1,20,000", "1200 per sqft", "1200/sqft", "1200 per sq ft", "12k per sqft", "12K/sft", "1200 psf", "₹1200 rft",
         "1200 per running foot", "1200 per rft", "１２００/sqft", "1200 ⁄ sqft", f"1{ZW}200 per sqft", "1200 per unit",
         "1200/pc", "20% off", "10 percent off", "Flat 10 per cent discount", "price ceiling", "supplier price",
         "procurement cost", "our margin", "dealer price", "MRP 4000"]  # fmt: skip
NOT_RATES = ["Width 12 ft", "Up to 45 days", "Typically 8 to 10 weeks", "3 BHK", "2 drawers", "18 mm board",
             "Ceiling height 10 ft", "1 unit"]  # fmt: skip


@pytest.mark.parametrize("value", RATES)
def test_rates_and_prices_are_refused_everywhere(value):
    assert text.forbidden_in(value), value
    assert text.leak_in(value), value  # even in promise-governed estimator and card text
    for cls in (public.FACTUAL_CUSTOMER_COPY, public.PROMISE_GOVERNED_COPY):
        assert public.check_text("x", value, cls), (value, cls)


@pytest.mark.parametrize("value", NOT_RATES)
def test_sizes_counts_and_timelines_are_not_rates(value):
    assert text.leak_in(value) is None, value


def test_public_totals_are_numbers_not_text():
    """Engine totals, ranges and rounded room subtotals are the only amounts a customer sees, always as numbers."""
    for (dto, field), cls in public.PUBLIC_FIELD_CLASSES.items():
        if cls == public.PRICE_OR_RATE_COPY:
            annotation = getattr(public, dto).model_fields[field].annotation
            assert annotation in (int, float), (dto, field, annotation)


# --- Phase 5: claim records ---------------------------------------------------------------------------------------
def parse_claim(statement, **over):
    return kinds.parse("copy", claims.claim_copy(statement, **over))


def test_a_complete_claim_record_parses():
    parse_claim("Most popular")
    parse_claim("Top rated")
    parse_claim("Limited-time offer")


@pytest.mark.parametrize(
    "over,match",
    [
        ({"categories": ["ranking"], "substantiation": "Independent survey report 2026 (synthetic)"}, "do not match"),
        (
            {"categories": ["popularity", "ranking"], "substantiation": "Independent survey report 2026 (synthetic)"},
            "do not match",
        ),
        ({"categories": ["factual_descriptor"]}, "do not match"),
        ({"source": "x"}, "placeholder"),
        ({"evidence_reference": "yes"}, "placeholder"),
        ({"evidence_reference": "internal"}, "placeholder"),
        ({"source": "approved"}, "placeholder"),
        ({"review_by": None}, "review date or an explicit non-expiring"),
        ({"non_expiring_policy": "Owner policy decision 2026-10 (synthetic)"}, "exactly one"),
        ({"evidence_period": None}, "period"),
        ({"approver": "Sales lead (role, test)"}, "self-approval"),
        ({"approver": "Marketing lead (role, test)"}, "self-approval"),
        ({"canonical_sha256": "0" * 64}, "digest"),
        ({"environments": []}, "environments"),
        ({"review_by": "2026-09-01"}, "after its effective date"),
    ],
)
def test_incomplete_or_inconsistent_claim_records_are_refused(over, match):
    with pytest.raises(ValueError, match=match):
        parse_claim("Most popular", **over)


def test_promotional_and_price_claims_are_time_boxed():
    with pytest.raises(ValueError, match="time-boxed"):
        parse_claim("Limited-time offer", review_by=None, non_expiring_policy="Owner policy decision 2026 (synthetic)")


def test_ranking_claims_need_substantiation_and_a_backup_owner():
    with pytest.raises(ValueError, match="substantiation"):
        parse_claim("Top rated", substantiation=None)
    with pytest.raises(ValueError, match="backup owner"):
        parse_claim("Top rated", backup_owner=None)


def test_a_claim_variant_is_the_same_claim_and_the_digest_follows_the_canonical_form():
    doc = claims.claim_copy("Most popular")
    doc["statement"] = "MOST_POPULAR"
    kinds.parse("copy", doc)  # same canonical text: same digest, same categories
    doc["statement"] = "Most popular choice"
    with pytest.raises(ValueError, match="digest"):
        kinds.parse("copy", doc)


# --- Phase 1 / 2: the public payload DTOs ---------------------------------------------------------------------------
def _weak(annotation, metadata=()) -> list[str]:
    """Why an annotation is weak: Any, object, an unparameterised or mutable container, or an unbounded string."""
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin is typing.Annotated:
        extra = [x for m in annotation.__metadata__ for x in (m.metadata if isinstance(m, FieldInfo) else [m])]
        return _weak(args[0], (*metadata, *extra))
    if annotation in (typing.Any, object) or annotation in (dict, list, set, tuple, frozenset):
        return [f"weak type {annotation!r}"]
    if origin in (list, set, frozenset):
        return [f"mutable container {annotation!r}"]
    if origin in (typing.Union, types.UnionType):
        return [w for a in args for w in _weak(a, metadata)]
    bounded = any(isinstance(m, annotated_types.MaxLen) or getattr(m, "max_length", None) for m in metadata)
    if annotation is str and not bounded:
        return ["unbounded string"]
    if origin in (tuple, dict):
        if not bounded:
            return [f"unbounded container {annotation!r}"]
        return [w for a in args if a is not Ellipsis for w in _weak(a)]
    return []


def _fields(roots):
    seen, pending = set(), list(roots)
    while pending:
        cls = pending.pop()
        if cls in seen:
            continue
        seen.add(cls)
        for name, info in cls.model_fields.items():
            yield cls, name, info
            pending.extend(text._models(info.annotation))


def test_no_public_dto_has_a_weak_type():
    problems = []
    for cls, name, info in _fields(public.ROOTS):
        for why in _weak(info.annotation, tuple(info.metadata)):
            problems.append(f"{cls.__name__}.{name}: {why}")
    assert problems == []


def test_every_public_field_is_classified_and_the_registry_has_no_stale_entries():
    found = public.fields()
    assert sorted(found - set(public.PUBLIC_FIELD_CLASSES)) == [], "classify the field in public.PUBLIC_FIELD_CLASSES"
    assert sorted(set(public.PUBLIC_FIELD_CLASSES) - found) == []
    assert set(public.PUBLIC_FIELD_CLASSES.values()) <= set(public.CLASSES)


def test_an_unclassified_or_weak_public_field_fails_closed():
    class PublicGadget(public._Dto):
        slogan: str

    assert ("PublicGadget", "slogan") in public.fields([PublicGadget]) - set(public.PUBLIC_FIELD_CLASSES)
    assert _weak(PublicGadget.model_fields["slogan"].annotation) == ["unbounded string"]
    with pytest.raises(KeyError, match="not classified"):
        list(public.strings(PublicGadget(slogan="Best ever")))


def test_public_dtos_refuse_unknown_fields_and_oversized_values():
    with pytest.raises(ValidationError):
        public.PublicCopy(statement="A", category="label", extra="x")
    with pytest.raises(ValidationError):
        public.PublicCopy(statement="A" * 501, category="label")
    with pytest.raises(ValidationError):
        public.PublicPreparation(label="Site", description="d", amount_minor=1, inclusions=tuple("x" * 25))
    with pytest.raises(ValidationError):
        public.PublicMedia(type="GLB", title="t", label="Design reference", attribution="a", items=(), urls={}, sort=1)


def test_every_public_dto_is_strict_and_frozen():
    for cls, _name, _info in _fields(public.ROOTS):
        assert issubclass(cls, BaseModel)
        assert cls.model_config.get("extra") == "forbid" and cls.model_config.get("frozen"), cls.__name__


# --- the shared checker by class ------------------------------------------------------------------------------------
@pytest.mark.parametrize("cls", [public.FACTUAL_CUSTOMER_COPY, public.PROMISE_GOVERNED_COPY])
@pytest.mark.parametrize(
    "value", ["Best seller", f"B{ZW}est seller", "Ｔｏｐ ｒａｔｅｄ", "Most_popular", "Free installation"]
)
def test_the_checker_refuses_claims_in_factual_and_estimator_text(cls, value):
    assert public.check_text("x", value, cls)


def test_estimator_text_may_state_a_governed_timeline_but_not_a_rate():
    assert public.check_text("t", "Up to 45 days", public.PROMISE_GOVERNED_COPY) == []
    assert public.check_text("t", "Up to 45 days", public.FACTUAL_CUSTOMER_COPY), "factual text states no duration"
    assert public.check_text("t", "Up to 45 days at 1200/sqft", public.PROMISE_GOVERNED_COPY)


def test_controlled_copy_must_be_the_approved_record():
    record = kinds.parse("copy", claims.claim_copy("Most popular"))
    governed = {"copy.badge": record}
    ok = public.check_text(
        "c", "Most popular", public.CONTROLLED_CUSTOMER_COPY, governed=governed, copy_key="copy.badge"
    )
    assert ok == []
    assert public.check_text(
        "c", "Best seller", public.CONTROLLED_CUSTOMER_COPY, governed=governed, copy_key="copy.badge"
    )
    assert public.check_text("c", "Most popular", public.CONTROLLED_CUSTOMER_COPY, governed=governed, copy_key="copy.x")


def test_identifiers_and_numbers_are_not_judged_as_prose():
    assert public.check_text("k", "best-seller.badge", public.IDENTIFIER) == []
