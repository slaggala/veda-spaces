"""CQX-02 customer-safe projection: frozen content only, allow-listed and classified, refused when tampered.

SYNTHETIC sites, card and policies only. Results are SYNTHETIC_VALIDATED."""

from __future__ import annotations

import json

from tests.support.commercial import install_full_policy
from tests.support.proposal import PROPOSAL_ON, customer, ok, setup, share
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.customer_proposal import projection

pytestmark = PROPOSAL_ON

# Internal commercial mechanics that must never reach a customer (instruction trust principle 6).
INTERNAL = ("rate_card", "rate_minor", "derivation", "provenance", "card basis", "OI-MTQ", "approved_by", "self_limit",
            "margin", "cost_minor", "WARDROBE.BODY", "SYNTHETIC-2", "estimate_line", "boq", "lineage", "threshold",
            "supplier", "procurement", "discount authority", "four_eyes", "rate_status", "tier_code", "formula",
            "measurement", "requirement", "_minor", "snapshot\"")  # fmt: skip


def _classified(path: str) -> bool:
    return path in projection.FIELDS or any(
        k.startswith(path + ".") or k.startswith(path + "[]") for k in projection.FIELDS
    )


def _ids(c, prop, est, q) -> list[str]:
    rows = ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))
    line_ids = [x["id"] for sec in rows["sections"] for x in sec["lines"]]
    return [q["id"], prop["id"], prop["lead_id"], est["id"], est["boq_id"], est["scope_id"], *line_ids]


def test_projection_is_customer_safe_classified_and_identifier_free(api, factory):
    c, prop, est, q = setup(api, factory, "3BHK")
    g = share(c, q)
    r = customer(api, g).get()
    assert r.status == 200
    p = r.data["proposal"]
    text = json.dumps(p)
    for marker in INTERNAL:
        assert marker not in text, marker
    for ident in _ids(c, prop, est, q):
        assert ident not in text  # no raw database identifier anywhere
    lead = ok(c.as_(c.founder).get(f"/api/v1/leads/{prop['lead_id']}"))
    assert lead["name"] not in text  # no customer name: a proposal opens for whoever holds the link
    unclassified = sorted(x for x in projection.paths(p) if not _classified(x))
    assert not unclassified, unclassified
    # room-wise, with stable customer references
    assert p["kind"] == "QUOTATION" and p["quotation_number"] == q["quotation_number"] and p["version_no"] == 1
    assert [r["ref"] for r in p["rooms"]] == [f"R{n}" for n in range(1, len(p["rooms"]) + 1)]
    assert all(x["ref"].startswith("L") for r in p["rooms"] for x in r["lines"])
    assert p["snapshot_sha256"] == ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))["snapshot_sha256"]
    assert p["unit_rates_shown"] is False and '"unit_rate":' not in text
    assert p["summary"]["gst"]["status"] == "Included" and p["summary"]["total"]
    # the staff preview is the same projection
    pv = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{q['id']}/proposal-preview"))
    assert pv["frozen"] is True and pv["proposal"] == p


def test_every_frozen_document_field_is_classified(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    from tests.support import dbh
    from veda.modules.mtq_commercial.models import Quotation

    doc = dbh.get(Quotation, q["id"]).snapshot
    assert set(doc) <= set(projection.DOCUMENT_FIELDS), set(doc) - set(projection.DOCUMENT_FIELDS)
    for sec in doc["sections"]:
        for line in sec["lines"]:
            assert set(line) <= set(projection.LINE_FIELDS), set(line) - set(projection.LINE_FIELDS)
    assert set(doc["summary"]) <= set(projection.SUMMARY_FIELDS)


def test_unit_rates_appear_only_when_the_owner_allows_them(api, factory):
    install_full_policy(OI_MTQ_10={"show_unit_rates": True})
    c, prop, est, q = setup(api, factory, "2BHK", policy=False)
    p = customer(api, share(c, q)).get().data["proposal"]
    assert p["unit_rates_shown"] is True and any("unit_rate" in x for r in p["rooms"] for x in r["lines"])


def test_tampered_document_or_lines_are_refused_and_nothing_is_recorded(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    g = share(c, q)
    from veda.modules.mtq_commercial.models import Quotation

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        row = s.get(Quotation, q["id"])
        row.snapshot = {**row.snapshot, "summary": {**row.snapshot["summary"], "total": "1.00"}}
    r = customer(api, g).get()
    assert r.status == 409 and r.code == "SNAPSHOT_INTEGRITY_FAILED" and "1.00" not in str(r.json)
    r = c.as_(c.estimator).get(f"/api/v1/quotations/{q['id']}/proposal-preview")
    assert r.status == 409
    grants = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/access-grants"))
    assert grants[0]["view_count"] == 0  # a refused view records nothing


def test_a_tampered_quotation_line_is_refused(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    g = share(c, q)
    import sqlalchemy as sa

    from veda.modules.mtq_commercial.models import QuotationLine

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        line = s.execute(sa.select(QuotationLine).where(QuotationLine.quotation_id == q["id"]).limit(1)).scalar_one()
        line.description = "Something else"
    r = customer(api, g).get()
    assert r.status == 409 and r.code == "SNAPSHOT_INTEGRITY_FAILED"


def test_a_draft_preview_is_marked_and_never_reaches_a_customer(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    q2 = ok(c.as_(c.estimator).post(f"/api/v1/quotations/{q['id']}/versions", {"cost_estimate_id": est["id"]},
                                    if_match=ok(c.as_(c.estimator).get(f"/api/v1/quotations/{q['id']}"))["version"]), 201)  # fmt: skip
    pv = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{q2['id']}/proposal-preview"))
    assert pv["frozen"] is False and pv["watermark"].startswith("Preview") and pv["proposal"]["snapshot_sha256"] is None
    assert "draft" not in pv["proposal"]
    r = c.as_(c.designer).get(f"/api/v1/quotations/{q['id']}/proposal-preview")
    assert r.status in (403, 404)  # designers have no preview permission
