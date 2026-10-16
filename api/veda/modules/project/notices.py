"""Project-delivery notifications (PEX-050): few, customer-safe and never duplicated.

Customers get an email for exactly two events, and only while the portal, the Project Lifecycle and the delivery flag
are on: their report was received, and their handover summary is ready to review. The email says only that there is an
update in their portal (template ``project_update``): no title, description, note, name of staff, finding or amount.
Staff get in-app notifications, by project team, for a new customer report and for a customer's acknowledgement.

Each notification is one outbox row written in the transaction of the change itself, so a retried request that changes
nothing writes nothing, and the worker delivers each row once. A handler re-reads its record and sends nothing if the
record no longer says what it said (a superseded package, an erased enquiry, a flag turned off).
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import outbox
from veda.platform.notifications.handlers import app_link, handler, notify_in_app, send
from veda.platform.notifications.models import OutboxEvent

from . import events
from .models import Project, ProjectCustomerReport, ProjectHandoverPackage

REPORT_RECEIVED = "project.customer_report_received"  # customer
HANDOVER_PACKAGE_READY = "project.handover_package_ready"  # customer
REPORT_SUBMITTED = "project.customer_report_submitted"  # staff
HANDOVER_ACKNOWLEDGED = "project.handover_acknowledged"  # staff
EVENT_TYPES = (REPORT_RECEIVED, HANDOVER_PACKAGE_READY, REPORT_SUBMITTED, HANDOVER_ACKNOWLEDGED)


def delivery_enabled() -> bool:
    cfg = settings()
    return bool(cfg.project_delivery_portal_enabled and cfg.customer_portal_enabled and cfg.project_lifecycle_enabled)


def customer(s: Session, p: Project, event_type: str, **ids: Any) -> None:
    if delivery_enabled():  # nothing is queued for a portal the customer cannot see
        outbox.enqueue(s, event_type, "project", p.id, project_id=p.id, **ids)


def staff(s: Session, p: Project, event_type: str, **ids: Any) -> None:
    outbox.enqueue(s, event_type, "project", p.id, project_id=p.id, **ids)


def _primary(s: Session, lead_id: str) -> list[tuple[str, str]]:
    from veda.modules.commercials.events import _recipients  # the enquiry's primary customers with ACTIVE access

    return _recipients(s, lead_id)


def _account(s: Session, account_id: str, lead_id: str) -> list[tuple[str, str]]:
    from veda.modules.portal.models import PortalAccess, PortalAccount

    row = s.execute(
        sa.select(PortalAccount.email_normalized, PortalAccount.display_name)
        .join(PortalAccess, PortalAccess.account_id == PortalAccount.id)
        .where(
            PortalAccount.id == account_id,
            PortalAccess.lead_id == lead_id,
            PortalAccess.status == "ACTIVE",
            PortalAccess.is_deleted == sa.false(),
            PortalAccount.status == "ACTIVE",
            PortalAccount.erased_on.is_(None),
        )  # fmt: skip
    ).first()
    return [(row[0], row[1])] if row else []


def _send(s: Session, event: OutboxEvent, p: Project, recipients: list[tuple[str, str]], kind: str) -> None:
    if not delivery_enabled():
        return
    link = app_link(f"/portal/properties/{p.property_id}#delivery")
    for email, name in recipients:
        send("project_update", [email], event, name=name, kind=kind, link=link)


@handler(REPORT_RECEIVED)
def _report_received(s: Session, event: OutboxEvent) -> None:
    p = events._project(s, event)
    r = s.get(ProjectCustomerReport, event.payload.get("report_id"))
    if p is None or r is None or r.is_deleted:
        return
    who = _account(s, r.account_id, p.lead_id) if r.account_id else _primary(s, p.lead_id)
    _send(s, event, p, who, "report_received")


@handler(HANDOVER_PACKAGE_READY)
def _package_ready(s: Session, event: OutboxEvent) -> None:
    p = events._project(s, event)
    pkg = s.get(ProjectHandoverPackage, event.payload.get("package_id"))
    if p is None or pkg is None or pkg.status != "PREPARED":
        return  # superseded or completed before the worker ran: send nothing
    _send(s, event, p, _primary(s, p.lead_id), "handover_ready")


@handler(REPORT_SUBMITTED)
def _report_submitted(s: Session, event: OutboxEvent) -> None:
    p = events._project(s, event)
    if p is not None:
        notify_in_app(s, event, events._owners(s, p, "PROJECT", "QUALITY"), notification_type="PROJECT_CUSTOMER_REPORT",
                      title=f"{p.project_number}: the customer reported an issue", entity=("project", p.id),
                      link_path=f"/projects/{p.id}")  # fmt: skip


@handler(HANDOVER_ACKNOWLEDGED)
def _acknowledged(s: Session, event: OutboxEvent) -> None:
    p = events._project(s, event)
    if p is not None:
        notify_in_app(s, event, events._owners(s, p, "HANDOVER", "PROJECT"),
                      notification_type="PROJECT_HANDOVER_ACKNOWLEDGED",
                      title=f"{p.project_number}: the customer acknowledged the handover summary",
                      entity=("project", p.id), link_path=f"/projects/{p.id}")  # fmt: skip
