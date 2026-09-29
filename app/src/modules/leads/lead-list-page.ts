import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { Lead, LeadStatus, OffsetMeta, UserRef } from '../../core/api/types.js';
import { lookupOptions } from '../../core/api/lookups.js';
import { formatAge, formatRelative } from '../../core/format/format.js';
import { statusLabel, t } from '../../core/i18n/strings.js';
import { navigate } from '../../core/router/next.js';
import { toast } from '../../design-system/components.js';
import { icon } from '../../design-system/icons.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { loadAssignees } from './assignees.js';
import { LookupAwareElement } from './base.js';
import { activeFilterCount, emptyFilters, filtersToQuery, parseFilters, type LeadFilters } from './filters.js';
import './lead-form.js';
import './status-dialog.js';
import { OPEN_STATUSES } from './transitions.js';

const ALL_STATUSES: LeadStatus[] = [...OPEN_STATUSES, 'WON', 'LOST'];

/** Leads list and board (09 §4.3). Filters sync to the URL and map 1:1 to the API (08 §8.2). */
export class VsLeadListPage extends LookupAwareElement {
  static override properties = {
    filters: { state: true }, leads: { state: true }, meta: { state: true }, loading: { state: true }, problem: { state: true },
    view: { state: true }, formOpen: { state: true }, assignees: { state: true }, spamCount: { state: true },
    moveLead: { state: true }, moveTo: { state: true }, filtersOpen: { state: true },
  };
  declare filters: LeadFilters;
  declare leads: Lead[];
  declare meta: OffsetMeta | null;
  declare loading: boolean;
  declare problem: ApiProblem | null;
  declare view: 'list' | 'board';
  declare formOpen: boolean;
  declare assignees: UserRef[];
  declare spamCount: number;
  declare moveLead: Lead | null;
  declare moveTo: LeadStatus | '';
  declare filtersOpen: boolean;
  private seq = 0;
  private searchTimer: number | undefined;
  private onPop = () => {
    this.filters = parseFilters(window.location.search);
    void this.load();
  };
  static override styles = [
    ...shared, pageStyles, tableStyles,
    css`
      .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; }
      .filters .search { flex: 1 1 280px; }
      .filters select { min-width: 140px; }
      .filters-toggle { display: none; }
      @media (max-width: 767px) {
        .filters-toggle { display: inline-flex; }
        .filters:not(.open) > :not(.search) { display: none; }
        .filters .field { flex: 1 1 140px; }
      }
      .sub { display: block; font-size: 12px; color: var(--vs-ink-muted); }
      .overdue { color: var(--vs-warning); font-weight: 600; }
      .board { display: grid; grid-template-columns: repeat(5, minmax(220px, 1fr)); gap: 12px; overflow-x: auto; }
      .col { background: var(--vs-cream); border-radius: 8px; padding: 8px; min-height: 200px; display: flex; flex-direction: column; gap: 8px; }
      .col.drop { outline: 2px dashed var(--vs-copper); }
      .col h2 { font: 600 11px/16px var(--vs-font-sans); letter-spacing: .14em; text-transform: uppercase; padding: 4px; color: var(--vs-ink-muted); }
      .tile { background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: 8px; padding: 10px; display: flex; flex-direction: column; gap: 4px; }
      .tile a { color: var(--vs-ink); font-weight: 600; text-decoration: none; }
      .seg { display: inline-flex; border: 1px solid var(--vs-line); border-radius: 2px; }
      .seg button { border: 0; background: var(--vs-surface); min-height: 40px; padding: 0 14px; cursor: pointer; font: 600 13px var(--vs-font-sans); color: var(--vs-ink-muted); }
      .seg button[aria-pressed='true'] { background: var(--vs-cream); color: var(--vs-ink); }
    `,
  ];

  constructor() {
    super();
    this.filters = parseFilters(window.location.search);
    this.leads = [];
    this.meta = null;
    this.loading = true;
    this.problem = null;
    this.view = 'list';
    this.formOpen = new URLSearchParams(window.location.search).get('new') === '1';
    this.assignees = [];
    this.spamCount = 0;
    this.moveLead = null;
    this.moveTo = '';
    this.filtersOpen = false;
  }

  override connectedCallback() {
    super.connectedCallback();
    window.addEventListener('popstate', this.onPop);
    void this.load();
    void loadAssignees(this.me).then((a) => (this.assignees = a));
    void this.loadSpamCount();
  }
  override disconnectedCallback() {
    window.removeEventListener('popstate', this.onPop);
    super.disconnectedCallback();
  }

  private async loadSpamCount() {
    if (!this.can('lead.update', 'ALL')) return;
    try {
      const r = await api.get<Lead[]>('/api/v1/leads', { spam_status: 'SUSPECTED', page_size: 1 });
      this.spamCount = (r.meta as unknown as OffsetMeta).total ?? 0;
    } catch {
      this.spamCount = 0;
    }
  }

  private async load() {
    const seq = ++this.seq;
    this.loading = true;
    this.problem = null;
    const query = filtersToQuery(this.view === 'board' ? { ...this.filters, open: true, status: [], page: 1, page_size: 100 } : this.filters);
    try {
      const r = await api.get<Lead[]>('/api/v1/leads', query);
      if (seq !== this.seq) return;
      this.leads = r.data;
      this.meta = r.meta as unknown as OffsetMeta;
    } catch (e) {
      if (seq === this.seq) this.problem = e as ApiProblem;
    } finally {
      if (seq === this.seq) this.loading = false;
    }
  }

  /** Update filters, push them to the URL (shareable, back-button friendly) and reload. */
  private setFilters(patch: Partial<LeadFilters>, resetPage = true) {
    this.filters = { ...this.filters, ...patch, ...(resetPage && !('page' in patch) ? { page: 1 } : {}) };
    const qs = filtersToQuery(this.filters).toString();
    history.pushState(null, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`);
    void this.load();
  }

  private selectFilter(key: 'status' | 'project_type' | 'budget_range' | 'source' | 'priority', label: string, options: Array<{ value: string; label: string }>) {
    const value = this.filters[key][0] ?? '';
    return html`<label class="field"><span class="label">${label}</span><select @change=${(e: Event) => {
      const v = (e.target as HTMLSelectElement).value;
      this.setFilters({ [key]: v ? [v] : [] } as Partial<LeadFilters>);
    }}><option value="">All</option>${options.map((o) => html`<option value=${o.value} ?selected=${o.value === value}>${o.label}</option>`)}</select></label>`;
  }

  private lk(category: string) {
    return lookupOptions(this.lookups, category).map((o) => ({ value: o.code, label: o.label }));
  }

  private renderFilters() {
    const f = this.filters;
    const ownerValue = f.assigned_to[0] ?? '';
    return html`<button class="btn small filters-toggle" aria-expanded=${this.filtersOpen ? 'true' : 'false'} @click=${() => (this.filtersOpen = !this.filtersOpen)}>
        Filters${activeFilterCount(f) ? ` (${activeFilterCount(f)})` : ''}</button>
    <div class="filters ${this.filtersOpen ? 'open' : ''}" role="search">
      <label class="field search"><span class="label">Search</span>
        <input type="search" placeholder="Name, phone, email, VS-L-…" .value=${f.q} @input=${(e: Event) => {
          const q = (e.target as HTMLInputElement).value;
          window.clearTimeout(this.searchTimer);
          this.searchTimer = window.setTimeout(() => this.setFilters({ q }), 300);
        }} /></label>
      ${this.view === 'list' ? this.selectFilter('status', 'Status', ALL_STATUSES.map((s) => ({ value: s, label: statusLabel(s) }))) : nothing}
      <label class="field"><span class="label">Owner</span><select @change=${(e: Event) => {
        const v = (e.target as HTMLSelectElement).value;
        this.setFilters({ assigned_to: v ? [v] : [] });
      }}>
        <option value="">Anyone</option><option value="me" ?selected=${ownerValue === 'me'}>Me</option><option value="unassigned" ?selected=${ownerValue === 'unassigned'}>Unassigned</option>
        ${this.assignees.filter((a) => a.id !== this.me?.id).map((a) => html`<option value=${a.id} ?selected=${ownerValue === a.id}>${a.display_name}</option>`)}
      </select></label>
      ${this.selectFilter('project_type', 'Type', this.lk('PROJECT_TYPE'))}
      ${this.selectFilter('budget_range', 'Budget', this.lk('BUDGET_RANGE'))}
      ${this.selectFilter('source', 'Source', this.lk('LEAD_SOURCE'))}
      <label class="field"><span class="label">Follow-up</span><select @change=${(e: Event) => this.setFilters({ follow_up: (e.target as HTMLSelectElement).value as LeadFilters['follow_up'] })}>
        ${[['', 'Any'], ['overdue', 'Overdue'], ['today', 'Today'], ['this_week', 'This week'], ['none', 'None']].map(([v, l]) => html`<option value=${v} ?selected=${f.follow_up === v}>${l}</option>`)}
      </select></label>
      <label class="field"><span class="label">Sort</span><select @change=${(e: Event) => this.setFilters({ sort: (e.target as HTMLSelectElement).value })}>
        ${[['-created_on', 'Newest'], ['created_on', 'Oldest'], ['next_follow_up_on', 'Next follow-up'], ['-status_changed_on', 'Recently moved'], ['name', 'Name'], ['-priority', 'Priority']]
          .map(([v, l]) => html`<option value=${v} ?selected=${f.sort === v}>${l}</option>`)}
      </select></label>
    </div>
    <div class="row">
      ${f.spam_status.includes('SUSPECTED') ? html`<span class="chip warning">Spam review <button aria-label="Clear spam filter" @click=${() => this.setFilters({ spam_status: [] })}>✕</button></span>` : nothing}
      ${f.consent === 'withdrawn' ? html`<span class="chip">Do not contact <button aria-label="Clear" @click=${() => this.setFilters({ consent: '' })}>✕</button></span>` : nothing}
      ${f.open ? html`<span class="chip">Open only <button aria-label="Clear" @click=${() => this.setFilters({ open: false })}>✕</button></span>` : nothing}
      ${this.spamCount && !f.spam_status.length ? html`<button class="chip warning" @click=${() => this.setFilters({ spam_status: ['SUSPECTED'] })}>Spam review (${this.spamCount})</button>` : nothing}
      ${activeFilterCount(f) || f.q ? html`<button class="btn ghost small" @click=${() => { this.filters = emptyFilters(); this.setFilters({}); }}>Clear all</button>` : nothing}
      ${this.can('lead.restore') ? html`<label class="check small"><input type="checkbox" .checked=${f.deleted_only} @change=${(e: Event) => this.setFilters({ deleted_only: (e.target as HTMLInputElement).checked })} /> Deleted only</label>` : nothing}
    </div>`;
  }

  private renderTable() {
    if (!this.leads.length)
      return html`<div class="card"><vs-empty-state heading=${activeFilterCount(this.filters) || this.filters.q ? 'No leads match these filters.' : t('empty.leads')}>
        ${this.can('lead.create') ? html`<button class="btn primary" @click=${() => (this.formOpen = true)}>+ New lead</button>` : nothing}</vs-empty-state></div>`;
    const spamView = this.filters.spam_status.includes('SUSPECTED');
    return html`<div class="table-wrap"><table class="cards">
      <thead><tr><th scope="col">Lead</th><th scope="col">Project</th><th scope="col">Status</th><th scope="col">Next</th><th scope="col">Owner</th><th scope="col">Source</th><th scope="col">Age</th>${spamView ? html`<th scope="col">Review</th>` : nothing}</tr></thead>
      <tbody>${this.leads.map(
        (l) => html`<tr class="clickable" @click=${(e: Event) => { if (!(e.target as HTMLElement).closest('button,a')) navigate(`/leads/${l.id}`); }}>
          <td data-label="Lead"><a class="primary-cell" href=${`/leads/${l.id}`}>${l.name}</a>
            ${l.duplicate_status === 'SUSPECTED' ? html` <span class="chip warning" title="Possible duplicate">⚠ dup</span>` : nothing}
            <span class="sub">${l.lead_number}${l.locality ? ` · ${l.locality}` : l.city ? ` · ${l.city}` : ''}${l.budget_range ? ` · ${l.budget_range.label}` : ''}</span></td>
          <td data-label="Project">${l.project_type?.label ?? '—'}</td>
          <td data-label="Status"><vs-status-pill status=${l.status}></vs-status-pill></td>
          <td data-label="Next" class=${l.is_follow_up_overdue ? 'overdue' : ''}>${l.next_follow_up_on ? html`${l.is_follow_up_overdue ? 'Overdue · ' : ''}${formatRelative(l.next_follow_up_on)}` : '—'}</td>
          <td data-label="Owner">${l.assigned_to?.display_name ?? html`<span class="muted">Unassigned</span>`}</td>
          <td data-label="Source">${l.source?.label ?? '—'}</td>
          <td data-label="Age">${formatAge(l.created_on)}</td>
          ${spamView ? html`<td data-label="Review"><div class="row">
            <button class="btn small" @click=${() => this.resolveSpam(l, 'NOT_SPAM')}>Not spam</button>
            <button class="btn small danger" @click=${() => this.resolveSpam(l, 'CONFIRMED_SPAM')}>Confirm spam</button></div></td>` : nothing}
        </tr>`,
      )}</tbody></table></div>
      ${this.meta ? html`<vs-pagination .page=${this.meta.page} .totalPages=${this.meta.total_pages} .total=${this.meta.total} .pageSize=${this.meta.page_size}
        @page-change=${(e: CustomEvent<number>) => this.setFilters({ page: e.detail }, false)}></vs-pagination>` : nothing}`;
  }

  private async resolveSpam(lead: Lead, resolution: 'NOT_SPAM' | 'CONFIRMED_SPAM') {
    try {
      await api.post(`/api/v1/leads/${lead.id}/spam-resolution`, { resolution }, { ifMatch: lead.version });
      toast(resolution === 'NOT_SPAM' ? 'Released to the pipeline' : 'Marked as spam', 'success');
      void this.load();
      void this.loadSpamCount();
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  /** Board: drag = status change; the "Move" menu is the keyboard alternative (AX-09). */
  private renderBoard() {
    const canMove = this.can('lead.status.change');
    return html`<div class="board" role="list">${OPEN_STATUSES.map((s) => {
      const items = this.leads.filter((l) => l.status === s);
      return html`<section class="col" role="listitem" aria-label=${`${statusLabel(s)}, ${items.length} leads`}
        @dragover=${(e: DragEvent) => { if (canMove) { e.preventDefault(); (e.currentTarget as HTMLElement).classList.add('drop'); } }}
        @dragleave=${(e: DragEvent) => (e.currentTarget as HTMLElement).classList.remove('drop')}
        @drop=${(e: DragEvent) => { (e.currentTarget as HTMLElement).classList.remove('drop'); const id = e.dataTransfer?.getData('text/plain'); const lead = this.leads.find((l) => l.id === id); if (lead) this.startMove(lead, s); }}>
        <h2>${statusLabel(s)} · ${items.length}</h2>
        ${items.map((l) => html`<article class="tile" draggable=${canMove ? 'true' : 'false'} @dragstart=${(e: DragEvent) => e.dataTransfer?.setData('text/plain', l.id)}>
          <a href=${`/leads/${l.id}`}>${l.name}</a>
          <span class="small muted">${l.lead_number} · ${l.project_type?.label ?? 'No project type'}</span>
          <span class="small">${l.assigned_to?.display_name ?? 'Unassigned'}</span>
          ${canMove && l.allowed_transitions?.length ? html`<label class="small"><span class="sr-only">Move ${l.name} to</span>
            <select @change=${(e: Event) => { const v = (e.target as HTMLSelectElement).value as LeadStatus; (e.target as HTMLSelectElement).value = ''; if (v) this.startMove(l, v); }}>
              <option value="">Move to…</option>${l.allowed_transitions.map((tr) => html`<option value=${tr}>${statusLabel(tr)}</option>`)}</select></label>` : nothing}
        </article>`)}
      </section>`;
    })}</div>`;
  }

  private startMove(lead: Lead, to: LeadStatus) {
    if (lead.status === to) return;
    if (lead.allowed_transitions && !lead.allowed_transitions.includes(to)) {
      toast(`${statusLabel(lead.status)} → ${statusLabel(to)} isn't allowed`, 'error');
      return;
    }
    this.moveLead = lead;
    this.moveTo = to;
  }

  override render() {
    return html`<div class="page">
      <div class="page-head">
        <div><p class="eyebrow">Pipeline</p><h1 class="display">Leads</h1></div><span class="spacer"></span>
        <div class="seg" role="group" aria-label="View">
          <button aria-pressed=${this.view === 'board' ? 'true' : 'false'} @click=${() => { this.view = 'board'; void this.load(); }}>Board</button>
          <button aria-pressed=${this.view === 'list' ? 'true' : 'false'} @click=${() => { this.view = 'list'; void this.load(); }}>List</button>
        </div>
        <vs-can permission="lead.create"><button class="btn primary" @click=${() => (this.formOpen = true)}>${icon('plus')} New lead</button></vs-can>
      </div>
      ${this.renderFilters()}
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${this.loading && !this.leads.length ? html`<div class="card"><vs-skeleton rows="8"></vs-skeleton></div>` : this.view === 'board' ? this.renderBoard() : this.renderTable()}
      <vs-lead-form .open=${this.formOpen} .assignees=${this.assignees} @close=${() => (this.formOpen = false)}></vs-lead-form>
      <vs-status-dialog .open=${Boolean(this.moveLead)} .lead=${this.moveLead} .to=${this.moveTo}
        @close=${() => { this.moveLead = null; this.moveTo = ''; }} @lead-updated=${() => void this.load()} @conflict=${() => void this.load()}></vs-status-dialog>
    </div>`;
  }
}
customElements.define('vs-lead-list-page', VsLeadListPage);
