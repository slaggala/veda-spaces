"""The customer configuration: a strict, allowlisted schema (R7, R8).

This is the only shape a V3 configuration takes, from the public request to the stored snapshot:

- every field is a catalog key, a closed literal, a bounded number or a boolean;
- there is no free text, no city or address, and no personal data;
- unknown fields are refused, and every collection and number is bounded.

The resolver normalises a valid configuration (explicit variant, options, measurements and extra counts for
everything priced), and the snapshot stores exactly that normal form. The request body itself is never stored.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, ValidationError

Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")]
InputCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]
Measure = Annotated[StrictFloat | StrictInt, Field(gt=0, le=100_000)]

MAX_ROOMS = 20
MAX_ITEMS = 12  # products or extras per room
MAX_KEYS = 10  # options or measurements per item


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProductChoice(_Strict):
    variant: Key | None = None
    options: dict[Key, Key] = Field(default_factory=dict, max_length=MAX_KEYS)
    measurements: dict[InputCode, Measure] = Field(default_factory=dict, max_length=MAX_KEYS)
    removed: StrictBool = False


class ExtraChoice(_Strict):
    count: Annotated[StrictInt, Field(ge=1, le=10)] = 1
    measurements: dict[InputCode, Measure] = Field(default_factory=dict, max_length=MAX_KEYS)


class RoomChoice(_Strict):
    room: Key
    products: dict[Key, ProductChoice] = Field(default_factory=dict, max_length=MAX_ITEMS)
    extras: dict[Key, ExtraChoice] = Field(default_factory=dict, max_length=MAX_ITEMS)


class Configuration(_Strict):
    home: Key
    package: Key
    project_kind: Literal["NEW_HOME", "RENOVATION"] = "NEW_HOME"
    rooms: list[RoomChoice] = Field(min_length=1, max_length=MAX_ROOMS)


_MESSAGES = {
    "missing": "This is required.",
    "extra_forbidden": "This field is not accepted.",
    "too_long": "Too many entries.",
    "too_short": "Choose at least one.",
}


def parse(raw: object) -> Configuration:
    """Validate an untrusted configuration. Raises ConfigurationError with customer-safe field errors: the path of
    each problem and a fixed message, never the submitted value, a schema detail or an internal identifier."""
    if not isinstance(raw, dict):
        raise ConfigurationError([{"field": "configuration", "code": "INVALID", "message": "Send your choices."}])
    try:
        return Configuration.model_validate(raw)
    except ValidationError as err:
        errors = []
        for e in err.errors()[:20]:
            path = ".".join(_segment(p) for p in e["loc"]) or "configuration"
            code = "UNKNOWN_FIELD" if e["type"] == "extra_forbidden" else "INVALID"
            errors.append(
                {"field": path[:120], "code": code, "message": _MESSAGES.get(e["type"], "This value is not accepted.")}
            )
        raise ConfigurationError(errors) from None


_SAFE_SEGMENT = re.compile(r"^(?:[a-z][a-z0-9_.-]{1,99}|[A-Z][A-Z0-9_]{1,39}|\d{1,3})$")


def _segment(part: str | int) -> str:
    """A path segment is echoed only when it is an index or a well-formed key; anything a customer typed is masked."""
    text = str(part)
    return text if _SAFE_SEGMENT.match(text) else "*"


class ConfigurationError(ValueError):
    def __init__(self, errors: list[dict[str, str]]):
        self.errors = errors
        super().__init__("; ".join(e["message"] for e in errors))
