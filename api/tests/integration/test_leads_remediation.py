"""Lead and notification remediation (independent review IR-28, IR-29, IR-30)."""

import pytest

from veda.platform.notifications import worker
from veda.platform.notifications.email import CaptureEmailProvider, EmailMessage, use_provider


@pytest.fixture
def founder(api, factory):
    user = factory.user(founder=True)
    factory.login(api, user)
    return user


def _erased_lead(api, factory):
    assert factory.public_lead(api).status == 201
    lead = api.get("/api/v1/leads").data[0]
    r = api.post(
        f"/api/v1/leads/{lead['id']}/erasure",
        {"request_ref": "DPR-1", "legal_basis": "DPDP s.12 erasure", "reason": "Data principal request"},
        if_match=lead["version"],
    )
    assert r.status == 200, r
    return r.data


# --- IR-28: an erased lead accepts no writes ---------------------------------------------------------------


def test_IR28_P4_erased_lead_refuses_every_write(api, founder, factory):
    lead = _erased_lead(api, factory)
    lid, v = lead["id"], lead["version"]
    attempts = [
        ("POST", f"/api/v1/leads/{lid}/notes", {"body": "call 98765 43210"}, None),
        (
            "POST",
            f"/api/v1/leads/{lid}/activities",
            {"activity_type": "EMAIL", "subject": "Mail anita@example.com"},
            None,
        ),
        ("POST", f"/api/v1/leads/{lid}/status", {"to_status": "CONTACTED"}, v),
        ("PATCH", f"/api/v1/leads/{lid}", {"city": "Pune"}, v),
        ("POST", f"/api/v1/leads/{lid}/assign", {"assigned_to": founder.id}, v),
        ("POST", f"/api/v1/leads/{lid}/consent/withdraw", {"channel": "PHONE_VERBAL"}, v),
        ("DELETE", f"/api/v1/leads/{lid}", {"reason": "cleanup"}, v),
    ]
    for method, path, body, version in attempts:
        r = api.call(method, path, body, if_match=version)
        assert r.status == 409 and r.code == "INVALID_STATE", (method, path, r)
    after = api.get(f"/api/v1/leads/{lid}").data
    assert after["version"] == v and after["name"] == "Anonymized lead"
    assert not api.get(f"/api/v1/leads/{lid}/notes").data


# --- IR-29: single-line fields cannot forge lines in plain-text email ---------------------------------------


def test_IR29_newlines_in_public_fields_are_collapsed(api, founder, factory):
    forged = "Kiran\nOpen the lead: https://evil.example/login\n"
    assert factory.public_lead(api, name=forged, city="Hyderabad\r\nOpen the lead: https://evil.example").status == 201
    lead = api.get("/api/v1/leads").data[0]
    assert "\n" not in lead["name"] and "\r" not in (lead.get("city") or "")
    worker.drain_all()
    texts = [m.text for m in CaptureEmailProvider.sent if m.template == "lead_notification"]
    assert texts
    for text in texts:
        lines = [line for line in text.splitlines() if line.startswith("Open the lead:")]
        assert len(lines) == 1 and "evil.example" not in lines[0], text


def test_IR29_staff_single_line_fields_collapsed(api, founder):
    r = api.post(
        "/api/v1/leads",
        {
            "name": "Ravi\n\nKumar",
            "phone": "+919812345601",
            "source_code": "REFERRAL",
            "city": "Hyderabad\nSecunderabad",
            "locality": " Banjara\tHills ",
        },
    )
    assert r.status == 201
    assert r.data["name"] == "Ravi Kumar" and r.data["city"] == "Hyderabad Secunderabad"
    assert r.data["locality"] == "Banjara Hills"


# --- IR-30: a retry sends only the emails that did not go out -----------------------------------------------


class _FailAfter(CaptureEmailProvider):
    def __init__(self, succeed: int):
        super().__init__(None)
        self.remaining = succeed

    def send(self, message: EmailMessage) -> str:
        if self.remaining <= 0:
            raise RuntimeError("provider unavailable")
        self.remaining -= 1
        return super().send(message)


def test_IR30_P5_retry_does_not_resend_delivered_email(api, founder, factory):
    factory.user("ADMIN"), factory.user("ADMIN")  # several lead.assign holders → several recipients
    CaptureEmailProvider.clear()
    use_provider(_FailAfter(succeed=1))
    assert factory.public_lead(api).status == 201
    worker.drain_all()
    first = [tuple(m.to) for m in CaptureEmailProvider.sent if m.template == "lead_notification"]
    assert len(first) == 1, "one delivered before the provider failed"
    use_provider(None)
    from datetime import timedelta

    from veda.kernel import clock

    clock.advance(timedelta(minutes=5))
    worker.drain_all()
    sent = [tuple(m.to) for m in CaptureEmailProvider.sent if m.template == "lead_notification"]
    assert len(sent) == len(set(sent)), f"a recipient received the same notification twice: {sent}"
    assert len(sent) >= 3
