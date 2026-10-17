import { css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { dayKey, formatAbsolute, formatDate } from '../../core/format/format.js';
import '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { salesApi, type Funnel } from './api.js';
import { channelLabel, countText, ratioText, stageLabel } from './labels.js';

type Load = 'loading' | 'ready' | 'off' | 'forbidden' | 'failed';

const RATIOS: [keyof Funnel['ratios'], string][] = [
  ['estimator_start_to_estimate', 'Estimator starts that completed an estimate'],
  ['site_visit_to_enquiry', 'Site visits that became an enquiry'],
  ['enquiry_to_quotation', 'Enquiries that received a quotation'],
  ['quotation_to_acceptance', 'Quotations the customer accepted'],
  ['enquiry_to_won', 'Enquiries won'],
  ['decided_to_won', 'Decided enquiries (won or lost) that were won'],
];

/** The last 30 business days ending today, as YYYY-MM-DD in the viewer's zone. */
export function defaultPeriod(now = new Date()): { from: string; to: string } {
  return { to: dayKey(now), from: dayKey(new Date(now.getTime() - 29 * 86_400_000)) };
}

/**
 * /sales/funnel — the acquisition funnel (SCA-007) over a period. Three kinds of number are kept apart: records the
 * owning feature wrote, the site's anonymous beacons, and "Not tracked" when a beacon was never received (never shown
 * as 0). A ratio appears only when both sides are tracked and the denominator is positive; otherwise its reason is.
 */
export class VsSalesFunnelPage extends SessionElement {
  static override properties = { report: { state: true }, load: { state: true }, problem: { state: true }, from: { state: true }, to: { state: true }, error: { state: true } };
  declare report: Funnel | null;
  declare load: Load;
  declare problem: ApiProblem | null;
  declare from: string;
  declare to: string;
  declare error: string;
  private focused = false;

  static override styles = [...shared, pageStyles, tableStyles, css`
    form.period { display: flex; flex-wrap: wrap; gap: var(--vs-space-3); align-items: flex-end; }
    form.period label { flex: 1 1 160px; max-width: 240px; }
    .kpis { display: grid; gap: var(--vs-space-3); grid-template-columns: repeat(auto-fit, minmax(min(100%, 170px), 1fr)); }
    .two { display: grid; gap: var(--vs-space-4); grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); align-items: start; }
    section.card { display: flex; flex-direction: column; gap: var(--vs-space-3); min-width: 0; }
    dl.ratios { margin: 0; display: flex; flex-direction: column; gap: var(--vs-space-2); }
    dl.ratios div { display: flex; justify-content: space-between; gap: var(--vs-space-3); border-bottom: 1px solid var(--vs-line); padding-bottom: var(--vs-space-2); }
    dl.ratios dt { color: var(--vs-ink-muted); }
    dl.ratios dd { margin: 0; font-weight: 600; white-space: nowrap; font-variant-numeric: tabular-nums; }
    td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
    td, th { overflow-wrap: anywhere; }
    .note { font-size: 13px; line-height: 20px; color: var(--vs-ink-muted); max-width: 72ch; }
    ul.plain { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vs-space-1); }
    ul.plain li { display: flex; justify-content: space-between; gap: var(--vs-space-3); }
  `];

  constructor() {
    super();
    this.report = null;
    this.load = 'loading';
    this.problem = null;
    const p = defaultPeriod();
    this.from = p.from;
    this.to = p.to;
    this.error = '';
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.fetch();
  }

  private async fetch() {
    this.load = 'loading';
    this.problem = null;
    try {
      this.report = (await salesApi.funnel(this.from, this.to)).data;
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

  private submit(e: Event) {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const from = (form.elements.namedItem('from') as HTMLInputElement).value;
    const to = (form.elements.namedItem('to') as HTMLInputElement).value;
    if (!from || !to) { this.error = 'Enter both dates.'; return; }
    if (from > to) { this.error = 'The start is after the end.'; return; }
    this.error = '';
    this.from = from;
    this.to = to;
    void this.fetch();
  }

  private tile(label: string, c: { count: number | null; tracking: 'TRACKED' | 'NOT_TRACKED' } | null | undefined, hint: string) {
    const text = countText(c);
    return html`<vs-kpi-tile label=${label} value=${text} hint=${text === 'Not tracked' ? 'No beacon received for this event' : hint}></vs-kpi-tile>`;
  }

  private renderReport(r: Funnel) {
    const step = (code: string) => r.leads.find((s) => s.code === code);
    const steps = r.leads.map((s) => ({ label: s.label || stageLabel(s.code), value: s.count }));
    const stages = r.current_stages.filter((s) => s.count).map((s) => ({ label: s.label || stageLabel(s.code), value: s.count }));
    return html`
      <p class="note">${formatDate(r.period.from)} to ${formatDate(r.period.to)} (${r.period.timezone}), as of ${formatAbsolute(r.as_of)}. Enquiries are the leads created in
        the period, judged by their records as of now.</p>
      <section aria-labelledby="h-kpi"><h2 id="h-kpi" class="eyebrow">At a glance</h2>
        <div class="kpis">
          ${this.tile('Site visits', r.site.site_visit, 'Browser sessions, one per day')}
          ${this.tile('Estimator starts', r.site.estimator_started, 'Browser sessions, one per day')}
          ${this.tile('Estimates completed', r.estimates_completed, 'Public budgetary estimates')}
          ${this.tile('Enquiries', step('leads_created'), 'Leads created')}
          ${this.tile('Quotations issued', step('quotation_issued'), 'Enquiries with an issued quotation')}
          ${this.tile('Accepted', step('accepted'), 'Enquiries with an accepted quotation')}
          ${this.tile('Won', step('won'), 'Enquiries closed as won')}
        </div></section>
      <div class="two">
        <section class="card" aria-labelledby="h-steps"><h2 id="h-steps" class="eyebrow">Enquiries by step reached</h2>
          <p class="note">Each enquiry counts at every step a record proves it reached.</p>
          <vs-bar-list .items=${steps}></vs-bar-list></section>
        <section class="card" aria-labelledby="h-ratios"><h2 id="h-ratios" class="eyebrow">Conversion</h2>
          <dl class="ratios">${RATIOS.map(([key, label]) => html`<div><dt>${label}</dt><dd>${ratioText(r.ratios[key])}</dd></div>`)}</dl>
          <p class="note">"Not tracked" means the site never sent that beacon; "No data yet" means nothing to divide by.</p></section>
      </div>
      <div class="two">
        <section class="card" aria-labelledby="h-channel"><h2 id="h-channel" class="eyebrow">By channel</h2>
          <div class="table-wrap" tabindex="0" role="region" aria-label="Enquiries by channel"><table class="cards"><caption class="sr-only">Enquiries by channel</caption>
            <thead><tr><th scope="col">Channel</th><th scope="col" class="num">Enquiries</th><th scope="col" class="num">Quoted</th><th scope="col" class="num">Accepted</th>
              <th scope="col" class="num">Won</th><th scope="col" class="num">Lost</th></tr></thead>
            <tbody>${r.by_channel.map((c) => html`<tr><th scope="row">${channelLabel(c)}</th><td class="num" data-label="Enquiries">${c.leads}</td>
              <td class="num" data-label="Quoted">${c.quotation_issued}</td><td class="num" data-label="Accepted">${c.accepted}</td>
              <td class="num" data-label="Won">${c.won}</td><td class="num" data-label="Lost">${c.lost}</td></tr>`)}</tbody></table></div></section>
        <section class="card" aria-labelledby="h-source"><h2 id="h-source" class="eyebrow">By source</h2>
          ${r.by_source.length ? html`<div class="table-wrap" tabindex="0" role="region" aria-label="Enquiries by source"><table class="cards"><caption class="sr-only">Enquiries by source</caption>
            <thead><tr><th scope="col">Source</th><th scope="col" class="num">Enquiries</th><th scope="col" class="num">Won</th></tr></thead>
            <tbody>${r.by_source.map((s) => html`<tr><th scope="row">${s.label || s.code}</th><td class="num" data-label="Enquiries">${s.leads}</td><td class="num" data-label="Won">${s.won}</td></tr>`)}</tbody>
            </table></div>` : html`<p class="muted">No enquiries in this period.</p>`}</section>
      </div>
      <div class="two">
        <section class="card" aria-labelledby="h-stages"><h2 id="h-stages" class="eyebrow">Where the cohort stands now</h2>
          ${stages.length ? html`<vs-bar-list .items=${stages}></vs-bar-list>` : html`<p class="muted">No enquiries in this period.</p>`}</section>
        <section class="card" aria-labelledby="h-lost"><h2 id="h-lost" class="eyebrow">Lost reasons</h2>
          ${r.lost_reasons.length ? html`<ul class="plain">${r.lost_reasons.map((x) => html`<li><span>${x.label || x.code}</span><span class="strong">${x.count}</span></li>`)}</ul>`
            : html`<p class="muted">No enquiries lost in this period.</p>`}</section>
      </div>
      <section class="card" aria-labelledby="h-cohort"><h2 id="h-cohort" class="eyebrow">About these numbers</h2>
        <ul class="plain">
          <li><span>Enquiries in the cohort</span><span class="strong">${r.cohort.size}</span></li>
          <li><span>Stages claimed by a staff status with no record behind it</span><span class="strong">${r.cohort.claimed_stages_without_record}</span></li>
          <li><span>Quiet for 14 days with nothing planned</span><span class="strong">${r.stalled.quiet}</span></li>
        </ul>
        ${r.cohort.truncated ? html`<vs-banner kind="warning">The period holds more enquiries than the report examines; choose a shorter period for complete figures.</vs-banner>` : nothing}
        <p class="note">A claimed stage is where staff put the lead (its status), with no visit, quotation, proposal or acceptance record to prove it. It is
          counted as reached but shown here so the figure can be read with that in mind.</p></section>`;
  }

  private renderBody() {
    switch (this.load) {
      case 'off': return html`<vs-banner kind="info">The sales funnel is not switched on here.</vs-banner>`;
      case 'forbidden': return html`<p role="status">You do not have access to the sales funnel.</p>`;
      case 'failed': return html`<vs-problem-banner .problem=${this.problem} heading="The funnel could not be loaded"></vs-problem-banner>
        <div><button class="btn" @click=${() => void this.fetch()}>Retry</button></div>`;
      case 'loading': return html`<vs-skeleton rows="8"></vs-skeleton>`;
      default: return this.report ? this.renderReport(this.report) : nothing;
    }
  }

  override render() {
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Sales</p><h1 class="title" id="page-title" tabindex="-1">Funnel</h1>
        <p class="note">How enquiries arrive and progress. Counts come from records; the site's anonymous beacons are shown only where they were received.</p></div></div>
      ${this.load === 'off' ? nothing : html`<form class="period" novalidate @submit=${(e: Event) => this.submit(e)}>
        <label class="field"><span class="label">From</span><input name="from" type="date" .value=${this.from} required aria-describedby=${this.error ? 'period-error' : nothing} /></label>
        <label class="field"><span class="label">To</span><input name="to" type="date" .value=${this.to} required /></label>
        <button class="btn" type="submit">Show</button>
        ${this.error ? html`<span id="period-error" class="danger-text small" role="alert">${this.error}</span>` : nothing}
      </form>`}
      ${this.renderBody()}
    </div>`;
  }
}
customElements.define('vs-sales-funnel-page', VsSalesFunnelPage);
