"""DTO building blocks: closed schemas and validators that emit 08 §11 codes."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Annotated, Any

import phonenumbers
from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict
from pydantic_core import PydanticCustomError

from . import clock
from .ids import is_valid_id


class Closed(BaseModel):
    """Closed request schema: unknown fields → 422 UNKNOWN_FIELD (SEC-004, 08 §2.2)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, populate_by_name=True)

    def provided(self) -> set[str]:
        return set(self.model_fields_set)


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")


_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")


def strip_controls(value: str) -> str:
    return _CONTROL.sub("", value)


def _id(value: Any) -> str:
    if not is_valid_id(value):
        raise PydanticCustomError("INVALID_ID", "Expected a canonical identifier (32 lowercase hex, UUIDv7).")
    return value


def _email(value: Any) -> str:
    if not isinstance(value, str):
        raise PydanticCustomError("INVALID_EMAIL", "Enter a valid email address.")
    v = value.strip()
    if len(v) > 254 or not EMAIL_RE.match(v):
        raise PydanticCustomError("INVALID_EMAIL", "Enter a valid email address.")
    return v


def _instant(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise PydanticCustomError("INVALID_DATETIME", "Include a UTC offset, for example 2026-09-30T11:00:00+05:30.")
        return clock.ensure_utc(value)
    try:
        return clock.parse_rfc3339(value)
    except (ValueError, TypeError):
        raise PydanticCustomError("INVALID_DATETIME", "Include a UTC offset, for example 2026-09-30T11:00:00+05:30.") from None


def _date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise PydanticCustomError("INVALID_DATE", "Use YYYY-MM-DD.") from None


def _reason(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PydanticCustomError("REASON_REQUIRED", "A reason is required.")
    if len(value) > 500:
        raise PydanticCustomError("TOO_LONG", "Must be at most 500 characters.")
    return value.strip()


def text(max_len: int, *, min_len: int = 0, code_empty: str = "REQUIRED"):
    def check(value: Any) -> str:
        if not isinstance(value, str):
            raise PydanticCustomError("INVALID", "Expected text.")
        v = strip_controls(value).strip()
        if min_len and len(v) < min_len:
            raise PydanticCustomError(code_empty, "This field is required.")
        if len(v) > max_len:
            raise PydanticCustomError("TOO_LONG", f"Must be at most {max_len} characters.")
        return v

    return BeforeValidator(check)


def optional_text(max_len: int):
    def check(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise PydanticCustomError("INVALID", "Expected text.")
        v = strip_controls(value).strip()
        if len(v) > max_len:
            raise PydanticCustomError("TOO_LONG", f"Must be at most {max_len} characters.")
        return v or None

    return BeforeValidator(check)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def casefold_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def parse_phone(raw: str) -> str:
    """libphonenumber, default region IN (04 §13). Returns E.164 or raises ValueError."""
    candidate = (raw or "").strip()
    if not candidate:
        raise ValueError("REQUIRED")
    try:
        number = phonenumbers.parse(candidate, None if candidate.startswith("+") else "IN")
    except phonenumbers.NumberParseException as exc:
        raise ValueError("INVALID_PHONE") from exc
    if not phonenumbers.is_valid_number(number):
        raise ValueError("INVALID_PHONE")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def _phone(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PydanticCustomError("REQUIRED", "Enter a phone number.")
    if len(value) > 30:
        raise PydanticCustomError("TOO_LONG", "Must be at most 30 characters.")
    try:
        parse_phone(value)
    except ValueError:
        raise PydanticCustomError("INVALID_PHONE", "Enter a valid phone number.") from None
    return value.strip()


def _timezone(value: Any) -> str:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(str(value))
    except (ZoneInfoNotFoundError, ValueError):
        raise PydanticCustomError("INVALID_TIMEZONE", "Use an IANA time zone such as Asia/Kolkata.") from None
    return str(value)


Id = Annotated[str, BeforeValidator(_id)]
Email = Annotated[str, BeforeValidator(_email)]
Instant = Annotated[datetime, BeforeValidator(_instant)]
CalendarDate = Annotated[date, BeforeValidator(_date)]
Reason = Annotated[str, BeforeValidator(_reason)]
Phone = Annotated[str, BeforeValidator(_phone)]
TimeZone = Annotated[str, BeforeValidator(_timezone)]
Password = Annotated[str, AfterValidator(lambda v: v)]


def csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return phone
    return phone[:3] + "*" * max(0, len(phone) - 7) + phone[-4:]
