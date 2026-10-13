"""Catalog media (ADR-013 D6; V3 remediation F and G).

- **Uploads:** staff with `catalog.media.edit` only; there is no public upload. Each upload is size-limited and
  content-sniffed: the declared type and the filename are ignored.
- **Images (F1):** one hard limit of 24,000,000 pixels (24 MP, for example 6000 × 4000) and 8,000 pixels per side. Both
  are checked from the image header *before* any decoding, so a decompression bomb is refused without being expanded.
  Pillow's own bomb guard is set to the same limit and its warning is an error, as a second line. Accepted images are
  re-encoded: EXIF orientation is applied, every metadata block is dropped, and WebP thumbnail, mobile and desktop
  variants are produced.
- **3D (G1, G2):** only GLB, and only after sanitisation:
  - the container structure is checked and the file must have no external or data URIs;
  - only allow-listed extensions and top-level sections are accepted;
  - meshes, materials, textures, images, nodes, accessors and vertices are limited, and embedded images must be real
    PNG or JPEG;
  - `extras` and authoring metadata are stripped, and the result is rewritten into a new, generated object.

  glTF (JSON) and USDZ are disabled. A model never prices anything.
- **Video:** refused. Approved external embeds only (an owner decision).
- **Storage:** objects are stored under their SHA-256 (`source/<sha>`, `variant/<sha>`), never under an uploaded
  filename. Local files in development and tests. A private, versioned, encrypted S3 bucket with no public ACL is
  prepared (F2) but is not active until the owner approves the infrastructure.
- **Scanning:** PENDING, CLEAN, INFECTED or FAILED. clamd is used where configured. Without a scanner, objects are CLEAN
  only in local and test; elsewhere they stay PENDING. A scanner error is FAILED and is retried. Release validation
  refuses anything not CLEAN (fail closed).
- **Delivery:** only a CLEAN, unwithdrawn variant referenced by the ACTIVE release is served, and only while
  VEDA_CATALOG_MEDIA_DELIVERY_ENABLED is on. Sources are never served.
- **Retention (G3):**
  - a withdrawal (deletion request or withdrawn consent) deletes the stored bytes of a source and its variants at once
    and keeps the hashes, so release manifests stay intact while nothing is served;
  - unreferenced sources are purged after the retention period.
"""

from __future__ import annotations

import json
import socket  # noqa: F401 - kept: tests patch media.socket.create_connection for the signature probe
import struct
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db, metrics  # noqa: F401 - metrics: tests patch media.metrics.emit
from veda.kernel.media import (  # the shared kernel media library (MTQ B1-T01); re-exported under the old names
    IMAGE_FORMATS,
    IMAGE_WIDTHS,
    MAX_IMAGE_BYTES,
    LocalStorage,
    MediaError,
    ObjectStore,
    S3Storage,
    clamd_scan,
    clamd_signature_age_hours,
    image_variants,
    scan_outcome,
    sha256_hex,
    sniff,
)
from veda.kernel.media import (
    MAX_IMAGE_PIXELS as MAX_IMAGE_PIXELS,
)
from veda.kernel.media import (
    MAX_IMAGE_SIDE as MAX_IMAGE_SIDE,
)
from veda.kernel.media import (
    MIN_IMAGE_SIDE as MIN_IMAGE_SIDE,
)
from veda.kernel.media import (
    check_image_size as check_image_size,
)
from veda.kernel.media import storage_errors as _storage_errors  # noqa: F401 - re-exported for tests

from .models import CatalogEvent, CatalogMediaObject, CatalogRecord, CatalogRelease

MAX_MODEL_BYTES = 25 * 1024 * 1024
GLB_MIME = "model/gltf-binary"
GLB_LIMITS = {"meshes": 200, "materials": 64, "textures": 32, "images": 32, "nodes": 1000, "accessors": 4000,
              "bufferViews": 4000, "samplers": 32, "scenes": 4, "cameras": 8}  # fmt: skip
MAX_VERTICES = 500_000
GLB_SECTIONS = frozenset({
    "asset", "scene", "scenes", "nodes", "meshes", "materials", "textures", "images", "samplers", "accessors",
    "bufferViews", "buffers", "cameras", "extensionsUsed",
})  # fmt: skip
GLB_EXTENSIONS = frozenset({"KHR_materials_unlit", "KHR_texture_transform", "KHR_materials_emissive_strength"})
_JSON, _BIN = 0x4E4F534A, 0x004E4942


def storage() -> ObjectStore:
    cfg = settings()
    if cfg.catalog_media_backend == "s3":
        return S3Storage(cfg.catalog_media_bucket or "", cfg.catalog_media_kms_key_arn)
    return LocalStorage(cfg.catalog_media_dir)


def _image_variants(data: bytes) -> tuple[list[tuple[str, bytes, int, int]], int, int]:
    """The catalogue's delivery variants (thumb 320, mobile 768, desktop 1600; WebP, no metadata)."""
    return image_variants(data, IMAGE_WIDTHS)


# --- 3D (G2) ---------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class SanitizedModel:
    data: bytes
    meshes: int
    materials: int
    vertices: int


def _strip_extras(value: object) -> object:
    if isinstance(value, dict):
        return {k: _strip_extras(v) for k, v in value.items() if k != "extras"}
    if isinstance(value, list):
        return [_strip_extras(v) for v in value]
    return value


def _has_uri(value: object) -> bool:
    if isinstance(value, dict):
        return "uri" in value or any(_has_uri(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_uri(v) for v in value)
    return False


def sanitize_glb(data: bytes) -> SanitizedModel:
    """Validate a binary glTF 2.0 file against the safety rules and rewrite it into a new, minimal GLB."""
    if len(data) > MAX_MODEL_BYTES:
        raise MediaError(f"the 3D file is larger than {MAX_MODEL_BYTES // (1024 * 1024)} MB")
    if len(data) < 20:
        raise MediaError("the 3D file is truncated")
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise MediaError("the 3D file is not a valid binary glTF 2.0 file")
    chunks: list[tuple[int, bytes]] = []
    offset = 12
    while offset < len(data):
        if offset + 8 > len(data):
            raise MediaError("the 3D file is truncated")
        clen, ctype = struct.unpack_from("<II", data, offset)
        if offset + 8 + clen > len(data):
            raise MediaError("the 3D file has a chunk past its end")
        chunks.append((ctype, data[offset + 8 : offset + 8 + clen]))
        offset += 8 + clen
    if not chunks or chunks[0][0] != _JSON or len(chunks) > 2 or (len(chunks) == 2 and chunks[1][0] != _BIN):
        raise MediaError("the 3D file must hold one JSON chunk and at most one binary chunk")
    try:
        doc = json.loads(chunks[0][1])
    except ValueError as err:
        raise MediaError("the 3D file's JSON chunk is invalid") from err
    if not isinstance(doc, dict) or str((doc.get("asset") or {}).get("version")) != "2.0":
        raise MediaError("the 3D file is not glTF 2.0")
    unknown = set(doc) - GLB_SECTIONS - {"extensionsRequired", "extensions", "extras"}
    if unknown:
        raise MediaError("the 3D file has unsupported content (animations, skins or other sections)")
    if doc.get("extensionsRequired") or doc.get("extensions"):
        raise MediaError("the 3D file requires extensions; export without them")
    if set(doc.get("extensionsUsed") or []) - GLB_EXTENSIONS:
        raise MediaError("the 3D file uses unsupported extensions")
    if _has_uri(doc):
        raise MediaError("the 3D file references external or embedded URIs; pack everything in the binary chunk")
    for section, limit in GLB_LIMITS.items():
        if len(doc.get(section) or []) > limit:
            raise MediaError(f"the 3D file has more than {limit} {section}")
    binary = chunks[1][1] if len(chunks) == 2 else b""
    buffers = doc.get("buffers") or []
    if len(buffers) > 1 or (buffers and int(buffers[0].get("byteLength", -1)) > len(binary)):
        raise MediaError("the 3D file's buffer does not match its binary chunk")
    views = doc.get("bufferViews") or []
    for view in views:
        start, size = int(view.get("byteOffset", 0)), int(view.get("byteLength", -1))
        if view.get("buffer") != 0 or start < 0 or size < 0 or start + size > len(binary):
            raise MediaError("the 3D file has a buffer view outside its binary chunk")
    for image in doc.get("images") or []:
        if image.get("mimeType") not in ("image/png", "image/jpeg") or not isinstance(image.get("bufferView"), int):
            raise MediaError("3D textures are embedded PNG or JPEG images only")
        view = views[image["bufferView"]] if image["bufferView"] < len(views) else None
        if view is None:
            raise MediaError("the 3D file has a texture outside its binary chunk")
        blob = binary[int(view.get("byteOffset", 0)) : int(view.get("byteOffset", 0)) + int(view["byteLength"])]
        try:
            actual = sniff(blob)
        except MediaError:
            actual = ""
        if actual != {"image/png": "PNG", "image/jpeg": "JPEG"}[image["mimeType"]]:
            raise MediaError("a 3D texture is not the image type it claims")
    accessors = doc.get("accessors") or []
    vertices = 0
    for mesh in doc.get("meshes") or []:
        for prim in mesh.get("primitives") or []:
            index = (prim.get("attributes") or {}).get("POSITION")
            if isinstance(index, int) and index < len(accessors):
                vertices += int(accessors[index].get("count", 0))
    if vertices > MAX_VERTICES:
        raise MediaError(f"the 3D file has more than {MAX_VERTICES:,} vertices")
    clean = _strip_extras(doc)
    if not isinstance(clean, dict):  # _strip_extras keeps a dict a dict; refuse rather than assume
        raise MediaError("the 3D file is not glTF 2.0")
    clean["asset"] = {"version": "2.0"}  # authoring metadata (generator, copyright) is not kept
    js = json.dumps(clean, separators=(",", ":"), ensure_ascii=True).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), _JSON) + js
    if binary:
        padded = binary + b"\0" * (-len(binary) % 4)
        body += struct.pack("<II", len(padded), _BIN) + padded
    out = struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body
    return SanitizedModel(out, len(clean.get("meshes") or []), len(clean.get("materials") or []), vertices)


def three_d_uploads_ready() -> bool:
    """R12 safe disablement: a GLB is accepted only when the approved private store, the malware scanner, approved
    media delivery and the 3D switch are all in place. None of them is today, so GLB uploads are refused everywhere,
    including local and test. The sanitiser above is kept for when 3D is approved."""
    cfg = settings()
    return bool(
        cfg.catalog_3d_enabled
        and cfg.catalog_media_backend == "s3"
        and cfg.catalog_media_bucket
        and cfg.catalog_media_scanner == "clamd"
        and cfg.catalog_media_delivery_enabled
    )


# --- scanning --------------------------------------------------------------------------------------------------------
def scan_status(data: bytes) -> str:
    """CLEAN, INFECTED or FAILED with a scanner; without one, CLEAN only in local and test, otherwise PENDING.
    Every outcome is counted for the alarms (no filename, key or content in the signal); a scanner that cannot be
    reached or does not answer leaves the object FAILED, which is never served and is retried."""
    cfg = settings()
    mode = cfg.catalog_media_scanner
    # The address is read only when a scanner is configured, as before; the lambda resolves clamd_scan at call time.
    address = cfg.catalog_clamd_address if mode == "clamd" else ""
    return scan_outcome(data, mode=mode, address=address, env=cfg.env, scan=lambda blob, a: clamd_scan(blob, a))


# --- upload ----------------------------------------------------------------------------------------------------------
@dataclass
class Uploaded:
    source: CatalogMediaObject
    variants: dict[str, CatalogMediaObject]

    def objects(self) -> dict:
        return {"source": self.source.object_sha256, "variants": {k: v.object_sha256 for k, v in self.variants.items()}}


def _sha(data: bytes) -> str:
    return sha256_hex(data)


def _store(s: Session, data: bytes, *, role: str, kind: str, variant: str, mime: str, width: int | None,
           height: int | None, status: str, source: CatalogMediaObject | None = None) -> CatalogMediaObject:  # fmt: skip
    sha = _sha(data)
    existing = s.execute(
        sa.select(CatalogMediaObject).where(CatalogMediaObject.object_sha256 == sha, CatalogMediaObject.role == role)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    key = f"{'source' if role == 'SOURCE' else 'variant'}/{sha}"
    storage().put(key, data, mime)
    row = CatalogMediaObject(
        object_sha256=sha, role=role, media_kind=kind, variant=variant, mime_type=mime, byte_size=len(data),
        width=width, height=height, storage_key=key, scan_status=status,
        scanned_on=db.tx_time(s) if status not in ("PENDING", "FAILED") else None,
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
        raise MediaError("video uploads are not accepted; use an approved external embed (owner decision)")
    if kind in ("USDZ", "GLTF"):
        raise MediaError("USDZ and glTF are not supported")
    if kind == "GLB" and not three_d_uploads_ready():
        raise MediaError("3D uploads are disabled until approved storage, scanning, delivery and 3D are in place")
    limit = MAX_MODEL_BYTES if kind == "GLB" else MAX_IMAGE_BYTES
    if len(data) > limit:
        raise MediaError(f"the file is larger than {limit // (1024 * 1024)} MB")
    if kind == "GLB":
        model = sanitize_glb(data)  # validated and rewritten before anything is stored
    else:
        images, width, height = _image_variants(data)
    status = scan_status(data)
    if status == "INFECTED":
        s.add(CatalogEvent(event_type="MEDIA_SCANNED", detail={"sha256": _sha(data), "result": "INFECTED"}))
        raise MediaError("the malware scan refused this file")
    if kind == "GLB":
        source = _store(s, data, role="SOURCE", kind="GLB", variant="source", mime=GLB_MIME, width=None, height=None,
                        status=status)  # fmt: skip
        made = {"web": _store(s, model.data, role="VARIANT", kind="GLB", variant="web", mime=GLB_MIME, width=None,
                              height=None, status=status, source=source)}  # fmt: skip
    else:
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
            for name, blob, w, h in images
        }
    s.add(CatalogEvent(event_type="MEDIA_UPLOADED", detail={"sha256": source.object_sha256, "kind": source.media_kind,
                                                            "scan": status, "variants": sorted(made)}))  # fmt: skip
    return Uploaded(source=source, variants=made)


def _family(s: Session, source: CatalogMediaObject) -> list[CatalogMediaObject]:
    return [
        source,
        *s.execute(sa.select(CatalogMediaObject).where(CatalogMediaObject.source_object_id == source.id)).scalars(),
    ]


def rescan_pending(s: Session) -> int:
    """Scan sources still PENDING or FAILED (scheduler); a source's result applies to its variants."""
    n = 0
    rows = s.execute(
        sa.select(CatalogMediaObject).where(
            CatalogMediaObject.scan_status.in_(("PENDING", "FAILED")),
            CatalogMediaObject.role == "SOURCE",
            CatalogMediaObject.withdrawn_on.is_(None),
        )
    ).scalars()
    pending = list(rows)
    now = clock.now()
    ages = [(now - (r.created_on if r.created_on.tzinfo else r.created_on.replace(tzinfo=now.tzinfo))).total_seconds()
            for r in pending]  # fmt: skip
    metrics.emit("MediaPendingMaxAgeSeconds", max(ages) if ages else 0, "Seconds")
    cfg = settings()
    if cfg.catalog_media_scanner == "clamd":
        age = clamd_signature_age_hours(cfg.catalog_clamd_address)
        if age is not None:
            metrics.emit("MediaSignatureAgeHours", age, "None")
    for src in pending:
        status = scan_status(storage().get(src.storage_key))
        if status in ("PENDING", "FAILED") and status == src.scan_status:
            continue
        for row in _family(s, src):
            row.scan_status = status
            row.scanned_on = db.tx_time(s) if status not in ("PENDING", "FAILED") else None
        s.add(CatalogEvent(event_type="MEDIA_SCANNED", detail={"sha256": src.object_sha256, "result": status}))
        n += 1
    return n


# --- retention (G3) --------------------------------------------------------------------------------------------------
def _source_of(s: Session, sha: str) -> CatalogMediaObject:
    row = s.execute(sa.select(CatalogMediaObject).where(CatalogMediaObject.object_sha256 == sha)).scalars().first()
    if row is None:
        raise MediaError("no such media object")
    if row.role == "VARIANT" and row.source_object_id:
        source = s.get(CatalogMediaObject, row.source_object_id)
        if source is not None:
            return source
    return row


def withdraw(s: Session, sha: str, reason: str) -> int:
    """A deletion request or withdrawn consent: the source and every variant stop being served and their bytes are
    deleted now. The rows keep their hashes, so manifests and history stay intact. Releases that still name the media
    no longer validate."""
    if len((reason or "").strip()) < 10:
        raise MediaError("say why the media is withdrawn (at least 10 characters)")
    source = _source_of(s, sha)
    now = db.tx_time(s)
    family = _family(s, source)
    for row in family:
        if row.withdrawn_on is None:
            storage().delete(row.storage_key)
            row.withdrawn_on, row.withdrawal_reason, row.purged_on = now, reason.strip()[:200], now
    s.add(CatalogEvent(event_type="MEDIA_WITHDRAWN", detail={"sha256": source.object_sha256, "objects": len(family)}))
    return len(family)


def referenced_hashes(s: Session) -> set[str]:
    """Every hash named by a media record that is not archived (any version, any status but ARCHIVED)."""
    found: set[str] = set()
    docs: list[dict[str, Any]] = list(
        s.execute(
            sa.select(CatalogRecord.document).where(CatalogRecord.kind == "media", CatalogRecord.status != "ARCHIVED")
        ).scalars()
    )
    for doc in docs:
        objects = doc.get("objects") or {}
        found.update(v for v in (objects.get("variants") or {}).values())
        if objects.get("source"):
            found.add(objects["source"])
    return found


def purge_unreferenced(s: Session, *, dry_run: bool = False) -> int:
    """Delete the bytes of sources (and their variants) that no live media record names, once the retention period
    has passed since upload. Rows and hashes stay for the audit trail."""
    cutoff = db.tx_time(s) - timedelta(days=settings().catalog_media_retention_days)
    keep = referenced_hashes(s)
    n = 0
    sources = s.execute(
        sa.select(CatalogMediaObject).where(
            CatalogMediaObject.role == "SOURCE", CatalogMediaObject.purged_on.is_(None),
            CatalogMediaObject.created_on < cutoff,
        )
    ).scalars()  # fmt: skip
    for source in list(sources):
        family = _family(s, source)
        if any(row.object_sha256 in keep for row in family):
            continue
        n += 1
        if not dry_run:
            for row in family:
                storage().delete(row.storage_key)
                row.purged_on = db.tx_time(s)
            s.add(CatalogEvent(event_type="MEDIA_PURGED", detail={"sha256": source.object_sha256}))
    return n


# --- delivery --------------------------------------------------------------------------------------------------------
def deliverable(s: Session, sha: str, *, release: CatalogRelease | None = None) -> CatalogMediaObject | None:
    """A CLEAN, unwithdrawn delivery variant referenced by `release` (the ACTIVE one for the public route), else None."""
    from . import service

    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        return None
    release = release if release is not None else service.active_release(s)
    if release is None:
        return None
    media_ids = [e["record_id"] for e in release.manifest["entries"] if e["kind"] == "media"]
    if not media_ids:
        return None
    docs: list[dict[str, Any]] = list(
        s.execute(sa.select(CatalogRecord.document).where(CatalogRecord.id.in_(media_ids))).scalars()
    )
    referencing = [doc for doc in docs if sha in ((doc.get("objects") or {}).get("variants") or {}).values()]
    if not referencing:
        return None
    today = clock.now().date()
    for doc in referencing:  # rights checked at serve time too: expired or not-yet-effective rights stop serving
        rights = doc.get("rights") or {}
        expires, effective = rights.get("expires"), rights.get("effective_from")
        if (expires and str(expires) < today.isoformat()) or (effective and str(effective) > today.isoformat()):
            return None
    row = s.execute(
        sa.select(CatalogMediaObject).where(
            CatalogMediaObject.object_sha256 == sha, CatalogMediaObject.role == "VARIANT"
        )
    ).scalar_one_or_none()
    if row is None or row.scan_status != "CLEAN" or row.withdrawn_on is not None or row.purged_on is not None:
        if row is not None and row.scan_status != "CLEAN":
            metrics.emit("MediaNonCleanRequested", 1)  # a released, referenced object that is not CLEAN was asked for
        return None
    if row.media_kind != "IMAGE":  # R12: a 3D object is never served, whatever references it or whoever knows its hash
        return None
    return row
