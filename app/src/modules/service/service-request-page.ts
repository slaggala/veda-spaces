import { css, html, nothing, type TemplateResult } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatDate, humanize } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import { badgeStyles, CLASS_LABEL, when, who } from '../project/labels.js';
import { variantUrl } from '../site/api.js';
import { serviceApi, STATUS, type RequestDetail } from './api.js';

type Value = string | boolean | null;
interface Field { name: string; label: string; kind: 'text' | 'textarea' | 'select' | 'date' | 'checkbox'; required?: boolean; minLength?: number;
  maxLength?: number; options?: [string, string][]; hint?: string; value?: Value; classification?: string }
interface Form { title: string; intro?: string; fields: Field[]; submit: string; danger?: boolean; done: string;
  run: (body: Record<string, unknown>) => Promise<{ data: RequestDetail }> }

/** Today in India (the business calendar the server judges dates by), never the UTC date (review L3). */
const TODAY = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date());
const CUSTOMER = 'POTENTIALLY_CUSTOMER_SAFE';
const INTERNAL = 'INTERNAL_ONLY';

/**
 * /service/:id — one post-handover service request (WSV). Shows the customer's words and photos, the warranty frozen at
 * handover with the statements a decision may cite, every coverage decision with its basis and reasons, visits,
 * resolutions and notes (internal and customer-visible kept apart), and only the commands the server says are
 * possible now. The server decides every rule again; hiding a button is never the authorisation.
 */
export class VsServiceRequestPage extends SessionElement {
  static override properties = { location: { attribute: false }, request: { state: true }, problem: { state: true }, form: { state: true },
    formErrors: { state: true }, busy: { state: true }, announcement: { state: true }, conflict: { state: true }, thumbs: { state: true } };
  declare location: { params: Record<string, string> } | undefined;
  declare request: RequestDetail | null;
  declare problem: ApiProblem | null;
  declare form: Form | null;
  declare formErrors: { field: string; message: string }[];
  declare busy: boolean;
  declare announcement: string;
  declare conflict: boolean;
  /** The customer's photos as data: URLs (staff attachment route; needs attachment.read on the customer's record). */
  declare thumbs: Record<string, string | null>;

  static override styles = [...shared, pageStyles, tableStyles, badgeStyles, css`
    .cols { display: grid; grid-template-columns: 1fr; gap: var(--vs-space-5); }
    @media (min-width: 1024px) { .cols { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); } }
    .cols > div { display: flex; flex-direction: column; gap: var(--vs-space-5); min-width: 0; }
    .card { border: 1px solid var(--vs-line); border-radius: var(--vs-radius); padding: var(--vs-space-4); background: var(--vs-surface); }
    .words { white-space: pre-wrap; overflow-wrap: anywhere; }
    .actions { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .actions .btn { min-height: var(--vs-target); }
    ul.plain { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vs-space-2); }
    .note.INTERNAL { border-left: 3px solid var(--vs-muted); padding-left: var(--vs-space-2); }
    .note.CUSTOMER { border-left: 3px solid var(--vs-copper); padding-left: var(--vs-space-2); }
    dl.meta { display: grid; grid-template-columns: max-content 1fr; gap: 4px var(--vs-space-3); margin: 0; }
    dl.meta dt { color: var(--vs-muted); }
    dl.meta dd { margin: 0; overflow-wrap: anywhere; }
    .field { display: flex; flex-direction: column; gap: 4px; }
    .field select, .field input, .field textarea { min-height: var(--vs-target); }
    .check { display: flex; align-items: center; gap: var(--vs-space-2); min-height: var(--vs-target); }
    .class-tag, .hint { font-size: 13px; color: var(--vs-muted); }
    .error { color: var(--vs-danger); font-size: 14px; }
    .statement { overflow-wrap: anywhere; }
    a.back { display: inline-flex; align-items: center; min-height: var(--vs-target); }
    .thumbs { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .thumbs img { border-radius: var(--vs-radius); max-width: 96px; height: auto; }
  `];

  constructor() {
    super();
    this.request = null;
    this.problem = null;
    this.form = null;
    this.formErrors = [];
    this.busy = false;
    this.announcement = '';
    this.conflict = false;
    this.thumbs = {};
  }

  private get routeId(): string { return this.location?.params?.id ?? window.location.pathname.split('/').pop() ?? ''; }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private async load() {
    this.problem = null;
    try { this.request = (await serviceApi.get(this.routeId)).data; } catch (e) { this.problem = e as ApiProblem; }
    void this.loadThumbs();
  }

  private async loadThumbs() {
    for (const p of this.request?.photos ?? []) {
      if (p.state !== 'AVAILABLE' || p.attachment_id in this.thumbs) continue;
      const url = await variantUrl(p.attachment_id, 'thumb').catch(() => null);
      this.thumbs = { ...this.thumbs, [p.attachment_id]: url };
    }
  }

  private async focusOn(selector: string) {
    await this.updateComplete;
    (this.renderRoot.querySelector(selector) as HTMLElement | null)?.focus();
  }

  // --- form plumbing (the project page's pattern) ----------------------------------------------------------------------
  private open(form: Form) {
    this.form = form;
    this.formErrors = [];
    this.problem = null;
    this.conflict = false;
  }

  private collect(el: HTMLFormElement): Record<string, unknown> {
    const out: Record<string, unknown> = {};
    for (const f of this.form?.fields ?? []) {
      const input = el.elements.namedItem(f.name) as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | null;
      if (!input) continue;
      if (f.kind === 'checkbox') out[f.name] = (input as HTMLInputElement).checked;
      else if (input.value.trim() !== '') out[f.name] = input.value.trim();
    }
    return out;
  }

  private async summaryFocus() {
    await this.updateComplete;
    (this.renderRoot.querySelector('vs-dialog vs-error-summary') as unknown as { focusSummary?: () => void } | null)?.focusSummary?.();
  }

  private async submit(e: Event) {
    e.preventDefault();
    const form = this.form;
    if (!form || this.busy) return;
    const body = this.collect(e.target as HTMLFormElement);
    const errors = form.fields.filter((f) => f.kind !== 'checkbox').flatMap((f) => {
      const v = String(body[f.name] ?? '');
      if (f.required && !v) return [{ field: f.name, message: `${f.label}: required.` }];
      if (f.minLength && v && v.length < f.minLength) return [{ field: f.name, message: `${f.label}: at least ${f.minLength} characters.` }];
      return [];
    });
    if (errors.length) {
      this.formErrors = errors;
      await this.summaryFocus();
      return;
    }
    this.busy = true;
    this.formErrors = [];
    try {
      this.request = (await form.run(body)).data;
      this.announcement = form.done;
      this.form = null;
      await this.focusOn('#page-title');
    } catch (err) {
      const p = err as ApiProblem;
      if (p.code === 'VERSION_CONFLICT' || p.code === 'PRECONDITION_REQUIRED') {
        this.form = null;
        this.conflict = true;
        await this.focusOn('#conflict');
      } else {
        this.formErrors = p.errors.length ? p.errors.map((x) => ({ field: x.field, message: x.message ?? humanize(x.code) }))
          : [{ field: '', message: p.detail || p.title }];
        await this.summaryFocus();
      }
    } finally { this.busy = false; }
  }

  private renderField(f: Field): TemplateResult {
    const err = this.formErrors.find((x) => x.field === f.name)?.message;
    const describedBy = [f.hint ? `hint-${f.name}` : '', err ? `err-${f.name}-msg` : ''].filter(Boolean).join(' ') || nothing;
    const id = `err-${f.name}`;
    if (f.kind === 'checkbox') return html`<label class="check"><input type="checkbox" name=${f.name} id=${id} ?checked=${f.value === true}>${f.label}</label>`;
    const control = f.kind === 'textarea'
      ? html`<textarea name=${f.name} id=${id} maxlength=${f.maxLength ?? 1000} ?required=${!!f.required} aria-invalid=${err ? 'true' : 'false'}
          aria-describedby=${describedBy} .value=${String(f.value ?? '')}></textarea>`
      : f.kind === 'select'
        ? html`<select name=${f.name} id=${id} ?required=${!!f.required} aria-invalid=${err ? 'true' : 'false'} aria-describedby=${describedBy}>
            ${f.required ? nothing : html`<option value="">—</option>`}
            ${(f.options ?? []).map(([v, l]) => html`<option value=${v} ?selected=${f.value === v}>${l}</option>`)}</select>`
        : html`<input type=${f.kind === 'date' ? 'date' : 'text'} name=${f.name} id=${id} maxlength=${f.maxLength ?? 200} ?required=${!!f.required}
            aria-invalid=${err ? 'true' : 'false'} aria-describedby=${describedBy} .value=${String(f.value ?? '')}>`;
    return html`<label class="field"><span class="label">${f.label}${f.required ? ' (required)' : ''}</span>${control}
      ${f.hint ? html`<span class="hint" id=${`hint-${f.name}`}>${f.hint}</span>` : nothing}
      ${f.classification ? html`<span class="class-tag">${CLASS_LABEL[f.classification]}</span>` : nothing}
      ${err ? html`<span class="error" id=${`err-${f.name}-msg`}>${err}</span>` : nothing}</label>`;
  }

  private renderForm(): TemplateResult {
    const f = this.form;
    return html`<vs-dialog heading=${f?.title ?? ''} wide ?open=${!!f} @close=${() => (this.form = null)}
      @focus-field=${(e: CustomEvent<string>) => (this.renderRoot.querySelector(`#err-${e.detail}`) as HTMLElement | null)?.focus()}>
      ${f ? html`<form id="service-form" class="stack" novalidate @submit=${(e: Event) => this.submit(e)}>
        ${f.intro ? html`<p>${f.intro}</p>` : nothing}
        <vs-error-summary .errors=${this.formErrors}></vs-error-summary>
        ${f.fields.map((x) => this.renderField(x))}
      </form>` : nothing}
      <div slot="actions"><button class="btn" @click=${() => (this.form = null)}>Cancel</button>
        <button class="btn ${f?.danger ? 'danger' : 'primary'}" type="submit" form="service-form" ?disabled=${this.busy}>${f?.submit ?? 'Save'}</button></div>
    </vs-dialog>`;
  }

  // --- commands --------------------------------------------------------------------------------------------------------
  private act(path: string, title: string, submit: string, done: string, fields: Field[], extra: Partial<Form> = {}) {
    const r = this.request!;
    this.open({ title, submit, done, fields, ...extra, run: (b) => serviceApi.act(r, path, b) });
  }

  private statementOptions(r: RequestDetail): [string, string][] {
    const out: [string, string][] = [];
    (r.entitlement.sources ?? []).forEach((s, i) => {
      s.warranty.forEach((x, j) => out.push([`sources/${i}/warranty/${j}`, `Warranty (${s.quotation_number}): ${x}`]));
      s.service_support.forEach((x, j) => out.push([`sources/${i}/service_support/${j}`, `Service support (${s.quotation_number}): ${x}`]));
      s.warranty_exclusions.forEach((x, j) => out.push([`sources/${i}/warranty_exclusions/${j}`, `Exclusion (${s.quotation_number}): ${x.text}`]));
      if (s.manufacturer_warranty_note) out.push([`sources/${i}/manufacturer_warranty_note`, `Manufacturer note (${s.quotation_number})`]);
    });
    return out;
  }

  private assess(r: RequestDetail) {
    const classes = (r.entitlement.coverage ?? []).map((c): [string, string] => [c.code, `${c.label} (${humanize(c.status)} on the reported date)`]);
    this.act('assessments', 'Decide coverage', 'Record the decision', 'Coverage decided.', [
      { name: 'outcome', label: 'Decision', kind: 'select', required: true, options: r.vocabulary.outcomes.map((o) => [o.code, o.label]) },
      ...(classes.length ? [{ name: 'coverage_class', label: 'Coverage class (recorded terms)', kind: 'select' as const, options: classes }] : []),
      { name: 'basis_path', label: 'Statement relied on', kind: 'select', options: this.statementOptions(r),
        hint: 'Covered rests on a warranty or service-support statement, or an active class. A manufacturer note or an exclusion never makes it covered.' },
      { name: 'period_basis', label: 'Why it is within (or outside) the period', kind: 'textarea', maxLength: 1000, classification: INTERNAL,
        hint: classes.length ? undefined : 'No warranty period is recorded for this home: required when you cite a statement.' },
      { name: 'service_class', label: 'If not covered', kind: 'select', options: [['CHARGEABLE', 'Could be offered as chargeable work'], ['NOT_SERVICEABLE', 'Cannot be serviced']],
        hint: 'Chargeable work cannot start until a commercial agreement mechanism exists.' },
      { name: 'explanation', label: 'Explanation for the customer', kind: 'textarea', required: true, minLength: 10, maxLength: 1000, classification: CUSTOMER },
      { name: 'internal_reason', label: 'Internal reason', kind: 'textarea', required: true, minLength: 10, maxLength: 2000, classification: INTERNAL },
    ], { intro: `Judged as of ${formatDate(r.reported_on)}, the date the problem was reported.` });
  }

  private commands(r: RequestDetail): TemplateResult {
    const a = r.actions;
    const evidence = (r as RequestDetail & { evidence_options?: { id: string; category: string; attached_to: string; internal: boolean }[] }).evidence_options ?? [];
    const owners = (r as RequestDetail & { owner_options?: { id: string; display_name: string | null }[] }).owner_options ?? [];
    const planned = r.visits.filter((v) => v.status === 'PLANNED');
    const buttons: TemplateResult[] = [];
    const add = (show: boolean | undefined, label: string, fn: () => void, cls = '') => {
      if (show) buttons.push(html`<button class="btn ${cls}" @click=${fn}>${label}</button>`);
    };
    add(a.triage, 'Triage', () => this.act('triage', 'Triage', 'Triage', 'Triaged.', [
      { name: 'category', label: 'Kind of problem', kind: 'select', value: r.category, options: r.vocabulary.categories.map((c) => [c.code, c.label]) },
      { name: 'priority', label: 'Priority', kind: 'select', required: true, value: r.priority, options: r.vocabulary.priorities.map((p) => [p, humanize(p)]) },
      { name: 'note', label: 'Internal note', kind: 'textarea', maxLength: 2000, classification: INTERNAL }]), 'primary');
    add(a.assess, 'Decide coverage', () => this.assess(r), 'primary');
    add(a.assign, r.owner ? 'Reassign' : 'Assign', () => this.act('assign', 'Assign the owner', 'Assign', 'Assigned.', [
      { name: 'owner_user_id', label: 'Owner', kind: 'select', required: true, options: owners.map((o) => [o.id, o.display_name ?? '—']) }]));
    add(a.plan_visit, 'Plan a visit', () => this.act('visits', 'Plan a visit', 'Plan', 'Visit planned.', [
      { name: 'kind', label: 'Visit', kind: 'select', required: true, options: [['INSPECTION', 'Inspection'], ['SERVICE', 'Service']] },
      { name: 'planned_on', label: 'Date agreed with the customer', kind: 'date', required: true, value: TODAY() },
      { name: 'customer_note', label: 'Note for the customer', kind: 'textarea', maxLength: 1000, classification: CUSTOMER },
      { name: 'internal_note', label: 'Internal note', kind: 'textarea', maxLength: 2000, classification: INTERNAL }]));
    for (const v of planned) {
      add(a.record_visit, `Record visit ${v.visit_no} as done`, () => {
        const req = this.request!;
        this.open({ title: `Visit ${v.visit_no}: done`, submit: 'Record', done: 'Visit recorded.', fields: [
          { name: 'done_on', label: 'Done on', kind: 'date', required: true, value: TODAY() },
          { name: 'customer_note', label: 'Note for the customer', kind: 'textarea', maxLength: 1000, classification: CUSTOMER },
          { name: 'internal_note', label: 'What was found and done', kind: 'textarea', maxLength: 2000, classification: INTERNAL },
          { name: 'evidence', label: 'Evidence (optional)', kind: 'select', options: evidence.map((o) => [o.id, `${humanize(o.category)} · ${humanize(o.attached_to)}`]) }],
        run: (b) => serviceApi.act(req, `visits/${v.id}/done`, { ...b, evidence: b.evidence ? [{ attachment_id: b.evidence }] : [] }) });
      });
    }
    add(a.add_evidence, 'Add evidence', () => this.act('evidence', 'Add evidence', 'Add', 'Evidence added.', [
      { name: 'attachment_id', label: 'Attachment', kind: 'select', required: true,
        options: evidence.map((o) => [o.id, `${humanize(o.category)} · ${humanize(o.attached_to)}${o.internal ? ' (internal)' : ''}`]) },
      { name: 'customer_visible', label: 'Show it to the customer', kind: 'checkbox' },
      { name: 'caption', label: 'Caption for the customer (needed to show it)', kind: 'text', maxLength: 160, classification: CUSTOMER }]));
    add(a.resolve, 'Resolve', () => this.act('resolve', 'Resolve', 'Resolve', 'Resolved: waiting for verification.', [
      { name: 'summary', label: 'What was done (the customer reads this)', kind: 'textarea', required: true, minLength: 10, maxLength: 1000, classification: CUSTOMER },
      { name: 'internal_note', label: 'Internal note', kind: 'textarea', maxLength: 2000, classification: INTERNAL }]), 'primary');
    add(a.verify, 'Verify and close', () => this.act('verify', 'Verify the resolution', 'Verify and close', 'Verified and closed.', [],
      { intro: 'You confirm the resolution independently of the person who resolved it.' }), 'primary');
    add(a.request_information, 'Ask the customer', () => this.act('information-requests', 'Ask the customer', 'Ask', 'Question sent.', [
      { name: 'question', label: 'Question (the customer reads this)', kind: 'textarea', required: true, minLength: 10, maxLength: 1000, classification: CUSTOMER }]));
    add(a.add_information, 'Record the customer\'s answer', () => this.act('information', 'Record the customer\'s answer', 'Record', 'Answer recorded.', [
      { name: 'text', label: 'What the customer said', kind: 'textarea', required: true, minLength: 3, maxLength: 2000 }]));
    add(a.close, 'Close without service', () => this.act('close', 'Close without service', 'Close', 'Closed.', [
      { name: 'closure_code', label: 'Why', kind: 'select', required: true, options: r.vocabulary.closures.map((c) => [c, humanize(c)]) },
      { name: 'duplicate_of_id', label: 'Duplicate of (request id)', kind: 'text', maxLength: 32 },
      { name: 'explanation', label: 'Explanation for the customer', kind: 'textarea', required: true, minLength: 10, maxLength: 1000, classification: CUSTOMER },
      { name: 'internal_reason', label: 'Internal reason', kind: 'textarea', maxLength: 2000, classification: INTERNAL }], { danger: true }));
    add(a.withdraw, 'Withdraw for the customer', () => this.act('withdraw', 'Withdraw at the customer\'s wish', 'Withdraw', 'Withdrawn.', [
      { name: 'reason', label: 'What the customer said', kind: 'textarea', maxLength: 1000 }], { danger: true }));
    add(a.reopen, 'Reopen', () => this.act('reopen', 'Reopen', 'Reopen', 'Reopened: decide coverage again.', [
      { name: 'reason', label: 'Why', kind: 'textarea', required: true, minLength: 10, maxLength: 1000, classification: INTERNAL }]));
    return buttons.length ? html`<div class="actions">${buttons}</div>` : html`<p class="muted">Nothing to do here now.</p>`;
  }

  private async register(r: RequestDetail) {
    this.busy = true;
    try {
      await serviceApi.register(r.project_id);
      await this.load();
      this.announcement = 'Warranty registered from the handover.';
    } catch (e) { this.problem = e as ApiProblem; } finally { this.busy = false; }
  }

  private warranty(r: RequestDetail): TemplateResult {
    const e = r.entitlement;
    if (!e.registered) {
      return html`<section class="card stack" aria-labelledby="w-h"><h2 id="w-h">Warranty</h2>
        <p>The warranty of this project is not registered yet. Coverage cannot be decided until it is.</p>
        ${this.can('warranty.manage') ? html`<div><button class="btn" ?disabled=${this.busy} @click=${() => this.register(r)}>Register from the handover</button></div>` : nothing}</section>`;
    }
    return html`<section class="card stack" aria-labelledby="w-h"><h2 id="w-h">Warranty</h2>
      <dl class="meta"><dt>Handed over</dt><dd>${formatDate(e.handover_on ?? '')}</dd><dt>Status</dt><dd>${e.status_label}</dd>
        ${e.handover?.date_check ? html`<dt>Check</dt><dd>The handover date is before the handover package was prepared.</dd>` : nothing}</dl>
      ${(e.coverage ?? []).length ? html`<ul class="plain">${e.coverage!.map((c) => html`<li><strong>${c.label}</strong>: ${humanize(c.status)}${c.ends_on ? `, until ${formatDate(c.ends_on)}` : ''}</li>`)}</ul>`
        : html`<p class="small muted">No structured warranty terms are recorded (owner decision WSV-D01). Decisions cite the accepted quotation's statements.</p>`}
      ${(e.sources ?? []).map((s) => html`<div class="stack"><h3>${s.quotation_number} v${s.version_no}</h3>
        ${s.warranty.length ? html`<p class="small muted">Warranty</p><ul class="plain">${s.warranty.map((x) => html`<li class="statement">${x}</li>`)}</ul>` : nothing}
        ${s.service_support.length ? html`<p class="small muted">Service support</p><ul class="plain">${s.service_support.map((x) => html`<li class="statement">${x}</li>`)}</ul>` : nothing}
        ${s.warranty_exclusions.length ? html`<p class="small muted">Exclusions</p><ul class="plain">${s.warranty_exclusions.map((x) => html`<li class="statement">${x.text}</li>`)}</ul>` : nothing}
        ${s.manufacturer_warranty_note ? html`<p class="small muted">Manufacturer note: ${s.manufacturer_warranty_note}</p>` : nothing}</div>`)}
    </section>`;
  }

  override render() {
    const r = this.request;
    if (!r) return html`<div class="page"><vs-problem-banner .problem=${this.problem}></vs-problem-banner>${this.problem ? nothing : html`<vs-skeleton rows="8"></vs-skeleton>`}</div>`;
    const [label, tone] = STATUS[r.status] ?? [r.status, 'info'];
    return html`<div class="page">
      <p><a class="back" href="/service" @click=${(e: Event) => { e.preventDefault(); navigate('/service'); }}>Service requests</a></p>
      <div class="page-head"><div><p class="eyebrow">${r.category_label}</p><h1 class="title" id="page-title" tabindex="-1">${r.request_number}</h1>
        <p><span class="badge ${tone}">${label}</span> ${r.closure_code ? html`<span class="muted">${humanize(r.closure_code)}</span>` : nothing}
          <span class="muted">Reported ${formatDate(r.reported_on)} ${r.channel === 'PORTAL' ? 'in the portal' : 'to staff'} · owner ${r.owner?.display_name ?? 'unassigned'} · cycle ${r.cycle}</span></p></div></div>
      ${this.conflict ? html`<vs-banner kind="warning" id="conflict" tabindex="-1">Someone else changed this request. <button class="btn small" @click=${() => { this.conflict = false; void this.load(); }}>Reload</button></vs-banner>` : nothing}
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${this.commands(r)}
      <div class="cols"><div>
        <section class="card stack" aria-labelledby="c-h"><h2 id="c-h">What the customer reported</h2>
          <p class="words">${r.description}</p>
          <dl class="meta"><dt>Where</dt><dd>${r.area ?? '—'}</dd><dt>Noticed</dt><dd>${r.noticed_on ? formatDate(r.noticed_on) : '—'}</dd>
            <dt>Photos</dt><dd>${r.photos.length ? html`<div class="thumbs">${r.photos.map((p, i) => this.thumbs[p.attachment_id]
              ? html`<img src=${this.thumbs[p.attachment_id]!} alt=${`Customer photo ${i + 1}`} width="96" />`
              : html`<span class="small muted">${p.state === 'AVAILABLE' ? 'Photo (no preview: needs attachment access)' : humanize(p.state)}</span>`)}</div>` : 'None'}</dd></dl></section>
        <section class="card stack" aria-labelledby="a-h"><h2 id="a-h">Coverage decisions</h2>
          ${r.assessments.length ? html`<ul class="plain">${r.assessments.map((a) => html`<li class="stack"><strong>${a.outcome_label}</strong>
            <span class="small muted">Cycle ${a.cycle}, as of ${formatDate(a.as_of)}, by ${who(a.assessed_by)} ${when(a.assessed_on)}${a.basis_kind ? ` · basis: ${humanize(a.basis_kind)}` : ''}${a.coverage_status ? ` (${humanize(a.coverage_status)})` : ''}</span>
            <span class="note CUSTOMER">${a.explanation}</span><span class="note INTERNAL">${a.internal_reason}${a.period_basis ? ` · Period: ${a.period_basis}` : ''}</span></li>`)}</ul>`
            : html`<p class="muted">No decision yet: the request only says the customer reported a problem.</p>`}</section>
        <section class="card stack" aria-labelledby="v-h"><h2 id="v-h">Visits and resolution</h2>
          ${r.visits.length ? html`<ul class="plain">${r.visits.map((v) => html`<li>Visit ${v.visit_no}: ${humanize(v.kind)}, ${humanize(v.status)}, ${formatDate(v.planned_on)}${v.done_on ? `, done ${formatDate(v.done_on)}` : ''}
            ${v.internal_note ? html`<span class="note INTERNAL">${v.internal_note}</span>` : nothing}</li>`)}</ul>` : html`<p class="muted">No visit planned.</p>`}
          ${r.resolutions.map((x) => html`<p><strong>Resolution (cycle ${x.cycle}): ${humanize(x.outcome)}</strong><br><span class="note CUSTOMER">${x.summary}</span></p>`)}</section>
        <section class="card stack" aria-labelledby="n-h"><h2 id="n-h">Notes</h2>
          ${r.notes.length ? html`<ul class="plain">${r.notes.map((n) => html`<li class="note ${n.visibility}"><span class="small muted">${humanize(n.kind)} · ${n.by === 'CUSTOMER' ? 'the customer' : who(n.author)} · ${when(n.created_on)} · ${n.visibility === 'INTERNAL' ? 'internal' : 'customer can see'}</span><br>${n.text}</li>`)}</ul>`
            : html`<p class="muted">No notes.</p>`}</section>
      </div><div>
        ${this.warranty(r)}
        ${r.timeline ? html`<section class="card stack" aria-labelledby="t-h"><h2 id="t-h">History</h2><ul class="plain">${r.timeline.map((t) => html`<li><span class="small">${when(t.at)}</span> ${humanize(t.code)}${t.to ? ` → ${humanize(t.to)}` : ''} <span class="small muted">${t.by === 'CUSTOMER' ? 'the customer' : who(t.actor)}</span></li>`)}</ul></section>` : nothing}
      </div></div>
      ${this.renderForm()}
      <div class="sr-only" role="status" aria-live="polite">${this.announcement}</div>
    </div>`;
  }
}
customElements.define('vs-service-request-page', VsServiceRequestPage);
