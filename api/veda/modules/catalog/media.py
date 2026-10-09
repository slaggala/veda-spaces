"""Catalog media (ADR-013 D6): admin-only uploads, private sources, generated variants, scanning, public delivery.

- Upload: staff with `catalog.media.edit` only (there is no public upload). Size-limited, content-sniffed (the declared
  type and filename are ignored), decoded with decompression-bomb limits.
- Images are re-encoded by Pillow: EXIF orientation applied, every metadata block dropped, delivered as WebP
  thumbnail, mobile and desktop variants.
- 3D: GLB (binary glTF 2.0) and USDZ (an uncompressed zip of USD layers) are validated structurally and may not
  reference external files. The model is delivery-only; nothing reads its geometry for price, scope or deliverability.
- Video: refused until a transcoder is approved (an owner decision); use an EXTERNAL_EMBED media record meanwhile.
- Objects are stored under their SHA-256 (`source/<sha>`, `variant/<sha>`), never under an uploaded filename.
- Scanning: clamd INSTREAM where configured. With no scanner, objects are CLEAN only in local and test; elsewhere
  they stay PENDING_SCAN, which release validation refuses (fail closed).
- Delivery: only a CLEAN variant referenced by the ACTIVE release is served publicly; sources never are.
"""

from __future__ import annotations

import hashlib
import io
import json
import socket
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import db

from .models import CatalogEvent, CatalogMediaObject, CatalogRecord

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_MODEL_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 40_000_000
IMAGE_WIDTHS = {"thumb": 320, "mobile": 768, "desktop": 1600}
IMAGE_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MODEL_MIME = {"GLB": "model/gltf-binary", "USDZ": "model/vnd.usdz+zip"}


class MediaError(ValueError):
    """An upload was refused; the message never echoes file contents or names."""


# --- storage ---------------------------------------------------------------------------------------------------------
class LocalStorage:
    """Development and test object store. Staging and production use an object bucket (owner decision, ADR-013)."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        if not key.startswith(("source/", "variant/")) or ".." in key or len(key.split("/")[-1]) != 64:
            raise MediaError("invalid storage key")
        return self.root / key

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()


def storage() -> LocalStorage:
    return LocalStorage(settings().catalog_media_dir)


# --- sniffing and validation -----------------------------------------------------------------------------------------
def sniff(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    if data[:4] == b"glTF":
        return "GLB"
    if data[:4] == b"PK\x03\x04":
        return "USDZ"
    if data[4:8] == b"ftyp":
        return "VIDEO"
    raise MediaError("unsupported file type (JPEG, PNG, WebP, GLB or USDZ)")


def _image_variants(data: bytes) -> tuple[list[tuple[str, bytes, int, int]], int, int]:
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # larger images raise DecompressionBombError
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in IMAGE_FORMATS:
                raise MediaError("unsupported image format")
            img.load()
            upright = ImageOps.exif_transpose(img)
            width, height = upright.size
            if min(width, height) < 320:
                raise MediaError("images need at least 320 pixels on each side")
            base = upright.convert("RGBA" if "A" in upright.getbands() else "RGB")
    except MediaError:
        raise
    except Exception as err:  # noqa: BLE001 — any decoder failure (truncated, bomb, malformed) refuses the upload
        raise MediaError("the image could not be decoded safely") from err
    out = []
    for name, target in IMAGE_WIDTHS.items():
        w = min(target, width)
        h = max(1, round(height * w / width))
        variant = base.resize((w, h), Image.Resampling.LANCZOS) if w != width else base.copy()
        buf = io.BytesIO()
        variant.save(buf, "WEBP", quality=82, method=4)  # no exif/icc/xmp passed: the variant carries no metadata
        out.append((name, buf.getvalue(), w, h))
    return out, width, height


def validate_glb(data: bytes) -> dict:
    """Binary glTF 2.0: header, a JSON chunk first, declared length matches, no external URIs."""
    if len(data) < 20:
        raise MediaError("the 3D file is truncated")
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise MediaError("the 3D file is not a valid binary glTF 2.0 file")
    chunk_len, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A or 20 + chunk_len > len(data):
        raise MediaError("the 3D file has no valid JSON chunk")
    try:
        doc = json.loads(data[20 : 20 + chunk_len])
    except ValueError as err:
        raise MediaError("the 3D file's JSON chunk is invalid") from err
    if not isinstance(doc, dict) or str((doc.get("asset") or {}).get("version")) != "2.0":
        raise MediaError("the 3D file is not glTF 2.0")
    for section in ("buffers", "images"):
        for item in doc.get(section) or []:
            if isinstance(item, dict) and "uri" in item:
                raise MediaError("the 3D file references external files; embed everything in the GLB")
    if doc.get("extensionsRequired"):
        raise MediaError("the 3D file requires extensions; export without required extensions")
    return {"meshes": len(doc.get("meshes") or []), "materials": len(doc.get("materials") or [])}


def validate_usdz(data: bytes) -> dict:
    """USDZ: a zip of USD layers and textures, stored uncompressed, with a USD layer first and no path escapes."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            if not infos or not infos[0].filename.lower().endswith((".usdc", ".usda", ".usd")):
                raise MediaError("the USDZ file must start with a USD layer")
            total = 0
            for info in infos:
                name = info.filename
                if name.startswith("/") or ".." in name.split("/") or info.compress_type != zipfile.ZIP_STORED:
                    raise MediaError("the USDZ file has an unsafe or compressed entry")
                if not name.lower().endswith((".usdc", ".usda", ".usd", ".png", ".jpg", ".jpeg")):
                    raise MediaError("the USDZ file contains an unsupported entry")
                total += info.file_size
            if total > MAX_MODEL_BYTES * 2:
                raise MediaError("the USDZ file is too large when unpacked")
    except zipfile.BadZipFile as err:
        raise MediaError("the USDZ file is not a valid archive") from err
    return {"entries": len(infos)}


# --- scanning --------------------------------------------------------------------------------------------------------
def clamd_scan(data: bytes, address: str) -> bool:
    """True when clamd reports the stream clean. Any failure is an error (the object stays PENDING_SCAN)."""
    host, _, port = address.rpartition(":")
    with socket.create_connection((host, int(port)), timeout=30) as sock:
        sock.sendall(b"zINSTREAM\0")
        for i in range(0, len(data), 64 * 1024):
            chunk = data[i : i + 64 * 1024]
            sock.sendall(struct.pack(">I", len(chunk)) + chunk)
        sock.sendall(struct.pack(">I", 0))
        reply = sock.recv(4096).decode(errors="replace").strip("\0\n ")
    if reply.endswith("OK"):
        return True
    if "FOUND" in reply:
        return False
    raise MediaError("the malware scanner did not answer")


def scan_status(data: bytes) -> str:
    cfg = settings()
    if cfg.catalog_media_scanner == "clamd":
        try:
            return "CLEAN" if clamd_scan(data, cfg.catalog_clamd_address) else "INFECTED"
        except (OSError, MediaError):
            return "PENDING_SCAN"
    return "CLEAN" if cfg.env in ("local", "test") else "PENDING_SCAN"


# --- upload ----------------------------------------------------------------------------------------------------------
@dataclass
class Uploaded:
    source: CatalogMediaObject
    variants: dict[str, CatalogMediaObject]

    def objects(self) -> dict:
        return {"source": self.source.object_sha256, "variants": {k: v.object_sha256 for k, v in self.variants.items()}}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _store(s: Session, data: bytes, *, role, kind, variant, mime, width, height, status, source=None):
    sha = _sha(data)
    existing = s.execute(
        sa.select(CatalogMediaObject).where(
            CatalogMediaObject.object_sha256 == sha, CatalogMediaObject.is_deleted.is_(False)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    key = f"{'source' if role == 'SOURCE' else 'variant'}/{sha}"
    storage().put(key, data)
    row = CatalogMediaObject(
        object_sha256=sha, role=role, media_kind=kind, variant=variant, mime_type=mime, byte_size=len(data),
        width=width, height=height, storage_key=key, scan_status=status,
        scanned_on=db.tx_time(s) if status != "PENDING_SCAN" else None,
        source_object_id=source.id if source is not None else None,
    )  # fmt: skip
    s.add(row)
    s.flush()
    return row


def upload(s: Session, data: bytes) -> Uploaded:
    """Validate, scan and store one upload; returns the private source and its delivery variants."""
    if not data:
        raise MediaError("the file is empty")
    kind = sniff(data)
    if kind == "VIDEO":
        raise MediaError("video uploads wait for an approved transcoder; use an external embed record instead")
    limit = MAX_MODEL_BYTES if kind in MODEL_MIME else MAX_IMAGE_BYTES
    if len(data) > limit:
        raise MediaError(f"the file is larger than {limit // (1024 * 1024)} MB")
    status = scan_status(data)
    if status == "INFECTED":
        s.add(CatalogEvent(event_type="MEDIA_SCANNED", detail={"sha256": _sha(data), "result": "INFECTED"}))
        raise MediaError("the malware scan refused this file")
    if kind in IMAGE_FORMATS:
        variants, width, height = _image_variants(data)
        source = _store(s, data, role="SOURCE", kind="IMAGE", variant="source", mime=IMAGE_FORMATS[kind],
                        width=width, height=height, status=status)  # fmt: skip
        made = {
            name: _store(
                s,
                blob,
                role="VARIANT",
                kind="IMAGE",
                variant=name,
                mime="image/webp",
                width=w,
                height=h,
                status=status,
                source=source,
            )  # fmt: skip
            for name, blob, w, h in variants
        }
    else:
        validate_glb(data) if kind == "GLB" else validate_usdz(data)
        source = _store(s, data, role="SOURCE", kind=kind, variant="source", mime=MODEL_MIME[kind], width=None,
                        height=None, status=status)  # fmt: skip
        # A validated model is delivered as is (re-export is the author's job); it is a separate, immutable object.
        made = {"web": _variant_copy(s, source, data, kind, status)}
    s.add(
        CatalogEvent(
            event_type="MEDIA_UPLOADED",
            detail={
                "sha256": source.object_sha256,
                "kind": source.media_kind,
                "scan": status,
                "variants": sorted(made),
            },
        )  # fmt: skip
    )
    return Uploaded(source=source, variants=made)


def _variant_copy(s: Session, source: CatalogMediaObject, data: bytes, kind: str, status: str) -> CatalogMediaObject:
    # A validated model is delivered unchanged, as its own object: its identifier is derived from the source hash so
    # that the private source and the public variant never share a key.
    sha = hashlib.sha256(b"variant:" + source.object_sha256.encode()).hexdigest()
    existing = s.execute(
        sa.select(CatalogMediaObject).where(CatalogMediaObject.object_sha256 == sha)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    key = f"variant/{sha}"
    storage().put(key, data)
    row = CatalogMediaObject(
        object_sha256=sha, role="VARIANT", media_kind=kind, variant="web", mime_type=MODEL_MIME[kind],
        byte_size=len(data), storage_key=key, scan_status=status,
        scanned_on=db.tx_time(s) if status != "PENDING_SCAN" else None, source_object_id=source.id,
    )  # fmt: skip
    s.add(row)
    s.flush()
    return row


def rescan_pending(s: Session) -> int:
    """Scan objects still PENDING_SCAN (scheduler); a source's result applies to its variants."""
    n = 0
    rows = s.execute(
        sa.select(CatalogMediaObject).where(
            CatalogMediaObject.scan_status == "PENDING_SCAN", CatalogMediaObject.role == "SOURCE"
        )
    ).scalars()
    for src in list(rows):
        status = scan_status(storage().get(src.storage_key))
        if status == "PENDING_SCAN":
            continue
        for row in [src, *s.execute(
            sa.select(CatalogMediaObject).where(CatalogMediaObject.source_object_id == src.id)
        ).scalars()]:  # fmt: skip
            row.scan_status, row.scanned_on = status, db.tx_time(s)
        s.add(CatalogEvent(event_type="MEDIA_SCANNED", detail={"sha256": src.object_sha256, "result": status}))
        n += 1
    return n


# --- delivery --------------------------------------------------------------------------------------------------------
def deliverable(s: Session, sha: str, *, release=None) -> CatalogMediaObject | None:
    """A CLEAN delivery variant referenced by `release` (the ACTIVE one for the public route), else None."""
    from . import service

    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        return None
    release = release if release is not None else service.active_release(s)
    if release is None:
        return None
    media_ids = [e["record_id"] for e in release.manifest["entries"] if e["kind"] == "media"]
    if not media_ids:
        return None
    referenced = False
    docs: list[dict[str, Any]] = list(
        s.execute(sa.select(CatalogRecord.document).where(CatalogRecord.id.in_(media_ids))).scalars()
    )
    for doc in docs:
        if sha in ((doc.get("objects") or {}).get("variants") or {}).values():
            referenced = True
            break
    if not referenced:
        return None
    row = s.execute(
        sa.select(CatalogMediaObject).where(
            CatalogMediaObject.object_sha256 == sha, CatalogMediaObject.is_deleted.is_(False)
        )
    ).scalar_one_or_none()
    if row is None or row.role != "VARIANT" or row.scan_status != "CLEAN":
        return None
    return row
