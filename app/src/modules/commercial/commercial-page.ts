import { css, html, nothing, type TemplateResult } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatINR, humanize } from '../../core/format/format.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import {
  commercial, type Boq, type BoqLine, type Estimate, type Issue, type Journey, type Lineage, type PolicyView,
  type Quotation, type Requirement, type Scope, type ScopeItem,
} from './api.js';

type Tab = 'overview' | 'scope' | 'boq' | 'estimate' | 'quotation';
const money = (minor: number | null | undefined) => (minor === null || minor === undefined ? '—' : formatINR(minor / 100));
const qty = (centi: number | null | undefined) => (centi === null || centi === undefined ? '—' : (centi / 100).toFixed(2));
const REQUIREMENT_TYPES = ['WARDROBE', 'TV_UNIT', 'CROCKERY_UNIT', 'STUDY_UNIT', 'VANITY', 'DRESSER', 'KITCHEN', 'KITCHEN_TALL_UNIT',
  'UTILITY_UNIT', 'BED', 'SIDE_TABLE', 'STORAGE_UNIT', 'FALSE_CEILING', 'PROFILE_LIGHTING', 'WALL_PANELLING', 'MIRROR_PANEL',
  'CURTAIN_PELMET', 'PARTITION', 'POOJA_UNIT', 'WINDOW_SEATING', 'PAINTING', 'ELECTRICAL', 'ELECTRICAL_SHIFTING', 'SENSOR_LIGHTING', 'CUSTOM'];

function byRoom<T extends { space_label: string | null }>(rows: T[]): [string, T[]][] {
  const out = new Map<string, T[]>();
  for (const r of rows) {
    const k = r.space_label ?? 'Project-wide';
    out.set(k, [...(out.get(k) ?? []), r]);
  }
  return [...out.entries()];
}

/**
 * The measurement-to-quotation workspace of one property (MTQ B2-B4): Scope → BOQ → Estimate → Quotation, reviewed
 * room by room. Every stage shows the upstream revision it was built from, whether it is stale, what blocks it, and
 * which owner decisions keep a quotation from being customer-issuable. The server decides everything; this page shows
 * it and sends staff decisions back.
 */
export class VsCommercialPage extends SessionElement {
  static override properties = {
    location: { attribute: false }, tab: { state: true }, journey: { state: true }, policy: { state: true },
    requirements: { state: true }, scope: { state: true }, boq: { state: true }, previousBoq: { state: true },
    boqDiff: { state: true }, estimate: { state: true }, quotation: { state: true }, documentHtml: { state: true },
    problem: { state: true }, disabled: { state: true }, busy: { state: true }, tier: { state: true },
  };
  declare location: { params: Record<string, string> } | undefined;
  declare tab: Tab;
  declare journey: Journey | null;
  declare policy: PolicyView | null;
  declare requirements: Requirement[];
  declare scope: Scope | null;
  declare boq: Boq | null;
  declare previousBoq: Boq | null;
  declare boqDiff: { change: string; label: string; from_quantity_centi: number | null; to_quantity_centi: number | null }[] | null;
  declare estimate: Estimate | null;
  declare quotation: Quotation | null;
  declare documentHtml: string | null;
  declare problem: ApiProblem | null;
  declare disabled: boolean;
  declare busy: boolean;
  declare tier: string;

  static override styles = [...shared, pageStyles, tableStyles, css`
    .lineage { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
    .lineage .card { padding: 12px; }
    .totals { display: flex; gap: 24px; flex-wrap: wrap; }
    .totals div { display: flex; flex-direction: column; }
    .totals .n { font: 600 20px/1.2 var(--vs-font-sans); }
    td.num, th.num { text-align: right; white-space: nowrap; }
    .derivation { font-size: 12px; color: var(--vs-ink-muted); }
    iframe { width: 100%; min-height: 520px; border: 1px solid var(--vs-line); border-radius: 8px; background: var(--vs-surface); }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; }
    button { min-height: 44px; }
  `];

  constructor() {
    super();
    this.tab = 'overview';
    this.journey = null; this.policy = null; this.requirements = []; this.scope = null; this.boq = null; this.previousBoq = null;
    this.boqDiff = null; this.estimate = null; this.quotation = null; this.documentHtml = null; this.problem = null;
    this.disabled = false; this.busy = false; this.tier = 'ESSENTIAL';
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private get propertyId(): string { return this.location?.params?.id ?? ''; }

  private async act(fn: () => Promise<unknown>) {
    this.problem = null;
    this.busy = true;
    try { await fn(); await this.load(); } catch (e) { this.problem = e as ApiProblem; } finally { this.busy = false; }
  }

  private async load() {
    try {
      const j = (await commercial.journey(this.propertyId)).data;
      this.journey = j;
      this.policy = (await commercial.policy()).data;
      this.requirements = (await commercial.requirements(this.propertyId)).data;
      const latestScope = j.scopes[0];
      this.scope = latestScope ? (await commercial.scope(latestScope.id)).data : null;
      const [b0, b1] = j.boqs;
      this.boq = b0 && this.can('boq.read') ? (await commercial.boq(b0.id)).data : null;
      this.previousBoq = b1 ?? null;
      this.boqDiff = b0 && b1 ? (await commercial.boqDiff(b1.id, b0.id)).data.lines : null;
      const e0 = j.cost_estimates?.[0];
      this.estimate = e0 ? (await commercial.estimate(e0.id)).data : null;
      const q0 = j.quotations?.[0];
      this.quotation = q0 ? (await commercial.quotation(q0.id)).data : null;
      this.documentHtml = q0 ? (await commercial.document(q0.id)).data.html : null;
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404 && !this.journey) this.disabled = true; else this.problem = p;
    }
  }

  override render() {
    if (this.disabled) {
      return html`<div class="page stack"><h1 class="display">Scope and quotation</h1>
        <vs-empty-state heading="Not enabled here">Scope, BOQ, estimates and quotations are not enabled here.</vs-empty-state></div>`;
    }
    const j = this.journey;
    const tabs = [
      { id: 'overview', label: 'Overview' }, { id: 'scope', label: 'Scope' }, { id: 'boq', label: 'BOQ', hidden: !this.can('boq.read') },
      { id: 'estimate', label: 'Estimate', hidden: !this.can('cost_estimate.read') },
      { id: 'quotation', label: 'Quotation', hidden: !this.can('quotation.read') || j?.quotations === undefined },
    ];
    return html`<div class="page stack">
      <div class="page-head"><h1 class="display">Scope and quotation${j ? html` · ${j.property_number}` : nothing}</h1></div>
      ${this.problem ? html`<vs-problem-banner .problem=${this.problem}></vs-problem-banner>` : nothing}
      ${j && j.ruleset.status !== 'APPROVED' ? html`<vs-banner kind="warning">Scope rules ${j.ruleset.version} are PROPOSED (owner
        decisions OI-MTQ-03 and OI-MTQ-04 not recorded): every recommendation needs a staff decision, and nothing built on them
        can be issued to a customer.</vs-banner>` : nothing}
      <vs-tabs label="Commercial stages" .tabs=${tabs} .selected=${this.tab} @tab-change=${(e: CustomEvent) => { this.tab = e.detail as Tab; }}>
        ${j ? this.panel(j) : html`<vs-skeleton rows="6"></vs-skeleton>`}
      </vs-tabs>
    </div>`;
  }

  private panel(j: Journey): TemplateResult {
    switch (this.tab) {
      case 'scope': return this.scopePanel();
      case 'boq': return this.boqPanel();
      case 'estimate': return this.estimatePanel();
      case 'quotation': return this.quotationPanel();
      default: return this.overview(j);
    }
  }

  private stale(l: Lineage | undefined) {
    if (!l?.stale) return html`<span class="chip success">Current</span>`;
    return html`<span class="chip warning" title=${l.reasons.map((r) => r.message).join(' ')}>Stale</span>`;
  }

  private issues(list: Issue[], heading: string) {
    if (!list.length) return nothing;
    return html`<section class="card stack" aria-label=${heading}><h3 class="title">${heading}</h3><ul>
      ${list.map((b) => html`<li><strong>${humanize(b.code)}</strong>${b.decision ? html` <span class="chip">${b.decision}</span>` : nothing}
        ${b.severity === 'WARNING' ? html`<span class="chip">warning</span>` : nothing} — ${b.message ?? ''}</li>`)}</ul></section>`;
  }

  // --- overview -------------------------------------------------------------------------------------------------------
  private overview(j: Journey) {
    const s = j.scopes[0]; const b = j.boqs[0]; const e = j.cost_estimates?.[0]; const q = j.quotations?.[0];
    const undecided = Object.entries(this.policy?.decisions ?? {}).filter(([, d]) => !d.decided);
    return html`<section class="stack" aria-labelledby="lin"><h2 id="lin" class="title">Lineage</h2>
      <div class="lineage">
        <div class="card"><div class="eyebrow">Measurements</div>${j.current_measurement_set
          ? html`Revision ${j.current_measurement_set.revision_no} · ${j.current_measurement_set.survey_level_code}` : 'No verified set'}</div>
        <div class="card"><div class="eyebrow">Scope</div>${s ? html`Revision ${s.revision_no} · ${humanize(s.status)} ${this.stale(s.lineage)}` : '—'}</div>
        <div class="card"><div class="eyebrow">BOQ</div>${b ? html`Revision ${b.revision_no} · ${humanize(b.status)} ${this.stale(b.lineage)}` : '—'}</div>
        <div class="card"><div class="eyebrow">Estimate</div>${e ? html`Revision ${e.revision_no} · ${humanize(e.status)} ${this.stale(e.lineage)}` : '—'}</div>
        <div class="card"><div class="eyebrow">Quotation</div>${q ? html`${q.label} · ${humanize(q.status)}` : '—'}</div>
      </div></section>
      <section class="card stack" aria-labelledby="dec"><h2 id="dec" class="title">Owner decisions not recorded</h2>
        ${undecided.length ? html`<ul>${undecided.map(([code, d]) => html`<li>${code}: ${d.label}</li>`)}</ul>
          <p class="muted small">Each blocks a customer-issuable quotation or keeps its feature disabled; none is assumed.</p>`
          : html`<p>All recorded (${this.policy?.version}).</p>`}</section>`;
  }

  // --- scope ----------------------------------------------------------------------------------------------------------
  private scopePanel() {
    const proposed = this.requirements.filter((r) => r.status === 'PROPOSED').length;
    const edit = this.can('scope.edit');
    return html`<section class="stack" aria-labelledby="req"><h2 id="req" class="title">Requirements</h2>
      <p class="muted">${proposed} recommendation(s) await a decision. Nothing is accepted without one.</p>
      ${edit ? html`<div class="actions"><button class="btn" ?disabled=${this.busy} @click=${() => this.act(() => commercial.seed(this.propertyId))}>Propose from measurements</button></div>` : nothing}
      ${byRoom(this.requirements).map(([room, rows]) => html`<h3 class="title">${room}</h3><div class="table-wrap"><table>
        <thead><tr><th>Requirement</th><th>Classification</th><th>Why</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>${rows.map((r) => html`<tr><td>${r.label}${r.catalogue_mapped ? nothing : html` <span class="chip warning">no catalogue line</span>`}</td>
          <td><span class="chip">${humanize(r.classification)}</span> <span class="small muted">${humanize(r.origin_code)}</span></td>
          <td class="small">${r.source_ref.fact ?? humanize(r.source_code)}</td><td>${humanize(r.status)}</td>
          <td>${edit ? html`<div class="actions">
            <button class="btn small" aria-label="Accept ${r.label} (${room})" @click=${() => this.act(() => commercial.decide(r, 'ACCEPTED'))}>Accept</button>
            <button class="btn small ghost" aria-label="Exclude ${r.label} (${room})" @click=${() => {
              const reason = prompt('Why is it excluded?') ?? undefined; if (reason !== undefined) void this.act(() => commercial.decide(r, 'EXCLUDED', reason)); }}>Exclude</button>
            <button class="btn small ghost" aria-label="Not applicable: ${r.label} (${room})" @click=${() => this.act(() => commercial.decide(r, 'NOT_APPLICABLE', 'Not applicable on site'))}>N/A</button></div>` : nothing}</td></tr>`)}
        </tbody></table></div>`)}
      ${edit ? this.addRequirement() : nothing}
    </section>${this.scopeRevision()}`;
  }

  private addRequirement() {
    const spaces = [...new Map(this.requirements.filter((r) => r.space_id).map((r) => [r.space_id!, r.space_label ?? ''])).entries()];
    const submit = (e: Event) => {
      e.preventDefault();
      const f = new FormData(e.target as HTMLFormElement);
      const body: Record<string, unknown> = { requirement_type_code: f.get('type'), source_code: f.get('source'), necessity_code: f.get('necessity'),
        space_id: f.get('space') || null, custom_label: f.get('custom') || null, notes: f.get('notes') || null };
      void this.act(() => commercial.addRequirement(this.propertyId, body));
    };
    return html`<form class="card stack" @submit=${submit} aria-labelledby="addreq"><h3 id="addreq" class="title">Add a requirement</h3>
      <div class="grid-2">
        <label class="field"><span class="label">Space</span><select name="space"><option value="">Project-wide</option>
          ${spaces.map(([id, label]) => html`<option value=${id}>${label}</option>`)}</select></label>
        <label class="field"><span class="label">Item</span><select name="type">${REQUIREMENT_TYPES.map((t) => html`<option value=${t}>${humanize(t)}</option>`)}</select></label>
        <label class="field"><span class="label">Source</span><select name="source"><option value="CUSTOMER_REQUEST">Customer request</option>
          <option value="STAFF_SELECTION">Staff selection</option><option value="MANUAL">Manual addition</option></select></label>
        <label class="field"><span class="label">Strength</span><select name="necessity"><option>RECOMMENDED</option><option>MANDATORY</option><option>OPTIONAL</option></select></label>
        <label class="field"><span class="label">Custom label (custom items)</span><input name="custom" maxlength="120"></label>
        <label class="field"><span class="label">Notes</span><input name="notes" maxlength="500"></label>
      </div><div><button class="btn primary" ?disabled=${this.busy}>Add</button></div></form>`;
  }

  private scopeRevision() {
    const s = this.scope;
    const edit = this.can('scope.edit');
    return html`<section class="stack" aria-labelledby="scp"><h2 id="scp" class="title">Scope revision${s ? html` ${s.revision_no} · ${humanize(s.status)}` : nothing}</h2>
      ${s ? html`<p class="small muted">Measurements revision ${s.measurement_revision_no} · ruleset ${s.ruleset_version} (${s.ruleset_status}) · tier ${humanize(s.tier_code)} ${this.stale(s.lineage)}</p>` : nothing}
      <div class="actions">
        ${edit && (!s || s.status !== 'DRAFT') ? html`<label class="field"><span class="label">Tier</span><select @change=${(e: Event) => { this.tier = (e.target as HTMLSelectElement).value; }}>
          <option>ESSENTIAL</option><option>PREMIUM</option><option>LUXURY</option></select></label>
          <button class="btn primary" ?disabled=${this.busy} @click=${() => this.act(() => commercial.draftScope(this.propertyId, this.tier))}>Draft a new scope revision</button>` : nothing}
        ${edit && s?.status === 'DRAFT' ? html`<button class="btn" ?disabled=${this.busy} @click=${() => this.act(() => commercial.refreshScope(s))}>Refresh from requirements</button>` : nothing}
        ${this.can('scope.confirm') && s?.status === 'DRAFT' ? html`<button class="btn primary" ?disabled=${this.busy} @click=${() => this.act(() => commercial.confirmScope(s))}>Confirm scope</button>` : nothing}
      </div>
      ${s?.items ? byRoom(s.items).map(([room, items]) => html`<h3 class="title">${room}</h3><div class="table-wrap"><table>
        <thead><tr><th>Item</th><th>Origin</th><th>Inclusion</th><th>Inputs (from measurements)</th><th><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>${items.map((i) => this.itemRow(i, s.status === 'DRAFT' && edit))}</tbody></table></div>`) : nothing}
      ${s?.exclusions?.length ? html`<p class="small">Excluded: ${s.exclusions.map((e) => `${e.label}${e.space_label ? ` (${e.space_label})` : ''}`).join('; ')}</p>` : nothing}
    </section>`;
  }

  private itemRow(i: ScopeItem, editable: boolean) {
    const override = () => {
      const name = prompt(`Input to enter (${Object.keys(i.inputs).join(', ')})`);
      if (!name) return;
      const value = prompt(`${name} value (card unit)`);
      const reason = prompt('Why is the measured value overridden?');
      if (value && reason) void this.act(() => commercial.patchItem(i, { dimension_overrides: { ...i.dimension_overrides, [name]: Number(value) }, override_reason: reason }));
    };
    return html`<tr><td>${i.label}${i.catalogue_mapped ? nothing : html`<br><span class="chip warning">${i.unmapped_reason}</span>`}
        ${i.finish_code ? html`<br><span class="small">${humanize(i.finish_code)}</span>` : nothing}</td>
      <td><span class="chip">${humanize(i.origin_code)}</span></td>
      <td>${editable ? html`<select aria-label="Inclusion of ${i.label}" @change=${(e: Event) => this.act(() => commercial.patchItem(i, { inclusion_code: (e.target as HTMLSelectElement).value, notes: 'Changed in review' }))}>
          ${['INCLUDED', 'OPTIONAL', 'EXCLUDED'].map((c) => html`<option ?selected=${c === i.inclusion_code}>${c}</option>`)}</select>` : humanize(i.inclusion_code)}</td>
      <td class="small">${Object.entries(i.inputs).map(([n, d]) => html`<div>${n}: ${i.dimension_overrides[n] ?? d.value ?? '—'} ${d.unit ?? ''}
        <span class="chip ${d.source === 'MISSING' || d.source === 'ASSUMED' ? 'warning' : ''}">${n in i.dimension_overrides ? 'staff' : d.source.toLowerCase()}</span>
        <span class="derivation">${d.explain}</span></div>`)}
        ${i.override_reason ? html`<div class="warning-text">Override: ${i.override_reason}</div>` : nothing}</td>
      <td>${editable ? html`<button class="btn small" aria-label="Enter a value for ${i.label}" @click=${override}>Enter value</button>` : nothing}</td></tr>`;
  }

  // --- BOQ ------------------------------------------------------------------------------------------------------------
  private boqPanel() {
    const b = this.boq;
    const confirmed = this.journey?.scopes.find((s) => s.status === 'CONFIRMED');
    return html`<section class="stack" aria-labelledby="boqh"><h2 id="boqh" class="title">BOQ${b ? html` revision ${b.revision_no} · ${humanize(b.status)}` : nothing}</h2>
      <div class="actions">${this.can('boq.generate') && confirmed ? html`<button class="btn" ?disabled=${this.busy} @click=${() => this.act(() => commercial.generateBoq(confirmed.id))}>Generate from scope revision ${confirmed.revision_no}</button>` : nothing}
        ${this.can('boq.review') && b?.status === 'GENERATED' ? html`<button class="btn primary" ?disabled=${this.busy} @click=${() => this.act(() => commercial.reviewBoq(b))}>Review and seal</button>` : nothing}</div>
      ${b ? html`<p class="small muted">Scope revision ${b.scope_revision_no} · measurements revision ${b.measurement_revision_no} · catalogue ${b.catalogue_card_version} · engine ${b.quantity_engine_version} ${this.stale(b.lineage)}</p>
        ${this.issues(b.issues, 'BOQ issues')}
        ${byRoom(b.lines ?? []).map(([room, lines]) => html`<h3 class="title">${room}</h3><div class="table-wrap"><table>
          <thead><tr><th>Line</th><th class="num">Quantity</th><th>Unit</th><th>How it was measured</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead>
          <tbody>${lines.map((l) => this.boqRow(l, b.status === 'GENERATED' && this.can('boq.override')))}</tbody></table></div>`)}
        ${this.boqDiff?.length ? html`<h3 class="title">Changes from revision ${this.previousBoq?.revision_no}</h3><ul>
          ${this.boqDiff.map((d) => html`<li>${humanize(d.change)}: ${d.label} ${qty(d.from_quantity_centi)} → ${qty(d.to_quantity_centi)}</li>`)}</ul>` : nothing}`
        : html`<p>No BOQ yet.</p>`}</section>`;
  }

  private boqRow(l: BoqLine, editable: boolean) {
    const override = () => {
      const value = prompt(`Quantity for ${l.label} (${l.unit_text})`);
      const reason = value ? prompt('Why is the calculated quantity overridden?') : null;
      if (value && reason) void this.act(() => commercial.overrideLine(l, Math.round(Number(value) * 100), reason));
    };
    return html`<tr><td>${l.label}${l.is_optional ? html` <span class="chip">optional</span>` : nothing}</td>
      <td class="num">${qty(l.final_quantity_centi)}${l.override_quantity_centi !== null ? html`<br><span class="small warning-text">calculated ${qty(l.calculated_quantity_centi)}</span>` : nothing}</td>
      <td>${l.unit_text}</td>
      <td class="derivation">${l.derivation}${l.override_reason ? html`<div class="warning-text">Override: ${l.override_reason}</div>` : nothing}</td>
      <td>${l.issues.length ? l.issues.map((i) => html`<span class="chip ${i.severity === 'BLOCKING' ? 'danger' : 'warning'}">${humanize(i.code)}</span> `) : html`<span class="chip success">OK</span>`}</td>
      <td>${editable && l.uom_code ? html`<div class="actions"><button class="btn small" aria-label="Override ${l.label}" @click=${override}>Override</button>
        ${l.override_quantity_centi !== null ? html`<button class="btn small ghost" aria-label="Clear override of ${l.label}" @click=${() => this.act(() => commercial.clearOverride(l))}>Clear</button>` : nothing}</div>` : nothing}</td></tr>`;
  }

  // --- estimate -------------------------------------------------------------------------------------------------------
  private estimatePanel() {
    const e = this.estimate;
    const reviewed = this.journey?.boqs.find((b) => b.status === 'REVIEWED');
    return html`<section class="stack" aria-labelledby="esth"><h2 id="esth" class="title">Estimate${e ? html` revision ${e.revision_no} · ${humanize(e.status)}` : nothing}</h2>
      <div class="actions">${this.can('cost_estimate.create') && reviewed ? html`<label class="field"><span class="label">Tier</span>
          <select @change=${(ev: Event) => { this.tier = (ev.target as HTMLSelectElement).value; }}><option>ESSENTIAL</option><option>PREMIUM</option><option>LUXURY</option></select></label>
        <button class="btn" ?disabled=${this.busy} @click=${() => this.act(() => commercial.price(reviewed.id, this.tier))}>Price BOQ revision ${reviewed.revision_no}</button>` : nothing}
        ${this.can('cost_estimate.approve') && e?.status === 'DRAFT' ? html`<button class="btn primary" ?disabled=${this.busy} @click=${() => this.act(() => commercial.approveEstimate(e))}>Approve</button>` : nothing}</div>
      ${e ? html`<p class="small muted">BOQ revision ${e.boq_revision_no}${e.rate_card_version ? html` · rate card ${e.rate_card_version}` : nothing} · tier ${humanize(e.tier_code)} · basis ${humanize(e.pricing_basis_code)} ${this.stale(e.lineage)}</p>
        <div class="totals" role="group" aria-label="Totals">
          <div><span class="eyebrow">Subtotal</span><span class="n">${money(e.subtotal_minor)}</span></div>
          <div><span class="eyebrow">Discount</span><span class="n">${money(e.discount_minor)}</span></div>
          <div><span class="eyebrow">GST</span><span class="n">${e.tax_status === 'APPLIED' ? money(e.tax_minor) : 'Not decided'}</span></div>
          <div><span class="eyebrow">Total</span><span class="n">${e.total_minor === null ? 'Before GST' : money(e.total_minor)}</span></div>
          <div><span class="eyebrow">Optional</span><span class="n">${money(e.optional_minor)}</span></div></div>
        ${this.issues(e.blockers, 'What blocks approval or issue')}
        ${(['rooms', 'categories', 'components'] as const).map((k) => html`<h3 class="title">By ${k === 'rooms' ? 'room' : k === 'categories' ? 'category' : 'cost component'}</h3>
          <div class="table-wrap"><table><thead><tr><th>${k === 'rooms' ? 'Room' : 'Group'}</th><th class="num">Amount</th><th class="num">Discount</th><th class="num">Optional</th><th class="num">Unpriced lines</th></tr></thead>
          <tbody>${e.views[k].map((v) => html`<tr><td>${v.label}</td><td class="num">${money(v.amount_minor)}</td><td class="num">${money(v.discount_minor)}</td>
            <td class="num">${money(v.optional_minor)}</td><td class="num">${v.unpriced_lines}</td></tr>`)}</tbody></table></div>`)}
        <h3 class="title">Lines</h3><div class="table-wrap"><table><thead><tr><th>Line</th><th class="num">Quantity</th>${this.can('cost_estimate.rate.view') ? html`<th class="num">Rate</th>` : nothing}<th class="num">Amount</th><th>Pricing</th></tr></thead>
          <tbody>${(e.lines ?? []).map((l) => html`<tr><td>${l.label}<br><span class="small muted">${l.space_label ?? 'Project'} · ${humanize(l.component_code)}</span></td>
            <td class="num">${qty(l.quantity_centi)}</td>${this.can('cost_estimate.rate.view') ? html`<td class="num">${money(l.rate_minor)}</td>` : nothing}
            <td class="num">${money(l.amount_minor)}</td><td>${l.rate_status === 'PRICED' ? html`<span class="chip success">priced</span>` : html`<span class="chip warning">${humanize(l.rate_status)}</span><br><span class="small">${l.rate_note ?? ''}</span>`}</td></tr>`)}</tbody></table></div>
        <section class="card stack" aria-labelledby="disc"><h3 id="disc" class="title">Discounts</h3>
          ${e.discount_policy?.enabled ? html`<p class="small">Own authority up to ${(e.discount_policy.self_limit_bp ?? 0) / 100}% · maximum ${(e.discount_policy.max_bp ?? 0) / 100}%</p>
            ${(e.adjustments ?? []).map((a) => html`<div>${humanize(a.scope_code)} ${a.kind_code === 'PERCENT' ? `${(a.value_bp ?? 0) / 100}%` : money(a.amount_minor)}: ${money(a.base_minor)} → ${money(a.post_minor)}
              <span class="chip">${humanize(a.status)}</span> ${a.reason}
              ${a.status === 'PROPOSED' && this.can('cost_estimate.discount.approve') ? html`<button class="btn small" @click=${() => this.act(() => commercial.decideDiscount(a, 'APPROVE'))}>Approve</button>
                <button class="btn small ghost" @click=${() => this.act(() => commercial.decideDiscount(a, 'REJECT'))}>Reject</button>` : nothing}</div>`)}`
            : html`<vs-banner kind="info">${e.discount_policy?.message ?? 'Discounts are disabled.'}</vs-banner>`}</section>`
        : html`<p>No estimate yet.</p>`}</section>`;
  }

  // --- quotation ------------------------------------------------------------------------------------------------------
  private quotationPanel() {
    const q = this.quotation;
    const approved = this.journey?.cost_estimates?.find((e) => e.status === 'APPROVED');
    const action = (name: string, body?: Record<string, unknown>) => () => q && this.act(() => commercial.quotationAction(q, name, body));
    return html`<section class="stack" aria-labelledby="qh"><h2 id="qh" class="title">Quotation${q ? html` ${q.label} · ${humanize(q.status)}` : nothing}</h2>
      <div class="actions">
        ${this.can('quotation.create') && approved && !q ? html`<button class="btn primary" ?disabled=${this.busy} @click=${() => this.act(() => commercial.createQuotation(approved.id))}>Create from estimate revision ${approved.revision_no}</button>` : nothing}
        ${q && q.status === 'DRAFT' && this.can('quotation.create') ? html`<button class="btn" @click=${action('submit')}>Submit for review</button>` : nothing}
        ${q && q.status === 'INTERNAL_REVIEW' && this.can('quotation.approve') ? html`<button class="btn primary" @click=${action('approve')}>Approve</button>` : nothing}
        ${q && ['INTERNAL_REVIEW', 'APPROVED'].includes(q.status) && this.canAny('quotation.create', 'quotation.approve') ? html`<button class="btn ghost" @click=${() => {
          const reason = prompt('Why does it go back to draft?'); if (reason) void action('return', { reason })(); }}>Return to draft</button>` : nothing}
        ${q && q.status === 'APPROVED' && this.can('quotation.issue') ? html`<button class="btn primary" ?disabled=${!q.customer_issuable} @click=${action('issue')}>Issue to customer</button>` : nothing}
        ${q && q.status === 'ISSUED' && this.can('quotation.decision.record') ? html`<button class="btn" @click=${action('decision', { decision: 'ACCEPTED', method: 'SIGNED_COPY' })}>Record acceptance</button>
          <button class="btn ghost" @click=${action('decision', { decision: 'REJECTED', method: 'SIGNED_COPY' })}>Record rejection</button>` : nothing}
        ${q && approved && q.status !== 'ACCEPTED' && approved.id !== q.lineage.cost_estimate_id && this.can('quotation.create') ? html`<button class="btn" @click=${action('versions', { cost_estimate_id: approved.id })}>New version from estimate revision ${approved.revision_no}</button>` : nothing}
        ${q && q.status === 'ACCEPTED' && approved && approved.id !== q.lineage.cost_estimate_id && this.can('quotation.variation.create') ? html`<button class="btn" @click=${() => this.act(() => commercial.variation(q, approved.id))}>Raise a variation</button>` : nothing}
      </div>
      ${q ? html`<p class="small muted">Measurements r${q.lineage.measurement_revision_no} → scope r${q.lineage.scope_revision_no} → BOQ r${q.lineage.boq_revision_no} → estimate r${q.lineage.estimate_revision_no}${q.valid_until ? html` · valid until ${q.valid_until}` : nothing}
          ${q.snapshot_sha256 ? html` · frozen document ${q.snapshot_verified ? 'verified' : 'DIGEST MISMATCH'}` : nothing}</p>
        ${q.customer_issuable ? html`<vs-banner kind="success">Customer-issuable.</vs-banner>` : this.issues(q.blockers, 'Why it cannot be issued to a customer yet')}
        <div class="totals" role="group" aria-label="Quotation totals"><div><span class="eyebrow">Works</span><span class="n">${money(q.base_total_minor)}</span></div>
          <div><span class="eyebrow">GST</span><span class="n">${q.tax_status === 'APPLIED' ? money(q.tax_minor) : 'To be confirmed'}</span></div>
          <div><span class="eyebrow">Total</span><span class="n">${q.total_minor === null ? 'To be confirmed' : money(q.total_minor)}</span></div></div>
        ${this.documentHtml ? html`<h3 class="title">Customer document</h3><iframe title="Customer quotation document" sandbox="" .srcdoc=${this.documentHtml}></iframe>` : nothing}`
        : html`<p>No quotation yet.</p>`}</section>`;
  }
}

customElements.define('vs-commercial-page', VsCommercialPage);
