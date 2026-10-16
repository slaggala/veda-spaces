"""Photos of service requests (WSV-018): the attachment pipeline, reached by customers only through portal routes.

The ``service_request`` entity binding resolves a request to its customer record, accepts uploads while the request is
open and lets only staff holding ``warranty.service.triage`` withdraw one, with a reason. Customers add at most
``MAX_CUSTOMER_PHOTOS`` photos per request, only while it is REPORTED or INFORMATION_REQUESTED, through
``create`` / ``receive`` / ``complete``: images only, at most 15 MiB, content-hash checked, scanned and re-encoded by the
attachment module, and delivered only when CLEAN (``attachments.service.is_available``). The account that added each
photo is on its ``service_request_photo`` row. Every read goes through the account's authorised property; there is no
public or predictable URL.
"""

from __future__ import annotations

import hashlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError, not_found
from veda.modules.attachments import registry

from . import access, events
from . import vocab as V
from .models import ServiceEvidence, ServiceRequest, ServiceRequestPhoto

CUSTOMER_STATES = (V.REPORTED, V.INFORMATION_REQUESTED)


def _resolve(s: Session, entity_id: str) -> registry.EntityContext | None:
    r = s.get(ServiceRequest, entity_id)
    if r is None or r.is_deleted:
        return None
    return registry.EntityContext(lead_id=r.lead_id, writable=r.status != V.CLOSED, withdraw_rule="VERIFIER_WITH_REASON",
                                  extra={"verify_permission": "warranty.service.triage"})  # fmt: skip


registry.bind(registry.EntityBinding("service_request", _resolve))


def rows(s: Session, r: ServiceRequest) -> list[ServiceRequestPhoto]:
    return list(s.execute(sa.select(ServiceRequestPhoto).where(ServiceRequestPhoto.request_id == r.id,
                                                               ServiceRequestPhoto.is_deleted == sa.false())
                          .order_by(ServiceRequestPhoto.created_on)).scalars())  # fmt: skip


def create(
    s: Session, r: ServiceRequest, account_id: str, body, key: str | None
) -> tuple[Any, ServiceRequestPhoto, bool]:
    """(attachment, link, created): a customer's photo, declared before its bytes are uploaded."""
    from veda.modules.attachments import service as att

    if not key or not 8 <= len(key) <= 128:
        raise ApiError(400, "IDEMPOTENCY_KEY_REQUIRED", "Send an Idempotency-Key header (8 to 128 characters).")
    access.lock(s, r)
    access.lead_open(s, r.lead_id)
    client_ref = "wsv-" + hashlib.sha256(f"{account_id}:{key}".encode()).hexdigest()[:56]
    mine = [x for x in rows(s, r) if x.channel == "PORTAL"]
    existing = next((x for x in mine if (a := s.get(att.Attachment, x.attachment_id)) is not None
                     and a.client_ref == client_ref), None)  # fmt: skip
    if existing is None:
        access.state(r, *CUSTOMER_STATES)
        if len(mine) >= V.MAX_CUSTOMER_PHOTOS:
            raise ApiError(409, "PHOTO_LIMIT_REACHED", f"A request takes at most {V.MAX_CUSTOMER_PHOTOS} photos.")
    a, created = att.create_for_portal(
        s, entity_type="service_request", entity_id=r.id, body=body, client_ref=client_ref
    )
    if not created and existing is not None:
        return a, existing, False
    link = ServiceRequestPhoto(request_id=r.id, lead_id=r.lead_id, attachment_id=a.id, channel="PORTAL",
                               account_id=account_id)  # fmt: skip
    s.add(link)
    s.flush()
    events.record(s, r, "PHOTO_ADDED", frm=r.status, to=r.status, account_id=account_id, attachment_id=a.id)
    return a, link, True


def link_for(s: Session, r: ServiceRequest, photo_id: str) -> tuple[ServiceRequestPhoto, Any]:
    from veda.modules.attachments.models import Attachment

    link = s.get(ServiceRequestPhoto, photo_id)
    if link is None or link.request_id != r.id or link.is_deleted:
        raise not_found()
    a = s.get(Attachment, link.attachment_id)
    if a is None or a.lead_id != r.lead_id or a.entity_type != "service_request" or a.entity_id != r.id:
        raise not_found()
    return link, a


def instructions(a, property_id: str, request_id: str, photo_id: str) -> dict[str, Any]:
    """The attachment module's upload instructions, pointed at the portal routes (never the staff ones)."""
    from veda.modules.attachments import service as att

    base = f"/api/v1/public/portal/properties/{property_id}/service-requests/{request_id}/photos/{photo_id}"
    out = dict(att.upload_instructions(a))
    if not out.get("required"):
        return out
    if out.get("method") == "PUT":
        out["url"] = f"{base}/content"
    out["then"] = f"{base}/complete"
    return out


def customer_list(s: Session, r: ServiceRequest) -> list[dict[str, Any]]:
    from veda.modules.attachments import service as att
    from veda.modules.attachments.models import Attachment

    out = []
    for link in rows(s, r):
        a = s.get(Attachment, link.attachment_id)
        if a is None:
            continue
        state = "AVAILABLE" if att.is_available(a) else ("CHECKING" if a.retention_state == "ACTIVE"
                                                          and a.upload_status != "REJECTED"
                                                          and a.scan_status == "PENDING" else "NOT_AVAILABLE")  # fmt: skip
        out.append({"id": link.id, "state": state, "added_by": "YOU" if link.channel == "PORTAL" else "VEDA_SPACES"})
    return out


def visible_evidence(s: Session, r: ServiceRequest) -> list[ServiceEvidence]:
    from veda.modules.attachments import service as att
    from veda.modules.attachments.models import Attachment

    found = s.execute(sa.select(ServiceEvidence).where(ServiceEvidence.request_id == r.id,
                                                       ServiceEvidence.customer_visible == sa.true(),
                                                       ServiceEvidence.is_deleted == sa.false())
                      .order_by(ServiceEvidence.created_on)).scalars()  # fmt: skip
    out = []
    for ev in found:
        a = s.get(Attachment, ev.attachment_id)
        if a is not None and att.is_available(a) and a.visibility_code == "STANDARD":
            out.append(ev)
    return out


def evidence_for(s: Session, r: ServiceRequest, evidence_id: str):
    from veda.modules.attachments.models import Attachment

    ev = next((x for x in visible_evidence(s, r) if x.id == evidence_id), None)
    if ev is None:
        raise not_found()
    return ev, s.get(Attachment, ev.attachment_id)
