"""Canonical customer-copy closure, Phase 7: release-wide validation of the final resolved public payload.

Release validation builds the complete public catalog payload and representative estimate payloads, exactly as the
serialisers build them. It checks every string with the one canonical checker, including the customer text that
lives in the staff-only card.

The payload digest is recorded at preview approval and at release approval, and activation re-checks it: a pricing,
specification, copy or catalog change after approval fails closed. The serialisers repeat the check at runtime
(defence in depth) and refuse to serve a payload that fails it.

Synthetic data only; error messages name fields, never the offending text or any rate."""

import copy

import pytest
import sqlalchemy as sa

from tests.integration.test_catalog import ON, SITE, approve_all, release, seed_slice, tx
from tests.support.dbh import rows
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.catalog import compile as catalog_compile
from veda.modules.catalog import public, service, validation
from veda.modules.catalog.models import CatalogEvent, CatalogRecord, CatalogRelease
from veda.modules.estimator import engine
from veda.modules.estimator.models import BudgetEstimate

KEY = "v3-payload-0123456789abcdef0123456789"


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


def change(uid, kind, key, fn):
    with db.unit_of_work(write=False) as s:
        row = service.versions(s, kind, key)[-1]
        rid, doc = row.id, copy.deepcopy(row.document)
    fn(doc)
    tx(uid, service.update_draft, rid, doc)


def draft_release(people, code="PAY-1"):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    rel = tx(a, service.create_release, code)
    return a, b, rel


def test_the_report_records_the_digest_of_the_checked_public_payload(people):
    a, _b, rel = draft_release(people)
    report = tx(a, service.validate_release, rel.id)
    assert report["ok"], report["errors"]
    assert report["checks"]["public_payload"] == "pass"
    sha = report["compiled"]["public_payload_sha256"]
    assert len(sha) == 64 and tx(a, service.validate_release, rel.id)["compiled"]["public_payload_sha256"] == sha
    with db.unit_of_work(write=False) as s:
        cat = catalog_compile.load_release(s, s.get(CatalogRelease, rel.id))
        configs = validation.representative_configurations(cat)
    assert len(configs) >= 3, "defaults, each extra and each other variant are priced and checked"


def test_estimator_text_with_a_claim_blocks_the_release(people, monkeypatch):
    a, _b, rel = draft_release(people)
    monkeypatch.setattr(engine, "DISCLAIMER", "Our best seller estimate, the cheapest in town.")
    report = tx(a, service.validate_release, rel.id)
    assert not report["ok"] and report["checks"]["public_payload"] == "fail"
    assert any("disclaimer" in e and "claim" in e for e in report["errors"]), report["errors"]
    assert not any("cheapest in town" in e for e in report["errors"]), "the report names fields, not the text"


@pytest.mark.parametrize("leak", ["Supplier rate 1200/sqft", "Rs 1200 per rft", "Our margin is 12 percent",
                                  "Best seller fittings"])  # fmt: skip
def test_customer_text_in_the_staff_only_card_is_governed(people, leak):
    a, b = people
    seed_slice(a)
    change(a, "pricing", "card-settings", lambda d: d["body"].update(exclusions=[*d["body"]["exclusions"], leak]))
    approve_all(a, b)
    rel = tx(a, service.create_release, "PAY-CARD")
    report = tx(a, service.validate_release, rel.id)
    assert not report["ok"] and report["checks"]["public_payload"] == "fail", report["errors"]
    assert any("exclusions" in e for e in report["errors"])
    assert not any("1200" in e for e in report["errors"]), "no rate is printed"


def _approved(people):
    a, b, rel = draft_release(people)
    report = tx(a, service.validate_release, rel.id)
    assert report["ok"], report["errors"]
    tx(b, service.approve_preview, rel.id)
    tx(a, service.submit_release, rel.id)
    tx(b, service.approve_release, rel.id, "Owner approval 2026-10-09 (synthetic test release)")
    return a, b, rel, report["compiled"]["public_payload_sha256"]


def test_approvals_and_activation_record_the_same_payload_digest(people):
    a, _b, rel, sha = _approved(people)
    tx(a, service.activate_release, rel.id)
    found = {e.event_type: (e.detail or {}).get("public_payload_sha256") for e in rows(
        sa.select(CatalogEvent).where(CatalogEvent.release_id == rel.id))}  # fmt: skip
    assert found["RELEASE_PREVIEW_APPROVED"] == found["RELEASE_APPROVED"] == found["RELEASE_ACTIVATED"] == sha


def test_a_payload_change_after_approval_refuses_activation(people, monkeypatch):
    """Estimator text changed after approval (standing in for a pricing, specification or copy change): the payload
    customers would see is not the approved one, so activation fails closed."""
    a, _b, rel, _sha = _approved(people)
    monkeypatch.setattr(engine, "TITLE", "VEDA SPACES INDICATIVE ESTIMATE")
    with pytest.raises(service.CatalogError, match="public payload changed"):
        tx(a, service.activate_release, rel.id)
    with db.unit_of_work(write=False) as s:
        assert s.get(CatalogRelease, rel.id).status == "APPROVED"


def test_a_payload_change_after_preview_refuses_release_approval(people, monkeypatch):
    a, b, rel = draft_release(people)
    assert tx(a, service.validate_release, rel.id)["ok"]
    tx(b, service.approve_preview, rel.id)
    tx(a, service.submit_release, rel.id)
    monkeypatch.setattr(engine, "TITLE", "VEDA SPACES INDICATIVE ESTIMATE")
    with pytest.raises(service.CatalogError, match="public payload changed since the customer preview"):
        tx(b, service.approve_release, rel.id, "Owner approval 2026-10-09 (synthetic test release)")


def _live(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    return release(a, b)


def _post(api, key=KEY):
    config = {"home": "slice.apartment-3bhk", "package": "slice.essential", "project_kind": "NEW_HOME",
              "rooms": [{"room": "living-room"}]}  # fmt: skip
    return api.post("/api/v1/public/catalog/estimates", {"configuration": config, "turnstile_token": "ok-token"},
                    anonymous=True, headers={"Origin": SITE, "Idempotency-Key": key})  # fmt: skip


@ON
def test_the_served_estimate_is_the_strict_public_dto(api, people):
    _live(people)
    r = _post(api)
    assert r.status == 201, r
    assert set(r.data) <= {name for name in public.PublicEstimate.model_fields}
    for dropped in ("v2_copy", "room_details", "warranty", "subject_to", "optional_items_minor", "rate_card_version"):
        assert dropped not in r.data, dropped
    assert "note" not in r.data["project_preparation"] and "component_codes" not in r.data["project_preparation"]
    public.PublicEstimate.model_validate(r.data, strict=False)


@ON
def test_the_serialiser_refuses_a_stored_estimate_whose_text_fails(api, people):
    """Defence in depth: a stored result altered outside the gate (here directly in the database) is not served."""
    _live(people)
    assert _post(api).status == 201
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        row = s.execute(sa.select(BudgetEstimate)).scalar_one()
        result = {**row.result, "exclusions": [*row.result["exclusions"], "B​est seller, 1200/sqft"]}
        s.execute(sa.update(BudgetEstimate).where(BudgetEstimate.id == row.id).values(result=result))
    replay = _post(api)
    assert replay.status == 503 and replay.json["code"] == "ESTIMATOR_UNAVAILABLE"
    assert "1200" not in str(replay.json)


@ON
def test_the_served_catalog_is_checked_before_it_is_cached(api, people, monkeypatch):
    _live(people)
    from veda.modules.catalog import configure

    configure._view_cache.clear()
    real = public.build_catalog

    def tampered(cat):
        dto = real(cat)
        return dto.model_copy(update={"product_family": {k: v.model_copy(update={"name": "Ｂｅｓｔ seller"})
                                                         for k, v in dto.product_family.items()}})  # fmt: skip

    monkeypatch.setattr(public, "build_catalog", tampered)
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 503
    monkeypatch.setattr(public, "build_catalog", real)
    configure._view_cache.clear()
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 200


def test_rows_are_never_rewritten_by_normalisation(people):
    """Normalisation is for comparison only: stored display text keeps its exact characters."""
    a, b = people
    seed_slice(a)
    with db.unit_of_work(write=False) as s:
        before = {r.id: r.document_sha256 for r in s.execute(sa.select(CatalogRecord)).scalars()}
    approve_all(a, b)
    tx(a, service.validate_release, tx(a, service.create_release, "PAY-RO").id)
    with db.unit_of_work(write=False) as s:
        after = {r.id: r.document_sha256 for r in s.execute(sa.select(CatalogRecord)).scalars()}
    assert {k: after[k] for k in before} == before


def test_record_events_audit_the_display_and_canonical_digests(people):
    a, _b = people
    doc = {"name": "TV units", "category": "media_units"}
    rid = tx(a, lambda s: service.create_record(s, "product_family", "audit.family", doc).id)
    with db.unit_of_work(write=False) as s:
        detail = s.execute(sa.select(CatalogEvent.detail).where(CatalogEvent.record_id == rid)).scalar_one()
        stored = s.get(CatalogRecord, rid).document
    digests = detail["text"]["name"]
    from veda.modules.catalog import text

    assert digests == {"display_sha256": text.display_digest("TV units"),
                       "canonical_sha256": text.canonical_digest("TV units")}  # fmt: skip
    assert digests["display_sha256"] != text.display_digest("TV units"), "the display text is audited as stored"
    assert stored["name"] == "TV units", "normalisation never rewrites what was stored"
