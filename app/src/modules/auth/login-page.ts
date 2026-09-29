import { LitElement, css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { session } from '../../core/auth/session.js';
import { navigate, sanitizeNext } from '../../core/router/next.js';
import { shared } from '../../design-system/styles.js';
import type { VsTurnstile } from './widgets.js';

/** Login (09 §4.1, UI-001). Uniform error; routes to MFA challenge or "check your email". */
export class VsLoginPage extends LitElement {
  static override properties = { error: { state: true }, busy: { state: true }, failures: { state: true }, showPassword: { state: true }, captcha: { state: true } };
  declare error: string;
  declare busy: boolean;
  declare failures: number;
  declare showPassword: boolean;
  declare captcha: boolean;
  static override styles = [...shared, css`form { display: flex; flex-direction: column; gap: 16px; } .show { background: none; border: 0; color: var(--vs-copper-text); cursor: pointer; font: 600 12px var(--vs-font-sans); }`];

  constructor() {
    super();
    this.error = '';
    this.busy = false;
    this.failures = 0;
    this.showPassword = false;
    this.captcha = false;
  }

  private get next(): string {
    return sanitizeNext(new URLSearchParams(window.location.search).get('next'));
  }

  private banner() {
    const q = new URLSearchParams(window.location.search);
    if (session.flash) return html`<vs-banner kind=${session.flash.kind === 'warning' ? 'warning' : 'info'}>${session.flash.text}</vs-banner>`;
    if (q.get('reset')) return html`<vs-banner kind="success">Password updated. Sign in with your new password.</vs-banner>`;
    if (q.get('invited')) return html`<vs-banner kind="success">Your account is ready. Sign in to continue.</vs-banner>`;
    if (q.get('email_changed')) return html`<vs-banner kind="success">Your sign-in email was updated. Sign in with the new address.</vs-banner>`;
    return nothing;
  }

  private async submit(e: Event) {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const email = (form.elements.namedItem('email') as HTMLInputElement).value.trim();
    const password = (form.elements.namedItem('password') as HTMLInputElement).value;
    if (!email || !password) {
      this.error = 'Enter your email and password.';
      return;
    }
    this.busy = true;
    this.error = '';
    session.flash = null;
    try {
      const turnstile = this.renderRoot.querySelector('vs-turnstile') as VsTurnstile | null;
      const result = await session.login(email, password, turnstile?.token || undefined);
      if (result.status === 'MFA_REQUIRED') navigate(`/mfa?next=${encodeURIComponent(this.next)}`);
      else if (result.status === 'MFA_ENROLLMENT_EMAIL_SENT') navigate('/mfa/check-email');
      else if (result.must_change_password) navigate('/change-password');
      else navigate(this.next);
    } catch (err) {
      const p = err as ApiProblem;
      this.failures += 1;
      if (p.ext<boolean>('captcha_required')) this.captcha = true;
      this.error =
        p.code === 'RATE_LIMITED' ? 'Too many attempts. Please wait a minute and try again.' :
        p.isNetwork ? 'We could not reach the server. Check your connection.' :
        p.code === 'INVALID_CREDENTIALS' ? 'Email or password is incorrect.' : p.detail || 'Sign-in failed. Please try again.';
      (form.elements.namedItem('password') as HTMLInputElement).focus();
    } finally {
      this.busy = false;
    }
  }

  override render() {
    return html`<vs-auth-layout>
      <div><h1 class="display">Welcome back</h1><p class="muted">Sign in to continue.</p></div>
      ${this.banner()}
      <form @submit=${this.submit} novalidate>
        <label class="field"><span class="label">Email</span>
          <input name="email" type="email" autocomplete="username" required aria-required="true" placeholder="you@vedaspaces.com" /></label>
        <div class="field">
          <span class="row"><label class="label" for="pw">Password</label><span class="spacer"></span>
            <button type="button" class="show" aria-pressed=${this.showPassword ? 'true' : 'false'} @click=${() => (this.showPassword = !this.showPassword)}>${this.showPassword ? 'Hide' : 'Show'}</button></span>
          <input id="pw" name="password" type=${this.showPassword ? 'text' : 'password'} autocomplete="current-password" required aria-required="true"
            aria-invalid=${this.error ? 'true' : 'false'} aria-describedby="login-error" />
        </div>
        <div class="row"><span class="spacer"></span><a href="/forgot-password">Forgot password?</a></div>
        ${this.captcha ? html`<vs-turnstile></vs-turnstile>` : nothing}
        <button class="btn primary block" ?disabled=${this.busy}>${this.busy ? 'Signing in…' : 'Sign in →'}</button>
        <p id="login-error" class="danger-text" role="alert" aria-live="assertive">${this.error ? html`⚠ ${this.error}` : nothing}</p>
        ${this.failures >= 3 ? html`<p class="small">Trouble signing in? <a href="/forgot-password">Reset your password.</a></p>` : nothing}
      </form>
    </vs-auth-layout>`;
  }
}
customElements.define('vs-login-page', VsLoginPage);
