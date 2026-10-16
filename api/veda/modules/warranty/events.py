"""The service timeline and notifications (WSV-030, WSV-040).

``record`` appends a ``service_event``: codes, ids, states, dates and digests only (``_check`` refuses free text), so an
event never needs erasing and the database refuses UPDATE and DELETE on it.

Notifications are one outbox row each, written in the transaction of the change itself, so a retried request that
changes nothing writes nothing; each event type has its own handler, which re-reads the request and sends nothing if it
has moved on or the customer's access ended.

- Customer email (template ``service_update``: "there is an update in your portal"; never a description, note,
  explanation, staff name or amount), only while warranty, portal and lifecycle flags are on, to the account that
  submitted the request (portal) or the enquiry's primary customers (recorded by staff): request received, information
  requested, coverage decided, visit planned, resolved (please confirm), closed.
- Staff in-app, to holders of ``warranty.service.view`` and the request's owner: a new customer request, information
  added by the customer, a resolution the customer rejected. Internal transitions notify no customer.

The post-handover subscriber registers the project's warranty entitlement when the project is handed over.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from veda.kernel import outbox
from veda.modules.project import hooks
from veda.platform.notifications.handlers import app_link, handler, notify_in_app, send
from veda.platform.notifications.models import OutboxEvent

from . import access
from .models import ServiceEvent, ServiceRequest

_SAFE = re.compile(r"^[A-Za-z0-9_.:>+-]{0,80}$")

RECEIVED = "warranty.service_received"
INFORMATION_REQUESTED = "warranty.service_information_requested"
COVERAGE_DECIDED = "warranty.service_coverage_decided"
VISIT_PLANNED = "warranty.service_visit_planned"
RESOLVED = "warranty.service_resolved"
CLOSED = "warranty.service_closed"
CUSTOMER_EVENTS = (RECEIVED, INFORMATION_REQUESTED, COVERAGE_DECIDED, VISIT_PLANNED, RESOLVED, CLOSED)
SUBMITTED = "warranty.service_submitted"  # staff
INFORMATION_ADDED = "warranty.service_information_added"  # staff
REJECTED = "warranty.service_resolution_rejected"  # staff
STAFF_EVENTS = (SUBMITTED, INFORMATION_ADDED, REJECTED)

WORDS: dict[str, tuple[str, str, str]] = {  # subject, headline, message
    RECEIVED: ("We have received your service request", "Thank you for telling us",
               "We have received the problem you reported. Our team will review it, and you can follow it in your "
               "project portal."),
    INFORMATION_REQUESTED: ("Veda Spaces needs a little more information", "We need a little more information",
                            "To look into your service request we need a little more information from you. Please "
                            "open your project portal to see what we asked."),
    COVERAGE_DECIDED: ("An update on your service request", "An update on your service request",
                       "We have reviewed your service request. Please open your project portal to see what happens "
                       "next."),
    VISIT_PLANNED: ("A visit has been planned for your service request", "A visit has been planned",
                    "We have planned a visit for your service request. Please open your project portal for the date."),
    RESOLVED: ("Please confirm your service request is resolved", "Is everything right now?",
               "We have recorded your service request as resolved. Please check and confirm in your project portal, "
               "or tell us if it is still not right."),
    CLOSED: ("Your service request is closed", "Your service request is closed",
             "Your service request has been closed. You can see its history in your project portal."),
}  # fmt: skip


def _check(detail: dict[str, Any]) -> dict[str, Any]:
    for k, v in detail.items():
        if v is None or isinstance(v, bool | int):
            continue
        if not isinstance(v, str) or not _SAFE.match(v):
            raise ValueError(f"service_event detail {k} must be a code, id, date or digest")
    return detail


def record(s: Session, r: ServiceRequest, code: str, *, frm: str | None = None, to: str | None = None,
           account_id: str | None = None, **detail: Any) -> ServiceEvent:  # fmt: skip
    e = ServiceEvent(request_id=r.id, lead_id=r.lead_id, event_code=code, from_state=frm, to_state=to,
                     account_id=account_id, detail=_check({k: v for k, v in detail.items() if v is not None}))  # fmt: skip
    s.add(e)
    s.flush()
    return e


def customer(s: Session, r: ServiceRequest, event_type: str, **ids: Any) -> None:
    if access.customer_enabled():  # nothing is queued for a portal the customer cannot see
        outbox.enqueue(s, event_type, "service_request", r.id, service_request_id=r.id, **ids)


def staff(s: Session, r: ServiceRequest, event_type: str, **ids: Any) -> None:
    outbox.enqueue(s, event_type, "service_request", r.id, service_request_id=r.id, **ids)


def _request(s: Session, event: OutboxEvent) -> ServiceRequest | None:
    from veda.modules.crm.leads.models import Lead

    r = s.get(ServiceRequest, event.payload.get("service_request_id"))
    if r is None or r.is_deleted:
        return None
    lead = s.get(Lead, r.lead_id)
    return None if lead is None or lead.anonymized_on is not None else r


def _recipients(s: Session, r: ServiceRequest) -> list[tuple[str, str]]:
    from veda.modules.project.notices import _account, _primary

    return _account(s, r.account_id, r.lead_id) if r.account_id else _primary(s, r.lead_id)


def _customer_handler(event_type: str, *states: str):
    @handler(event_type)
    def _send(s: Session, event: OutboxEvent) -> None:
        r = _request(s, event)
        if r is None or not access.customer_enabled():
            return
        if states and r.status not in states:
            return  # moved on before the worker ran: the newer update is what the customer will hear about
        subject, headline, message = WORDS[event_type]
        link = app_link(f"/portal/properties/{r.property_id}#service")
        for email, name in _recipients(s, r):
            send("service_update", [email], event, name=name, subject=subject, headline=headline, message=message,
                 link=link)  # fmt: skip

    return _send


_customer_handler(RECEIVED)
_customer_handler(INFORMATION_REQUESTED, "INFORMATION_REQUESTED")
_customer_handler(COVERAGE_DECIDED)
_customer_handler(VISIT_PLANNED, "IN_PROGRESS")
_customer_handler(RESOLVED, "RESOLVED")
_customer_handler(CLOSED, "CLOSED")


def _staff_recipients(s: Session, r: ServiceRequest) -> list[str]:
    from veda.platform.rbac.resolver import holders_of, load_grants

    out = []
    for uid in holders_of(s, "warranty.service.view"):
        scope = load_grants(s, uid).granted.get("warranty.service.view")
        if scope == "ALL" or uid == r.owner_user_id:
            out.append(uid)
        elif scope == "OWN":
            from veda.modules.project.access import is_member

            if is_member(s, r.project_id, uid):
                out.append(uid)
    if r.owner_user_id and r.owner_user_id not in out:
        from veda.platform.identity.models import User

        owner = s.get(User, r.owner_user_id)
        if (
            owner is not None
            and owner.status == "ACTIVE"
            and load_grants(s, owner.id).granted.get("warranty.service.view")
        ):
            out.append(r.owner_user_id)
    return out


def _staff_handler(event_type: str, kind: str, words: str):
    @handler(event_type)
    def _notify(s: Session, event: OutboxEvent) -> None:
        r = _request(s, event)
        if r is None:
            return
        notify_in_app(s, event, _staff_recipients(s, r), notification_type=kind,
                      title=f"{r.request_number}: {words}", entity=("service_request", r.id),
                      link_path=f"/service/{r.id}")  # fmt: skip

    return _notify


_staff_handler(SUBMITTED, "SERVICE_REQUEST_SUBMITTED", "a customer reported a problem")
_staff_handler(INFORMATION_ADDED, "SERVICE_INFORMATION_ADDED", "the customer added information")
_staff_handler(REJECTED, "SERVICE_RESOLUTION_REJECTED", "the customer says it is still not right")


# --- post-handover registration ----------------------------------------------------------------------------------------
@hooks.after_handover
def _register_after_handover(s: Session, p, payload: dict[str, Any]) -> None:
    if not access.staff_enabled():
        return  # registered later by the staff command, from the same handover record
    from veda.modules.project import access as paccess

    from . import entitlement

    paccess.lock(s, p)
    entitlement.register(s, p, "HANDOVER_EVENT")
