import { LitElement, css, html, nothing, type TemplateResult } from 'lit';
import { shared } from '../../design-system/styles.js';
import { mediaUrl, type MediaImage, type Page, type ProposalLine, type Room } from './api.js';

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
  static override properties = { page: { attribute: false }, preview: { type: Boolean }, gallery: { state: true }, failed: { state: true } };
  declare page: Page | null;
  declare preview: boolean;
  declare gallery: { title: string; images: MediaImage[]; index: number } | null;
  /** Rooms whose image failed to load: they show the named placeholder instead. */
  declare failed: ReadonlySet<string>;

  static override styles = [...shared, css`
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
    .table-like { display: grid; } .tr { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--vs-space-3); padding: 8px 0; border-top: 1px solid var(--vs-line); }
    .tr.head { font: 600 11px/16px var(--vs-font-sans); letter-spacing: .14em; text-transform: uppercase; color: var(--vs-ink-muted); border-top: 0; }
    .tr .num { text-align: right; white-space: nowrap; } .tr.total { font-weight: 700; font-size: 18px; border-top: 2px solid var(--vs-ink); }
    .milestones { margin: 0; padding-left: 20px; }
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
    return html`${this.pricingPanel(page)}`;
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
