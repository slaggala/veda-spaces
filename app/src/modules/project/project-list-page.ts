import { css, html, nothing, type TemplateResult } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatDate, formatRelative, humanize } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { projectApi, type Dashboard, type ProjectRow, type Query, type Vocabulary } from './api.js';
import { badgeStyles, PARTY, who } from './labels.js';

const VIEWS: [string, string][] = [['all', 'All authorised'], ['mine', 'My projects'], ['blocked', 'Blocked'], ['action_required', 'Action required'],
  ['site_readiness', 'Site readiness'], ['installation', 'Installation'], ['handover', 'Handover readiness']];

/**
 * Projects (PLB-10, PLB-37): every project the signed-in person may see, with the eight answers staff ask first
 * (project, current stage, owner, next milestone, readiness, blockers, target date, last material change), views and
 * filters, and the accepted quotations waiting to be booked. Never a ranking of people.
 */
export class VsProjectListPage extends SessionElement {
  static override properties = { data: { state: true }, problem: { state: true }, disabled: { state: true }, view: { state: true },
    filters: { state: true }, busy: { state: true }, announcement: { state: true }, vocab: { state: true } };
  declare data: Dashboard | null;
  declare vocab: Vocabulary | null;
  declare problem: ApiProblem | null;
  declare disabled: boolean;
  declare view: string;
  declare filters: Query;
  declare busy: boolean;
  declare announcement: string;

  static override styles = [...shared, pageStyles, tableStyles, badgeStyles, css`
    .views { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .views button[aria-pressed='true'] { border-color: var(--vs-copper-strong); color: var(--vs-copper-text); background: var(--vs-cream); }
    .filters { display: grid; gap: var(--vs-space-3); grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr)); align-items: end; }
    td, th { overflow-wrap: anywhere; }
    td a { font-weight: 600; display: inline-flex; align-items: center; min-height: var(--vs-target); }
    .sub { display: block; font-size: 12px; line-height: 18px; color: var(--vs-ink-muted); }
    ul.problems { margin: 4px 0 0; padding-left: 18px; font-size: 13px; }
  `];

  constructor() {
    super();
    this.data = null;
    this.vocab = null;
    this.problem = null;
    this.disabled = false;
    this.view = 'all';
    this.filters = {};
    this.busy = false;
    this.announcement = '';
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private async load() {
    this.busy = true;
    this.problem = null;
    try {
      const [r, v] = await Promise.all([projectApi.list({ view: this.view, ...Object.fromEntries(Object.entries(this.filters).filter(([, v]) => v)) }),
        this.vocab ? null : projectApi.vocabulary()]);
      this.data = r.data;
      if (v) this.vocab = v.data;
      this.announcement = `${r.data.projects.length} project${r.data.projects.length === 1 ? '' : 's'} shown.`;
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404 && p.code === 'NOT_FOUND') this.disabled = true;
      else this.problem = p;
    } finally { this.busy = false; }
  }

  private setView(v: string) {
    this.view = v;
    void this.load();
  }

  private applyFilters(e: Event) {
    e.preventDefault();
    const f = new FormData(e.target as HTMLFormElement);
    this.filters = Object.fromEntries([...f.entries()].map(([k, v]) => [k, String(v).trim()]).filter(([, v]) => v));
    void this.load();
  }

  private async book(quotationId: string, propertyId: string) {
    this.problem = null;
    try {
      const r = await projectApi.book(quotationId, propertyId);
      navigate(`/projects/${r.data.id}`);
    } catch (e) { this.problem = e as ApiProblem; }
  }

  private readiness(r: ProjectRow): TemplateResult {
    const x = r.readiness;
    if (!x) return html`<span class="badge ok">Handed over</span>`;
    if (x.awaiting_approval) return html`<span class="badge action">Awaiting approval</span>`;
    if (x.allowed) return html`<span class="badge ok">Ready for ${x.next_stage_label}</span>`;
    return html`<span class="badge warn">${x.blocker_count} to clear</span><span class="sub">before ${x.next_stage_label}${x.risk === 'HIGH' ? ' (high risk)' : ''}</span>`;
  }

  private blockers(r: ProjectRow): TemplateResult {
    const b = r.blockers;
    if (!b.gating && !b.informational) return html`<span class="muted">None</span>`;
    return html`${b.gating ? html`<span class="badge gating">${b.gating} gating</span>` : nothing}
      ${b.informational ? html`<span class="badge info">${b.informational} for information</span>` : nothing}
      ${b.customer_actions ? html`<span class="sub">${b.customer_actions} waiting for the ${PARTY.CUSTOMER.toLowerCase()}</span>` : nothing}`;
  }

  private row(r: ProjectRow): TemplateResult {
    const m = r.next_milestone;
    return html`<tr>
      <td data-label="Project"><a href=${`/projects/${r.id}`} @click=${(e: Event) => { e.preventDefault(); navigate(`/projects/${r.id}`); }}>${r.project_number}</a>
        <span class="sub">${r.property.property_number}${r.property.locality ? ` · ${r.property.locality}` : ''}</span></td>
      <td data-label="Current stage">${r.stage.label}<span class="sub">Stage ${r.stage.sequence} of ${r.stage.of}</span></td>
      <td data-label="Owner">${who(r.owner, 'No project owner')}<span class="sub">Next: ${humanize(r.next_action_owner.responsibility)} · ${who(r.next_action_owner.person, 'unassigned')}</span></td>
      <td data-label="Next milestone">${m ? html`${m.label}<span class="sub">${m.planned_date ? formatDate(m.planned_date) : 'Not planned'}${m.overdue ? ' · past its planned date' : ''}</span>` : html`<span class="muted">None planned</span>`}</td>
      <td data-label="Readiness">${this.readiness(r)}</td>
      <td data-label="Blockers">${this.blockers(r)}</td>
      <td data-label="Target date">${r.target_date ? formatDate(r.target_date) : html`<span class="muted">—</span>`}</td>
      <td data-label="Last material change">${r.last_material_change ? formatRelative(r.last_material_change) : '—'}</td>
    </tr>`;
  }

  private renderBookable(d: Dashboard): TemplateResult | typeof nothing {
    if (!d.bookable.length) return nothing;
    return html`<section class="stack" aria-labelledby="bookable-h">
      <h2 id="bookable-h">Accepted quotations waiting to be booked</h2>
      <p class="small muted">A project is created only from an accepted quotation; it references the accepted baseline and never changes it.</p>
      <div class="table-wrap" tabindex="0" role="region" aria-label="Accepted quotations, scrolls sideways on small screens"><table class="cards">
        <caption class="sr-only">Accepted quotations without a project</caption>
        <thead><tr><th scope="col">Quotation</th><th scope="col">Accepted</th><th scope="col">Can it be booked?</th><th scope="col"><span class="sr-only">Action</span></th></tr></thead>
        <tbody>${d.bookable.map((b) => html`<tr>
          <td data-label="Quotation">${b.label}</td>
          <td data-label="Accepted">${b.decided_on ? formatRelative(b.decided_on) : '—'}</td>
          <td data-label="Can it be booked?">${b.problems.length ? html`<span class="badge warn">Not yet</span><ul class="problems">${b.problems.map((x) => html`<li>${x.message}</li>`)}</ul>` : html`<span class="badge ok">Yes</span>`}</td>
          <td data-label="Action">${b.problems.length ? nothing : html`<button class="btn" @click=${() => this.book(b.quotation_id, b.property_id)}>Book ${b.quotation_number} as a project</button>`}</td>
        </tr>`)}</tbody></table></div>
    </section>`;
  }

  private renderFilters(d: Dashboard): TemplateResult {
    const f = this.filters;
    const stages = [...new Map(d.projects.map((r) => [r.stage.code, r.stage.label])).entries()];
    return html`<form class="filters" role="search" aria-label="Filter projects" @submit=${this.applyFilters}>
      <label class="field"><span class="label">Search</span><input name="q" .value=${f.q ?? ''} placeholder="Project, quotation or property reference" maxlength="40"></label>
      <label class="field"><span class="label">Stage</span><select name="stage"><option value="">Any stage</option>
        ${(this.vocab ? this.vocab.stages.map((s) => [s.code, s.label]) : stages).map(([c, l]) => html`<option value=${c} ?selected=${f.stage === c}>${l}</option>`)}</select></label>
      <label class="field"><span class="label">Readiness</span><select name="readiness"><option value="">Any</option>
        ${[['ready', 'Ready to move'], ['blocked', 'Something to clear'], ['awaiting_approval', 'Awaiting approval']].map(([v, l]) => html`<option value=${v} ?selected=${f.readiness === v}>${l}</option>`)}</select></label>
      <label class="field"><span class="label">Blockers</span><select name="blocker"><option value="">Any</option>
        ${[['gating', 'Gating blocker open'], ['any', 'Any open issue'], ['none', 'No open issue']].map(([v, l]) => html`<option value=${v} ?selected=${f.blocker === v}>${l}</option>`)}</select></label>
      <label class="field"><span class="label">Milestones</span><select name="milestone"><option value="">Any</option>
        ${[['overdue', 'Past a planned date'], ['planned', 'Next one planned'], ['none', 'None open']].map(([v, l]) => html`<option value=${v} ?selected=${f.milestone === v}>${l}</option>`)}</select></label>
      <label class="field"><span class="label">Handover</span><select name="handover"><option value="">Any</option>
        ${[['ready', 'Ready for handover'], ['not_ready', 'Not ready']].map(([v, l]) => html`<option value=${v} ?selected=${f.handover === v}>${l}</option>`)}</select></label>
      <div class="row"><button class="btn" type="submit">Apply filters</button>
        <button class="btn ghost" type="button" @click=${() => { this.filters = {}; void this.load(); }}>Clear</button></div>
    </form>`;
  }

  override render() {
    if (this.disabled) {
      return html`<div class="page"><h1 class="title" id="page-title" tabindex="-1">Projects</h1>
        <vs-empty-state heading="Project lifecycle is not enabled in this environment."></vs-empty-state></div>`;
    }
    const d = this.data;
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Operations</p><h1 class="title" id="page-title" tabindex="-1">Projects</h1></div></div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${d && d.lifecycle.status !== 'APPROVED' ? html`<vs-banner kind="warning"><strong>Lifecycle ${d.lifecycle.version} is a proposal.</strong>
        The owner has not recorded the lifecycle policy (${Object.values(d.policy.decisions).filter((x) => !x.decided).length} decisions open):
        high-risk moves (scope freeze, production release, installation, ready for handover, handover) stay refused until they are recorded.</vs-banner>` : nothing}
      <div class="views" role="group" aria-label="Project views">${VIEWS.map(([v, label]) => html`<button class="btn small" aria-pressed=${this.view === v ? 'true' : 'false'}
        @click=${() => this.setView(v)}>${label}${d ? html` <span class="muted">(${d.counts[v] ?? 0})</span>` : nothing}</button>`)}</div>
      ${d ? this.renderFilters(d) : nothing}
      ${!d ? html`<vs-skeleton rows="6"></vs-skeleton>` : d.projects.length === 0 ? html`<vs-empty-state heading="No projects in this view."></vs-empty-state>`
        : html`<div class="table-wrap" tabindex="0" role="region" aria-label="Projects, scrolls sideways on small screens"><table class="cards">
          <caption class="sr-only">Projects in the ${VIEWS.find(([v]) => v === this.view)?.[1].toLowerCase()} view</caption>
          <thead><tr><th scope="col">Project</th><th scope="col">Current stage</th><th scope="col">Owner</th><th scope="col">Next milestone</th>
            <th scope="col">Readiness</th><th scope="col">Blockers</th><th scope="col">Target date</th><th scope="col">Last material change</th></tr></thead>
          <tbody>${d.projects.map((r) => this.row(r))}</tbody></table></div>`}
      ${d ? this.renderBookable(d) : nothing}
      <div class="sr-only" role="status" aria-live="polite">${this.busy ? 'Loading projects…' : this.announcement}</div>
    </div>`;
  }
}
customElements.define('vs-project-list-page', VsProjectListPage);
