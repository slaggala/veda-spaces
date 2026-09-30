import { LitElement, css, html, nothing, svg } from 'lit';
import qrcode from 'qrcode-generator';
import { shared } from '../../design-system/styles.js';
import { passwordChecks, strength } from './password.js';

/** Renders an otpauth:// URI as an inline SVG QR code (no innerHTML). */
export class VsQrCode extends LitElement {
  static override properties = { value: { type: String } };
  declare value: string;
  static override styles = css`:host { display: inline-block; background: var(--vs-surface); padding: 12px; border: 1px solid var(--vs-line); border-radius: 8px; } svg { display: block; width: 180px; height: 180px; } rect.d { fill: var(--vs-ink); }`;
  override render() {
    if (!this.value) return nothing;
    const qr = qrcode(0, 'M');
    qr.addData(this.value);
    qr.make();
    const n = qr.getModuleCount();
    const cells = [];
    for (let r = 0; r < n; r += 1) for (let c = 0; c < n; c += 1) if (qr.isDark(r, c)) cells.push(svg`<rect class="d" x=${c} y=${r} width="1" height="1"/>`);
    return html`<svg viewBox="0 0 ${n} ${n}" role="img" aria-label="QR code for your authenticator app" shape-rendering="crispEdges">${cells}</svg>`;
  }
}
customElements.define('vs-qr-code', VsQrCode);

/** Recovery codes shown once, with download/copy/print and an acknowledgement (09 §4.10, MFA-005). */
export class VsRecoveryCodes extends LitElement {
  static override properties = { codes: { attribute: false }, saved: { state: true } };
  declare codes: string[];
  declare saved: boolean;
  static override styles = [
    ...shared,
    css`
      ol { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 24px; list-style: none; padding: 16px; margin: 0; background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: 8px; }
      li { font-family: var(--vs-font-mono); font-size: 15px; letter-spacing: .06em; }
    `,
  ];
  constructor() {
    super();
    this.codes = [];
    this.saved = false;
  }
  private download() {
    const blob = new Blob([`Veda Spaces recovery codes\nEach code works once.\n\n${this.codes.join('\n')}\n`], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'veda-spaces-recovery-codes.txt';
    a.click();
    URL.revokeObjectURL(a.href);
  }
  override render() {
    return html`<div class="stack">
      <p>Save these recovery codes somewhere safe. Each works once, and they won't be shown again.</p>
      <ol aria-label="Recovery codes">${this.codes.map((c) => html`<li>${c}</li>`)}</ol>
      <div class="row">
        <button class="btn small" @click=${this.download}>Download .txt</button>
        <button class="btn small" @click=${() => navigator.clipboard?.writeText(this.codes.join('\n'))}>Copy</button>
        <button class="btn small" @click=${() => window.print()}>Print</button>
      </div>
      <label class="check"><input type="checkbox" .checked=${this.saved} @change=${(e: Event) => (this.saved = (e.target as HTMLInputElement).checked)} /> I have saved these codes</label>
      <button class="btn primary" ?disabled=${!this.saved} @click=${() => this.dispatchEvent(new CustomEvent('continue', { bubbles: true, composed: true }))}>Continue →</button>
    </div>`;
  }
}
customElements.define('vs-recovery-codes', VsRecoveryCodes);

/** New-password field with policy checklist and strength meter (09 §4.2). */
export class VsNewPassword extends LitElement {
  static override properties = { personal: { attribute: false }, value: { state: true }, show: { state: true }, error: { type: String } };
  declare personal: string[];
  declare value: string;
  declare show: boolean;
  declare error: string;
  static override styles = [
    ...shared,
    css`
      .meter { height: 6px; background: var(--vs-cream); border-radius: 2px; overflow: hidden; display: flex; gap: 2px; }
      .meter span { flex: 1; background: var(--vs-cream); }
      .meter span.on { background: var(--vs-copper); }
      ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 2px; font-size: 13px; }
      li.ok { color: var(--vs-success); }
      li.ok::before { content: '✓ '; }
      li:not(.ok)::before { content: '○ '; }
      .show { background: none; border: 0; color: var(--vs-copper-text); cursor: pointer; font: 600 12px var(--vs-font-sans); }
    `,
  ];
  constructor() {
    super();
    this.personal = [];
    this.value = '';
    this.show = false;
    this.error = '';
  }
  get valid(): boolean {
    return passwordChecks(this.value, this.personal).every((c) => c.ok);
  }
  override focus() {
    (this.renderRoot.querySelector('input') as HTMLInputElement | null)?.focus();
  }
  override render() {
    const checks = passwordChecks(this.value, this.personal);
    const s = strength(this.value);
    return html`<div class="field">
      <span class="row"><label class="label" for="np">New password</label><span class="spacer"></span>
        <button type="button" class="show" @click=${() => (this.show = !this.show)} aria-pressed=${this.show ? 'true' : 'false'}>${this.show ? 'Hide' : 'Show'}</button></span>
      <input id="np" name="new_password" type=${this.show ? 'text' : 'password'} autocomplete="new-password" aria-required="true"
        aria-invalid=${this.error ? 'true' : 'false'} aria-describedby="np-rules np-err" .value=${this.value}
        @input=${(e: Event) => {
          this.value = (e.target as HTMLInputElement).value;
          this.dispatchEvent(new CustomEvent('value-change', { detail: this.value }));
        }} />
      <div class="meter" aria-hidden="true">${[1, 2, 3, 4].map((i) => html`<span class=${i <= s.score ? 'on' : ''}></span>`)}</div>
      <span class="small muted">${this.value ? s.label : ''}</span>
      <ul id="np-rules">${checks.map((c) => html`<li class=${c.ok ? 'ok' : ''}>${c.label}</li>`)}</ul>
      <span id="np-err" class="error" aria-live="polite">${this.error || nothing}</span>
    </div>`;
  }
}
customElements.define('vs-new-password', VsNewPassword);

declare global {
  interface Window {
    turnstile?: { render(el: Element, opts: Record<string, unknown>): string; reset(id?: string): void };
  }
}

const siteKey = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_TURNSTILE_SITE_KEY ?? '';

/** Cloudflare Turnstile widget, shown on login after repeated failures from this network (05 §4). */
export class VsTurnstile extends LitElement {
  static override properties = { token: { state: true } };
  declare token: string;
  constructor() {
    super();
    this.token = '';
  }
  static get enabled(): boolean {
    return Boolean(siteKey);
  }
  protected override async firstUpdated() {
    if (!siteKey) return;
    if (!window.turnstile) {
      await new Promise<void>((resolve, reject) => {
        const s = document.createElement('script');
        s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
        s.async = true;
        s.onload = () => resolve();
        s.onerror = () => reject(new Error('turnstile'));
        document.head.append(s);
      }).catch(() => undefined);
    }
    const host = this.renderRoot.querySelector('div');
    if (host && window.turnstile) {
      window.turnstile.render(host, { sitekey: siteKey, callback: (t: string) => (this.token = t) });
    }
  }
  override render() {
    return siteKey ? html`<div></div>` : html`<p class="small">Additional verification is required. Please wait a few minutes and try again.</p>`;
  }
}
customElements.define('vs-turnstile', VsTurnstile);
