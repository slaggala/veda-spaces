"""Kernel logical types and their per-engine physical mapping (03 §12, PLAT-004).

| Logical     | SQLite                               | PostgreSQL  |
|-------------|--------------------------------------|-------------|
| GUID        | CHAR(32) + canonical UUIDv7 CHECK    | uuid        |
| UTCDATETIME | TEXT ``YYYY-MM-DDTHH:MM:SS.ffffffZ`` | timestamptz |
| JSON        | TEXT + ``json_valid`` CHECK          | jsonb       |
| BOOL        | INTEGER + ``IN (0,1)`` CHECK         | boolean     |

The SQLite-only CHECK constraints are attached by ``veda.kernel.base``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeDecorator

from .ids import is_valid_id


class InvalidIdError(ValueError):
    pass


class GUID(TypeDecorator):
    """UUIDv7, always the 32-hex form in application code (ADR-002)."""

    impl = sa.CHAR(32)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=False))
        return dialect.type_descriptor(sa.CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not is_valid_id(value):
            raise InvalidIdError(f"not a canonical UUIDv7: {value!r}")
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return str(value).replace("-", "").lower()

    def __repr__(self) -> str:
        return "GUID()"


class UTCDateTime(TypeDecorator):
    """An instant stored in UTC (PLAT-007). Naive datetimes are rejected."""

    impl = sa.String(27)
    cache_ok = True
    FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.TIMESTAMP(timezone=True))
        return dialect.type_descriptor(sa.String(27))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError("UTCDateTime requires a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive datetimes are not allowed (PLAT-007)")
        value = value.astimezone(UTC)
        if dialect.name == "postgresql":
            return value
        return value.strftime(self.FORMAT)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        return datetime.strptime(value, self.FORMAT).replace(tzinfo=UTC)

    def __repr__(self) -> str:
        return "UTCDateTime()"


class JSONType(TypeDecorator):
    """JSON document: TEXT + json_valid on SQLite, jsonb on PostgreSQL."""

    impl = sa.JSON(none_as_null=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.JSONB(none_as_null=True))
        return dialect.type_descriptor(sa.JSON(none_as_null=True))

    def __repr__(self) -> str:
        return "JSONType()"


def Bool() -> sa.Boolean:  # noqa: N802 - reads like a type in model declarations
    # The SQLite IN (0,1) CHECK is attached explicitly and named (03 §1).
    return sa.Boolean(create_constraint=False)
