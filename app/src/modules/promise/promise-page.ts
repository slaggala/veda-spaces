import { css, html, nothing, type TemplateResult } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatFull, humanize } from '../../core/format/format.js';
import '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { promiseApi, type Change, type Changes, type Landing, type Person, type PreviewView, type SectionView, type VersionDetail,
  type VersionSummary, type Vocabulary } from './api.js';
import './promise-editor.js';
import type { VsPromiseEditor } from './promise-editor.js';
import { previewPage } from './promise-preview.js';

type View = 'landing' | 'version';
type Tab = 'edit' | 'changes' | 'preview' | 'history';
type Confirm = { action: 'submit' | 'approve' | 'publish' | 'return' | 'discard' | 'changes' | 'create'; title: string; body: string;
  text?: { label: string; required: boolean; name: 'reason' | 'comment' | 'note' | 'change_summary' }; section?: string; basedOn?: string };

const WIDTHS = [['Mobile', 360], ['Tablet', 768], ['Desktop', 1280]] as const;
const who = (p: Person | null) => p?.display_name ?? (p ? 'Unknown user' : '—');
const when = (iso: string | null) => (iso ? formatFull(iso) : '—');
const counts = (q: Record<string, number>) => Object.entries(q).map(([k, n]) => `${humanize(k)} ${n}`).join(' · ') || 'None';
const shown = (v: unknown): string => (v == null ? '—' : Array.isArray(v) ? v.join(', ') : typeof v === 'object' ? JSON.stringify(v) : String(v));

/**
 * Commercial › Customer Promise (decision log 37): the landing page (OI-MTQ-18 state, published and open versions,
 * completeness of the fourteen customer areas, history) and a version's workspace (structured section editing, review,
 * approval, publication, the semantic changes and the customer preview). The API checks every action again (capabilities,
 * state, four-eyes, content rules); this page only hides what the signed-in user may not do.
 */
export class VsPromisePage extends SessionElement {
  static override properties = {
    view: { state: true }, tab: { state: true }, landing: { state: true }, history: { state: true }, vocab: { state: true },
    version: { state: true }, section: { state: true }, problem: { state: true }, errors: { state: true }, conflict: { state: true },
    changes: { state: true }, preview: { state: true }, width: { state: true }, confirm: { state: true }, busy: { state: true },
    announcement: { state: true }, dirty: { state: true }, disabled: { state: true },
  };
  declare view: View;
  declare tab: Tab;
  declare landing: Landing | null;
  declare history: VersionSummary[];
  declare vocab: Vocabulary | null;
  declare version: VersionDetail | null;
  declare section: string;
  declare problem: ApiProblem | null;
  declare errors: { field: string; message: string }[];
  declare conflict: boolean;
  declare changes: Changes | null;
  declare preview: PreviewView | null;
  declare width: number;
  declare confirm: Confirm | null;
  declare busy: boolean;
  declare announcement: string;
  declare dirty: boolean;
  /** The API answered 404: the portal is not enabled in this environment. */
  declare disabled: boolean;

  static override styles = [...shared, pageStyles, tableStyles, css`
    .btn.small { min-height: var(--vs-target); }
    .btn { white-space: nowrap; min-width: var(--vs-target); }
    .cards { display: grid; gap: var(--vs-space-4); grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); }
    .layout { display: grid; gap: var(--vs-space-5); grid-template-columns: minmax(0, 1fr); }
    @media (min-width: 1024px) { .layout { grid-template-columns: 240px minmax(0, 1fr); } }
    nav.sections ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
    nav.sections button { width: 100%; justify-content: flex-start; text-align: left; border-color: transparent; background: transparent; }
    nav.sections button[aria-current='true'] { border-color: var(--vs-copper); background: var(--vs-surface); }
    .tabs { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .tabs button[aria-pressed='true'], .widths button[aria-pressed='true'] { border-color: var(--vs-copper-strong); color: var(--vs-copper-text); }
    .preview-banner { border: 2px dashed var(--vs-danger); color: var(--vs-danger); padding: var(--vs-space-3) var(--vs-space-4);
      border-radius: var(--vs-radius-card); font: 700 16px/22px var(--vs-font-sans); letter-spacing: .08em; text-align: center; }
    .frame { margin: 0 auto; width: 100%; border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); background: var(--vs-paper); overflow: hidden; }
    .tag { font: 600 11px/16px var(--vs-font-sans); letter-spacing: .06em; text-transform: uppercase; padding: 1px 8px;
      border-radius: var(--vs-radius-pill); border: 1px solid var(--vs-line); white-space: nowrap; }
    ul.plain { margin: 0; padding-left: 18px; display: grid; gap: 4px; } ul.plain li { overflow-wrap: anywhere; }
    td, th { overflow-wrap: anywhere; } td.before, td.after { white-space: pre-wrap; }
    h2:focus, h3:focus { outline: none; } h2:focus-visible { outline: 2px solid var(--vs-focus-ring); }
    dl.meta { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 4px var(--vs-space-3); margin: 0; font-size: 14px; }
    dl.meta dt { color: var(--vs-ink-muted); } dl.meta dd { margin: 0; overflow-wrap: anywhere; }
  `];

  constructor() {
    super();
    this.view = 'landing';
    this.tab = 'edit';
    this.landing = null;
    this.history = [];
    this.vocab = null;
    this.version = null;
    this.section = 'CONTACTS';
    this.problem = null;
    this.errors = [];
    this.conflict = false;
    this.changes = null;
    this.preview = null;
    this.width = 1280;
    this.confirm = null;
    this.busy = false;
    this.announcement = '';
    this.dirty = false;
    this.disabled = false;
  }

  private readonly beforeUnload = (e: BeforeUnloadEvent) => { if (this.dirty) e.preventDefault(); };

  override connectedCallback() {
    super.connectedCallback();
    window.addEventListener('beforeunload', this.beforeUnload);
    void this.loadLanding();
  }

  override disconnectedCallback() {
    window.removeEventListener('beforeunload', this.beforeUnload);
    super.disconnectedCallback();
  }

  private get editor(): VsPromiseEditor | null {
    return this.renderRoot.querySelector('vs-promise-editor') as VsPromiseEditor | null;
  }

  /** True when there is nothing unsaved, or the user agreed to lose it. */
  private leaveOk(): boolean {
    if (!this.dirty) return true;
    if (!confirm('This section has unsaved changes. Leave without saving them?')) return false;
    this.dirty = false;
    return true;
  }

  private async run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    this.problem = null;
    this.busy = true;
    try { return await fn(); } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404 && p.code === 'NOT_FOUND' && !this.landing) this.disabled = true;
      else this.problem = p;
      return undefined;
    } finally { this.busy = false; }
  }

  private async focusHeading(id: string) {
    await this.updateComplete;
    (this.renderRoot.querySelector(`#${id}`) as HTMLElement | null)?.focus();
  }

  private async loadLanding() {
    await this.run(async () => {
      const [l, h, v] = await Promise.all([promiseApi.landing(), promiseApi.versions(), this.vocab ? null : promiseApi.vocabulary()]);
      this.landing = l.data;
      this.history = h.data;
      if (v) this.vocab = v.data;
    });
  }

  private async openVersion(id: string, tab: Tab = 'edit') {
    if (!this.leaveOk()) return;
    const r = await this.run(() => promiseApi.version(id));
    if (!r) return;
    this.version = r.data;
    this.view = 'version';
    this.tab = tab;
    this.errors = [];
    this.conflict = false;
    this.changes = null;
    this.preview = null;
    if (!this.version.sections.some((s) => s.code === this.section)) this.section = 'CONTACTS';
    if (tab === 'changes') void this.loadChanges();
    await this.focusHeading('version-title');
  }

  private async backToLanding() {
    if (!this.leaveOk()) return;
    this.view = 'landing';
    this.version = null;
    await this.loadLanding();
    await this.focusHeading('page-title');
  }

  private async reload() {
    if (!this.version) return;
    this.dirty = false;
    const r = await this.run(() => promiseApi.version(this.version!.id));
    if (r) { this.version = r.data; this.conflict = false; this.errors = []; }
  }

  private selectSection(code: string) {
    if (code === this.section || !this.leaveOk()) return;
    this.section = code;
    this.errors = [];
    void this.focusHeading('section-title');
  }

  private async setTab(tab: Tab) {
    if (tab !== 'edit' && !this.leaveOk()) return;
    this.tab = tab;
    if (tab === 'changes' && !this.changes) await this.loadChanges();
    if (tab === 'preview' && !this.preview) await this.loadPreview();
    await this.focusHeading('tab-title');
  }

  private async loadChanges() {
    if (!this.version) return;
    const r = await this.run(() => promiseApi.changes(this.version!.id));
    if (r) this.changes = r.data;
  }

  private async loadPreview() {
    if (!this.version) return;
    const r = await this.run(() => promiseApi.preview(this.version!.id));
    if (r) this.preview = r.data;
  }

  // --- writes ---------------------------------------------------------------------------------------------------------
  private async apply(fn: () => Promise<{ data: VersionDetail }>, done: string) {
    this.problem = null;
    this.errors = [];
    this.conflict = false;
    this.busy = true;
    try {
      const r = await fn();
      this.version = r.data;
      this.dirty = false;
      this.changes = null;
      this.preview = null;
      this.announcement = done;
      return true;
    } catch (e) {
      const p = e as ApiProblem;
      if (p.code === 'VERSION_CONFLICT' || p.code === 'PRECONDITION_REQUIRED') this.conflict = true;
      else if (p.errors.length) this.errors = p.errors.map((x) => ({ field: x.field, message: x.message ?? humanize(x.code) }));
      else this.problem = p;
      const problems = p.ext<{ section: string; message: string }[]>('problems');
      if (problems?.length) this.errors = problems.map((x) => ({ field: '', message: `${this.sectionTitle(x.section)}: ${x.message}` }));
      this.announcement = 'The action was not completed.';
      await this.updateComplete;
      (this.renderRoot.querySelector('vs-error-summary') as unknown as { focusSummary?: () => void } | null)?.focusSummary?.();
      return false;
    } finally { this.busy = false; }
  }

  private sectionTitle(code: string) {
    return this.vocab?.sections.find((s) => s.code === code)?.title ?? humanize(code);
  }

  private async save(e: CustomEvent<{ value: Record<string, unknown> }>) {
    const v = this.version;
    if (!v || this.busy) return;
    const ok = await this.apply(() => promiseApi.save(v, this.section, e.detail.value), `${this.sectionTitle(this.section)} saved.`);
    if (ok) await this.focusHeading('section-title');
  }

  private async runConfirm(form: HTMLFormElement) {
    const c = this.confirm;
    const v = this.version;
    if (!c) return;
    const text = c.text ? String(new FormData(form).get(c.text.name) ?? '').trim() : '';
    if (c.text?.required && text.length < 5) {
      const field = form.querySelector('textarea');
      field?.setAttribute('aria-invalid', 'true');
      field?.focus();
      return;
    }
    this.confirm = null;
    if (c.action === 'create') {
      const r = await this.run(() => promiseApi.create({ ...(c.basedOn ? { based_on_pack_id: c.basedOn } : {}), change_summary: text || null }));
      if (r) { this.announcement = `Draft version ${r.data.version_no} started.`; this.version = r.data; await this.openVersion(r.data.id); }
      return;
    }
    if (!v) return;
    const labels: Record<string, string> = { submit: 'Submitted for review.', approve: 'Version approved.', publish: 'Version published.',
      return: 'Returned to draft.', discard: 'Draft discarded.', changes: 'Changes requested; the version is back in draft.' };
    if (c.action === 'changes') await this.apply(() => promiseApi.review(v, c.section!, 'CHANGES_REQUESTED', text), labels.changes);
    else if (c.action === 'approve') await this.apply(() => promiseApi.action(v, 'approve', text ? { note: text } : {}), labels.approve);
    else if (c.action === 'return' || c.action === 'discard') await this.apply(() => promiseApi.action(v, c.action as 'return', { reason: text }), labels[c.action]);
    else await this.apply(() => promiseApi.action(v, c.action as 'submit'), labels[c.action]);
    await this.focusHeading('version-title');
  }

  private async approveSection(code: string) {
    const v = this.version;
    if (!v) return;
    await this.apply(() => promiseApi.review(v, code, 'APPROVED'), `${this.sectionTitle(code)} approved.`);
  }

  // --- landing --------------------------------------------------------------------------------------------------------
  private versionCard(label: string, v: VersionSummary | null, empty: string): TemplateResult {
    return html`<section class="card stack" aria-labelledby=${`card-${label}`}>
      <h3 id=${`card-${label}`}>${label}</h3>
      ${v ? html`<dl class="meta">
          <dt>Version</dt><dd>${v.version_no} (${v.content_version})</dd>
          <dt>Status</dt><dd><span class="tag">${humanize(v.status)}</span></dd>
          <dt>Summary</dt><dd>${v.change_summary ?? '—'}</dd>
          ${v.published_on ? html`<dt>Effective since</dt><dd>${when(v.published_on)} (published by ${who(v.published_by)})</dd>` : html`<dt>Started</dt><dd>${when(v.created_on)} by ${who(v.created_by)}</dd>`}
          <dt>Quotations</dt><dd>${counts(v.quotations)}</dd></dl>
        <div><button class="btn" @click=${() => this.openVersion(v.id)}>Open version ${v.version_no}</button></div>`
        : html`<p class="muted">${empty}</p>`}
    </section>`;
  }

  private renderLanding(): TemplateResult {
    const l = this.landing;
    if (!l) return html`<vs-skeleton rows="6"></vs-skeleton>`;
    return html`
      <vs-banner kind=${l.authority.state === 'DELEGATED_TO_CUSTOMER_PROMISE' ? 'info' : 'warning'}>
        <strong>Owner decision OI-MTQ-18:</strong> ${l.authority.message}
        ${l.authority.register_reference ? html`<br><span class="small">Register reference: ${l.authority.register_reference} (${l.authority.decided_on})</span>` : nothing}
      </vs-banner>
      <div class="cards">
        ${this.versionCard('Published version', l.published, 'Nothing is published yet.')}
        ${this.versionCard('Version in progress', l.open, 'No draft is in progress.')}
      </div>
      ${l.pending_reviews.length ? html`<p>Sections waiting for review: ${l.pending_reviews.map((c) => this.sectionTitle(c)).join(', ')}.</p>` : nothing}
      ${l.actions.create_draft ? html`<div class="row"><button class="btn primary" @click=${() => (this.confirm = { action: 'create', title: 'Start a new draft',
          body: l.published ? `The draft starts as a copy of published version ${l.published.version_no}. Nothing changes for customers until a version is reviewed, approved and published.`
            : 'The first draft starts empty. Nothing is pre-filled: every section is written and approved by Veda Spaces.',
          text: { label: 'What this version changes (optional)', required: false, name: 'change_summary' } })}>Start a new draft</button></div>` : nothing}
      <section class="stack" aria-labelledby="completeness">
        <h2 id="completeness">Completeness of the customer information</h2>
        <p class="small muted">“Structure” means the platform can show the area; “owner-approved content” means a published version
          carries it and OI-MTQ-18 names this portal as the source. Effective dating: ${humanize(l.effective_dating)}.</p>
        <div class="table-wrap" tabindex="0" role="region" aria-label="Table, scrolls sideways on small screens"><table class="cards"><caption class="sr-only">Customer information areas</caption>
          <thead><tr><th scope="col">Area</th><th scope="col">Section</th><th scope="col">Status</th><th scope="col">Customers see</th>
            <th scope="col">Structure</th><th scope="col">Owner-approved content</th></tr></thead>
          <tbody>${l.areas.map((a) => html`<tr>
            <td data-label="Area">${a.title}</td>
            <td data-label="Section">${a.section ? this.sectionTitle(a.section) : `Contract terms (${a.governed_by})`}</td>
            <td data-label="Status"><span class="tag">${humanize(a.status)}</span></td>
            <td data-label="Customers see">${humanize(a.customer_sees)}</td>
            <td data-label="Structure">${a.structure_exists ? 'Exists' : 'Missing'}</td>
            <td data-label="Owner-approved content">${a.owner_approved_content ? 'Yes' : 'No'}</td></tr>`)}</tbody></table></div>
      </section>
      <section class="stack" aria-labelledby="history">
        <h2 id="history">Versions</h2>
        ${this.history.length ? html`<div class="table-wrap" tabindex="0" role="region" aria-label="Table, scrolls sideways on small screens"><table class="cards"><caption class="sr-only">Customer Promise versions</caption>
          <thead><tr><th scope="col">Version</th><th scope="col">Status</th><th scope="col">Effective</th><th scope="col">Started</th>
            <th scope="col">Approved</th><th scope="col">Published</th><th scope="col">Summary</th><th scope="col">Quotations</th><th scope="col">Actions</th></tr></thead>
          <tbody>${this.history.map((h) => html`<tr>
            <td data-label="Version">${h.version_no}${h.origin === 'ROLLBACK' ? html` <span class="tag">Rollback of ${h.based_on_version}</span>` : nothing}</td>
            <td data-label="Status">${humanize(h.status)}</td><td data-label="Effective">${humanize(h.effective)}</td>
            <td data-label="Started">${who(h.created_by)}, ${when(h.created_on)}</td>
            <td data-label="Approved">${h.approved_by ? `${who(h.approved_by)}, ${when(h.approved_on)}` : '—'}</td>
            <td data-label="Published">${h.published_by ? `${who(h.published_by)}, ${when(h.published_on)}` : '—'}</td>
            <td data-label="Summary">${h.change_summary ?? '—'}</td><td data-label="Quotations">${counts(h.quotations)}</td>
            <td data-label="Actions"><div class="row">
              <button class="btn small" aria-label=${`Open version ${h.version_no} from the history`} @click=${() => this.openVersion(h.id)}>Open</button>
              ${h.status === 'SUPERSEDED' && l.actions.create_draft ? html`<button class="btn small" aria-label=${`Start a rollback draft from version ${h.version_no}`}
                @click=${() => (this.confirm = { action: 'create', basedOn: h.id, title: `Roll back to version ${h.version_no}`,
                  body: `A new draft is created from version ${h.version_no}. Version ${h.version_no} itself is never reactivated: the new version goes through review, approval and publication like any other.`,
                  text: { label: 'Why roll back (optional)', required: false, name: 'change_summary' } })}>Roll back</button>` : nothing}
            </div></td></tr>`)}</tbody></table></div>` : html`<p class="muted">No versions yet.</p>`}
      </section>`;
  }

  // --- version --------------------------------------------------------------------------------------------------------
  private renderActions(v: VersionDetail): TemplateResult {
    const a = v.actions;
    const btn = (on: boolean, label: string, c: Confirm, kind = '') => (on ? html`<button class="btn ${kind}" aria-disabled=${this.busy ? 'true' : 'false'}
      @click=${() => { if (!this.busy && this.leaveOk()) this.confirm = c; }}>${label}</button>` : nothing);
    return html`<div class="row" role="group" aria-label="Version actions">
      ${btn(a.submit, 'Submit for review', { action: 'submit', title: 'Submit for review', body: `Version ${v.version_no} is frozen for review: the changed sections are reviewed one by one, and nobody who saved a section reviews it.` }, 'primary')}
      ${btn(a.approve, 'Approve version', { action: 'approve', title: `Approve version ${v.version_no}`, body: 'Every changed section has an approving review. Approving makes the version ready to publish; it does not publish it.',
        text: { label: 'Note (optional)', required: false, name: 'note' } }, 'primary')}
      ${btn(a.publish, 'Publish', { action: 'publish', title: `Publish version ${v.version_no}`, body: `Version ${v.version_no} becomes the Customer Promise from now on${this.landing?.published ? `; version ${this.landing.published.version_no} is superseded (kept, never deleted)` : ''}. Quotations already issued never change; open drafts must be revised to carry it.` }, 'primary')}
      ${btn(a.return, 'Return to draft', { action: 'return', title: 'Return to draft', body: 'The version goes back to draft so it can be changed; its review history is kept.',
        text: { label: 'Reason', required: true, name: 'reason' } })}
      ${btn(a.discard, 'Discard draft', { action: 'discard', title: `Discard draft version ${v.version_no}`, body: 'The draft is kept as discarded (never deleted) and can no longer be edited.',
        text: { label: 'Reason', required: true, name: 'reason' } }, 'danger')}
    </div>`;
  }

  private renderSectionNav(v: VersionDetail): TemplateResult {
    return html`<nav class="sections" aria-label="Sections"><ol>${v.sections.map((s) => html`<li>
      <button class="btn" aria-current=${s.code === this.section ? 'true' : 'false'} @click=${() => this.selectSection(s.code)}>
        ${s.title}${s.changed ? html`<span class="sr-only"> (changed)</span><span aria-hidden="true"> •</span>` : nothing}
        ${v.pending_reviews.includes(s.code) ? html`<span class="tag">Review</span>` : nothing}</button></li>`)}</ol></nav>`;
  }

  private renderSection(v: VersionDetail, s: SectionView): TemplateResult {
    const contacts = (v.sections.find((x) => x.code === 'CONTACTS')?.value.contacts ?? []) as unknown[];
    return html`<section class="stack" aria-labelledby="section-title">
      <h3 id="section-title" tabindex="-1">${s.title}${s.sensitive ? html` <span class="tag">Sensitive: legal or control review</span>` : nothing}</h3>
      <p class="small muted">${s.changed ? 'Changed from the published version.' : 'Same as the published version.'}
        Edited with ${s.edit_permission}; reviewed with ${s.review_permission}.
        ${s.contributors.length ? html`Saved in this version by ${s.contributors.map(who).join(', ')}.` : nothing}</p>
      ${s.review ? html`<p class="small">Review: <strong>${humanize(s.review.decision)}</strong> by ${who(s.review.by)}, ${when(s.review.on)}${s.review.comment ? ` — ${s.review.comment}` : ''}</p>` : nothing}
      ${s.can_review ? html`<div class="row" role="group" aria-label=${`Review ${s.title}`}>
          <button class="btn primary" aria-disabled=${this.busy ? 'true' : 'false'} @click=${() => !this.busy && this.approveSection(s.code)}>Approve section</button>
          <button class="btn" @click=${() => (this.confirm = { action: 'changes', section: s.code, title: `Request changes: ${s.title}`,
            body: 'The version returns to draft for the author to correct; your comment is kept in the review history.',
            text: { label: 'What needs to change', required: true, name: 'comment' } })}>Request changes</button></div>` : nothing}
      ${!s.can_edit && v.status === 'DRAFT' ? html`<p class="small muted">You can read this section; editing it needs ${s.edit_permission}.</p>` : nothing}
      <vs-promise-editor .section=${s} .vocab=${this.vocab} .context=${{ contacts }} ?editable=${s.can_edit} ?busy=${this.busy}
        .errors=${this.errors} @editor-change=${(e: CustomEvent<{ dirty: boolean }>) => (this.dirty = e.detail.dirty)}
        @editor-save=${(e: CustomEvent<{ value: Record<string, unknown> }>) => this.save(e)}></vs-promise-editor>
    </section>`;
  }

  private renderChanges(): TemplateResult {
    const c = this.changes;
    if (!c) return html`<vs-skeleton rows="4"></vs-skeleton>`;
    const groups = new Map<string, Change[]>();
    for (const x of c.changes) groups.set(x.section, [...(groups.get(x.section) ?? []), x]);
    return html`<p>${c.from ? `Version ${c.to.version_no} compared with version ${c.from.version_no} (${humanize(c.from.status)}).` : `Version ${c.to.version_no} compared with an empty pack (nothing was published before).`}</p>
      ${!c.changes.length ? html`<p>No change.</p>` : [...groups.entries()].map(([section, rows]) => html`<section class="stack" aria-labelledby=${`chg-${section}`}>
        <h3 id=${`chg-${section}`}>${this.sectionTitle(section)} (${rows.length} ${rows.length === 1 ? 'change' : 'changes'})</h3>
        <div class="table-wrap" tabindex="0" role="region" aria-label="Table, scrolls sideways on small screens"><table class="cards"><caption class="sr-only">Changes in ${this.sectionTitle(section)}</caption>
          <thead><tr><th scope="col">Change</th><th scope="col">What changed</th><th scope="col">Before</th><th scope="col">After</th></tr></thead>
          <tbody>${rows.map((x) => html`<tr><td data-label="Change"><span class="tag">${humanize(x.change)}</span></td>
            <td data-label="What changed">${x.message}</td><td data-label="Before" class="before">${shown(x.before)}</td>
            <td data-label="After" class="after">${shown(x.after)}</td></tr>`)}</tbody></table></div></section>`)}`;
  }

  private renderPreview(): TemplateResult {
    const p = this.preview;
    if (!p) return html`<vs-skeleton rows="6"></vs-skeleton>`;
    return html`<div class="preview-banner" role="note">${p.label}</div>
      <p class="small muted">Rendered by the customer proposal page itself. No quotation, customer link, acceptance or commitment is created.
        Contact chosen per quotation and each site's readiness are set by staff on the quotation, so they show as to be confirmed here.</p>
      <div class="row widths" role="group" aria-label="Preview width">${WIDTHS.map(([label, px]) => html`<button class="btn small"
        aria-pressed=${this.width === px ? 'true' : 'false'} @click=${() => (this.width = px)}>${label} ${px}px</button>`)}</div>
      <div class="frame" style=${`max-width: ${this.width}px`} data-width=${this.width}>
        <vs-promise-preview .page=${previewPage(p.information, p.content_version)}></vs-promise-preview></div>`;
  }

  private renderHistory(v: VersionDetail): TemplateResult {
    return html`<section class="stack" aria-labelledby="rev-h"><h3 id="rev-h">Review history</h3>
        ${v.reviews.length ? html`<div class="table-wrap" tabindex="0" role="region" aria-label="Table, scrolls sideways on small screens"><table class="cards"><caption class="sr-only">Section reviews</caption>
          <thead><tr><th scope="col">Round</th><th scope="col">Section</th><th scope="col">Decision</th><th scope="col">Comment</th><th scope="col">Reviewer</th><th scope="col">When</th></tr></thead>
          <tbody>${v.reviews.map((r) => html`<tr><td data-label="Round">${r.round}</td><td data-label="Section">${this.sectionTitle(r.section)}</td>
            <td data-label="Decision">${humanize(r.decision)}${r.current ? '' : ' (earlier)'}</td><td data-label="Comment">${r.comment ?? '—'}</td>
            <td data-label="Reviewer">${who(r.by)}</td><td data-label="When">${when(r.on)}</td></tr>`)}</tbody></table></div>` : html`<p class="muted">No reviews yet.</p>`}
      </section>
      ${v.events ? html`<section class="stack" aria-labelledby="ev-h"><h3 id="ev-h">Event history</h3>
        <div class="table-wrap" tabindex="0" role="region" aria-label="Table, scrolls sideways on small screens"><table class="cards"><caption class="sr-only">Events of this version</caption>
          <thead><tr><th scope="col">Event</th><th scope="col">Section</th><th scope="col">State</th><th scope="col">Reason</th><th scope="col">By</th><th scope="col">When</th></tr></thead>
          <tbody>${v.events.map((e) => html`<tr><td data-label="Event">${humanize(e.code)}</td><td data-label="Section">${e.section ? this.sectionTitle(e.section) : '—'}</td>
            <td data-label="State">${e.from || e.to ? `${humanize(e.from) || '—'} → ${humanize(e.to) || '—'}` : '—'}</td><td data-label="Reason">${e.reason ?? '—'}</td>
            <td data-label="By">${who(e.by)}</td><td data-label="When">${when(e.on)}</td></tr>`)}</tbody></table></div></section>` : nothing}`;
  }

  private renderVersion(): TemplateResult {
    const v = this.version!;
    const s = v.sections.find((x) => x.code === this.section) ?? v.sections[0];
    const tabs: [Tab, string][] = [['edit', v.status === 'DRAFT' ? 'Sections' : 'Sections and review'], ['changes', 'What changed'],
      ...(v.actions.preview ? [['preview', 'Preview as customer'] as [Tab, string]] : []), ['history', 'History']];
    return html`<div class="row"><button class="btn ghost" @click=${() => this.backToLanding()}>← Customer Promise</button></div>
      <h2 id="version-title" tabindex="-1">Version ${v.version_no} · ${humanize(v.status)}</h2>
      <dl class="meta">
        <dt>Origin</dt><dd>${humanize(v.origin)}${v.based_on_version ? ` (from version ${v.based_on_version})` : ''}</dd>
        <dt>Summary</dt><dd>${v.change_summary ?? '—'}</dd>
        <dt>Started</dt><dd>${who(v.created_by)}, ${when(v.created_on)}</dd>
        ${v.submitted_by ? html`<dt>Submitted</dt><dd>${who(v.submitted_by)}, ${when(v.submitted_on)}</dd>` : nothing}
        ${v.approved_by ? html`<dt>Approved</dt><dd>${who(v.approved_by)}, ${when(v.approved_on)}</dd>` : nothing}
        ${v.published_by ? html`<dt>Published</dt><dd>${who(v.published_by)}, ${when(v.published_on)}</dd>` : nothing}
        ${v.superseded_on ? html`<dt>Superseded</dt><dd>${when(v.superseded_on)} by version ${v.superseded_by_version}</dd>` : nothing}
        <dt>Quotations</dt><dd>${counts(v.quotations)}</dd>
      </dl>
      ${this.renderActions(v)}
      ${v.problems.length ? html`<vs-banner kind="warning"><strong>Before this version can be submitted or published:</strong>
        <ul class="plain">${v.problems.map((p) => html`<li>${this.sectionTitle(p.section)}: ${p.message}</li>`)}</ul></vs-banner>` : nothing}
      ${v.pending_reviews.length ? html`<p>Waiting for review: ${v.pending_reviews.map((c) => this.sectionTitle(c)).join(', ')}.</p>` : nothing}
      <div class="tabs" role="group" aria-label="Version views">${tabs.map(([t, label]) => html`<button class="btn small" aria-pressed=${this.tab === t ? 'true' : 'false'}
        @click=${() => this.setTab(t)}>${label}</button>`)}</div>
      <h2 class="sr-only" id="tab-title" tabindex="-1">${tabs.find(([t]) => t === this.tab)?.[1]}</h2>
      ${this.tab === 'edit' ? html`<div class="layout">${this.renderSectionNav(v)}<div>${s ? this.renderSection(v, s) : nothing}</div></div>`
        : this.tab === 'changes' ? this.renderChanges() : this.tab === 'preview' ? this.renderPreview() : this.renderHistory(v)}`;
  }

  private renderConfirm(): TemplateResult {
    const c = this.confirm;
    return html`<vs-dialog heading=${c?.title ?? ''} ?open=${!!c} @close=${() => (this.confirm = null)}>
      ${c ? html`<form id="confirm-form" class="stack" novalidate @submit=${(e: Event) => { e.preventDefault(); void this.runConfirm(e.target as HTMLFormElement); }}>
        <p>${c.body}</p>
        ${c.text ? html`<label class="field"><span class="label">${c.text.label}</span>
          <textarea name=${c.text.name} maxlength=${c.text.name === 'change_summary' ? 500 : 1000} ?required=${c.text.required}
            aria-describedby=${c.text.required ? 'confirm-hint' : nothing}></textarea>
          ${c.text.required ? html`<span class="hint" id="confirm-hint">Required: at least 5 characters.</span>` : nothing}</label>` : nothing}
      </form>` : nothing}
      <div slot="actions"><button class="btn" @click=${() => (this.confirm = null)}>Cancel</button>
        <button class="btn primary" type="submit" form="confirm-form">Confirm</button></div>
    </vs-dialog>`;
  }

  override render() {
    if (this.disabled) {
      return html`<div class="page"><h1 class="title" id="page-title" tabindex="-1">Customer Promise</h1>
        <vs-empty-state heading="The Customer Promise portal is not enabled in this environment."></vs-empty-state></div>`;
    }
    return html`<div class="page" @focus-field=${(e: CustomEvent<string>) => { if (!this.editor?.focusField(e.detail)) this.editor?.focus(); }}>
      <div class="page-head"><div><p class="eyebrow">Commercial</p><h1 class="title" id="page-title" tabindex="-1">Customer Promise</h1></div></div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${this.conflict ? html`<vs-banner kind="danger">Someone else changed this version after you opened it. Your changes were not saved and
        nothing was overwritten. <button class="btn small" @click=${() => (!this.dirty || confirm('Reload and lose your unsaved changes?')) && this.reload()}>Reload the version</button></vs-banner>` : nothing}
      <vs-error-summary .errors=${this.errors}></vs-error-summary>
      ${this.view === 'landing' ? this.renderLanding() : this.renderVersion()}
      ${this.renderConfirm()}
      <div class="sr-only" role="status" aria-live="polite">${this.announcement}</div>
    </div>`;
  }
}
customElements.define('vs-promise-page', VsPromisePage);
