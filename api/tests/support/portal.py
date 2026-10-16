"""Customer Project Portal test harness: SYNTHETIC customers on SYNTHETIC quotations made through the real B1-B4 API
(``tests.support.project.Projects``), staff-granted portal access, and the real emailed sign-in link."""

from __future__ import annotations

from typing import Any

import pytest

from tests.support.project import Projects
from veda.platform.notifications import worker
from veda.platform.notifications.email import CaptureEmailProvider

ON = pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
                          customer_portal_enabled=True)  # fmt: skip
PUBLIC = "/api/v1/public/portal"
HEADER = "X-Veda-Portal"


class Customer:
    """A signed-in portal customer: every call sends only the portal session header (never a staff token)."""

    def __init__(self, api, email: str, token: str | None = None):
        self.api, self.email, self.token = api, email, token

    def call(self, method: str, path: str, body: Any = None, token: str | None = None):
        tok = token if token is not None else self.token
        return self.api.call(method, path, body, headers={HEADER: tok} if tok else None, anonymous=True)

    def get(self, path: str, **kw):
        return self.call("GET", path, **kw)

    def home(self):
        return self.get(f"{PUBLIC}/home")

    def property(self, property_id: str):
        return self.get(f"{PUBLIC}/properties/{property_id}")

    def quotation(self, quotation_id: str):
        return self.get(f"{PUBLIC}/quotations/{quotation_id}")


class Portal(Projects):
    """The commercial team and project personas (``Projects``), plus portal access and sign-in."""

    def grant(self, lead_id: str, email: str, user=None, status: int = 201, **body):
        r = self.as_(user or self.c.sales).post(f"/api/v1/leads/{lead_id}/portal-access", {"email": email, **body})
        assert r.status == status, r
        return r

    def access(self, lead_id: str, user=None) -> list[dict]:
        r = self.as_(user or self.manager).get(f"/api/v1/leads/{lead_id}/portal-access")
        assert r.status == 200, r
        return r.data

    def link_token(self, email: str) -> str:
        worker.drain_all()
        msgs = [m for m in CaptureEmailProvider.sent if email in m.to and "/portal/sign-in#t=" in m.text]
        assert msgs, f"no portal sign-in email to {email}"
        return msgs[-1].text.split("/portal/sign-in#t=")[1].split()[0]

    def emails_to(self, email: str) -> int:
        worker.drain_all()
        return sum(1 for m in CaptureEmailProvider.sent if email in m.to and "/portal/sign-in#t=" in m.text)

    def sign_in(self, email: str, token: str | None = None) -> Customer:
        r = self.api.post(f"{PUBLIC}/session", {"token": token or self.link_token(email)}, anonymous=True)
        assert r.status == 201, r
        return Customer(self.api, email, r.data["token"])

    def invite(self, lead_id: str, email: str, **body) -> Customer:
        self.grant(lead_id, email, **body)
        return self.sign_in(email)


def keys(value: Any, prefix: str = "") -> set[str]:
    """Every key path of a JSON value (for the no-internal-field assertions)."""
    out: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            out.add(k)
            out |= keys(v, f"{prefix}{k}.")
    elif isinstance(value, list):
        for v in value:
            out |= keys(v, prefix)
    return out
