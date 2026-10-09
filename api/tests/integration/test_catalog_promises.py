"""V3 remediation Layer E: promise governance (R2, R3) and the vertical slice against Essential Specification 1.1
(R14, H1, H2). Synthetic data; the promise matrix is the packaged ESSENTIAL-1.1 matrix, or a synthetic confirmed one
where a test needs a promise to pass."""

import copy
import json
from pathlib import Path

import pytest

from tests.integration.test_catalog import approve_all, release, seed_slice, tx
from veda.modules.catalog import kinds, migrate_v2, seed, service, validation
from veda.modules.estimator import activation, promise_matrix

REPO = Path(__file__).resolve().parents[3]
SPEC = json.loads((REPO / "docs/implementation/estimator/specifications/essential-specification-v1.1.json").read_text())
PRODUCT = {"name": "TV unit", "family": "tv-units", "rooms": ["LIVING"], "default_variant": "va",
           "variants": [{"key": "va", "name": "Panelled", "engine_product": "TV_UNIT", "materials": ["laminate.matte"]}]}  # fmt: skip


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


# --- R2/R3: promise wording never bypasses governance -------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Ten-year warranty on the carcass",
        "Guaranteed for life",
        "ISI certified boards",
        "Free design visit",
        "Hinges included",
        "Loft excluded",
        "Installation in one day",
        "Delivery to your door",
        "Ready in 45 days",
        "Project timeline of six weeks",
        "BWP grade plywood",
        "Marine plywood shelves",
        "Branded hardware",
        "Hettich channels",
        "After-sales service",
        "Support for every unit",
        "Soft-close shutters",
        "Waterproof base",
    ],
)
def test_promise_wording_is_refused_in_descriptive_text_even_with_materials(text):
    for doc in (
        {**PRODUCT, "description": text},  # the variant names a material: no bypass any more
        {**PRODUCT, "variants": [{**PRODUCT["variants"][0], "name": text}]},
        {"name": "Feature wall", "kind": "room_extra", "add": {"engine_product": "FEATURE_WALL"}, "what_is_this": text,
         "materials": ["laminate.matte"]},
    ):  # fmt: skip
        kind = "product" if "variants" in doc else "extra"
        with pytest.raises(kinds.KindError, match="promise"):
            kinds.parse(kind, doc)
    with pytest.raises(kinds.KindError, match="promise"):
        kinds.parse("copy", {"statement": text, "category": "description", "promise": False})


def test_staff_only_text_is_not_customer_text():
    doc = {**PRODUCT, "variants": [*PRODUCT["variants"], {"key": "vb", "name": "Soft-close storage", "visibility": "staff",
                                                          "engine_product": "TV_UNIT"}]}  # fmt: skip
    kinds.parse("product", doc)  # allowed: no customer ever sees it


def test_a_promise_copy_names_its_matrix_row_and_what_it_applies_to():
    governance = {"owner": "Role", "backup": "Role", "quotation_mapping": "x1", "verification": "x1",
                  "warranty_source": "x1"}  # fmt: skip
    with pytest.raises(ValueError, match="promise-matrix row"):
        kinds.parse(
            "copy", {"statement": "Soft-close TV-unit hardware", "category": "hardware", "governance": governance}
        )
    with pytest.raises(ValueError, match="at least one"):
        kinds.parse("copy", {"statement": "Soft-close TV-unit hardware", "category": "hardware", "governance": governance,
                             "matrix_row": "spec.soft_close", "applies_to": {}})  # fmt: skip


def _promise(statement="Soft-close TV-unit hardware", row="spec.soft_close", status="OPERATIONALLY_CONFIRMED"):
    return {"statement": statement, "category": "hardware", "promise": True, "matrix_row": row,
            "applies_to": {"products": ["tv-unit"], "rooms": ["living-room"]},
            "governance": {"owner": "Procurement lead (role, test)", "backup": "Projects lead (role, test)",
                           "quotation_mapping": "Hardware line", "verification": "Handover checklist (test)",
                           "warranty_source": "Manufacturer terms (test)", "status": status,
                           "confirmed_on": "2026-10-01"}}  # fmt: skip


def _release_with(people, *records, code="SLICE-P"):
    a, b = people
    seed_slice(a)
    for kind, key, doc in records:
        tx(a, service.create_record, kind, key, doc)
    approve_all(a, b)
    rel = tx(a, service.create_release, code)
    return a, b, rel, tx(a, service.validate_release, rel.id)


@pytest.mark.parametrize(
    "doc,problem",
    [
        (_promise(row="spec.nonexistent"), "not linked to a row"),
        (_promise(statement="Soft-close hardware on every unit"), "not registered text"),
        (_promise(), "matrix row spec.soft_close is BLOCKED"),  # the packaged ESSENTIAL-1.1 matrix
    ],
)
def test_release_refuses_unregistered_or_unconfirmed_promises(people, doc, problem):
    _a, _b, _rel, report = _release_with(people, ("copy", "copy.promise-x", doc))
    assert not report["ok"] and any(problem in e for e in report["errors"]), report["errors"]


def test_a_promise_linked_to_a_confirmed_matrix_row_releases(people, monkeypatch):
    confirmed = copy.deepcopy(promise_matrix.load(validation.MATRIX_SPEC))
    for row in confirmed["rows"]:
        if row["id"] == "spec.soft_close":
            row.update(status=promise_matrix.READY, accountable_owner="Procurement lead (role, test)",
                       backup_owner="Projects lead (role, test)", confirmed_on="2026-10-01")  # fmt: skip
    monkeypatch.setattr(validation, "matrix", lambda: confirmed)
    _a, _b, _rel, report = _release_with(people, ("copy", "copy.promise-x", _promise()))
    assert report["ok"], report["errors"]


def test_customer_view_never_shows_specification_fields(people, api):
    from veda.modules.catalog import compile as catalog_compile

    a, b = people
    seed_slice(a)
    approve_all(a, b)
    rel = release(a, b)
    from veda.kernel import db
    from veda.modules.catalog.models import CatalogRelease

    with db.unit_of_work(write=False) as s:
        view = catalog_compile.customer_view(catalog_compile.load_release(s, s.get(CatalogRelease, rel)))
    text = json.dumps(view)
    for field in ('"grade"', '"thickness"', '"brands"', '"warranty_source"', '"governance"', '"matrix_row"'):
        assert field not in text, field
    assert "hinge.soft-close" not in view["hardware"], "staff-only hardware is not shown"


# --- R14/H1: no silent reuse of one choice's price for another ----------------------------------------------------
def test_choices_priced_alike_need_a_decision(people):
    a, b = people
    seed_slice(a)
    from veda.kernel import db

    with db.unit_of_work(write=False) as s:
        rule = service.versions(s, "rule", "rule.veneer-consultation")[-1].id
    tx(a, service.archive_record, rule)  # veneer no longer consultation-only
    approve_all(a, b)
    rel = tx(a, service.create_release, "SLICE-V")
    report = tx(a, service.validate_release, rel.id)
    assert any("laminate, veneer price identically" in e for e in report["errors"]), report["errors"]


# --- Essential 1.1 applicability of the slice (R14, H1, H2) -------------------------------------------------------
def _lines(category):
    return {line for c in SPEC["categories"] if c["code"] == category for line in json.dumps(c).split('"')
            if line.startswith(("TV_UNIT.", "FEATURE_WALL."))}  # fmt: skip


def test_the_slice_follows_essential_1_1():
    assert "TV_UNIT.PANEL" in _lines("surface"), "laminate wall panelling is an Essential surface line"
    assert "FEATURE_WALL.*" in _lines("decorative"), "the feature wall is decorative: no material promised"
    assert {"TV_UNIT.SOFT_CLOSE", "TV_UNIT.SOFT_CLOSE_STORAGE"} <= _lines("soft_close")
    rows = {r["id"]: r for r in promise_matrix.load("ESSENTIAL-1.1")["rows"]}
    assert rows["spec.soft_close"]["status"] == "BLOCKED", "so soft-close stays out of every release"
    assert "Soft-close TV-unit hardware" in rows["spec.soft_close"]["statements"]
    assert any("Veneer" in s for s in rows["spec.decorative"]["statements"]), "veneer is decided during design"
    assert ("copy", "copy.soft-close.promise") in seed.BLOCKED_FROM_RELEASE
    assert ("extra", "tv-soft-close-storage") in seed.BLOCKED_FROM_RELEASE


def test_the_v2_package_promise_is_registered_matrix_text():
    v2_copy = activation.customer_copy()
    recs = {(k, key): d for k, key, d in migrate_v2.records(json.loads(
        (REPO / "api/tests/fixtures/estimator/synthetic-rate-card.json").read_text()), copy=v2_copy)}  # fmt: skip
    promise = recs[("copy", "package.essential.summary")]
    row = {r["id"]: r for r in promise_matrix.load("ESSENTIAL-1.1")["rows"]}[promise["matrix_row"]]
    assert promise["statement"] in row["statements"]
