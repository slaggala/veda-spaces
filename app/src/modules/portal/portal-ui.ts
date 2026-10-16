import { LitElement, css, html, nothing } from 'lit';
import { formatAbsolute, formatDate } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import { shared } from '../../design-system/styles.js';
import { forgetSession, portalApi, STATE_LABELS, transient, type StepState } from './api.js';

/**
 * Shared look of the customer portal: a calm, premium, mobile-first page with no workspace chrome. Information first,
 * then what needs the customer, in plain words; states are always named in text (never colour alone).
 */
export const portalStyles = [...shared, css`
  :host { display: block; min-height: 100vh; background: var(--vs-paper); color: var(--vs-ink); }
  .wrap { max-width: 1040px; margin: 0 auto; padding: var(--vs-space-5) var(--vs-space-4) var(--vs-space-8); display: flex; flex-direction: column; gap: var(--vs-space-5); }
  h1, h2, h3 { font-family: var(--vs-font-serif); font-weight: 500; margin: 0; overflow-wrap: anywhere; }
  h1 { font-size: 30px; line-height: 38px; }
  h2 { font-size: 22px; line-height: 30px; }
  h3 { font-size: 17px; line-height: 24px; font-family: var(--vs-font-sans); font-weight: 600; }
  p { margin: 0; }
  a { color: var(--vs-copper-text); }
  .lead-text { font-size: 17px; line-height: 26px; }
  .card { overflow-wrap: anywhere; }
  .section { display: flex; flex-direction: column; gap: var(--vs-space-3); scroll-margin-top: var(--vs-space-6); }
  .btn, button, a.btn { min-height: var(--vs-target); }
  a.btn { display: inline-flex; align-items: center; justify-content: center; text-decoration: none; }
  a.back { display: inline-flex; align-items: center; min-height: var(--vs-target); }
  :is(a, button, input, select, summary):focus-visible { outline: 2px solid var(--vs-focus-ring); outline-offset: 2px; }
  /* Headings take focus only to orient screen-reader users after a change; they are not controls. */
  :is(h1, h2, h3)[tabindex='-1']:focus { outline: none; }
  .badge { display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px; border-radius: var(--vs-radius-pill); font-size: 13px; line-height: 22px; font-weight: 600; border: 1px solid var(--vs-line); background: var(--vs-surface); white-space: nowrap; }
  .badge::before { content: ''; width: 8px; height: 8px; border-radius: 50%; background: var(--vs-ink-muted); }
  .badge.COMPLETED::before { background: var(--vs-success); }
  .badge.ACTION_REQUIRED { border-color: var(--vs-copper); color: var(--vs-copper-text); }
  .badge.ACTION_REQUIRED::before { background: var(--vs-copper); }
  .badge.IN_PROGRESS::before { background: var(--vs-copper-strong); }
  .badge.UPCOMING::before { background: transparent; border: 2px solid var(--vs-ink-muted); width: 6px; height: 6px; }
  .badge.NOT_YET_AVAILABLE { color: var(--vs-ink-muted); }
  .badge.BLOCKED { border-color: var(--vs-warning); color: var(--vs-warning); }
  .badge.BLOCKED::before { border-radius: 1px; background: var(--vs-warning); }
  /* payment states (PCM): each has its own marker shape as well as its word */
  .badge.PAID::before, .badge.VALID::before { background: var(--vs-success); }
  .badge.OVERDUE, .badge.DUE, .badge.PARTIALLY_PAID { border-color: var(--vs-copper); color: var(--vs-copper-text); }
  .badge.OVERDUE::before { border-radius: 1px; transform: rotate(45deg); background: var(--vs-copper); }
  .badge.DUE::before { background: var(--vs-copper); }
  .badge.PARTIALLY_PAID::before { background: linear-gradient(90deg, var(--vs-copper) 50%, transparent 50%); border: 1px solid var(--vs-copper); }
  .badge.CANCELLED, .badge.CORRECTED { color: var(--vs-ink-muted); }
  .muted { color: var(--vs-ink-muted); }
  .facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--vs-space-3); margin: 0; }
  .facts div { display: flex; flex-direction: column; gap: 2px; }
  .facts dt { font-size: 13px; color: var(--vs-ink-muted); }
  .facts dd { margin: 0; font-weight: 600; overflow-wrap: anywhere; }
  .amount { font-family: var(--vs-font-serif); font-size: 26px; line-height: 32px; }
  ul.plain { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vs-space-2); }
  ul.bullets { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: var(--vs-space-1); }
  .notice { border-left: 3px solid var(--vs-copper); padding: var(--vs-space-3) var(--vs-space-4); background: var(--vs-surface); border-radius: var(--vs-radius-card); }
`];

/** A state badge; ``state`` is a journey state, or a payment state (with its server-provided label). */
export function stateBadge(state: StepState | string, label?: string) {
  return html`<span class="badge ${state}">${label ?? STATE_LABELS[state as StepState] ?? state}</span>`;
}

/** A date (YYYY-MM-DD) or an instant, in the customer's words. */
export function when(value: string | null | undefined): string {
  if (!value) return '';
  return value.length === 10 ? formatDate(value) : formatAbsolute(value);
}

/** The portal's header: the brand, and sign out when signed in. */
export class VsPortalHeader extends LitElement {
  static override properties = { signedIn: { type: Boolean, attribute: 'signed-in' }, busy: { state: true } };
  declare signedIn: boolean;
  declare busy: boolean;

  static override styles = [...shared, css`
    :host { display: block; background: var(--vs-surface); border-bottom: 1px solid var(--vs-line); }
    header { max-width: 1040px; margin: 0 auto; padding: var(--vs-space-3) var(--vs-space-4); display: flex; align-items: center; justify-content: space-between; gap: var(--vs-space-3); }
    a.brand { font-family: var(--vs-font-serif); font-size: 22px; letter-spacing: .08em; color: var(--vs-copper-text); text-decoration: none; min-height: var(--vs-target); display: inline-flex; align-items: center; }
    .btn { min-height: var(--vs-target); }
    :is(a, button):focus-visible { outline: 2px solid var(--vs-focus-ring); outline-offset: 2px; }
  `];

  constructor() {
    super();
    this.signedIn = false;
    this.busy = false;
  }

  private async signOut() {
    this.busy = true;
    try { await portalApi.signOut(); } catch { /* the session ends here whatever the server says */ }
    forgetSession();
    this.busy = false;
    navigate('/portal');
  }

  override render() {
    return html`<header>
      <a class="brand" href="/portal" aria-label="Veda Spaces: your project portal home">VEDA SPACES</a>
      ${this.signedIn ? html`<button class="btn ghost" ?disabled=${this.busy} @click=${() => void this.signOut()}>Sign out</button>` : nothing}
    </header>`;
  }
}
customElements.define('vs-portal-header', VsPortalHeader);

/** Ask for a sign-in link by email. The answer never says whether the email has access. */
export class VsPortalSignIn extends LitElement {
  static override properties = { notice: { type: String }, sent: { state: true }, busy: { state: true }, error: { state: true } };
  declare notice: string;
  declare sent: string;
  declare busy: boolean;
  declare error: string;

  static override styles = [...portalStyles, css`
    .box { max-width: 480px; margin: var(--vs-space-6) auto 0; display: flex; flex-direction: column; gap: var(--vs-space-4); }
    input { min-height: var(--vs-target); font-size: 16px; }
  `];

  constructor() {
    super();
    this.notice = '';
    this.sent = '';
    this.busy = false;
    this.error = '';
  }

  private async submit(e: Event) {
    e.preventDefault();
    const input = this.renderRoot.querySelector<HTMLInputElement>('#email')!;
    const email = input.value.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      this.error = 'Enter the email address Veda Spaces has for you, for example name@example.com.';
      await this.updateComplete;
      input.focus();
      return;
    }
    this.error = '';
    this.busy = true;
    try {
      this.sent = (await portalApi.requestLink(email)).data.message;
      await this.updateComplete;
      this.renderRoot.querySelector<HTMLElement>('#sent')?.focus();
    } catch (err) {
      const p = err as { status: number; code?: string };
      this.error = p.status === 404 ? 'The project portal is not available here.'
        : transient(p) ? 'We could not send the link just now. Please wait a minute and try again.'
          : 'Please check the email address and try again.';
    } finally {
      this.busy = false;
    }
  }

  override render() {
    if (this.sent) {
      return html`<div class="box card" role="status">
        <h1 id="sent" tabindex="-1">Check your email</h1>
        <p class="lead-text">${this.sent}</p>
        <button class="btn ghost" @click=${() => { this.sent = ''; }}>Use a different email</button>
      </div>`;
    }
    return html`<form class="box card" novalidate @submit=${(e: Event) => void this.submit(e)}>
      <h1>Your project portal</h1>
      <p class="lead-text">Follow your interior project with Veda Spaces: your quotation, what comes next and who to talk to.</p>
      ${this.notice ? html`<p class="notice" role="status">${this.notice}</p>` : nothing}
      <label class="field"><span class="label">Your email address</span>
        <input id="email" type="email" autocomplete="email" inputmode="email" required aria-invalid=${this.error ? 'true' : 'false'}
          aria-describedby=${this.error ? 'email-error' : 'email-hint'} />
        ${this.error ? html`<span class="error" id="email-error">${this.error}</span>`
          : html`<span class="hint" id="email-hint">We will email you a link that signs you in. No password needed.</span>`}
      </label>
      <button class="btn primary block" type="submit" ?disabled=${this.busy}>${this.busy ? 'Sending…' : 'Email me a sign-in link'}</button>
    </form>`;
  }
}
customElements.define('vs-portal-sign-in', VsPortalSignIn);
