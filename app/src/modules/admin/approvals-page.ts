import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { Approval } from '../../core/api/types.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatAbsolute, formatRelative, humanize } from '../../core/format/format.js';
import { toast } from '../../design-system/components.js';
import { pageStyles, shared } from '../../design-system/styles.js';

const DECIDE_ERRORS: Record<string, string> = {
  APPROVER_NOT_ELIGIBLE: "You aren't eligible to decide this request.",
  INVALID_STATE: 'This request was already decided, expired or cancelled.',
  LAST_FOUNDER: 'This would remove the last Founder.',
};

/** Approvals inbox for dual-control and Founder-governance requests (09 §4.12, RBAC-021). */
export class VsApprovalsPage extends SessionElement {
  static override properties = { view: { state: true }, items: { state: true }, problem: { state: true }, deciding: { state: true }, decision: { state: true }, busy: { state: true } };
  declare view: 'approver' | 'requester';
  declare items: Approval[] | null;
  declare problem: ApiProblem | null;
  declare deciding: Approval | null;
  declare decision: 'approve' | 'deny';
  declare busy: boolean;
  static override styles = [...shared, pageStyles, css`.req { display: flex; flex-direction: column; gap: 6px; } .seg { display: inline-flex; border: 1px solid var(--vs-line); } .seg button { border: 0; background: var(--vs-surface); min-height: 40px; padding: 0 14px; cursor: pointer; font: 600 13px var(--vs-font-sans); color: var(--vs-ink-muted); } .seg button[aria-pressed='true'] { background: var(--vs-cream); color: var(--vs-ink); }`];

  constructor() {
    super();
    this.view = 'approver';
    this.items = null;
    this.problem = null;
    this.deciding = null;
    this.decision = 'approve';
    this.busy = false;
  }
  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }
  private async load() {
    this.items = null;
    try {
      this.items = (await api.get<Approval[]>('/api/v1/approvals', { status: this.view === 'approver' ? 'PENDING' : undefined, role: this.view })).data;
    } catch (e) {
      this.problem = e as ApiProblem;
      this.items = [];
    }
  }
  private canDecide(a: Approval): boolean {
    if (a.can_decide !== undefined) return a.can_decide;
    return a.requested_by?.id !== this.me?.id && a.target_user?.id !== this.me?.id && a.status === 'PENDING';
  }
  private async decide(e: Event) {
    e.preventDefault();
    const a = this.deciding!;
    const reason = ((e.target as HTMLFormElement).elements.namedItem('reason') as HTMLInputElement).value.trim();
    if (!reason) return void toast('A reason is required', 'error');
    this.busy = true;
    try {
      const r = await api.post<Approval>(`/api/v1/approvals/${a.id}/${this.decision}`, { reason });
      toast(this.decision === 'approve' ? (r.data?.status === 'FAILED' ? `Approved, but execution failed: ${humanize(r.data.status_reason)}` : 'Approved and executed') : 'Request denied', r.data?.status === 'FAILED' ? 'error' : 'success');
      this.deciding = null;
      await this.load();
    } catch (err) {
      const p = err as ApiProblem;
      this.problem = p;
      if (DECIDE_ERRORS[p.code]) toast(DECIDE_ERRORS[p.code], 'error');
    } finally {
      this.busy = false;
    }
  }
  private async cancel(a: Approval) {
    if (!confirm('Cancel this request?')) return;
    try {
      await api.post(`/api/v1/approvals/${a.id}/cancel`, {});
      toast('Request cancelled');
      await this.load();
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }
  override render() {
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Admin</p><h1 class="display">Approvals</h1></div><span class="spacer"></span>
        <div class="seg" role="group" aria-label="Show">
          <button aria-pressed=${this.view === 'approver' ? 'true' : 'false'} @click=${() => { this.view = 'approver'; void this.load(); }}>Pending for me</button>
          <button aria-pressed=${this.view === 'requester' ? 'true' : 'false'} @click=${() => { this.view = 'requester'; void this.load(); }}>Requested by me</button></div></div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${!this.items ? html`<div class="card"><vs-skeleton rows="4"></vs-skeleton></div>` : !this.items.length ? html`<div class="card"><vs-empty-state heading="Nothing waiting."></vs-empty-state></div>`
        : this.items.map((a) => html`<article class="card req">
          <div class="row"><strong>${humanize(a.action_type)}</strong> · ${a.target_user?.display_name}${a.target_user?.email ? ` (${a.target_user.email})` : ''}
            ${a.action_class === 'FOUNDER' ? html`<span class="chip">Founder-level</span>` : nothing}<span class="spacer"></span><span class="chip">${humanize(a.status)}</span></div>
          <div class="small muted">Requested by ${a.requested_by?.display_name ?? 'break-glass custodian'} · ${formatRelative(a.created_on)} · expires ${formatRelative(a.expires_on)}</div>
          ${a.channel === 'BREAK_GLASS' ? html`<vs-banner kind="warning">Approval by a break-glass custodian${a.not_before ? `; executes no earlier than ${formatAbsolute(a.not_before)}` : ''}.</vs-banner>` : nothing}
          <p>Reason: "${a.reason}"</p>
          ${a.status_reason ? html`<p class="small">Status reason: ${humanize(a.status_reason)}</p>` : nothing}
          <div class="row">
            ${this.view === 'approver' && a.status === 'PENDING' && a.channel === 'IN_APP'
              ? this.canDecide(a) ? html`<button class="btn" @click=${() => { this.deciding = a; this.decision = 'deny'; }}>Deny…</button>
                  <button class="btn primary" @click=${() => { this.deciding = a; this.decision = 'approve'; }}>Approve…</button>`
                : html`<span class="small muted">You can't decide this request.</span>` : nothing}
            ${this.view === 'requester' && a.status === 'PENDING' ? html`<button class="btn" @click=${() => this.cancel(a)}>Cancel request</button>` : nothing}
          </div></article>`)}
      <vs-dialog .open=${Boolean(this.deciding)} heading=${this.decision === 'approve' ? 'Approve request' : 'Deny request'} @close=${() => (this.deciding = null)}>
        <form id="df" class="stack" @submit=${this.decide}>
          ${this.decision === 'approve' ? html`<p>The action runs immediately after approval.</p>` : nothing}
          <label class="field"><span class="label">Reason *</span><input name="reason" maxlength="1000" /></label>
        </form>
        <div slot="actions"><button class="btn" @click=${() => (this.deciding = null)}>Cancel</button>
          <button class="btn ${this.decision === 'deny' ? 'danger' : 'primary'}" form="df" ?disabled=${this.busy}>${this.decision === 'approve' ? 'Approve' : 'Deny'}</button></div>
      </vs-dialog>
    </div>`;
  }
}
customElements.define('vs-approvals-page', VsApprovalsPage);
