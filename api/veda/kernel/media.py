"""Kernel media utilities (MTQ B1-T01): pure, module-independent pieces shared by the catalogue media pipeline and
the attachment module (ATT).

Extracted from ``veda.modules.catalog.media`` without behaviour change. Nothing here imports a module's models or
settings: callers pass their own limits, key prefixes and scanner configuration, so the catalogue's behaviour is
exactly what it was and ATT reuses the same, already reviewed code paths.

- **Sniffing:** the declared type and the filename are never trusted; the first bytes decide.
- **Images:** header-checked complexity limits before any pixel is decoded (decompression bombs are refused unexpanded),
  Pillow's own guard at the same limit as a second line, EXIF orientation applied, every metadata block dropped, WebP
  variants at fixed widths.
- **Storage:** objects live under content-hash keys (``<prefix>/<sha256>``), never under an uploaded filename. A local
  store for development and tests; a private, KMS-encrypted S3 store elsewhere. Access denials are counted, never
  described (no key, bucket, filename or content in a signal).
- **Scanning:** a clamd INSTREAM client and a signature-age probe; a scanner error is an error, never "clean".
"""

from __future__ import annotations

import hashlib
import io
import re
import socket
import struct
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Protocol

from veda.kernel import clock, metrics

# The catalogue's limits (ADR-013 F1). Callers may pass stricter ones; none may pass looser ones than these hard caps.
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000  # 24 MP, for example 6000 × 4000
MAX_IMAGE_SIDE = 8_000
MIN_IMAGE_SIDE = 320
IMAGE_WIDTHS: Mapping[str, int] = {"thumb": 320, "mobile": 768, "desktop": 1600}
IMAGE_FORMATS: Mapping[str, str] = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
VARIANT_MIME = "image/webp"
VARIANT_QUALITY = 82

CONTENT_KEY_PREFIXES = ("source/", "variant/")  # the catalogue's prefixes; ATT passes its own
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MediaError(ValueError):
    """An upload was refused; the message never echoes file contents or names."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- storage keys ----------------------------------------------------------------------------------------------------
def content_key(prefix: str, sha256: str) -> str:
    """The storage key of an object: its prefix and its content hash. Never derived from a filename."""
    if not _SHA256_RE.match(sha256):
        raise MediaError("invalid storage key")
    return check_key(f"{prefix}{sha256}", (prefix,))


def check_key(key: str, prefixes: tuple[str, ...] = CONTENT_KEY_PREFIXES) -> str:
    """Refuse anything that is not ``<allowed prefix><64-character name>`` (no traversal, no other shapes)."""
    if not key.startswith(prefixes) or ".." in key or len(key.split("/")[-1]) != 64:
        raise MediaError("invalid storage key")
    return key


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    """Development and test object store."""

    def __init__(self, root: str | Path, prefixes: tuple[str, ...] = CONTENT_KEY_PREFIXES):
        self.root = Path(root)
        self.prefixes = prefixes

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self.root / check_key(key, self.prefixes)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)

    def get(self, key: str) -> bytes:
        return (self.root / check_key(key, self.prefixes)).read_bytes()

    def delete(self, key: str) -> None:
        (self.root / check_key(key, self.prefixes)).unlink(missing_ok=True)


class S3Storage:
    """A private, versioned bucket with every public-access block on and no ACLs; each object encrypted with KMS;
    keys are content hashes. Delivery goes through the API, never to the bucket directly."""

    def __init__(self, bucket: str, kms_key_arn: str | None, prefixes: tuple[str, ...] = CONTENT_KEY_PREFIXES):
        import boto3

        self.bucket, self.kms_key_arn, self.prefixes = bucket, kms_key_arn, prefixes
        self.client = boto3.client("s3")

    def put(self, key: str, data: bytes, content_type: str) -> None:
        extra = {"SSEKMSKeyId": self.kms_key_arn} if self.kms_key_arn else {}
        with storage_errors("put"):
            self.client.put_object(Bucket=self.bucket, Key=check_key(key, self.prefixes), Body=data,
                                   ContentType=content_type, ServerSideEncryption="aws:kms", **extra)  # fmt: skip

    def get(self, key: str) -> bytes:
        with storage_errors("get"):
            body = self.client.get_object(Bucket=self.bucket, Key=check_key(key, self.prefixes))["Body"].read()
        return bytes(body)

    def delete(self, key: str) -> None:
        with storage_errors("delete"):
            self.client.delete_object(Bucket=self.bucket, Key=check_key(key, self.prefixes))

    def presign_post(self, key: str, content_type: str, size: int, expires: int) -> dict:
        """A pre-signed POST for exactly one object (MTQ B1-T02): the key, the content type, the exact length and
        KMS encryption are conditions of the signature, so the client can upload only what the server agreed to.
        The server still reads the object back and checks its length and SHA-256 before using it."""
        fields = {"Content-Type": content_type, "x-amz-server-side-encryption": "aws:kms"}
        conditions: list = [
            {"Content-Type": content_type},
            {"x-amz-server-side-encryption": "aws:kms"},
            ["content-length-range", size, size],
        ]
        if self.kms_key_arn:
            fields["x-amz-server-side-encryption-aws-kms-key-id"] = self.kms_key_arn
            conditions.append({"x-amz-server-side-encryption-aws-kms-key-id": self.kms_key_arn})
        with storage_errors("presign"):
            post = self.client.generate_presigned_post(
                self.bucket, check_key(key, self.prefixes), Fields=fields, Conditions=conditions, ExpiresIn=expires
            )
        return {"url": post["url"], "fields": post["fields"], "expires_in": expires}


class storage_errors:  # noqa: N801 - a context manager used as `with storage_errors(op)`
    """Count S3 and KMS access denials (MediaStorageAccessDenied, MediaKmsAccessDenied) and re-raise. The signal names
    the operation and the error code only: never the key, the bucket, a filename or the content."""

    def __init__(self, op: str):
        self.op = op

    def __enter__(self) -> None:
        return None

    def __exit__(self, kind, err, tb) -> Literal[False]:
        code = str(getattr(err, "response", {}).get("Error", {}).get("Code", "")) if err is not None else ""
        if code.startswith("KMS") or code in (
            "KMS.AccessDeniedException",
            "AccessDeniedException",
            "KMS.DisabledException",
        ):
            metrics.emit("MediaKmsAccessDenied", 1, dimensions={"Operation": self.op})
        elif code in ("AccessDenied", "AllAccessDisabled", "InvalidObjectState"):
            metrics.emit("MediaStorageAccessDenied", 1, dimensions={"Operation": self.op})
        return False


# --- sniffing --------------------------------------------------------------------------------------------------------
def sniff(data: bytes) -> str:
    """The file type from its leading bytes: JPEG, PNG, WEBP, GLB, USDZ, VIDEO or GLTF; anything else is refused."""
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
    if data.lstrip()[:1] == b"{":
        return "GLTF"
    raise MediaError("unsupported file type (JPEG, PNG, WebP or GLB)")


def sniff_image(data: bytes) -> str:
    """JPEG, PNG or WEBP from the leading bytes; every other type (including PDF, video and 3D) is refused."""
    try:
        kind = sniff(data)
    except MediaError:
        kind = ""
    if kind not in IMAGE_FORMATS:
        raise MediaError("only JPEG, PNG or WebP images are accepted")
    return kind


# --- images ----------------------------------------------------------------------------------------------------------
def check_image_size(
    width: int,
    height: int,
    *,
    max_side: int = MAX_IMAGE_SIDE,
    max_pixels: int = MAX_IMAGE_PIXELS,
    min_side: int = MIN_IMAGE_SIDE,
) -> None:
    """The hard complexity limit, applied to the header's dimensions before any pixel is decoded."""
    if width > max_side or height > max_side:
        raise MediaError(f"images are at most {max_side} pixels on each side")
    if width * height > max_pixels:
        raise MediaError(f"images are at most {max_pixels:,} pixels")
    if min(width, height) < min_side:
        raise MediaError(f"images need at least {min_side} pixels on each side")


def image_variants(
    data: bytes,
    widths: Mapping[str, int] = IMAGE_WIDTHS,
    *,
    max_side: int = MAX_IMAGE_SIDE,
    max_pixels: int = MAX_IMAGE_PIXELS,
    min_side: int = MIN_IMAGE_SIDE,
    quality: int = VARIANT_QUALITY,
) -> tuple[list[tuple[str, bytes, int, int]], int, int]:
    """Decode safely, apply EXIF orientation, drop every metadata block and return WebP variants at ``widths``
    (never upscaled) with the upright width and height."""
    from PIL import Image, ImageOps

    limits = {"max_side": max_side, "max_pixels": max_pixels, "min_side": min_side}
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS  # Pillow's own guard, at the hard limit (second line of defence)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as header:  # reads the header only
                if header.format not in IMAGE_FORMATS:
                    raise MediaError("unsupported image format")
                check_image_size(*header.size, **limits)  # before verify() or load() touch the pixels
                header.verify()
            with Image.open(io.BytesIO(data)) as img:
                check_image_size(*img.size, **limits)
                img.load()
                upright = ImageOps.exif_transpose(img)
                width, height = upright.size
                check_image_size(width, height, **limits)
                base = upright.convert("RGBA" if "A" in upright.getbands() else "RGB")
    except MediaError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as err:  # Pillow's guard, same limit
        raise MediaError(f"images are at most {MAX_IMAGE_PIXELS:,} pixels") from err
    except Exception as err:  # noqa: BLE001 — any decoder failure (truncated, malformed) refuses the upload
        raise MediaError("the image could not be decoded safely") from err
    out = []
    for name, target in widths.items():
        w = min(target, width)
        h = max(1, round(height * w / width))
        variant = base.resize((w, h), Image.Resampling.LANCZOS) if w != width else base.copy()
        buf = io.BytesIO()
        variant.save(buf, "WEBP", quality=quality, method=4)  # no exif/icc/xmp passed: the variant carries no metadata
        out.append((name, buf.getvalue(), w, h))
    return out, width, height


# --- scanning --------------------------------------------------------------------------------------------------------
def clamd_scan(data: bytes, address: str) -> bool:
    """True when clamd reports the stream clean, False when it finds something; an error raises."""
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


def scan_outcome(data: bytes, *, mode: str, address: str, env: str, scan=None) -> str:
    """CLEAN, INFECTED or FAILED with a scanner (mode ``clamd``); without one, CLEAN only in local and test,
    otherwise PENDING. Every outcome is counted for the alarms (no filename, key or content in the signal); a scanner
    that cannot be reached or does not answer gives FAILED, which is never served and is retried."""
    if mode == "clamd":
        scan = scan or clamd_scan  # resolved at call time, so the client can be replaced in tests
        try:
            clean = scan(data, address)
        except OSError:
            metrics.emit("MediaScannerUnavailable", 1)
            return "FAILED"
        except (MediaError, ValueError):
            metrics.emit("MediaScanFailed", 1)
            return "FAILED"
        if not clean:
            metrics.emit("MediaInfected", 1)
        return "CLEAN" if clean else "INFECTED"
    return "CLEAN" if env in ("local", "test") else "PENDING"


def clamd_signature_age_hours(address: str, *, now=None) -> float | None:
    """Hours since the scanner's signature database was built (clamd VERSION: "ClamAV 1.4.1/27400/<date>"), or None
    when the scanner does not answer (counted as unavailable)."""
    from email.utils import parsedate_to_datetime

    host, _, port = address.rpartition(":")
    try:
        with socket.create_connection((host, int(port)), timeout=10) as sock:
            sock.sendall(b"zVERSION\0")
            reply = sock.recv(512).decode(errors="replace").strip("\0\n ")
    except OSError:
        metrics.emit("MediaScannerUnavailable", 1)
        return None
    parts = reply.split("/")
    try:
        built = parsedate_to_datetime(parts[2].strip() + " +0000") if len(parts) >= 3 else None
    except (TypeError, ValueError):
        built = None
    if built is None:
        return None
    return max(0.0, ((now or clock.now()) - built).total_seconds() / 3600)


__all__ = [
    "CONTENT_KEY_PREFIXES",
    "IMAGE_FORMATS",
    "IMAGE_WIDTHS",
    "MAX_IMAGE_BYTES",
    "MAX_IMAGE_PIXELS",
    "MAX_IMAGE_SIDE",
    "MIN_IMAGE_SIDE",
    "VARIANT_MIME",
    "LocalStorage",
    "MediaError",
    "ObjectStore",
    "S3Storage",
    "check_image_size",
    "check_key",
    "clamd_scan",
    "clamd_signature_age_hours",
    "content_key",
    "image_variants",
    "scan_outcome",
    "sha256_hex",
    "sniff",
    "sniff_image",
    "storage_errors",
]
