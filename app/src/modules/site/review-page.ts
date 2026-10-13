import { css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { navigate } from '../../core/router/next.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { site, variantUrl, type MeasurementSet, type Property, type Readiness } from './api.js';
import { siteTargets } from './styles.js';
import { formatArea, formatLength } from './units.js';

const label = (code: string) => code.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

/**
 * Verification review (MTQ B1-T10; blueprint §13.1): numbers beside their photos, every fail-closed check with its
 * pointer, verification (four-eyes, acknowledgements for acknowledgeable warnings), return for correction, and the
 * per-space comparison with another revision.
 */
export class VsReviewPage extends SessionElement {
  static override properties = {
    location: { attribute: false }, set: { state: true }, property: { state: true }, checks: { state: true }, photos: { state: true },
    diff: { state: true }, problem: { state: true }, ack: { state: true }, reason: { state: true }, busy: { state: true }, disabled: { state: true },
  };
  declare location: { params: Record<string, string>; search?: string } | undefined;
  declare set: MeasurementSet | null;
  declare property: Property | null;
  declare checks: Readiness | null;
  declare photos: Record<string, string[]>;
  declare diff: { spaces: Array<Record<string, unknown>> } | null;
  declare problem: ApiProblem | null;
  declare ack: string;
  declare reason: string;
  declare busy: boolean;
  declare disabled: boolean;

  static override styles = [...shared, pageStyles, tableStyles, siteTargets, css`
    .space { display: grid; gap: 12px; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
    @media (max-width: 767px) { .space { grid-template-columns: 1fr; } }
    .thumbs { display: flex; gap: 8px; flex-wrap: wrap; }
    .thumbs img { width: 120px; height: 90px; object-fit: cover; border-radius: 6px; border: 1px solid var(--vs-line); }
    ul.plain { padding-left: 18px; margin: 4px 0; }
  `];

  constructor() {
    super();
    this.set = null; this.property = null; this.checks = null; this.photos = {}; this.diff = null; this.problem = null;
    this.ack = ''; this.reason = ''; this.busy = false; this.disabled = false;
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private get routeId(): string { return this.location?.params?.id ?? ''; }

  private async load() {
    try {
      this.set = (await site.set(this.routeId)).data;
      this.property = (await site.property(this.set.property_id)).data;
      this.checks = (await site.checks(this.routeId)).data;
      const compare = new URLSearchParams(this.location?.search ?? window.location.search).get('compare');
      if (compare) this.diff = (await site.diff(compare, this.routeId)).data;
      void this.loadPhotos();
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404 && !this.set) this.disabled = true; else this.problem = p;
    }
  }

  private async loadPhotos() {
    const out: Record<string, string[]> = {};
    for (const sp of this.property?.spaces ?? []) {
      const atts = (await site.attachments('property_space', sp.id)).data.filter((a) => a.available).slice(0, 4);
      out[sp.id] = (await Promise.all(atts.map((a) => variantUrl(a.id)))).filter((u): u is string => !!u);
    }
    this.photos = out;
  }

  private async act(fn: () => Promise<unknown>, after?: () => void) {
    this.busy = true;
    this.problem = null;
    try { await fn(); after?.(); await this.load(); } catch (e) { this.problem = e as ApiProblem; } finally { this.busy = false; }
  }

  private verify() {
    const acks = (this.checks?.verify_problems ?? []).filter((p) => p.acknowledgeable).map((p) => ({ code: p.code, note: this.ack.trim() }));
    void this.act(() => site.verify(this.set!, acks));
  }

  private reject() {
    void this.act(async () => {
      const r = (await site.reject(this.set!, this.reason.trim())).data;
      navigate(`/site/properties/${r.correction.property_id}`);
    });
  }

  override render() {
    if (this.disabled) return html`<div class="page"><p>Not available, or site measurement is not enabled here.</p></div>`;
    const m = this.set;
    if (!m) return html`<div class="page"><p>Loading…</p></div>`;
    const unit = m.unit_system_code;
    const blocking = (this.checks?.verify_problems ?? []).filter((p) => !p.acknowledgeable);
    const ackable = (this.checks?.verify_problems ?? []).filter((p) => p.acknowledgeable);
    const canVerify = this.can('measurement.verify') && m.status === 'SUBMITTED';
    const spaces = new Map((this.property?.spaces ?? []).map((s) => [s.id, s]));
    return html`<div class="page stack">
      <header class="row"><h1 class="display">Review · Rev ${m.revision_no}</h1><span class="spacer"></span>
        <span class="small">${label(m.status)} · ${label(m.survey_level_code)} survey</span></header>
      ${this.problem ? html`<div role="alert" class="danger-text">${this.problem.detail ?? this.problem.title}
        ${(this.problem.body?.pointers as Array<{ message: string }> | undefined)?.length ? html`<ul class="plain">${(this.problem.body.pointers as Array<{ message: string }>).map((p) => html`<li>${p.message}</li>`)}</ul>` : nothing}</div>` : nothing}
      ${m.rejection_reason ? html`<p class="warning-text">Returned: ${m.rejection_reason}</p>` : nothing}
      ${m.snapshot_sha256 ? html`<p class="small mono">Sealed ${m.snapshot_sha256.slice(0, 16)}…</p>` : nothing}
      ${canVerify ? html`<section class="card stack" aria-labelledby="checks"><h2 id="checks" class="title">Checks</h2>
        ${blocking.length ? html`<ul class="plain">${blocking.map((p) => html`<li class="danger-text">${p.space ? `${p.space}: ` : ''}${p.message}</li>`)}</ul>` : html`<p class="success-text">All checks pass.</p>`}
        ${ackable.map((p) => html`<p class="warning-text">${p.message}</p>`)}
        ${ackable.length ? html`<label class="field"><span class="label">Acknowledgement note</span><textarea .value=${this.ack}
          @input=${(e: Event) => { this.ack = (e.target as HTMLTextAreaElement).value; }}></textarea></label>` : nothing}
        <div class="row">
          <button class="btn primary" ?disabled=${this.busy || blocking.length > 0 || (ackable.length > 0 && this.ack.trim().length < 5)} @click=${() => this.verify()}>Verify</button>
          <label class="field" style="flex:1"><span class="label">Reason to return for correction</span><input .value=${this.reason}
            @input=${(e: Event) => { this.reason = (e.target as HTMLInputElement).value; }} /></label>
          <button class="btn" ?disabled=${this.busy || !this.reason.trim()} @click=${() => this.reject()}>Return for correction</button>
        </div></section>` : nothing}
      ${this.diff ? html`<section class="card stack" aria-labelledby="diff"><h2 id="diff" class="title">Changes from the earlier revision</h2>
        ${this.diff.spaces.length ? html`<table><thead><tr><th>Space</th><th>Change</th><th>Details</th></tr></thead><tbody>
          ${this.diff.spaces.map((d) => html`<tr><td>${spaces.get(d.space_id as string)?.label ?? d.space_id}</td><td>${label(d.change as string)}</td>
            <td>${Object.entries((d.fields ?? {}) as Record<string, { from: number | null; to: number | null }>).map(([f, v]) => html`<div>${label(f)}: ${f.endsWith('_mm')
              ? `${formatLength(v.from, unit)} → ${formatLength(v.to, unit)}` : `${v.from ?? '—'} → ${v.to ?? '—'}`}</div>`)}
            ${Object.entries((d.walls ?? {}) as Record<string, { from: number | null; to: number | null }>).map(([w, v]) => html`<div>W${w}: ${formatLength(v.from, unit)} → ${formatLength(v.to, unit)}</div>`)}</td></tr>`)}
        </tbody></table>` : html`<p>No differences.</p>`}</section>` : nothing}
      ${(m.spaces ?? []).map((sm) => html`<section class="card space" aria-label=${spaces.get(sm.space_id)?.label ?? 'Space'}>
        <div class="stack"><h3>${spaces.get(sm.space_id)?.label ?? sm.space_id}</h3>
          <p>${label(sm.shape_code)} · ${formatLength(sm.length_mm, unit)} × ${formatLength(sm.width_mm, unit)} · ceiling ${formatLength(sm.ceiling_height_mm, unit)}</p>
          <p class="small">Floor ${formatArea(sm.derived_floor_area_sqft_centi)} · walls ${formatArea(sm.derived_wall_area_net_sqft_centi)} net · perimeter ${formatLength(sm.derived_perimeter_mm, unit)}</p>
          <ul class="plain">${sm.walls.map((w) => html`<li>W${w.wall_index}: ${formatLength(w.length_mm, unit)}${w.usable_for_code.length ? ` · ${w.usable_for_code.map(label).join(', ')}` : ''}
            ${w.openings.length ? ` · ${w.openings.length} opening${w.openings.length > 1 ? 's' : ''}` : ''}</li>`)}</ul>
          ${(sm.electrical_points ?? []).length ? html`<p class="small">${(sm.electrical_points ?? []).length} electrical points</p>` : nothing}</div>
        <div class="thumbs">${(this.photos[sm.space_id] ?? []).map((src) => html`<img src=${src} alt="Photo of ${spaces.get(sm.space_id)?.label ?? 'the space'}" />`)}</div>
      </section>`)}
    </div>`;
  }
}

customElements.define('vs-review-page', VsReviewPage);
