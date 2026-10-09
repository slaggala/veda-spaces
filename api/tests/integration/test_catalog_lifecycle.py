"""V3 remediation Layer B: four-eyes over every contributor (R1), rollback as a new release (R9), rejecting a scheduled
release (R10), and import permissions and idempotency (R15). Synthetic data only."""

from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.integration.test_catalog import STAFF, approve_all, live_slice, pricing_records, release, seed_slice, tx
from tests.support.dbh import rows
from veda.kernel import db
from veda.modules.catalog import importexport, service
from veda.modules.catalog.models import CatalogConfiguration, CatalogRecord, CatalogRelease
from veda.modules.estimator.models import BudgetEstimate, EstimatorRateCard

FAMILY = {"name": "TV units", "category": "media_units"}


@pytest.fixture
def staff(factory):
    return [factory.user("FOUNDER").id for _ in range(4)]


def fresh(uid, key="tv-units"):
    return tx(uid, service.create_record, "product_family", key, FAMILY)


# --- R1: four-eyes over every contributor -------------------------------------------------------------------------
def test_creator_who_submits_cannot_self_approve(staff):
    a, b, *_ = staff
    row = fresh(a)
    tx(a, service.submit, row.id)
    with pytest.raises(service.CatalogError, match="four-eyes"):
        tx(a, service.approve_record, row.id)
    assert tx(b, service.approve_record, row.id).status == "APPROVED"


def test_an_editor_cannot_approve_even_when_someone_else_submitted(staff):
    a, b, c, _ = staff
    row = fresh(a)
    tx(b, service.update_draft, row.id, {**FAMILY, "name": "TV and media units"})
    tx(a, service.submit, row.id)
    with pytest.raises(service.CatalogError, match="four-eyes"):
        tx(b, service.approve_record, row.id)  # B edited it, though A submitted and A was the last to touch it
    assert tx(c, service.approve_record, row.id).status == "APPROVED"


def test_an_uninvolved_reviewer_approves(staff):
    a, b, c, d = staff
    row = fresh(a)
    tx(b, service.update_draft, row.id, {**FAMILY, "name": "TV and media units"})
    tx(c, service.submit, row.id)
    for involved in (a, b, c):
        with pytest.raises(service.CatalogError, match="four-eyes"):
            tx(involved, service.approve_record, row.id)
    approved = tx(d, service.approve_record, row.id)
    assert approved.status == "APPROVED" and set(approved.contributors) == {a, b, c}


def test_removing_a_contributor_does_not_open_approval(staff):
    a, b, c, _ = staff
    row = fresh(a)
    tx(b, service.update_draft, row.id, {**FAMILY, "name": "TV and media units"})
    tx(c, service.submit, row.id)
    with db.unit_of_work(write=True) as s:  # a direct write, as an attacker or a bug might do
        s.execute(sa.update(CatalogRecord).where(CatalogRecord.id == row.id).values(contributors=[]))
    with pytest.raises(service.CatalogError, match="four-eyes"):
        tx(b, service.approve_record, row.id)  # the event trail still names B


def test_an_earlier_review_goes_stale_when_the_draft_changes(staff):
    a, b, *_ = staff
    row = fresh(a)
    tx(a, service.submit, row.id)
    rejected = tx(b, service.reject_record, row.id, "Use the brochure name")
    assert rejected.reviewed_by == b
    edited = tx(a, service.update_draft, row.id, {**FAMILY, "name": "TV and media units"})
    assert edited.reviewed_by is None and edited.review_note is None
    tx(a, service.submit, row.id)
    assert tx(b, service.approve_record, row.id).reviewed_by == b


def test_a_release_approver_must_not_have_changed_its_records(staff):
    a, b, c, _ = staff
    seed_slice(a)
    approve_all(a, b)
    rel = tx(c, service.create_release, "SLICE-1")  # C authors the release; A wrote every record in it
    with pytest.raises(service.CatalogError, match="four-eyes"):
        tx(a, service.approve_preview, rel.id)
    tx(b, service.approve_preview, rel.id)  # B only reviewed records: reviewing is not contributing


# --- R9: rollback restores the previous manifest as a new release ---------------------------------------------------
def test_rollback_restores_the_exact_previous_manifest_as_a_new_release(staff, api):
    a, b, *_ = staff
    first = live_slice((a, b))
    with db.unit_of_work(write=False) as s:
        first_row = s.get(CatalogRelease, first)
        first_entries = first_row.manifest["entries"]
        first_activated = first_row.activated_on
        first_card = s.get(EstimatorRateCard, first_row.rate_card_id).document
    estimates_before = [(r.id, r.rate_card_id, r.range_low_minor) for r in rows(sa.select(BudgetEstimate))]
    # A second release changes a product, a rule, pricing, copy and a media mapping.
    with db.unit_of_work(write=False) as s:
        latest = {k: (key, dict(service.versions(s, k, key)[-1].document)) for k, key in (
            ("product", "tv-unit"), ("rule", "rule.tv-width"), ("copy", "copy.laminate"), ("media", "img.tv-laminate"),
            ("pricing", pricing_records()[1][1]))}  # fmt: skip
    for kind, (key, doc) in latest.items():
        new = tx(a, service.new_version, kind, key)
        if kind == "product":
            doc["description"] = "A unit for the TV wall, refreshed."
        elif kind == "rule":
            doc["max"] = 18
        elif kind == "copy":
            doc["statement"] = "A decorative laminate surface on the panel, in a matte finish."
        elif kind == "media":
            doc["caption"] = "Refreshed caption"
        else:
            doc["note"] = "Refreshed pricing note"
        tx(a, service.update_draft, new.id, doc)
    approve_all(a, b)
    second = release(a, b, "SLICE-2")

    restored = tx(a, service.rollback, "Owner asked to restore SLICE-1 (synthetic test)", "SLICE-2")
    with db.unit_of_work(write=False) as s:
        active = service.active_release(s)
        assert active.id == restored.id and active.id not in (first, second), "a new release, not a reset"
        assert active.rollback_of_id == first and active.previous_release_id == second
        assert active.manifest["entries"] == first_entries, "exact previous versions, rules, pricing, copy, media"
        old = s.get(CatalogRelease, first)
        assert (
            old.status == "RETIRED" and old.activated_on == first_activated and old.manifest["entries"] == first_entries
        )
        assert s.get(CatalogRelease, second).status == "RETIRED"
        card = s.get(EstimatorRateCard, active.rate_card_id).document
        assert {**card, "version": "x"} == {**first_card, "version": "x"}, "the same pricing as SLICE-1"
        for kind, (key, _doc) in latest.items():
            statuses = [r.status for r in service.versions(s, kind, key)]
            assert statuses[-2:] == ["ACTIVE", "RETIRED"], (kind, statuses)
    assert [(r.id, r.rate_card_id, r.range_low_minor) for r in rows(sa.select(BudgetEstimate))] == estimates_before


def test_rollback_needs_a_reason_and_a_previous_release(staff):
    a, b, *_ = staff
    live_slice((a, b))
    with pytest.raises(service.CatalogError, match="reason"):
        tx(a, service.rollback, "", "SLICE-1")
    with pytest.raises(service.CatalogError, match="replaced no release"):
        tx(a, service.rollback, "Restore the previous catalog (test)", "SLICE-1")


# --- R10: rejecting a scheduled release ---------------------------------------------------------------------------
def test_rejecting_a_scheduled_release_clears_everything_and_keeps_history(staff):
    a, b, *_ = staff
    seed_slice(a)
    approve_all(a, b)
    rel = tx(a, service.create_release, "SLICE-1")
    tx(b, service.approve_preview, rel.id)
    tx(a, service.submit_release, rel.id)
    tx(b, service.approve_release, rel.id, "Owner approval 2026-10-09 (synthetic)")
    with db.unit_of_work(write=False) as s:
        at = db.tx_time(s) + timedelta(days=1)
    tx(a, service.schedule_release, rel.id, at)
    assert _statuses(rel.id) == {"SCHEDULED"}
    with pytest.raises(service.CatalogError, match="say why"):
        tx(b, service.reject_release, rel.id, "")
    rejected = tx(b, service.reject_release, rel.id, "Hold until the photos are approved")
    assert rejected.status == "DRAFT" and rejected.scheduled_for is None
    assert rejected.approved_by is None and rejected.approval_reference is None and rejected.preview_approved_by is None
    assert _statuses(rel.id) == {"APPROVED"}, "no record is left SCHEDULED"
    from veda.modules.catalog.models import CatalogEvent

    event = rows(sa.select(CatalogEvent).where(CatalogEvent.event_type == "RELEASE_REJECTED"))[0]
    assert event.detail["cleared"]["status"] == "SCHEDULED" and event.detail["cleared"]["approved_by"] == b
    with db.unit_of_work(write=True) as s:
        assert service.run_scheduled(s) == [], "nothing activates from a stale schedule"
    tx(b, service.approve_preview, rel.id)  # the release can go through review again
    tx(a, service.submit_release, rel.id)


def _statuses(release_id):
    with db.unit_of_work(write=False) as s:
        return {r.status for r in service.release_records(s, s.get(CatalogRelease, release_id))}


# --- R15: import permissions and idempotency ------------------------------------------------------------------------
def test_import_needs_the_edit_permission_of_every_kind(app):
    rows_ = [importexport.ImportRow(k, f"{k.replace('_', '-')}.x1", {}) for k in ("pricing", "copy", "material", "media", "product")]  # fmt: skip
    with db.unit_of_work(write=False) as s:
        report = importexport.dry_run(s, rows_, can_edit=lambda kind: False)  # catalog.admin and nothing else
    errors = {r["kind"]: r["errors"][0] for r in report["rows"]}
    assert errors == {
        "pricing": "pricing rows need catalog.pricing.edit",
        "copy": "copy rows need catalog.spec.edit",
        "material": "material rows need catalog.spec.edit",
        "media": "media rows need catalog.media.edit",
        "product": "product rows need catalog.edit",
    }


def test_repeating_an_import_is_a_deterministic_no_op(staff):
    a, *_ = staff
    rows_ = [importexport.ImportRow("product_family", "beds", {"name": "Beds", "category": "beds"})]
    first = tx(a, importexport.apply, rows_, can_edit=lambda kind: True)
    second = tx(a, importexport.apply, rows_, can_edit=lambda kind: True)
    third = tx(a, importexport.apply, rows_, can_edit=lambda kind: True)
    assert first["result"] == "CREATED" and second["result"] == third["result"] == "NO_CHANGE"
    assert second == third and second["created"] == [] and second["content_sha256"] == first["content_sha256"]
    assert [(r.record_key, r.record_version, r.status) for r in rows(sa.select(CatalogRecord))] == [
        ("beds", 1, "DRAFT")
    ]


@STAFF
def test_import_route_refuses_rows_beyond_the_admins_edit_permissions(api, factory):
    admin = factory.user("ADMIN")
    factory.grant(admin, "catalog.admin")
    factory.grant(admin, "catalog.edit")
    token = factory.login(api, admin, set_default=False)
    content = "kind,key,document\n" + '\n'.join([
        'product_family,beds,"{""name"": ""Beds"", ""category"": ""beds""}"',
        'copy,copy.x1,"{""statement"": ""Beds for every room"", ""category"": ""description"", ""promise"": false}"',
    ])  # fmt: skip
    dry = api.post("/api/v1/catalog/import", {"format": "csv", "content": content}, token=token)
    assert dry.status == 200 and not dry.data["ok"] and "catalog.spec.edit" in dry.data["rows"][1]["errors"][0]
    applied = api.post("/api/v1/catalog/import", {"format": "csv", "content": content, "apply": True}, token=token)
    assert applied.status == 422 and not rows(sa.select(CatalogRecord)), "all-or-nothing"
    assert not rows(sa.select(CatalogConfiguration))
