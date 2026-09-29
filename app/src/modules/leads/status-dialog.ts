import { html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { Lead, LeadStatus } from '../../core/api/types.js';
import { localInputToInstant } from '../../core/format/format.js';
import { statusLabel } from '../../core/i18n/strings.js';
import { shared } from '../../design-system/styles.js';
import { LookupAwareElement } from './base.js';
import { transitionBody, transitionRules, validateTransition } from './transitions.js';

/** Status transition dialog: asks only for the inputs 04 §3 requires, explains side effects (09 §4.4). */
export class VsStatusDialog extends LookupAwareElement {
  static override properties = { lead: { attribute: false }, to: { type: String }, open: { type: Boolean }, errors: { state: true }, problem: { state: true }, busy: { state: true }, reason: { state: true }, plannedCount: { type: Number } };
  declare lead: Lead | null;
  declare to: LeadStatus | '';
  declare open: boolean;
  declare errors: Record<string, string>;
  declare problem: ApiProblem | null;
  declare busy: boolean;
  declare reason: string;
  declare plannedCount: number;
  static override styles = shared;

  constructor() {
    super();
    this.lead = null;
    this.to = '';
    this.open = false;
    this.errors = {};
    this.problem = null;
    this.busy = false;
    this.reason = '';
    this.plannedCount = 0;
  }

  private async submit(e: Event) {
    e.preventDefault();
    if (!this.lead || !this.to) return;
    const f = e.target as HTMLFormElement;
    const v = (n: string) => (f.elements.namedItem(n) as HTMLInputElement | null)?.value ?? '';
    const wonLocal = v('won_on');
    const input = { comment: v('comment'), lost_reason_code: v('lost_reason_code'), lost_reason_note: v('lost_reason_note'), won_on: wonLocal ? localInputToInstant(wonLocal) : undefined };
    this.errors = validateTransition(this.lead.status, this.to, input);
    if (Object.keys(this.errors).length) {
      (f.querySelector('[aria-invalid="true"]') as HTMLElement | null)?.focus();
      return;
    }
    this.busy = true;
    this.problem = null;
    try {
      const r = await api.post<Lead>(`/api/v1/leads/${this.lead.id}/status`, transitionBody(this.to, input), { ifMatch: this.lead.version });
      this.dispatchEvent(new CustomEvent('lead-updated', { detail: r.data, bubbles: true, composed: true }));
      this.close();
    } catch (err) {
      const p = err as ApiProblem;
      if (p.code === 'COMMENT_REQUIRED') this.errors = { comment: 'Add a comment explaining this change.' };
      else if (p.code === 'LOST_REASON_REQUIRED') this.errors = { lost_reason_code: 'Choose a lost reason.' };
      else this.problem = p;
      if (p.code === 'VERSION_CONFLICT') this.dispatchEvent(new CustomEvent('conflict', { bubbles: true, composed: true }));
    } finally {
      this.busy = false;
    }
  }

  private close() {
    this.open = false;
    this.errors = {};
    this.problem = null;
    this.reason = '';
    this.dispatchEvent(new CustomEvent('close', { bubbles: true, composed: true }));
  }

  override render() {
    const lead = this.lead;
    const to = this.to as LeadStatus;
    const rules = lead && to ? transitionRules(lead.status, to) : null;
    const title = !to ? '' : rules?.kind === 'reopen' ? `Reopen as ${statusLabel(to)}` : to === 'LOST' ? 'Mark as Lost' : to === 'WON' ? 'Mark as Won' : `Move to ${statusLabel(to)}`;
    return html`<vs-dialog .open=${this.open} heading=${title} @close=${() => this.open && this.close()}>
      ${lead && rules
        ? html`<form id="f" @submit=${this.submit} novalidate class="stack">
            ${rules.cancelsPlanned && this.plannedCount
              ? html`<vs-banner kind="warning">${this.plannedCount} planned follow-up${this.plannedCount === 1 ? '' : 's'} will be cancelled.</vs-banner>` : nothing}
            ${rules.kind === 'back' ? html`<p class="muted">Moving back one step needs a comment.</p>` : nothing}
            ${rules.lostReasonRequired
              ? html`<div @change=${(e: Event) => { const t = e.target as HTMLSelectElement; if (t.name === 'lost_reason_code') this.reason = t.value; }}>
                  ${this.lookupSelect('lost_reason_code', 'LOST_REASON', this.reason, { label: 'Lost reason', required: true, error: this.errors.lost_reason_code })}</div>
                <label class="field"><span class="label">Note${this.reason === 'OTHER' ? ' *' : ''}</span>
                  <textarea name="lost_reason_note" maxlength="1000" aria-invalid=${this.errors.lost_reason_note ? 'true' : 'false'}></textarea>
                  ${this.errors.lost_reason_note ? html`<span class="error">⚠ ${this.errors.lost_reason_note}</span>` : nothing}</label>`
              : nothing}
            ${rules.wonOnAllowed ? html`<label class="field"><span class="label">Won on</span><input name="won_on" type="datetime-local" /><span class="hint">Leave empty for now.</span></label>` : nothing}
            <label class="field"><span class="label">Comment${rules.commentRequired ? ' *' : ' (optional)'}</span>
              <textarea name="comment" maxlength="1000" aria-required=${rules.commentRequired ? 'true' : 'false'} aria-invalid=${this.errors.comment ? 'true' : 'false'}></textarea>
              ${this.errors.comment ? html`<span class="error">⚠ ${this.errors.comment}</span>` : nothing}</label>
            <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
          </form>`
        : html`<p>This move is not available.</p>`}
      <div slot="actions">
        <button class="btn" @click=${this.close}>Cancel</button>
        <button class="btn ${to === 'LOST' ? 'danger' : 'primary'}" form="f" ?disabled=${this.busy || !rules}>${this.busy ? 'Saving…' : title}</button>
      </div>
    </vs-dialog>`;
  }
}
customElements.define('vs-status-dialog', VsStatusDialog);
