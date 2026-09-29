import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { Permission, Scope } from '../../core/api/types.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { toast } from '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { loadPermissions } from './common.js';

interface Holder { user: { id: string; display_name: string }; scope: Scope; sources?: Array<{ type: string; role_code?: string }>; via?: string }

/** Permission catalog (09 §4.8). Codes and sensitivity are defined in code; only name/description are editable. */
export class VsPermissionsPage extends SessionElement {
  static override properties = { catalog: { state: true }, problem: { state: true }, q: { state: true }, module: { state: true }, sensitiveOnly: { state: true }, selected: { state: true }, holders: { state: true } };
  declare catalog: Permission[];
  declare problem: ApiProblem | null;
  declare q: string;
  declare module: string;
  declare sensitiveOnly: boolean;
  declare selected: Permission | null;
  declare holders: Holder[] | null;
  static override styles = [...shared, pageStyles, tableStyles, css`.filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end; }`];

  constructor() {
    super();
    this.catalog = [];
    this.problem = null;
    this.q = '';
    this.module = '';
    this.sensitiveOnly = false;
    this.selected = null;
    this.holders = null;
  }
  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }
  private async load() {
    try {
      this.catalog = await loadPermissions();
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }
  private async open(p: Permission) {
    this.selected = p;
    this.holders = null;
    if (this.can('user.read')) {
      try {
        this.holders = (await api.get<Holder[]>(`/api/v1/permissions/${p.id}/holders`)).data;
      } catch {
        this.holders = [];
      }
    }
  }
  private async save(e: Event) {
    e.preventDefault();
    const p = this.selected!;
    const f = e.target as HTMLFormElement;
    const v = (n: string) => (f.elements.namedItem(n) as HTMLInputElement).value.trim();
    try {
      const r = await api.patch<Permission>(`/api/v1/permissions/${p.id}`, { name: v('name'), description: v('description') || null }, { ifMatch: p.version });
      toast('Permission saved', 'success');
      this.selected = r.data;
      await this.load();
    } catch (err) {
      this.problem = err as ApiProblem;
    }
  }
  override render() {
    const q = this.q.toLowerCase();
    const rows = this.catalog.filter((p) => (!q || p.code.includes(q) || p.name.toLowerCase().includes(q)) && (!this.module || p.module === this.module) && (!this.sensitiveOnly || p.is_sensitive));
    const modules = Array.from(new Set(this.catalog.map((p) => p.module)));
    const p = this.selected;
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Admin</p><h1 class="display">Permissions</h1></div><span class="spacer"></span>
        <p class="muted small">Permissions are defined by the platform. You can edit descriptions and see who has access.</p></div>
      <div class="filters" role="search">
        <label class="field"><span class="label">Search</span><input type="search" @input=${(e: Event) => (this.q = (e.target as HTMLInputElement).value)} /></label>
        <label class="field"><span class="label">Module</span><select @change=${(e: Event) => (this.module = (e.target as HTMLSelectElement).value)}><option value="">All</option>${modules.map((m) => html`<option>${m}</option>`)}</select></label>
        <label class="check"><input type="checkbox" @change=${(e: Event) => (this.sensitiveOnly = (e.target as HTMLInputElement).checked)} /> Sensitive only</label>
      </div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      <div class="table-wrap"><table class="cards"><thead><tr><th>Permission</th><th>Code</th><th>Scope</th><th>Roles</th><th>Req</th></tr></thead>
        <tbody>${rows.map((row) => html`<tr class="clickable" tabindex="0" @click=${() => this.open(row)} @keydown=${(e: KeyboardEvent) => e.key === 'Enter' && this.open(row)}>
          <td data-label="Permission">${row.name}${row.is_sensitive ? html` <span title=${row.sensitivity_class ?? 'Sensitive'}>🔒</span>` : nothing}</td>
          <td data-label="Code" class="mono">${row.code}</td><td data-label="Scope">${row.supports_scope ? 'Yes' : '—'}</td>
          <td data-label="Roles">${(row.granted_to_roles ?? []).map((r) => `${r.code.charAt(0)}${r.scope === 'OWN' ? '(own)' : ''}`).join(' · ') || '—'}</td>
          <td data-label="Req" class="mono">${row.requirement_ref ?? ''}</td></tr>`)}</tbody></table></div>
      <vs-drawer .open=${Boolean(p)} heading=${p?.name ?? ''} @close=${() => (this.selected = null)}>
        ${p ? html`<p class="mono">${p.code}</p>
          ${p.is_sensitive ? html`<vs-banner kind="warning">Sensitive (${p.sensitivity_class}). Holding it makes MFA mandatory, and it is only effective in MFA-verified sessions.</vs-banner>` : nothing}
          ${this.can('permission.manage') ? html`<form class="stack" @submit=${this.save}>
              <label class="field"><span class="label">Name</span><input name="name" .value=${p.name} maxlength="120" /></label>
              <label class="field"><span class="label">Description</span><textarea name="description" maxlength="500" .value=${p.description ?? ''}></textarea></label>
              <div class="row"><span class="spacer"></span><button class="btn primary">Save</button></div></form>`
            : html`<p>${p.description ?? ''}</p>`}
          <h3 class="eyebrow">Granted to roles</h3>
          <ul>${(p.granted_to_roles ?? []).map((r) => html`<li>${r.code} · ${r.scope}</li>`)}</ul>
          ${this.can('user.read') ? html`<h3 class="eyebrow">Effective holders</h3>${!this.holders ? html`<vs-skeleton rows="3"></vs-skeleton>` : this.holders.length
            ? html`<ul>${this.holders.map((h) => html`<li>${h.user?.display_name} · ${h.scope}${h.sources ? ` · via ${h.sources.map((s) => s.role_code ?? s.type).join(', ')}` : h.via ? ` · via ${h.via}` : ''}</li>`)}</ul>`
            : html`<p class="muted">No holders.</p>`}` : nothing}` : nothing}
      </vs-drawer>
    </div>`;
  }
}
customElements.define('vs-permissions-page', VsPermissionsPage);
