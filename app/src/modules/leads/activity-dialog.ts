import { html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { LeadActivity, UserRef } from '../../core/api/types.js';
import { instantToLocalInput, localInputToInstant } from '../../core/format/format.js';
import { shared } from '../../design-system/styles.js';
import { LookupAwareElement } from './base.js';

export type ActivityMode = 'log' | 'plan' | 'complete' | 'cancel' | 'edit';
export const USER_TYPES = ['CALL', 'WHATSAPP', 'EMAIL', 'MEETING', 'SITE_VISIT', 'QUOTATION', 'FOLLOW_UP'] as const;
const CONTACT = new Set(['CALL', 'WHATSAPP', 'EMAIL', 'MEETING', 'SITE_VISIT', 'FOLLOW_UP']);

const TYPE_LABEL: Record<string, string> = {
  CALL: 'Call', WHATSAPP: 'WhatsApp', EMAIL: 'Email', MEETING: 'Meeting', SITE_VISIT: 'Site visit', QUOTATION: 'Quotation',
  FOLLOW_UP: 'Follow-up', STATUS_CHANGE: 'Status change', ASSIGNMENT: 'Assignment', SYSTEM: 'System',
};
export const activityTypeLabel = (t: string) => TYPE_LABEL[t] ?? t;

/** Quick picks for planning a follow-up (09 §4.4). Returns datetime-local strings in the user's zone. */
export function quickPicks(now = new Date()): Array<{ label: string; value: string }> {
  const at = (days: number, hour: number, minute = 0) => {
    const base = instantToLocalInput(new Date(now.getTime() + days * 86_400_000).toISOString()).slice(0, 10);
    return `${base}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
  };
  const later = instantToLocalInput(new Date(now.getTime() + 3 * 3_600_000).toISOString());
  return [
    { label: 'Later today', value: later },
    { label: 'Tomorrow 11:00', value: at(1, 11) },
    { label: 'In 3 days', value: at(3, 11) },
    { label: 'Next week', value: at(7, 11) },
  ];
}

/** Log, plan, complete, cancel or edit an activity (08 §9.2). */
export class VsActivityDialog extends LookupAwareElement {
  static override properties = {
    open: { type: Boolean }, mode: { type: String }, leadId: { type: String }, activity: { attribute: false }, preset: { attribute: false },
    assignees: { attribute: false }, defaultOwner: { type: String }, consentWithdrawn: { type: Boolean },
    problem: { state: true }, busy: { state: true }, scheduled: { state: true }, errors: { state: true },
  };
  declare open: boolean;
  declare mode: ActivityMode;
  declare leadId: string;
  declare activity: LeadActivity | null;
  declare preset: { activity_type?: string; direction?: string } | null;
  declare assignees: UserRef[];
  declare defaultOwner: string;
  declare consentWithdrawn: boolean;
  declare problem: ApiProblem | null;
  declare busy: boolean;
  declare scheduled: string;
  declare errors: Record<string, string>;
  static override styles = shared;

  constructor() {
    super();
    this.open = false;
    this.mode = 'log';
    this.leadId = '';
    this.activity = null;
    this.preset = null;
    this.assignees = [];
    this.defaultOwner = '';
    this.consentWithdrawn = false;
    this.problem = null;
    this.busy = false;
    this.scheduled = '';
    this.errors = {};
  }

  override willUpdate(changed: Map<string, unknown>) {
    if (changed.has('open') && this.open) {
      this.problem = null;
      this.errors = {};
      this.scheduled = this.mode === 'edit' ? instantToLocalInput(this.activity?.scheduled_on) : '';
    }
  }

  private close() {
    this.open = false;
    this.dispatchEvent(new CustomEvent('close', { bubbles: true, composed: true }));
  }

  private async submit(e: Event) {
    e.preventDefault();
    const f = e.target as HTMLFormElement;
    const v = (n: string) => ((f.elements.namedItem(n) as HTMLInputElement | null)?.value ?? '').trim();
    const num = (n: string) => (v(n) ? Number(v(n)) : undefined);
    const base = `/api/v1/leads/${this.leadId}/activities`;
    this.errors = {};
    let request: Promise<unknown>;
    if (this.mode === 'log') {
      if (!v('subject')) return void (this.errors = { subject: 'Add a subject.' });
      request = api.post(base, {
        activity_type: v('activity_type'), activity_status: 'COMPLETED', direction: v('direction') || undefined, subject: v('subject'),
        description: v('description') || undefined, completed_on: v('completed_on') ? localInputToInstant(v('completed_on')) : new Date().toISOString(),
        duration_minutes: num('duration_minutes'), outcome_code: v('outcome_code') || undefined,
      });
    } else if (this.mode === 'plan') {
      if (!v('subject')) return void (this.errors = { subject: 'Add a subject.' });
      if (!this.scheduled) return void (this.errors = { scheduled_on: 'Choose when.' });
      request = api.post(base, {
        activity_type: v('activity_type'), activity_status: 'PLANNED', subject: v('subject'), description: v('description') || undefined,
        scheduled_on: localInputToInstant(this.scheduled), duration_minutes: num('duration_minutes'), location: v('location') || undefined,
        owner_user_id: v('owner_user_id') || undefined,
      });
    } else if (this.mode === 'complete' && this.activity) {
      request = api.post(`${base}/${this.activity.id}/complete`, {
        completed_on: v('completed_on') ? localInputToInstant(v('completed_on')) : undefined, outcome_code: v('outcome_code') || undefined,
        description: v('description') || undefined, duration_minutes: num('duration_minutes'),
      }, { ifMatch: this.activity.version });
    } else if (this.mode === 'cancel' && this.activity) {
      request = api.post(`${base}/${this.activity.id}/cancel`, { reason: v('reason') || undefined }, { ifMatch: this.activity.version });
    } else if (this.mode === 'edit' && this.activity) {
      request = api.patch(`${base}/${this.activity.id}`, {
        subject: v('subject'), description: v('description') || null, scheduled_on: this.scheduled ? localInputToInstant(this.scheduled) : undefined,
        duration_minutes: num('duration_minutes') ?? null, location: v('location') || null, owner_user_id: v('owner_user_id') || undefined,
      }, { ifMatch: this.activity.version });
    } else return;
    this.busy = true;
    try {
      await request;
      this.dispatchEvent(new CustomEvent('activity-saved', { bubbles: true, composed: true }));
      this.close();
    } catch (err) {
      const p = err as ApiProblem;
      this.problem = p;
      for (const fe of p.errors) this.errors = { ...this.errors, [fe.field]: fe.message ?? fe.code };
    } finally {
      this.busy = false;
    }
  }

  private typeSelect(value: string) {
    return html`<label class="field"><span class="label">Type</span><select name="activity_type">
      ${USER_TYPES.map((t) => html`<option value=${t} ?selected=${t === value}>${activityTypeLabel(t)}</option>`)}</select></label>`;
  }

  private err(field: string) {
    return this.errors[field] ? html`<span class="error">⚠ ${this.errors[field]}</span>` : nothing;
  }

  private body() {
    const a = this.activity;
    const now = instantToLocalInput(new Date().toISOString());
    switch (this.mode) {
      case 'log':
        return html`${this.consentWithdrawn ? html`<vs-banner kind="danger">Do not contact: consent was withdrawn. Log only inbound or already-completed interactions.</vs-banner>` : nothing}
          <div class="grid-2">${this.typeSelect(this.preset?.activity_type ?? 'CALL')}
            <label class="field"><span class="label">Direction</span><select name="direction"><option value="">—</option>
              <option value="OUTBOUND" ?selected=${this.preset?.direction !== 'INBOUND'}>Outbound</option><option value="INBOUND" ?selected=${this.preset?.direction === 'INBOUND'}>Inbound</option></select></label></div>
          <label class="field"><span class="label">Subject *</span><input name="subject" maxlength="200" aria-required="true" .value=${this.preset?.activity_type ? `${activityTypeLabel(this.preset.activity_type)} with client` : ''} aria-invalid=${this.errors.subject ? 'true' : 'false'} />${this.err('subject')}</label>
          ${this.lookupSelect('outcome_code', 'ACTIVITY_OUTCOME', '', { label: 'Outcome' })}
          <div class="grid-2"><label class="field"><span class="label">When</span><input name="completed_on" type="datetime-local" .value=${now} /></label>
            <label class="field"><span class="label">Duration (min)</span><input name="duration_minutes" type="number" min="0" max="1440" inputmode="numeric" /></label></div>
          <label class="field"><span class="label">Notes</span><textarea name="description" maxlength="4000"></textarea></label>`;
      case 'plan':
      case 'edit':
        return html`${this.mode === 'plan' ? this.typeSelect(this.preset?.activity_type ?? 'FOLLOW_UP') : nothing}
          <label class="field"><span class="label">Subject *</span><input name="subject" maxlength="200" .value=${a?.subject ?? ''} aria-invalid=${this.errors.subject ? 'true' : 'false'} />${this.err('subject')}</label>
          <fieldset class="field"><legend class="label">When *</legend>
            <div class="row">${quickPicks().map((q) => html`<button type="button" class="btn small ${this.scheduled === q.value ? 'primary' : ''}" @click=${() => (this.scheduled = q.value)}>${q.label}</button>`)}</div>
            <input type="datetime-local" aria-label="Custom date and time" .value=${this.scheduled} @change=${(e: Event) => (this.scheduled = (e.target as HTMLInputElement).value)} aria-invalid=${this.errors.scheduled_on ? 'true' : 'false'} />
            ${this.err('scheduled_on')}</fieldset>
          <div class="grid-2">
            <label class="field"><span class="label">Owner</span><select name="owner_user_id">
              ${this.assignees.map((u) => html`<option value=${u.id} ?selected=${u.id === (a?.owner?.id ?? this.defaultOwner)}>${u.display_name}</option>`)}</select>${this.err('owner_user_id')}</label>
            <label class="field"><span class="label">Duration (min)</span><input name="duration_minutes" type="number" min="0" max="1440" .value=${a?.duration_minutes != null ? String(a.duration_minutes) : ''} /></label></div>
          <label class="field"><span class="label">Location</span><input name="location" maxlength="300" .value=${a?.location ?? ''} /></label>
          <label class="field"><span class="label">Notes</span><textarea name="description" maxlength="4000" .value=${a?.description ?? ''}></textarea></label>`;
      case 'complete':
        return html`<p>${a?.subject}</p>${this.lookupSelect('outcome_code', 'ACTIVITY_OUTCOME', '', { label: 'Outcome' })}
          <div class="grid-2"><label class="field"><span class="label">Completed</span><input name="completed_on" type="datetime-local" .value=${now} /></label>
            <label class="field"><span class="label">Duration (min)</span><input name="duration_minutes" type="number" min="0" max="1440" /></label></div>
          <label class="field"><span class="label">Notes</span><textarea name="description" maxlength="4000"></textarea></label>`;
      case 'cancel':
        return html`<p>Cancel "${a?.subject}"?</p><label class="field"><span class="label">Reason</span><input name="reason" maxlength="300" placeholder="Client rescheduled" /></label>`;
    }
  }

  override render() {
    const titles: Record<ActivityMode, string> = { log: 'Log activity', plan: 'Plan follow-up', complete: 'Complete activity', cancel: 'Cancel activity', edit: 'Edit activity' };
    const blocked = this.mode === 'plan' && this.consentWithdrawn && CONTACT.has(this.preset?.activity_type ?? 'FOLLOW_UP');
    return html`<vs-dialog .open=${this.open} heading=${titles[this.mode]} @close=${() => this.open && this.close()}>
      ${blocked
        ? html`<vs-banner kind="danger">Consent to contact was withdrawn, so contact activities can't be planned.</vs-banner>`
        : html`<form id="af" class="stack" @submit=${this.submit} novalidate>${this.body()}<vs-problem-banner .problem=${this.problem}></vs-problem-banner></form>`}
      <div slot="actions"><button class="btn" @click=${this.close}>Close</button>
        ${blocked ? nothing : html`<button class="btn ${this.mode === 'cancel' ? 'danger' : 'primary'}" form="af" ?disabled=${this.busy}>${this.busy ? 'Saving…' : titles[this.mode]}</button>`}</div>
    </vs-dialog>`;
  }
}
customElements.define('vs-activity-dialog', VsActivityDialog);
