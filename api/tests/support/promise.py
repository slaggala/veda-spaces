"""Customer Promise test harness: SYNTHETIC personas and SYNTHETIC section content.

Every value is invented for tests: not a Veda Spaces contact, inclusion, responsibility, warranty, service promise,
duration or payment instruction. Personas are synthetic accounts named by the capability they test; no real employee.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from tests.support.proposal import SYNTHETIC_PACK

ON = pytest.mark.settings(customer_promise_admin_enabled=True)
BASE = "/api/v1/customer-promise"
AUTHORITY = {"source": "CUSTOMER_PROMISE_ADMIN", "register_reference": "SYNTHETIC register entry OI-MTQ-18",
             "decided_on": "2026-10-15"}  # fmt: skip

# SYNTHETIC section values, one per section (exactly the section's keys).
SECTION_VALUES: dict[str, dict[str, Any]] = {
    "CONTACTS": {"email_domains": ["synthetic.example"], "contacts": copy.deepcopy(SYNTHETIC_PACK["contacts"]),
                 "support_escalation": SYNTHETIC_PACK["support_escalation"]},
    "INCLUSIONS": {"project_inclusions": copy.deepcopy(SYNTHETIC_PACK["project_inclusions"])},
    "RESPONSIBILITIES": {"client_responsibilities": copy.deepcopy(SYNTHETIC_PACK["client_responsibilities"])},
    "SITE_READINESS": {"site_readiness": copy.deepcopy(SYNTHETIC_PACK["site_readiness"])},
    "SITE_WORK": {"site_dependent_work": copy.deepcopy(SYNTHETIC_PACK["site_dependent_work"])},
    "WARRANTY": {"manufacturer_warranty_note": SYNTHETIC_PACK["manufacturer_warranty_note"]},
    "EXCLUSIONS": {"warranty_exclusions": copy.deepcopy(SYNTHETIC_PACK["warranty_exclusions"])},
    "SERVICE": {"service_guidance": copy.deepcopy(SYNTHETIC_PACK["service_guidance"])},
    "HANDOVER": {"handover": copy.deepcopy(SYNTHETIC_PACK["handover"])},
    "CARE": {"care": copy.deepcopy(SYNTHETIC_PACK["care"])},
    "NEXT_STEPS": {"next_steps": copy.deepcopy(SYNTHETIC_PACK["next_steps"])},
    "PAYMENT_SAFETY": {"payment_safety": SYNTHETIC_PACK["payment_safety"]},
}  # fmt: skip
SENSITIVE = ("RESPONSIBILITIES", "SITE_WORK", "WARRANTY", "EXCLUSIONS", "PAYMENT_SAFETY")
ORDINARY = tuple(c for c in SECTION_VALUES if c not in SENSITIVE)
AUTHOR_GRANTS = ("customer_promise.contacts.edit", "customer_promise.warranty.edit",
                 "customer_promise.payment_safety.edit")  # fmt: skip


def ok(r, *codes):
    assert r.status in (codes or (200, 201)), r
    return r.data


class Team:
    """The personas (synthetic accounts):

    - author: commercial owner (SALES_MANAGER) also granted contacts, warranty and payment-safety editing;
    - reviewer: a second SALES_MANAGER (ordinary sections);
    - legal: the legal/control approver (an ESTIMATOR account granted view + sensitive review; MFA);
    - approver: a FOUNDER who wrote nothing;
    - publisher: an account granted view + publish only (MFA);
    - viewer: ADMIN (view only);
    - sales, estimator, designer: ordinary roles with no Customer Promise capability.
    """

    def __init__(self, api, factory):
        self.api, self.factory = api, factory
        self.author = factory.user("SALES_MANAGER", mfa=True)
        for code in AUTHOR_GRANTS:
            factory.grant(self.author, code)
        self.reviewer = factory.user("SALES_MANAGER", mfa=True)
        self.legal = factory.user("ESTIMATOR", mfa=True)
        for code in ("customer_promise.view", "customer_promise.review.sensitive"):
            factory.grant(self.legal, code)
        self.approver = factory.user("FOUNDER")
        self.publisher = factory.user("ESTIMATOR", mfa=True)
        for code in ("customer_promise.view", "customer_promise.publish"):
            factory.grant(self.publisher, code)
        self.viewer = factory.user("ADMIN")
        self.sales = factory.user("SALES")
        self.estimator = factory.user("ESTIMATOR")
        self.designer = factory.user("DESIGNER")

    def as_(self, user):
        self.factory.login(self.api, user)
        return self.api

    def get(self, user, pack_id: str) -> dict:
        return ok(self.as_(user).get(f"{BASE}/versions/{pack_id}"))

    def draft(self, user=None, **body) -> dict:
        return ok(self.as_(user or self.author).post(f"{BASE}/versions", body), 201)

    def save(self, pack: dict, code: str, value: dict | None = None, user=None, status: int = 200):
        user = user or self.author
        cur = self.get(user, pack["id"])
        r = self.as_(user).put(f"{BASE}/versions/{pack['id']}/sections/{code}",
                               {"value": value if value is not None else SECTION_VALUES[code]},
                               if_match=cur["version"])  # fmt: skip
        assert r.status == status, r
        return r.data if status == 200 else r

    def act(self, pack: dict, action: str, user, body: dict | None = None, status: int = 200):
        cur = self.get(self.approver, pack["id"])  # the version the page showed (read by someone who may)
        r = self.as_(user).post(f"{BASE}/versions/{pack['id']}/{action}", body, if_match=cur["version"])
        assert r.status == status, r
        return r.data if status == 200 else r

    def review(self, pack: dict, code: str, user, decision: str = "APPROVED", comment: str | None = None,
               status: int = 200):  # fmt: skip
        body = {"decision": decision, **({"comment": comment} if comment else {})}
        return self.act(pack, f"sections/{code}/review", user, body, status)

    def review_all(self, pack: dict) -> dict:
        p = self.get(self.approver, pack["id"])
        for code in p["changed_sections"]:
            self.review(pack, code, self.legal if code in SENSITIVE else self.reviewer)
        return self.get(self.approver, pack["id"])

    def full_draft(self, **body) -> dict:
        p = self.draft(**body)
        for code in SECTION_VALUES:
            p = self.save(p, code)
        return p

    def publish_new(self, mutate=None, **body) -> dict:
        """A draft (all sections, or the published version changed by ``mutate(team, pack)``), reviewed, approved and
        published by the personas."""
        p = self.full_draft(**body) if mutate is None else mutate(self, self.draft(**body))
        self.act(p, "submit", self.author)
        self.review_all(p)
        self.act(p, "approve", self.approver)
        return self.act(p, "publish", self.publisher)
