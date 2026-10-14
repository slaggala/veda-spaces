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
}

const BASE = '/api/v1/public/proposal';
const STORE = 'vs-proposal-link';
export const HEADER = 'X-Veda-Proposal';
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
  };
}

// --- staff (bearer session; proposal.* permissions) --------------------------------------------------------------------
export interface Grant {
  id: string; version: number; quotation_id: string; quotation_number: string; version_no: number; recipient_kind: string;
  recipient_label: string | null; status: string; expires_on: string; first_viewed_on: string | null; last_viewed_on: string | null;
  view_count: number; revoke_reason_code: string | null; shared_on: string; token?: string; link?: string;
}
export interface Preview { frozen: boolean; status: string; watermark?: string; proposal: Proposal }

const P = '/api/v1';
export const staffProposal = {
  grants: (quotationId: string) => api.get<Grant[]>(`${P}/quotations/${quotationId}/access-grants`),
  share: (quotationId: string, body: { recipient_kind: string; recipient_label?: string | null; expires_in_days: number }) =>
    api.request<Grant>(`${P}/quotations/${quotationId}/access-grants`, { method: 'POST', body, idempotencyKey: newKey() }),
  rotate: (g: Grant) => api.request<Grant>(`${P}/proposal-access-grants/${g.id}/rotate`, { method: 'POST', ifMatch: g.version, idempotencyKey: newKey() }),
  revoke: (g: Grant) => api.request<Grant>(`${P}/proposal-access-grants/${g.id}/revoke`, { method: 'POST', ifMatch: g.version }),
  preview: (quotationId: string) => api.get<Preview>(`${P}/quotations/${quotationId}/proposal-preview`),
};

/** A staff preview as a page model: the customer's view with no live state and no actions. */
export function previewPage(p: Preview): Page {
  const state = p.status === 'ACCEPTED' ? 'ACCEPTED' : p.status === 'REJECTED' ? 'DECLINED' : p.status === 'EXPIRED' ? 'EXPIRED' : 'OPEN';
  return { state, link: { expires_on: '', status: 'PREVIEW' }, proposal: p.proposal, history: [], notices: [], actions: [],
    capabilities: { interaction: false, acceptance: false } };
}
