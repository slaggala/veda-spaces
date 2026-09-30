"""Email header-injection and escaping (NOTIF-005, Phase 5 evidence)."""

from veda.platform.notifications.templates import render


def test_subject_cannot_carry_header_injection():
    subject, text, html = render(
        "approval", name="x", title="Hello\r\nBcc: attacker@example.com", message="m", link="https://app.example/x"
    )
    assert "\r" not in subject and "\n" not in subject
    assert subject == "Hello Bcc: attacker@example.com"


def test_html_body_is_escaped_and_text_is_not():
    subject, text, html = render("digest", name="<b>Priya</b>", title="t", message="a & b", link="https://x")
    assert "&lt;b&gt;Priya&lt;/b&gt;" in html and "<b>Priya</b>" not in html
    assert "<b>Priya</b>" in text and "a & b" in text
