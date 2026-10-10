"""V2/V3 equivalence and the vertical slice on the owner's private rate card (remediation H3).

The card is never committed. These tests run only when VEDA_PRIVATE_CARD names it, outside the repository, and are
skipped everywhere else, including CI. They assert equality and print no amount.

    VEDA_PRIVATE_CARD=~/veda-private/.../rate-card-essential-2026-10-draft-4.json \\
    VEDA_PRIVATE_CARD_SHA256=2c7b503c... pytest tests/integration/test_catalog_real_card.py
"""

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from tests.integration.test_catalog import (
    CLIENT,
    STATES,
    approve_all,
    new_key,
    release,
    tx,
    v2_selections,
    v3_configuration,
)
from tests.support.dbh import rows
from veda.kernel import db
from veda.modules.catalog import compile as catalog_compile
from veda.modules.catalog import migrate_v2, seed, service
from veda.modules.catalog.models import CatalogConfiguration, CatalogRelease
from veda.modules.estimator import engine

REPO = Path(__file__).resolve().parents[3]
CARD_PATH = os.environ.get("VEDA_PRIVATE_CARD")
pytestmark = pytest.mark.skipif(
    not CARD_PATH, reason="local only: set VEDA_PRIVATE_CARD to the owner's private card (never committed)"
)


def card() -> dict:
    path = Path(CARD_PATH or "").expanduser().resolve()
    assert REPO not in path.parents, "the private card must stay outside the repository"
    raw = path.read_bytes()
    expected = os.environ.get("VEDA_PRIVATE_CARD_SHA256")
    doc = json.loads(raw)
    if expected:
        canonical = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert canonical == expected, "not the expected card"
    return doc


def test_real_card_round_trips_and_every_v2_request_matches():
    document = card()
    recs = migrate_v2.records(document)
    cat = catalog_compile.load([SimpleNamespace(kind=k, record_key=key, record_version=1, document=d)
                                for k, key, d in recs], "REAL-EQUIVALENCE", "0" * 64)  # fmt: skip
    compiled = catalog_compile.card_document(cat)
    assert service.sha({**compiled, "version": "x"}) == service.sha({**document, "version": "x"}), "same card"
    real = catalog_compile.compile_card(cat)
    bundle = migrate_v2.bundles()
    for state in STATES:
        v2 = engine.EstimateRequest.model_validate({"property_type": "APARTMENT", "home_size": "3BHK",
                                                    "project_kind": "NEW_HOME", "package": "ESSENTIAL",
                                                    "selections": v2_selections(bundle, state)})  # fmt: skip
        v3 = catalog_compile.resolve(cat, v3_configuration(bundle, state)).request
        assert v3.model_dump(mode="json") == v2.model_dump(mode="json")
        a = engine.calculate(real, v2).staff_view()
        b = engine.calculate(real, v3).staff_view()
        for field in ("range", "gst", "project_preparation", "custom_features_allowance", "timeline", "rooms"):
            assert a[field] == b[field], field


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


@pytest.mark.settings(catalog_estimator_enabled=True)
def test_corrected_slice_on_the_real_card(api, people):
    a, b = people
    document = card()

    def run(s):
        seed.apply(s)
        for kind, key, doc in migrate_v2.records(document):
            if kind == "pricing":
                service.create_record(s, kind, key, doc)

    tx(a, run)
    approve_all(a, b)
    rel = release(a, b, "REAL-SLICE")

    def post(config):
        return api.post("/api/v1/public/catalog/estimates", {"configuration": config, "turnstile_token": "ok"},
                        anonymous=True, headers={"Origin": "http://localhost:8000", "Idempotency-Key": new_key(), "X-Veda-Client": CLIENT})  # fmt: skip

    base = {"home": "slice.apartment-3bhk", "package": "slice.essential", "rooms": [{"room": "living-room"}]}
    laminate = post(base)
    wall = post({**base, "rooms": [{"room": "living-room", "extras": {"feature-wall": {}}}]})
    veneer = post(
        {**base, "rooms": [{"room": "living-room", "products": {"tv-unit": {"options": {"panel-finish": "veneer"}}}}]}
    )
    soft = post({**base, "rooms": [{"room": "living-room", "extras": {"tv-soft-close-storage": {}}}]})
    assert laminate.status == 201 and wall.status == 201
    assert wall.json["data"]["range"]["low_minor"] > laminate.json["data"]["range"]["low_minor"]
    assert veneer.status == 422 and veneer.json["errors"][0]["code"] == "CONSULTATION_REQUIRED", "veneer never priced"
    assert soft.status == 422, "soft-close storage stays blocked"
    snap = rows(sa.select(CatalogConfiguration))[0]
    with db.unit_of_work(write=False) as s:
        cat = catalog_compile.load_release(s, s.get(CatalogRelease, rel))
        again = catalog_compile.resolve(cat, snap.selections)
    assert again.request.model_dump(mode="json") == snap.resolved_request, "the snapshot reproduces exactly"
