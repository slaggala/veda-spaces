"""PR #95 independent-review remediation: N1 frozen acceptance totals, N2 idempotency after validation, N3 only visible
lines, N5 interleavings under the property lock, MC-2 template-v2 rollback behaviour. SYNTHETIC only.

Forced interleavings follow test_mtq_submit_race: the first request pauses right after its link resolved (before the
lock); the second runs and commits; the first resumes. On PostgreSQL the second commits while the first waits, so the
first must re-read under the lock and refuse. On SQLite a write unit of work starts BEGIN IMMEDIATE, so the second
waits for the first (which commits after its pause) instead. Either way the outcome is one deterministic winner,
never a 500, an IntegrityError or a mutation after a decision.
"""

from __future__ import annotations

import threading

import pytest
import sqlalchemy as sa

from tests.integration.test_cqx_acceptance import _ack_required, _body, _ready
from tests.support.api import ApiClient
from tests.support.proposal import ACCEPTANCE_ON, Customer, customer, ok
from veda.kernel import db
from veda.kernel.context import actor, system_context

pytestmark = ACCEPTANCE_ON
PAUSE = 2.0


def _engine() -> str:
    from veda.kernel.db import engine

    return engine().dialect.name


def _evidence_count() -> int:
    from veda.modules.customer_proposal.models import QuotationAcceptanceEvidence

    with db.unit_of_work() as s:
        return s.execute(sa.select(sa.func.count()).select_from(QuotationAcceptanceEvidence)).scalar()


def _mutate(qid: str, fn) -> None:
    from veda.modules.mtq_commercial.models import Quotation, QuotationLine

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        q = s.get(Quotation, qid)
        lines = s.execute(sa.select(QuotationLine).where(QuotationLine.quotation_id == qid)
                          .order_by(QuotationLine.position)).scalars().all()  # fmt: skip
        fn(q, lines)


# --- N1 ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("what", ["chosen_tax", "chosen_amount", "included_amount", "quotation_total"])
def test_acceptance_is_bound_to_the_frozen_values_not_mutable_rows(api, factory, what):
    c, prop, est, q, g, cust, picked = _ready(api, factory)
    page = _ack_required(cust)
    lead_status = ok(c.as_(c.sales).get(f"/api/v1/leads/{prop['lead_id']}"))["status"]
    ref = int(picked["ref"][1:])

    def mutate(qq, lines):
        chosen = next(x for x in lines if x.position == ref)
        included = next(x for x in lines if not x.is_optional and x.is_priced and x.amount_minor)
        if what == "chosen_tax":
            chosen.tax_minor = int(chosen.tax_minor or 0) + 100
        elif what == "chosen_amount":
            chosen.amount_minor = int(chosen.amount_minor or 0) + 100
        elif what == "included_amount":
            included.amount_minor = int(included.amount_minor or 0) + 100
        else:
            qq.total_minor = int(qq.total_minor or 0) + 100

    _mutate(q["id"], mutate)
    r = cust.post("/decision", _body(page), key="n1".ljust(32, "x"))
    assert r.status == 409 and r.code == "SNAPSHOT_INTEGRITY_FAILED", r
    assert _evidence_count() == 0
    assert ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))["status"] == "ISSUED"
    assert ok(c.as_(c.sales).get(f"/api/v1/leads/{prop['lead_id']}"))["status"] == lead_status


def test_a_stale_total_or_changed_choices_or_tampered_document_never_accept(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory)
    page = _ack_required(cust)
    for over, code in (({"displayed_total": page["proposal"]["summary"]["total"]}, "TOTAL_MISMATCH"),
                       ({"selected_line_refs": []}, "SELECTION_MISMATCH")):  # fmt: skip
        r = cust.post("/decision", _body(page, **over), key=code.ljust(32, "x")[:32])
        assert r.status == 409 and r.code == code, r
    from veda.modules.mtq_commercial.models import Quotation

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        row = s.get(Quotation, q["id"])
        row.snapshot = {
            **row.snapshot,
            "optional_items": [{**x, "price_with_gst": "1.00"} for x in row.snapshot["optional_items"]],
        }
    r = cust.post("/decision", _body(page), key="tamper".ljust(32, "x"))
    assert r.status == 409 and r.code == "SNAPSHOT_INTEGRITY_FAILED"
    assert _evidence_count() == 0


def test_the_accepted_total_is_the_frozen_total_plus_frozen_option_prices(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory)
    page = _ack_required(cust)
    from decimal import Decimal

    def minor(t):
        return int(Decimal(t.replace(",", "")) * 100)

    frozen = minor(page["proposal"]["summary"]["total"]) + minor(picked["price_with_gst"])
    assert minor(page["decision"]["total"]) == frozen
    assert cust.post("/decision", _body(page), key="ok".ljust(32, "x")).status == 200
    assert ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))["decision"]["accepted_total_minor"] == frozen


# --- N2 ---------------------------------------------------------------------------------------------------------------
def test_idempotency_is_evaluated_only_after_validation_and_bound_to_the_request(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory, choose=False)
    page = cust.get().data
    k1 = "decline".ljust(32, "x")
    assert cust.post("/decision", _body(page, decision="DECLINED", displayed_total=None), key=k1).status == 200
    accept = _body(page)
    r = cust.post("/decision", accept, key=k1)  # a lost Decline response followed by Accept with the same key
    assert r.status == 409 and r.code == "IDEMPOTENCY_KEY_REUSED", r
    r = cust.post("/decision", accept, key="accept".ljust(32, "x"))  # a fresh key: the version is already decided
    assert r.status == 409 and r.code == "ALREADY_DECIDED"
    for over, code in (({"version_no": 2}, "VERSION_MISMATCH"), ({"snapshot_sha256": "0" * 64}, "PROPOSAL_CHANGED")):
        r = cust.post("/decision", _body(page, decision="DECLINED", displayed_total=None, **over), key=k1)
        assert r.status == 409 and r.code == code, r  # validated before idempotency: never a replayed success
    again = cust.post("/decision", _body(page, decision="DECLINED", displayed_total=None), key=k1)
    assert again.status == 200 and again.data["decision"]["decided"] == "DECLINED"  # the identical retry
    assert _evidence_count() == 1


def test_same_key_with_changed_selection_conflicts_and_concurrent_duplicates_record_once(app, api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory)
    page = _ack_required(cust)
    key = "dup".ljust(32, "x")
    results: list = []

    def accept():
        results.append(Customer(ApiClient(app.test_client()), g["token"]).post("/decision", _body(page), key=key))

    threads = [threading.Thread(target=accept) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert [r.status for r in results] == [200, 200, 200], results
    assert _evidence_count() == 1
    r = cust.post("/decision", _body(page, selected_line_refs=[]), key=key)
    assert r.status == 409 and r.code == "IDEMPOTENCY_KEY_REUSED"


# --- N3 ---------------------------------------------------------------------------------------------------------------
def test_lines_the_document_does_not_show_are_never_selectable(api, factory):
    c, prop, est, q, g, cust, picked = _ready(api, factory, choose=False)
    from veda.modules.customer_proposal import projection
    from veda.modules.mtq_commercial.models import Quotation

    with db.unit_of_work() as s:
        qq = s.get(Quotation, q["id"])
        shown, optional = projection.printed(s, qq)
        hidden = [ref for ref in projection.refs(s, qq) if ref not in shown]
        included = [ref for ref in shown if ref not in optional]
    assert optional
    for ref in hidden + included[:2] + ["L9999"]:
        r = cust.post("/selections", {"line_ref": ref, "state": "SELECTED"})
        assert r.status == 422 and r.json["errors"][0]["code"] == "NOT_OPTIONAL", (ref, r)


# --- N5 ---------------------------------------------------------------------------------------------------------------
def _race(app, monkeypatch, first, second):
    """Run ``first`` until its link resolved, pause it, run ``second`` to completion, resume ``first``."""
    from veda.modules.customer_proposal import grants

    original = grants.resolve
    paused, done = threading.Event(), threading.Event()
    holder: dict = {}

    def resolve_then_pause(s, token):
        found = original(s, token)
        if threading.current_thread() is holder.get("first"):
            paused.set()
            done.wait(timeout=PAUSE)
        return found

    monkeypatch.setattr(grants, "resolve", resolve_then_pause)
    out: dict = {}

    def run_first():
        out["first"] = first(ApiClient(app.test_client()))

    def run_second():
        assert paused.wait(timeout=20), "the first request never reached its pause"
        out["second"] = second(ApiClient(app.test_client()))
        done.set()

    holder["first"] = threading.Thread(target=run_first)
    t2 = threading.Thread(target=run_second)
    holder["first"].start()
    t2.start()
    holder["first"].join(timeout=60)
    t2.join(timeout=60)
    assert "first" in out and "second" in out, out
    assert out["first"].status < 500 and out["second"].status < 500, out
    return out["first"], out["second"]


def test_a_choice_racing_acceptance_never_lands_after_it(app, api, factory, monkeypatch):
    c, prop, est, q, g, cust, picked = _ready(api, factory)
    page = _ack_required(cust)
    first, second = _race(app, monkeypatch,
                          lambda a: Customer(a, g["token"]).post("/selections", {"line_ref": picked["ref"], "state": "DESELECTED"}),
                          lambda a: Customer(a, g["token"]).post("/decision", _body(page), key="race".ljust(32, "x")))  # fmt: skip
    if _engine() == "postgresql":  # the decision committed while the choice waited: the choice is refused
        assert second.status == 200 and first.status == 409 and first.code == "PROPOSAL_NOT_OPEN", (first, second)
    else:  # SQLite serialises: the choice committed first, so the decision no longer matches what was shown
        assert first.status == 200 and second.status == 409 and second.code == "SELECTION_MISMATCH", (first, second)
    from veda.modules.customer_proposal.models import CustomerOptionalSelection, QuotationAcceptanceEvidence

    with db.unit_of_work() as s:
        ev = s.execute(sa.select(QuotationAcceptanceEvidence)).scalar_one_or_none()
        sel = s.execute(sa.select(CustomerOptionalSelection)).scalar_one()
        if ev is not None:
            assert sel.updated_on <= ev.decided_on and sel.state == "SELECTED"  # nothing changed after the decision


def test_an_acknowledgement_racing_acceptance_never_lands_after_it(app, api, factory, monkeypatch):
    c, prop, est, q, g, cust, picked = _ready(api, factory, choose=False)
    page = _ack_required(cust)
    extra = next(x for x in page["terms"]["sections"] if x["available"] and not x["required"])
    first, second = _race(app, monkeypatch,
                          lambda a: Customer(a, g["token"]).post("/acknowledgements", {"section": extra["code"],
                                                                                       "section_sha256": extra["sha256"]}),
                          lambda a: Customer(a, g["token"]).post("/decision", _body(page), key="race".ljust(32, "x")))  # fmt: skip
    assert second.status == 200, second
    if _engine() == "postgresql":
        assert first.status == 409 and first.code == "PROPOSAL_NOT_OPEN", first
    else:
        assert first.status == 201, first  # acknowledged before the decision (SQLite serialises)


def test_a_request_racing_acceptance_is_recorded_once_and_never_changes_the_decision(app, api, factory, monkeypatch):
    c, prop, est, q, g, cust, picked = _ready(api, factory, choose=False)
    page = _ack_required(cust)
    first, second = _race(app, monkeypatch,
                          lambda a: Customer(a, g["token"]).post("/requests", {"category": "GENERAL_QUESTION",
                                                                               "message": "One more question"},
                                                                 key="q".ljust(32, "x")),
                          lambda a: Customer(a, g["token"]).post("/decision", _body(page), key="race".ljust(32, "x")))  # fmt: skip
    assert second.status == 200 and first.status == 201, (first, second)  # a question stays possible after acceptance
    assert _evidence_count() == 1 and ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))["status"] == "ACCEPTED"


def test_revocation_racing_acceptance_wins_or_loses_cleanly(app, api, factory, monkeypatch):
    c, prop, est, q, g, cust, picked = _ready(api, factory, choose=False)
    page = _ack_required(cust)
    staff = factory.login(api, c.sales, set_default=False)
    grant = next(x for x in ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/access-grants")) if x["id"] == g["id"])

    def revoke(a):
        a.token = staff
        return a.post(f"/api/v1/proposal-access-grants/{g['id']}/revoke", if_match=grant["version"])

    first, second = _race(app, monkeypatch,
                          lambda a: Customer(a, g["token"]).post("/decision", _body(page), key="race".ljust(32, "x")),
                          revoke)  # fmt: skip
    if _engine() == "postgresql":  # revoked while the decision waited: the decision is refused, nothing recorded
        assert second.status == 200 and first.status == 410 and first.code == "PROPOSAL_LINK_REVOKED", (first, second)
        assert _evidence_count() == 0
    else:  # SQLite: the decision committed first; the revocation still succeeds after it
        assert first.status == 200 and second.status == 200, (first, second)
        assert _evidence_count() == 1


def test_rotation_racing_a_choice_refuses_the_old_link(app, api, factory, monkeypatch):
    c, prop, est, q, g, cust, picked = _ready(api, factory, choose=False)
    page = cust.get().data
    option = next(x for x in page["proposal"]["optional_items"] if x["priced"])
    staff = factory.login(api, c.sales, set_default=False)
    grant = next(x for x in ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/access-grants")) if x["id"] == g["id"])

    def rotate(a):
        a.token = staff
        return a.post(f"/api/v1/proposal-access-grants/{g['id']}/rotate", if_match=grant["version"])

    first, second = _race(app, monkeypatch,
                          lambda a: Customer(a, g["token"]).post("/selections", {"line_ref": option["ref"], "state": "SELECTED"}),
                          rotate)  # fmt: skip
    if _engine() == "postgresql":
        assert second.status == 201 and first.status == 410 and first.code == "PROPOSAL_LINK_REVOKED", (first, second)
    else:
        assert first.status == 200 and second.status == 201, (first, second)
    assert customer(api, g).get().code == "PROPOSAL_LINK_REVOKED"  # the old link is dead either way


# --- MC-2 -------------------------------------------------------------------------------------------------------------
def test_a_current_template_document_under_a_rollback_image_is_refused_not_misrendered_and_roll_forward_recovers(
    api, factory, monkeypatch
):
    """MC-2 / N6: an image without the current template's reader (the previous release) refuses a document issued
    with it (fail closed: no rendering, no acceptance); rolling forward to an image with the reader serves it again,
    byte for byte. Since the customer-completeness release the current template is version 3 (its rollback image, the
    PR #95 release, reads versions 1 and 2)."""
    c, prop, est, q, g, cust, picked = _ready(api, factory, choose=False)
    staff_doc = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document"))
    assert staff_doc["template_version"] == "mtq-quotation-html/3"
    from veda.modules.mtq_commercial import rendering

    v3 = rendering.TEMPLATES.pop("mtq-quotation-html/3")  # the rollback image knows only versions 1 and 2
    try:
        r = c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document")
        assert r.status == 409 and r.code == "SNAPSHOT_INTEGRITY_FAILED"
        assert cust.get().code == "SNAPSHOT_INTEGRITY_FAILED"
        page_body = {"decision": "DECLINED", "version_no": 1, "snapshot_sha256": q["snapshot_sha256"],
                     "selected_line_refs": [], "confirm": True}  # fmt: skip
        assert cust.post("/decision", page_body, key="rb".ljust(32, "x")).code == "SNAPSHOT_INTEGRITY_FAILED"
    finally:
        rendering.TEMPLATES["mtq-quotation-html/3"] = v3  # roll forward
    again = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document"))
    assert again["html"] == staff_doc["html"] and again["snapshot_verified"] is True
    assert cust.get().status == 200
