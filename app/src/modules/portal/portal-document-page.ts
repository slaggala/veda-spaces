import { LitElement, css, html, nothing } from 'lit';
import { forgetSession, portalApi, sessionToken, transient, type CommercialDocument } from './api.js';
import { portalStyles, stateBadge, when } from './portal-ui.js';

type Load = 'loading' | 'ready' | 'signed-out' | 'not-found' | 'offline' | 'unavailable';

/**
 * /portal/invoices/:id and /portal/receipts/:id — one of the customer's invoices or receipts, exactly as Veda Spaces
 * issued it (the frozen document the server verified). It can be downloaded as the sealed file; the page shows the same
 * document's fields itself and never inserts the file's HTML. There is no way to pay here.
 */
export class VsPortalDocumentPage extends LitElement {
  static override properties = { location: { attribute: false }, load: { state: true }, page: { state: true } };
  declare location: { params: Record<string, string> } | undefined;
  declare load: Load;
  declare page: CommercialDocument | null;

  static override styles = [...portalStyles, css`
    .doc-head { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: var(--vs-space-3); }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: var(--vs-space-2); border-bottom: 1px solid var(--vs-line); vertical-align: top; overflow-wrap: anywhere; }
    th { font-weight: 500; color: var(--vs-ink-muted); }
    td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
    tr.total td, tr.total th { font-weight: 700; color: var(--vs-ink); border-top: 2px solid var(--vs-ink); }
    .actions { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    @media print { vs-portal-header, .actions, a.back { display: none; } }
  `];

  constructor() {
    super();
    this.load = 'loading';
    this.page = null;
  }

  private get kind(): 'invoices' | 'receipts' {
    return (this.location as { pathname?: string } | undefined)?.pathname?.includes('/receipts/') || window.location.pathname.includes('/receipts/')
      ? 'receipts' : 'invoices';
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
      this.page = (await portalApi.document(this.kind, this.routeId)).data;
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

  private download() {
    const page = this.page;
    if (!page) return;
    const url = URL.createObjectURL(new Blob([page.html], { type: 'text/html;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = page.filename;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  private rows(items: [string, string | null | undefined][], total?: [string, string]) {
    return html`<table><tbody>${items.filter(([, v]) => v).map(([k, v]) => html`<tr><th scope="row">${k}</th><td class="num">${v}</td></tr>`)}
      ${total ? html`<tr class="total"><th scope="row">${total[0]}</th><td class="num">${total[1]}</td></tr>` : nothing}</tbody></table>`;
  }

  private ready(p: CommercialDocument) {
    const d = p.document;
    const name = p.kind === 'INVOICE' ? `${d.title} ${p.number}` : `Receipt ${p.number}`;
    return html`
      <p><a class="back" href="/portal/properties/${p.property_id}#payments">← Your project</a></p>
      <article class="card stack" aria-labelledby="doc-title">
        <div class="doc-head">
          <div class="stack"><p class="eyebrow">${d.brand?.name ?? 'Veda Spaces'}</p><h1 id="doc-title" tabindex="-1">${name}</h1>
            <p class="muted">${d.date ? `Issued ${when(d.date)}` : ''}${d.due_on ? ` · Due by ${when(d.due_on)}` : ''}</p></div>
          ${stateBadge(p.status, p.status_label)}
        </div>
        ${p.notices.map((n) => html`<p class="notice" role="status">${n.message}</p>`)}
        ${d.issuer ? html`<p class="small muted">${[d.issuer.legal_name, ...(d.issuer.address_lines ?? [])].join(', ')}${d.issuer.gstin ? ` · GSTIN ${d.issuer.gstin}` : ''}</p>` : nothing}
        <p>${d.customer?.name ? html`For ${d.customer.name}<br />` : nothing}<span class="muted">Property ${d.property?.reference} · ${d.property?.configuration}${d.property?.city ? ` · ${d.property.city}` : ''}
          <br />Quotation ${d.quotation?.reference}${d.quotation?.variations?.length ? `; variations ${d.quotation.variations.join(', ')}` : ''}</span></p>
        ${p.kind === 'INVOICE' ? html`
          <h2>${d.instalment.label}</h2><p class="muted">Instalment ${d.instalment.position} of ${d.instalment.of}: ${d.instalment.when}</p>
          ${this.rows([['Instalment (₹)', d.amounts.instalment], ['Of which GST, as quoted (₹)', d.amounts.gst_included],
            ['Paid towards this instalment (₹)', d.amounts.paid_towards]], ['Amount due (₹)', d.amounts.due])}
          ${d.note ? html`<p>${d.note}</p>` : nothing}`
        : html`
          <p class="amount">₹ ${d.payment.amount}</p>
          <p>Received on ${when(d.payment.received_on)} by ${d.payment.method}${d.payment.reference ? ` (reference ${d.payment.reference})` : ''}.</p>
          ${d.payment.note ? html`<p>${d.payment.note}</p>` : nothing}
          ${d.applied_to?.length ? html`<h2>Applied to</h2>${this.rows(d.applied_to.map((a: { label: string; amount: string }) => [`${a.label} (₹)`, a.amount]))}` : nothing}`}
        <h2>Your project account</h2>
        ${this.rows([['Project value (₹)', d.position.value], ['Paid (₹)', d.position.paid]], ['Outstanding (₹)', d.position.outstanding])}
        <p class="small muted">${p.kind === 'INVOICE' ? 'As at the date of this invoice.' : 'After this payment.'}</p>
        ${d.payment_safety ? html`<p class="notice">${d.payment_safety}</p>` : nothing}
        <p class="small muted">${d.statement}</p>
        ${(d.issuer?.footer ?? []).map((l: string) => html`<p class="small muted">${l}</p>`)}
        <div class="actions"><button class="btn primary" @click=${() => this.download()}>Download<span class="sr-only"> ${name}</span></button>
          <button class="btn" @click=${() => window.print()}>Print</button></div>
      </article>`;
  }

  private content() {
    switch (this.load) {
      case 'loading':
        return html`<div class="card" role="status" aria-live="polite"><vs-skeleton rows="8"></vs-skeleton><span class="sr-only">Loading your document…</span></div>`;
      case 'signed-out':
        return html`<vs-portal-sign-in notice="Please sign in to see your document."></vs-portal-sign-in>`;
      case 'not-found':
        return html`<div class="card" role="alert"><h1 tabindex="-1">We could not find this document</h1><p>It may not be linked to your portal.</p>
          <a class="btn primary" href="/portal">Go to your portal</a></div>`;
      case 'offline':
        return html`<div class="card" role="alert"><h1>We could not load your document</h1><p>Check your connection and try again.</p>
          <button class="btn primary" @click=${() => void this.fetch()}>Try again</button></div>`;
      case 'unavailable':
        return html`<div class="card" role="alert"><h1>This document cannot be shown right now</h1><p>Please contact Veda Spaces.</p>
          <a class="btn" href="/portal">Go to your portal</a></div>`;
      default:
        return this.ready(this.page!);
    }
  }

  override render() {
    return html`<vs-portal-header ?signed-in=${this.load !== 'signed-out'}></vs-portal-header><main class="wrap" id="main">${this.content()}</main>`;
  }
}
customElements.define('vs-portal-document-page', VsPortalDocumentPage);
