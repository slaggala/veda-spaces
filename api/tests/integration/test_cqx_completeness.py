"""CQX customer completeness (OI-MTQ-18, template 3): the Veda contact, item dimensions, milestone amounts and the
customer information sections, frozen at issue, never defaulted, never changed afterwards, and customer-safe.

SYNTHETIC sites, card, policies and pack only (tests.support.proposal.SYNTHETIC_PACK). SYNTHETIC_VALIDATED.
"""

from __future__ import annotations

import copy
import json
import re
from decimal import Decimal

from tests.support import reference_guard
from tests.support.commercial import Commercial, approved_estimate, install_full_policy, load_card, step
from tests.support.proposal import PROPOSAL_ON, SYNTHETIC_PACK, SYNTHETIC_PREP, customer, ok, setup, share
from veda.kernel import db
from veda.modules.customer_proposal import projection

pytestmark = PROPOSAL_ON

# Nothing Veda Spaces shows may carry real-looking contact, payment, tax or account data: the structural fixture guard
# (tests.support.reference_guard) stores nothing derived from any external document; copied wording is a policy matter.
PROMISE = re.compile(r"\b\d+\s*(working\s+)?(days?|weeks?|months?|years?)\b|guarantee|lifetime|free service", re.I)


def _classified(path: str) -> bool:
    return path in projection.FIELDS or any(
        k.startswith(path + ".") or k.startswith(path + "[]") for k in projection.FIELDS
    )


def _minor(text: str | None) -> int:
    return int(Decimal((text or "0").replace(",", "")) * 100)


def _draft(c: Commercial, key: str = "3BHK") -> tuple[dict, dict, dict]:
    prop, est = approved_estimate(c, key)
    q = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    return prop, est, q


def _patch(c: Commercial, q: dict, body: dict):
    cur = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{q['id']}"))
    return c.as_(c.estimator).patch(f"/api/v1/quotations/{q['id']}", {"customer_information": body},
                                    if_match=cur["version"])  # fmt: skip


def _issue(c: Commercial, q: dict) -> dict:
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    return ok(step(c, q, "issue", c.manager))


def test_without_a_recorded_pack_every_section_is_to_be_confirmed_and_viewing_still_works(api, factory):
    c, prop, est, q = setup(api, factory, "3BHK")
    staff = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document"))
    assert staff["template_version"] == "mtq-quotation-html/3"
    assert "Contact details to be confirmed." in staff["html"] and "To be confirmed by Veda Spaces." in staff["html"]
    page = customer(api, share(c, q)).get()
    assert page.status == 200  # viewing is never blocked by content the owner has not approved yet
    p = page.data["proposal"]
    info = p["information"]
    assert info["contacts"] == {"quotation": None, "support": [], "service": []}
    assert all(info[k] is None for k in info if k != "contacts")
    # milestone amounts: from the frozen total and the approved shares, reconciling exactly
    amounts = [_minor(m["amount"]) for m in p["payment_schedule"]]
    assert all(amounts) and sum(amounts) == _minor(p["summary"]["total"])
    assert page.data["pricing"]["milestones"] == p["payment_schedule"]
    unclassified = sorted(x for x in projection.paths(p) if not _classified(x))
    assert not unclassified, unclassified
    pv = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{q['id']}/proposal-preview"))
    checklist = {i["code"]: i for i in pv["trust_checklist"]["items"]}
    assert pv["trust_checklist"]["customer_ready"] is False
    for code in ("ARRANGE", "CONTACT", "SERVICE", "SITE_WORK", "AFTER_APPROVAL", "WARRANTY_EXCLUDES", "MATERIAL"):
        assert checklist[code]["status"] == "TO_BE_CONFIRMED" and checklist[code]["missing"], code
    for code in ("BUYING", "INCLUDED", "COST", "PAY_WHEN", "WARRANTY", "EXCLUDED", "OPTIONAL"):
        assert checklist[code]["status"] == "ANSWERED", code


def test_a_recorded_pack_and_the_staff_choices_are_frozen_at_issue_and_never_change(api, factory):
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP, OI_MTQ_18=SYNTHETIC_PACK)
    load_card()
    c = Commercial(api, factory)
    prop, est, q = _draft(c)
    # only approved codes, and only a QUOTATION contact as the quotation contact
    bad = _patch(c, q, {"contact_code": "SYN_SUPPORT", "readiness": {"NOPE": "READY"}})
    assert bad.status == 422 and {e["code"] for e in bad.json["errors"]} == {"UNKNOWN_CONTACT", "UNKNOWN_ITEM"}
    assert _patch(c, q, {"readiness": {"SYN_FLOOR": "PERHAPS"}}).status == 422  # a closed status vocabulary
    chosen = {"contact_code": "SYN_QUOTE_DESK", "responsibilities": {"SYN_LIFT": "NOT_REQUIRED"},
              "readiness": {"SYN_FLOOR": "CUSTOMER_ACTION_REQUIRED"}}  # fmt: skip
    assert ok(_patch(c, q, chosen))["customer_inputs"] == chosen
    issued = _issue(c, q)
    after = _patch(c, issued, {"contact_code": "SYN_QUOTE_DESK"})
    assert after.status == 409 and after.code == "QUOTATION_FROZEN"
    g = share(c, issued)
    before = customer(api, g).get().data["proposal"]
    info = before["information"]
    assert info["content_version"] == "SYN-C1"
    assert info["contacts"]["quotation"]["display_name"] == "SYNTHETIC Quotation Desk"
    assert [x["display_name"] for x in info["contacts"]["support"]] == ["SYNTHETIC Support"]
    assert {r["code"]: r["status"] for r in info["client_responsibilities"]} == {
        "SYN_APPLIANCE": "REQUIRED",
        "SYN_LIFT": "NOT_REQUIRED",
    }
    assert {r["code"]: r["status"] for r in info["site_readiness"]} == {
        "SYN_FLOOR": "CUSTOMER_ACTION_REQUIRED",
        "SYN_POWER": "TO_BE_CONFIRMED",
    }
    assert info["service_guidance"]["contact"]["display_name"] == "SYNTHETIC Service"
    assert [s["stage"] for s in info["next_steps"]] == ["PROPOSAL_ACCEPTED", "VEDA_CONFIRMATION", "HANDOVER"]
    text = json.dumps(before)
    assert "business_channel_approved" not in text and "SYN_QUOTE_DESK" not in text  # no internal codes of contacts
    assert not reference_guard.rule_findings(text), reference_guard.rule_findings(text)
    unclassified = sorted(x for x in projection.paths(before) if not _classified(x))
    assert not unclassified, unclassified
    pv = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{issued['id']}/proposal-preview"))
    answered = {i["code"] for i in pv["trust_checklist"]["items"] if i["status"] == "ANSWERED"}
    assert {"ARRANGE", "CONTACT", "SERVICE", "SITE_WORK", "AFTER_APPROVAL", "WARRANTY_EXCLUDES"} <= answered
    # the owner changes the pack later: the issued version is unchanged, byte for byte
    staff_before = ok(c.as_(c.sales).get(f"/api/v1/quotations/{issued['id']}/document"))
    changed = copy.deepcopy(SYNTHETIC_PACK)
    changed["content_version"] = "SYN-C2"
    changed["contacts"][0]["display_name"] = "SYNTHETIC Renamed Desk"
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP, OI_MTQ_18=changed)
    staff_after = ok(c.as_(c.sales).get(f"/api/v1/quotations/{issued['id']}/document"))
    assert staff_after["html"] == staff_before["html"] and staff_after["document"] == staff_before["document"]
    assert customer(api, g).get().data["proposal"] == before


def test_choices_need_a_recorded_pack(api, factory):
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP)
    load_card()
    c = Commercial(api, factory)
    _, _, q = _draft(c, "2BHK")
    r = _patch(c, q, {"contact_code": "SYN_QUOTE_DESK"})
    assert r.status == 409 and r.code == "CUSTOMER_PACK_NOT_DECIDED"


def test_dimensions_follow_the_measurement_lineage_and_never_guess(api, factory):
    c, prop, est, q = setup(api, factory, "3BHK")
    from veda.modules.mtq_commercial import customer_pack, quotations, rendering
    from veda.modules.mtq_commercial.models import Quotation

    with db.unit_of_work() as s:
        row = s.get(Quotation, q["id"])
        rows = [x for x in quotations.lines(s, row) if not (x.quantity_centi == 0 and not x.amount_minor)]
        inputs = rendering._formula_inputs(s, rows)
        expected = sorted(json.dumps([x.description, *customer_pack.dimensions(inputs.get(x.id))]) for x in rows)
    p = customer(api, share(c, q)).get().data["proposal"]
    lines = [x for r in p["rooms"] for x in r["lines"]] + p["optional_items"]
    sized = [x for x in lines if "dimension_status" in x]
    assert sized, "a measured 3 BHK carries sized lines"
    assert any(x["dimension_status"] == "CONFIRMED" and x["dimensions"] for x in sized)
    shown = sorted(json.dumps([x["description"], x.get("dimensions", []), x.get("dimension_status")]) for x in lines)
    assert shown == expected  # every line's sizes are exactly its BOQ line's verified inputs
    for x in lines:
        for d in x.get("dimensions", []):
            assert re.fullmatch(
                r"(Width|Height|Depth|Total run|Wall-unit run|Length|Door width|Area|Floor area)", d["label"]
            )
            assert re.fullmatch(r"\d+(\.\d{1,2})? (ft|sq ft)", d["value"]), d
    # nothing of the measurement engine reaches the customer
    text = json.dumps(p)
    for marker in ("MEASURED", "DERIVED", "ASSUMED", "explain", "refs", "wall_index", "W1", "mm"):
        assert f'"{marker}' not in text and f" {marker} " not in text, marker


def test_a_document_issued_with_template_2_still_renders_and_shows_its_sections_as_to_be_confirmed(
    api, factory, monkeypatch
):
    """A version issued by the previous release (template 2, no customer information) keeps rendering under this
    release, byte for byte, and its page says the new sections are to be confirmed (never filled from today's pack)."""
    from veda.modules.mtq_commercial import rendering

    original = rendering.document_model

    def previous_release(s, q, *, frozen=False):
        doc = original(s, q, frozen=frozen)
        doc.pop("customer_information", None)
        doc["document_version"] = "mtq-quotation-document/1"
        for m in doc["payment_schedule"]:
            m.pop("amount", None)
        for line in [x for sec in doc["sections"] for x in sec["lines"]] + doc["optional_items"]:
            line.pop("dimensions", None)
            line.pop("dimension_status", None)
        return doc

    monkeypatch.setattr(rendering, "document_model", previous_release)
    monkeypatch.setattr(rendering, "CURRENT_TEMPLATE", "mtq-quotation-html/2")
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP, OI_MTQ_18=SYNTHETIC_PACK)
    load_card()
    c = Commercial(api, factory)
    _, _, q = _draft(c, "2BHK")
    issued = _issue(c, q)
    first = ok(c.as_(c.sales).get(f"/api/v1/quotations/{issued['id']}/document"))
    monkeypatch.setattr(rendering, "document_model", original)
    monkeypatch.setattr(rendering, "CURRENT_TEMPLATE", "mtq-quotation-html/3")
    again = ok(c.as_(c.sales).get(f"/api/v1/quotations/{issued['id']}/document"))
    assert again["template_version"] == "mtq-quotation-html/2" and again["html"] == first["html"]
    p = customer(api, share(c, issued)).get().data["proposal"]
    assert p["information"]["contacts"]["quotation"] is None and p["information"]["next_steps"] is None
    assert all(m["amount"] is None for m in p["payment_schedule"])
    assert not any("dimension_status" in x for r in p["rooms"] for x in r["lines"])


def test_lead_erasure_keeps_the_business_information_and_reseals_with_template_3(api, factory):
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP, OI_MTQ_18=SYNTHETIC_PACK)
    load_card()
    c = Commercial(api, factory)
    prop, _, q = _draft(c, "2BHK")
    ok(_patch(c, q, {"contact_code": "SYN_QUOTE_DESK"}))
    issued = _issue(c, q)
    from veda.kernel.context import actor, system_context
    from veda.modules.crm.leads import erasure as lead_erasure
    from veda.modules.crm.leads.models import Lead

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead_erasure.run(s, s.get(Lead, prop["lead_id"]))
    doc = ok(c.as_(c.sales).get(f"/api/v1/quotations/{issued['id']}/document"))
    assert doc["snapshot_verified"] is True and doc["template_version"] == "mtq-quotation-html/3"
    assert doc["document"]["customer"]["name"] == "[erased]" and doc["document"]["subject"] == "[erased]"
    info = doc["document"]["customer_information"]
    assert info["contacts"]["quotation"]["display_name"] == "SYNTHETIC Quotation Desk"  # a business contact stays
    assert "SYNTHETIC Quotation Desk" in doc["html"] and "[erased]" in doc["html"]


def test_the_customer_page_makes_no_unsupported_promise(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK", OI_MTQ_18=SYNTHETIC_PACK)
    page = customer(api, share(c, q)).get().data
    text = json.dumps({k: v for k, v in page.items() if k != "link"})
    found = [m.group(0) for m in PROMISE.finditer(text)]
    assert not found, found
    assert not reference_guard.rule_findings(text)


def test_materials_and_hardware_come_from_the_approved_specification_and_the_checklist_can_be_complete(api, factory):
    from tests.integration.test_estimator_spec import SPEC_DOC, load_spec

    load_spec(copy.deepcopy(SPEC_DOC))
    install_full_policy(OI_MTQ_15=SYNTHETIC_PREP, OI_MTQ_18=SYNTHETIC_PACK)
    load_card()
    c = Commercial(api, factory)
    _, _, q = _draft(c)
    ok(_patch(c, q, {"contact_code": "SYN_QUOTE_DESK"}))
    issued = _issue(c, q)
    page = customer(api, share(c, issued)).get().data
    specs = page["specifications"]
    groups = {cat["group"] for cat in specs["categories"]}
    assert groups == {"MATERIAL", "HARDWARE"}
    assert all(bool(cat["hardware_category"]) == (cat["group"] == "HARDWARE") for cat in specs["categories"])
    assert all("hardware_category" in cat for hits in specs["lines"].values() for cat in hits)
    pv = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{issued['id']}/proposal-preview"))
    items = {i["code"]: i for i in pv["trust_checklist"]["items"]}
    sized = [x for r in page["proposal"]["rooms"] for x in r["lines"] if "dimension_status" in x]
    size_ok = bool(sized) and all(x["dimension_status"] == "CONFIRMED" for x in sized)
    assert items["SIZE"]["status"] == ("ANSWERED" if size_ok else "TO_BE_CONFIRMED")
    assert all(i["status"] == "ANSWERED" for code, i in items.items() if code != "SIZE"), items
    assert pv["trust_checklist"]["customer_ready"] is size_ok
