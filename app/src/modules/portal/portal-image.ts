import { LitElement, css, html, nothing, type PropertyValues } from 'lit';
import { documentImage } from './api.js';

/**
 * A document Veda Spaces shared on the customer's project (CPP-D04), loaded through the portal session. An <img> cannot
 * carry the X-Veda-Portal header and the site CSP allows images only from 'self' and data:, so the bytes are fetched
 * with the header and inlined. Nothing is cached beyond this element; a refusal shows a plain "not available". The bytes
 * are fetched only once the element is near the viewport (a long list never loads every image at once), and again
 * whenever its document changes (an element reused for another document never shows the previous image).
 */
export class VsPortalImage extends LitElement {
  static override properties = { propertyId: { attribute: false }, documentId: { attribute: false }, label: { attribute: false },
    variant: { attribute: false }, src: { state: true }, failed: { state: true } };
  declare propertyId: string;
  declare documentId: string;
  declare label: string;
  declare variant: 'thumb' | 'mobile' | 'desktop';
  declare src: string | null;
  declare failed: boolean;

  static override styles = css`
    :host { display: block; }
    img { display: block; width: 100%; height: auto; border-radius: var(--vs-radius, 8px); background: var(--vs-paper, #f5f2ed); }
    .ph { display: flex; align-items: center; justify-content: center; min-height: 96px; border-radius: var(--vs-radius, 8px);
      background: var(--vs-paper, #f5f2ed); color: var(--vs-muted, #5c5750); font-size: 14px; padding: 8px; text-align: center; }
  `;

  constructor() {
    super();
    this.src = null;
    this.failed = false;
    this.variant = 'mobile';
  }

  private observer: IntersectionObserver | null = null;
  private visible = false;
  private request = 0;

  override connectedCallback(): void {
    super.connectedCallback();
    if (typeof IntersectionObserver === 'undefined') { this.visible = true; return; }
    this.observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && !this.visible) { this.visible = true; void this.fetch(); }
    }, { rootMargin: '200px' });
    this.observer.observe(this);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.observer?.disconnect();
    this.observer = null;
    this.request += 1; // a response arriving after removal is dropped
  }

  protected override updated(changed: PropertyValues): void {
    if ((changed.has('propertyId') || changed.has('documentId') || changed.has('variant')) && this.visible) void this.fetch();
  }

  private async fetch(): Promise<void> {
    const mine = ++this.request;
    this.src = null;
    this.failed = false;
    const url = await documentImage(this.propertyId, this.documentId, this.variant);
    if (mine !== this.request) return; // a newer document (or removal) superseded this request
    if (url) this.src = url; else this.failed = true;
  }

  override render() {
    if (this.src) return html`<img src=${this.src} alt=${this.label} />`;
    return html`<div class="ph" role=${this.failed ? 'status' : nothing}>${this.failed ? 'This image is not available right now.' : 'Loading image…'}</div>`;
  }
}

customElements.define('vs-portal-image', VsPortalImage);
