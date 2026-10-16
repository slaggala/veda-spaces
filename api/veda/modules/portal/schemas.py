"""Customer Project Portal request bodies. Closed: an unknown field is refused (422 UNKNOWN_FIELD)."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, WithJsonSchema
from pydantic_core import PydanticCustomError

from veda.kernel.dto import Closed, optional_text, text

from . import vocab as V


def _relationship(value: str) -> str:
    if value not in V.RELATIONSHIPS:
        raise PydanticCustomError("INVALID_CHOICE", "Not one of the allowed values.")
    return value


Relationship = Annotated[
    str, AfterValidator(_relationship), WithJsonSchema({"type": "string", "enum": list(V.RELATIONSHIPS)})
]


class SignInIn(Closed):
    email: Annotated[str, text(254, min_len=3)]


class SessionIn(Closed):
    token: Annotated[str, text(100, min_len=1)]


class GrantIn(Closed):
    email: Annotated[str | None, optional_text(254)] = None  # default: the enquiry's email
    display_name: Annotated[str | None, optional_text(150)] = None  # default: the enquiry's name
    relationship: Relationship = "PRIMARY_CUSTOMER"
