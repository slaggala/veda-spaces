import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { Permission, Role, RoleGrant, Scope, UserListItem } from '../../core/api/types.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { toast } from '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { FOUNDER_ONLY, isFounderGoverned, loadPermissions, loadRoles } from './common.js';

type Staged = Map<string, Scope | null>;

/** Role management with the staged permission matrix (09 §4.7, UI-007). */
export class VsRolesPage extends SessionElement {
  static override properties = {
    roles: { state: true }, catalog: { state: true }, selectedId: { state: true }, grants: { state: true }, staged: { state: true },
    problem: { state: true }, filter: { state: true }, module: { state: true }, onlyGranted: { state: true }, createOpen: { state: true },
    users: { state: true }, busy: { state: true }, editOpen: { state: true },
  };
  declare roles: Role[];
  declare catalog: Permission[];
  declare selectedId: string;
  declare grants: Map<string, Scope>;
  declare staged: Staged;
  declare problem: ApiProblem | null;
  declare filter: string;
  declare module: string;
  declare onlyGranted: boolean;
  declare createOpen: boolean;
  declare users: UserListItem[] | null;
  declare busy: boolean;
  declare editOpen: boolean;
  static override styles = [
    ...shared, pageStyles, tableStyles,
    css`
      .layout { display: grid; grid-template-columns: 240px 1fr; gap: 16px; align-items: start; }
      .list { list-style: none; margin: 0; padding: 0; background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: 8px; }
      .list button { display: flex; width: 100%; gap: 8px; align-items: center; min-height: 44px; padding: 0 12px; background: none; border: 0; border-bottom: 1px solid var(--vs-line); text-align: left; font: inherit; color: var(--vs-ink); cursor: pointer; }
      .list button[aria-current='true'] { background: var(--vs-cream); font-weight: 600; }
      .group td { background: var(--vs-cream); font: 600 11px/16px var(--vs-font-sans); letter-spacing: .14em; text-transform: uppercase; color: var(--vs-ink-muted); }
      .changed { background: var(--vs-cream); }
      .scope { display: inline-flex; gap: 8px; }
      .scope label { display: inline-flex; gap: 4px; align-items: center; font-size: 13px; }
      .savebar { position: sticky; bottom: 0; background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: 8px; padding: 12px 16px; display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; box-shadow: var(--vs-shadow); }
      @media (max-width: 1023px) { .layout { grid-template-columns: 1fr; } }
    `,
  ];

  constructor() {
    super();
    this.roles = [];
    this.catalog = [];
    this.selectedId = '';
    this.grants = new Map();
    this.staged = new Map();
    this.problem = null;
    this.filter = '';
    this.module = '';
    this.onlyGranted = false;
    this.createOpen = false;
    this.users = null;
    this.busy = false;
    this.editOpen = false;
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.init();
  }

  private async init() {
    try {
      const [roles, catalog] = await Promise.all([loadRoles(), loadPermissions()]);
      this.roles = roles;
      this.catalog = catalog;
      if (!this.selectedId && roles.length) await this.select(roles[0].id);
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  private get currentRole(): Role | undefined {
    return this.roles.find((r) => r.id === this.selectedId);
  }

  private async select(id: string) {
    if (this.staged.size && !confirm('Discard unsaved changes?')) return;
    this.selectedId = id;
    this.staged = new Map();
    this.users = null;
    try {
      const r = await api.get<RoleGrant[]>(`/api/v1/roles/${id}/permissions`);
      this.grants = new Map(r.data.map((g) => [g.permission_code, g.scope]));
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  private effective(code: string): Scope | null {
    return this.staged.has(code) ? this.staged.get(code)! : this.grants.get(code) ?? null;
  }

  private stage(code: string, scope: Scope | null) {
    const next = new Map(this.staged);
    if ((this.grants.get(code) ?? null) === scope) next.delete(code);
    else next.set(code, scope);
    this.staged = next;
  }

  private async save() {
    const role = this.currentRole;
    if (!role) return;
    const reason = ((this.renderRoot.querySelector('#reason') as HTMLInputElement | null)?.value ?? '').trim();
    if (!reason) return void toast('A reason is required', 'error');
    const permissions: RoleGrant[] = [];
    for (const p of this.catalog) {
      const s = this.effective(p.code);
      if (s) permissions.push({ permission_code: p.code, scope: p.supports_scope ? s : 'ALL' });
    }
    this.busy = true;
    try {
      const r = await api.put(`/api/v1/roles/${role.id}/permissions`, { permissions, reason }, { ifMatch: role.version });
      const d = r.meta as { added?: number; removed?: number; changed?: number };
      toast(d.added !== undefined ? `Saved: ${d.added} added, ${d.removed ?? 0} removed, ${d.changed ?? 0} changed` : 'Role permissions saved', 'success');
      this.staged = new Map();
      this.roles = await loadRoles();
      await this.select(role.id);
    } catch (e) {
      this.problem = e as ApiProblem;
    } finally {
      this.busy = false;
    }
  }

  private async create(e: Event) {
    e.preventDefault();
    const f = e.target as HTMLFormElement;
    const v = (n: string) => (f.elements.namedItem(n) as HTMLInputElement).value.trim();
    try {
      const r = await api.post<Role>('/api/v1/roles', { code: v('code'), name: v('name'), description: v('description') || undefined, ...(v('copy_from_role_id') ? { copy_from_role_id: v('copy_from_role_id') } : {}) });
      this.createOpen = false;
      this.roles = await loadRoles();
      await this.select(r.data.id);
      toast('Role created', 'success');
    } catch (err) {
      this.problem = err as ApiProblem;
    }
  }

  private async saveMeta(e: Event) {
    e.preventDefault();
    const role = this.currentRole!;
    const f = e.target as HTMLFormElement;
    const v = (n: string) => (f.elements.namedItem(n) as HTMLInputElement).value.trim();
    try {
      await api.patch(`/api/v1/roles/${role.id}`, { name: v('name'), description: v('description') || null, is_assignable: (f.elements.namedItem('is_assignable') as HTMLInputElement).checked }, { ifMatch: role.version });
      this.editOpen = false;
      this.roles = await loadRoles();
      toast('Role saved', 'success');
    } catch (err) {
      this.problem = err as ApiProblem;
    }
  }

  private async removeRole() {
    const role = this.currentRole!;
    if (!confirm(`Delete role ${role.name}?`)) return;
    try {
      await api.delete(`/api/v1/roles/${role.id}`, { ifMatch: role.version });
      this.roles = await loadRoles();
      this.selectedId = '';
      if (this.roles.length) await this.select(this.roles[0].id);
      toast('Role deleted', 'success');
    } catch (err) {
      this.problem = err as ApiProblem;
    }
  }

  private async loadUsers() {
    try {
      this.users = (await api.get<UserListItem[]>(`/api/v1/roles/${this.selectedId}/users`)).data;
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  private renderMatrix(role: Role) {
    const locked = isFounderGoverned(role) || !this.can('role.manage');
    const q = this.filter.toLowerCase();
    const rows = this.catalog.filter((p) =>
      (!q || p.code.includes(q) || p.name.toLowerCase().includes(q)) && (!this.module || p.module === this.module) && (!this.onlyGranted || this.effective(p.code)));
    const groups = new Map<string, Permission[]>();
    for (const p of rows) {
      const key = `${p.module} › ${p.resource}`;
      groups.set(key, [...(groups.get(key) ?? []), p]);
    }
    return html`<div class="table-wrap"><table>
      <thead><tr><th>Permission</th><th>Grant</th><th>Scope</th></tr></thead>
      <tbody>${Array.from(groups.entries()).map(([g, perms]) => html`<tr class="group"><td colspan="3">${g}</td></tr>
        ${perms.map((p) => {
          const scope = this.effective(p.code);
          const founderOnly = p.grant_path === FOUNDER_ONLY;
          const notHeld = !this.can(p.code);
          const disabled = locked || founderOnly || notHeld;
          const why = founderOnly ? 'Founder governance only' : notHeld ? "Includes permissions you don't have" : '';
          return html`<tr class=${this.staged.has(p.code) ? 'changed' : ''}>
            <td><div>${p.name}${p.is_sensitive ? html` <span title=${`Sensitive: ${p.sensitivity_class ?? ''}`}>🔒</span>` : nothing}</div><div class="mono muted">${p.code}</div>${why && !locked ? html`<div class="small muted">${why}</div>` : nothing}</td>
            <td><input type="checkbox" aria-label=${`Grant ${p.code}`} .checked=${Boolean(scope)} ?disabled=${disabled} title=${why}
              @change=${(e: Event) => this.stage(p.code, (e.target as HTMLInputElement).checked ? (p.supports_scope ? 'OWN' : 'ALL') : null)} /></td>
            <td>${p.supports_scope && scope ? html`<div class="scope" role="radiogroup" aria-label=${`Scope for ${p.code}`}>
              ${(['ALL', 'OWN'] as Scope[]).map((s) => html`<label><input type="radio" name=${`s-${p.code}`} .checked=${scope === s} ?disabled=${disabled} @change=${() => this.stage(p.code, s)} />${s === 'ALL' ? 'All' : 'Own'}</label>`)}
              <label title="Available when teams are introduced"><input type="radio" disabled />Team ⊘</label></div>` : html`<span class="muted">—</span>`}</td></tr>`;
        })}`)}</tbody></table></div>`;
  }

  override render() {
    const role = this.currentRole;
    const modules = Array.from(new Set(this.catalog.map((p) => p.module)));
    const diffs = Array.from(this.staged.entries()).map(([code, scope]) => {
      const before = this.grants.get(code);
      return !before ? `+ ${code}${scope ? ` (${scope === 'ALL' ? 'All' : 'Own'})` : ''}` : !scope ? `− ${code}` : `${code} ${before} → ${scope}`;
    });
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Admin</p><h1 class="display">Roles</h1></div></div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      <div class="layout">
        <nav aria-label="Roles"><div class="row"><span class="spacer"></span><vs-can permission="role.manage"><button class="btn small" @click=${() => (this.createOpen = true)}>+ New</button></vs-can></div>
          <ul class="list">${this.roles.map((r) => html`<li><button aria-current=${r.id === this.selectedId ? 'true' : 'false'} @click=${() => this.select(r.id)}>
            ${r.name} <span class="small muted">(${r.user_count})</span><span class="spacer"></span>${r.is_system ? html`<span class="small muted">SYS</span>` : nothing}</button></li>`)}</ul></nav>
        ${role ? html`<section class="stack">
          <div class="row"><h2 class="title">${role.name}</h2>${role.is_system ? html`<span class="chip">System role</span>` : nothing}
            ${isFounderGoverned(role) ? html`<span class="chip">🔒 Founder governance only</span>` : nothing}<span class="spacer"></span>
            ${this.can('role.manage') && !isFounderGoverned(role) ? html`<button class="btn small" @click=${() => (this.editOpen = true)}>Edit</button>
              ${!role.is_system ? html`<button class="btn small danger" @click=${this.removeRole}>Delete</button>` : nothing}` : nothing}</div>
          <p class="muted">${role.description ?? ''} · ${role.user_count} users ${this.can('user.read') ? html`<button class="btn ghost small" @click=${this.loadUsers}>View users</button>` : nothing}
            ${role.mfa_required ? ' · MFA required' : ''}</p>
          ${this.users ? html`<p class="small">${this.users.map((u) => u.full_name).join(', ') || 'No users'}</p>` : nothing}
          ${isFounderGoverned(role) ? html`<vs-banner kind="info">The Founder role changes only by reviewed migration. Founder status is granted or revoked through <a href="/admin/founder-actions">Founder actions</a>.</vs-banner>` : nothing}
          <div class="row">
            <label class="field"><span class="label">Filter</span><input type="search" @input=${(e: Event) => (this.filter = (e.target as HTMLInputElement).value)} /></label>
            <label class="field"><span class="label">Module</span><select @change=${(e: Event) => (this.module = (e.target as HTMLSelectElement).value)}><option value="">All</option>${modules.map((m) => html`<option>${m}</option>`)}</select></label>
            <label class="check"><input type="checkbox" @change=${(e: Event) => (this.onlyGranted = (e.target as HTMLInputElement).checked)} /> Show only granted</label>
          </div>
          ${this.renderMatrix(role)}
          ${this.staged.size ? html`<div class="savebar" role="region" aria-label="Unsaved changes">
            <div class="spacer"><strong>${this.staged.size} unsaved change${this.staged.size === 1 ? '' : 's'}:</strong> <span class="small">${diffs.join(', ')}</span></div>
            <label class="field"><span class="label">Reason *</span><input id="reason" maxlength="500" /></label>
            <button class="btn" @click=${() => (this.staged = new Map())}>Discard</button><button class="btn primary" ?disabled=${this.busy} @click=${this.save}>Save changes</button></div>` : nothing}
        </section>` : html`<vs-skeleton rows="8"></vs-skeleton>`}
      </div>
      <vs-dialog .open=${this.createOpen} heading="New role" @close=${() => (this.createOpen = false)}>
        <form id="rf" class="stack" @submit=${this.create}>
          <label class="field"><span class="label">Code *</span><input name="code" pattern="^[A-Z][A-Z0-9_]{1,49}$" placeholder="SALES_MANAGER" required /><span class="hint">Uppercase letters, digits and underscores. Can't be changed later.</span></label>
          <label class="field"><span class="label">Name *</span><input name="name" maxlength="100" required /></label>
          <label class="field"><span class="label">Description</span><input name="description" maxlength="500" /></label>
          <label class="field"><span class="label">Copy permissions from</span><select name="copy_from_role_id"><option value="">Start empty</option>
            ${this.roles.filter((r) => !isFounderGoverned(r)).map((r) => html`<option value=${r.id}>${r.name}</option>`)}</select></label>
        </form>
        <div slot="actions"><button class="btn" @click=${() => (this.createOpen = false)}>Cancel</button><button class="btn primary" form="rf">Create role</button></div>
      </vs-dialog>
      <vs-dialog .open=${this.editOpen} heading="Edit role" @close=${() => (this.editOpen = false)}>
        ${role ? html`<form id="ef" class="stack" @submit=${this.saveMeta}>
          <p class="mono">${role.code}</p>
          <label class="field"><span class="label">Name</span><input name="name" .value=${role.name} maxlength="100" /></label>
          <label class="field"><span class="label">Description</span><input name="description" .value=${role.description ?? ''} maxlength="500" /></label>
          <label class="check"><input type="checkbox" name="is_assignable" .checked=${role.is_assignable} /> Assignable to users</label>
        </form>` : nothing}
        <div slot="actions"><button class="btn" @click=${() => (this.editOpen = false)}>Cancel</button><button class="btn primary" form="ef">Save</button></div>
      </vs-dialog>
    </div>`;
  }
}
customElements.define('vs-roles-page', VsRolesPage);
