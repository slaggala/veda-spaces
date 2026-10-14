import { LitElement, css, html, nothing, type TemplateResult } from 'lit';
import { shared } from '../../design-system/styles.js';
import type { Page, ProposalLine, Room } from './api.js';

const STATE_LABEL: Record<Page['state'], string> = {
  OPEN: 'Open for your review', SUPERSEDED: 'Replaced by a newer version', EXPIRED: 'Past its validity',
  ACCEPTED: 'Accepted', DECLINED: 'Declined', UNAVAILABLE: 'Not available',
};

export const rupees = (v: string | null | undefined) => (v ? `₹ ${v}` : null);

/**
 * <vs-proposal-view>: renders one customer proposal page model (CQX-03 onwards). Pure: it shows exactly what the
 * server sent (the frozen, customer-safe projection and its live state) and raises events for customer actions; it
 * never computes a price. Staff preview reuses it with `preview` set (no actions).
 *
 * Mobile first (360 px upwards): one column, a sticky total bar at the bottom; from 960 px a summary column beside the
 * rooms. Rooms are native <details> (keyboard and screen-reader accessible), opened for printing.
 */
export class VsProposalView extends LitElement {
  static override properties = { page: { attribute: false }, preview: { type: Boolean } };
  declare page: Page | null;
  declare preview: boolean;

  static override styles = [...shared, css`
    :host { display: block; color: var(--vs-ink); }
    a, button, summary, input, select, textarea { min-height: var(--vs-target); }
    a:focus-visible, button:focus-visible, summary:focus-visible, input:focus-visible, select:focus-visible,
    textarea:focus-visible, [tabindex]:focus-visible { outline: 2px solid var(--vs-focus-ring); outline-offset: 2px; }
    .wrap { max-width: 1120px; margin: 0 auto; padding: var(--vs-space-4) var(--vs-space-4) 96px; display: grid; gap: var(--vs-space-5); }
    header.brand { display: flex; flex-direction: column; gap: var(--vs-space-2); border-bottom: 2px solid var(--vs-copper); padding-bottom: var(--vs-space-4); }
    .brandname { font-family: var(--vs-font-serif); font-size: 26px; letter-spacing: .08em; color: var(--vs-copper-text); }
    h1 { font-family: var(--vs-font-serif); font-weight: 500; font-size: 30px; line-height: 36px; margin: 0; overflow-wrap: anywhere; }
    h2 { font-family: var(--vs-font-serif); font-weight: 500; font-size: 24px; line-height: 30px; margin: 0; }
    h3 { font-size: 16px; line-height: 22px; margin: 0; }
    .meta { display: flex; flex-wrap: wrap; gap: var(--vs-space-2) var(--vs-space-4); font-size: 14px; color: var(--vs-ink-muted); }
    .state { display: inline-flex; align-items: center; gap: 6px; font: 600 12px/18px var(--vs-font-sans); letter-spacing: .08em; text-transform: uppercase;
      padding: 4px 10px; border-radius: var(--vs-radius-pill); border: 1px solid var(--vs-line); background: var(--vs-surface); width: fit-content; }
    .state.OPEN { color: var(--vs-success); } .state.SUPERSEDED, .state.EXPIRED, .state.UNAVAILABLE { color: var(--vs-warning); }
    .layout { display: grid; gap: var(--vs-space-5); grid-template-columns: minmax(0, 1fr); }
    @media (min-width: 960px) { .layout { grid-template-columns: minmax(0, 1fr) 320px; } aside .sticky { position: sticky; top: var(--vs-space-4); } .bar { display: none; } }
    .kpis { display: grid; gap: var(--vs-space-3); grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
    .kpi { background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); padding: var(--vs-space-3) var(--vs-space-4); }
    .kpi .n { font: 600 20px/28px var(--vs-font-sans); overflow-wrap: anywhere; }
    nav.rooms ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    nav.rooms a { display: inline-flex; align-items: center; padding: 0 var(--vs-space-3); border: 1px solid var(--vs-line); border-radius: var(--vs-radius-pill);
      color: var(--vs-ink); text-decoration: none; background: var(--vs-surface); font-weight: 500; }
    .cards { display: grid; gap: var(--vs-space-3); grid-template-columns: repeat(auto-fill, minmax(min(100%, 240px), 1fr)); }
    .roomcard { display: flex; flex-direction: column; gap: var(--vs-space-2); text-decoration: none; color: inherit; background: var(--vs-surface);
      border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); overflow: hidden; }
    .roomcard .body { padding: var(--vs-space-3) var(--vs-space-4) var(--vs-space-4); display: flex; flex-direction: column; gap: 4px; }
    .ph { aspect-ratio: 16 / 9; background: var(--vs-cream); display: flex; align-items: center; justify-content: center; color: var(--vs-ink-muted);
      font-family: var(--vs-font-serif); font-size: 20px; text-align: center; padding: var(--vs-space-2); }
    details.room { background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); }
    details.room > summary { display: flex; align-items: center; gap: var(--vs-space-3); padding: var(--vs-space-3) var(--vs-space-4); cursor: pointer; list-style: none; }
    details.room > summary::-webkit-details-marker { display: none; }
    details.room > summary::after { content: '+'; margin-left: auto; font-size: 20px; color: var(--vs-copper-text); }
    details.room[open] > summary::after { content: '−'; }
    .lines { list-style: none; margin: 0; padding: 0 var(--vs-space-4) var(--vs-space-3); }
    .line { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px var(--vs-space-3); padding: var(--vs-space-3) 0; border-top: 1px solid var(--vs-line); }
    .line .amt { text-align: right; white-space: nowrap; font-weight: 600; }
    .line .sub { grid-column: 1 / -1; font-size: 13px; color: var(--vs-ink-muted); overflow-wrap: anywhere; }
    .tag { font: 600 11px/16px var(--vs-font-sans); letter-spacing: .06em; text-transform: uppercase; padding: 1px 8px; border-radius: var(--vs-radius-pill);
      border: 1px solid var(--vs-line); color: var(--vs-ink-muted); margin-left: 6px; white-space: nowrap; }
    .summary dl { display: grid; grid-template-columns: 1fr auto; gap: 6px var(--vs-space-3); margin: 0; }
    .summary dt { color: var(--vs-ink-muted); } .summary dd { margin: 0; text-align: right; font-weight: 600; white-space: nowrap; }
    .summary dt.total, .summary dd.total { font-size: 18px; color: var(--vs-ink); border-top: 2px solid var(--vs-ink); padding-top: 6px; }
    .bar { position: fixed; left: 0; right: 0; bottom: 0; z-index: 10; background: var(--vs-surface); border-top: 1px solid var(--vs-line);
      display: flex; align-items: center; gap: var(--vs-space-3); padding: var(--vs-space-2) var(--vs-space-4); box-shadow: var(--vs-shadow); }
    .bar .n { font: 600 18px/24px var(--vs-font-sans); } .bartotal { display: flex; flex-direction: column; }
    .actions-list { margin: 0; padding-left: 20px; } .actions-list a { color: var(--vs-copper-text); }
    .preview-mark { border: 2px dashed var(--vs-warning); padding: var(--vs-space-2) var(--vs-space-3); border-radius: var(--vs-radius-card); color: var(--vs-warning); font-weight: 600; }
    @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; scroll-behavior: auto !important; } }
    @media print {
      .bar, nav.rooms, .no-print, button { display: none !important; }
      .wrap { padding: 0; } .layout { grid-template-columns: 1fr; } aside .sticky { position: static; }
      details.room { break-inside: avoid; border: 0; } details.room > summary::after { content: ''; }
      .roomcard .ph { display: none; }
    }
  `];

  constructor() {
    super();
    this.page = null;
    this.preview = false;
  }

  override connectedCallback() {
    super.connectedCallback();
    window.addEventListener('beforeprint', this.openAll);
  }

  override disconnectedCallback() {
    window.removeEventListener('beforeprint', this.openAll);
    super.disconnectedCallback();
  }

  /** Print the whole proposal: every room opened first (a closed <details> would print its title only). */
  private openAll = () => {
    this.renderRoot.querySelectorAll('details').forEach((d) => { d.open = true; });
  };

  protected emit(name: string, detail: unknown = null) {
    this.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
  }

  override render() {
    const page = this.page;
    if (!page) return nothing;
    const p = page.proposal;
    return html`<div class="wrap">
      ${this.preview ? html`<div class="preview-mark" role="note">Staff preview: exactly what the customer sees. No action is possible here.</div>` : nothing}
      <header class="brand">
        <div class="brandname" aria-hidden="true">${p.brand.name}</div>
        <span class="eyebrow">${p.kind === 'VARIATION' ? 'Variation to your accepted proposal' : 'Your interior proposal'}</span>
        <h1>${p.subject}</h1>
        <div class="meta"><span>${p.reference}</span><span>Issued ${p.issued_on}</span>
          ${p.valid_until ? html`<span>Valid until ${p.valid_until}</span>` : nothing}
          <span>${p.property.configuration}${p.property.city ? html` · ${p.property.city}` : nothing}</span><span>Property ${p.property.reference}</span></div>
        <span class="state ${page.state}">${STATE_LABEL[page.state]}</span>
      </header>
      ${page.notices.map((n) => html`<vs-banner kind=${n.code === 'ACCEPTED' ? 'success' : n.code === 'LINK_EXPIRES_SOON' ? 'info' : 'warning'}>${n.message}</vs-banner>`)}
      ${p.cover_note ? html`<p>${p.cover_note}</p>` : nothing}
      <div class="layout">
        <main class="stack" aria-label="Proposal">
          ${this.overview(page)}
          ${this.actionsPanel(page)}
          ${this.roomsPanel(page)}
          ${this.sections(page)}
        </main>
        <aside aria-label="Summary"><div class="sticky stack">${this.summary(page)}</div></aside>
      </div>
      ${this.bar(page)}
    </div>`;
  }

  // --- CQX-03 overview ------------------------------------------------------------------------------------------------
  protected overview(page: Page): TemplateResult {
    const p = page.proposal;
    const rooms = p.rooms.filter((r) => r.kind === 'ROOM').length;
    return html`<section aria-labelledby="ov" class="stack"><h2 id="ov" class="sr-only">Overview</h2>
      <div class="kpis">
        <div class="kpi"><div class="eyebrow">${p.kind === 'VARIATION' ? 'Net change' : 'Proposal value'}</div>
          <div class="n">${rupees(p.kind === 'VARIATION' ? p.summary.net_change ?? null : p.summary.total) ?? 'To be confirmed'}</div></div>
        <div class="kpi"><div class="eyebrow">Rooms</div><div class="n">${rooms}</div></div>
        <div class="kpi"><div class="eyebrow">Version</div><div class="n">${p.version_no}</div></div>
        <div class="kpi"><div class="eyebrow">Valid until</div><div class="n">${p.valid_until ?? '—'}</div></div>
      </div>
      ${page.history.length ? html`<p class="small muted">This is version ${p.version_no}. Earlier version${page.history.length > 1 ? 's' : ''}:
        ${page.history.map((h) => `version ${h.version_no} (${h.issued_on ?? ''})`).join(', ')}.</p>` : nothing}
    </section>`;
  }

  protected actionsPanel(page: Page): TemplateResult | typeof nothing {
    if (this.preview || !page.actions.length) return nothing;
    return html`<section class="card stack" aria-labelledby="todo"><h2 id="todo">Your next steps</h2>
      <ol class="actions-list">${page.actions.map((a) => html`<li><a href=${`#${a.target}`} @click=${(e: Event) => this.jump(e, a.target)}>${a.label}</a></li>`)}</ol></section>`;
  }

  protected jump(e: Event, id: string) {
    const el = this.renderRoot.querySelector(`#${CSS.escape(id)}`) as HTMLElement | null;
    if (!el) return;
    e.preventDefault();
    if (el instanceof HTMLDetailsElement) el.open = true;
    const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' });
    el.setAttribute('tabindex', '-1');
    el.focus({ preventScroll: true });
  }

  protected roomsPanel(page: Page): TemplateResult {
    const rooms = page.proposal.rooms;
    return html`<section aria-labelledby="rooms" class="stack"><h2 id="rooms">${page.proposal.kind === 'VARIATION' ? 'Changes' : 'Room by room'}</h2>
      <nav class="rooms" aria-label="Rooms"><ul>${rooms.map((r) => html`<li><a href=${`#${r.ref}`} @click=${(e: Event) => this.jump(e, r.ref)}>${r.title}</a></li>`)}</ul></nav>
      <div class="cards">${rooms.map((r) => this.roomCard(r))}</div>
      ${rooms.map((r) => this.roomDetail(page, r))}
    </section>`;
  }

  protected roomCard(r: Room): TemplateResult {
    return html`<a class="roomcard" href=${`#${r.ref}`} @click=${(e: Event) => this.jump(e, r.ref)} aria-label=${`${r.title}: ${r.included_count} included item${r.included_count === 1 ? '' : 's'}${r.optional_count ? `, ${r.optional_count} optional` : ''}${r.subtotal ? `, ${rupees(r.subtotal)}` : ''}`}>
      ${this.roomImage(r)}
      <div class="body"><h3>${r.title}</h3>
        <span class="small muted">${r.included_count} included${r.optional_count ? html` · ${r.optional_count} optional` : nothing}</span>
        ${r.subtotal ? html`<span class="strong">${rupees(r.subtotal)}</span>` : nothing}</div></a>`;
  }

  /** The room's image slot (CQX-04 adds approved reference images); a named placeholder otherwise. */
  protected roomImage(r: Room): TemplateResult {
    return html`<div class="ph" aria-hidden="true">${r.title}</div>`;
  }

  protected roomDetail(page: Page, r: Room): TemplateResult {
    return html`<details class="room" id=${r.ref}><summary><h3>${r.title}</h3>
        ${r.subtotal ? html`<span class="strong">${rupees(r.subtotal)}</span>` : nothing}</summary>
      <ul class="lines">${r.lines.map((x) => this.line(page, x))}</ul></details>`;
  }

  protected line(_page: Page, x: ProposalLine): TemplateResult {
    return html`<li class="line"><div><span class="strong">${x.description}</span>${x.status !== 'Included' ? html`<span class="tag">${x.status}</span>` : nothing}</div>
      <div class="amt">${x.priced ? rupees(x.amount) : html`<span class="muted">To be confirmed</span>`}</div>
      ${x.detail || x.quantity ? html`<div class="sub">${[x.quantity, x.detail].filter(Boolean).join(' · ')}</div>` : nothing}
      ${x.change ? html`<div class="sub">${x.change}${x.delta ? ` · change ${rupees(x.delta)}` : ''}</div>` : nothing}</li>`;
  }

  /** Later CQX steps add pricing, optional items, terms, questions, comparison and decision sections here. */
  protected sections(_page: Page): TemplateResult | typeof nothing {
    return nothing;
  }

  protected summary(page: Page): TemplateResult {
    const s = page.proposal.summary;
    return html`<section class="card summary stack" aria-labelledby="sum"><h2 id="sum">Summary</h2><dl>
      ${page.proposal.kind === 'VARIATION'
        ? html`<dt>Net change</dt><dd>${rupees(s.net_change ?? null) ?? '—'}</dd>`
        : html`<dt>Total of works</dt><dd>${rupees(s.base_total) ?? '—'}</dd>
          ${s.discount ? html`<dt>Discount</dt><dd>− ${rupees(s.discount)}</dd>` : nothing}`}
      <dt>GST</dt><dd>${s.gst?.amount ? rupees(s.gst.amount) : s.gst?.status ?? 'To be confirmed'}</dd>
      <dt class="total">Total</dt><dd class="total">${rupees(s.total) ?? 'To be confirmed'}</dd>
    </dl></section>`;
  }

  protected bar(page: Page): TemplateResult | typeof nothing {
    if (this.preview) return nothing;
    const s = page.proposal.summary;
    return html`<div class="bar no-print" role="region" aria-label="Proposal total"><div class="bartotal"><span class="eyebrow">Total</span>
      <span class="n">${rupees(s.total) ?? 'To be confirmed'}</span></div><span class="spacer"></span>
      <a class="btn" href="#sum" @click=${(e: Event) => this.jump(e, 'sum')}>Summary</a></div>`;
  }
}

customElements.define('vs-proposal-view', VsProposalView);
