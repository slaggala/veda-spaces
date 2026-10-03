import { LitElement, css, html, nothing } from 'lit';
import { api } from '../core/api/client.js';
import type { Lead, PermissionMap } from '../core/api/types.js';
import { filterNav, has, NAV_ITEMS } from '../core/authz/permissions.js';
import { navigate } from '../core/router/next.js';
import { shared } from '../design-system/styles.js';

interface Item { label: string; hint?: string; path: string }

/** ⌘K / Ctrl-K: jump to a lead by number, name or phone, or to a page. Permission-filtered (09 §3.2). */
export class VsCommandPalette extends LitElement {
  static override properties = { open: { state: true }, results: { state: true }, active: { state: true }, perms: { attribute: false } };
  declare open: boolean;
  declare results: Item[];
  /** Index of the highlighted option (aria-activedescendant); -1 when there are no results. */
  declare active: number;
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
      li { display: flex; align-items: center; gap: 4px; padding: 10px 12px; min-height: 44px; box-sizing: border-box; cursor: pointer; color: var(--vs-ink); border-radius: 4px; }
      li:hover, li[aria-selected='true'] { background: var(--vs-cream); }
      li[aria-selected='true'] { outline: 2px solid var(--vs-focus-ring); outline-offset: -2px; }
    `,
  ];
  constructor() {
    super();
    this.open = false;
    this.results = [];
    this.active = -1;
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
    this.setResults(this.pages(''));
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
      this.setResults(pages);
      return;
    }
    try {
      const r = await api.get<Lead[]>('/api/v1/leads', { q, page_size: 8 });
      if (seq !== this.seq) return;
      this.setResults([...r.data.map((l) => ({ label: l.name, hint: l.lead_number, path: `/leads/${l.id}` })), ...pages]);
    } catch {
      this.setResults(pages);
    }
  }
  private setResults(items: Item[]) {
    this.results = items;
    this.active = items.length ? 0 : -1;
  }
  private go(path: string) {
    this.open = false;
    navigate(path);
  }
  /** Combobox keys (WAI-ARIA combobox with listbox popup; RR-18): focus stays in the input. */
  private onInputKey(e: KeyboardEvent) {
    const n = this.results.length;
    if (!n) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      this.active = e.key === 'ArrowDown' ? (this.active + 1) % n : (this.active - 1 + n) % n;
      this.updateComplete.then(() => this.renderRoot.querySelector(`#opt-${this.active}`)?.scrollIntoView({ block: 'nearest' }));
    } else if (e.key === 'Enter' && this.active >= 0) {
      e.preventDefault();
      this.go(this.results[this.active].path);
    }
  }
  override render() {
    const n = this.results.length;
    return html`<vs-dialog .open=${this.open} heading="Jump to" @close=${() => (this.open = false)}>
      <label class="field"><span class="sr-only">Search leads and pages</span>
        <input type="search" role="combobox" aria-autocomplete="list" aria-controls="results" aria-expanded=${n ? 'true' : 'false'}
          aria-activedescendant=${this.active >= 0 ? `opt-${this.active}` : nothing} autocomplete="off"
          placeholder="Lead name, phone, VS-L-… or a page" @keydown=${this.onInputKey}
          @input=${(e: Event) => this.search((e.target as HTMLInputElement).value)} />
      </label>
      <ul id="results" role="listbox" aria-label="Results">${this.results.map(
        (r, i) => html`<li id="opt-${i}" role="option" aria-selected=${i === this.active ? 'true' : 'false'}
          @pointermove=${() => (this.active = i)} @click=${() => this.go(r.path)}>${r.label}${r.hint ? html` <span class="small muted">· ${r.hint}</span>` : nothing}</li>`,
      )}</ul>
      <p class="sr-only" role="status">${this.open ? (n === 1 ? '1 result' : `${n} results`) : ''}</p>
    </vs-dialog>`;
  }
}
customElements.define('vs-command-palette', VsCommandPalette);
