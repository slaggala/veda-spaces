"""B1-B3 policy closure: the allowlist-driven public-content policy, with every reviewer-reproduced example.

- B1: no money or rate in any customer prose. Amounts exist only as typed engine integers.
- B2: no claim outside a governed claim reference. Estimator and card text follow the same rule.
- Measurements are structured and distinct from rates. "area assumed 900 sq ft" is never a rate.
- The remaining normalisation gaps are closed, and the public rule DTO is no broader than the source model.

Detection is defence in depth behind the policies; these tests pin both. Synthetic text only."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.support import claims
from veda.modules.catalog import kinds, public, text
from veda.modules.estimator import ratecard

CARD = ratecard.parse(
    json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-rate-card.json").read_text())
)
PROSE = (public.FACTUAL_TEXT, public.CONTROLLED_LEGAL_COPY, *public.STRUCTURED_TEXT)

# --- B1: money in prose --------------------------------------------------------------------------------------------
B1 = ["1200 per square foot", "1200 a square foot", "1200 per square feet", "1200 per sq-ft", "1200 per s.ft",
      "1200 per running ft", "1200/ft²", "1200 per m²", "1200 per linear foot", "INR1200", "Rs1200", "$1200",
      "USD 1200", "1.2 L", "1.2 Cr", "trade price", "list price", "net rate", "basic rate", "vendor cost",
      "buying price", "supplier price", "procurement cost", "margin", "price ceiling", "15% discount"]  # fmt: skip
VARIANTS = ["₹1200", "₹ 1,200", "Rs. 1200", "1200/-", "1,20,000", "12k per sqft", "12K/sft", "1200 psf", "1200 per rft",
            "per sqft 1200", "/sqft: 1200", "rate: 1200", "rate of 1200", "¹²⁰⁰/sqft", "1200 ⁄ sqft", "１２００ per sq ft",
            "1​200 per sqft", "1200 each unit", "1200/pc", "€ 99", "1200 for every square foot", "1200 per metre",
            "10 percent off", "flat 20%", "2.5 lakhs", "3 crore", "MRP 4000", "dealer price list", "unit rate"]  # fmt: skip


@pytest.mark.parametrize("value", B1 + VARIANTS)
def test_money_and_rates_are_refused_in_every_prose_policy(value):
    assert text.money_in(value), value
    for policy in PROSE:
        assert public.check_text("field", value, policy), (value, policy)


@pytest.mark.parametrize("value", ["Area assumed 900 sq ft", "Kitchen – Base unit: area assumed 900 sq ft (typical)",
                                   "TV wall 8 ft wide", "Width 12 ft", "3 BHK", "2 drawers", "18 mm board", "1 unit",
                                   "TV wall 8′", "Shelves every 2 ft", "1 L-shaped counter", "16/18 mm",
                                   "About 2 months and 10 days, plus up to 10 days' grace", "4 nos"])  # fmt: skip
def test_measurements_quantities_and_timelines_are_not_money(value):
    assert text.money_in(value) is None, (value, text.money_in(value))


def test_a_rate_in_measurement_like_wording_is_still_refused():
    assert text.money_in("Area assumed 900 sq ft at 1200 per sq ft")
    assert text.money_in("TV wall 8 ft, 1200 a running foot")


def test_amounts_exist_only_as_typed_engine_integers():
    amounts = {k for k, p in public.PUBLIC_FIELD_POLICIES.items() if p == public.ENGINE_GENERATED_AMOUNT}
    assert amounts == {("PublicRange", "low_minor"), ("PublicRange", "high_minor"), ("PublicGst", "low_minor"),
                       ("PublicGst", "high_minor"), ("PublicRoomTotal", "amount_minor"),
                       ("PublicPreparation", "amount_minor"), ("PublicAllowance", "low_minor"),
                       ("PublicAllowance", "high_minor")}  # fmt: skip
    assert "pricing_card_version" in public.PublicEstimate.model_fields, "amounts name the approved card"


# --- B2: claims ---------------------------------------------------------------------------------------------------
B2 = ["Lifetime warranty", "Certified material", "Guaranteed delivery", "Award-winning", "Market leader", "Highly rated",
      "Unrivalled", "Five-star rated", "Most trusted", "Top 10", "Great value", "No extra charge", "Only today",
      "Act now", "Offer ends soon", "Best", "Finest", "Lowest price", "Free installation"]  # fmt: skip
SYNONYMS = {
    "ranking": ["Industry leader", "Unparalleled", "Second to none", "Top 5 interiors", "World-class finish"],
    "popularity": ["Customer favourite", "Trusted by thousands", "4.8 star rated", "Loved by families", "Best-selling"],
    "certification": ["ISO 9001", "Lab tested", "Approved by experts", "BIS certified board"],
    "award": ["Award winner 2025", "Prize-winning design"],
    "warranty": ["10-year guarantee", "Assured quality", "Warranty included"],
    "service": ["On-time handover", "Delivered within 30 days", "Same-day callback", "24x7 support"],
    "urgency": ["Hurry, few left", "While stocks last", "Book now", "Last chance"],
    "promotional": ["Value for money", "At no extra cost", "Complimentary design", "Big savings", "Free"],
    "durability": ["Termite-proof", "Scratch resistant", "Maintenance-free", "Long-lasting", "Never fades"],
    "environmental": ["Eco-friendly", "Low VOC", "Child-safe", "Formaldehyde free"],
    "quality": ["Premium laminate", "Superior finish", "Luxurious feel", "High-end look"],
}


@pytest.mark.parametrize("value", B2 + [v for vs in SYNONYMS.values() for v in vs])
def test_every_claim_example_needs_a_governed_claim_reference(value):
    assert text.claims_in(value), value
    for policy in PROSE:
        assert public.check_text("field", value, policy), (value, policy)


@pytest.mark.parametrize("category,value", [(c, v) for c, vs in SYNONYMS.items() for v in vs])
def test_claims_are_categorised(category, value):
    assert category in text.claims_in(value), (value, text.claims_in(value))


@pytest.mark.parametrize("value", ["Premium", "Luxury", "Essential", "Premium package", "Luxury package",
                                   "Luxury package: discussed in a design consultation", "Space-saving drawers",
                                   "Offers open storage", "Proofed edges", "Leading edge trim", "Free-standing unit",
                                   "Site and floor protection", "Pest-control preparation where applicable",
                                   "Appliances, loose furniture and décor", "Matte laminate", "Natural wood veneer"])  # fmt: skip
def test_tier_names_and_ordinary_descriptions_are_factual(value):
    assert text.claims_in(value) == [], (value, text.claims_in(value))


# --- normalisation gaps ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["Bést seller", "B̲e̲s̲t̲ seller", "Bést seller", "ʙᴇꜱᴛ ꜱᴇʟʟᴇʀ", "B3st seller",
                                   "Fr33 installation", "l1fetime warranty", "Bεst seller", "Bеst sеller", "BEST SELLER",
                                   "Best　seller", "Best seller", "C3rtified", "$ale"])  # fmt: skip
def test_remaining_normalisation_gaps_are_closed(value):
    assert text.claims_in(value), value


def test_mixed_script_words_are_refused_at_authoring_and_in_payloads():
    assert text.mixed_script_words("Bеst seller") == ["Bеst"]
    assert text.mixed_script_words("Natural wood veneer, décor") == []
    assert public.check_text("x", "Matte lаminate", public.FACTUAL_TEXT)
    with pytest.raises(ValueError, match="mix scripts"):
        kinds.parse("product_family", {"name": "TV unіts", "category": "media_units"})


def test_superscript_and_foot_symbols_in_rates():
    assert text.money_in("₹1200/ft²") and text.money_in("1200 per ft²") and text.money_in("¹²⁰⁰ per sq ft")
    assert text.money_in("8′ TV wall") is None


# --- structured measurements -------------------------------------------------------------------------------------
def assumption(**over):
    base = {"room": "LIVING", "room_label": "Living room", "item": "TV_UNIT", "item_label": "TV unit", "instance": 1,
            "measurement": "WIDTH", "measurement_label": "TV wall width", "measurement_type": "LENGTH", "value": 8.0,
            "unit": "FT", "basis": "TYPICAL_ASSUMPTION"}  # fmt: skip
    return public.PublicAssumption(**{**base, **over})


def test_every_typical_measurement_of_the_card_is_a_safe_structured_assumption():
    found = 0
    for p in CARD.products:
        for i in p.inputs:
            unit = {"length": ("LENGTH", "FT"), "area": ("AREA", "SQ_FT"), "count": ("QUANTITY", "NOS")}[i.kind]
            for value in i.typical.values():
                a = assumption(item=p.code, item_label=p.label, measurement=i.name, measurement_label=i.label,
                               measurement_type=unit[0], unit=unit[1], value=float(value))  # fmt: skip
                assert public.check_payload(a) == [], (p.code, i.name)
                found += 1
    assert found > 10


@pytest.mark.parametrize("bad", [{"measurement_type": "RATE"}, {"measurement_type": "TOTAL_AMOUNT"}, {"unit": "INR"},
                                 {"unit": "sq ft"}, {"value": -1.0}, {"basis": "QUOTED"}])  # fmt: skip
def test_rates_and_amounts_are_never_public_measurements(bad):
    with pytest.raises(ValidationError):
        assumption(**bad)
    assert {"RATE", "TOTAL_AMOUNT"} <= set(public.MEASUREMENT_TYPES)


def test_the_area_assumption_that_caused_a_503_is_structured_and_safe():
    a = assumption(item="KITCHEN_BASE", item_label="Base unit", measurement="AREA", measurement_label="Area",
                   measurement_type="AREA", value=900.0, unit="SQ_FT", room="KITCHEN", room_label="Kitchen")  # fmt: skip
    assert public.check_payload(a) == []


# --- public rule DTO ------------------------------------------------------------------------------------------------
def test_the_public_rule_dto_is_no_broader_than_the_source_model():
    ok = public.PublicRule(type="measurement_bounds", subject="product:tv-unit", objects=(), input="WIDTH", min=3.0,
                           max=20.0, message="copy.rule.tv-width")  # fmt: skip
    assert ok.subject == "product:tv-unit"
    for bad in ({"subject": "anything at all"}, {"objects": ("not a ref",)}, {"type": "staff_only"},
                {"min": 0.0}, {"objects": tuple(f"extra:e{i:02d}" for i in range(13))}, {"extra_field": 1}):  # fmt: skip
        with pytest.raises(ValidationError):
            public.PublicRule(**{**ok.model_dump(), **bad})


# --- authoring: the author selects a content policy ------------------------------------------------------------------
def test_copy_needs_an_author_selected_content_policy():
    doc = {"statement": "Natural wood veneer", "category": "material", "promise": False}
    with pytest.raises(ValueError, match="content policy"):
        kinds.parse("copy", doc)
    kinds.parse("copy", {**doc, "content_policy": "FACTUAL_TEXT"})
    with pytest.raises(ValueError, match="governed claim reference is a claim record"):
        kinds.parse("copy", {**doc, "content_policy": "GOVERNED_CLAIM_REFERENCE"})


@pytest.mark.parametrize("policy", ["FACTUAL_TEXT", "CONTROLLED_LEGAL_COPY"])
@pytest.mark.parametrize("value", ["Best seller", "Lifetime warranty", "Guaranteed delivery", "Rs 1200 per sqft"])
def test_claim_or_money_cannot_be_authored_as_factual_or_legal_copy(policy, value):
    with pytest.raises(ValueError):
        kinds.parse("copy", {"statement": value, "category": "label", "promise": False, "content_policy": policy})


def test_a_claim_record_cannot_be_authored_as_factual_copy():
    with pytest.raises(ValueError, match="GOVERNED_CLAIM_REFERENCE"):
        kinds.parse("copy", {**claims.claim_copy("Most popular"), "content_policy": "FACTUAL_TEXT"})


@pytest.mark.parametrize("over,match", [
    ({"approved_on": "2026-10-05"}, "approved on or before"),
    ({"review_by": None, "non_expiring_policy": "Owner policy decision 2026 (synthetic)"}, "time-boxed"),
])  # fmt: skip
def test_claim_record_dates_and_time_boxing(over, match):
    with pytest.raises(ValueError, match=match):
        kinds.parse("copy", claims.claim_copy("Most popular", **over))


def test_a_withdrawn_claim_record_fails_closed():
    from veda.modules.catalog import claims as validity

    model = kinds.parse("copy", claims.claim_copy("Most popular", status="WITHDRAWN"))

    class Cat:
        release_code, manifest_sha256 = "T", "0" * 64

        def of(self, cls):
            return {"copy.x": model} if cls is kinds.Copy else {}

        def one(self, cls, key):
            return None

    assert any("WITHDRAWN, not approved" in p for p in validity.problems(Cat(), env="test"))


def test_served_claim_categories_are_exactly_the_detected_ones():
    import typing

    assert set(typing.get_args(public.ClaimTag)) == set(text.CATEGORIES)
