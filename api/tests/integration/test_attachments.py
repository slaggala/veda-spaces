"""MTQ B1-T02: the attachment module (ATT, migration 0106; blocker closure §6).

The MTQ record types arrive in B1-T03; here a test binding stands in for one, so ATT is tested on its own terms:
scope, frozen limits, idempotency, verified completion, scanning, fail-closed delivery, withdrawal and erasure."""

from __future__ import annotations

import base64
import hashlib
import io

import pytest
import sqlalchemy as sa
from PIL import Image

from veda.kernel import db
from veda.kernel import media as km
from veda.kernel.context import actor, system_context
from veda.modules.attachments import registry, service
from veda.modules.attachments.models import CATEGORIES, ENTITY_TYPES, Attachment

ON = pytest.mark.settings(mtq_site_enabled=True)


def jpeg(size=(1200, 900), *, gps: bool = True) -> bytes:
    img = Image.new("RGB", size, (90, 120, 150))
    for x in range(0, size[0], 29):
        img.putpixel((x, x % size[1]), (255, 0, 0))
    exif = Image.Exif()
    exif[0x0112] = 1
    if gps:
        exif[0x8825] = {2: (17.0, 23.0, 1.0)}
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    return buf.getvalue()


class Binding:
    """A stand-in for the MTQ bindings: entity ids map to leads with configurable limits and state."""

    def __init__(self):
        self.leads: dict[str, str] = {}
        self.wall: str | None = None
        self.container_usage: tuple[int, int] = (0, 0)
        self.writable = True
        self.rule = "UPLOADER_OR_ALL"

    def resolve(self, s, entity_id):
        lead = self.leads.get(entity_id)
        if lead is None:
            return None
        return registry.EntityContext(
            lead_id=lead,
            container_id="c" if self.container_usage else None,
            wall_id=self.wall,
            writable=self.writable,
            withdraw_rule=self.rule,
        )


@pytest.fixture
def binding():
    b = Binding()
    previous = registry._reset_for_tests(
        {"property": registry.EntityBinding("property", b.resolve, container_usage=lambda s, cid: b.container_usage)}
    )
    yield b
    registry._reset_for_tests(previous)


@pytest.fixture
def sales(api, factory):
    user = factory.user("SALES")
    factory.login(api, user)
    return user


def new_lead(api, token=None) -> str:
    r = api.post(
        "/api/v1/leads", {"name": "Site Owner", "phone": "+91 90000 54321", "source_code": "PHONE"}, token=token
    )
    assert r.status == 201, r
    return r.data["id"]


def entity(binding, lead_id) -> str:
    from veda.kernel.ids import new_id

    eid = new_id()
    binding.leads[eid] = lead_id
    return eid


def declare(api, eid, data, **extra):
    body = {
        "entity_type": "property",
        "entity_id": eid,
        "mime_type": "image/jpeg",
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "filename": "C:\\Users\\me\\..\\kitchen wall\x07.jpg",
        **extra,
    }
    return api.post("/api/v1/attachments", body)


def upload(api, att_id, data):
    return api.put(f"/api/v1/attachments/{att_id}/content", {"data_base64": base64.b64encode(data).decode()})


def full_upload(api, eid, data, **extra):
    r = declare(api, eid, data, **extra)
    assert r.status in (200, 201), r
    assert upload(api, r.data["id"], data).status == 200
    done = api.post(f"/api/v1/attachments/{r.data['id']}/complete")
    assert done.status == 200, done
    return done.data


def test_literals_match_the_migration_checks():
    from veda.modules.attachments import schemas

    assert set(schemas.EntityType.__args__) == set(ENTITY_TYPES)
    assert set(schemas.Category.__args__) == set(CATEGORIES)


def test_every_route_is_404_while_the_flag_is_off(api, factory):
    user = factory.user(founder=True)
    factory.login(api, user)
    zero = "0" * 32
    for method, path in (
        ("POST", "/api/v1/attachments"),
        ("GET", "/api/v1/attachments?entity_type=property&entity_id=" + zero),
        ("GET", f"/api/v1/attachments/{zero}"),
        ("PUT", f"/api/v1/attachments/{zero}/content"),
        ("POST", f"/api/v1/attachments/{zero}/complete"),
        ("GET", f"/api/v1/attachments/{zero}/content"),
        ("POST", f"/api/v1/attachments/{zero}/withdraw"),
    ):
        assert api.call(method, path, {} if method != "GET" else None).status == 404, (method, path)
        assert api.call(method, path, None, anonymous=True).status == 404


@ON
def test_upload_complete_and_deliver_without_metadata(api, sales, binding):
    eid = entity(binding, new_lead(api))
    data = jpeg()
    r = declare(api, eid, data, client_ref="wall-1-photo-1", category_code="LASER_READING")
    assert r.status == 201, r
    assert r.data["upload"]["method"] == "PUT" and r.data["scan_status"] == "PENDING"
    assert r.data["filename"] == "kitchen wall.jpg"  # path parts and control characters removed
    assert r.data["available"] is False
    assert api.get(f"/api/v1/attachments/{r.data['id']}/content").status == 409  # fail closed before completion
    assert upload(api, r.data["id"], data).status == 200
    done = api.post(f"/api/v1/attachments/{r.data['id']}/complete").data
    assert done["upload_status"] == "RECEIVED" and done["scan_status"] == "CLEAN" and done["available"] is True
    assert set(done["variants"]) == {"thumb", "mobile", "desktop", "full"}
    assert api.post(f"/api/v1/attachments/{r.data['id']}/complete").data == done  # idempotent
    got = api.get(f"/api/v1/attachments/{r.data['id']}/content?variant=full")
    assert got.status == 200
    assert got.headers["Content-Type"] == "image/webp" and got.headers["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in got.headers["Cache-Control"] and "kitchen" not in got.headers["Content-Disposition"]
    with Image.open(io.BytesIO(got.raw.data)) as out:
        assert out.size == (1200, 900) and not out.getexif()
    # The uploaded bytes are not kept once the re-encoded variants exist and the scan is clean.
    assert service._fetch(km.content_key("upload/", hashlib.sha256(data).hexdigest())) is None
    listed = api.get(f"/api/v1/attachments?entity_type=property&entity_id={eid}").data
    assert [a["id"] for a in listed] == [r.data["id"]]


@ON
def test_client_ref_is_idempotent_and_never_reused(api, sales, binding):
    eid = entity(binding, new_lead(api))
    data = jpeg()
    first = declare(api, eid, data, client_ref="offline-17")
    again = declare(api, eid, data, client_ref="offline-17")
    assert first.status == 201 and again.status == 200 and again.data["id"] == first.data["id"]
    other = declare(api, eid, jpeg((900, 700)), client_ref="offline-17")
    assert other.status == 409 and other.code == "CLIENT_REF_REUSED"


@ON
@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"mime_type": "application/pdf"}, "VALIDATION_FAILED"),
        ({"byte_size": 15 * 1024 * 1024 + 1}, "VALIDATION_FAILED"),
        ({"sha256": "ABC"}, "VALIDATION_FAILED"),
        ({"entity_type": "lead"}, "VALIDATION_FAILED"),
        ({"unexpected": 1}, "VALIDATION_FAILED"),
    ],
)
def test_declarations_are_validated(api, sales, binding, override, code):
    eid = entity(binding, new_lead(api))
    r = declare(api, eid, jpeg(), **override)
    assert r.status == 422 and r.code in (code, "UNKNOWN_FIELD"), r


@ON
def test_bytes_that_do_not_match_or_are_not_images_are_rejected(api, sales, binding):
    eid = entity(binding, new_lead(api))
    data = jpeg()
    r = declare(api, eid, data)
    assert upload(api, r.data["id"], data[:-10] + b"0123456789").status == 200
    done = api.post(f"/api/v1/attachments/{r.data['id']}/complete").data
    assert done["upload_status"] == "REJECTED" and done["rejection_reason"] == "CHECKSUM_MISMATCH"
    pdf = b"%PDF-1.7\n" + b"0" * 2000
    r = declare(api, eid, pdf)
    upload(api, r.data["id"], pdf)
    done = api.post(f"/api/v1/attachments/{r.data['id']}/complete").data
    assert done["upload_status"] == "REJECTED" and done["rejection_reason"] == "UNSUPPORTED_TYPE"
    assert api.get(f"/api/v1/attachments/{r.data['id']}/content").status == 409


@ON
def test_completion_before_upload_is_refused(api, sales, binding):
    eid = entity(binding, new_lead(api))
    r = declare(api, eid, jpeg())
    done = api.post(f"/api/v1/attachments/{r.data['id']}/complete")
    assert done.status == 409 and done.code == "UPLOAD_NOT_RECEIVED"


def _seed_wall_photos(lead_id, wall_id, user_id, n, tag):
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        for i in range(n):
            sha = hashlib.sha256(f"{tag}-{i}".encode()).hexdigest()
            s.add(
                Attachment(
                    lead_id=lead_id,
                    entity_type="space_wall",
                    entity_id=wall_id,
                    category_code="SITE_PHOTO",
                    declared_mime_type="image/jpeg",
                    byte_size=10,
                    sha256=sha,
                    storage_backend="local",
                    upload_key="upload/" + sha,
                    uploaded_by=user_id,
                )  # fmt: skip
            )


@ON
def test_wall_and_set_limits(api, sales, binding):
    from veda.kernel.ids import new_id

    eid = entity(binding, new_lead(api))
    binding.wall = new_id()
    _seed_wall_photos(binding.leads[eid], binding.wall, sales.id, 5, "a")
    r = declare(api, eid, jpeg())  # the sixth photo on the wall: no warning yet
    assert r.status == 201 and not (r.json.get("meta") or {}).get("warnings")
    _seed_wall_photos(binding.leads[eid], binding.wall, sales.id, 1, "b")
    soft = declare(api, eid, jpeg((900, 700)))  # the seventh: past the soft limit of six
    assert soft.status == 201 and soft.json["meta"]["warnings"][0]["code"] == "WALL_SOFT_LIMIT"
    _seed_wall_photos(binding.leads[eid], binding.wall, sales.id, 6, "c")
    hard = declare(api, eid, jpeg((800, 700)))  # twelve already: the hard limit
    assert hard.status == 422 and hard.code == "ATTACHMENT_LIMIT_EXCEEDED" and hard.json["limit"] == "WALL"
    binding.wall = None
    binding.container_usage = (800, 0)
    full_set = declare(api, eid, jpeg((700, 700)))
    assert full_set.status == 422 and full_set.json["limit"] == "MEASUREMENT_SET"
    binding.container_usage = (10, 1024 * 1024 * 1024 - 100)
    assert declare(api, eid, jpeg((700, 650))).json["limit"] == "MEASUREMENT_SET"  # the 1 GiB cap


@ON
def test_frozen_records_take_no_new_uploads(api, sales, binding):
    eid = entity(binding, new_lead(api))
    binding.writable = False
    r = declare(api, eid, jpeg())
    assert r.status == 409 and r.code == "ENTITY_FROZEN"


@ON
def test_scope_other_sales_users_never_see_it(api, factory, binding):
    owner = factory.user("SALES")
    factory.login(api, owner)
    eid = entity(binding, new_lead(api))
    att = full_upload(api, eid, jpeg())
    other = factory.user("SALES")
    factory.login(api, other)
    assert api.get(f"/api/v1/attachments/{att['id']}").status == 404
    assert api.get(f"/api/v1/attachments/{att['id']}/content").status == 404
    assert declare(api, eid, jpeg((900, 600))).status == 404  # the lead is not theirs
    founder = factory.user(founder=True)
    factory.login(api, founder)
    assert api.get(f"/api/v1/attachments/{att['id']}").status == 200


@ON
def test_withdrawal_deletes_bytes_and_keeps_the_record(api, sales, binding):
    eid = entity(binding, new_lead(api))
    att = full_upload(api, eid, jpeg())
    r = api.post(f"/api/v1/attachments/{att['id']}/withdraw", {"reason": "Wrong wall"}, if_match=att["version"])
    assert r.status == 200 and r.data["retention_state"] == "WITHDRAWN" and r.data["scan_status"] == "WITHDRAWN"
    assert api.get(f"/api/v1/attachments/{att['id']}/content").status == 409
    with db.unit_of_work(write=False) as s:
        row = s.get(Attachment, att["id"])
        assert row.sha256 == att["sha256"] and row.bytes_deleted_on is not None
        for meta in row.variants.values():
            assert service._fetch(km.content_key("att/", meta["sha256"])) is None
    again = api.post(f"/api/v1/attachments/{att['id']}/withdraw", {}, if_match=r.data["version"])
    assert again.status == 409


@ON
def test_verifier_rule_after_submission(api, factory, binding):
    sales = factory.user("SALES")
    factory.login(api, sales)
    eid = entity(binding, new_lead(api))
    att = full_upload(api, eid, jpeg())
    binding.rule = "VERIFIER_WITH_REASON"
    r = api.post(f"/api/v1/attachments/{att['id']}/withdraw", {"reason": "x"}, if_match=att["version"])
    assert r.status == 403  # SALES does not hold measurement.verify


@ON
def test_infected_uploads_are_quarantined_and_never_served(api, sales, binding, monkeypatch):
    from veda import config

    eid = entity(binding, new_lead(api))
    cfg = config.settings()
    monkeypatch.setattr(service, "settings", lambda: _with(cfg, attachment_scanner="clamd"))
    monkeypatch.setattr(km, "clamd_scan", lambda data, address: False)
    data = jpeg()
    r = declare(api, eid, data)
    upload(api, r.data["id"], data)
    done = api.post(f"/api/v1/attachments/{r.data['id']}/complete").data
    assert done["scan_status"] == "INFECTED" and done["available"] is False and done["variants"] == {}
    assert api.get(f"/api/v1/attachments/{r.data['id']}/content").status == 409
    assert service._fetch(km.content_key("upload/", done["sha256"])) is not None  # kept for investigation


@ON
def test_scanner_outage_fails_closed_then_rescan_clears(api, sales, binding, monkeypatch):
    from veda import config

    eid = entity(binding, new_lead(api))
    cfg = config.settings()
    monkeypatch.setattr(service, "settings", lambda: _with(cfg, attachment_scanner="clamd"))

    def down(data, address):
        raise OSError("refused")

    monkeypatch.setattr(km, "clamd_scan", down)
    data = jpeg()
    r = declare(api, eid, data)
    upload(api, r.data["id"], data)
    done = api.post(f"/api/v1/attachments/{r.data['id']}/complete").data
    assert done["scan_status"] == "FAILED" and done["available"] is False
    monkeypatch.setattr(km, "clamd_scan", lambda data, address: True)
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        assert service.rescan_pending(s) == 1
    after = api.get(f"/api/v1/attachments/{r.data['id']}").data
    assert after["scan_status"] == "CLEAN" and after["available"] is True
    assert service._fetch(km.content_key("upload/", done["sha256"])) is None


@ON
def test_lead_erasure_deletes_attachment_bytes(api, sales, binding):
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead

    lead_id = new_lead(api)
    att = full_upload(api, entity(binding, lead_id), jpeg())
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead = s.get(Lead, lead_id)
        lead_service.anonymize(s, lead, legal_basis="TEST", request_ref=None)
    with db.unit_of_work(write=False) as s:
        row = s.get(Attachment, att["id"])
        assert row.retention_state == "ERASED" and row.original_filename is None and row.bytes_deleted_on
        for meta in row.variants.values():
            assert service._fetch(km.content_key("att/", meta["sha256"])) is None
    assert api.get(f"/api/v1/attachments/{att['id']}/content").status == 409
    assert declare(api, entity(binding, lead_id), jpeg((640, 640))).status == 409  # an erased lead is closed


@ON
def test_purge_quarantine_and_abandoned_uploads(api, sales, binding):
    from datetime import timedelta

    from veda.kernel import clock

    eid = entity(binding, new_lead(api))
    pending = declare(api, eid, jpeg()).data
    clock.advance(timedelta(hours=25))
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        assert service.purge(s) == {"infected_purged": 0, "abandoned": 1}
    with db.unit_of_work(write=False) as s:  # the access token has expired with the clock: read the row
        row = s.get(Attachment, pending["id"])
        assert row.upload_status == "REJECTED" and row.rejection_reason == "ABANDONED" and row.bytes_deleted_on


def _with(cfg, **changes):
    from dataclasses import replace

    return replace(cfg, **changes)


def test_erasure_cascade_is_registered():
    from veda.modules.crm.leads import erasure

    assert "veda.modules.attachments.service:erase_for_lead" in erasure.CASCADES


def test_schema_has_the_attachment_table(app):
    with db.unit_of_work(write=False) as s:
        cols = {c["name"] for c in sa.inspect(s.connection()).get_columns("attachment")}
    assert {"lead_id", "entity_type", "entity_id", "sha256", "scan_status", "retention_state", "uploaded_by"} <= cols


def test_presigned_post_binds_key_type_length_and_kms(monkeypatch):
    import boto3

    seen = {}

    class Client:
        def generate_presigned_post(self, bucket, key, Fields, Conditions, ExpiresIn):  # noqa: N803 - boto3 names
            seen.update(bucket=bucket, key=key, fields=Fields, conditions=Conditions, expires=ExpiresIn)
            return {"url": "https://bucket.s3.amazonaws.com/", "fields": {**Fields, "key": key, "policy": "p"}}

    monkeypatch.setattr(boto3, "client", lambda name: Client())
    store = km.S3Storage("veda-attachments", "arn:aws:kms:ap-south-1:1:key/k", prefixes=service.PREFIXES)
    key = km.content_key("upload/", "e" * 64)
    out = store.presign_post(key, "image/jpeg", 12345, 300)
    assert seen["key"] == key and seen["expires"] == 300
    assert ["content-length-range", 12345, 12345] in seen["conditions"]
    assert {"Content-Type": "image/jpeg"} in seen["conditions"]
    assert {"x-amz-server-side-encryption": "aws:kms"} in seen["conditions"]
    assert {"x-amz-server-side-encryption-aws-kms-key-id": "arn:aws:kms:ap-south-1:1:key/k"} in seen["conditions"]
    assert out["fields"]["key"] == key and out["expires_in"] == 300
    with pytest.raises(km.MediaError):
        store.presign_post("source/" + "e" * 64, "image/jpeg", 1, 300)  # another module's prefix is refused


def test_attachment_category_lookup_is_seeded_and_matches_the_check(app):
    with db.unit_of_work(write=False) as s:
        codes = (
            s.execute(
                sa.text(
                    "SELECT v.code FROM lookup_value v JOIN lookup_category c ON c.id = v.category_id "
                    "WHERE c.code = 'ATTACHMENT_CATEGORY'"
                )
            )
            .scalars()
            .all()
        )
    assert set(codes) == set(CATEGORIES)
