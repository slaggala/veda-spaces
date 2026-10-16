import { LitElement, css, html } from 'lit';
import { navigate } from '../../core/router/next.js';
import { keepSession, portalApi, takeLinkToken, transient } from './api.js';
import { portalStyles } from './portal-ui.js';

type State = 'signing-in' | 'refused' | 'offline' | 'request';

/**
 * /portal/sign-in — the emailed link lands here. The one-time token is read from the URL fragment and scrubbed at once,
 * exchanged for a portal session, and the customer goes to their portal home. A link that has expired or was used
 * offers a new one by email.
 */
export class VsPortalSignInPage extends LitElement {
  static override properties = { state: { state: true } };
  declare state: State;
  private token: string | null = null;

  static override styles = [...portalStyles, css`
    .box { max-width: 480px; margin: var(--vs-space-6) auto 0; display: flex; flex-direction: column; gap: var(--vs-space-4); }
  `];

  constructor() {
    super();
    this.state = 'signing-in';
  }

  override connectedCallback() {
    super.connectedCallback();
    this.token = takeLinkToken();
    if (!this.token) {
      this.state = 'request';
      return;
    }
    void this.exchange();
  }

  private async exchange() {
    this.state = 'signing-in';
    try {
      const r = await portalApi.startSession(this.token ?? '');
      keepSession(r.data.token);
      navigate('/portal');
    } catch (e) {
      this.state = transient(e as { status: number; code?: string }) ? 'offline' : 'refused';
      await this.updateComplete;
      this.renderRoot.querySelector<HTMLElement>('h1')?.focus();
    }
  }

  override render() {
    const body = {
      'signing-in': html`<div class="box card" role="status" aria-live="polite"><h1 tabindex="-1">Signing you in…</h1></div>`,
      offline: html`<div class="box card" role="alert"><h1 tabindex="-1">We could not sign you in just now</h1>
        <p>Check your connection and try again. Your link still works if it has not expired.</p>
        <button class="btn primary" @click=${() => void this.exchange()}>Try again</button></div>`,
      refused: html`<vs-portal-sign-in notice="This sign-in link has expired or was already used. Ask for a new one below."></vs-portal-sign-in>`,
      request: html`<vs-portal-sign-in></vs-portal-sign-in>`,
    }[this.state];
    return html`<vs-portal-header></vs-portal-header><main class="wrap" id="main">${body}</main>`;
  }
}
customElements.define('vs-portal-sign-in-page', VsPortalSignInPage);
