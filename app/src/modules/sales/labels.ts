import { css, html } from 'lit';
import { formatINR } from '../../core/format/format.js';
import { icon } from '../../design-system/icons.js';
import type { Counted, Quoted, Ratio, Ref, Stage } from './api.js';

/**
 * Sales vocabulary mirrored from the API (api/veda/modules/sales/vocab.py). The server's label travels with every
 * code and wins when present; these maps only fill in for a code that arrives without one.
 */
export const STAGES = ['NEW', 'CONTACTED', 'CONSULTATION', 'SITE_MEASUREMENT', 'QUOTATION_PREPARATION', 'QUOTATION_ISSUED', 'CUSTOMER_CONSIDERING',
  'QUOTATION_DECLINED', 'ACCEPTED', 'WON', 'LOST'] as const;
export const STAGE_LABELS: Record<string, string> = {
  NEW: 'New enquiry', CONTACTED: 'Contacted', CONSULTATION: 'Consultation held', SITE_MEASUREMENT: 'Site measurement',
  QUOTATION_PREPARATION: 'Quotation in preparation', QUOTATION_ISSUED: 'Quotation issued', CUSTOMER_CONSIDERING: 'Customer considering',
  QUOTATION_DECLINED: 'Quotation declined', ACCEPTED: 'Accepted by the customer', WON: 'Won', LOST: 'Lost',
};
export const BASIS_LABELS: Record<string, string> = {
  NONE: 'No evidence yet', LEAD_STATUS: 'Status recorded by staff', ACTIVITY: 'Logged activity', MEASUREMENT_RECORD: 'Measurement visit record',
  QUOTATION_RECORD: 'Quotation record', PROPOSAL_RECORD: 'Customer proposal record',
};
export const ATTENTION = ['FOLLOW_UP_OVERDUE', 'NO_FOLLOW_UP_PLANNED', 'QUIET', 'UNASSIGNED', 'CUSTOMER_REQUEST_OPEN', 'PROPOSAL_NOT_OPENED',
  'ACCEPTED_NOT_CLOSED', 'DECLINED_STILL_OPEN'] as const;
export const ATTENTION_LABELS: Record<string, string> = {
  FOLLOW_UP_OVERDUE: 'Follow-up overdue', NO_FOLLOW_UP_PLANNED: 'No follow-up planned', QUIET: 'No activity for 14 days and nothing planned',
  UNASSIGNED: 'No owner', CUSTOMER_REQUEST_OPEN: 'Customer question or change request waiting',
  PROPOSAL_NOT_OPENED: 'Proposal link shared, not opened yet', ACCEPTED_NOT_CLOSED: 'Customer accepted: close the lead as won',
  DECLINED_STILL_OPEN: 'Quotation declined: record the outcome',
};
export const CHANNELS = ['REFERRAL', 'DIRECT', 'SOCIAL', 'PAID', 'ORGANIC_SEARCH', 'OTHER', 'UNKNOWN'] as const;
export const CHANNEL_LABELS: Record<string, string> = {
  REFERRAL: 'Referral', DIRECT: 'Direct contact', SOCIAL: 'Social media', PAID: 'Paid campaign', ORGANIC_SEARCH: 'Organic search', OTHER: 'Other',
  UNKNOWN: 'Unknown',
};
export const STATUS_GROUPS: [string, string][] = [['open', 'Open'], ['closed', 'Closed'], ['all', 'All']];
export const OWNER_FILTERS: [string, string][] = [['', 'Anyone'], ['me', 'Me'], ['unassigned', 'Unassigned']];

const fallback = (map: Record<string, string>, code: string | null | undefined): string =>
  code ? map[code] ?? code.toLowerCase().replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : '—';

/** The server's label when it sent one, else the mirrored vocabulary, else the code in words. */
export function stageLabel(stage: Partial<Ref> | string | null | undefined): string {
  if (typeof stage === 'string') return fallback(STAGE_LABELS, stage);
  return stage?.label || fallback(STAGE_LABELS, stage?.code);
}
export function basisLabel(stage: Partial<Stage> | null | undefined): string {
  return stage?.basis_label || fallback(BASIS_LABELS, stage?.basis);
}
export function attentionLabel(item: Partial<Ref> | string): string {
  if (typeof item === 'string') return fallback(ATTENTION_LABELS, item);
  return item.label || fallback(ATTENTION_LABELS, item.code);
}
export function channelLabel(item: Partial<Ref> | string | null | undefined): string {
  if (typeof item === 'string') return fallback(CHANNEL_LABELS, item);
  return item?.label || fallback(CHANNEL_LABELS, item?.code);
}

/** The quoted amount as the server allows it to be seen: a figure, "Withheld" (no quotation.read), or nothing. */
export function quotedText(q: Quoted): string {
  if (!q) return '—';
  if ('withheld' in q) return 'Withheld';
  return formatINR(q.amount_minor / 100);
}

/**
 * A funnel count in words: "Not tracked" when the site never sent that beacon (never 0, which would claim the event
 * happened nought times), the figure itself otherwise (a tracked zero is 0).
 */
export function countText(c: Pick<Counted, 'count' | 'tracking'> | null | undefined): string {
  if (!c || c.tracking === 'NOT_TRACKED' || c.count === null || c.count === undefined) return 'Not tracked';
  return String(c.count);
}

/** A ratio as a percentage, or the reason there is none. No percentage is ever shown for a null value. */
export function ratioText(r: Ratio | null | undefined): string {
  if (!r || r.value === null || r.value === undefined) {
    return r?.reason === 'NO_DENOMINATOR' ? 'No data yet' : 'Not tracked';
  }
  return `${Math.round(r.value * 1000) / 10}%`;
}

// Stage pills reuse the lead-status tones of the design system (tokens.css --vs-status-*), by the closest CRM status.
const TONE: Record<string, string> = {
  NEW: 'new', CONTACTED: 'contacted', CONSULTATION: 'contacted', SITE_MEASUREMENT: 'site_visit', QUOTATION_PREPARATION: 'site_visit',
  QUOTATION_ISSUED: 'quotation_sent', CUSTOMER_CONSIDERING: 'negotiation', QUOTATION_DECLINED: 'lost', ACCEPTED: 'won', WON: 'won', LOST: 'lost',
};

export const salesStyles = css`
  .stage { display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px; border-radius: var(--vs-radius-pill); font: 600 12px/18px var(--vs-font-sans); white-space: nowrap; background: var(--vs-cream); color: var(--vs-ink); }
  .stage::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
  .stage.new { background: var(--vs-status-new-bg); color: var(--vs-status-new-fg); }
  .stage.contacted { background: var(--vs-status-contacted-bg); color: var(--vs-status-contacted-fg); }
  .stage.site_visit { background: var(--vs-status-site_visit-bg); color: var(--vs-status-site_visit-fg); }
  .stage.quotation_sent { background: var(--vs-status-quotation_sent-bg); color: var(--vs-status-quotation_sent-fg); }
  .stage.negotiation { background: var(--vs-status-negotiation-bg); color: var(--vs-status-negotiation-fg); }
  .stage.won { background: var(--vs-status-won-bg); color: var(--vs-status-won-fg); }
  .stage.lost { background: var(--vs-status-lost-bg); color: var(--vs-status-lost-fg); }
  .stage-cell { display: inline-flex; flex-direction: column; align-items: flex-start; gap: 2px; }
  .basis { font-size: 12px; line-height: 18px; color: var(--vs-ink-muted); }
  .claim { display: inline-flex; align-items: center; gap: 4px; font: 600 12px/18px var(--vs-font-sans); color: var(--vs-warning); }
  .claim .icon { width: 16px; height: 16px; }
  .overdue { display: inline-flex; align-items: center; gap: 4px; font-weight: 600; color: var(--vs-danger); }
  .overdue .icon { width: 16px; height: 16px; }
  .attention { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 4px; }
  .attention li { display: inline-flex; align-items: center; padding: 2px 8px; border: 1px solid var(--vs-line); border-radius: var(--vs-radius-pill); font-size: 12px; line-height: 18px; background: var(--vs-surface); }
`;

/** Stage pill with its basis; a stage claimed by a staff status alone carries a visible "by status" marker (not colour alone). */
export function stagePill(stage: Stage, withBasis = true) {
  return html`<span class="stage-cell">
    <span class="stage ${TONE[stage.code] ?? ''}">${stageLabel(stage)}</span>
    ${withBasis ? html`<span class="basis">${stage.claimed_without_record
      ? html`<span class="claim">${icon('alert')}by status</span> · ${basisLabel(stage)}`
      : basisLabel(stage)}</span>` : ''}
  </span>`;
}
