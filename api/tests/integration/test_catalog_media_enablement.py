"""Targeted media enablement (application side).

Covers:
- the V3 staging approval record;
- the media settings, which fail closed;
- serve-time rights validity;
- scanner and storage signals, which carry no data;
- permission separations.

The synthetic slice only: no real media, no customer content, nothing deployed."""

import base64
import copy
import hashlib
import io
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


# --- the V3 staging approval record: one policy, four gates, one conformance set --------------------------------------
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "v3_approval"
CASES = json.loads((FIXTURES / "cases.json").read_text())


def _case_inputs(case):
    path = FIXTURES / f"{case['record']}.json"
    raw = path.read_bytes() if path.exists() else None
    bound = {"record": hashlib.sha256(raw).hexdigest() if raw else None, "other": CASES["other_digest"], None: None}
    return path, raw, bound[case["bound"]], date.fromisoformat(case["today"])


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["name"])
def test_runtime_rules_give_the_shared_conformance_codes(case):
    _, raw, bound, today = _case_inputs(case)
    assert staging_approval.evaluate(raw, today=today, bound_sha256=bound) == case["codes"]


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["name"])
def test_the_deployment_check_gives_the_same_decision(case, monkeypatch, capsys):
    path, _, bound, today = _case_inputs(case)

    class Bound:
        catalog_approval_sha256 = bound

    monkeypatch.setattr(config, "settings", lambda: Bound())
    clock.set_clock(lambda: datetime.combine(today, datetime.min.time(), UTC).replace(hour=12))
    assert staging_approval.main(["x", str(path)]) == (0 if not case["codes"] else 1)
    out = capsys.readouterr().out
    assert all(c in out for c in case["codes"]), out


def test_every_gate_reads_the_one_policy_and_the_terraform_cases_are_current():
    from tools import v3_approval_conformance

    root = Path(__file__).resolve().parents[3]
    assert "v3_approval_policy.json" in (root / "app/scripts/v3-approval.mjs").read_text()
    assert "v3_approval_policy.json" in (root / "infra/terraform/modules/v3-approval/main.tf").read_text()
    assert 'source = "../../modules/v3-approval"' in (root / "infra/terraform/envs/staging-core/main.tf").read_text()
    assert "evaluateV3Approval" in (root / "app/scripts/staging-build.mjs").read_text()
    assert v3_approval_conformance.main(["x", "--check"]) == 0, "regenerate the Terraform conformance cases"
    covered = {c["record"] for c in CASES["cases"]}
    assert {p.stem for p in FIXTURES.glob("*.json")} - {"cases"} <= covered, "every fixture is a conformance case"
    for required in ("approved", "expired", "future-review", "revoked", "wrong-environment", "self-approved",
                     "missing-evidence", "wrong-scope-public-intake"):  # fmt: skip
        assert required in covered, required
    assert any(c["bound"] == "other" and c["codes"] == ["DIGEST_MISMATCH"] for c in CASES["cases"])


def test_no_fixture_the_runtime_rejects_is_used_as_an_approved_record():
    approved = [c for c in CASES["cases"] if not c["codes"]]
    assert approved, "the conformance set has accepted records"
    for case in approved:
        _, raw, bound, today = _case_inputs(case)
        assert staging_approval.evaluate(raw, today=today, bound_sha256=bound) == []


def test_the_committed_template_is_a_draft_and_no_approved_record_exists():
    raw = TEMPLATE.read_bytes()
    doc = json.loads(raw)
    assert doc["status"] == "DRAFT" and doc["evidence"] == {} and doc["approver"] is None
    assert doc["review_by"] is None and doc["expires_at"] is None and doc["approved_at"] is None
    assert "STATUS" in staging_approval.evaluate(raw, today=date(2026, 10, 11), bound_sha256=None)
    assert not staging_approval.RECORD.exists(), "no approval record is committed until the owner approves one"


def test_the_policy_names_every_piece_of_evidence():
    assert set(staging_approval.REQUIRED_EVIDENCE) == {
        "application_certification", "application_commit", "pr69_merge", "real_card_evidence", "infrastructure_plan",
        "infrastructure_apply", "scanner_capacity", "scanner_decision", "media_bucket", "iam", "ssm_settings", "csp",
        "media_smoke_test", "promise_owner_approval", "media_rights_approver"}  # fmt: skip
    assert staging_approval.MAX_REVIEW_DAYS == 90


def test_a_missing_or_unreadable_record_does_not_authorise(tmp_path):
    assert staging_approval.evaluate(None, today=date(2026, 10, 11), bound_sha256=None) == ["NO_RECORD"]
    assert staging_approval.read(tmp_path / "absent.json") is None


def test_production_can_never_use_a_staging_approval():
    raw = (FIXTURES / "wrong-environment.json").read_bytes()
    codes = staging_approval.evaluate(raw, today=date(2026, 10, 11), bound_sha256=hashlib.sha256(raw).hexdigest())
    assert codes == ["ENVIRONMENT"]
    assert config.validate_environment(config.Settings(env="production", database_url="sqlite://",
                                                       catalog_estimator_enabled=True)), "production refuses V3 anyway"  # fmt: skip


# --- the runtime gate on staging: the catalog and every media route --------------------------------------------------
NOW = datetime(2026, 10, 11, 12, tzinfo=UTC)


def _record(**over):
    doc = json.loads((FIXTURES / "approved.json").read_text())
    doc.update({"release": "SLICE-1", **over})  # the release the test slice activates
    return doc


@pytest.fixture
def on_staging(monkeypatch, tmp_path):
    """Run the API as protected staging with `doc` as the packaged record, bound by its own digest unless `bound`."""
    from veda.modules.catalog import configure

    real = configure.settings
    state = {"bound": None}

    class Staging:
        def __getattr__(self, name):
            if name == "env":
                return "staging"
            if name == "catalog_approval_sha256":
                return state["bound"]
            return getattr(real(), name)

    monkeypatch.setattr(configure, "settings", lambda: Staging())
    record = tmp_path / "v3-staging-approval.json"
    monkeypatch.setattr(staging_approval, "RECORD", record)
    monkeypatch.setattr(staging_approval, "read", lambda path=record: path.read_bytes() if path.exists() else None)
    clock.set_clock(lambda: NOW)

    def use(doc, *, bound="record"):
        configure._view_cache.clear()
        if doc is None:
            record.unlink(missing_ok=True)
            state["bound"] = None
            return
        raw = json.dumps(doc, indent=2).encode()
        record.write_bytes(raw)
        state["bound"] = hashlib.sha256(raw).hexdigest() if bound == "record" else bound

    return use


def _released(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b)
    with db.unit_of_work(write=False) as s:
        doc = service.versions(s, "media", "img.tv-laminate")[-1].document
    return next(iter(doc["objects"]["variants"].values()))


LAPSED = {
    "missing": (None, "record"),
    "revoked": (
        _record(status="REVOKED", revoked_at="2026-10-05", revocation_reason="Synthetic: rights complaint"),
        "record",
    ),
    "expired": (_record(expires_at="2026-10-10"), "record"),
    "review reached": (_record(review_by="2026-10-11"), "record"),
    "review window exceeded": (_record(review_by="2026-12-31"), "record"),
    "digest mismatch": (_record(), "c" * 64),
    "unbound": (_record(), None),
    "another release": (_record(release="SLICE-2"), "record"),
}


@ON
@pytest.mark.parametrize("why", list(LAPSED))
def test_on_staging_approval_loss_stops_the_catalog_and_public_media_at_once(api, people, on_staging, why):
    sha = _released(people)
    media_route = f"/api/v1/public/catalog/media/{sha}"
    on_staging(_record())
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 200, "a current approval serves the catalog"
    assert api.get(media_route, anonymous=True).status == 200, "and its media"
    doc, bound = LAPSED[why]
    on_staging(doc, bound=bound)
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 503, why
    assert api.get(media_route, anonymous=True).status == 503, f"{why}: media stops with the catalog"


@ON
@pytest.mark.parametrize("why", [w for w in LAPSED if w != "another release"])
def test_on_staging_approval_loss_stops_every_staff_media_operation(api, people, factory, on_staging, why):
    sha = _released(people)
    founder = factory.user("FOUNDER")
    factory.grant(founder, "catalog.media.edit")
    token = factory.login(api, founder, set_default=False)
    upload = {"data_base64": base64.b64encode(_jpeg()).decode()}
    on_staging(_record())
    assert api.get("/api/v1/catalog/media", token=token).status == 200
    assert api.get(f"/api/v1/catalog/media/{sha}", token=token).status == 200
    doc, bound = LAPSED[why]
    on_staging(doc, bound=bound)
    assert api.get("/api/v1/catalog/media", token=token).status == 503, f"list: {why}"
    assert api.get(f"/api/v1/catalog/media/{sha}", token=token).status == 503, f"preview: {why}"
    assert api.post("/api/v1/catalog/media", upload, token=token).status == 503, f"upload: {why}"
    assert api.post(f"/api/v1/catalog/media/{sha}/withdraw", {"note": "synthetic"}, token=token).status == 503, (
        f"withdraw: {why}"
    )


@ON
def test_staff_media_needs_no_matching_release_so_the_next_release_can_be_prepared(api, people, factory, on_staging):
    sha = _released(people)
    founder = factory.user("FOUNDER")
    token = factory.login(api, founder, set_default=False)
    on_staging(_record(release="SLICE-2"))
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 503, "serving needs the approved release"
    assert api.get(f"/api/v1/catalog/media/{sha}", token=token).status == 200, "staff preview does not"


@ON
def test_off_staging_the_approval_gate_is_not_consulted(api, people):
    sha = _released(people)
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 200, "test environment: no record needed"
    assert api.get(f"/api/v1/public/catalog/media/{sha}", anonymous=True).status == 200


def _jpeg():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (120, 90, 60)).save(buf, "JPEG")
    return buf.getvalue()


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
