"""V3 remediation A3: isolation. V3 is off by default, production refuses it, migration 0103 only adds, and the V1/V2
estimator code is untouched apart from refusing to activate a compiled catalog card."""

import ast
from pathlib import Path

from veda import config

API = Path(__file__).resolve().parents[2]
MIGRATION = API / "migrations/versions/0103_catalog.py"
MIGRATION_0104 = API / "migrations/versions/0104_catalog_idempotency.py"


def test_every_v3_switch_defaults_off():
    s = config.Settings(env="test", database_url="sqlite://")
    assert not s.catalog_estimator_enabled and not s.catalog_admin_enabled
    assert not s.catalog_media_delivery_enabled and not s.catalog_3d_enabled and not s.catalog_analytics_enabled
    assert not s.estimator_enabled, "public V1/V2 intake stays off by default too"
    assert s.catalog_four_eyes and s.catalog_media_backend == "local" and s.catalog_media_scanner == "none"


def test_migration_0103_only_adds_tables_and_indexes():
    tree = ast.parse(MIGRATION.read_text())
    calls = {
        f"{n.func.value.id}.{n.func.attr}"
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "op"
    }  # fmt: skip
    assert calls == {"op.create_table", "op.create_index"}, calls
    source = MIGRATION.read_text()
    assert 'down_revision = "0102_estimator_spec"' in source
    for existing in ("budget_estimate", "estimator_rate_card", "lead", "app_user"):
        assert f'op.create_table(\n        "{existing}"' not in source


def test_the_only_estimator_change_is_the_catalog_card_guard():
    """Every function of the estimator service keeps its V2 shape; activate_card gains one refusal."""
    source = (API / "veda/modules/estimator/service.py").read_text()
    assert source.count("CATALOG-") == 1 and "compiled catalog card" in source
    engine = (API / "veda/modules/estimator/engine.py").read_text()
    assert "catalog" not in engine.lower(), "the pricing engine knows nothing about the catalog"


def test_migration_0104_only_adds_nullable_columns_and_an_index():
    source = MIGRATION_0104.read_text()
    assert 'down_revision = "0103_catalog"' in source
    for forbidden in ("drop_", "alter_column", "DROP ", "UPDATE ", "DELETE "):
        assert forbidden not in source, forbidden
    assert source.count("ADD COLUMN") == 2 and "nullable=True" in source and "op.create_index(" in source


def test_migration_0105_only_adds_the_claim_control_table():
    source = (API / "migrations/versions/0105_catalog_claim_control.py").read_text()
    assert 'down_revision = "0104_catalog_idempotency"' in source
    tree = ast.parse(source)
    calls = {
        f"{n.func.value.id}.{n.func.attr}"
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "op"
    }  # fmt: skip
    assert calls == {"op.create_table", "op.create_index"}, calls
    assert source.count("op.create_table(") == 1 and '"catalog_claim_control"' in source
    for forbidden in ("drop_", "alter_column", "DROP ", "UPDATE ", "DELETE "):
        assert forbidden not in source, forbidden
