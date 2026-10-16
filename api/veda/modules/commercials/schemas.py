"""Project Commercials request bodies. Closed: an unknown field is refused (422 UNKNOWN_FIELD). Money is integer paise
(``*_minor``), strictly an integer: a float, a string or a boolean is refused."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field, WithJsonSchema, model_validator
from pydantic_core import PydanticCustomError

from veda.kernel.dto import CalendarDate, Closed, Id, optional_text, text

from . import vocab as V

Paise = Annotated[int, Field(strict=True, ge=1, le=10**13)]


def _one_of(values: tuple[str, ...]):
    def check(value: str) -> str:
        if value not in values:
            raise PydanticCustomError("INVALID_CHOICE", "Not one of the allowed values.")
        return value

    return AfterValidator(check)


Method = Annotated[str, _one_of(V.PAYMENT_METHODS), WithJsonSchema({"type": "string", "enum": list(V.PAYMENT_METHODS)})]
ReversalReason = Annotated[str, _one_of(V.REVERSAL_REASONS),
                           WithJsonSchema({"type": "string", "enum": list(V.REVERSAL_REASONS)})]  # fmt: skip


class OpenIn(Closed):
    quotation_id: Id


class InstalmentIn(Closed):
    label: Annotated[str, text(120, min_len=1)]
    when: Annotated[str, text(200, min_len=1)]
    amount_minor: Paise
    requested: bool = False
    due_on: CalendarDate | None = None


class ScheduleIn(Closed):
    reason: Annotated[str, text(1000, min_len=5)]
    instalments: list[InstalmentIn] = Field(max_length=V.MAX_INSTALMENTS)


class RequestIn(Closed):
    due_on: CalendarDate | None = None


class PaymentIn(Closed):
    amount_minor: Paise
    received_on: CalendarDate
    method_code: Method
    external_reference: Annotated[str | None, optional_text(100)] = None
    customer_note: Annotated[str | None, optional_text(300)] = None
    internal_note: Annotated[str | None, optional_text(1000)] = None


class ReverseIn(Closed):
    reason_code: ReversalReason
    note: Annotated[str | None, optional_text(500)] = None

    @model_validator(mode="after")
    def _note(self):
        if self.reason_code == "OTHER" and not self.note:
            raise PydanticCustomError("REASON_REQUIRED", "Say why the payment is reversed.")
        return self


class InvoiceIn(Closed):
    instalment_id: Id
    due_on: CalendarDate | None = None
    customer_note: Annotated[str | None, optional_text(500)] = None


class CancelIn(Closed):
    reason: Annotated[str, text(500, min_len=5)]
