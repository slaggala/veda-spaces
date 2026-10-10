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


# --- B1 final closure: countable-item rates, price qualifiers, commission, percentage savings ---------------------------
B1_FINAL = ["1200 per shutter", "1200 per door", "1200 per drawer", "1200 per panel", "1200 per box", "1200 per room",
            "1200 per visit", "1200 per day", "1200 per hour", "1200 per item", "1200 per unit",
            "1200 per shutter installed", "1200 per wardrobe", "1200 per module", "1200 per piece", "1200 extra",
            "1200 only", "120000 commission", "commission 1200", "1200 commission", "Save 20%", "Save 20% on wardrobes",
            "20% off"]  # fmt: skip
# The rule is generic (COUNTABLE_RATE): any noun after "per" or "/", an amount "each", or "a"/"an" + a countable noun.
B1_FINAL_VARIANTS = ["1200 per cabinet", "1200 per partition", "1200 per window", "1200 per bed", "1200 per storage",
                     "1200 per shelf", "1200 per carcass", "1200 per gizmo", "1200/shutter", "1200 each",
                     "1200 a shutter", "only 1200", "starting at 1200", "1,200 per door", "Rs 1200 per visit",
                     "12k per module", "Get 15% discount on modules", "Save up to 25%"]  # fmt: skip
MEASUREMENTS = ["900 sq ft", "120 sq ft", "10 ft", "4 m", "3 rooms", "2 wardrobes selected", "2 extra drawers",
                "Only the selected rooms", "TV unit for 1 room", "16/18 mm", "Shelves every 2 ft"]  # fmt: skip


@pytest.mark.parametrize("value", B1_FINAL + B1_FINAL_VARIANTS)
def test_b1_final_countable_rates_qualifiers_commission_and_savings_are_refused(value):
    assert text.money_in(value), value
    for policy in PROSE:
        assert public.check_text("field", value, policy), (value, policy)
    with pytest.raises(ValueError):
        kinds.parse(
            "copy", {"statement": value, "category": "label", "promise": False, "content_policy": "FACTUAL_TEXT"}
        )


@pytest.mark.parametrize("value", MEASUREMENTS)
def test_b1_final_does_not_regress_measurements_and_quantities(value):
    assert text.money_in(value) is None, (value, text.money_in(value))


def test_save_with_a_multi_digit_percentage_is_a_promotional_claim():
    assert "promotional" in text.claims_in("Save 20% on wardrobes")
    assert "promotional" in text.claims_in("Save 125 percent")


# --- category-level classification, independent of the number used ---------------------------------------------------
NUMBERS = ["0", "1", "5", "7", "42", "99", "120", "999", "1200", "12345", "120000", "1,200", "1,20,000", "1.5", "12.75",
           "twelve hundred", "seven", "fifty"]  # fmt: skip
NOUNS = ["shutter", "door", "drawer", "panel", "box", "room", "visit", "day", "hour", "item", "unit", "piece",
         "wardrobe", "module", "cabinet", "partition", "window", "bed", "storage", "shelf", "carcass", "gizmo",
         "frobnicator", "sq ft", "running foot", "metre"]  # fmt: skip
CATEGORY_TEMPLATES = {
    text.RATE: [
        "{n} per {x}",
        "{n}/{x}",
        "{n} per {x} installed",
        "{n} each",
        "{n} a {x}",
        "{n} for every {x}",
        "per {x} {n}",
        "rate {n}",
        "{n} per {x}, fitted",
    ],
    text.DISCOUNT: ["save {n}%", "Save {n}% on {x}s", "{n}% off", "{n}% discount on every {x}", "get {n}% cashback"],
    text.COMMISSION: ["{n} commission", "commission {n}", "commission of {n} per {x}", "{n} brokerage"],
    text.PROMOTIONAL_PRICE: [
        "{n} extra",
        "{n} only",
        "only {n}",
        "starting at {n}",
        "Rs {n}",
        "₹{n}",
        "{n} lakh",
        "{x}: {n}",
    ],
}


@pytest.mark.parametrize("category", list(CATEGORY_TEMPLATES))
def test_money_categories_are_classified_whatever_the_number_and_noun(category):
    misses = []
    for template in CATEGORY_TEMPLATES[category]:
        for n in NUMBERS:
            for x in NOUNS:
                value = template.format(n=n, x=x)
                found = text.money_categories(value)
                if not found or (category in (text.DISCOUNT, text.COMMISSION) and category not in found):
                    misses.append((value, found))
    assert misses == [], misses[:10]


ALLOWED_TEMPLATES = ["{n} ft", "{n} feet", "{n} sq ft", "{n} sqm", "{n} mm board", "{n} m deep", "{n}′ TV wall",
                     "{n} days", "up to {n} weeks", "about {n} months", "{n} rooms", "{n} wardrobes selected",
                     "{n} extra drawers", "area assumed {n} sq ft", "TV unit for {n} room", "from {n} to 20 feet",
                     "{n}-{n} days", "{n} x 3 ft panel", "Bedroom {n}"]  # fmt: skip


def test_measurements_durations_quantities_and_labels_are_allowed_whatever_the_number():
    false = []
    for template in ALLOWED_TEMPLATES:
        for n in [n for n in NUMBERS if n[0].isdigit() and "," not in n]:
            value = template.format(n=n)
            if text.money_categories(value):
                false.append((value, text.money_categories(value)))
    assert false == [], false[:10]


def test_a_number_with_no_allowlisted_role_is_never_prose():
    for value in ("Cabinets 1200", "TV unit, 4500.", "Includes the hood (899)", "Call for 3500"):
        assert text.money_categories(value), value


# --- QUANTITY is proven, never inferred ----------------------------------------------------------------------------
QUANTITY_FALSE_NEGATIVES = ["1200 apiece", "1200 plus GST", "1200 additional per door", "1200 on every door",
                            "1200 for installation", "1200 monthly", "1200 annually", "1200 hourly", "1200 weekly",
                            "100 apiece", "5000 annually", "25 daily", "1.2 lakh monthly"]  # fmt: skip
LABELS_AND_CODES = ["Package 3", "Bedroom 2", "Specification 1.1", "I-401", "E1"]
ADVERSARIAL_WORDINGS = ["{n} daily", "{n} weekly", "{n} monthly", "{n} annually", "{n} apiece", "{n} including GST",
                        "{n} plus GST", "{n} on every {x}", "{n} additional per {x}", "{n} for installation",
                        "{n} for each {x}", "{n} incl. GST", "{n} + GST"]  # fmt: skip
ENTITY_NOUNS = ["door", "shutter", "drawer", "wardrobe", "panel", "room"]
UNPROVEN_WORDS = ["installation", "fitting", "labour", "service", "gizmos", "approx", "flat", "net", "only", "fitted",
                  "delivered", "charges", "frobnicators", "upfront", "total"]  # fmt: skip


@pytest.mark.parametrize("value", QUANTITY_FALSE_NEGATIVES)
def test_reviewer_quantity_false_negatives_are_money(value):
    assert text.money_categories(value), value
    for policy in PROSE:
        assert public.check_text("field", value, policy), (value, policy)


@pytest.mark.parametrize("value", LABELS_AND_CODES)
def test_labels_and_codes_are_allowed(value):
    assert text.money_categories(value) == [], (value, text.money_categories(value))


def test_adversarial_periodic_tax_and_every_wordings_are_money_for_any_number():
    misses = [
        (w.format(n=n, x=x), text.money_categories(w.format(n=n, x=x)))
        for w in ADVERSARIAL_WORDINGS for n in NUMBERS for x in ENTITY_NOUNS
        if not text.money_categories(w.format(n=n, x=x))
    ]  # fmt: skip
    assert misses == [], misses[:10]


def test_a_following_word_never_makes_a_quantity_unless_it_is_an_approved_entity():
    digits = [n for n in NUMBERS if n[0].isdigit()]
    unproven = [(f"{n} {w}", text.money_categories(f"{n} {w}")) for n in digits for w in UNPROVEN_WORDS
                if not text.money_categories(f"{n} {w}")]  # fmt: skip
    assert unproven == [], unproven[:10]
    proven = [(f"{n} {w}s", text.money_categories(f"{n} {w}s")) for n in digits if "." not in n for w in ENTITY_NOUNS
              if text.money_categories(f"{n} {w}s")]  # fmt: skip
    assert proven == [], proven[:10]
    assert {"rooms", "drawers", "wardrobes", "panels", "doors", "shutters"} <= text.QUANTITY_NOUNS


def test_the_quantity_lookup_includes_the_schemas_rooms():
    import typing

    for code in typing.get_args(kinds.RoomCode):
        word = code.split("_")[0].lower()
        if word not in ("whole", "kids", "master"):
            assert word in text.QUANTITY_NOUNS or word + "s" in text.QUANTITY_NOUNS, code
