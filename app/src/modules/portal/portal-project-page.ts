import { LitElement, css, html, nothing } from 'lit';
import { forgetSession, portalApi, sessionToken, transient, type Commercials, type Contact, type DocumentEntry, type Entry, type PropertyView } from './api.js';
import { portalStyles, stateBadge, when } from './portal-ui.js';

type Load = 'loading' | 'ready' | 'signed-out' | 'not-found' | 'offline' | 'unavailable';

const SECTIONS = [
  ['attention', 'Needs you'], ['journey', 'Your journey'], ['payments', 'Payments'], ['quotation', 'Quotation'], ['included', "What's included"],
  ['commitments', 'Our commitments'], ['your-part', 'Your part'], ['documents', 'Documents'], ['contact', 'Contact'],
] as const;

/**
 * /portal/properties/:id — one home's project, for the homeowner: where it stands and what comes next first, then what
 * needs them, the journey, the quotation, what is included, what Veda Spaces has committed to, their own part, their
 * documents and their contact. Every value comes from the server, which reads it from its source of truth; anything the
 * server has no authoritative data for is shown as not yet available, never filled in here.
 */
export class VsPortalProjectPage extends LitElement {
  static override properties = { location: { attribute: false }, load: { state: true }, view: { state: true } };
  declare location: { params: Record<string, string> } | undefined;
  declare load: Load;
  declare view: PropertyView | null;

  static override styles = [...portalStyles, css`
    .hero { display: flex; flex-direction: column; gap: var(--vs-space-3); }
    nav.jump { position: sticky; top: 0; z-index: 1; background: var(--vs-paper); padding: var(--vs-space-2) 0; border-bottom: 1px solid var(--vs-line); }
    nav.jump ul { list-style: none; margin: 0; padding: 0; display: flex; gap: var(--vs-space-2); overflow-x: auto; scrollbar-width: thin; }
    nav.jump a { display: inline-flex; align-items: center; min-height: var(--vs-target); padding: 0 var(--vs-space-3); border: 1px solid var(--vs-line); border-radius: var(--vs-radius-pill); white-space: nowrap; text-decoration: none; background: var(--vs-surface); }
    .layout { display: grid; grid-template-columns: 1fr; gap: var(--vs-space-5); }
    @media (min-width: 1024px) { .layout { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); } .side { position: sticky; top: var(--vs-space-8); align-self: start; } }
    .main, .side { display: flex; flex-direction: column; gap: var(--vs-space-5); min-width: 0; }
    ol.journey { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
    ol.journey li { display: grid; grid-template-columns: 28px 1fr; gap: var(--vs-space-3); padding-bottom: var(--vs-space-4); position: relative; }
    ol.journey li::before { content: ''; position: absolute; left: 13px; top: 28px; bottom: 0; width: 2px; background: var(--vs-line); }
    ol.journey li:last-child::before { display: none; }
    .dot { width: 28px; height: 28px; border-radius: 50%; border: 2px solid var(--vs-line); background: var(--vs-surface); display: inline-flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; }
    .dot.COMPLETED { background: var(--vs-success); border-color: var(--vs-success); color: var(--vs-surface); }
    .dot.ACTION_REQUIRED { border-color: var(--vs-copper); color: var(--vs-copper-text); }
    .dot.IN_PROGRESS { border-color: var(--vs-copper-strong); }
    .step { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
    .step-head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--vs-space-2); }
    .action { border: 1px solid var(--vs-copper); }
    details { border-top: 1px solid var(--vs-line); padding: var(--vs-space-2) 0; }
    details:first-of-type { border-top: 0; }
    summary { cursor: pointer; min-height: var(--vs-target); display: flex; align-items: center; justify-content: space-between; gap: var(--vs-space-2); font-weight: 600; }
    summary:focus-visible { outline: 2px solid var(--vs-focus-ring); outline-offset: 2px; }
    .item { display: flex; flex-direction: column; gap: 2px; padding: var(--vs-space-2) 0; border-bottom: 1px dashed var(--vs-line); }
    .item:last-child { border-bottom: 0; }
    .doc { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--vs-space-2); }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: var(--vs-space-2); border-bottom: 1px solid var(--vs-line); vertical-align: top; overflow-wrap: anywhere; }
    th { font-size: 13px; color: var(--vs-ink-muted); font-weight: 600; }
    td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
    .money { display: grid; gap: var(--vs-space-3); grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr)); margin: 0; }
    .money div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .money dt { font-size: 13px; color: var(--vs-ink-muted); }
    .money dd { margin: 0; font-family: var(--vs-font-serif); font-size: 24px; line-height: 30px; font-variant-numeric: lining-nums tabular-nums; overflow-wrap: anywhere; }
    .instalments { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
    .instalments li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--vs-space-1) var(--vs-space-3); padding: var(--vs-space-3) 0; border-bottom: 1px solid var(--vs-line); }
    .instalments li:last-child { border-bottom: 0; }
    .instalments .figures { text-align: right; font-variant-numeric: tabular-nums; }
  `];

  constructor() {
    super();
    this.load = 'loading';
    this.view = null;
  }

  private get routeId(): string { return this.location?.params?.id ?? window.location.pathname.split('/').pop() ?? ''; }

  override connectedCallback() {
    super.connectedCallback();
    if (!sessionToken()) {
      this.load = 'signed-out';
      return;
    }
    void this.fetch();
  }

  private async fetch() {
    this.load = 'loading';
    try {
      this.view = (await portalApi.property(this.routeId)).data;
      this.load = 'ready';
      await this.updateComplete;
      this.renderRoot.querySelector<HTMLElement>('h1')?.focus();
    } catch (e) {
      const p = e as { status: number; code?: string };
      if (p.status === 401) {
        forgetSession();
        this.load = 'signed-out';
      } else {
        this.load = p.status === 404 || p.status === 422 ? 'not-found' : transient(p) ? 'offline' : 'unavailable';
      }
    }
  }

  private entries(items: Entry[] | null | undefined, empty: string) {
    if (!items?.length) return html`<p class="muted">${empty}</p>`;
    return html`<ul class="bullets">${items.map((i) => html`<li>${i.label ? html`<span class="strong">${i.label}:</span> ` : nothing}${i.text}${i.duration ? html` <span class="muted">(${i.duration})</span>` : nothing}</li>`)}</ul>`;
  }

  private contact(c: Contact | null) {
    if (!c?.name) {
      return html`<p class="muted">Contact details are not available in your portal yet. Please use the contact details Veda Spaces gave you.</p>`;
    }
    return html`<div class="stack">
      <p class="strong">${c.name}</p>${c.role ? html`<p class="muted">${c.role}</p>` : nothing}
      ${c.phone ? html`<a class="btn" href="tel:${c.phone}">Call ${c.phone}</a>` : nothing}
      ${c.email ? html`<a class="btn ghost" href="mailto:${c.email}">Email ${c.email}</a>` : nothing}
      ${c.hours ? html`<p class="small muted">${c.hours}</p>` : nothing}
      ${!c.phone && !c.email ? html`<p class="small muted">Your consultant. Contact details will appear here once your quotation is issued.</p>` : nothing}
    </div>`;
  }

  private ready(v: PropertyView) {
    const title = [v.property.configuration, v.property.locality, v.property.city].filter(Boolean).join(' · ') || 'Your home';
    const actions = v.attention.filter((a) => a.status === 'ACTION_REQUIRED');
    const upcoming = v.attention.filter((a) => a.status !== 'ACTION_REQUIRED');
    const c = v.commitments;
    return html`
      <p><a class="back" href="/portal">← All your homes</a></p>
      <section class="hero" aria-labelledby="title">
        <p class="eyebrow">${v.property.reference} · Enquiry ${v.enquiry.reference}</p>
        <h1 id="title" tabindex="-1">${title}</h1>
        <p class="lead-text">${v.headline}</p>
        ${v.next_step ? html`<div class="notice"><p><span class="strong">What happens next:</span> ${v.next_step.label}. ${v.next_step.detail}
          ${v.next_step.date ? html`<span class="muted">(${when(v.next_step.date)})</span>` : nothing}</p></div>` : nothing}
      </section>
      <nav class="jump" aria-label="Sections of this page"><ul>${SECTIONS.map(([id, label]) => html`<li><a href="#${id}" @click=${(e: Event) => this.jump(e, id)}>${label}</a></li>`)}</ul></nav>
      <div class="layout">
        <div class="main">
          <section class="section" id="attention" aria-labelledby="h-attention">
            <h2 id="h-attention" tabindex="-1">Needs you</h2>
            ${actions.length ? actions.map((a) => html`<article class="card action stack">
                <div class="step-head">${stateBadge('ACTION_REQUIRED')}<h3>${a.title}</h3></div>
                <p>${a.text}</p>
                ${a.due ? html`<p class="muted">${a.kind === 'QUOTATION_DECISION' ? 'Valid until' : 'By'} ${when(a.due)}</p>` : nothing}
                ${a.quotation_id ? html`<a class="btn primary" href="/portal/quotations/${a.quotation_id}">View your quotation</a>` : nothing}
                ${a.invoice_id ? html`<a class="btn" href="/portal/invoices/${a.invoice_id}">View the invoice</a>` : nothing}
              </article>`) : html`<p class="card">Nothing needs you right now.</p>`}
            ${upcoming.map((a) => html`<article class="card stack"><div class="step-head">${stateBadge(a.status)}<h3>${a.title}</h3></div>
              <p>${a.text}${a.due ? html` <span class="strong">${when(a.due)}</span>` : nothing}</p></article>`)}
          </section>

          <section class="section" id="journey" aria-labelledby="h-journey">
            <h2 id="h-journey" tabindex="-1">Your journey</h2>
            <ol class="journey card">${v.journey.map((s, i) => html`<li>
              <span class="dot ${s.state}" aria-hidden="true">${s.state === 'COMPLETED' ? '✓' : i + 1}</span>
              <div class="step"><div class="step-head"><h3>${s.label}</h3>${stateBadge(s.state)}</div>
                <p>${s.detail}${s.date ? html` <span class="muted">${when(s.date)}</span>` : nothing}</p></div>
            </li>`)}</ol>
          </section>

          <section class="section" id="payments" aria-labelledby="h-payments">
            <h2 id="h-payments" tabindex="-1">Payments</h2>
            ${this.payments(v.commercials)}
          </section>

          <section class="section" id="quotation" aria-labelledby="h-quotation">
            <h2 id="h-quotation" tabindex="-1">Your quotation</h2>
            ${v.quotation ? html`<article class="card stack">
                <div class="step-head"><h3>${v.quotation.title} ${v.quotation.reference}</h3>${stateBadge(v.quotation.status, v.quotation.status_label)}</div>
                <dl class="facts">
                  ${v.quotation.total ? html`<div><dt>Total</dt><dd class="amount">${v.quotation.total}</dd></div>` : nothing}
                  ${v.quotation.issued_on ? html`<div><dt>Issued</dt><dd>${when(v.quotation.issued_on)}</dd></div>` : nothing}
                  ${v.quotation.valid_until ? html`<div><dt>Valid until</dt><dd>${when(v.quotation.valid_until)}</dd></div>` : nothing}
                </dl>
                ${v.quotation.state === 'OPEN' ? html`<p class="notice">To accept, decline or ask a question, use the secure proposal link Veda Spaces sent you, or speak to your Veda Spaces contact.</p>` : nothing}
                ${v.quotation.state !== 'UNAVAILABLE' ? html`<a class="btn primary" href="/portal/quotations/${v.quotation.id}">View the full quotation</a>` : nothing}
              </article>` : html`<p class="card">Your quotation will appear here once Veda Spaces issues it.</p>`}
          </section>

          <section class="section" id="included" aria-labelledby="h-included">
            <h2 id="h-included" tabindex="-1">What's included</h2>
            ${v.included?.length ? html`<div class="card">${v.included.map((r) => html`<details>
                <summary><span>${r.title}</span><span class="muted small">${r.included_count} included${r.optional_count ? `, ${r.optional_count} optional` : ''}</span></summary>
                ${r.items.map((it) => html`<div class="item"><span>${it.description}</span>
                  ${it.detail ? html`<span class="small muted">${it.detail}</span>` : nothing}
                  ${it.status && it.status !== 'Included' ? html`<span class="small">${it.status}</span>` : nothing}
                  ${it.dimensions?.length ? html`<span class="small muted">${it.dimensions.map((d) => `${d.label} ${d.value}`).join(' · ')}</span>` : nothing}</div>`)}
              </details>`)}</div>` : html`<p class="card muted">The rooms and items of your project appear here once your quotation is issued.</p>`}
          </section>

          <section class="section" id="commitments" aria-labelledby="h-commitments">
            <h2 id="h-commitments" tabindex="-1">What Veda Spaces has committed to</h2>
            ${c ? html`<div class="card stack">
                <p class="small muted">As written in your ${c.source ?? 'quotation'}.</p>
                <h3>Included in your project</h3>${this.entries(c.inclusions, 'To be confirmed by Veda Spaces.')}
                <h3>Warranty</h3>${c.warranty?.length ? html`<ul class="bullets">${c.warranty.map((w) => html`<li>${w}</li>`)}</ul>` : html`<p class="muted">To be confirmed by Veda Spaces.</p>`}
                ${c.manufacturer_warranty_note ? html`<p class="small">${c.manufacturer_warranty_note}</p>` : nothing}
                ${c.payment_schedule?.length ? html`<h3>Payment schedule</h3><div class="table-wrap"><table>
                  <thead><tr><th scope="col">Stage</th><th scope="col">Share</th><th scope="col">When</th></tr></thead>
                  <tbody>${c.payment_schedule.map((m) => html`<tr><td>${m.label}</td><td>${m.share}</td><td>${m.trigger}</td></tr>`)}</tbody></table></div>` : nothing}
                ${c.payment_safety ? html`<p class="notice">${c.payment_safety}</p>` : nothing}
                <h3>At handover</h3>${this.entries(c.handover, 'To be confirmed by Veda Spaces.')}
                <h3>What happens after you accept</h3>${this.entries(c.next_steps, 'To be confirmed by Veda Spaces.')}
              </div>` : html`<p class="card muted">Veda Spaces' commitments to you appear here once your quotation is issued.</p>`}
          </section>

          <section class="section" id="your-part" aria-labelledby="h-your-part">
            <h2 id="h-your-part" tabindex="-1">Your part</h2>
            ${v.responsibilities ? html`<div class="card stack">
                <h3>Your responsibilities</h3>${this.entries(v.responsibilities.client, 'To be confirmed by Veda Spaces.')}
                <h3>Getting your site ready</h3>${this.entries(v.responsibilities.site_readiness, 'To be confirmed by Veda Spaces.')}
              </div>` : html`<p class="card muted">What we will need from you appears here once your quotation is issued.</p>`}
          </section>
        </div>

        <aside class="side" aria-label="Documents and contact">
          <section class="section" id="documents" aria-labelledby="h-documents">
            <h2 id="h-documents" tabindex="-1">Documents</h2>
            <div class="card">${v.documents.length ? html`<ul class="plain">${v.documents.map((d) => this.document(d))}</ul>`
              : html`<p class="muted">No documents yet. Your quotation will be listed here once issued.</p>`}</div>
          </section>
          <section class="section" id="contact" aria-labelledby="h-contact">
            <h2 id="h-contact" tabindex="-1">Your Veda Spaces contact</h2>
            <div class="card">${this.contact(v.contact)}</div>
            ${v.support?.escalation ? html`<p class="small muted">${v.support.escalation}</p>` : nothing}
          </section>
        </aside>
      </div>`;
  }

  private document(d: DocumentEntry) {
    if (d.kind === 'INVOICE' || d.kind === 'RECEIPT') {
      const e = d as Extract<DocumentEntry, { number: string }>;
      const name = `${d.kind === 'INVOICE' ? 'Invoice' : 'Receipt'} ${e.number}`;
      return html`<li class="doc"><span><span class="strong">${name}</span><br /><span class="small muted">${e.issued_on ? `${when(e.issued_on)} · ` : ''}₹ ${e.amount} · ${e.status_label}</span></span>
        <a class="btn" href="/portal/${d.kind === 'INVOICE' ? 'invoices' : 'receipts'}/${e.id}">Open<span class="sr-only"> ${name}</span></a></li>`;
    }
    const q = d as Extract<DocumentEntry, { reference: string }>;
    return html`<li class="doc"><span><span class="strong">${q.title} ${q.reference}</span><br /><span class="small muted">${q.issued_on ? `Issued ${when(q.issued_on)} · ` : ''}${q.status_label}</span></span>
      ${q.state !== 'UNAVAILABLE' ? html`<a class="btn" href="/portal/quotations/${q.id}">Open<span class="sr-only"> ${q.title} ${q.reference}</span></a>` : nothing}</li>`;
  }

  /** What the customer has agreed, paid and still owes, from the server's one calculation. No way to pay here. */
  private payments(c: Commercials | null) {
    if (!c) return html`<p class="card muted">Your payment details appear here once Veda Spaces has set up your project's payment schedule.</p>`;
    if (!c.available || !c.summary) return html`<p class="card" role="status">${c.message ?? 'Your payment details are not available right now.'}</p>`;
    const s = c.summary;
    return html`<div class="card stack">
      <dl class="money">
        <div><dt>Total project value</dt><dd>₹ ${s.total_value}</dd></div>
        <div><dt>Paid</dt><dd>₹ ${s.paid}</dd></div>
        <div><dt>Outstanding</dt><dd>₹ ${s.outstanding}</dd></div>
      </dl>
      ${s.includes_gst ? html`<p class="small muted">The project value includes GST of ₹ ${s.includes_gst}, as in your accepted quotation.</p>` : nothing}
      ${s.next_payment ? html`<div class="notice"><p><span class="strong">Next payment:</span> ${s.next_payment.label}, ₹ ${s.next_payment.amount}
        ${stateBadge(s.next_payment.state, s.next_payment.state_label)}</p>
        <p class="small">${s.next_payment.due_on ? `Due by ${when(s.next_payment.due_on)}.` : `When: ${s.next_payment.when}.`}</p></div>`
        : html`<p class="notice">Nothing is outstanding. Thank you.</p>`}
      ${(c.notices ?? []).map((n) => html`<p class="notice" role="status">${n.message}</p>`)}
      <p class="small muted">${c.how_to_pay} Veda Spaces does not collect payments through this portal.</p>
      ${c.schedule?.length ? html`<h3>Payment schedule</h3><ul class="instalments">${c.schedule.map((x) => html`<li>
          <span><span class="strong">${x.label}</span><br /><span class="small muted">${x.due_on ? `Due by ${when(x.due_on)}` : x.when}</span></span>
          <span class="figures"><span class="strong">₹ ${x.amount}</span><br />${stateBadge(x.state, x.state_label)}
            ${x.state === 'PARTIALLY_PAID' || x.state === 'OVERDUE' ? html`<br /><span class="small muted">Paid ₹ ${x.paid}, ₹ ${x.remaining} to go</span>` : nothing}</span>
        </li>`)}</ul>` : nothing}
      <h3>Payments recorded</h3>
      ${c.payments?.length ? html`<ul class="instalments">${c.payments.map((p) => html`<li>
          <span><span class="strong">₹ ${p.amount}</span> <span class="badge ${p.status}">${p.status_label}</span><br />
            <span class="small muted">${when(p.received_on)} · ${p.method}${p.reference ? ` · ${p.reference}` : ''}</span>
            ${p.note ? html`<br /><span class="small">${p.note}</span>` : nothing}
            ${p.correction ? html`<br /><span class="small">${p.correction}</span>` : nothing}</span>
          <span>${p.receipt ? html`<a class="btn" href="/portal/receipts/${p.receipt.id}">Receipt<span class="sr-only"> ${p.receipt.number}</span></a>` : nothing}</span>
        </li>`)}</ul>` : html`<p class="muted">No payments recorded yet.</p>`}
    </div>`;
  }

  /** In-page navigation: scroll to the section and move focus to its heading (screen readers follow). */
  private jump(e: Event, id: string) {
    e.preventDefault();
    const heading = this.renderRoot.querySelector<HTMLElement>(`#h-${id}`);
    heading?.scrollIntoView({ block: 'start' });
    heading?.focus({ preventScroll: true });
  }

  private content() {
    switch (this.load) {
      case 'loading':
        return html`<div class="card" role="status" aria-live="polite"><vs-skeleton rows="8"></vs-skeleton><span class="sr-only">Loading your project…</span></div>`;
      case 'signed-out':
        return html`<vs-portal-sign-in notice="Please sign in to see your project."></vs-portal-sign-in>`;
      case 'not-found':
        return html`<div class="card" role="alert"><h1 tabindex="-1">We could not find this project</h1><p>It may not be linked to your portal.</p>
          <a class="btn primary" href="/portal">Go to your portal</a></div>`;
      case 'offline':
        return html`<div class="card" role="alert"><h1>We could not load your project</h1><p>Check your connection and try again.</p>
          <button class="btn primary" @click=${() => void this.fetch()}>Try again</button></div>`;
      case 'unavailable':
        return html`<div class="card" role="alert"><h1>Your project cannot be shown right now</h1><p>Please try again later or contact Veda Spaces.</p></div>`;
      default:
        return this.ready(this.view!);
    }
  }

  override render() {
    return html`<vs-portal-header ?signed-in=${this.load !== 'signed-out'}></vs-portal-header><main class="wrap" id="main">${this.content()}</main>`;
  }
}
customElements.define('vs-portal-project-page', VsPortalProjectPage);
