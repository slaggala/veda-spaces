import { LitElement, css, html, nothing } from 'lit';
import { newIdempotencyKey } from '../../core/api/client.js';
import {
  forgetSession, portalApi, sessionToken, transient, type Commercials, type Contact, type DeliveryProject, type DocumentEntry, type Entry, type ProjectDocument,
  type PropertyView,
} from './api.js';
import { portalStyles, stateBadge, when } from './portal-ui.js';

type Load = 'loading' | 'ready' | 'signed-out' | 'not-found' | 'offline' | 'unavailable';

const SECTIONS = [
  ['attention', 'Needs you'], ['journey', 'Your journey'], ['delivery', 'Work on your home'], ['payments', 'Payments'], ['quotation', 'Quotation'], ['included', "What's included"],
  ['commitments', 'Our commitments'], ['your-part', 'Your part'], ['documents', 'Documents'], ['contact', 'Contact'],
] as const;

/**
 * /portal/properties/:id — one home's project, for the homeowner: where it stands and what comes next first, then what
 * needs them, the journey, the quotation, what is included, what Veda Spaces has committed to, their own part, their
 * documents and their contact. Every value comes from the server, which reads it from its source of truth; anything the
 * server has no authoritative data for is shown as not yet available, never filled in here.
 */
export class VsPortalProjectPage extends LitElement {
  static override properties = { location: { attribute: false }, load: { state: true }, view: { state: true }, reporting: { state: true },
    sending: { state: true }, formError: { state: true }, announcement: { state: true }, enlarged: { state: true } };
  declare location: { params: Record<string, string> } | undefined;
  declare load: Load;
  declare view: PropertyView | null;
  /** The project whose report form is open (one at a time). */
  declare reporting: string | null;
  declare sending: boolean;
  declare formError: string;
  declare announcement: string;
  /** The shared document shown large (one at a time). */
  declare enlarged: string | null;
  /** One key per report being written: a retry after a lost answer is the same report, never a second one. */
  private reportKey = '';

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
    .doc.shared vs-portal-image.thumb { width: 72px; flex: none; }
    .doc.shared .grow { flex: 1 1 160px; min-width: 0; overflow-wrap: anywhere; }
    .doc.shared vs-portal-image.large { flex: 1 1 100%; max-width: 100%; }
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
    this.reporting = null;
    this.sending = false;
    this.formError = '';
    this.announcement = '';
    this.enlarged = null;
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

          <section class="section" id="delivery" aria-labelledby="h-delivery">
            <h2 id="h-delivery" tabindex="-1">Work on your home</h2>
            ${this.delivery(v)}
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
              : html`<p class="muted">No documents yet. Your quotation, and anything Veda Spaces shares about your project, will be listed here.</p>`}</div>
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
    if (d.kind === 'PROJECT_DOCUMENT') {
      const e = d as ProjectDocument;
      return html`<li class="doc shared"><vs-portal-image class="thumb" .propertyId=${this.view?.id ?? ''} .documentId=${e.id} .label=${e.title} .variant=${'thumb'}></vs-portal-image>
        <span class="grow"><span class="strong">${e.title}</span><br /><span class="small muted">${e.label} · shared ${when(e.published_on)}</span></span>
        <button class="btn" aria-expanded=${this.enlarged === e.id ? 'true' : 'false'} @click=${() => { this.enlarged = this.enlarged === e.id ? null : e.id; }}>${this.enlarged === e.id ? 'Hide' : 'View'}<span class="sr-only"> ${e.title}</span></button>
        ${this.enlarged === e.id ? html`<vs-portal-image class="large" .propertyId=${this.view?.id ?? ''} .documentId=${e.id} .label=${e.title} .variant=${'desktop'}></vs-portal-image>` : nothing}</li>`;
    }
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

  /** Project delivery, as the server states it: what is done, under way, on hold or next, and the handover. No
   * percentage is shown: progress is the state of each piece of work Veda Spaces shares with you. */
  private delivery(v: PropertyView) {
    if (!v.delivery?.projects.length) {
      return html`<p class="card muted">Progress on site appears here once your project is under way.</p>`;
    }
    return v.delivery.projects.map((d) => this.deliveryProject(v, d));
  }

  private deliveryProject(v: PropertyView, d: DeliveryProject) {
    const order = ['ACTION_REQUIRED', 'BLOCKED', 'IN_PROGRESS', 'UPCOMING', 'COMPLETED'] as const;
    const words: Record<string, string> = { ACTION_REQUIRED: 'Needs you', BLOCKED: 'On hold', IN_PROGRESS: 'In progress', UPCOMING: 'Coming up', COMPLETED: 'Completed' };
    const pkg = d.package;
    return html`<div class="stack">
      <article class="card stack" aria-labelledby=${`phase-${d.id}`}>
        <div class="step-head"><h3 id=${`phase-${d.id}`}>Now: ${d.phase.label}</h3>${stateBadge(d.status === 'HANDED_OVER' ? 'COMPLETED' : 'IN_PROGRESS', d.status === 'HANDED_OVER' ? 'Handed over' : 'Under way')}</div>
        ${d.next_date ? html`<p><span class="strong">Next date agreed with you:</span> ${d.next_date.label}, ${when(d.next_date.date)}</p>`
          : html`<p class="small muted">No date has been agreed with you for the next step yet. Your Veda Spaces contact will confirm it.</p>`}
        ${d.paused.map((x) => html`<p class="notice">${stateBadge(x.state)} ${x.text}${x.who === 'VEDA_SPACES' ? html` <span class="small muted">(Veda Spaces is working on this)</span>` : nothing}</p>`)}
      </article>
      ${d.work.items.length ? html`<article class="card stack" aria-labelledby=${`work-${d.id}`}><h3 id=${`work-${d.id}`}>The work</h3>
        <p class="small muted">${order.filter((k) => d.work.counts[k]).map((k) => `${d.work.counts[k]} ${words[k].toLowerCase()}`).join(' · ')}</p>
        <ul class="plain">${order.flatMap((k) => d.work.items.filter((w) => w.state === k)).map((w) => html`<li class="item">
          <div class="step-head"><span class="strong">${w.label}</span>${stateBadge(w.state)}</div>
          <span class="small muted">${w.detail}${w.completed_on ? ` · ${when(w.completed_on)}` : ''}</span></li>`)}</ul></article>` : nothing}
      <article class="card stack" aria-labelledby=${`quality-${d.id}`}><h3 id=${`quality-${d.id}`}>Quality checks and snags</h3>
        <p>${d.quality.checks_passed} quality check${d.quality.checks_passed === 1 ? '' : 's'} passed${d.quality.being_corrected ? `, ${d.quality.being_corrected} being corrected` : ''}.</p>
        ${d.snags.length ? html`<ul class="plain">${d.snags.map((n) => html`<li class="item"><div class="step-head"><span>Snag ${n.number}: ${n.title}</span>${stateBadge(n.state, n.status)}</div></li>`)}</ul>`
          : html`<p class="small muted">No snags are listed for you.</p>`}
      </article>
      ${this.reports(v, d)}
      ${this.handover(v, d, pkg)}
    </div>`;
  }

  private reports(v: PropertyView, d: DeliveryProject) {
    const open = this.reporting === d.id;
    return html`<article class="card stack" aria-labelledby=${`reports-${d.id}`}>
      <div class="step-head"><h3 id=${`reports-${d.id}`}>Something not right?</h3></div>
      ${d.reports.length ? html`<ul class="plain">${d.reports.map((r) => html`<li class="item">
        <div class="step-head"><span class="strong">Report ${r.number}${r.area ? `: ${r.area}` : ''}</span>${stateBadge(r.status === 'Reviewed' ? 'INFORMATION' : r.status.startsWith('Accepted') ? 'IN_PROGRESS' : 'UPCOMING', r.status)}</div>
        <span>${r.description}</span>
        ${r.outcome ? html`<span class="small"><span class="strong">${r.outcome}.</span> ${r.response ?? ''}</span>` : r.response ? html`<span class="small">${r.response}</span>` : nothing}
        ${r.snag_number ? html`<span class="small muted">Followed as snag ${r.snag_number}.</span>` : nothing}</li>`)}</ul>` : nothing}
      ${!d.can_report ? html`<p class="small muted">${d.status === 'HANDED_OVER' ? 'Your home has been handed over. For anything you notice now, please contact Veda Spaces.'
        : 'To report something you have noticed, please speak to your Veda Spaces contact.'}</p>`
        : open ? html`<form class="stack" novalidate @submit=${(e: Event) => this.sendReport(e, v, d)}>
            ${this.formError ? html`<p class="notice" role="alert" id="report-error">${this.formError}</p>` : nothing}
            <label class="field"><span class="label">What have you noticed? (required)</span>
              <textarea name="description" minlength="10" maxlength="2000" required aria-describedby="report-hint ${this.formError ? 'report-error' : ''}"></textarea>
              <span class="hint small muted" id="report-hint">Describe it in your own words. Veda Spaces reviews every report and replies here.</span></label>
            <label class="field"><span class="label">Where is it? (optional)</span><input name="area" maxlength="120" autocomplete="off" /></label>
            <div class="row"><button class="btn primary" type="submit" ?disabled=${this.sending}>${this.sending ? 'Sending…' : 'Send report'}</button>
              <button class="btn ghost" type="button" @click=${() => { this.reporting = null; this.formError = ''; }}>Cancel</button></div>
          </form>`
          : html`<div><button class="btn" @click=${() => this.startReport(d)}>Report something</button></div>`}
    </article>`;
  }

  private async startReport(d: DeliveryProject) {
    this.reporting = d.id;
    this.formError = '';
    this.reportKey = newIdempotencyKey();
    await this.updateComplete;
    this.renderRoot.querySelector<HTMLTextAreaElement>('textarea[name=description]')?.focus();
  }

  private async sendReport(e: Event, v: PropertyView, d: DeliveryProject) {
    e.preventDefault();
    if (this.sending) return;
    const form = e.target as HTMLFormElement;
    const description = (form.elements.namedItem('description') as HTMLTextAreaElement).value.trim();
    const area = (form.elements.namedItem('area') as HTMLInputElement).value.trim();
    if (description.length < 10) {
      this.formError = 'Please describe what you have noticed (at least 10 characters).';
      await this.updateComplete;
      this.renderRoot.querySelector<HTMLTextAreaElement>('textarea[name=description]')?.focus();
      return;
    }
    this.sending = true;
    try {
      const r = (await portalApi.report(v.id, d.id, { description, ...(area ? { area } : {}) }, this.reportKey)).data;
      this.replace(d.id, r.delivery);
      this.reporting = null;
      this.formError = '';
      this.announcement = `Thank you. ${r.reference} has been received; Veda Spaces will review it.`;
    } catch (err) {
      const p = err as { status: number; code?: string; detail?: string };
      this.formError = transient(p) ? 'We could not send your report. Check your connection and try again; it will not be sent twice.'
        : p.detail ?? 'Your report could not be sent. Please speak to your Veda Spaces contact.';
    } finally { this.sending = false; }
  }

  private handover(v: PropertyView, d: DeliveryProject, pkg: DeliveryProject['package']) {
    const h = d.handover;
    return html`<article class="card stack" aria-labelledby=${`handover-${d.id}`}>
      <div class="step-head"><h3 id=${`handover-${d.id}`}>Handover</h3>${stateBadge(h.state, h.label)}</div>
      ${h.date ? html`<p>Handed over ${when(h.date)}.</p>` : nothing}
      ${h.remaining.length ? html`<p>Before your handover:</p><ul class="bullets">${h.remaining.map((x) => html`<li>${x.label} (${x.count})</li>`)}</ul>` : nothing}
      ${pkg ? html`<div class="stack">
        <h4>Your handover summary</h4>
        ${pkg.status === 'BEING_UPDATED' ? html`<p class="notice" role="status">Veda Spaces is updating your handover summary.</p>` : nothing}
        ${pkg.work_completed.length ? html`<p><span class="strong">Work completed:</span> ${pkg.work_completed.map((w) => w.label).join(', ')}</p>` : nothing}
        <p>${pkg.quality.checks_passed} quality checks passed${pkg.quality.corrected_after_failure ? `, ${pkg.quality.corrected_after_failure} after a correction` : ''}; ${pkg.snags.fixed_and_verified} snags fixed and checked.</p>
        ${pkg.snags.open_minor.length ? html`<p>Still to finish (does not hold the handover): ${pkg.snags.open_minor.map((n) => `snag ${n.number}, ${n.title}`).join('; ')}.</p>` : nothing}
        ${pkg.documents.length ? html`<p><span class="strong">Handover documents:</span> ${pkg.documents.map((x) => x.title).join(', ')} (see Documents).</p>`
          : pkg.documents_note ? html`<p class="small muted">${pkg.documents_note}</p>` : nothing}
        <p class="small muted">${pkg.warranty_note}</p>
        ${pkg.acknowledged_on ? html`<p>${stateBadge('COMPLETED', 'Received')} You confirmed receiving this summary on ${when(pkg.acknowledged_on)}.</p>`
          : pkg.can_acknowledge ? html`<div><button class="btn primary" ?disabled=${this.sending} @click=${() => this.acknowledge(v, d, pkg)}>I have received this summary</button></div>`
            : nothing}
      </div>` : nothing}
    </article>`;
  }

  private async acknowledge(v: PropertyView, d: DeliveryProject, pkg: NonNullable<DeliveryProject['package']>) {
    if (this.sending) return;
    this.sending = true;
    try {
      const r = (await portalApi.acknowledge(v.id, d.id, pkg.id, pkg.content_sha256)).data;
      this.replace(d.id, r.delivery);
      this.view = { ...this.view!, attention: this.view!.attention.filter((a) => a.kind !== 'HANDOVER_ACKNOWLEDGEMENT') };
      this.announcement = 'Thank you. Your confirmation has been recorded.';
    } catch (err) {
      const p = err as { status: number; detail?: string };
      this.announcement = transient(p) ? 'We could not record your confirmation. Please try again.' : p.detail ?? 'Your confirmation could not be recorded.';
      if (!transient(p)) void this.fetch();
    } finally { this.sending = false; }
  }

  private replace(id: string, next: DeliveryProject) {
    const v = this.view;
    if (!v?.delivery) return;
    this.view = { ...v, delivery: { ...v.delivery, projects: v.delivery.projects.map((x) => (x.id === id ? next : x)) } };
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
    return html`<vs-portal-header ?signed-in=${this.load !== 'signed-out'}></vs-portal-header><main class="wrap" id="main">${this.content()}</main>
      <div class="sr-only" role="status" aria-live="polite">${this.announcement}</div>`;
  }
}
customElements.define('vs-portal-project-page', VsPortalProjectPage);
