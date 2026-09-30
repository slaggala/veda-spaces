import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { OffsetMeta, Role, UserListItem } from '../../core/api/types.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatRelative, humanize, initials } from '../../core/format/format.js';
import { toast } from '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { isFounderGoverned, loadRoles, MFA_LABEL } from './common.js';
import './user-drawer.js';

/** User management (09 §4.6, UI-006). */
export class VsUsersPage extends SessionElement {
  static override properties = {
    users: { state: true }, meta: { state: true }, problem: { state: true }, loading: { state: true }, roles: { state: true },
    q: { state: true }, status: { state: true }, roleId: { state: true }, showDeleted: { state: true }, page: { state: true },
    selected: { state: true }, inviteOpen: { state: true }, inviteProblem: { state: true },
  };
  declare users: UserListItem[];
  declare meta: OffsetMeta | null;
  declare problem: ApiProblem | null;
  declare loading: boolean;
  declare roles: Role[];
  declare q: string;
  declare status: string;
  declare roleId: string;
  declare showDeleted: boolean;
  declare page: number;
  declare selected: string | null;
  declare inviteOpen: boolean;
  declare inviteProblem: ApiProblem | null;
  private timer: number | undefined;
  static override styles = [...shared, pageStyles, tableStyles, css`.avatar { width: 32px; height: 32px; border-radius: 50%; background: var(--vs-cream); display: inline-flex; align-items: center; justify-content: center; font: 700 11px var(--vs-font-sans); margin-right: 8px; } .user { display: flex; align-items: center; } .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; } fieldset { border: 0; padding: 0; margin: 0; }`];

  constructor() {
    super();
    this.users = [];
    this.meta = null;
    this.problem = null;
    this.loading = true;
    this.roles = [];
    this.q = '';
    this.status = '';
    this.roleId = '';
    this.showDeleted = false;
    this.page = 1;
    this.selected = new URLSearchParams(window.location.search).get('user');
    this.inviteOpen = false;
    this.inviteProblem = null;
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
    if (this.can('role.read')) void loadRoles().then((r) => (this.roles = r)).catch(() => undefined);
  }

  private async load() {
    this.loading = true;
    try {
      const r = await api.get<UserListItem[]>('/api/v1/users', {
        q: this.q || undefined, status: this.status || undefined, role_id: this.roleId || undefined,
        include_deleted: this.showDeleted ? 'true' : undefined, page: this.page, page_size: 25,
      });
      this.users = r.data;
      this.meta = r.meta as unknown as OffsetMeta;
      this.problem = null;
    } catch (e) {
      this.problem = e as ApiProblem;
    } finally {
      this.loading = false;
    }
  }

  private async invite(e: Event) {
    e.preventDefault();
    const f = e.target as HTMLFormElement;
    const v = (n: string) => ((f.elements.namedItem(n) as HTMLInputElement | null)?.value ?? '').trim();
    const roleIds = Array.from(f.querySelectorAll<HTMLInputElement>('input[name="role_ids"]:checked')).map((i) => i.value);
    this.inviteProblem = null;
    try {
      await api.post('/api/v1/users', {
        email: v('email'), full_name: v('full_name'), phone: v('phone') || undefined, timezone: v('timezone') || undefined,
        ...(roleIds.length ? { role_ids: roleIds } : {}),
      });
      toast('Invitation sent', 'success');
      this.inviteOpen = false;
      f.reset();
      void this.load();
    } catch (err) {
      this.inviteProblem = err as ApiProblem;
    }
  }

  override render() {
    const assignable = this.roles.filter((r) => r.is_assignable && !isFounderGoverned(r));
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Admin</p><h1 class="display">Users</h1></div><span class="spacer"></span>
        <vs-can permission="user.create"><button class="btn primary" @click=${() => (this.inviteOpen = true)}>+ Invite user</button></vs-can></div>
      <div class="filters" role="search">
        <label class="field"><span class="label">Search</span><input type="search" placeholder="Name or email" @input=${(e: Event) => {
          this.q = (e.target as HTMLInputElement).value;
          window.clearTimeout(this.timer);
          this.timer = window.setTimeout(() => { this.page = 1; void this.load(); }, 300);
        }} /></label>
        <label class="field"><span class="label">Status</span><select @change=${(e: Event) => { this.status = (e.target as HTMLSelectElement).value; this.page = 1; void this.load(); }}>
          <option value="">Any</option>${['ACTIVE', 'INVITED', 'LOCKED', 'DISABLED'].map((s) => html`<option value=${s}>${humanize(s)}</option>`)}</select></label>
        ${this.roles.length ? html`<label class="field"><span class="label">Role</span><select @change=${(e: Event) => { this.roleId = (e.target as HTMLSelectElement).value; this.page = 1; void this.load(); }}>
          <option value="">Any</option>${this.roles.map((r) => html`<option value=${r.id}>${r.name}</option>`)}</select></label>` : nothing}
        ${this.can('user.restore') ? html`<label class="check"><input type="checkbox" @change=${(e: Event) => { this.showDeleted = (e.target as HTMLInputElement).checked; void this.load(); }} /> Show deleted</label>` : nothing}
      </div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${this.loading && !this.users.length ? html`<div class="card"><vs-skeleton rows="6"></vs-skeleton></div>` : html`<div class="table-wrap"><table class="cards">
        <thead><tr><th>User</th><th>Roles</th><th>Status</th><th>Last sign-in</th><th>MFA</th></tr></thead>
        <tbody>${this.users.map((u) => html`<tr class="clickable" tabindex="0" @click=${() => (this.selected = u.id)} @keydown=${(e: KeyboardEvent) => e.key === 'Enter' && (this.selected = u.id)}>
          <td data-label="User"><div class="user"><span class="avatar" aria-hidden="true">${initials(u.full_name)}</span><div>
            <div class="strong">${u.full_name}${u.protection_level === 'FOUNDER' ? html` <span title="Founder-protected account" aria-label="Founder-protected">★</span>` : nothing}${u.id === this.me?.id ? html` <span class="chip">You</span>` : nothing}</div>
            <div class="small muted">${u.email}${u.email_change_pending ? ' · email change pending' : ''}</div></div></div></td>
          <td data-label="Roles">${u.roles.map((r) => r.name).join(', ') || '—'}</td>
          <td data-label="Status">${u.is_deleted ? html`<span class="chip danger">Deleted</span>` : html`<span class="chip ${u.status === 'ACTIVE' ? 'success' : u.status === 'LOCKED' ? 'warning' : ''}">${humanize(u.status)}</span>`}</td>
          <td data-label="Last sign-in">${u.last_login_on ? formatRelative(u.last_login_on) : '—'}</td>
          <td data-label="MFA"><span class=${u.mfa.required && !u.mfa.enrolled ? 'warning-text' : ''}>${MFA_LABEL(u.mfa)}</span>${u.is_privileged ? html` <span class="small muted">· privileged</span>` : nothing}</td>
        </tr>`)}</tbody></table></div>
        ${this.meta ? html`<vs-pagination .page=${this.meta.page} .totalPages=${this.meta.total_pages} .total=${this.meta.total} .pageSize=${this.meta.page_size}
          @page-change=${(e: CustomEvent<number>) => { this.page = e.detail; void this.load(); }}></vs-pagination>` : nothing}`}
      <vs-user-drawer .userId=${this.selected} .roles=${this.roles} @close=${() => (this.selected = null)} @user-changed=${() => void this.load()}></vs-user-drawer>
      <vs-drawer .open=${this.inviteOpen} heading="Invite user" @close=${() => (this.inviteOpen = false)}>
        <form id="inv" class="stack" @submit=${this.invite} novalidate>
          <p class="muted">We'll email an invitation link. It expires in 72 hours, or 24 hours if the roles include sensitive permissions.</p>
          <label class="field"><span class="label">Email *</span><input name="email" type="email" required autocomplete="off" /></label>
          <label class="field"><span class="label">Full name *</span><input name="full_name" required maxlength="150" /></label>
          <div class="grid-2"><label class="field"><span class="label">Phone</span><input name="phone" type="tel" /></label>
            <label class="field"><span class="label">Timezone</span><input name="timezone" value="Asia/Kolkata" /></label></div>
          ${this.can('user.role.manage') && assignable.length ? html`<fieldset class="field"><legend class="label">Roles</legend>
            ${assignable.map((r) => html`<label class="check"><input type="checkbox" name="role_ids" value=${r.id} /> ${r.name}${r.description ? html` <span class="small muted">· ${r.description}</span>` : nothing}</label>`)}</fieldset>` : nothing}
          <vs-problem-banner .problem=${this.inviteProblem}></vs-problem-banner>
        </form>
        <div slot="actions"><button class="btn" @click=${() => (this.inviteOpen = false)}>Cancel</button><button class="btn primary" form="inv">Send invite</button></div>
      </vs-drawer>
    </div>`;
  }
}
customElements.define('vs-users-page', VsUsersPage);
