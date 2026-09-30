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
  static override properties = { open: { state: true }, kind: { state: true }, error: { state: true }, busy: { state: true } };
  declare open: boolean;
  declare kind: 'mfa' | 'password';
  declare error: string;
  declare busy: boolean;
  private mfaToken = '';
  private resolve: ((ok: boolean) => void) | null = null;
  static override styles = [...shared, css`form { display: flex; flex-direction: column; gap: 16px; }`];

  constructor() {
    super();
    this.open = false;
    this.kind = 'mfa';
    this.error = '';
    this.busy = false;
  }

  override connectedCallback() {
    super.connectedCallback();
    registerStepUpPresenter((problem) => this.present(problem));
  }
  override disconnectedCallback() {
    registerStepUpPresenter(null);
    super.disconnectedCallback();
  }

  present(problem: ApiProblem): Promise<boolean> {
    this.kind = problem.ext<string>('kind') === 'password' ? 'password' : 'mfa';
    this.mfaToken = problem.ext<string>('mfa_token') ?? '';
    this.error = '';
    this.open = true;
    return new Promise((resolve) => (this.resolve = resolve));
  }

  private finish(ok: boolean) {
    this.open = false;
    this.resolve?.(ok);
    this.resolve = null;
  }

  private async submit(e: Event) {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const value = (form.elements.namedItem('secret') as HTMLInputElement).value.trim();
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
      this.error =
        p.code === 'MFA_CODE_INVALID' ? "That code didn't work. Try the current code." :
        p.code === 'INVALID_CREDENTIALS' ? 'That password is incorrect.' :
        p.code === 'MFA_CHALLENGE_INVALID' ? 'This confirmation expired. Close and try the action again.' :
        p.detail || 'Could not confirm. Try again.';
    } finally {
      this.busy = false;
    }
  }

  override render() {
    return html`<vs-dialog .open=${this.open} heading="Confirm it's you" @close=${() => this.resolve && this.finish(false)}>
      <form @submit=${this.submit} novalidate>
        <p>${this.kind === 'mfa'
          ? 'Enter the 6-digit code from your authenticator app to continue.'
          : 'Re-enter your password to continue.'}</p>
        <label class="field"><span class="label">${this.kind === 'mfa' ? 'Code' : 'Password'}</span>
          ${this.kind === 'mfa'
            ? html`<input name="secret" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]*" aria-invalid=${this.error ? 'true' : 'false'} aria-describedby="su-err" />`
            : html`<input name="secret" type="password" autocomplete="current-password" aria-invalid=${this.error ? 'true' : 'false'} aria-describedby="su-err" />`}
          <span id="su-err" class="error" aria-live="assertive">${this.error || nothing}</span>
        </label>
        <div class="row"><span class="spacer"></span>
          <button type="button" class="btn" @click=${() => this.finish(false)}>Cancel</button>
          <button class="btn primary" ?disabled=${this.busy}>${this.busy ? 'Confirming…' : 'Confirm'}</button>
        </div>
      </form>
    </vs-dialog>`;
  }
}
customElements.define('vs-step-up-dialog', VsStepUpDialog);
