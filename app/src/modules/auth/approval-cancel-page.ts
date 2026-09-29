import { LitElement, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import { fragmentParam } from '../../core/router/next.js';
import { shared } from '../../design-system/styles.js';

/**
 * Cancel a pending break-glass request from the signed link in the notification email (06 §7.5 step 5, TD-G G12;
 * DEV-005, AM-5, IR-07). The token is taken from the URL fragment and the fragment is scrubbed at once. Nothing
 * happens on load: mail scanners open links, so cancelling needs an explicit confirmation.
 */
export class VsApprovalCancelPage extends LitElement {
  static override properties = { state: { state: true }, message: { state: true } };
  declare state: 'confirm' | 'working' | 'done' | 'error';
  declare message: string;
  static override styles = shared;
  private token: string | null = null;

  constructor() {
    super();
    this.state = 'confirm';
    this.message = '';
  }

  override connectedCallback() {
    super.connectedCallback();
    this.token = fragmentParam('token');
    if (window.location.hash) history.replaceState(null, '', window.location.pathname);
    if (!this.token) {
      this.state = 'error';
      this.message = 'This link is invalid.';
    }
  }

  private async cancel() {
    this.state = 'working';
    try {
      await api.post('/api/v1/approvals/cancel-link', { token: this.token }, { anonymous: true });
      this.token = null;
      this.state = 'done';
    } catch (err) {
      const p = err as ApiProblem;
      this.state = 'error';
      this.message = p.code === 'EMAIL_TOKEN_INVALID'
        ? 'This link has expired or was already used, or the request is no longer pending.' : p.detail || 'Something went wrong.';
    }
  }

  override render() {
    const heading = { confirm: 'Cancel this break-glass request?', working: 'Cancelling…', done: 'Request cancelled', error: 'Link not valid' }[this.state];
    return html`<vs-auth-layout eyebrow="Founder governance" tagline="Break-glass requests can be stopped by any notified Founder.">
      <h1 class="display" tabindex="-1">${heading}</h1>
      ${this.state === 'confirm'
        ? html`<p>A break-glass custodian asked to change Founder access. If you did not expect this, cancel it now; the
              change will not happen. Anyone you trust to decide should be told.</p>
            <button class="btn primary" @click=${() => this.cancel()}>Cancel the request</button>`
        : nothing}
      ${this.state === 'working' ? html`<vs-skeleton rows="2"></vs-skeleton>` : nothing}
      ${this.state === 'done' ? html`<p role="status">The request was cancelled and the other notified people can no longer use their links.</p><a href="/login">Go to sign in</a>` : nothing}
      ${this.state === 'error' ? html`<p role="alert">${this.message}</p><a href="/login">Go to sign in</a>` : nothing}
    </vs-auth-layout>`;
  }
}
customElements.define('vs-approval-cancel-page', VsApprovalCancelPage);
