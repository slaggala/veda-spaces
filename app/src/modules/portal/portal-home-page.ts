import { LitElement, css, html, nothing } from 'lit';
import { forgetSession, portalApi, sessionToken, transient, type Home, type PropertyCard } from './api.js';
import { portalStyles, stateBadge, when } from './portal-ui.js';

type Load = 'loading' | 'ready' | 'signed-out' | 'ended' | 'unavailable' | 'offline';

/**
 * /portal — the customer's portal home. Signed out: ask for a sign-in link. Signed in: each of their homes, what is
 * happening, what needs them, their quotation and who to talk to — the most useful things first.
 */
export class VsPortalHomePage extends LitElement {
  static override properties = { load: { state: true }, home: { state: true } };
  declare load: Load;
  declare home: Home | null;

  static override styles = [...portalStyles, css`
    .cards { display: grid; grid-template-columns: 1fr; gap: var(--vs-space-4); }
    @media (min-width: 768px) { .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    .home-card { display: flex; flex-direction: column; gap: var(--vs-space-3); }
    .row-between { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--vs-space-2); }
    .eyebrow { margin: 0; }
  `];

  constructor() {
    super();
    this.load = 'loading';
    this.home = null;
  }

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
      this.home = (await portalApi.home()).data;
      this.load = 'ready';
    } catch (e) {
      const p = e as { status: number; code?: string };
      if (p.status === 401) {
        forgetSession();
        this.load = 'ended';
      } else {
        this.load = p.status === 404 ? 'unavailable' : transient(p) ? 'offline' : 'unavailable';
      }
    }
  }

  private card(p: PropertyCard) {
    const title = [p.property.configuration, p.property.locality, p.property.city].filter(Boolean).join(' · ') || 'Your home';
    return html`<article class="card home-card" aria-labelledby="h-${p.id}">
      <div class="row-between">
        <p class="eyebrow">${p.property.reference}</p>
        ${p.attention_count ? stateBadge('ACTION_REQUIRED', p.attention_count === 1 ? '1 thing needs you' : `${p.attention_count} things need you`) : nothing}
      </div>
      <h2 id="h-${p.id}">${title}</h2>
      <p class="lead-text">${p.headline}</p>
      ${p.next_step ? html`<p><span class="strong">Next:</span> ${p.next_step.label}. ${p.next_step.detail}
        ${p.next_step.date ? html`<span class="muted">(${when(p.next_step.date)})</span>` : nothing}</p>` : nothing}
      ${p.quotation ? html`<dl class="facts">
        <div><dt>Your ${p.quotation.title.toLowerCase()}</dt><dd>${p.quotation.reference}</dd></div>
        <div><dt>Status</dt><dd>${stateBadge(p.quotation.status, p.quotation.status_label)}</dd></div>
        ${p.quotation.total ? html`<div><dt>Total</dt><dd>${p.quotation.total}</dd></div>` : nothing}
      </dl>` : nothing}
      ${p.contact?.name ? html`<p class="muted">Your Veda Spaces contact: ${p.contact.name}${p.contact.role ? `, ${p.contact.role}` : ''}</p>` : nothing}
      <a class="btn primary" href="/portal/properties/${p.id}">Open your project<span class="sr-only">: ${title}</span></a>
    </article>`;
  }

  private content() {
    switch (this.load) {
      case 'loading':
        return html`<div class="card" role="status" aria-live="polite"><vs-skeleton rows="6"></vs-skeleton><span class="sr-only">Loading your portal…</span></div>`;
      case 'signed-out':
        return html`<vs-portal-sign-in></vs-portal-sign-in>`;
      case 'ended':
        return html`<vs-portal-sign-in notice="You were signed out. Ask for a new sign-in link to continue."></vs-portal-sign-in>`;
      case 'unavailable':
        return html`<div class="card" role="alert"><h1>The project portal is not available here</h1><p>Please contact Veda Spaces.</p></div>`;
      case 'offline':
        return html`<div class="card" role="alert"><h1>We could not load your portal</h1><p>Check your connection and try again.</p>
          <button class="btn primary" @click=${() => void this.fetch()}>Try again</button></div>`;
      default:
        break;
    }
    const home = this.home!;
    const cards = home.enquiries.flatMap((e) => e.properties);
    const closed = home.enquiries.filter((e) => !e.properties.length);
    return html`<section class="section" aria-labelledby="welcome">
        <p class="eyebrow">Your project portal</p>
        <h1 id="welcome" tabindex="-1">Hello, ${home.customer.name}</h1>
        <p class="lead-text muted">Everything about your home with Veda Spaces, in one place.</p>
      </section>
      ${cards.length ? html`<div class="cards">${cards.map((p) => this.card(p))}</div>` : nothing}
      ${closed.map((e) => html`<div class="card"><h2>Your enquiry ${e.reference}</h2><p>${e.closed ? 'This enquiry is closed.'
        : 'We have your enquiry. Your home will appear here once Veda Spaces has recorded it.'}</p></div>`)}
      ${!home.enquiries.length ? html`<div class="card"><h2>Nothing to show yet</h2>
        <p>No enquiry is linked to your portal at the moment. Your Veda Spaces contact can help.</p></div>` : nothing}`;
  }

  override render() {
    return html`<vs-portal-header ?signed-in=${this.load === 'ready'}></vs-portal-header><main class="wrap" id="main">${this.content()}</main>`;
  }
}
customElements.define('vs-portal-home-page', VsPortalHomePage);
