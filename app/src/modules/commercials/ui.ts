import { css, html } from 'lit';
import type { InstalmentState } from './api.js';

/** Shared look of the staff commercial pages: figures easy to scan (tabular numerals, right-aligned), states always named
 * in text with a shape marker (never colour alone). */
export const commercialStyles = css`
  /* positioned, so the visually hidden labels inside a cell stay within the table's own scroll area */
  .table-wrap { position: relative; }
  .table-wrap:focus-visible { outline: 2px solid var(--vs-focus-ring); outline-offset: 2px; }
  .figures { display: grid; gap: var(--vs-space-3); grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr)); }
  .figure { display: flex; flex-direction: column; gap: 4px; background: var(--vs-surface); border: 1px solid var(--vs-line);
    border-radius: var(--vs-radius-card); padding: var(--vs-space-3) var(--vs-space-4); min-width: 0; }
  .figure .label { font-size: 11px; line-height: 16px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--vs-ink-muted); }
  .figure .value { font-family: var(--vs-font-serif); font-size: 28px; line-height: 34px; font-variant-numeric: lining-nums tabular-nums; overflow-wrap: anywhere; }
  .figure .value.small { font-size: 22px; line-height: 30px; }
  .figure .hint { font-size: 13px; line-height: 20px; color: var(--vs-ink-muted); }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .sub { display: block; font-size: 12px; line-height: 18px; color: var(--vs-ink-muted); }
  .badge { display: inline-flex; align-items: center; gap: 6px; padding: 1px 8px; border-radius: var(--vs-radius-pill); border: 1px solid var(--vs-line);
    font-size: 12px; line-height: 20px; font-weight: 600; white-space: nowrap; background: var(--vs-surface); }
  .badge::before { content: ''; width: 8px; height: 8px; border-radius: 50%; background: var(--vs-ink-muted); }
  .badge.PAID::before, .badge.ISSUED::before, .badge.VALID::before { background: var(--vs-success); }
  .badge.OVERDUE { border-color: var(--vs-danger); color: var(--vs-danger); }
  .badge.OVERDUE::before { border-radius: 1px; transform: rotate(45deg); background: var(--vs-danger); }
  .badge.DUE, .badge.PARTIALLY_PAID { border-color: var(--vs-copper); color: var(--vs-copper-text); }
  .badge.DUE::before { background: var(--vs-copper); }
  .badge.PARTIALLY_PAID::before { background: linear-gradient(90deg, var(--vs-copper) 50%, transparent 50%); border: 1px solid var(--vs-copper); }
  .badge.UPCOMING::before, .badge.DRAFT::before { background: transparent; border: 2px solid var(--vs-ink-muted); width: 6px; height: 6px; }
  .badge.REVERSED, .badge.CANCELLED { text-decoration: line-through; color: var(--vs-ink-muted); }
  .section-title { font-family: var(--vs-font-serif); font-size: 22px; line-height: 28px; font-weight: 500; }
  ol.history { margin: 0; padding-left: 20px; display: grid; gap: var(--vs-space-2); }
  ol.history li { overflow-wrap: anywhere; }
  .row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--vs-space-2); }
`;

export function stateBadge(state: InstalmentState | string, label: string) {
  return html`<span class="badge ${state}">${label}</span>`;
}
