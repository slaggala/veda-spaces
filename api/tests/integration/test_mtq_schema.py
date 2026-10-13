"""MTQ B1-T03: migration 0200_mtq_site (B1-SCOPE §2, §4; blocker closure §4).

Additive only, both engines: nine tables with the contract, the frozen vocabularies as CHECKs and lookups, the two
sequences, the DESIGNER and SURVEYOR roles with their grants, and the same end state whether the database is fresh or
upgraded from the revision before ATT (0105, what staging runs today)."""

from __future__ import annotations

import importlib.util

import pytest
import sqlalchemy as sa

from tests.support import pg
from veda.kernel import conformance, db
from veda.kernel.ids import new_id
from veda.modules.mtq import vocab
from veda.modules.mtq.models import TABLES

ROOT_MIGRATION = "migrations/versions/0200_mtq_site.py"


def _migration_module():
    from tests.conftest import ROOT

    spec = importlib.util.spec_from_file_location("m0200", ROOT / ROOT_MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_frozen_seed_copy_equals_the_vocabulary():
    """The migration carries its own copy of the seed (migrations never import live vocabularies)."""
    assert _migration_module().LOOKUPS == vocab.LOOKUPS


def test_reserved_revisions_are_untouched():
    from tests.conftest import ROOT

    names = {p.name for p in (ROOT / "migrations/versions").glob("*.py")}
    for reserved in ("0201", "0202", "0203"):
        assert not any(n.startswith(reserved) for n in names), reserved
    assert "0200_mtq_site.py" in names and "0106_attachment.py" in names


def test_wall_tag_vocabulary_is_the_frozen_seventeen():
    assert len(vocab.WALL_TAGS) == 17 and len(set(vocab.WALL_TAGS)) == 17
    assert vocab.BEDROOM_TYPES == ("MASTER_BEDROOM", "BEDROOM", "CHILDREN_BEDROOM", "GUEST_BEDROOM", "PARENTS_BEDROOM")
    assert "SERVANT_ROOM" not in vocab.BEDROOM_TYPES and "STUDY" not in vocab.BEDROOM_TYPES


def _state(conn) -> dict:
    roles = dict(conn.execute(sa.text("SELECT code, mfa_required FROM role WHERE is_deleted = :f"), {"f": False}).all())
    grants = set(
        conn.execute(
            sa.text(
                "SELECT r.code, p.code, rp.scope FROM role_permission rp JOIN role r ON r.id = rp.role_id "
                "JOIN permission p ON p.id = rp.permission_id WHERE rp.is_deleted = :f"
            ),
            {"f": False},
        ).all()
    )
    lookups = set(
        conn.execute(
            sa.text(
                "SELECT c.code, v.code FROM lookup_value v JOIN lookup_category c ON c.id = v.category_id "
                "WHERE c.module IN ('mtq', 'attachments')"
            )
        ).all()
    )
    sequences = set(conn.execute(sa.text("SELECT sequence_key, prefix FROM number_sequence")).all())
    return {"roles": roles, "grants": grants, "lookups": lookups, "sequences": sequences}


def test_tables_lookups_sequences_and_roles_exist(app):
    with db.engine().connect() as conn:
        tables = set(sa.inspect(conn).get_table_names())
        assert set(TABLES) <= tables
        state = _state(conn)
    assert {("PROPERTY", "VS-P-"), ("MEASUREMENT", "VS-M-")} <= state["sequences"]
    assert {"DESIGNER", "SURVEYOR"} <= set(state["roles"])
    assert not any(state["roles"][r] for r in ("DESIGNER", "SURVEYOR"))  # no MFA requirement (mobile capture)
    expected = {(cat, code) for cat, _, _, values in vocab.LOOKUPS for code, _, _ in values}
    assert expected <= state["lookups"]
    from veda.platform.rbac.registry import MATRIX, matrix_scope

    for code, grants in MATRIX.items():
        if code.startswith(("property.", "measurement.", "attachment.")):
            for role, symbol in grants.items():
                assert (role, code, matrix_scope(symbol)) in state["grants"], (role, code)
    assert ("SURVEYOR", "measurement.verify") not in {(r, c) for r, c, _ in state["grants"]}
    assert ("SALES", "measurement.capture") not in {(r, c) for r, c, _ in state["grants"]}


def test_upgrade_from_0105_reaches_the_fresh_state(tmp_path, engine, app):
    """Staging runs 0105 today: 0106 then 0200 must leave the same roles, grants, lookups and sequences as a fresh
    database, with the conformance check clean and existing rows untouched."""
    from alembic import command
    from alembic.config import Config

    from tests.conftest import ROOT

    with db.engine().connect() as conn:
        fresh = _state(conn)
    if engine == "sqlite":
        url = f"sqlite:///{tmp_path / 'from0105.db'}"
    else:
        name = f"veda_up_{new_id()[-10:]}"
        pg.admin(f"CREATE DATABASE {name}")
        url = pg.url(name)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["skip_logging"] = True
    try:
        command.upgrade(cfg, "0105_catalog_claim_control")
        eng = db.create_engine(url)
        with eng.begin() as conn:
            # What 0105 looks like on a database seeded before MTQ existed: drop the two roles 0003 seeded from the
            # live registry, as an older image's 0003 would never have created them.
            for code in ("DESIGNER", "SURVEYOR"):
                rid = conn.execute(sa.text("SELECT id FROM role WHERE code = :c"), {"c": code}).scalar()
                conn.execute(sa.text("DELETE FROM role_permission WHERE role_id = :r"), {"r": rid})
                conn.execute(sa.text("DELETE FROM role WHERE id = :r"), {"r": rid})
            users_before = conn.execute(sa.text("SELECT count(*) FROM app_user")).scalar()
            leads_before = conn.execute(sa.text("SELECT count(*) FROM lead")).scalar()
        eng.dispose()
        command.upgrade(cfg, "head")
        eng = db.create_engine(url)
        with eng.begin() as conn:
            upgraded = _state(conn)
            assert conn.execute(sa.text("SELECT count(*) FROM app_user")).scalar() == users_before
            assert conn.execute(sa.text("SELECT count(*) FROM lead")).scalar() == leads_before
            report = conformance.check(conn)
            assert report.ok, report.problems
        eng.dispose()
        assert upgraded["roles"] == fresh["roles"]
        assert upgraded["grants"] == fresh["grants"]
        assert upgraded["lookups"] == fresh["lookups"]
        assert upgraded["sequences"] == fresh["sequences"]
        # Idempotent: a second run of the seed helpers inserts nothing.
        mod = _migration_module()
        from veda.kernel import migration_support as ms

        eng = db.create_engine(url)
        with eng.begin() as conn:
            assert ms.seed_lookups(conn, mod.LOOKUPS, module="mtq") == 0
            assert ms.seed_missing_roles(conn, mod.ROLES, audit=False) == []
            assert all(not ms.seed_sequence(conn, k, p) for k, p in mod.SEQUENCES)
        eng.dispose()
    finally:
        if engine != "sqlite":
            db.dispose()
            pg.admin(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


@pytest.mark.parametrize(
    ("table", "column", "bad"),
    [
        ("property", "property_type_code", "VILLA"),  # deferred from B1
        ("property", "usage_code", "COMMERCIAL"),
        ("property_space", "space_type_code", "CABIN"),  # commercial space types are not seeded in B1
        ("space_wall", "wall_type_code", "CURTAIN"),
        ("space_opening", "opening_type_code", "SKYLIGHT"),
        ("space_electrical_point", "point_type_code", "SOLAR"),
    ],
)
def test_vocabulary_checks_refuse_values_outside_b1(app, table, column, bad):
    """The CHECK constraints carry the frozen B1 lists (widened only by a later migration)."""
    import veda.models as models

    t = models.metadata.tables[table]
    names = {c.name for c in t.constraints}
    assert f"ck_{table}__{column}" in names
    check = next(c for c in t.constraints if c.name == f"ck_{table}__{column}")
    assert f"'{bad}'" not in str(check.sqltext)


def test_no_existing_table_is_altered():
    """0106 and 0200 create tables only, 0204 grants rows only: no ALTER of an existing table, no data change outside
    seeds."""
    from tests.conftest import ROOT

    for path in (
        "migrations/versions/0106_attachment.py",
        ROOT_MIGRATION,
        "migrations/versions/0204_mtq_self_service.py",
    ):
        text = (ROOT / path).read_text()
        for forbidden in ("op.alter_column", "op.add_column", "op.drop_", "batch_alter_table", "op.execute("):
            assert forbidden not in text, (path, forbidden)


def test_lead_erasure_removes_site_pii_from_rows_and_audit(api, factory):
    """07 §8.2 for MTQ: address, coordinates, visit contact and notes go; measurements stay; audit payloads of rows
    whose parent is a property or a set are rewritten too."""
    import json
    from datetime import timedelta

    from veda.kernel import clock, outbox
    from veda.kernel.context import actor, system_context
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead
    from veda.modules.mtq.models import MeasurementNote, MeasurementSet, MeasurementVisit, Property, PropertySpace
    from veda.platform import maintenance
    from veda.platform.audit.models import AuditLog

    founder = factory.user(founder=True)
    factory.login(api, founder)
    lead_id = api.post("/api/v1/leads", {"name": "Asha Rao", "phone": "+91 90000 11111", "source_code": "PHONE"}).data[
        "id"
    ]
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        now = db.tx_time(s)
        prop = Property(property_number="VS-P-T1", lead_id=lead_id, property_type_code="APARTMENT",
                        project_kind_code="NEW", address_line_1="Flat 402, Lotus Towers", pincode="500081",
                        geo_lat_e6=17_440_000, geo_lng_e6=78_380_000, notes="Gate code QX-PLUM")  # fmt: skip
        s.add(prop)
        s.flush()
        space = PropertySpace(property_id=prop.id, space_type_code="KITCHEN", label="Kitchen", sort_order=10)
        visit = MeasurementVisit(visit_number="VS-M-T1", property_id=prop.id, lead_id=lead_id, survey_level_code="FULL",
                                 status_changed_on=now, customer_contact_name="Asha Rao",
                                 customer_contact_phone="+919000011111", access_notes="Call Asha at the gate")  # fmt: skip
        s.add_all([space, visit])
        s.flush()
        mset = MeasurementSet(property_id=prop.id, measurement_visit_id=visit.id, revision_no=1, survey_level_code="FULL",
                              method_code="LASER", unit_system_code="MM", captured_by=founder.id,
                              property_capture={"main_door_width_mm": 1000, "access_notes": "Asha's mother is home"})  # fmt: skip
        s.add(mset)
        s.flush()
        s.add(MeasurementNote(measurement_set_id=mset.id, space_id=space.id, note_type_code="CUSTOMER_REQUEST",
                              body="Asha wants the fridge on the left"))  # fmt: skip
        prop_id, visit_id, set_id = prop.id, visit.id, mset.id
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead = s.get(Lead, lead_id)
        lead_service.anonymize(s, lead, legal_basis="TEST", request_ref=None)
        outbox.enqueue(s, "lead.erasure_requested", "lead", lead.id, lead_id=lead.id)
    clock.advance(timedelta(seconds=1))
    assert maintenance.run_erasure_audit() >= 1
    with db.unit_of_work(write=False) as s:
        prop = s.get(Property, prop_id)
        assert prop.address_line_1 is None and prop.geo_lat_e6 is None and prop.notes is None
        assert prop.property_type_code == "APARTMENT"  # the building facts stay
        visit = s.get(MeasurementVisit, visit_id)
        assert (
            visit.customer_contact_name is None and visit.customer_contact_phone is None and visit.access_notes is None
        )
        mset = s.get(MeasurementSet, set_id)
        assert mset.property_capture == {"main_door_width_mm": 1000, "access_notes": "[erased]"}
        note = s.execute(sa.select(MeasurementNote).where(MeasurementNote.measurement_set_id == set_id)).scalar_one()
        assert note.body == "[erased]"
        payloads = s.execute(sa.select(AuditLog.old_value, AuditLog.new_value)).all()
    blob = json.dumps([list(p) for p in payloads], default=str)
    for secret in ("Lotus Towers", "QX-PLUM", "Asha", "+919000011111", "fridge on the left", "mother is home"):
        assert secret not in blob, secret
    with db.unit_of_work(write=False) as s:
        for old, new in s.execute(
            sa.select(AuditLog.old_value, AuditLog.new_value).where(AuditLog.entity_id == prop_id)
        ).all():
            for payload in (old or {}, new or {}):
                assert payload.get("geo_lat_e6") in (None, "[ERASED]") and payload.get("pincode") in (None, "[ERASED]")
