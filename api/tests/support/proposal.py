"""CQX test harness: SYNTHETIC sites through an issued quotation (SYNTHETIC commercial policy), shared with a SYNTHETIC
customer by a secure link, and a customer client that sends only the link's header (never a staff session).

Nothing here is a real customer, rate, decision or policy. Results are SYNTHETIC_VALIDATED only.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from tests.support.commercial import Commercial, approved_estimate, install_full_policy, load_card, ok, step

FLAGS = dict(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True)
PROPOSAL_ON = pytest.mark.settings(**FLAGS, customer_proposal_enabled=True)
INTERACTION_ON = pytest.mark.settings(**FLAGS, customer_proposal_enabled=True,
                                      customer_proposal_interaction_enabled=True)  # fmt: skip
ACCEPTANCE_ON = pytest.mark.settings(**FLAGS, customer_proposal_enabled=True,
                                     customer_proposal_interaction_enabled=True,
                                     customer_quotation_acceptance_enabled=True)  # fmt: skip
HEADER = "X-Veda-Proposal"

# SYNTHETIC customer-proposal decisions, for exercising the decided paths. Refused outside the test environment.
SYNTHETIC_PROPOSAL_POLICY: dict[str, Any] = {
    "schema": "veda.customer-proposal-policy/1",
    "version": "SYNTHETIC-CQX-1",
    "status": "SYNTHETIC_TEST_ONLY",
    "note": "SYNTHETIC test policy. Not an owner decision.",
    "decisions": {
        "CQX-D01": {"method": "LINK_POSSESSION"},
        "CQX-D02": {"live_total": True},
        "CQX-D03": {"required_sections": ["SCOPE", "PAYMENT_MILESTONES", "WARRANTY", "TERMS"]},
        "CQX-D04": {"record_ip": False, "record_user_agent": False, "retention_days": 365},
    },
}


def install_proposal_policy(**decisions) -> dict:
    """SYNTHETIC_PROPOSAL_POLICY with ``decisions`` replaced (codes with '-' as '_': CQX_D01=None)."""
    from veda.modules.customer_proposal import policy

    doc = copy.deepcopy(SYNTHETIC_PROPOSAL_POLICY)
    for k, v in decisions.items():
        doc["decisions"][k.replace("_", "-")] = v
    policy.install_for_tests(doc)
    return doc


def digital_acceptance_policy(**decisions) -> None:
    """The SYNTHETIC commercial policy with CUSTOMER_DIGITAL among the acceptance methods, plus the CQX policy."""
    install_full_policy(OI_MTQ_11={"methods": ["STAFF_RECORDED", "SIGNED_COPY", "CUSTOMER_DIGITAL"]})
    install_proposal_policy(**decisions)


def issued(c: Commercial, key: str = "2BHK", *, optional: str = "ACCEPTED") -> tuple[dict, dict, dict]:
    """A synthetic site of ``key`` through an issued quotation version 1: (property, estimate, quotation)."""
    prop, est = approved_estimate(c, key, optional=optional)
    q = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    q = ok(step(c, q, "issue", c.manager))
    return prop, est, q


# SYNTHETIC preparation drivers so 5 BHK and independent-house quotations can be issued in tests (as the MTQ end-to-end
# suite does); the real OI-MTQ-15 decision is the owner's and stays null.
SYNTHETIC_PREP = {"home_size_by_bedrooms": {"5": "4BHK"}, "independent_house_factor_bp": 13_000}


def setup(api, factory, key: str = "2BHK", *, policy: bool = True, optional: str = "ACCEPTED", **decisions):
    if policy:
        install_full_policy(**{"OI_MTQ_15": SYNTHETIC_PREP, **decisions})
    load_card()
    c = Commercial(api, factory)
    prop, est, q = issued(c, key, optional=optional)
    return c, prop, est, q


def share(c: Commercial, q: dict, user=None, *, kind: str = "PRIMARY_CUSTOMER", days: int = 14, code: int = 201):
    r = c.as_(user or c.sales).post(f"/api/v1/quotations/{q['id']}/access-grants",
                                    {"recipient_kind": kind, "expires_in_days": days})  # fmt: skip
    assert r.status == code, r
    return r.data if code == 201 else r


class Customer:
    """The customer's browser: only the link's token, in its header; never a bearer token."""

    def __init__(self, api, token: str):
        self.api, self.token = api, token

    def _h(self, extra: dict | None = None) -> dict:
        return {HEADER: self.token, **(extra or {})}

    def get(self, path: str = "", **kw):
        return self.api.get(
            f"/api/v1/public/proposal{path}", anonymous=True, headers=self._h(kw.pop("headers", None)), **kw
        )

    def post(self, path: str, body: dict | None = None, *, key: str | None = None, **kw):
        extra = {"Idempotency-Key": key} if key else None
        return self.api.post(f"/api/v1/public/proposal{path}", body or {}, anonymous=True, headers=self._h(extra), **kw)


def customer(api, grant: dict) -> Customer:
    return Customer(api, grant["token"])


__all__ = ["ACCEPTANCE_ON", "Commercial", "Customer", "INTERACTION_ON", "PROPOSAL_ON", "customer", "issued", "ok",
           "setup", "share", "step"]  # fmt: skip


# SYNTHETIC customer information pack (OI-MTQ-18) for exercising the decided paths. Every value is invented for tests:
# not a Veda Spaces contact, rule, responsibility, warranty or promise. The real decision stays null.
SYNTHETIC_PACK: dict[str, Any] = {
    "content_version": "SYN-C1",
    "contacts": [
        {
            "code": "SYN_QUOTE_DESK",
            "kind": "QUOTATION",
            "display_name": "SYNTHETIC Quotation Desk",
            "role": "Quotation consultant (synthetic)",
            "phone": "+00 0000 000000",
            "email": "quotes@synthetic.example",
            "hours": "SYNTHETIC hours",
            "business_channel_approved": True,
        },
        {
            "code": "SYN_SUPPORT",
            "kind": "SUPPORT",
            "display_name": "SYNTHETIC Support",
            "role": "Customer care (synthetic)",
            "email": "support@synthetic.example",
            "business_channel_approved": True,
        },
        {
            "code": "SYN_SERVICE",
            "kind": "SERVICE",
            "display_name": "SYNTHETIC Service",
            "role": "Service team (synthetic)",
            "phone": "+00 0000 000001",
            "business_channel_approved": True,
        },
    ],
    "support_escalation": "SYNTHETIC escalation route.",
    "project_inclusions": [{"code": "SYN_INSTALL", "text": "SYNTHETIC installation of the listed items."}],
    "client_responsibilities": [
        {
            "code": "SYN_APPLIANCE",
            "category": "APPLIANCE_MODEL",
            "text": "SYNTHETIC: share your appliance models.",
            "default_status": "REQUIRED",
        },
        {"code": "SYN_LIFT", "category": "SERVICE_LIFT_ACCESS", "text": "SYNTHETIC: service lift access."},
    ],
    "site_readiness": [
        {"code": "SYN_FLOOR", "category": "FLOORING", "text": "SYNTHETIC: flooring complete."},
        {"code": "SYN_POWER", "category": "ELECTRICAL_SUPPLY", "text": "SYNTHETIC: power available."},
    ],
    "site_dependent_work": {
        "intro": "SYNTHETIC: some needs become clear only on site.",
        "approval_rule": "SYNTHETIC: such work is agreed with you as a change order before it starts.",
        "categories": [{"code": "SYN_ELEC", "category": "ELECTRICAL", "text": "SYNTHETIC electrical changes."}],
    },
    "manufacturer_warranty_note": "SYNTHETIC: manufacturer warranty follows each manufacturer's own terms.",
    "warranty_exclusions": [{"code": "SYN_MISUSE", "text": "SYNTHETIC: damage from misuse."}],
    "service_guidance": {
        "contact_code": "SYN_SERVICE",
        "what_to_provide": ["SYNTHETIC: your quotation reference."],
        "reference_process": "SYNTHETIC: you receive a request reference.",
        "escalation": "SYNTHETIC service escalation.",
    },
    "handover": [{"code": "SYN_INSPECT", "category": "FINAL_INSPECTION", "text": "SYNTHETIC joint inspection."}],
    "care": [{"code": "SYN_DRY", "category": "FURNITURE_CLEANING", "text": "SYNTHETIC: wipe with a dry cloth."}],
    "next_steps": [
        {"code": "SYN_ACCEPTED", "stage": "PROPOSAL_ACCEPTED", "label": "Proposal accepted", "text": "SYNTHETIC step."},
        {"code": "SYN_CONFIRM", "stage": "VEDA_CONFIRMATION", "label": "Veda confirmation", "text": "SYNTHETIC step."},
        {"code": "SYN_HANDOVER", "stage": "HANDOVER", "label": "Handover", "text": "SYNTHETIC step."},
    ],
    "payment_safety": "SYNTHETIC: payment instructions come only through approved Veda Spaces channels.",
}
