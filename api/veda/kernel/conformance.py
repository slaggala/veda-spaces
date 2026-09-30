"""Schema conformance check (03 §2.7, DATA-011, DATA-014, TD-H).

Introspects a migrated database (SQLite or PostgreSQL) and fails when any
table breaks rules 1–9. The FK-less allow-list is exactly the ten columns of
03 §2.11 and the non-entity string exemptions exactly the three of §2.11.1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from .audit_registry import (
    EVENT_ONLY,
    FKLESS_IDENTIFIERS,
    IMMUTABLE_STORE,
    NON_ENTITY_STRING_IDENTIFIERS,
    UNIQUE_INDEX_EXCEPTIONS,
    all_policies,
)

IGNORED_TABLES = {"alembic_version"}
ID_LIKE = re.compile(r".*(_id|_by|_to)$")
NOT_NULL = {"id", "created_on", "updated_on", "created_by", "updated_by", "is_deleted", "version"}
NULLABLE = {"deleted_on", "deleted_by"}
BEHAVIOR_EXCEPTIONS = {"EXC-001", "EXC-003", "EXC-004", "EXC-006"}


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def add(self, rule: int, message: str) -> None:
        self.problems.append(f"rule {rule}: {message}")


def _kind(col_type, dialect: str) -> str:
    name = type(col_type).__name__.upper()
    text = (
        str(
            col_type.compile(
                dialect=sa.dialects.postgresql.dialect() if dialect == "postgresql" else sa.dialects.sqlite.dialect()
            )
        ).upper()
        if hasattr(col_type, "compile")
        else name
    )
    if dialect == "postgresql":
        if "UUID" in name or text == "UUID":
            return "GUID"
        if "TIMESTAMP" in name:
            return "UTCDATETIME"
        if "JSON" in name:
            return "JSON"
    else:
        if text.startswith("CHAR(32)"):
            return "GUID"
        if text.startswith("VARCHAR(27)"):
            return "UTCDATETIME"
    if "BOOL" in name:
        return "BOOL"
    if name in ("FLOAT", "REAL", "DOUBLE", "DOUBLE_PRECISION", "NUMERIC", "DECIMAL"):
        return "FLOAT"
    if "INT" in name:
        return "INTEGER"
    if "ENUM" in name:
        return "ENUM"
    return text


def _string_spec(col_type) -> tuple[str, int | None]:
    name = type(col_type).__name__.upper()
    return ("VARCHAR" if "VARCHAR" in name or name == "STRING" else name), getattr(col_type, "length", None)


def _indexes(conn: Connection, inspector, table: str) -> list[dict]:
    out = []
    dialect = conn.dialect.name
    sqls = {}
    if dialect == "sqlite":
        sqls = {
            r[0]: (r[1] or "")
            for r in conn.exec_driver_sql(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name = ?", (table,)
            )
        }
    for ix in inspector.get_indexes(table):
        where = None
        if dialect == "sqlite":
            sql = sqls.get(ix["name"], "")
            pos = sql.upper().find(" WHERE ")
            where = sql[pos + 7 :] if pos >= 0 else None
        else:
            where = (ix.get("dialect_options") or {}).get("postgresql_where")
        out.append(
            {
                "name": ix["name"],
                "unique": bool(ix.get("unique")),
                "columns": ix.get("column_names") or [],
                "where": where,
            }
        )
    return out


def _check_names(conn: Connection, inspector, table: str) -> set[str]:
    names = {c["name"] for c in inspector.get_check_constraints(table) if c.get("name")}
    if conn.dialect.name == "sqlite":
        sql = (
            conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name = ?", (table,)).scalar()
            or ""
        )
        names |= set(re.findall(r"CONSTRAINT\s+(\w+)\s+CHECK", sql))
    return names


def check(
    conn: Connection,
    *,
    fkless=FKLESS_IDENTIFIERS,
    non_entity=NON_ENTITY_STRING_IDENTIFIERS,
    unique_exceptions=UNIQUE_INDEX_EXCEPTIONS,
    policies=None,
) -> Report:
    report = Report()
    inspector = sa.inspect(conn)
    dialect = conn.dialect.name
    policies = policies if policies is not None else all_policies()
    tables = [t for t in inspector.get_table_names() if t not in IGNORED_TABLES]
    fkless_keys = {f.key: f for f in fkless}

    if dialect == "postgresql":
        found = conn.execute(
            sa.text(
                "SELECT table_schema FROM information_schema.tables WHERE table_name = 'user' "
                "AND table_schema NOT IN ('pg_catalog', 'information_schema')"
            )
        ).fetchall()
        for (schema,) in found:
            report.add(8, f"a table named user exists in schema {schema} (ADR-001)")
        enums = conn.execute(sa.text("SELECT typname FROM pg_type WHERE typtype = 'e'")).fetchall()
        for (name,) in enums:
            report.add(6, f"native ENUM type {name} is not allowed")
    if "user" in tables:
        report.add(8, "a table named user exists (ADR-001)")

    for f in fkless:
        if not f.documented():
            report.add(3, f"FK-less registry entry {f.key} is missing documentation fields")

    for table in tables:
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        fks = inspector.get_foreign_keys(table)
        fk_cols = {}
        for fk in fks:
            for c in fk["constrained_columns"]:
                fk_cols[c] = fk
            opts = fk.get("options") or {}
            for action in ("ondelete", "onupdate"):
                value = (opts.get(action) or "").upper()
                if value in ("CASCADE", "SET NULL", "SET DEFAULT"):
                    report.add(6, f"{table}.{fk['constrained_columns']} has {action} {value}")
        checks = _check_names(conn, inspector, table)
        indexes = _indexes(conn, inspector, table)
        # rule 7 / 9: registry
        policy = policies.get(table)
        if policy is None:
            report.add(7, f"{table} is not registered in the audit policy registry")
        else:
            if (policy.policy == IMMUTABLE_STORE and "EXC-001" not in policy.exceptions) or (
                not policy.soft_delete and not (set(policy.exceptions) & BEHAVIOR_EXCEPTIONS)
            ):
                report.add(9, f"{table} deviates from the contract without a registered exception")
            if f"ck_{table}__never_deleted" in checks and policy.soft_delete:
                report.add(9, f"{table} blocks soft delete but the registry says it is soft-deletable")
            if policy.policy == EVENT_ONLY and not policy.exceptions:
                report.add(9, f"{table} is EVENT_ONLY without a registered exception")
        # rule 1: contract columns
        for name in NOT_NULL | NULLABLE:
            col = cols.get(name)
            if col is None:
                report.add(1, f"{table} lacks contract column {name}")
                continue
            if name in NOT_NULL and col["nullable"]:
                report.add(1, f"{table}.{name} must be NOT NULL")
            if name in NULLABLE and not col["nullable"]:
                report.add(1, f"{table}.{name} must be nullable")
            kind = _kind(col["type"], dialect)
            expected = {
                "id": "GUID",
                "created_by": "GUID",
                "updated_by": "GUID",
                "deleted_by": "GUID",
                "created_on": "UTCDATETIME",
                "updated_on": "UTCDATETIME",
                "deleted_on": "UTCDATETIME",
                "is_deleted": "BOOL",
                "version": "INTEGER",
            }[name]
            if kind != expected:
                report.add(1, f"{table}.{name} has type {kind}, expected {expected}")
        for name, col in cols.items():
            kind = _kind(col["type"], dialect)
            if kind == "FLOAT":
                report.add(1, f"{table}.{name} uses floating point (DATA-016)")
            if kind == "ENUM":
                report.add(6, f"{table}.{name} uses a native ENUM")
        # rule 2: primary key
        pk = inspector.get_pk_constraint(table).get("constrained_columns") or []
        if pk != ["id"] or ("id" in cols and _kind(cols["id"]["type"], dialect) != "GUID"):
            report.add(2, f"{table} primary key must be id of type GUID (found {pk})")
        if dialect == "sqlite" and f"ck_{table}__id_format" not in checks:
            report.add(1, f"{table} lacks ck_{table}__id_format")
        # rule 3: actor FKs and ID-like columns
        for actor_col in ("created_by", "updated_by", "deleted_by"):
            fk = fk_cols.get(actor_col)
            if fk is None or fk["referred_table"] != "app_user" or fk["referred_columns"] != ["id"]:
                report.add(3, f"{table}.{actor_col} must be an FK to app_user.id")
        for name, col in cols.items():
            if name == "id":
                continue
            kind = _kind(col["type"], dialect)
            key = f"{table}.{name}"
            id_like = bool(ID_LIKE.match(name)) or kind == "GUID"
            if name in fk_cols:
                if kind != "GUID":
                    report.add(4, f"{key} is an FK but not of the GUID type")
                continue
            if key in non_entity:
                want_type, want_len = non_entity[key]
                got_type, got_len = _string_spec(col["type"])
                if kind == "GUID" or got_type != want_type or got_len != want_len:
                    report.add(3, f"{key} must be exactly {want_type}({want_len}) (R-01)")
                continue
            if not id_like:
                continue
            entry = fkless_keys.get(key)
            if entry is None:
                report.add(3, f"{key} is ID-like without an FK and is not a registered FK-less identifier")
                continue
            if kind != "GUID":
                report.add(3, f"{key} is registered FK-less but is not GUID-typed")
            if dialect == "sqlite" and f"ck_{table}__{name}_format" not in checks:
                report.add(3, f"{key} lacks its UUIDv7 format CHECK")
            if entry.discriminator and entry.discriminator not in cols:
                report.add(3, f"{key} lacks its discriminator column {entry.discriminator}")
            if entry.pair_check and entry.pair_check not in checks:
                report.add(3, f"{key} lacks its pair CHECK {entry.pair_check}")
            if entry.index and entry.index not in {ix["name"] for ix in indexes}:
                report.add(3, f"{key} lacks its index {entry.index}")
        for key in non_entity:
            t, c = key.split(".")
            if t == table and c not in cols:
                report.add(3, f"documented non-entity identifier {key} is missing")
        # rule 5: unique indexes need the live predicate unless allow-listed (EXC-007)
        for ix in indexes:
            if not ix["unique"] or ix["name"] in unique_exceptions:
                continue
            where = (ix["where"] or "").lower()
            if "is_deleted" not in where:
                report.add(5, f"unique index {ix['name']} lacks the is_deleted = false predicate")
    for f in fkless:
        if f.table not in tables:
            continue
        if f.column not in {c["name"] for c in inspector.get_columns(f.table)}:
            report.add(3, f"registered FK-less identifier {f.key} is missing from the schema")
    return report
