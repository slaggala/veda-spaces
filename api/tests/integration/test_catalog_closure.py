"""V3 pre-activation closure: badges and every customer-visible text path (R2/R3), rollback lineage (R9), 3D safe
disablement (R12), market-condition rules, and soft-close enforcement through the real release gate. Synthetic only."""

import copy
import json
import re

import pytest
import sqlalchemy as sa

from tests.integration.test_catalog import (
    ON,
    approve_all,
    living,
    pricing_records,
    public_estimate,
    release,
    seed_slice,
    tx,
)  # fmt: skip
from tests.support.dbh import rows
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.catalog import compile as catalog_compile
from veda.modules.catalog import kinds, media, seed, service
from veda.modules.catalog.models import (
    CatalogConfiguration,
    CatalogEvent,
    CatalogMediaObject,
    CatalogRecord,
    CatalogRelease,
)
from veda.modules.estimator.models import BudgetEstimate


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


def latest(kind, key):
    with db.unit_of_work(write=False) as s:
        row = service.versions(s, kind, key)[-1]
        return row.id, copy.deepcopy(row.document), row.status


def change(uid, kind, key, fn):
    rid, doc, status = latest(kind, key)
    if status != "DRAFT":
        rid = tx(uid, service.new_version, kind, key).id
    fn(doc)
    tx(uid, service.update_draft, rid, doc)


# --- R2/R3: badges ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", ["Lifetime warranty", "Guaranteed lowest price", "Free installation", "Best seller",
                                  "Premium pick", "Certified quality", "Delivery included", "#1 choice"])  # fmt: skip
def test_badge_claims_cannot_be_registered_without_governance(text):
    with pytest.raises(ValueError):
        kinds.parse("copy", {"statement": text, "category": "badge", "promise": False})


def test_free_form_badge_text_is_refused():
    with pytest.raises(ValueError):
        kinds.parse("package", {"name": "Essential", "engine_package": "ESSENTIAL", "public_summary": "copy.x1",
                                "badge": "Lifetime warranty"})  # fmt: skip


def test_a_badge_must_be_a_badge_copy_record_in_the_release(people):
    a, b = people
    seed_slice(a)
    change(a, "package", "slice.essential", lambda d: d.update(badge="copy.disclaimer"))
    approve_all(a, b)
    rel = tx(a, service.create_release, "SLICE-B")
    report = tx(a, service.validate_release, rel.id)
    assert any("badge must be a badge copy record" in e for e in report["errors"])


def test_an_unconfirmed_promise_badge_blocks_release(people):
    a, b = people
    seed_slice(a)
    tx(a, service.create_record, "copy", "copy.badge.warranty", {
        "statement": "Manufacturer’s warranty", "category": "badge", "promise": True, "matrix_row": "manufacturer_warranty",
        "applies_to": {"packages": ["slice.essential"]},
        "governance": {"owner": "UNASSIGNED", "backup": "UNASSIGNED", "quotation_mapping": "x1", "verification": "x1",
                       "warranty_source": "x1"}})  # fmt: skip
    change(a, "package", "slice.essential", lambda d: d.update(badge="copy.badge.warranty"))
    approve_all(a, b)
    rel = tx(a, service.create_release, "SLICE-W")
    report = tx(a, service.validate_release, rel.id)
    assert not report["ok"] and any("copy.badge.warranty" in e for e in report["errors"])
    with pytest.raises(service.CatalogError, match="does not validate"):
        tx(b, service.approve_preview, rel.id)


@ON
def test_only_approved_badge_copy_reaches_the_public_payload(api, people):
    a, b = people
    seed_slice(a)
    tx(a, service.create_record, "copy", "copy.badge.chosen", {
        "statement": "Most chosen", "category": "badge", "promise": False,
        "applies_to": {"packages": ["slice.essential"]},
        "claim": {"category": "popularity", "status": "APPROVED", "source": "Order data (synthetic)",
                  "owner": "Sales lead (role, test)", "effective_from": "2026-10-01"}})  # fmt: skip
    change(a, "package", "slice.essential", lambda d: d.update(badge="copy.badge.chosen"))
    approve_all(a, b)
    release(a, b)
    view = api.get("/api/v1/public/catalog", anonymous=True).data
    assert view["package"]["slice.essential"]["badge"] == "copy.badge.chosen"
    assert view["copy"]["copy.badge.chosen"]["statement"] == "Most chosen"
    for claim in ("Lifetime warranty", "Guaranteed lowest price", "Free installation"):
        assert claim not in json.dumps(view)


@pytest.mark.parametrize(
    "kind,doc",
    [
        ("media", {"type": "EXTERNAL_EMBED", "title": "Tour", "alt": "A tour", "embed_url": "https://player.vimeo.com/v/1",
                   "rights": {"owner": "Lifetime warranty studio", "licence": "x1", "usage": "owned"}}),
        ("media", {"type": "EXTERNAL_EMBED", "title": "Tour", "alt": "A tour", "caption": "Free installation",
                   "embed_url": "https://player.vimeo.com/v/1", "rights": {"owner": "x1", "licence": "x1", "usage": "owned"}}),
        ("product", {"name": "TV unit", "family": "f1", "rooms": ["LIVING"], "default_variant": "va",
                     "variants": [{"key": "va", "name": "A", "engine_product": "TV_UNIT", "option_groups": [
                         {"key": "g1", "name": "Guaranteed finish", "default": "c1", "choices": [{"key": "c1", "name": "One"}]}]}]}),
        ("product", {"name": "TV unit", "family": "f1", "rooms": ["LIVING"], "default_variant": "va",
                     "variants": [{"key": "va", "name": "A", "engine_product": "TV_UNIT", "measurements": [
                         {"input": "WIDTH", "label": "Width", "unit": "ft", "min": 1, "max": 9, "hint": "Free site visit"}]}]}),
    ],
)  # fmt: skip
def test_short_text_paths_are_promise_checked(kind, doc):
    """The inventory: rights owner shown as attribution, captions, option labels, measurement hints."""
    with pytest.raises(kinds.KindError, match="promise"):
        kinds.parse(kind, doc)


KEYISH = re.compile(
    r"^([a-z][a-z0-9_.-]{1,99}|[A-Z][A-Z0-9_]{1,39}|[0-9a-f]{64}|/api/v1/[\w/.-]+|https://\S+|\d{4}-\d{2}-\d{2})$"
)


def _strings(value, path=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(value, str):
        yield path, value


def test_every_string_in_the_customer_payload_is_governed(people):
    """A guard over the whole public catalog payload: every free string is either a key, code, hash, path or date, a
    promise copy statement (matrix-governed), or free of promise wording."""
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    rel = release(a, b)
    with db.unit_of_work(write=False) as s:
        cat = catalog_compile.load_release(s, s.get(CatalogRelease, rel))
        view = catalog_compile.customer_view(cat)
    promise_statements = {c.statement for c in cat.of(kinds.Copy).values() if c.promise}
    checked = 0
    for path, text in _strings(view):
        if KEYISH.match(text) or text in promise_statements:
            continue
        checked += 1
        assert not kinds._PROMISE_WORDS.search(text), (path, text)
    assert checked > 40


# --- R9: rollback lineage -----------------------------------------------------------------------------------------
def _new_release(a, b, code, desc):
    change(a, "product", "tv-unit", lambda d: d.update(description=desc))
    approve_all(a, b)
    return release(a, b, code)


def _active():
    with db.unit_of_work(write=False) as s:
        r = service.active_release(s)
        return r.id, r.release_code, r.rollback_of_id, [e["record_id"] for e in r.manifest["entries"]]


def _entries(release_id):
    with db.unit_of_work(write=False) as s:
        return [e["record_id"] for e in s.get(CatalogRelease, release_id).manifest["entries"]]


def test_rollback_restores_the_release_active_immediately_before(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    first = release(a, b, "REL-A")
    second = _new_release(a, b, "REL-B", "A unit for the TV wall, second.")
    third = _new_release(a, b, "REL-C", "A unit for the TV wall, third.")
    tx(a, service.rollback, "Restore before C (test)", "REL-C")
    _id, _code, rolled_from, entries = _active()
    assert rolled_from == second and entries == _entries(second), "C rolls back to B, not A"
    assert first != second != third


def test_a_stale_draft_time_target_is_not_used(people):
    """A active → B active → C drafted (while B active) → B replaced by D → C active → rollback C restores D."""
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b, "REL-A")
    _new_release(a, b, "REL-B", "A unit for the TV wall, second.")
    change(a, "product", "tv-unit", lambda d: d.update(description="A unit for the TV wall, third."))
    approve_all(a, b)
    c = tx(a, service.create_release, "REL-C")  # drafted while B is active
    d = _new_release(a, b, "REL-D", "A unit for the TV wall, fourth.")  # B is replaced before C goes live
    tx(b, service.approve_preview, c.id)
    tx(a, service.submit_release, c.id)
    tx(b, service.approve_release, c.id, "Owner approval 2026-10-09 (synthetic)")
    tx(a, service.activate_release, c.id)
    tx(a, service.rollback, "Restore before C (test)", "REL-C")
    _id, _code, rolled_from, entries = _active()
    assert rolled_from == d and entries == _entries(d), "the release active immediately before C (D), not B"


def test_multiple_rollbacks_walk_the_activation_history(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b, "REL-A")
    second = _new_release(a, b, "REL-B", "A unit for the TV wall, second.")
    third = _new_release(a, b, "REL-C", "A unit for the TV wall, third.")
    first_rb = tx(a, service.rollback, "Restore B (test one)", "REL-C")
    assert _active()[2] == second
    tx(a, service.rollback, "Undo the rollback (test two)", first_rb.release_code)
    assert _active()[2] == third and _active()[3] == _entries(third), "rolling back a rollback restores C"
    assert len({r.release_code for r in rows(sa.select(CatalogRelease))}) == 5, "two new releases; none mutated"


def test_rollback_refuses_when_another_release_became_active(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b, "REL-A")
    _new_release(a, b, "REL-B", "A unit for the TV wall, second.")
    _new_release(a, b, "REL-C", "A unit for the TV wall, third.")  # activated after the admin looked at B
    with pytest.raises(service.CatalogError, match="the active release is REL-C, not REL-B"):
        tx(a, service.rollback, "Roll back B (test)", "REL-B")


def test_concurrent_activation_is_refused(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    first = release(a, b, "REL-A")
    change(a, "product", "tv-unit", lambda d: d.update(description="A unit for the TV wall, second."))
    approve_all(a, b)
    rel = tx(a, service.create_release, "REL-B")
    tx(b, service.approve_preview, rel.id)
    tx(a, service.submit_release, rel.id)
    tx(b, service.approve_release, rel.id, "Owner approval 2026-10-09 (synthetic)")
    with pytest.raises(service.CatalogError, match="active release changed"):
        tx(a, service.activate_release, rel.id, expected_active="someone-else")
    with db.unit_of_work(write=False) as s:
        assert service.active_release(s).id == first


@pytest.mark.parametrize("damage", ["delete-event", "duplicate-event", "wrong-previous", "no-previous"])
def test_missing_or_corrupted_history_fails_closed(people, damage):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    first = release(a, b, "REL-A")
    second = _new_release(a, b, "REL-B", "A unit for the TV wall, second.")
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        event = s.execute(sa.select(CatalogEvent).where(CatalogEvent.release_id == second,
                                                        CatalogEvent.event_type == "RELEASE_ACTIVATED")).scalar_one()  # fmt: skip
        if damage == "delete-event":
            s.execute(sa.delete(CatalogEvent).where(CatalogEvent.id == event.id))
        elif damage == "duplicate-event":
            s.add(CatalogEvent(event_type="RELEASE_ACTIVATED", release_id=second, detail=dict(event.detail)))
        elif damage == "wrong-previous":
            s.execute(sa.update(CatalogEvent).where(CatalogEvent.id == event.id).values(
                detail={**event.detail, "previous_release_id": second}))  # fmt: skip
        else:
            s.execute(sa.update(CatalogEvent).where(CatalogEvent.id == event.id).values(
                detail={**event.detail, "previous_release_id": None}))  # fmt: skip
    with pytest.raises(service.CatalogError, match="refusing|nothing to roll back"):
        tx(a, service.rollback, "Roll back B (test)", "REL-B")
    with db.unit_of_work(write=False) as s:
        assert service.active_release(s).id == second and s.get(CatalogRelease, first).status == "RETIRED"


# --- R12: 3D safely disabled ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("flags", [{}, {"catalog_3d_enabled": True}])
def test_glb_upload_is_refused(people, flags, monkeypatch):
    if flags:
        from veda.config import settings

        monkeypatch.setattr(settings(), "catalog_3d_enabled", True)
    with pytest.raises(media.MediaError, match="3D uploads are disabled"):
        tx(people[0], lambda s: media.upload(s, seed._glb()))
    assert not rows(sa.select(CatalogMediaObject))


def test_a_glb_record_cannot_enter_a_release(people):
    a, b = people
    seed_slice(a)
    tx(a, service.create_record, "media", "model.candidate", {
        "type": "GLB", "title": "TV unit 3D", "alt": "A 3D view", "rights": {"owner": "x1", "licence": "x1", "usage": "owned"},
        "objects": {"variants": {"web": "a" * 64}},
        "three_d": {"model_version": "1", "preview_image": "img.tv-laminate", "fallback_gallery": "gallery.tv-unit"}})  # fmt: skip
    approve_all(a, b)
    rel = tx(a, service.create_release, "SLICE-3D")
    report = tx(a, service.validate_release, rel.id)
    assert report["checks"]["three_d"] == "fail" and any("3D media is disabled" in e for e in report["errors"])


@ON
def test_a_glb_is_never_served_even_by_hash(api, people):
    """A candidate GLB object written around every control (CLEAN, a VARIANT, referenced by the active release's
    media record) is still refused: delivery serves images only."""
    a, b = people
    rel = None
    seed_slice(a)
    approve_all(a, b)
    rel = release(a, b)
    sha = "b" * 64
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.add(CatalogMediaObject(object_sha256=sha, role="VARIANT", media_kind="GLB", variant="web",
                                 mime_type="model/gltf-binary", byte_size=10, storage_key=f"variant/{sha}",
                                 scan_status="CLEAN"))  # fmt: skip
        media_id = next(e["record_id"] for e in s.get(CatalogRelease, rel).manifest["entries"]
                        if e["key"] == "img.tv-laminate")  # fmt: skip
        row = s.get(CatalogRecord, media_id)
        doc = copy.deepcopy(row.document)
        doc["objects"]["variants"]["web"] = sha
        s.execute(sa.update(CatalogRecord).where(CatalogRecord.id == media_id).values(document=doc))
    with db.unit_of_work(write=False) as s:
        assert media.deliverable(s, sha, release=s.get(CatalogRelease, rel)) is None
    assert api.get(f"/api/v1/public/catalog/media/{sha}", anonymous=True).status == 404


def test_gallery_fallback_is_preserved(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    rel = release(a, b)
    with db.unit_of_work(write=False) as s:
        view = catalog_compile.customer_view(catalog_compile.load_release(s, s.get(CatalogRelease, rel)))
    assert "gallery.tv-unit" in view["product"]["tv-unit"]["media"]
    assert not [m for m in view["media"].values() if m["type"] in kinds.THREE_D_TYPES]


# --- market-condition rules -----------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "doc",
    [
        {"type": "hidden_when", "subject": "extra:feature-wall", "condition": {"markets": ["Hyderabad"]}},
        {"type": "requires_consultation", "subject": "product:tv-unit", "condition": {"markets": ["Hyderabad"]}},
        {"type": "unavailable_online", "subject": "product:tv-unit", "condition": {"markets": ["Bengaluru"]}},
        {"type": "available_only_for", "subject": "product:tv-unit", "condition": {"markets": ["Hyderbad"]}},
        {"type": "hidden_when", "subject": "extra:feature-wall", "condition": {"markets": [""]}},
        {"type": "hidden_when", "subject": "extra:feature-wall", "condition": {}},
        {"type": "default_when", "subject": "extra:feature-wall", "condition": {"markets": ["Hyderabad"], "home_sizes": ["3BHK"]}},
        {"type": "hidden_when", "subject": "extra:feature-wall", "condition": {"city": "Hyderabad"}},
        {"type": "hidden_when", "subject": "extra:feature-wall", "condition": {"home_sizes": "3BHK"}},
    ],
)  # fmt: skip
def test_unsupported_or_malformed_market_conditions_are_refused(doc):
    with pytest.raises(ValueError):
        kinds.parse("rule", doc)


def test_market_availability_is_refused():
    with pytest.raises(ValueError, match="market or city"):
        kinds.parse("extra", {"name": "Feature wall", "kind": "room_extra", "add": {"engine_product": "FEATURE_WALL"},
                              "availability": {"markets": ["Hyderabad"]}})  # fmt: skip


@ON
def test_a_market_rule_written_around_validation_makes_v3_unavailable(api, people):
    """Conflicting or unsupported market logic never becomes visible, selectable or priceable: the public catalog
    fails closed (503) instead of evaluating half of it."""
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    rel = release(a, b)
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        rule_id = next(
            e["record_id"] for e in s.get(CatalogRelease, rel).manifest["entries"] if e["key"] == "rule.tv-width"
        )
        s.execute(
            sa.update(CatalogRecord)
            .where(CatalogRecord.id == rule_id)
            .values(
                document={
                    "type": "requires_consultation",
                    "subject": "product:tv-unit",
                    "condition": {"markets": ["Hyderabad"]},
                }
            )
        )
    from veda.modules.catalog import configure

    configure._view_cache.clear()
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 503
    assert public_estimate(api, living()).status == 503
    assert not rows(sa.select(BudgetEstimate))


# --- soft-close: blocked by the release gate, not by a test helper --------------------------------------------------
def _soft_close_everything_but_the_owner(a):
    """Make every other soft-close condition hold: the storage option exists, the extra is customer-visible and offered
    in the room, the copy's own governance is confirmed. Only the matrix row (owner UNASSIGNED) remains BLOCKED."""

    def storage(d):
        d["variants"][1]["option_groups"] = [{"key": "storage", "name": "Storage", "default": "open", "choices": [
            {"key": "open", "name": "Open shelves"},
            {"key": "soft-close", "name": "Closing drawers", "engine_options": {"STYLE": "BOX_STORAGE"}}]}]  # fmt: skip

    change(a, "product", "tv-unit", storage)
    change(a, "extra", "tv-soft-close-storage", lambda d: d.update(visibility="customer", name="Closing drawers",
                                                                   hardware=[], what_is_this="Drawers below the unit."))  # fmt: skip
    change(a, "room_template", "living-room", lambda d: d.update(extras=["feature-wall", "tv-soft-close-storage"]))
    change(a, "copy", "copy.soft-close.promise", lambda d: d["governance"].update(
        owner="Procurement lead (role, test)", backup="Projects lead (role, test)", verification="Checklist (test)",
        warranty_source="Manufacturer terms (test)", status="OPERATIONALLY_CONFIRMED", confirmed_on="2026-10-01"))  # fmt: skip


@ON
def test_soft_close_is_blocked_while_its_promise_owner_is_unassigned(api, people):
    a, b = people
    seed_slice(a)
    _soft_close_everything_but_the_owner(a)
    approve_all(a, b, include_blocked=True)  # nothing held back by the test helper: the real gate decides
    rel = tx(a, service.create_release, "SLICE-SC")
    report = tx(a, service.validate_release, rel.id)
    assert not report["ok"] and report["checks"]["promises"] == "fail"
    assert any("spec.soft_close is BLOCKED" in e for e in report["errors"]), report["errors"]
    with pytest.raises(service.CatalogError, match="does not validate"):
        tx(b, service.approve_preview, rel.id)
    with db.unit_of_work(write=False) as s:
        assert service.active_release(s) is None, "it cannot enter an active release"
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 503, "no public catalog shows it"


@ON
def test_soft_close_never_reaches_the_payload_estimate_or_snapshot(api, people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)  # the corrected slice, as released
    release(a, b)
    view = api.get("/api/v1/public/catalog", anonymous=True).data
    assert "tv-soft-close-storage" not in json.dumps(view) and "soft-close" not in json.dumps(view).lower()
    refused = public_estimate(api, living(extras={"tv-soft-close-storage": {}}))
    assert refused.status == 422, "it cannot be priced"
    ok = public_estimate(api, living())
    assert ok.status == 201
    snap = rows(sa.select(CatalogConfiguration))[0]
    assert "soft-close" not in json.dumps(snap.selections) and "soft-close" not in json.dumps(snap.versions)
    est = rows(sa.select(BudgetEstimate))[0]
    assert all(s["options"].get("STYLE") != "BOX_STORAGE" for s in est.inputs["selections"])
    assert pricing_records()  # the synthetic card is the only pricing used
