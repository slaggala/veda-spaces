"""Request schemas of the estimator routes. Public bodies are loose (`Any`) and validated by the engine's closed models
after the feature flag and Turnstile, so a bad request never reaches the database."""

from __future__ import annotations

from typing import Any

from veda.kernel.dto import Closed
from veda.modules.crm.leads.schemas import PublicLeadIn


class PublicEstimateIn(Closed):
    property_type: Any = None
    home_size: Any = None
    project_kind: Any = None
    city: Any = None
    package: Any = None
    selections: Any = None
    turnstile_token: Any = None


class PublicEnquiryIn(PublicLeadIn):
    """The website enquiry (04 §5.1) plus the estimate it follows and how the customer prefers to be contacted."""

    estimate_reference: Any = None
    preferred_contact: Any = None


class EstimateRevisionIn(Closed):
    package: str | None = None
    selections: list[dict] | None = None
