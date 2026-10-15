"""The customer trust checklist (CTB-18): can a customer answer each basic question from what this proposal shows?

Evaluated on the customer projection (the frozen document as the customer sees it) and the approved specification,
never on staff-only data. Each question is ANSWERED or TO_BE_CONFIRMED, with what is missing. The checklist is shown to
staff (proposal preview); it never blocks viewing: a synthetic, viewing-only staging proposal may carry sections the
owner has not approved yet, and the page says so. Use with real customers needs ``customer_ready`` (every question
answered); that gate belongs to the real-customer enablement record, not to issuance.
"""

from __future__ import annotations

from typing import Any

QUESTIONS: tuple[tuple[str, str], ...] = (
    ("BUYING", "What am I buying?"),
    ("SIZE", "What size is it?"),
    ("MATERIAL", "What material is it?"),
    ("HARDWARE", "Which hardware applies?"),
    ("INCLUDED", "What is included?"),
    ("EXCLUDED", "What is excluded?"),
    ("ARRANGE", "What do I arrange?"),
    ("OPTIONAL", "What is optional?"),
    ("COST", "What does it cost?"),
    ("PAY_WHEN", "When do I pay?"),
    ("WARRANTY", "What warranty applies?"),
    ("WARRANTY_EXCLUDES", "What does the warranty not cover?"),
    ("SERVICE", "How do I ask for service?"),
    ("SITE_WORK", "What happens if site-dependent work is discovered?"),
    ("AFTER_APPROVAL", "What happens after I approve?"),
    ("CONTACT", "Who do I contact?"),
)


def checklist(proposal: dict[str, Any], specifications: dict[str, Any] | None) -> dict[str, Any]:
    info = proposal.get("information") or {}
    lines = [x for r in proposal.get("rooms") or [] for x in r.get("lines") or []]
    sized = [x for x in lines + list(proposal.get("optional_items") or []) if "dimension_status" in x]
    groups = {c.get("group") for c in (specifications or {}).get("categories") or []}
    summary = proposal.get("summary") or {}
    schedule = proposal.get("payment_schedule") or []

    def missing(cond: bool, what: str) -> str | None:
        return None if cond else what

    gaps = {
        "BUYING": missing(bool(lines), "no priced lines"),
        "SIZE": (
            missing(bool(sized), "no line carries a verified dimension")
            or missing(all(x["dimension_status"] == "CONFIRMED" for x in sized), "some dimensions are to be confirmed")
        ),  # fmt: skip
        "MATERIAL": missing("MATERIAL" in groups, "no approved material specification"),
        "HARDWARE": missing("HARDWARE" in groups, "no approved hardware specification"),
        "INCLUDED": missing(any(x.get("status") != "Optional" for x in lines), "no included lines"),
        "EXCLUDED": missing(bool(proposal.get("exclusions")), "no approved exclusions (OI-MTQ-09)"),
        "ARRANGE": missing(
            bool(info.get("client_responsibilities")), "no approved customer responsibilities (OI-MTQ-18)"
        ),
        "OPTIONAL": None,  # the optional items are listed, or the page says there are none
        "COST": missing(
            bool(summary.get("total")) and (summary.get("gst") or {}).get("status") == "Included",
            "the total including GST is not decided (OI-MTQ-07)",
        ),  # fmt: skip
        "PAY_WHEN": missing(
            bool(schedule) and all(m.get("amount") for m in schedule),
            "no approved payment plan with amounts (OI-MTQ-09)",
        ),  # fmt: skip
        "WARRANTY": missing(bool(proposal.get("warranty")), "no approved warranty text (OI-MTQ-09)"),
        "WARRANTY_EXCLUDES": missing(
            bool(info.get("warranty_exclusions")), "no approved warranty exclusions (OI-MTQ-18)"
        ),
        "SERVICE": missing(bool(info.get("service_guidance")), "no approved service guidance (OI-MTQ-18)"),
        "SITE_WORK": missing(bool(info.get("site_dependent_work")), "no approved site-dependent-work rule (OI-MTQ-18)"),
        "AFTER_APPROVAL": missing(bool(info.get("next_steps")), "no approved next steps (OI-MTQ-18)"),
        "CONTACT": missing(
            bool((info.get("contacts") or {}).get("quotation")),
            "no approved Veda Spaces contact chosen for this version (OI-MTQ-18)",
        ),  # fmt: skip
    }
    items = [{"code": code, "question": question, "status": "TO_BE_CONFIRMED" if gaps[code] else "ANSWERED",
              "missing": gaps[code]} for code, question in QUESTIONS]  # fmt: skip
    return {"customer_ready": all(i["status"] == "ANSWERED" for i in items), "items": items}
