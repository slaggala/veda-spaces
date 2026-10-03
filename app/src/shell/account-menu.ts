import { LitElement, css, html, nothing } from 'lit';
import { icon } from '../design-system/icons.js';
import { shared } from '../design-system/styles.js';

/**
 * Account menu in the top bar: a disclosure button and a panel of links (09 §3.2; IR-37, RR-18).
 *
 * The panel closes, without stealing focus, on a pointer press anywhere outside it and when keyboard focus leaves
 * it; Escape (from the button or the panel) closes it and returns focus to the button. Choosing an entry closes it.
 * "Sign out" is reported as a `sign-out` event so the shell owns the session.
 */
export class VsAccountMenu extends LitElement {
  static override properties = { open: { type: Boolean, reflect: true }, name: { type: String }, initials: { type: String } };
  declare open: boolean;
  declare name: string;
  declare initials: string;
  static override styles = [
    ...shared,
    css`
      :host { position: relative; display: block; }
      .panel { position: absolute; right: 0; top: 48px; min-width: 220px; background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: 8px; box-shadow: var(--vs-shadow); padding: 8px; z-index: 50; display: flex; flex-direction: column; }
      .panel a, .panel button { text-align: left; background: none; border: 0; min-height: 44px; padding: 0 12px; font: inherit; color: var(--vs-ink); cursor: pointer; text-decoration: none; display: flex; align-items: center; gap: 8px; }
      .toggle { background: none; border: 0; cursor: pointer; min-height: 44px; min-width: 44px; }
      .avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--vs-cream); color: var(--vs-ink); display: inline-flex; align-items: center; justify-content: center; font: 700 12px/1 var(--vs-font-sans); }
    `,
  ];

  constructor() {
    super();
    this.open = false;
    this.name = '';
    this.initials = '';
  }

  // composedPath() crosses shadow roots, so a press on any part of this element (or inside the panel) is "inside".
  private onDocPointer = (e: PointerEvent) => {
    if (this.open && !e.composedPath().includes(this)) this.open = false;
  };

  override connectedCallback() {
    super.connectedCallback();
    document.addEventListener('pointerdown', this.onDocPointer, true);
  }
  override disconnectedCallback() {
    document.removeEventListener('pointerdown', this.onDocPointer, true);
    super.disconnectedCallback();
  }

  /** Close and put focus back on the toggle (Escape, or after a choice that stays on the page). */
  close(restoreFocus = true) {
    this.open = false;
    if (restoreFocus) this.updateComplete.then(() => (this.renderRoot.querySelector('.toggle') as HTMLElement | null)?.focus());
  }

  private onKey(e: KeyboardEvent) {
    if (e.key !== 'Escape' || !this.open) return;
    e.stopPropagation();
    this.close();
  }

  private onFocusOut(e: FocusEvent) {
    const to = e.relatedTarget as Node | null;
    // relatedTarget is retargeted to this host when focus moves within the shadow root; null means it left the page.
    if (this.open && to && to !== this && !this.contains(to) && !this.renderRoot.contains(to)) this.open = false;
  }

  override render() {
    return html`<div @keydown=${this.onKey} @focusout=${this.onFocusOut}>
      <button class="toggle" aria-controls="account-menu" aria-expanded=${this.open ? 'true' : 'false'} aria-label="Account menu"
        @click=${() => (this.open = !this.open)}><span class="avatar" aria-hidden="true">${this.initials}</span></button>
      ${this.open
        ? html`<div class="panel" id="account-menu">
            <span class="small muted">${this.name}</span>
            <a href="/profile" @click=${() => this.close(false)}>${icon('settings')} Profile</a>
            <button @click=${() => { this.close(false); this.dispatchEvent(new CustomEvent('sign-out', { bubbles: true, composed: true })); }}>${icon('logout')} Sign out</button>
          </div>`
        : nothing}
    </div>`;
  }
}
customElements.define('vs-account-menu', VsAccountMenu);
