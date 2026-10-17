import type { Me, PermissionMap, Scope } from '../api/types.js';

const RANK: Record<Scope, number> = { OWN: 1, TEAM: 2, ALL: 3 };

/** UI permission checks are hints only; the server is authoritative (RBAC-012). */
export function has(perms: PermissionMap | null | undefined, code: string, minScope?: Scope): boolean {
  const scope = perms?.[code];
  if (!scope) return false;
  return !minScope || RANK[scope] >= RANK[minScope];
}

export function hasAny(perms: PermissionMap | null | undefined, codes: readonly string[]): boolean {
  return codes.some((c) => has(perms, c));
}

export function hasAll(perms: PermissionMap | null | undefined, codes: readonly string[]): boolean {
  return codes.every((c) => has(perms, c));
}

/**
 * OWN-scope evaluation for a lead-like row (06 §4): the actor owns a lead when assigned_to or created_by
 * is the actor. Used by <vs-can scope-for> to hide actions the server would refuse.
 */
export function canOnRow(
  perms: PermissionMap | null | undefined,
  code: string,
  actorId: string | undefined,
  row?: { assigned_to?: { id: string } | null; created_by?: { id: string } | null; owner?: { id: string } | null } | null,
): boolean {
  const scope = perms?.[code];
  if (!scope) return false;
  if (scope === 'ALL' || !row) return true;
  if (!actorId) return false;
  return row.assigned_to?.id === actorId || row.created_by?.id === actorId || row.owner?.id === actorId;
}

export function suspendedCodes(me: Me | null): Map<string, string> {
  const out = new Map<string, string>();
  for (const entry of me?.suspended_permissions ?? []) {
    if (typeof entry === 'string') out.set(entry, 'MFA_REQUIRED');
    else out.set(entry.code, entry.reason);
  }
  return out;
}

export interface NavItem {
  path: string;
  label: string;
  icon: string;
  group: 'main' | 'admin' | 'account';
  /** The item renders when the user holds ANY of these permission codes (09 §3.1). */
  anyOf: readonly string[];
  /** MC-3: a feature the deployment must have switched on (``/auth/me`` ``features``) besides the permission. */
  feature?: FeatureCode;
  mobile?: boolean;
}

export type FeatureCode = 'mtq_site' | 'mtq_estimation' | 'mtq_quotation' | 'customer_promise_admin' | 'project_lifecycle' | 'customer_portal'
  | 'project_commercials' | 'warranty_service' | 'sales_experience';
export type FeatureMap = Partial<Record<FeatureCode, boolean>>;

export const NAV_ITEMS: readonly NavItem[] = [
  { path: '/', label: 'Dashboard', icon: 'home', group: 'main', anyOf: ['lead.read'], mobile: true },
  { path: '/leads', label: 'Leads', icon: 'users', group: 'main', anyOf: ['lead.read'], mobile: true },
  { path: '/follow-ups', label: 'Follow-ups', icon: 'calendar', group: 'main', anyOf: ['lead_activity.read'], mobile: true },
  { path: '/site', label: 'Site visits', icon: 'calendar', group: 'main', anyOf: ['measurement.visit.read', 'property.read'], feature: 'mtq_site', mobile: true },
  // Operations › Projects (PLB-10): behind VEDA_PROJECT_LIFECYCLE_ENABLED and project.view.
  { path: '/projects', label: 'Projects', icon: 'list', group: 'main', anyOf: ['project.view'], feature: 'project_lifecycle', mobile: true },
  // After handover › Service (WSV): behind VEDA_WARRANTY_SERVICE_ENABLED and warranty.service.view.
  { path: '/service', label: 'Service', icon: 'list', group: 'main', anyOf: ['warranty.service.view'], feature: 'warranty_service', mobile: true },
  // Commercial › Payments (PCM): behind VEDA_PROJECT_COMMERCIALS_ENABLED and commercials.view.
  { path: '/commercials', label: 'Payments', icon: 'list', group: 'main', anyOf: ['commercials.view'], feature: 'project_commercials' },
  // Sales & Customer Acquisition (SCA): behind VEDA_SALES_EXPERIENCE_ENABLED and each page's own view permission.
  { path: '/sales', label: 'Sales pipeline', icon: 'users', group: 'main', anyOf: ['sales.pipeline.view'], feature: 'sales_experience', mobile: true },
  { path: '/sales/funnel', label: 'Funnel', icon: 'list', group: 'main', anyOf: ['sales.funnel.view'], feature: 'sales_experience' },
  { path: '/sales/demo', label: 'Customer journey demo', icon: 'star', group: 'main', anyOf: ['sales.demo.view'], feature: 'sales_experience' },
  { path: '/approvals', label: 'Approvals', icon: 'check', group: 'admin', anyOf: ['user.mfa.reset', 'user.email.change', 'user.founder.manage'] },
  { path: '/admin/users', label: 'Users', icon: 'user', group: 'admin', anyOf: ['user.read'] },
  { path: '/admin/roles', label: 'Roles', icon: 'shield', group: 'admin', anyOf: ['role.read'] },
  { path: '/admin/permissions', label: 'Permissions', icon: 'key', group: 'admin', anyOf: ['permission.read'] },
  { path: '/admin/founder-actions', label: 'Founder actions', icon: 'star', group: 'admin', anyOf: ['user.founder.manage'] },
  { path: '/catalog', label: 'Estimator catalog', icon: 'list', group: 'admin', anyOf: ['catalog.view'] },
  // Commercial › Customer Promise (decision log 37): behind VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED and its view capability.
  { path: '/commercial/customer-promise', label: 'Customer Promise', icon: 'shield', group: 'admin', anyOf: ['customer_promise.view'], feature: 'customer_promise_admin' },
  { path: '/audit', label: 'Audit log', icon: 'list', group: 'admin', anyOf: ['audit.read', 'security_event.read'] },
  { path: '/profile', label: 'Profile', icon: 'settings', group: 'account', anyOf: ['profile.read'], mobile: true },
];

/**
 * Permission-driven navigation: only items whose permission the user holds (09 §3.1, 02 §2.2), and, for an item
 * behind a feature, only while the deployment has that feature on (MC-3: a permission alone never makes a
 * switched-off feature discoverable; a missing or unknown feature map counts as off).
 */
export function filterNav(items: readonly NavItem[], perms: PermissionMap | null | undefined, features?: FeatureMap | null): NavItem[] {
  return items.filter((item) => hasAny(perms, item.anyOf) && (!item.feature || features?.[item.feature] === true));
}
