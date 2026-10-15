import { css, html, LitElement, nothing, type PropertyValues, type TemplateResult } from 'lit';
import { shared } from '../../design-system/styles.js';
import type { SectionView, Vocabulary } from './api.js';
import { blankRow, clone, PARTS, type FieldDef, type ListDef, type ObjectDef, type Part, type StringsDef, type TextDef } from './schema.js';

type Obj = Record<string, unknown>;
const fid = (path: string) => `f-${path.replace(/[^A-Za-z0-9_-]/g, '_')}`;

/**
 * <vs-promise-editor>: structured editing of one Customer Promise section (CPA-17). Holds the unsaved draft of the
 * section; ``dirty`` says whether it differs from what was loaded. Save is explicit (``editor-save`` with the value);
 * server field errors (``errors``, keyed by the API's field path) mark their control (aria-invalid, aria-describedby).
 */
export class VsPromiseEditor extends LitElement {
  static override properties = {
    section: { attribute: false }, vocab: { attribute: false }, editable: { type: Boolean }, busy: { type: Boolean },
    errors: { attribute: false }, context: { attribute: false }, draft: { state: true },
  };
  declare section: SectionView | null;
  declare vocab: Vocabulary | null;
  declare editable: boolean;
  declare busy: boolean;
  declare errors: { field: string; message: string }[];
  /** Other sections of the same version the editor needs (the contacts, for the service contact). */
  declare context: Obj;
  declare draft: Obj;
  private base = '';

  static override styles = [...shared, css`
    :host { display: block; }
    .btn.small { min-height: var(--vs-target); }
    fieldset { border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); padding: var(--vs-space-3) var(--vs-space-4); margin: 0;
      display: grid; gap: var(--vs-space-3); min-width: 0; }
    fieldset.entry { background: var(--vs-paper); }
    fieldset.entry.inactive { border-style: dashed; }
    legend { padding: 0 4px; font-weight: 600; overflow-wrap: anywhere; }
    .grid { display: grid; gap: var(--vs-space-3); grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); }
    .wide { grid-column: 1 / -1; }
    .count { font-size: 12px; color: var(--vs-ink-muted); }
    .rowbtns { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .strings { display: grid; gap: var(--vs-space-2); }
    .stringrow { display: flex; gap: var(--vs-space-2); align-items: flex-end; } .stringrow label { flex: 1; min-width: 0; }
    .error { font-size: 12px; color: var(--vs-danger); }
    input[readonly], textarea[readonly] { background: var(--vs-paper); }
  `];

  constructor() {
    super();
    this.section = null;
    this.vocab = null;
    this.editable = false;
    this.busy = false;
    this.errors = [];
    this.context = {};
    this.draft = {};
  }

  protected override willUpdate(changed: PropertyValues<this>) {
    if (changed.has('section') && this.section) {
      this.draft = clone(this.section.value);
      this.base = JSON.stringify(this.value());
    }
  }

  get dirty(): boolean {
    return !!this.section && JSON.stringify(this.value()) !== this.base;
  }

  /** Undo every unsaved change. */
  reset() {
    if (this.section) this.draft = clone(this.section.value);
    this.changed();
  }

  /** The section value as the API takes it: optional empty text as null, ``active`` only when switched off. */
  value(): Obj {
    const norm = (parts: Part[], src: Obj): Obj => {
      const out: Obj = {};
      for (const p of parts) {
        if (p.kind === 'list') out[p.key] = ((src[p.key] as Obj[] | null) ?? []).map((row) => this.normRow(p, row));
        else if (p.kind === 'strings') out[p.key] = ((src[p.key] as string[] | null) ?? []).map((x) => x.trim()).filter(Boolean);
        else if (p.kind === 'scalar') out[p.key] = this.text(src[p.key], true);
        else if (p.kind === 'object') out[p.key] = src[p.key] ? norm(p.parts, src[p.key] as Obj) : null;
        else out[p.name] = this.normField(p, src[p.name]);
      }
      return out;
    };
    return this.section ? norm(PARTS[this.section.code] ?? [], this.draft) : {};
  }

  private text(v: unknown, optional: boolean) {
    const s = typeof v === 'string' ? v : v == null ? '' : String(v);
    return optional && !s.trim() ? null : s;
  }

  private normField(f: FieldDef, v: unknown): unknown {
    if (f.kind === 'checkbox') return v === true;
    return this.text(v, !!f.optional);
  }

  private normRow(def: ListDef, row: Obj): Obj {
    const out: Obj = {};
    for (const f of def.fields) out[f.name] = this.normField(f, row[f.name]);
    if (def.active && row.active === false) out.active = false;
    return out;
  }

  private changed() {
    this.draft = { ...this.draft };
    this.dispatchEvent(new CustomEvent('editor-change', { bubbles: true, composed: true, detail: { dirty: this.dirty } }));
  }

  /** Focus the control of an API field path (from the error summary); false when no control has that path. */
  focusField(path: string): boolean {
    const el = this.renderRoot.querySelector<HTMLElement>(`#${fid(path)}`);
    el?.focus();
    return !!el;
  }

  private err(path: string) {
    return this.errors.find((e) => e.field === path)?.message ?? null;
  }

  private aria(path: string, hint?: string) {
    const e = this.err(path);
    const ids = [hint ? `${fid(path)}-hint` : '', e ? `${fid(path)}-err` : ''].filter(Boolean).join(' ');
    return { invalid: e ? 'true' : 'false', describedby: ids || nothing, error: e ? html`<span class="error" id=${`${fid(path)}-err`}>${e}</span>` : nothing };
  }

  private control(f: FieldDef, obj: Obj, path: string): TemplateResult {
    const id = fid(path);
    const a = this.aria(path, f.hint);
    const ro = !this.editable;
    const hint = f.hint ? html`<span class="hint" id=${`${id}-hint`}>${f.hint}</span>` : nothing;
    const set = (v: unknown) => { obj[f.name] = v; this.changed(); };
    if (f.kind === 'checkbox') {
      return html`<div class="wide"><label class="check"><input type="checkbox" id=${id} .checked=${obj[f.name] === true} ?disabled=${ro}
        aria-invalid=${a.invalid} aria-describedby=${a.describedby} @change=${(e: Event) => set((e.target as HTMLInputElement).checked)} />
        ${f.label}</label>${hint}${a.error}</div>`;
    }
    if (f.kind === 'select') {
      const opts = this.vocab ? f.options?.(this.vocab, this.draft, this.context) ?? [] : [];
      const value = String(obj[f.name] ?? '');
      return html`<label class="field"><span class="label">${f.label}</span>
        <select id=${id} ?disabled=${ro} aria-invalid=${a.invalid} aria-describedby=${a.describedby}
          @change=${(e: Event) => set((e.target as HTMLSelectElement).value || null)}>
          ${f.optional || !opts.includes(value) ? html`<option value="" ?selected=${!value}>${f.optional ? 'None' : 'Choose…'}</option>` : nothing}
          ${opts.map((o) => html`<option value=${o} ?selected=${o === value}>${o.replace(/_/g, ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase())}</option>`)}
        </select>${hint}${a.error}</label>`;
    }
    const value = String(obj[f.name] ?? '');
    const count = f.max ? html`<span class="count" aria-live="off">${value.length} / ${f.max} characters</span>` : nothing;
    const input = f.kind === 'textarea'
      ? html`<textarea id=${id} ?readonly=${ro} maxlength=${f.max ?? 600} .value=${value} aria-invalid=${a.invalid} aria-describedby=${a.describedby}
          @input=${(e: Event) => set((e.target as HTMLTextAreaElement).value)}></textarea>`
      : html`<input id=${id} ?readonly=${ro} maxlength=${f.max ?? 80} .value=${value} aria-invalid=${a.invalid} aria-describedby=${a.describedby}
          @input=${(e: Event) => set((e.target as HTMLInputElement).value)} />`;
    return html`<label class="field ${f.kind === 'textarea' ? 'wide' : ''}"><span class="label">${f.label}${f.optional ? ' (optional)' : ''}</span>
      ${input}${hint}${count}${a.error}</label>`;
  }

  private list(def: ListDef, owner: Obj, path: string): TemplateResult {
    if (!Array.isArray(owner[def.key])) owner[def.key] = [];
    const rows = owner[def.key] as Obj[];
    const move = (i: number, by: number) => { const [r] = rows.splice(i, 1); rows.splice(i + by, 0, r); this.changed(); };
    return html`<fieldset><legend>${def.label}</legend>
      ${this.aria(path).error}
      ${rows.length ? rows.map((row, i) => {
        const p = `${path}[${i}]`;
        const inactive = row.active === false;
        const name = `${def.item} ${i + 1}${row.code ? ` (${String(row.code)})` : ''}`;
        return html`<fieldset class="entry ${inactive ? 'inactive' : ''}"><legend>${name}${inactive ? ' — inactive, not published' : ''}</legend>
          ${this.aria(p).error}
          <div class="grid">${def.fields.map((f) => this.control(f, row, `${p}.${f.name}`))}</div>
          ${def.active ? html`<label class="check"><input type="checkbox" .checked=${!inactive} ?disabled=${!this.editable}
            @change=${(e: Event) => { if ((e.target as HTMLInputElement).checked) delete row.active; else row.active = false; this.changed(); }} />
            Active (shown to customers when published)</label>` : nothing}
          ${this.editable ? html`<div class="rowbtns">
            ${def.reorder ? html`<button type="button" class="btn small" ?disabled=${i === 0} aria-label=${`Move ${name} up`} @click=${() => move(i, -1)}>Move up</button>
              <button type="button" class="btn small" ?disabled=${i === rows.length - 1} aria-label=${`Move ${name} down`} @click=${() => move(i, 1)}>Move down</button>` : nothing}
            <button type="button" class="btn small ghost" aria-label=${`Remove ${name}`} @click=${() => { rows.splice(i, 1); this.changed(); }}>Remove</button></div>` : nothing}
        </fieldset>`;
      }) : html`<p class="muted">None. Customers see “to be confirmed” for this until approved content is published.</p>`}
      ${this.editable ? html`<div><button type="button" class="btn" @click=${() => { rows.push(blankRow(def, this.vocab, this.draft, this.context)); this.changed(); }}>Add ${def.item.toLowerCase()}</button></div>` : nothing}
    </fieldset>`;
  }

  private strings(def: StringsDef, owner: Obj, path: string): TemplateResult {
    if (!Array.isArray(owner[def.key])) owner[def.key] = [];
    const rows = owner[def.key] as string[];
    return html`<fieldset><legend>${def.label}</legend>
      ${def.hint ? html`<p class="small muted">${def.hint}</p>` : nothing}
      <div class="strings">${rows.map((v, i) => {
        const p = `${path}[${i}]`;
        const a = this.aria(p);
        return html`<div class="stringrow"><label class="field"><span class="label">${def.item} ${i + 1}</span>
          <input id=${fid(p)} ?readonly=${!this.editable} maxlength=${def.max} .value=${v} aria-invalid=${a.invalid} aria-describedby=${a.describedby}
            @input=${(e: Event) => { rows[i] = (e.target as HTMLInputElement).value; this.changed(); }} />${a.error}</label>
          ${this.editable ? html`<button type="button" class="btn small ghost" aria-label=${`Remove ${def.item.toLowerCase()} ${i + 1}`} @click=${() => { rows.splice(i, 1); this.changed(); }}>Remove</button>` : nothing}</div>`;
      })}</div>
      ${!rows.length ? html`<p class="muted">None.</p>` : nothing}
      ${this.editable ? html`<div><button type="button" class="btn" @click=${() => { rows.push(''); this.changed(); }}>Add ${def.item.toLowerCase()}</button></div>` : nothing}
    </fieldset>`;
  }

  private scalar(def: TextDef, owner: Obj, path: string): TemplateResult {
    return this.control({ name: def.key, label: def.label, kind: 'textarea', optional: true, max: def.max, hint: def.hint }, owner, path);
  }

  private object(def: ObjectDef, owner: Obj, path: string): TemplateResult {
    const value = owner[def.key] as Obj | null;
    const blank = (): Obj => {
      const o: Obj = {};
      for (const p of def.parts) {
        if (p.kind === 'list' || p.kind === 'strings') o[p.key] = [];
        else if (p.kind === 'scalar' || p.kind === 'object') o[p.key] = null;
        else o[p.name] = p.optional ? null : '';
      }
      return o;
    };
    return html`<fieldset><legend>${def.label}</legend>
      ${this.aria(path).error}
      ${value ? html`${def.parts.map((p) => this.renderPart(p, value, path))}
          ${this.editable ? html`<div><button type="button" class="btn ghost" @click=${() => { owner[def.key] = null; this.changed(); }}>Remove this policy</button></div>` : nothing}`
        : html`<p class="muted">Not provided. Customers see “to be confirmed”.</p>
          ${this.editable ? html`<div><button type="button" class="btn" @click=${() => { owner[def.key] = blank(); this.changed(); }}>Write this policy</button></div>` : nothing}`}
    </fieldset>`;
  }

  private renderPart(p: Part, owner: Obj, prefix: string): TemplateResult {
    const at = (k: string) => (prefix ? `${prefix}.${k}` : k);
    if (p.kind === 'list') return this.list(p, owner, at(p.key));
    if (p.kind === 'strings') return this.strings(p, owner, at(p.key));
    if (p.kind === 'scalar') return this.scalar(p, owner, at(p.key));
    if (p.kind === 'object') return this.object(p, owner, at(p.key));
    return this.control(p, owner, at(p.name));
  }

  override render() {
    if (!this.section) return nothing;
    const parts = PARTS[this.section.code] ?? [];
    return html`<form class="stack" novalidate @submit=${(e: Event) => {
        e.preventDefault();
        if (this.editable && !this.busy) this.dispatchEvent(new CustomEvent('editor-save', { bubbles: true, composed: true, detail: { value: this.value() } }));
      }}>
      ${parts.map((p) => this.renderPart(p, this.draft, ''))}
      ${this.editable ? html`<div class="row">
          <button class="btn primary" type="submit" aria-disabled=${this.busy ? 'true' : 'false'}>Save section</button>
          <button type="button" class="btn" ?disabled=${!this.dirty} @click=${() => this.reset()}>Undo unsaved changes</button>
          <span class="small muted" role="status">${this.dirty ? 'Unsaved changes' : 'No unsaved changes'}</span></div>` : nothing}
    </form>`;
  }
}
if (!customElements.get('vs-promise-editor')) customElements.define('vs-promise-editor', VsPromiseEditor);
