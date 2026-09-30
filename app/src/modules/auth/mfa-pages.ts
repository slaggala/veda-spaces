import { LitElement, css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { AuthenticatedResult, EnrollStart } from '../../core/api/types.js';
import { session } from '../../core/auth/session.js';
import { formatAbsolute } from '../../core/format/format.js';
import { t } from '../../core/i18n/strings.js';
import { fragmentParam, navigate, sanitizeNext } from '../../core/router/next.js';
import { shared } from '../../design-system/styles.js';
import { takeInviteContext } from './enroll-state.js';

const codeInput = (error: string) => html`<input name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]*" maxlength="6"
  required aria-required="true" aria-invalid=${error ? 'true' : 'false'} aria-describedby="code-err" />`;

const formStyles = css`form { display: flex; flex-direction: column; gap: 16px; }`;

/** Two-step verification at login (09 §4.10). Recovery codes are NOT accepted here (05 §11.4). */
export class VsMfaChallengePage extends LitElement {
  static override properties = { error: { state: true }, busy: { state: true }, expired: { state: true }, warning: { state: true } };
  declare error: string;
  declare busy: boolean;
  declare expired: boolean;
  declare warning: string;
  private timers: number[] = [];
  static override styles = [...shared, formStyles];
  constructor() {
    super();
    this.error = '';
    this.busy = false;
    this.expired = false;
    this.warning = '';
  }
  override connectedCallback() {
    super.connectedCallback();
    const pending = session.pendingMfa;
    if (!pending) {
      queueMicrotask(() => navigate('/login'));
      return;
    }
    // AX-07 (IR-37): announce the time limit before it runs out, then say plainly that it has.
    const left = pending.expiresAt - Date.now();
    this.timers.push(window.setTimeout(() => { this.warning = 'This sign-in request expires in 1 minute.'; }, Math.max(0, left - 60_000)));
    this.timers.push(window.setTimeout(() => {
      this.expired = true;
      this.warning = '';
      this.error = 'This sign-in attempt expired. Please sign in again.';
    }, Math.max(0, left)));
  }
  override disconnectedCallback() {
    super.disconnectedCallback();
    this.timers.forEach((t) => clearTimeout(t));
    this.timers = [];
  }
  private async submit(e: Event) {
    e.preventDefault();
    const input = (e.target as HTMLFormElement).elements.namedItem('code') as HTMLInputElement;
    const code = input.value.replace(/\s/g, '');
    if (!/^\d{6}$/.test(code)) {
      this.error = 'Enter the 6-digit code.';
      input.focus();
      return;
    }
    this.busy = true;
    try {
      const result = await session.verifyMfa(code);
      const next = sanitizeNext(new URLSearchParams(window.location.search).get('next'));
      navigate(result.must_change_password ? '/change-password' : next);
    } catch (err) {
      const p = err as ApiProblem;
      if (p.code === 'MFA_CHALLENGE_INVALID') {
        this.expired = true;
        this.error = 'This sign-in attempt expired. Please sign in again.';
      } else {
        const left = p.ext<number>('attempts_remaining');
        this.error = p.code === 'RATE_LIMITED' ? 'Too many attempts. Please wait and try again.' :
          `That code didn't work.${left !== undefined ? ` ${left} attempts left.` : ''}`;
      }
      input.value = '';
      input.focus();
    } finally {
      this.busy = false;
    }
  }
  override render() {
    return html`<vs-auth-layout>
      <div><h1 class="display">Two-step verification</h1><p class="muted">Enter the 6-digit code from your authenticator app.</p></div>
      <form @submit=${this.submit} novalidate>
        <label class="field"><span class="label">Code</span>${codeInput(this.error)}</label>
        <p id="code-err" class="danger-text" role="alert" aria-live="assertive">${this.error ? html`⚠ ${this.error}` : nothing}</p>
        <p class="muted" role="status" aria-live="polite">${this.warning}</p>
        ${this.expired
          ? html`<a class="btn primary block" href="/login">Sign in again</a>`
          : html`<button class="btn primary block" ?disabled=${this.busy}>${this.busy ? 'Verifying…' : 'Verify →'}</button>`}
        ${session.pendingMfa?.recoveryAvailable !== false ? html`<a href="/mfa/recovery">Lost your authenticator? Use a recovery code</a>` : nothing}
      </form>
    </vs-auth-layout>`;
  }
}
customElements.define('vs-mfa-challenge-page', VsMfaChallengePage);

/** Self-service recovery: password re-entry AND a recovery code (MFA-013, owner Decision 2). */
export class VsMfaRecoveryPage extends LitElement {
  static override properties = { error: { state: true }, busy: { state: true } };
  declare error: string;
  declare busy: boolean;
  static override styles = [...shared, formStyles];
  constructor() {
    super();
    this.error = '';
    this.busy = false;
  }
  override connectedCallback() {
    super.connectedCallback();
    if (!session.pendingMfa) queueMicrotask(() => navigate('/login'));
  }
  private async submit(e: Event) {
    e.preventDefault();
    const f = e.target as HTMLFormElement;
    const password = (f.elements.namedItem('password') as HTMLInputElement).value;
    const code = (f.elements.namedItem('recovery_code') as HTMLInputElement).value.trim().toUpperCase();
    if (!password || !code) {
      this.error = 'Enter your password and a recovery code.';
      return;
    }
    this.busy = true;
    try {
      await session.recover(password, code);
      navigate('/recovery-mode');
    } catch (err) {
      const p = err as ApiProblem;
      this.error = p.code === 'MFA_CHALLENGE_INVALID' ? 'This sign-in attempt expired. Please sign in again.' :
        p.code === 'RATE_LIMITED' ? 'Too many attempts. Please wait and try again.' : 'Password or recovery code is incorrect.';
    } finally {
      this.busy = false;
    }
  }
  override render() {
    return html`<vs-auth-layout>
      <div><h1 class="display">Recover your account</h1><p class="muted">Re-enter your password and one of your recovery codes.</p></div>
      <form @submit=${this.submit} novalidate>
        <label class="field"><span class="label">Password</span><input name="password" type="password" autocomplete="current-password" aria-required="true" /></label>
        <label class="field"><span class="label">Recovery code</span><input name="recovery_code" autocomplete="off" placeholder="XXXXX-XXXXX" aria-required="true" /></label>
        <p class="danger-text" role="alert" aria-live="assertive">${this.error ? html`⚠ ${this.error}` : nothing}</p>
        <button class="btn primary block" ?disabled=${this.busy}>${this.busy ? 'Checking…' : 'Recover →'}</button>
        <a href="/mfa">Back to code entry</a>
      </form>
    </vs-auth-layout>`;
  }
}
customElements.define('vs-mfa-recovery-page', VsMfaRecoveryPage);

/** Restricted recovery shell: only "Set up new authenticator" and "Sign out" (09 §4.10). */
export class VsRecoveryModePage extends LitElement {
  static override styles = [...shared, css`:host { display: block; max-width: 560px; margin: 64px auto; padding: 0 16px; } .stack { gap: 20px; }`];
  override render() {
    return html`<div class="stack">
      <h1 class="display">Recovery mode</h1>
      <vs-banner kind="warning">${t('recovery.banner')}</vs-banner>
      <div class="row">
        <a class="btn primary" href="/mfa/enroll?mode=recovery">Set up new authenticator →</a>
        <button class="btn" @click=${async () => { await session.logout(); navigate('/login'); }}>Sign out</button>
      </div>
    </div>`;
  }
}
customElements.define('vs-recovery-mode-page', VsRecoveryModePage);

export class VsEnrollEmailSentPage extends LitElement {
  static override styles = shared;
  override render() {
    const email = session.pendingMfa?.email;
    return html`<vs-auth-layout>
      <h1 class="display">Check your email</h1>
      <p>We've sent a secure setup link to ${email ? html`<strong>your verified address</strong>` : 'your verified address'}. It expires in 30 minutes.</p>
      <p class="muted">Two-step verification is required for your account. For your security, an authenticator can only be set up from that link.</p>
      <a href="/login">Back to sign in</a>
    </vs-auth-layout>`;
  }
}
customElements.define('vs-enroll-email-sent-page', VsEnrollEmailSentPage);

type EnrollMode = 'email' | 'recovery' | 'invite' | 'profile';

/**
 * Authenticator enrollment (05 §11.3). Every path combines two independent proofs:
 *  A profile  – FULL session + fresh password re-entry ({reauth:true}; server asks for step-up)
 *  B invite   – invite token + new password ({invite_context})
 *  C email    – emailed enrollment token + password ({enrollment_token, password})
 *  D recovery – RECOVERY session (password + recovery code) ({})
 */
export class VsMfaEnrollPage extends LitElement {
  static override properties = {
    step: { state: true }, start: { state: true }, error: { state: true }, busy: { state: true }, codes: { state: true }, coolingOff: { state: true },
  };
  declare step: 'proof' | 'scan' | 'codes';
  declare start: EnrollStart | null;
  declare error: string;
  declare busy: boolean;
  declare codes: string[];
  declare coolingOff: string | null;
  private mode: EnrollMode = 'profile';
  private enrollmentToken: string | null = null;
  private inviteContext: string | null = null;
  private result: AuthenticatedResult | null = null;
  static override styles = [...shared, formStyles, css`ol.steps { padding-left: 20px; display: flex; flex-direction: column; gap: 16px; } .secret { font-family: var(--vs-font-mono); word-break: break-all; }`];

  constructor() {
    super();
    this.step = 'proof';
    this.start = null;
    this.error = '';
    this.busy = false;
    this.codes = [];
    this.coolingOff = null;
  }

  override connectedCallback() {
    super.connectedCallback();
    const q = new URLSearchParams(window.location.search);
    this.enrollmentToken = fragmentParam('token') ?? q.get('token');
    if (this.enrollmentToken) this.mode = 'email';
    else if (q.get('mode') === 'invite') this.mode = 'invite';
    else if (session.isRecovery) this.mode = 'recovery';
    else this.mode = 'profile';
    if (this.mode === 'invite') this.inviteContext = takeInviteContext();
    if (this.mode === 'invite' && !this.inviteContext) {
      this.error = 'This setup link is no longer valid. Open the invitation link from your email again.';
      return;
    }
    if (this.mode !== 'email') void this.begin();
  }

  private async begin(password?: string) {
    this.busy = true;
    this.error = '';
    let body: Record<string, unknown> = {};
    if (this.mode === 'email') body = { enrollment_token: this.enrollmentToken, password };
    else if (this.mode === 'invite') body = { invite_context: this.inviteContext };
    else if (this.mode === 'profile') body = { reauth: true };
    try {
      const { data } = await api.post<EnrollStart>('/api/v1/auth/mfa/enroll/start', body, { anonymous: this.mode === 'email' || this.mode === 'invite' });
      this.start = data;
      this.step = 'scan';
    } catch (err) {
      const p = err as ApiProblem;
      this.error =
        p.code === 'ENROLLMENT_PROOF_INVALID' ? (this.mode === 'email' ? 'The link has expired or the password is incorrect.' : 'We could not verify it is you. Start again.') :
        p.code === 'MFA_ALREADY_ENROLLED' ? 'You already have an authenticator. Remove it first or replace it from your profile.' :
        p.code === 'SESSION_INVALID' ? 'Your recovery session expired. Sign in again with a different recovery code.' :
        p.code === 'STEP_UP_REQUIRED' ? 'Please confirm your password to continue.' :
        p.detail || 'Could not start setup.';
    } finally {
      this.busy = false;
    }
  }

  private async proof(e: Event) {
    e.preventDefault();
    const pw = ((e.target as HTMLFormElement).elements.namedItem('password') as HTMLInputElement).value;
    if (!pw) {
      this.error = 'Enter your password.';
      return;
    }
    await this.begin(pw);
  }

  private async confirm(e: Event) {
    e.preventDefault();
    const f = e.target as HTMLFormElement;
    const code = (f.elements.namedItem('code') as HTMLInputElement).value.replace(/\s/g, '');
    const label = (f.elements.namedItem('label') as HTMLInputElement).value.trim();
    if (!/^\d{6}$/.test(code)) {
      this.error = 'Enter the 6-digit code from the app.';
      return;
    }
    this.busy = true;
    this.error = '';
    try {
      const { data } = await api.post<AuthenticatedResult>(
        '/api/v1/auth/mfa/enroll/confirm',
        { challenge_token: this.start?.challenge_token, code, label: label || undefined },
        { anonymous: this.mode === 'email' || this.mode === 'invite' },
      );
      this.result = data;
      this.codes = data.recovery_codes ?? [];
      this.coolingOff = data.cooling_off_until ?? null;
      this.step = 'codes';
    } catch (err) {
      const p = err as ApiProblem;
      this.error = p.code === 'MFA_CODE_INVALID' ? "That code didn't work. Check the time on your phone and try the current code." :
        p.code === 'SESSION_INVALID' ? 'Your recovery session expired. Sign in again with a different recovery code.' :
        p.detail || 'Could not confirm the code.';
    } finally {
      this.busy = false;
    }
  }

  private async finish() {
    if (this.result?.access_token) await session.completeAuthentication(this.result);
    else await session.reloadMe();
    navigate(session.isAuthenticated ? '/' : '/login');
  }

  override render() {
    return html`<vs-auth-layout eyebrow="Security" tagline="Protect your workspace with a second step.">
      <div><h1 class="display">Set up two-step verification</h1></div>
      ${this.step === 'proof' && this.mode === 'email'
        ? html`<form @submit=${this.proof} novalidate>
            <p>Confirm your password to continue setting up your authenticator.</p>
            <label class="field"><span class="label">Password</span><input name="password" type="password" autocomplete="current-password" aria-required="true" /></label>
            <p class="danger-text" role="alert">${this.error || nothing}</p>
            <button class="btn primary block" ?disabled=${this.busy}>Continue →</button>
          </form>`
        : nothing}
      ${this.step === 'proof' && this.mode !== 'email'
        ? html`${this.busy ? html`<vs-skeleton rows="3"></vs-skeleton>` : nothing}
            ${this.error ? html`<p class="danger-text" role="alert">${this.error}</p>
              ${this.mode === 'profile' ? html`<button class="btn" @click=${() => this.begin()}>Try again</button>` : html`<a href="/login">Back to sign in</a>`}` : nothing}`
        : nothing}
      ${this.step === 'scan' && this.start
        ? html`<ol class="steps">
            <li>Install an authenticator app (for example Google Authenticator, Microsoft Authenticator or 1Password).</li>
            <li><p>Scan this code:</p><vs-qr-code .value=${this.start.otpauth_uri}></vs-qr-code>
              <details><summary>Can't scan? Enter this key</summary><p class="secret">${this.start.secret}</p><p class="small muted">The key is shown only once.</p></details></li>
            <li><form @submit=${this.confirm} novalidate>
              <label class="field"><span class="label">6-digit code</span>${codeInput(this.error)}</label>
              <label class="field"><span class="label">Device name (optional)</span><input name="label" maxlength="100" placeholder="My phone" /></label>
              <p id="code-err" class="danger-text" role="alert" aria-live="assertive">${this.error || nothing}</p>
              <button class="btn primary block" ?disabled=${this.busy}>${this.busy ? 'Confirming…' : 'Confirm →'}</button>
            </form></li>
          </ol>`
        : nothing}
      ${this.step === 'codes'
        ? html`${this.coolingOff ? html`<vs-banner kind="warning">For your security, email, password and access changes are locked until ${formatAbsolute(this.coolingOff)}.</vs-banner>` : nothing}
            <vs-recovery-codes .codes=${this.codes} @continue=${this.finish}></vs-recovery-codes>`
        : nothing}
    </vs-auth-layout>`;
  }
}
customElements.define('vs-mfa-enroll-page', VsMfaEnrollPage);
