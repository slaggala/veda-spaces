import { css, html, nothing } from 'lit';
import type { Information, Page } from '../proposal/api.js';
import { VsProposalView } from '../proposal/proposal-view.js';

/** A page model carrying only the customer information block: no rooms, prices, terms, link or capabilities. */
export function previewPage(info: Information, version: string): Page {
  return {
    state: 'OPEN',
    link: { expires_on: '', status: 'PREVIEW' },
    history: [],
    capabilities: { interaction: false, acceptance: false },
    notices: [],
    actions: [],
    proposal: {
      schema: 'veda.customer-proposal/1', kind: 'QUOTATION', title: 'Customer Promise preview',
      brand: { name: 'Veda Spaces', tagline: 'Interiors, measured and made' }, reference: version, quotation_number: '', version_no: 0,
      variation_no: 0, issued_on: '', valid_until: null, subject: 'Customer Promise preview', cover_note: null,
      property: { reference: '', configuration: '', city: null }, snapshot_sha256: null, rooms: [], optional_items: [],
      summary: { base_total: null, total: null, currency: 'INR' }, payment_schedule: [], warranty: [], service_support: [],
      assumptions: [], exclusions: [], terms: [], terms_version: null, unit_rates_shown: false, sections: {}, information: info,
    },
  };
}

/**
 * <vs-promise-preview>: the customer-information panels of the real customer proposal page (CQX), fed a Customer
 * Promise version. No quotation, link, acceptance or customer action exists here: the view is always in preview mode.
 */
export class VsPromisePreview extends VsProposalView {
  static override styles = [...VsProposalView.styles, css`.wrap { padding-bottom: var(--vs-space-4); }`];

  constructor() {
    super();
    this.preview = true;
  }

  override render() {
    const page = this.page;
    if (!page) return nothing;
    const info = page.proposal.information;
    return html`<div class="wrap">
      ${this.contactPanel(page)}
      ${this.scopePanel(page)}
      ${this.beforeStartPanel(page)}
      ${this.warrantyPanel(page)}
      ${this.nextPanel(page)}
      <section class="card stack" aria-labelledby="payh" id="payment-safety"><h2 tabindex="-1" id="payh">Paying Veda Spaces safely</h2>
        ${info?.payment_safety ? html`<p class="small">${info.payment_safety}</p>` : html`<p class="tbc">How to pay will be confirmed by Veda Spaces.</p>`}
      </section>
    </div>`;
  }
}
if (!customElements.get('vs-promise-preview')) customElements.define('vs-promise-preview', VsPromisePreview);
