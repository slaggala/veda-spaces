"""PR #91 certification remediation: the effective accepted baseline (merge blocker 6), reproducible and tamper-proof
issued documents, lead erasure of frozen documents and events, and the internal lineage permission (pre-enablement
corrections A-C). SYNTHETIC sites, card and policy only."""

from __future__ import annotations

import sqlalchemy as sa

from tests.support.commercial import ALL_ON, Commercial, approved_estimate, install_full_policy, load_card, ok, step
from veda.kernel import db
from veda.kernel.context import actor, system_context

pytestmark = ALL_ON


def _issued(c: Commercial, key: str = "2BHK", *, optional: str = "EXCLUDED", body: dict | None = None):
    prop, est = approved_estimate(c, key, optional=optional)
    q = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", body or {}), 201)
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    return prop, est, ok(step(c, q, "issue", c.manager))


def _reprice(c: Commercial, prop: dict, edit=None) -> dict:
    """A new scope revision (optionally edited), BOQ, review and approved estimate."""
    scope = c.fill_staff_inputs(c.draft_scope(prop))
    if edit:
        edit(scope)
    boq = ok(c.review(c.boq(c.confirm(scope))))
    est = ok(c.as_(c.estimator).post(f"/api/v1/boqs/{boq['id']}/cost-estimates", {"tier_code": "ESSENTIAL"}), 201)
    return ok(c.as_(c.manager).post(f"/api/v1/cost-estimates/{est['id']}/approve", if_match=est["version"]))


def _lines(q: dict) -> list[dict]:
    return [x for sec in q["sections"] for x in sec["lines"]]


# --- merge blocker 6: optional items chosen at acceptance -----------------------------------------------------------
def test_optional_item_chosen_at_acceptance_is_part_of_the_baseline(api, factory):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    prop, _, q = _issued(c, optional="ACCEPTED")
    chosen = next(x for x in _lines(q) if x["is_optional"] and x["is_priced"] and ":CEILING_PROFILE_LIGHTING:PROFILE"
                  in x["line_key"])  # fmt: skip
    issued_sha = q["snapshot_sha256"]
    q = ok(step(c, q, "decision", c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY",
                                            "selected_optional_line_ids": [chosen["id"]]}))  # fmt: skip
    assert q["snapshot_sha256"] == issued_sha  # the issued document is never changed
    assert len(q["decision"]["accepted_baseline_sha256"]) == 64 and q["decision"]["accepted_baseline_lines"] > 0
    key = chosen["line_key"]
    requirement_id = key.split(":")[0]

    # 1. the chosen item is kept unchanged (still offered as optional in the new estimate): no ADD, no change
    v = ok(c.as_(c.sales).post(f"/api/v1/quotations/{q['id']}/variations",
                               {"cost_estimate_id": _reprice(c, prop)["id"]}), 201)  # fmt: skip
    assert key not in {x["line_key"] for x in _lines(v)}
    assert v["base_total_minor"] == 0

    # 2. its quantity changes: a quantity delta only
    def longer(scope):
        item = next(i for i in scope["items"] if i["requirement_id"] == requirement_id)
        cur = ok(c.as_(c.estimator).get(f"/api/v1/scopes/{scope['id']}"))
        it = next(i for i in cur["items"] if i["id"] == item["id"])
        ok(c.as_(c.estimator).patch(f"/api/v1/scope-items/{item['id']}", {"dimension_overrides": {
            **it["dimension_overrides"], "LENGTH": 80}, "override_reason": "longer profile run (synthetic)"},
            if_match=it["version"]))  # fmt: skip

    v2 = ok(step(c, v, "versions", c.estimator, {"cost_estimate_id": _reprice(c, prop, longer)["id"]}, code=201))
    mine = [x for x in _lines(v2) if x["line_key"] == key]
    assert [x["change_code"] for x in mine] == ["CHANGE_QUANTITY"]
    assert mine[0]["baseline_amount_minor"] == chosen["amount_minor"] - chosen["discount_minor"]

    # 3. it is removed: an omission only
    api_ = c.as_(c.estimator)
    req = next(r for r in ok(api_.get(f"/api/v1/properties/{prop['id']}/requirements")) if r["id"] == requirement_id)
    ok(api_.post(f"/api/v1/requirements/{requirement_id}/decision", {"status": "EXCLUDED", "reason": "dropped"},
                 if_match=req["version"]))  # fmt: skip
    v3 = ok(step(c, v2, "versions", c.estimator, {"cost_estimate_id": _reprice(c, prop)["id"]}, code=201))
    mine = [x for x in _lines(v3) if x["line_key"] == key]
    assert [x["change_code"] for x in mine] == ["OMIT"]
    assert mine[0]["delta_amount_minor"] == -(chosen["amount_minor"] - chosen["discount_minor"])


# --- B: reproducible, tamper-proof issued documents -----------------------------------------------------------------
def test_issued_document_survives_a_template_change(api, factory, monkeypatch):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    _, est, q = _issued(c)
    first = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document"))
    assert first["template_version"] == "mtq-quotation-html/1" and first["snapshot_verified"] is True
    from veda.modules.mtq_commercial import rendering

    monkeypatch.setitem(rendering.TEMPLATES, "mtq-quotation-html/2", lambda doc: "<html>a new design</html>")
    monkeypatch.setattr(rendering, "CURRENT_TEMPLATE", "mtq-quotation-html/2")
    again = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document"))
    assert again["html"] == first["html"] and again["document"] == first["document"]
    assert again["template_version"] == "mtq-quotation-html/1"
    draft = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    assert (
        ok(c.as_(c.estimator).get(f"/api/v1/quotations/{draft['id']}/document"))["html"] == "<html>a new design</html>"
    )


def test_a_tampered_document_is_refused(api, factory):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    _, _, q = _issued(c)
    from veda.modules.mtq_commercial.models import Quotation

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        row = s.get(Quotation, q["id"])
        row.snapshot = {**row.snapshot, "summary": {**row.snapshot["summary"], "total": "1.00"}}
    r = c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document")
    assert r.status == 409 and r.code == "SNAPSHOT_INTEGRITY_FAILED" and "html" not in (r.json or {})
    assert ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}"))["snapshot_verified"] is False
    _, _, q2 = _issued(c, "3BHK")
    with db.engine().begin() as conn:
        conn.execute(
            sa.text("UPDATE quotation SET issued_html = :h WHERE id = :i"), {"h": "<p>forged</p>", "i": q2["id"]}
        )
    r = c.as_(c.sales).get(f"/api/v1/quotations/{q2['id']}/document")
    assert r.status == 409 and r.code == "SNAPSHOT_INTEGRITY_FAILED"


# --- A: lead erasure ------------------------------------------------------------------------------------------------
def test_lead_erasure_redacts_the_frozen_document_and_events(api, factory):
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead
    from veda.modules.mtq_commercial.models import Quotation, QuotationEvent

    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    prop, est = approved_estimate(c, "2BHK")
    q = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations",
                                   {"cover_note": "For Mr Probe Person at 12 Probe Street",
                                    "title": "Probe Person flat"}), 201)  # fmt: skip
    step(c, q, "submit", c.estimator)
    step(c, q, "return", c.manager, {"reason": "Ask Mr Probe Person about the loft"})
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    q = ok(step(c, q, "issue", c.manager))
    with db.unit_of_work() as s:
        name = s.get(Lead, q["lead_id"]).name
        frozen = s.get(Quotation, q["id"]).snapshot
        assert name and frozen["customer"]["name"] == name  # frozen at issue
        before = {k: frozen[k] for k in ("summary", "sections", "quotation_number", "property", "payment_schedule")}
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, q["lead_id"]), legal_basis="TEST", request_ref=None)
    with db.unit_of_work() as s:
        row = s.get(Quotation, q["id"])
        assert (row.title, row.cover_note) == ("[erased]", "[erased]")
        assert row.snapshot["subject"] == row.snapshot["cover_note"] == row.snapshot["customer"]["name"] == "[erased]"
        for text in ("Probe Person", "Probe Street", name):
            assert text not in row.issued_html and text not in str(row.snapshot)
        assert row.total_minor == q["total_minor"]
        assert {k: row.snapshot[k] for k in before} == before  # the commercial record stays
        events = s.execute(sa.select(QuotationEvent).where(QuotationEvent.quotation_id == q["id"])).scalars().all()
        assert all("Probe" not in str(e.detail) for e in events)
        redacted = [e for e in events if e.event_code == "SNAPSHOT_REDACTED"]
        assert len(redacted) == 1 and redacted[0].detail["previous_snapshot_sha256"] == q["snapshot_sha256"]
    rendered = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document"))  # re-sealed: still renders
    assert rendered["snapshot_verified"] is True and "Probe" not in rendered["html"]


# --- C: internal lineage is not a customer-facing permission ---------------------------------------------------------
def test_lineage_trace_needs_its_own_permission(api, factory):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    _, est = approved_estimate(c, "2BHK")
    q = ok(c.as_(c.sales).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    line = next(x for x in _lines(q) if x["line_key"].endswith(":WARDROBE:BODY"))
    assert ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}"))  # sales read the quotation (amounts, no rates)
    assert c.as_(c.sales).get(f"/api/v1/quotation-lines/{line['id']}/trace").status == 403
    t = ok(c.as_(c.estimator).get(f"/api/v1/quotation-lines/{line['id']}/trace"))
    assert t["estimate_line"]["rate_card_version"] == "SYNTHETIC-2" and t["estimate_line"]["rate_card_sha256"]
    from veda.modules.mtq_commercial import quotations
    from veda.modules.mtq_commercial.models import QuotationLine

    with db.unit_of_work() as s:  # without cost_estimate.rate.view the walk carries no pricing provenance
        bare = quotations.trace(s, s.get(QuotationLine, line["id"]), rates=False)
    assert not {"rate_card_version", "rate_card_sha256", "provenance"} & set(bare["estimate_line"])
    assert bare["boq_line"]["derivation"] and bare["measurement"]["measurement_set_id"] == est["measurement_set_id"]


def test_erasure_never_reseals_a_tampered_document(api, factory):
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead
    from veda.modules.mtq_commercial.models import Quotation, QuotationEvent

    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    _, _, q = _issued(c, body={"cover_note": "For Mr Probe Person", "title": "Probe Person flat"})
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        row = s.get(Quotation, q["id"])
        row.snapshot = {**row.snapshot, "summary": {**row.snapshot["summary"], "total": "1.00"}}  # tampered
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, q["lead_id"]), legal_basis="TEST", request_ref=None)
    with db.unit_of_work() as s:
        row = s.get(Quotation, q["id"])
        assert row.snapshot["subject"] == row.snapshot["customer"]["name"] == "[erased]"  # still redacted
        assert row.issued_html is None and "Probe" not in str(row.snapshot)
        assert (row.snapshot_sha256, row.issued_html_sha256) == (q["snapshot_sha256"], q["issued_html_sha256"])
        ev = s.execute(sa.select(QuotationEvent).where(QuotationEvent.quotation_id == q["id"],
                                                       QuotationEvent.event_code == "SNAPSHOT_REDACTED")).scalar_one()  # fmt: skip
        assert ev.detail["integrity"] == "INTEGRITY_FAILED_BEFORE_REDACTION" and ev.detail["resealed"] is False
    r = c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document")
    assert r.status == 409 and r.code == "SNAPSHOT_INTEGRITY_FAILED"  # never turned into a verified document
    assert ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}"))["snapshot_verified"] is False
