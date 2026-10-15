"""Publication rules (CPA-31): what a pack must satisfy beyond "every field holds valid copy".

The copy rules of ``customer_pack`` (no money, durations outside a stage's own field, contacts outside contact fields,
links, payment or bank details, unsupported claims) already apply to every save. These rules check meaning across
sections. None of them decides which sections are required: every section is optional under OI-MTQ-18 (an empty
section is shown "to be confirmed"), so a rule applies only to content that is there.
"""

from __future__ import annotations

import re
from typing import Any

from . import sections as SEC

# Veda Spaces' own commitments are contract terms (OI-MTQ-09 service_support), never part of the manufacturer note.
_VEDA_COMMITMENT = re.compile(r"\bworkmanship\b|\bour\s+(?:own\s+)?(?:warranty|guarantee)\b|\bveda\s+spaces?\s+warrant",
                              re.I)  # fmt: skip


def problems(content: dict[str, Any], *, warranty_terms_decided: bool) -> list[dict[str, str]]:
    """Every reason this content may not be published, each with its section."""
    out: list[dict[str, str]] = []

    def add(section: str, code: str, message: str) -> None:
        out.append({"section": section, "code": code, "message": message})

    try:
        SEC.check(content)
    except SEC.ContentError as err:
        for e in err.errors:
            key = e["field"].split(".")[0].split("[")[0]
            section = SEC.section_of_key(key).code if key in SEC.PACK_KEYS else "CONTACTS"
            add(section, "INVALID_CONTENT", f"{e['field']}: {e['message']}")
        return out
    c = SEC.customer_content(content, "CHECK")
    if not SEC.has_content(content):
        add("CONTACTS", "EMPTY_PACK", "The pack has no customer content to publish.")
    if any(x.get("email") for x in c["contacts"]) and not c["email_domains"]:
        add("CONTACTS", "EMAIL_DOMAINS_REQUIRED", "Name Veda Spaces' business e-mail domains before publishing a "
            "contact with an e-mail address (every contact e-mail must use one of them).")  # fmt: skip
    if c["support_escalation"] and not any(x["kind"] in ("SUPPORT", "SERVICE") for x in c["contacts"]):
        add("CONTACTS", "ESCALATION_WITHOUT_CHANNEL", "An escalation route needs a support or service contact to "
            "escalate from.")  # fmt: skip
    sg = c.get("service_guidance")
    if sg and not sg.get("contact_code") and not any(x["kind"] in ("SUPPORT", "SERVICE") for x in c["contacts"]):
        add("SERVICE", "SERVICE_CHANNEL_REQUIRED", "Service guidance needs a service or support contact.")
    stages = [x["stage"] for x in c["next_steps"]]
    if len(stages) != len(set(stages)):
        add("NEXT_STEPS", "DUPLICATE_STAGE", "Each stage appears once among the active next steps.")
    sdw = c.get("site_dependent_work")
    if sdw:
        cats = [x["category"] for x in sdw.get("categories") or []]
        if len(cats) != len(set(cats)):
            add("SITE_WORK", "DUPLICATE_CATEGORY", "Each site-dependent work category appears once.")
    if c["warranty_exclusions"] and not (c["manufacturer_warranty_note"] or warranty_terms_decided):
        add("EXCLUSIONS", "EXCLUSIONS_WITHOUT_WARRANTY", "Warranty exclusions need a warranty statement they qualify: "
            "a manufacturer-warranty note here, or the warranty terms (owner decision OI-MTQ-09).")  # fmt: skip
    note = c["manufacturer_warranty_note"]
    if note and _VEDA_COMMITMENT.search(note):
        add("WARRANTY", "VEDA_COMMITMENT_IN_MANUFACTURER_NOTE", "The manufacturer-warranty note describes the "
            "manufacturer's warranty only; Veda Spaces' own service or workmanship commitments are contract terms "
            "(owner decision OI-MTQ-09).")  # fmt: skip
    return out
