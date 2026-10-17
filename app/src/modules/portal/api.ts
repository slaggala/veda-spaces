import { api } from '../../core/api/client.js';
import { fragmentParam } from '../../core/router/next.js';
import type { Page } from '../proposal/api.js';

/**
 * The Customer Project Portal API (CPP). A customer never holds a staff token: the portal session travels only in the
 * X-Veda-Portal header and is kept in this tab's sessionStorage (gone when the tab closes; the same choice as the CQX
 * proposal link). The emailed sign-in link carries its one-time token in the URL fragment, which browsers never send to
 * a server; `takeLinkToken` reads it and scrubs the address bar at once.
 */

export type StepState = 'COMPLETED' | 'IN_PROGRESS' | 'ACTION_REQUIRED' | 'UPCOMING' | 'NOT_YET_AVAILABLE' | 'INFORMATION' | 'BLOCKED';
export interface Step { key: string; label: string; state: StepState; detail: string; date: string | null }
export interface QuotationSummary {
  id: string; reference: string; title: string; kind: 'QUOTATION' | 'VARIATION'; version_no: number;
  state: 'OPEN' | 'ACCEPTED' | 'DECLINED' | 'EXPIRED' | 'SUPERSEDED' | 'UNAVAILABLE'; status: StepState; status_label: string;
  issued_on: string | null; valid_until: string | null; days_left: number | null; total: string | null; currency: string | null;
}
export interface Contact { source: 'QUOTATION' | 'CONSULTANT'; name: string | null; role: string | null; phone: string | null;
  email: string | null; hours: string | null }
export interface Attention { kind: 'QUOTATION_DECISION' | 'PROJECT_ACTION' | 'SITE_READINESS' | 'SITE_VISIT' | 'PAYMENT_DUE' | 'HANDOVER_ACKNOWLEDGEMENT'; status: StepState;
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
/** A document staff explicitly shared on the project (CPP-D04): an image, served only through the portal session. */
export interface ProjectDocument { kind: 'PROJECT_DOCUMENT'; id: string; document_class: string; label: string; title: string; published_on: string;
  width: number | null; height: number | null; project_id?: string }
export type DocumentEntry = { kind: 'WARRANTY_SUMMARY'; id: string; title: string; issued_on: string; project_id: string } | (QuotationSummary & { kind: string }) | { kind: 'INVOICE' | 'RECEIPT'; id: string; number: string; issued_on: string | null;
  amount: string; status: string; status_label: string; label?: string | null; due_on?: string | null } | ProjectDocument;
export interface Entry { code: string; text: string; category?: string; status?: string; stage?: string; label?: string; duration?: string | null }
export interface PropertyCard {
  id: string; property: { reference: string; configuration: string | null; locality: string | null; city: string | null };
  enquiry: { reference: string }; headline: string; next_step: Omit<Step, 'key'> & { key: string } | null; attention_count: number;
  quotation: QuotationSummary | null; contact: Contact | null; project_tracking: boolean;
  payments: { available: boolean; outstanding?: string; next_payment?: NextPayment | null } | null;
}
/** Project delivery (PEX), customer-safe: built by the server from records staff marked visible, in customer words. */
export interface DeliveryProject {
  id: string; status: 'ACTIVE' | 'HANDED_OVER'; phase: { code: string; label: string };
  work: { items: { label: string; state: StepState; detail: string; completed_on: string | null }[]; counts: Record<string, number> };
  paused: { text: string; state: StepState; who: 'YOU' | 'VEDA_SPACES' }[];
  next_date: { label: string; date: string } | null;
  quality: { checks_passed: number; being_corrected: number };
  snags: { number: number; title: string; status: string; state: StepState }[];
  reports: { number: number; description: string; area: string | null; status: string; outcome: string | null; response: string | null; snag_number: number | null }[];
  can_report: boolean;
  handover: { state: StepState; label: string; date: string | null; remaining: { label: string; count: number }[] };
  documents?: ProjectDocument[];
  package: null | { id: string; number: number; content_sha256: string; status: 'READY_TO_REVIEW' | 'BEING_UPDATED' | 'HANDED_OVER';
    work_completed: { label: string; finished_on: string | null }[]; quality: { checks_passed: number; corrected_after_failure: number };
    snags: { fixed_and_verified: number; open_minor: { number: number; title: string }[] }; documents: ProjectDocument[]; documents_note: string | null;
    warranty_note: string; acknowledged_on: string | null; can_acknowledge: boolean };
}
export interface Included { title: string; kind: string; included_count: number; optional_count: number;
  items: { description: string; detail: string | null; status: string; dimensions?: { label: string; value: string }[] }[] }
/** Warranty and after-sales service (WSV), customer-safe: statements verbatim, statuses in plain words, no internal note. */
export interface WarrantySummary {
  state: 'BEFORE_HANDOVER' | 'BEING_PREPARED' | 'REGISTERED'; message?: string; id?: string; handed_over_on?: string; status?: string;
  status_label?: string; period_note?: string | null;
  coverage?: { label: string; covers: string; exclusions: string[]; status: string; status_label: string; starts_on: string | null; ends_on: string | null }[];
  statements?: { kind: string; text: string; source: string }[]; exclusions?: string[]; manufacturer_notes?: string[]; policy_url?: string | null;
}
export interface ServiceRequestView {
  id: string; reference: string; status: string; status_label: string; next: 'YOU' | 'VEDA_SPACES' | null; category: string; description: string;
  area: string | null; noticed_on: string | null; reported_on: string; project_id: string;
  photos: { id: string; state: 'AVAILABLE' | 'CHECKING' | 'NOT_AVAILABLE'; added_by: 'YOU' | 'VEDA_SPACES' }[];
  messages: { from: 'YOU' | 'VEDA_SPACES'; label: string; text: string; on: string }[];
  coverage: { outcome: string; label: string; explanation: string; chargeable_note: string | null } | null;
  visits: { kind: string; status: string; planned_on: string; done_on: string | null; note: string | null }[];
  resolution: { summary: string; outcome: string } | null; evidence: { id: string; caption: string | null }[];
  can_add_information: boolean; can_add_photos: boolean; can_confirm: boolean; can_reject: boolean; can_withdraw: boolean;
}
export interface WarrantyView {
  available: boolean; categories: { code: string; label: string }[]; max_photos: number;
  projects: { id: string; handed_over: boolean; warranty: WarrantySummary; requests: ServiceRequestView[]; can_report: boolean }[];
}
export interface PhotoUpload { required: boolean; method?: string; url?: string; fields?: Record<string, string>; then?: string }

export interface PropertyView extends PropertyCard {
  journey: Step[]; attention: Attention[]; quotations: QuotationSummary[]; documents: DocumentEntry[]; commercials: Commercials | null;
  included: Included[] | null;
  commitments: null | { source: string | null; inclusions: Entry[] | null; warranty: string[] | null; manufacturer_warranty_note: string | null;
    handover: Entry[] | null; care: Entry[] | null; next_steps: Entry[] | null;
    payment_schedule: { label: string; share: string; trigger: string; amount?: string | null }[] | null; payment_safety: string | null };
  responsibilities: null | { client: Entry[] | null; site_readiness: Entry[] | null };
  support: null | { contacts: Omit<Contact, 'source'>[]; escalation: string | null };
  delivery: { available: boolean; projects: DeliveryProject[] } | null;
  warranty?: WarrantyView | null;
}
export interface Home { customer: { name: string }; enquiries: { reference: string; relationship: string; closed: boolean; properties: PropertyCard[] }[];
  project_tracking_available: boolean; delivery_available?: boolean }
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
  /** Report an issue (PEX-D01). The key makes a retry the same report, never a second one. */
  report: (propertyId: string, projectId: string, body: { description: string; area?: string }, key: string) =>
    api.request<{ reference: string; received: boolean; delivery: DeliveryProject }>(
      `${BASE}/properties/${encodeURIComponent(propertyId)}/projects/${encodeURIComponent(projectId)}/reports`,
      { method: 'POST', anonymous: true, headers: headers(), body, idempotencyKey: key }),
  /** Report a problem after handover (WSV). The key makes a retry the same request, never a second one. */
  serviceSubmit: (propertyId: string, body: Record<string, unknown>, key: string) =>
    api.request<{ request: ServiceRequestView }>(`${BASE}/properties/${encodeURIComponent(propertyId)}/service-requests`,
      { method: 'POST', anonymous: true, headers: headers(), body, idempotencyKey: key }),
  serviceAct: (propertyId: string, requestId: string, action: 'information' | 'confirm' | 'reject' | 'withdraw', body: Record<string, unknown> = {}) =>
    api.request<{ request: ServiceRequestView }>(`${BASE}/properties/${encodeURIComponent(propertyId)}/service-requests/${encodeURIComponent(requestId)}/${action}`,
      { method: 'POST', anonymous: true, headers: headers(), body }),
  photoDeclare: (propertyId: string, requestId: string, body: { mime_type: string; byte_size: number; sha256: string }, key: string) =>
    api.request<{ photo_id: string; upload: PhotoUpload }>(`${BASE}/properties/${encodeURIComponent(propertyId)}/service-requests/${encodeURIComponent(requestId)}/photos`,
      { method: 'POST', anonymous: true, headers: headers(), body, idempotencyKey: key }),
  photoContent: (propertyId: string, requestId: string, photoId: string, dataBase64: string) =>
    api.request(`${BASE}/properties/${encodeURIComponent(propertyId)}/service-requests/${encodeURIComponent(requestId)}/photos/${encodeURIComponent(photoId)}/content`,
      { method: 'PUT', anonymous: true, headers: headers(), body: { data_base64: dataBase64 } }),
  photoComplete: (propertyId: string, requestId: string, photoId: string) =>
    api.request<{ request: ServiceRequestView }>(`${BASE}/properties/${encodeURIComponent(propertyId)}/service-requests/${encodeURIComponent(requestId)}/photos/${encodeURIComponent(photoId)}/complete`,
      { method: 'POST', anonymous: true, headers: headers(), body: {} }),
  /** Confirm receipt of exactly this handover summary (by its digest); repeating it changes nothing. */
  acknowledge: (propertyId: string, projectId: string, packageId: string, sha: string) =>
    api.request<{ acknowledged_on: string; delivery: DeliveryProject }>(
      `${BASE}/properties/${encodeURIComponent(propertyId)}/projects/${encodeURIComponent(projectId)}/handover/acknowledge`,
      { method: 'POST', anonymous: true, headers: headers(), body: { package_id: packageId, content_sha256: sha } }),
};

/** A shared project document's image as a data: URL (the session travels in the header, never in a URL). */
export async function documentImage(propertyId: string, documentId: string, variant: 'thumb' | 'mobile' | 'desktop' = 'mobile'): Promise<string | null> {
  return portalImage(`/properties/${encodeURIComponent(propertyId)}/documents/${encodeURIComponent(documentId)}/content`, variant);
}

/** Any image the portal serves under the session (shared documents, request photos, shared evidence) as a data: URL. */
export async function portalImage(path: string, variant: 'thumb' | 'mobile' | 'desktop' = 'mobile'): Promise<string | null> {
  try {
    const r = await fetch(`${api.baseUrl}${BASE}${path}?variant=${variant}`, { headers: headers(), credentials: 'include', cache: 'no-store' });
    if (!r.ok) return null;
    const blob = await r.blob();
    return await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : null);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

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
  NOT_YET_AVAILABLE: 'Not yet available', INFORMATION: 'For your information', BLOCKED: 'On hold',
};

export const RELATIONSHIPS: Record<string, string> = {
  PRIMARY_CUSTOMER: 'Primary customer', CO_OWNER: 'Co-owner', FAMILY_MEMBER: 'Family member', OTHER: 'Other',
};
