import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { CursorMeta, LeadActivity } from '../../core/api/types.js';
import { formatRelative } from '../../core/format/format.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { activityTypeLabel } from './activity-dialog.js';
import './activity-dialog.js';
import { LookupAwareElement } from './base.js';

/** Cross-lead "my follow-ups" (08 §9.2 GET /activities?owner=me&status=PLANNED, LEAD-015). */
export class VsFollowupsPage extends LookupAwareElement {
  static override properties = { items: { state: true }, cursor: { state: true }, problem: { state: true }, loading: { state: true }, owner: { state: true }, target: { state: true }, mode: { state: true } };
  declare items: LeadActivity[];
  declare cursor: string | null;
  declare problem: ApiProblem | null;
  declare loading: boolean;
  declare owner: string;
  declare target: LeadActivity | null;
  declare mode: 'complete' | 'cancel';
  static override styles = [...shared, pageStyles, tableStyles, css`.overdue { color: var(--vs-warning); font-weight: 600; }`];

  constructor() {
    super();
    this.items = [];
    this.cursor = null;
    this.problem = null;
    this.loading = true;
    this.owner = 'me';
    this.target = null;
    this.mode = 'complete';
  }
  override connectedCallback() {
    super.connectedCallback();
    void this.load(true);
  }
  private async load(reset: boolean) {
    this.loading = true;
    try {
      const r = await api.get<LeadActivity[]>('/api/v1/activities', { owner: this.owner || undefined, status: 'PLANNED', limit: 50, cursor: reset ? undefined : this.cursor ?? undefined });
      this.items = reset ? r.data : [...this.items, ...r.data];
      const meta = r.meta as unknown as CursorMeta;
      this.cursor = meta.has_more ? meta.next_cursor : null;
    } catch (e) {
      this.problem = e as ApiProblem;
    } finally {
      this.loading = false;
    }
  }
  override render() {
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Work</p><h1 class="display">Follow-ups</h1></div><span class="spacer"></span>
        <label class="field"><span class="label">Owner</span><select @change=${(e: Event) => { this.owner = (e.target as HTMLSelectElement).value; void this.load(true); }}>
          <option value="me">Mine</option>${this.can('lead_activity.read', 'ALL') ? html`<option value="">Everyone I can see</option>` : nothing}</select></label></div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${this.loading && !this.items.length ? html`<div class="card"><vs-skeleton rows="6"></vs-skeleton></div>` : !this.items.length
        ? html`<div class="card"><vs-empty-state heading="No planned follow-ups."></vs-empty-state></div>`
        : html`<div class="table-wrap"><table class="cards"><thead><tr><th>When</th><th>Activity</th><th>Lead</th><th>Owner</th><th><span class="sr-only">Actions</span></th></tr></thead>
          <tbody>${this.items.map((a) => html`<tr>
            <td data-label="When" class=${a.is_overdue ? 'overdue' : ''}>${a.is_overdue ? 'Overdue · ' : ''}${formatRelative(a.scheduled_on)}</td>
            <td data-label="Activity">${activityTypeLabel(a.activity_type)} · ${a.subject}</td>
            <td data-label="Lead">${a.lead ? html`<a href=${`/leads/${a.lead.id}`}>${a.lead.name}</a> <span class="small muted">${a.lead.lead_number}</span>` : '—'}</td>
            <td data-label="Owner">${a.owner?.display_name ?? '—'}</td>
            <td><div class="row"><button class="btn small" @click=${() => { this.mode = 'complete'; this.target = a; }}>Complete</button>
              <button class="btn small ghost" @click=${() => { this.mode = 'cancel'; this.target = a; }}>Cancel</button></div></td></tr>`)}</tbody></table></div>
          ${this.cursor ? html`<button class="btn" @click=${() => this.load(false)}>Load more</button>` : nothing}`}
      <vs-activity-dialog .open=${Boolean(this.target)} .mode=${this.mode} .leadId=${this.target?.lead_id ?? this.target?.lead?.id ?? ''} .activity=${this.target}
        @close=${() => (this.target = null)} @activity-saved=${() => void this.load(true)}></vs-activity-dialog>
    </div>`;
  }
}
customElements.define('vs-followups-page', VsFollowupsPage);
