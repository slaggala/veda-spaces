/** DTO types mirroring 08-api-design. Unknown enum values must be tolerated (08 §2.9). */

export type Scope = 'ALL' | 'TEAM' | 'OWN';
export type PermissionMap = Record<string, Scope>;

export interface UserRef {
  id: string;
  display_name: string;
}

export interface CodeLabel {
  code: string;
  label: string;
}

export interface RoleRef {
  id: string;
  code: string;
  name: string;
}

export interface SuspendedPermission {
  code: string;
  reason: string;
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  display_name: string | null;
  phone: string | null;
  timezone: string;
  locale: string;
  status: string;
  roles: RoleRef[];
  authz_version: number;
  permissions: PermissionMap;
  suspended_permissions: Array<SuspendedPermission | string>;
  session: {
    type: 'FULL' | 'RECOVERY';
    auth_methods: string[];
    mfa_verified_on: string | null;
    cooling_off_until: string | null;
  };
  mfa: { required: boolean; required_by: string[]; enrolled: boolean };
  email_change: { proposed_email: string; requested_on: string; expires_on: string } | null;
  must_change_password?: boolean;
  version: number;
}

export interface AuthenticatedResult {
  status: 'AUTHENTICATED';
  access_token: string;
  token_type: 'Bearer';
  expires_in: number;
  must_change_password: boolean;
  user: { id: string; full_name: string; display_name: string | null; timezone: string };
  recovery_codes?: string[];
  cooling_off_until?: string | null;
}

export type LoginResult =
  | AuthenticatedResult
  | { status: 'MFA_REQUIRED'; mfa_token: string; methods: string[]; recovery_available: boolean; expires_in: number }
  | { status: 'MFA_ENROLLMENT_EMAIL_SENT'; message: string };

export interface RecoveryResult {
  status: 'RECOVERY_SESSION';
  access_token: string;
  expires_in: number;
  allowed: string[];
}

export interface EnrollStart {
  otpauth_uri: string;
  secret: string;
  challenge_token: string;
  expires_in: number;
}

export type LeadStatus = 'NEW' | 'CONTACTED' | 'SITE_VISIT' | 'QUOTATION_SENT' | 'NEGOTIATION' | 'WON' | 'LOST';

export interface Lead {
  id: string;
  lead_number: string;
  name: string;
  phone: string;
  phone_raw?: string;
  public_reference?: string;
  email: string | null;
  city: string | null;
  locality: string | null;
  project_type: CodeLabel | null;
  property_type: CodeLabel | null;
  budget_range: CodeLabel | null;
  message: string | null;
  status: LeadStatus;
  status_changed_on: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  source: CodeLabel | null;
  source_detail: string | null;
  attribution?: Record<string, string | null>;
  assigned_to: UserRef | null;
  assigned_on: string | null;
  next_follow_up_on: string | null;
  is_follow_up_overdue: boolean;
  last_activity_on: string | null;
  expected_close_on: string | null;
  won_on: string | null;
  lost_on: string | null;
  lost_reason: CodeLabel | null;
  lost_reason_note: string | null;
  duplicate_status: 'NONE' | 'SUSPECTED' | 'CONFIRMED' | 'NOT_DUPLICATE';
  duplicate_of: { id: string; lead_number: string; name?: string; status?: string } | null;
  spam_status: 'NONE' | 'SUSPECTED' | 'CONFIRMED_SPAM' | 'NOT_SPAM';
  consent: {
    contact: boolean;
    policy_version: string | null;
    captured_on: string | null;
    channel: string | null;
    source_page: string | null;
    ip_address: string | null;
    withdrawn_on: string | null;
    withdrawal_channel: string | null;
  } | null;
  intake_unmapped: Record<string, string> | null;
  allowed_transitions: LeadStatus[];
  erasure?: { audit_status: 'PENDING' | 'COMPLETED' } | null;
  anonymized_on?: string | null;
  created_on: string;
  created_by: UserRef | null;
  updated_on: string;
  updated_by: UserRef | null;
  is_deleted: boolean;
  version: number;
}

export interface LeadNote {
  id: string;
  lead_id: string;
  body: string;
  is_pinned: boolean;
  visibility: string;
  created_by: UserRef;
  created_on: string;
  updated_on: string;
  is_edited: boolean;
  can_edit: boolean;
  can_delete: boolean;
  version: number;
}

export interface LeadActivity {
  id: string;
  lead_id: string;
  lead?: { id: string; lead_number: string; name: string };
  activity_type: string;
  activity_status: 'PLANNED' | 'COMPLETED' | 'CANCELLED';
  is_system_generated: boolean;
  subject: string;
  description: string | null;
  direction: 'INBOUND' | 'OUTBOUND' | null;
  scheduled_on: string | null;
  completed_on: string | null;
  duration_minutes: number | null;
  outcome: CodeLabel | null;
  location: string | null;
  owner: UserRef | null;
  from_status: string | null;
  to_status: string | null;
  is_overdue: boolean;
  can_edit: boolean;
  created_on: string;
  version: number;
}

export interface LeadSummary {
  period: { from: string; to: string; timezone: string };
  pipeline: Record<string, number>;
  closed_in_period: { WON: number; LOST: number };
  new_leads: { count: number; previous_period_count: number };
  unassigned_open: number;
  follow_ups: { due_today: number; overdue: number };
  conversion_rate: number | null;
  median_hours_to_first_contact: number | null;
  by_source: Array<{ code: string; label: string; count: number }>;
  needs_reassignment: number;
}

export interface LookupValue {
  id: string;
  code: string;
  label: string;
  description?: string | null;
  sort_order: number;
  is_active: boolean;
  attributes?: Record<string, unknown> | null;
}

export interface LookupCategory {
  code: string;
  name?: string;
  values: LookupValue[];
}

export interface UserListItem {
  id: string;
  email: string;
  email_change_pending: boolean;
  full_name: string;
  display_name: string | null;
  status: string;
  protection_level: 'STANDARD' | 'FOUNDER';
  is_privileged: boolean;
  roles: RoleRef[];
  mfa: { required: boolean; enrolled: boolean };
  last_login_on: string | null;
  created_on: string;
  is_deleted: boolean;
  version: number;
}

export interface UserDetail extends UserListItem {
  phone: string | null;
  timezone: string;
  locale: string;
  email_verified_on: string | null;
  email_change: { proposed_email: string; requested_on: string; expires_on: string } | null;
  security_cooling_off_until: string | null;
  throttled_until: string | null;
  must_change_password: boolean;
  pending_approvals?: unknown[];
}

export interface Role {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_system: boolean;
  is_assignable: boolean;
  grant_path?: string;
  mfa_required?: boolean;
  user_count: number;
  permission_count: number;
  version: number;
}

export interface Permission {
  id: string;
  code: string;
  module: string;
  resource: string;
  action: string;
  name: string;
  description: string | null;
  supports_scope: boolean;
  is_sensitive: boolean;
  sensitivity_class?: string | null;
  grant_path?: string;
  requirement_ref: string | null;
  granted_to_roles: Array<{ code: string; scope: Scope }>;
  version: number;
}

export interface RoleGrant {
  permission_code: string;
  scope: Scope;
  id?: string;
}

export interface EffectivePermission {
  code: string;
  scope?: Scope;
  status: 'EFFECTIVE' | 'SUSPENDED' | 'DENIED';
  suspended_reason?: string;
  sources: Array<{ type: string; role_code?: string; scope?: Scope; grant_id?: string; reason?: string }>;
}

export interface DirectGrant {
  id: string;
  permission_code: string;
  effect: 'GRANT' | 'DENY';
  scope: Scope;
  reason: string;
  created_on?: string;
  version?: number;
}

export interface Approval {
  id: string;
  action_class: 'STANDARD' | 'FOUNDER';
  action_type: string;
  channel: 'IN_APP' | 'BREAK_GLASS';
  status: string;
  status_reason?: string | null;
  target_user: UserRef & { email?: string };
  requested_by: UserRef | null;
  reason: string;
  request_payload?: Record<string, unknown>;
  created_on: string;
  expires_on: string;
  not_before?: string | null;
  can_decide?: boolean;
  version?: number;
}

export interface AuditEntry {
  id: string;
  entity_type: string;
  entity_id: string;
  entity_label?: string | null;
  action: string;
  changed_fields: string[] | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  performed_by: UserRef;
  performed_on: string;
  performed_via: string;
  parent_entity_type: string | null;
  parent_entity_id: string | null;
  transaction_id: string;
  request_id: string | null;
  ip_address: string | null;
  user_agent?: string | null;
  session_id?: string | null;
  reason: string | null;
}

export interface SecurityEvent {
  id: string;
  event_type: string;
  event_category: string;
  outcome: string;
  severity: string;
  subject_user: UserRef | null;
  actor: UserRef | null;
  failure_reason: string | null;
  permission_code?: string | null;
  occurred_on: string;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
  detail: Record<string, unknown> | null;
}

export interface Notification {
  id: string;
  notification_type: string;
  title: string;
  body: string | null;
  link_path: string | null;
  read_on: string | null;
  created_on: string;
}

export interface SessionInfo {
  id: string;
  device_label: string | null;
  ip_city?: string | null;
  ip_address?: string | null;
  started_on: string;
  last_seen_on: string;
  current: boolean;
}

export interface MfaStatus {
  required: boolean;
  required_by: string[];
  factor: { type: string; label: string | null; confirmed_on: string | null; last_used_on: string | null } | null;
  recovery_codes_remaining: number;
  cooling_off_until: string | null;
}

export interface OffsetMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  total_is_estimate?: boolean;
}

export interface CursorMeta {
  limit: number;
  next_cursor: string | null;
  has_more: boolean;
  unread_count?: number;
}
