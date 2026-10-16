"""Customer-visible project documents (CPP-D04, decision log 46).

The owner decided that the Customer Project Portal may show customer-visible project documents. Visibility is always
explicit: an attachment never becomes visible because it belongs to the project. A person with
``project.publish_document`` on the project publishes one site photograph of the project's own property as one class
(``vocab.CUSTOMER_DOCUMENT_CLASSES``) with a title in customer wording; withdrawing keeps the row and its history.

Refused at publication: an attachment of another customer record, one that is not scanned clean and available, and one
the attachment module marks INTERNAL (floor plans and anything staff kept internal). The bytes are served only through
the customer route, which re-checks on every request the account's access to the property, that the row is still
PUBLISHED and that the attachment is still available (``content_for``); there is no public or predictable URL.

Other customer documents (issued quotations, invoices and receipts, the handover summary) are already customer-safe
projections of their own modules and are listed by the portal from those modules; nothing here re-publishes them.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError, field_error, not_found

from . import access
from . import vocab as V
from .models import Project, ProjectCustomerDocument

CODE = "project.publish_document"


def rows(s: Session, p: Project, *, published_only: bool = False) -> list[ProjectCustomerDocument]:
    q = sa.select(ProjectCustomerDocument).where(ProjectCustomerDocument.project_id == p.id,
                                                 ProjectCustomerDocument.is_deleted == sa.false())  # fmt: skip
    if published_only:
        q = q.where(ProjectCustomerDocument.status == "PUBLISHED")
    return list(
        s.execute(q.order_by(ProjectCustomerDocument.published_on.desc(), ProjectCustomerDocument.id)).scalars()
    )


def _attachment(s: Session, attachment_id: str):
    from veda.modules.attachments.models import Attachment

    return s.get(Attachment, attachment_id)


def _of_property(s: Session, a, property_id: str) -> bool:
    """The attachment is a photograph of this property (attached to it, or to one of its spaces)."""
    if a.entity_type == "property":
        return a.entity_id == property_id
    if a.entity_type == "property_space":
        from veda.modules.mtq.models import PropertySpace

        sp = s.get(PropertySpace, a.entity_id)
        return sp is not None and sp.property_id == property_id
    return False


def _options_query(p: Project):
    """Shareable attachments: site photographs of this property, live, scanned clean, not internal, not shown now."""
    from veda.modules.attachments.models import Attachment
    from veda.modules.mtq.models import PropertySpace

    shown = sa.select(ProjectCustomerDocument.attachment_id).where(ProjectCustomerDocument.project_id == p.id,
                                                                   ProjectCustomerDocument.status == "PUBLISHED",
                                                                   ProjectCustomerDocument.is_deleted == sa.false())  # fmt: skip
    spaces = sa.select(PropertySpace.id).where(PropertySpace.property_id == p.property_id)
    return (sa.select(Attachment).where(
        Attachment.lead_id == p.lead_id, Attachment.is_deleted == sa.false(), Attachment.retention_state == "ACTIVE",
        Attachment.scan_status == "CLEAN", Attachment.visibility_code == "STANDARD",
        Attachment.category_code.in_(V.CUSTOMER_DOCUMENT_CATEGORIES), Attachment.id.not_in(shown),
        sa.or_(sa.and_(Attachment.entity_type == "property", Attachment.entity_id == p.property_id),
               sa.and_(Attachment.entity_type == "property_space", Attachment.entity_id.in_(spaces))),
    ).order_by(Attachment.created_on.desc()).limit(100))  # fmt: skip


def _publishable(s: Session, p: Project, attachment_id: str):
    from veda.modules.attachments import service as att

    a = _attachment(s, attachment_id)
    if a is None or a.lead_id != p.lead_id or a.is_deleted or not _of_property(s, a, p.property_id):
        raise ApiError(422, "VALIDATION_FAILED", "Choose an attachment of this project's property.",
                       errors=[field_error("attachment_id", "UNKNOWN_ATTACHMENT", "Not an attachment of this "
                                           "project.")])  # fmt: skip
    if not att.is_available(a):
        raise ApiError(422, "DOCUMENT_NOT_AVAILABLE", "Only a scanned, available attachment can be shown to the "
                       "customer.", errors=[field_error("attachment_id", "NOT_AVAILABLE", "Not scanned clean and "
                                                        "available.")])  # fmt: skip
    if a.visibility_code != "STANDARD":
        raise ApiError(422, "DOCUMENT_INTERNAL", "This attachment is internal and cannot be shown to the customer.",
                       errors=[field_error("attachment_id", "INTERNAL", "Internal attachments stay staff-only.")])  # fmt: skip
    if a.category_code not in V.CUSTOMER_DOCUMENT_CATEGORIES:
        raise ApiError(422, "DOCUMENT_CLASS_NOT_ALLOWED", "Only site photographs can be shown to the customer; sketches, "
                       "laser readings and floor plans are survey working material.",
                       errors=[field_error("attachment_id", "NOT_A_PHOTOGRAPH", "Not a site photograph.")])  # fmt: skip
    return a


def _open(s: Session, p: Project) -> None:
    from veda.modules.crm.leads.models import Lead

    lead = s.get(Lead, p.lead_id)
    if lead is None or lead.anonymized_on is not None:
        raise ApiError(409, "INVALID_STATE", "This project's customer record was erased; nothing can be published.")


def publish(s: Session, ctx, p: Project, body) -> ProjectCustomerDocument:
    """A new publication (a handed-over project may still receive its handover photographs)."""
    access.require(s, ctx, p, CODE)
    access.lock(s, p)
    _open(s, p)
    a = _publishable(s, p, body.attachment_id)
    title = body.title.strip()
    current = next((d for d in rows(s, p, published_only=True) if d.attachment_id == a.id), None)
    if current is not None:
        if (current.document_class, current.title) == (body.document_class, title):
            return current  # a repeated publication of the same thing changes nothing
        raise ApiError(409, "ALREADY_PUBLISHED", "This attachment is already shown to the customer; withdraw it first "
                       "to show it differently.", extra={"document_id": current.id})  # fmt: skip
    d = ProjectCustomerDocument(project_id=p.id, lead_id=p.lead_id, attachment_id=a.id,
                                document_class=body.document_class, title=title, status="PUBLISHED",
                                published_by=ctx.user.id, published_on=db.tx_time(s))  # fmt: skip
    s.add(d)
    access.touch(s, p)
    s.flush()
    return d


def withdraw(s: Session, ctx, p: Project, d: ProjectCustomerDocument, reason: str | None,
             if_match: int | None) -> ProjectCustomerDocument:  # fmt: skip
    from veda.kernel.http import check_version

    access.require(s, ctx, p, CODE)
    access.lock(s, p, d)
    check_version(if_match, d.version)
    if d.status != "PUBLISHED":
        raise ApiError(409, "INVALID_STATE", "This document is no longer shown to the customer.")
    text = (reason or "").strip()
    if len(text) < 5:
        raise ApiError(422, "VALIDATION_FAILED", "Say why it is withdrawn (at least 5 characters).",
                       errors=[field_error("reason", "REASON_REQUIRED", "At least 5 characters.")])  # fmt: skip
    d.status, d.withdrawn_by, d.withdrawn_on, d.withdrawn_reason = "WITHDRAWN", ctx.user.id, db.tx_time(s), text
    access.touch(s, p)
    s.flush()
    return d


def staff_view(s: Session, ctx, p: Project, people) -> dict[str, Any]:
    """The staff list (with history) and, for a publisher, the attachments that could be published."""
    from veda.modules.attachments import service as att

    out = []
    for d in rows(s, p):
        a = _attachment(s, d.attachment_id)
        out.append({"id": d.id, "version": d.version, "attachment_id": d.attachment_id,
                    "document_class": d.document_class, "class_label": V.CUSTOMER_DOCUMENT_CLASSES[d.document_class],
                    "title": d.title, "status": d.status, "published_on": clock.to_rfc3339(d.published_on),
                    "published_by": people(d.published_by),
                    "withdrawn_on": clock.to_rfc3339(d.withdrawn_on) if d.withdrawn_on else None,
                    "withdrawn_by": people(d.withdrawn_by), "withdrawn_reason": d.withdrawn_reason,
                    "available": a is not None and att.is_available(a)})  # fmt: skip
    can = access.can(s, ctx, p, CODE)
    options: list[dict[str, Any]] = []
    if can:
        options = [{"id": a.id, "category": a.category_code, "attached_to": a.entity_type,
                    "uploaded_on": clock.to_rfc3339(a.created_on)}
                   for a in s.execute(_options_query(p)).scalars() if att.is_available(a)]  # fmt: skip
    return {"documents": out, "can_publish": can, "options": options,
            "classes": [{"code": k, "label": v} for k, v in V.CUSTOMER_DOCUMENT_CLASSES.items()]}  # fmt: skip


# --- customer --------------------------------------------------------------------------------------------------------
def customer_list(s: Session, p: Project) -> list[dict[str, Any]]:
    """What the customer sees: published, still available, customer wording only (no file name, uploader or id of
    the attachment). The id is the publication's, used only with the account's authorised property."""
    from veda.modules.attachments import service as att

    out = []
    for d in rows(s, p, published_only=True):
        a = _attachment(s, d.attachment_id)
        if a is None or not att.is_available(a):
            continue
        out.append({"id": d.id, "kind": "PROJECT_DOCUMENT", "document_class": d.document_class,
                    "label": V.CUSTOMER_DOCUMENT_CLASSES[d.document_class], "title": d.title,
                    "published_on": clock.to_rfc3339(d.published_on), "width": a.width, "height": a.height})  # fmt: skip
    return out


def content_for(s: Session, property_id: str, document_id: str):
    """The attachment behind a publication reached through an authorised property (the caller resolved it), or 404:
    another customer's document, a withdrawn one, an unavailable file and an unknown id all look the same."""
    from veda.modules.attachments import service as att

    d = s.get(ProjectCustomerDocument, document_id)
    if d is None or d.is_deleted or d.status != "PUBLISHED":
        raise not_found()
    p = s.get(Project, d.project_id)
    if p is None or p.property_id != property_id:
        raise not_found()
    a = _attachment(s, d.attachment_id)
    if (a is None or a.lead_id != p.lead_id or not att.is_available(a) or a.visibility_code != "STANDARD"
            or a.category_code not in V.CUSTOMER_DOCUMENT_CATEGORIES):  # fmt: skip
        raise not_found()
    return d, a
