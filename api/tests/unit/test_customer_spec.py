"""ADR-012 T9: the customer-facing specification schema refuses amounts, pricing words, durations and personal data."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from veda.modules.estimator import customer_spec

REPO = Path(__file__).resolve().parents[3]
SYNTHETIC = json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-customer-spec.json").read_text())
ESSENTIAL = json.loads(
    (REPO / "docs/implementation/estimator/specifications/essential-specification-v1.0.json").read_text()
)


def test_the_committed_specifications_are_valid():
    assert customer_spec.parse(SYNTHETIC).spec_code == "SYNTHETIC-ESSENTIAL-1.0"
    essential = customer_spec.parse(ESSENTIAL)
    assert essential.spec_code == "ESSENTIAL-1.0" and len(essential.categories) == 9
    for c in essential.categories:  # T3: requirement, examples, equivalent rule and final-selection checkpoint
        assert c.requirement and c.equivalent_rule and c.final_selection


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
