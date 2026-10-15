import { api } from '../../core/api/client.js';
import type { Information } from '../proposal/api.js';

/** Types and calls of the Customer Promise API (staff only; every route answers 404 while
 * VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED is off). Every write sends the version the page showed (If-Match). */

const BASE = '/api/v1/customer-promise';
const key = () => crypto.randomUUID().replace(/-/g, '');

export interface Person { id: string; display_name: string | null }
export interface VersionSummary {
  id: string; version: number; version_no: number; status: string; origin: string; content_version: string;
  change_summary: string | null; based_on_version: number | null; content_sha256: string;
  created_on: string | null; created_by: Person | null; updated_on: string | null;
  submitted_on: string | null; submitted_by: Person | null; approved_on: string | null; approved_by: Person | null;
  published_on: string | null; published_by: Person | null; published_sha256: string | null;
  superseded_on: string | null; superseded_by_version: number | null;
  effective: 'CURRENT' | 'HISTORICAL' | 'NOT_EFFECTIVE'; quotations: Record<string, number>;
}
export interface SectionReview { decision: string; by: Person | null; on: string | null; comment: string | null }
export interface SectionView {
  code: string; title: string; keys: string[]; sensitive: boolean; edit_permission: string; review_permission: string;
  changed: boolean; value: Record<string, unknown>; sha256: string; review: SectionReview | null; contributors: Person[];
  can_edit: boolean; can_review: boolean;
}
export interface Problem { section: string; code: string; message: string }
export interface ReviewRow { id: string; round: number; section: string; decision: string; comment: string | null; by: Person | null; on: string | null; current: boolean }
export interface EventRow { code: string; section: string | null; from: string | null; to: string | null; reason: string | null;
  detail: Record<string, unknown> | null; by: Person | null; on: string | null }
export interface VersionDetail extends VersionSummary {
  sections: SectionView[]; changed_sections: string[]; pending_reviews: string[]; problems: Problem[]; reviews: ReviewRow[];
  actions: { save: boolean; summary: boolean; discard: boolean; submit: boolean; approve: boolean; return: boolean; publish: boolean;
    preview: boolean; history: boolean };
  events?: EventRow[];
}
export interface AreaView { code: string; title: string; section: string | null; governed_by: string; status: string;
  structure_exists: boolean; owner_approved_content: boolean; customer_sees: string }
export interface Landing {
  authority: { state: string; register_reference: string | null; decided_on: string | null; message: string };
  published: VersionSummary | null; open: VersionSummary | null; pending_reviews: string[]; areas: AreaView[]; versions: number;
  effective_dating: string; actions: { create_draft: boolean; preview: boolean; history: boolean };
}
export interface Vocabulary {
  sections: { code: string; title: string; keys: string[]; sensitive: boolean; edit_permission: string; review_permission: string }[];
  areas: { code: string; title: string; section: string | null }[];
  contact_kinds: string[]; responsibility_categories: string[]; responsibility_statuses: string[]; readiness_categories: string[];
  readiness_statuses: string[]; site_work_categories: string[]; handover_categories: string[]; care_categories: string[];
  stages: string[]; limits: { copy: number; label: number; duration: number; summary: number };
}
export interface Change { section: string; change: string; subject: string; item: string | null; message: string; before: unknown; after: unknown }
export interface Changes { from: { pack_id: string; version_no: number; status: string } | null; to: { pack_id: string; version_no: number; status: string }; changes: Change[] }
export interface PreviewView { label: string; published: boolean; pack_id: string; version_no: number; status: string; content_version: string;
  information: Information; creates: Record<string, boolean> }

export const promiseApi = {
  landing: () => api.get<Landing>(BASE),
  vocabulary: () => api.get<Vocabulary>(`${BASE}/vocabulary`),
  versions: () => api.get<VersionSummary[]>(`${BASE}/versions`),
  version: (id: string) => api.get<VersionDetail>(`${BASE}/versions/${id}`),
  create: (body: { based_on_pack_id?: string; change_summary?: string | null }) =>
    api.post<VersionDetail>(`${BASE}/versions`, body, { idempotencyKey: key() }),
  summary: (v: VersionDetail, change_summary: string | null) =>
    api.patch<VersionDetail>(`${BASE}/versions/${v.id}`, { change_summary }, { ifMatch: v.version }),
  save: (v: VersionDetail, section: string, value: Record<string, unknown>) =>
    api.put<VersionDetail>(`${BASE}/versions/${v.id}/sections/${section}`, { value }, { ifMatch: v.version }),
  action: (v: VersionDetail, action: 'submit' | 'approve' | 'publish' | 'return' | 'discard', body?: Record<string, unknown>) =>
    // a draft is discarded through /abandon (no route path may contain "card": the rate-card exposure guard)
    api.post<VersionDetail>(`${BASE}/versions/${v.id}/${action === 'discard' ? 'abandon' : action}`, body ?? {}, { ifMatch: v.version }),
  review: (v: VersionDetail, section: string, decision: 'APPROVED' | 'CHANGES_REQUESTED', comment?: string) =>
    api.post<VersionDetail>(`${BASE}/versions/${v.id}/sections/${section}/review`, comment ? { decision, comment } : { decision }, { ifMatch: v.version }),
  changes: (id: string) => api.get<Changes>(`${BASE}/versions/${id}/changes`),
  preview: (id: string) => api.get<PreviewView>(`${BASE}/versions/${id}/preview`),
};
