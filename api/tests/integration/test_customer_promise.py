"""Customer Promise administration: lifecycle, section editing, review, four-eyes, publication, supersession,
rollback by a new version, semantic changes, preview, history, audit, least privilege and workflow bypass attempts.

SYNTHETIC personas and content only (tests.support.promise). SYNTHETIC_VALIDATED.
"""

from __future__ import annotations

import copy

import pytest
import sqlalchemy as sa

from tests.support.promise import BASE, ON, ORDINARY, SECTION_VALUES, SENSITIVE, Team, ok
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.customer_promise import sections as SEC
from veda.modules.mtq_commercial.customer_pack import FREE_MAIL
from veda.modules.customer_promise.models import CustomerPromiseEvent, CustomerPromisePack, CustomerPromiseReview
from veda.platform.audit.models import AuditLog

pytestmark = ON


# --- landing, structure, no seeded policy ---------------------------------------------------------------------------
def test_landing_starts_empty_with_structure_but_no_business_content(api, factory):
    t = Team(api, factory)
    page = ok(t.as_(t.viewer).get(BASE))
    assert page["published"] is None and page["open"] is None and page["versions"] == 0
    assert page["authority"]["state"] == "NOT_RECORDED"
    assert [a["code"] for a in page["areas"]] == [a.code for a in SEC.AREAS] and len(page["areas"]) == 14
    for a in page["areas"]:
        assert a["structure_exists"] is True and a["owner_approved_content"] is False
        assert a["customer_sees"] == "TO_BE_CONFIRMED"
    assert {a["status"] for a in page["areas"] if a["section"]} == {"NOT_STARTED"}
    assert page["effective_dating"] == "IMMEDIATE_ON_PUBLISH"
    assert page["actions"] == {"create_draft": False, "preview": False, "history": False}  # a viewer only views
    draft = t.draft()
    assert draft["version_no"] == 1 and draft["status"] == "DRAFT" and draft["origin"] == "NEW"
    # nothing is seeded: every section of the first draft is empty
    for sec in draft["sections"]:
        assert all(v in (None, []) for v in sec["value"].values()), sec["code"]
    vocab = ok(t.as_(t.viewer).get(f"{BASE}/vocabulary"))
    assert len(vocab["sections"]) == 12 and "READY" in vocab["readiness_statuses"]


@pytest.mark.settings(customer_promise_admin_enabled=False)
def test_the_admin_api_is_absent_while_the_flag_is_off(api, factory):
    t = Team(api, factory)
    for path in (BASE, f"{BASE}/versions", f"{BASE}/vocabulary"):
        r = t.as_(t.approver).get(path)
        assert r.status == 404, path
    assert api.get(BASE, anonymous=True).status == 404  # before authentication
    me = ok(t.as_(t.approver).get("/api/v1/auth/me"))
    assert me["features"]["customer_promise_admin"] is False


# --- the full lifecycle -----------------------------------------------------------------------------------------------
def test_author_review_change_request_four_eyes_approve_publish(api, factory):
    t = Team(api, factory)
    p = t.full_draft(change_summary="SYNTHETIC first pack")
    assert sorted(p["changed_sections"]) == sorted(SECTION_VALUES)
    assert p["actions"]["submit"] is True and p["problems"] == []
    p = t.act(p, "submit", t.author)
    assert p["status"] == "IN_REVIEW" and sorted(p["pending_reviews"]) == sorted(SECTION_VALUES)
    # the author cannot review or approve their own sections
    # the commercial owner holds the ordinary review capability, but never reviews what they saved
    assert t.review(p, "INCLUSIONS", t.author, status=409).code == "FOUR_EYES_REQUIRED"
    # an ordinary reviewer cannot review a sensitive section
    for code in SENSITIVE:
        t.review(p, code, t.reviewer, status=403)
    # reviews: the ordinary ones by the reviewer, then a change request on a sensitive one
    for code in ORDINARY:
        t.review(p, code, t.reviewer)
    p = t.review(p, "EXCLUSIONS", t.legal, "CHANGES_REQUESTED", comment="SYNTHETIC: name the exclusion clearly")
    assert p["status"] == "DRAFT"
    t.review(p, "WARRANTY", t.legal, status=409)  # not in review any more
    # the author corrects the exclusion; only that section needs reviewing again in the next round
    fixed = {"warranty_exclusions": [{"code": "SYN_MISUSE", "text": "SYNTHETIC: damage caused by misuse."}]}
    p = t.save(p, "EXCLUSIONS", fixed)
    p = t.act(p, "submit", t.author)
    assert p["status"] == "IN_REVIEW"
    assert sorted(p["pending_reviews"]) == sorted(SECTION_VALUES)  # a new round: every changed section again
    p = t.review_all(p)
    assert p["pending_reviews"] == [] and p["actions"]["approve"] is True
    # the history of the change request is kept
    requested = [r for r in p["reviews"] if r["decision"] == "CHANGES_REQUESTED"]
    assert len(requested) == 1 and requested[0]["section"] == "EXCLUSIONS" and requested[0]["round"] == 1
    assert requested[0]["comment"] == "SYNTHETIC: name the exclusion clearly" and requested[0]["by"]["id"] == t.legal.id
    # four-eyes on approval: the author (contributor and submitter) is refused even with the capability
    t.factory.grant(t.author, "customer_promise.approve")
    t.act(p, "approve", t.author, status=409)
    # a reviewer may not publish an unapproved version, nor may the publisher
    t.act(p, "publish", t.publisher, status=409)
    p = t.act(p, "approve", t.approver)
    assert p["status"] == "APPROVED" and p["approved_by"]["id"] == t.approver.id
    p = t.act(p, "publish", t.publisher)
    assert p["status"] == "PUBLISHED" and p["effective"] == "CURRENT" and p["content_version"] == "CPP-1"
    assert p["published_by"]["id"] == t.publisher.id and len(p["published_sha256"]) == 64
    with db.unit_of_work(write=False) as s:
        row = s.get(CustomerPromisePack, p["id"])
        assert row.published_content["content_version"] == "CPP-1"
        assert SEC.digest(row.published_content) == row.published_sha256
        events = [e.event_code for e in s.execute(sa.select(CustomerPromiseEvent).where(
            CustomerPromiseEvent.pack_id == p["id"]).order_by(CustomerPromiseEvent.created_on)).scalars()]  # fmt: skip
    for code in ("DRAFT_CREATED", "SECTION_UPDATED", "SUBMITTED", "SECTION_APPROVED", "CHANGES_REQUESTED", "APPROVED",
                 "PUBLISHED"):  # fmt: skip
        assert code in events, code
    page = ok(t.as_(t.viewer).get(BASE))
    assert page["published"]["version_no"] == 1 and page["open"] is None
    # published but OI-MTQ-18 not delegated: customers still see "to be confirmed"
    assert {a["status"] for a in page["areas"] if a["section"]} == {"PUBLISHED"}
    assert all(a["owner_approved_content"] is False for a in page["areas"])


def test_published_content_never_changes_in_place_and_a_new_version_supersedes(api, factory):
    t = Team(api, factory)
    v1 = t.publish_new()
    for action in ("submit", "approve", "publish"):
        t.act(v1, action, t.approver, status=409)
    t.save(v1, "INCLUSIONS", {"project_inclusions": []}, status=409)

    def edit(team, p):
        value = copy.deepcopy(SECTION_VALUES["CONTACTS"])
        value["contacts"][0]["hours"] = "SYNTHETIC new hours"
        p = team.save(p, "CONTACTS", value)
        readiness = copy.deepcopy(SECTION_VALUES["SITE_READINESS"])
        readiness["site_readiness"][0]["text"] = "SYNTHETIC: flooring finished and dry."
        p = team.save(p, "SITE_READINESS", readiness)
        exclusions = {"warranty_exclusions": [*SECTION_VALUES["EXCLUSIONS"]["warranty_exclusions"],
                                              {"code": "SYN_WATER", "text": "SYNTHETIC: standing water damage."}]}  # fmt: skip
        p = team.save(p, "EXCLUSIONS", exclusions)
        steps = copy.deepcopy(SECTION_VALUES["NEXT_STEPS"])
        steps["next_steps"][1]["label"] = "Veda Spaces confirmation"
        return team.save(p, "NEXT_STEPS", steps)

    draft = t.draft(change_summary="SYNTHETIC second pack")
    assert draft["origin"] == "REVISION" and draft["based_on_version"] == 1 and draft["changed_sections"] == []
    r = t.as_(t.author).post(f"{BASE}/versions", {})
    assert r.status == 409 and r.code == "DRAFT_EXISTS"
    p = edit(t, draft)
    assert sorted(p["changed_sections"]) == ["CONTACTS", "EXCLUSIONS", "NEXT_STEPS", "SITE_READINESS"]
    changes = ok(t.as_(t.reviewer).get(f"{BASE}/versions/{p['id']}/changes"))
    assert changes["from"]["version_no"] == 1 and changes["to"]["version_no"] == 2
    messages = [c["message"] for c in changes["changes"]]
    assert "Contact SYN_QUOTE_DESK: hours changed" in messages
    assert "Site-readiness requirement SYN_FLOOR: wording changed" in messages
    assert "Warranty exclusion added: SYN_WATER" in messages
    assert "Next-step stage SYN_CONFIRM: name changed" in messages
    t.act(p, "submit", t.author)
    p = t.review_all(p)
    assert len(p["reviews"]) == 4  # only the changed sections are reviewed
    t.act(p, "approve", t.approver)
    v2 = t.act(p, "publish", t.publisher)
    assert v2["status"] == "PUBLISHED"
    old = t.get(t.viewer, v1["id"])
    assert old["status"] == "SUPERSEDED" and old["superseded_by_version"] == 2 and old["effective"] == "HISTORICAL"
    assert old["published_sha256"] == v1["published_sha256"]  # untouched
    history = ok(t.as_(t.viewer).get(f"{BASE}/versions"))
    assert [(h["version_no"], h["status"]) for h in history] == [(2, "PUBLISHED"), (1, "SUPERSEDED")]
    with db.unit_of_work(write=False) as s:
        assert s.execute(sa.select(sa.func.count()).select_from(CustomerPromisePack)
                         .where(CustomerPromisePack.status == "PUBLISHED")).scalar() == 1  # fmt: skip


def test_rollback_is_a_new_version_from_an_earlier_one_through_full_governance(api, factory):
    t = Team(api, factory)
    v1 = t.publish_new()

    def change(team, p):
        return team.save(p, "PAYMENT_SAFETY", {"payment_safety": "SYNTHETIC: pay only through recorded channels."})

    v2 = t.publish_new(mutate=change)
    rb = t.draft(based_on_pack_id=v1["id"], change_summary="SYNTHETIC rollback to version 1")
    assert rb["origin"] == "ROLLBACK" and rb["based_on_version"] == 1 and rb["version_no"] == 3
    assert rb["changed_sections"] == ["PAYMENT_SAFETY"]
    # the creator restored that content: they are its author for four-eyes
    t.act(rb, "submit", t.author)
    t.factory.grant(t.author, "customer_promise.review.sensitive")
    t.review(rb, "PAYMENT_SAFETY", t.author, status=409)
    t.review(rb, "PAYMENT_SAFETY", t.legal)
    t.act(rb, "approve", t.approver)
    v3 = t.act(rb, "publish", t.publisher)
    assert v3["status"] == "PUBLISHED"
    assert t.get(t.viewer, v1["id"])["status"] == "SUPERSEDED"  # v1 is never reactivated
    assert t.get(t.viewer, v2["id"])["status"] == "SUPERSEDED"
    with db.unit_of_work(write=False) as s:
        a, c = s.get(CustomerPromisePack, v1["id"]), s.get(CustomerPromisePack, v3["id"])
        assert a.content == c.content and a.published_content != c.published_content  # content_version differs
        assert c.published_content["content_version"] == "CPP-3"
    # only a version that was published can be rolled back to
    r = t.as_(t.author).post(f"{BASE}/versions", {"based_on_pack_id": v3["id"]})
    assert r.status == 201
    t.act(r.data, "discard", t.author, {"reason": "SYNTHETIC not needed"})
    r = t.as_(t.author).post(f"{BASE}/versions", {"based_on_pack_id": r.data["id"]})
    assert r.status == 409 and r.code == "NOT_APPROVED_CONTENT"


def test_discarded_drafts_are_kept_and_published_history_is_never_deleted(api, factory):
    t = Team(api, factory)
    p = t.draft()
    t.act(p, "discard", t.author, {"reason": "x"}, status=422)
    d = t.act(p, "discard", t.author, {"reason": "SYNTHETIC duplicate"})
    assert d["status"] == "DISCARDED"
    assert ok(t.as_(t.viewer).get(f"{BASE}/versions"))[0]["status"] == "DISCARDED"
    v = t.publish_new()
    for path in (f"{BASE}/versions/{v['id']}", f"{BASE}/versions/{d['id']}"):
        assert t.as_(t.approver).delete(path).status in (404, 405)


# --- validation and claim governance ---------------------------------------------------------------------------------
def test_content_rules_refuse_claims_money_durations_contacts_links_and_payment_details(api, factory):
    t = Team(api, factory)
    p = t.draft()
    bad = {
        "PAYMENT_SAFETY": [{"payment_safety": "Pay to account 000011110000 at our bank."},
                           {"payment_safety": "Use UPI synthetic.pay@okexample for advances."},
                           {"payment_safety": "Scan the QR code to pay."},
                           {"payment_safety": "Pay at https://pay.synthetic.example"}],
        "WARRANTY": [{"manufacturer_warranty_note": "A ten year warranty on all hardware."},
                     {"manufacturer_warranty_note": "Lifetime guarantee on every cabinet."},
                     {"manufacturer_warranty_note": "Lifelong support for every product."},
                     {"manufacturer_warranty_note": "Covered for a decade by the maker."}],
        "INCLUSIONS": [{"project_inclusions": [{"code": "SYN_A", "text": "Free service for all customers."}]},
                       {"project_inclusions": [{"code": "SYN_A", "text": "Installation worth Rs 5000 included."}]},
                       {"project_inclusions": [{"code": "SYN_A", "text": "Call 0000 111 000 for help."}]},
                       {"project_inclusions": [{"code": "SYN_A", "text": "<script>alert(1)</script>",
                                                "active": False}]},
                       {"project_inclusions": [{"code": "SYN_A", "text": "Click javascript:alert(1) now."}]},
                       {"project_inclusions": [{"code": "SYN_A", "text": "Best in class fittings."}]},
                       {"project_inclusions": [{"code": "SYN_A", "text": "Done in 3 weeks."}]}],
        "CONTACTS": [{"email_domains": [], "contacts": [{**SECTION_VALUES["CONTACTS"]["contacts"][0],
                                                         "email": f"desk@{sorted(FREE_MAIL)[0]}"}], "support_escalation": None},
                     {"email_domains": [], "contacts": [{**SECTION_VALUES["CONTACTS"]["contacts"][0],
                                                         "business_channel_approved": False}], "support_escalation": None}],
    }  # fmt: skip
    for code, values in bad.items():
        for value in values:
            r = t.save(p, code, value, status=422)
            assert r.code == "VALIDATION_FAILED", (code, value)
            assert all("field" in e and "message" in e for e in r.json["errors"])
    # an unknown field and a wrong section shape (mass assignment) are refused
    r = t.save(p, "INCLUSIONS", {"project_inclusions": [], "payment_safety": "x"}, status=422)
    assert r.code == "VALIDATION_FAILED"
    r = t.as_(t.author).put(f"{BASE}/versions/{p['id']}/sections/INCLUSIONS",
                            {"value": SECTION_VALUES["INCLUSIONS"], "status": "PUBLISHED"},
                            if_match=t.get(t.author, p["id"])["version"])  # fmt: skip
    assert r.status == 422
    r = t.as_(t.author).put(f"{BASE}/versions/{p['id']}/sections/NOPE", {"value": {}},
                            if_match=t.get(t.author, p["id"])["version"])  # fmt: skip
    assert r.status == 404
    # a duration only in a stage's own field
    steps = {"next_steps": [{"code": "SYN_A", "stage": "PROPOSAL_ACCEPTED", "label": "Accepted", "text": "We confirm.",
                             "duration": "About two weeks"}]}  # fmt: skip
    assert t.save(p, "NEXT_STEPS", steps)["status"] == "DRAFT"
    out_of_order = {"next_steps": [{"code": "SYN_B", "stage": "HANDOVER", "label": "Handover", "text": "Then."},
                                   {"code": "SYN_A", "stage": "PROPOSAL_ACCEPTED", "label": "Accepted", "text": "We."}]}  # fmt: skip
    assert t.save(p, "NEXT_STEPS", out_of_order, status=422).code == "VALIDATION_FAILED"


def test_publication_rules_check_meaning_not_just_presence(api, factory):
    t = Team(api, factory)
    p = t.draft()
    r = t.act(p, "submit", t.author, status=422)
    assert {x["code"] for x in r.json["problems"]} >= {"EMPTY_PACK", "NO_CHANGE"}
    contacts = copy.deepcopy(SECTION_VALUES["CONTACTS"])
    contacts["email_domains"] = []
    p = t.save(p, "CONTACTS", contacts)
    p = t.save(p, "EXCLUSIONS")
    p = t.save(p, "WARRANTY", {"manufacturer_warranty_note": "Workmanship is covered by Veda Spaces itself."})
    two = {"next_steps": [{"code": "SYN_A", "stage": "VEDA_CONFIRMATION", "label": "A", "text": "One."},
                          {"code": "SYN_B", "stage": "VEDA_CONFIRMATION", "label": "B", "text": "Two."}]}  # fmt: skip
    p = t.save(p, "NEXT_STEPS", two)
    codes = {x["code"] for x in t.get(t.author, p["id"])["problems"]}
    assert {"EMAIL_DOMAINS_REQUIRED", "VEDA_COMMITMENT_IN_MANUFACTURER_NOTE", "DUPLICATE_STAGE"} <= codes
    t.act(p, "submit", t.author, status=422)
    p = t.save(p, "WARRANTY", {"manufacturer_warranty_note": None})
    assert "EXCLUSIONS_WITHOUT_WARRANTY" in {x["code"] for x in t.get(t.author, p["id"])["problems"]}
    # an inactive duplicate stage is not published, so it is not a duplicate
    two["next_steps"][1]["active"] = False
    p = t.save(p, "NEXT_STEPS", two)
    assert "DUPLICATE_STAGE" not in {x["code"] for x in t.get(t.author, p["id"])["problems"]}


def test_inactive_entries_are_kept_in_the_draft_but_not_published(api, factory):
    t = Team(api, factory)

    def change(team, p):
        value = copy.deepcopy(SECTION_VALUES["INCLUSIONS"])
        value["project_inclusions"].append({"code": "SYN_LATER", "text": "SYNTHETIC later item.", "active": False})
        return team.save(p, "INCLUSIONS", value)

    t.publish_new()
    v2 = t.publish_new(mutate=change)
    with db.unit_of_work(write=False) as s:
        row = s.get(CustomerPromisePack, v2["id"])
        assert [x["code"] for x in row.content["project_inclusions"]] == ["SYN_INSTALL", "SYN_LATER"]
        assert [x["code"] for x in row.published_content["project_inclusions"]] == ["SYN_INSTALL"]
    changes = ok(t.as_(t.viewer).get(f"{BASE}/versions/{v2['id']}/changes"))
    assert "Project inclusion added: SYN_LATER (inactive)" in [c["message"] for c in changes["changes"]]


# --- preview ----------------------------------------------------------------------------------------------------------
def test_preview_uses_the_customer_projection_is_labelled_and_creates_nothing(api, factory):
    t = Team(api, factory)
    p = t.full_draft()
    assert t.as_(t.sales).get(f"{BASE}/versions/{p['id']}/preview").status == 403
    pv = ok(t.as_(t.author).get(f"{BASE}/versions/{p['id']}/preview"))
    assert pv["label"] == "PREVIEW / NOT PUBLISHED" and pv["published"] is False
    assert pv["creates"] == {"quotation": False, "customer_link": False, "acceptance_evidence": False}
    info = pv["information"]
    assert info["content_version"] == "CPP-1"
    assert info["contacts"]["support"][0]["display_name"] == "SYNTHETIC Support"
    assert info["client_responsibilities"][0]["status"] == "REQUIRED"  # the default state, as a quotation shows it
    assert info["site_readiness"][0]["status"] == "TO_BE_CONFIRMED"  # project state is never set by the policy
    assert info["contacts"]["quotation"] is None  # chosen per quotation version by staff, never by the pack
    from veda.modules.customer_proposal.models import ProposalAccessGrant, QuotationAcceptanceEvidence
    from veda.modules.mtq_commercial.models import Quotation

    with db.unit_of_work(write=False) as s:
        for model in (Quotation, ProposalAccessGrant, QuotationAcceptanceEvidence):
            assert s.execute(sa.select(sa.func.count()).select_from(model)).scalar() == 0
        assert s.execute(sa.select(CustomerPromiseEvent.event_code).where(
            CustomerPromiseEvent.event_code == "PREVIEWED")).scalars().all() == ["PREVIEWED"]  # fmt: skip


# --- concurrency ------------------------------------------------------------------------------------------------------
def test_a_stale_browser_cannot_overwrite_or_publish(api, factory):
    t = Team(api, factory)
    p = t.full_draft()
    stale = p["version"]
    t.save(p, "CARE", {"care": [{"code": "SYN_DRY", "category": "FURNITURE_CLEANING", "text": "SYNTHETIC wipe dry."}]})
    r = t.as_(t.author).put(f"{BASE}/versions/{p['id']}/sections/CARE", {"value": SECTION_VALUES["CARE"]},
                            if_match=stale)  # fmt: skip
    assert r.status == 409 and r.code == "VERSION_CONFLICT"
    r = t.as_(t.author).put(f"{BASE}/versions/{p['id']}/sections/CARE", {"value": SECTION_VALUES["CARE"]})
    assert r.status == 428
    t.act(p, "submit", t.author)
    p = t.review_all(p)
    approved = t.act(p, "approve", t.approver)
    r = t.as_(t.publisher).post(f"{BASE}/versions/{p['id']}/publish", None, if_match=approved["version"] - 1)
    assert r.status == 409
    assert t.act(p, "publish", t.publisher)["status"] == "PUBLISHED"
    r = t.as_(t.publisher).post(f"{BASE}/versions/{p['id']}/publish", None, if_match=approved["version"])
    assert r.status == 409  # a duplicate publication


def test_a_section_review_goes_stale_when_reviewed_content_changes(api, factory):
    t = Team(api, factory)
    p = t.full_draft()
    t.act(p, "submit", t.author)
    t.review(p, "CARE", t.reviewer)
    t.act(p, "return", t.author, {"reason": "SYNTHETIC one more change"})
    t.save(p, "CARE", {"care": [{"code": "SYN_DRY", "category": "FURNITURE_CLEANING", "text": "SYNTHETIC wipe dry."}]})
    p = t.act(p, "submit", t.author)
    assert "CARE" in p["pending_reviews"]


# --- least privilege and bypass ---------------------------------------------------------------------------------------
def test_least_privilege_for_every_persona(api, factory):
    t = Team(api, factory)
    p = t.full_draft()
    for user in (t.sales, t.estimator, t.designer):
        assert t.as_(user).get(BASE).status == 403
        assert t.as_(user).get(f"{BASE}/versions/{p['id']}").status == 403
        assert t.as_(user).post(f"{BASE}/versions", {}).status == 403
    # the viewer sees but cannot act
    assert t.as_(t.viewer).get(f"{BASE}/versions/{p['id']}").status == 200
    assert t.save(p, "CARE", user=t.viewer, status=403).code == "PERMISSION_DENIED"
    t.act(p, "submit", t.viewer, status=403)
    # the commercial author edits ordinary sections only (contacts, warranty, payment safety are granted separately)
    plain = t.factory.user("SALES_MANAGER", mfa=True)
    t.save(p, "INCLUSIONS", user=plain)
    for code in ("CONTACTS", "SERVICE", "WARRANTY", "EXCLUSIONS", "PAYMENT_SAFETY"):
        r = t.save(p, code, user=plain, status=403)
        assert r.json["permission"] == SEC.BY_CODE[code].edit
    t.act(p, "submit", t.author)
    # the publisher cannot review or approve; the reviewer cannot approve or publish
    t.review(p, "CARE", t.publisher, status=403)
    t.act(p, "approve", t.reviewer, status=403)
    t.act(p, "publish", t.reviewer, status=403)
    # a customer (no staff session) reaches nothing
    assert api.get(BASE, anonymous=True).status == 401
    assert api.get(f"{BASE}/versions/{p['id']}", anonymous=True).status == 401


def test_direct_api_workflow_bypass_is_refused(api, factory):
    t = Team(api, factory)
    p = t.full_draft()
    for action in ("approve", "publish"):
        r = t.act(p, action, t.approver, status=409)
        assert r.code == "INVALID_STATE"
    t.act(p, "submit", t.author)
    r = t.act(p, "approve", t.approver, status=409)
    assert r.code == "REVIEW_INCOMPLETE"
    r = t.act(p, "publish", t.approver, status=409)
    assert r.code == "INVALID_STATE"
    t.save(p, "CARE", status=409)  # content is frozen once submitted
    # an approval is given to a digest: tampering after approval is refused at publication
    t.review_all(p)
    t.act(p, "approve", t.approver)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:  # a direct write, as an attacker might do
        row = s.get(CustomerPromisePack, p["id"])
        row.content = {**row.content, "payment_safety": "SYNTHETIC: changed after approval."}
    r = t.act(p, "publish", t.publisher, status=409)
    assert r.code == "APPROVAL_STALE"


def test_four_eyes_reads_the_event_trail_not_only_the_stored_contributors(api, factory):
    t = Team(api, factory)
    p = t.full_draft()
    helper = t.factory.user("FOUNDER")  # holds every capability
    t.save(p, "PAYMENT_SAFETY", {"payment_safety": "SYNTHETIC: only recorded channels."}, user=helper)
    t.act(p, "submit", t.author)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        s.execute(sa.update(CustomerPromisePack).where(CustomerPromisePack.id == p["id"]).values(contributors={}))
    t.review(p, "PAYMENT_SAFETY", helper, status=409)
    t.review_all(p)
    t.act(p, "approve", helper, status=409)
    assert t.act(p, "approve", t.approver)["status"] == "APPROVED"


# --- audit ------------------------------------------------------------------------------------------------------------
def test_audit_log_records_field_changes_and_events_carry_no_secrets(api, factory):
    t = Team(api, factory)
    v = t.publish_new()
    detail = t.get(t.approver, v["id"])
    assert detail["actions"]["history"] is True and detail["events"]
    assert "events" not in t.get(t.viewer, v["id"])  # history needs customer_promise.audit.read
    with db.unit_of_work(write=False) as s:
        logged = s.execute(sa.select(AuditLog.entity_type, AuditLog.action).where(
            AuditLog.entity_type.in_(("customer_promise_pack", "customer_promise_review", "customer_promise_event"))
        )).all()  # fmt: skip
        assert {e for e, _ in logged} == {"customer_promise_pack", "customer_promise_review", "customer_promise_event"}
        reviews = s.execute(sa.select(sa.func.count()).select_from(CustomerPromiseReview)).scalar()
        assert reviews == len(SECTION_VALUES)
        for e in s.execute(sa.select(CustomerPromiseEvent)).scalars():
            text = str(e.detail or "") + str(e.reason or "")
            assert "token" not in text.lower() and "password" not in text.lower()
