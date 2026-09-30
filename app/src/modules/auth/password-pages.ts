import { LitElement, css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import { session } from '../../core/auth/session.js';
import { maskEmail } from '../../core/format/format.js';
import { fragmentParam, navigate } from '../../core/router/next.js';
import { shared } from '../../design-system/styles.js';
import { setInviteContext } from './enroll-state.js';
import { POLICY_MESSAGES } from './password.js';
import type { VsNewPassword } from './widgets.js';

const formStyles = css`form { display: flex; flex-direction: column; gap: 16px; }`;

function policyError(p: ApiProblem): string {
  if (p.code === 'PASSWORD_POLICY') return p.errors.map((e) => POLICY_MESSAGES[e.code] ?? e.message ?? e.code).join(' ') || 'Choose a stronger password.';
  if (p.code === 'PASSWORD_REUSED') return POLICY_MESSAGES.PASSWORD_REUSED;
  return p.detail || 'Something went wrong. Please try again.';
}

/** Forgot password (09 §4.2). Always 202; enumeration-safe message. */
export class VsForgotPasswordPage extends LitElement {
  static override properties = { sentTo: { state: true }, busy: { state: true }, error: { state: true }, canResend: { state: true } };
  declare sentTo: string;
  declare busy: boolean;
  declare error: string;
  declare canResend: boolean;
  static override styles = [...shared, formStyles];
  constructor() {
    super();
    this.sentTo = '';
    this.busy = false;
    this.error = '';
    this.canResend = false;
  }
  private async send(email: string) {
    this.busy = true;
    this.error = '';
    try {
      await api.post('/api/v1/auth/password/forgot', { email }, { anonymous: true });
      this.sentTo = email;
      this.canResend = false;
      setTimeout(() => (this.canResend = true), 60_000);
    } catch (err) {
      const p = err as ApiProblem;
      this.error = p.code === 'RATE_LIMITED' ? 'Too many requests. Please wait a few minutes.' : p.fieldError('email') ? 'Enter a valid email address.' : 'Could not send the link. Try again.';
    } finally {
      this.busy = false;
    }
  }
  override render() {
    return html`<vs-auth-layout>
      ${this.sentTo
        ? html`<h1 class="display">Check your email</h1>
            <p>If an account exists for <strong>${maskEmail(this.sentTo)}</strong>, a link is on its way. It expires in 30 minutes.</p>
            <p class="muted">Didn't get it? Check spam, or resend.</p>
            <button class="btn" ?disabled=${!this.canResend || this.busy} @click=${() => this.send(this.sentTo)}>Resend</button>
            <a href="/login">← Back to sign in</a>`
        : html`<h1 class="display">Forgot password</h1>
            <p class="muted">Enter your work email and we'll send a reset link.</p>
            <form novalidate @submit=${(e: Event) => {
              e.preventDefault();
              const email = ((e.target as HTMLFormElement).elements.namedItem('email') as HTMLInputElement).value.trim();
              if (!email) this.error = 'Enter your email.';
              else void this.send(email);
            }}>
              <label class="field"><span class="label">Email</span><input name="email" type="email" autocomplete="email" aria-required="true" /></label>
              <p class="danger-text" role="alert">${this.error || nothing}</p>
              <button class="btn primary block" ?disabled=${this.busy}>Send reset link →</button>
              <a href="/login">← Back to sign in</a>
            </form>`}
    </vs-auth-layout>`;
  }
}
customElements.define('vs-forgot-password-page', VsForgotPasswordPage);

abstract class NewPasswordForm extends LitElement {
  static override properties = { error: { state: true }, busy: { state: true }, invalidToken: { state: true } };
  declare error: string;
  declare busy: boolean;
  declare invalidToken: boolean;
  protected token: string | null = null;
  static override styles = [...shared, formStyles];
  constructor() {
    super();
    this.error = '';
    this.busy = false;
    this.invalidToken = false;
  }
  override connectedCallback() {
    super.connectedCallback();
    this.token = fragmentParam('token') ?? new URLSearchParams(window.location.search).get('token');
    if (!this.token) this.invalidToken = true;
    // Remove the secret from the address bar and history (it is single-use anyway).
    if (window.location.hash) history.replaceState(null, '', window.location.pathname);
  }
  protected readPassword(form: HTMLFormElement): string | null {
    const np = form.querySelector('vs-new-password') as VsNewPassword;
    const confirm = (form.elements.namedItem('confirm') as HTMLInputElement).value;
    if (!np.valid) {
      this.error = 'Choose a password that meets every rule.';
      np.focus();
      return null;
    }
    if (np.value !== confirm) {
      this.error = "The passwords don't match.";
      return null;
    }
    return np.value;
  }
}

export class VsResetPasswordPage extends NewPasswordForm {
  private async submit(e: Event) {
    e.preventDefault();
    const pw = this.readPassword(e.target as HTMLFormElement);
    if (!pw) return;
    this.busy = true;
    try {
      await api.post('/api/v1/auth/password/reset', { token: this.token, new_password: pw }, { anonymous: true });
      session.clearLocal();
      navigate('/login?reset=1');
    } catch (err) {
      const p = err as ApiProblem;
      if (p.code === 'RESET_TOKEN_INVALID') this.invalidToken = true;
      else this.error = policyError(p);
    } finally {
      this.busy = false;
    }
  }
  override render() {
    return html`<vs-auth-layout>
      <h1 class="display">Set a new password</h1>
      ${this.invalidToken
        ? html`<p>This link has expired or was already used.</p><a class="btn primary" href="/forgot-password">Request a new link</a>`
        : html`<form novalidate @submit=${this.submit}>
            <vs-new-password></vs-new-password>
            <label class="field"><span class="label">Confirm</span><input name="confirm" type="password" autocomplete="new-password" aria-required="true" /></label>
            <p class="danger-text" role="alert" aria-live="assertive">${this.error || nothing}</p>
            <button class="btn primary block" ?disabled=${this.busy}>Update password →</button>
          </form>`}
    </vs-auth-layout>`;
  }
}
customElements.define('vs-reset-password-page', VsResetPasswordPage);

/**
 * Accept invite (05 §8.4). When the MFA policy requires it, enrollment happens inside the same flow
 * (path B): the server answers {status:'MFA_ENROLLMENT_REQUIRED', invite_context}.
 */
export class VsAcceptInvitePage extends NewPasswordForm {
  private async submit(e: Event) {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const pw = this.readPassword(form);
    if (!pw) return;
    const fullName = (form.elements.namedItem('full_name') as HTMLInputElement).value.trim();
    this.busy = true;
    try {
      const r = await api.post<{ status?: string; invite_context?: string; access_token?: string } | undefined>(
        '/api/v1/auth/invite/accept',
        { token: this.token, new_password: pw, ...(fullName ? { full_name: fullName } : {}) },
        { anonymous: true },
      );
      if (r.data?.status === 'MFA_ENROLLMENT_REQUIRED' && r.data.invite_context) {
        setInviteContext(r.data.invite_context);
        navigate('/mfa/enroll?mode=invite');
      } else if (r.data?.access_token) {
        await session.completeAuthentication({ access_token: r.data.access_token });
        navigate('/');
      } else {
        navigate('/login?invited=1');
      }
    } catch (err) {
      const p = err as ApiProblem;
      if (p.code === 'INVITE_TOKEN_INVALID') this.invalidToken = true;
      else this.error = policyError(p);
    } finally {
      this.busy = false;
    }
  }
  override render() {
    return html`<vs-auth-layout eyebrow="Welcome" tagline="Welcome to Veda Spaces.">
      <h1 class="display">Welcome to Veda Spaces</h1>
      ${this.invalidToken
        ? html`<p>This invitation has expired or was already used. Ask your administrator to resend it.</p>`
        : html`<form novalidate @submit=${this.submit}>
            <label class="field"><span class="label">Your name (optional)</span><input name="full_name" autocomplete="name" maxlength="150" /></label>
            <vs-new-password></vs-new-password>
            <label class="field"><span class="label">Confirm</span><input name="confirm" type="password" autocomplete="new-password" aria-required="true" /></label>
            <p class="danger-text" role="alert" aria-live="assertive">${this.error || nothing}</p>
            <button class="btn primary block" ?disabled=${this.busy}>Set password →</button>
          </form>`}
    </vs-auth-layout>`;
  }
}
customElements.define('vs-accept-invite-page', VsAcceptInvitePage);

/** Change password (AUTH-012). Also the forced-change screen when must_change_password is set. */
export class VsChangePasswordPage extends LitElement {
  static override properties = { error: { state: true }, busy: { state: true } };
  declare error: string;
  declare busy: boolean;
  static override styles = [...shared, formStyles];
  constructor() {
    super();
    this.error = '';
    this.busy = false;
  }
  private async submit(e: Event) {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const current = (form.elements.namedItem('current_password') as HTMLInputElement).value;
    const np = form.querySelector('vs-new-password') as VsNewPassword;
    const confirm = (form.elements.namedItem('confirm') as HTMLInputElement).value;
    if (!current) return void (this.error = 'Enter your current password.');
    if (!np.valid) return void (this.error = 'Choose a password that meets every rule.');
    if (np.value !== confirm) return void (this.error = "The passwords don't match.");
    this.busy = true;
    try {
      await api.post('/api/v1/auth/password/change', { current_password: current, new_password: np.value });
      session.mustChangePassword = false;
      await session.reloadMe();
      navigate('/');
    } catch (err) {
      const p = err as ApiProblem;
      this.error = p.code === 'INVALID_CREDENTIALS' ? 'Your current password is incorrect.' :
        p.code === 'COOLING_OFF' ? 'Password changes are locked during the post-recovery cooling-off. Use "Forgot password" if you need to reset it.' : policyError(p);
    } finally {
      this.busy = false;
    }
  }
  override render() {
    const me = session.me;
    return html`<vs-auth-layout eyebrow="Security" tagline="A fresh key for your workspace.">
      <h1 class="display">Change password</h1>
      ${session.mustChangePassword ? html`<vs-banner kind="warning">You need to set a new password before continuing.</vs-banner>` : nothing}
      <form novalidate @submit=${this.submit}>
        <label class="field"><span class="label">Current password</span><input name="current_password" type="password" autocomplete="current-password" aria-required="true" /></label>
        <vs-new-password .personal=${[me?.full_name ?? '', me?.email ?? '']}></vs-new-password>
        <label class="field"><span class="label">Confirm</span><input name="confirm" type="password" autocomplete="new-password" aria-required="true" /></label>
        <p class="danger-text" role="alert" aria-live="assertive">${this.error || nothing}</p>
        <button class="btn primary block" ?disabled=${this.busy}>Update password →</button>
        ${session.mustChangePassword ? html`<button type="button" class="btn ghost" @click=${async () => { await session.logout(); navigate('/login'); }}>Sign out</button>` : html`<a href="/profile">Cancel</a>`}
      </form>
    </vs-auth-layout>`;
  }
}
customElements.define('vs-change-password-page', VsChangePasswordPage);
