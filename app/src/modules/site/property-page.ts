import { css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatFull } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { site, type MeasurementSet, type Property, type Space, type Visit } from './api.js';
import { siteTargets } from './styles.js';
import { formatArea } from './units.js';

const SPACE_TYPES = ['LIVING', 'DINING', 'LIVING_DINING', 'FAMILY_LOUNGE', 'FOYER', 'PASSAGE', 'STAIRCASE', 'POOJA', 'MASTER_BEDROOM', 'BEDROOM',
  'CHILDREN_BEDROOM', 'GUEST_BEDROOM', 'PARENTS_BEDROOM', 'SERVANT_ROOM', 'DRESSING', 'WALK_IN_CLOSET', 'TOILET', 'POWDER_ROOM', 'STUDY',
  'HOME_OFFICE', 'MEDIA_ROOM', 'KITCHEN', 'UTILITY', 'STORE', 'LAUNDRY', 'BALCONY', 'TERRACE', 'SIT_OUT', 'PORCH', 'PARKING', 'GARDEN', 'CUSTOM'];
const label = (code: string) => code.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

/**
 * One property (MTQ B1-T10): its derived configuration, the space tree in walk order, measurement visits and the
 * revisions of its measurements. Space ids never change; archiving a space keeps it for history.
 */
export class VsPropertyPage extends SessionElement {
  static override properties = {
    location: { attribute: false }, property: { state: true }, visits: { state: true }, sets: { state: true },
    problem: { state: true }, disabled: { state: true }, addForm: { state: true }, visitForm: { state: true }, busy: { state: true },
  };
  declare location: { params: Record<string, string> } | undefined;
  declare property: Property | null;
  declare visits: Visit[];
  declare sets: MeasurementSet[];
  declare problem: ApiProblem | null;
  declare disabled: boolean;
  declare busy: boolean;
  declare addForm: { type: string; label: string; custom: string; parent: string; level: string };
  declare visitForm: { when: string; surveyor: string; level: string; contact: string; phone: string };

  static override styles = [...shared, pageStyles, tableStyles, siteTargets, css`
    .grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
    td.indent-1 { padding-left: 28px; } td.indent-2 { padding-left: 52px; }
    .stats { display: flex; gap: 24px; flex-wrap: wrap; }
    .stats div { display: flex; flex-direction: column; }
    .stats .n { font: 600 24px/1.1 var(--vs-font-sans); }
  `];

  constructor() {
    super();
    this.property = null; this.visits = []; this.sets = []; this.problem = null; this.disabled = false; this.busy = false;
    this.addForm = { type: 'BEDROOM', label: '', custom: '', parent: '', level: '0' };
    this.visitForm = { when: '', surveyor: '', level: 'FULL', contact: '', phone: '' };
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private get routeId(): string { return this.location?.params?.id ?? ''; }

  private async act(fn: () => Promise<unknown>) {
    this.problem = null;
    this.busy = true;
    try { await fn(); await this.load(); } catch (e) { this.problem = e as ApiProblem; } finally { this.busy = false; }
  }

  private async load() {
    try {
      this.property = (await site.property(this.routeId)).data;
      if (this.can('measurement.visit.read')) this.visits = (await site.visits({ property_id: this.routeId })).data;
      if (this.can('measurement.read')) this.sets = (await site.sets(this.routeId)).data;
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404 && !this.property) this.disabled = true; else this.problem = p;
    }
  }

  private depth(s: Space): number {
    let d = 0;
    let cur: Space | undefined = s;
    while (cur?.parent_space_id && d < 3) { cur = this.property?.spaces?.find((x) => x.id === cur!.parent_space_id); d += 1; }
    return d;
  }

  private move(s: Space, delta: number) {
    const ids = (this.property?.spaces ?? []).map((x) => x.id);
    const i = ids.indexOf(s.id);
    const j = i + delta;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    void this.act(() => site.orderSpaces(this.routeId, ids));
  }

  private addSpace() {
    const f = this.addForm;
    const body: Record<string, unknown> = { space_type_code: f.type, label: f.label.trim() || label(f.type), level_index: Number(f.level) || 0 };
    if (f.type === 'CUSTOM') body.custom_type_label = f.custom.trim();
    if (f.parent) body.parent_space_id = f.parent;
    void this.act(async () => { await site.addSpace(this.routeId, body); this.addForm = { ...this.addForm, label: '', custom: '' }; });
  }

  private schedule() {
    const f = this.visitForm;
    const body: Record<string, unknown> = { property_id: this.routeId, survey_level_code: f.level };
    if (f.when) body.scheduled_start_on = new Date(f.when).toISOString();
    if (f.surveyor.trim()) body.assigned_to = f.surveyor.trim();
    if (f.contact.trim()) body.customer_contact_name = f.contact.trim();
    if (f.phone.trim()) body.customer_contact_phone = f.phone.trim();
    void this.act(() => site.createVisit(body));
  }

  private transition(v: Visit, to: string) {
    if (to === 'CANCELLED') {
      const reason = prompt('Why is the visit cancelled?');
      if (!reason) return;
      void this.act(() => site.visitStatus(v, { to_status: to, reason }));
      return;
    }
    void this.act(() => site.visitStatus(v, { to_status: to }));
  }

  override render() {
    if (this.disabled) return html`<div class="page"><p>This property is not available, or site measurement is not enabled here.</p></div>`;
    const p = this.property;
    if (!p) return html`<div class="page"><p>Loading…</p></div>`;
    const spaces = p.spaces ?? [];
    const editable = this.can('property.update');
    return html`<div class="page stack">
      <header class="stack"><span class="eyebrow">${p.property_number}</span><h1 class="display">${p.display_label}</h1>
        <div class="stats">
          <div><span class="n">${p.derived_bedroom_count}</span><span class="small muted">bedrooms (derived)</span></div>
          <div><span class="n">${p.derived_toilet_count}</span><span class="small muted">toilets</span></div>
          <div><span class="n">${p.derived_level_count}</span><span class="small muted">levels</span></div>
          <div><span class="n">${formatArea(p.derived_measured_floor_area_sqft_centi) || '—'}</span><span class="small muted">measured (latest verified)</span></div>
        </div>
        ${p.configuration_label ? html`<p class="small muted">Customer's description: ${p.configuration_label}</p>` : nothing}
        ${this.me?.features?.mtq_estimation === true && this.can('scope.read')
          ? html`<p><a class="btn" href="/site/properties/${p.id}/commercial">Scope, BOQ and quotation</a></p>` : nothing}</header>
      ${this.problem ? html`<div role="alert" class="danger-text">${this.problem.detail ?? this.problem.title}</div>` : nothing}
      <section class="card stack" aria-labelledby="spaces"><h2 id="spaces" class="title">Spaces (walk order)</h2>
        <table><thead><tr><th>Space</th><th>Type</th><th>Level</th><th>In scope</th>${editable ? html`<th><span class="sr-only">Actions</span></th>` : nothing}</tr></thead><tbody>
          ${spaces.map((s, i) => html`<tr><td class="indent-${this.depth(s)}">${s.label}</td><td>${label(s.space_type_code)}${s.custom_type_label ? ` (${s.custom_type_label})` : ''}</td>
            <td>${s.level_index}</td><td>${editable ? html`<label class="hit"><input type="checkbox" aria-label="In scope: ${s.label}" .checked=${s.is_in_scope}
              @change=${(e: Event) => this.act(() => site.patchSpace(s, { is_in_scope: (e.target as HTMLInputElement).checked }))} /></label>` : s.is_in_scope ? 'Yes' : 'No'}</td>
            ${editable ? html`<td class="row">
              <button class="btn small ghost" aria-label="Move ${s.label} up" ?disabled=${i === 0} @click=${() => this.move(s, -1)}>↑</button>
              <button class="btn small ghost" aria-label="Move ${s.label} down" ?disabled=${i === spaces.length - 1} @click=${() => this.move(s, 1)}>↓</button>
              <button class="btn small ghost danger-text" @click=${() => { const r = prompt(`Archive ${s.label}? Give a reason.`); if (r !== null) void this.act(() => site.archiveSpace(s, r)); }}>Archive</button>
            </td>` : nothing}</tr>`)}
        </tbody></table>
        ${editable ? html`<fieldset><legend>Add a space</legend><div class="grid">
          <label class="field"><span class="label">Type</span><select @change=${(e: Event) => { this.addForm = { ...this.addForm, type: (e.target as HTMLSelectElement).value }; }}>
            ${SPACE_TYPES.map((t) => html`<option value=${t} ?selected=${t === this.addForm.type}>${label(t)}</option>`)}</select></label>
          <label class="field"><span class="label">Label</span><input .value=${this.addForm.label} @input=${(e: Event) => { this.addForm = { ...this.addForm, label: (e.target as HTMLInputElement).value }; }} /></label>
          ${this.addForm.type === 'CUSTOM' ? html`<label class="field"><span class="label">Custom type name</span><input .value=${this.addForm.custom}
            @input=${(e: Event) => { this.addForm = { ...this.addForm, custom: (e.target as HTMLInputElement).value }; }} /></label>` : nothing}
          <label class="field"><span class="label">Inside</span><select @change=${(e: Event) => { this.addForm = { ...this.addForm, parent: (e.target as HTMLSelectElement).value }; }}>
            <option value="">— (top level)</option>${spaces.map((s) => html`<option value=${s.id}>${s.label}</option>`)}</select></label>
          <label class="field"><span class="label">Level</span><input inputmode="numeric" .value=${this.addForm.level}
            @input=${(e: Event) => { this.addForm = { ...this.addForm, level: (e.target as HTMLInputElement).value }; }} /></label>
        </div><button class="btn" ?disabled=${this.busy} @click=${() => this.addSpace()}>Add space</button></fieldset>` : nothing}
      </section>
      ${this.can('measurement.visit.read') ? html`<section class="card stack" aria-labelledby="visits"><h2 id="visits" class="title">Visits</h2>
        <table><thead><tr><th>Visit</th><th>When</th><th>Surveyor</th><th>Survey</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>
          ${this.visits.map((v) => html`<tr><td>${v.visit_number}</td><td>${formatFull(v.scheduled_start_on)}</td><td>${v.assigned_to?.display_name ?? '—'}</td>
            <td>${label(v.survey_level_code)}</td><td>${label(v.status)}</td><td class="row">
            ${v.allowed_transitions.filter((t) => t !== 'SCHEDULED').map((t) => html`<button class="btn small" @click=${() => this.transition(v, t)}>${label(t)}</button>`)}</td></tr>`)}
        </tbody></table>
        ${this.can('measurement.visit.create') ? html`<fieldset><legend>Schedule a visit</legend><div class="grid">
          <label class="field"><span class="label">Start</span><input type="datetime-local" .value=${this.visitForm.when} @input=${(e: Event) => { this.visitForm = { ...this.visitForm, when: (e.target as HTMLInputElement).value }; }} /></label>
          <label class="field"><span class="label">Surveyor (user id)</span><input .value=${this.visitForm.surveyor} @input=${(e: Event) => { this.visitForm = { ...this.visitForm, surveyor: (e.target as HTMLInputElement).value }; }} /></label>
          <label class="field"><span class="label">Survey</span><select @change=${(e: Event) => { this.visitForm = { ...this.visitForm, level: (e.target as HTMLSelectElement).value }; }}>
            <option value="FULL">Full (quotation-ready)</option><option value="LITE">Lite (qualify the lead)</option></select></label>
          <label class="field"><span class="label">Contact on site</span><input .value=${this.visitForm.contact} @input=${(e: Event) => { this.visitForm = { ...this.visitForm, contact: (e.target as HTMLInputElement).value }; }} /></label>
          <label class="field"><span class="label">Contact phone</span><input type="tel" .value=${this.visitForm.phone} @input=${(e: Event) => { this.visitForm = { ...this.visitForm, phone: (e.target as HTMLInputElement).value }; }} /></label>
        </div><button class="btn" ?disabled=${this.busy} @click=${() => this.schedule()}>${this.visitForm.when ? 'Schedule' : 'Request'} visit</button></fieldset>` : nothing}
      </section>` : nothing}
      ${this.can('measurement.read') ? html`<section class="card stack" aria-labelledby="revs"><h2 id="revs" class="title">Measurement revisions</h2>
        <table><thead><tr><th>Revision</th><th>Survey</th><th>Status</th><th>Area</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>
          ${this.sets.map((m, i) => html`<tr><td>Rev ${m.revision_no}</td><td>${label(m.survey_level_code)}</td><td>${label(m.status)}</td>
            <td>${formatArea(m.summary?.total_floor_area_sqft_centi as number)}</td><td class="row">
            ${m.status === 'DRAFT' ? html`<button class="btn small primary" @click=${() => navigate(`/site/sets/${m.id}/capture`)}>Capture</button>`
              : html`<button class="btn small" @click=${() => navigate(`/site/sets/${m.id}/review`)}>Review</button>`}
            ${i > 0 ? html`<button class="btn small ghost" @click=${() => navigate(`/site/sets/${m.id}/review?compare=${this.sets[i - 1].id}`)}>Compare with rev ${this.sets[i - 1].revision_no}</button>` : nothing}
            </td></tr>`)}
        </tbody></table></section>` : nothing}
    </div>`;
  }
}

customElements.define('vs-property-page', VsPropertyPage);
