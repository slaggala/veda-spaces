"""Project Commercials test harness: SYNTHETIC accepted quotations made through the real B1-B4 API
(``tests.support.portal.Portal``), the commercial team, and a SYNTHETIC PCM-D01 decision (refused outside tests).
Nothing here is a real customer, amount, GSTIN or Veda Spaces decision.

Personas: ``manager`` and ``second_manager`` (SALES_MANAGER: every ``commercials.*`` code), ``founder``, ``sales`` (no
commercial code), ``accounts`` (an ESTIMATOR granted ``commercials.view`` and ``commercials.payment.record`` at OWN
scope: the individually-granted persona).
"""

from __future__ import annotations

import copy
import itertools
from typing import Any

import pytest

from tests.support.commercial import ok
from tests.support.portal import Portal

ON = pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
                          customer_portal_enabled=True, project_commercials_enabled=True)  # fmt: skip
BASE = "/api/v1/commercials"
SYNTHETIC_POLICY: dict[str, Any] = {
    "schema": "veda.commercials.policy/1", "version": "PCM-SYNTHETIC-1", "status": "SYNTHETIC_TEST_ONLY",
    "note": "Synthetic test policy; never a Veda decision.",
    "decisions": {"PCM-D01": {"document_title": "Tax invoice", "legal_name": "Synthetic Interiors (test only)",
                              "address_lines": ["1 Test Street", "Test City 000000"], "gstin": "00AAAAA0000A0Z0",
                              "sac_code": "995411", "footer": ["Synthetic footer (test only)."]}},
}  # fmt: skip
_keys = itertools.count(1)


def install_policy(doc: dict | None = SYNTHETIC_POLICY) -> None:
    from veda.modules.commercials import policy

    policy.install_for_tests(copy.deepcopy(doc) if doc is not None else None)


@pytest.fixture
def invoice_policy(app):
    install_policy()
    yield
    install_policy(None)


def key() -> str:
    return f"pcm-test-key-{next(_keys):08d}"


class Commercials(Portal):
    """The portal harness (accepted quotations, portal customers) plus the commercial API."""

    def __init__(self, api, factory):
        super().__init__(api, factory)
        self.second_manager = self.c.second_manager
        self.sales = self.c.sales
        self.accounts = factory.user("ESTIMATOR")
        for code in ("commercials.view", "commercials.payment.record"):
            factory.grant(self.accounts, code, scope="OWN")

    def tok(self, user) -> str:
        return self.token(user)

    def call(self, method: str, path: str, body=None, user=None, **kw):
        return self.api.call(method, path, body, token=self.tok(user or self.manager), **kw)

    # --- accounts ----------------------------------------------------------------------------------------------------
    def open(self, q: dict, user=None, status: int = 201):
        r = self.call("POST", BASE, {"quotation_id": q["id"]}, user)
        assert r.status == status, r
        return r.data if status in (200, 201) else r

    def opened(self, key_: str = "2BHK", **kw) -> tuple[dict, dict, dict]:
        """(property, accepted quotation, commercial record)."""
        prop, _, q = self.accepted(key_, **kw)
        return prop, q, self.open(q)

    def get(self, account: dict | str, user=None) -> dict:  # type: ignore[override]
        aid = account if isinstance(account, str) else account["id"]
        return ok(self.call("GET", f"{BASE}/{aid}", user=user))

    def revise(self, account: dict, instalments: list[dict], reason: str = "Synthetic revision", user=None,
               status: int = 200):  # fmt: skip
        cur = self.get(account)
        r = self.call("POST", f"{BASE}/{account['id']}/schedule", {"reason": reason, "instalments": instalments}, user,
                      if_match=cur["version"])  # fmt: skip
        assert r.status == status, r
        return r.data if status == 200 else r

    def request(self, account: dict, instalment_id: str, due_on: str | None = None, user=None, status: int = 200):
        cur = self.get(account)
        r = self.call("POST", f"{BASE}/{account['id']}/instalments/{instalment_id}/request",
                      {"due_on": due_on} if due_on else {}, user, if_match=cur["version"])  # fmt: skip
        assert r.status == status, r
        return r.data if status == 200 else r

    def pay(self, account: dict, amount_minor: int, *, user=None, status: int = 201, idem: str | None = None,
            received_on: str | None = None, **fields):  # fmt: skip
        from veda.kernel import clock

        body = {"amount_minor": amount_minor, "received_on": received_on or clock.now().date().isoformat(),
                "method_code": "BANK_TRANSFER", **fields}  # fmt: skip
        r = self.call("POST", f"{BASE}/{account['id']}/payments", body, user,
                      headers={"Idempotency-Key": idem or key()})  # fmt: skip
        assert r.status == status, r
        return r.data if status in (200, 201) else r

    def reverse(self, account: dict, payment_id: str, reason_code: str = "RECORDED_IN_ERROR", user=None,
                status: int = 200, note: str | None = None):  # fmt: skip
        cur = self.get(account)
        body = {"reason_code": reason_code, **({"note": note} if note else {})}
        r = self.call("POST", f"{BASE}/{account['id']}/payments/{payment_id}/reverse", body, user or self.second_manager,
                      if_match=cur["version"])  # fmt: skip
        assert r.status == status, r
        return r.data if status == 200 else r

    def draft(self, account: dict, instalment_id: str, user=None, status: int = 201, **fields):
        r = self.call("POST", f"{BASE}/{account['id']}/invoices", {"instalment_id": instalment_id, **fields}, user)
        assert r.status == status, r
        return r.data if status == 201 else r

    def invoice(self, invoice_id: str, user=None) -> dict:
        return ok(self.call("GET", f"/api/v1/commercial-invoices/{invoice_id}", user=user))

    def invoice_action(self, invoice_id: str, action: str, body=None, user=None, status: int = 200):
        cur = self.invoice(invoice_id)
        r = self.call("POST", f"/api/v1/commercial-invoices/{invoice_id}/{action}", body or {}, user,
                      if_match=cur["version"])  # fmt: skip
        assert r.status == status, r
        return r.data if status == 200 else r

    def issued_invoice(self, account: dict, position: int = 1, **fields) -> dict:
        line = self.get(account)["schedule"]["lines"][position - 1]
        inv = self.draft(account, line["id"], **fields)
        return self.invoice_action(inv["id"], "issue")


def amounts(account: dict) -> list[int]:
    return [x["amount_minor"] for x in account["schedule"]["lines"]]
