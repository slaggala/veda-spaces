"""Sales stage derivation and channel attribution (SCA-004/005): pure functions, every rule pinned."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from veda.modules.sales import attribution, stages, vocab
from veda.modules.sales.stages import Facts

NOW = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)


def derive(**kw) -> stages.Progression:
    return stages.derive(Facts(**{"lead_status": "NEW", **kw}), now=NOW)


def test_vocabulary_is_complete_and_ordered():
    assert set(vocab.STAGE_LABELS) == set(vocab.STAGES) and set(vocab.BASIS_LABELS) == set(vocab.BASES)
    assert set(vocab.ATTENTION_LABELS) == set(vocab.ATTENTION) and set(vocab.CHANNEL_LABELS) == set(vocab.CHANNELS)
    assert set(vocab.LEAD_STATUS_STAGE.values()) <= set(vocab.STAGES)
    assert vocab.STAGES.index("ACCEPTED") < vocab.STAGES.index("WON") < vocab.STAGES.index("LOST")


@pytest.mark.parametrize(
    ("status", "stage"),
    [
        ("NEW", "NEW"),
        ("CONTACTED", "CONTACTED"),
        ("SITE_VISIT", "SITE_MEASUREMENT"),
        ("QUOTATION_SENT", "QUOTATION_ISSUED"),
        ("NEGOTIATION", "CUSTOMER_CONSIDERING"),
    ],  # fmt: skip
)
def test_a_staff_status_alone_is_a_claim(status, stage):
    p = derive(lead_status=status)
    assert p.stage == stage
    assert p.basis == ("NONE" if stage == "NEW" else "LEAD_STATUS")
    assert p.claimed_without_record is (stage != "NEW")


def test_records_outrank_a_status_at_the_same_stage_and_prove_it():
    p = derive(lead_status="SITE_VISIT", visits=1)
    assert (p.stage, p.basis, p.claimed_without_record) == ("SITE_MEASUREMENT", "MEASUREMENT_RECORD", False)
    p = derive(lead_status="QUOTATION_SENT", quotations=1, quotation_issued=True)
    assert (p.stage, p.basis, p.claimed_without_record) == ("QUOTATION_ISSUED", "QUOTATION_RECORD", False)
    p = derive(lead_status="NEW", contacted_activity=True, meeting_done=True)
    assert (p.stage, p.basis) == ("CONSULTATION", "ACTIVITY")
    p = derive(lead_status="CONTACTED", quotations=2)
    assert (p.stage, p.basis) == ("QUOTATION_PREPARATION", "QUOTATION_RECORD")


def test_a_status_never_hides_stronger_evidence_and_evidence_never_hides_a_later_status():
    # the staff status is behind the records: the records win
    p = derive(lead_status="CONTACTED", quotations=1, quotation_issued=True, proposal_opened=True)
    assert (p.stage, p.basis) == ("CUSTOMER_CONSIDERING", "PROPOSAL_RECORD")
    # the staff status is ahead of the records: the status shows, marked as a claim
    p = derive(lead_status="NEGOTIATION", visits=1)
    assert (p.stage, p.basis, p.claimed_without_record) == ("CUSTOMER_CONSIDERING", "LEAD_STATUS", True)


def test_acceptance_and_decline_come_from_the_quotation_record_only():
    p = derive(lead_status="NEGOTIATION", quotations=1, quotation_issued=True, quotation_accepted=True)
    assert (p.stage, p.basis) == ("ACCEPTED", "QUOTATION_RECORD") and "ACCEPTED_NOT_CLOSED" in p.attention
    p = derive(lead_status="QUOTATION_SENT", quotations=1, quotation_issued=True, quotation_declined=True)
    assert (p.stage, p.basis) == ("QUOTATION_DECLINED", "QUOTATION_RECORD") and "DECLINED_STILL_OPEN" in p.attention
    # an opened link is never an acceptance
    p = derive(
        lead_status="QUOTATION_SENT", quotations=1, quotation_issued=True, proposal_opened=True, proposal_shared=True
    )
    assert p.stage == "CUSTOMER_CONSIDERING" and "ACCEPTED_NOT_CLOSED" not in p.attention


def test_a_logged_site_visit_is_measurement_evidence_and_withdrawn_consent_needs_no_follow_up():
    p = derive(lead_status="CONTACTED", site_visit_logged=True)
    assert (p.stage, p.basis, p.claimed_without_record) == ("SITE_MEASUREMENT", "ACTIVITY", False)
    p = derive(lead_status="CONTACTED", consent_withdrawn=True, last_activity_on=NOW - timedelta(days=60))
    assert p.attention == ()
    p = derive(lead_status="CONTACTED", consent_withdrawn=True, assigned=False)
    assert p.attention == ("UNASSIGNED",)


def test_closed_leads_follow_the_crm_and_carry_no_attention():
    assert derive(lead_status="LOST") == stages.Progression("LOST", "LEAD_STATUS", ())
    won = derive(lead_status="WON", next_follow_up_on=NOW - timedelta(days=3))
    assert won.stage == "WON" and won.attention == () and won.claimed_without_record is True
    assert derive(lead_status="WON", quotation_accepted=True).claimed_without_record is False


def test_attention_is_deterministic_from_dates_and_records():
    p = derive(lead_status="CONTACTED", next_follow_up_on=NOW - timedelta(hours=1), last_activity_on=NOW)
    assert p.attention == ("FOLLOW_UP_OVERDUE",)
    p = derive(lead_status="CONTACTED", last_activity_on=NOW - timedelta(days=vocab.QUIET_DAYS + 1), assigned=False)
    assert p.attention == ("NO_FOLLOW_UP_PLANNED", "QUIET", "UNASSIGNED")
    p = derive(lead_status="CONTACTED", last_activity_on=NOW - timedelta(days=vocab.QUIET_DAYS - 1))
    assert p.attention == ("NO_FOLLOW_UP_PLANNED",)
    p = derive(lead_status="QUOTATION_SENT", last_activity_on=NOW, next_follow_up_on=NOW + timedelta(days=1), quotations=1,
               quotation_issued=True, quotation_open=True, proposal_shared=True, customer_requests_open=2)  # fmt: skip
    assert p.attention == ("CUSTOMER_REQUEST_OPEN", "PROPOSAL_NOT_OPENED")
    p = derive(lead_status="QUOTATION_SENT", last_activity_on=NOW, next_follow_up_on=NOW + timedelta(days=1), quotations=1,
               quotation_issued=True, quotation_open=False, proposal_shared=True)  # fmt: skip
    assert p.attention == ()  # an expired quotation's unopened link is not an action


@pytest.mark.parametrize(
    ("source", "utm_source", "utm_medium", "referrer", "expected"),
    [
        ("REFERRAL", None, None, None, "REFERRAL"),
        ("ARCHITECT_PARTNER", None, None, None, "REFERRAL"),
        ("PHONE", None, None, None, "DIRECT"),
        ("WALK_IN", None, None, None, "DIRECT"),
        ("WHATSAPP", None, None, None, "DIRECT"),
        ("INSTAGRAM", None, None, None, "SOCIAL"),
        ("GOOGLE_ADS", None, None, None, "PAID"),
        ("OTHER", None, None, None, "UNKNOWN"),
        ("WEBSITE", None, None, None, "UNKNOWN"),
        ("WEBSITE", None, None, "https://www.vedaspaces.com/estimate", "UNKNOWN"),
        ("WEBSITE", "google", "cpc", None, "PAID"),
        ("WEBSITE", "newsletter", "email", None, "OTHER"),
        ("WEBSITE", "instagram", "social", "https://l.instagram.com/", "SOCIAL"),
        ("WEBSITE", None, "referral", "https://partner.example/", "OTHER"),  # a web referral is not a personal one
        ("WEBSITE", None, "organic", None, "ORGANIC_SEARCH"),
        ("WEBSITE", None, None, "https://api.whatsapp.com/send", "DIRECT"),
        ("WEBSITE", "whatsapp", None, None, "DIRECT"),
        ("WEBSITE", None, None, "https://www.google.co.in/search?q=x", "ORGANIC_SEARCH"),
        ("WEBSITE", None, None, "bing.com", "ORGANIC_SEARCH"),
        ("WEBSITE", None, None, "https://m.facebook.com/", "SOCIAL"),
        ("WEBSITE", None, None, "https://someblog.example/post", "OTHER"),
        (None, None, None, None, "UNKNOWN"),
    ],
)
def test_channel_derivation(source, utm_source, utm_medium, referrer, expected):
    ch = attribution.channel(source, utm_source, utm_medium, referrer)
    assert ch.code == expected and ch.detail


def test_channel_never_reads_a_query_string_or_path_as_evidence():
    assert attribution.channel("WEBSITE", None, None, "https://example.test/?utm_source=google").code == "OTHER"
    assert attribution.channel("WEBSITE", None, None, "not a url").code == "OTHER"
