import { html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { Role, UserListItem } from '../../core/api/types.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatAbsolute } from '../../core/format/format.js';
import { toast } from '../../design-system/components.js';
import { pageStyles, shared } from '../../design-system/styles.js';
import { fetchAll, isFounderGoverned, loadRoles } from './common.js';

const ACTIONS = [
  ['GRANT_FOUNDER', 'Grant Founder status'],
  ['REVOKE_FOUNDER', 'Revoke Founder status (self step-down allowed)'],
  ['FOUNDER_MFA_RESET', "Reset a Founder's MFA"],
  ['FOUNDER_STATUS_CHANGE', 'Change a Founder account status'],
  ['FOUNDER_EMAIL_CHANGE', "Change a Founder's sign-in email"],
  ['RESTORE_FOUNDER', 'Restore a deleted Founder (returns deactivated)'],
] as const;

const ERR: Record<string, string> = {
  APPROVER_NOT_ELIGIBLE: "You aren't eligible to request Founder-level actions right now (MFA-verified session and step-up required).",
  SELF_MODIFICATION_DENIED: 'You can only target yourself for a Founder step-down.',
  REQUEST_ALREADY_OPEN: 'A Founder-level request for this person is already open.',
  LAST_FOUNDER: 'This would leave no active Founder.',
  SECOND_FOUNDER_REQUIRED: 'Restoring a Founder needs a second eligible Founder to approve in the app.',
  REASON_REQUIRED: 'A reason is required.',
};

/** Founder-governance requests (06 §7.2, 08 §5.11). Approval happens in the Approvals inbox or by a custodian. */
export class VsFounderActionsPage extends SessionElement {
  static override properties = { users: { state: true }, deleted: { state: true }, roles: { state: true }, action: { state: true }, problem: { state: true }, result: { state: true }, busy: { state: true } };
  declare users: UserListItem[];
  declare deleted: UserListItem[];
  declare roles: Role[];
  declare action: string;
  declare problem: ApiProblem | null;
  declare result: { approval_id: string; channel: string; not_before?: string } | null;
  declare busy: boolean;
  static override styles = [...shared, pageStyles];

  constructor() {
    super();
    this.users = [];
    this.deleted = [];
    this.roles = [];
    this.action = 'GRANT_FOUNDER';
    this.problem = null;
    this.result = null;
    this.busy = false;
  }
  override connectedCallback() {
    super.connectedCallback();
    void fetchAll<UserListItem>('/api/v1/users').then((u) => (this.users = u)).catch((e) => (this.problem = e));
    // Deleted Founders are restored only through this dual-control request, never the generic user restore (OD-2).
    if (this.can('user.restore')) {
      void fetchAll<UserListItem>('/api/v1/users', { include_deleted: 'true' })
        .then((u) => (this.deleted = u.filter((x) => x.is_deleted && x.protection_level === 'FOUNDER')))
        .catch(() => undefined);
    }
    if (this.can('role.read')) void loadRoles().then((r) => (this.roles = r)).catch(() => undefined);
  }
  private async submit(e: Event) {
    e.preventDefault();
    const f = e.target as HTMLFormElement;
    const v = (n: string) => ((f.elements.namedItem(n) as HTMLInputElement | null)?.value ?? '').trim();
    const restore = this.action === 'RESTORE_FOUNDER';
    const body: Record<string, unknown> = {
      action: restore ? 'FOUNDER_STATUS_CHANGE' : this.action, target_user_id: v('target_user_id'), reason: v('reason'),
    };
    if (restore) body.status = 'RESTORE';
    if (this.action === 'FOUNDER_STATUS_CHANGE') body.status = v('status');
    if (this.action === 'FOUNDER_EMAIL_CHANGE') body.new_email = v('new_email');
    if (this.action === 'REVOKE_FOUNDER') {
      const post = Array.from(f.querySelectorAll<HTMLInputElement>('input[name="post_roles"]:checked')).map((i) => i.value);
      if (post.length) body.post_roles = post;
    }
    this.busy = true;
    this.problem = null;
    try {
      const r = await api.post<{ approval_id: string; channel: string; not_before?: string }>('/api/v1/founder-actions', body);
      this.result = r.data;
      toast('Founder-level request created', 'success');
    } catch (err) {
      const p = err as ApiProblem;
      this.problem = p;
      if (ERR[p.code]) toast(ERR[p.code], 'error');
    } finally {
      this.busy = false;
    }
  }
  override render() {
    const founders = this.users.filter((u) => u.protection_level === 'FOUNDER');
    const targets = this.action === 'GRANT_FOUNDER' ? this.users.filter((u) => u.protection_level !== 'FOUNDER' && u.status === 'ACTIVE')
      : this.action === 'RESTORE_FOUNDER' ? this.deleted : founders;
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Governance</p><h1 class="display">Founder actions</h1></div></div>
      <vs-banner kind="info">Founder-level changes always need a second person. With two or more eligible Founders another Founder approves in the app.
        With a single Founder, a break-glass custodian approves and the action runs no earlier than the configured delay; every Founder and the target are notified and can cancel.</vs-banner>
      <p class="small muted">Active Founders: ${founders.length} ${founders.length === 1 ? '(single-Founder mode)' : ''}</p>
      ${this.result ? html`<vs-banner kind="success">Request ${this.result.approval_id} created (${this.result.channel === 'BREAK_GLASS' ? 'awaiting a break-glass custodian' : 'awaiting another Founder'}${this.result.not_before ? `; not before ${formatAbsolute(this.result.not_before)}` : ''}).
        <a href="/approvals">View in Approvals</a></vs-banner>` : nothing}
      <form class="card stack" @submit=${this.submit} novalidate>
        <label class="field"><span class="label">Action</span><select name="action" @change=${(e: Event) => (this.action = (e.target as HTMLSelectElement).value)}>
          ${ACTIONS.map(([v, l]) => html`<option value=${v} ?selected=${v === this.action}>${l}</option>`)}</select></label>
        <label class="field"><span class="label">Person</span><select name="target_user_id">
          ${targets.map((u) => html`<option value=${u.id}>${u.full_name} (${u.email})${u.id === this.me?.id ? ' — you' : ''}</option>`)}</select></label>
        ${this.action === 'FOUNDER_STATUS_CHANGE' ? html`<label class="field"><span class="label">New status</span><select name="status">
          <option value="DISABLED">Deactivate</option><option value="ACTIVE">Reactivate</option><option value="UNLOCK">Unlock</option><option value="DELETED">Delete</option></select></label>` : nothing}
        ${this.action === 'FOUNDER_EMAIL_CHANGE' ? html`<label class="field"><span class="label">New email</span><input name="new_email" type="email" /></label>` : nothing}
        ${this.action === 'REVOKE_FOUNDER' && this.roles.length ? html`<fieldset class="field"><legend class="label">Roles to hold afterwards (optional)</legend>
          ${this.roles.filter((r) => !isFounderGoverned(r) && r.is_assignable).map((r) => html`<label class="check"><input type="checkbox" name="post_roles" value=${r.id} /> ${r.name}</label>`)}</fieldset>` : nothing}
        <label class="field"><span class="label">Reason *</span><textarea name="reason" maxlength="1000"></textarea></label>
        <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
        <div class="row"><span class="spacer"></span><button class="btn primary" ?disabled=${this.busy}>Submit request</button></div>
      </form>
    </div>`;
  }
}
customElements.define('vs-founder-actions-page', VsFounderActionsPage);
