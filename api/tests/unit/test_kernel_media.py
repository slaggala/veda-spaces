"""MTQ B1-T01: the kernel media library is a behaviour-preserving extraction of the catalogue media pipeline.

Characterisation: the catalogue's public names are the kernel's objects, the catalogue's variants are byte-identical to
the kernel's for the same input, refusals carry the same messages, and the kernel never imports a module."""

from __future__ import annotations

import ast
import io
from pathlib import Path

import pytest
from PIL import Image

from veda.kernel import media as km
from veda.modules.catalog import media as cm

ROOT = Path(__file__).resolve().parents[2]


def _image(fmt: str, size: tuple[int, int], *, mode: str = "RGB", orientation: int | None = None) -> bytes:
    img = Image.new(mode, size, (120, 60, 30) if mode == "RGB" else (120, 60, 30, 200))
    for x in range(0, size[0], 37):
        for y in range(0, size[1], 41):
            img.putpixel((x, y), (x % 255, y % 255, (x * y) % 255) + ((255,) if mode == "RGBA" else ()))
    buf, kw = io.BytesIO(), {}
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        exif[0x8825] = {2: (12.0, 58.0, 1.0)}  # a GPS block: must never survive
        kw["exif"] = exif.tobytes()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def test_catalogue_names_are_the_kernel_objects():
    for name in (
        "MediaError",
        "LocalStorage",
        "S3Storage",
        "ObjectStore",
        "sniff",
        "check_image_size",
        "clamd_scan",
        "clamd_signature_age_hours",
        "MAX_IMAGE_BYTES",
        "MAX_IMAGE_PIXELS",
        "MAX_IMAGE_SIDE",
        "MIN_IMAGE_SIDE",
        "IMAGE_FORMATS",
        "IMAGE_WIDTHS",
    ):
        assert getattr(cm, name) is getattr(km, name), name
    assert cm._storage_errors is km.storage_errors


def test_kernel_media_imports_no_module_and_no_settings():
    tree = ast.parse((ROOT / "veda/kernel/media.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    assert not any(m.startswith("veda.modules") for m in imported), imported
    assert "veda.config" not in imported  # callers pass their own limits and scanner configuration


@pytest.mark.parametrize(
    "data",
    [
        _image("JPEG", (2000, 1200)),
        _image("PNG", (900, 1400), mode="RGBA"),
        _image("WEBP", (640, 480)),
        _image("JPEG", (1200, 800), orientation=6),
    ],
    ids=["jpeg", "png-alpha", "webp", "jpeg-rotated-with-gps"],
)
def test_catalogue_variants_are_byte_identical_to_the_kernel(data):
    assert cm._image_variants(data) == km.image_variants(data, km.IMAGE_WIDTHS)
    variants, width, height = km.image_variants(data)
    assert [name for name, *_ in variants] == ["thumb", "mobile", "desktop"]
    for _, blob, w, h in variants:
        with Image.open(io.BytesIO(blob)) as out:
            assert out.format == "WEBP" and out.size == (w, h)
            assert not out.getexif(), "variants carry no metadata"
            assert "exif" not in out.info and "icc_profile" not in out.info and "xmp" not in out.info
        assert w <= min(1600, width)  # never upscaled


def test_exif_orientation_is_applied():
    _, width, height = km.image_variants(_image("JPEG", (1200, 800), orientation=6))
    assert (width, height) == (800, 1200)


def test_custom_widths_and_limits_for_other_callers():
    variants, *_ = km.image_variants(_image("PNG", (2400, 1800)), {"thumb": 256, "review": 1024})
    assert [(n, w) for n, _, w, _ in variants] == [("thumb", 256), ("review", 1024)]
    with pytest.raises(km.MediaError, match="at most 2048 pixels on each side"):
        km.check_image_size(2400, 1800, max_side=2048)


@pytest.mark.parametrize(
    ("size", "message"),
    [
        ((8001, 10), "images are at most 8000 pixels on each side"),
        ((5000, 5000), "images are at most 24,000,000 pixels"),
        ((319, 400), "images need at least 320 pixels on each side"),
    ],
)
def test_size_refusals_unchanged(size, message):
    with pytest.raises(km.MediaError, match=message):
        cm.check_image_size(*size)


def test_sniff_unchanged_and_image_only_sniff():
    assert km.sniff(b"\xff\xd8\xffxx") == "JPEG"
    assert km.sniff(b"glTFxxxx") == "GLB"
    for blob in (b"%PDF-1.7 ...", b"glTFxxxx", b"0000ftypmp42", b"PK\x03\x04", b"<svg/>"):
        with pytest.raises(km.MediaError, match="only JPEG, PNG or WebP"):
            km.sniff_image(blob)
    assert km.sniff_image(b"\x89PNG\r\n\x1a\n....") == "PNG"


def test_storage_keys(tmp_path):
    store = km.LocalStorage(tmp_path)
    store.put("source/" + "a" * 64, b"x", "image/png")
    for bad in ("other/" + "c" * 64, "source/../" + "d" * 61, "source/abc"):
        with pytest.raises(km.MediaError, match="invalid storage key"):
            store.put(bad, b"x", "image/png")
    att = km.LocalStorage(tmp_path, prefixes=("att/",))
    key = km.content_key("att/", "f" * 64)
    att.put(key, b"y", "image/jpeg")
    assert att.get(key) == b"y"
    with pytest.raises(km.MediaError):
        att.put("source/" + "a" * 64, b"x", "image/png")  # another caller's prefix is refused
    with pytest.raises(km.MediaError):
        km.content_key("att/", "not-a-hash")


def test_scan_outcome_modes(monkeypatch):
    seen = []
    monkeypatch.setattr(km.metrics, "emit", lambda name, value=1, **kw: seen.append(name))
    assert km.scan_outcome(b"x", mode="none", address="", env="test") == "CLEAN"
    assert km.scan_outcome(b"x", mode="none", address="", env="staging") == "PENDING"
    assert km.scan_outcome(b"x", mode="clamd", address="h:1", env="staging", scan=lambda d, a: True) == "CLEAN"
    assert km.scan_outcome(b"x", mode="clamd", address="h:1", env="staging", scan=lambda d, a: False) == "INFECTED"

    def down(d, a):
        raise OSError("refused")

    assert km.scan_outcome(b"x", mode="clamd", address="h:1", env="staging", scan=down) == "FAILED"
    assert seen == ["MediaInfected", "MediaScannerUnavailable"]
