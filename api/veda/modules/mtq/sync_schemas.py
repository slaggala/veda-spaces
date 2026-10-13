"""Closed request schema for the offline sync batch (MTQ B1-T09). Each operation's ``data`` is validated against the
closed model of its type when it is applied (capture.SpaceCaptureIn, MeasurementNoteIn, PropertyCaptureIn,
attachments AttachmentCreateIn), so an invalid operation is rejected alone and never reaches a column."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from veda.kernel.dto import Closed, Id

from .schemas import ClientRef

OpType = Literal["space", "note", "release", "property_capture", "attachment"]


class SyncOperation(Closed):
    op_id: ClientRef  # the client's id for the queued operation; echoed in the result
    type: OpType
    space_id: Id | None = None
    data: Annotated[dict[str, Any], Field(max_length=40)] = {}

    @model_validator(mode="after")
    def _space(self):
        if self.type in ("space", "release") and self.space_id is None:
            raise ValueError(f"a {self.type} operation names its space")
        if self.type not in ("space", "release") and self.space_id is not None:
            raise ValueError("only space and release operations name a space")
        if self.type == "release" and self.data:
            raise ValueError("a release carries no data")
        return self


class SyncBatchIn(Closed):
    batch_id: ClientRef
    operations: Annotated[list[SyncOperation], Field(min_length=1, max_length=50)]

    @model_validator(mode="after")
    def _unique(self):
        ids = [o.op_id for o in self.operations]
        if len(set(ids)) != len(ids):
            raise ValueError("op_id values repeat within the batch")
        return self
