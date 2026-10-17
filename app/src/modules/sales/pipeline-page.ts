import { css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatRelative } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import '../../design-system/components.js';
import { icon } from '../../design-system/icons.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { salesApi, type PipelineMeta, type PipelineRow, type StatusGroup } from './api.js';
import { ATTENTION, attentionLabel, CHANNELS, channelLabel, OWNER_FILTERS, quotedText, salesStyles, stageLabel, stagePill, STAGES, STATUS_GROUPS } from './labels.js';

type Load = 'loading' | 'ready' | 'off' | 'forbidden' | 'failed';
const LIMIT = 25;

/**
 * /sales — the sales pipeline (SCA-006): one row per lead in the signed-in person's scope, with the stage the records
 * prove, the facts behind it, who owns it, the follow-up state and what the customer is expected to do. Every value is
 * the server's; filters are re-requested, never applied here, so a filter never changes what a stage means.
 */
export class VsSalesPipelinePage extends SessionElement {
  static override properties = {
    rows: { state: true }, meta: { state: true }, load: { state: true }, problem: { state: true }, status: { state: true }, stage: { state: true },
    attention: { state: true }, channel: { state: true }, owner: { state: true }, q: { state: true }, page: { state: true },
  };
  declare rows: PipelineRow[] | null;
  declare meta: PipelineMeta | null;
  declare load: Load;
  declare problem: ApiProblem | null;
  declare status: StatusGroup;
  declare stage: string;
  declare attention: string;
  declare channel: string;
  declare owner: string;
  declare q: string;
  declare page: number;
  private focused = false;

  static override styles = [...shared, pageStyles, tableStyles, salesStyles, css`
    .filters { display: grid; gap: var(--vs-space-3); grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr)); align-items: end; }
    .group { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .group button[aria-pressed='true'] { background: var(--vs-ink); color: var(--vs-surface); border-color: var(--vs-ink); }
    .counts { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); list-style: none; margin: 0; padding: 0; }
    .counts button { min-height: var(--vs-target); padding: 0 var(--vs-space-3); border: 1px solid var(--vs-line); border-radius: var(--vs-radius-pill); background: var(--vs-surface); font: 500 13px/18px var(--vs-font-sans); color: var(--vs-ink); cursor: pointer; }
    .counts button[aria-pressed='true'] { background: var(--vs-ink); color: var(--vs-surface); border-color: var(--vs-ink); }
    .counts .n { font-weight: 700; margin-left: 4px; font-variant-numeric: tabular-nums; }
    td a.lead { font-weight: 600; display: inline-flex; align-items: center; min-height: var(--vs-target); min-width: var(--vs-target); white-space: nowrap; }
    td, th { overflow-wrap: anywhere; vertical-align: top; }
    .sub { display: block; font-size: 12px; line-height: 18px; color: var(--vs-ink-muted); }
    .cell { display: flex; flex-direction: column; gap: 2px; align-items: flex-start; min-width: 0; }
    .note { font-size: 13px; line-height: 20px; color: var(--vs-ink-muted); max-width: 72ch; }
    .search { display: flex; gap: var(--vs-space-2); align-items: flex-end; }
    .search label { flex: 1; }
    @media (max-width: 767px) {
      table.cards td { align-items: flex-start; }
      table.cards td::before { flex: none; width: 96px; }
      table.cards td > .cell { align-items: flex-end; text-align: right; flex: 1; }
      table.cards td > .cell .attention { justify-content: flex-end; }
    }
  `];

  constructor() {
    super();
    this.rows = null;
    this.meta = null;
    this.load = 'loading';
    this.problem = null;
    this.status = 'open';
    this.stage = '';
    this.attention = '';
    this.channel = '';
    this.owner = '';
    this.q = '';
    this.page = 1;
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.fetch();
  }

  private async fetch() {
    this.load = 'loading';
    this.problem = null;
    this.rows = null;
    try {
      const r = await salesApi.pipeline({ status: this.status, stage: this.stage, attention: this.attention, channel: this.channel, owner: this.owner,
        q: this.q.trim(), page: this.page, limit: LIMIT });
      this.rows = r.data;
      this.meta = r.meta as unknown as PipelineMeta;
      this.load = 'ready';
      if (!this.focused) {
        this.focused = true;
        await this.updateComplete;
        this.renderRoot.querySelector<HTMLElement>('#page-title')?.focus();
      }
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404) this.load = 'off';
      else if (p.status === 403) this.load = 'forbidden';
      else { this.problem = p; this.load = 'failed'; }
    }
  }

  private set(patch: Partial<Pick<VsSalesPipelinePage, 'status' | 'stage' | 'attention' | 'channel' | 'owner' | 'q' | 'page'>>) {
    Object.assign(this, { page: 1 }, patch);
    void this.fetch();
  }

  private value(e: Event): string { return (e.target as HTMLInputElement | HTMLSelectElement).value; }

  private renderFilters() {
    return html`<form class="stack" role="search" aria-label="Pipeline filters" @submit=${(e: Event) => { e.preventDefault(); this.set({}); }}>
      <div class="group" role="group" aria-label="Status">${STATUS_GROUPS.map(([code, label]) => html`<button type="button" class="btn" aria-pressed=${this.status === code ? 'true' : 'false'}
        @click=${() => this.set({ status: code as StatusGroup })}>${label}</button>`)}</div>
      <div class="filters">
        <label class="field"><span class="label">Stage</span><select name="stage" .value=${this.stage} @change=${(e: Event) => this.set({ stage: this.value(e) })}>
          <option value="">All stages</option>${STAGES.map((s) => html`<option value=${s} ?selected=${s === this.stage}>${stageLabel(s)}</option>`)}</select></label>
        <label class="field"><span class="label">Attention</span><select name="attention" .value=${this.attention} @change=${(e: Event) => this.set({ attention: this.value(e) })}>
          <option value="">Anything</option>${ATTENTION.map((a) => html`<option value=${a} ?selected=${a === this.attention}>${attentionLabel(a)}</option>`)}</select></label>
        <label class="field"><span class="label">Channel</span><select name="channel" .value=${this.channel} @change=${(e: Event) => this.set({ channel: this.value(e) })}>
          <option value="">All channels</option>${CHANNELS.map((c) => html`<option value=${c} ?selected=${c === this.channel}>${channelLabel(c)}</option>`)}</select></label>
        <label class="field"><span class="label">Owner</span><select name="owner" .value=${this.owner} @change=${(e: Event) => this.set({ owner: this.value(e) })}>
          ${OWNER_FILTERS.map(([code, label]) => html`<option value=${code} ?selected=${code === this.owner}>${label}</option>`)}</select></label>
        <div class="search"><label class="field"><span class="label">Search</span><input name="q" type="search" autocomplete="off" .value=${this.q} placeholder="Name, number or city"
          @input=${(e: Event) => { this.q = this.value(e); }} /></label><button class="btn" type="submit">Search</button></div>
      </div>
    </form>`;
  }

  private renderCounts(meta: PipelineMeta) {
    const entries = STAGES.filter((s) => meta.stage_counts[s]).map((s) => [s, meta.stage_counts[s]] as const);
    if (!entries.length) return nothing;
    return html`<ul class="counts" aria-label="Leads per stage">${entries.map(([s, n]) => html`<li><button type="button" aria-pressed=${this.stage === s ? 'true' : 'false'}
      @click=${() => this.set({ stage: this.stage === s ? '' : s })}>${stageLabel(s)}<span class="n">${n}</span></button></li>`)}</ul>`;
  }

  private renderRow(r: PipelineRow) {
    const f = r.facts;
    return html`<tr>
      <td data-label="Lead"><span class="cell"><a class="lead" href="/leads/${r.lead.id}" @click=${(e: Event) => { e.preventDefault(); navigate(`/leads/${r.lead.id}`); }}>${r.lead.lead_number}</a>
        <span class="sub">${r.lead.name}${r.lead.city ? ` · ${r.lead.city}` : ''}</span></span></td>
      <td data-label="Stage"><span class="cell">${stagePill(r.stage)}
        ${f.quotation ? html`<span class="sub">${f.quotation.quotation_number} v${f.quotation.version_no} · ${f.quotation.status.toLowerCase().replace(/_/g, ' ')}</span>` : nothing}</span></td>
      <td data-label="Channel"><span class="cell">${channelLabel(r.channel)}${r.channel.detail ? html`<span class="sub">${r.channel.detail}</span>` : nothing}</span></td>
      <td data-label="Quoted"><span class="cell">${quotedText(r.quoted)}</span></td>
      <td data-label="Owner"><span class="cell">${r.owner?.display_name ?? 'Unassigned'}</span></td>
      <td data-label="Last activity"><span class="cell">${formatRelative(r.last_activity_on)}</span></td>
      <td data-label="Next follow-up"><span class="cell">${r.next_follow_up_on
        ? r.is_follow_up_overdue ? html`<span class="overdue">${icon('alert')}Overdue</span><span class="sub">${formatRelative(r.next_follow_up_on)}</span>` : formatRelative(r.next_follow_up_on)
        : html`<span class="muted">None planned</span>`}</span></td>
      <td data-label="Attention"><span class="cell">${r.attention.length ? html`<ul class="attention" aria-label="Attention">${r.attention.map((a) => html`<li>${attentionLabel(a)}</li>`)}</ul>` : html`<span class="muted">—</span>`}</span></td>
      <td data-label="Customer"><span class="cell">${r.customer_action ?? html`<span class="muted">—</span>`}</span></td>
    </tr>`;
  }

  private renderBody() {
    switch (this.load) {
      case 'off':
        return html`<vs-banner kind="info">The sales pipeline is not switched on here.</vs-banner>`;
      case 'forbidden':
        return html`<p role="status">You do not have access to the sales pipeline.</p>`;
      case 'failed':
        return html`<vs-problem-banner .problem=${this.problem} heading="The pipeline could not be loaded"></vs-problem-banner>
          <div><button class="btn" @click=${() => void this.fetch()}>Retry</button></div>`;
      case 'loading':
        return html`<vs-skeleton rows="8"></vs-skeleton>`;
      default: {
        const rows = this.rows ?? [];
        const meta = this.meta;
        if (!rows.length) return html`<vs-empty-state heading="No leads match these filters"></vs-empty-state>`;
        return html`${meta?.truncated ? html`<vs-banner kind="warning">Only the ${meta.scanned} most recent leads were examined; narrow the filters to see the rest.</vs-banner>` : nothing}
          <div class="table-wrap" tabindex="0" role="region" aria-label="Sales pipeline, scrolls sideways on small screens"><table class="cards">
            <caption class="sr-only">Sales pipeline</caption>
            <thead><tr><th scope="col">Lead</th><th scope="col">Stage</th><th scope="col">Channel</th><th scope="col">Quoted</th><th scope="col">Owner</th>
              <th scope="col">Last activity</th><th scope="col">Next follow-up</th><th scope="col">Attention</th><th scope="col">Customer</th></tr></thead>
            <tbody>${rows.map((r) => this.renderRow(r))}</tbody></table></div>
          ${meta && meta.total > meta.limit ? html`<vs-pagination .page=${meta.page} .totalPages=${Math.max(1, Math.ceil(meta.total / meta.limit))} .total=${meta.total} .pageSize=${meta.limit}
            @page-change=${(e: CustomEvent<number>) => { this.page = e.detail; void this.fetch(); }}></vs-pagination>` : nothing}`;
      }
    }
  }

  override render() {
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Sales</p><h1 class="title" id="page-title" tabindex="-1">Sales pipeline</h1>
        <p class="note">Stages are derived from records (visits, quotations, proposal links, acceptances); a stage marked "by status" rests on a staff status with
          no record behind it. A consultation is a logged Meeting.</p></div></div>
      ${this.load === 'off' ? nothing : this.renderFilters()}
      ${this.meta && this.load === 'ready' ? this.renderCounts(this.meta) : nothing}
      ${this.renderBody()}
    </div>`;
  }
}
customElements.define('vs-sales-pipeline-page', VsSalesPipelinePage);
