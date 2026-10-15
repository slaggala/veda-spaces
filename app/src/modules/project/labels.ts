import { css } from 'lit';
import { formatFull } from '../../core/format/format.js';
import type { Person } from './api.js';

/** Words for the codes the project pages show. Codes stay the server's; these are display labels only. */
export const PARTY: Record<string, string> = { CUSTOMER: 'Customer', VEDA: 'Veda Spaces', THIRD_PARTY: 'Third party', TO_BE_CONFIRMED: 'To be confirmed' };
export const SEVERITY: Record<string, string> = { ACTION: 'Your action', GATING: 'Blocks progress', SITE: 'Site readiness', INFORMATIONAL: 'For information' };
export const OUTCOME: Record<string, string> = { REFUSED: 'Refused', AWAITING_APPROVAL: 'Awaiting approval', COMPLETED: 'Completed',
  REJECTED: 'Rejected', WITHDRAWN: 'Withdrawn' };
export const CLASS_LABEL: Record<string, string> = { INTERNAL_ONLY: 'Internal only', POTENTIALLY_CUSTOMER_SAFE: 'May be shown to the customer later',
  CUSTOMER_ACTION: 'Customer action (customer-safe wording)' };

export const who = (p: Person | null | undefined, empty = '—') => p?.display_name ?? (p ? 'Unknown user' : empty);
export const when = (iso: string | null | undefined) => (iso ? formatFull(iso) : '—');
export const party = (code: string | null | undefined) => (code ? PARTY[code] ?? code : '—');

/** Status badges: text always says the state; colour only reinforces it (09 §2.2). Tokens only (lint:tokens). */
export const badgeStyles = css`
  .badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border-radius: var(--vs-radius-pill); border: 1px solid var(--vs-line);
    background: var(--vs-surface); color: var(--vs-ink); font: 600 12px/18px var(--vs-font-sans); white-space: nowrap; }
  .badge.gating, .badge.danger { border-color: var(--vs-danger); color: var(--vs-danger); }
  .badge.warn { border-color: var(--vs-warning); color: var(--vs-warning); }
  .badge.ok { border-color: var(--vs-success); color: var(--vs-success); }
  .badge.action { border-color: var(--vs-copper-strong); color: var(--vs-copper-text); }
  .badge.info { color: var(--vs-ink-muted); }
`;
