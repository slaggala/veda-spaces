"""Extension points of the attachment module.

ATT knows nothing about the records photos are attached to. A module that owns an ``entity_type`` registers a binding
that resolves an entity id to its lead and its limits container, and says whether it may still change. A module may
also widen OWN access to a lead (MTQ: the surveyor assigned to a visit). Both are registered at import time by the
owning module; an entity type without a binding is refused (fail closed).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import ENTITY_TYPES


@dataclass(frozen=True)
class EntityContext:
    """What ATT needs to know about the record an attachment belongs to."""

    lead_id: str
    container_id: str | None = None  # the measurement set whose hard limits apply (800 objects, 1 GiB)
    wall_id: str | None = None  # the wall whose per-wall limits apply (6 soft, 12 hard)
    space_id: str | None = None  # the space whose soft limit applies (40)
    writable: bool = True  # False once the owning record is frozen (e.g. a SUBMITTED set): no new uploads
    withdraw_rule: str = "UPLOADER_OR_ALL"  # or "VERIFIER_WITH_REASON" once the owning record is submitted
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EntityBinding:
    entity_type: str
    resolve: Callable[[Session, str], EntityContext | None]
    # Counts (objects, bytes) of live attachments in a container, across every entity type in it.
    container_usage: Callable[[Session, str], tuple[int, int]] | None = None
    # Serialises a new attachment against the container's freeze (MTQ: the property lock submit takes) and refreshes
    # the container, so ``resolve`` re-read after it decides ``writable`` and the limits on the committed state.
    container_lock: Callable[[Session, str], None] | None = None


_BINDINGS: dict[str, EntityBinding] = {}
_LEAD_ACCESS: list[Callable[[str], sa.ColumnElement[bool]]] = []


def bind(binding: EntityBinding) -> None:
    if binding.entity_type not in ENTITY_TYPES:
        raise RuntimeError(f"{binding.entity_type} is not an attachment entity type (migration 0106 CHECK)")
    _BINDINGS[binding.entity_type] = binding


def binding_for(entity_type: str) -> EntityBinding | None:
    return _BINDINGS.get(entity_type)


def grant_lead_access(predicate: Callable[[str], sa.ColumnElement[bool]]) -> None:
    """Register a predicate ``f(actor_id) -> condition on lead.id`` that makes a lead OWN-visible to an actor."""
    _LEAD_ACCESS.append(predicate)


def lead_access_predicates(actor_id: str) -> list[sa.ColumnElement[bool]]:
    return [p(actor_id) for p in _LEAD_ACCESS]


def _reset_for_tests(bindings: dict[str, EntityBinding] | None = None) -> dict[str, EntityBinding]:
    """Tests only: swap the binding table and return the previous one."""
    previous = dict(_BINDINGS)
    if bindings is not None:
        _BINDINGS.clear()
        _BINDINGS.update(bindings)
    return previous
