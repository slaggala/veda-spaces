"""Customer-safe classification of every project-lifecycle field (PLB-42). Preparation only.

A future customer project portal must not need to expose raw internal rows. Every column of every project table is
classified here (a unit test refuses an unclassified or stale entry):

- ``INTERNAL_ONLY``: never shown to a customer (staff notes, descriptions, internal titles, reasons, people, digests,
  evidence, gate evaluations, commercial amounts).
- ``POTENTIALLY_CUSTOMER_SAFE``: may be shown to the customer of this project once a portal and its copy are approved
  (references, stage codes mapped to Customer Promise stages, customer-worded labels, statuses, dates already shared).
- ``CUSTOMER_ACTION``: the customer-worded description of something the customer must do (only where the responsible
  party is CUSTOMER).

PEX: the portal's delivery view (``delivery.py``) reads only SAFE and CUSTOMER_ACTION fields, and only while
VEDA_PROJECT_DELIVERY_PORTAL_ENABLED (with the portal and lifecycle flags) is on; it asserts the class of each field it
reads. A customer report's description and area are the customer's own words, shown back only to that customer's
portal; the handover package's content is built from customer-safe fields only.
"""

from __future__ import annotations

from typing import Any

INTERNAL = "INTERNAL_ONLY"
SAFE = "POTENTIALLY_CUSTOMER_SAFE"
CUSTOMER_ACTION = "CUSTOMER_ACTION"
CLASSES = (INTERNAL, SAFE, CUSTOMER_ACTION)

_CONTRACT = ("id", "created_on", "updated_on", "created_by", "updated_by", "is_deleted", "deleted_on", "deleted_by",
             "version", "project_id", "lead_id")  # fmt: skip

# Only the non-INTERNAL fields are listed per table; every other column of the table is INTERNAL_ONLY. ``COLUMNS``
# names every column (generated from the models by the unit test's comparison), so a new column must be classified.
_SAFE: dict[str, dict[str, str]] = {
    "project": {"project_number": SAFE, "status": SAFE, "stage_code": SAFE, "handed_over_on": SAFE},
    "project_baseline": {},
    "project_stage": {"stage_code": SAFE, "sequence_no": SAFE, "status": SAFE, "entered_on": SAFE,
                      "completed_on": SAFE},
    "project_member": {},
    "project_transition": {"handover_on": SAFE},
    "project_checklist_item": {},
    "project_milestone": {"milestone_code": SAFE, "customer_label": SAFE, "customer_promised_date": SAFE,
                          "actual_date": SAFE, "status": SAFE},
    "project_site_readiness": {"kind": SAFE, "item_code": SAFE, "category": SAFE, "promise_content_version": SAFE,
                               "status": SAFE, "responsible_party": SAFE, "due_date": SAFE,
                               "customer_action": CUSTOMER_ACTION},
    "project_blocker": {"responsible_party": SAFE, "customer_action": CUSTOMER_ACTION, "target_date": SAFE,
                        "customer_summary": SAFE, "impact": SAFE, "status": SAFE},
    "project_qc_check": {"result": SAFE},
    "project_snag": {"snag_no": SAFE, "category": SAFE, "customer_title": SAFE, "status": SAFE, "space_id": SAFE,
                     "customer_visible": SAFE, "source": SAFE, "closure_code": SAFE},
    "project_event": {},
    "project_work_package": {"stage_code": SAFE, "customer_label": SAFE, "customer_visible": SAFE, "status": SAFE,
                             "actual_start": SAFE, "actual_finish": SAFE},
    "project_qc_point": {},
    "project_customer_report": {"report_no": SAFE, "description": SAFE, "area": SAFE, "status": SAFE,
                                "decline_code": SAFE, "response": SAFE, "triaged_on": SAFE},
    "project_handover_package": {"package_no": SAFE, "status": SAFE, "content": SAFE, "content_sha256": SAFE,
                                 "acknowledged_on": SAFE, "completed_on": SAFE},
    "project_customer_document": {"document_class": SAFE, "title": SAFE, "published_on": SAFE},
}  # fmt: skip


def column_class(table: str, column: str) -> str:
    return _SAFE.get(table, {}).get(column, INTERNAL)


def classify(table: str, columns: list[str]) -> dict[str, str]:
    return {c: (INTERNAL if c in _CONTRACT else column_class(table, c)) for c in columns}


def tables() -> tuple[str, ...]:
    return tuple(_SAFE)


def listed() -> dict[str, dict[str, str]]:
    return {t: dict(v) for t, v in _SAFE.items()}


def public_view() -> dict[str, Any]:
    """The non-internal fields, for the workspace's badges ("may be shown to the customer later")."""
    return {
        "classes": list(CLASSES),
        "default": INTERNAL,
        "fields": listed(),
        "published_through": "VEDA_PROJECT_DELIVERY_PORTAL_ENABLED",
    }
