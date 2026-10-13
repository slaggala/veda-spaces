"""Closed request schemas for the attachment API (unknown fields → 422 UNKNOWN_FIELD)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from veda.kernel.dto import Closed, Id, Query, optional_text

from .models import MAX_OBJECT_BYTES
from .service import validate_sha256

# These Literals equal the 0106 CHECK value lists (models.ENTITY_TYPES, models.CATEGORIES); a test keeps them equal.
EntityType = Literal[
    "property",
    "property_space",
    "measurement_set",
    "space_wall",
    "space_opening",
    "space_electrical_point",
    "measurement_note",
]
Category = Literal["SITE_PHOTO", "LASER_READING", "SKETCH", "FLOOR_PLAN", "OTHER"]
ImageMime = Literal["image/jpeg", "image/png", "image/webp"]  # images only in B1; PDF floor plans deferred
ClientRef = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")]
Sha256 = Annotated[str, AfterValidator(validate_sha256)]
VariantName = Literal["thumb", "mobile", "desktop", "full"]


class AttachmentCreateIn(Closed):
    entity_type: EntityType
    entity_id: Id
    category_code: Category = "SITE_PHOTO"
    mime_type: ImageMime
    byte_size: Annotated[int, Field(ge=1, le=MAX_OBJECT_BYTES)]
    sha256: Sha256
    filename: Annotated[str | None, optional_text(255)] = None
    caption: Annotated[str | None, optional_text(200)] = None
    visibility_code: Literal["STANDARD", "INTERNAL"] = "STANDARD"
    client_ref: ClientRef | None = None


class AttachmentContentIn(Closed):
    """Local backend only (development and tests): the bytes, base64-encoded."""

    data_base64: Annotated[str, Field(min_length=4, max_length=(MAX_OBJECT_BYTES * 4) // 3 + 8)]


class AttachmentWithdrawIn(Closed):
    reason: Annotated[str | None, optional_text(200)] = None


class AttachmentListQuery(Query):
    entity_type: EntityType
    entity_id: Id
    include_withdrawn: bool = False


class AttachmentContentQuery(Query):
    variant: VariantName = "mobile"
