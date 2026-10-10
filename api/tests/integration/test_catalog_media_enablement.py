"""Targeted media enablement (application side).

Covers:
- the V3 staging approval record;
- the media settings, which fail closed;
- serve-time rights validity;
- scanner and storage signals, which carry no data;
- permission separations.

The synthetic slice only: no real media, no customer content, nothing deployed."""

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from tests.integration.test_catalog import ON, approve_all, release, seed_slice
from veda import config
from veda.kernel import clock, db
from veda.modules.catalog import media, service, staging_approval
from veda.modules.catalog.models import CatalogMediaObject

TEMPLATE = Path(__file__).resolve().parents[3] / "docs/implementation/catalog/v3-staging-approval.template.json"


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


@pytest.fixture(autouse=True)
def _clock():
    yield
    clock.reset()


# --- the V3 staging approval record (schema 2: explicit review and expiry policy) -------------------------------------
TODAY = date(2026, 10, 10)


def approved(**over):
    doc = json.loads(TEMPLATE.read_text())
    doc.update(status="APPROVED", author="Catalog lead (role, test)", approver="Owner (role, test)",
               approved_at="2026-10-01", review_by="2026-12-01", expires_at="2027-03-01")  # fmt: skip
    doc["evidence"] = {
        k: {"git_sha": "a" * 40, "reference": f"git {k} (synthetic)"} for k in staging_approval.GIT_EVIDENCE
    }
    doc["evidence"] |= {
        k: {"sha256": "b" * 64, "reference": f"evidence {k} (synthetic)"} for k in staging_approval.DIGEST_EVIDENCE
    }
    doc.update(over)
    return doc


def test_the_committed_template_is_a_draft_and_no_approved_record_exists():
    doc = json.loads(TEMPLATE.read_text())
    template = staging_approval.check(doc)
    assert template.status == "DRAFT" and template.evidence == {} and template.approver is None
    assert template.review_by is None and template.expires_at is None and template.approved_at is None
    assert not staging_approval.approves(doc, today=TODAY)
    assert not staging_approval.RECORD.exists(), "no approval record is committed until the owner approves one"


def test_a_complete_independent_current_record_approves():
    assert staging_approval.approves(approved(), today=TODAY)
    assert staging_approval.approves(approved(expires_at=None, non_expiring_decision="Owner decision: reviewed every 90 days instead"),
                                     today=TODAY)  # fmt: skip
    assert set(staging_approval.REQUIRED_EVIDENCE) == {
        "application_certification", "application_commit", "pr69_merge", "real_card_evidence", "infrastructure_plan",
        "infrastructure_apply", "scanner_capacity", "scanner_decision", "media_bucket", "iam", "ssm_settings", "csp",
        "media_smoke_test", "promise_owner_approval", "media_rights_approver"}  # fmt: skip


@pytest.mark.parametrize("over,why", [
    ({"status": "DRAFT"}, "is DRAFT"),
    ({"status": "IN_REVIEW"}, "is IN_REVIEW"),
    ({"status": "REVOKED", "revoked_at": "2026-10-05", "revocation_reason": "Evidence withdrawn (synthetic)"}, "is REVOKED"),
    ({"expires_at": "2026-10-10"}, "expired"),
    ({"expires_at": "2026-10-05"}, "expired"),
    ({"review_by": "2026-10-10"}, "review date"),
    ({"approved_at": "2026-10-20", "review_by": "2026-12-01"}, "future"),
])  # fmt: skip
def test_records_that_do_not_authorise_v3_today(over, why):
    found = staging_approval.problems(approved(**over), today=TODAY)
    assert any(why in p for p in found), found


@pytest.mark.parametrize("over,why", [
    ({"approver": "Catalog lead (role, test)"}, "four-eyes"),
    ({"approver": "  catalog LEAD (role, test) "}, "four-eyes"),
    ({"approver": "[OWNER TO FILL]"}, "placeholder"),
    ({"approver": None}, "approver"),
    ({"review_by": None}, "review date"),
    ({"review_by": "2027-06-01"}, "review date"),  # more than 90 days after approval
    ({"expires_at": None}, "non-expiring"),
    ({"non_expiring_decision": "Owner decision: no expiry, reviewed quarterly (test)"}, "exactly one"),
    ({"expires_at": "2026-09-01"}, "expires after"),
    ({"status": "REVOKED"}, "when and why"),
    ({"revoked_at": "2026-10-05"}, "only a REVOKED"),
    ({"environment": "production"}, "environment"),
    ({"approval_scope": {"version": "v3", "protected": True, "public_intake": True, "media_delivery": False,
                         "three_d": False, "video": False}}, "public_intake"),
    ({"approval_scope": {"version": "v3", "protected": False, "public_intake": False, "media_delivery": False,
                         "three_d": False, "video": False}}, "protected"),
    ({"schema": "veda.catalog.v3-staging-approval/1"}, "not a"),
])  # fmt: skip
def test_malformed_or_inconsistent_records_are_refused(over, why):
    with pytest.raises(ValueError, match=why):
        staging_approval.check(approved(**over))
    assert not staging_approval.approves(approved(**over), today=TODAY)


@pytest.mark.parametrize("missing", ["real_card_evidence", "scanner_capacity", "media_rights_approver", "pr69_merge"])
def test_every_piece_of_evidence_is_required(missing):
    doc = approved()
    del doc["evidence"][missing]
    with pytest.raises(ValueError, match=missing):
        staging_approval.check(doc)


def test_evidence_must_be_a_digest_not_a_placeholder():
    doc = approved()
    doc["evidence"]["real_card_evidence"] = {"reference": "OWNER-RUN REAL-CARD EVIDENCE PENDING"}
    with pytest.raises(ValueError, match="real_card_evidence"):
        staging_approval.check(doc)


def test_a_missing_or_unreadable_record_does_not_authorise(tmp_path):
    assert staging_approval.problems(None) == ["no V3 staging approval record"]
    bad = tmp_path / "record.json"
    bad.write_text("{not json")
    assert staging_approval.load(bad) is None and not staging_approval.approves(staging_approval.load(bad))
    assert staging_approval.main(["x", str(bad)]) == 1


def test_production_can_never_use_a_staging_approval():
    with pytest.raises(ValueError):
        staging_approval.check(approved(environment="production"))
    assert config.validate_environment(config.Settings(env="production", database_url="sqlite://",
                                                       catalog_estimator_enabled=True)), "production refuses V3 anyway"  # fmt: skip


@ON
def test_on_staging_v3_stops_serving_when_the_approval_is_not_current(api, people, monkeypatch, tmp_path):
    """An expired, revoked or missing approval stops V3 at once on staging: not only at plan, build or deploy."""
    from veda.modules.catalog import configure

    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b)
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 200, (
        "test environment: no approval record needed"
    )
    real = configure.settings

    class Staging:
        def __getattr__(self, name):
            return "staging" if name == "env" else getattr(real(), name)

    monkeypatch.setattr(configure, "settings", lambda: Staging())
    configure._view_cache.clear()
    monkeypatch.setattr(staging_approval, "RECORD", tmp_path / "absent.json")
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 503
    record = tmp_path / "record.json"
    record.write_text(json.dumps(approved(expires_at="2026-10-05", review_by="2026-10-04", approved_at="2026-10-01")))
    monkeypatch.setattr(staging_approval, "RECORD", record)
    monkeypatch.setattr(staging_approval, "load", lambda path=record: json.loads(record.read_text()))
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 503, "expired approval: fail closed"
    record.write_text(json.dumps(approved(approved_at="2026-10-01", review_by="2026-12-01", expires_at="2099-01-01")))
    clock.set_clock(lambda: datetime(2026, 10, 10, 12, tzinfo=UTC))
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 200, "a current approval serves"


# --- settings fail closed --------------------------------------------------------------------------------------------
def staging(**over):
    base = dict(env="staging", database_url="sqlite://", catalog_admin_enabled=True, catalog_media_backend="s3",
                catalog_media_bucket="veda-stg-media-111122223333", catalog_media_scanner="clamd",
                catalog_media_kms_key_arn="arn:aws:kms:ap-south-1:111122223333:alias/veda-stg-data",
                catalog_media_rights_approver="Brand lead (role, test)")  # fmt: skip
    return config.Settings(**{**base, **over})


def media_problems(s):
    return [p for p in config.validate_environment(s) if "CATALOG" in p.upper() or "catalog" in p]


def test_the_media_settings_fail_closed_in_staging():
    assert media_problems(staging()) == []
    assert any("KMS_KEY_ARN" in p for p in media_problems(staging(catalog_media_kms_key_arn=None)))
    assert any("RIGHTS_APPROVER" in p for p in media_problems(staging(catalog_media_rights_approver="[OWNER TO FILL]")))
    assert any("RIGHTS_APPROVER" in p for p in media_problems(staging(catalog_media_rights_approver=None)))
    assert any("SCANNER=clamd" in p for p in media_problems(staging(catalog_media_scanner="none")))
    assert any("prefix" in p.lower() for p in media_problems(staging(catalog_media_source_prefix="uploads/")))
    assert any("VIDEO" in p for p in media_problems(staging(catalog_video_enabled=True)))


def test_with_the_catalog_off_the_planned_media_settings_change_nothing():
    off = staging(catalog_admin_enabled=False, catalog_media_scanner="none", catalog_media_rights_approver=None)
    assert media_problems(off) == [], "the settings are planned with every flag off and validate as they are"


def test_production_still_refuses_v3_and_media():
    prod = [p for p in config.validate_environment(config.Settings(
        env="production", database_url="sqlite://", catalog_estimator_enabled=True, catalog_admin_enabled=True,
        catalog_media_delivery_enabled=True))]  # fmt: skip
    for flag in ("VEDA_CATALOG_ESTIMATOR_ENABLED", "VEDA_CATALOG_ADMIN_ENABLED", "VEDA_CATALOG_MEDIA_DELIVERY_ENABLED"):
        assert any(flag in p and "production" in p for p in prod), flag


# --- serve-time rights validity --------------------------------------------------------------------------------------
@ON
def test_media_stops_serving_when_its_rights_expire_or_have_not_started(api, people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b)
    with db.unit_of_work(write=False) as s:
        doc = service.versions(s, "media", "img.tv-laminate")[-1].document
    sha = next(iter(doc["objects"]["variants"].values()))
    route = f"/api/v1/public/catalog/media/{sha}"
    assert api.get(route, anonymous=True).status == 200
    with db.unit_of_work(write=True) as s:
        from sqlalchemy import update

        from veda.kernel.context import actor, system_context
        from veda.modules.catalog.models import CatalogRecord

        with actor(system_context("SYSTEM_JOB")):
            row = service.versions(s, "media", "img.tv-laminate")[-1]
            expiring = copy.deepcopy(row.document)
            expiring["rights"]["expires"] = "2026-12-31"
            s.execute(update(CatalogRecord).where(CatalogRecord.id == row.id).values(document=expiring))
    clock.set_clock(lambda: datetime(2027, 1, 2, 12, tzinfo=UTC))
    assert api.get(route, anonymous=True).status == 404, "expired rights stop serving at once, not at the next release"


def test_rights_dates_are_consistent():
    from veda.modules.catalog import kinds

    with pytest.raises(ValueError, match="expire after"):
        kinds.Rights(owner="Studio", licence="Owned", usage="owned", effective_from=date(2026, 10, 1),
                     expires=date(2026, 9, 1))  # fmt: skip


# --- scanner and storage signals carry counts only ------------------------------------------------------------------
def test_scanner_outcomes_are_counted_without_data(monkeypatch):
    seen = []
    monkeypatch.setattr(media.metrics, "emit", lambda name, value=1, unit="Count", **kw: seen.append((name, kw)))
    monkeypatch.setattr(media, "settings", lambda: config.Settings(env="staging", database_url="sqlite://",
                                                                    catalog_media_scanner="clamd",
                                                                    catalog_clamd_address="127.0.0.1:9"))  # fmt: skip
    assert media.scan_status(b"data") == "FAILED"
    assert seen[-1][0] == "MediaScannerUnavailable"
    monkeypatch.setattr(media, "clamd_scan", lambda data, address: False)
    assert media.scan_status(b"data") == "INFECTED" and seen[-1][0] == "MediaInfected"
    monkeypatch.setattr(media, "clamd_scan", lambda data, address: (_ for _ in ()).throw(media.MediaError("no answer")))
    assert media.scan_status(b"data") == "FAILED" and seen[-1][0] == "MediaScanFailed"
    assert all(not kw.get("dimensions") for _name, kw in seen), "no filename, key or content in a scan signal"


def test_storage_denials_are_counted_by_operation_only(monkeypatch):
    seen = []
    monkeypatch.setattr(media.metrics, "emit", lambda name, value=1, unit="Count", **kw: seen.append((name, kw)))

    class Denied(Exception):
        def __init__(self, code):
            self.response = {"Error": {"Code": code}}

    for code, metric in (
        ("AccessDenied", "MediaStorageAccessDenied"),
        ("KMS.AccessDeniedException", "MediaKmsAccessDenied"),
    ):
        with pytest.raises(Denied):
            with media._storage_errors("put"):
                raise Denied(code)
        assert seen[-1] == (metric, {"dimensions": {"Operation": "put"}})


def test_signature_age_is_read_from_clamd_version(monkeypatch):
    class Sock:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def sendall(self, data):
            assert data == b"zVERSION\0"

        def recv(self, n):
            return b"ClamAV 1.4.1/27400/Thu Oct  8 08:00:00 2026\0"

    monkeypatch.setattr(media.socket, "create_connection", Sock)
    now = datetime(2026, 10, 10, 8, tzinfo=UTC)
    assert round(media.clamd_signature_age_hours("clamd:3310", now=now)) == 48


# --- permission separations ------------------------------------------------------------------------------------------
def test_media_operators_get_no_approval_or_pricing_permission():
    from veda.modules.catalog import permissions

    defs = {p.code: p for p in permissions.PERMISSIONS}
    media_edit = defs["catalog.media.edit"]
    assert "approv" not in media_edit.description.lower() and "pric" not in media_edit.description.lower()
    assert permissions.EDIT_PERMISSION["media"] == "catalog.media.edit"
    assert permissions.EDIT_PERMISSION["pricing"] != "catalog.media.edit"


@ON
def test_a_media_editor_cannot_approve_or_see_pricing(api, factory, people):
    live = people
    seed_slice(live[0])
    editor = factory.user("ADMIN")
    factory.grant(editor, "catalog.media.edit")
    token = factory.login(api, editor, set_default=False)
    records = api.get("/api/v1/catalog/records", token=token)
    assert records.status in (200, 403)
    if records.status == 200:
        assert not any(r["kind"] == "pricing" for r in records.data), "no pricing without pricing.view"
    with db.unit_of_work(write=False) as s:
        rid = service.versions(s, "media", "img.tv-laminate")[-1].id
    assert api.post(f"/api/v1/catalog/records/{rid}/approve", {}, token=token).status == 403, "no approval"
    assert api.post("/api/v1/catalog/releases", {"code": "MEDIA-X"}, token=token).status == 403, "no release control"


def test_the_scanner_has_no_catalog_identity():
    """The scanner is a network service the API calls; it holds no credential, role or permission of its own."""
    compose = (Path(__file__).resolve().parents[2] / "deploy" / "docker-compose.yml").read_text()
    clamd = compose[compose.index("  clamd:") :]
    assert "env_file" not in clamd.split("\nvolumes:")[0], "the scanner gets no application configuration or secret"
    assert CatalogMediaObject.__tablename__ == "catalog_media_object"
