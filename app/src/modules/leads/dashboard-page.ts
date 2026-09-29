import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { Lead, LeadActivity, LeadSummary, UserRef } from '../../core/api/types.js';
import { formatAge, formatRelative, getUserTimeZone } from '../../core/format/format.js';
import { statusLabel } from '../../core/i18n/strings.js';
import { navigate } from '../../core/router/next.js';
import { toast } from '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import './activity-dialog.js';
import { loadAssignees } from './assignees.js';
import { LookupAwareElement } from './base.js';
import './lead-form.js';
import { OPEN_STATUSES } from './transitions.js';

const PERIODS = [['today', 'Today'], ['7d', 'Last 7 days'], ['30d', 'Last 30 days'], ['90d', 'Last 90 days']] as const;

function greeting(tz: string): string {
  const hour = Number(new Intl.DateTimeFormat('en-GB', { timeZone: tz, hour: '2-digit', hourCycle: 'h23' }).format(new Date()));
  return hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
}

/** Lead dashboard (09 §4.3, LEAD-014). Every metric is scoped by lead.read on the server. */
export class VsDashboardPage extends LookupAwareElement {
  static override properties = {
    period: { state: true }, summary: { state: true }, followUps: { state: true }, unassigned: { state: true }, recent: { state: true },
    problem: { state: true }, assignees: { state: true }, formOpen: { state: true }, completing: { state: true },
  };
  declare period: string;
  declare summary: LeadSummary | null;
  declare followUps: LeadActivity[] | null;
  declare unassigned: Lead[] | null;
  declare recent: Lead[] | null;
  declare problem: ApiProblem | null;
  declare assignees: UserRef[];
  declare formOpen: boolean;
  declare completing: LeadActivity | null;
  static override styles = [
    ...shared, pageStyles, tableStyles,
    css`
      .kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
      .two { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
      .pipeline { display: flex; gap: 4px; flex-wrap: wrap; }
      .pipeline a { flex: 1 1 120px; text-decoration: none; color: var(--vs-ink); padding: 12px; border-radius: 8px; border: 1px solid var(--vs-line); background: var(--vs-surface); display: flex; flex-direction: column; gap: 4px; }
      .pipeline a:hover { border-color: var(--vs-copper); }
      .pipeline .n { font-family: var(--vs-font-serif); font-size: 32px; line-height: 36px; font-variant-numeric: lining-nums tabular-nums; }
      ul.list { list-style: none; margin: 0; padding: 0; }
      ul.list li { display: flex; gap: 12px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--vs-line); }
      ul.list li:last-child { border-bottom: 0; }
      .overdue { color: var(--vs-warning); font-weight: 600; }
      section h2 { margin-bottom: 8px; }
      @media (max-width: 1199px) { .kpis { grid-template-columns: repeat(3, 1fr); } }
      @media (max-width: 767px) { .kpis { grid-template-columns: repeat(2, 1fr); } .two { grid-template-columns: 1fr; } .followups { order: -1; } }
    `,
  ];

  constructor() {
    super();
    this.period = '30d';
    this.summary = null;
    this.followUps = null;
    this.unassigned = null;
    this.recent = null;
    this.problem = null;
    this.assignees = [];
    this.formOpen = false;
    this.completing = null;
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.loadAll();
    void loadAssignees(this.me).then((a) => (this.assignees = a));
  }

  private async loadAll() {
    this.problem = null;
    const tasks: Array<Promise<unknown>> = [
      api.get<LeadSummary>('/api/v1/leads/summary', { period: this.period }).then((r) => (this.summary = r.data)),
      api.get<Lead[]>('/api/v1/leads', { page_size: 8 }).then((r) => (this.recent = r.data)),
    ];
    if (this.can('lead_activity.read')) {
      tasks.push(api.get<LeadActivity[]>('/api/v1/activities', { owner: 'me', status: 'PLANNED', limit: 10 }).then((r) => (this.followUps = r.data)));
    }
    if (this.can('lead.assign')) {
      tasks.push(api.get<Lead[]>('/api/v1/leads', { assigned_to: 'unassigned', open: 'true', page_size: 6 }).then((r) => (this.unassigned = r.data)));
    }
    const results = await Promise.allSettled(tasks);
    const failed = results.find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined;
    if (failed) this.problem = failed.reason as ApiProblem;
  }

  private async assign(lead: Lead, userId: string) {
    if (!userId) return;
    try {
      await api.post(`/api/v1/leads/${lead.id}/assign`, { assigned_to: userId }, { ifMatch: lead.version });
      toast(`${lead.name} assigned`, 'success');
      void this.loadAll();
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  private renderKpis() {
    const s = this.summary;
    if (!s) return html`<div class="kpis">${[1, 2, 3, 4, 5].map(() => html`<div class="card"><vs-skeleton rows="2"></vs-skeleton></div>`)}</div>`;
    const prev = s.new_leads.previous_period_count;
    const delta = prev ? Math.round(((s.new_leads.count - prev) / prev) * 100) : null;
    const conv = s.conversion_rate == null ? '—' : `${Math.round(s.conversion_rate * 100)}%`;
    return html`<div class="kpis">
      <vs-kpi-tile label="New leads" .value=${String(s.new_leads.count)} .hint=${delta == null ? 'No previous period' : `${delta >= 0 ? '▲' : '▼'} ${Math.abs(delta)}% vs previous`}></vs-kpi-tile>
      <vs-kpi-tile label="Follow-ups" .value=${String(s.follow_ups.due_today)} hint="due today"><a href="/follow-ups"> View →</a></vs-kpi-tile>
      <vs-kpi-tile label="Overdue" .value=${String(s.follow_ups.overdue)} tone=${s.follow_ups.overdue ? 'warning' : ''} hint=""><a href="/leads?follow_up=overdue">View →</a></vs-kpi-tile>
      <vs-kpi-tile label="Conversion" .value=${conv} .hint=${`${s.closed_in_period.WON} won · ${s.closed_in_period.LOST} lost`}></vs-kpi-tile>
      <vs-kpi-tile label="First contact (median)" .value=${s.median_hours_to_first_contact == null ? '—' : `${s.median_hours_to_first_contact.toFixed(1)} h`} hint="target < 4 h"></vs-kpi-tile>
    </div>`;
  }

  override render() {
    const s = this.summary;
    const name = this.me?.display_name || this.me?.full_name?.split(' ')[0] || '';
    return html`<div class="page">
      <div class="page-head">
        <div><p class="eyebrow">Overview</p><h1 class="display">${greeting(getUserTimeZone())}${name ? `, ${name}` : ''}</h1></div>
        <span class="spacer"></span>
        <label class="field"><span class="sr-only">Period</span><select @change=${(e: Event) => { this.period = (e.target as HTMLSelectElement).value; void this.loadAll(); }}>
          ${PERIODS.map(([v, l]) => html`<option value=${v} ?selected=${v === this.period}>${l}</option>`)}</select></label>
        <vs-can permission="lead.create"><button class="btn primary" @click=${() => (this.formOpen = true)}>+ New lead</button></vs-can>
      </div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${this.renderKpis()}
      <section class="card"><h2 class="eyebrow">Pipeline</h2>
        ${s ? html`<nav class="pipeline" aria-label="Pipeline by status">${OPEN_STATUSES.map((st) => html`<a href=${`/leads?status=${st}`}>
            <span class="small">${statusLabel(st)}</span><span class="n">${s.pipeline[st] ?? 0}</span></a>`)}</nav>` : html`<vs-skeleton rows="2"></vs-skeleton>`}
        ${s?.needs_reassignment ? html`<p class="warning-text small">${s.needs_reassignment} open leads belong to deactivated users and need reassignment.</p>` : nothing}
      </section>
      <div class="two">
        ${this.can('lead_activity.read') ? html`<section class="card followups"><div class="row"><h2 class="eyebrow">My follow-ups</h2><span class="spacer"></span><a href="/follow-ups">See all →</a></div>
          ${!this.followUps ? html`<vs-skeleton rows="3"></vs-skeleton>` : this.followUps.length ? html`<ul class="list">${this.followUps.map((a) => html`<li>
            <div class="spacer"><div class=${a.is_overdue ? 'overdue' : 'strong'}>${formatRelative(a.scheduled_on)}${a.is_overdue ? ' · OVERDUE' : ''} · ${a.subject}</div>
              ${a.lead ? html`<a class="small" href=${`/leads/${a.lead.id}`}>${a.lead.name} · ${a.lead.lead_number}</a>` : nothing}</div>
            <button class="btn small" aria-label=${`Complete ${a.subject}`} @click=${() => (this.completing = a)}>✓</button></li>`)}</ul>`
            : html`<p class="muted">No planned follow-ups. Nicely done.</p>`}
        </section>` : nothing}
        <vs-can permission="lead.assign"><section class="card"><h2 class="eyebrow">Unassigned${s ? ` (${s.unassigned_open})` : ''}</h2>
          ${!this.unassigned ? html`<vs-skeleton rows="3"></vs-skeleton>` : this.unassigned.length ? html`<ul class="list">${this.unassigned.map((l) => html`<li>
            <div class="spacer"><a class="strong" href=${`/leads/${l.id}`}>${l.name}</a><div class="small muted">${l.project_type?.label ?? '—'} · ${l.locality ?? l.city ?? '—'} · ${formatAge(l.created_on)}</div></div>
            <label><span class="sr-only">Assign ${l.name}</span><select @change=${(e: Event) => this.assign(l, (e.target as HTMLSelectElement).value)}>
              <option value="">Assign…</option>${this.assignees.map((u) => html`<option value=${u.id}>${u.display_name}</option>`)}</select></label></li>`)}</ul>`
            : html`<p class="muted">Every open lead has an owner.</p>`}
        </section></vs-can>
      </div>
      <div class="two">
        <section class="card"><h2 class="eyebrow">Recent leads</h2>
          ${!this.recent ? html`<vs-skeleton rows="5"></vs-skeleton>` : this.recent.length ? html`<div class="table-wrap"><table class="cards"><thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Owner</th><th>Age</th></tr></thead>
            <tbody>${this.recent.map((l) => html`<tr class="clickable" @click=${() => navigate(`/leads/${l.id}`)}>
              <td data-label="Name"><a href=${`/leads/${l.id}`}>${l.name}</a><div class="small muted">${l.lead_number}</div></td><td data-label="Type">${l.project_type?.label ?? '—'}</td>
              <td data-label="Status"><vs-status-pill status=${l.status}></vs-status-pill></td><td data-label="Owner">${l.assigned_to?.display_name ?? '—'}</td><td data-label="Age">${formatAge(l.created_on)}</td></tr>`)}</tbody></table></div>`
            : html`<vs-empty-state heading="No leads yet. Share your enquiry form or add one manually."></vs-empty-state>`}
        </section>
        <section class="card"><h2 class="eyebrow">Leads by source</h2>
          ${s ? html`<vs-bar-list .items=${s.by_source.map((b) => ({ label: b.label, value: b.count, href: `/leads?source=${b.code}` }))}></vs-bar-list>` : html`<vs-skeleton rows="4"></vs-skeleton>`}
        </section>
      </div>
      <vs-lead-form .open=${this.formOpen} .assignees=${this.assignees} @close=${() => (this.formOpen = false)}></vs-lead-form>
      <vs-activity-dialog .open=${Boolean(this.completing)} mode="complete" .leadId=${this.completing?.lead_id ?? this.completing?.lead?.id ?? ''} .activity=${this.completing}
        @close=${() => (this.completing = null)} @activity-saved=${() => void this.loadAll()}></vs-activity-dialog>
    </div>`;
  }
}
customElements.define('vs-dashboard-page', VsDashboardPage);
