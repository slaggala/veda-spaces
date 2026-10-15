"""OI-MTQ-18 customer information pack (CQX customer completeness): copy governance, milestone reconciliation,
dimensions from verified sources only, and the issued-template compatibility guarantee. SYNTHETIC only."""

from __future__ import annotations

import copy
import hashlib
import random

import pytest
from pydantic import ValidationError

from tests.support.proposal import SYNTHETIC_PACK
from veda.modules.mtq_commercial import customer_pack as cp
from veda.modules.mtq_commercial import rendering


def _pack(**changes):
    doc = copy.deepcopy(SYNTHETIC_PACK)
    doc.update(changes)
    return doc


def test_the_synthetic_pack_is_a_valid_shape():
    assert cp.CustomerPack.model_validate(SYNTHETIC_PACK).content_version == "SYN-C1"


@pytest.mark.parametrize("text", [
    "Finished within 4 days (synthetic).", "A 7 year warranty (synthetic).", "Only ₹ 5,000 extra.", "Call +00 00000 00001.",
    "Write to someone@example.com.", "Pay to ZZZZ0SYN001.", "Account 00000000000000.", "Pay synthetic@okexample.",
    "The No. 1 synthetic studio.", "Lifetime support for synthetic items.", "100% synthetic satisfaction.", "Free service for everyone.",
    "Guaranteed synthetic results.",
])  # fmt: skip
def test_customer_copy_refuses_money_durations_contacts_bank_details_and_claims(text):
    with pytest.raises(ValidationError):
        cp.CustomerPack.model_validate(_pack(project_inclusions=[{"code": "X1", "text": text}]))


def test_a_contact_must_be_an_approved_business_channel():
    bad = _pack(contacts=[{**SYNTHETIC_PACK["contacts"][0], "business_channel_approved": False}])
    with pytest.raises(ValidationError):
        cp.CustomerPack.model_validate(bad)
    unreachable = {k: v for k, v in SYNTHETIC_PACK["contacts"][0].items() if k not in ("phone", "email")}
    with pytest.raises(ValidationError):
        cp.CustomerPack.model_validate(_pack(contacts=[unreachable]))


def test_next_steps_follow_the_stage_order_and_codes_are_unique():
    steps = SYNTHETIC_PACK["next_steps"]
    with pytest.raises(ValidationError):
        cp.CustomerPack.model_validate(_pack(next_steps=list(reversed(steps))))
    with pytest.raises(ValidationError):
        cp.CustomerPack.model_validate(
            _pack(warranty_exclusions=[{"code": "A1", "text": "x"}, {"code": "A1", "text": "y"}])
        )
    # a duration appears only in a stage's own duration field (recording it is the approval)
    timed = [{**steps[0], "duration": "About 2 weeks"}]
    assert cp.CustomerPack.model_validate(_pack(next_steps=timed)).next_steps[0].duration == "About 2 weeks"


def test_milestone_amounts_always_reconcile_exactly_and_deterministically():
    rng = random.Random(95)
    for _ in range(2000):
        total = rng.randint(1, 10**11)
        cuts = sorted(rng.sample(range(1, 10_000), rng.randint(0, 6)))
        shares = [b - a for a, b in zip([0, *cuts], [*cuts, 10_000], strict=True)]
        amounts = cp.milestone_amounts(total, shares)
        assert amounts is not None and sum(amounts) == total
        assert all(abs(a * 10_000 - total * s) < 10_000 for a, s in zip(amounts, shares, strict=True))
        assert amounts == cp.milestone_amounts(total, shares)
    assert cp.milestone_amounts(None, [10_000]) is None  # GST undecided: no total, no amounts
    assert cp.milestone_amounts(100, [5_000, 4_000]) is None  # shares not 100 %
    assert cp.milestone_amounts(100, [3_333, 3_333, 3_334]) == [33, 33, 34]


def test_dimensions_come_only_from_verified_inputs():
    inputs = {"inputs": {
        "WIDTH": {"value": "8.2000", "unit": "ft", "source": "MEASURED"},
        "HEIGHT": {"value": "7.0000", "unit": "ft", "source": "STAFF"},
        "RUN": {"value": "12.0000", "unit": "ft", "source": "ASSUMED"},
        "DRAWERS": {"value": "2", "unit": "nos", "source": "MEASURED"},
    }}  # fmt: skip
    shown, status = cp.dimensions(inputs)
    assert shown == [{"label": "Width", "value": "8.2 ft"}, {"label": "Height", "value": "7 ft"}]
    assert status == "TO_BE_CONFIRMED"  # the assumed run is not shown, and the line says so
    assert cp.dimensions({"inputs": {"AREA": {"value": "72.5", "unit": "sq ft", "source": "DERIVED"}}}) == (
        [{"label": "Area", "value": "72.5 sq ft"}],
        "CONFIRMED",
    )
    assert cp.dimensions({"inputs": {"COB": {"value": "4", "unit": "nos", "source": "STAFF"}}}) == ([], None)
    assert cp.dimensions(None) == ([], None)
    assert cp.dimensions({"inputs": {"WIDTH": {"value": None, "unit": "ft", "source": "MISSING"}}}) == (
        [],
        "TO_BE_CONFIRMED",
    )


# Rendered by the templates of the PR #95 release, before this change (digests taken from that code): an issued
# document is re-rendered with its pinned template on redaction, so versions 1 and 2 must never change.
GOLDEN = {
    "mtq-quotation-html/1": "a18f4d3264acc713522e91416c8a3d988846eddda5b082a5c1130cde87f16570",  # pragma: allowlist secret (SHA-256 of rendered HTML)
    "mtq-quotation-html/2": "0f97535d32f3e719cca9cf037489098d41955632982a896de058eab4c7db92f8",  # pragma: allowlist secret (SHA-256 of rendered HTML)
}
SAMPLE = {
    "document_version": "mtq-quotation-document/1", "brand": {"name": "Veda Spaces", "tagline": "Interiors, measured and made"},
    "title": "Quotation", "quotation_number": "VS-Q-2026-000009", "reference": "VS-Q-2026-000009 v1", "version_no": 1,
    "variation_no": 0, "date": "2026-10-15", "valid_until": "2026-11-14", "subject": "SYNTHETIC interior works",
    "cover_note": "SYNTHETIC cover note.", "property": {"reference": "VS-P-2026-000009", "configuration": "2 BHK apartment",
                                                         "city": "Synthetic City"},
    "sections": [{"title": "Master bedroom", "kind": "Space", "subtotal": "1,20,000.00", "lines": [
        {"description": "Wardrobe — Body", "detail": "Laminate finish", "quantity": "42.5 sq ft", "amount": "90,000.00",
         "priced": True, "status": "Included"},
        {"description": "Loft", "detail": None, "quantity": None, "amount": None, "priced": False, "status": "Mandatory"}]}],
    "optional_items": [{"description": "Mirror", "detail": "Master bedroom; Glass", "quantity": "1 nos", "amount": "5,000.00",
                        "priced": True, "status": "Optional"}],
    "summary": {"base_total": "1,20,000.00", "discount": None, "taxable": "1,20,000.00",
                "gst": {"status": "Included", "amount": "21,600.00"}, "total": "1,41,600.00", "optional_total": "5,000.00",
                "currency": "INR"},
    "payment_schedule": [{"label": "Booking", "share": "10%", "trigger": "On acceptance (synthetic)"}],
    "warranty": ["Synthetic warranty."], "service_support": ["Synthetic service support."],
    "assumptions": ["Synthetic assumption."], "exclusions": ["Synthetic exclusion."], "terms": ["Synthetic terms."],
    "terms_version": "SYN-T1", "customer": {"name": "SYNTHETIC Customer"},
}  # fmt: skip


def test_earlier_templates_render_byte_for_byte_as_before():
    for version, digest in GOLDEN.items():
        assert hashlib.sha256(rendering.TEMPLATES[version](SAMPLE).encode()).hexdigest() == digest, version
    assert rendering.CURRENT_TEMPLATE == "mtq-quotation-html/3"


def test_template_3_shows_every_section_or_says_it_is_to_be_confirmed():
    empty = {**SAMPLE, "customer_information": cp.information(None, None)}
    page = rendering.html_v3(empty)
    for heading in ("Your Veda Spaces contact", "What is included", "What you arrange", "Site-dependent work",
                    "Before we start", "Manufacturer warranty", "What the warranty does not cover",
                    "Need help after handover?", "Handover", "Care and maintenance", "What happens after you accept",
                    "Support", "Payments"):  # fmt: skip
        assert f"<h2>{heading}</h2>" in page, heading
    assert "Contact details to be confirmed." in page and page.count("To be confirmed by Veda Spaces.") >= 10
    full = cp.information(SYNTHETIC_PACK, {"contact_code": "SYN_QUOTE_DESK", "readiness": {"SYN_FLOOR": "READY"}})
    lines = [{**SAMPLE["sections"][0]["lines"][0], "dimensions": [{"label": "Width", "value": "8.2 ft"}],
              "dimension_status": "TO_BE_CONFIRMED"}]  # fmt: skip
    doc = {**SAMPLE, "sections": [{**SAMPLE["sections"][0], "lines": lines}], "customer_information": full,
           "payment_schedule": [{**SAMPLE["payment_schedule"][0], "amount": "1,41,600.00"}]}  # fmt: skip
    page = rendering.html_v3(doc)
    assert "SYNTHETIC Quotation Desk" in page and "quotes@synthetic.example" in page
    assert "Width 8.2 ft · dimension to be confirmed" in page and "(1,41,600.00)" in page
    assert "<span class='tag'>Ready</span>" in page and "<span class='tag'>Required</span>" in page
    assert "SYNTHETIC: payment instructions" in page and "Customer information version SYN-C1" in page


def test_information_without_a_pack_is_all_to_be_confirmed_and_never_defaulted():
    info = cp.information(None, {"contact_code": "ANY"})
    assert info["contacts"] == {"quotation": None, "support": [], "service": []}
    assert all(info[k] is None for k in info if k != "contacts")
    full = cp.information(SYNTHETIC_PACK, None)
    assert full["contacts"]["quotation"] is None  # a contact is shown only once staff chose one for the version
    assert [r["status"] for r in full["client_responsibilities"]] == ["REQUIRED", "TO_BE_CONFIRMED"]
    assert {r["status"] for r in full["site_readiness"]} == {"TO_BE_CONFIRMED"}
    assert "business_channel_approved" not in str(full) and "code" not in full["contacts"]["support"][0]
