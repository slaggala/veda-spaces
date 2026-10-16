import { api, newIdempotencyKey } from '../../core/api/client.js';

/**
 * The Project Commercials staff API (every route answers 404 while VEDA_PROJECT_COMMERCIALS_ENABLED is off). Money is
 * integer paise (`*_minor`); every figure the page shows comes formatted from the server, which computes the position
 * once (`commercials.position`). The page never adds, subtracts or rounds money: it only converts what staff type
 * (rupees) into paise, exactly, from the text (`rupeesToPaise`). A payment always carries an Idempotency-Key (one per
 * dialog), so a double click or a retry records it once.
 */

const BASE = '/api/v1/commercials';

export interface Person { id: string; display_name: string | null }
export type InstalmentState = 'PAID' | 'OVERDUE' | 'PARTIALLY_PAID' | 'DUE' | 'UPCOMING';
export interface Position {
  currency: string; value_minor: number; value: string; tax_minor: number | null; tax: string | null; paid_minor: number; paid: string;
  outstanding_minor: number; outstanding: string; credit_minor: number; credit: string | null;
  schedule_state: 'IN_BALANCE' | 'REVISION_REQUIRED' | 'NONE'; unscheduled_minor: number; unscheduled: string;
  next_instalment_id: string | null; as_of: string;
}
export interface Header {
  id: string; version: number; quotation_number: string; base_quotation: { id: string; reference: string | null };
  lead: { id: string; name: string | null; reference: string | null; erased: boolean };
  property: { id: string; reference: string | null; city: string | null }; opened_on: string;
}
export interface AccountRow extends Header {
  position: Position; next: { label: string; amount: string; state: InstalmentState; due_on: string | null } | null; overdue: number;
}
export interface Line {
  id: string; position: number; label: string; when: string; amount_minor: number; amount: string; gst_included: string | null;
  share: string | null; applied_minor: number; applied: string; remaining_minor: number; remaining: string; state: InstalmentState;
  state_label: string; requested_on: string | null; requested_by: Person | null; due_on: string | null;
  invoice: { id: string; number: string | null; status: 'DRAFT' | 'ISSUED' } | null;
}
export interface Payment {
  id: string; amount_minor: number; amount: string; received_on: string; method_code: string; method: string;
  external_reference: string | null; customer_note: string | null; internal_note: string | null; recorded_on: string;
  recorded_by: Person | null; status: 'RECORDED' | 'REVERSED';
  reversal: { reason_code: string; note: string | null; reversed_on: string; reversed_by: Person | null } | null;
  receipt: { id: string; number: string } | null;
}
export interface Invoice {
  id: string; version: number; status: 'DRAFT' | 'ISSUED' | 'CANCELLED'; number: string | null; instalment_id: string;
  label: string | null; amount_minor: number; amount: string; gst_included: string | null; due_on: string | null;
  customer_note: string | null; drafted_on: string; drafted_by: Person | null; issued_on: string | null; issued_by: Person | null;
  cancelled_on: string | null; cancelled_by: Person | null; cancel_reason: string | null;
}
export interface Detail extends Header {
  position: Position;
  baseline: { sequence_no: number; kind: 'ORIGINAL' | 'VARIATION'; quotation_id: string; reference: string; accepted_total: string;
    accepted_gst: string | null; value: string; decided_on: string; baseline_sha256: string; snapshot_sha256: string }[];
  schedule: { id: string; revision_no: number; source: string; reason: string | null; total: string; lines: Line[] } | null;
  revisions: { id: string; revision_no: number; status: string; source: string; reason: string | null; total: string;
    created_on: string; created_by: Person | null; superseded_on: string | null }[];
  payments: Payment[]; invoices: Invoice[]; problems: { code: string; message: string }[];
  policy: { version: string; status: string; decisions: Record<string, { label: string; decided: boolean }> };
  capabilities: { writable: boolean; manage_schedule: boolean; record_payment: boolean; reverse_payment: boolean; issue_invoice: boolean;
    view_audit: boolean; invoice_issuable: boolean };
  methods: { code: string; label: string }[]; reversal_reasons: string[];
}
export interface Candidate { quotation_id: string; reference: string; quotation_number: string; lead: { id: string; name: string | null };
  property: { id: string; reference: string | null }; accepted_total: string | null; decided_on: string | null }
export interface DocumentModel { title: string; number: string | null; date: string | null; [key: string]: unknown }
export interface InvoiceView extends Invoice {
  account_id: string; account_version: number;
  preview?: { draft: true; available: boolean; document?: DocumentModel; html?: string };
  document?: DocumentModel; html?: string; filename?: string;
}
export interface ReceiptView { id: string; number: string; payment_id: string; account_id: string; status: 'VALID' | 'CANCELLED';
  document: DocumentModel; html: string; filename: string }
export interface HistoryRow { id: string; code: string; entity_id: string | null; detail: Record<string, unknown>; at: string; by: Person | null }
export interface InstalmentInput { label: string; when: string; amount_minor: number; requested?: boolean; due_on?: string | null }

export const commercialsApi = {
  list: () => api.get<AccountRow[]>(BASE),
  candidates: () => api.get<Candidate[]>(`${BASE}/candidates`),
  open: (quotationId: string, key: string) =>
    api.request<Detail>(BASE, { method: 'POST', body: { quotation_id: quotationId }, idempotencyKey: key }),
  get: (id: string) => api.get<Detail>(`${BASE}/${encodeURIComponent(id)}`),
  history: (id: string) => api.get<HistoryRow[]>(`${BASE}/${encodeURIComponent(id)}/history`),
  revise: (a: Detail, reason: string, instalments: InstalmentInput[]) =>
    api.request<Detail>(`${BASE}/${a.id}/schedule`, { method: 'POST', body: { reason, instalments }, ifMatch: a.version }),
  request: (a: Detail, instalmentId: string, dueOn: string | null) =>
    api.request<Detail>(`${BASE}/${a.id}/instalments/${instalmentId}/request`, { method: 'POST', body: dueOn ? { due_on: dueOn } : {}, ifMatch: a.version }),
  pay: (a: Detail, body: Record<string, unknown>, key: string) =>
    api.request<Detail & { payment_id: string; receipt_id: string | null; replayed: boolean }>(`${BASE}/${a.id}/payments`,
      { method: 'POST', body, idempotencyKey: key }),
  reverse: (a: Detail, paymentId: string, body: { reason_code: string; note?: string }) =>
    api.request<Detail>(`${BASE}/${a.id}/payments/${paymentId}/reverse`, { method: 'POST', body, ifMatch: a.version }),
  draft: (a: Detail, body: Record<string, unknown>, key: string) =>
    api.request<InvoiceView>(`${BASE}/${a.id}/invoices`, { method: 'POST', body, idempotencyKey: key }),
  invoice: (id: string) => api.get<InvoiceView>(`/api/v1/commercial-invoices/${encodeURIComponent(id)}`),
  issue: (inv: { id: string; version: number }) =>
    api.request<InvoiceView>(`/api/v1/commercial-invoices/${inv.id}/issue`, { method: 'POST', body: {}, ifMatch: inv.version }),
  cancel: (inv: { id: string; version: number }, reason: string) =>
    api.request<InvoiceView>(`/api/v1/commercial-invoices/${inv.id}/cancel`, { method: 'POST', body: { reason }, ifMatch: inv.version }),
  abandon: (inv: { id: string; version: number }) =>
    api.request<Detail>(`/api/v1/commercial-invoices/${inv.id}/abandon`, { method: 'POST', body: {}, ifMatch: inv.version }),
  receipt: (id: string) => api.get<ReceiptView>(`/api/v1/commercial-receipts/${encodeURIComponent(id)}`),
};

export { newIdempotencyKey };

/** Rupees as typed (`12,500` or `12500.50`) → paise, exactly, from the text: never through a floating-point number. */
export function rupeesToPaise(text: string): number | null {
  const v = text.trim().replace(/,/g, '');
  const m = /^(0|[1-9]\d{0,11})(?:\.(\d{1,2}))?$/.exec(v);
  if (!m) return null;
  const paise = (m[2] ?? '').padEnd(2, '0');
  return Number(m[1]) * 100 + Number(paise);
}

/** Paise → the rupee text staff edit (the inverse of rupeesToPaise, exact for integers). */
export function paiseToRupees(minor: number): string {
  const sign = minor < 0 ? '-' : '';
  const abs = Math.abs(minor);
  const whole = Math.floor(abs / 100);
  const rest = abs % 100;
  return `${sign}${whole}${rest ? `.${String(rest).padStart(2, '0')}` : ''}`;
}

/** Save a frozen document's HTML (as the server sealed it) as a file. The page never renders that HTML itself. */
export function download(filename: string, htmlText: string): void {
  const url = URL.createObjectURL(new Blob([htmlText], { type: 'text/html;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export const STATE_TEXT: Record<InstalmentState, string> = {
  PAID: 'Paid', OVERDUE: 'Overdue', PARTIALLY_PAID: 'Partly paid', DUE: 'Due', UPCOMING: 'Upcoming',
};
export const REVERSAL_TEXT: Record<string, string> = {
  RECORDED_IN_ERROR: 'Recorded in error', DUPLICATE: 'Recorded twice', PAYMENT_RETURNED: 'Payment returned (did not clear)', OTHER: 'Other reason',
};
