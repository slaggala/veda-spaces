from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDef:
    """A code-registry permission entry (06 §3)."""

    code: str
    name: str
    description: str
    supports_scope: bool
    sensitivity_class: str | None
    requirement_ref: str
    grant_path: str = "STANDARD"

    @property
    def is_sensitive(self) -> bool:
        return self.sensitivity_class is not None

    @property
    def parts(self) -> tuple[str, str, str]:
        """(module, resource, action) derived from the code."""
        head, _, rest = self.code.partition(".")
        return head, head, rest


@dataclass(frozen=True)
class RoleDef:
    code: str
    name: str
    description: str
    mfa_required: bool
    is_assignable: bool = True
    grant_path: str = "STANDARD"
    sort_order: int = 100
