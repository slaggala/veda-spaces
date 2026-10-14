import { LitElement, css, html, nothing, type TemplateResult } from 'lit';
import type { VsErrorSummary } from '../../design-system/components.js';
import { shared } from '../../design-system/styles.js';
import { mediaUrl, type Comparison, type MediaImage, type Page, type ProposalLine, type Room, type VariationView } from './api.js';

/** Row-and-column layout that never scrolls sideways (tables become stacked rows on narrow screens). */
export const tableLikeStyles = css`
    .table-like { display: grid; } .tr { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--vs-space-3); padding: 8px 0; border-top: 1px solid var(--vs-line); }
    .tr.head { font: 600 11px/16px var(--vs-font-sans); letter-spacing: .14em; text-transform: uppercase; color: var(--vs-ink-muted); border-top: 0; }
    .tr .num { text-align: right; white-space: nowrap; } .tr.total { font-weight: 700; font-size: 18px; border-top: 2px solid var(--vs-ink); }
    .tr.var { grid-template-columns: minmax(0, 2fr) minmax(0, 1.2fr) repeat(3, auto); }
    @media (max-width: 599px) { .tr.var { grid-template-columns: minmax(0, 1fr) auto; } .tr.var > :nth-child(3), .tr.var > :nth-child(4) { display: none; } }
`;

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
  static override properties = {
    page: { attribute: false }, preview: { type: Boolean }, gallery: { state: true }, failed: { state: true },
    announcement: { type: String }, busy: { type: Boolean }, errors: { attribute: false }, askCategory: { state: true },
    comparison: { attribute: false },
  };
  /** The comparison with the version issued before this one, once the customer asked for it. */
  declare comparison: Comparison | null;
  /** The category chosen in the question form (decides which fields it asks for). */
  declare askCategory: string;
  /** Polite screen-reader announcement of the last action's result (set by the page). */
  declare announcement: string;
  /** An action is in flight: controls are disabled (slow networks never double-submit). */
  declare busy: boolean;
  /** Field errors of the last action, shown in an error summary. */
  declare errors: { field: string; message: string }[];
  declare page: Page | null;
  declare preview: boolean;
  declare gallery: { title: string; images: MediaImage[]; index: number } | null;
  /** Rooms whose image failed to load: they show the named placeholder instead. */
  declare failed: ReadonlySet<string>;

  static override styles = [...shared, tableLikeStyles, css`
    :host { display: block; color: var(--vs-ink); }
    a, button, summary, input, select, textarea { min-height: var(--vs-target); }
    a:focus-visible, button:focus-visible, summary:focus-visible, input:focus-visible, select:focus-visible,
    textarea:focus-visible, [tabindex]:focus-visible { outline: 2px solid var(--vs-focus-ring); outline-offset: 2px; }
    .wrap { max-width: 1120px; margin: 0 auto; padding: var(--vs-space-4) var(--vs-space-4) 96px; display: grid; gap: var(--vs-space-5); }
    .brand { display: flex; flex-direction: column; gap: var(--vs-space-2); border-bottom: 2px solid var(--vs-copper); padding-bottom: var(--vs-space-4); }
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
    figure { margin: 0; } img { max-width: 100%; display: block; }
    .thumb { position: relative; aspect-ratio: 16 / 9; overflow: hidden; background: var(--vs-cream); }
    .thumb img { width: 100%; height: 100%; object-fit: cover; }
    .imglabel { position: absolute; left: 8px; bottom: 8px; font: 600 11px/16px var(--vs-font-sans); padding: 2px 8px; border-radius: var(--vs-radius-pill);
      background: var(--vs-surface); color: var(--vs-ink); border: 1px solid var(--vs-line); }
    .thumbs { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: var(--vs-space-2); align-items: flex-start; }
    .thumbs .sub { flex-basis: 100%; margin: 0; }
    .thumbbtn { position: relative; padding: 0; border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); overflow: hidden; width: 120px; height: 80px;
      background: var(--vs-cream); cursor: pointer; } .thumbbtn img { width: 100%; height: 100%; object-fit: cover; }
    details.spec { grid-column: 1 / -1; } details.spec > summary { cursor: pointer; color: var(--vs-copper-text); font-weight: 600; display: flex; align-items: center; }
    .speccat h4 { margin: var(--vs-space-2) 0 0; font-size: 14px; } .speccat p { margin: 4px 0; font-size: 14px; }
    .speccat dl { display: grid; grid-template-columns: minmax(110px, auto) 1fr; gap: 2px var(--vs-space-3); margin: 0; font-size: 13px; }
    .speccat dt { color: var(--vs-ink-muted); } .speccat dd { margin: 0; overflow-wrap: anywhere; }
    figure.big img { width: 100%; max-height: 70vh; object-fit: contain; } figure.big figcaption { margin-top: var(--vs-space-2); }
    .milestones { margin: 0; padding-left: 20px; }
    fieldset.optitem { border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); padding: var(--vs-space-3) var(--vs-space-4); margin: 0;
      display: grid; gap: var(--vs-space-2); min-width: 0; }
    fieldset.optitem legend { padding: 0 4px; overflow-wrap: anywhere; }
    .optrow { display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--vs-space-2); font-size: 14px; }
    .choices { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .choice { display: inline-flex; align-items: center; gap: 8px; min-height: var(--vs-target); padding: 0 var(--vs-space-3);
      border: 1px solid var(--vs-line); border-radius: var(--vs-radius-control); cursor: pointer; background: var(--vs-surface); }
    .choice input { width: 20px; height: 20px; min-height: 0; margin: 0; }
    .tr.cmp { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) auto; }
    .term .termbody { padding: 0 var(--vs-space-4) var(--vs-space-3); } .term ul { margin: 0 0 var(--vs-space-2); padding-left: 20px; }
    .tag.ok { color: var(--vs-success); }
    .requests { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--vs-space-3); }
    .request { border-top: 1px solid var(--vs-line); padding-top: var(--vs-space-3); }
    .msg, .reply { margin: 4px 0; white-space: pre-wrap; overflow-wrap: anywhere; } .reply { padding-left: var(--vs-space-3); border-left: 2px solid var(--vs-copper); }
    textarea, select, input:not([type=radio]) { font: inherit; padding: 8px 10px; border: 1px solid var(--vs-line); border-radius: var(--vs-radius-control);
      background: var(--vs-surface); color: var(--vs-ink); max-width: 100%; box-sizing: border-box; width: 100%; }
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
    this.gallery = null;
    this.failed = new Set();
    this.announcement = '';
    this.busy = false;
    this.errors = [];
    this.askCategory = 'GENERAL_QUESTION';
    this.comparison = null;
  }

  override connectedCallback() {
    super.connectedCallback();
    window.addEventListener('beforeprint', this.openAll);
  }

  override disconnectedCallback() {
    window.removeEventListener('beforeprint', this.openAll);
    super.disconnectedCallback();
  }

  /** A failed action moves focus to its error summary (AX-03). */
  override updated(changed: Map<string, unknown>) {
    if (changed.has('errors') && this.errors.length) {
      void this.updateComplete.then(() => (this.renderRoot.querySelector('vs-error-summary') as VsErrorSummary | null)?.focusSummary());
    }
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
      <div class="brand">
        <div class="brandname" aria-hidden="true">${p.brand.name}</div>
        <span class="eyebrow">${p.kind === 'VARIATION' ? 'Variation to your accepted proposal' : 'Your interior proposal'}</span>
        <h1>${p.subject}</h1>
        <div class="meta"><span>${p.reference}</span><span>Issued ${p.issued_on}</span>
          ${p.valid_until ? html`<span>Valid until ${p.valid_until}</span>` : nothing}
          <span>${p.property.configuration}${p.property.city ? html` · ${p.property.city}` : nothing}</span><span>Property ${p.property.reference}</span></div>
        <span class="state ${page.state}">${STATE_LABEL[page.state]}</span>
      </div>
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
      ${this.galleryDialog()}
      <div class="sr-only" role="status" aria-live="polite">${this.announcement}</div>
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

  /** The room's first approved reference image, or a named placeholder (missing-image fallback). */
  protected roomImage(r: Room): TemplateResult {
    const img = this.page?.media?.rooms?.[r.ref];
    if (!img || this.failed.has(r.ref)) return html`<div class="ph" aria-hidden="true">${r.title}</div>`;
    // A failed image becomes the named placeholder; nothing critical is ever shown only as an image.
    return html`<figure class="thumb"><img src=${mediaUrl(img.urls.mobile ?? img.urls.thumb)} alt=${img.alt} loading="lazy"
      @error=${() => { this.failed = new Set([...this.failed, r.ref]); }}><figcaption class="imglabel">${img.label}</figcaption></figure>`;
  }

  protected roomDetail(page: Page, r: Room): TemplateResult {
    return html`<details class="room" id=${r.ref}><summary><h3>${r.title}</h3>
        ${r.subtotal ? html`<span class="strong">${rupees(r.subtotal)}</span>` : nothing}</summary>
      <ul class="lines">${r.lines.map((x) => this.line(page, x))}</ul></details>`;
  }

  protected line(page: Page, x: ProposalLine): TemplateResult {
    const specs = page.specifications?.lines?.[x.ref] ?? [];
    const images = page.media?.lines?.[x.ref] ?? [];
    return html`<li class="line"><div><span class="strong">${x.description}</span>${x.status !== 'Included' ? html`<span class="tag">${x.status}</span>` : nothing}</div>
      <div class="amt">${x.priced ? rupees(x.amount) : html`<span class="muted">To be confirmed</span>`}</div>
      ${x.detail || x.quantity ? html`<div class="sub">${[x.quantity, x.detail].filter(Boolean).join(' · ')}</div>` : nothing}
      ${x.unit_rate ? html`<div class="sub">Rate ${rupees(x.unit_rate)}</div>` : nothing}
      ${x.change ? html`<div class="sub">${x.change}${x.delta ? ` · change ${rupees(x.delta)}` : ''}</div>` : nothing}
      ${images.length ? this.thumbs(x.description, images) : nothing}
      ${specs.length ? html`<details class="spec"><summary>Materials and specification</summary>${specs.map((c) => html`<div class="speccat">
          <h4>${c.label}</h4><p>${c.summary}</p>
          <dl>${this.spec('Requirement', c.requirement)}${this.spec('Grade', c.grade)}${this.spec('Thickness', c.thickness)}
            ${this.spec('Finish', c.finish)}${this.spec('Brand examples', c.brand_examples)}${this.spec('Approved equivalents', c.equivalent_rule)}
            ${this.spec('Final selection', c.final_selection)}${this.spec('Material warranty', c.warranty_summary)}</dl></div>`)}
        <p class="small muted">Specification ${page.specifications?.name} (version ${page.specifications?.version}), as approved when this proposal was issued.</p></details>` : nothing}</li>`;
  }

  private spec(label: string, value: string | null) {
    return value ? html`<dt>${label}</dt><dd>${value}</dd>` : nothing;
  }

  private thumbs(title: string, images: MediaImage[]) {
    return html`<div class="thumbs" role="group" aria-label=${`Reference images: ${title}`}>
      ${images.map((img, i) => html`<button class="thumbbtn" aria-label=${`Open image ${i + 1} of ${images.length}: ${img.alt} (${img.label})`}
        @click=${() => { this.gallery = { title, images, index: i }; }}><img src=${mediaUrl(img.urls.thumb ?? img.urls.mobile)} alt="" loading="lazy"
        @error=${(e: Event) => { (e.target as HTMLElement).closest('button')?.remove(); }}><span class="imglabel">${img.label}</span></button>`)}
      <p class="sub">${this.page?.media?.note ?? ''}</p></div>`;
  }

  protected galleryDialog(): TemplateResult | typeof nothing {
    const g = this.gallery;
    if (!g) return nothing;
    const img = g.images[g.index];
    const go = (d: number) => { this.gallery = { ...g, index: (g.index + d + g.images.length) % g.images.length }; };
    return html`<vs-dialog open wide heading=${g.title} @close=${() => { this.gallery = null; }}>
      <figure class="big"><img src=${mediaUrl(img.urls.desktop ?? img.urls.mobile ?? img.urls.thumb)} alt=${img.alt}>
        <figcaption><span class="tag">${img.label}</span> ${img.caption ?? img.title}</figcaption></figure>
      <p class="small muted">${this.page?.media?.note ?? ''}</p>
      ${g.images.length > 1 ? html`<div slot="actions"><button class="btn" @click=${() => go(-1)}>Previous</button>
        <span role="status" class="small">${g.index + 1} of ${g.images.length}</span><button class="btn" @click=${() => go(1)}>Next</button></div>` : nothing}
    </vs-dialog>`;
  }

  /** The proposal's sections after the rooms, in reading order. */
  protected sections(page: Page): TemplateResult {
    return html`${this.errors.length ? html`<vs-error-summary .errors=${this.errors}></vs-error-summary>` : nothing}
      ${page.variation ? variationTable(page.variation) : nothing}
      ${this.optionalPanel(page)}${this.pricingPanel(page)}${this.termsPanel(page)}${this.comparePanel(page)}${this.questionsPanel(page)}`;
  }

  // --- CQX-09 terms and acknowledgements -----------------------------------------------------------------------------
  protected termsPanel(page: Page): TemplateResult | typeof nothing {
    const t = page.terms;
    if (!t) return nothing;
    const can = page.capabilities.interaction && !this.preview;
    return html`<section class="card stack" aria-labelledby="tm" id="terms"><h2 id="tm">Terms and what is included</h2>
      ${t.policy_decided && t.pending.length && can ? html`<p class="small">Before you can accept, please read and acknowledge the sections marked "required".</p>` : nothing}
      ${t.sections.map((x) => html`<details class="room term" id=${`term-${x.code}`}><summary><h3>${x.title}</h3>
          ${x.required ? html`<span class="tag">Required</span>` : nothing}${x.acknowledged_on ? html`<span class="tag ok">Acknowledged</span>` : nothing}</summary>
        <div class="termbody">${x.available
          ? html`<ul>${x.items.map((i) => html`<li>${i}</li>`)}</ul>`
          : html`<p class="muted">To be confirmed by Veda Spaces. This is not part of the proposal until it is confirmed.</p>`}
          ${x.code === 'WARRANTY' ? html`<p class="small muted">Warranty is shown as approved; Veda Spaces' own service support is a separate section.</p>` : nothing}
          ${can && x.available ? (x.acknowledged_on
            ? html`<p class="small">You acknowledged this section on ${x.acknowledged_on.slice(0, 10)}.</p>`
            : html`<button class="btn" ?disabled=${this.busy} @click=${() => this.emit('proposal-ack', { section: x.code, sha256: x.sha256, title: x.title })}>
                I have read and understood: ${x.title}</button>`) : nothing}</div></details>`)}
    </section>`;
  }

  // --- CQX-08 comparison with the previous version -------------------------------------------------------------------
  protected comparePanel(page: Page): TemplateResult | typeof nothing {
    if (!page.comparison_available || this.preview) return nothing;
    const c = this.comparison;
    const word = { ADDED: 'Added', CHANGED: 'Changed', REMOVED: 'Removed' } as const;
    return html`<section class="card stack" aria-labelledby="cmp" id="compare"><h2 id="cmp">What changed from the previous version</h2>
      ${c ? html`<p>Version ${c.from_version}: ${rupees(c.total_before) ?? '—'} → version ${c.to_version}: <span class="strong">${rupees(c.total_after) ?? '—'}</span></p>
        ${c.changes.length ? html`<div class="table-like" role="table" aria-label="Changes between versions">
          <div role="row" class="tr head cmp"><span role="columnheader">Item</span><span role="columnheader">Change</span><span role="columnheader" class="num">Before → after</span></div>
          ${c.changes.map((x) => html`<div role="row" class="tr cmp"><span role="cell">${x.description}${x.room ? html`<br><span class="small muted">${x.room}</span>` : nothing}</span>
            <span role="cell">${word[x.change]}${x.quantity_before !== x.quantity_after && (x.quantity_before || x.quantity_after) ? html`<br><span class="small muted">${x.quantity_before ?? '—'} → ${x.quantity_after ?? '—'}</span>` : nothing}</span>
            <span role="cell" class="num">${rupees(x.before) ?? '—'} → ${rupees(x.after) ?? '—'}</span></div>`)}</div>`
          : html`<p>No item changed.</p>`}`
        : html`<p>See exactly what is different from the version you received before.</p>
          <div><button class="btn" ?disabled=${this.busy} @click=${() => this.emit('proposal-compare')}>Show the changes</button></div>`}
    </section>`;
  }

  // --- CQX-07 questions and change requests -------------------------------------------------------------------------
  protected questionsPanel(page: Page): TemplateResult | typeof nothing {
    const r = page.requests;
    if (!r || this.preview) return nothing;
    const cats: [string, string][] = [['GENERAL_QUESTION', 'A question about the proposal'], ['LINE_QUESTION', 'A question about an item'],
      ['ADD_ITEM', 'Add an item'], ['REMOVE_ITEM', 'Remove an item'], ['CHANGE_QUANTITY', 'Change a quantity'],
      ['CHANGE_MATERIAL', 'Change a material'], ['CHANGE_FINISH', 'Change a finish'], ['DISCUSS_PRICE', 'Discuss the price']];
    const needsLine = ['LINE_QUESTION', 'REMOVE_ITEM', 'CHANGE_QUANTITY', 'CHANGE_MATERIAL', 'CHANGE_FINISH'].includes(this.askCategory);
    const allLines = [...page.proposal.rooms.flatMap((room) => room.lines.map((x) => ({ ...x, room_title: room.title }))), ...page.proposal.optional_items];
    const submit = (e: Event) => {
      e.preventDefault();
      const form = e.target as HTMLFormElement;
      const f = new FormData(form);
      const body: Record<string, unknown> = { category: this.askCategory, message: String(f.get('message') ?? '') };
      if (needsLine) body.line_ref = f.get('line') || null;
      if (this.askCategory === 'ADD_ITEM' && f.get('room')) body.room_ref = f.get('room');
      if (this.askCategory === 'CHANGE_QUANTITY' && f.get('quantity')) body.requested_quantity = f.get('quantity');
      this.emit('proposal-ask', { body, form });
    };
    return html`<section class="card stack" aria-labelledby="qs" id="questions"><h2 id="qs">Questions and changes</h2>
      <p class="small muted">Ask anything, or tell us what you would like changed. Your message goes to Veda Spaces; it does not change this proposal. If a change is agreed, you will receive a revised proposal.</p>
      ${r.items.length ? html`<ol class="requests">${r.items.map((i) => html`<li class="request">
          <div class="optrow"><span class="strong">${i.category_label}${i.room ? html` · ${i.room}` : nothing}</span><span class="tag">${i.status_label}</span></div>
          <p class="msg">${i.message}</p>${i.requested_quantity ? html`<p class="small">Requested quantity: ${i.requested_quantity}</p>` : nothing}
          ${i.response ? html`<p class="reply"><span class="small muted">Veda Spaces:</span> ${i.response}</p>` : nothing}
          ${i.answered_by_revision ? html`<p class="small">Answered in ${i.answered_by_revision}.</p>` : nothing}</li>`)}</ol>` : nothing}
      ${r.can_ask ? html`<form class="stack" @submit=${submit} novalidate>
          <label class="field"><span class="label">What is it about?</span>
            <select name="category" @change=${(e: Event) => { this.askCategory = (e.target as HTMLSelectElement).value; }} ?disabled=${this.busy}>
              ${cats.map(([v, l]) => html`<option value=${v} ?selected=${v === this.askCategory}>${l}</option>`)}</select></label>
          ${needsLine ? html`<label class="field"><span class="label">Which item?</span><select name="line" required ?disabled=${this.busy}>
              <option value="">Choose an item</option>${allLines.map((x) => html`<option value=${x.ref}>${x.room_title ? `${x.room_title} – ` : ''}${x.description}</option>`)}</select></label>` : nothing}
          ${this.askCategory === 'ADD_ITEM' ? html`<label class="field"><span class="label">Which room? (optional)</span><select name="room" ?disabled=${this.busy}>
              <option value="">Anywhere / not sure</option>${page.proposal.rooms.map((room) => html`<option value=${room.ref}>${room.title}</option>`)}</select></label>` : nothing}
          ${this.askCategory === 'CHANGE_QUANTITY' ? html`<label class="field"><span class="label">What quantity would you like?</span>
              <input name="quantity" maxlength="40" autocomplete="off" ?disabled=${this.busy}></label>` : nothing}
          <label class="field"><span class="label">Your message</span><textarea name="message" required minlength="3" maxlength="2000" rows="4" ?disabled=${this.busy}></textarea>
            <span class="hint">Up to 2000 characters. Please do not include payment or bank details.</span></label>
          <div><button class="btn primary" ?disabled=${this.busy}>Send to Veda Spaces</button></div></form>`
        : html`<p class="muted">Questions and change requests are not available on this proposal here. Please contact your Veda Spaces representative.</p>`}
    </section>`;
  }

  // --- CQX-06 optional items ------------------------------------------------------------------------------------------
  protected optionalPanel(page: Page): TemplateResult | typeof nothing {
    const items = page.proposal.optional_items;
    if (!items.length) return nothing;
    const states = new Map((page.selections?.items ?? []).map((i) => [i.ref, i.state]));
    const can = page.capabilities.interaction && !this.preview;
    const sel = page.selections;
    const choices: [string, string][] = [['SELECTED', 'Add to my proposal'], ['DESELECTED', 'Not for me'], ['REQUESTED_FOR_DISCUSSION', 'I would like to discuss it']];
    return html`<section class="card stack" aria-labelledby="opt" id="optional"><h2 id="opt">Optional items</h2>
      <p class="small muted">Optional items are not in the total. Your choice is sent to Veda Spaces for review; it does not change the proposal by itself.</p>
      ${items.map((x) => {
        const state = states.get(x.ref) ?? 'NOT_SELECTED';
        const images = page.media?.lines?.[x.ref] ?? [];
        return html`<fieldset class="optitem" ?disabled=${!can || this.busy}><legend><span class="strong">${x.description}</span>
            ${x.room_title ? html`<span class="small muted"> · ${x.room_title}</span>` : nothing}</legend>
          <div class="optrow"><span>${[x.quantity, x.detail].filter(Boolean).join(' · ')}</span>
            <span class="strong">${x.priced ? rupees(x.amount) : 'Price to be confirmed'}</span></div>
          ${images.length ? this.thumbs(x.description, images) : nothing}
          ${can ? html`<div class="choices">${choices.map(([value, label]) => html`<label class="choice">
              <input type="radio" name=${`opt-${x.ref}`} .value=${value} ?checked=${state === value} ?disabled=${value === 'SELECTED' && !x.priced}
                @change=${() => this.emit('proposal-select', { line_ref: x.ref, state: value, description: x.description })}>${label}</label>`)}</div>`
            : html`<p class="small">Your choice: ${{ NOT_SELECTED: 'not chosen', SELECTED: 'added', DESELECTED: 'not for me', REQUESTED_FOR_DISCUSSION: 'to discuss' }[state]}</p>`}
        </fieldset>`;
      })}
      ${sel && sel.selected_refs.length ? html`<p class="strong" aria-live="polite">${sel.status === 'CALCULATED'
        ? html`With your choices: ${rupees(sel.total_with_selections)} (adds ${rupees(sel.extra)}), subject to Veda Spaces' confirmation.`
        : html`PRICE CONFIRMATION REQUIRED: Veda Spaces will confirm the price of your choices.`}</p>` : nothing}
    </section>`;
  }

  // --- CQX-05 price and payment ---------------------------------------------------------------------------------------
  protected pricingPanel(page: Page): TemplateResult | typeof nothing {
    const pr = page.pricing;
    if (!pr) return nothing;
    return html`<section class="card stack" aria-labelledby="price" id="pricing"><h2 id="price">Price and payment</h2>
      ${pr.package ? html`<p>Package: <span class="strong">${pr.package}</span></p>` : nothing}
      <div class="table-like" role="table" aria-label="Room subtotals">
        <div role="row" class="tr head"><span role="columnheader">Room</span><span role="columnheader" class="num">Amount</span></div>
        ${pr.rooms.map((r) => html`<div role="row" class="tr"><span role="cell">${r.title}</span><span role="cell" class="num">${rupees(r.subtotal) ?? '—'}</span></div>`)}
        ${pr.discount ? html`<div role="row" class="tr"><span role="cell">Discount</span><span role="cell" class="num">− ${rupees(pr.discount)}</span></div>` : nothing}
        <div role="row" class="tr"><span role="cell">GST</span><span role="cell" class="num">${pr.gst?.amount ? rupees(pr.gst.amount) : pr.gst?.status ?? 'To be confirmed'}</span></div>
        <div role="row" class="tr total"><span role="cell">Total</span><span role="cell" class="num">${rupees(pr.total) ?? 'To be confirmed'}</span></div>
      </div>
      ${pr.optional_total ? html`<p class="small muted">Optional items are not included in the total. If you chose all of them they would add ${rupees(pr.optional_total)} before any confirmation by Veda Spaces.</p>` : nothing}
      <p class="small muted">${pr.unit_rates_shown ? 'Unit rates are shown on each line.' : 'Amounts are shown per item, room and project; unit rates are not part of this proposal.'}</p>
      ${pr.milestones.length ? html`<h3>Payment milestones</h3><ol class="milestones">${pr.milestones.map((m) => html`<li><span class="strong">${m.label}</span> — ${m.share} · ${m.trigger}</li>`)}</ol>`
        : html`<p class="muted">Payment milestones will be confirmed by Veda Spaces.</p>`}
      ${pr.valid_until ? html`<p>Valid until <span class="strong">${pr.valid_until}</span>${pr.days_left !== null && pr.days_left >= 0 ? html` (${pr.days_left} day${pr.days_left === 1 ? '' : 's'} left)` : nothing}.</p>` : nothing}
      ${pr.alternatives.length ? html`<h3>Other packages shared with you</h3><div class="table-like" role="table" aria-label="Packages">
        <div role="row" class="tr head"><span role="columnheader">Proposal</span><span role="columnheader" class="num">Total</span></div>
        <div role="row" class="tr"><span role="cell">${page.proposal.reference}${pr.package ? ` · ${pr.package}` : ''} (this one)</span><span role="cell" class="num">${rupees(pr.total) ?? '—'}</span></div>
        ${pr.alternatives.map((a) => html`<div role="row" class="tr"><span role="cell">${a.reference}${a.package ? ` · ${a.package}` : ''}</span><span role="cell" class="num">${rupees(a.total) ?? '—'}</span></div>`)}
        </div><p class="small muted">Each proposal has its own link from Veda Spaces.</p>` : nothing}
    </section>`;
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

/** A variation beside the accepted baseline (CQX-08): shared by the customer page and the staff preview. */
export function variationTable(v: VariationView): TemplateResult {
  return html`<section class="card stack" aria-labelledby="var" id="variation"><h2 id="var">Changes to your accepted proposal</h2>
    <p class="small muted">Compared with your accepted proposal ${v.baseline_reference}. Your accepted proposal itself does not change.</p>
    <div class="table-like" role="table" aria-label="Changes">
      <div role="row" class="tr head var"><span role="columnheader">Item</span><span role="columnheader">Change</span><span role="columnheader" class="num">Before</span>
        <span role="columnheader" class="num">After</span><span role="columnheader" class="num">Difference</span></div>
      ${v.changes.map((x) => html`<div role="row" class="tr var"><span role="cell">${x.description}${x.room ? html`<br><span class="small muted">${x.room}</span>` : nothing}</span>
        <span role="cell">${x.change_label}${x.quantity_before || x.quantity_after ? html`<br><span class="small muted">${x.quantity_before ?? '—'} → ${x.quantity_after ?? '—'}</span>` : nothing}</span>
        <span role="cell" class="num">${rupees(x.amount_before) ?? '—'}</span><span role="cell" class="num">${x.priced ? rupees(x.amount_after) ?? '—' : 'To be confirmed'}</span>
        <span role="cell" class="num">${rupees(x.delta) ?? '—'}</span></div>`)}
      <div role="row" class="tr var total"><span role="cell">Net change</span><span role="cell"></span><span role="cell"></span><span role="cell"></span>
        <span role="cell" class="num">${rupees(v.net_change) ?? '—'}</span></div>
    </div>
    <p>GST on the change: ${v.gst.amount ? rupees(v.gst.amount) : v.gst.status}. ${v.net_change_with_gst ? html`Net change with GST: <span class="strong">${rupees(v.net_change_with_gst)}</span>.` : nothing}</p>
    ${v.kept_choices.length ? html`<p class="small">Kept from your accepted choices: ${v.kept_choices.map((k) => k.description).join('; ')}.</p>` : nothing}
    ${v.accepted_value ? html`<p class="small">Accepted value so far: ${rupees(v.accepted_value)}${v.value_if_accepted ? html` · if you accept this change: ${rupees(v.value_if_accepted)}` : nothing}.</p>` : nothing}
  </section>`;
}
