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

CASCADES: tuple[str, ...] = ("veda.modules.attachments.service:erase_for_lead",)


def _load(path: str) -> Callable:
    module, _, name = path.partition(":")
    return getattr(importlib.import_module(module), name)


def run(s: Session, lead) -> dict[str, int]:
    """Run every cascade for one lead inside the caller's transaction; returns rows touched per cascade."""
    return {path: int(_load(path)(s, lead) or 0) for path in CASCADES}
