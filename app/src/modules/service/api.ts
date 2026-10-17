import { api, newIdempotencyKey } from '../../core/api/client.js';

/** Warranty and after-sales service (WSV), staff side. Every value is the server's; nothing is computed here. */
export interface Person { id: string; display_name: string | null }
export interface CoverageClass { code: string; label: string; covers: string; exclusions: string[]; status: string; starts_on: string | null;
  ends_on: string | null; conflict: boolean }
export interface Source { quotation_id: string; quotation_number: string; kind: string; version_no: number; variation_no: number; terms_version: string | null;
  snapshot_sha256: string; warranty: string[]; service_support: string[]; manufacturer_warranty_note: string | null;
  warranty_exclusions: { code: string; text: string }[] }
export interface Entitlement {
  registered: boolean; id?: string; project_id: string | null; handover_on?: string; registered_on?: string; registered_via?: string;
  terms_sha256?: string; status: string; status_label: string; coverage?: CoverageClass[]; sources?: Source[];
  handover?: { transition_id: string; handover_on: string; date_check: string | null; package_sha256: string | null; acknowledged_on: string | null };
  policy: { version: string; status: string; decisions: Record<string, { label: string; decided: boolean }> };
  project?: { id: string; project_number: string; status: string }; can_register?: boolean;
}
export interface RequestRow {
  id: string; version: number; request_number: string; status: string; category: string; category_label: string; priority: string;
  channel: 'PORTAL' | 'STAFF'; reported_on: string; property_id: string; project_id: string; owner: Person | null; service_class: string | null;
  outcome: string | null; closure_code: string | null; cycle: number; updated_on: string;
}
export interface Assessment { id: string; cycle: number; outcome: string; outcome_label: string; service_class: string | null; basis_kind: string | null;
  basis_path: string | null; as_of: string; coverage_status: string | null; explanation: string; internal_reason: string; period_basis: string | null;
  assessed_by: Person | null; assessed_on: string }
export interface Visit { id: string; version: number; visit_no: number; kind: 'INSPECTION' | 'SERVICE'; status: 'PLANNED' | 'DONE' | 'CANCELLED';
  planned_on: string; done_on: string | null; customer_note: string | null; internal_note: string | null; cancel_reason: string | null; done_by: Person | null }
export interface RequestDetail extends RequestRow {
  description: string; area: string | null; space_id: string | null; noticed_on: string | null; related_request_id: string | null;
  duplicate_of_id: string | null; rejections: number; closed_on: string | null; verified_by_kind: string | null; entitlement: Entitlement;
  assessments: Assessment[]; visits: Visit[];
  resolutions: { id: string; cycle: number; summary: string; internal_note: string | null; resolved_by: Person | null; resolved_on: string; outcome: string;
    decided_on: string | null; decided_by: Person | null; decided_by_customer: boolean }[];
  notes: { id: string; kind: string; visibility: 'CUSTOMER' | 'INTERNAL'; text: string; by: 'CUSTOMER' | null; author: Person | null; created_on: string }[];
  photos: { id: string; state: string; added_by: string; attachment_id: string }[];
  evidence: { id: string; attachment_id: string; customer_visible: boolean; caption: string | null; added_by: Person | null; added_on: string }[];
  actions: Record<string, boolean>;
  vocabulary: { categories: { code: string; label: string }[]; outcomes: { code: string; label: string }[]; closures: string[]; priorities: string[];
    visit_kinds: string[]; max_rejections: number };
  timeline?: { code: string; from: string | null; to: string | null; detail: Record<string, unknown>; by: 'CUSTOMER' | null; actor: Person | null; at: string }[];
}
type Body = Record<string, unknown>;
const BASE = '/api/v1/service-requests';
const at = (r: { id: string }) => `${BASE}/${r.id}`;

export const serviceApi = {
  list: (status = 'OPEN') => api.request<RequestRow[]>(BASE, { query: { status } }),
  get: (id: string) => api.get<RequestDetail>(`${BASE}/${id}`),
  act: (r: RequestDetail, path: string, body: Body = {}) => api.post<RequestDetail>(`${at(r)}/${path}`, body, { ifMatch: r.version }),
  entitlement: (projectId: string) => api.get<Entitlement>(`/api/v1/warranty/projects/${projectId}`),
  register: (projectId: string) => api.post<Entitlement>('/api/v1/warranty/entitlements', { project_id: projectId }, { idempotencyKey: newIdempotencyKey() }),
};

export const STATUS: Record<string, [string, string]> = {
  REPORTED: ['Reported', 'action'], INFORMATION_REQUESTED: ['Waiting for the customer', 'info'], TRIAGED: ['Triaged', 'action'],
  ASSESSED: ['Coverage decided', 'action'], AWAITING_COMMERCIAL_AGREEMENT: ['Not covered: awaiting agreement', 'gating'],
  IN_PROGRESS: ['In progress', 'action'], RESOLVED: ['Awaiting verification', 'info'], CLOSED: ['Closed', 'ok'],
};
export const FILTERS: [string, string][] = [['OPEN', 'Open'], ['MINE', 'Mine'], ['WAITING_FOR_CUSTOMER', 'Waiting for the customer'],
  ['AWAITING_VERIFICATION', 'Awaiting verification'], ['AWAITING_COMMERCIAL_AGREEMENT', 'Awaiting agreement'], ['CLOSED', 'Closed']];
