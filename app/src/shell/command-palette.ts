import { LitElement, css, html, nothing } from 'lit';
import { api } from '../core/api/client.js';
import type { Lead, PermissionMap } from '../core/api/types.js';
import { filterNav, has, NAV_ITEMS } from '../core/authz/permissions.js';
import { navigate } from '../core/router/next.js';
import { shared } from '../design-system/styles.js';

interface Item { label: string; hint?: string; path: string }

/** ⌘K / Ctrl-K: jump to a lead by number, name or phone, or to a page. Permission-filtered (09 §3.2). */
export class VsCommandPalette extends LitElement {
  static override properties = { open: { state: true }, results: { state: true }, perms: { attribute: false } };
  declare open: boolean;
  declare results: Item[];
  declare perms: PermissionMap;
  private seq = 0;
  private onKey = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      this.show();
    }
  };
  static override styles = [
    ...shared,
    css`
      ul { list-style: none; margin: 0; padding: 0; max-height: 50vh; overflow-y: auto; }
      li button { width: 100%; text-align: left; background: none; border: 0; padding: 10px 12px; min-height: 44px; cursor: pointer; font: inherit; color: var(--vs-ink); border-radius: 4px; }
      li button:hover, li button:focus-visible { background: var(--vs-cream); }
    `,
  ];
  constructor() {
    super();
    this.open = false;
    this.results = [];
    this.perms = {};
  }
  override connectedCallback() {
    super.connectedCallback();
    window.addEventListener('keydown', this.onKey);
  }
  override disconnectedCallback() {
    window.removeEventListener('keydown', this.onKey);
    super.disconnectedCallback();
  }
  show() {
    this.open = true;
    this.results = this.pages('');
    this.updateComplete.then(() => (this.renderRoot.querySelector('input') as HTMLInputElement | null)?.focus());
  }
  private pages(q: string): Item[] {
    const items: Item[] = filterNav(NAV_ITEMS, this.perms).map((n) => ({ label: n.label, hint: 'Page', path: n.path }));
    if (has(this.perms, 'lead.create')) items.push({ label: 'New lead', hint: 'Action', path: '/leads?new=1' });
    return items.filter((i) => i.label.toLowerCase().includes(q.toLowerCase()));
  }
  private async search(q: string) {
    const seq = ++this.seq;
    const pages = this.pages(q);
    if (q.trim().length < 2 || !has(this.perms, 'lead.read')) {
      this.results = pages;
      return;
    }
    try {
      const r = await api.get<Lead[]>('/api/v1/leads', { q, page_size: 8 });
      if (seq !== this.seq) return;
      this.results = [...r.data.map((l) => ({ label: l.name, hint: l.lead_number, path: `/leads/${l.id}` })), ...pages];
    } catch {
      this.results = pages;
    }
  }
  private go(path: string) {
    this.open = false;
    navigate(path);
  }
  override render() {
    return html`<vs-dialog .open=${this.open} heading="Jump to" @close=${() => (this.open = false)}>
      <label class="field"><span class="sr-only">Search leads and pages</span>
        <input type="search" placeholder="Lead name, phone, VS-L-… or a page" @input=${(e: Event) => this.search((e.target as HTMLInputElement).value)} />
      </label>
      <ul role="listbox" aria-label="Results">${this.results.map(
        (r) => html`<li role="option"><button @click=${() => this.go(r.path)}>${r.label}${r.hint ? html` <span class="small muted">· ${r.hint}</span>` : nothing}</button></li>`,
      )}</ul>
    </vs-dialog>`;
  }
}
customElements.define('vs-command-palette', VsCommandPalette);
