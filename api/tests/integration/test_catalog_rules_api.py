"""V3 remediation Layers C and D: staff-only visibility (R4), strict rule paths (R5), package and extra pricing with
reconciliation (R6), the allowlisted configuration and its retention (R7), and controlled public validation errors
(R8). Synthetic data only."""

import copy
import json
import re
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.integration.test_catalog import ON, SLICE, living, public_estimate, release, seed_slice, tx
from tests.support.dbh import rows
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.modules.catalog import compile as catalog_compile
from veda.modules.catalog import configure, rules, service
from veda.modules.catalog.models import CatalogConfiguration, CatalogEvent, CatalogRecord, CatalogRelease
from veda.modules.estimator import service as estimator_service
from veda.modules.estimator.models import BudgetEstimate

UUID = re.compile(r"[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-")


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


def edit(uid, kind, key, change):
    with db.unit_of_work(write=False) as s:
        row = service.versions(s, kind, key)[-1]
        rid, doc = row.id, copy.deepcopy(row.document)
    change(doc)
    tx(uid, service.update_draft, rid, doc)


def approve_and_release(a, b, code="SLICE-1", extra_records=()):
    for kind, key, doc in extra_records:
        tx(a, service.create_record, kind, key, doc)
    with db.unit_of_work(write=False) as s:
        ids = [r.id for r in s.execute(sa.select(CatalogRecord).where(CatalogRecord.status == "DRAFT")).scalars()]
    for rid in ids:
        tx(a, service.submit, rid)
    for rid in ids:
        tx(b, service.approve_record, rid)
    return release(a, b, code)


def tv(doc, fn):
    fn(doc)


# --- R4: staff-only visibility ------------------------------------------------------------------------------------
@ON
def test_staff_only_items_are_neither_shown_nor_selectable(api, people):
    a, b = people
    seed_slice(a)

    def hide(doc):
        doc["variants"][1]["visibility"] = "staff"  # the box variant
        doc["variants"][0]["option_groups"][0]["choices"][1]["visibility"] = "staff"  # veneer

    edit(a, "product", "tv-unit", hide)
    edit(a, "extra", "feature-wall", lambda d: d.update(visibility="staff"))
    approve_and_release(a, b, extra_records=[("rule", "rule.staff-wall", {
        "type": "staff_only", "subject": "extra:tv-soft-close-storage"})])  # fmt: skip
    view = api.get("/api/v1/public/catalog", anonymous=True).data
    tvu = view["product"]["tv-unit"]
    assert [v["key"] for v in tvu["variants"]] == ["panelled"]
    assert [c["key"] for c in tvu["variants"][0]["option_groups"][0]["choices"]] == ["laminate"]
    assert "feature-wall" not in view["extra"] and "feature-wall" not in view["room_template"]["living-room"]["extras"]
    assert "tv-soft-close-storage" not in json.dumps(view["rule"])
    for config, code in (
        (living(products={"tv-unit": {"variant": "box"}}), "VARIANT_UNAVAILABLE"),
        (living(products={"tv-unit": {"options": {"panel-finish": "veneer"}}}), "UNKNOWN_CHOICE"),
        (living(extras={"feature-wall": {}}), "EXTRA_UNAVAILABLE"),
    ):
        r = public_estimate(api, config)
        assert r.status == 422 and code in {e["code"] for e in r.json["errors"]}, (config, r.json)
    assert public_estimate(api, living()).status == 201, "visible choices still price"


# --- R5: strict rule paths ------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path,problem",
    [
        ("product:tv-unit#boxx", "has no variant boxx"),
        ("product:tv-unit@panel-finsh=laminate", "has no option group panel-finsh"),
        ("product:tv-unit#panelled@panel-finish=marble", "has no choice marble"),
        ("product:tv-units", "no product tv-units"),
        ("extra:feature-wal", "no extra feature-wal"),
        ("room:living", "no room template living"),
    ],
)
def test_misspelled_rule_paths_fail_validation(people, path, problem):
    a, b = people
    seed_slice(a)
    rule = {"type": "excludes", "subject": "extra:feature-wall", "objects": [path]}
    with db.unit_of_work(write=False) as s:
        ids = [r.id for r in s.execute(sa.select(CatalogRecord).where(CatalogRecord.status == "DRAFT")).scalars()]
    tx(a, service.create_record, "rule", "rule.typo", rule)
    with db.unit_of_work(write=False) as s:
        ids = [r.id for r in s.execute(sa.select(CatalogRecord).where(CatalogRecord.status == "DRAFT")).scalars()]
    for rid in ids:
        tx(a, service.submit, rid)
        tx(b, service.approve_record, rid)
    rel = tx(a, service.create_release, "SLICE-1")
    report = tx(a, service.validate_release, rel.id)
    assert not report["ok"] and report["checks"]["rules"] == "fail"
    assert any(path in e and problem in e for e in report["errors"]), report["errors"]


def test_valid_rule_paths_pass(people):
    a, _ = people
    seed_slice(a)
    with db.unit_of_work(write=False) as s:
        rows_ = [r for r in s.execute(sa.select(CatalogRecord)).scalars()]
        cat = catalog_compile.load(rows_, "T", "0" * 64)
    for path in ("product:tv-unit", "product:tv-unit#box", "product:tv-unit@panel-finish=veneer",
                 "product:tv-unit#panelled@panel-finish=laminate", "extra:feature-wall", "room:living-room"):  # fmt: skip
        assert rules.path_problem(cat, path) is None, path


# --- R6: package and extra pricing; reconciliation ----------------------------------------------------------------
@ON
def test_package_excluded_extras_and_products_are_never_priced(api, people):
    a, b = people
    seed_slice(a)
    edit(a, "package", "slice.essential", lambda d: d.update(excluded_extras=["feature-wall"]))
    approve_and_release(a, b)
    r = public_estimate(api, living(extras={"feature-wall": {}}))
    assert r.status == 422 and "PACKAGE_EXCLUDED" in {e["code"] for e in r.json["errors"]}
    assert not rows(sa.select(BudgetEstimate)) and not rows(sa.select(CatalogConfiguration))


@ON
def test_selected_resolved_priced_and_stored_configurations_reconcile(api, people):
    a, b = people
    seed_slice(a)
    rel = approve_and_release(a, b)
    chosen = living(
        products={"tv-unit": {"measurements": {"WIDTH": 12}}}, extras={"feature-wall": {"measurements": {"WIDTH": 10}}}
    )
    r = public_estimate(api, chosen)
    assert r.status == 201, r.json
    snap = rows(sa.select(CatalogConfiguration))[0]
    est = rows(sa.select(BudgetEstimate))[0]
    with db.unit_of_work(write=False) as s:
        cat = catalog_compile.load_release(s, s.get(CatalogRelease, rel))
        resolved = catalog_compile.resolve(cat, chosen)
        again = catalog_compile.resolve(cat, snap.selections)
    # selected → resolved valid configuration (normal form) → priced request → stored snapshot
    assert snap.selections == resolved.configuration.model_dump(mode="json")
    assert snap.resolved_request == resolved.request.model_dump(mode="json") == est.inputs
    assert again.request == resolved.request and again.configuration == resolved.configuration, "reproducible"
    room = snap.selections["rooms"][0]
    assert room["products"]["tv-unit"] == {"variant": "panelled", "options": {"panel-finish": "laminate"},
                                           "measurements": {"WIDTH": 12.0}, "removed": False}  # fmt: skip
    priced = [(x["room"], x["product"]) for x in snap.resolved_request["selections"]]
    assert priced == [("LIVING", "TV_UNIT"), ("LIVING", "FEATURE_WALL")], "exactly the selected items, nothing else"


# --- R7: allowlisted configuration and retention ----------------------------------------------------------------------
@ON
@pytest.mark.parametrize(
    "config",
    [
        {**SLICE, "city": "Hyderabad", "rooms": [{"room": "living-room"}]},
        {**SLICE, "notes": "call me on 9876543210", "rooms": [{"room": "living-room"}]},
        {**SLICE, "rooms": [{"room": "living-room", "comment": "x"}]},
        {**SLICE, "rooms": [{"room": "living-room", "products": {"tv-unit": {"colour": "teal"}}}]},
        {
            **SLICE,
            "rooms": [
                {"room": "living-room", "products": {"tv-unit": {"options": {"panel-finish": "Laminate please"}}}}
            ],
        },
        {**SLICE, "rooms": [{"room": "living-room", "products": {"call 9876543210": {}}}]},
    ],
)
def test_configurations_refuse_unknown_fields_and_free_text(api, people, config):
    live(people)
    r = public_estimate(api, config)
    assert r.status == 422 and not rows(sa.select(CatalogConfiguration))
    assert "9876543210" not in json.dumps(r.json) and "Hyderabad" not in json.dumps(r.json), "values are never echoed"


def live(people):
    a, b = people
    seed_slice(a)
    return approve_and_release(a, b)


@ON
def test_snapshots_follow_estimate_retention_and_can_be_deleted(api, people, factory):
    live(people)
    refs = [public_estimate(api, living()).json["data"]["configuration_reference"] for _ in range(2)]
    clock.advance(timedelta(days=400))
    from veda.platform import maintenance

    result = maintenance.estimate_retention()
    assert result["configurations_removed"] == 2
    snaps = rows(sa.select(CatalogConfiguration).execution_options(include_deleted=True))
    assert len(snaps) == 2 and all(x.is_deleted and x.deleted_on for x in snaps), (
        "soft-deleted (audited), not silently dropped"
    )
    events = rows(sa.select(CatalogEvent).where(CatalogEvent.event_type == "CONFIGURATION_PURGED"))
    assert sorted(e.detail["reference"] for e in events) == sorted(refs)


@ON
def test_a_configuration_deletion_request(api, people, factory):
    live(people)
    ref = public_estimate(api, living()).json["data"]["configuration_reference"]
    admin = factory.user("FOUNDER")
    token = factory.login(api, admin, set_default=False)
    assert api.get(f"/api/v1/catalog/configurations/{ref}", token=token).status == 200
    short = api.delete(f"/api/v1/catalog/configurations/{ref}", {"note": "no"}, token=token)
    assert short.status == 422
    gone = api.delete(f"/api/v1/catalog/configurations/{ref}", {"note": "Customer asked us to delete it"}, token=token)
    assert gone.status == 204
    assert api.get(f"/api/v1/catalog/configurations/{ref}", token=token).status == 404
    assert rows(sa.select(BudgetEstimate)), "the estimate keeps its own snapshots"


# --- R8: controlled public validation errors ----------------------------------------------------------------------
MALFORMED = [
    None, [], "living-room", 42, True, {}, {"home": None}, {"home": 7, "package": [], "rooms": "all"},
    {**SLICE, "rooms": []}, {**SLICE, "rooms": [None]}, {**SLICE, "rooms": [[]]}, {**SLICE, "rooms": [{"room": 5}]},
    {**SLICE, "rooms": [{"room": "living-room", "products": []}]},
    {**SLICE, "rooms": [{"room": "living-room", "products": {"tv-unit": "panelled"}}]},
    {**SLICE, "rooms": [{"room": "living-room", "products": {"tv-unit": {"measurements": {"WIDTH": "12"}}}}]},
    {**SLICE, "rooms": [{"room": "living-room", "products": {"tv-unit": {"measurements": {"WIDTH": -1}}}}]},
    {**SLICE, "rooms": [{"room": "living-room", "products": {"tv-unit": {"measurements": {"WIDTH": 1e309}}}}]},
    {**SLICE, "rooms": [{"room": "living-room", "products": {"tv-unit": {"removed": "yes"}}}]},
    {**SLICE, "rooms": [{"room": "living-room", "extras": {"feature-wall": {"count": 0}}}]},
    {**SLICE, "rooms": [{"room": "living-room", "extras": {"feature-wall": {"count": 1.5}}}]},
    {**SLICE, "rooms": [{"room": "living-room"}] * 25},
    {**SLICE, "project_kind": "MANSION", "rooms": [{"room": "living-room"}]},
    {**SLICE, "home": "../../etc/passwd", "rooms": [{"room": "living-room"}]},
    {**SLICE, "rooms": [{"room": "living-room", "products": {f"p{i:02d}x": {} for i in range(30)}}]},
]  # fmt: skip


@ON
@pytest.mark.parametrize("config", MALFORMED, ids=range(len(MALFORMED)))
def test_malformed_public_payloads_get_safe_4xx(api, people, config):
    live(people)
    r = public_estimate(api, config)
    assert 400 <= r.status < 500, (config, r.status)
    text = json.dumps(r.json)
    for leak in ("Traceback", "pydantic", "input_value", "rate", "staff_note", "record_id", "sqlalchemy"):
        assert leak not in text, leak
    assert not UUID.search(text), "no internal identifiers"
    assert all(set(e) <= {"field", "code", "message"} for e in r.json.get("errors", []))


@ON
def test_non_json_and_wrong_types_on_public_routes_are_4xx(api, people):
    live(people)
    raw = api.call("POST", "/api/v1/public/catalog/estimates", raw_body=b"{not json", anonymous=True,
                   headers={"Origin": "http://localhost:8000"})  # fmt: skip
    assert raw.status == 400
    arr = api.call("POST", "/api/v1/public/catalog/estimates", raw_body=b"[1,2]", anonymous=True,
                   headers={"Origin": "http://localhost:8000"})  # fmt: skip
    assert 400 <= arr.status < 500
    assert api.get(f"/api/v1/public/catalog/media/{'z' * 64}", anonymous=True).status == 404


def test_estimator_v1_v2_untouched_by_configuration_schema(app):
    """V2 requests still go through the engine model directly; the V3 schema is not on that path."""
    assert "configuration" not in estimator_service.create_public.__code__.co_varnames
    with actor(system_context("CLI")), db.unit_of_work(write=False) as s:
        assert configure.purge(s, dry_run=True) == 0
