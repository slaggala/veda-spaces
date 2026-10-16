import { LitElement, css, html } from 'lit';
import type { Page } from '../proposal/api.js';
import '../proposal/proposal-view.js';
import { forgetSession, portalApi, sessionToken, transient, type QuotationPage } from './api.js';
import { portalStyles, stateBadge } from './portal-ui.js';

type Load = 'loading' | 'ready' | 'signed-out' | 'not-found' | 'offline' | 'unavailable';

/**
 * /portal/quotations/:id — one issued version of the customer's quotation, shown with the same customer-safe view as
 * the secure proposal link (CQX), read-only. Deciding stays on the secure link, whose evidence binds the decision.
 */
export class VsPortalQuotationPage extends LitElement {
  static override properties = { location: { attribute: false }, load: { state: true }, page: { state: true } };
  declare location: { params: Record<string, string> } | undefined;
  declare load: Load;
  declare page: QuotationPage | null;

  static override styles = [...portalStyles, css`
    .head { display: flex; flex-direction: column; gap: var(--vs-space-2); }
  `];

  constructor() {
    super();
    this.load = 'loading';
    this.page = null;
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
      this.page = (await portalApi.quotation(this.routeId)).data;
      this.load = 'ready';
    } catch (e) {
      const p = e as { status: number; code?: string };
      if (p.status === 401) {
        forgetSession();
        this.load = 'signed-out';
      } else if (p.status === 404 || p.status === 422) {
        this.load = 'not-found';
      } else {
        this.load = transient(p) ? 'offline' : 'unavailable';
      }
    }
  }

  private content() {
    switch (this.load) {
      case 'loading':
        return html`<div class="card" role="status" aria-live="polite"><vs-skeleton rows="10"></vs-skeleton><span class="sr-only">Loading your quotation…</span></div>`;
      case 'signed-out':
        return html`<vs-portal-sign-in notice="Please sign in to see your quotation."></vs-portal-sign-in>`;
      case 'not-found':
        return html`<div class="card" role="alert"><h1>We could not find this quotation</h1><p>It may not have been issued to you.</p>
          <a class="btn primary" href="/portal">Go to your portal</a></div>`;
      case 'offline':
        return html`<div class="card" role="alert"><h1>We could not load your quotation</h1><p>Check your connection and try again.</p>
          <button class="btn primary" @click=${() => void this.fetch()}>Try again</button></div>`;
      case 'unavailable':
        return html`<div class="card" role="alert"><h1>This quotation cannot be shown right now</h1>
          <p>Please contact your Veda Spaces representative.</p><a class="btn" href="/portal">Go to your portal</a></div>`;
      default:
        break;
    }
    const page = this.page!;
    const s = page.summary;
    return html`<p><a href="/portal">← Your portal</a></p>
      <div class="head"><p class="eyebrow">${s.title} ${s.reference}</p>${stateBadge(s.status, s.status_label)}</div>
      <vs-proposal-view portal .page=${{ ...page, link: { expires_on: '', status: 'PORTAL' } } as Page}></vs-proposal-view>`;
  }

  override render() {
    return html`<vs-portal-header ?signed-in=${this.load !== 'signed-out'}></vs-portal-header><main class="wrap" id="main">${this.content()}</main>`;
  }
}
customElements.define('vs-portal-quotation-page', VsPortalQuotationPage);
