"""Customer-safety closure, Phase 3: the machine-verified inventory of customer-visible text.

The registry must classify every string-bearing field of every catalog model (found by type, not by a hand list),
staff-only fields must be stripped from the customer view, and the generated inventory document must be current."""

import importlib.util
from pathlib import Path

import pytest
from pydantic import BaseModel

from veda.modules.catalog import compile as catalog_compile
from veda.modules.catalog import kinds, text

API = Path(__file__).resolve().parents[2]


def test_every_text_field_of_every_catalog_model_is_classified():
    found = text.string_fields(kinds.SCHEMAS.values())
    assert found, "the walk found the models' fields"
    assert sorted(found - set(text.FIELD_CLASSES)) == [], "classify each new text field in text.FIELD_CLASSES"
    assert sorted(set(text.FIELD_CLASSES) - found) == [], "remove classifications of fields that no longer exist"


def test_a_new_unclassified_field_fails():
    class Gadget(kinds.Described):
        slogan: str

    assert ("Gadget", "slogan") in text.string_fields([Gadget]) - set(text.FIELD_CLASSES)
    with pytest.raises(KeyError, match="not classified"):
        list(text.visible_text(Gadget(name="Gadget", slogan="Best ever")))


def test_nested_models_are_walked():
    found = text.string_fields([kinds.SCHEMAS["media"], kinds.SCHEMAS["product"]])
    for nested in (("Hotspot", "label"), ("CameraPreset", "label"), ("Rights", "owner"), ("OptionGroup", "name"),
                   ("MeasurementPrompt", "hint"), ("Described", "what_is_this")):  # fmt: skip
        assert nested in found


STRIPPED_PARENTS = {"Governance", "ClaimGovernance", "Rights", "Objects", "Pricing"}  # removed whole from the view


def test_staff_fields_never_reach_the_customer_view():
    for (decl, field), cls in text.FIELD_CLASSES.items():
        if cls == text.STAFF:
            assert field in catalog_compile._STAFF_FIELDS or decl in STRIPPED_PARENTS, (decl, field)
    for parent in ("governance", "claim", "rights", "objects"):
        assert parent in catalog_compile._STAFF_FIELDS


def test_the_inventory_document_is_current():
    spec = importlib.util.spec_from_file_location("inventory", API / "tools/catalog_text_inventory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DOC.read_text() == module.render(), "run: python tools/catalog_text_inventory.py --write"


def test_every_classified_factual_or_statement_field_is_checked():
    """visible_text yields exactly the factual and statement fields, so the text gate covers each one."""
    factual = {k for k, v in text.FIELD_CLASSES.items() if v in (text.FACTUAL, text.STATEMENT)}
    assert ("Described", "name") in factual and ("Copy", "statement") in factual and ("Media", "caption") in factual
    assert all(isinstance(cls, type) and issubclass(cls, BaseModel) for cls in kinds.SCHEMAS.values())
