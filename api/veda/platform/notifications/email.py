"""Email provider abstraction (NOTIF-009, ADR-007).

* ``SesEmailProvider`` — Amazon SES v2 in production (IAM role, no static keys).
* ``CaptureEmailProvider`` — local/test/staging: records messages in memory and
  optionally writes ``.eml`` files for inspection. Nothing leaves the host.
* ``LoggingEmailProvider`` — logs masked metadata only.

Emails are sent only by the outbox worker after commit, so a provider error
never rolls back or delays business data (NOTIF-008).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from pathlib import Path

from veda.config import settings
from veda.kernel.dto import mask_email
from veda.kernel.ids import new_id

log = logging.getLogger("veda.email")


@dataclass
class EmailMessage:
    to: list[str]
    subject: str
    text: str
    html: str
    template: str
    headers: dict[str, str] = field(default_factory=dict)


class EmailProvider:
    name = "base"

    def send(self, message: EmailMessage) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class CaptureEmailProvider(EmailProvider):
    name = "capture"
    _lock = threading.Lock()
    sent: list[EmailMessage] = []

    def __init__(self, directory: str | None = None):
        self.directory = Path(directory) if directory else None

    def send(self, message: EmailMessage) -> str:
        message_id = new_id()
        with self._lock:
            CaptureEmailProvider.sent.append(message)
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
            mime = MimeMessage()
            mime["From"] = settings().email_sender
            mime["To"] = ", ".join(message.to)
            mime["Subject"] = message.subject
            for k, v in message.headers.items():
                mime[k] = v
            mime.set_content(message.text)
            mime.add_alternative(message.html, subtype="html")
            (self.directory / f"{message_id}-{message.template}.eml").write_bytes(bytes(mime))
        log.info("email_captured template=%s to=%s", message.template, [mask_email(t) for t in message.to])
        return message_id

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls.sent.clear()


class LoggingEmailProvider(EmailProvider):
    name = "log"

    def send(self, message: EmailMessage) -> str:
        log.info("email_logged template=%s to=%s", message.template, [mask_email(t) for t in message.to])
        return new_id()


class FailingEmailProvider(EmailProvider):
    """Test double proving delivery failures never affect committed business data."""

    name = "failing"

    def send(self, message: EmailMessage) -> str:
        raise RuntimeError("email provider unavailable")


class SesEmailProvider(EmailProvider):  # pragma: no cover - requires AWS
    name = "ses"

    def __init__(self, region: str, configuration_set: str | None):
        import boto3

        self._client = boto3.client("sesv2", region_name=region)
        self._configuration_set = configuration_set

    def send(self, message: EmailMessage) -> str:
        kwargs = {
            "FromEmailAddress": settings().email_sender,
            "Destination": {"ToAddresses": message.to},
            "Content": {"Simple": {
                "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": message.text, "Charset": "UTF-8"},
                         "Html": {"Data": message.html, "Charset": "UTF-8"}},
                "Headers": [{"Name": k, "Value": v} for k, v in message.headers.items()],
            }},
            "EmailTags": [{"Name": "template", "Value": message.template}],
        }
        if self._configuration_set:
            kwargs["ConfigurationSetName"] = self._configuration_set
        return self._client.send_email(**kwargs)["MessageId"]


_override: EmailProvider | None = None


def use_provider(provider: EmailProvider | None) -> None:
    global _override
    _override = provider


def provider() -> EmailProvider:
    if _override is not None:
        return _override
    s = settings()
    if s.email_provider == "ses":
        return SesEmailProvider(s.aws_region, s.ses_configuration_set)
    if s.email_provider == "log":
        return LoggingEmailProvider()
    return CaptureEmailProvider(s.email_capture_dir)
