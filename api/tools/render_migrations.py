"""Render explicit Alembic DDL for each P0 revision from the model metadata.

Developer tool. It prints ``op.create_table``/``op.create_index`` code for the
tables of one revision; the output is pasted (or written with ``--write``)
into the migration file between the ``# --- generated DDL`` markers. The
committed migrations are the source of truth; the models-match-schema test
(12 §4.11, PLAT-005) keeps them aligned.

    python tools/render_migrations.py 0004_auth
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.sql.elements import False_, TextClause, True_

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import veda.models as models  # noqa: E402
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: E402

REVISIONS: dict[str, list[str]] = {
    "0002_identity": ["app_user", "user_credential"],
    "0003_rbac": ["role", "permission", "user_role", "role_permission", "user_permission"],
    "0004_auth": [
        "user_session",
        "refresh_token",
        "user_action_token",
        "user_mfa_factor",
        "user_mfa_recovery_code",
        "mfa_challenge",
        "security_event_log",
    ],
    "0005_audit": ["audit_log"],
    "0006_reference": ["lookup_category", "lookup_value", "number_sequence"],
    "0007_notifications": ["outbox_event", "notification"],
    "0008_account_security": ["admin_approval_request"],
    "0100_crm_leads": ["lead", "lead_note", "lead_activity"],
}

# Columns added to existing tables by later revisions: app_user by 0008_account_security (02 §8.3),
# mfa_challenge by 0009_mfa_challenge_binding (IR-01). Those revisions ALTER the table by hand.
DEFERRED_COLUMNS = {
    "app_user": {
        "proposed_email",
        "proposed_email_normalized",
        "proposed_email_requested_on",
        "proposed_email_requested_by",
        "protection_level",
        "security_cooling_off_until",
    },
    "mfa_challenge": {"factor_id", "enrollment_path"},
}


def render_type(t) -> str:
    if isinstance(t, GUID):
        return "GUID()"
    if isinstance(t, UTCDateTime):
        return "UTCDateTime()"
    if isinstance(t, JSONType):
        return "JSONType()"
    if isinstance(t, sa.Boolean):
        return "sa.Boolean()"
    if isinstance(t, sa.Text):
        return "sa.Text()"
    if isinstance(t, sa.CHAR):
        return f"sa.CHAR({t.length})"
    if isinstance(t, sa.String):
        return f"sa.String({t.length})"
    if isinstance(t, sa.BigInteger):
        return "sa.BigInteger()"
    if isinstance(t, sa.SmallInteger):
        return "sa.SmallInteger()"
    if isinstance(t, sa.Integer):
        return "sa.Integer()"
    if isinstance(t, sa.Date):
        return "sa.Date()"
    raise TypeError(f"unhandled type {t!r}")


def render_default(sd) -> str | None:
    if sd is None:
        return None
    arg = sd.arg
    if isinstance(arg, False_):
        return "sa.false()"
    if isinstance(arg, True_):
        return "sa.true()"
    if isinstance(arg, TextClause):
        return f"sa.text({arg.text!r})"
    if isinstance(arg, str):
        return repr(arg)
    raise TypeError(f"unhandled server default {arg!r}")


def mentions(sqltext: str, columns: set[str]) -> bool:
    return any(re.search(rf"\b{re.escape(c)}\b", sqltext) for c in columns)


def ddl_dialect(constraint) -> str | None:
    cond = getattr(constraint, "_ddl_if", None)
    return getattr(cond, "dialect", None) if cond is not None else None


def render_table(table: sa.Table, skip: set[str]) -> str:
    lines = [f'    op.create_table(\n        "{table.name}",']
    for col in table.columns:
        if col.name in skip:
            continue
        args = [repr(col.name), render_type(col.type)]
        kwargs = [f"nullable={col.nullable}"]
        default = render_default(col.server_default)
        if default:
            kwargs.append(f"server_default={default}")
        lines.append(f"        sa.Column({', '.join(args + kwargs)}),")
    lines.append(f'        sa.PrimaryKeyConstraint("id", name="pk_{table.name}"),')
    for fk in sorted(table.foreign_key_constraints, key=lambda c: c.name):
        cols = [c.name for c in fk.columns]
        if set(cols) & skip:
            continue
        refs = [e.target_fullname for e in fk.elements]
        lines.append(
            f"        sa.ForeignKeyConstraint({cols!r}, {refs!r}, name={fk.name!r}, ondelete={fk.ondelete!r}),"
        )
    checks = [c for c in table.constraints if isinstance(c, sa.CheckConstraint)]
    for ck in sorted(checks, key=lambda c: (c.name, ddl_dialect(c) or "")):
        text = str(ck.sqltext)
        if mentions(text, skip):
            continue
        dialect = ddl_dialect(ck)
        suffix = f'.ddl_if(dialect="{dialect}")' if dialect else ""
        lines.append(f"        sa.CheckConstraint({text!r}, name={ck.name!r}){suffix},")
    lines.append("    )")
    for idx in sorted(table.indexes, key=lambda i: i.name):
        exprs = []
        skip_index = False
        for e in idx.expressions:
            if isinstance(e, sa.Column):
                if e.name in skip:
                    skip_index = True
                exprs.append(repr(e.name))
            else:
                exprs.append(f"sa.text({str(e)!r})")
        if skip_index:
            continue
        kw = []
        if idx.unique:
            kw.append("unique=True")
        sw = idx.dialect_options["sqlite"].get("where")
        pw = idx.dialect_options["postgresql"].get("where")
        if sw is not None:
            kw.append(f"sqlite_where=sa.text({str(sw)!r})")
        if pw is not None:
            kw.append(f"postgresql_where=sa.text({str(pw)!r})")
        extra = (", " + ", ".join(kw)) if kw else ""
        lines.append(f'    op.create_index({idx.name!r}, "{table.name}", [{", ".join(exprs)}]{extra})')
    return "\n".join(lines)


def render_revision(rev: str) -> str:
    parts = []
    for name in REVISIONS[rev]:
        table = models.metadata.tables[name]
        parts.append(render_table(table, DEFERRED_COLUMNS.get(name, set())))
    return "\n\n".join(parts)


MARK_START = "    # --- generated DDL (tools/render_migrations.py) ---"
MARK_END = "    # --- end generated DDL ---"


def write_into(rev: str) -> None:
    path = next(Path(__file__).resolve().parents[1].joinpath("migrations", "versions").glob(f"{rev}.py"))
    text = path.read_text()
    start, end = text.index(MARK_START), text.index(MARK_END)
    new = text[: start + len(MARK_START)] + "\n" + render_revision(rev) + "\n" + text[end:]
    path.write_text(new)
    print(f"updated {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("revision", nargs="?", choices=sorted(REVISIONS))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    revs = sorted(REVISIONS) if args.all else [args.revision]
    for r in revs:
        if args.write:
            write_into(r)
        else:
            print(f"# {r}\n{render_revision(r)}\n")
