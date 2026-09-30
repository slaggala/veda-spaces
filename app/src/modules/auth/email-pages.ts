import { LitElement, html } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import { session } from '../../core/auth/session.js';
import { fragmentParam } from '../../core/router/next.js';
import { shared } from '../../design-system/styles.js';

abstract class TokenActionPage extends LitElement {
  static override properties = { state: { state: true }, message: { state: true } };
  declare state: 'working' | 'done' | 'error';
  declare message: string;
  static override styles = shared;
  protected abstract endpoint: string;
  constructor() {
    super();
    this.state = 'working';
    this.message = '';
  }
  override connectedCallback() {
    super.connectedCallback();
    const token = fragmentParam('token') ?? new URLSearchParams(window.location.search).get('token');
    if (window.location.hash) history.replaceState(null, '', window.location.pathname);
    if (!token) {
      this.state = 'error';
      this.message = 'This link is invalid.';
      return;
    }
    void this.run(token);
  }
  private async run(token: string) {
    try {
      await api.post(this.endpoint, { token }, { anonymous: true });
      this.state = 'done';
      this.onDone();
    } catch (err) {
      const p = err as ApiProblem;
      this.state = 'error';
      this.message = p.code === 'EMAIL_TOKEN_INVALID' ? 'This link has expired or was already used.' :
        p.code === 'DUPLICATE' ? 'That address is now used by another account. Ask an administrator for help.' : p.detail || 'Something went wrong.';
    }
  }
  protected onDone(): void {}
}

/** Verify a proposed sign-in email (05 §8.6 step 6). Completion revokes every session. */
export class VsVerifyEmailPage extends TokenActionPage {
  protected endpoint = '/api/v1/auth/email/verify';
  protected override onDone() {
    session.clearLocal();
  }
  override render() {
    return html`<vs-auth-layout eyebrow="Account" tagline="Your sign-in email.">
      <h1 class="display">${this.state === 'done' ? 'Email updated' : this.state === 'error' ? 'Link not valid' : 'Verifying…'}</h1>
      ${this.state === 'working' ? html`<vs-skeleton rows="2"></vs-skeleton>` : ''}
      ${this.state === 'done' ? html`<p>Your sign-in email was changed. For your security, every session was signed out.</p><a class="btn primary" href="/login?email_changed=1">Sign in</a>` : ''}
      ${this.state === 'error' ? html`<p role="alert">${this.message}</p><a href="/login">Go to sign in</a>` : ''}
    </vs-auth-layout>`;
  }
}
customElements.define('vs-verify-email-page', VsVerifyEmailPage);

/** Cancel a pending email change from the alert sent to the current address (05 §8.6 step 7). */
export class VsCancelEmailPage extends TokenActionPage {
  protected endpoint = '/api/v1/auth/email/cancel';
  override render() {
    return html`<vs-auth-layout eyebrow="Account" tagline="Your sign-in email.">
      <h1 class="display">${this.state === 'done' ? 'Change cancelled' : this.state === 'error' ? 'Link not valid' : 'Cancelling…'}</h1>
      ${this.state === 'done' ? html`<p>The email change was cancelled. Your sign-in email stays the same. If you didn't request it, contact the Founder and change your password.</p><a href="/login">Go to sign in</a>` : ''}
      ${this.state === 'error' ? html`<p role="alert">${this.message}</p><a href="/login">Go to sign in</a>` : ''}
    </vs-auth-layout>`;
  }
}
customElements.define('vs-cancel-email-page', VsCancelEmailPage);
