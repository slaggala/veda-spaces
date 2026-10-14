import { api } from '../../core/api/client.js';
import { fragmentParam } from '../../core/router/next.js';

/**
 * The customer proposal API (CQX). A customer has no session: the link's token travels only in the X-Veda-Proposal
 * header, never in a URL. The link carries it in the fragment (`/proposal#t=…`), which browsers never send to a server;
 * `takeToken` moves it into this tab's sessionStorage (gone when the tab closes) and scrubs the address bar at once, so
 * it does not stay in the visible URL, a bookmark or a shared screenshot.
 */

export interface ProposalLine {
  ref: string; description: string; detail: string | null; quantity: string | null; amount: string | null; priced: boolean;
  status: string; unit_rate?: string; change?: string; delta?: string | null; room_ref?: string | null; room_title?: string | null;
}
export interface Room {
  ref: string; title: string; kind: 'ROOM' | 'PROJECT' | 'CHANGES'; subtotal: string | null; lines: ProposalLine[];
  included_count: number; optional_count: number;
}
export interface Summary {
  base_total: string | null; discount?: string | null; taxable?: string | null; gst?: { status: string; amount: string | null };
  total: string | null; optional_total?: string | null; net_change?: string | null; currency: string;
}
export interface Proposal {
  schema: string; kind: 'QUOTATION' | 'VARIATION'; title: string; brand: { name: string; tagline: string }; reference: string;
  quotation_number: string; version_no: number; variation_no: number; issued_on: string; valid_until: string | null;
  subject: string; cover_note: string | null; property: { reference: string; configuration: string; city: string | null };
  snapshot_sha256: string | null; rooms: Room[]; optional_items: ProposalLine[]; summary: Summary;
  payment_schedule: { label: string; share: string; trigger: string }[]; warranty: string[]; service_support: string[];
  assumptions: string[]; exclusions: string[]; terms: string[]; terms_version: string | null; unit_rates_shown: boolean;
  sections: Record<string, string | null>;
}
export interface SpecCategory {
  label: string; summary: string; requirement: string; grade: string | null; thickness: string | null; finish: string | null;
  brand_examples: string | null; equivalent_rule: string; final_selection: string; warranty_summary: string;
}
export interface Specifications { name: string; version: string; summary: string; equivalent_policy: string; final_selection: string;
  lines: Record<string, SpecCategory[]> }
export interface MediaImage { title: string; alt: string; caption: string | null; label: 'Design reference' | 'Illustrative example';
  urls: { thumb?: string; mobile?: string; desktop?: string } }
export interface Pricing {
  currency: string; total: string | null; gst: { status: string; amount: string | null } | null; discount: string | null;
  base_total: string | null; optional_total: string | null; rooms: { ref: string; title: string; subtotal: string | null }[];
  milestones: { label: string; share: string; trigger: string }[]; valid_until: string | null; days_left: number | null;
  unit_rates_shown: boolean; package: string | null;
  alternatives: { reference: string; package: string | null; total: string | null; valid_until: string | null }[];
}
export interface Selections {
  items: { ref: string; state: 'NOT_SELECTED' | 'SELECTED' | 'DESELECTED' | 'REQUESTED_FOR_DISCUSSION'; priced: boolean }[];
  selected_refs: string[]; status: 'CALCULATED' | 'PRICE_CONFIRMATION_REQUIRED'; extra: string | null; total_with_selections: string | null;
}
export interface CustomerRequest {
  ref: string; category: string; category_label: string; line_ref: string | null; room: string | null; about_version: number;
  about_variation: number; message: string; requested_quantity: string | null; status: string; status_label: string;
  response: string | null; sent_on: string; responded_on: string | null; answered_by_revision: string | null;
}
export interface VariationView {
  reference: string; baseline_reference: string; status: string; net_change: string | null; gst: { status: string; amount: string | null };
  net_change_with_gst: string | null; accepted_value: string | null; value_if_accepted: string | null; issuable: boolean;
  kept_choices: { description: string; amount: string | null }[];
  changes: { ref: string; description: string; room: string | null; change: string; change_label: string; quantity_before: string | null;
    quantity_after: string | null; amount_before: string | null; amount_after: string | null; delta: string | null; priced: boolean }[];
}
export interface Comparison {
  from_version: number; to_version: number; total_before: string | null; total_after: string | null;
  changes: { change: 'ADDED' | 'CHANGED' | 'REMOVED'; description: string; room: string | null; before: string | null; after: string | null;
    status: string; quantity_before?: string | null; quantity_after?: string | null }[];
}
export interface TermsSection { code: string; title: string; items: string[]; available: boolean; sha256: string | null; required: boolean;
  acknowledged_on: string | null }
export interface Terms { sections: TermsSection[]; policy_decided: boolean; pending: string[] }
export interface Notice { code: string; message: string }
export interface Action { code: string; label: string; target: string }
export interface Page {
  state: 'OPEN' | 'SUPERSEDED' | 'EXPIRED' | 'ACCEPTED' | 'DECLINED' | 'UNAVAILABLE';
  link: { expires_on: string; status: string };
  proposal: Proposal;
  history: { version_no: number; issued_on: string | null }[];
  capabilities: { interaction: boolean; acceptance: boolean };
  notices: Notice[];
  actions: Action[];
  specifications?: Specifications | null;
  pricing?: Pricing;
  selections?: Selections;
  requests?: { can_ask: boolean; items: CustomerRequest[] };
  comparison_available?: boolean;
  terms?: Terms;
  variation?: VariationView;
  media?: { note: string; lines: Record<string, MediaImage[]>; rooms: Record<string, MediaImage | null> };
}

const BASE = '/api/v1/public/proposal';
const STORE = 'vs-proposal-link';
export const HEADER = 'X-Veda-Proposal';
/** Media URLs are API paths: images load from the API origin. */
export const mediaUrl = (path: string | undefined) => (path ? api.buildUrl(path) : '');
export const newKey = () => crypto.randomUUID().replace(/-/g, '');

/** The link's token: from the fragment on first open (then scrubbed), else from this tab's storage. */
export function takeToken(): string | null {
  const fromLink = fragmentParam('t');
  if (window.location.hash) history.replaceState(null, '', window.location.pathname);
  try {
    if (fromLink) sessionStorage.setItem(STORE, fromLink);
    return fromLink ?? sessionStorage.getItem(STORE);
  } catch {
    return fromLink; // storage unavailable (private mode): works until the page is reloaded
  }
}

export function forgetToken(): void {
  try { sessionStorage.removeItem(STORE); } catch { /* nothing stored */ }
}

export function proposalApi(token: string) {
  const headers = { [HEADER]: token };
  return {
    view: () => api.request<Page>(BASE, { anonymous: true, headers }),
    select: (line_ref: string, state: string) =>
      api.request<Selections>(`${BASE}/selections`, { method: 'POST', anonymous: true, headers, body: { line_ref, state }, idempotencyKey: newKey() }),
    acknowledge: (section: string, section_sha256: string) =>
      api.request<{ terms: Terms }>(`${BASE}/acknowledgements`, { method: 'POST', anonymous: true, headers, body: { section, section_sha256 } }),
    compare: () => api.request<{ comparison: Comparison | null }>(`${BASE}/comparison`, { anonymous: true, headers }),
    ask: (body: Record<string, unknown>, key: string) =>
      api.request<CustomerRequest[]>(`${BASE}/requests`, { method: 'POST', anonymous: true, headers, body, idempotencyKey: key }),
  };
}

// --- staff (bearer session; proposal.* permissions) --------------------------------------------------------------------
export interface Grant {
  id: string; version: number; quotation_id: string; quotation_number: string; version_no: number; recipient_kind: string;
  recipient_label: string | null; status: string; expires_on: string; first_viewed_on: string | null; last_viewed_on: string | null;
  view_count: number; revoke_reason_code: string | null; shared_on: string; token?: string; link?: string;
}
export interface Preview { frozen: boolean; status: string; watermark?: string; proposal: Proposal }
export interface StaffRequest {
  id: string; version: number; request_kind: string; category: string; version_no: number; variation_no: number; line_ref: string | null;
  room: string | null; message: string; requested_quantity: string | null; status: string; response: string | null;
  recipient_kind: string | null; sent_on: string; responded_on: string | null; resulting_quotation_id: string | null; resulting_label: string | null;
}
export interface Activity {
  selections: { line_ref: string; description: string | null; state: string; change_no: number; changed_on: string }[];
  summary: Selections;
  requests: StaffRequest[];
  acknowledgements: { section: string; recipient_kind: string; acknowledged_on: string; section_sha256: string; evidence_sha256: string }[];
}

const P = '/api/v1';
export const staffProposal = {
  grants: (quotationId: string) => api.get<Grant[]>(`${P}/quotations/${quotationId}/access-grants`),
  share: (quotationId: string, body: { recipient_kind: string; recipient_label?: string | null; expires_in_days: number }) =>
    api.request<Grant>(`${P}/quotations/${quotationId}/access-grants`, { method: 'POST', body, idempotencyKey: newKey() }),
  rotate: (g: Grant) => api.request<Grant>(`${P}/proposal-access-grants/${g.id}/rotate`, { method: 'POST', ifMatch: g.version, idempotencyKey: newKey() }),
  revoke: (g: Grant) => api.request<Grant>(`${P}/proposal-access-grants/${g.id}/revoke`, { method: 'POST', ifMatch: g.version }),
  preview: (quotationId: string) => api.get<Preview>(`${P}/quotations/${quotationId}/proposal-preview`),
  activity: (quotationId: string) => api.get<Activity>(`${P}/quotations/${quotationId}/customer-activity`),
  respond: (r: StaffRequest, status: string, response: string | null) =>
    api.request<StaffRequest>(`${P}/customer-requests/${r.id}/respond`, { method: 'POST', body: { status, response }, ifMatch: r.version }),
  link: (r: StaffRequest, resulting_quotation_id: string, response: string | null) =>
    api.request<StaffRequest>(`${P}/customer-requests/${r.id}/link`, { method: 'POST', body: { resulting_quotation_id, response }, ifMatch: r.version }),
  variationPreview: (quotationId: string) => api.get<VariationView>(`${P}/quotations/${quotationId}/variation-preview`),
  chain: (quotationId: string) => api.get<{ versions: { id: string; label: string; status: string }[] }>(`${P}/quotations/${quotationId}/chain`),
};

/** A staff preview as a page model: the customer's view with no live state and no actions. */
export function previewPage(p: Preview): Page {
  const state = p.status === 'ACCEPTED' ? 'ACCEPTED' : p.status === 'REJECTED' ? 'DECLINED' : p.status === 'EXPIRED' ? 'EXPIRED' : 'OPEN';
  return { state, link: { expires_on: '', status: 'PREVIEW' }, proposal: p.proposal, history: [], notices: [], actions: [],
    capabilities: { interaction: false, acceptance: false } };
}
