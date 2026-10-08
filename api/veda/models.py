"""Imports every model so the metadata is complete, then finalizes it.

Anything that needs the full schema (migrations, conformance check, tests)
imports ``veda.models``.
"""

from veda.kernel.base import Base, finalize_metadata
from veda.modules.crm.leads.models import Lead, LeadActivity, LeadNote
from veda.modules.estimator.models import (
    BudgetEstimate,
    BudgetEstimateAssumption,
    BudgetEstimateLeadLink,
    BudgetEstimateLine,
    BudgetEstimateProjectItem,
    EstimateEvent,
    EstimatorCustomerSpec,
    EstimatorCustomerSpecItem,
    EstimatorRateCard,
    EstimatorRateItem,
    EstimatorSpecEvent,
)
from veda.platform.audit.models import AuditLog
from veda.platform.auth.models import (
    MfaChallenge,
    RefreshToken,
    SecurityEventLog,
    UserActionToken,
    UserMfaFactor,
    UserMfaRecoveryCode,
    UserSession,
)
from veda.platform.identity.models import User, UserCredential
from veda.platform.lookups.models import LookupCategory, LookupValue, NumberSequence
from veda.platform.notifications.models import Notification, OutboxEvent
from veda.platform.rbac.models import AdminApprovalRequest, Permission, Role, RolePermission, UserPermission, UserRole

metadata = Base.metadata
finalize_metadata(metadata)

__all__ = [
    "AdminApprovalRequest",
    "AuditLog",
    "BudgetEstimate",
    "BudgetEstimateAssumption",
    "BudgetEstimateLeadLink",
    "BudgetEstimateLine",
    "BudgetEstimateProjectItem",
    "EstimateEvent",
    "EstimatorCustomerSpec",
    "EstimatorCustomerSpecItem",
    "EstimatorRateCard",
    "EstimatorRateItem",
    "EstimatorSpecEvent",
    "Lead",
    "LeadActivity",
    "LeadNote",
    "LookupCategory",
    "LookupValue",
    "MfaChallenge",
    "Notification",
    "NumberSequence",
    "OutboxEvent",
    "Permission",
    "RefreshToken",
    "Role",
    "RolePermission",
    "SecurityEventLog",
    "User",
    "UserActionToken",
    "UserCredential",
    "UserMfaFactor",
    "UserMfaRecoveryCode",
    "UserPermission",
    "UserRole",
    "UserSession",
    "metadata",
]
