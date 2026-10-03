import { LitElement, css, html, nothing } from 'lit';
import { api } from '../core/api/client.js';
import type { ApiProblem } from '../core/api/problem.js';
import { registerStepUpPresenter } from '../core/auth/step-up.js';
import { shared } from '../design-system/styles.js';

/**
 * "Confirm it's you" (09 §4.10): step-up with the authenticator (kind=mfa, POST /auth/mfa/step-up) or
 * password re-entry for users without a factor (kind=password, POST /auth/reauth). Resolves the pending
 * API call so it is retried once (05 §11.6).
 */
export class VsStepUpDialog extends LitElement {
  static override properties = {
    open: { state: true }, kind: { state: true }, error: { state: true }, busy: { state: true },
    warning: { state: true }, expired: { state: true }, expiresInMinutes: { state: true },
  };
  declare open: boolean;
  declare kind: 'mfa' | 'password';
  declare error: string;
  declare busy: boolean;
  /** Polite pre-expiry warning (AX-07: time-outs are announced before expiry; RR-18). */
  declare warning: string;
  /** The step-up challenge expired: the code can no longer be confirmed. */
  declare expired: boolean;
  declare expiresInMinutes: number;
  /** How long before expiry the warning is announced. */
  static warnBeforeMs = 60_000;
  private mfaToken = '';
  private resolve: ((ok: boolean) => void) | null = null;
  private timers: number[] = [];
  static override styles = [...shared, css`form { display: flex; flex-direction: column; gap: 16px; }`];

  constructor() {
    super();
    this.open = false;
    this.kind = 'mfa';
    this.error = '';
    this.busy = false;
    this.warning = '';
    this.expired = false;
    this.expiresInMinutes = 0;
  }

  override connectedCallback() {
    super.connectedCallback();
    registerStepUpPresenter((problem) => this.present(problem));
  }
  override disconnectedCallback() {
    this.clearTimers();
    registerStepUpPresenter(null);
    super.disconnectedCallback();
  }

  present(problem: ApiProblem): Promise<boolean> {
    this.kind = problem.ext<string>('kind') === 'password' ? 'password' : 'mfa';
    this.mfaToken = problem.ext<string>('mfa_token') ?? '';
    this.error = '';
    this.warning = '';
    this.expired = false;
    this.clearTimers();
    const expiresIn = problem.ext<number>('expires_in');
    this.expiresInMinutes = this.kind === 'mfa' && typeof expiresIn === 'number' && expiresIn > 0 ? Math.max(1, Math.round(expiresIn / 60)) : 0;
    if (this.expiresInMinutes) {
      const ms = (expiresIn as number) * 1000;
      this.timers.push(window.setTimeout(() => { if (!this.expired) this.warning = 'This confirmation expires in 1 minute.'; },
        Math.max(0, ms - VsStepUpDialog.warnBeforeMs)));
      this.timers.push(window.setTimeout(() => this.expire(), ms));
    }
    this.open = true;
    return new Promise((resolve) => (this.resolve = resolve));
  }

  private clearTimers() {
    this.timers.forEach((t) => clearTimeout(t));
    this.timers = [];
  }

  private expire() {
    this.clearTimers();
    this.expired = true;
    this.warning = '';
    this.error = 'This confirmation expired. Cancel, then try the action again.';
  }

  private finish(ok: boolean) {
    this.clearTimers();
    this.open = false;
    this.resolve?.(ok);
    this.resolve = null;
  }

  private async submit(e: Event) {
    e.preventDefault();
    if (this.expired) return;
    const form = e.target as HTMLFormElement;
    const input = form.elements.namedItem('secret') as HTMLInputElement;
    const value = input.value.trim();
    if (!value) {
      this.error = this.kind === 'mfa' ? 'Enter the 6-digit code.' : 'Enter your password.';
      return;
    }
    this.busy = true;
    try {
      if (this.kind === 'mfa') await api.post('/api/v1/auth/mfa/step-up', { mfa_token: this.mfaToken, code: value }, { noRetry: true });
      else await api.post('/api/v1/auth/reauth', { password: value }, { noRetry: true });
      this.finish(true);
    } catch (err) {
      const p = err as ApiProblem;
      if (p.code === 'MFA_CHALLENGE_INVALID') {
        this.expire();
        return;
      }
      const left = p.ext<number>('attempts_remaining');
      this.error =
        p.code === 'MFA_CODE_INVALID'
          ? `That code didn't work.${left !== undefined ? ` ${left === 1 ? '1 attempt' : `${left} attempts`} left.` : ' Try the current code.'}` :
        p.code === 'INVALID_CREDENTIALS' ? 'That password is incorrect.' :
        p.code === 'RATE_LIMITED' ? 'Too many attempts. Please wait and try again.' :
        p.detail || 'Could not confirm. Try again.';
      input.value = '';
      input.focus();
    } finally {
      this.busy = false;
    }
  }

  override render() {
    return html`<vs-dialog .open=${this.open} heading="Confirm it's you" @close=${() => this.resolve && this.finish(false)}>
      <form @submit=${this.submit} novalidate>
        <p id="su-help">${this.kind === 'mfa'
          ? `Enter the 6-digit code from your authenticator app to continue.${this.expiresInMinutes ? ` This request expires in ${this.expiresInMinutes} minute${this.expiresInMinutes === 1 ? '' : 's'}.` : ''}`
          : 'Re-enter your password to continue.'}</p>
        <p class="muted" role="status" aria-live="polite">${this.warning}</p>
        <label class="field"><span class="label">${this.kind === 'mfa' ? 'Code' : 'Password'}</span>
          ${this.kind === 'mfa'
            ? html`<input name="secret" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]*" ?disabled=${this.expired} aria-invalid=${this.error ? 'true' : 'false'} aria-describedby="su-help su-err" />`
            : html`<input name="secret" type="password" autocomplete="current-password" aria-invalid=${this.error ? 'true' : 'false'} aria-describedby="su-err" />`}
          <span id="su-err" class="error" aria-live="assertive">${this.error || nothing}</span>
        </label>
        <div class="row"><span class="spacer"></span>
          <button type="button" class="btn" @click=${() => this.finish(false)}>Cancel</button>
          <button class="btn primary" ?disabled=${this.busy || this.expired}>${this.busy ? 'Confirming…' : 'Confirm'}</button>
        </div>
      </form>
    </vs-dialog>`;
  }
}
customElements.define('vs-step-up-dialog', VsStepUpDialog);
