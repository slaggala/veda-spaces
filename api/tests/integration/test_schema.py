"""Schema, migrations and purge (12 §4.1) and TD-H (FK-less identifier conformance)."""

from dataclasses import replace
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support import pg
from veda.kernel import audit_registry, clock, conformance, db
from veda.kernel.context import actor, system_context
from veda.kernel.ids import new_id

HEAD = "0010_consent_evidence_guard"


def _connect():
    return db.engine().connect()


def test_DATA_011_conformance_passes_on_migrated_schema(app):
    with _connect() as conn:
        report = conformance.check(conn)
    assert report.ok, report.problems


def test_PLAT_013_no_user_table_and_expected_inventory(app):
    with _connect() as conn:
        tables = set(sa.inspect(conn).get_table_names())
    assert "user" not in tables and "app_user" in tables
    assert tables - {"alembic_version"} == set(audit_registry.all_policies())


def test_FKLESS_allow_list_is_exact():
    assert len(audit_registry.FKLESS_IDENTIFIERS) == 10
    assert {f.key for f in audit_registry.FKLESS_IDENTIFIERS} == {
        "audit_log.session_id",
        "security_event_log.session_id",
        "refresh_token.replaced_by_id",
        "audit_log.entity_id",
        "audit_log.parent_entity_id",
        "audit_log.transaction_id",
        "security_event_log.target_entity_id",
        "outbox_event.aggregate_id",
        "notification.entity_id",
        "user_mfa_recovery_code.batch_id",
    }
    assert set(audit_registry.NON_ENTITY_STRING_IDENTIFIERS) == {
        "audit_log.request_id",
        "security_event_log.request_id",
        "outbox_event.locked_by",
    }


def test_exception_registry_unique_indexes_exact(app):
    with _connect() as conn:
        insp = sa.inspect(conn)
        unique_without_predicate = set()
        for table in insp.get_table_names():
            for ix in conformance._indexes(conn, insp, table):
                if ix["unique"] and "is_deleted" not in (ix["where"] or "").lower():
                    unique_without_predicate.add(ix["name"])
    assert unique_without_predicate == set(audit_registry.UNIQUE_INDEX_EXCEPTIONS)


def test_PLAT_005_models_match_migrated_schema(app):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    import veda.models as models

    with _connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": False}), models.metadata)
        insp = sa.inspect(conn)
        db_indexes = {ix["name"] for t in insp.get_table_names() for ix in insp.get_indexes(t)}
    model_indexes = {ix.name for t in models.metadata.tables.values() for ix in t.indexes}
    # Alembic cannot compare expression (DESC) indexes; compare those by name instead.
    relevant = [d for d in diffs if not (isinstance(d, tuple) and d[0] in ("remove_index", "add_index"))]

    def fk_sig(fk):
        return (fk.parent.name, tuple(c.name for c in fk.columns), tuple(e.target_fullname for e in fk.elements))

    # SQLite does not reflect names of column-level FKs added by ALTER TABLE ADD COLUMN (0008); pair them up.
    removed = {fk_sig(d[1]) for d in relevant if d[0] == "remove_fk"}
    added = {fk_sig(d[1]) for d in relevant if d[0] == "add_fk"}
    relevant = [d for d in relevant if not (d[0] in ("remove_fk", "add_fk") and fk_sig(d[1]) in removed & added)]
    assert relevant == [], relevant
    assert db_indexes >= model_indexes, model_indexes - db_indexes


def test_DATA_010_foreign_keys_on_every_connection(app):
    if not db.is_sqlite():
        pytest.skip("SQLite pragma")
    for _ in range(3):
        with _connect() as conn:
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert conn.exec_driver_sql("PRAGMA journal_mode").scalar().lower() == "wal"


def test_AUDIT_004_evidence_stores_reject_update_and_delete(app, api, factory):
    factory.login(api, factory.user("SALES"))  # writes security events
    for table in ("audit_log", "security_event_log"):
        with _connect() as conn:
            row_id = conn.execute(sa.text(f"SELECT id FROM {table} LIMIT 1")).scalar()
            assert row_id is not None
        for statement in (f"UPDATE {table} SET request_id = 'x' WHERE id = :id", f"DELETE FROM {table} WHERE id = :id"):
            with pytest.raises(Exception) as exc:
                with db.engine().begin() as conn:
                    conn.execute(sa.text(statement), {"id": row_id})
            assert "immutable" in str(exc.value).lower()


def test_AUDIT_004_readiness_fails_without_guards(app, client):
    assert client.get("/health/ready").status_code == 200
    from veda.kernel import migration_support

    with db.engine().begin() as conn:
        if db.is_sqlite():
            conn.exec_driver_sql("DROP TRIGGER trg_audit_log__no_update")
        else:
            conn.exec_driver_sql("DROP TRIGGER trg_audit_log__no_update ON audit_log")
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.get_json()["checks"]["immutability_guards"] == "missing"
    with db.engine().begin() as conn:
        migration_support.create_immutability_guards(conn, "audit_log")
    assert client.get("/health/ready").status_code == 200


def test_F12_readiness_ignores_outbox_lag(app, client, api, factory):
    factory.public_lead(api)
    clock.advance(timedelta(hours=3))
    body = client.get("/health/ready").get_json()
    assert body["status"] == "ok" and body["checks"]["outbox_lag_s"] >= 3 * 3600 - 5


def test_DATA_017_purge_ordering_with_foreign_keys_on(app, api, factory, client):
    from veda import config
    from veda.platform import maintenance
    from veda.platform.notifications import worker

    sales = factory.user("SALES")
    factory.login(api, sales)
    api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)  # rotated chain
    api.post("/api/v1/auth/logout", headers=api.csrf_headers())
    founder = factory.user(founder=True)
    factory.login(api, founder)
    factory.public_lead(api)
    worker.drain_all()
    api.post("/api/v1/notifications/read-all")
    cfg = config.settings()
    cfg.user_session_retention_days = cfg.token_retention_days = cfg.outbox_retention_days = 1
    cfg.notification_read_retention_days = cfg.notification_unread_retention_days = 1
    clock.advance(timedelta(days=40))
    result = maintenance.purge()
    assert result["user_session"] >= 1 and result["refresh_token"] >= 2 and result["notification"] >= 1
    assert result["outbox_event"] >= 1
    if db.is_sqlite():
        with _connect() as conn:
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    with _connect() as conn:
        orphans = conn.execute(sa.text("SELECT count(*) FROM security_event_log WHERE session_id IS NOT NULL")).scalar()
    assert orphans > 0, "evidence rows keep their session_id correlation (EXC-009)"


def test_migration_upgrade_with_data(tmp_path, engine):
    """F-19: seed representative data at N-1 (0008), upgrade to head, assert rows and constraints still hold."""
    from alembic import command
    from alembic.config import Config

    from tests.conftest import ROOT

    if engine == "sqlite":
        url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    else:
        name = f"veda_up_{new_id()[-10:]}"
        pg.admin(f"CREATE DATABASE {name}")
        url = pg.url(name)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["skip_logging"] = True
    command.upgrade(cfg, "0008_account_security")
    eng = db.create_engine(url)
    with eng.begin() as conn:
        before = conn.execute(sa.text("SELECT count(*) FROM permission")).scalar()
        users = conn.execute(sa.text("SELECT count(*) FROM app_user")).scalar()
    eng.dispose()
    command.upgrade(cfg, "head")
    eng = db.create_engine(url)
    with eng.begin() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM permission")).scalar() == before
        assert conn.execute(sa.text("SELECT count(*) FROM app_user")).scalar() == users
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == HEAD
        assert conformance.check(conn).ok
    eng.dispose()
    if engine != "sqlite":
        pg.admin(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


def test_RBAC_001_migration_order():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from tests.conftest import ROOT

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    order = [r.revision for r in reversed(list(ScriptDirectory.from_config(cfg).walk_revisions()))]
    assert order == [
        "0001_kernel",
        "0002_identity",
        "0003_rbac",
        "0004_auth",
        "0005_audit",
        "0006_reference",
        "0007_notifications",
        "0008_account_security",
        "0100_crm_leads",
        "0009_mfa_challenge_binding",
        HEAD,
    ]


def test_seed_data(app):
    with _connect() as conn:
        system = conn.execute(
            sa.text("SELECT user_type, created_by FROM app_user WHERE id = '00000000000070008000000000000001'")
        ).one()
        assert system[0] == "SYSTEM" and str(system[1]).replace("-", "") == "00000000000070008000000000000001"
        humans = conn.execute(sa.text("SELECT count(*) FROM app_user WHERE user_type = 'HUMAN'")).scalar()
        assert humans == 0, "no human users in any migration (AUTH-014)"
        cats = conn.execute(sa.text("SELECT count(*) FROM lookup_category")).scalar()
        assert cats == 6
        seeded_audit = conn.execute(
            sa.text("SELECT count(*) FROM audit_log WHERE performed_via = 'MIGRATION'")
        ).scalar()
        assert seeded_audit > 0


# --- TD-H negative fixtures --------------------------------------------------------------------------


def _scratch_schema(mutator, engine, tmp_path):
    """Create a scratch schema from a mutated copy of the metadata and run the conformance check."""
    import veda.models as models

    md = sa.MetaData(naming_convention=models.metadata.naming_convention)
    for table in models.metadata.sorted_tables:
        copy = table.to_metadata(md)
        # to_metadata() does not carry ddl_if(); re-apply the per-dialect conditions.
        originals = {(c.name, str(c.sqltext)): c for c in table.constraints if isinstance(c, sa.CheckConstraint)}
        for c in copy.constraints:
            if isinstance(c, sa.CheckConstraint):
                src = originals.get((c.name, str(c.sqltext)))
                if src is not None and getattr(src, "_ddl_if", None) is not None:
                    c._ddl_if = src._ddl_if
    mutator(md)
    if engine == "sqlite":
        url = f"sqlite:///{tmp_path / f's-{new_id()}.db'}"
        name = None
    else:
        name = f"veda_s_{new_id()[-10:]}"
        pg.admin(f"CREATE DATABASE {name}")
        url = pg.url(name)
    eng = db.create_engine(url)
    try:
        md.create_all(eng)
        with eng.connect() as conn:
            return conformance.check(conn)
    finally:
        eng.dispose()
        if name:
            pg.admin(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


def _add_column(table, column):
    def mutate(md):
        md.tables[table].append_column(column)

    return mutate


def _rebuild_table(table, **overrides):
    """Replace one column definition (type change)."""

    def mutate(md):
        t = md.tables[table]
        for name, new_col in overrides.items():
            old = t.c[name]
            t._columns.remove(old)
            t.append_column(new_col, replace_existing=True)
            for c in list(t.constraints):
                if isinstance(c, sa.CheckConstraint) and c.name and name in (c.name or ""):
                    t.constraints.discard(c)

    return mutate


def _drop_constraint(table, name):
    def mutate(md):
        t = md.tables[table]
        for c in list(t.constraints):
            if c.name == name:
                t.constraints.discard(c)

    return mutate


def test_TD_H1_real_schema_passes(engine, tmp_path):
    report = _scratch_schema(lambda md: None, engine, tmp_path)
    assert report.ok, report.problems


@pytest.mark.parametrize(
    "case",
    [
        "H2",
        "H3",
        "H5",
        "H6",
        "H10",
        "H11a",
        "H11b",
        "missing_version",
        "user_table",
        "float_money",
        "unique_without_predicate",
        "cascade",
    ],
)
def test_TD_H_negative_fixtures_fail(engine, tmp_path, case):
    from veda.kernel.types import GUID, UTCDateTime

    mutators = {
        "H2": _add_column("lead", sa.Column("foo_id", GUID())),
        "H3": _rebuild_table("audit_log", entity_id=sa.Column("entity_id", sa.String(64), nullable=False)),
        "H5": _drop_constraint("audit_log", "ck_audit_log__entity_id_format"),
        "H6": _drop_constraint("security_event_log", "ck_security_event_log__target_pair"),
        "H10": _add_column("lead", sa.Column("foo_id", sa.String(64))),
        "H11a": _rebuild_table("outbox_event", locked_by=sa.Column("locked_by", GUID())),
        "H11b": _rebuild_table("audit_log", request_id=sa.Column("request_id", sa.String(128))),
        "missing_version": _rebuild_table("lead_note", version=sa.Column("version", sa.Integer, nullable=True)),
        "float_money": _add_column("lead", sa.Column("budget_amount", sa.Float)),
        "unique_without_predicate": lambda md: sa.Index("ux_lead__phone_all", md.tables["lead"].c.phone, unique=True),
        "cascade": _add_column(
            "lead_note", sa.Column("extra_id", GUID(), sa.ForeignKey("lead.id", ondelete="CASCADE"))
        ),
    }

    def user_table(md):
        sa.Table("user", md, sa.Column("id", GUID(), primary_key=True), sa.Column("created_on", UTCDateTime()))

    mutators["user_table"] = user_table
    if case == "H5" and engine != "sqlite":
        pytest.skip("format CHECKs are SQLite-only; PostgreSQL's native uuid enforces format (03 §12)")
    report = _scratch_schema(mutators[case], engine, tmp_path)
    assert not report.ok, case


def test_TD_H4_undocumented_registry_entry_fails(engine, tmp_path):
    entry = replace(audit_registry.FKLESS_IDENTIFIERS[8], why_no_fk="")
    import veda.models as models

    with db.create_engine(f"sqlite:///{tmp_path / 'h4.db'}").connect() as conn:
        models.metadata.create_all(conn)
        report = conformance.check(
            conn, fkless=(*audit_registry.FKLESS_IDENTIFIERS[:8], entry, audit_registry.FKLESS_IDENTIFIERS[9])
        )
    assert not report.ok and any("documentation" in p for p in report.problems)


def test_TD_H7_malformed_identifiers_rejected(app):
    from veda.platform.audit.models import AuditLog

    for bad in (
        "0192A4F1C3B27E8D9F10A2B3C4D5E6F7",
        "0192a4f1c3b24e8d9f10a2b3c4d5e6f7",
        "0192a4f1-c3b2-7e8d-9f10-a2b3c4d5e6f7",
    ):
        with pytest.raises((ValueError, sa.exc.StatementError, sa.exc.IntegrityError)):
            with actor(system_context()), db.unit_of_work(write=True) as s:
                row = AuditLog(
                    entity_type="lead",
                    entity_id=bad,
                    action="CREATE",
                    performed_by=system_context().actor_id,
                    performed_on=db.tx_time(s),
                    performed_via="SYSTEM_JOB",
                    transaction_id=new_id(),
                )
                s.add(row)
        if db.is_sqlite():
            with pytest.raises(sa.exc.IntegrityError):
                with db.engine().begin() as conn:
                    conn.exec_driver_sql(
                        "INSERT INTO audit_log (id, created_on, updated_on, created_by, updated_by, is_deleted, version, "
                        "entity_type, entity_id, action, performed_by, performed_on, performed_via, transaction_id, "
                        f"payload_schema) VALUES ('{new_id()}', '2026-09-29T00:00:00.000000Z', '2026-09-29T00:00:00.000000Z', "
                        "'00000000000070008000000000000001', '00000000000070008000000000000001', 0, 1, 'lead', "
                        f"'{bad}', 'CREATE', '00000000000070008000000000000001', '2026-09-29T00:00:00.000000Z', 'SYSTEM_JOB', "
                        f"'{new_id()}', 1)"
                    )
