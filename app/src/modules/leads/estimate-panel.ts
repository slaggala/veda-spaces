import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { EstimateDetail, EstimateSelection, EstimateSummary } from '../../core/api/types.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatDate, formatFull, humanize } from '../../core/format/format.js';
import { toast } from '../../design-system/components.js';
import { shared } from '../../design-system/styles.js';
import { apiUnit, measurementRows, PACKAGES, rangeText, revisedSelections, rupees } from './estimates.js';

type Dialog = '' | 'detail' | 'revise' | 'copy';

/**
 * Budgetary Estimate panel on the lead detail page (ADR-012, owner instruction Part H). Staff see the full estimate,
 * including internal lines and the preparation components; actions never convert an estimate into a quotation.
 */
export class VsEstimatePanel extends SessionElement {
  static override properties = {
    leadId: { type: String }, estimates: { state: true }, detail: { state: true }, dialog: { state: true },
    problem: { state: true }, busy: { state: true }, copy: { state: true },
  };
  declare leadId: string;
  declare estimates: EstimateSummary[] | null;
  declare detail: EstimateDetail | null;
  declare dialog: Dialog;
  declare problem: ApiProblem | null;
  declare busy: boolean;
  declare copy: Record<string, unknown> | null;

  static override styles = [
    ...shared,
    css`
      :host { display: block; }
      .range { font-weight: 600; font-size: 1.1rem; }
      .meta { font-size: 12px; color: var(--vs-ink-muted); }
      ul { margin: 0; padding-left: 18px; }
      table { width: 100%; border-collapse: collapse; font-size: 14px; }
      th, td { text-align: left; padding: 6px 4px; border-bottom: 1px solid var(--vs-line); vertical-align: top; }
      td.num { text-align: right; white-space: nowrap; }
      .badge { display: inline-block; font-size: 12px; padding: 2px 8px; border: 1px solid var(--vs-line); border-radius: 999px; }
      .actions { display: flex; flex-wrap: wrap; gap: 8px; }
      section + section { margin-top: 12px; }
      @media print { .actions, .no-print { display: none; } }
    `,
  ];

  constructor() {
    super();
    this.leadId = '';
    this.estimates = null;
    this.detail = null;
    this.dialog = '';
    this.problem = null;
    this.busy = false;
    this.copy = null;
  }

  override updated(changed: Map<string, unknown>) {
    if (changed.has('leadId') && this.leadId && this.can('estimate.read')) void this.load();
  }

  private async load() {
    try {
      this.estimates = (await api.get<EstimateSummary[]>(`/api/v1/leads/${this.leadId}/estimates`)).data;
    } catch {
      this.estimates = [];
    }
  }

  private async open(id: string) {
    try {
      this.detail = (await api.get<EstimateDetail>(`/api/v1/estimates/${id}`)).data;
      this.problem = null;
      this.dialog = 'detail';
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  private async act(path: string, body?: unknown, message = 'Done'): Promise<boolean> {
    if (!this.detail) return false;
    this.busy = true;
    try {
      const r = await api.post<EstimateDetail>(`/api/v1/estimates/${this.detail.id}/${path}`, body);
      toast(message, 'success');
      if (path === 'duplicate' || path === 'revisions') this.detail = r.data;
      else if (path === 'site-measurement') this.detail = r.data;
      await this.load();
      this.dispatchEvent(new CustomEvent('estimate-changed', { bubbles: true, composed: true }));
      return true;
    } catch (e) {
      this.problem = e as ApiProblem;
      return false;
    } finally {
      this.busy = false;
    }
  }

  private async consultationCopy() {
    if (!this.detail) return;
    try {
      this.copy = (await api.post<Record<string, unknown>>(`/api/v1/estimates/${this.detail.id}/consultation-copy`)).data;
      this.dialog = 'copy';
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  private submitRevision(ev: Event) {
    ev.preventDefault();
    if (!this.detail) return;
    const form = new FormData(ev.target as HTMLFormElement);
    const pkg = String(form.get('package') || this.detail.package);
    const edits: Record<string, string> = {};
    for (const [k, v] of form.entries()) if (k.includes('|')) edits[k] = String(v);
    const selections = revisedSelections(this.detail.inputs.selections, edits);
    this.problem = null;
    void this.act('revisions', { package: pkg, selections }, 'Revised estimate created').then((ok) => {
      if (ok) this.dialog = 'detail'; // on failure the form stays open with the problem shown in it
    });
  }

  /** Inputs of a selection that used a typical size (from the stored assumptions). */
  private typicalInputs(sel: EstimateSelection, index: number): { name: string; unit: string }[] {
    const sels = this.detail?.inputs.selections ?? [];
    const instance = sels.slice(0, index).filter((s) => s.room === sel.room && s.product === sel.product).length + 1;
    const details = (this.detail?.estimate as unknown as { assumption_details?: { room: string; product: string; instance: number; input: string; unit: string }[] })?.assumption_details ?? [];
    return details
      .filter((a) => a.room === sel.room && a.product === sel.product && a.instance === instance)
      .map((a) => ({ name: a.input, unit: apiUnit(a.unit) }));
  }

  private renderDetail(d: EstimateDetail) {
    const e = d.estimate;
    const manage = this.can('estimate.manage');
    return html`<div class="stack">
      ${this.problem ? html`<vs-problem-banner .problem=${this.problem}></vs-problem-banner>` : nothing}
      <p class="meta">${d.reference} · created ${formatFull(d.created_on)} · ${humanize(d.origin)}${d.source_reference ? ` · from ${d.source_reference}` : ''} · rate card ${d.rate_card_version} (rules ${d.calculation_version}) · specification ${d.specification ? d.specification.spec_code : 'none'} · valid until ${formatDate(d.expires_on.slice(0, 10))}</p>
      <p class="meta">${e.disclaimer}</p>
      <section><h3 class="eyebrow">Property</h3><p>${humanize(d.property_type)} · ${d.home_size.replace('BHK', ' BHK')} · ${humanize(d.project_kind)}${d.city ? ` · ${d.city}` : ''} · package ${humanize(d.package)}${d.preferred_contact ? ` · prefers ${humanize(d.preferred_contact)}` : ''}</p>
        ${d.site_measurement_required ? html`<span class="badge">Site measurement required</span>` : nothing}</section>
      <section><h3 class="eyebrow">Estimate range</h3><p class="range">${rangeText(e.range)}</p><p class="meta">Plus GST ${e.gst.pct}%: ${rupees(e.gst.low_minor)} – ${rupees(e.gst.high_minor)} · base ${rupees(e.base_minor)} · ${e.timeline.label}</p></section>
      <section><h3 class="eyebrow">Rooms and selections</h3>
        <table><thead><tr><th scope="col">Room</th><th scope="col">Item</th><th scope="col">Qty</th><th scope="col">Rate</th><th scope="col" class="num">Amount</th></tr></thead>
          <tbody>${(e.lines ?? []).map((l) => html`<tr><td>${humanize(l.room)}</td><td>${l.label}${l.typical ? html` <span class="badge">typical size</span>` : nothing}${l.optional ? html` <span class="badge">optional</span>` : nothing}</td><td>${l.quantity} ${l.uom}</td><td>${rupees(l.rate_minor)}</td><td class="num">${rupees(l.amount_minor)}</td></tr>`)}</tbody></table>
        <p class="meta">Room totals: ${e.rooms.map((r) => `${r.label} ${rupees(r.amount_minor)}`).join(' · ')}${e.optional_items_minor ? ` · optional items ${rupees(e.optional_items_minor)}` : ''}</p></section>
      <section><h3 class="eyebrow">${e.project_preparation.label} — ${rupees(e.project_preparation.amount_minor)}</h3>
        <ul>${(e.project_preparation.components ?? []).map((c) => html`<li>${c.label} (${c.inclusion}): ${rupees(c.amount_minor)}</li>`)}</ul>
        <p class="meta">Customers see this as one grouped value; the detailed final quotation shows every component.</p></section>
      <section><h3 class="eyebrow">${e.custom_features_allowance.label} — ${rupees(e.custom_features_allowance.low_minor)} – ${rupees(e.custom_features_allowance.high_minor)}</h3>
        <p class="meta">${e.custom_features_allowance.low_pct}–${e.custom_features_allowance.high_pct}% of room work ${rupees(e.custom_features_allowance.basis_minor ?? 0)}; midpoint ${rupees(e.custom_features_allowance.amount_minor ?? 0)} is in the base. Shown to the customer as its own range; the detailed quotation replaces it with the actual items.</p></section>
      <section><h3 class="eyebrow">Measurements</h3>
        <ul>${d.inputs.selections.map((s, i) => html`<li>${humanize(s.room)} – ${humanize(s.product)}: ${measurementRows(s, this.typicalInputs(s, i)).map((m) => (m.typical ? `${humanize(m.name)} typical` : `${humanize(m.name)} ${m.value} ${m.unit}`)).join(', ') || 'no measurement needed'}</li>`)}</ul></section>
      ${d.specification ? html`<section><h3 class="eyebrow">What the customer was promised (${d.specification.spec_code})</h3>
        <ul>${(d.room_details ?? []).map((r) => html`<li>${humanize(r.room)}: ${r.materials?.line ?? 'materials confirmed in the detailed quotation'}</li>`)}</ul>
        <p class="meta">Carry these into the detailed quotation: each line maps to the specification categories listed in the customer-promise matrix.</p></section>` : nothing}
      <section><h3 class="eyebrow">Assumptions</h3><ul>${e.assumptions.map((a) => html`<li>${a}</li>`)}</ul></section>
      <section><h3 class="eyebrow">Exclusions and client scope</h3><ul>${[...e.exclusions, ...e.client_scope.map((c) => `${c} (client scope)`)].map((x) => html`<li>${x}</li>`)}</ul></section>
      <section><h3 class="eyebrow">Warranty summary</h3><ul>${e.warranty.items.map((w) => html`<li>${w}</li>`)}</ul></section>
      ${d.lead ? html`<p class="meta">Linked lead ${d.lead.lead_number} (${humanize(d.lead.status)})</p>` : nothing}
      <section class="no-print"><h3 class="eyebrow">History</h3><ul>${d.events.map((ev) => html`<li>${humanize(ev.type)} · ${formatFull(ev.on)}</li>`)}</ul></section>
      ${manage ? html`<div class="actions">
        <button class="btn small" ?disabled=${this.busy} @click=${() => void this.act('duplicate', undefined, 'Estimate duplicated')}>Duplicate</button>
        <button class="btn small" ?disabled=${this.busy} @click=${() => (this.dialog = 'revise')}>Revise measurements or package</button>
        <button class="btn small" ?disabled=${this.busy} @click=${() => void this.consultationCopy()}>Consultation copy</button>
        <button class="btn small" ?disabled=${this.busy || d.site_measurement_required} @click=${() => void this.act('site-measurement', undefined, 'Site measurement marked as required')}>Mark site measurement required</button>
        <button class="btn small" ?disabled=${this.busy || !d.lead} @click=${() => void this.act('quotation-process', undefined, 'Official quotation process recorded')}>Start official quotation</button>
      </div>` : nothing}
    </div>`;
  }

  private renderRevise(d: EstimateDetail) {
    return html`<form id="rev" class="stack" @submit=${(ev: Event) => this.submitRevision(ev)}>
      ${this.problem ? html`<vs-problem-banner .problem=${this.problem}></vs-problem-banner>` : nothing}
      <label class="field"><span class="label">Package</span>
        <select name="package">${PACKAGES.map((p) => html`<option value=${p} ?selected=${p === d.package}>${humanize(p)}</option>`)}</select></label>
      <p class="meta">Only approved packages are accepted. Leave a measurement empty to use the typical size.</p>
      ${d.inputs.selections.map((s, i) => {
        const rows = measurementRows(s, this.typicalInputs(s, i));
        return rows.length ? html`<fieldset><legend>${humanize(s.room)} – ${humanize(s.product)}</legend>
          ${rows.map((m) => html`<label class="field"><span class="label">${humanize(m.name)} (${m.unit})</span>
            <input name=${`${i}|${m.name}|${m.unit}`} inputmode="decimal" .value=${m.value} placeholder="typical" /></label>`)}</fieldset>` : nothing;
      })}
    </form>`;
  }

  private renderCopy() {
    const c = this.copy as { title?: string; reference?: string; range?: { low_minor: number; high_minor: number }; disclaimer?: string; assumptions?: string[]; custom_features_allowance?: { label: string; description: string; low_minor: number; high_minor: number } } | null;
    if (!c) return nothing;
    const allowance = c.custom_features_allowance;
    return html`<div class="stack"><h3>${c.title}</h3><p class="meta">Consultation copy · ${c.reference}</p><p>${c.disclaimer}</p>
      ${c.range ? html`<p class="range">${rangeText(c.range)}</p>` : nothing}
      ${allowance ? html`<p>${allowance.label}: ${rangeText(allowance)} — ${allowance.description}</p>` : nothing}<ul>${(c.assumptions ?? []).map((a) => html`<li>${a}</li>`)}</ul>
      <p class="meta">A preliminary budgetary estimate, not a quotation.</p></div>`;
  }

  override render() {
    if (!this.can('estimate.read') || !this.estimates?.length) return nothing;
    return html`<section class="card stack"><h2 class="eyebrow">Budgetary Estimate</h2>
      ${this.problem ? html`<vs-problem-banner .problem=${this.problem}></vs-problem-banner>` : nothing}
      ${this.estimates.map((e) => html`<div class="stack">
        <div class="range">${rangeText(e.range)}</div>
        <div class="meta">${e.reference} · ${humanize(e.package)} · ${formatFull(e.created_on)} · ${humanize(e.origin)}${e.site_measurement_required ? ' · site measurement required' : ''}</div>
        <button class="btn small" @click=${() => void this.open(e.id)}>View estimate</button></div>`)}
      <vs-dialog wide .open=${this.dialog === 'detail'} heading="Preliminary Budgetary Estimate" @close=${() => (this.dialog = '')}>
        ${this.detail && this.dialog === 'detail' ? this.renderDetail(this.detail) : nothing}</vs-dialog>
      <vs-dialog wide .open=${this.dialog === 'revise'} heading="Revise estimate" @close=${() => (this.dialog = 'detail')}>
        ${this.detail && this.dialog === 'revise' ? this.renderRevise(this.detail) : nothing}
        <div slot="actions"><button class="btn" @click=${() => (this.dialog = 'detail')}>Cancel</button><button class="btn primary" form="rev" ?disabled=${this.busy}>Create revised estimate</button></div></vs-dialog>
      <vs-dialog wide .open=${this.dialog === 'copy'} heading="Consultation copy" @close=${() => (this.dialog = 'detail')}>
        ${this.renderCopy()}<div slot="actions"><button class="btn" @click=${() => window.print()}>Print</button></div></vs-dialog>
    </section>`;
  }
}
customElements.define('vs-estimate-panel', VsEstimatePanel);
