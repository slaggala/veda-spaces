"""Sales request schemas (SCA): closed, like every DTO (unknown field → 422)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import Field

from veda.kernel.dto import Closed


class PipelineQuery(Closed):
    status: Literal["open", "won", "lost", "closed", "all"] = "open"
    stage: Annotated[str, Field(max_length=30)] | None = None  # one of vocab.STAGES (422 otherwise)
    attention: Annotated[str, Field(max_length=30)] | None = None  # one of vocab.ATTENTION
    channel: Annotated[str, Field(max_length=20)] | None = None  # one of vocab.CHANNELS
    owner: Annotated[str, Field(max_length=32)] | None = None  # "me", "unassigned" or a user id
    q: Annotated[str, Field(max_length=100)] | None = None
    page: Annotated[int, Field(ge=1)] = 1
    limit: Annotated[int, Field(ge=1, le=100)] = 25


class FunnelQuery(Closed):
    date_from: date | None = Field(default=None, alias="from")
    date_to: date | None = Field(default=None, alias="to")


class PublicEventIn(Closed):
    """Loose types on purpose: the service validates and answers 422 with field errors, never 500."""

    event: Any = None
    client: Any = None
    utm_source: Any = None
    utm_medium: Any = None
    referrer_host: Any = None
