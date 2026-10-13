"""The rate card MTQ prices with: the estimator's one ACTIVE card (versioned, owner-approved on activation, immutable
once active). MTQ never loads, edits or activates a card; it pins the one in force on every estimate."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError
from veda.modules.estimator import ratecard
from veda.modules.estimator import service as estimator_service
from veda.modules.estimator.models import EstimatorRateCard


def active_row(s: Session) -> EstimatorRateCard | None:
    return s.execute(sa.select(EstimatorRateCard).where(EstimatorRateCard.status == "ACTIVE")).scalar_one_or_none()


def active(s: Session) -> tuple[EstimatorRateCard, ratecard.RateCard]:
    try:
        return estimator_service.active_card(s)
    except ApiError as err:
        raise ApiError(409, "RATE_CARD_UNAVAILABLE", "No rate card is active; nothing can be priced.") from err
