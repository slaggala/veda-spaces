"""MC-2 (PR #87 review): no upload completes, and no variant is made, after a withdrawal or a lead erasure; bytes
that arrive late are deleted at the refused completion and by the purge sweep. Each case runs on the local backend
and on an in-memory stand-in for the S3 backend (the lifecycle code is the same; only the store differs)."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from tests.integration.test_attachments import binding, declare, entity, jpeg, new_lead, sales, upload  # noqa: F401
from veda import config
from veda.kernel import db
from veda.kernel import media as km
from veda.kernel.context import actor, system_context
from veda.modules.attachments import service
from veda.modules.attachments.models import Attachment

ON = pytest.mark.settings(mtq_site_enabled=True)


class _Missing(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class MemoryS3(km.S3Storage):
    """The S3 store's interface over a dict: what a pre-signed POST would write is a put() by the test."""

    objects: dict[str, bytes] = {}

    def __init__(self, bucket, kms_key_arn, prefixes=km.CONTENT_KEY_PREFIXES, region=None):  # noqa: D107 - no boto
        self.bucket, self.kms_key_arn, self.prefixes = bucket, kms_key_arn, prefixes

    def put(self, key, data, content_type):
        MemoryS3.objects[km.check_key(key, self.prefixes)] = data

    def get(self, key):
        try:
            return MemoryS3.objects[km.check_key(key, self.prefixes)]
        except KeyError as err:
            raise _Missing() from err

    def delete(self, key):
        MemoryS3.objects.pop(km.check_key(key, self.prefixes), None)

    def presign_post(self, key, content_type, size, expires):
        return {"url": "https://veda-stg-attachments-111122223333.s3.ap-south-1.amazonaws.com/",
                "fields": {"key": key}, "expires_in": expires}  # fmt: skip


@pytest.fixture(params=["local", "s3"])
def backend(request, monkeypatch):
    if request.param == "s3":
        MemoryS3.objects = {}
        cfg = config.settings()
        s3 = replace(cfg, attachment_backend="s3", attachment_bucket="veda-stg-attachments-111122223333",
                     attachment_kms_key_arn="arn:aws:kms:ap-south-1:111122223333:alias/veda-stg-data")  # fmt: skip
        monkeypatch.setattr(service, "settings", lambda: s3)
        monkeypatch.setattr(km, "S3Storage", MemoryS3)
    return request.param


def _land(att: dict, data: bytes) -> None:
    """The bytes arrive as a pre-signed POST (S3) or a late PUT would write them: straight into the store."""
    service.storage().put(km.content_key("upload/", att["sha256"]), data, "image/jpeg")


def _send(api, backend, att, data):
    if backend == "local":
        assert upload(api, att["id"], data).status == 200
    else:
        _land(att, data)


def _row(att_id) -> Attachment:
    with db.unit_of_work(write=False) as s:
        row = s.get(Attachment, att_id)
        s.expunge(row)
        return row


def _object(key_prefix: str, sha: str) -> bytes | None:
    return service._fetch(km.content_key(key_prefix, sha))


def _erase(lead_id):
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, lead_id), legal_basis="TEST", request_ref=None)


@ON
def test_withdrawal_before_completion_refuses_it_and_cleans_late_bytes(api, sales, binding, backend):  # noqa: F811
    data = jpeg()
    att = declare(api, entity(binding, new_lead(api)), data).data
    assert att["upload"]["required"] is True
    w = api.post(f"/api/v1/attachments/{att['id']}/withdraw", {"reason": "wrong room"}, if_match=att["version"])
    assert w.status == 200 and w.data["upload_status"] == "REJECTED"
    assert api.get(f"/api/v1/attachments/{att['id']}").data["upload"] == {"required": False}  # no new instructions
    if backend == "local":
        assert upload(api, att["id"], data).status == 409  # the API takes no bytes for it
    _land(att, data)  # a pre-signed POST issued before the withdrawal lands afterwards
    for _ in range(2):  # refused, and refused the same way on retry
        r = api.post(f"/api/v1/attachments/{att['id']}/complete")
        assert r.status == 409 and r.json["code"] == "ATTACHMENT_NOT_ACTIVE"
    assert _object("upload/", att["sha256"]) is None, "late bytes deleted at the refused completion"
    row = _row(att["id"])
    assert (row.retention_state, row.scan_status, row.upload_status, row.rejection_reason) == (
        "WITHDRAWN", "WITHDRAWN", "REJECTED", "INVALIDATED")  # fmt: skip
    assert row.variants in (None, {}) and row.variant_status != "READY"


@ON
def test_erasure_before_completion_refuses_it_and_cleans_late_bytes(api, sales, binding, backend):  # noqa: F811
    data = jpeg()
    lead_id = new_lead(api)
    att = declare(api, entity(binding, lead_id), data).data
    _erase(lead_id)
    _land(att, data)
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:  # the erased lead is out of scope
        with pytest.raises(service.ApiError) as err:
            service.complete(s, s.get(Attachment, att["id"]))
    assert err.value.code == "ATTACHMENT_NOT_ACTIVE"
    assert _object("upload/", att["sha256"]) is None
    row = _row(att["id"])
    assert row.retention_state == "ERASED" and row.upload_status == "REJECTED" and row.scan_status != "CLEAN"


@ON
def test_completion_refused_when_the_owner_record_is_gone(api, sales, binding, backend):  # noqa: F811
    data = jpeg()
    eid = entity(binding, new_lead(api))
    att = declare(api, eid, data).data
    _send(api, backend, att, data)
    binding.leads.pop(eid)  # the space or wall it belonged to was deleted meanwhile
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        with pytest.raises(service.ApiError) as err:
            service.complete(s, s.get(Attachment, att["id"]))
    assert err.value.code == "ATTACHMENT_OWNER_GONE"
    assert _object("upload/", att["sha256"]) is None and _row(att["id"]).scan_status == "PENDING"


@ON
def test_a_withdrawn_attachment_never_becomes_clean_or_gets_variants(api, sales, binding, backend):  # noqa: F811
    data = jpeg()
    att = declare(api, entity(binding, new_lead(api)), data).data
    _send(api, backend, att, data)
    api.post(f"/api/v1/attachments/{att['id']}/withdraw", {"reason": "x"}, if_match=att["version"])
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        row = s.get(Attachment, att["id"])
        service._apply_scan(s, row, data)  # even called directly, nothing changes
        assert row.scan_status == "WITHDRAWN" and row.variant_status != "READY"
        with pytest.raises(km.MediaError):
            service._store_variants(row, data)
        assert service.rescan_pending(s) == 0
    for name in service.VARIANT_WIDTHS:
        assert name not in (_row(att["id"]).variants or {})


@ON
def test_purge_sweeps_objects_that_land_after_invalidation(api, sales, binding, backend):  # noqa: F811
    data = jpeg()
    att = declare(api, entity(binding, new_lead(api)), data).data
    api.post(f"/api/v1/attachments/{att['id']}/withdraw", {"reason": "x"}, if_match=att["version"])
    _land(att, data)  # nobody calls complete: only the purge can find it
    assert _object("upload/", att["sha256"]) is not None
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        assert service.purge(s)["invalidated_swept"] >= 1
    assert _object("upload/", att["sha256"]) is None


@ON
def test_erasure_leaves_none_of_the_four_variants_or_the_upload(api, sales, binding, backend):  # noqa: F811
    data = jpeg()
    lead_id = new_lead(api)
    att = declare(api, entity(binding, lead_id), data).data
    _send(api, backend, att, data)
    done = api.post(f"/api/v1/attachments/{att['id']}/complete")
    assert done.status == 200 and done.data["scan_status"] == "CLEAN", done
    variants = _row(att["id"]).variants
    assert set(variants) == set(service.VARIANT_WIDTHS) and len(variants) == 4
    assert all(_object("att/", m["sha256"]) is not None for m in variants.values())
    _erase(lead_id)
    assert all(_object("att/", m["sha256"]) is None for m in variants.values())
    assert _object("upload/", att["sha256"]) is None
    row = _row(att["id"])
    assert row.retention_state == "ERASED" and row.original_filename is None and row.bytes_deleted_on is not None
    assert row.sha256 == hashlib.sha256(data).hexdigest()  # the non-content record the retention policy keeps
    _land(att, data)  # even a late duplicate POST is swept
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        service.purge(s)
    assert _object("upload/", att["sha256"]) is None
