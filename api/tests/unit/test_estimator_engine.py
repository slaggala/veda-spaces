"""E1: the Budgetary Estimate pricing engine (ADR-012 §3) on the SYNTHETIC rate card (no commercial rates)."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from veda.modules.estimator import engine, ratecard
from veda.modules.estimator.engine import EstimateError, EstimateRequest

CARD_DOC = json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-rate-card.json").read_text())
CARD = ratecard.parse(CARD_DOC)
PREP_2BHK = 1_200_000 + 1_000_000 + 1_200_000 + 700_000 + 900_000 + 400_000  # carpentry, apartment (no hardware)


def req(*selections, package="ESSENTIAL", home_size="2BHK", property_type="APARTMENT", **extra):
    return EstimateRequest.model_validate(
        {
            "property_type": property_type,
            "home_size": home_size,
            "project_kind": "NEW_HOME",
            "package": package,
            "selections": list(selections),
            **extra,
        }
    )


def sel(product, room, measurements=None, **options):
    return {
        "product": product,
        "room": room,
        "measurements": {k: {"value": v[0], "unit": v[1]} for k, v in (measurements or {}).items()},
        "options": options,
    }


def lines(est, product=None):
    return {(ln.product, ln.code): ln.amount_minor for ln in est.lines if product in (None, ln.product)}


def wardrobe(**options):
    return sel("WARDROBE", "MASTER_BEDROOM", {"WIDTH": (6, "ft"), "HEIGHT": (7, "ft")}, **options)


# --- worked example (hand-computed) ---------------------------------------------------------------------------------


def test_wardrobe_worked_example_measured():
    est = engine.calculate(CARD, req(wardrobe()))
    assert lines(est) == {
        ("WARDROBE", "BODY"): 42 * 100_000,
        ("WARDROBE", "LOFT"): 12 * 80_000,
        ("WARDROBE", "SOFT_CLOSE"): 42 * 5_000,  # hinge hardware is part of the wardrobe (D5)
        ("WARDROBE", "SOFT_CLOSE_LOFT"): 12 * 5_000,
    }
    assert est.prep_minor == PREP_2BHK == 5_400_000
    work = 5_430_000
    assert (est.allowance_low_minor, est.allowance_minor, est.allowance_high_minor) == (271_500, 543_000, 814_500)
    assert est.base_minor == work + 543_000 + PREP_2BHK == 11_373_000, "allowance midpoint is in the base"
    # low: 0.9 × (work + prep) + 5 % allowance = 10_018_500 → ₹1,00,00,000 paise; high: 1.15 × … + 15 % = 13_269_000
    assert (est.low_minor, est.high_minor) == (10_000_000, 13_500_000), "measured band −10/+15, rounded to ₹5,000"
    assert (est.gst_low_minor, est.gst_high_minor) == (1_800_000, 2_430_000)
    assert est.timeline["min_days"] == 70 and est.budget_range_code == "UNDER_5L"
    assert est.project_type_code == "BEDROOM_WARDROBE" and not est.assumptions


def test_typical_sizes_widen_the_band_and_are_labelled():
    measured = engine.calculate(CARD, req(wardrobe()))
    typical = engine.calculate(CARD, req(sel("WARDROBE", "MASTER_BEDROOM")))
    assert typical.base_minor == measured.base_minor, "the synthetic typical wardrobe is 6 × 7"
    assert typical.low_minor <= measured.low_minor and typical.high_minor > measured.high_minor
    assert [a.input for a in typical.assumptions] == ["WIDTH", "HEIGHT"]
    assert typical.customer_view()["assumptions"] == [
        "Master bedroom – Wardrobe: width assumed 6 ft (typical for 2 bhk).",
        "Master bedroom – Wardrobe: height assumed 7 ft (typical for 2 bhk).",
    ]


# --- every product -------------------------------------------------------------------------------------------------

EVERY_PRODUCT = [
    (
        sel("KITCHEN", "KITCHEN", {"RUN": (10, "ft"), "DRAWERS": (4, "nos")}),
        3_000_000 + 2_000_000 + 1_600_000 + 2_000_000 + 800_000 + (29 + 20 + 20) * 5_000,
    ),
    (wardrobe(DOOR="SLIDING", GLASS="YES"), 4_200_000 + 960_000 + 1_000_000 + 420_000 + 12 * 5_000),
    (
        sel("TV_UNIT", "LIVING", {"WIDTH": (7, "ft")}, STYLE="PANELLED"),
        1_050_000 + 2_100_000 + 3_920_000 + (9.1 + 21) * 5_000,
    ),
    (sel("FEATURE_WALL", "LIVING", {"WIDTH": (8, "ft"), "HEIGHT": (9, "ft")}, FINISH="WALLPAPER"), 72 * 20_000),
    (sel("CROCKERY_UNIT", "DINING", {"WIDTH": (5, "ft"), "HEIGHT": (7, "ft")}, GLASS="YES"), 3_500_000 + 525_000),
    (sel("PARTITION", "LIVING", {"WIDTH": (4, "ft"), "HEIGHT": (8, "ft")}), 32 * 150_000),
    (sel("FALSE_CEILING", "WHOLE_HOME", {"AREA": (900, "sqft")}, DESIGN="COVE"), 4_500_000 + 1_800_000 + 22.5 * 70_000),
    (sel("STUDY_UNIT", "STUDY", {"WIDTH": (5, "ft")}), 1_250_000 + 1_000_000),
    (sel("VANITY_UNIT", "MASTER_BEDROOM", TYPE="DRESSER"), 12 * 120_000 + 400_000),
    (sel("BED", "MASTER_BEDROOM", SIZE="KING", HEADBOARD="CUSHIONED"), 3_600_000 + 700_000 + 1_500_000 + 1_800_000),
    (sel("UTILITY", "UTILITY", {"WIDTH": (4, "ft")}), 800_000 + 500_000),
    (sel("PAINTING", "WHOLE_HOME", {"AREA": (2500, "sqft")}), 2500 * 2_500),
    (sel("ELECTRICAL", "WHOLE_HOME", {"CARPET": (1100, "sqft"), "SPOTS": (8, "nos")}), 1100 * 3_000 + 8 * 50_000),
    # The recurring product types (D9).
    (
        sel("POOJA_UNIT", "POOJA", {"WIDTH": (3, "ft"), "DOOR_WIDTH": (4, "ft")}, DOOR="CNC_VENEER", ASTA_CHAKRA="YES"),
        6 * 100_000 + 15 * 90_000 + 30 * 150_000 + 1_200_000,
    ),
    (sel("WINDOW_SEATING", "BEDROOM_2", {"WIDTH": (5, "ft")}), 10 * 100_000 + 45 * 80_000),
    (sel("VENEER_ACCENTS", "KITCHEN", {"LENGTH": (18, "ft")}), 18 * 90_000),
    (sel("STORAGE_BOXES", "MASTER_BEDROOM", {"WIDTH": (3, "ft"), "HEIGHT": (7, "ft")}), 21 * 100_000),
    (
        sel("CEILING_PROFILE_LIGHTING", "WHOLE_HOME", {"LENGTH": (50, "ft"), "COB": (4, "nos")}),
        50 * 60_000 + 4 * 100_000,
    ),
]


@pytest.mark.parametrize("selection,expected", EVERY_PRODUCT, ids=[s["product"] for s, _ in EVERY_PRODUCT])
def test_every_product(selection, expected):
    est = engine.calculate(CARD, req(selection))
    assert sum(lines(est).values()) == expected
    assert {p.code for p in CARD.products} == {s["product"] for s, _ in EVERY_PRODUCT}


def test_fixed_and_measured_items_together():
    est = engine.calculate(CARD, req(sel("VANITY_UNIT", "BEDROOM_2"), sel("BED", "BEDROOM_2", HEADBOARD="NONE")))
    assert lines(est) == {
        ("VANITY_UNIT", "TOILET"): 900_000,
        ("VANITY_UNIT", "MIRROR"): 400_000,
        ("BED", "QUEEN"): 3_000_000,
        ("BED", "HYDRAULIC"): 700_000,
    }
    assert not est.assumptions, "fixed items need no measurement"


# --- units and bounds ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "width,unit", [(6, "ft"), (72, "in"), (1.8288, "m"), (182.88, "cm")], ids=["ft", "in", "m", "cm"]
)
def test_units_convert(width, unit):
    est = engine.calculate(CARD, req(sel("WARDROBE", "MASTER_BEDROOM", {"WIDTH": (width, unit), "HEIGHT": (7, "ft")})))
    assert lines(est)[("WARDROBE", "BODY")] == 4_200_000


def test_square_metres_convert():
    est = engine.calculate(CARD, req(sel("FALSE_CEILING", "LIVING", {"AREA": (50, "sqm")}, LIGHTS="NO")))
    assert lines(est) == {("FALSE_CEILING", "GYPSUM"): round(538.2 * 5_000)}


@pytest.mark.parametrize(
    "measurements,code",
    [
        ({"WIDTH": (0.1, "ft")}, "OUT_OF_BOUNDS"),
        ({"WIDTH": (151, "ft")}, "OUT_OF_BOUNDS"),
        ({"WIDTH": (6, "sqft")}, "INVALID_UNIT"),
        ({"DEPTH": (2, "ft")}, "UNKNOWN_INPUT"),
    ],
)
def test_invalid_measurements(measurements, code):
    with pytest.raises(EstimateError) as err:
        engine.calculate(CARD, req(sel("WARDROBE", "MASTER_BEDROOM", measurements)))
    assert code in {e["code"] for e in err.value.errors}


@pytest.mark.parametrize(
    "selection,code",
    [
        (sel("SAUNA", "LIVING"), "UNKNOWN_PRODUCT"),
        (sel("WARDROBE", "GARAGE"), "UNKNOWN_ROOM"),
        (sel("WARDROBE", "KITCHEN"), "ROOM_NOT_ALLOWED"),
        (sel("WARDROBE", "MASTER_BEDROOM", COLOUR="RED"), "UNKNOWN_OPTION"),
        (sel("WARDROBE", "MASTER_BEDROOM", DOOR="FOLDING"), "INVALID_CHOICE"),
    ],
)
def test_invalid_selections(selection, code):
    with pytest.raises(EstimateError) as err:
        engine.calculate(CARD, req(selection))
    assert [e["code"] for e in err.value.errors] == [code]


def test_instance_limit():
    with pytest.raises(EstimateError) as err:
        engine.calculate(CARD, req(sel("KITCHEN", "KITCHEN"), sel("KITCHEN", "KITCHEN")))
    assert err.value.errors[0]["code"] == "TOO_MANY"


def test_request_schema_is_closed_and_has_no_personal_data():
    for extra in ({"name": "A"}, {"phone": "9999999999"}, {"email": "a@b.c"}):
        with pytest.raises(ValidationError):
            req(wardrobe(), **extra)
    assert set(EstimateRequest.model_fields) == {
        "property_type",
        "home_size",
        "project_kind",
        "city",
        "package",
        "selections",
    }
    with pytest.raises(ValidationError):
        req(*[wardrobe()] * 41)


# --- packages --------------------------------------------------------------------------------------------------------


def test_premium_uses_its_own_rates_and_disabled_packages_are_refused():
    essential = engine.calculate(CARD, req(wardrobe()))
    premium = engine.calculate(CARD, req(wardrobe(), package="PREMIUM"))
    assert lines(premium)[("WARDROBE", "BODY")] == 42 * 130_000 and premium.base_minor > essential.base_minor
    with pytest.raises(EstimateError) as err:
        engine.calculate(CARD, req(wardrobe(), package="LUXURY"))
    assert err.value.errors[0]["code"] == "PACKAGE_UNAVAILABLE"


def test_an_enabled_package_must_price_every_line():
    doc = copy.deepcopy(CARD_DOC)
    doc["packages"]["LUXURY"] = True
    doc["products"][0]["lines"][0]["rates"].pop("LUXURY")
    with pytest.raises(ValidationError, match="no rate for enabled package"):
        ratecard.parse(doc)


# --- Project Preparation & Protection Package -------------------------------------------------------------------------


def test_preparation_is_one_grouped_value_for_customers_and_detailed_for_staff():
    est = engine.calculate(CARD, req(wardrobe()))
    customer = est.customer_view()["project_preparation"]
    assert customer["label"] == "Project Preparation & Protection Package" and customer["amount_minor"] == PREP_2BHK
    assert "components" not in customer and len(customer["inclusions"]) == 6
    assert "MANDATORY" not in json.dumps(est.customer_view()).upper()
    staff = est.staff_view()["project_preparation"]["components"]
    assert sum(c["amount_minor"] for c in staff) == PREP_2BHK
    assert est.base_minor == sum(lines(est).values()) + est.allowance_minor + PREP_2BHK, "never hidden from the total"


def test_preparation_follows_scope_home_size_and_property_type():
    painting_only = engine.calculate(CARD, req(sel("PAINTING", "WHOLE_HOME")))
    assert [c.code for c in painting_only.prep] == ["DEEP_CLEANING"], "only what applies to the selected scope"
    small = engine.calculate(CARD, req(wardrobe(), home_size="1BHK")).prep_minor
    large = engine.calculate(CARD, req(wardrobe(), home_size="4BHK")).prep_minor
    villa = engine.calculate(CARD, req(wardrobe(), property_type="VILLA")).prep_minor
    assert small < PREP_2BHK < large and villa > PREP_2BHK


# --- totals, views and reproducibility ----------------------------------------------------------------------------------


def test_room_subtotals_optional_items_and_total():
    est = engine.calculate(
        CARD, req(wardrobe(), sel("BED", "MASTER_BEDROOM"), sel("PAINTING", "WHOLE_HOME", {"AREA": (2000, "sqft")}))
    )
    view = est.customer_view()
    assert [r["room"] for r in view["rooms"]] == ["MASTER_BEDROOM"]
    assert view["optional_items_minor"] == 2000 * 2_500
    assert est.base_minor == (
        sum(r["amount_minor"] for r in view["rooms"]) + est.allowance_minor + est.prep_minor + est.optional_minor
    )
    assert view["range"]["low_minor"] <= est.base_minor <= view["range"]["high_minor"]


def test_customer_view_never_shows_rates_lines_or_quantities():
    view = engine.calculate(CARD, req(wardrobe(), sel("KITCHEN", "KITCHEN"))).customer_view()

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)

    leaked = {k for k in keys(view)} & {"rate_minor", "lines", "quantity", "components", "base_minor", "uom"}
    assert not leaked
    assert view["title"] == "VEDA SPACES PRELIMINARY BUDGETARY ESTIMATE" and view["disclaimer"].startswith(
        "This is a preliminary"
    )
    assert view["client_scope"] == ["Sink", "Tiles", "Granite", "Taps"] and view["rate_card_version"] == "SYNTHETIC-2"


def test_reproducible():
    r = req(wardrobe(DOOR="SLIDING"), sel("KITCHEN", "KITCHEN"), sel("FALSE_CEILING", "WHOLE_HOME"))
    assert json.dumps(engine.calculate(CARD, r).staff_view(), default=str) == json.dumps(
        engine.calculate(CARD, r).staff_view(), default=str
    )


def test_monotonic_in_size():
    amounts = [
        engine.calculate(CARD, req(sel("WARDROBE", "MASTER_BEDROOM", {"WIDTH": (w, "ft")}))).base_minor
        for w in (3, 6, 9, 12)
    ]
    assert amounts == sorted(amounts) and len(set(amounts)) == 4


def test_timeline_bands_follow_the_upper_estimate():
    small = engine.calculate(CARD, req(wardrobe()))
    assert small.timeline["min_days"] == 70, "below the first band limit"
    huge = engine.calculate(
        CARD,
        req(
            *[
                sel("WARDROBE", r, {"WIDTH": (60, "ft"), "HEIGHT": (9, "ft")})
                for r in ("MASTER_BEDROOM", "BEDROOM_2", "BEDROOM_3")
            ]
            * 2
        ),
    )
    assert huge.high_minor > 350_000_000 and huge.timeline["label"] == "Confirmed after design"


def test_lookup_mapping_and_warranty_follow_the_selection():
    kitchen = engine.calculate(CARD, req(sel("KITCHEN", "KITCHEN")))
    assert kitchen.project_type_code == "MODULAR_KITCHEN"
    assert {w["code"] for w in kitchen.warranty} == {"PLYWOOD", "TANDEMS", "CHANNELS_HINGES", "FREE_SERVICE"}
    home = engine.calculate(CARD, req(sel("KITCHEN", "KITCHEN"), wardrobe(), sel("FALSE_CEILING", "WHOLE_HOME")))
    assert home.project_type_code == "FULL_HOME" and "ELECTRICAL" in {w["code"] for w in home.warranty}
    assert engine.calculate(CARD, req(sel("TV_UNIT", "LIVING"))).project_type_code == "LIVING_DINING"
    note = kitchen.customer_view()["warranty"]["note"]
    assert "do not extend Veda Spaces workmanship" in note


# --- rate card validation --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda d: d["packages"].update(ESSENTIAL=False), "ESSENTIAL must be enabled"),
        (lambda d: d["products"].append(copy.deepcopy(d["products"][0])), "duplicate product codes"),
        (lambda d: d["timeline"].reverse(), "timeline"),
        (lambda d: d["products"][1]["inputs"][0]["typical"].update(DEFAULT=199), "outside bounds"),
        (lambda d: d["products"][1]["lines"][0]["quantity"].update(input="DEPTH"), "unknown input"),
        (lambda d: d["ranges"]["typical"].update(low_pct=1), "at least as wide"),
        (lambda d: d.update(salesperson="x"), "Extra inputs"),
        (lambda d: d["project_preparation"][0]["amounts"].update(HUGE=1), "approved home sizes"),
        (lambda d: d["project_preparation"].append(dict(d["project_preparation"][0], code="SOFT_CLOSE")), "among"),
        (lambda d: d["custom_features_allowance"].update(low_pct=20, high_pct=10), "must not be below"),
        (lambda d: d.pop("custom_features_allowance"), "custom_features_allowance"),
    ],
)
def test_invalid_rate_cards_are_refused(mutate, message):
    doc = copy.deepcopy(CARD_DOC)
    mutate(doc)
    with pytest.raises(ValidationError, match=message):
        ratecard.parse(doc)


def test_a_home_size_without_approved_preparation_amounts_is_not_offered():
    doc = copy.deepcopy(CARD_DOC)
    for comp in doc["project_preparation"]:
        comp["amounts"] = {"3BHK": comp["amounts"]["3BHK"]}
    card = ratecard.parse(doc)
    assert card.available_home_sizes() == ("3BHK",)
    with pytest.raises(EstimateError) as err:
        engine.calculate(card, req(wardrobe(), home_size="2BHK"))
    assert err.value.errors[0]["code"] == "HOME_SIZE_UNAVAILABLE"
    assert engine.calculate(card, req(wardrobe(), home_size="3BHK")).prep_minor > 0


# --- Custom Features Allowance and hardware (ADR-012 D5, D9) ----------------------------------------------------------


def test_allowance_is_an_explicit_component_of_the_estimate():
    est = engine.calculate(CARD, req(wardrobe(), sel("KITCHEN", "KITCHEN")))
    work = sum(ln.amount_minor for ln in est.lines)
    assert est.allowance_basis_minor == work
    assert (est.allowance_low_minor, est.allowance_high_minor) == (round(work * 0.05), round(work * 0.15))
    customer = est.customer_view()["custom_features_allowance"]
    assert customer == {
        "label": "Custom Features Allowance",
        "description": engine.ALLOWANCE_DESCRIPTION,
        "low_minor": est.allowance_low_minor,
        "high_minor": est.allowance_high_minor,
    }, "shown as its own range; the percentages and the basis stay internal"
    staff = est.staff_view()["custom_features_allowance"]
    assert staff["low_pct"] == 5 and staff["high_pct"] == 15 and staff["basis_minor"] == work
    assert staff["amount_minor"] == est.allowance_minor


def test_allowance_applies_to_room_work_only():
    painting = engine.calculate(CARD, req(sel("PAINTING", "WHOLE_HOME", {"AREA": (2000, "sqft")})))
    assert painting.allowance_basis_minor == 0 and painting.allowance_high_minor == 0, "never on optional items"
    est = engine.calculate(CARD, req(wardrobe(), sel("PAINTING", "WHOLE_HOME", {"AREA": (2000, "sqft")})))
    assert est.allowance_basis_minor == sum(ln.amount_minor for ln in est.lines if not ln.optional)
    doc = copy.deepcopy(CARD_DOC)
    doc["custom_features_allowance"] = {"low_pct": 0, "high_pct": 0, "applies_to": ["CEILING"]}
    none = engine.calculate(ratecard.parse(doc), req(wardrobe()))
    assert none.allowance_minor == 0 and none.base_minor == sum(lines(none).values()) + none.prep_minor


def test_soft_close_hardware_is_in_the_products_not_the_package():
    assert [c.code for c in CARD.project_preparation] == [
        "FLOOR_PROTECTION",
        "PLY_PROTECTION",
        "FREIGHT",
        "DEBRIS",
        "DEEP_CLEANING",
        "PEST_CONTROL",
    ]
    est = engine.calculate(
        CARD, req(wardrobe(), sel("KITCHEN", "KITCHEN"), sel("TV_UNIT", "LIVING", {"WIDTH": (7, "ft")}, STYLE="BOX"))
    )
    hardware = {(ln.product, ln.code) for ln in est.lines if ln.code.startswith("SOFT_CLOSE")}
    assert {p for p, _ in hardware} == {"WARDROBE", "KITCHEN", "TV_UNIT"}
    assert ("TV_UNIT", "SOFT_CLOSE_STORAGE") not in hardware, "only the shutters that exist"
    sliding = engine.calculate(CARD, req(wardrobe(DOOR="SLIDING")))
    assert ("WARDROBE", "SOFT_CLOSE") not in lines(sliding), "sliding doors carry their channel, not hinges"
    assert "hardware" not in est.customer_view()["project_preparation"]["description"]


def test_a_full_home_fits_in_one_request():
    bedrooms = ("MASTER_BEDROOM", "BEDROOM_2", "BEDROOM_3")
    selections = [sel("KITCHEN", "KITCHEN"), sel("UTILITY", "UTILITY"), sel("POOJA_UNIT", "DINING")]
    selections += [sel("TV_UNIT", "LIVING"), sel("VENEER_ACCENTS", "LIVING", STYLE="BEADING")]
    selections += [sel("CEILING_PROFILE_LIGHTING", "WHOLE_HOME"), sel("FALSE_CEILING", "WHOLE_HOME")]
    for room in bedrooms:
        selections += [sel("WARDROBE", room), sel("BED", room), sel("VANITY_UNIT", room), sel("WINDOW_SEATING", room)]
        selections += [sel("STORAGE_BOXES", room, TYPE="BEDSIDE_TABLE"), sel("STORAGE_BOXES", room)]
        selections += [sel("FEATURE_WALL", room, FINISH="WALLPAPER"), sel("STUDY_UNIT", room)]
    selections += [sel("PAINTING", "WHOLE_HOME"), sel("ELECTRICAL", "WHOLE_HOME")]
    assert len(selections) == 33
    est = engine.calculate(CARD, req(*selections, home_size="3BHK"))
    assert est.low_minor < est.base_minor < est.high_minor and est.allowance_minor > 0
