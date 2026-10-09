"""V3 remediation Layers F and G: the image complexity limit (R11), scan states, 3D sanitisation and formats, media
withdrawal and retention, and the feature flags around the catalog API and media delivery. Synthetic files only."""

import io
import json
import struct
import zlib
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.integration.test_catalog import ON, STAFF, approve_all, living, public_estimate, release, seed_slice, tx
from tests.support.dbh import rows
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.modules.catalog import compile as catalog_compile
from veda.modules.catalog import kinds, media, seed, service
from veda.modules.catalog.models import CatalogEvent, CatalogMediaObject, CatalogRecord, CatalogRelease


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


def png(width, height):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (180, 160, 140)).save(buf, "PNG", compress_level=1)
    return buf.getvalue()


def forged_png(width, height):
    """A tiny PNG whose header claims huge dimensions (a decompression bomb, never decoded)."""
    data = bytearray(png(400, 400))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data[16:29] = ihdr
    data[29:33] = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)
    return bytes(data)


def upload(uid, data):
    return tx(uid, lambda s: media.upload(s, data).objects())


# --- R11: one documented hard pixel limit, enforced before decoding ----------------------------------------------
def test_the_pixel_limit_is_documented_and_exact():
    assert media.MAX_IMAGE_PIXELS == 24_000_000 and "24,000,000 pixels" in media.__doc__
    media.check_image_size(6000, 4000)  # exactly at the limit
    media.check_image_size(5999, 4000)  # just below
    with pytest.raises(media.MediaError, match="at most 24,000,000 pixels"):
        media.check_image_size(6000, 4001)  # just above
    with pytest.raises(media.MediaError, match="8000 pixels on each side"):
        media.check_image_size(8001, 400)


def test_images_at_and_below_the_limit_are_accepted_above_refused(people):
    a, _ = people
    assert upload(a, png(6000, 4000))["variants"], "exactly 24,000,000 pixels"
    assert upload(a, png(5999, 4000))["variants"], "one column fewer"
    with pytest.raises(media.MediaError, match="at most 24,000,000 pixels"):
        upload(a, png(6000, 4001))


@pytest.mark.parametrize("w,h", [(50_000, 50_000), (8_000, 8_000), (65_535, 400)])
def test_a_forged_bomb_header_is_refused_without_decoding(people, w, h):
    with pytest.raises(media.MediaError, match="at most"):
        upload(people[0], forged_png(w, h))
    assert not rows(sa.select(CatalogMediaObject)), "nothing stored"


# --- scan states -----------------------------------------------------------------------------------------------------
def test_scan_states_fail_closed(monkeypatch):
    class Deployed:
        catalog_media_scanner, env, catalog_clamd_address = "none", "staging", ""

    monkeypatch.setattr(media, "settings", lambda: Deployed())
    assert media.scan_status(b"x") == "PENDING"

    class Unreachable:
        catalog_media_scanner, env, catalog_clamd_address = "clamd", "staging", "127.0.0.1:1"

    monkeypatch.setattr(media, "settings", lambda: Unreachable())
    assert media.scan_status(b"x") == "FAILED"


# --- G1/G2: 3D formats and GLB sanitisation -------------------------------------------------------------------------
def glb(doc, binary=b"\0" * 36, extra_chunks=()):
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js
    if binary is not None:
        b = binary + b"\0" * (-len(binary) % 4)
        body += struct.pack("<II", len(b), 0x004E4942) + b
    for c in extra_chunks:
        body += struct.pack("<II", len(c), 0x12345678) + c
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


BASE = json.loads(seed._glb()[20 : 20 + struct.unpack_from("<I", seed._glb(), 12)[0]])


def test_a_valid_glb_is_rewritten_without_metadata():
    doc = {**BASE, "asset": {"version": "2.0", "generator": "SecretTool 9", "copyright": "Someone"},
           "nodes": [{**BASE["nodes"][0], "extras": {"author": "someone@example.com"}}]}  # fmt: skip
    out = media.sanitize_glb(glb(doc))
    text = out.data.decode("latin-1")
    assert "SecretTool" not in text and "someone@example.com" not in text and "Someone" not in text
    assert out.meshes == 1 and out.vertices == 3
    media.sanitize_glb(out.data)  # the rewritten file is itself valid


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda d: d["buffers"][0].update(uri="https://example.com/x.bin"), "URIs"),
        (lambda d: d.update(images=[{"uri": "data:image/png;base64,AAAA"}]), "URIs"),
        (lambda d: d.update(animations=[{}]), "unsupported content"),
        (lambda d: d.update(skins=[{}]), "unsupported content"),
        (lambda d: d.update(extensionsRequired=["KHR_draco_mesh_compression"]), "requires extensions"),
        (lambda d: d.update(extensionsUsed=["EXT_meshopt_compression"]), "unsupported extensions"),
        (lambda d: d.update(meshes=d["meshes"] * 201), "more than 200 meshes"),
        (lambda d: d["accessors"][0].update(count=600_000), "vertices"),
        (lambda d: d["bufferViews"][0].update(byteLength=10_000), "outside its binary chunk"),
        (lambda d: d.update(asset={"version": "1.0"}), "not glTF 2.0"),
    ],
)
def test_unsafe_glb_content_is_refused(change, match):
    doc = json.loads(json.dumps(BASE))
    change(doc)
    with pytest.raises(media.MediaError, match=match):
        media.sanitize_glb(glb(doc))


def test_glb_texture_must_be_the_image_it_claims():
    doc = json.loads(json.dumps(BASE))
    doc["bufferViews"].append({"buffer": 0, "byteOffset": 0, "byteLength": 36})
    doc["images"] = [{"bufferView": 1, "mimeType": "image/png"}]
    with pytest.raises(media.MediaError, match="not the image type it claims"):
        media.sanitize_glb(glb(doc))


def test_glb_container_structure():
    with pytest.raises(media.MediaError, match="one JSON chunk"):
        media.sanitize_glb(glb(BASE, extra_chunks=[b"\0" * 4]))
    raw = bytearray(glb(BASE))
    raw[8:12] = struct.pack("<I", len(raw) + 4)
    with pytest.raises(media.MediaError, match="not a valid binary glTF"):
        media.sanitize_glb(bytes(raw))


@pytest.mark.parametrize("data", [b"PK\x03\x04" + b"\0" * 100, b'{"asset": {"version": "2.0"}}'])
def test_usdz_and_gltf_are_disabled(people, data):
    with pytest.raises(media.MediaError, match="disabled"):
        upload(people[0], data)


def test_gltf_and_usdz_media_records_are_refused():
    for kind_ in ("GLTF", "USDZ"):
        with pytest.raises(ValueError, match="disabled"):
            kinds.parse("media", {"type": kind_, "title": "Model", "alt": "A model",
                                  "rights": {"owner": "x1", "licence": "x1", "usage": "owned"},
                                  "objects": {"variants": {"web": "a" * 64}},
                                  "three_d": {"model_version": "1", "preview_image": "img.p1", "fallback_gallery": "g.f1"}})  # fmt: skip


def test_a_client_image_needs_its_consent_reference():
    rights = {"owner": "A client", "licence": "Permission", "usage": "client_permission"}
    with pytest.raises(ValueError, match="written permission"):
        kinds.parse("media", {"type": "EXTERNAL_EMBED", "title": "Tour", "alt": "A tour",
                              "embed_url": "https://player.vimeo.com/video/1", "rights": rights})  # fmt: skip
    kinds.parse("media", {"type": "EXTERNAL_EMBED", "title": "Tour", "alt": "A tour",
                          "embed_url": "https://player.vimeo.com/video/1",
                          "rights": {**rights, "consent_reference": "CONSENT-2026-001"}})  # fmt: skip


def _live(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    return release(a, b)


def test_3d_is_hidden_from_customers_unless_enabled(people):
    rel = _live(people)
    with db.unit_of_work(write=False) as s:
        view = catalog_compile.customer_view(catalog_compile.load_release(s, s.get(CatalogRelease, rel)))
    assert "model.tv-unit" not in view["media"] and "model.tv-unit" not in view["product"]["tv-unit"]["media"]
    assert "gallery.tv-unit" in view["media"], "the gallery stays"


@pytest.mark.settings(catalog_3d_enabled=True)
def test_3d_is_shown_when_enabled(people):
    rel = _live(people)
    with db.unit_of_work(write=False) as s:
        view = catalog_compile.customer_view(catalog_compile.load_release(s, s.get(CatalogRelease, rel)))
    assert view["media"]["model.tv-unit"]["three_d"]["fallback_gallery"] == "gallery.tv-unit"


# --- G3: withdrawal and retention ---------------------------------------------------------------------------------
@ON
def test_withdrawn_media_stops_being_served_and_fails_new_releases(api, people):
    a, b = people
    _live(people)
    doc = rows(sa.select(CatalogRecord.document).where(CatalogRecord.record_key == "img.tv-laminate"))[0]
    thumb = doc["objects"]["variants"]["thumb"]
    assert api.get(f"/api/v1/public/catalog/media/{thumb}", anonymous=True).status == 200
    with pytest.raises(media.MediaError, match="say why"):
        tx(a, media.withdraw, thumb, "no")
    assert tx(a, media.withdraw, thumb, "Consent withdrawn by the photographer (test)") == 4
    assert api.get(f"/api/v1/public/catalog/media/{thumb}", anonymous=True).status == 404
    obj = rows(sa.select(CatalogMediaObject).where(CatalogMediaObject.object_sha256 == thumb))[0]
    assert obj.withdrawn_on and obj.purged_on, "hash kept, bytes gone"
    with pytest.raises(FileNotFoundError):
        media.storage().get(obj.storage_key)
    assert public_estimate(api, living()).status == 201, "estimates never depend on media"
    rel = tx(a, service.create_release, "SLICE-2")
    report = tx(a, service.validate_release, rel.id)
    assert any("withdrawn" in e for e in report["errors"])
    assert rows(sa.select(CatalogEvent).where(CatalogEvent.event_type == "MEDIA_WITHDRAWN"))


def test_unreferenced_media_is_purged_after_retention(people):
    a, _ = people
    loose = upload(a, png(800, 600))
    kept = upload(a, png(900, 600))
    tx(a, service.create_record, "media", "img.kept", {"type": "IMAGE", "title": "Kept", "alt": "A kept image",
       "rights": {"owner": "x1", "licence": "x1", "usage": "owned"}, "objects": kept})  # fmt: skip
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        assert media.purge_unreferenced(s) == 0, "nothing is purged before the retention period"
    clock.advance(timedelta(days=181))
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        assert media.purge_unreferenced(s) == 1
    purged = {r.object_sha256 for r in rows(sa.select(CatalogMediaObject)) if r.purged_on}
    assert loose["source"] in purged and kept["source"] not in purged


# --- flags ----------------------------------------------------------------------------------------------------------
def test_staff_catalog_api_is_off_by_default(api, factory):
    token = factory.login(api, factory.user("FOUNDER"), set_default=False)
    for path in ("/api/v1/catalog/dashboard", "/api/v1/catalog/records", "/api/v1/catalog/releases"):
        r = api.get(path, token=token)
        assert r.status == 404, path
    assert api.get("/api/v1/catalog/dashboard", anonymous=True).status == 404, "404 before authentication"


@STAFF
def test_staff_catalog_api_with_its_flag(api, factory):
    token = factory.login(api, factory.user("FOUNDER"), set_default=False)
    assert api.get("/api/v1/catalog/dashboard", token=token).status == 200


@pytest.mark.settings(catalog_estimator_enabled=True)
def test_public_media_is_off_without_its_flag(api, people):
    _live(people)
    doc = rows(sa.select(CatalogRecord.document).where(CatalogRecord.record_key == "img.tv-laminate"))[0]
    thumb = doc["objects"]["variants"]["thumb"]
    assert api.get(f"/api/v1/public/catalog/media/{thumb}", anonymous=True).status == 404
    assert api.get("/api/v1/public/catalog", anonymous=True).status == 200
