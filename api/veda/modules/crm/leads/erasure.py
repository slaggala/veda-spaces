"""Erasure cascades (07 §8.2; MTQ blocker closure §6.4).

Records in other modules that hang off a lead and hold personal data or personal media are erased together with the
lead, by both the staff erasure and the lead-retention job, which share ``service.anonymize``. Each cascade is named
here by dotted path and imported at call time, so the leads module depends on no downstream module and a cascade can
never be skipped because its module was not imported by the process (CLI, scheduler or API).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable

from sqlalchemy.orm import Session

CASCADES: tuple[str, ...] = (
    "veda.modules.attachments.service:erase_for_lead",
    "veda.modules.mtq.erasure:erase_for_lead",
    "veda.modules.mtq_commercial.erasure:erase_for_lead",
    "veda.modules.customer_proposal.erasure:erase_for_lead",
    "veda.modules.project.erasure:erase_for_lead",
    "veda.modules.portal.erasure:erase_for_lead",
    "veda.modules.commercials.erasure:erase_for_lead",
)


# Ids of every row, in another module, whose audit payloads may hold the lead's personal data and whose audit parent is
# not the lead itself; the erasure-audit job rewrites those payloads too (07 §8.2 step 6).
DESCENDANTS: tuple[str, ...] = (
    "veda.modules.attachments.service:audit_ids_for_lead",
    "veda.modules.mtq.erasure:audit_ids_for_lead",
    "veda.modules.mtq_commercial.erasure:audit_ids_for_lead",
    "veda.modules.customer_proposal.erasure:audit_ids_for_lead",
    "veda.modules.project.erasure:audit_ids_for_lead",
    "veda.modules.portal.erasure:audit_ids_for_lead",
    "veda.modules.commercials.erasure:audit_ids_for_lead",
)


def _load(path: str) -> Callable:
    module, _, name = path.partition(":")
    return getattr(importlib.import_module(module), name)


def run(s: Session, lead) -> dict[str, int]:
    """Run every cascade for one lead inside the caller's transaction; returns rows touched per cascade."""
    return {path: int(_load(path)(s, lead) or 0) for path in CASCADES}


def descendant_ids(s: Session, lead_id: str) -> list[str]:
    ids: list[str] = []
    for path in DESCENDANTS:
        ids.extend(_load(path)(s, lead_id))
    return ids
