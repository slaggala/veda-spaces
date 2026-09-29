"""Helpers used by Alembic data migrations and the maintenance CLI.

Data migrations run as SYSTEM with ``performed_via = MIGRATION`` and write
explicit audit rows (07 §3). They use lightweight typed table clauses so an
old revision never depends on the current shape of a model.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa

from . import clock
from .audit_registry import ALWAYS_EXCLUDED, FULL, all_policies, policy_for
from .ids import ANONYMOUS_USER_ID, SYSTEM_USER_ID, WEB_INTAKE_USER_ID, new_id
from .types import GUID, JSONType, UTCDateTime

IMMUTABLE_TABLES = ("audit_log", "security_event_log")

CONTRACT_COLS = {
    "id": GUID(),
    "created_on": UTCDateTime(),
    "updated_on": UTCDateTime(),
    "created_by": GUID(),
    "updated_by": GUID(),
    "is_deleted": sa.Boolean(),
    "deleted_on": UTCDateTime(),
    "deleted_by": GUID(),
    "version": sa.Integer(),
}


def dialect_name(conn) -> str:
    return conn.dialect.name


def lw(_table_name: str, /, **columns) -> sa.TableClause:
    """A lightweight typed table clause including the contract columns."""
    cols = {**CONTRACT_COLS, **columns}
    return sa.table(_table_name, *[sa.column(k, v) for k, v in cols.items()])


def contract(actor: str = SYSTEM_USER_ID, now: datetime | None = None, id_: str | None = None) -> dict[str, Any]:
    now = now or clock.now()
    return {
        "id": id_ or new_id(),
        "created_on": now,
        "updated_on": now,
        "created_by": actor,
        "updated_by": actor,
        "is_deleted": False,
        "deleted_on": None,
        "deleted_by": None,
        "version": 1,
    }


def _serialize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value.hex
    if isinstance(value, datetime):
        return clock.to_rfc3339(value, micros=True)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return str(value)


def snapshot(table: str, row: dict[str, Any]) -> dict[str, Any]:
    policy = policy_for(table)
    excluded = set(ALWAYS_EXCLUDED) | set(policy.excluded if policy else ())
    redacted = set(policy.redacted if policy else ())
    out = {}
    for key, value in row.items():
        if key in excluded:
            continue
        out[key] = "[REDACTED]" if key in redacted and value is not None else _serialize(value)
    return out


AUDIT_LOG = lw(
    "audit_log",
    entity_type=sa.String(60),
    entity_id=GUID(),
    action=sa.String(20),
    old_value=JSONType(),
    new_value=JSONType(),
    changed_fields=JSONType(),
    performed_by=GUID(),
    performed_on=UTCDateTime(),
    performed_via=sa.String(20),
    parent_entity_type=sa.String(60),
    parent_entity_id=GUID(),
    transaction_id=GUID(),
    request_id=sa.String(64),
    session_id=GUID(),
    ip_address=sa.String(45),
    user_agent=sa.String(500),
    reason=sa.String(500),
    payload_schema=sa.SmallInteger(),
)


def write_audit(
    conn,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    new_value=None,
    old_value=None,
    changed_fields=None,
    parent: tuple[str, str] | None = None,
    transaction_id: str,
    now: datetime,
    actor: str = SYSTEM_USER_ID,
    via: str = "MIGRATION",
    reason: str | None = None,
) -> None:
    conn.execute(
        AUDIT_LOG.insert().values(
            **contract(actor, now),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            changed_fields=changed_fields,
            performed_by=actor,
            performed_on=now,
            performed_via=via,
            parent_entity_type=parent[0] if parent else None,
            parent_entity_id=parent[1] if parent else None,
            transaction_id=transaction_id,
            request_id=None,
            session_id=None,
            ip_address=None,
            user_agent=None,
            reason=reason,
            payload_schema=1,
        )
    )


def audit_table_exists(conn) -> bool:
    return sa.inspect(conn).has_table("audit_log")


def insert_audited(
    conn,
    table: sa.TableClause,
    values: dict[str, Any],
    *,
    transaction_id: str,
    now: datetime,
    actor: str = SYSTEM_USER_ID,
    audit: bool = True,
) -> str:
    row = {**contract(actor, now, values.get("id")), **values}
    conn.execute(table.insert().values(**row))
    policy = policy_for(table.name)
    if audit and policy and policy.policy == FULL:
        snap = snapshot(table.name, row)
        parent = None
        if policy.parent:
            parent = (policy.parent[0], row[policy.parent[1]])
        write_audit(
            conn,
            entity_type=table.name,
            entity_id=row["id"],
            action="CREATE",
            new_value=snap,
            changed_fields=sorted(k for k, v in snap.items() if v is not None),
            parent=parent,
            transaction_id=transaction_id,
            now=now,
            actor=actor,
        )
    return row["id"]


# ---------------------------------------------------------------------------
# 0002_identity: seeded system actors (03 §2.3)
# ---------------------------------------------------------------------------

APP_USER_0002 = lw(
    "app_user",
    email=sa.String(254),
    email_normalized=sa.String(254),
    full_name=sa.String(150),
    display_name=sa.String(80),
    phone_e164=sa.String(16),
    user_type=sa.String(20),
    status=sa.String(20),
    status_changed_on=UTCDateTime(),
    timezone=sa.String(40),
    locale=sa.String(10),
    email_verified_on=UTCDateTime(),
    mfa_required=sa.Boolean(),
    authz_version=sa.Integer(),
    last_login_on=UTCDateTime(),
)

SYSTEM_USERS = (
    (SYSTEM_USER_ID, "system@system.vedaspaces.invalid", "System", "System"),
    (WEB_INTAKE_USER_ID, "web-intake@system.vedaspaces.invalid", "Website intake", "Website"),
    (ANONYMOUS_USER_ID, "anonymous@system.vedaspaces.invalid", "Anonymous", "Anonymous"),
)


def seed_system_users(conn) -> None:
    now = clock.now()
    for user_id, email, full_name, display in SYSTEM_USERS:
        conn.execute(
            APP_USER_0002.insert().values(
                **contract(SYSTEM_USER_ID, now, user_id),
                email=email,
                email_normalized=email,
                full_name=full_name,
                display_name=display,
                phone_e164=None,
                user_type="SYSTEM",
                status="ACTIVE",
                status_changed_on=now,
                timezone="Asia/Kolkata",
                locale="en-IN",
                email_verified_on=None,
                mfa_required=False,
                authz_version=1,
                last_login_on=None,
            )
        )


# ---------------------------------------------------------------------------
# 0003_rbac: roles, permission sync and the default matrix (06 §3, §6)
# ---------------------------------------------------------------------------

ROLE = lw(
    "role",
    code=sa.String(50),
    name=sa.String(100),
    name_normalized=sa.String(100),
    description=sa.String(500),
    is_system=sa.Boolean(),
    is_assignable=sa.Boolean(),
    grant_path=sa.String(25),
    mfa_required=sa.Boolean(),
    sort_order=sa.Integer(),
)
PERMISSION = lw(
    "permission",
    code=sa.String(100),
    module=sa.String(50),
    resource=sa.String(50),
    action=sa.String(50),
    name=sa.String(120),
    description=sa.String(500),
    supports_scope=sa.Boolean(),
    is_sensitive=sa.Boolean(),
    sensitivity_class=sa.String(20),
    grant_path=sa.String(25),
    is_system=sa.Boolean(),
    requirement_ref=sa.String(50),
)
ROLE_PERMISSION = lw("role_permission", role_id=GUID(), permission_id=GUID(), scope=sa.String(10))


def _permission_values(entry) -> dict[str, Any]:
    d = entry.definition
    return {
        "code": d.code,
        "module": entry.module,
        "resource": entry.resource,
        "action": entry.action,
        "name": d.name,
        "description": d.description,
        "supports_scope": d.supports_scope,
        "is_sensitive": d.is_sensitive,
        "sensitivity_class": d.sensitivity_class,
        "grant_path": d.grant_path,
        "is_system": True,
        "requirement_ref": d.requirement_ref,
    }


def sync_permissions(conn, *, audit: bool, via: str = "MIGRATION") -> dict[str, int]:
    """Upsert registry entries; soft-delete removed codes; never rename (06 §3)."""
    from veda.platform.rbac.registry import REGISTRY

    now = clock.now()
    tx = new_id()
    counts = {"inserted": 0, "updated": 0, "deleted": 0}
    existing = {
        r.code: r for r in conn.execute(sa.select(PERMISSION).where(PERMISSION.c.is_deleted == sa.false())).mappings()
    }
    registry_codes = set()
    for entry in REGISTRY:
        registry_codes.add(entry.code)
        values = _permission_values(entry)
        current = existing.get(entry.code)
        if current is None:
            insert_audited(conn, PERMISSION, values, transaction_id=tx, now=now, audit=audit)
            counts["inserted"] += 1
            continue
        # Registry-owned metadata only; name/description may be edited through the API (permission.manage).
        owned = (
            "module",
            "resource",
            "action",
            "supports_scope",
            "is_sensitive",
            "sensitivity_class",
            "grant_path",
            "requirement_ref",
        )
        changes = {k: values[k] for k in owned if current[k] != values[k]}
        if changes:
            conn.execute(
                PERMISSION.update()
                .where(PERMISSION.c.id == current["id"])
                .values(**changes, updated_on=now, updated_by=SYSTEM_USER_ID, version=current["version"] + 1)
            )
            if audit:
                write_audit(
                    conn,
                    entity_type="permission",
                    entity_id=current["id"],
                    action="UPDATE",
                    old_value={k: _serialize(current[k]) for k in changes},
                    new_value=_serialize(changes),
                    changed_fields=sorted(changes),
                    transaction_id=tx,
                    now=now,
                    via=via,
                )
            counts["updated"] += 1
    for code, current in existing.items():
        if code not in registry_codes:
            conn.execute(
                PERMISSION.update()
                .where(PERMISSION.c.id == current["id"])
                .values(
                    is_deleted=True,
                    deleted_on=now,
                    deleted_by=SYSTEM_USER_ID,
                    updated_on=now,
                    updated_by=SYSTEM_USER_ID,
                    version=current["version"] + 1,
                )
            )
            if audit:
                write_audit(
                    conn,
                    entity_type="permission",
                    entity_id=current["id"],
                    action="DELETE",
                    old_value={"is_deleted": False},
                    new_value={"is_deleted": True},
                    changed_fields=["is_deleted", "deleted_on", "deleted_by"],
                    transaction_id=tx,
                    now=now,
                    via=via,
                )
            counts["deleted"] += 1
    if counts["updated"] or counts["deleted"]:
        # Permission metadata or catalog changed: effective maps may change (06 §9).
        u = APP_USER_0002
        conn.execute(
            u.update()
            .where(u.c.user_type == "HUMAN")
            .values(
                authz_version=u.c.authz_version + 1, version=u.c.version + 1, updated_on=now, updated_by=SYSTEM_USER_ID
            )
        )
    return counts


def seed_roles_and_matrix(conn, *, audit: bool) -> None:
    from veda.platform.rbac.registry import MATRIX, ROLES, matrix_scope

    now = clock.now()
    tx = new_id()
    role_ids: dict[str, str] = {}
    for role in ROLES:
        role_ids[role.code] = insert_audited(
            conn,
            ROLE,
            {
                "code": role.code,
                "name": role.name,
                "name_normalized": role.name.strip().lower(),
                "description": role.description,
                "is_system": True,
                "is_assignable": role.is_assignable,
                "grant_path": role.grant_path,
                "mfa_required": role.mfa_required,
                "sort_order": role.sort_order,
            },
            transaction_id=tx,
            now=now,
            audit=audit,
        )
    perm_ids = {
        r.code: r.id
        for r in conn.execute(
            sa.select(PERMISSION.c.code, PERMISSION.c.id).where(PERMISSION.c.is_deleted == sa.false())
        )
    }
    for code, grants in MATRIX.items():
        for role_code, symbol in grants.items():
            insert_audited(
                conn,
                ROLE_PERMISSION,
                {
                    "role_id": role_ids[role_code],
                    "permission_id": perm_ids[code],
                    "scope": matrix_scope(symbol),
                },
                transaction_id=tx,
                now=now,
                audit=audit,
            )


def assert_rbac_seed(conn) -> None:
    """06 §3.1 rules 3 and 5, asserted in the seed migration (RBAC-018)."""
    rows = (
        conn.execute(
            sa.text(
                "SELECT r.code AS role_code, r.grant_path AS role_path, p.code AS perm_code, p.is_sensitive AS sensitive, "
                "p.grant_path AS perm_path FROM role_permission rp JOIN role r ON r.id = rp.role_id "
                "JOIN permission p ON p.id = rp.permission_id WHERE rp.is_deleted = :f AND r.is_deleted = :f AND p.is_deleted = :f"
            ),
            {"f": False},
        )
        .mappings()
        .all()
    )
    for r in rows:
        if r["role_code"] == "SALES" and r["sensitive"]:
            raise RuntimeError(f"seed violation: SALES holds sensitive permission {r['perm_code']}")
        if r["perm_path"] == "FOUNDER_WORKFLOW_ONLY" and r["role_path"] != "FOUNDER_WORKFLOW_ONLY":
            raise RuntimeError(f"seed violation: {r['perm_code']} outside the FOUNDER_WORKFLOW_ONLY role")


# ---------------------------------------------------------------------------
# 0005_audit: backfill CREATE rows for data seeded before audit_log existed
# ---------------------------------------------------------------------------


def backfill_audit(conn, tables: list[str]) -> int:
    now = clock.now()
    tx = new_id()
    count = 0
    for name in tables:
        policy = policy_for(name)
        if not policy or policy.policy != FULL:
            continue
        reflected = sa.Table(name, sa.MetaData(), autoload_with=conn)
        for row in conn.execute(sa.select(reflected)).mappings():
            data = dict(row)
            snap = snapshot(name, data)
            parent = (policy.parent[0], _serialize(data[policy.parent[1]])) if policy.parent else None
            write_audit(
                conn,
                entity_type=name,
                entity_id=_serialize(data["id"]),
                action="CREATE",
                new_value=snap,
                changed_fields=sorted(k for k, v in snap.items() if v is not None),
                parent=parent,
                transaction_id=tx,
                now=now,
            )
            count += 1
    return count


# ---------------------------------------------------------------------------
# 0006_reference: lookups and number sequences (03 §6)
# ---------------------------------------------------------------------------

LOOKUP_CATEGORY = lw(
    "lookup_category",
    code=sa.String(50),
    name=sa.String(100),
    description=sa.String(500),
    module=sa.String(50),
    is_system=sa.Boolean(),
)
LOOKUP_VALUE = lw(
    "lookup_value",
    category_id=GUID(),
    code=sa.String(50),
    label=sa.String(120),
    description=sa.String(500),
    sort_order=sa.Integer(),
    is_active=sa.Boolean(),
    attributes=JSONType(),
)
NUMBER_SEQUENCE = lw(
    "number_sequence",
    sequence_key=sa.String(50),
    prefix=sa.String(20),
    reset_period=sa.String(10),
    current_period=sa.String(10),
    next_value=sa.BigInteger(),
    padding=sa.Integer(),
)

_L = 100_000 * 100  # one lakh rupees in paise

LOOKUPS: tuple[tuple[str, str, str, tuple[tuple[str, str, dict | None], ...]], ...] = (
    (
        "PROJECT_TYPE",
        "Project type",
        "Service required by the enquirer",
        (
            ("FULL_HOME", "Complete Home Interiors", None),
            ("MODULAR_KITCHEN", "Modular Kitchen", None),
            ("BEDROOM_WARDROBE", "Bedrooms & Wardrobes", None),
            ("LIVING_DINING", "Living & Dining", None),
            ("SPACE_PLANNING", "Space Planning & Styling", None),
            ("RENOVATION", "Home Renovation", None),
            ("OTHER", "Other", None),
        ),
    ),
    (
        "PROPERTY_TYPE",
        "Property type",
        "Optional on the public form; enrichable by staff (ADR-005)",
        (
            ("APARTMENT", "Apartment / Flat", None),
            ("INDEPENDENT_HOUSE", "Independent House", None),
            ("VILLA", "Villa", None),
            ("OFFICE", "Office", None),
            ("RETAIL", "Retail / Shop", None),
            ("OTHER", "Other", None),
        ),
    ),
    (
        "BUDGET_RANGE",
        "Budget range",
        "Indicative budget",
        (
            ("UNDER_5L", "Under ₹5 L", {"min_inr_minor": 0, "max_inr_minor": 5 * _L}),
            ("5L_10L", "₹5–10 L", {"min_inr_minor": 5 * _L, "max_inr_minor": 10 * _L}),
            ("10L_20L", "₹10–20 L", {"min_inr_minor": 10 * _L, "max_inr_minor": 20 * _L}),
            ("20L_35L", "₹20–35 L", {"min_inr_minor": 20 * _L, "max_inr_minor": 35 * _L}),
            ("35L_50L", "₹35–50 L", {"min_inr_minor": 35 * _L, "max_inr_minor": 50 * _L}),
            ("ABOVE_50L", "Above ₹50 L", {"min_inr_minor": 50 * _L, "max_inr_minor": None}),
            ("UNDECIDED", "Not decided yet", None),
        ),
    ),
    (
        "LEAD_SOURCE",
        "Lead source",
        "Where the enquiry came from",
        (
            ("WEBSITE", "Website", None),
            ("WHATSAPP", "WhatsApp", None),
            ("PHONE", "Phone", None),
            ("WALK_IN", "Walk-in", None),
            ("REFERRAL", "Referral", None),
            ("INSTAGRAM", "Instagram", None),
            ("FACEBOOK", "Facebook", None),
            ("GOOGLE_ADS", "Google Ads", None),
            ("ARCHITECT_PARTNER", "Architect partner", None),
            ("OTHER", "Other", None),
        ),
    ),
    (
        "LOST_REASON",
        "Lost reason",
        "Why a lead was lost",
        (
            ("BUDGET_MISMATCH", "Budget mismatch", None),
            ("CHOSE_COMPETITOR", "Chose competitor", None),
            ("PROJECT_POSTPONED", "Project postponed", None),
            ("NOT_RESPONSIVE", "Not responsive", None),
            ("OUT_OF_SERVICE_AREA", "Out of service area", None),
            ("SCOPE_TOO_SMALL", "Scope too small", None),
            ("DUPLICATE", "Duplicate", None),
            ("SPAM", "Spam", None),
            ("OTHER", "Other", None),
        ),
    ),
    (
        "ACTIVITY_OUTCOME",
        "Activity outcome",
        "Result of a contact activity",
        (
            ("CONNECTED", "Connected", None),
            ("NO_ANSWER", "No answer", None),
            ("BUSY", "Busy", None),
            ("CALLBACK_REQUESTED", "Callback requested", None),
            ("INTERESTED", "Interested", None),
            ("NOT_INTERESTED", "Not interested", None),
            ("VISIT_SCHEDULED", "Visit scheduled", None),
            ("QUOTE_REQUESTED", "Quote requested", None),
        ),
    ),
)


def seed_reference_data(conn) -> None:
    now = clock.now()
    tx = new_id()
    for code, name, description, values in LOOKUPS:
        category_id = insert_audited(
            conn,
            LOOKUP_CATEGORY,
            {
                "code": code,
                "name": name,
                "description": description,
                "module": "crm",
                "is_system": True,
            },
            transaction_id=tx,
            now=now,
        )
        for order, (vcode, label, attrs) in enumerate(values, start=1):
            insert_audited(
                conn,
                LOOKUP_VALUE,
                {
                    "category_id": category_id,
                    "code": vcode,
                    "label": label,
                    "description": None,
                    "sort_order": order * 10,
                    "is_active": True,
                    "attributes": attrs,
                },
                transaction_id=tx,
                now=now,
            )
    insert_audited(
        conn,
        NUMBER_SEQUENCE,
        {
            "sequence_key": "LEAD",
            "prefix": "VS-L-",
            "reset_period": "YEAR",
            "current_period": None,
            "next_value": 1,
            "padding": 6,
        },
        transaction_id=tx,
        now=now,
    )


# ---------------------------------------------------------------------------
# Immutability guards (07 §6.2)
# ---------------------------------------------------------------------------


def trigger_names(table: str) -> tuple[str, str]:
    return f"trg_{table}__no_update", f"trg_{table}__no_delete"


def create_immutability_guards(conn, table: str) -> None:
    upd, dele = trigger_names(table)
    if dialect_name(conn) == "sqlite":
        conn.exec_driver_sql(
            f"CREATE TRIGGER IF NOT EXISTS {upd} BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'immutable'); END"
        )
        conn.exec_driver_sql(
            f"CREATE TRIGGER IF NOT EXISTS {dele} BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'immutable'); END"
        )
        return
    conn.exec_driver_sql(
        "CREATE OR REPLACE FUNCTION veda_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN IF current_setting('veda.maintenance', true) = 'on' THEN "
        "IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW; END IF; "
        "RAISE EXCEPTION 'immutable' USING ERRCODE = 'restrict_violation'; END $$"
    )
    conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {upd} ON {table}")
    conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {dele} ON {table}")
    conn.exec_driver_sql(
        f"CREATE TRIGGER {upd} BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION veda_immutable_guard()"
    )
    conn.exec_driver_sql(
        f"CREATE TRIGGER {dele} BEFORE DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION veda_immutable_guard()"
    )
    # Role separation when the deployment provisions the roles (07 §6.2).
    # Bandit B608 (SQL built from strings) does not apply: {table} is a fixed evidence-store table name.
    conn.exec_driver_sql(  # nosec B608
        "DO $$ BEGIN "
        f"IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'veda_app') THEN "
        f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM veda_app; GRANT INSERT, SELECT ON {table} TO veda_app; END IF; "
        f"IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'veda_retention') THEN "
        f"GRANT SELECT, DELETE ON {table} TO veda_retention; END IF; END $$"
    )


def drop_immutability_guards(conn, table: str) -> None:
    """Maintenance CLI only (A-02): lifted and restored inside one transaction."""
    upd, dele = trigger_names(table)
    if dialect_name(conn) == "sqlite":
        conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {upd}")
        conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {dele}")
    else:
        conn.exec_driver_sql("SET LOCAL veda.maintenance = 'on'")


def restore_immutability_guards(conn, table: str) -> None:
    if dialect_name(conn) == "sqlite":
        create_immutability_guards(conn, table)
    else:
        conn.exec_driver_sql("SET LOCAL veda.maintenance = 'off'")


def guards_present(conn) -> bool:
    expected = {name for t in IMMUTABLE_TABLES for name in trigger_names(t)}
    if dialect_name(conn) == "sqlite":
        found = {r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'trigger'")}
    else:
        found = {r[0] for r in conn.exec_driver_sql("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")}
    return expected <= found


def registered_full_tables() -> list[str]:
    return [t for t, p in all_policies().items() if p.policy == FULL]
