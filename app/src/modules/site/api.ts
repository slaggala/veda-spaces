import { api } from '../../core/api/client.js';

/** Types and calls for the MTQ B1 site API (blueprint §11.1, B1 subset). Every route answers 404 while the feature
 * is off; callers treat a 404 on the first call as "not enabled here". */

export interface Space {
  id: string; version: number; property_id: string; parent_space_id: string | null; space_type_code: string;
  custom_type_label: string | null; label: string; instance_no: number; level_index: number; zone_code: string;
  sort_order: number; is_in_scope: boolean; space_template_key: string | null; template_version: string | null;
  attributes: Record<string, unknown>; counts_as_bedroom: boolean; counts_as_toilet: boolean;
}
export interface Property {
  id: string; version: number; property_number: string; lead_id: string; property_type_code: string;
  project_kind_code: string; configuration_label: string | null; display_label: string;
  derived_bedroom_count: number; derived_toilet_count: number; derived_level_count: number;
  derived_measured_floor_area_sqft_centi: number | null; built_up_area_sqft_centi: number | null;
  carpet_area_sqft_centi: number | null; city: string | null; locality: string | null;
  template_key: string | null; latest_verified_set: { id: string; revision_no: number } | null; spaces?: Space[];
}
export interface Visit {
  id: string; version: number; visit_number: string; property_id: string; lead_id: string; visit_type_code: string;
  status: string; survey_level_code: string; scheduled_start_on: string | null; started_on: string | null;
  assigned_to: { id: string; display_name: string | null } | null; allowed_transitions: string[];
  customer_contact_name: string | null; customer_contact_phone: string | null; access_notes: string | null;
}
export interface Opening {
  id?: string; client_ref: string; opening_type_code: string; width_mm: number; height_mm: number;
  sill_height_mm?: number | null; offset_from_wall_start_mm?: number | null; swing_code?: string | null;
  deducts_from_wall_area?: boolean; purpose_code?: string | null; depth_mm?: number | null; is_existing?: boolean;
}
export interface Obstruction { kind: string; offset_mm?: number | null; width_mm?: number | null; height_from_floor_mm?: number | null; height_mm?: number | null }
export interface Wall {
  id?: string; wall_index: number; client_ref?: string | null; label?: string | null; length_mm: number;
  height_mm?: number | null; wall_type_code: string; is_external?: boolean; is_proposed?: boolean;
  usable_for_code: string[]; obstructions: Obstruction[]; openings: Opening[];
}
export interface ElectricalPoint {
  id?: string; client_ref: string; point_type_code: string; status_code: string; wall_index?: number | null;
  from_offset_mm?: number | null; from_height_mm?: number | null; to_wall_index?: number | null;
  to_offset_mm?: number | null; to_height_mm?: number | null; sensor_type_code?: string | null;
  switching_code?: string | null; location_code?: string | null; quantity?: number; reason_code?: string | null;
  notes?: string | null;
}
export interface SpaceMeasurement {
  id: string; version: number; space_id: string; client_ref: string | null; shape_code: string;
  length_mm: number | null; width_mm: number | null; ceiling_height_mm: number | null; beam_bottom_height_mm: number | null;
  floor_to_lintel_mm: number | null; stated_floor_area_sqft_centi: number | null; polygon: number[][] | null;
  flooring_code: string | null; existing_condition_code: string | null; confidence_code: string; is_complete: boolean;
  attributes: Record<string, unknown>; derived_floor_area_sqft_centi: number | null; derived_perimeter_mm: number | null;
  derived_wall_area_net_sqft_centi: number | null; captured_by: string; claim_expires_on: string | null; walls: Wall[];
  electrical_points?: ElectricalPoint[];
}
export interface Note { id: string; client_ref: string | null; space_id: string | null; note_type_code: string; body: string }
export interface MeasurementSet {
  id: string; version: number; property_id: string; measurement_visit_id: string | null; revision_no: number;
  status: string; survey_level_code: string; method_code: string; unit_system_code: 'FT_IN' | 'MM'; captured_by: string;
  supersedes_set_id: string | null; rejection_reason: string | null; snapshot_sha256: string | null;
  summary: Record<string, number | string>; property_capture: Record<string, unknown>;
  spaces?: SpaceMeasurement[]; notes?: Note[];
}
export interface Problem { pointer: string; code: string; message: string; space?: string; acknowledgeable?: boolean }
export interface Readiness {
  survey_level: string; ready_to_submit: boolean; ready_to_verify: boolean; submit_problems: Problem[];
  verify_problems: Problem[]; usable_segments: Record<string, Record<string, number[][]>>;
}
export interface Attachment {
  id: string; version: number; entity_type: string; entity_id: string; category_code: string; scan_status: string;
  upload_status: string; available: boolean; width: number | null; height: number | null; byte_size: number;
  upload?: { required: boolean; method?: string; url?: string; fields?: Record<string, string>; then?: string };
}
export interface Templates {
  template_version: string;
  property_templates: Record<string, { property_type_code: string; configuration_label: string | null; spaces: Array<{ ref: string; label: string; optional?: boolean }> }>;
  space_templates: Record<string, { space_types: string[]; full_required: string[]; checklist: string[] }>;
}

export const site = {
  templates: () => api.request<Templates>('/api/v1/mtq/templates'),
  properties: (query: Record<string, string> = {}) => api.request<Property[]>('/api/v1/properties', { query }),
  property: (id: string) => api.request<Property>(`/api/v1/properties/${id}`),
  createProperty: (body: Record<string, unknown>) =>
    api.request<Property>('/api/v1/properties', { method: 'POST', body, idempotencyKey: crypto.randomUUID().replace(/-/g, '') }),
  patchProperty: (p: Property, body: Record<string, unknown>) =>
    api.request<Property>(`/api/v1/properties/${p.id}`, { method: 'PATCH', body, ifMatch: p.version }),
  addSpace: (propertyId: string, body: Record<string, unknown>) =>
    api.request<Space>(`/api/v1/properties/${propertyId}/spaces`, { method: 'POST', body }),
  patchSpace: (s: Space, body: Record<string, unknown>) =>
    api.request<Space>(`/api/v1/spaces/${s.id}`, { method: 'PATCH', body, ifMatch: s.version }),
  archiveSpace: (s: Space, reason: string) =>
    api.request<null>(`/api/v1/spaces/${s.id}`, { method: 'DELETE', body: { reason }, ifMatch: s.version }),
  orderSpaces: (propertyId: string, ids: string[]) =>
    api.request<Space[]>(`/api/v1/properties/${propertyId}/spaces/order`, { method: 'PUT', body: { space_ids: ids } }),
  visits: (query: Record<string, string>) => api.request<Visit[]>('/api/v1/measurement-visits', { query }),
  createVisit: (body: Record<string, unknown>) =>
    api.request<Visit>('/api/v1/measurement-visits', { method: 'POST', body, idempotencyKey: crypto.randomUUID().replace(/-/g, '') }),
  visitStatus: (v: Visit, body: Record<string, unknown>) =>
    api.request<Visit>(`/api/v1/measurement-visits/${v.id}/status`, {
      method: 'POST', body, ifMatch: v.version, idempotencyKey: crypto.randomUUID().replace(/-/g, ''),
    }),
  openSet: (visitId: string, body: Record<string, unknown>) =>
    api.request<MeasurementSet>(`/api/v1/measurement-visits/${visitId}/measurement-sets`, { method: 'POST', body }),
  sets: (propertyId: string) => api.request<MeasurementSet[]>(`/api/v1/properties/${propertyId}/measurement-sets`),
  set: (id: string) => api.request<MeasurementSet>(`/api/v1/measurement-sets/${id}`),
  checks: (id: string) => api.request<Readiness>(`/api/v1/measurement-sets/${id}/checks`),
  submit: (m: MeasurementSet) =>
    api.request<MeasurementSet>(`/api/v1/measurement-sets/${m.id}/submit`, { method: 'POST', ifMatch: m.version }),
  verify: (m: MeasurementSet, acknowledgements: Array<{ code: string; note: string }>) =>
    api.request<MeasurementSet>(`/api/v1/measurement-sets/${m.id}/verify`, { method: 'POST', body: { acknowledgements }, ifMatch: m.version }),
  reject: (m: MeasurementSet, reason: string) =>
    api.request<{ rejected: MeasurementSet; correction: MeasurementSet }>(`/api/v1/measurement-sets/${m.id}/reject`, {
      method: 'POST', body: { reason }, ifMatch: m.version,
    }),
  diff: (a: string, b: string) => api.request<{ spaces: Array<Record<string, unknown>> }>(`/api/v1/measurement-sets/${a}/diff/${b}`),
  attachments: (entityType: string, entityId: string) =>
    api.request<Attachment[]>('/api/v1/attachments', { query: { entity_type: entityType, entity_id: entityId } }),
};

/** Fetch a protected photo variant as a data: URL. The site CSP allows images only from 'self' and data: (no blob:),
 * and an <img> cannot carry the bearer token, so the bytes are fetched with it and inlined. */
export async function variantUrl(attachmentId: string, variant: 'thumb' | 'mobile' | 'desktop' | 'full' = 'thumb'): Promise<string | null> {
  const token = api.token;
  const r = await fetch(`${api.baseUrl}/api/v1/attachments/${attachmentId}/content?variant=${variant}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}, credentials: 'include',
  });
  if (!r.ok) return null;
  const blob = await r.blob();
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : null);
    reader.onerror = () => resolve(null);
    reader.readAsDataURL(blob);
  });
}
