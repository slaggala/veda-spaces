"""Seed and release the synthetic catalog slice on a LOCAL database (browser E2E and demos only).

    VEDA_ENV=local VEDA_DATABASE_URL=sqlite:///var/e2e.db .venv/bin/python tools/e2e_catalog.py

Refuses outside local and test. The author is the system user and the reviewer the first Founder in the database,
so four-eyes review holds. Pricing is the SYNTHETIC test card; the soft-close promise gets placeholder role owners
("local demo") so the slice can be released locally. No real person is named, nothing reaches staging or production.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import veda.models  # noqa: E402,F401  (the full schema)
from veda.config import settings  # noqa: E402
from veda.kernel import db  # noqa: E402
from veda.kernel.context import ActorContext, actor, system_context  # noqa: E402
from veda.modules.catalog import migrate_v2, seed, service  # noqa: E402
from veda.modules.catalog.models import CatalogRecord  # noqa: E402
from veda.platform.identity.models import User  # noqa: E402

CARD = Path(__file__).resolve().parents[1] / "tests/fixtures/estimator/synthetic-rate-card.json"
DEMO = {"owner": "Local demo owner (role)", "backup": "Local demo backup (role)", "quotation_mapping": "Hardware line",
        "verification": "Local demo verification", "warranty_source": "Local demo terms",
        "status": "OPERATIONALLY_CONFIRMED", "confirmed_on": "2026-10-09"}  # fmt: skip
CODE = "LOCAL-SLICE"


def main() -> int:
    db.configure(settings().database_url)
    if settings().env not in ("local", "test"):
        print("refused: local and test databases only", file=sys.stderr)
        return 2
    author = system_context("CLI")
    with actor(author), db.unit_of_work(write=True) as s:
        if service.active_release(s) is not None:
            print(json.dumps({"active": service.active_release(s).release_code}))
            return 0
        reviewer = s.execute(sa.select(User.id).where(User.protection_level == "FOUNDER").limit(1)).scalar_one()
        seed.apply(s)
        for kind, key, doc in migrate_v2.records(json.loads(CARD.read_text())):
            if kind == "pricing" and not service.versions(s, kind, key):
                service.create_record(s, kind, key, doc)
        row = service.versions(s, "copy", "copy.soft-close.promise")[-1]
        if row.status == "DRAFT":
            service.update_draft(s, row.id, {**copy.deepcopy(row.document), "governance": DEMO})
        for r in s.execute(sa.select(CatalogRecord).where(CatalogRecord.status == "DRAFT")).scalars().all():
            service.submit(s, r.id)
    with actor(ActorContext(actor_id=reviewer, via="CLI")), db.unit_of_work(write=True) as s:
        for r in s.execute(sa.select(CatalogRecord).where(CatalogRecord.status == "IN_REVIEW")).scalars().all():
            service.approve_record(s, r.id)
    with actor(author), db.unit_of_work(write=True) as s:
        release_id = service.create_release(s, CODE).id
        report = service.validate_release(s, release_id)
        if not report["ok"]:
            print(json.dumps({"ok": False, "errors": report["errors"]}))
            return 3
    with actor(ActorContext(actor_id=reviewer, via="CLI")), db.unit_of_work(write=True) as s:
        service.approve_preview(s, release_id)
    with actor(author), db.unit_of_work(write=True) as s:
        service.submit_release(s, release_id)
    with actor(ActorContext(actor_id=reviewer, via="CLI")), db.unit_of_work(write=True) as s:
        service.approve_release(s, release_id, "Local E2E release of the synthetic slice")
    with actor(author), db.unit_of_work(write=True) as s:
        service.activate_release(s, release_id)
    print(json.dumps({"active": CODE}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
