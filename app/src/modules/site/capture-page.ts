import { css, html, nothing, type TemplateResult } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { navigate } from '../../core/router/next.js';
import { pageStyles, shared } from '../../design-system/styles.js';
import { site, type MeasurementSet, type Property, type Readiness, type Space, type Templates } from './api.js';
import {
  ATTRIBUTE_FIELDS, emptyOpening, emptyPoint, emptyRoom, emptyWall, fromMeasurement, STAIR_FIELDS, toPayload,
  type OpeningDraft, type RoomDraft, type WallDraft,
} from './capture-model.js';
import { queue, type QueuedOp } from './offline-queue.js';
import { preparePhoto } from './photos.js';
import { formatArea, formatLength, parseLength, type UnitSystem } from './units.js';

const WALL_TAGS = ['WARDROBE', 'LOFT', 'BED_HEAD', 'TV_UNIT', 'STUDY_UNIT', 'CROCKERY_UNIT', 'KITCHEN_RUN', 'KITCHEN_WALL_RUN', 'TALL_UNIT',
  'VANITY', 'SHOE_RACK', 'POOJA_UNIT', 'FEATURE_WALL', 'WINDOW_SEATING', 'STORAGE_WALL', 'PARTITION_EDGE', 'NONE'];
const OBSTRUCTIONS = ['SWITCHBOARD', 'AC_INDOOR', 'AC_PIPE', 'AC_DRAIN', 'COLUMN', 'BEAM_DROP', 'PIPE', 'GAS_LINE', 'WINDOW_GRILL', 'DB_BOX',
  'GEYSER', 'ARCHITRAVE', 'OTHER', 'NONE'];
const OPENINGS = ['DOOR', 'WINDOW', 'FRENCH_WINDOW', 'ARCH', 'NICHE', 'VENTILATOR', 'AC_SLEEVE', 'SHAFT', 'DUCT', 'CUSTOM'];
const POINTS = ['LIGHT_POINT', 'SENSOR_LIGHT', 'FAN_POINT', 'SWITCHBOARD', 'SOCKET_5A', 'SOCKET_15A', 'AC_POINT', 'DB_BOX', 'TV_POINT',
  'DATA_POINT', 'GEYSER_POINT', 'EXHAUST_POINT', 'CHIMNEY_POINT', 'APPLIANCE_POINT', 'PROFILE_LIGHT_FEED', 'CUSTOM'];
const FLOORINGS = ['VITRIFIED', 'MARBLE', 'GRANITE', 'WOOD', 'CEMENT', 'TILE_CERAMIC', 'NONE_BARE'];
const CONDITIONS = ['BARE_SHELL', 'FINISHED_NEW', 'OCCUPIED_GOOD', 'OCCUPIED_WORN', 'DAMP', 'CRACKED'];
const label = (code: string) => code.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

/**
 * Measurement capture (MTQ B1-T10; blueprint §13.2). Mobile-first, keyboard-usable, works offline: every save goes to
 * the device queue first and syncs when the connection allows. Required, conditional and optional inputs are marked
 * from the survey level and the space's template; nothing here shows a price.
 */
export class VsCapturePage extends SessionElement {
  static override properties = {
    location: { attribute: false }, set: { state: true }, property: { state: true }, templates: { state: true },
    checks: { state: true }, roomId: { state: true }, draft: { state: true }, unit: { state: true }, ops: { state: true },
    problem: { state: true }, errors: { state: true }, busy: { state: true }, disabled: { state: true }, note: { state: true },
    online: { state: true }, unowned: { state: true },
  };
  declare location: { params: Record<string, string> } | undefined;
  declare set: MeasurementSet | null;
  declare property: Property | null;
  declare templates: Templates | null;
  declare checks: Readiness | null;
  declare roomId: string | null;
  declare draft: RoomDraft | null;
  declare unit: UnitSystem;
  declare ops: QueuedOp[];
  declare problem: ApiProblem | null;
  declare errors: string[];
  declare busy: boolean;
  declare disabled: boolean;
  declare note: { type: string; body: string };
  declare online: boolean;
  /** Operations on this device that predate ownership (B1-PE-01): counted, never shown or sent. */
  declare unowned: number;

  static override styles = [...shared, pageStyles, css`
    :host { display: block; }
    .layout { display: grid; gap: 16px; grid-template-columns: 260px 1fr; align-items: start; }
    @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
    .rooms button { width: 100%; text-align: left; justify-content: flex-start; }
    .rooms button[aria-current='true'] { border-color: var(--vs-copper); }
    .badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px; background: var(--vs-cream); }
    .badge.ok { color: var(--vs-success); } .badge.todo { color: var(--vs-warning); } .badge.bad { color: var(--vs-danger); }
    .grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
    fieldset { border: 1px solid var(--vs-line); border-radius: 8px; padding: 12px; margin: 0 0 12px; min-width: 0; }
    legend { font-weight: 600; padding: 0 4px; }
    .req::after { content: ' · required'; color: var(--vs-danger); font-weight: 600; }
    .opt::after { content: ' · optional'; color: var(--vs-ink-muted); }
    .tags { display: flex; flex-wrap: wrap; gap: 4px 12px; }
    .tags label { display: flex; gap: 6px; align-items: center; font-size: 13px; min-height: 32px; }
    .bar { position: sticky; top: 0; z-index: 2; background: var(--vs-surface); padding: 8px 0; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .conflict { border-left: 3px solid var(--vs-danger); padding-left: 8px; }
    ul.plain { padding-left: 18px; margin: 4px 0; }
    input.len { font-family: var(--vs-font-mono); }
  `];

  constructor() {
    super();
    this.set = null; this.property = null; this.templates = null; this.checks = null; this.roomId = null; this.draft = null;
    this.unit = 'FT_IN'; this.ops = []; this.problem = null; this.errors = []; this.busy = false; this.disabled = false;
    this.note = { type: 'OBSERVATION', body: '' }; this.online = queue.online; this.unowned = 0;
  }

  private readonly onQueue = () => { void this.refreshQueue(); };

  override connectedCallback() {
    super.connectedCallback();
    queue.addEventListener('change', this.onQueue);
    void this.load();
  }

  override disconnectedCallback() {
    queue.removeEventListener('change', this.onQueue);
    super.disconnectedCallback();
  }

  private get setId(): string { return this.location?.params?.id ?? ''; }

  private async run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    this.problem = null;
    this.busy = true;
    try { return await fn(); } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404 && !this.set) this.disabled = true; else this.problem = p;
      return undefined;
    } finally { this.busy = false; }
  }

  private async load() {
    await this.run(async () => {
      this.set = (await site.set(this.setId)).data;
      this.unit = this.set.unit_system_code;
      this.property = (await site.property(this.set.property_id)).data;
      this.templates = (await site.templates()).data;
      this.checks = (await site.checks(this.setId)).data;
    });
    await this.refreshQueue();
    if (!this.roomId && this.spaces.length) this.openRoom(this.spaces[0].id);
  }

  private async refreshQueue() {
    this.ops = await queue.pending(this.setId);
    this.unowned = (await queue.unowned()).length;
    this.online = queue.online;
  }

  private async discardUnowned() {
    if (!confirm(`Discard ${this.unowned} unsent change${this.unowned === 1 ? '' : 's'} of unknown origin from this device? They cannot be recovered.`)) return;
    await queue.discardUnowned();
  }

  private get spaces(): Space[] { return (this.property?.spaces ?? []).filter((s) => s.is_in_scope); }

  private space(id: string | null): Space | undefined { return this.spaces.find((s) => s.id === id); }

  private requirements(spaceType: string): Set<string> {
    if (this.set?.survey_level_code !== 'FULL' || !this.templates) return new Set();
    const tpl = Object.values(this.templates.space_templates).find((t) => t.space_types.includes(spaceType));
    return new Set(tpl?.full_required ?? []);
  }

  private roomProblems(id: string): string[] {
    return (this.checks?.submit_problems ?? []).filter((p) => p.pointer.startsWith(`/spaces/${id}`)).map((p) => p.message);
  }

  private openRoom(id: string) {
    const existing = this.set?.spaces?.find((s) => s.space_id === id);
    this.roomId = id;
    this.draft = existing ? fromMeasurement(existing, this.unit) : emptyRoom(id);
    this.errors = [];
  }

  private patch(change: Partial<RoomDraft>) { if (this.draft) this.draft = { ...this.draft, ...change }; }

  private patchWall(i: number, change: Partial<WallDraft>) {
    if (!this.draft) return;
    const walls = this.draft.walls.map((w, j) => (j === i ? { ...w, ...change } : w));
    this.draft = { ...this.draft, walls };
  }

  private patchOpening(wi: number, oi: number, change: Partial<OpeningDraft>) {
    const w = this.draft?.walls[wi];
    if (!w) return;
    this.patchWall(wi, { openings: w.openings.map((o, j) => (j === oi ? { ...o, ...change } : o)) });
  }

  /** Validate locally, queue the room, then sync when online. */
  private async save() {
    const sp = this.space(this.roomId);
    if (!this.draft || !sp || !this.set) return;
    const { payload, errors } = toPayload(this.draft, this.unit, sp.space_type_code);
    this.errors = errors;
    if (!payload) return;
    await queue.enqueue(this.set.id, 'space', payload, { spaceId: sp.id, label: sp.label });
    await this.sync();
  }

  private async sync() {
    if (!this.set) return;
    const results = await queue.flush(this.set.id);
    await queue.resumeUploads(this.set.id);
    if (results.some((r) => r.status === 'APPLIED' || r.status === 'DUPLICATE')) {
      await this.run(async () => {
        this.set = (await site.set(this.setId)).data;
        this.checks = (await site.checks(this.setId)).data;
      });
      const fresh = this.set?.spaces?.find((s) => s.space_id === this.roomId);
      if (fresh && this.draft && !this.ops.some((o) => o.space_id === this.roomId && o.state === 'PENDING')) {
        this.draft = fromMeasurement(fresh, this.unit);
      }
    }
    await this.refreshQueue();
  }

  private async addPhoto(e: Event, entityType: string, entityId: string, category = 'SITE_PHOTO') {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file || !this.set) return;
    try {
      const photo = await preparePhoto(file);
      await queue.queuePhoto(this.set.id, {
        entity_type: entityType, entity_id: entityId, category_code: category, mime_type: 'image/jpeg', byte_size: photo.blob.size,
        sha256: photo.sha256, client_ref: `ph-${photo.sha256.slice(0, 24)}`,
      }, photo.blob, 'photo');
      await this.sync();
    } catch (err) {
      this.errors = [(err as Error).message];
    }
  }

  private async addNote() {
    if (!this.set || !this.note.body.trim()) return;
    await queue.enqueue(this.set.id, 'note', { client_ref: `nt-${crypto.randomUUID().slice(0, 18)}`, space_id: this.roomId,
      note_type_code: this.note.type, body: this.note.body.trim() }, { label: 'note' });
    this.note = { type: 'OBSERVATION', body: '' };
    await this.sync();
  }

  private async submit() {
    if (!this.set) return;
    await this.sync();
    const done = await this.run(async () => (await site.submit(this.set!)).data);
    if (done) navigate(`/site/properties/${done.property_id}`);
  }

  private lengthInput(value: string, onChange: (v: string) => void, name: string, required = false): TemplateResult {
    const parsed = value.trim() ? parseLength(value, this.unit) : null;
    const bad = value.trim() !== '' && (parsed === null || parsed <= 0);
    return html`<label class="field"><span class="label ${required ? 'req' : 'opt'}">${name}</span>
      <input class="len" inputmode="decimal" .value=${value} aria-invalid=${bad ? 'true' : 'false'}
        placeholder=${this.unit === 'FT_IN' ? `11' 6"` : 'mm'} @input=${(e: Event) => onChange((e.target as HTMLInputElement).value)} />
      <span class="hint">${bad ? 'Not a length' : parsed !== null ? `${parsed} mm` : ''}</span></label>`;
  }

  private select(value: string, options: string[], onChange: (v: string) => void, name: string, required = false, blank = true): TemplateResult {
    return html`<label class="field"><span class="label ${required ? 'req' : 'opt'}">${name}</span>
      <select @change=${(e: Event) => onChange((e.target as HTMLSelectElement).value)}>
        ${blank ? html`<option value="" ?selected=${value === ''}>—</option>` : nothing}
        ${options.map((o) => html`<option value=${o} ?selected=${o === value}>${label(o)}</option>`)}
      </select></label>`;
  }

  private renderWall(w: WallDraft, i: number): TemplateResult {
    const tagged = w.tags.some((t) => t !== 'NONE' && t !== 'PARTITION_EDGE');
    const stair = this.space(this.roomId)?.space_type_code === 'STAIRCASE';
    return html`<fieldset>
      <legend>W${w.wall_index}${w.wall_index === 0 ? ' (open entry edge)' : ''}</legend>
      <div class="grid">
        ${this.lengthInput(w.length, (v) => this.patchWall(i, { length: v }), 'Length', true)}
        ${this.lengthInput(w.height, (v) => this.patchWall(i, { height: v }), stair ? 'Height (own)' : 'Height (if not CH)', stair)}
        ${this.select(w.type, ['MASONRY', 'RCC', 'PARTITION', 'GLASS', 'OPEN'], (v) => this.patchWall(i, { type: v }), 'Type', true, false)}
        <label class="check"><input type="checkbox" .checked=${w.external} @change=${(e: Event) => this.patchWall(i, { external: (e.target as HTMLInputElement).checked })} /> External</label>
        ${w.type === 'PARTITION' ? html`<label class="check"><input type="checkbox" .checked=${w.proposed}
          @change=${(e: Event) => this.patchWall(i, { proposed: (e.target as HTMLInputElement).checked })} /> Proposed partition</label>` : nothing}
      </div>
      ${w.type === 'OPEN' ? nothing : html`
        <details ?open=${w.tags.length > 0}><summary>Tags${w.tags.length ? `: ${w.tags.map(label).join(', ')}` : ''}</summary>
          <div class="tags">${WALL_TAGS.map((t) => html`<label><input type="checkbox" .checked=${w.tags.includes(t)}
            @change=${(e: Event) => {
              const on = (e.target as HTMLInputElement).checked;
              const tags = t === 'NONE' ? (on ? ['NONE'] : []) : on ? [...w.tags.filter((x) => x !== 'NONE'), t] : w.tags.filter((x) => x !== t);
              this.patchWall(i, { tags });
            }} />${label(t)}</label>`)}</div></details>
        <div class=${tagged ? 'req' : ''}><span class="label">Obstructions</span></div>
        ${w.obstructions.map((o, oi) => html`<div class="grid">
          ${this.select(o.kind, OBSTRUCTIONS, (v) => this.patchWall(i, { obstructions: w.obstructions.map((x, j) => (j === oi ? { ...x, kind: v } : x)) }), 'Kind', true, false)}
          ${o.kind === 'NONE' ? nothing : html`
            ${this.lengthInput(o.offset, (v) => this.patchWall(i, { obstructions: w.obstructions.map((x, j) => (j === oi ? { ...x, offset: v } : x)) }), 'Offset from start', true)}
            ${this.lengthInput(o.width, (v) => this.patchWall(i, { obstructions: w.obstructions.map((x, j) => (j === oi ? { ...x, width: v } : x)) }), 'Width')}`}
          <button class="btn small ghost" @click=${() => this.patchWall(i, { obstructions: w.obstructions.filter((_, j) => j !== oi) })}>Remove</button>
        </div>`)}
        <div class="row">
          <button class="btn small" @click=${() => this.patchWall(i, { obstructions: [...w.obstructions, { kind: 'SWITCHBOARD', offset: '', width: '', heightFromFloor: '' }] })}>Add obstruction</button>
          ${tagged && !w.obstructions.length ? html`<button class="btn small" @click=${() => this.patchWall(i, { obstructions: [{ kind: 'NONE', offset: '', width: '', heightFromFloor: '' }] })}>Mark none</button>` : nothing}
        </div>
        <span class="label">Openings</span>
        ${w.openings.map((o, oi) => html`<div class="grid">
          ${this.select(o.type, OPENINGS, (v) => this.patchOpening(i, oi, { type: v }), 'Type', true, false)}
          ${this.lengthInput(o.width, (v) => this.patchOpening(i, oi, { width: v }), 'Width', true)}
          ${this.lengthInput(o.height, (v) => this.patchOpening(i, oi, { height: v }), 'Height', true)}
          ${this.lengthInput(o.offset, (v) => this.patchOpening(i, oi, { offset: v }), 'Offset from start', tagged)}
          ${['WINDOW', 'FRENCH_WINDOW', 'VENTILATOR', 'NICHE', 'AC_SLEEVE'].includes(o.type) ? this.lengthInput(o.sill, (v) => this.patchOpening(i, oi, { sill: v }), 'Sill', tagged) : nothing}
          ${['DOOR', 'WINDOW', 'FRENCH_WINDOW'].includes(o.type) ? this.select(o.swing, ['IN', 'OUT', 'SLIDING', 'NONE'], (v) => this.patchOpening(i, oi, { swing: v }), 'Swing', tagged) : nothing}
          ${o.type === 'NICHE' ? html`${this.lengthInput(o.depth, (v) => this.patchOpening(i, oi, { depth: v }), 'Depth', true)}
            ${this.select(o.purpose, ['FRIDGE', 'APPLIANCE', 'STORAGE', 'WASH', 'OTHER'], (v) => this.patchOpening(i, oi, { purpose: v }), 'Purpose')}` : nothing}
          <button class="btn small ghost" @click=${() => this.patchWall(i, { openings: w.openings.filter((_, j) => j !== oi) })}>Remove</button>
        </div>`)}
        <div class="row">
          <button class="btn small" @click=${() => this.patchWall(i, { openings: [...w.openings, emptyOpening()] })}>Add opening</button>
          ${w.wall_index >= 0 && this.draft && this.set?.spaces?.find((s) => s.space_id === this.roomId)?.walls.find((x) => x.wall_index === w.wall_index)?.id
            ? html`<label class="btn small">Photo<input class="sr-only" type="file" accept="image/*" capture="environment"
                @change=${(e: Event) => this.addPhoto(e, 'space_wall', this.set!.spaces!.find((s) => s.space_id === this.roomId)!.walls.find((x) => x.wall_index === w.wall_index)!.id!, 'LASER_READING')} /></label>`
            : html`<span class="small muted">Save the room to photograph this wall</span>`}
        </div>`}
      <button class="btn small ghost danger-text" @click=${() => this.patch({ walls: this.draft!.walls.filter((_, j) => j !== i) })}>Remove wall</button>
    </fieldset>`;
  }

  private renderRoom(): TemplateResult | typeof nothing {
    const sp = this.space(this.roomId);
    const d = this.draft;
    if (!sp || !d) return nothing;
    const req = this.requirements(sp.space_type_code);
    const full = this.set?.survey_level_code === 'FULL';
    const outdoor = sp.zone_code === 'OUTDOOR';
    const stair = sp.space_type_code === 'STAIRCASE';
    const problems = this.roomProblems(sp.id);
    return html`<section class="card stack" aria-labelledby="room-title">
      <div class="row"><h2 id="room-title" class="title">${sp.label}</h2><span class="spacer"></span>
        <label class="btn small">Room photo<input class="sr-only" type="file" accept="image/*" capture="environment" @change=${(e: Event) => this.addPhoto(e, 'property_space', sp.id)} /></label></div>
      ${problems.length ? html`<div class="warning-text small"><ul class="plain">${problems.map((p) => html`<li>${p}</li>`)}</ul></div>` : nothing}
      <fieldset><legend>Shape and size</legend><div class="grid">
        ${this.select(d.shape, ['RECTANGULAR', 'L_SHAPE', 'POLYGON', 'FREEFORM'], (v) => this.patch({ shape: v }), 'Shape', true, false)}
        ${stair ? nothing : html`${this.lengthInput(d.length, (v) => this.patch({ length: v }), 'Length', true)}
          ${this.lengthInput(d.width, (v) => this.patch({ width: v }), 'Width', true)}`}
        ${stair || outdoor ? nothing : this.lengthInput(d.ceiling, (v) => this.patch({ ceiling: v }), 'Ceiling height', true)}
        ${this.lengthInput(d.beam, (v) => this.patch({ beam: v }), 'Beam bottom')}
        ${this.lengthInput(d.lintel, (v) => this.patch({ lintel: v }), 'Floor to lintel', req.has('FL'))}
        ${d.shape === 'FREEFORM' ? html`<label class="field"><span class="label req">Stated area (sq ft)</span>
          <input inputmode="decimal" .value=${d.stated_area} @input=${(e: Event) => this.patch({ stated_area: (e.target as HTMLInputElement).value })} /></label>` : nothing}
      </div></fieldset>
      ${d.shape === 'L_SHAPE' ? html`<fieldset><legend>L-shape legs (stand at W1, facing in)</legend><div class="grid">
        ${this.select(d.legs.turn, ['LEFT', 'RIGHT'], (v) => this.patch({ legs: { ...d.legs, turn: v } }), 'Turn', true, false)}
        ${this.lengthInput(d.legs.la, (v) => this.patch({ legs: { ...d.legs, la: v } }), 'Leg A length', true)}
        ${this.lengthInput(d.legs.wa, (v) => this.patch({ legs: { ...d.legs, wa: v } }), 'Leg A width', true)}
        ${this.lengthInput(d.legs.lb, (v) => this.patch({ legs: { ...d.legs, lb: v } }), 'Leg B length', true)}
        ${this.lengthInput(d.legs.wb, (v) => this.patch({ legs: { ...d.legs, wb: v } }), 'Leg B depth', true)}
      </div></fieldset>` : nothing}
      ${stair ? html`<fieldset><legend>Staircase</legend><div class="grid">
        ${STAIR_FIELDS.map((k) => k === 'turn_type_code'
          ? this.select(d.stair[k] ?? '', ['STRAIGHT', 'L', 'U', 'SPIRAL', 'CUSTOM'], (v) => this.patch({ stair: { ...d.stair, [k]: v } }), 'Turn', true)
          : k.endsWith('_mm') ? this.lengthInput(d.stair[k] ?? '', (v) => this.patch({ stair: { ...d.stair, [k]: v } }), label(k.replace(/_mm$/, '')), !k.startsWith('landing'))
            : html`<label class="field"><span class="label ${k === 'handrail_wall_index' ? 'opt' : 'req'}">${label(k)}</span>
              <input inputmode="numeric" .value=${d.stair[k] ?? ''} @input=${(e: Event) => this.patch({ stair: { ...d.stair, [k]: (e.target as HTMLInputElement).value } })} /></label>`)}
      </div></fieldset>` : nothing}
      <fieldset><legend>Condition and readings</legend><div class="grid">
        ${outdoor || stair ? nothing : html`${this.select(d.flooring, FLOORINGS, (v) => this.patch({ flooring: v }), 'Flooring', full)}
          ${this.select(d.condition, CONDITIONS, (v) => this.patch({ condition: v }), 'Condition', full)}`}
        ${this.select(d.confidence, ['HIGH', 'MEDIUM', 'LOW'], (v) => this.patch({ confidence: v }), 'Confidence', true, false)}
        ${ATTRIBUTE_FIELDS.filter((k) => req.has(`ATTR:${k}`) || d.attrs[k] !== undefined).map((k) => this.attrInput(k, req.has(`ATTR:${k}`)))}
      </div>
      <details><summary>More readings</summary><div class="grid">
        ${ATTRIBUTE_FIELDS.filter((k) => !req.has(`ATTR:${k}`) && d.attrs[k] === undefined).map((k) => this.attrInput(k, false))}</div></details>
      </fieldset>
      <h3>Walls (clockwise from W1)</h3>
      ${d.walls.map((w, i) => this.renderWall(w, i))}
      <div class="row">
        <button class="btn small" @click=${() => this.patch({ walls: [...d.walls, emptyWall(Math.max(0, ...d.walls.map((w) => w.wall_index)) + 1)] })}>Add wall</button>
        ${d.walls.some((w) => w.wall_index === 0) ? nothing : html`<button class="btn small ghost" @click=${() => this.patch({ walls: [emptyWall(0), ...d.walls] })}>Add open entry edge</button>`}
      </div>
      <h3>Electrical points</h3>
      ${d.points.map((p, pi) => html`<fieldset><legend>${label(p.type)}</legend><div class="grid">
        ${this.select(p.type, POINTS, (v) => this.patch({ points: d.points.map((x, j) => (j === pi ? { ...x, type: v } : x)) }), 'Type', true, false)}
        ${this.select(p.status, ['EXISTING', 'SHIFT', 'NEW', 'REMOVE'], (v) => this.patch({ points: d.points.map((x, j) => (j === pi ? { ...x, status: v } : x)) }), 'Status', true, false)}
        ${this.select(p.wall_index, ['', ...d.walls.map((w) => String(w.wall_index))].filter(Boolean), (v) => this.patch({ points: d.points.map((x, j) => (j === pi ? { ...x, wall_index: v, location: v ? x.location : 'CEILING' } : x)) }), 'Wall (blank = ceiling)')}
        ${this.lengthInput(p.from_offset, (v) => this.patch({ points: d.points.map((x, j) => (j === pi ? { ...x, from_offset: v } : x)) }), p.wall_index ? 'Offset from start' : 'X from entry corner', p.status !== 'NEW')}
        ${this.lengthInput(p.from_height, (v) => this.patch({ points: d.points.map((x, j) => (j === pi ? { ...x, from_height: v } : x)) }), p.wall_index ? 'Height from floor' : 'Y from entry corner')}
        ${p.status === 'SHIFT' || p.status === 'NEW' ? html`
          ${this.select(p.to_wall_index, d.walls.map((w) => String(w.wall_index)), (v) => this.patch({ points: d.points.map((x, j) => (j === pi ? { ...x, to_wall_index: v } : x)) }), 'To wall', p.status === 'SHIFT' && !!p.wall_index)}
          ${this.lengthInput(p.to_offset, (v) => this.patch({ points: d.points.map((x, j) => (j === pi ? { ...x, to_offset: v } : x)) }), 'New position', true)}` : nothing}
        ${p.type === 'SENSOR_LIGHT' ? this.select(p.sensor, ['PIR', 'MICROWAVE', 'NONE'], (v) => this.patch({ points: d.points.map((x, j) => (j === pi ? { ...x, sensor: v } : x)) }), 'Sensor', true) : nothing}
        <label class="field"><span class="label opt">Quantity</span><input inputmode="numeric" .value=${p.quantity}
          @input=${(e: Event) => this.patch({ points: d.points.map((x, j) => (j === pi ? { ...x, quantity: (e.target as HTMLInputElement).value } : x)) })} /></label>
        <button class="btn small ghost" @click=${() => this.patch({ points: d.points.filter((_, j) => j !== pi) })}>Remove</button>
      </div></fieldset>`)}
      <button class="btn small" @click=${() => this.patch({ points: [...d.points, emptyPoint()] })}>Add point</button>
      <fieldset><legend>Note</legend><div class="grid">
        ${this.select(this.note.type, ['OBSERVATION', 'RISK', 'CUSTOMER_REQUEST', 'VOICE_TRANSCRIPT'], (v) => { this.note = { ...this.note, type: v }; }, 'Type', true, false)}
        <label class="field" style="grid-column: 1 / -1"><span class="label">Text</span><textarea .value=${this.note.body}
          @input=${(e: Event) => { this.note = { ...this.note, body: (e.target as HTMLTextAreaElement).value }; }}></textarea></label>
      </div><button class="btn small" @click=${() => this.addNote()} ?disabled=${!this.note.body.trim()}>Add note</button></fieldset>
      ${this.errors.length ? html`<div role="alert" class="danger-text"><ul class="plain">${this.errors.map((x) => html`<li>${x}</li>`)}</ul></div>` : nothing}
      <div class="row">
        <label class="check"><input type="checkbox" .checked=${d.complete} @change=${(e: Event) => this.patch({ complete: (e.target as HTMLInputElement).checked })} /> Room complete</label>
        <span class="spacer"></span>
        <button class="btn primary" @click=${() => this.save()}>Save room</button>
      </div>
    </section>`;
  }

  private attrInput(k: string, required: boolean): TemplateResult {
    const d = this.draft!;
    const set = (v: string) => this.patch({ attrs: { ...d.attrs, [k]: v } });
    if (['has_gas_line', 'has_water_inlet', 'has_drain', 'counter_existing'].includes(k)) {
      return this.select(d.attrs[k] ?? '', ['true', 'false'], set, label(k), required);
    }
    if (k === 'ac_type') return this.select(d.attrs[k] ?? '', ['SPLIT', 'WINDOW', 'CASSETTE', 'DUCTED', 'NONE'], set, 'AC type', required);
    if (k === 'exposure_code') return this.select(d.attrs[k] ?? '', ['OPEN', 'COVERED', 'ENCLOSED'], set, 'Exposure', required);
    if (k === 'railing_height_mm') return this.lengthInput(d.attrs[k] ?? '', set, 'Railing height', required);
    return html`<label class="field"><span class="label ${required ? 'req' : 'opt'}">${label(k)}</span>
      <input inputmode="numeric" .value=${d.attrs[k] ?? ''} @input=${(e: Event) => set((e.target as HTMLInputElement).value)} /></label>`;
  }

  private renderQueue(): TemplateResult {
    const open = this.ops.filter((o) => o.state !== 'PENDING' && o.state !== 'UPLOADING');
    const pending = this.ops.filter((o) => o.state === 'PENDING' || o.state === 'UPLOADING').length;
    return html`<div class="bar" role="status" aria-live="polite">
        <span class="badge ${this.online ? 'ok' : 'todo'}">${this.online ? 'Online' : 'Offline'}</span>
        <span class="small">${pending} waiting to sync</span>
        <button class="btn small" @click=${() => this.sync()} ?disabled=${!pending}>Sync now</button>
        <label class="small">Units <select @change=${(e: Event) => { this.unit = (e.target as HTMLSelectElement).value as UnitSystem; if (this.roomId) this.openRoom(this.roomId); }}>
          <option value="FT_IN" ?selected=${this.unit === 'FT_IN'}>ft-in</option><option value="MM" ?selected=${this.unit === 'MM'}>mm</option></select></label>
      </div>
      ${this.unowned ? html`<div class="card conflict stack">
        <div class="small">${this.unowned} unsent change${this.unowned === 1 ? '' : 's'} on this device ${this.unowned === 1 ? 'was' : 'were'} saved before
          captures recorded who made them. ${this.unowned === 1 ? 'It' : 'They'} will not be sent under your name.</div>
        <div class="row"><button class="btn small ghost" @click=${() => this.discardUnowned()}>Discard</button></div></div>` : nothing}
      ${open.map((o) => html`<div class="card conflict stack" role="alert">
        <div class="strong">${o.label}: ${o.state === 'CONFLICT' ? 'changed on the server meanwhile' : o.state === 'CLAIMED' ? 'another surveyor holds this room'
          : o.state === 'FROZEN' ? 'this revision is no longer a draft' : 'refused'}</div>
        ${o.result?.conflicting_fields ? html`<div class="small">Differs: ${(o.result.conflicting_fields as string[]).join(', ')}</div>` : nothing}
        ${o.result?.message ? html`<div class="small">${o.result.message as string}</div>` : nothing}
        <div class="row">
          ${o.state === 'CONFLICT' || o.state === 'CLAIMED' ? html`<button class="btn small" @click=${() => queue.resolve(o, 'MINE').then(() => this.sync())}>${o.state === 'CLAIMED' ? 'Take over and keep mine' : 'Keep mine'}</button>` : nothing}
          ${o.state === 'FROZEN' && o.result?.current_draft_id ? html`<button class="btn small" @click=${() => navigate(`/site/sets/${o.result!.current_draft_id as string}/capture`)}>Open the current draft</button>` : nothing}
          <button class="btn small ghost" @click=${() => queue.resolve(o, 'SERVER').then(() => this.load())}>${o.state === 'CONFLICT' ? 'Keep the server version' : 'Discard'}</button>
        </div></div>`)}`;
  }

  override render() {
    if (this.disabled) return html`<div class="page"><p>Site measurement is not enabled here.</p></div>`;
    if (!this.set) return html`<div class="page"><p>${this.problem ? this.problem.detail : 'Loading…'}</p></div>`;
    const draftOpen = this.set.status === 'DRAFT';
    return html`<div class="page stack">
      <header class="row"><h1 class="display">Capture</h1><span class="spacer"></span>
        <span class="badge">Rev ${this.set.revision_no} · ${label(this.set.status)} · ${this.set.survey_level_code === 'FULL' ? 'Full' : 'Lite'} survey</span></header>
      ${this.problem ? html`<div role="alert" class="danger-text">${this.problem.detail}</div>` : nothing}
      ${draftOpen ? this.renderQueue() : html`<p>This revision is ${label(this.set.status).toLowerCase()} and read-only.</p>`}
      <div class="layout">
        <nav class="rooms stack" aria-label="Rooms in walk order">
          ${this.spaces.map((sp) => {
            const sm = this.set?.spaces?.find((s) => s.space_id === sp.id);
            const issues = this.roomProblems(sp.id).length;
            const state = !sm ? 'todo' : issues ? 'bad' : 'ok';
            return html`<button class="btn" aria-current=${this.roomId === sp.id ? 'true' : 'false'} @click=${() => this.openRoom(sp.id)}>
              <span>${sp.label}</span><span class="spacer"></span><span class="badge ${state}">${!sm ? 'To do' : issues ? `${issues} to fix` : 'Done'}</span></button>`;
          })}
          <p class="small muted">${this.checks?.ready_to_submit ? 'Ready to submit' : `${this.checks?.submit_problems.length ?? 0} items before submission`}</p>
          ${sumArea(this.set) ? html`<p class="small">Measured: ${formatArea(sumArea(this.set))}</p>` : nothing}
          ${draftOpen && this.me?.id === this.set.captured_by ? html`<button class="btn primary" ?disabled=${!this.checks?.ready_to_submit || this.ops.length > 0 || this.busy}
            @click=${() => this.submit()}>Submit set</button>` : nothing}
        </nav>
        ${draftOpen ? this.renderRoom() : this.renderReadOnly()}
      </div>
    </div>`;
  }

  private renderReadOnly(): TemplateResult {
    return html`<section class="card"><ul class="plain">${(this.set?.spaces ?? []).map((sm) => html`<li>
      ${this.space(sm.space_id)?.label ?? sm.space_id}: ${formatLength(sm.length_mm, this.unit)} × ${formatLength(sm.width_mm, this.unit)}, ${formatArea(sm.derived_floor_area_sqft_centi)}</li>`)}</ul></section>`;
  }
}

function sumArea(m: MeasurementSet): number {
  return (m.spaces ?? []).reduce((n, s) => n + (s.derived_floor_area_sqft_centi ?? 0), 0);
}

customElements.define('vs-capture-page', VsCapturePage);
