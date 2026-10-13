import { api } from '../../core/api/client.js';

/** Types and calls for the MTQ B2-B4 commercial API. Every route answers 404 while its feature is off
 * (VEDA_MTQ_ESTIMATION_ENABLED for scope, BOQ and estimates; VEDA_MTQ_QUOTATION_ENABLED for quotations). */

const key = () => crypto.randomUUID().replace(/-/g, '');

export interface Issue { code: string; severity?: string; kind?: string; message?: string; decision?: string | null; reason?: string }
export interface Lineage { stale: boolean; reasons: { code: string; message: string }[] }

export interface Requirement {
  id: string; version: number; space_id: string | null; space_label: string | null; requirement_type_code: string;
  label: string; necessity_code: string; status: string; classification: string; source_code: string; origin_code: string;
  source_ref: { rule_key?: string; fact?: string; ruleset_status?: string }; catalogue_mapped: boolean;
  decision_reason: string | null; notes: string | null;
}
export interface InputValue { value: string | null; unit?: string; source: string; explain: string }
export interface ScopeItem {
  id: string; version: number; requirement_id: string; space_id: string | null; space_label: string | null;
  item_type_code: string; label: string; origin_code: string; necessity_code: string; inclusion_code: string;
  catalogue_mapped: boolean; unmapped_reason: string | null; effective_options: Record<string, string>;
  finish_code: string | null; inputs: Record<string, InputValue>; dimension_overrides: Record<string, string>;
  override_reason: string | null; dimension_source_code: string; carried_from_item_id: string | null;
}
export interface Scope {
  id: string; version: number; revision_no: number; status: string; tier_code: string; measurement_revision_no: number;
  ruleset_version: string; ruleset_status: string; exclusions: { label: string; space_label: string | null }[];
  generation_run: { undecided_requirement_ids?: string[] }; lineage?: Lineage; items?: ScopeItem[]; snapshot_sha256: string | null;
}
export interface BoqLine {
  id: string; version: number; space_id: string | null; space_label: string | null; label: string; uom_code: string | null;
  unit_text: string; formula_kind: string; derivation: string; calculated_quantity_centi: number | null;
  override_quantity_centi: number | null; override_reason: string | null; final_quantity_centi: number | null;
  is_optional: boolean; dimension_source_code: string; status: string; issues: Issue[];
}
export interface Boq {
  id: string; version: number; revision_no: number; status: string; scope_revision_no: number; measurement_revision_no: number;
  catalogue_card_version: string; quantity_engine_version: string; issues: Issue[]; lineage: Lineage;
  summary: { issue_counts?: { blocking: number; warning: number }; project?: { label: string; uom_code: string; quantity_centi: number; is_optional: boolean }[];
    assumptions?: { label: string; space_label: string | null; derivation: string }[] };
  lines?: BoqLine[];
}
export interface EstimateLine {
  id: string; space_id: string | null; space_label: string | null; label: string; component_code: string; category_code: string;
  quantity_centi: number | null; uom_code: string | null; rate_minor: number | null; rate_status: string; rate_note: string | null;
  amount_minor: number | null; discount_minor: number; is_optional: boolean; finish_code: string | null;
}
export interface Adjustment { id: string; version: number; scope_code: string; kind_code: string; value_bp: number | null;
  amount_minor: number | null; base_minor: number; discount_minor: number; post_minor: number; reason: string; status: string;
  authority_code: string | null }
export interface View { key: string | null; label: string; amount_minor: number; discount_minor: number; optional_minor: number; unpriced_lines: number }
export interface Estimate {
  id: string; version: number; revision_no: number; status: string; tier_code: string; boq_id: string; boq_revision_no: number;
  rate_card_version: string | null; subtotal_minor: number; optional_minor: number; discount_minor: number; taxable_minor: number;
  tax_status: string; tax_minor: number | null; total_minor: number | null; unpriced_lines: number; blockers: Issue[];
  lineage: Lineage; pricing_basis_code: string; views: { rooms: View[]; categories: View[]; components: View[] };
  lines?: EstimateLine[]; adjustments?: Adjustment[]; discount_policy?: { enabled: boolean; message?: string; self_limit_bp?: number; max_bp?: number };
}
export interface QuotationLine { id: string; description: string; detail: string | null; quantity_centi: number | null; uom_code: string | null;
  amount_minor: number | null; is_priced: boolean; is_optional: boolean; is_mandatory: boolean; change_code: string; delta_amount_minor: number | null }
export interface Quotation {
  id: string; version: number; label: string; quotation_number: string; version_no: number; quotation_kind: string; status: string;
  title: string; cover_note: string | null; base_total_minor: number; optional_minor: number; discount_minor: number;
  taxable_minor: number; tax_status: string; tax_minor: number | null; total_minor: number | null; customer_issuable: boolean;
  blockers: Issue[]; valid_until: string | null; snapshot_sha256: string | null; snapshot_verified: boolean | null;
  lineage: { estimate_revision_no: number; boq_revision_no: number; scope_revision_no: number; measurement_revision_no: number; cost_estimate_id: string };
  sections?: { id: string; title: string; section_code: string; subtotal_minor: number; lines: QuotationLine[] }[];
  events?: { event_code: string; occurred_on: string }[];
}
export interface Journey {
  property_number: string; current_measurement_set: { id: string; revision_no: number; survey_level_code: string } | null;
  ruleset: { version: string; status: string }; requirements: Record<string, number>; scopes: Scope[]; boqs: Boq[];
  cost_estimates?: Estimate[]; quotations?: Quotation[];
}
export interface PolicyView { version: string; status: string; decisions: Record<string, { label: string; decided: boolean }> }

const P = '/api/v1';
export const commercial = {
  journey: (id: string) => api.get<Journey>(`${P}/properties/${id}/commercial`),
  policy: () => api.get<PolicyView>(`${P}/mtq/commercial-policy`),
  requirements: (id: string) => api.get<Requirement[]>(`${P}/properties/${id}/requirements`),
  seed: (id: string) => api.request(`${P}/properties/${id}/requirements/seed`, { method: 'POST', idempotencyKey: key() }),
  addRequirement: (id: string, body: Record<string, unknown>) =>
    api.request<Requirement>(`${P}/properties/${id}/requirements`, { method: 'POST', body, idempotencyKey: key() }),
  decide: (r: Requirement, status: string, reason?: string) =>
    api.request<Requirement>(`${P}/requirements/${r.id}/decision`, { method: 'POST', body: { status, reason: reason || null }, ifMatch: r.version, idempotencyKey: key() }),
  scope: (id: string) => api.get<Scope>(`${P}/scopes/${id}`),
  draftScope: (id: string, tier: string) => api.request<Scope>(`${P}/properties/${id}/scopes`, { method: 'POST', body: { tier_code: tier }, idempotencyKey: key() }),
  refreshScope: (s: Scope) => api.request<Scope>(`${P}/scopes/${s.id}/refresh`, { method: 'POST', ifMatch: s.version }),
  confirmScope: (s: Scope) => api.request<Scope>(`${P}/scopes/${s.id}/confirm`, { method: 'POST', ifMatch: s.version, idempotencyKey: key() }),
  patchItem: (i: ScopeItem, body: Record<string, unknown>) => api.request<ScopeItem>(`${P}/scope-items/${i.id}`, { method: 'PATCH', body, ifMatch: i.version }),
  boq: (id: string) => api.get<Boq>(`${P}/boqs/${id}`),
  generateBoq: (scopeId: string) => api.request<Boq>(`${P}/scopes/${scopeId}/boqs`, { method: 'POST', idempotencyKey: key() }),
  overrideLine: (l: BoqLine, quantity_centi: number, reason: string) =>
    api.request<Boq>(`${P}/boq-lines/${l.id}/override`, { method: 'POST', body: { quantity_centi, reason }, ifMatch: l.version }),
  clearOverride: (l: BoqLine) => api.request<Boq>(`${P}/boq-lines/${l.id}/override`, { method: 'DELETE', ifMatch: l.version }),
  reviewBoq: (b: Boq) => api.request<Boq>(`${P}/boqs/${b.id}/review`, { method: 'POST', ifMatch: b.version, idempotencyKey: key() }),
  boqDiff: (a: string, b: string) => api.get<{ lines: { change: string; label: string; from_quantity_centi: number | null; to_quantity_centi: number | null }[] }>(`${P}/boqs/${a}/diff/${b}`),
  estimate: (id: string) => api.get<Estimate>(`${P}/cost-estimates/${id}`),
  price: (boqId: string, tier: string) => api.request<Estimate>(`${P}/boqs/${boqId}/cost-estimates`, { method: 'POST', body: { tier_code: tier }, idempotencyKey: key() }),
  approveEstimate: (e: Estimate) => api.request<Estimate>(`${P}/cost-estimates/${e.id}/approve`, { method: 'POST', ifMatch: e.version, idempotencyKey: key() }),
  discount: (e: Estimate, body: Record<string, unknown>) => api.request<Estimate>(`${P}/cost-estimates/${e.id}/adjustments`, { method: 'POST', body, idempotencyKey: key() }),
  decideDiscount: (a: Adjustment, decision: string) => api.request<Estimate>(`${P}/estimate-adjustments/${a.id}/decision`, { method: 'POST', body: { decision }, ifMatch: a.version, idempotencyKey: key() }),
  quotation: (id: string) => api.get<Quotation>(`${P}/quotations/${id}`),
  document: (id: string) => api.get<{ document: Record<string, unknown>; html: string }>(`${P}/quotations/${id}/document`),
  createQuotation: (estimateId: string) => api.request<Quotation>(`${P}/cost-estimates/${estimateId}/quotations`, { method: 'POST', body: {}, idempotencyKey: key() }),
  quotationAction: (q: Quotation, action: string, body?: Record<string, unknown>) =>
    api.request<Quotation>(`${P}/quotations/${q.id}/${action}`, { method: 'POST', body, ifMatch: q.version, idempotencyKey: key() }),
  variation: (q: Quotation, estimateId: string) => api.request<Quotation>(`${P}/quotations/${q.id}/variations`, { method: 'POST', body: { cost_estimate_id: estimateId }, idempotencyKey: key() }),
};
