/**
 * Lead list filters ↔ URL query, mapping 1:1 to the API params of 08 §8.2 so views are shareable and
 * back-button friendly (09 §4.3).
 */
export interface LeadFilters {
  q: string;
  status: string[];
  open: boolean;
  assigned_to: string[];
  project_type: string[];
  budget_range: string[];
  source: string[];
  priority: string[];
  city: string[];
  created_on_from: string;
  created_on_to: string;
  status_changed_on_from: string;
  status_changed_on_to: string;
  follow_up: '' | 'overdue' | 'today' | 'this_week' | 'none';
  duplicate_status: string[];
  spam_status: string[];
  consent: '' | 'withdrawn';
  include_deleted: boolean;
  deleted_only: boolean;
  sort: string;
  page: number;
  page_size: number;
}

export const DEFAULT_SORT = '-created_on';
export const DEFAULT_PAGE_SIZE = 25;
export const SORTABLE = ['created_on', 'status_changed_on', 'next_follow_up_on', 'name', 'priority'] as const;

const LIST_KEYS = ['status', 'assigned_to', 'project_type', 'budget_range', 'source', 'priority', 'city', 'duplicate_status', 'spam_status'] as const;
const TEXT_KEYS = ['q', 'created_on_from', 'created_on_to', 'status_changed_on_from', 'status_changed_on_to'] as const;
const FOLLOW_UPS = new Set(['overdue', 'today', 'this_week', 'none']);
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function emptyFilters(): LeadFilters {
  return {
    q: '', status: [], open: false, assigned_to: [], project_type: [], budget_range: [], source: [], priority: [], city: [],
    created_on_from: '', created_on_to: '', status_changed_on_from: '', status_changed_on_to: '', follow_up: '',
    duplicate_status: [], spam_status: [], consent: '', include_deleted: false, deleted_only: false,
    sort: DEFAULT_SORT, page: 1, page_size: DEFAULT_PAGE_SIZE,
  };
}

function csv(value: string | null): string[] {
  return value ? value.split(',').map((v) => v.trim()).filter(Boolean) : [];
}

export function parseFilters(search: string | URLSearchParams): LeadFilters {
  const p = typeof search === 'string' ? new URLSearchParams(search) : search;
  const f = emptyFilters();
  for (const k of LIST_KEYS) f[k] = csv(p.get(k));
  for (const k of TEXT_KEYS) f[k] = p.get(k) ?? '';
  for (const k of ['created_on_from', 'created_on_to', 'status_changed_on_from', 'status_changed_on_to'] as const) {
    if (f[k] && !DATE.test(f[k])) f[k] = '';
  }
  f.open = p.get('open') === 'true';
  const fu = p.get('follow_up') ?? '';
  f.follow_up = FOLLOW_UPS.has(fu) ? (fu as LeadFilters['follow_up']) : '';
  f.consent = p.get('consent') === 'withdrawn' ? 'withdrawn' : '';
  f.include_deleted = p.get('include_deleted') === 'true';
  f.deleted_only = p.get('deleted_only') === 'true';
  const sort = p.get('sort');
  if (sort && sort.split(',').every((s) => (SORTABLE as readonly string[]).includes(s.replace(/^-/, '')))) f.sort = sort;
  const page = Number(p.get('page'));
  f.page = Number.isInteger(page) && page >= 1 ? page : 1;
  const size = Number(p.get('page_size'));
  f.page_size = Number.isInteger(size) && size >= 1 && size <= 100 ? size : DEFAULT_PAGE_SIZE;
  return f;
}

/** Serialize to query params, omitting empty values and defaults. Used for both the URL and the API. */
export function filtersToQuery(f: LeadFilters): URLSearchParams {
  const p = new URLSearchParams();
  if (f.q.trim()) p.set('q', f.q.trim());
  for (const k of LIST_KEYS) if (f[k].length) p.set(k, f[k].join(','));
  if (f.open) p.set('open', 'true');
  for (const k of ['created_on_from', 'created_on_to', 'status_changed_on_from', 'status_changed_on_to'] as const) if (f[k]) p.set(k, f[k]);
  if (f.follow_up) p.set('follow_up', f.follow_up);
  if (f.consent) p.set('consent', f.consent);
  if (f.include_deleted) p.set('include_deleted', 'true');
  if (f.deleted_only) p.set('deleted_only', 'true');
  if (f.sort && f.sort !== DEFAULT_SORT) p.set('sort', f.sort);
  if (f.page > 1) p.set('page', String(f.page));
  if (f.page_size !== DEFAULT_PAGE_SIZE) p.set('page_size', String(f.page_size));
  return p;
}

/** Number of active (non-default) filters, excluding search, sort and paging. */
export function activeFilterCount(f: LeadFilters): number {
  let n = 0;
  for (const k of LIST_KEYS) if (f[k].length) n += 1;
  if (f.open) n += 1;
  if (f.follow_up) n += 1;
  if (f.consent) n += 1;
  if (f.created_on_from || f.created_on_to) n += 1;
  if (f.status_changed_on_from || f.status_changed_on_to) n += 1;
  if (f.include_deleted || f.deleted_only) n += 1;
  return n;
}
