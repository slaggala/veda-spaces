// Lead edit form values and the PATCH built from them (08 §8.5, UI-005).
import type { Lead } from '../../core/api/types.js';

export const EDITABLE = ['name', 'phone', 'email', 'city', 'locality', 'project_type_code', 'property_type_code', 'budget_range_code', 'message', 'priority', 'source_code', 'source_detail', 'expected_close_on'] as const;
export type Editable = (typeof EDITABLE)[number];

export function leadValues(lead: Lead | null): Record<Editable, string> {
  return {
    name: lead?.name ?? '', phone: lead?.phone ?? '', email: lead?.email ?? '', city: lead?.city ?? '', locality: lead?.locality ?? '',
    project_type_code: lead?.project_type?.code ?? '', property_type_code: lead?.property_type?.code ?? '', budget_range_code: lead?.budget_range?.code ?? '',
    message: lead?.message ?? '', priority: lead?.priority ?? 'MEDIUM', source_code: lead?.source?.code ?? '', source_detail: lead?.source_detail ?? '',
    expected_close_on: lead?.expected_close_on ?? '',
  };
}

/** The fields the user changed relative to the record they loaded, '' sent as null. */
export function leadPatch(values: Record<Editable, string>, loaded: Record<Editable, string>): Record<string, unknown> {
  const patch: Record<string, unknown> = {};
  for (const k of EDITABLE) if (values[k] !== loaded[k]) patch[k] = values[k] === '' ? null : values[k];
  return patch;
}
