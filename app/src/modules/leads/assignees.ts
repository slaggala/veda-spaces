import { api } from '../../core/api/client.js';
import type { Me, UserRef } from '../../core/api/types.js';
import { has } from '../../core/authz/permissions.js';

let cache: Promise<UserRef[]> | null = null;

/** Eligible assignees (08 §5.12, lead.assign). Users without lead.assign can only pick themselves. */
export function loadAssignees(me: Me | null): Promise<UserRef[]> {
  const self: UserRef[] = me ? [{ id: me.id, display_name: me.display_name || me.full_name }] : [];
  if (!has(me?.permissions, 'lead.assign')) return Promise.resolve(self);
  if (!cache) {
    cache = api
      .get<Array<UserRef & { open_lead_count?: number }>>('/api/v1/users/assignable')
      .then((r) => r.data)
      .catch(() => {
        cache = null;
        return self;
      });
  }
  return cache;
}
