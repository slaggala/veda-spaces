import { api } from '../../core/api/client.js';
import type { PropertyView } from '../portal/api.js';
import type { Page } from '../proposal/api.js';

/**
 * Sales & Customer Acquisition (SCA), staff side. Every row is a read-only projection the server derives from records
 * other modules own (visits, quotations, proposal links, acceptances); nothing here is computed, stored or predicted.
 * Every route answers 404 while VEDA_SALES_EXPERIENCE_ENABLED is off.
 */
export interface Ref { code: string; label: string }
export interface Person { id: string; display_name: string | null }
export interface Stage { code: string; label: string; basis: string; basis_label: string; claimed_without_record: boolean }
export interface Visit { id: string; visit_number: string; status: string; scheduled_start_on: string | null; completed_on: string | null; property_id: string }
export interface QuotationFact { id: string; quotation_number: string; version_no: number; status: string; issued_on: string | null; valid_until: string | null;
  property_id: string }
export interface Facts {
  estimate: { reference: string; created_on: string; expires_on: string | null } | null;
  contacted_on: string | null;
  consultation_on: string | null;
  properties: string[];
  visits: Visit[];
  quotation: QuotationFact | null;
  quotations: number;
  accepted: { id: string; quotation_number: string; version_no: number; decided_on: string | null; method: string | null } | null;
  proposal: { shared_on: string | null; first_viewed_on: string | null; last_viewed_on: string | null; view_count: number; links: number; active_links: number } | null;
  customer_requests: { total: number; waiting_on_staff: number; waiting_on_customer: number };
  project: { id: string; project_number: string; stage_code: string; status: string } | null;
}
export type Quoted = { amount_minor: number; currency: string } | { withheld: true } | null;
export interface PipelineRow {
  lead: { id: string; lead_number: string; name: string; city: string | null; status: string; created_on: string };
  source: Ref | null;
  channel: Ref & { detail: string | null };
  stage: Stage;
  facts: Facts;
  quoted: Quoted;
  owner: Person | null;
  last_activity_on: string | null;
  next_follow_up_on: string | null;
  is_follow_up_overdue: boolean;
  attention: Ref[];
  customer_action: string | null;
  closed: { won_on: string | null; lost_on: string | null; lost_reason: Ref | null };
}
export interface PipelineMeta { page: number; limit: number; total: number; scanned: number; truncated: boolean; stage_counts: Record<string, number> }
export type StatusGroup = 'open' | 'won' | 'lost' | 'closed' | 'all';
export interface PipelineQuery { status: StatusGroup; stage?: string; attention?: string; channel?: string; owner?: string; q?: string; page?: number; limit?: number }

export type Tracking = 'TRACKED' | 'NOT_TRACKED';
export interface Counted { count: number | null; basis: string; tracking: Tracking }
export interface SiteEvent extends Counted { by_channel: Record<string, number> | null }
export interface Ratio { value: number | null; reason: 'NOT_TRACKED' | 'NO_DENOMINATOR' | null }
export interface Funnel {
  period: { from: string; to: string; timezone: string };
  as_of: string;
  site: Record<'site_visit' | 'estimator_started' | 'enquiry_started' | 'journey_viewed', SiteEvent>;
  estimates_completed: Counted;
  leads: (Ref & Counted)[];
  cohort: { size: number; truncated: boolean; claimed_stages_without_record: number };
  current_stages: (Ref & { count: number })[];
  ratios: Record<'estimator_start_to_estimate' | 'site_visit_to_enquiry' | 'enquiry_to_quotation' | 'quotation_to_acceptance' | 'enquiry_to_won' | 'decided_to_won', Ratio>;
  by_channel: (Ref & { leads: number; quotation_issued: number; accepted: number; won: number; lost: number })[];
  by_source: (Ref & { leads: number; won: number })[];
  lost_reasons: (Ref & { count: number })[];
  stalled: { quiet: number };
}

export interface JourneyStep { key: string; label: string; state: string; detail: string; date: string | null }
export interface Demo {
  demo: true; label: string; as_of: string;
  portal: PropertyView & { demo: true; label: string };
  proposal: Page & { demo: true; label: string };
  journey: JourneyStep[];
}

const BASE = '/api/v1/sales';

export const salesApi = {
  pipeline: (query: PipelineQuery) => api.get<PipelineRow[]>(`${BASE}/pipeline`, { ...query }),
  progression: (leadId: string) => api.get<PipelineRow>(`${BASE}/leads/${leadId}/progression`),
  funnel: (from: string, to: string) => api.get<Funnel>(`${BASE}/funnel`, { from, to }),
  demo: () => api.get<Demo>(`${BASE}/demo`),
};
