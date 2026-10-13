"""Offline batch sync (MTQ B1-T09; blueprint §6.1 (4), §11.1 ``/sync``; B1-SCOPE §2.8 offline).

A surveyor's client queues operations while offline and sends them in bounded batches. The server applies them in
the order given (deterministic), each in its own savepoint, and answers per operation; one failed operation never
undoes another. Nothing is last-write-wins:

- **Idempotent retries.** A space write whose content already equals the server state is a ``DUPLICATE`` (the earlier
  attempt landed; its response was lost), never a second write and never a conflict. Notes and attachments are
  idempotent by ``client_ref``. A whole batch replayed with the same ``Idempotency-Key`` returns the first response.
- **Conflicts.** A space write on a stale ``base_version`` with different content is a ``CONFLICT`` carrying the server
  state and the conflicting fields; the client resolves it and resends. A claimed space is ``CLAIMED``.
- **Revision awareness.** Operations against a revision that is no longer a draft are ``FROZEN`` and say which
  draft (if any) now holds the property, so the client rebases instead of writing into a sealed revision.
- **Attachment awareness.** An ``attachment`` operation registers the photo's metadata (before its bytes) and returns
  the upload instructions; the set can be submitted while uploads drain, never verified (B1-SCOPE §2.8).
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError
from veda.kernel.http import pydantic_errors

from . import capture as C
from . import sets
from .models import MeasurementSet, Property, SpaceMeasurement

MAX_OPERATIONS = 50
PASSED_THROUGH = (
    "current_version",
    "server",
    "conflicting_fields",
    "claimed_by",
    "claim_expires_on",
    "pointers",
    "limit",
)
STATUS_FOR_CODE = {
    "VERSION_CONFLICT": "CONFLICT",
    "SPACE_CLAIMED": "CLAIMED",
    "CLAIM_TAKE_OVER_REQUIRED": "CLAIMED",
    "SET_FROZEN": "FROZEN",
    "ENTITY_FROZEN": "FROZEN",
    "CLIENT_REF_REUSED": "REJECTED",
}


def _payload(model, data: dict) -> Any:
    return model.model_validate(data)


def _space_write(s: Session, ctx, mset: MeasurementSet, prop: Property, op) -> dict[str, Any]:
    payload = _payload(C.SpaceCaptureIn, op.data)
    existing = s.execute(
        sa.select(SpaceMeasurement).where(
            SpaceMeasurement.measurement_set_id == mset.id, SpaceMeasurement.space_id == op.space_id
        )
    ).scalar_one_or_none()
    if existing is not None and payload.base_version != existing.version:
        server = sets.present_measurement(s, existing)
        differences = sets._differences(server, payload)
        if not differences:  # the earlier attempt landed and its answer was lost: never write twice
            return {"status": "DUPLICATE", "entity_id": existing.id, "version": existing.version}
        if payload.base_version is None:  # the client thought it was first; someone else's data is there
            raise ApiError(409, "VERSION_CONFLICT", "This space was measured on the server meanwhile.",
                           extra={"current_version": existing.version, "server": server,
                                  "conflicting_fields": differences})  # fmt: skip
    sm, created = sets.upsert_space(s, ctx, mset, prop, op.space_id, payload)
    s.flush()
    return {"status": "APPLIED", "entity_id": sm.id, "version": sm.version, "created": created}


def _note(s: Session, ctx, mset: MeasurementSet, prop: Property, op) -> dict[str, Any]:
    payload = _payload(C.MeasurementNoteIn, op.data)
    note, created = sets.add_note(s, ctx, mset, prop, payload)
    s.flush()
    return {"status": "APPLIED" if created else "DUPLICATE", "entity_id": note.id, "version": note.version}


def _release(s: Session, ctx, mset: MeasurementSet, prop: Property, op) -> dict[str, Any]:
    sm = sets.release_claim(s, ctx, mset, prop, op.space_id)
    s.flush()
    return {"status": "APPLIED", "entity_id": sm.id, "version": sm.version}


def _property_capture(s: Session, ctx, mset: MeasurementSet, prop: Property, op) -> dict[str, Any]:
    payload = _payload(C.PropertyCaptureIn, op.data)
    new = payload.model_dump(exclude_none=True)
    if (mset.property_capture or {}) == new:
        return {"status": "DUPLICATE", "entity_id": mset.id, "version": mset.version}
    sets.update_set(s, ctx, mset, prop, C.SetPatchIn(property_capture=payload))
    s.flush()
    return {"status": "APPLIED", "entity_id": mset.id, "version": mset.version}


def _attachment(s: Session, ctx, mset: MeasurementSet, prop: Property, op) -> dict[str, Any]:
    from veda.modules.attachments import schemas as AS
    from veda.modules.attachments import service as att

    payload = _payload(AS.AttachmentCreateIn, op.data)
    if not payload.client_ref:
        raise ApiError(422, "VALIDATION_FAILED", "An offline attachment needs its client_ref.")
    row, created, warnings = att.create(s, ctx, payload)
    s.flush()
    return {"status": "APPLIED" if created else "DUPLICATE", "entity_id": row.id, "version": row.version,
            "upload": att.upload_instructions(row), "warnings": warnings}  # fmt: skip


HANDLERS = {
    "space": _space_write,
    "note": _note,
    "release": _release,
    "property_capture": _property_capture,
    "attachment": _attachment,
}


def _current_draft(s: Session, property_id: str) -> str | None:
    return s.execute(
        sa.select(MeasurementSet.id).where(MeasurementSet.property_id == property_id, MeasurementSet.status == "DRAFT")
    ).scalar_one_or_none()


def run(s: Session, ctx, mset: MeasurementSet, prop: Property, body) -> dict[str, Any]:
    # B1-PE-06: the whole batch holds the property lock submit/reject/verify take, so its duplicate and conflict reads
    # and its writes see one state of the revision; each write re-checks DRAFT under it (sets.lock_draft).
    sets.lock_property(s, prop.id)
    s.refresh(mset)
    results = []
    for op in body.operations:
        handler = HANDLERS[op.type]
        versioned = set(s.info.get("veda_versioned", set()))
        savepoint = s.begin_nested()
        try:
            outcome = handler(s, ctx, mset, prop, op)
            savepoint.commit()
        except ApiError as err:
            savepoint.rollback()
            s.info["veda_versioned"] = versioned  # the rolled-back writes never happened (version bookkeeping)
            extra = err.extra or {}
            outcome = {
                **{k: extra[k] for k in PASSED_THROUGH if k in extra},
                "set_status": extra.get("status"),  # the revision's own status, never the operation's
                "status": STATUS_FOR_CODE.get(err.code, "REJECTED"),
                "http_status": err.status,
                "code": err.code,
                "message": err.detail,
                **({"errors": err.errors} if err.errors else {}),
            }
            if err.code in ("SET_FROZEN", "ENTITY_FROZEN"):
                outcome["current_draft_id"] = _current_draft(s, prop.id)
        except ValidationError as err:
            savepoint.rollback()
            s.info["veda_versioned"] = versioned
            outcome = {"status": "REJECTED", "http_status": 422, "code": "VALIDATION_FAILED",
                       "errors": pydantic_errors(err)}  # fmt: skip
        results.append({"op_id": op.op_id, "type": op.type, "space_id": op.space_id, **outcome})
    s.flush()
    versions = dict(
        s.execute(
            sa.select(SpaceMeasurement.space_id, SpaceMeasurement.version).where(
                SpaceMeasurement.measurement_set_id == mset.id
            )
        ).all()
    )
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {
        "batch_id": body.batch_id,
        "measurement_set_id": mset.id,
        "set_status": mset.status,
        "server_time": clock.to_rfc3339(db.tx_time(s)),
        "results": results,
        "counts": counts,
        "space_versions": versions,
    }


def state(s: Session, mset: MeasurementSet) -> dict[str, Any]:
    """What a reconnecting client needs to reconcile its queue: per-space versions and claims, the set's state."""
    spaces = [
        {
            "space_id": sm.space_id,
            "measurement_id": sm.id,
            "version": sm.version,
            "client_ref": sm.client_ref,
            "captured_by": sm.captured_by,
            "claim_expires_on": clock.to_rfc3339(sm.claim_expires_on) if sm.claim_expires_on else None,
        }  # fmt: skip
        for sm in s.execute(sa.select(SpaceMeasurement).where(SpaceMeasurement.measurement_set_id == mset.id)).scalars()
    ]
    return {
        "measurement_set_id": mset.id,
        "set_status": mset.status,
        "set_version": mset.version,
        "current_draft_id": _current_draft(s, mset.property_id) if mset.status != "DRAFT" else mset.id,
        "server_time": clock.to_rfc3339(db.tx_time(s)),
        "spaces": spaces,
    }
