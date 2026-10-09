"""ADR-013: the catalog-driven estimator (V3) — lifecycle, four-eyes, releases, the vertical slice, public API, media,
rollback, import and V2/V3 equivalence.

Synthetic data only: the synthetic rate card (tests/fixtures) and the generated slice (veda.modules.catalog.seed).
Promise owners in tests are role placeholders, never people.
"""

import base64
import copy
import io
import json
from pathlib import Path

import pytest
import sqlalchemy as sa

from tests.support.dbh import rows
from veda.kernel import db
from veda.kernel.context import ActorContext, actor, system_context
from veda.modules.catalog import compile as catalog_compile
from veda.modules.catalog import importexport, media, migrate_v2, seed, service
from veda.modules.catalog.models import CatalogConfiguration, CatalogRecord, CatalogRelease
from veda.modules.estimator import engine
from veda.modules.estimator import service as estimator_service
from veda.modules.estimator.models import BudgetEstimate, EstimatorRateCard

CARD_DOC = json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-rate-card.json").read_text())
ON = pytest.mark.settings(catalog_estimator_enabled=True)
SITE = "http://localhost:8000"
GOVERNED = {"owner": "Procurement lead (role, test)", "backup": "Projects lead (role, test)",
            "quotation_mapping": "Hardware line", "verification": "Site handover checklist (test)",
            "warranty_source": "Manufacturer terms (test)", "status": "OPERATIONALLY_CONFIRMED",
            "confirmed_on": "2026-10-01"}  # fmt: skip
SLICE = {"home": "slice.apartment-3bhk", "package": "slice.essential", "project_kind": "NEW_HOME"}


def as_user(uid):
    return actor(ActorContext(actor_id=uid, via="API"))


def tx(uid, fn, *args, **kw):
    with as_user(uid), db.unit_of_work(write=True) as s:
        return fn(s, *args, **kw)


def pricing_records():
    return [r for r in migrate_v2.records(CARD_DOC) if r[0] == "pricing"]


@pytest.fixture
def people(factory):
    a, b = factory.user("FOUNDER"), factory.user("FOUNDER")
    return a.id, b.id


def seed_slice(author, *, governed=True):
    def run(s):
        seed.apply(s)
        for kind, key, doc in pricing_records():
            service.create_record(s, kind, key, doc)
        if governed:
            row = service.versions(s, "copy", "copy.soft-close.promise")[-1]
            doc = copy.deepcopy(row.document)
            doc["governance"] = GOVERNED
            service.update_draft(s, row.id, doc)

    tx(author, run)


def approve_all(author, reviewer):
    def ids(s, status):
        return [r.id for r in s.execute(sa.select(CatalogRecord).where(CatalogRecord.status == status)).scalars()]

    with as_user(author), db.unit_of_work(write=True) as s:
        for rid in ids(s, "DRAFT"):
            service.submit(s, rid)
    with as_user(reviewer), db.unit_of_work(write=True) as s:
        for rid in ids(s, "IN_REVIEW"):
            service.approve_record(s, rid)


def release(author, approver, code="SLICE-1"):
    rel = tx(author, service.create_release, code)
    report = tx(author, service.validate_release, rel.id)
    assert report["ok"], report["errors"]
    tx(approver, service.approve_preview, rel.id)
    tx(author, service.submit_release, rel.id)
    tx(approver, service.approve_release, rel.id, "Owner approval 2026-10-09 (synthetic test release)")
    tx(author, service.activate_release, rel.id)
    return rel.id


def live_slice(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    return release(a, b)


def public_estimate(api, configuration):
    return api.post("/api/v1/public/catalog/estimates", {"configuration": configuration, "turnstile_token": "ok-token"},
                    anonymous=True, headers={"Origin": SITE})  # fmt: skip


def living(**room):
    return {**SLICE, "rooms": [{"room": "living-room", **room}]}


# --- lifecycle and four-eyes -----------------------------------------------------------------------------------------
def test_records_are_versioned_and_only_drafts_change(people):
    a, b = people
    doc = {"name": "Apartment", "code": "APARTMENT"}
    row = tx(a, service.create_record, "property_type", "apartment", doc)
    assert row.record_version == 1 and row.status == "DRAFT"
    with pytest.raises(service.CatalogError, match="open draft"):
        tx(a, service.create_record, "property_type", "apartment", doc)
    tx(a, service.submit, row.id)
    with pytest.raises(service.CatalogError, match="only a DRAFT is edited"):
        tx(a, service.update_draft, row.id, {**doc, "name": "Flat"})
    with pytest.raises(service.CatalogError, match="four-eyes"):
        tx(a, service.approve_record, row.id)
    tx(b, service.approve_record, row.id)
    v2 = tx(a, service.new_version, "property_type", "apartment")
    assert v2.record_version == 2 and v2.status == "DRAFT"
    with db.unit_of_work(write=False) as s:
        assert [r.status for r in service.versions(s, "property_type", "apartment")] == ["APPROVED", "DRAFT"]


def test_reject_needs_a_reason_and_returns_to_draft(people):
    a, b = people
    row = tx(a, service.create_record, "product_family", "tv-units", {"name": "TV units", "category": "media_units"})
    tx(a, service.submit, row.id)
    with pytest.raises(service.CatalogError, match="say why"):
        tx(b, service.reject_record, row.id, "")
    assert tx(b, service.reject_record, row.id, "Use the family name from the brochure").status == "DRAFT"


@pytest.mark.parametrize(
    "kind,doc,match",
    [
        ("product_family", {"name": "TV units with a lifetime warranty", "category": "x1"}, "promise"),
        ("product_family", {"name": "TV units from ₹40,000", "category": "x1"}, "amount of money"),
        ("product_family", {"name": "TV units", "category": "x1", "colour": "red"}, "Extra inputs"),
        ("copy", {"statement": "Branded hinges included", "category": "hardware", "promise": False}, "promise"),
        ("copy", {"statement": "Soft-close hinges", "category": "hardware"}, "governance"),
        (
            "media",
            {
                "type": "EXTERNAL_EMBED",
                "title": "Tour",
                "alt": "A tour",
                "embed_url": "https://evil.example/x",
                "rights": {"owner": "x1", "licence": "x1", "usage": "owned"},
            },
            "external embed",
        ),  # fmt: skip
    ],
)
def test_unregistered_promises_and_unsafe_content_are_refused(people, kind, doc, match):
    with pytest.raises(service.CatalogError, match=match):
        tx(people[0], service.create_record, kind, "some-key", doc)


def test_pricing_body_is_validated_by_the_engine_schema(people):
    bad = {"scope": "product", "engine_product": "TV_UNIT", "body": {"code": "TV_UNIT", "label": "TV"}}
    with pytest.raises(service.CatalogError, match="invalid pricing"):
        tx(people[0], service.create_record, "pricing", "engine.tv-unit", bad)


# --- releases --------------------------------------------------------------------------------------------------------
def test_release_validation_fails_closed_on_an_unconfirmed_promise(people):
    a, b = people
    seed_slice(a, governed=False)
    approve_all(a, b)
    rel = tx(a, service.create_release, "SLICE-0")
    report = tx(a, service.validate_release, rel.id)
    assert not report["ok"] and report["checks"]["promises"] == "fail"
    assert any("copy.soft-close.promise" in e for e in report["errors"])
    with pytest.raises(service.CatalogError, match="does not validate"):
        tx(b, service.approve_preview, rel.id)


def test_release_four_eyes_and_full_lifecycle(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    rel = tx(a, service.create_release, "SLICE-1")
    with pytest.raises(service.CatalogError, match="approve the customer preview first"):
        tx(a, service.submit_release, rel.id)
    with pytest.raises(service.CatalogError, match="four-eyes"):
        tx(a, service.approve_preview, rel.id)
    tx(b, service.approve_preview, rel.id)
    tx(a, service.submit_release, rel.id)
    with pytest.raises(service.CatalogError, match="four-eyes"):
        tx(a, service.approve_release, rel.id, "Owner approval 2026-10-09 (synthetic)")
    with pytest.raises(service.CatalogError, match="approval reference"):
        tx(b, service.approve_release, rel.id, "ok")
    tx(b, service.approve_release, rel.id, "Owner approval 2026-10-09 (synthetic)")
    activated = tx(a, service.activate_release, rel.id)
    assert activated.status == "ACTIVE"
    with db.unit_of_work(write=False) as s:
        card = s.get(EstimatorRateCard, s.get(CatalogRelease, rel.id).rate_card_id)
        assert card.card_version == "CATALOG-SLICE-1" and card.status == "DRAFT", "never the V1/V2 card"
        assert {r.status for r in service.release_records(s, s.get(CatalogRelease, rel.id))} == {"ACTIVE"}


def test_manifest_drift_is_refused(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    rel = tx(a, service.create_release, "SLICE-1")
    with as_user(a), db.unit_of_work(write=True) as s:
        row = service.versions(s, "product", "tv-unit")[-1]
        row.document = {**row.document, "name": "Changed behind the manifest"}
    with pytest.raises(service.CatalogError, match="changed; refusing"):
        _records(a, rel.id)
    assert not tx(a, service.validate_release, rel.id)["ok"], "validation fails closed too"


def _records(uid, release_id):
    with as_user(uid), db.unit_of_work(write=False) as s:
        return service.release_records(s, s.get(CatalogRelease, release_id))


def test_rollback_restores_the_whole_previous_manifest(people):
    a, b = people
    first = live_slice(people)
    tv = tx(a, service.new_version, "product", "tv-unit")
    tx(a, service.update_draft, tv.id, {**tv.document, "description": "A unit for the TV wall, refreshed."})
    approve_all(a, b)
    second = release(a, b, "SLICE-2")
    with db.unit_of_work(write=False) as s:
        assert service.active_release(s).id == second
        assert [r.status for r in service.versions(s, "product", "tv-unit")] == ["RETIRED", "ACTIVE"]
    tx(a, service.rollback)
    with db.unit_of_work(write=False) as s:
        assert service.active_release(s).id == first
        assert [r.status for r in service.versions(s, "product", "tv-unit")] == ["ACTIVE", "RETIRED"]
        assert s.get(CatalogRelease, second).status == "RETIRED"


def test_scheduled_release_activates_only_when_due(people):
    from datetime import timedelta

    from veda.kernel import clock

    a, b = people
    seed_slice(a)
    approve_all(a, b)
    rel = tx(a, service.create_release, "SLICE-1")
    tx(b, service.approve_preview, rel.id)
    tx(a, service.submit_release, rel.id)
    tx(b, service.approve_release, rel.id, "Owner approval 2026-10-09 (synthetic)")
    with db.unit_of_work(write=False) as s:
        at = db.tx_time(s) + timedelta(hours=2)
    tx(a, service.schedule_release, rel.id, at)
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        assert service.run_scheduled(s) == []
    clock.advance(timedelta(hours=3))
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        assert service.run_scheduled(s) == ["SLICE-1"]


def test_v1_v2_activate_card_refuses_compiled_catalog_cards(people):
    live_slice(people)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        with pytest.raises(estimator_service.CardError, match="compiled catalog card"):
            estimator_service.activate_card(s, "CATALOG-SLICE-1", "Owner approval reference (synthetic)")


# --- the vertical slice through the public API -----------------------------------------------------------------------
def test_public_catalog_is_disabled_by_default(api, people):
    live_slice(people)
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 404
    assert public_estimate(api, living()).status == 404


@ON
def test_public_catalog_view_has_no_rates_or_staff_data(api, people):
    live_slice(people)
    r = api.get("/api/v1/public/catalog", anonymous=True)
    assert r.status == 200
    text = json.dumps(r.data)
    for forbidden in ("rate", "rates", "amount_minor", "staff_note", "warranty_source", "governance", "rights",
                      "pricing", "UNASSIGNED"):  # fmt: skip
        assert f'"{forbidden}"' not in text, forbidden
    sources = {m["objects"]["source"] for m in rows(sa.select(CatalogRecord.document).where(CatalogRecord.kind == "media"))
               if m.get("objects", {}).get("source")}  # fmt: skip
    assert sources and not any(sha in text for sha in sources), "private sources are never exposed"
    tv = r.data["product"]["tv-unit"]
    assert [v["key"] for v in tv["variants"]] == ["panelled", "box"]
    assert r.data["media"]["img.tv-laminate"]["label"] == "Illustrative example"
    assert r.data["extra"]["feature-wall"]["what_is_this"]


@ON
def test_vertical_slice_estimate_and_snapshot(api, people):
    live_slice(people)
    base = public_estimate(api, living())
    assert base.status == 201, base
    ref = base.data["configuration_reference"]
    snap = rows(sa.select(CatalogConfiguration))[0]
    assert snap.configuration_reference == ref and snap.estimate_id
    for kind, key in (("product", "tv-unit"), ("room_template", "living-room"), ("material", "laminate.matte"),
                      ("copy", "copy.laminate"), ("media", "img.living-room"), ("package", "slice.essential"),
                      ("home_config", "slice.apartment-3bhk"), ("rule", "rule.tv-width")):  # fmt: skip
        assert snap.versions[kind][key] == 1, (kind, key)
    assert snap.resolved_request["selections"] == [
        {"room": "LIVING", "product": "TV_UNIT", "measurements": {}, "options": {"STYLE": "PANELLED"}}
    ]
    est = rows(sa.select(BudgetEstimate))[0]
    assert est.rate_card_version == "CATALOG-SLICE-1"

    def low(config):
        r = public_estimate(api, config)
        assert r.status == 201, r
        return r.data["range"]["low_minor"]

    veneer = low(living(products={"tv-unit": {"options": {"panel-finish": "veneer"}}}))
    assert veneer == base.data["range"]["low_minor"], "the synthetic card prices both finishes alike"
    box = low(living(products={"tv-unit": {"variant": "box"}}))
    soft = low(living(products={"tv-unit": {"variant": "box"}}, extras={"tv-soft-close-storage": {}}))
    assert box < soft, "soft-close storage moves the estimate"
    wall = low(living(extras={"feature-wall": {}}))
    assert wall > base.data["range"]["low_minor"], "the feature wall adds to the estimate"
    wide = low(living(products={"tv-unit": {"measurements": {"WIDTH": 18}}}))
    assert wide != base.data["range"]["low_minor"], "measurements refine the estimate later"


@ON
@pytest.mark.parametrize(
    "config,code",
    [
        (living(products={"tv-unit": {"measurements": {"WIDTH": 25}}}), "OUT_OF_RANGE"),
        (living(extras={"tv-soft-close-storage": {}}), "REQUIRES"),
        (living(products={"wardrobe": {}}), "PRODUCT_UNAVAILABLE"),
        (living(products={"tv-unit": {"variant": "floating"}}), "VARIANT_UNAVAILABLE"),
        (living(products={"tv-unit": {"options": {"panel-finish": "marble"}}}), "UNKNOWN_CHOICE"),
        (living(products={"tv-unit": {"removed": True}}), "NOT_REMOVABLE"),
        (living(extras={"jacuzzi": {}}), "EXTRA_UNAVAILABLE"),
        ({**SLICE, "rooms": [{"room": "kitchen"}]}, "ROOM_UNAVAILABLE"),
        ({**SLICE, "package": "luxury", "rooms": [{"room": "living-room"}]}, "PACKAGE_UNAVAILABLE"),
    ],
)
def test_unsupported_combinations_fail_closed(api, people, config, code):
    live_slice(people)
    r = public_estimate(api, config)
    assert r.status == 422 and code in {e["code"] for e in r.json["errors"]}, r
    assert not rows(sa.select(CatalogConfiguration))


@ON
def test_public_media_serves_only_active_clean_variants(api, people):
    live_slice(people)
    doc = rows(sa.select(CatalogRecord.document).where(CatalogRecord.record_key == "img.tv-laminate"))[0]
    variant, source = doc["objects"]["variants"]["thumb"], doc["objects"]["source"]
    r = api.get(f"/api/v1/public/catalog/media/{variant}", anonymous=True)
    assert r.status == 200 and r.headers["Content-Type"] == "image/webp"
    assert "immutable" in r.headers["Cache-Control"] and r.headers["X-Content-Type-Options"] == "nosniff"
    assert api.get(f"/api/v1/public/catalog/media/{source}", anonymous=True).status == 404
    assert api.get(f"/api/v1/public/catalog/media/{'0' * 64}", anonymous=True).status == 404


# --- staff API and permissions ---------------------------------------------------------------------------------------
def test_staff_permissions_least_privilege(api, factory, people):
    live_slice(people)
    admin, sales = factory.user("ADMIN"), factory.user("SALES")
    t_admin, t_sales = factory.login(api, admin, set_default=False), factory.login(api, sales, set_default=False)
    assert api.get("/api/v1/catalog/dashboard", token=t_sales).status == 403
    dash = api.get("/api/v1/catalog/dashboard", token=t_admin)
    assert dash.status == 200 and dash.data["active_release"] == "SLICE-1" and dash.data["unpriced_items"] is None
    listed = api.get("/api/v1/catalog/records", token=t_admin).data
    assert listed and not any(r["kind"] == "pricing" for r in listed), "pricing is invisible without pricing.view"
    created = api.post("/api/v1/catalog/records", {"kind": "product_family", "key": "beds", "document":
                       {"name": "Beds", "category": "beds"}}, token=t_admin)  # fmt: skip
    assert created.status == 403
    factory.grant(admin, "catalog.edit")
    t_admin = factory.login(api, admin, set_default=False)
    created = api.post("/api/v1/catalog/records", {"kind": "product_family", "key": "beds", "document":
                       {"name": "Beds", "category": "beds"}}, token=t_admin)  # fmt: skip
    assert created.status == 201 and created.data["status"] == "DRAFT"
    pricing = api.post("/api/v1/catalog/records", {"kind": "pricing", "key": "engine.x", "document":
                       pricing_records()[1][2]}, token=t_admin)  # fmt: skip
    assert pricing.status == 403, "content editors cannot edit pricing"
    assert api.post(f"/api/v1/catalog/records/{created.data['id']}/submit", token=t_admin).status == 200
    assert api.post(f"/api/v1/catalog/records/{created.data['id']}/approve", {}, token=t_admin).status == 403


def test_founder_preview_and_configuration_reopen(api, factory, people):
    rel = live_slice(people)
    founder = factory.user("FOUNDER")
    token = factory.login(api, founder, set_default=False)
    view = api.get(f"/api/v1/catalog/releases/{rel}", token=token)
    assert view.status == 200 and view.data["validation"]["ok"] and view.data["diff"]["against"] == "SLICE-1"
    preview = api.post(f"/api/v1/catalog/releases/{rel}/preview-estimate", {"configuration": living()}, token=token)
    assert preview.status == 200 and preview.data["request"]["selections"][0]["product"] == "TV_UNIT"


# --- media security --------------------------------------------------------------------------------------------------
def _jpeg_with_exif() -> bytes:
    from PIL import Image

    img = Image.new("RGB", (800, 600), (200, 100, 50))
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"  # Make
    exif[0x8825] = {2: (17, 23, 0)}  # GPS
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_images_are_reencoded_without_metadata(people):
    from PIL import Image

    data = _jpeg_with_exif()
    assert b"SecretCamera" in data
    with as_user(people[0]), db.unit_of_work(write=True) as s:
        up = media.upload(s, data)
        assert set(up.variants) == {"thumb", "mobile", "desktop"}
        for v in up.variants.values():
            blob = media.storage().get(v.storage_key)
            assert b"SecretCamera" not in blob and v.mime_type == "image/webp" and v.scan_status == "CLEAN"
            assert not Image.open(io.BytesIO(blob)).getexif()
        assert up.source.storage_key == f"source/{up.source.object_sha256}", "stored by hash, never by filename"


@pytest.mark.parametrize(
    "data,match",
    [
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "unsupported file type"),
        (b"MZ\x90\x00" + b"\0" * 100, "unsupported file type"),
        (b"\x00\x00\x00\x18ftypmp42" + b"\0" * 100, "transcoder"),
        (b"\xff\xd8\xff\xe0" + b"\0" * 100, "decoded safely"),
        (b"glTF" + b"\x02\x00\x00\x00" + b"\x10\x00\x00\x00" + b"\0" * 4, "truncated"),
    ],
)
def test_unsafe_uploads_are_refused(people, data, match):
    with as_user(people[0]), db.unit_of_work(write=True) as s:
        with pytest.raises(media.MediaError, match=match):
            media.upload(s, data)


def test_glb_with_external_references_is_refused(people):
    glb = seed._glb()
    js_len = int.from_bytes(glb[12:16], "little")
    doc = json.loads(glb[20 : 20 + js_len])
    doc["buffers"][0]["uri"] = "https://example.com/tracker.bin"
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    body = len(js).to_bytes(4, "little") + b"JSON" + js
    bad = b"glTF" + (2).to_bytes(4, "little") + (12 + len(body)).to_bytes(4, "little") + body
    with pytest.raises(media.MediaError, match="external files"):
        media.validate_glb(bad)


def test_without_a_scanner_deployed_media_stays_pending(monkeypatch):
    from veda.modules.catalog import media as m

    class Fake:
        catalog_media_scanner, env = "none", "staging"

    monkeypatch.setattr(m, "settings", lambda: Fake())
    assert m.scan_status(b"x") == "PENDING_SCAN"


def test_media_upload_route_needs_media_permission(api, factory):
    admin = factory.user("ADMIN")
    token = factory.login(api, admin, set_default=False)
    body = {"data_base64": base64.b64encode(_jpeg_with_exif()).decode()}
    assert api.post("/api/v1/catalog/media", body, token=token).status == 403
    factory.grant(admin, "catalog.media.edit")
    token = factory.login(api, admin, set_default=False)
    r = api.post("/api/v1/catalog/media", body, token=token)
    assert r.status == 201 and set(r.data["objects"]["variants"]) == {"thumb", "mobile", "desktop"}


# --- import / export ---------------------------------------------------------------------------------------------------
def test_import_is_a_dry_run_first_and_creates_drafts_only(people):
    a, b = people
    content = "kind,key,document\n" + "\n".join([
        'product_family,beds,"{""name"": ""Beds"", ""category"": ""beds""}"',
        'product_family,beds,"{""name"": ""Beds"", ""category"": ""beds""}"',
        'room_template,bedroom,"{""name"": ""Bedroom"", ""room_code"": ""MASTER_BEDROOM"", ""included"": [{""product"": ""bed"", ""variant"": ""std""}]}"',
        'pricing,engine.bed,"{}"',
    ])  # fmt: skip
    rows_ = importexport.parse_rows(content, "csv")
    with as_user(a), db.unit_of_work(write=False) as s:
        report = importexport.dry_run(s, rows_, can_price=False)
    errs = {r["row"]: r["errors"] for r in report["rows"]}
    assert not report["ok"] and "duplicate" in errs[2][0] and "neither in the file" in errs[3][0]
    assert "pricing.edit" in errs[4][0]
    with as_user(a), db.unit_of_work(write=True) as s, pytest.raises(importexport.ImportError_):
        importexport.apply(s, rows_, can_price=False)
    good = importexport.parse_rows(content.splitlines()[0] + "\n" + content.splitlines()[1], "csv")
    result = tx(a, importexport.apply, good, can_price=False)
    assert result["created"] == [{"kind": "product_family", "key": "beds", "version": 1}]
    assert {r.status for r in rows(sa.select(CatalogRecord))} == {"DRAFT"}
    again = tx(a, importexport.dry_run, good, can_price=False)
    assert again["ok"] and again["rows"][0]["change"] == "unchanged", "re-importing the same file changes nothing"
    changed = [{"kind": "product_family", "key": "beds", "document": {"name": "Beds and cots", "category": "beds"}}]
    blocked = tx(a, importexport.dry_run, changed, can_price=False)
    assert not blocked["ok"] and "open draft" in blocked["rows"][0]["errors"][0]


def test_export_excludes_pricing_without_permission(people):
    live_slice(people)
    with db.unit_of_work(write=False) as s:
        rel = service.active_release(s)
        hidden = json.loads(importexport.export(s, release_id=rel.id, include_pricing=False))
        shown = json.loads(importexport.export(s, release_id=rel.id, include_pricing=True))
    assert not any(r["kind"] == "pricing" for r in hidden["records"])
    assert any(r["kind"] == "pricing" for r in shown["records"]) and hidden["release"] == "SLICE-1"


# --- V2 migration and V2/V3 equivalence ------------------------------------------------------------------------------
def v2_selections(bundle, state):
    """A Python port of estimate-v2.js `selections()` (the request the V2 page sends)."""
    sel = []
    rooms = bundle["rooms_by_size"]["3BHK"]
    for room in rooms:
        r = state["rooms"].get(room["id"], {"on": True, "extras": {}})
        if not r["on"]:
            continue
        chosen = list(room["includes"])
        for x in room["extras"]:
            v = r["extras"].get(x["id"])
            n = (v or 0) if x["count"] else (1 if v else 0)
            chosen += [x["id"]] * n
        for item_id in chosen:
            item = bundle["items"][item_id]
            if not item["product"]:
                continue
            options = dict(item["options"])
            if item_id == "pooja" and state["rooms"].get("pooja", {}).get("extras", {}).get("asta"):
                options["ASTA_CHAKRA"] = "YES"
            measurements = {}
            for f in bundle["refine"]:
                v = state["measures"].get(f"{f['room']}:{f['item']}")
                if f["room"] == room["id"] and f["item"] == item_id and v:
                    measurements[f["input"]] = {"value": float(v), "unit": f["unit"]}
            sel.append(
                {"room": room["room"], "product": item["product"], "options": options, "measurements": measurements}
            )
    return sel


def v3_configuration(bundle, state):
    rooms = []
    for room in bundle["rooms_by_size"]["3BHK"]:
        r = state["rooms"].get(room["id"], {"on": True, "extras": {}})
        if not r["on"]:
            continue
        products = {}
        for f in bundle["refine"]:
            v = state["measures"].get(f"{f['room']}:{f['item']}")
            if f["room"] == room["id"] and v:
                products.setdefault(f["item"].replace("_", "-"), {"measurements": {}})["measurements"][f["input"]] = v
        extras = {}
        for x in room["extras"]:
            v = r["extras"].get(x["id"])
            if v:
                extras[x["id"].replace("_", "-")] = {"count": v} if x["count"] else {}
        rooms.append({"room": f"v2.{room['id']}", "products": products, "extras": extras})
    return {"home": "apartment.3bhk", "package": "essential", "project_kind": "NEW_HOME", "rooms": rooms}


STATES = [
    {"rooms": {}, "measures": {}},
    {"rooms": {"pooja": {"on": True, "extras": {"asta": True}}, "living": {"on": True, "extras": {"living_wall": True, "living_beading": True}}},
     "measures": {"kitchen:kitchen": 14, "living:living_tv": 9, "whole:ceiling": 900}},
    {"rooms": {"bed3": {"on": False, "extras": {}}, "master": {"on": True, "extras": {"bedside": 2, "dressing": True}},
               "whole": {"on": True, "extras": {"painting": True}}}, "measures": {"master:wardrobe": 7}},
]  # fmt: skip


def test_v2_migration_round_trips_the_card_and_every_request():
    recs = migrate_v2.records(CARD_DOC)
    from types import SimpleNamespace

    cat = catalog_compile.load([SimpleNamespace(kind=k, record_key=key, record_version=1, document=d)
                                for k, key, d in recs], "V2-EQUIVALENCE", "0" * 64)  # fmt: skip
    compiled = catalog_compile.card_document(cat)
    assert service.sha({**compiled, "version": "x"}) == service.sha({**CARD_DOC, "version": "x"}), "same card"
    card = catalog_compile.compile_card(cat)
    bundle = migrate_v2.bundles()
    for state in STATES:
        v2 = engine.EstimateRequest.model_validate({"property_type": "APARTMENT", "home_size": "3BHK",
                                                    "project_kind": "NEW_HOME", "package": "ESSENTIAL",
                                                    "selections": v2_selections(bundle, state)})  # fmt: skip
        v3 = catalog_compile.resolve(cat, v3_configuration(bundle, state)).request
        assert v3.model_dump(mode="json") == v2.model_dump(mode="json")
        a, b = engine.calculate(card, v2), engine.calculate(card, v3)
        assert (a.low_minor, a.high_minor, a.base_minor) == (b.low_minor, b.high_minor, b.base_minor)


def test_v2_migration_is_idempotent_and_draft_only(people):
    a, _ = people
    first = tx(a, migrate_v2.apply, CARD_DOC)
    assert first["created"] and not first["unchanged"]
    second = tx(a, migrate_v2.apply, CARD_DOC)
    assert not second["created"] and len(second["unchanged"]) == len(first["created"])
    assert {r.status for r in rows(sa.select(CatalogRecord))} == {"DRAFT"}
    assert not rows(sa.select(CatalogRelease)), "nothing is released or activated"


def test_v2_bundles_match_the_v2_page():
    """v2_bundles.json is extracted from estimate-v2.js; this keeps them in step without running Node."""
    import re

    js = (Path(__file__).parents[3] / "app/e2e/site-release/assets/estimate-v2.js").read_text()
    bundle = migrate_v2.bundles()
    for item_id, item in bundle["items"].items():
        m = re.search(rf"^\s+{item_id}: \{{ label: P\.items\.{item_id}, product: (null|'(\w+)')(.*)\}},", js, re.M)
        assert m, item_id
        assert (m.group(2) or None) == item["product"], item_id
        opts = (
            dict(re.findall(r"(\w+): '(\w+)'", re.search(r"options: \{([^}]*)\}", m.group(3)).group(1)))
            if "options" in m.group(3)
            else {}
        )
        assert opts == item["options"], item_id
    for room in bundle["rooms_by_size"]["3BHK"]:
        assert re.search(rf"\{{ id: '{room['id']}', label: U\.rooms\.{room['id']}", js), room["id"]
    for f in bundle["refine"]:
        assert re.search(rf"room: '{f['room']}', item: '{f['item']}', input: '{f['input']}'", js), f
