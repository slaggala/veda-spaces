import { LitElement, css, html, nothing } from 'lit';
import { api } from '../core/api/client.js';
import type { CursorMeta, Notification } from '../core/api/types.js';
import { formatRelative } from '../core/format/format.js';
import { navigate } from '../core/router/next.js';
import { icon } from '../design-system/icons.js';
import { shared } from '../design-system/styles.js';

/** In-app notifications, polled every 60 s and on focus (02 §10.2, NOTIF-001). */
export class VsNotificationsTray extends LitElement {
  static override properties = { items: { state: true }, unread: { state: true }, open: { state: true } };
  declare items: Notification[];
  declare unread: number;
  declare open: boolean;
  private timer: number | undefined;
  private onFocus = () => void this.poll();
  static override styles = [
    ...shared,
    css`
      :host { position: relative; display: inline-block; }
      .bell { position: relative; background: none; border: 0; color: inherit; min-width: 44px; min-height: 44px; cursor: pointer; }
      .badge { position: absolute; top: 6px; right: 4px; background: var(--vs-copper-strong); color: var(--vs-on-copper-strong); border-radius: 999px; font: 700 10px/16px var(--vs-font-sans); min-width: 16px; padding: 0 4px; }
      .panel { position: absolute; right: 0; top: 48px; width: min(380px, calc(100vw - 24px)); max-height: 70vh; overflow-y: auto; background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: 8px; box-shadow: var(--vs-shadow); z-index: 50; }
      header { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--vs-line); }
      ul { list-style: none; margin: 0; padding: 0; }
      li button { display: block; width: 100%; text-align: left; background: none; border: 0; border-bottom: 1px solid var(--vs-line); padding: 12px 16px; cursor: pointer; font: inherit; color: var(--vs-ink); }
      li.unread button { background: var(--vs-cream); }
      .empty { padding: 24px 16px; color: var(--vs-ink-muted); }
    `,
  ];

  constructor() {
    super();
    this.items = [];
    this.unread = 0;
    this.open = false;
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.poll();
    this.timer = window.setInterval(() => void this.poll(), 60_000);
    window.addEventListener('focus', this.onFocus);
  }
  override disconnectedCallback() {
    window.clearInterval(this.timer);
    window.removeEventListener('focus', this.onFocus);
    super.disconnectedCallback();
  }

  async poll() {
    try {
      const r = await api.get<Notification[]>('/api/v1/notifications', { limit: 20 });
      this.items = r.data ?? [];
      const meta = r.meta as Partial<CursorMeta>;
      this.unread = meta.unread_count ?? this.items.filter((n) => !n.read_on).length;
    } catch {
      /* polling failures are silent; the next poll retries */
    }
  }

  private async openItem(n: Notification) {
    if (!n.read_on) {
      try {
        await api.post(`/api/v1/notifications/${n.id}/read`);
      } catch { /* ignore */ }
    }
    this.open = false;
    void this.poll();
    if (n.link_path && /^\/(?![/\\])/.test(n.link_path)) navigate(n.link_path);
  }

  private async readAll() {
    await api.post('/api/v1/notifications/read-all');
    await this.poll();
  }

  override render() {
    return html`<button class="bell" aria-haspopup="true" aria-expanded=${this.open ? 'true' : 'false'}
        aria-label=${`Notifications${this.unread ? `, ${this.unread} unread` : ''}`} @click=${() => (this.open = !this.open)}>
        ${icon('bell')}${this.unread ? html`<span class="badge" aria-hidden="true">${this.unread}</span>` : nothing}
      </button>
      ${this.open
        ? html`<div class="panel" role="region" aria-label="Notifications" @keydown=${(e: KeyboardEvent) => e.key === 'Escape' && (this.open = false)}>
            <header><strong>Notifications</strong><span class="spacer"></span>
              ${this.unread ? html`<button class="btn ghost small" @click=${this.readAll}>Mark all read</button>` : nothing}</header>
            ${this.items.length
              ? html`<ul>${this.items.map(
                  (n) => html`<li class=${n.read_on ? '' : 'unread'}><button @click=${() => this.openItem(n)}>
                    <div class="strong">${n.title}</div>${n.body ? html`<div class="small muted">${n.body}</div>` : nothing}
                    <div class="small muted">${formatRelative(n.created_on)}</div></button></li>`,
                )}</ul>`
              : html`<p class="empty">You're all caught up.</p>`}
          </div>`
        : nothing}`;
  }
}
customElements.define('vs-notifications-tray', VsNotificationsTray);
