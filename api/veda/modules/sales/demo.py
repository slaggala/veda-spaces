"""The customer-journey demo (SCA-009): a synthetic, read-only model of what a customer sees after choosing Veda Spaces.

Built from constants on every request: no database row is read or written, no customer exists behind it, and every
name, reference, contact and figure is marked DEMO or synthetic. The staff page renders it with the real portal and
proposal views, so what a prospect is shown is the real experience, with invented content. Because it has no rows it
can appear in no report, and because the route needs ``sales.demo.view`` behind the feature flag it is never public.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

LABEL = "DEMO: synthetic example, not a customer"
BRAND = {"name": "Veda Spaces", "tagline": "Interiors, measured and made"}
CONTACT = {"display_name": "DEMO designer", "role": "Your design consultant (demo)", "phone": "+00 0000 000000",
           "email": "demo@example.com", "hours": "Mon-Sat, 10:00-18:00", "channel_note": "Synthetic contact for demonstrations"}  # fmt: skip
PORTAL_CONTACT = {"source": "CONSULTANT", "name": "DEMO designer", "role": "Your design consultant (demo)",
                  "phone": "+00 0000 000000", "email": "demo@example.com", "hours": "Mon-Sat, 10:00-18:00"}  # fmt: skip
NEXT_STEPS = [
    ("PROPOSAL_ACCEPTED", "Proposal accepted", "You accept the quotation and Veda Spaces confirms receipt."),
    ("VEDA_CONFIRMATION", "Veda Spaces confirmation", "Your project is booked and your project team is named."),
    (
        "SCOPE_DESIGN_FINALISATION",
        "Design and scope finalised",
        "Drawings, finishes and the frozen scope are confirmed with you.",
    ),
    ("PRODUCTION_READINESS", "Production readiness", "Materials and hardware are ordered against the frozen scope."),
    ("SITE_READINESS", "Site readiness", "The site is checked for the work that depends on it before installation."),
    ("INSTALLATION", "Installation", "Work is installed in the planned sequence; progress is shared with you."),
    ("JOINT_INSPECTION", "Joint inspection", "Quality checks and snags are reviewed together before handover."),
    ("HANDOVER", "Handover", "The handover package is prepared, reviewed with you and acknowledged."),
]


def _d(today: date, days: int) -> str:
    return (today + timedelta(days=days)).isoformat()


def _steps(today: date) -> list[dict]:
    return [
        {"key": "consultation", "label": "Consultation", "state": "COMPLETED", "detail": "DEMO: first conversation held", "date": _d(today, -40)},
        {"key": "site_measurement", "label": "Site measurement", "state": "COMPLETED", "detail": "DEMO: visit completed", "date": _d(today, -33)},
        {"key": "design_scope", "label": "Design and scope", "state": "COMPLETED", "detail": "DEMO: scope confirmed", "date": _d(today, -26)},
        {"key": "quotation", "label": "Your quotation", "state": "COMPLETED", "detail": "DEMO: quotation issued", "date": _d(today, -21)},
        {"key": "approval", "label": "Your approval", "state": "COMPLETED", "detail": "DEMO: accepted", "date": _d(today, -14)},
        {"key": "execution", "label": "Execution", "state": "IN_PROGRESS", "detail": "DEMO: installation under way", "date": None},
        {"key": "quality", "label": "Quality checks", "state": "UPCOMING", "detail": "After installation", "date": None},
        {"key": "handover", "label": "Handover", "state": "UPCOMING", "detail": "After the joint inspection", "date": None},
    ]  # fmt: skip


def portal_view(today: date) -> dict:
    """Shaped like the portal's property view (``app/src/modules/portal/api.ts`` PropertyView)."""
    quotation = {"id": "demo-quotation", "reference": "DEMO-Q-0001", "title": "DEMO: 3 BHK apartment interiors", "kind": "QUOTATION",
                 "version_no": 1, "state": "ACCEPTED", "status": "COMPLETED", "status_label": "Accepted", "issued_on": _d(today, -21),
                 "valid_until": _d(today, 9), "days_left": None, "total": "DEMO amount", "currency": "INR"}  # fmt: skip
    project = {
        "id": "demo-project", "status": "ACTIVE", "phase": {"code": "INSTALLATION", "label": "Installation"},
        "work": {"items": [
            {"label": "Kitchen cabinetry", "state": "COMPLETED", "detail": "Installed", "completed_on": _d(today, -3)},
            {"label": "Master bedroom wardrobe", "state": "IN_PROGRESS", "detail": "Being installed", "completed_on": None},
            {"label": "Living room TV unit", "state": "UPCOMING", "detail": "Planned next", "completed_on": None},
        ], "counts": {"COMPLETED": 1, "IN_PROGRESS": 1, "UPCOMING": 1}},
        "paused": [],
        "next_date": None,
        "quality": {"checks_passed": 2, "being_corrected": 0},
        "snags": [{"number": 1, "title": "DEMO: drawer alignment", "status": "IN_PROGRESS", "state": "IN_PROGRESS"}],
        "reports": [], "can_report": False,
        "handover": {"state": "UPCOMING", "label": "After the joint inspection", "date": None, "remaining": [{"label": "Work packages", "count": 2}]},
        "documents": [], "package": None,
    }  # fmt: skip
    return {
        "demo": True, "label": LABEL,
        "id": "demo-property",
        "property": {"reference": "DEMO-P-0001", "configuration": "3 BHK apartment", "locality": "Demo locality", "city": "Hyderabad"},
        "enquiry": {"reference": "DEMO-REF1"},
        "headline": "DEMO: your home interiors project",
        "next_step": {"key": "execution", "label": "Execution", "state": "IN_PROGRESS", "detail": "DEMO: installation under way", "date": None},
        "attention_count": 0, "quotation": quotation, "contact": PORTAL_CONTACT, "project_tracking": True,
        "payments": {"available": True, "outstanding": "DEMO amount", "next_payment": None},
        "journey": _steps(today), "attention": [], "quotations": [quotation],
        "documents": [{"kind": "QUOTATION", **quotation}],
        "commercials": {"available": True, "summary": {"currency": "INR", "total_value": "DEMO total", "includes_gst": "GST shown on the quotation",
                        "paid": "DEMO paid", "outstanding": "DEMO outstanding", "credit": None, "next_payment": None, "as_of": _d(today, 0)},
                        "schedule": [
                            {"label": "On acceptance", "when": "Paid", "amount": "DEMO amount", "gst_included": None, "paid": "DEMO amount", "remaining": None, "state": "PAID", "state_label": "Paid", "requested": False, "due_on": _d(today, -14)},
                            {"label": "Before installation", "when": "Paid", "amount": "DEMO amount", "gst_included": None, "paid": "DEMO amount", "remaining": None, "state": "PAID", "state_label": "Paid", "requested": False, "due_on": _d(today, -5)},
                            {"label": "At handover", "when": "Upcoming", "amount": "DEMO amount", "gst_included": None, "paid": "0", "remaining": "DEMO amount", "state": "UPCOMING", "state_label": "Upcoming", "requested": False, "due_on": None},
                        ], "payments": [], "invoices": [], "receipts": [], "notices": [], "how_to_pay": "DEMO: how to pay is confirmed by Veda Spaces."},
        "included": [{"title": "Kitchen", "kind": "ROOM", "included_count": 2, "optional_count": 0, "items": [
            {"description": "DEMO: base and wall units", "detail": None, "status": "INCLUDED"},
            {"description": "DEMO: tall unit", "detail": None, "status": "INCLUDED"}]}],
        "commitments": {"source": "DEMO", "inclusions": [{"code": "D1", "text": "DEMO: the scope listed in your quotation"}],
                        "warranty": ["DEMO: warranty and service as set out in your accepted quotation"], "manufacturer_warranty_note": None,
                        "handover": [{"code": "D2", "text": "DEMO: a walkthrough of every room with you"}],
                        "care": [{"code": "D3", "text": "DEMO: care guidance for finishes and hardware"}],
                        "next_steps": [{"code": c, "stage": c, "label": label, "text": text, "duration": None} for c, label, text in NEXT_STEPS],
                        "payment_schedule": [{"label": "On acceptance", "share": "Share A", "trigger": "Acceptance", "amount": None},
                                             {"label": "Before installation", "share": "Share B", "trigger": "Production readiness", "amount": None},
                                             {"label": "At handover", "share": "Share C", "trigger": "Handover", "amount": None}],
                        "payment_safety": "DEMO: pay only to the account named on your quotation."},
        "responsibilities": {"client": [{"code": "D4", "text": "DEMO: items you supply, as listed in your quotation"}],
                             "site_readiness": [{"code": "D5", "text": "DEMO: the site is ready for installation on the agreed date"}]},
        "support": {"contacts": [{k: v for k, v in PORTAL_CONTACT.items() if k != "source"}], "escalation": "DEMO: escalation route named on your quotation"},
        "delivery": {"available": True, "projects": [project]},
        "warranty": {"available": True, "categories": [], "max_photos": 0,
                     "projects": [{"id": "demo-project", "handed_over": False, "can_report": False,
                                   "warranty": {"state": "BEFORE_HANDOVER", "message": "DEMO: your warranty is registered at handover."}, "requests": []}]},
    }  # fmt: skip


def information() -> dict:
    return {
        "content_version": "DEMO",
        "contacts": {"quotation": CONTACT, "support": [CONTACT], "service": [CONTACT]},
        "support_escalation": "DEMO: escalation route named on your quotation",
        "project_inclusions": [{"code": "D1", "text": "DEMO: the scope listed in your quotation"}],
        "client_responsibilities": [{"code": "D4", "text": "DEMO: items you supply, as listed in your quotation"}],
        "site_readiness": [{"code": "D5", "text": "DEMO: the site is ready for installation on the agreed date"}],
        "site_dependent_work": None,
        "manufacturer_warranty_note": None,
        "warranty_exclusions": [{"code": "D6", "text": "DEMO: damage from misuse"}],
        "service_guidance": {"contact": CONTACT, "what_to_provide": ["DEMO: your reference and a photo"], "reference_process": None, "escalation": None},
        "handover": [{"code": "D2", "text": "DEMO: a walkthrough of every room with you"}],
        "care": [{"code": "D3", "text": "DEMO: care guidance for finishes and hardware"}],
        "next_steps": [{"code": c, "stage": c, "label": label, "text": text, "duration": None} for c, label, text in NEXT_STEPS],
        "payment_safety": "DEMO: pay only to the account named on your quotation.",
    }  # fmt: skip


def proposal_page(today: date) -> dict:
    """Shaped like the customer proposal page model (``app/src/modules/proposal/api.ts`` Page), preview mode."""
    rooms: list[dict[str, Any]] = [
        {"ref": "R1", "title": "Kitchen", "kind": "ROOM", "subtotal": "DEMO subtotal", "included_count": 2, "optional_count": 0, "lines": [
            {"ref": "L1", "description": "DEMO: base and wall units", "detail": "Laminate finish (demo)", "quantity": "DEMO qty", "amount": "DEMO amount", "priced": True, "status": "INCLUDED"},
            {"ref": "L2", "description": "DEMO: tall unit", "detail": None, "quantity": "DEMO qty", "amount": "DEMO amount", "priced": True, "status": "INCLUDED"}]},
        {"ref": "R2", "title": "Master bedroom", "kind": "ROOM", "subtotal": "DEMO subtotal", "included_count": 1, "optional_count": 1, "lines": [
            {"ref": "L3", "description": "DEMO: wardrobe", "detail": "Hinged (demo)", "quantity": "DEMO qty", "amount": "DEMO amount", "priced": True, "status": "INCLUDED"},
            {"ref": "L4", "description": "DEMO: loft storage", "detail": None, "quantity": "DEMO qty", "amount": "DEMO amount", "priced": True, "status": "OPTIONAL"}]},
    ]  # fmt: skip
    loft = rooms[1]["lines"][1]
    return {
        "demo": True, "label": LABEL,
        "state": "OPEN", "link": {"expires_on": "", "status": "PREVIEW"}, "history": [],
        "capabilities": {"interaction": False, "acceptance": False}, "notices": [], "actions": [],
        "proposal": {
            "schema": "veda.customer-proposal/1", "kind": "QUOTATION", "title": "DEMO: your quotation", "brand": BRAND,
            "reference": "DEMO-Q-0001", "quotation_number": "DEMO-Q-0001", "version_no": 1, "variation_no": 0,
            "issued_on": _d(today, -21), "valid_until": _d(today, 9), "subject": "DEMO: 3 BHK apartment interiors",
            "cover_note": "DEMO: a synthetic quotation used to show the customer experience.",
            "property": {"reference": "DEMO-P-0001", "configuration": "3 BHK apartment", "city": "Hyderabad"},
            "snapshot_sha256": None, "rooms": rooms, "optional_items": [loft],
            "summary": {"base_total": "DEMO total", "total": "DEMO total", "currency": "INR"},
            "payment_schedule": [{"label": "On acceptance", "share": "Share A", "trigger": "Acceptance", "amount": None},
                                 {"label": "Before installation", "share": "Share B", "trigger": "Production readiness", "amount": None},
                                 {"label": "At handover", "share": "Share C", "trigger": "Handover", "amount": None}],
            "warranty": ["DEMO: warranty and service as set out in the policy"], "service_support": ["DEMO: service support after handover"],
            "assumptions": ["DEMO: sizes as measured on site"], "exclusions": ["DEMO: civil work"], "terms": ["DEMO: terms as issued"],
            "terms_version": "DEMO", "unit_rates_shown": False, "sections": {}, "information": information(),
        },
    }  # fmt: skip


def model(today: date) -> dict:
    return {"demo": True, "label": LABEL, "as_of": today.isoformat(), "portal": portal_view(today),
            "proposal": proposal_page(today), "journey": _steps(today)}  # fmt: skip
