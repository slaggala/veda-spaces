import { css, html, nothing, type PropertyValues } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { DirectGrant, EffectivePermission, Permission, Role, UserDetail } from '../../core/api/types.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatAbsolute, formatRelative, humanize } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import { toast } from '../../design-system/components.js';
import { shared, tableStyles } from '../../design-system/styles.js';
import { FOUNDER_ONLY, isFounderGoverned, loadPermissions, MFA_LABEL } from './common.js';

type Action = '' | 'email' | 'status' | 'mfa-reset' | 'mfa-require' | 'delete' | 'revoke' | 'roles' | 'grant';

const ERRORS: Record<string, string> = {
  SELF_MODIFICATION_DENIED: "You can't change your own account here. Use your Profile.",
  ESCALATION_DENIED: 'This account holds permissions you do not have.',
  FOUNDER_PROTECTED: 'Founder accounts use the Founder workflow.',
  FOUNDER_GOVERNANCE_REQUIRED: 'Founder status can only change through the Founder workflow.',
  LAST_FOUNDER: 'This is the last active Founder.',
  LAST_ADMINISTRATOR: 'This is the last recovery administrator. Give another person these permissions first.',
  REASON_REQUIRED: 'A reason is required.',
  TIME_BOUND_GRANTS_NOT_ENABLED: 'Time-bound grants are not available yet.',
  SCOPE_NOT_SUPPORTED: 'That scope is not available.',
};

/** User drawer: Profile / Access / Security / Sessions / Activity tabs (09 §4.6). */
export class VsUserDrawer extends SessionElement {
  static override properties = {
    userId: { attribute: false }, roles: { attribute: false }, user: { state: true }, tab: { state: true }, problem: { state: true },
    userRoles: { state: true }, grants: { state: true }, effective: { state: true }, catalog: { state: true }, action: { state: true }, busy: { state: true },
    statusTarget: { state: true }, mfaRequireTarget: { state: true }, actionProblem: { state: true },
  };
  declare userId: string | null;
  declare roles: Role[];
  declare user: UserDetail | null;
  declare tab: string;
  declare problem: ApiProblem | null;
  declare userRoles: Array<{ role_id?: string; id?: string; role?: { id: string; code: string; name: string }; code?: string; name?: string; created_on?: string }> | null;
  declare grants: DirectGrant[] | null;
  declare effective: { authz_version: number; mfa: { enrolled: boolean; required: boolean; required_by: string[] }; permissions: EffectivePermission[] } | null;
  declare catalog: Permission[];
  declare action: Action;
  declare busy: boolean;
  declare statusTarget: 'ACTIVE' | 'DISABLED';
  declare mfaRequireTarget: boolean;
  declare actionProblem: ApiProblem | null;
  static override styles = [...shared, tableStyles, css`dl { display: grid; grid-template-columns: 150px 1fr; gap: 6px 12px; margin: 0; } dt { color: var(--vs-ink-muted); } dd { margin: 0; } section { display: flex; flex-direction: column; gap: 10px; padding: 12px 0; border-bottom: 1px solid var(--vs-line); } .locked { color: var(--vs-ink-muted); font-size: 12px; }`];

  constructor() {
    super();
    this.userId = null;
    this.roles = [];
    this.user = null;
    this.tab = 'profile';
    this.problem = null;
    this.userRoles = null;
    this.grants = null;
    this.effective = null;
    this.catalog = [];
    this.action = '';
    this.busy = false;
    this.statusTarget = 'DISABLED';
    this.mfaRequireTarget = false;
    this.actionProblem = null;
  }

  protected override willUpdate(changed: PropertyValues<this>) {
    if (changed.has('userId') && this.userId) {
      this.tab = 'profile';
      this.user = null;
      this.userRoles = null;
      this.grants = null;
      this.effective = null;
      void this.load();
    }
  }

  private get isSelf(): boolean {
    return this.user?.id === this.me?.id;
  }
  private get isFounder(): boolean {
    return this.user?.protection_level === 'FOUNDER';
  }

  private async load() {
    try {
      this.user = (await api.get<UserDetail>(`/api/v1/users/${this.userId}`, { include_deleted: 'true' })).data;
      this.problem = null;
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  private async loadAccess() {
    const id = this.userId;
    const tasks: Array<Promise<unknown>> = [
      api.get<typeof this.userRoles>(`/api/v1/users/${id}/roles`).then((r) => (this.userRoles = r.data)),
      api.get<DirectGrant[]>(`/api/v1/users/${id}/permissions`).then((r) => (this.grants = r.data)),
    ];
    if (this.can('permission.read')) {
      tasks.push(api.get<NonNullable<typeof this.effective>>(`/api/v1/users/${id}/effective-permissions`).then((r) => (this.effective = r.data)));
      if (!this.catalog.length) tasks.push(loadPermissions().then((p) => (this.catalog = p)));
    }
    const res = await Promise.allSettled(tasks);
    const failed = res.find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined;
    if (failed) this.problem = failed.reason as ApiProblem;
  }

  private close() {
    this.dispatchEvent(new CustomEvent('close', { bubbles: true, composed: true }));
  }

  /** Run an account-control action; step-up is handled by the API client (G10). */
  private async run(label: string, fn: () => Promise<{ status: number; data: unknown }>) {
    this.busy = true;
    this.actionProblem = null;
    try {
      const r = await fn();
      const body = r.data as { status?: string } | undefined;
      if (r.status === 202 && body?.status === 'APPROVAL_REQUIRED') toast('Request created. Another administrator must approve it in Approvals.', 'success');
      else if (r.status === 202 && body?.status === 'VERIFICATION_SENT') toast('Verification sent to the new address; the current address was alerted.', 'success');
      else toast(label, 'success');
      this.action = '';
      await this.load();
      if (this.tab === 'access') await this.loadAccess();
      this.dispatchEvent(new CustomEvent('user-changed', { bubbles: true, composed: true }));
    } catch (e) {
      this.actionProblem = e as ApiProblem;
    } finally {
      this.busy = false;
    }
  }

  private formValue(id: string): string {
    return ((this.renderRoot.querySelector(`#${id}`) as HTMLInputElement | null)?.value ?? '').trim();
  }

  private renderProfile(u: UserDetail) {
    const editable = this.can('user.profile.update') && !this.isSelf && !u.is_deleted;
    return html`<dl>
        <dt>Email</dt><dd>${u.email} ${u.email_verified_on ? html`<span class="chip success">✓ verified</span>` : nothing}</dd>
        ${u.email_change ? html`<dt>Pending email</dt><dd>${u.email_change.proposed_email} (expires ${formatRelative(u.email_change.expires_on)})</dd>` : nothing}
        <dt>Status</dt><dd>${humanize(u.status)}${u.is_deleted ? ' · deleted' : ''}</dd>
        <dt>Protection</dt><dd>${u.protection_level === 'FOUNDER' ? '★ Founder' : 'Standard'}</dd>
        <dt>Last sign-in</dt><dd>${formatAbsolute(u.last_login_on)}</dd>
        <dt>Created</dt><dd>${formatAbsolute(u.created_on)}</dd>
      </dl>
      ${this.isSelf ? html`<p class="small muted">Edit your own details on your <a href="/profile">Profile</a>.</p>` : nothing}
      ${editable ? html`<form class="stack" @submit=${(e: Event) => {
        e.preventDefault();
        const f = e.target as HTMLFormElement;
        const v = (n: string) => (f.elements.namedItem(n) as HTMLInputElement).value.trim();
        void this.run('Profile saved', () => api.patch(`/api/v1/users/${u.id}`, {
          full_name: v('full_name'), display_name: v('display_name') || null, phone: v('phone') || null, timezone: v('timezone'), locale: v('locale'),
        }, { ifMatch: u.version }));
      }}>
        <div class="grid-2">
          <label class="field"><span class="label">Full name</span><input name="full_name" .value=${u.full_name} maxlength="150" /></label>
          <label class="field"><span class="label">Display name</span><input name="display_name" .value=${u.display_name ?? ''} maxlength="80" /></label>
          <label class="field"><span class="label">Phone</span><input name="phone" .value=${u.phone ?? ''} /></label>
          <label class="field"><span class="label">Timezone</span><input name="timezone" .value=${u.timezone} /></label>
          <label class="field"><span class="label">Locale</span><input name="locale" .value=${u.locale} /></label>
        </div>
        <div class="row"><span class="spacer"></span><button class="btn primary" ?disabled=${this.busy}>Save profile</button></div>
      </form>` : nothing}`;
  }

  private renderAccess(u: UserDetail) {
    if (this.isSelf) return html`<vs-banner kind="info">You can't change your own access.</vs-banner>${this.renderEffective()}`;
    const founderLocked = this.isFounder;
    const canRoles = this.can('user.role.manage') && !founderLocked && !u.is_deleted;
    const canGrant = this.can('user.permission.manage') && !founderLocked && !u.is_deleted;
    const currentRoleIds = new Set((this.userRoles ?? []).map((r) => r.role_id ?? r.role?.id ?? r.id ?? ''));
    return html`<section><div class="row"><h3 class="eyebrow">Roles</h3><span class="spacer"></span>
        ${canRoles ? html`<button class="btn small" @click=${() => (this.action = 'roles')}>Edit roles</button>` : nothing}</div>
      ${founderLocked ? html`<p class="locked">🔒 Founder governance only. Use <a href="/admin/founder-actions">Founder actions</a>.</p>` : nothing}
      ${!this.userRoles ? html`<vs-skeleton rows="2"></vs-skeleton>` : this.userRoles.length ? html`<ul>${this.userRoles.map((r) => html`<li>${r.role?.name ?? r.name ?? r.code}${r.created_on ? html` <span class="small muted">since ${formatAbsolute(r.created_on)}</span>` : nothing}</li>`)}</ul>` : html`<p class="muted">No roles.</p>`}
      ${this.action === 'roles' ? html`<form class="stack card" @submit=${(e: Event) => {
          e.preventDefault();
          const f = e.target as HTMLFormElement;
          const ids = Array.from(f.querySelectorAll<HTMLInputElement>('input[name="role"]:checked')).map((i) => ({ role_id: i.value }));
          const reason = (f.elements.namedItem('reason') as HTMLInputElement).value.trim();
          if (!reason) return void toast('A reason is required', 'error');
          void this.run('Roles updated', () => api.put(`/api/v1/users/${u.id}/roles`, { roles: ids, reason }, { ifMatch: u.version }));
        }}>
          ${this.roles.map((r) => {
            const locked = isFounderGoverned(r) || !r.is_assignable;
            return html`<label class="check"><input type="checkbox" name="role" value=${r.id} ?checked=${currentRoleIds.has(r.id)} ?disabled=${locked} /> ${r.name}
              ${locked ? html`<span class="locked">${isFounderGoverned(r) ? '🔒 Founder governance only' : 'Not assignable'}</span>` : nothing}</label>`;
          })}
          <label class="field"><span class="label">Reason *</span><input name="reason" maxlength="500" /></label>
          <div class="row"><span class="spacer"></span><button type="button" class="btn" @click=${() => (this.action = '')}>Cancel</button><button class="btn primary" ?disabled=${this.busy}>Save roles</button></div>
        </form>` : nothing}
    </section>
    <section><div class="row"><h3 class="eyebrow">Direct permissions</h3><span class="spacer"></span>
        ${canGrant ? html`<button class="btn small" @click=${() => (this.action = 'grant')}>+ Add exception</button>` : nothing}</div>
      ${!this.grants ? html`<vs-skeleton rows="2"></vs-skeleton>` : this.grants.length ? html`<ul class="stack">${this.grants.map((g) => html`<li class="row">
          <span class="chip ${g.effect === 'DENY' ? 'danger' : 'success'}">${g.effect}</span><span class="mono">${g.permission_code}</span>${g.effect === 'GRANT' ? html`<span class="small">· ${g.scope}</span>` : nothing}
          <span class="small muted">"${g.reason}"</span><span class="spacer"></span>
          ${canGrant ? html`<button class="btn ghost small" aria-label=${`Remove ${g.effect} ${g.permission_code}`} @click=${() => this.run('Exception removed', () => api.delete(`/api/v1/users/${u.id}/permissions/${g.id}`, { ifMatch: g.version }))}>✕</button>` : nothing}</li>`)}</ul>`
        : html`<p class="muted">No direct grants or denies.</p>`}
      ${this.action === 'grant' ? html`<form class="stack card" @submit=${(e: Event) => {
          e.preventDefault();
          const f = e.target as HTMLFormElement;
          const v = (n: string) => (f.elements.namedItem(n) as HTMLInputElement).value.trim();
          if (!v('reason')) return void toast('A reason is required', 'error');
          const effect = v('effect');
          void this.run('Exception added', () => api.post(`/api/v1/users/${u.id}/permissions`, {
            permission_code: v('permission_code'), effect, ...(effect === 'GRANT' ? { scope: v('scope') } : {}), reason: v('reason'),
          }));
        }}>
          <label class="field"><span class="label">Permission</span><select name="permission_code">
            ${this.catalog.filter((p) => p.grant_path !== FOUNDER_ONLY).map((p) => html`<option value=${p.code} ?disabled=${!this.can(p.code)}>${p.name} (${p.code})${p.is_sensitive ? ' 🔒' : ''}${this.can(p.code) ? '' : ' — you don\'t hold this'}</option>`)}</select></label>
          <div class="grid-2"><label class="field"><span class="label">Effect</span><select name="effect"><option>GRANT</option><option>DENY</option></select></label>
            <label class="field"><span class="label">Scope</span><select name="scope"><option>ALL</option><option>OWN</option><option disabled>TEAM (available when teams are introduced)</option></select></label></div>
          <label class="field"><span class="label">Reason *</span><input name="reason" maxlength="500" /></label>
          <div class="row"><span class="spacer"></span><button type="button" class="btn" @click=${() => (this.action = '')}>Cancel</button><button class="btn primary" ?disabled=${this.busy}>Add</button></div>
        </form>` : nothing}
    </section>${this.renderEffective()}`;
  }

  private renderEffective() {
    if (!this.can('permission.read')) return nothing;
    const e = this.effective;
    return html`<section><h3 class="eyebrow">Effective permissions</h3>
      ${!e ? html`<vs-skeleton rows="3"></vs-skeleton>` : html`
        <p class="small">MFA: ${MFA_LABEL(e.mfa)}${e.mfa.required ? ` · required by ${e.mfa.required_by.map(humanize).join(', ')}` : ''}</p>
        <div class="table-wrap"><table><thead><tr><th>Permission</th><th>Scope</th><th>Status</th><th>Sources</th></tr></thead><tbody>
        ${e.permissions.map((p) => html`<tr><td class="mono">${p.code}</td><td>${p.scope ?? '—'}</td>
          <td>${p.status === 'SUSPENDED' ? html`<span class="chip warning">Pending MFA</span>` : p.status === 'DENIED' ? html`<span class="chip danger">Denied</span>` : html`<span class="chip success">Effective</span>`}</td>
          <td class="small">${p.sources.map((s) => s.type === 'ROLE' ? `${s.role_code} (${s.scope})` : s.type === 'USER_DENY' ? `Direct deny${s.reason ? ` "${s.reason}"` : ''}` : `Direct grant (${s.scope})`).join(', ')}</td></tr>`)}
        </tbody></table></div>`}
    </section>`;
  }

  private guardNote(): string | null {
    if (this.isSelf) return "You can't change your own account here (use your Profile).";
    if (this.isFounder) return 'Founder accounts use the Founder workflow.';
    return null;
  }

  private renderSecurity(u: UserDetail) {
    const guard = this.guardNote();
    const disabled = Boolean(guard) || u.is_deleted;
    const reasonField = (id: string, label = 'Reason *') => html`<label class="field"><span class="label">${label}</span><input id=${id} maxlength="1000" /></label>`;
    return html`${guard ? html`<vs-banner kind="info">${guard}${this.isFounder ? html` <a href="/admin/founder-actions">Founder actions</a>` : nothing}</vs-banner>` : nothing}
      <section><h3 class="eyebrow">Sign-in email</h3><p>${u.email} ${u.email_verified_on ? '✓ verified' : ''}${u.email_change_pending ? ' · change pending' : ''}</p>
        ${this.can('user.email.change') ? html`<div><button class="btn small" ?disabled=${disabled} @click=${() => (this.action = 'email')}>Change email…</button></div>` : nothing}
        ${this.action === 'email' ? html`<div class="card stack"><p class="small">The new address must verify it, and the current address receives an alert with a cancel link.${u.is_privileged ? ' Privileged account: another administrator must approve.' : ''}</p>
          <label class="field"><span class="label">New email *</span><input id="new_email" type="email" /></label>${reasonField('email_reason')}
          <div class="row"><span class="spacer"></span><button class="btn" @click=${() => (this.action = '')}>Cancel</button>
            <button class="btn primary" ?disabled=${this.busy} @click=${() => this.run('Email change started', () => api.post(`/api/v1/users/${u.id}/email-change`, { new_email: this.formValue('new_email'), reason: this.formValue('email_reason') }, { ifMatch: u.version }))}>${u.is_privileged ? 'Request approval' : 'Send verification'}</button></div></div>` : nothing}
      </section>
      <section><h3 class="eyebrow">Status</h3><p>${humanize(u.status)}${u.throttled_until ? ` · throttled until ${formatAbsolute(u.throttled_until)}` : ''}</p>
        ${this.can('user.status.manage') ? html`<div class="row">
          ${u.status === 'DISABLED' ? html`<button class="btn small" ?disabled=${disabled} @click=${() => { this.statusTarget = 'ACTIVE'; this.action = 'status'; }}>Reactivate…</button>`
            : html`<button class="btn small" ?disabled=${disabled} @click=${() => { this.statusTarget = 'DISABLED'; this.action = 'status'; }}>Deactivate…</button>`}
          ${u.status === 'LOCKED' || u.throttled_until ? html`<button class="btn small" ?disabled=${disabled} @click=${() => this.run('Account unlocked', () => api.post(`/api/v1/users/${u.id}/unlock`, {}))}>Unlock</button>` : nothing}</div>` : nothing}
        ${this.action === 'status' ? html`<div class="card stack"><p>${this.statusTarget === 'DISABLED' ? 'Deactivating signs the user out everywhere and cancels pending links.' : 'The user will be able to sign in again.'}</p>${reasonField('status_reason')}
          <div class="row"><span class="spacer"></span><button class="btn" @click=${() => (this.action = '')}>Cancel</button>
            <button class="btn ${this.statusTarget === 'DISABLED' ? 'danger' : 'primary'}" ?disabled=${this.busy} @click=${() => this.run(this.statusTarget === 'DISABLED' ? 'User deactivated' : 'User reactivated', () => api.post(`/api/v1/users/${u.id}/status`, { status: this.statusTarget, reason: this.formValue('status_reason') }, { ifMatch: u.version }))}>
              ${this.statusTarget === 'DISABLED' ? 'Deactivate' : 'Reactivate'}</button></div></div>` : nothing}
      </section>
      <section><h3 class="eyebrow">Two-step verification</h3><p>${MFA_LABEL(u.mfa)}</p>
        ${this.can('user.mfa.require') ? html`<label class="check"><input type="checkbox" .checked=${u.mfa.required} ?disabled=${disabled}
          @change=${(e: Event) => { this.mfaRequireTarget = (e.target as HTMLInputElement).checked; (e.target as HTMLInputElement).checked = u.mfa.required; this.action = 'mfa-require'; }} /> Require MFA for this user</label>` : nothing}
        ${this.action === 'mfa-require' ? html`<div class="card stack"><p>${this.mfaRequireTarget ? 'Require two-step verification for this user.' : 'Stop requiring two-step verification for this user.'}</p>${reasonField('mfa_require_reason')}
          <div class="row"><span class="spacer"></span><button class="btn" @click=${() => (this.action = '')}>Cancel</button>
            <button class="btn primary" ?disabled=${this.busy} @click=${() => this.run('MFA requirement updated', () => api.put(`/api/v1/users/${u.id}/mfa-requirement`, { mfa_required: this.mfaRequireTarget, reason: this.formValue('mfa_require_reason') }, { ifMatch: u.version }))}>Save</button></div></div>` : nothing}
        ${this.can('user.mfa.reset') ? html`<div><button class="btn small" ?disabled=${disabled || !u.mfa.enrolled} @click=${() => (this.action = 'mfa-reset')}>Reset MFA…</button></div>` : nothing}
        ${this.action === 'mfa-reset' ? html`<div class="card stack">
          <p><strong>Verify identity first.</strong> Confirm who you are speaking to by video call or in person before resetting.</p>
          <label class="check"><input type="checkbox" id="idv" /> I verified this person's identity</label>
          ${reasonField('mfa_reason', 'Reason (include how identity was verified) *')}
          ${u.is_privileged ? html`<vs-banner kind="warning">This request needs approval by another administrator.</vs-banner>` : nothing}
          <div class="row"><span class="spacer"></span><button class="btn" @click=${() => (this.action = '')}>Cancel</button>
            <button class="btn danger" ?disabled=${this.busy} @click=${() => {
              if (!(this.renderRoot.querySelector('#idv') as HTMLInputElement).checked) return void toast('Confirm identity verification first', 'error');
              void this.run('MFA reset. An enrollment link was sent to their verified email.', () => api.post(`/api/v1/users/${u.id}/mfa/reset`, { reason: this.formValue('mfa_reason') }, { ifMatch: u.version }));
            }}>${u.is_privileged ? 'Request reset' : 'Reset MFA'}</button></div></div>` : nothing}
      </section>
      <section><h3 class="eyebrow">Other actions</h3><div class="row">
        ${this.can('user.password.reset') && u.status === 'ACTIVE' ? html`<button class="btn small" ?disabled=${disabled} @click=${() => this.run('Reset link sent to their verified email', () => api.post(`/api/v1/users/${u.id}/password-reset`, {}))}>Send password reset</button>` : nothing}
        ${this.can('user.create') && u.status === 'INVITED' ? html`<button class="btn small" ?disabled=${disabled} @click=${() => this.run('Invitation resent', () => api.post(`/api/v1/users/${u.id}/invite/resend`, {}))}>Resend invite</button>` : nothing}
        ${this.can('user.delete') && !u.is_deleted ? html`<button class="btn small danger" ?disabled=${disabled} @click=${() => (this.action = 'delete')}>Delete…</button>` : nothing}
        ${this.can('user.restore') && u.is_deleted ? html`<button class="btn small" @click=${() => this.run('User restored (disabled)', () => api.post(`/api/v1/users/${u.id}/restore`, {}, { ifMatch: u.version }))}>Restore</button>` : nothing}
      </div>
        ${this.action === 'delete' ? html`<div class="card stack"><p>Delete ${u.full_name}? They are signed out everywhere. Someone with restore permission can bring the account back as disabled.</p>${reasonField('delete_reason')}
          <div class="row"><span class="spacer"></span><button class="btn" @click=${() => (this.action = '')}>Cancel</button>
            <button class="btn danger" ?disabled=${this.busy} @click=${() => this.run('User deleted', () => api.request(`/api/v1/users/${u.id}`, { method: 'DELETE', ifMatch: u.version, body: { reason: this.formValue('delete_reason') } }))}>Delete user</button></div></div>` : nothing}
      </section>
      ${this.can('security_event.read') ? html`<section><a href=${`/audit?tab=security&subject_user_id=${u.id}`} @click=${(e: Event) => { e.preventDefault(); navigate(`/audit?tab=security&subject_user_id=${u.id}`); }}>Security events for this user →</a></section>` : nothing}`;
  }

  private renderSessions(u: UserDetail) {
    const guard = this.guardNote();
    return html`<p class="muted">Revoking signs the user out of every device. Their current access tokens stop working on the next request.</p>
      ${this.can('user.session.revoke') ? html`<label class="field"><span class="label">Reason *</span><input id="revoke_reason" maxlength="1000" /></label>
        <div><button class="btn danger" ?disabled=${Boolean(guard) || this.busy} @click=${() => this.run('All sessions revoked', () => api.post(`/api/v1/users/${u.id}/sessions/revoke`, { reason: this.formValue('revoke_reason') }))}>Revoke all sessions</button></div>
        ${guard ? html`<p class="small muted">${guard}</p>` : nothing}` : html`<p class="muted">You don't have permission to revoke sessions.</p>`}`;
  }

  override render() {
    const u = this.user;
    const err = this.actionProblem;
    return html`<vs-drawer wide .open=${Boolean(this.userId)} heading=${u ? `${u.full_name}${u.protection_level === 'FOUNDER' ? ' ★' : ''}` : 'User'} @close=${() => this.close()}>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${!u ? html`<vs-skeleton rows="6"></vs-skeleton>` : html`
        <vs-tabs .tabs=${[{ id: 'profile', label: 'Profile' }, { id: 'access', label: 'Access' }, { id: 'security', label: 'Security' }, { id: 'sessions', label: 'Sessions' }, { id: 'activity', label: 'Activity', hidden: !this.can('audit.read') }]}
          .selected=${this.tab} @tab-change=${(e: CustomEvent<string>) => { this.tab = e.detail; this.action = ''; this.actionProblem = null; if (e.detail === 'access') void this.loadAccess(); if (e.detail === 'activity') navigate(`/audit?performed_by=${u.id}`); }}></vs-tabs>
        ${err ? html`<vs-banner kind="danger">${ERRORS[err.code] ?? err.detail ?? err.title}${err.requestId ? html` <span class="mono small">(${err.requestId})</span>` : nothing}</vs-banner>` : nothing}
        ${this.tab === 'profile' ? this.renderProfile(u) : this.tab === 'access' ? this.renderAccess(u) : this.tab === 'security' ? this.renderSecurity(u) : this.tab === 'sessions' ? this.renderSessions(u) : nothing}`}
    </vs-drawer>`;
  }
}
customElements.define('vs-user-drawer', VsUserDrawer);
