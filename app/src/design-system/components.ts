import { LitElement, css, html, nothing, type PropertyValues } from 'lit';
import { styleMap } from 'lit/directives/style-map.js';
import { statusLabel } from '../core/i18n/strings.js';
import type { ApiProblem } from '../core/api/problem.js';
import { icon } from './icons.js';
import { shared } from './styles.js';

const PIPELINE = ['NEW', 'CONTACTED', 'SITE_VISIT', 'QUOTATION_SENT', 'NEGOTIATION', 'WON'] as const;

/** Status chip: colour + text label, never colour alone (09 §2.2). */
export class VsStatusPill extends LitElement {
  static override properties = { status: { type: String } };
  declare status: string;
  static override styles = css`
    :host { display: inline-flex; }
    span { display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px; border-radius: 999px; font: 600 12px/18px var(--vs-font-sans); white-space: nowrap; }
    span::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
    .NEW { background: var(--vs-status-new-bg); color: var(--vs-status-new-fg); }
    .CONTACTED { background: var(--vs-status-contacted-bg); color: var(--vs-status-contacted-fg); }
    .SITE_VISIT { background: var(--vs-status-site_visit-bg); color: var(--vs-status-site_visit-fg); }
    .QUOTATION_SENT { background: var(--vs-status-quotation_sent-bg); color: var(--vs-status-quotation_sent-fg); }
    .NEGOTIATION { background: var(--vs-status-negotiation-bg); color: var(--vs-status-negotiation-fg); }
    .WON { background: var(--vs-status-won-bg); color: var(--vs-status-won-fg); }
    .LOST { background: var(--vs-status-lost-bg); color: var(--vs-status-lost-fg); }
  `;
  override render() {
    return html`<span class=${this.status}>${statusLabel(this.status)}</span>`;
  }
}

/** Pipeline stepper exposed as an ordered list with aria-current (AX-09). */
export class VsStatusStepper extends LitElement {
  static override properties = { status: { type: String } };
  declare status: string;
  static override styles = css`
    :host { display: block; overflow-x: auto; }
    ol { list-style: none; display: flex; margin: 0; padding: 4px 0; gap: 0; min-width: max-content; }
    li { display: flex; align-items: center; gap: 8px; font: 600 11px/16px var(--vs-font-sans); letter-spacing: .12em; text-transform: uppercase; color: var(--vs-ink-muted); }
    li:not(:last-child)::after { content: ''; width: 32px; height: 1px; background: var(--vs-line); margin: 0 8px; }
    .dot { width: 10px; height: 10px; border-radius: 50%; border: 1.5px solid var(--vs-ink-muted); }
    li.done .dot { background: var(--vs-ink-muted); }
    li[aria-current='step'] { color: var(--vs-copper-text); }
    li[aria-current='step'] .dot { border-color: var(--vs-copper); background: var(--vs-copper); }
    li.lost { color: var(--vs-danger); }
  `;
  override render() {
    const lost = this.status === 'LOST';
    const idx = PIPELINE.indexOf(this.status as (typeof PIPELINE)[number]);
    return html`<ol aria-label="Pipeline status">
      ${PIPELINE.map(
        (s, i) => html`<li class=${i < idx ? 'done' : ''} aria-current=${s === this.status ? 'step' : 'false'}>
          <span class="dot" aria-hidden="true"></span>${statusLabel(s)}
        </li>`,
      )}
      ${lost ? html`<li class="lost" aria-current="step"><span class="dot" aria-hidden="true"></span>${statusLabel('LOST')}</li>` : nothing}
    </ol>`;
  }
}

/** Modal dialog on native <dialog>: focus trap, Esc to close, focus restore (AX-01). */
export class VsDialog extends LitElement {
  static override properties = { open: { type: Boolean, reflect: true }, heading: { type: String }, wide: { type: Boolean } };
  declare open: boolean;
  declare heading: string;
  declare wide: boolean;
  private returnFocus: Element | null = null;
  static override styles = [
    ...shared,
    css`
      dialog { border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); background: var(--vs-surface); color: var(--vs-ink); padding: 0; width: min(480px, calc(100vw - 32px)); box-shadow: var(--vs-shadow); }
      dialog.wide { width: min(720px, calc(100vw - 32px)); }
      dialog::backdrop { background: var(--vs-scrim); }
      header { display: flex; align-items: center; padding: 20px 24px 8px; gap: 12px; }
      h2 { font-family: var(--vs-font-serif); font-size: 26px; line-height: 30px; flex: 1; }
      .body { padding: 8px 24px 16px; display: flex; flex-direction: column; gap: 16px; }
      ::slotted([slot='actions']) { display: flex; gap: 12px; justify-content: flex-end; padding: 12px 24px 20px; flex-wrap: wrap; }
      .close { background: none; border: 0; color: var(--vs-ink-muted); cursor: pointer; min-width: 44px; min-height: 44px; }
    `,
  ];
  constructor() {
    super();
    this.open = false;
    this.heading = '';
    this.wide = false;
  }
  protected override updated(changed: PropertyValues<this>) {
    const dialog = this.renderRoot.querySelector('dialog');
    if (!dialog || !changed.has('open')) return;
    if (this.open && !dialog.open) {
      this.returnFocus = document.activeElement;
      dialog.showModal();
    } else if (!this.open && dialog.open) {
      dialog.close();
    }
  }
  private onClose() {
    if (this.open) {
      this.open = false;
      this.dispatchEvent(new CustomEvent('close', { bubbles: true, composed: true }));
    }
    (this.returnFocus as HTMLElement | null)?.focus?.();
  }
  override render() {
    return html`<dialog class=${this.wide ? 'wide' : ''} aria-labelledby="h" @close=${this.onClose} @cancel=${this.onClose}>
      <header><h2 id="h">${this.heading}</h2><button class="close" aria-label="Close" @click=${() => (this.open = false)}>${icon('x')}</button></header>
      <div class="body"><slot></slot></div>
      <slot name="actions"></slot>
    </dialog>`;
  }
}

/** Right drawer 560 px, full screen on mobile (09 §3.2). */
export class VsDrawer extends VsDialog {
  static override styles = [
    ...VsDialog.styles,
    css`
      dialog { margin: 0 0 0 auto; height: 100vh; max-height: 100vh; width: min(560px, 100vw); border-radius: 0; border-width: 0 0 0 1px; }
      dialog.wide { width: min(760px, 100vw); }
      .body { overflow-y: auto; max-height: calc(100vh - 150px); }
      @media (max-width: 767px) { dialog, dialog.wide { width: 100vw; } }
    `,
  ];
}

type ToastKind = 'info' | 'success' | 'error';
/** Toasts: bottom-centre, 4 s, role=status. No Undo in P0 (F-20). */
export class VsToaster extends LitElement {
  static override properties = { items: { state: true } };
  declare items: Array<{ id: number; text: string; kind: ToastKind }>;
  private seq = 0;
  static override styles = css`
    :host { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); z-index: 1000; display: flex; flex-direction: column; gap: 8px; pointer-events: none; }
    div { background: var(--vs-sidebar); color: var(--vs-on-sidebar); padding: 12px 18px; border-radius: 8px; font: 500 14px/20px var(--vs-font-sans); box-shadow: var(--vs-shadow); max-width: min(480px, calc(100vw - 32px)); }
    .error { border-left: 3px solid var(--vs-danger); }
    .success { border-left: 3px solid var(--vs-success); }
  `;
  constructor() {
    super();
    this.items = [];
  }
  show(text: string, kind: ToastKind = 'info') {
    const id = ++this.seq;
    this.items = [...this.items, { id, text, kind }];
    setTimeout(() => (this.items = this.items.filter((t) => t.id !== id)), 4000);
  }
  override render() {
    return html`<div role="status" aria-live="polite" hidden></div>${this.items.map((t) => html`<div class=${t.kind} role="status">${t.text}</div>`)}`;
  }
}

export function toast(text: string, kind: ToastKind = 'info'): void {
  let el = document.querySelector('vs-toaster') as VsToaster | null;
  if (!el) {
    el = document.createElement('vs-toaster') as VsToaster;
    document.body.append(el);
  }
  el.show(text, kind);
}

/** Page-level problem banner with the request id and a copy button (09 §3.2). */
export class VsProblemBanner extends LitElement {
  static override properties = { problem: { attribute: false }, heading: { type: String } };
  declare problem: ApiProblem | null;
  declare heading: string;
  static override styles = [
    ...shared,
    css`
      :host { display: block; }
      .banner { display: flex; gap: 12px; align-items: flex-start; padding: 12px 16px; border: 1px solid var(--vs-danger); border-left-width: 3px; border-radius: 8px; background: var(--vs-surface); }
      .icon { color: var(--vs-danger); flex: none; }
      button { background: none; border: 0; color: var(--vs-copper-text); cursor: pointer; font: inherit; min-height: 32px; }
    `,
  ];
  constructor() {
    super();
    this.problem = null;
    this.heading = '';
  }
  override render() {
    const p = this.problem;
    if (!p) return nothing;
    const message = p.isNetwork ? 'We could not reach the server. Check your connection and try again.' : p.detail || p.title;
    return html`<div class="banner" role="alert">
      ${icon('alert')}
      <div class="stack">
        <strong>${this.heading || message}</strong>
        ${this.heading ? html`<span>${message}</span>` : nothing}
        ${p.requestId
          ? html`<span class="small muted">Request <span class="mono">${p.requestId}</span>
              <button @click=${() => navigator.clipboard?.writeText(p.requestId ?? '')} aria-label="Copy request id">Copy</button></span>`
          : nothing}
      </div>
    </div>`;
  }
}

/** Info / warning banner (e.g. cooling-off, Do not contact). */
export class VsBanner extends LitElement {
  static override properties = { kind: { type: String } };
  declare kind: 'info' | 'warning' | 'danger' | 'success';
  static override styles = css`
    :host { display: block; }
    div { display: flex; gap: 12px; align-items: flex-start; padding: 12px 16px; border-radius: 8px; border: 1px solid var(--vs-line); border-left: 3px solid var(--vs-copper); background: var(--vs-surface); font: 500 14px/22px var(--vs-font-sans); color: var(--vs-ink); }
    .warning { border-left-color: var(--vs-warning); }
    .danger { border-left-color: var(--vs-danger); }
    .success { border-left-color: var(--vs-success); }
  `;
  constructor() {
    super();
    this.kind = 'info';
  }
  override render() {
    return html`<div class=${this.kind} role=${this.kind === 'danger' ? 'alert' : 'status'}><slot></slot></div>`;
  }
}

export class VsEmptyState extends LitElement {
  static override properties = { heading: { type: String } };
  declare heading: string;
  static override styles = css`
    :host { display: block; }
    div { text-align: center; padding: 48px 16px; color: var(--vs-ink-muted); display: flex; flex-direction: column; gap: 12px; align-items: center; }
    p { font-family: var(--vs-font-serif); font-size: 24px; line-height: 30px; color: var(--vs-ink); margin: 0; }
  `;
  override render() {
    return html`<div><p>${this.heading}</p><slot></slot></div>`;
  }
}

/** Skeleton rows matching the final layout; never full-page spinners (09 §3.2). */
export class VsSkeleton extends LitElement {
  static override properties = { rows: { type: Number } };
  declare rows: number;
  static override styles = css`
    :host { display: block; }
    div { height: 16px; margin: 14px 0; border-radius: 2px; background: linear-gradient(90deg, var(--vs-cream), var(--vs-surface), var(--vs-cream)); background-size: 200% 100%; animation: shimmer 1.4s infinite; }
    div:nth-child(3n) { width: 70%; }
    @keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
  `;
  constructor() {
    super();
    this.rows = 5;
  }
  override render() {
    return html`<span class="sr-only" role="status">Loading…</span>${Array.from({ length: this.rows }, () => html`<div aria-hidden="true"></div>`)}`;
  }
}

export class VsKpiTile extends LitElement {
  static override properties = { label: { type: String }, value: { type: String }, hint: { type: String }, tone: { type: String } };
  declare label: string;
  declare value: string;
  declare hint: string;
  declare tone: string;
  static override styles = css`
    :host { display: block; background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: 8px; padding: 16px 20px; }
    .label { font: 600 11px/16px var(--vs-font-sans); letter-spacing: .18em; text-transform: uppercase; color: var(--vs-ink-muted); }
    .value { font-family: var(--vs-font-serif); font-size: 44px; line-height: 48px; font-variant-numeric: lining-nums tabular-nums; }
    .hint { font: 500 12px/18px var(--vs-font-sans); color: var(--vs-ink-muted); }
    .warning .value { color: var(--vs-warning); }
  `;
  override render() {
    return html`<div class=${this.tone ?? ''}><div class="label">${this.label}</div><div class="value">${this.value}</div>
      <div class="hint">${this.hint}<slot></slot></div></div>`;
  }
}

export interface BarItem { label: string; value: number; href?: string }
export class VsBarList extends LitElement {
  static override properties = { items: { attribute: false } };
  declare items: BarItem[];
  static override styles = css`
    :host { display: block; }
    ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
    li { display: grid; grid-template-columns: 120px 1fr 40px; gap: 12px; align-items: center; font: 500 13px/18px var(--vs-font-sans); }
    .bar { height: 10px; background: var(--vs-cream); border-radius: 2px; overflow: hidden; }
    .fill { height: 100%; background: var(--vs-copper); }
    a { color: var(--vs-ink); text-decoration: none; }
    a:hover { color: var(--vs-copper-text); text-decoration: underline; }
    .n { text-align: right; font-variant-numeric: tabular-nums; }
  `;
  constructor() {
    super();
    this.items = [];
  }
  override render() {
    const max = Math.max(1, ...this.items.map((i) => i.value));
    return html`<ul>${this.items.map(
      (i) => html`<li>
        ${i.href ? html`<a href=${i.href}>${i.label}</a>` : html`<span>${i.label}</span>`}
        <span class="bar" aria-hidden="true"><span class="fill" style=${styleMap({ width: `${(i.value / max) * 100}%`, display: 'block' })}></span></span>
        <span class="n">${i.value}</span>
      </li>`,
    )}</ul>`;
  }
}

export class VsPagination extends LitElement {
  static override properties = { page: { type: Number }, totalPages: { type: Number }, total: { type: Number }, pageSize: { type: Number } };
  declare page: number;
  declare totalPages: number;
  declare total: number;
  declare pageSize: number;
  static override styles = [...shared, css`:host { display: block; } nav { display: flex; align-items: center; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }`];
  private go(page: number) {
    this.dispatchEvent(new CustomEvent('page-change', { detail: page, bubbles: true, composed: true }));
  }
  override render() {
    if (!this.total) return nothing;
    const from = (this.page - 1) * this.pageSize + 1;
    const to = Math.min(this.total, this.page * this.pageSize);
    return html`<nav aria-label="Pagination">
      <span class="small muted">${from}–${to} of ${this.total}</span>
      <button class="btn small" ?disabled=${this.page <= 1} @click=${() => this.go(this.page - 1)} aria-label="Previous page">‹</button>
      <span class="small" aria-current="page">Page ${this.page} of ${this.totalPages}</span>
      <button class="btn small" ?disabled=${this.page >= this.totalPages} @click=${() => this.go(this.page + 1)} aria-label="Next page">›</button>
    </nav>`;
  }
}

export interface TabItem { id: string; label: string; hidden?: boolean }
/** Tabs with roving arrow-key focus (AX-01). */
export class VsTabs extends LitElement {
  static override properties = { tabs: { attribute: false }, selected: { type: String } };
  declare tabs: TabItem[];
  declare selected: string;
  static override styles = css`
    :host { display: block; border-bottom: 1px solid var(--vs-line); }
    div { display: flex; gap: 4px; overflow-x: auto; }
    button { background: none; border: 0; border-bottom: 2px solid transparent; padding: 10px 14px; min-height: 44px; font: 600 14px/20px var(--vs-font-sans); color: var(--vs-ink-muted); cursor: pointer; white-space: nowrap; }
    button[aria-selected='true'] { color: var(--vs-ink); border-bottom-color: var(--vs-copper); }
    button:focus-visible { outline: 2px solid var(--vs-focus-ring); outline-offset: -2px; }
  `;
  constructor() {
    super();
    this.tabs = [];
    this.selected = '';
  }
  private select(id: string) {
    this.selected = id;
    this.dispatchEvent(new CustomEvent('tab-change', { detail: id, bubbles: true, composed: true }));
  }
  private onKey(e: KeyboardEvent) {
    const visible = this.tabs.filter((t) => !t.hidden);
    const i = visible.findIndex((t) => t.id === this.selected);
    let next = -1;
    if (e.key === 'ArrowRight') next = (i + 1) % visible.length;
    if (e.key === 'ArrowLeft') next = (i - 1 + visible.length) % visible.length;
    if (next < 0) return;
    e.preventDefault();
    this.select(visible[next].id);
    this.updateComplete.then(() => (this.renderRoot.querySelector('[aria-selected="true"]') as HTMLElement | null)?.focus());
  }
  override render() {
    return html`<div role="tablist" @keydown=${this.onKey}>${this.tabs
      .filter((t) => !t.hidden)
      .map(
        (t) => html`<button role="tab" aria-selected=${t.id === this.selected ? 'true' : 'false'} tabindex=${t.id === this.selected ? 0 : -1}
          @click=${() => this.select(t.id)}>${t.label}</button>`,
      )}</div>`;
  }
}

/** Field-level before/after table used by the audit viewer (09 §4.9). */
export class VsDiffViewer extends LitElement {
  static override properties = { oldValue: { attribute: false }, newValue: { attribute: false }, fields: { attribute: false } };
  declare oldValue: Record<string, unknown> | null;
  declare newValue: Record<string, unknown> | null;
  declare fields: string[] | null;
  static override styles = css`
    :host { display: block; overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font: 400 13px/20px var(--vs-font-sans); }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--vs-line); vertical-align: top; }
    th { font: 600 11px/16px var(--vs-font-sans); letter-spacing: .14em; text-transform: uppercase; color: var(--vs-ink-muted); }
    .before::before { content: '− '; color: var(--vs-danger); }
    .after::before { content: '+ '; color: var(--vs-success); }
    .v { font-family: var(--vs-font-mono); font-size: 12px; word-break: break-word; }
  `;
  static display(v: unknown): string {
    if (v === null || v === undefined) return '—';
    if (v === '[REDACTED]') return '•••• (changed)';
    if (typeof v === 'object' && v && 'label' in (v as Record<string, unknown>)) return String((v as Record<string, unknown>).label);
    if (typeof v === 'object') return JSON.stringify(v);
    return String(v);
  }
  override render() {
    const keys = this.fields?.length
      ? this.fields
      : Array.from(new Set([...Object.keys(this.oldValue ?? {}), ...Object.keys(this.newValue ?? {})])).filter((k) => k !== '_snapshot');
    if (!keys.length) return html`<p>No field changes recorded.</p>`;
    return html`<table>
      <thead><tr><th scope="col">Field</th><th scope="col">Before</th><th scope="col">After</th></tr></thead>
      <tbody>${keys.map(
        (k) => html`<tr><th scope="row">${k.replace(/_/g, ' ')}</th>
          <td class="v ${this.oldValue && k in this.oldValue ? 'before' : ''}">${VsDiffViewer.display(this.oldValue?.[k])}</td>
          <td class="v ${this.newValue && k in this.newValue ? 'after' : ''}">${VsDiffViewer.display(this.newValue?.[k])}</td></tr>`,
      )}</tbody>
    </table>`;
  }
}

/** Accessible form error summary: role=alert, receives focus, links to fields (AX-03). */
export class VsErrorSummary extends LitElement {
  static override properties = { errors: { attribute: false } };
  declare errors: Array<{ field: string; message: string }>;
  static override styles = css`
    :host { display: block; }
    div { border: 1px solid var(--vs-danger); border-left-width: 3px; border-radius: 8px; padding: 12px 16px; background: var(--vs-surface); }
    div:focus { outline: 2px solid var(--vs-focus-ring); outline-offset: 2px; }
    strong { color: var(--vs-danger); }
    ul { margin: 6px 0 0; padding-left: 18px; }
    a { color: var(--vs-copper-text); }
  `;
  constructor() {
    super();
    this.errors = [];
  }
  focusSummary() {
    (this.renderRoot.querySelector('div') as HTMLElement | null)?.focus();
  }
  override render() {
    if (!this.errors.length) return nothing;
    const n = this.errors.length;
    return html`<div role="alert" tabindex="-1">
      <strong>Please fix ${n} ${n === 1 ? 'thing' : 'things'}</strong>
      <ul>${this.errors.map(
        (e) => html`<li><a href="#" @click=${(ev: Event) => {
          ev.preventDefault();
          this.dispatchEvent(new CustomEvent('focus-field', { detail: e.field, bubbles: true, composed: true }));
        }}>${e.message}</a></li>`,
      )}</ul>
    </div>`;
  }
}

export function define(): void {
  const defs: Array<[string, CustomElementConstructor]> = [
    ['vs-status-pill', VsStatusPill], ['vs-status-stepper', VsStatusStepper], ['vs-dialog', VsDialog], ['vs-drawer', VsDrawer],
    ['vs-toaster', VsToaster], ['vs-problem-banner', VsProblemBanner], ['vs-banner', VsBanner], ['vs-empty-state', VsEmptyState],
    ['vs-skeleton', VsSkeleton], ['vs-kpi-tile', VsKpiTile], ['vs-bar-list', VsBarList], ['vs-pagination', VsPagination],
    ['vs-tabs', VsTabs], ['vs-diff-viewer', VsDiffViewer], ['vs-error-summary', VsErrorSummary],
  ];
  for (const [name, ctor] of defs) if (!customElements.get(name)) customElements.define(name, ctor);
}
define();

declare global {
  interface HTMLElementTagNameMap {
    'vs-dialog': VsDialog;
    'vs-drawer': VsDrawer;
    'vs-toaster': VsToaster;
    'vs-error-summary': VsErrorSummary;
  }
}
