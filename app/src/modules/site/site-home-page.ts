import { css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatFull } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { site, type Property, type Templates, type Visit } from './api.js';
import { registerSiteWorker } from './pwa.js';

const label = (code: string) => code.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

/**
 * Site measurement home (MTQ B1-T10): the surveyor's visits, the properties in scope, and a new property for a lead,
 * optionally seeded from a template. BHK is chosen through the template and then derived from the spaces.
 */
export class VsSiteHomePage extends SessionElement {
  static override properties = {
    visits: { state: true }, properties: { state: true }, templates: { state: true }, problem: { state: true },
    disabled: { state: true }, form: { state: true }, busy: { state: true },
  };
  declare visits: Visit[];
  declare properties: Property[];
  declare templates: Templates | null;
  declare problem: ApiProblem | null;
  declare disabled: boolean;
  declare busy: boolean;
  declare form: { lead_id: string; property_type_code: string; template_key: string; include: string[]; city: string; built_up: string };

  static override styles = [...shared, pageStyles, tableStyles, css`
    .grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
    .opt { display: flex; flex-wrap: wrap; gap: 4px 16px; }
    .opt label { display: flex; gap: 6px; align-items: center; min-height: 32px; font-size: 13px; }
  `];

  constructor() {
    super();
    this.visits = []; this.properties = []; this.templates = null; this.problem = null; this.disabled = false; this.busy = false;
    this.form = { lead_id: '', property_type_code: 'APARTMENT', template_key: 'APARTMENT_3BHK', include: [], city: '', built_up: '' };
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private async load() {
    this.problem = null;
    try {
      this.templates = (await site.templates()).data;
      registerSiteWorker();
    } catch (e) {
      if ((e as ApiProblem).status === 404) { this.disabled = true; return; }
      this.problem = e as ApiProblem;
      return;
    }
    try {
      if (this.can('measurement.visit.read')) {
        this.visits = (await site.visits({ assigned_to: 'me', status: 'SCHEDULED,IN_PROGRESS' })).data;
      }
      if (this.can('property.read')) this.properties = (await site.properties({ page_size: '50' })).data;
    } catch (e) { this.problem = e as ApiProblem; }
  }

  private async create() {
    const f = this.form;
    this.busy = true;
    this.problem = null;
    try {
      const body: Record<string, unknown> = { lead_id: f.lead_id.trim(), property_type_code: f.property_type_code };
      if (f.template_key) { body.template_key = f.template_key; body.include_optional = f.include; }
      if (f.city.trim()) body.city = f.city.trim();
      if (f.built_up.trim()) body.built_up_area_sqft_centi = Math.round(Number(f.built_up) * 100);
      const p = (await site.createProperty(body)).data;
      navigate(`/site/properties/${p.id}`);
    } catch (e) { this.problem = e as ApiProblem; } finally { this.busy = false; }
  }

  private async start(v: Visit) {
    try {
      const started = (await site.visitStatus(v, { to_status: 'IN_PROGRESS' })).data;
      const set = (await site.openSet(started.id, {})).data;
      navigate(`/site/sets/${set.id}/capture`);
    } catch (e) {
      const p = e as ApiProblem;
      const existing = p.body?.measurement_set_id as string | undefined;
      if (p.code === 'DRAFT_EXISTS' && existing) navigate(`/site/sets/${existing}/capture`);
      else this.problem = p;
    }
  }

  private templateKeys(): string[] {
    if (!this.templates) return [];
    return Object.entries(this.templates.property_templates).filter(([, t]) => t.property_type_code === this.form.property_type_code).map(([k]) => k);
  }

  override render() {
    if (this.disabled) return html`<div class="page"><h1 class="display">Site measurement</h1><p>Site measurement is not enabled here.</p></div>`;
    const tpl = this.templates?.property_templates[this.form.template_key];
    return html`<div class="page stack">
      <h1 class="display">Site measurement</h1>
      ${this.problem ? html`<div role="alert" class="danger-text">${this.problem.detail ?? this.problem.title}</div>` : nothing}
      ${this.can('measurement.visit.read') ? html`<section class="card stack" aria-labelledby="mine">
        <h2 id="mine" class="title">My visits</h2>
        ${this.visits.length ? html`<table><thead><tr><th>Visit</th><th>When</th><th>Survey</th><th>Status</th><th></th></tr></thead><tbody>
          ${this.visits.map((v) => html`<tr><td>${v.visit_number}</td><td>${formatFull(v.scheduled_start_on)}</td><td>${label(v.survey_level_code)}</td>
            <td>${label(v.status)}</td><td><button class="btn small primary" @click=${() => this.start(v)}>${v.status === 'IN_PROGRESS' ? 'Continue' : 'Start'}</button>
            <a class="btn small ghost" href="/site/properties/${v.property_id}">Property</a></td></tr>`)}
        </tbody></table>` : html`<p class="muted">No visits assigned to you.</p>`}
      </section>` : nothing}
      ${this.can('property.read') ? html`<section class="card stack" aria-labelledby="props">
        <h2 id="props" class="title">Properties</h2>
        ${this.properties.length ? html`<table><thead><tr><th>Property</th><th>Configuration</th><th>City</th><th>Verified</th></tr></thead><tbody>
          ${this.properties.map((p) => html`<tr><td><a href="/site/properties/${p.id}">${p.property_number}</a></td><td>${p.display_label}</td>
            <td>${p.city ?? ''}</td><td>${p.latest_verified_set ? `Rev ${p.latest_verified_set.revision_no}` : '—'}</td></tr>`)}
        </tbody></table>` : html`<p class="muted">No properties yet.</p>`}
      </section>` : nothing}
      ${this.can('property.create') ? html`<section class="card stack" aria-labelledby="new">
        <h2 id="new" class="title">New property</h2>
        <div class="grid">
          <label class="field"><span class="label">Lead id</span><input .value=${this.form.lead_id} autocomplete="off"
            @input=${(e: Event) => { this.form = { ...this.form, lead_id: (e.target as HTMLInputElement).value }; }} /></label>
          <label class="field"><span class="label">Property type</span><select @change=${(e: Event) => {
            const t = (e.target as HTMLSelectElement).value;
            this.form = { ...this.form, property_type_code: t, template_key: t === 'APARTMENT' ? 'APARTMENT_3BHK' : 'INDEPENDENT_HOUSE', include: [] };
          }}><option value="APARTMENT">Apartment</option><option value="INDEPENDENT_HOUSE">Independent house</option></select></label>
          <label class="field"><span class="label">Template</span><select @change=${(e: Event) => { this.form = { ...this.form, template_key: (e.target as HTMLSelectElement).value, include: [] }; }}>
            ${this.templateKeys().map((k) => html`<option value=${k} ?selected=${k === this.form.template_key}>${label(k)}</option>`)}
            <option value="" ?selected=${this.form.template_key === ''}>No template (add spaces by hand)</option></select></label>
          <label class="field"><span class="label">City</span><input .value=${this.form.city} @input=${(e: Event) => { this.form = { ...this.form, city: (e.target as HTMLInputElement).value }; }} /></label>
          <label class="field"><span class="label">Stated built-up area (sq ft)</span><input inputmode="decimal" .value=${this.form.built_up}
            @input=${(e: Event) => { this.form = { ...this.form, built_up: (e.target as HTMLInputElement).value }; }} /></label>
        </div>
        ${tpl ? html`<fieldset><legend>Optional spaces</legend><div class="opt">${tpl.spaces.filter((s) => s.optional).map((s) => html`<label>
          <input type="checkbox" .checked=${this.form.include.includes(s.ref)} @change=${(e: Event) => {
            const on = (e.target as HTMLInputElement).checked;
            this.form = { ...this.form, include: on ? [...this.form.include, s.ref] : this.form.include.filter((x) => x !== s.ref) };
          }} />${s.label}</label>`)}</div></fieldset>` : nothing}
        <div><button class="btn primary" ?disabled=${this.busy || !/^[0-9a-f]{32}$/.test(this.form.lead_id.trim())} @click=${() => this.create()}>Create property</button></div>
      </section>` : nothing}
    </div>`;
  }
}

customElements.define('vs-site-home-page', VsSiteHomePage);
