"""Sales & Customer Acquisition test harness (SCA): the flags, the public beacon, and the lead facts."""

from __future__ import annotations

from tests.support.proposal import FLAGS as PROPOSAL_FLAGS

SALES = "/api/v1/sales"
EVENTS = "/api/v1/public/acquisition/events"
FLAGS = dict(PROPOSAL_FLAGS, customer_proposal_enabled=True, sales_experience_enabled=True)
INTERNAL_KEYS = ("decision_note", "margin", "cost_minor", "rate_minor", "internal", "approval_note", "cover_note",
                 "notes", "message", "snapshot", "issued_html", "phone", "email")  # fmt: skip


def beacon(api, event: str, client: str = "client-token-0123456789", **extra):
    return api.post(EVENTS, {"event": event, "client": client, **extra}, anonymous=True,
                    headers={"Origin": "http://localhost:8000"})  # fmt: skip


def keys(value, prefix: str = "") -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            out.add(k)
            out |= keys(v, prefix)
    elif isinstance(value, list):
        for v in value:
            out |= keys(v, prefix)
    return out


def progression(api, lead_id: str, token=None) -> dict:
    r = api.get(f"{SALES}/leads/{lead_id}/progression", token=token)
    assert r.status == 200, r
    return r.data
