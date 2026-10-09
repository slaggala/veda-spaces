import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatFull, humanize } from '../../core/format/format.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';

type Tab = 'dashboard' | 'records' | 'releases' | 'media' | 'transfer';

interface CatalogRecord {
  id: string; kind: string; key: string; version: number; status: string; title: string; sha256: string;
  updated_on: string; updated_by: string; submitted_by: string | null; reviewed_by: string | null; review_note: string | null;
  document?: Record<string, unknown>;
}
interface Release {
  id: string; code: string; status: string; manifest_sha256: string; entries: number; created_on: string; valid: boolean | null;
  approval_reference: string | null; scheduled_for: string | null; activated_on: string | null; preview_approved_by: string | null;
  manifest?: Array<{ kind: string; key: string; version: number; sha256: string }>;
  validation?: { ok: boolean; checks: Record<string, string>; errors: string[]; warnings: string[] } | null;
  diff?: { against: string | null; added: unknown[]; removed: unknown[]; changed: unknown[] };
}
interface MediaObject { sha256: string; role: string; kind: string; variant: string; mime: string; bytes: number; width: number | null; height: number | null; scan_status: string; created_on: string }

const KINDS = ['home_config', 'room_template', 'product_family', 'product', 'extra', 'material', 'hardware', 'media', 'package', 'pricing', 'rule', 'copy', 'property_type'];
const EDIT: Record<string, string> = { pricing: 'catalog.pricing.edit', media: 'catalog.media.edit', material: 'catalog.spec.edit', hardware: 'catalog.spec.edit', copy: 'catalog.spec.edit' };

/**
 * Estimator catalog workspace (ADR-013): dashboard, versioned records, releases (validation, customer preview,
 * approval, schedule, activation, rollback), media library, import and export. Every action is checked by the API
 * (least privilege, four-eyes); this page only hides what the user cannot do. Pricing is never shown without
 * catalog.pricing.view.
 */
export class VsCatalogPage extends SessionElement {
  static override properties = {
    tab: { state: true }, problem: { state: true }, dashboard: { state: true }, records: { state: true }, releases: { state: true },
    media: { state: true }, record: { state: true }, release: { state: true }, draft: { state: true }, kind: { state: true },
    preview: { state: true }, transfer: { state: true }, busy: { state: true },
  };
  declare tab: Tab;
  declare problem: ApiProblem | null;
  declare dashboard: Record<string, unknown> | null;
  declare records: CatalogRecord[];
  declare releases: Release[];
  declare media: MediaObject[];
  declare record: CatalogRecord | null;
  declare release: Release | null;
  declare draft: string;
  declare kind: string;
  declare preview: Record<string, unknown> | null;
  declare transfer: Record<string, unknown> | null;
  declare busy: boolean;
  static override styles = [...shared, pageStyles, tableStyles, css`
    .grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
    .stat { font: 600 28px/1.1 var(--vs-font-sans); }
    textarea { width: 100%; min-height: 320px; font-family: var(--vs-font-mono); font-size: 12px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 12px 0; }
    .pass { color: var(--vs-success); } .fail { color: var(--vs-danger); }
    ul.plain { padding-left: 18px; margin: 4px 0; }
    pre { font-family: var(--vs-font-mono); font-size: 12px; white-space: pre-wrap; background: var(--vs-cream); padding: 12px; border-radius: 8px; }`];

  constructor() {
    super();
    this.tab = 'dashboard';
    this.problem = null;
    this.dashboard = null;
    this.records = [];
    this.releases = [];
    this.media = [];
    this.record = null;
    this.release = null;
    this.draft = '';
    this.kind = '';
    this.preview = null;
    this.transfer = null;
    this.busy = false;
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private async run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    this.problem = null;
    this.busy = true;
    try { return await fn(); } catch (e) { this.problem = e as ApiProblem; return undefined; } finally { this.busy = false; }
  }

  private async load() {
    await this.run(async () => {
      if (this.tab === 'dashboard') this.dashboard = (await api.get<Record<string, unknown>>('/api/v1/catalog/dashboard')).data;
      if (this.tab === 'records') this.records = (await api.get<CatalogRecord[]>('/api/v1/catalog/records', this.kind ? { kind: this.kind } : undefined)).data;
      if (this.tab === 'releases') this.releases = (await api.get<Release[]>('/api/v1/catalog/releases')).data;
      if (this.tab === 'media') this.media = (await api.get<MediaObject[]>('/api/v1/catalog/media')).data;
    });
  }

  private async openRecord(id: string) {
    const r = await this.run(() => api.get<CatalogRecord>(`/api/v1/catalog/records/${id}`));
    if (r) { this.record = r.data; this.draft = JSON.stringify(r.data.document ?? {}, null, 2); }
  }

  private async recordAction(path: string, body?: unknown, method: 'post' | 'put' = 'post') {
    if (!this.record) return;
    const r = await this.run(() => (method === 'put' ? api.put<CatalogRecord>(path, body) : api.post<CatalogRecord>(path, body)));
    if (r) { this.record = r.data; this.draft = JSON.stringify(r.data.document ?? {}, null, 2); void this.load(); }
  }

  private parsedDraft(): Record<string, unknown> | null {
    try { return JSON.parse(this.draft) as Record<string, unknown>; } catch { this.problem = { title: 'The document is not valid JSON.' } as ApiProblem; return null; }
  }

  private async openRelease(id: string) {
    const r = await this.run(() => api.get<Release>(`/api/v1/catalog/releases/${id}`));
    if (r) { this.release = r.data; this.preview = null; }
  }

  private async releaseAction(action: string, body?: unknown) {
    if (!this.release) return;
    const r = await this.run(() => api.post<Release>(`/api/v1/catalog/releases/${this.release!.id}/${action}`, body));
    if (r) { await this.openRelease(this.release.id); void this.load(); }
  }

  private async customerPreview() {
    if (!this.release) return;
    const r = await this.run(() => api.get<Record<string, unknown>>(`/api/v1/catalog/releases/${this.release!.id}/customer-view`));
    if (r) this.preview = r.data;
  }

  private renderDashboard() {
    const d = this.dashboard;
    if (!d) return html`<vs-skeleton rows="6"></vs-skeleton>`;
    const list = (label: string, items: unknown) => html`<div class="card"><h3>${label}</h3>${Array.isArray(items) && items.length
      ? html`<ul class="plain">${(items as string[]).slice(0, 12).map((i) => html`<li>${typeof i === 'string' ? i : JSON.stringify(i)}</li>`)}</ul>`
      : items === null ? html`<p class="small muted">Needs catalog pricing access.</p>` : html`<p class="small muted">None.</p>`}</div>`;
    return html`<div class="grid">
        <div class="card"><p class="small muted">Active release</p><p class="stat">${(d.active_release as string) ?? 'None'}</p></div>
        <div class="card"><p class="small muted">Drafts</p><p class="stat">${d.drafts}</p></div>
        <div class="card"><p class="small muted">Pending review</p><p class="stat">${d.pending_review}</p></div>
        <div class="card"><p class="small muted">Approved, not released</p><p class="stat">${d.approved_unreleased}</p></div>
      </div>
      <div class="grid">
        ${list('Products with missing images', d.products_missing_images)}
        ${list('Extras without “What is this?”', d.extras_without_explanation)}
        ${list('Materials without a registered statement', d.materials_without_specification)}
        ${list('Unpriced items', d.unpriced_items)}
        ${list('Unsupported combinations', d.unsupported_combinations)}
        ${list('Scheduled releases', d.scheduled)}
      </div>
      <div class="card"><h3>Recent changes</h3><ul class="plain">${((d.recent as Array<{ event: string; on: string }>) ?? []).map((e) => html`<li>${humanize(e.event)} · ${formatFull(e.on)}</li>`)}</ul></div>`;
  }

  private renderRecords() {
    return html`<div class="row" role="search">
        <label class="field"><span class="label">Kind</span><select @change=${(e: Event) => { this.kind = (e.target as HTMLSelectElement).value; void this.load(); }}>
          <option value="">All</option>${KINDS.map((k) => html`<option value=${k} ?selected=${this.kind === k}>${humanize(k)}</option>`)}</select></label>
        ${this.can('catalog.edit') || this.can('catalog.spec.edit') || this.can('catalog.media.edit') || this.can('catalog.pricing.edit')
          ? html`<button class="btn" @click=${() => { this.record = { id: '', kind: this.kind || 'product', key: '', version: 0, status: 'NEW', title: '', sha256: '', updated_on: '', updated_by: '', submitted_by: null, reviewed_by: null, review_note: null }; this.draft = '{\n}'; }}>New record</button>` : nothing}
      </div>
      ${!this.records.length ? html`<div class="card"><vs-empty-state heading="No catalog records."></vs-empty-state></div>`
        : html`<div class="table-wrap"><table class="cards"><thead><tr><th>Kind</th><th>Key</th><th>Version</th><th>Status</th><th>Title</th><th>Updated</th></tr></thead>
          <tbody>${this.records.map((r) => html`<tr class="clickable" tabindex="0" @click=${() => this.openRecord(r.id)} @keydown=${(e: KeyboardEvent) => e.key === 'Enter' && this.openRecord(r.id)}>
            <td data-label="Kind">${humanize(r.kind)}</td><td data-label="Key" class="mono">${r.key}</td><td data-label="Version">${r.version}</td>
            <td data-label="Status">${humanize(r.status)}</td><td data-label="Title">${r.title}</td><td data-label="Updated">${formatFull(r.updated_on)}</td></tr>`)}</tbody></table></div>`}`;
  }

  private renderRecordDrawer() {
    const r = this.record;
    if (!r) return nothing;
    const isNew = r.status === 'NEW';
    const canEdit = this.can(EDIT[r.kind] ?? 'catalog.edit');
    const editable = canEdit && (isNew || r.status === 'DRAFT') && r.document !== undefined || isNew;
    return html`${isNew ? html`<div class="row">
          <label class="field"><span class="label">Kind</span><select @change=${(e: Event) => (this.record = { ...r, kind: (e.target as HTMLSelectElement).value })}>
            ${KINDS.filter((k) => this.can(EDIT[k] ?? 'catalog.edit')).map((k) => html`<option value=${k} ?selected=${r.kind === k}>${humanize(k)}</option>`)}</select></label>
          <label class="field"><span class="label">Key</span><input .value=${r.key} @input=${(e: Event) => (this.record = { ...r, key: (e.target as HTMLInputElement).value.trim() })} /></label></div>`
        : html`<p class="small muted">${humanize(r.kind)} · <span class="mono">${r.key}</span> · version ${r.version} · ${humanize(r.status)}${r.review_note ? ` · note: ${r.review_note}` : ''}</p>`}
      ${r.document === undefined && !isNew ? html`<p>Pricing details need catalog pricing access.</p>`
        : html`<label class="field"><span class="label">Document (validated by the server)</span><textarea ?readonly=${!editable} .value=${this.draft} @input=${(e: Event) => (this.draft = (e.target as HTMLTextAreaElement).value)}></textarea></label>`}
      <div class="row">
        ${isNew ? html`<button class="btn primary" ?disabled=${this.busy} @click=${async () => { const doc = this.parsedDraft(); if (!doc) return;
          const created = await this.run(() => api.post<CatalogRecord>('/api/v1/catalog/records', { kind: r.kind, key: r.key, document: doc }));
          if (created) { this.record = created.data; void this.load(); } }}>Create draft</button>` : nothing}
        ${!isNew && editable && r.status === 'DRAFT' ? html`<button class="btn" @click=${() => { const doc = this.parsedDraft(); if (doc) void this.recordAction(`/api/v1/catalog/records/${r.id}`, { document: doc }, 'put'); }}>Save draft</button>
          <button class="btn primary" @click=${() => this.recordAction(`/api/v1/catalog/records/${r.id}/submit`)}>Submit for review</button>` : nothing}
        ${!isNew && r.status === 'IN_REVIEW' && this.can('catalog.review') ? html`<button class="btn primary" @click=${() => this.recordAction(`/api/v1/catalog/records/${r.id}/approve`, {})}>Approve</button>
          <button class="btn" @click=${() => { const note = prompt('Why is it rejected?'); if (note) void this.recordAction(`/api/v1/catalog/records/${r.id}/reject`, { note }); }}>Reject</button>` : nothing}
        ${!isNew && canEdit && ['IN_REVIEW', 'APPROVED', 'ACTIVE', 'RETIRED', 'SCHEDULED'].includes(r.status) ? html`<button class="btn" @click=${() => this.recordAction(`/api/v1/catalog/records/${r.id}/new-version`)}>New version</button>` : nothing}
        ${!isNew && canEdit && ['DRAFT', 'APPROVED', 'RETIRED'].includes(r.status) ? html`<button class="btn ghost" @click=${() => this.recordAction(`/api/v1/catalog/records/${r.id}/archive`)}>Archive</button>` : nothing}
      </div>`;
  }

  private renderReleases() {
    return html`${this.can('catalog.admin') ? html`<div class="row"><button class="btn primary" @click=${async () => {
        const code = prompt('Release code (capital letters, digits, . _ -)'); if (!code) return;
        const r = await this.run(() => api.post<Release>('/api/v1/catalog/releases', { code }));
        if (r) { void this.load(); void this.openRelease(r.data.id); } }}>New release from approved records</button>
        <button class="btn" @click=${async () => { const reason = prompt('Roll back to the previous release (its whole manifest, restored as a new release). Reason or approval reference:'); if (reason) { await this.run(() => api.post('/api/v1/catalog/rollback', { approval_reference: reason })); void this.load(); } }}>Roll back</button></div>` : nothing}
      ${!this.releases.length ? html`<div class="card"><vs-empty-state heading="No releases yet."></vs-empty-state></div>`
        : html`<div class="table-wrap"><table class="cards"><thead><tr><th>Release</th><th>Status</th><th>Entries</th><th>Valid</th><th>Created</th></tr></thead>
          <tbody>${this.releases.map((r) => html`<tr class="clickable" tabindex="0" @click=${() => this.openRelease(r.id)} @keydown=${(e: KeyboardEvent) => e.key === 'Enter' && this.openRelease(r.id)}>
            <td data-label="Release" class="mono">${r.code}</td><td data-label="Status">${humanize(r.status)}</td><td data-label="Entries">${r.entries}</td>
            <td data-label="Valid">${r.valid === null ? 'Not validated' : r.valid ? 'Yes' : 'No'}</td><td data-label="Created">${formatFull(r.created_on)}</td></tr>`)}</tbody></table></div>`}`;
  }

  private renderReleaseDrawer() {
    const r = this.release;
    if (!r) return nothing;
    const v = r.validation;
    return html`<p class="small muted">${humanize(r.status)} · manifest <span class="mono">${r.manifest_sha256.slice(0, 12)}…</span> · ${r.entries} records
        ${r.approval_reference ? html` · approval: ${r.approval_reference}` : nothing}</p>
      <div class="row">
        ${this.can('catalog.admin') ? html`<button class="btn" @click=${() => this.releaseAction('validate')}>Validate</button>` : nothing}
        <button class="btn" @click=${() => this.customerPreview()}>Customer preview</button>
        ${this.can('catalog.approve') && ['DRAFT', 'IN_REVIEW'].includes(r.status) ? html`<button class="btn" @click=${() => this.releaseAction('preview-approval')}>Approve preview</button>` : nothing}
        ${this.can('catalog.admin') && r.status === 'DRAFT' ? html`<button class="btn" @click=${() => this.releaseAction('submit')}>Submit</button>` : nothing}
        ${this.can('catalog.approve') && r.status === 'IN_REVIEW' ? html`<button class="btn primary" @click=${() => { const ref = prompt('Approval reference'); if (ref) void this.releaseAction('approve', { approval_reference: ref }); }}>Approve release</button>` : nothing}
        ${this.can('catalog.admin') && r.status === 'APPROVED' ? html`<button class="btn" @click=${() => { const at = prompt('Activate at (ISO date-time with offset)'); if (at) void this.releaseAction('schedule', { at }); }}>Schedule</button>
          <button class="btn primary" @click=${() => { if (confirm(`Activate ${r.code}? Customers see it only while the V3 flag is on.`)) void this.releaseAction('activate'); }}>Activate now</button>` : nothing}
      </div>
      ${v ? html`<div class="card"><h3>Validation ${v.ok ? html`<span class="pass">passed</span>` : html`<span class="fail">failed</span>`}</h3>
          <ul class="plain">${Object.entries(v.checks).map(([k, s]) => html`<li class=${s}>${humanize(k)}: ${s}</li>`)}</ul>
          ${v.errors.length ? html`<h4>Errors</h4><ul class="plain">${v.errors.map((e) => html`<li>${e}</li>`)}</ul>` : nothing}
          ${v.warnings.length ? html`<details><summary>${v.warnings.length} warnings</summary><ul class="plain">${v.warnings.map((w) => html`<li>${w}</li>`)}</ul></details>` : nothing}</div>` : nothing}
      ${r.diff ? html`<div class="card"><h3>Changes against ${r.diff.against ?? 'nothing (first release)'}</h3>
          <p>${r.diff.added.length} added · ${r.diff.changed.length} changed · ${r.diff.removed.length} removed</p></div>` : nothing}
      ${this.preview ? html`<div class="card"><h3>Customer preview</h3>
          ${Object.values((this.preview.room_template ?? {}) as Record<string, { name: string; included: Array<{ product: string }>; extras: string[] }>).map((room) => html`
            <h4>${room.name}</h4><ul class="plain">${room.included.map((s) => html`<li>${(this.preview!.product as Record<string, { name: string }>)[s.product]?.name ?? s.product}</li>`)}
            ${room.extras.map((x) => html`<li>Extra: ${(this.preview!.extra as Record<string, { name: string }>)[x]?.name ?? x}</li>`)}</ul>`)}
          <details><summary>Full customer view (exactly what the public page receives)</summary><pre>${JSON.stringify(this.preview, null, 2)}</pre></details></div>` : nothing}
      <details><summary>Manifest</summary><ul class="plain">${(r.manifest ?? []).map((e) => html`<li class="mono">${e.kind} ${e.key} v${e.version}</li>`)}</ul></details>`;
  }

  private renderMedia() {
    return html`${this.can('catalog.media.edit') ? html`<div class="row"><label class="field"><span class="label">Upload an image (JPEG, PNG, WebP) or a 3D model (GLB, USDZ)</span>
        <input type="file" accept="image/jpeg,image/png,image/webp,.glb,.usdz" @change=${async (e: Event) => {
          const file = (e.target as HTMLInputElement).files?.[0]; if (!file) return;
          const bytes = new Uint8Array(await file.arrayBuffer());
          let bin = ''; for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
          const r = await this.run(() => api.post<Record<string, unknown>>('/api/v1/catalog/media', { data_base64: btoa(bin) }));
          if (r) { this.transfer = r.data; void this.load(); } }} /></label></div>
        <p class="small muted">The file name is never kept. Images are re-encoded without metadata; files stay private until a release uses them.</p>
        ${this.transfer ? html`<pre>${JSON.stringify(this.transfer, null, 2)}</pre>` : nothing}` : nothing}
      <div class="table-wrap"><table class="cards"><thead><tr><th>Object</th><th>Role</th><th>Kind</th><th>Variant</th><th>Size</th><th>Scan</th></tr></thead>
        <tbody>${this.media.map((m) => html`<tr><td data-label="Object" class="mono">${m.sha256.slice(0, 16)}…</td><td data-label="Role">${humanize(m.role)}</td>
          <td data-label="Kind">${m.kind}</td><td data-label="Variant">${m.variant}</td><td data-label="Size">${m.width ? `${m.width}×${m.height} · ` : ''}${Math.round(m.bytes / 1024)} KB</td>
          <td data-label="Scan">${humanize(m.scan_status)}</td></tr>`)}</tbody></table></div>`;
  }

  private renderTransfer() {
    let content = '';
    let format = 'csv';
    return html`<div class="card"><h3>Import (dry run first; creates drafts only)</h3>
        <label class="field"><span class="label">Format</span><select @change=${(e: Event) => (format = (e.target as HTMLSelectElement).value)}><option value="csv">CSV (kind,key,document)</option><option value="json">JSON</option></select></label>
        <label class="field"><span class="label">Content</span><textarea @input=${(e: Event) => (content = (e.target as HTMLTextAreaElement).value)}></textarea></label>
        <div class="row"><button class="btn" @click=${async () => { const r = await this.run(() => api.post<Record<string, unknown>>('/api/v1/catalog/import', { format, content })); if (r) this.transfer = r.data; }}>Dry run</button>
          <button class="btn primary" @click=${async () => { const r = await this.run(() => api.post<Record<string, unknown>>('/api/v1/catalog/import', { format, content, apply: true })); if (r) this.transfer = r.data; }}>Create drafts</button></div>
        ${this.transfer ? html`<pre>${JSON.stringify(this.transfer, null, 2)}</pre>` : nothing}</div>
      <div class="card"><h3>Export</h3><p class="small muted">The latest version of every record, as JSON. Pricing is included only with pricing access.</p>
        <button class="btn" @click=${async () => { const r = await this.run(() => api.get<unknown>('/api/v1/catalog/export')); if (r) this.transfer = r.data as Record<string, unknown>; }}>Export</button></div>`;
  }

  override render() {
    const tabs: Array<{ id: Tab; label: string; hidden?: boolean }> = [
      { id: 'dashboard', label: 'Dashboard' }, { id: 'records', label: 'Records' }, { id: 'releases', label: 'Releases' },
      { id: 'media', label: 'Media' }, { id: 'transfer', label: 'Import and export', hidden: !this.can('catalog.admin') },
    ];
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Estimator</p><h1 class="display">Catalog</h1></div></div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      <vs-tabs label="Catalog" .tabs=${tabs} .selected=${this.tab} @tab-change=${(e: CustomEvent<Tab>) => { this.tab = e.detail; this.transfer = null; void this.load(); }}>
        ${{ dashboard: () => this.renderDashboard(), records: () => this.renderRecords(), releases: () => this.renderReleases(), media: () => this.renderMedia(), transfer: () => this.renderTransfer() }[this.tab]()}
      </vs-tabs>
      <vs-drawer wide .open=${Boolean(this.record)} heading=${this.record ? (this.record.status === 'NEW' ? 'New catalog record' : this.record.title) : ''} @close=${() => (this.record = null)}>${this.renderRecordDrawer()}</vs-drawer>
      <vs-drawer wide .open=${Boolean(this.release)} heading=${this.release ? `Release ${this.release.code}` : ''} @close=${() => (this.release = null)}>${this.renderReleaseDrawer()}</vs-drawer>
    </div>`;
  }
}
customElements.define('vs-catalog-page', VsCatalogPage);
