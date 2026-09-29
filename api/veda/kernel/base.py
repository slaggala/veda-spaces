"""Declarative base and the nine-column audit contract (ADR-003, 03 §2.1).

Every persisted table inherits ``AuditedBase``. ``finalize_metadata`` then
attaches, per table:

* the portable contract CHECKs (soft-delete consistency, version, time order);
* the SQLite-only CHECKs that give the logical types their meaning on SQLite
  (UUIDv7 format per GUID column, ``json_valid`` per JSON column, ``IN (0,1)``
  per BOOL column, ``length(col) <= n`` per VARCHAR/CHAR column) (03 §12).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, event
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    ORMExecuteState,
    Session,
    declared_attr,
    mapped_column,
    with_loader_criteria,
)

from .types import GUID, Bool, JSONType, UTCDateTime

NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s__%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}

CONTRACT_COLUMNS = (
    "id",
    "created_on",
    "updated_on",
    "created_by",
    "updated_by",
    "is_deleted",
    "deleted_on",
    "deleted_by",
    "version",
)


def guid_format_sql(col: str) -> str:
    return (
        f"length({col}) = 32 AND {col} NOT GLOB '*[^0-9a-f]*' "
        f"AND substr({col}, 13, 1) = '7' AND substr({col}, 17, 1) IN ('8', '9', 'a', 'b')"
    )


def sqlite_check(sqltext: str, name: str) -> CheckConstraint:
    return CheckConstraint(sqltext, name=name).ddl_if(dialect="sqlite")


def live_where():
    """Partial-index predicate ``is_deleted = false`` rendered per engine (03 §1)."""
    return {"sqlite_where": sa.text("is_deleted = 0"), "postgresql_where": sa.text("is_deleted = false")}


def where(sqlite: str, postgresql: str | None = None):
    return {"sqlite_where": sa.text(sqlite), "postgresql_where": sa.text(postgresql or sqlite)}


def in_check(table: str, col: str, values: tuple[str, ...], *, nullable: bool = False, name: str | None = None) -> CheckConstraint:
    quoted = ", ".join(f"'{v}'" for v in values)
    expr = f"{col} IN ({quoted})"
    if nullable:
        expr = f"{col} IS NULL OR {expr}"
    return CheckConstraint(expr, name=name or f"ck_{table}__{col}")


def actor_fk(table_placeholder: str | None = None):
    return ForeignKey("app_user.id", ondelete="RESTRICT")


class Base(DeclarativeBase):
    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: UTCDateTime()}


class AuditedBase(Base):
    """Abstract base carrying the audit contract. Populated only by the kernel hook."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, sort_order=-100)
    created_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, sort_order=-99)
    updated_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, sort_order=-98)

    @declared_attr
    def created_by(cls) -> Mapped[str]:
        return mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False, sort_order=-97)

    @declared_attr
    def updated_by(cls) -> Mapped[str]:
        return mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False, sort_order=-96)

    is_deleted: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false(), sort_order=-95)
    deleted_on: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, sort_order=-94)

    @declared_attr
    def deleted_by(cls) -> Mapped[str | None]:
        return mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True, sort_order=-93)

    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default=sa.text("1"), sort_order=-92)

    @declared_attr.directive
    def __mapper_args__(cls):
        # The kernel sets ``version`` itself — once per object per unit of work — and SQLAlchemy still puts the
        # previous value in every UPDATE's WHERE clause (optimistic concurrency, DATA-006).
        return {"version_id_col": cls.__table__.c.version, "version_id_generator": False}


def _string_length(col_type) -> int | None:
    if isinstance(col_type, (sa.String, sa.CHAR)) and not isinstance(col_type, sa.Text):
        return col_type.length
    return None


def finalize_metadata(metadata: sa.MetaData) -> None:
    """Attach contract and SQLite type CHECKs to every table exactly once."""
    for table in metadata.sorted_tables:
        if table.info.get("veda_finalized"):
            continue
        t = table.name
        existing = {c.name for c in table.constraints if c.name}

        def add(constraint: CheckConstraint, table=table, existing=existing) -> None:
            if constraint.name not in existing:
                table.append_constraint(constraint)
                existing.add(constraint.name)

        add(
            CheckConstraint(
                "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR "
                "(is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
                name=f"ck_{t}__soft_delete_consistent",
            )
        )
        add(CheckConstraint("version >= 1", name=f"ck_{t}__version_positive"))
        add(CheckConstraint("updated_on >= created_on", name=f"ck_{t}__updated_after_created"))
        for column in table.columns:
            ctype = column.type
            if isinstance(ctype, GUID):
                name = f"ck_{t}__id_format" if column.name == "id" else f"ck_{t}__{column.name}_format"
                expr = guid_format_sql(column.name)
                if column.nullable:
                    expr = f"{column.name} IS NULL OR ({expr})"
                add(sqlite_check(expr, name))
            elif isinstance(ctype, JSONType):
                add(sqlite_check(f"{column.name} IS NULL OR json_valid({column.name})", f"ck_{t}__{column.name}_json"))
            elif isinstance(ctype, sa.Boolean):
                add(sqlite_check(f"{column.name} IN (0, 1)", f"ck_{t}__{column.name}_bool"))
            else:
                length = _string_length(ctype)
                if length:
                    add(sqlite_check(f"length({column.name}) <= {length}", f"ck_{t}__{column.name}_len"))
        table.info["veda_finalized"] = True


# ---------------------------------------------------------------------------
# Default soft-delete filter (DATA-008): repositories see live rows unless the
# statement opts out with ``execution_options(include_deleted=True)``.
# ---------------------------------------------------------------------------


@event.listens_for(Session, "do_orm_execute")
def _soft_delete_filter(state: ORMExecuteState) -> None:
    if not state.is_select or state.is_column_load or state.is_relationship_load:
        return
    if state.execution_options.get("include_deleted", False):
        return
    state.statement = state.statement.options(
        with_loader_criteria(AuditedBase, lambda cls: cls.is_deleted == sa.false(), include_aliases=True)
    )


__all__ = [
    "AuditedBase",
    "Base",
    "Bool",
    "CONTRACT_COLUMNS",
    "GUID",
    "JSONType",
    "UTCDateTime",
    "finalize_metadata",
    "in_check",
    "live_where",
    "sqlite_check",
    "where",
]
