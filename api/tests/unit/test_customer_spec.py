"""ADR-012 T9: the customer-facing specification schema refuses amounts, pricing words, durations and personal data;
room promises follow what the estimate priced in each room (trust finalisation, Phase 3)."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from veda.modules.estimator import customer_spec

REPO = Path(__file__).resolve().parents[3]
SYNTHETIC = json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-customer-spec.json").read_text())
SPECS = REPO / "docs/implementation/estimator/specifications"
ESSENTIAL_10 = json.loads((SPECS / "essential-specification-v1.0.json").read_text())
ESSENTIAL = json.loads((SPECS / "essential-specification-v1.1.json").read_text())
CARD = json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-rate-card.json").read_text())
CARD_LINES = {f"{p['code']}.{ln['code']}" for p in CARD["products"] for ln in p["lines"]}
CARD_PRODUCTS = {p["code"] for p in CARD["products"]}


def test_the_committed_specifications_are_valid():
    assert customer_spec.parse(SYNTHETIC).spec_code == "SYNTHETIC-ESSENTIAL-1.1"
    assert customer_spec.parse(ESSENTIAL_10).spec_code == "ESSENTIAL-1.0"  # stays loadable: estimates point to it
    essential = customer_spec.parse(ESSENTIAL)
    assert essential.spec_code == "ESSENTIAL-1.1" and len(essential.categories) == 14
    for c in essential.categories:  # T3: requirement, examples, equivalent rule and final-selection checkpoint
        assert c.requirement and c.equivalent_rule and c.final_selection


@pytest.mark.parametrize("doc", [ESSENTIAL, SYNTHETIC], ids=["ESSENTIAL-1.1", "SYNTHETIC-1.1"])
def test_every_promise_is_tied_to_lines_the_card_prices(doc):
    """No generic room promise: every category names the priced lines that carry it, and they exist in the card."""
    for c in customer_spec.parse(doc).categories:
        assert c.applies_to.lines, f"{c.code} applies to no priced line"
        for ref in c.applies_to.lines:
            product, line = ref.split(".")
            assert (ref in CARD_LINES) if line != "*" else (product in CARD_PRODUCTS), (
                f"{c.code}: {ref} is not in the card"
            )


@pytest.mark.parametrize(
    "text,reason",
    [
        ("Laminate up to ₹2,500 per sheet", "an amount of money"),
        ("Handles within Rs 800", "an amount of money"),
        ("Supplied at cost", "pricing wording"),
        ("Laminate price limit applies", "pricing wording"),
        ("Plywood with a 30-year warranty", "a warranty or time duration"),
        ("Hinges guaranteed for 5 years", "a warranty or time duration"),
        ("Call 9876543210", "a phone number"),
        ("Write to someone@example.com", "an email address"),
    ],
)
def test_forbidden_content_is_refused(text, reason):
    doc = copy.deepcopy(SYNTHETIC)
    doc["categories"][0]["details"] = [text]
    with pytest.raises(ValidationError, match=reason):
        customer_spec.parse(doc)


def test_false_ceiling_is_not_pricing_wording():
    doc = copy.deepcopy(SYNTHETIC)
    doc["categories"][3]["requirement"] = "Gypsum false ceiling on steel channels"
    assert customer_spec.parse(doc)


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda d: d.update(spec_code="SYNTHETIC-ESSENTIAL-2.0"), "must end with the version"),
        (lambda d: d["categories"].append(copy.deepcopy(d["categories"][0])), "duplicate category codes"),
        (lambda d: d["categories"][0]["applies_to"].update(rooms=["GARAGE"]), "rooms"),
        (lambda d: d.update(rate_minor=1), "Extra inputs"),
        (lambda d: d["categories"][0].pop("equivalent_rule"), "equivalent_rule"),
    ],
)
def test_invalid_specifications_are_refused(mutate, message):
    doc = copy.deepcopy(SYNTHETIC)
    mutate(doc)
    with pytest.raises(ValidationError, match=message):
        customer_spec.parse(doc)


def test_customer_view_holds_customer_fields_only():
    view = customer_spec.customer_view(ESSENTIAL)
    text = json.dumps(view, ensure_ascii=False)
    assert "₹" not in text and "rate" not in json.dumps(list(view)) and view["categories"][0]["rooms"]


# --- room promises (Phase 3) -------------------------------------------------------------------------------------------
KITCHEN = [
    ("KITCHEN", x)
    for x in ("BASE", "WALL", "LOFT", "TANDEM", "PLUMBING", "SOFT_CLOSE", "SOFT_CLOSE_WALL", "SOFT_CLOSE_LOFT")
]
BEDROOM = [
    ("WARDROBE", "BODY"),
    ("WARDROBE", "LOFT"),
    ("WARDROBE", "SOFT_CLOSE"),
    ("WARDROBE", "SOFT_CLOSE_LOFT"),
    ("BED", "QUEEN"),
    ("BED", "HYDRAULIC"),
    ("BED", "PANEL"),
    ("VANITY_UNIT", "TOILET"),
    ("VANITY_UNIT", "MIRROR"),
]


def lines_for(priced, doc=ESSENTIAL):
    return {room: v["line"] for room, v in customer_spec.room_materials(doc, priced).items()}


def test_room_lines_follow_the_priced_lines():
    got = lines_for(
        {
            "KITCHEN": KITCHEN,
            "MASTER_BEDROOM": BEDROOM,
            "LIVING": [
                ("TV_UNIT", "BOX"),
                ("TV_UNIT", "STORAGE"),
                ("TV_UNIT", "PANEL"),
                ("TV_UNIT", "SOFT_CLOSE"),
                ("TV_UNIT", "SOFT_CLOSE_STORAGE"),
                ("FEATURE_WALL", "PANELLING"),
            ],
            "POOJA": [("POOJA_UNIT", "UNIT"), ("POOJA_UNIT", "BEADING"), ("POOJA_UNIT", "DOOR")],
            "WHOLE_HOME": [
                ("FALSE_CEILING", "GYPSUM"),
                ("FALSE_CEILING", "PANEL_LIGHTS"),
                ("CEILING_PROFILE_LIGHTING", "PROFILE"),
            ],
            "DINING": [("CROCKERY_UNIT", "BODY")],
        }
    )
    assert got == {
        "KITCHEN": "Branded plywood cabinetry · Laminate finish · Soft-close kitchen hardware",
        "MASTER_BEDROOM": "Branded plywood furniture · Laminate finish · Soft-close wardrobe hardware",
        "LIVING": "Branded plywood TV unit · Laminate finish · Soft-close TV-unit hardware",
        "POOJA": "Approved board structure · Laminate finish · Approved hinges and channels",
        "WHOLE_HOME": "Gypsum ceiling on steel channels · Approved lighting specification",
        "DINING": "Branded plywood crockery unit · Laminate finish · Approved hinges and channels",
    }


def test_no_soft_close_promise_without_a_soft_close_line():
    sliding = [
        ("WARDROBE", "BODY"),
        ("WARDROBE", "SLIDING"),
        ("BED", "QUEEN"),
        ("BED", "HYDRAULIC"),
    ]  # no loft, no hinges
    line = lines_for({"BEDROOM_2": sliding})["BEDROOM_2"]
    assert "Soft-close" not in line and line.endswith("Approved hinges and channels")
    details = customer_spec.room_materials(ESSENTIAL, {"BEDROOM_2": sliding})["BEDROOM_2"]["categories"]
    assert "soft_close" not in details and "hardware" in details


def test_no_plywood_promise_for_gypsum_glass_veneer_or_wall_finishes():
    priced = {
        "WHOLE_HOME": [("FALSE_CEILING", "GYPSUM"), ("PAINTING", "FULL"), ("ELECTRICAL", "WIRING")],
        "LIVING": [("PARTITION", "FLUTED"), ("FEATURE_WALL", "WALLPAPER"), ("VENEER_ACCENTS", "ARCH")],
    }
    got = customer_spec.room_materials(ESSENTIAL, priced)
    assert "plywood" not in (got["WHOLE_HOME"]["line"] or "").lower()
    assert (
        got["WHOLE_HOME"]["line"] == "Gypsum ceiling on steel channels · Premium emulsion paint · Branded copper wiring"
    )
    assert got["LIVING"] == {"line": None, "categories": ["decorative"]}, "only a final-selection statement applies"


def test_every_room_line_phrase_belongs_to_a_category_that_applies_there():
    priced = {"KITCHEN": KITCHEN, "MASTER_BEDROOM": BEDROOM, "POOJA": [("POOJA_UNIT", "UNIT"), ("POOJA_UNIT", "DOOR")]}
    spec = customer_spec.parse(ESSENTIAL)
    for room, v in customer_spec.room_materials(ESSENTIAL, priced).items():
        allowed = set()
        for c in spec.categories:
            if c.code in v["categories"]:
                allowed |= {c.summary, *c.phrases.values()}
        assert set(v["line"].split(" · ")) <= allowed, room


def test_a_specification_without_line_applicability_gives_nothing_per_room():
    """F1 regression: ESSENTIAL-1.0's generic categories never reach a room, neither as a line nor in the details."""
    got = customer_spec.room_materials(ESSENTIAL_10, {"KITCHEN": KITCHEN, "POOJA": [("POOJA_UNIT", "UNIT")]})
    assert got == {"KITCHEN": {"line": None, "categories": []}, "POOJA": {"line": None, "categories": []}}
    assert customer_spec.customer_view(ESSENTIAL_10)["room_promises"] is False
    assert customer_spec.customer_view(ESSENTIAL)["room_promises"] is True


# Every priced line of every product, alone in every room the card allows it in (F1 negative tests).
SINGLE_LINES = [(room, p["code"], ln["code"]) for p in CARD["products"] for room in p["rooms"] for ln in p["lines"]]


@pytest.mark.parametrize("room,product,line", SINGLE_LINES, ids=[f"{r}-{p}.{ln}" for r, p, ln in SINGLE_LINES])
def test_room_details_show_only_categories_carried_by_the_priced_line(room, product, line):
    spec = customer_spec.parse(ESSENTIAL)
    got = customer_spec.room_materials(ESSENTIAL, {room: [(product, line)]})[room]
    expected = [
        c.code
        for c in spec.categories
        if room in c.applies_to.rooms and ({f"{product}.{line}", f"{product}.*"} & set(c.applies_to.lines))
    ]
    assert got["categories"] == expected
    assert ("soft_close" in got["categories"]) == (
        line.startswith("SOFT_CLOSE") or (product, line) == ("KITCHEN", "TANDEM")
    )
    assert ("lighting" in got["categories"]) == (
        (product, line) in {("FALSE_CEILING", "PANEL_LIGHTS"), ("ELECTRICAL", "SPOTS")}
        or product == "CEILING_PROFILE_LIGHTING"
    )
    not_plywood = {
        "FEATURE_WALL",
        "FALSE_CEILING",
        "CEILING_PROFILE_LIGHTING",
        "VENEER_ACCENTS",
        "POOJA_UNIT",
        "PAINTING",
        "ELECTRICAL",
    }
    if (
        product in not_plywood
        or line in {"FLUTED", "GLASS", "MIRROR", "CUSHION", "HYDRAULIC", "SLIDING", "ARCH", "TANDEM"}
        or line.startswith("SOFT_CLOSE")
    ):
        assert "structure" not in got["categories"] and "plywood" not in (got["line"] or "").lower()
    assert all(c.code == "decorative" for c in spec.categories if c.code in got["categories"]) or product not in {
        "FEATURE_WALL",
        "VENEER_ACCENTS",
    }


def test_a_feature_wall_only_room_gets_no_cabinetry_promise():
    for finish in ("PANELLING", "WALLPAPER", "TEXTURE"):
        got = customer_spec.room_materials(ESSENTIAL, {"BEDROOM_2": [("FEATURE_WALL", finish)]})["BEDROOM_2"]
        assert got == {"line": None, "categories": ["decorative"]}


def test_lighting_only_when_lighting_is_priced():
    plain = customer_spec.room_materials(ESSENTIAL, {"WHOLE_HOME": [("FALSE_CEILING", "GYPSUM")]})["WHOLE_HOME"]
    assert "lighting" not in plain["categories"] and plain["line"] == "Gypsum ceiling on steel channels"


@pytest.mark.parametrize("room,product,line", SINGLE_LINES, ids=[f"{r}-{p}.{ln}" for r, p, ln in SINGLE_LINES])
def test_essential_10_never_reaches_room_details(room, product, line):
    assert customer_spec.room_materials(ESSENTIAL_10, {room: [(product, line)]})[room] == {
        "line": None,
        "categories": [],
    }


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda c: c["phrases"].update(BED="Branded plywood bed"), "does not apply to"),
        (lambda c: c.update(line_group=None), "give the category a line_group"),
        (lambda c: c["applies_to"].update(lines=["kitchen.base"]), "lines"),
        (lambda c: c["phrases"].update(KITCHEN="Laminate at ₹90 per sq ft"), "an amount of money"),
    ],
)
def test_room_line_wording_is_validated(mutate, message):
    doc = copy.deepcopy(ESSENTIAL)
    soft_close = next(c for c in doc["categories"] if c["code"] == "soft_close")
    mutate(soft_close)
    with pytest.raises(ValidationError, match=message):
        customer_spec.parse(doc)
