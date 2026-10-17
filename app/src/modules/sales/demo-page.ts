import { css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatDate } from '../../core/format/format.js';
import '../../design-system/components.js';
import { pageStyles, shared } from '../../design-system/styles.js';
import { VsPortalProjectPage } from '../portal/portal-project-page.js';
import '../portal/portal-service.js';
import { STATE_LABELS, type StepState } from '../portal/api.js';
import '../proposal/proposal-view.js';
import { salesApi, type Demo } from './api.js';

type Load = 'loading' | 'ready' | 'off' | 'forbidden' | 'failed';
const TABS = [{ id: 'proposal', label: "Customer's proposal" }, { id: 'portal', label: "Customer's project portal" }];

/**
 * The customer's project portal rendered from a model it is given (the sales demo): the real portal page, minus its
 * header, sign-out, back link and every request. Nothing here reads a session or calls the portal API; the model is
 * synthetic and arrives already shaped, so there is no fetch to replace, only to skip.
 */
export class VsSalesDemoPortal extends VsPortalProjectPage {
  static override styles = [...VsPortalProjectPage.styles, css`
    :host { min-height: 0; }
    .wrap { padding: 0; }
    a.back { display: none; }
  `];

  constructor() {
    super();
    this.load = 'ready';
  }

  protected override start() { /* a provided view: nothing to load */ }

  override render() {
    return html`<div class="wrap">${this.view ? this.content() : nothing}</div>`;
  }
}
customElements.define('vs-sales-demo-portal', VsSalesDemoPortal);

/**
 * /sales/demo — the customer-journey demo (SCA-009): a synthetic customer's proposal and project portal, rendered by the
 * real customer views from a model the server builds from constants. No customer exists behind it, nothing here calls
 * a customer-facing API, and the page says so at the top and the bottom.
 */
export class VsSalesDemoPage extends SessionElement {
  static override properties = { demo: { state: true }, load: { state: true }, problem: { state: true }, tab: { state: true } };
  declare demo: Demo | null;
  declare load: Load;
  declare problem: ApiProblem | null;
  declare tab: string;
  private focused = false;

  static override styles = [...shared, pageStyles, css`
    ol.journey { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--vs-space-2); grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); }
    ol.journey li { display: flex; flex-direction: column; gap: 2px; padding: var(--vs-space-3); border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); background: var(--vs-surface); min-width: 0; }
    ol.journey .state { font-size: 12px; line-height: 18px; font-weight: 600; color: var(--vs-ink-muted); }
    ol.journey li[aria-current='step'] { border-color: var(--vs-copper); }
    ol.journey li[aria-current='step'] .state { color: var(--vs-copper-text); }
    ol.journey .detail { font-size: 13px; line-height: 20px; overflow-wrap: anywhere; }
    .frame { border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); padding: var(--vs-space-4); background: var(--vs-paper); min-width: 0; overflow: hidden; }
    .note { font-size: 13px; line-height: 20px; color: var(--vs-ink-muted); max-width: 72ch; }
  `];

  constructor() {
    super();
    this.demo = null;
    this.load = 'loading';
    this.problem = null;
    this.tab = 'proposal';
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.fetch();
  }

  private async fetch() {
    this.load = 'loading';
    this.problem = null;
    try {
      this.demo = (await salesApi.demo()).data;
      this.load = 'ready';
      if (!this.focused) {
        this.focused = true;
        await this.updateComplete;
        this.renderRoot.querySelector<HTMLElement>('#page-title')?.focus();
      }
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404) this.load = 'off';
      else if (p.status === 403) this.load = 'forbidden';
      else { this.problem = p; this.load = 'failed'; }
    }
  }

  private banner(d: Demo | null) {
    return html`<vs-banner kind="warning">${d?.label ?? 'DEMO: synthetic example, not a customer'}</vs-banner>`;
  }

  private renderDemo(d: Demo) {
    return html`
      <p class="note">What a customer sees after choosing Veda Spaces, with invented content: the real proposal and portal views rendering a synthetic model
        (as of ${formatDate(d.as_of)}). No customer, record or link exists behind it, and no action is possible here.</p>
      <section aria-labelledby="h-journey"><h2 id="h-journey" class="eyebrow">The journey</h2>
        <ol class="journey">${d.journey.map((s) => html`<li aria-current=${s.state === 'IN_PROGRESS' ? 'step' : nothing}>
          <span class="strong">${s.label}</span>
          <span class="state">${STATE_LABELS[s.state as StepState] ?? s.state}${s.date ? ` · ${formatDate(s.date)}` : ''}</span>
          <span class="detail">${s.detail}</span></li>`)}</ol></section>
      <vs-tabs label="Customer views" .tabs=${TABS} .selected=${this.tab} @tab-change=${(e: CustomEvent<string>) => { this.tab = e.detail; }}>
        ${this.tab === 'proposal'
          ? html`<section aria-labelledby="h-proposal"><h2 id="h-proposal" class="eyebrow">Customer's proposal</h2>
              <div class="frame"><vs-proposal-view preview .page=${d.proposal}></vs-proposal-view></div></section>`
          : html`<section aria-labelledby="h-portal"><h2 id="h-portal" class="eyebrow">Customer's project portal</h2>
              <div class="frame"><vs-sales-demo-portal .view=${d.portal}></vs-sales-demo-portal></div></section>`}
      </vs-tabs>`;
  }

  private renderBody() {
    switch (this.load) {
      case 'off': return html`<vs-banner kind="info">The customer journey demo is not switched on here.</vs-banner>`;
      case 'forbidden': return html`<p role="status">You do not have access to the customer journey demo.</p>`;
      case 'failed': return html`<vs-problem-banner .problem=${this.problem} heading="The demo could not be loaded"></vs-problem-banner>
        <div><button class="btn" @click=${() => void this.fetch()}>Retry</button></div>`;
      case 'loading': return html`<vs-skeleton rows="8"></vs-skeleton>`;
      default: return this.demo ? this.renderDemo(this.demo) : nothing;
    }
  }

  override render() {
    return html`<div class="page">
      ${this.banner(this.demo)}
      <div class="page-head"><div><p class="eyebrow">Sales</p><h1 class="title" id="page-title" tabindex="-1">Customer journey demo</h1></div></div>
      ${this.renderBody()}
      ${this.banner(this.demo)}
    </div>`;
  }
}
customElements.define('vs-sales-demo-page', VsSalesDemoPage);
