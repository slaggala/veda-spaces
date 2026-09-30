/**
 * Externalized UI strings (02 §2.1: English only in P0; Hindi/Telugu later without refactor).
 * Only shared/system strings live here; page-specific copy follows the same t() pattern.
 */
const en = {
  'app.name': 'Veda Workspace',
  'status.NEW': 'New',
  'status.CONTACTED': 'Contacted',
  'status.SITE_VISIT': 'Site visit',
  'status.QUOTATION_SENT': 'Quotation sent',
  'status.NEGOTIATION': 'Negotiation',
  'status.WON': 'Won',
  'status.LOST': 'Lost',
  'priority.HIGH': 'High',
  'priority.MEDIUM': 'Medium',
  'priority.LOW': 'Low',
  'error.generic': 'Something went wrong. Please try again.',
  'error.network': 'We could not reach the server. Check your connection and try again.',
  'error.forbidden': "You don't have permission to do that.",
  'session.expired': 'Your session expired. Please sign in again.',
  'noaccess.title': "You don't have access",
  'noaccess.body': 'Ask an administrator if you need this.',
  'empty.leads': 'No leads yet. Share your enquiry form or add one manually.',
  'recovery.banner':
    "You're in recovery mode. You can only set up a new authenticator. All your other sessions were signed out, and we've emailed you about this.",
} as const;

export type StringKey = keyof typeof en;

export function t(key: StringKey | string, vars?: Record<string, string | number>): string {
  let s: string = (en as Record<string, string>)[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
  return s;
}

export function statusLabel(status: string): string {
  return t(`status.${status}`);
}
