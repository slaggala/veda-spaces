import { api } from '../../core/api/client.js';
import { fragmentParam } from '../../core/router/next.js';
import type { Page } from '../proposal/api.js';

/**
 * The Customer Project Portal API (CPP). A customer never holds a staff token: the portal session travels only in the
 * X-Veda-Portal header and is kept in this tab's sessionStorage (gone when the tab closes; the same choice as the CQX
 * proposal link). The emailed sign-in link carries its one-time token in the URL fragment, which browsers never send to
 * a server; `takeLinkToken` reads it and scrubs the address bar at once.
 */

export type StepState = 'COMPLETED' | 'IN_PROGRESS' | 'ACTION_REQUIRED' | 'UPCOMING' | 'NOT_YET_AVAILABLE' | 'INFORMATION';
export interface Step { key: string; label: string; state: StepState; detail: string; date: string | null }
export interface QuotationSummary {
  id: string; reference: string; title: string; kind: 'QUOTATION' | 'VARIATION'; version_no: number;
  state: 'OPEN' | 'ACCEPTED' | 'DECLINED' | 'EXPIRED' | 'SUPERSEDED' | 'UNAVAILABLE'; status: StepState; status_label: string;
  issued_on: string | null; valid_until: string | null; days_left: number | null; total: string | null; currency: string | null;
}
export interface Contact { source: 'QUOTATION' | 'CONSULTANT'; name: string | null; role: string | null; phone: string | null;
  email: string | null; hours: string | null }
export interface Attention { kind: 'QUOTATION_DECISION' | 'PROJECT_ACTION' | 'SITE_READINESS' | 'SITE_VISIT' | 'PAYMENT_DUE'; status: StepState;
  title: string; text: string; due: string | null; quotation_id?: string; amount?: string; invoice_id?: string | null }
/** Project Commercials, customer-safe (PCM): every figure formatted by the server from its one calculation. */
export type PaymentState = 'PAID' | 'OVERDUE' | 'PARTIALLY_PAID' | 'DUE' | 'UPCOMING' | 'UPDATING';
export interface NextPayment { label: string; amount: string; when: string; state: PaymentState; state_label: string; due_on: string | null }
export interface Commercials {
  available: boolean; message?: string;
  summary?: { currency: string; total_value: string; includes_gst: string | null; paid: string; outstanding: string; credit: string | null;
    next_payment: NextPayment | null; as_of: string };
  schedule?: { label: string; when: string; amount: string; gst_included: string | null; paid: string; remaining: string | null; state: PaymentState;
    state_label: string; requested: boolean; due_on: string | null }[];
  payments?: { amount: string; received_on: string; method: string; reference: string | null; note: string | null; status: 'RECORDED' | 'CORRECTED';
    status_label: string; correction: string | null; receipt: { id: string; number: string; status: 'VALID' | 'CANCELLED' } | null }[];
  invoices?: { id: string; number: string; issued_on: string | null; due_on: string | null; label: string | null; amount: string; status: string; status_label: string }[];
  receipts?: { id: string; number: string; issued_on: string; amount: string; status: 'VALID' | 'CANCELLED'; status_label: string }[];
  notices?: { code: string; message: string }[]; how_to_pay?: string;
}
export interface CommercialDocument {
  kind: 'INVOICE' | 'RECEIPT'; id: string; number: string; status: string; status_label: string; property_id: string;
  document: Record<string, any>; notices: { code: string; message: string }[]; html: string; filename: string; // eslint-disable-line @typescript-eslint/no-explicit-any
}
export type DocumentEntry = (QuotationSummary & { kind: string }) | { kind: 'INVOICE' | 'RECEIPT'; id: string; number: string; issued_on: string | null;
  amount: string; status: string; status_label: string; label?: string | null; due_on?: string | null };
export interface Entry { code: string; text: string; category?: string; status?: string; stage?: string; label?: string; duration?: string | null }
export interface PropertyCard {
  id: string; property: { reference: string; configuration: string | null; locality: string | null; city: string | null };
  enquiry: { reference: string }; headline: string; next_step: Omit<Step, 'key'> & { key: string } | null; attention_count: number;
  quotation: QuotationSummary | null; contact: Contact | null; project_tracking: boolean;
  payments: { available: boolean; outstanding?: string; next_payment?: NextPayment | null } | null;
}
export interface Included { title: string; kind: string; included_count: number; optional_count: number;
  items: { description: string; detail: string | null; status: string; dimensions?: { label: string; value: string }[] }[] }
export interface PropertyView extends PropertyCard {
  journey: Step[]; attention: Attention[]; quotations: QuotationSummary[]; documents: DocumentEntry[]; commercials: Commercials | null;
  included: Included[] | null;
  commitments: null | { source: string | null; inclusions: Entry[] | null; warranty: string[] | null; manufacturer_warranty_note: string | null;
    handover: Entry[] | null; care: Entry[] | null; next_steps: Entry[] | null;
    payment_schedule: { label: string; share: string; trigger: string; amount?: string | null }[] | null; payment_safety: string | null };
  responsibilities: null | { client: Entry[] | null; site_readiness: Entry[] | null };
  support: null | { contacts: Omit<Contact, 'source'>[]; escalation: string | null };
}
export interface Home { customer: { name: string }; enquiries: { reference: string; relationship: string; closed: boolean; properties: PropertyCard[] }[];
  project_tracking_available: boolean }
export interface QuotationPage extends Omit<Page, 'link'> { summary: QuotationSummary }

const BASE = '/api/v1/public/portal';
const STORE = 'vs-portal-session';
export const HEADER = 'X-Veda-Portal';

export function takeLinkToken(): string | null {
  const token = fragmentParam('t');
  if (window.location.hash) history.replaceState(null, '', window.location.pathname);
  return token;
}

export function sessionToken(): string | null {
  try { return sessionStorage.getItem(STORE); } catch { return memory; }
}

let memory: string | null = null; // storage unavailable (private mode): this page's lifetime only

export function keepSession(token: string): void {
  memory = token;
  try { sessionStorage.setItem(STORE, token); } catch { /* memory only */ }
}

export function forgetSession(): void {
  memory = null;
  try { sessionStorage.removeItem(STORE); } catch { /* nothing stored */ }
}

function headers(): Record<string, string> {
  const token = sessionToken();
  return token ? { [HEADER]: token } : {};
}

export const portalApi = {
  requestLink: (email: string) =>
    api.request<{ sent: boolean; message: string }>(`${BASE}/sign-in`, { method: 'POST', anonymous: true, body: { email } }),
  startSession: (token: string) =>
    api.request<{ token: string; expires_on: string }>(`${BASE}/session`, { method: 'POST', anonymous: true, body: { token } }),
  signOut: () => api.request(`${BASE}/sign-out`, { method: 'POST', anonymous: true, headers: headers() }),
  home: () => api.request<Home>(`${BASE}/home`, { anonymous: true, headers: headers() }),
  property: (id: string) => api.request<PropertyView>(`${BASE}/properties/${encodeURIComponent(id)}`, { anonymous: true, headers: headers() }),
  quotation: (id: string) => api.request<QuotationPage>(`${BASE}/quotations/${encodeURIComponent(id)}`, { anonymous: true, headers: headers() }),
  document: (kind: 'invoices' | 'receipts', id: string) =>
    api.request<CommercialDocument>(`${BASE}/${kind}/${encodeURIComponent(id)}`, { anonymous: true, headers: headers() }),
};

// --- staff (bearer session; portal.access.* permissions) ---------------------------------------------------------------
export interface AccessRow {
  id: string; version: number; relationship: string; status: 'ACTIVE' | 'REVOKED';
  account: { display_name: string; email: string; status: string; last_signed_in_on: string | null };
  granted_on: string; granted_by: { id: string; display_name: string | null } | null; revoked_on: string | null;
  revoked_by: { id: string; display_name: string | null } | null; revoke_reason_code: string | null;
}

export const portalStaffApi = {
  list: (leadId: string) => api.get<AccessRow[]>(`/api/v1/leads/${leadId}/portal-access`),
  grant: (leadId: string, body: { email?: string; display_name?: string; relationship: string }, key: string) =>
    api.request<AccessRow[]>(`/api/v1/leads/${leadId}/portal-access`, { method: 'POST', body, idempotencyKey: key }),
  revoke: (row: AccessRow) =>
    api.request<AccessRow[]>(`/api/v1/portal-access/${row.id}/revoke`, { method: 'POST', body: {}, ifMatch: row.version }),
};

/** A transient failure: offline, rate limited or the server busy (retrying may help; nothing was refused). */
export function transient(p: { status: number; code?: string }): boolean {
  return p.status === 0 || p.code === 'NETWORK_ERROR' || p.status === 429 || p.status >= 500;
}

export const STATE_LABELS: Record<StepState, string> = {
  COMPLETED: 'Completed', IN_PROGRESS: 'In progress', ACTION_REQUIRED: 'Action required', UPCOMING: 'Upcoming',
  NOT_YET_AVAILABLE: 'Not yet available', INFORMATION: 'For your information',
};

export const RELATIONSHIPS: Record<string, string> = {
  PRIMARY_CUSTOMER: 'Primary customer', CO_OWNER: 'Co-owner', FAMILY_MEMBER: 'Family member', OTHER: 'Other',
};
