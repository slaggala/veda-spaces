"""Migration evidence: run from api/ in a clean environment.

    ENGINES=sqlite,postgresql python ../docs/implementation/evidence/migration_evidence.py
PostgreSQL uses VEDA_TEST_DATABASE_URL_PG when set (e.g. a PostgreSQL 16 server), else the embedded server.
"""
import hashlib, json, os, sys, tempfile, uuid
from pathlib import Path
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

sys.path.insert(0, ".")
from tests.support import pg
from veda.kernel import conformance, db, migration_support

ROOT = Path(".").resolve()

def cfg(url):
    c = Config(str(ROOT / "alembic.ini")); c.set_main_option("script_location", str(ROOT / "migrations"))
    c.attributes["url"] = url; c.attributes["skip_logging"] = True; return c

def fresh(engine):
    if engine == "sqlite":
        return f"sqlite:///{tempfile.mkdtemp()}/m.db"
    name = f"veda_mig_{uuid.uuid4().hex[:8]}"; pg.admin(f"CREATE DATABASE {name}"); return pg.url(name)

def seed_fingerprint(conn):
    q = {"roles": "SELECT code, grant_path, mfa_required, is_assignable FROM role ORDER BY code",
         "permissions": "SELECT code, sensitivity_class, grant_path, supports_scope FROM permission ORDER BY code",
         "matrix": "SELECT r.code, p.code, rp.scope FROM role_permission rp JOIN role r ON r.id=rp.role_id JOIN permission p ON p.id=rp.permission_id ORDER BY 1,2",
         "lookups": "SELECT c.code, v.code, v.label, v.sort_order FROM lookup_value v JOIN lookup_category c ON c.id=v.category_id ORDER BY 1,2",
         "system_users": "SELECT id, user_type, email FROM app_user ORDER BY id",
         "sequence": "SELECT sequence_key, prefix, reset_period, next_value, padding FROM number_sequence"}
    data = {k: [[str(x).replace('-', '') if 'id' == k else str(x) for x in r] for r in conn.execute(sa.text(v))] for k, v in q.items()}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(), {k: len(v) for k, v in data.items()}

scripts = ScriptDirectory.from_config(cfg("sqlite://"))
out = {"alembic_heads": scripts.get_heads(),
       "revision_order": [r.revision for r in reversed(list(scripts.walk_revisions()))]}
for engine in [e for e in os.environ.get("ENGINES", "sqlite,postgresql").split(",") if e]:
    r = {}
    url = fresh(engine); c = cfg(url)
    command.upgrade(c, "head")
    eng = db.create_engine(url)
    with eng.connect() as conn:
        insp = sa.inspect(conn)
        tables = sorted(t for t in insp.get_table_names() if t != "alembic_version")
        r["server_version"] = (conn.execute(sa.text("SHOW server_version")).scalar() if engine == "postgresql"
                               else "SQLite " + conn.execute(sa.text("SELECT sqlite_version()")).scalar())
        r["version"] = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        r["tables"] = len(tables)
        r["columns"] = sum(len(insp.get_columns(t)) for t in tables)
        r["mfa_challenge_binding_columns"] = sorted({"factor_id", "enrollment_path"} & {x["name"] for x in insp.get_columns("mfa_challenge")})
        r["indexes"] = sum(len(insp.get_indexes(t)) for t in tables)
        r["foreign_keys"] = sum(len(insp.get_foreign_keys(t)) for t in tables)
        r["check_constraints"] = sum(len(conformance._check_names(conn, insp, t)) for t in tables)
        rep = conformance.check(conn); r["conformance_ok"] = rep.ok; r["conformance_problems"] = rep.problems
        r["audit_columns_on_every_table"] = all({"id","created_on","updated_on","created_by","updated_by","is_deleted","deleted_on","deleted_by","version"} <= {x["name"] for x in insp.get_columns(t)} for t in tables)
        r["immutability_guards"] = migration_support.guards_present(conn)
        r["human_users"] = conn.execute(sa.text("SELECT count(*) FROM app_user WHERE user_type='HUMAN'")).scalar()
        r["password_hashes"] = conn.execute(sa.text("SELECT count(*) FROM user_credential WHERE password_hash IS NOT NULL")).scalar()
        fp1, counts = seed_fingerprint(conn); r["seed_counts"] = counts
        try:
            conn.execute(sa.text("INSERT INTO lookup_category (id, created_on, updated_on, created_by, updated_by, is_deleted, version, code, name, module, is_system) VALUES ('0192a4f1c3b24e8d9f10a2b3c4d5e6f7', '2026-09-29T00:00:00.000000Z', '2026-09-29T00:00:00.000000Z', '00000000000070008000000000000001', '00000000000070008000000000000001', false, 1, 'X', 'X', 'x', true)" if engine=="sqlite" else "SELECT 1"))
            r["raw_uuidv4_insert_rejected_by_db"] = False if engine == "sqlite" else "n/a (native uuid; version nibble validated by the kernel GUID type on bind)"
        except Exception:
            r["raw_uuidv4_insert_rejected_by_db"] = True
            conn.rollback()
    eng.dispose()
    try:
        command.downgrade(c, "-1"); r["downgrade_-1"] = "succeeded (unexpected)"
    except NotImplementedError as exc:
        r["downgrade_-1"] = f"refused: NotImplementedError({exc}) — expand-only policy, 02 §12.4"
    eng = db.create_engine(url)
    with eng.connect() as conn:
        r["version_after_refused_downgrade"] = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        r["binding_columns_after_refused_downgrade"] = sorted({"factor_id", "enrollment_path"} & {x["name"] for x in sa.inspect(conn).get_columns("mfa_challenge")})
    eng.dispose()
    command.upgrade(c, "head")
    eng = db.create_engine(url)
    with eng.connect() as conn:
        r["version_after_downgrade_attempt_and_reupgrade"] = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    eng.dispose()
    url2 = fresh(engine); command.upgrade(cfg(url2), "head")
    eng = db.create_engine(url2)
    with eng.connect() as conn:
        fp2, _ = seed_fingerprint(conn)
    eng.dispose()
    r["seed_deterministic_across_fresh_databases"] = fp1 == fp2
    out[engine] = r
print(json.dumps(out, indent=2))
