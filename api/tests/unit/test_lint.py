"""Static conformance lints (12 §4.4 Lint, §4.11): role literals, route declarations,
module boundaries, raw SQL and bulk mutations, secret scanning."""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "veda"
SEED_FILES = {"veda/platform/rbac/registry.py", "veda/modules/crm/leads/permissions.py", "veda/kernel/migration_support.py"}
DATA_ATTRIBUTE_CONTEXT = ("protection_level", "PROTECTION_LEVELS", "action_class", "APPROVAL_CLASSES")


def python_files():
    return [p for p in APP.rglob("*.py") if "__pycache__" not in p.parts]


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def test_RBAC_002_no_role_code_literals_outside_seed_files():
    offenders = []
    for path in python_files():
        if rel(path) in SEED_FILES:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            for code in ("ADMIN", "SALES", "FOUNDER"):
                if f'"{code}"' in line or f"'{code}'" in line:
                    if code == "FOUNDER" and any(ctx in line for ctx in DATA_ATTRIBUTE_CONTEXT):
                        continue  # Founder *protection* is a data attribute, not a role check (06 §2)
                    offenders.append(f"{rel(path)}:{lineno}: {line.strip()}")
    assert offenders == [], "\n".join(offenders)


def test_no_role_code_comparisons_anywhere():
    for path in python_files():
        text = path.read_text()
        assert not re.search(r"Role\.code\s*==\s*[\"']", text) or rel(path) in SEED_FILES | {"veda/cli/main.py"}, rel(path)


def test_RBAC_012_every_route_declares_a_permission_or_rbx(app):
    from veda.kernel import http

    undeclared = [s.endpoint for s in http.ROUTES if not s.declared]
    assert undeclared == []
    public = {s.rule for s in http.ROUTES if s.auth == "public"}
    assert all(s.rbx for s in http.ROUTES if s.auth == "public"), "public routes are in the RBX register"
    assert "/api/v1/public/leads" in public


def test_startup_fails_for_undeclared_route(app):
    from veda.app import check_route_declarations

    @app.route("/api/v1/sneaky")
    def sneaky():
        return "x"

    with pytest.raises(RuntimeError, match="no permission or RBX declaration"):
        check_route_declarations(app)


def test_PLAT_011_module_boundaries():
    """Modules import other modules' service interfaces only; the platform never imports module
    internals except the maintenance CLI jobs and the app factory's registration."""
    allowed_platform = {"veda/platform/maintenance.py", "veda/platform/rbac/registry.py"}
    for path in python_files():
        r = rel(path)
        if not r.startswith("veda/platform/") and not r.startswith("veda/kernel/"):
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            for name in names:
                if name.startswith("veda.modules"):
                    assert r in allowed_platform, f"{r} imports {name}"
                    if r == "veda/platform/rbac/registry.py":
                        assert name == "veda.modules.crm.leads", "only the module's permission registry"


def test_no_raw_sql_or_bulk_mutation_in_services():
    allowed = {"veda/kernel/migration_support.py", "veda/platform/maintenance.py", "veda/kernel/db.py",
               "veda/platform/health.py", "veda/kernel/conformance.py", "veda/kernel/sequences.py"}
    pattern = re.compile(r"exec_driver_sql|sa\.update\(|sa\.delete\(|\.update\(\)\.where|\.delete\(\)\.where|"
                         r"sa\.text\(\"(?:SELECT|UPDATE|DELETE|INSERT)")
    offenders = []
    for path in python_files():
        if rel(path) in allowed or "/models.py" in rel(path):
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if pattern.search(line) and "pg_advisory_xact_lock" not in line:
                offenders.append(f"{rel(path)}:{lineno}")
    assert offenders == [], offenders


def test_PLAT_008_no_secrets_committed():
    suspicious = re.compile(r"(AKIA[0-9A-Z]{16}|-----BEGIN (?:EC |RSA )?PRIVATE KEY-----|xox[bp]-[0-9A-Za-z-]+)")
    for path in list(APP.rglob("*")) + [ROOT / "alembic.ini", ROOT / "deploy" / "gunicorn.conf.py"]:
        if path.is_file() and path.suffix in (".py", ".ini", ".jinja", ".yml", ".txt", ""):
            assert not suspicious.search(path.read_text(errors="ignore")), rel(path)


def test_OPS_010_single_worker_deployment():
    conf = (ROOT / "deploy" / "gunicorn.conf.py").read_text()
    assert "workers = 1" in conf and 'worker_class = "gthread"' in conf
