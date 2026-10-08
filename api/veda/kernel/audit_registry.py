"""Audit policy registry (07 §2) and contract exception registry (03 §2.9, §2.11).

Both registries are read by the audit hook and by the schema conformance
check (03 §2.7 rules 7 and 9, 12 §4.1).
"""

from __future__ import annotations

from dataclasses import dataclass

FULL = "FULL"
EVENT_ONLY = "EVENT_ONLY"
IMMUTABLE_STORE = "IMMUTABLE_STORE"

ALWAYS_EXCLUDED = frozenset({"updated_on", "updated_by", "version"})


@dataclass(frozen=True)
class AuditPolicy:
    table: str
    policy: str
    excluded: frozenset[str] = frozenset()
    redacted: frozenset[str] = frozenset()
    parent: tuple[str, str] | None = None  # (parent_entity_type, fk attribute)
    pii: frozenset[str] = frozenset()
    soft_delete: bool = True
    exceptions: tuple[str, ...] = ()


_POLICIES: dict[str, AuditPolicy] = {}


def register(policy: AuditPolicy) -> AuditPolicy:
    _POLICIES[policy.table] = policy
    return policy


def policy_for(table: str) -> AuditPolicy | None:
    return _POLICIES.get(table)


def all_policies() -> dict[str, AuditPolicy]:
    return dict(_POLICIES)


def parent_types() -> frozenset[str]:
    return frozenset(p.parent[0] for p in _POLICIES.values() if p.parent)


# --- 07 §2 ------------------------------------------------------------------
register(
    AuditPolicy(
        "app_user",
        FULL,
        excluded=frozenset({"last_login_on", "authz_version"}),
        pii=frozenset(
            {"email", "email_normalized", "proposed_email", "proposed_email_normalized", "full_name", "phone_e164"}
        ),
        exceptions=("EXC-008",),
    )
)
register(
    AuditPolicy(
        "user_credential",
        FULL,
        excluded=frozenset({"failed_login_count", "failed_window_started_on", "locked_until"}),
        redacted=frozenset({"password_hash"}),
        parent=("app_user", "user_id"),
    )
)
register(AuditPolicy("role", FULL))
register(AuditPolicy("permission", FULL))
register(AuditPolicy("user_role", FULL, parent=("app_user", "user_id")))
register(AuditPolicy("role_permission", FULL, parent=("role", "role_id")))
register(AuditPolicy("user_permission", FULL, parent=("app_user", "user_id")))
register(
    AuditPolicy(
        "user_mfa_factor",
        FULL,
        excluded=frozenset({"last_used_step", "last_used_on"}),
        redacted=frozenset({"secret_ciphertext", "wrapped_data_key"}),
        parent=("app_user", "user_id"),
    )
)
register(
    AuditPolicy(
        "admin_approval_request",
        FULL,
        parent=("app_user", "target_user_id"),
        soft_delete=False,
        exceptions=("EXC-006",),
    )
)
register(AuditPolicy("lookup_category", FULL))
register(AuditPolicy("lookup_value", FULL, parent=("lookup_category", "category_id")))
register(AuditPolicy("number_sequence", FULL, excluded=frozenset({"next_value", "current_period"})))
register(
    AuditPolicy(
        "lead",
        FULL,
        excluded=frozenset({"next_follow_up_on", "last_activity_on", "search_text"}),
        pii=frozenset(
            {
                "name",
                "phone",
                "phone_raw",
                "email",
                "email_normalized",
                "city",
                "message",
                "locality",
                "consent_ip_address",
                "consent_source_page",
                "consent_withdrawal_note",
                "intake_unmapped",
            }
        ),
        exceptions=("EXC-007", "EXC-010"),
    )
)
register(AuditPolicy("lead_note", FULL, parent=("lead", "lead_id"), pii=frozenset({"body"})))
# metadata_ carries the consent-history snapshot, which holds the withdrawal note and source page (RR-12).
register(
    AuditPolicy(
        "lead_activity", FULL, parent=("lead", "lead_id"), pii=frozenset({"description", "location", "metadata_"})
    )
)
# Budgetary Estimate (ADR-012). No personal data: rooms, measurements and preferences only. The rate-card document and
# the estimate result snapshot are large and reproducible (document_sha256, rule versions), so they are not snapshotted.
register(AuditPolicy("estimator_rate_card", FULL, excluded=frozenset({"document"})))
register(AuditPolicy("estimator_rate_item", FULL, parent=("estimator_rate_card", "rate_card_id")))
register(AuditPolicy("budget_estimate", FULL, excluded=frozenset({"inputs", "result"}), exceptions=("EXC-007",)))
register(AuditPolicy("budget_estimate_line", FULL, parent=("budget_estimate", "estimate_id")))
register(AuditPolicy("budget_estimate_assumption", FULL, parent=("budget_estimate", "estimate_id")))
register(AuditPolicy("budget_estimate_project_item", FULL, parent=("budget_estimate", "estimate_id")))
register(AuditPolicy("budget_estimate_lead_link", FULL, parent=("lead", "lead_id")))
register(AuditPolicy("estimate_event", FULL))

register(AuditPolicy("user_session", EVENT_ONLY, soft_delete=False, exceptions=("EXC-003", "EXC-006")))
register(AuditPolicy("refresh_token", EVENT_ONLY, soft_delete=False, exceptions=("EXC-003", "EXC-007", "EXC-009")))
register(AuditPolicy("user_action_token", EVENT_ONLY, soft_delete=False, exceptions=("EXC-003", "EXC-006", "EXC-007")))
register(AuditPolicy("user_mfa_recovery_code", EVENT_ONLY, soft_delete=False, exceptions=("EXC-006", "EXC-007")))
register(AuditPolicy("mfa_challenge", EVENT_ONLY, soft_delete=False, exceptions=("EXC-003", "EXC-007")))
register(AuditPolicy("outbox_event", EVENT_ONLY, soft_delete=False, exceptions=("EXC-004",)))
register(AuditPolicy("notification", EVENT_ONLY, exceptions=("EXC-005", "EXC-007")))

register(AuditPolicy("audit_log", IMMUTABLE_STORE, soft_delete=False, exceptions=("EXC-001", "EXC-002", "EXC-009")))
register(
    AuditPolicy(
        "security_event_log",
        IMMUTABLE_STORE,
        soft_delete=False,
        exceptions=("EXC-001", "EXC-002", "EXC-007", "EXC-009"),
    )
)


# --- 03 §2.9 EXC-007: unique indexes without the is_deleted predicate -------
UNIQUE_INDEX_EXCEPTIONS = frozenset(
    {
        "ux_refresh_token__token_hash",
        "ux_user_action_token__token_hash",
        "ux_mfa_challenge__token_hash",
        "ux_user_mfa_recovery_code__hash",
        "ux_security_event_log__chain_seq",
        "ux_admin_approval_request__open_per_target_action",
        "ux_admin_approval_request__open_founder_target",
        "ux_lead__public_reference",
        "ux_lead__intake_idempotency_key",
        "ux_budget_estimate__public_reference",
        "ux_notification__event_recipient",
    }
)


# --- 03 §2.11: the exact allow-list of FK-less GUID identifier columns ------
@dataclass(frozen=True)
class FklessIdentifier:
    table: str
    column: str
    exception: str
    purpose: str
    why_no_fk: str
    discriminator: str | None
    validation: str
    index: str | None
    retention: str
    requirements: str
    approved_by: str
    pair_check: str | None = None

    @property
    def key(self) -> str:
        return f"{self.table}.{self.column}"

    def documented(self) -> bool:
        return all([self.purpose, self.why_no_fk, self.validation, self.retention, self.requirements, self.approved_by])


FKLESS_IDENTIFIERS: tuple[FklessIdentifier, ...] = (
    FklessIdentifier(
        "audit_log",
        "session_id",
        "EXC-009",
        "Session in which the change was made",
        "Sessions are purged before evidence",
        None,
        "Format CHECK",
        None,
        "With audit_log",
        "AUDIT-003, DATA-017",
        "03 §2.3, ADR-003",
    ),
    FklessIdentifier(
        "security_event_log",
        "session_id",
        "EXC-009",
        "Session context of the event",
        "Sessions are purged before evidence",
        None,
        "Format CHECK",
        None,
        "With security_event_log",
        "SEVT-002, DATA-017",
        "03 §2.3, ADR-004",
    ),
    FklessIdentifier(
        "refresh_token",
        "replaced_by_id",
        "EXC-009",
        "Successor in a rotation chain",
        "Chains are purged in any order",
        None,
        "Format CHECK",
        None,
        "With refresh_token",
        "AUTH-005, DATA-017",
        "03 §5.2",
    ),
    FklessIdentifier(
        "audit_log",
        "entity_id",
        "EXC-011",
        "The audited row",
        "Polymorphic target, any audited table",
        "entity_type",
        "Format CHECK + discriminator",
        "ix_audit_log__entity",
        "With audit_log",
        "AUDIT-002, DATA-014",
        "03 §7, 07 §4",
    ),
    FklessIdentifier(
        "audit_log",
        "parent_entity_id",
        "EXC-011",
        "Aggregate root of a child change",
        "Polymorphic parent",
        "parent_entity_type",
        "Format CHECK + pair CHECK",
        "ix_audit_log__parent",
        "With audit_log",
        "AUDIT-006, DATA-014",
        "03 §7, 07 §4.2",
        pair_check="ck_audit_log__parent_pair",
    ),
    FklessIdentifier(
        "audit_log",
        "transaction_id",
        "EXC-011",
        "Groups all audit rows of one DB transaction",
        "Group id: there is no transaction table",
        None,
        "Format CHECK",
        "ix_audit_log__transaction_id",
        "With audit_log",
        "AUDIT-003, DATA-015",
        "03 §2.8, 07 §3",
    ),
    FklessIdentifier(
        "security_event_log",
        "target_entity_id",
        "EXC-011",
        "Object of a sensitive action",
        "Polymorphic target",
        "target_entity_type",
        "Format CHECK + pair CHECK",
        "ix_security_event_log__target",
        "With security_event_log",
        "SEVT-002, RBAC-017",
        "03 §5.4, 05 §9.1",
        pair_check="ck_security_event_log__target_pair",
    ),
    FklessIdentifier(
        "outbox_event",
        "aggregate_id",
        "EXC-011",
        "Entity that raised the event",
        "Polymorphic, and events must outlive entity changes",
        "aggregate_type",
        "Format CHECK + discriminator",
        "ix_outbox_event__aggregate",
        "Purged per 03 §2.10 step 6",
        "NOTIF-003, DATA-017",
        "03 §8.1, 02 §10.1",
    ),
    FklessIdentifier(
        "notification",
        "entity_id",
        "EXC-011",
        "Deep-link target",
        "Polymorphic, optional",
        "entity_type",
        "Format CHECK + pair CHECK",
        "ix_notification__entity",
        "Purged per 03 §2.10 step 5",
        "NOTIF-001, LEAD-029",
        "03 §8.2",
        pair_check="ck_notification__entity_pair",
    ),
    FklessIdentifier(
        "user_mfa_recovery_code",
        "batch_id",
        "EXC-011",
        "Groups codes issued together",
        "Group id: there is no batch table",
        None,
        "Format CHECK",
        "ix_user_mfa_recovery_code__batch",
        "With the codes",
        "MFA-005",
        "03 §5.6, 05 §11.5",
    ),
)

# --- 03 §2.11.1 (R-01): documented non-entity string identifiers ------------
NON_ENTITY_STRING_IDENTIFIERS: dict[str, tuple[str, int]] = {
    "audit_log.request_id": ("VARCHAR", 64),
    "security_event_log.request_id": ("VARCHAR", 64),
    "outbox_event.locked_by": ("VARCHAR", 64),
}
