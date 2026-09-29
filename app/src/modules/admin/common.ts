import { api } from '../../core/api/client.js';
import type { Permission, Role } from '../../core/api/types.js';

/** Fetch every page of an offset-paginated collection (max page_size 100, 08 §2.5). */
export async function fetchAll<T>(path: string, query: Record<string, string> = {}): Promise<T[]> {
  const out: T[] = [];
  for (let page = 1; page < 50; page += 1) {
    const r = await api.get<T[]>(path, { ...query, page, page_size: 100 });
    out.push(...r.data);
    const meta = r.meta as { total_pages?: number };
    if (!meta.total_pages || page >= meta.total_pages) break;
  }
  return out;
}

export const loadRoles = () => fetchAll<Role>('/api/v1/roles');
export const loadPermissions = () => fetchAll<Permission>('/api/v1/permissions');

export const FOUNDER_ONLY = 'FOUNDER_WORKFLOW_ONLY';

/** A role is Founder-governed when its grant_path says so; the FOUNDER code is only a display fallback. */
export function isFounderGoverned(role: Pick<Role, 'grant_path' | 'is_assignable' | 'code'>): boolean {
  return role.grant_path === FOUNDER_ONLY;
}

export const MFA_LABEL = (mfa: { required: boolean; enrolled: boolean }) =>
  mfa.enrolled ? (mfa.required ? '✓ On' : '✓ On (optional)') : mfa.required ? 'Required' : 'Optional';
