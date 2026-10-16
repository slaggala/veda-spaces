import { css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatAbsolute, formatDate } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { commercialsApi, newIdempotencyKey, type AccountRow, type Candidate } from './api.js';
import { commercialStyles, stateBadge } from './ui.js';

/**
 * /commercials — every commercial record the signed-in person may see, with what is outstanding and what is next, and
 * the accepted quotations that have no commercial record yet (for those who may open one). Figures come from the server.
 */
export class VsCommercialsListPage extends SessionElement {
  static override properties = { rows: { state: true }, candidates: { state: true }, problem: { state: true }, disabled: { state: true },
    busy: { state: true }, announcement: { state: true } };
  declare rows: AccountRow[] | null;
  declare candidates: Candidate[] | null;
  declare problem: ApiProblem | null;
  declare disabled: boolean;
  declare busy: boolean;
  declare announcement: string;

  static override styles = [...shared, pageStyles, tableStyles, commercialStyles, css`
    td a { font-weight: 600; display: inline-flex; align-items: center; min-height: var(--vs-target); }
    td, th { overflow-wrap: anywhere; }
    .btn.small { min-height: var(--vs-target); }
  `];

  constructor() {
    super();
    this.rows = null;
    this.candidates = null;
    this.problem = null;
    this.disabled = false;
    this.busy = false;
    this.announcement = '';
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private async load() {
    this.problem = null;
    try {
      this.rows = (await commercialsApi.list()).data;
      this.candidates = this.can('commercials.schedule.manage') ? (await commercialsApi.candidates()).data : [];
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404) this.disabled = true;
      else this.problem = p;
    }
  }

  private async openRecord(c: Candidate) {
    this.busy = true;
    try {
      const r = await commercialsApi.open(c.quotation_id, newIdempotencyKey());
      this.announcement = `Commercial record opened for ${c.reference}.`;
      navigate(`/commercials/${r.data.id}`);
    } catch (e) { this.problem = e as ApiProblem; } finally { this.busy = false; }
  }

  override render() {
    if (this.disabled) {
      return html`<div class="page"><h1 class="title" tabindex="-1">Payments</h1>
        <vs-empty-state heading="Project commercials are not enabled in this environment."></vs-empty-state></div>`;
    }
    const rows = this.rows;
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Commercial</p><h1 class="title" id="page-title" tabindex="-1">Payments</h1>
        <p class="muted">What each project is worth, what has been paid and what is outstanding. Payments are recorded by staff once money
          reaches Veda Spaces; nothing is collected online.</p></div></div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${rows === null ? html`<vs-skeleton rows="6"></vs-skeleton>` : !rows.length
        ? html`<vs-empty-state heading="No commercial records yet"><p>Open one from an accepted quotation below.</p></vs-empty-state>`
        : html`<div class="table-wrap"><table><caption class="sr-only">Commercial records</caption>
          <thead><tr><th scope="col">Customer and quotation</th><th scope="col" class="num">Value (₹)</th><th scope="col" class="num">Paid (₹)</th>
            <th scope="col" class="num">Outstanding (₹)</th><th scope="col">Next payment</th><th scope="col">Schedule</th></tr></thead>
          <tbody>${rows.map((r) => html`<tr>
            <td><a href="/commercials/${r.id}" @click=${(e: Event) => { e.preventDefault(); navigate(`/commercials/${r.id}`); }}>${r.lead.name ?? 'Customer'}</a>
              <span class="sub">${r.quotation_number} · ${r.property.reference ?? ''}</span></td>
            <td class="num">${r.position.value}</td><td class="num">${r.position.paid}</td><td class="num">${r.position.outstanding}</td>
            <td>${r.next ? html`${r.next.label} · ₹ ${r.next.amount}<span class="sub">${stateBadge(r.next.state, r.next.state === 'OVERDUE' ? 'Overdue' : r.next.due_on ? `Due ${formatDate(r.next.due_on)}` : 'No due date')}</span>`
              : 'Nothing outstanding'}</td>
            <td>${r.position.schedule_state === 'IN_BALANCE' ? 'Up to date' : r.position.schedule_state === 'NONE' ? 'Not set' : html`<span class="badge OVERDUE">Revise</span>`}</td>
          </tr>`)}</tbody></table></div>`}
      ${this.candidates?.length ? html`<section class="stack" aria-labelledby="h-candidates"><h2 id="h-candidates" class="section-title">Accepted quotations without a commercial record</h2>
        <div class="table-wrap"><table><thead><tr><th scope="col">Quotation</th><th scope="col">Customer</th><th scope="col" class="num">Accepted total (₹)</th>
          <th scope="col">Accepted</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
          <tbody>${this.candidates.map((c) => html`<tr><td>${c.reference}<span class="sub">${c.property.reference ?? ''}</span></td><td>${c.lead.name ?? '—'}</td>
            <td class="num">${c.accepted_total ?? '—'}</td><td>${c.decided_on ? formatAbsolute(c.decided_on) : '—'}</td>
            <td><button class="btn small primary" ?disabled=${this.busy} @click=${() => this.openRecord(c)}>Open record<span class="sr-only"> for ${c.reference}</span></button></td></tr>`)}</tbody></table></div>
      </section>` : nothing}
      <div class="sr-only" role="status" aria-live="polite">${this.announcement}</div>
    </div>`;
  }
}
customElements.define('vs-commercials-list-page', VsCommercialsListPage);
