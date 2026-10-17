import { css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatAbsolute, formatDate, humanize } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import '../../design-system/components.js';
import { shared } from '../../design-system/styles.js';
import { salesApi, type PipelineRow } from './api.js';
import { attentionLabel, channelLabel, quotedText, salesStyles, stagePill } from './labels.js';

/**
 * <vs-sales-progression-card>: one lead's derived sales progression on its detail page (SCA-006): the stage the records
 * prove, the records themselves with links to where they live, and what needs attention. It renders nothing when the
 * feature is off (404) or the viewer may not see the pipeline (403): the lead page is unchanged for them.
 */
export class VsSalesProgressionCard extends SessionElement {
  static override properties = { leadId: { type: String }, row: { state: true }, off: { state: true }, problem: { state: true } };
  declare leadId: string;
  declare row: PipelineRow | null;
  declare off: boolean;
  declare problem: ApiProblem | null;

  static override styles = [...shared, salesStyles, css`
    :host { display: block; }
    dl { margin: 0; display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--vs-space-2); }
    dl div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    dt { font-size: 11px; line-height: 16px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--vs-ink-muted); }
    dd { margin: 0; overflow-wrap: anywhere; }
    .links { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .links a, .links button { min-height: var(--vs-target); }
    a.inline { display: inline-flex; align-items: center; min-height: var(--vs-target); }
    .meta { font-size: 12px; line-height: 18px; color: var(--vs-ink-muted); }
  `];

  constructor() {
    super();
    this.leadId = '';
    this.row = null;
    this.off = false;
    this.problem = null;
  }

  override updated(changed: Map<string, unknown>) {
    if (changed.has('leadId') && this.leadId) void this.load();
  }

  private async load() {
    this.row = null;
    this.off = false;
    this.problem = null;
    if (this.me && !this.can('sales.pipeline.view')) { this.off = true; return; }
    try {
      this.row = (await salesApi.progression(this.leadId)).data;
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404 || p.status === 403) this.off = true;
      else this.problem = p;
    }
  }

  private go(e: Event, path: string) {
    e.preventDefault();
    navigate(path);
  }

  private renderFacts(r: PipelineRow) {
    const f = r.facts;
    const link = (path: string, text: string) => html`<a class="inline" href=${path} @click=${(e: Event) => this.go(e, path)}>${text}</a>`;
    return html`<dl>
      ${f.estimate ? html`<div><dt>Budgetary estimate</dt><dd>${f.estimate.reference} <span class="meta">· ${formatAbsolute(f.estimate.created_on)}</span></dd></div>` : nothing}
      ${f.contacted_on ? html`<div><dt>First contact</dt><dd>${formatAbsolute(f.contacted_on)}</dd></div>` : nothing}
      ${f.consultation_on ? html`<div><dt>Consultation (logged Meeting)</dt><dd>${formatAbsolute(f.consultation_on)}</dd></div>` : nothing}
      ${f.visits.length ? html`<div><dt>Measurement visits</dt><dd class="stack">${f.visits.map((v) => html`<span>${link(`/site/properties/${v.property_id}`, v.visit_number)}
        <span class="meta">· ${humanize(v.status)}${v.completed_on ? ` · completed ${formatAbsolute(v.completed_on)}` : v.scheduled_start_on ? ` · ${formatAbsolute(v.scheduled_start_on)}` : ''}</span></span>`)}</dd></div>` : nothing}
      ${f.quotation ? html`<div><dt>Quotation</dt><dd>${f.quotation.quotation_number} v${f.quotation.version_no} <span class="meta">· ${humanize(f.quotation.status)}${f.quotation.issued_on ? ` · issued ${formatAbsolute(f.quotation.issued_on)}` : ''}${f.quotation.valid_until ? ` · valid until ${formatDate(f.quotation.valid_until)}` : ''}${f.quotations > 1 ? ` · ${f.quotations} quotations in all` : ''}</span>
        <br />Quoted: ${quotedText(r.quoted)}</dd></div>` : nothing}
      ${f.proposal ? html`<div><dt>Customer proposal</dt><dd>${f.proposal.first_viewed_on ? `Opened ${formatAbsolute(f.proposal.first_viewed_on)}` : 'Shared, not opened yet'}
        <span class="meta">· ${f.proposal.view_count} ${f.proposal.view_count === 1 ? 'view' : 'views'} · ${f.proposal.active_links} of ${f.proposal.links} ${f.proposal.links === 1 ? 'link' : 'links'} active</span></dd></div>` : nothing}
      ${f.customer_requests.total ? html`<div><dt>Customer requests</dt><dd>${f.customer_requests.total} <span class="meta">· ${f.customer_requests.waiting_on_staff} waiting on staff · ${f.customer_requests.waiting_on_customer} waiting on the customer</span></dd></div>` : nothing}
      ${f.accepted ? html`<div><dt>Accepted</dt><dd>${f.accepted.quotation_number} v${f.accepted.version_no} <span class="meta">· ${formatAbsolute(f.accepted.decided_on)}${f.accepted.method ? ` · ${humanize(f.accepted.method)}` : ''}</span></dd></div>` : nothing}
      ${f.project ? html`<div><dt>Project</dt><dd>${link(`/projects/${f.project.id}`, f.project.project_number)} <span class="meta">· ${humanize(f.project.stage_code)} · ${humanize(f.project.status)}</span></dd></div>` : nothing}
      <div><dt>Channel</dt><dd>${channelLabel(r.channel)}${r.channel.detail ? html` <span class="meta">· ${r.channel.detail}</span>` : nothing}</dd></div>
      ${r.customer_action ? html`<div><dt>Customer's next step</dt><dd>${r.customer_action}</dd></div>` : nothing}
    </dl>`;
  }

  override render() {
    if (this.off) return nothing;
    const r = this.row;
    const property = r?.facts.properties[0];
    return html`<section class="card stack" aria-labelledby="sales-h"><h2 class="eyebrow" id="sales-h">Sales progression</h2>
      ${this.problem ? html`<vs-problem-banner .problem=${this.problem}></vs-problem-banner>` : nothing}
      ${!r && !this.problem ? html`<vs-skeleton rows="3"></vs-skeleton>` : nothing}
      ${r ? html`
        ${stagePill(r.stage)}
        ${this.renderFacts(r)}
        ${r.attention.length ? html`<div><span class="meta">Needs attention</span><ul class="attention" aria-label="Needs attention">${r.attention.map((a) => html`<li>${attentionLabel(a)}</li>`)}</ul></div>` : nothing}
        <div class="links">
          ${property ? html`<a class="btn small" href=${`/site/properties/${property}`} @click=${(e: Event) => this.go(e, `/site/properties/${property}`)}>Open property</a>`
            : this.can('property.create') ? html`<a class="btn small" href=${`/site?lead=${this.leadId}`} @click=${(e: Event) => this.go(e, `/site?lead=${this.leadId}`)}>Create property for this lead</a>` : nothing}
        </div>
        <p class="meta">Derived from records; a stage marked "by status" rests on a staff status with no record behind it.</p>` : nothing}
    </section>`;
  }
}
customElements.define('vs-sales-progression-card', VsSalesProgressionCard);
