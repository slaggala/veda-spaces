import { api } from './client.js';
import type { LookupCategory, LookupValue } from './types.js';

let cache: Promise<Record<string, LookupCategory>> | null = null;

/**
 * GET /api/v1/lookups returns every category with its active values in one call (08 §7). Accepts
 * either an array of {code, values} or an object keyed by category code.
 */
export function normalizeLookups(data: unknown): Record<string, LookupCategory> {
  const out: Record<string, LookupCategory> = {};
  if (Array.isArray(data)) {
    for (const c of data as Array<LookupCategory & { category_code?: string }>) {
      const code = c.code ?? c.category_code ?? '';
      if (code) out[code] = { code, name: c.name, values: sortValues(c.values ?? []) };
    }
  } else if (data && typeof data === 'object') {
    for (const [code, v] of Object.entries(data as Record<string, unknown>)) {
      const values = Array.isArray(v) ? (v as LookupValue[]) : ((v as LookupCategory).values ?? []);
      out[code] = { code, name: (v as LookupCategory).name, values: sortValues(values) };
    }
  }
  return out;
}

function sortValues(values: LookupValue[]): LookupValue[] {
  return [...values].sort((a, b) => (a.sort_order ?? 100) - (b.sort_order ?? 100) || a.label.localeCompare(b.label));
}

export function loadLookups(force = false): Promise<Record<string, LookupCategory>> {
  if (!cache || force) {
    cache = api
      .get<unknown>('/api/v1/lookups')
      .then((r) => normalizeLookups(r.data))
      .catch((e) => {
        cache = null;
        throw e;
      });
  }
  return cache;
}

export function lookupOptions(lookups: Record<string, LookupCategory> | undefined, category: string, includeInactive = false): LookupValue[] {
  return (lookups?.[category]?.values ?? []).filter((v) => includeInactive || v.is_active !== false);
}
