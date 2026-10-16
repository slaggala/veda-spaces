import { css, html, nothing } from 'lit';
import { newIdempotencyKey } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatAbsolute } from '../../core/format/format.js';
import { toast } from '../../design-system/components.js';
import { shared } from '../../design-system/styles.js';
import { portalStaffApi, RELATIONSHIPS, type AccessRow } from './api.js';

/**
 * Lead page: who has customer portal access to this enquiry; invite a customer (they receive a sign-in link by email);
 * end an access at once. Shown only while the portal is switched on and the user may see access (portal.access.view);
 * the server checks every action again, within the lead's scope.
 */
export class VsPortalAccessCard extends SessionElement {
  static override properties = {
    leadId: { type: String, attribute: 'lead-id' }, rows: { state: true }, busy: { state: true }, inviting: { state: true },
    confirm: { state: true }, error: { state: true },
  };
  declare leadId: string;
  declare rows: AccessRow[] | null;
  declare busy: boolean;
  declare inviting: boolean;
  declare confirm: AccessRow | null;
  declare error: string;
  private key = newIdempotencyKey();

  static override styles = [...shared, css`
    :host { display: block; }
    ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vs-space-2); }
    li { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--vs-space-2); border-bottom: 1px solid var(--vs-line); padding-bottom: var(--vs-space-2); }
    li:last-child { border-bottom: 0; }
    .who { display: flex; flex-direction: column; min-width: 0; overflow-wrap: anywhere; }
    .btn { min-height: var(--vs-target); }
  `];

  constructor() {
    super();
    this.leadId = '';
    this.rows = null;
    this.busy = false;
    this.inviting = false;
    this.confirm = null;
    this.error = '';
  }

  private get enabled(): boolean {
    return this.me?.features?.customer_portal === true && this.can('portal.access.view');
  }

  override updated(changed: Map<string, unknown>) {
    if (changed.has('leadId') && this.leadId && this.enabled) void this.load();
  }

  private async load() {
    try {
      this.rows = (await portalStaffApi.list(this.leadId)).data;
    } catch {
      this.rows = null;
    }
  }

  private async invite(e: Event) {
    e.preventDefault();
    const f = e.target as HTMLFormElement;
    const v = (n: string) => (f.elements.namedItem(n) as HTMLInputElement | HTMLSelectElement).value.trim();
    this.busy = true;
    this.error = '';
    try {
      this.rows = (await portalStaffApi.grant(this.leadId, { email: v('email') || undefined, display_name: v('display_name') || undefined,
        relationship: v('relationship') }, this.key)).data;
      this.key = newIdempotencyKey();
      this.inviting = false;
      toast('Portal access given. The customer has been emailed a sign-in link.', 'success');
    } catch (err) {
      const p = err as ApiProblem;
      if (p.status >= 400 && p.status < 500) this.key = newIdempotencyKey();
      this.error = p.errors?.[0]?.message ?? p.detail ?? 'Access could not be given.';
    } finally {
      this.busy = false;
    }
  }

  private async revoke(row: AccessRow) {
    this.busy = true;
    try {
      this.rows = (await portalStaffApi.revoke(row)).data;
      toast('Portal access ended.', 'success');
    } catch (err) {
      toast((err as ApiProblem).detail ?? 'Access could not be ended.', 'error');
      void this.load();
    } finally {
      this.busy = false;
      this.confirm = null;
    }
  }

  override render() {
    if (!this.enabled) return nothing;
    const active = (this.rows ?? []).filter((r) => r.status === 'ACTIVE');
    const ended = (this.rows ?? []).filter((r) => r.status !== 'ACTIVE');
    return html`<section class="card stack" aria-labelledby="portal-h">
      <h2 id="portal-h" class="title">Customer portal</h2>
      <p class="small muted">Customers see their home's progress, their issued quotations and what Veda Spaces has committed to. They never see internal pricing, notes or drafts.</p>
      ${this.rows === null ? html`<vs-skeleton rows="2"></vs-skeleton>` : active.length ? html`<ul>${active.map((r) => html`<li>
          <span class="who"><span class="strong">${r.account.display_name}</span><span class="small muted">${r.account.email} · ${RELATIONSHIPS[r.relationship] ?? r.relationship}</span>
            <span class="small muted">${r.account.last_signed_in_on ? `Last signed in ${formatAbsolute(r.account.last_signed_in_on)}` : 'Not signed in yet'}</span></span>
          ${this.can('portal.access.revoke') ? html`<button class="btn small danger" ?disabled=${this.busy} @click=${() => (this.confirm = r)}>End access<span class="sr-only"> for ${r.account.display_name}</span></button>` : nothing}
        </li>`)}</ul>` : html`<p class="small">No customer has portal access to this enquiry.</p>`}
      ${ended.length ? html`<p class="small muted">${ended.length} ended access${ended.length > 1 ? 'es' : ''}.</p>` : nothing}
      ${this.can('portal.access.grant') && !this.inviting ? html`<button class="btn" @click=${() => { this.inviting = true; }}>Invite a customer</button>` : nothing}
      ${this.inviting ? html`<form class="stack" @submit=${(e: Event) => void this.invite(e)}>
          ${this.error ? html`<vs-banner kind="danger" role="alert">${this.error}</vs-banner>` : nothing}
          <label class="field"><span class="label">Customer's email</span><input name="email" type="email" autocomplete="off" placeholder="Leave blank to use the enquiry's email" /></label>
          <label class="field"><span class="label">Name to greet them by</span><input name="display_name" maxlength="150" placeholder="Leave blank to use the enquiry's name" /></label>
          <label class="field"><span class="label">Relationship</span><select name="relationship">${Object.entries(RELATIONSHIPS).map(([k, l]) => html`<option value=${k}>${l}</option>`)}</select></label>
          <div class="row"><button class="btn" type="button" @click=${() => { this.inviting = false; this.error = ''; }}>Cancel</button>
            <button class="btn primary" type="submit" ?disabled=${this.busy}>Give access and send link</button></div>
        </form>` : nothing}
      <vs-dialog .open=${this.confirm !== null} heading="End portal access" @close=${() => (this.confirm = null)}>
        <p>${this.confirm?.account.display_name} will be signed out and can no longer see this enquiry in the portal.</p>
        <div slot="actions"><button class="btn" @click=${() => (this.confirm = null)}>Cancel</button>
          <button class="btn danger" ?disabled=${this.busy} @click=${() => this.confirm && void this.revoke(this.confirm)}>End access</button></div>
      </vs-dialog>
    </section>`;
  }
}
customElements.define('vs-portal-access-card', VsPortalAccessCard);
