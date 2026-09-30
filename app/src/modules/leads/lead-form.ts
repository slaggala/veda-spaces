import { html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { Lead, UserRef } from '../../core/api/types.js';
import { formatRelative } from '../../core/format/format.js';
import { statusLabel } from '../../core/i18n/strings.js';
import { navigate } from '../../core/router/next.js';
import { toast } from '../../design-system/components.js';
import { shared } from '../../design-system/styles.js';
import { resolveConflict } from '../../shell/conflict-dialog.js';
import { LookupAwareElement } from './base.js';
import { EDITABLE, type Editable, leadPatch, leadValues } from './edits.js';

interface DuplicateHit { id: string; lead_number: string; name: string; status: string; created_on?: string }


/** Lead create / edit drawer (09 §4.5). The duplicate check warns but never blocks. */
export class VsLeadForm extends LookupAwareElement {
  static override properties = {
    open: { type: Boolean }, lead: { attribute: false }, assignees: { attribute: false },
    duplicates: { state: true }, errors: { state: true }, problem: { state: true }, busy: { state: true }, priority: { state: true },
  };
  declare open: boolean;
  declare lead: Lead | null;
  declare assignees: UserRef[];
  declare duplicates: DuplicateHit[];
  declare errors: Record<string, string>;
  declare problem: ApiProblem | null;
  declare busy: boolean;
  declare priority: string;
  private dirty = false;
  static override styles = shared;

  constructor() {
    super();
    this.open = false;
    this.lead = null;
    this.assignees = [];
    this.duplicates = [];
    this.errors = {};
    this.problem = null;
    this.busy = false;
    this.priority = 'MEDIUM';
  }

  override willUpdate(changed: Map<string, unknown>) {
    if (changed.has('open') && this.open) {
      this.errors = {};
      this.problem = null;
      this.duplicates = [];
      this.dirty = false;
      this.priority = this.lead?.priority ?? 'MEDIUM';
    }
  }

  private get form(): HTMLFormElement | null {
    return this.renderRoot.querySelector('form');
  }

  private read(): Record<Editable, string> {
    const f = this.form!;
    const out = {} as Record<Editable, string>;
    for (const k of EDITABLE) {
      const el = f.elements.namedItem(k) as HTMLInputElement | null;
      out[k] = k === 'priority' ? this.priority : (el?.value ?? '').trim();
    }
    return out;
  }

  private async checkDuplicates() {
    const f = this.form;
    if (!f) return;
    const phone = (f.elements.namedItem('phone') as HTMLInputElement).value.trim();
    const email = (f.elements.namedItem('email') as HTMLInputElement).value.trim();
    if (!phone && !email) return;
    try {
      const r = await api.get<DuplicateHit[]>('/api/v1/leads/duplicates', { phone, email, exclude_id: this.lead?.id });
      this.duplicates = r.data ?? [];
    } catch {
      this.duplicates = [];
    }
  }

  private async close(force = false) {
    if (!force && this.dirty && !confirm('Discard unsaved changes?')) {
      this.open = true;
      return;
    }
    this.open = false;
    this.dispatchEvent(new CustomEvent('close', { bubbles: true, composed: true }));
  }

  private applyProblem(p: ApiProblem) {
    const errs: Record<string, string> = {};
    for (const e of p.errors) errs[e.field] = e.message ?? e.code;
    if (p.code === 'INVALID_ASSIGNEE') errs.assigned_to = 'Choose an active teammate who can see leads.';
    if (p.code === 'SOURCE_NOT_ALLOWED') errs.source_code = 'Website is reserved for online enquiries.';
    this.errors = errs;
    if (!Object.keys(errs).length) this.problem = p;
    this.updateComplete.then(() => (this.renderRoot.querySelector('[aria-invalid="true"]') as HTMLElement | null)?.focus());
  }

  private async submit(e: Event) {
    e.preventDefault();
    const values = this.read();
    const errs: Record<string, string> = {};
    if (values.name.length < 2) errs.name = 'Enter the full name.';
    if (!values.phone) errs.phone = 'Enter a phone number.';
    if (!this.lead && !values.source_code) errs.source_code = 'Choose a source.';
    this.errors = errs;
    if (Object.keys(errs).length) {
      this.updateComplete.then(() => (this.renderRoot.querySelector('[aria-invalid="true"]') as HTMLElement | null)?.focus());
      return;
    }
    this.busy = true;
    this.problem = null;
    try {
      if (this.lead) await this.saveEdit(values, this.lead);
      else await this.create(values);
    } catch (err) {
      this.applyProblem(err as ApiProblem);
    } finally {
      this.busy = false;
    }
  }

  private async create(values: Record<Editable, string>) {
    const f = this.form!;
    const body: Record<string, unknown> = {};
    for (const k of EDITABLE) if (values[k]) body[k] = values[k];
    const assigned = (f.elements.namedItem('assigned_to') as HTMLSelectElement | null)?.value;
    if (assigned) body.assigned_to = assigned;
    const note = (f.elements.namedItem('initial_note') as HTMLTextAreaElement).value.trim();
    if (note) body.initial_note = note;
    const r = await api.post<Lead>('/api/v1/leads', body);
    toast(`Lead ${r.data.lead_number} created`, 'success');
    this.dirty = false;
    await this.close(true);
    this.dispatchEvent(new CustomEvent('lead-saved', { detail: r.data, bubbles: true, composed: true }));
    navigate(`/leads/${r.data.id}`);
  }

  /** `patch` is the user's own edits, computed once against the record as loaded. A conflict re-apply sends exactly
   *  those edits against the fresh version and never the rest of the stale form (IR-15, TD-F step 4). */
  private async saveEdit(values: Record<Editable, string>, original: Lead, version = original.version,
                         patch: Record<string, unknown> = leadPatch(values, leadValues(original))): Promise<void> {
    const before = leadValues(original);
    if (!Object.keys(patch).length) {
      await this.close(true);
      return;
    }
    try {
      const r = await api.patch<Lead>(`/api/v1/leads/${original.id}`, patch, { ifMatch: version });
      toast('Lead saved', 'success');
      this.dirty = false;
      await this.close(true);
      this.dispatchEvent(new CustomEvent('lead-saved', { detail: r.data, bubbles: true, composed: true }));
    } catch (err) {
      const p = err as ApiProblem;
      if (p.code !== 'VERSION_CONFLICT') throw p;
      const fresh = (await api.get<Lead>(`/api/v1/leads/${original.id}`)).data;
      const theirs = leadValues(fresh);
      const changed = EDITABLE.filter((k) => theirs[k] !== before[k]);
      const who = p.ext<{ display_name?: string }>('updated_by')?.display_name;
      const choice = await resolveConflict({ fields: changed, updatedBy: who, updatedOn: formatRelative(p.ext<string>('updated_on')) });
      if (choice === 'reload') {
        this.lead = fresh;
        this.dirty = false;
        this.requestUpdate();
      } else if (choice === 'reapply') {
        await this.saveEdit(values, fresh, fresh.version, patch);
      }
    }
  }

  private field(name: Editable, label: string, value: string, opts: { required?: boolean; type?: string; autocomplete?: string; max?: number; blur?: boolean } = {}) {
    const err = this.errors[name];
    return html`<label class="field"><span class="label">${label}${opts.required ? ' *' : ''}</span>
      <input name=${name} type=${opts.type ?? 'text'} .value=${value} maxlength=${opts.max ?? 200} autocomplete=${opts.autocomplete ?? 'off'}
        aria-required=${opts.required ? 'true' : 'false'} aria-invalid=${err ? 'true' : 'false'}
        @blur=${opts.blur ? () => this.checkDuplicates() : null} />
      ${err ? html`<span class="error">⚠ ${err}</span>` : nothing}</label>`;
  }

  override render() {
    const lead = this.lead;
    const v = leadValues(lead);
    const canAssign = this.can('lead.assign');
    return html`<vs-drawer .open=${this.open} heading=${lead ? `Edit ${lead.lead_number}` : 'New lead'} @close=${() => this.open && this.close()}>
      <form id="lf" class="stack" novalidate @submit=${this.submit} @input=${() => (this.dirty = true)}>
        <p class="eyebrow">Contact</p>
        ${this.field('name', 'Full name', v.name, { required: true, autocomplete: 'name', max: 150 })}
        ${this.field('phone', 'Phone', v.phone, { required: true, type: 'tel', autocomplete: 'tel', max: 30, blur: true })}
        ${this.field('email', 'Email', v.email, { type: 'email', autocomplete: 'email', max: 254, blur: true })}
        ${this.duplicates.length
          ? html`<vs-banner kind="warning"><div><strong>Possible duplicate</strong>${this.duplicates.map(
              (d) => html`<div class="small">${d.lead_number} · ${d.name} · ${statusLabel(d.status)}${d.created_on ? ` · ${formatRelative(d.created_on)}` : ''}
                <a href=${`/leads/${d.id}`} target="_blank" rel="noopener">Open</a></div>`,
            )}</div></vs-banner>`
          : nothing}
        <p class="eyebrow">Project</p>
        <div class="grid-2">
          ${this.lookupSelect('project_type_code', 'PROJECT_TYPE', v.project_type_code, { label: 'Project type', error: this.errors.project_type_code })}
          ${this.lookupSelect('property_type_code', 'PROPERTY_TYPE', v.property_type_code, { label: 'Property type', error: this.errors.property_type_code })}
          ${this.lookupSelect('budget_range_code', 'BUDGET_RANGE', v.budget_range_code, { label: 'Budget range', error: this.errors.budget_range_code })}
          ${this.field('expected_close_on', 'Expected close', v.expected_close_on, { type: 'date' })}
          ${this.field('city', 'City', v.city, { max: 100 })}
          ${this.field('locality', 'Area / locality', v.locality, { max: 150 })}
        </div>
        <label class="field"><span class="label">Message / brief</span><textarea name="message" maxlength="4000" .value=${v.message}></textarea></label>
        <p class="eyebrow">Source & ownership</p>
        <div class="grid-2">
          ${this.lookupSelect('source_code', 'LEAD_SOURCE', v.source_code, { label: 'Source', required: !lead, error: this.errors.source_code })}
          ${this.field('source_detail', 'Detail', v.source_detail, { max: 200 })}
        </div>
        <fieldset class="field"><legend class="label">Priority</legend><div class="row" role="radiogroup">
          ${['HIGH', 'MEDIUM', 'LOW'].map((p) => html`<label class="check"><input type="radio" name="priority" value=${p} .checked=${this.priority === p}
            @change=${() => (this.priority = p)} /> ${p.charAt(0) + p.slice(1).toLowerCase()}</label>`)}</div></fieldset>
        ${!lead
          ? html`${canAssign
              ? html`<label class="field"><span class="label">Assign to</span><select name="assigned_to" aria-invalid=${this.errors.assigned_to ? 'true' : 'false'}>
                  <option value="">Unassigned</option>
                  ${this.assignees.map((u) => html`<option value=${u.id} ?selected=${u.id === this.me?.id}>${u.id === this.me?.id ? `Me (${u.display_name})` : u.display_name}</option>`)}
                </select>${this.errors.assigned_to ? html`<span class="error">⚠ ${this.errors.assigned_to}</span>` : nothing}</label>`
              : html`<p class="small muted">Assigned to you.</p>`}
            <label class="field"><span class="label">First note</span><textarea name="initial_note" maxlength="10000"></textarea></label>`
          : nothing}
        <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      </form>
      <div slot="actions"><button class="btn" @click=${() => this.close()}>Cancel</button>
        <button class="btn primary" form="lf" ?disabled=${this.busy}>${this.busy ? 'Saving…' : lead ? 'Save' : 'Create lead →'}</button></div>
    </vs-drawer>`;
  }
}
customElements.define('vs-lead-form', VsLeadForm);
