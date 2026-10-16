import { css, html } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatDate } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { badgeStyles } from '../project/labels.js';
import { FILTERS, serviceApi, STATUS, type RequestRow } from './api.js';

/**
 * /service — post-handover service requests the signed-in person may see (WSV). A request is only "the customer reported
 * an issue" until someone decides its coverage; the queue shows where each one stands and who acts next.
 */
export class VsServiceListPage extends SessionElement {
  static override properties = { rows: { state: true }, filter: { state: true }, problem: { state: true }, disabled: { state: true } };
  declare rows: RequestRow[] | null;
  declare filter: string;
  declare problem: ApiProblem | null;
  declare disabled: boolean;

  static override styles = [...shared, pageStyles, tableStyles, badgeStyles, css`
    .filters { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .filters button { min-height: var(--vs-target); }
    .filters button[aria-pressed='true'] { background: var(--vs-ink); color: var(--vs-surface); }
    td a { font-weight: 600; display: inline-flex; align-items: center; min-height: var(--vs-target); }
    td, th { overflow-wrap: anywhere; }
  `];

  constructor() {
    super();
    this.rows = null;
    this.filter = 'OPEN';
    this.problem = null;
    this.disabled = false;
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private async load() {
    this.problem = null;
    this.rows = null;
    try {
      this.rows = (await serviceApi.list(this.filter)).data;
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404) this.disabled = true;
      else this.problem = p;
    }
  }

  private choose(code: string) {
    this.filter = code;
    void this.load();
  }

  override render() {
    if (this.disabled) {
      return html`<div class="page"><h1 class="title" tabindex="-1">Service</h1>
        <vs-empty-state heading="Warranty and service are not enabled in this environment."></vs-empty-state></div>`;
    }
    const rows = this.rows;
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">After handover</p><h1 class="title" id="page-title" tabindex="-1">Service</h1>
        <p class="muted">Problems customers reported after handover. Nothing is assumed: coverage is decided on each request, with its reason.</p></div></div>
      <div class="filters" role="group" aria-label="Show">${FILTERS.map(([code, label]) => html`<button class="btn" aria-pressed=${this.filter === code ? 'true' : 'false'}
        @click=${() => this.choose(code)}>${label}</button>`)}</div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${rows === null ? html`<vs-skeleton rows="6"></vs-skeleton>` : !rows.length ? html`<vs-empty-state heading="No service requests here"></vs-empty-state>`
        : html`<div class="table-wrap" tabindex="0" role="region" aria-label="Service requests, scrolls sideways on small screens"><table class="cards">
          <caption class="sr-only">Service requests</caption>
          <thead><tr><th scope="col">Request</th><th scope="col">Problem</th><th scope="col">Status</th><th scope="col">Owner</th><th scope="col">Reported</th></tr></thead>
          <tbody>${rows.map((r) => html`<tr>
            <td data-label="Request"><a href="/service/${r.id}" @click=${(e: Event) => { e.preventDefault(); navigate(`/service/${r.id}`); }}>${r.request_number}</a>
              <span class="sub">${r.channel === 'PORTAL' ? 'From the portal' : 'Recorded by staff'}${r.priority === 'HIGH' ? ' · High priority' : ''}</span></td>
            <td data-label="Problem">${r.category_label}</td>
            <td data-label="Status"><span class="badge ${STATUS[r.status]?.[1] ?? 'info'}">${STATUS[r.status]?.[0] ?? r.status}</span></td>
            <td data-label="Owner">${r.owner?.display_name ?? 'Unassigned'}</td>
            <td data-label="Reported">${formatDate(r.reported_on)}</td></tr>`)}</tbody></table></div>`}
    </div>`;
  }
}
customElements.define('vs-service-list-page', VsServiceListPage);
