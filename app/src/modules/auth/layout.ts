import { LitElement, css, html } from 'lit';
import { shared } from '../../design-system/styles.js';

/** Split layout for sign-in screens: site photography + form panel (09 §4.1). */
export class VsAuthLayout extends LitElement {
  static override properties = { eyebrow: { type: String }, tagline: { type: String } };
  declare eyebrow: string;
  declare tagline: string;
  static override styles = [
    ...shared,
    css`
      :host { display: grid; grid-template-columns: 1.1fr 1fr; min-height: 100vh; }
      .hero { background-image: var(--vs-hero-overlay), url('/img/warm-hero.jpg'); background-size: cover; background-position: center; color: var(--vs-on-hero); display: flex; flex-direction: column; justify-content: flex-end; padding: 64px; gap: 16px; }
      .hero .eyebrow { color: var(--vs-on-hero); }
      .hero h2 { font-family: var(--vs-font-serif); font-size: 48px; line-height: 52px; max-width: 12em; }
      .panel { display: flex; flex-direction: column; justify-content: center; padding: 48px clamp(24px, 6vw, 96px); gap: 24px; background: var(--vs-paper); }
      .wordmark { font-family: var(--vs-font-serif); font-size: 20px; letter-spacing: .28em; }
      .content { max-width: 420px; width: 100%; display: flex; flex-direction: column; gap: 20px; }
      footer { font-size: 12px; color: var(--vs-ink-muted); }
      @media (max-width: 767px) {
        :host { grid-template-columns: 1fr; }
        .hero { min-height: 160px; padding: 24px; }
        .hero h2 { font-size: 30px; line-height: 34px; }
        .panel { padding: 24px 16px; justify-content: flex-start; }
      }
    `,
  ];
  constructor() {
    super();
    this.eyebrow = 'Studio workspace';
    this.tagline = 'Designing homes, one relationship at a time.';
  }
  override render() {
    return html`<div class="hero" aria-hidden="true"><p class="eyebrow">${this.eyebrow}</p><h2>${this.tagline}</h2></div>
      <div class="panel"><div class="wordmark">VEDA SPACES</div><div class="content"><slot></slot></div>
      <footer>Staff access only · <a href="https://www.vedaspaces.com/privacy">Privacy</a></footer></div>`;
  }
}
customElements.define('vs-auth-layout', VsAuthLayout);
