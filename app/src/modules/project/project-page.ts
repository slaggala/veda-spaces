import { css, html, nothing, type TemplateResult } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatDate, formatINR, formatRelative, humanize } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import {
  projectApi, type Attention, type Blocker, type Candidate, type ChecklistItem, type CustomerReport, type GateBlocker, type HistoryRow,
  type Milestone, type ProjectDetail, type QcPoint, type ReadinessItem, type Snag, type TeamMember, type Transition, type TransitionResult,
  type Vocabulary, type WorkPackage,
} from './api.js';
import { badgeStyles, CLASS_LABEL, OUTCOME, party, SEVERITY, SNAG_ACTION, SNAG_STATUS, when, who, WORK_STATE } from './labels.js';

type Tab = 'overview' | 'timeline' | 'stage' | 'checklist' | 'work' | 'blockers' | 'milestones' | 'baseline' | 'site' | 'quality' | 'reports'
  | 'handover' | 'history';
type Value = string | boolean | null;
interface Field {
  name: string; label: string; kind: 'text' | 'textarea' | 'select' | 'date' | 'checkbox'; required?: boolean; minLength?: number;
  maxLength?: number; options?: [string, string][]; hint?: string; value?: Value; classification?: string;
}
interface Form {
  title: string; intro?: string; fields: Field[]; submit: string; danger?: boolean; done: string;
  run: (body: Record<string, unknown>) => Promise<{ data: ProjectDetail | TransitionResult }>;
}

const TABS: [Tab, string][] = [['overview', 'Overview'], ['timeline', 'Timeline'], ['stage', 'Stage and readiness'], ['checklist', 'Checklist'],
  ['work', 'Work plan'], ['blockers', 'Blockers'], ['milestones', 'Milestones'], ['baseline', 'Commercial baseline'], ['site', 'Site readiness'],
  ['quality', 'Quality and snags'], ['reports', 'Customer reports'], ['handover', 'Handover'], ['history', 'Audit and history']];
const TODAY = () => new Date().toISOString().slice(0, 10);
const REASON = { minLength: 5, hint: 'Required: at least 5 characters.' };
const opt = (codes: readonly string[]): [string, string][] => codes.map((c) => [c, humanize(c)]);
const money = (minor: number | null | undefined) => (minor == null ? '—' : formatINR(minor / 100));

/**
 * One project (PLB-11, PLB-40, PLB-41): who, where, what stage, what blocks it and what to do next first; then the
 * stages and gates, checklists, blockers, milestones, the commercial baseline, site readiness, quality and snags, the
 * handover, the timeline and the audit history. Every command goes to the server, which evaluates the gates and checks
 * the capability in this project's scope; the page only hides what the signed-in person may not do.
 */
export class VsProjectPage extends SessionElement {
  static override properties = {
    location: { attribute: false }, project: { state: true }, vocab: { state: true }, tab: { state: true }, form: { state: true },
    formErrors: { state: true }, problem: { state: true }, conflict: { state: true }, busy: { state: true }, announcement: { state: true },
    refusal: { state: true }, history: { state: true }, candidates: { state: true }, missing: { state: true },
  };
  declare location: { params: Record<string, string> } | undefined;
  declare project: ProjectDetail | null;
  declare vocab: Vocabulary | null;
  declare tab: Tab;
  declare form: Form | null;
  declare formErrors: { field: string; message: string }[];
  declare problem: ApiProblem | null;
  declare conflict: boolean;
  declare busy: boolean;
  declare announcement: string;
  /** The last refused transition request: shown with its exact blockers until the next action. */
  declare refusal: Transition | null;
  declare history: HistoryRow[] | null;
  declare candidates: Candidate[] | null;
  /** The API answered 404: the feature is off, or the project does not exist or is outside the person's scope. */
  declare missing: boolean;

  static override styles = [...shared, pageStyles, tableStyles, badgeStyles, css`
    .hero { display: grid; gap: var(--vs-space-3) var(--vs-space-5); grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); }
    .hero dt { font-size: 11px; line-height: 16px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--vs-ink-muted); }
    .hero dd { margin: 2px 0 0; font-size: 16px; line-height: 24px; overflow-wrap: anywhere; }
    dl.meta { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 4px var(--vs-space-3); margin: 0; font-size: 14px; }
    dl.meta dt { color: var(--vs-ink-muted); } dl.meta dd { margin: 0; overflow-wrap: anywhere; }
    .attention { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--vs-space-3); }
    .attention li { border: 1px solid var(--vs-line); border-left: 3px solid var(--vs-line); border-radius: var(--vs-radius-card);
      padding: var(--vs-space-3) var(--vs-space-4); background: var(--vs-surface); display: grid; gap: 4px; }
    .attention li.GATING, .attention li.ACTION { border-left-color: var(--vs-danger); }
    .attention li.SITE { border-left-color: var(--vs-warning); }
    .attention h3 { font-size: 16px; line-height: 22px; font-weight: 600; overflow-wrap: anywhere; }
    .stages { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
    .stages li { display: grid; grid-template-columns: 2.5rem minmax(0, 1fr) auto; gap: var(--vs-space-2); align-items: center; padding: 6px 8px; border-radius: 6px; }
    .stages li[aria-current='step'] { background: var(--vs-cream); font-weight: 600; }
    .actions { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .btn { white-space: normal; text-align: left; }
    .btn.small { min-height: var(--vs-target); }
    td .btn { white-space: nowrap; min-width: var(--vs-target); }
    td, th { overflow-wrap: anywhere; }
    ul.plain { margin: 0; padding-left: 18px; display: grid; gap: 4px; }
    ol.timeline { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--vs-space-2); }
    ol.timeline li { border-left: 2px solid var(--vs-line); padding: 2px 0 2px var(--vs-space-3); }
    .group { border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); padding: var(--vs-space-3) var(--vs-space-4); background: var(--vs-surface); }
    .group h3 { font-size: 16px; line-height: 22px; font-weight: 600; }
    h2:focus, h3:focus { outline: none; } h2:focus-visible { outline: 2px solid var(--vs-focus-ring); }
    .class-tag { font-size: 11px; line-height: 16px; color: var(--vs-ink-muted); }
    form.stack .field .error { font-size: 12px; color: var(--vs-danger); }
  `];

  constructor() {
    super();
    this.project = null;
    this.vocab = null;
    this.tab = 'overview';
    this.form = null;
    this.formErrors = [];
    this.problem = null;
    this.conflict = false;
    this.busy = false;
    this.announcement = '';
    this.refusal = null;
    this.history = null;
    this.candidates = null;
    this.missing = false;
  }

  private get routeId(): string { return this.location?.params?.id ?? window.location.pathname.split('/').pop() ?? ''; }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private async load() {
    this.problem = null;
    try {
      const [p, v] = await Promise.all([projectApi.get(this.routeId), this.vocab ? null : projectApi.vocabulary()]);
      this.project = p.data;
      if (v) this.vocab = v.data;
      this.conflict = false;
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404) this.missing = true;
      else this.problem = p;
    }
  }

  private stageLabel(code: string | null | undefined): string {
    if (!code) return '—';
    return this.project?.stages.find((s) => s.code === code)?.label ?? this.vocab?.stages.find((s) => s.code === code)?.label ?? humanize(code);
  }

  private async focusOn(selector: string) {
    await this.updateComplete;
    (this.renderRoot.querySelector(selector) as HTMLElement | null)?.focus();
  }

  private async setTab(tab: Tab) {
    this.tab = tab;
    if (tab === 'history' && this.history === null && this.project?.actions.view_audit) {
      try { this.history = (await projectApi.history(this.project)).data; } catch (e) { this.problem = e as ApiProblem; }
    }
  }

  // --- forms ----------------------------------------------------------------------------------------------------------
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
      await this.focusOn('vs-dialog vs-error-summary');
      (this.renderRoot.querySelector('vs-dialog vs-error-summary') as unknown as { focusSummary?: () => void } | null)?.focusSummary?.();
      return;
    }
    this.busy = true;
    this.formErrors = [];
    try {
      const r = await form.run(body);
      const result = r.data as ProjectDetail | TransitionResult;
      if ('transition' in result) {
        this.project = result.project;
        this.refusal = result.outcome === 'REFUSED' ? result.transition : null;
        this.announcement = result.outcome === 'REFUSED' ? `Refused: ${result.transition.blockers.length} thing(s) to clear first.`
          : result.outcome === 'AWAITING_APPROVAL' ? 'Requested: waiting for an independent approval.' : form.done;
      } else {
        this.project = result;
        this.refusal = null;
        this.announcement = form.done;
      }
      this.form = null;
      this.history = null;
      await this.focusOn(this.refusal ? '#refusal-h' : '#page-title');
    } catch (err) {
      const p = err as ApiProblem;
      if (p.code === 'VERSION_CONFLICT' || p.code === 'PRECONDITION_REQUIRED') {
        this.form = null;
        this.conflict = true;
        await this.focusOn('#conflict');
      } else if (p.errors.length) {
        this.formErrors = p.errors.map((x) => ({ field: x.field, message: x.message ?? humanize(x.code) }));
        await this.updateComplete;
        (this.renderRoot.querySelector('vs-dialog vs-error-summary') as unknown as { focusSummary?: () => void } | null)?.focusSummary?.();
      } else {
        const blockers = p.ext<GateBlocker[]>('blockers');
        this.formErrors = [{ field: '', message: p.detail || p.title }, ...(blockers ?? []).map((b) => ({ field: '', message: b.message }))];
        await this.updateComplete;
        (this.renderRoot.querySelector('vs-dialog vs-error-summary') as unknown as { focusSummary?: () => void } | null)?.focusSummary?.();
      }
    } finally { this.busy = false; }
  }

  private fieldError(name: string) {
    return this.formErrors.find((e) => e.field === name)?.message;
  }

  private renderField(f: Field): TemplateResult {
    const err = this.fieldError(f.name);
    const describedBy = [f.hint ? `hint-${f.name}` : '', err ? `err-${f.name}-msg` : ''].filter(Boolean).join(' ') || nothing;
    const common = { id: `err-${f.name}`, invalid: err ? 'true' : 'false' };
    if (f.kind === 'checkbox') {
      return html`<label class="check"><input type="checkbox" name=${f.name} id=${common.id} ?checked=${f.value === true}>${f.label}</label>`;
    }
    const control = f.kind === 'textarea'
      ? html`<textarea name=${f.name} id=${common.id} maxlength=${f.maxLength ?? 1000} ?required=${!!f.required} aria-invalid=${common.invalid}
          aria-describedby=${describedBy} .value=${String(f.value ?? '')}></textarea>`
      : f.kind === 'select'
        ? html`<select name=${f.name} id=${common.id} ?required=${!!f.required} aria-invalid=${common.invalid} aria-describedby=${describedBy}>
            ${f.required ? nothing : html`<option value="">—</option>`}
            ${(f.options ?? []).map(([v, l]) => html`<option value=${v} ?selected=${f.value === v}>${l}</option>`)}</select>`
        : html`<input type=${f.kind === 'date' ? 'date' : 'text'} name=${f.name} id=${common.id} maxlength=${f.maxLength ?? 200}
            ?required=${!!f.required} aria-invalid=${common.invalid} aria-describedby=${describedBy} .value=${String(f.value ?? '')}>`;
    return html`<label class="field"><span class="label">${f.label}${f.required ? ' (required)' : ''}</span>${control}
      ${f.hint ? html`<span class="hint" id=${`hint-${f.name}`}>${f.hint}</span>` : nothing}
      ${f.classification ? html`<span class="class-tag">${CLASS_LABEL[f.classification]}</span>` : nothing}
      ${err ? html`<span class="error" id=${`err-${f.name}-msg`}>${err}</span>` : nothing}</label>`;
  }

  private renderForm(): TemplateResult {
    const f = this.form;
    return html`<vs-dialog heading=${f?.title ?? ''} wide ?open=${!!f} @close=${() => (this.form = null)}
      @focus-field=${(e: CustomEvent<string>) => (this.renderRoot.querySelector(`#err-${e.detail}`) as HTMLElement | null)?.focus()}>
      ${f ? html`<form id="project-form" class="stack" novalidate @submit=${(e: Event) => this.submit(e)}>
        ${f.intro ? html`<p>${f.intro}</p>` : nothing}
        <vs-error-summary .errors=${this.formErrors}></vs-error-summary>
        ${f.fields.map((x) => this.renderField(x))}
      </form>` : nothing}
      <div slot="actions"><button class="btn" @click=${() => (this.form = null)}>Cancel</button>
        <button class="btn ${f?.danger ? 'danger' : 'primary'}" type="submit" form="project-form" ?disabled=${this.busy}>${f?.submit ?? 'Save'}</button></div>
    </vs-dialog>`;
  }

  // --- commands -------------------------------------------------------------------------------------------------------
  private requestMove(p: ProjectDetail) {
    const ev = p.readiness;
    const to = ev?.to;
    if (!to) return;
    this.open({ title: `Request the move to ${this.stageLabel(to)}`, submit: 'Request the move', done: `Moved to ${this.stageLabel(to)}.`,
      intro: `The system checks every gate now. If something is not satisfied the request is recorded as refused, with what is missing.${ev?.independent_approval ? ' This move needs an independent approval.' : ''}`,
      fields: [{ name: 'reason', label: 'Note for the record (optional)', kind: 'textarea' }],
      run: (b) => projectApi.transition(p, { to_stage: to, ...b }) });
  }

  private handover(p: ProjectDetail) {
    this.open({ title: 'Complete the handover', submit: 'Complete the handover', done: 'Handed over.',
      intro: 'The handover gates are checked again with this evidence. Once handed over, the project is closed.',
      fields: [
        { name: 'handover_on', label: 'Handover date', kind: 'date', required: true, value: new Date().toISOString().slice(0, 10) },
        { name: 'acknowledgement_reference', label: 'Customer acknowledgement reference', kind: 'text', maxLength: 200,
          hint: p.handover_packages.some((x) => x.status === 'PREPARED' && x.acknowledged_on) ? 'Not needed: the customer acknowledged the current handover package in the portal.'
            : 'For example the number of the signed handover sheet.' },
        { name: 'evidence_attachment_id', label: 'Handover evidence', kind: 'select', hint: 'A scanned photo already attached to this property.',
          options: p.evidence_options.map((o) => [o.id, `${humanize(o.category)} · ${humanize(o.attached_to)} · ${o.uploaded_on ? formatRelative(o.uploaded_on) : ''}`]) },
        { name: 'observations', label: 'Non-blocking observations', kind: 'textarea', maxLength: 2000, classification: 'INTERNAL_ONLY' },
      ],
      run: (b) => projectApi.handover(p, b) });
  }

  private decide(p: ProjectDetail, t: Transition, action: 'approve' | 'reject' | 'withdraw') {
    const words = { approve: ['Approve the move', 'Approved.'], reject: ['Reject the move', 'Rejected.'], withdraw: ['Withdraw the request', 'Withdrawn.'] }[action];
    this.open({ title: `${words[0]} to ${this.stageLabel(t.to_stage)}`, submit: words[0], done: words[1], danger: action !== 'approve',
      intro: action === 'approve' ? 'Every gate is evaluated again before the move.' : undefined,
      fields: [{ name: 'reason', label: action === 'approve' ? 'Note (optional)' : 'Reason', kind: 'textarea', ...(action === 'approve' ? {} : { required: true, ...REASON }) }],
      run: (b) => projectApi.decide(p, t, action, b) });
  }

  private async assign(p: ProjectDetail) {
    if (!this.candidates) {
      try { this.candidates = (await projectApi.candidates(p)).data; } catch (e) { this.problem = e as ApiProblem; return; }
    }
    const people = this.candidates ?? [];
    this.open({ title: 'Assign an owner or team member', submit: 'Assign', done: 'Assigned.',
      intro: 'Each ownership responsibility has one owner; assigning a new owner ends the previous assignment and needs a reason. Joining a team gives no extra capability.',
      fields: [
        { name: 'responsibility', label: 'Responsibility', kind: 'select', required: true, options: opt(this.vocab?.responsibilities ?? []) },
        { name: 'user_id', label: 'Person', kind: 'select', required: true,
          options: people.map((c) => [c.id, `${c.display_name ?? 'Unknown'} (can hold: ${c.responsibilities.map(humanize).join(', ')})`]) },
        { name: 'reason', label: 'Reason (when replacing an owner)', kind: 'textarea', maxLength: 500 },
      ],
      run: (b) => projectApi.assign(p, b) });
  }

  private removeMember(p: ProjectDetail, m: TeamMember) {
    this.open({ title: `End ${who(m.user)}'s ${humanize(m.responsibility).toLowerCase()} assignment`, submit: 'End the assignment', danger: true,
      done: 'Assignment ended.', fields: [{ name: 'reason', label: 'Reason', kind: 'textarea', required: true, maxLength: 500, ...REASON }],
      run: (b) => projectApi.removeMember(p, m, b) });
  }

  private completeItem(p: ProjectDetail, i: ChecklistItem, na: boolean) {
    this.open({ title: na ? `Mark not applicable: ${i.label}` : `Complete: ${i.label}`, submit: na ? 'Mark not applicable' : 'Complete', done: 'Checklist updated.',
      intro: na && i.required ? 'This item is required: marking it not applicable needs its own permission and a reason.' : undefined,
      fields: [
        ...(na ? [{ name: 'not_applicable_reason', label: 'Why it does not apply', kind: 'textarea' as const, required: true, ...REASON }] : []),
        { name: 'note', label: 'Note', kind: 'textarea', classification: 'INTERNAL_ONLY' },
        ...this.evidenceFields(p),
      ],
      run: (b) => projectApi.completeItem(p, i, { state: na ? 'NOT_APPLICABLE' : 'DONE', ...b }) });
  }

  private evidenceFields(p: ProjectDetail): Field[] {
    return [
      { name: 'evidence_attachment_id', label: 'Evidence (optional)', kind: 'select', hint: 'A scanned photo already attached to this property.',
        options: p.evidence_options.map((o) => [o.id, `${humanize(o.category)} · ${humanize(o.attached_to)} · ${o.uploaded_on ? formatRelative(o.uploaded_on) : ''}`]) },
      { name: 'evidence_reference', label: 'Evidence reference (optional)', kind: 'text', maxLength: 200, classification: 'INTERNAL_ONLY' },
    ];
  }

  private reopenItem(p: ProjectDetail, i: ChecklistItem) {
    this.open({ title: `Reopen: ${i.label}`, submit: 'Reopen', danger: true, done: 'Checklist item reopened.',
      fields: [{ name: 'reason', label: 'Reason', kind: 'textarea', required: true, ...REASON }], run: (b) => projectApi.reopenItem(p, i, b) });
  }

  private raiseBlocker(p: ProjectDetail) {
    const v = this.vocab;
    this.open({ title: 'Raise a blocker or an issue', submit: 'Raise', done: 'Blocker raised.',
      intro: 'A gating blocker stops its stage and every later one until resolved; an informational issue never stops progress.',
      fields: [
        { name: 'impact', label: 'Impact', kind: 'select', required: true, options: [['GATING', 'Gating: stops progress'], ['INFORMATIONAL', 'For information only']] },
        { name: 'blocks_stage_code', label: 'Stops (gating only)', kind: 'select', options: p.stages.filter((s) => !s.terminal).map((s) => [s.code, s.label]) },
        { name: 'category', label: 'Category', kind: 'select', required: true, options: opt(v?.blocker_categories ?? []) },
        { name: 'title', label: 'Title', kind: 'text', required: true, minLength: 3, maxLength: 160, classification: 'INTERNAL_ONLY' },
        { name: 'responsible_party', label: 'Who needs to act', kind: 'select', required: true, options: (v?.responsible_parties ?? []).map((c) => [c, party(c)]) },
        { name: 'customer_action', label: 'What the customer needs to do (when the customer acts)', kind: 'textarea', maxLength: 300,
          classification: 'CUSTOMER_ACTION', hint: 'Customer-safe words: it may be shown to the customer in a future portal.' },
        { name: 'customer_summary', label: 'What the customer is told while this pauses their work (optional)', kind: 'textarea', maxLength: 300,
          classification: 'POTENTIALLY_CUSTOMER_SAFE', hint: 'Shown in the customer portal only when written. Never internal detail or blame.' },
        { name: 'related_work_package_id', label: 'Work it holds up', kind: 'select', options: this.workOptions(p) },
        { name: 'description', label: 'Details', kind: 'textarea', maxLength: 2000, classification: 'INTERNAL_ONLY' },
        { name: 'assigned_to', label: 'Assigned to', kind: 'select', options: p.team.filter((m) => m.active && m.user).map((m) => [m.user!.id, `${who(m.user)} (${humanize(m.responsibility)})`]) },
        { name: 'target_date', label: 'Target resolution date', kind: 'date' },
      ],
      run: (b) => projectApi.raiseBlocker(p, b) });
  }

  private updateBlocker(p: ProjectDetail, b: Blocker) {
    this.open({ title: `Update: ${b.title}`, submit: 'Save', done: 'Blocker updated.',
      fields: [
        { name: 'status', label: 'Status', kind: 'select', required: true, value: b.status,
          options: opt(['OPEN', 'IN_PROGRESS', 'WAITING_CUSTOMER', 'WAITING_VEDA']) },
        { name: 'responsible_party', label: 'Who needs to act', kind: 'select', required: true, value: b.responsible_party,
          options: (this.vocab?.responsible_parties ?? []).map((c) => [c, party(c)]) },
        { name: 'customer_action', label: 'What the customer needs to do', kind: 'textarea', maxLength: 300, value: b.customer_action, classification: 'CUSTOMER_ACTION' },
        { name: 'customer_summary', label: 'What the customer is told while this pauses their work', kind: 'textarea', maxLength: 300,
          value: b.customer_summary, classification: 'POTENTIALLY_CUSTOMER_SAFE' },
        { name: 'assigned_to', label: 'Assigned to', kind: 'select', value: b.assigned_to?.id ?? null,
          options: p.team.filter((m) => m.active && m.user).map((m) => [m.user!.id, `${who(m.user)} (${humanize(m.responsibility)})`]) },
        { name: 'target_date', label: 'Target resolution date', kind: 'date', value: b.target_date },
      ],
      run: (body) => projectApi.updateBlocker(p, b, body) });
  }

  private closeBlocker(p: ProjectDetail, b: Blocker, action: 'resolve' | 'cancel') {
    this.open({ title: `${action === 'resolve' ? 'Resolve' : 'Cancel'}: ${b.title}`, submit: action === 'resolve' ? 'Resolve' : 'Cancel the blocker',
      danger: action === 'cancel', done: action === 'resolve' ? 'Blocker resolved.' : 'Blocker cancelled.',
      fields: [{ name: 'resolution', label: action === 'resolve' ? 'How it was resolved' : 'Why it is cancelled', kind: 'textarea', required: true, ...REASON }],
      run: (body) => projectApi.closeBlocker(p, b, action, body) });
  }

  private addMilestone(p: ProjectDetail) {
    this.open({ title: 'Add a milestone', submit: 'Add', done: 'Milestone added.',
      intro: `A planned date is an internal plan, never a commitment to the customer.${p.actions.record_promised_date ? ' Record a customer-promised date only if it was already promised.' : ' A customer-promised date is a customer commitment: recording one needs owner decision PLB-OD-13.'}`,
      fields: [
        { name: 'milestone_code', label: 'Type', kind: 'select', required: true, options: opt(this.vocab?.milestone_types ?? []) },
        { name: 'label', label: 'Label (internal)', kind: 'text', required: true, maxLength: 120 },
        { name: 'stage_code', label: 'Stage it belongs to', kind: 'select', required: true, value: p.stage.code,
          options: p.stages.filter((s) => !s.terminal && s.status !== 'COMPLETED').map((s) => [s.code, s.label]) },
        { name: 'planned_date', label: 'Planned date (internal)', kind: 'date' },
        ...(p.actions.record_promised_date ? [{ name: 'customer_promised_date', label: 'Customer-promised date (only if already promised)', kind: 'date' as const }] : []),
        { name: 'customer_label', label: 'Customer-safe label (optional)', kind: 'text', maxLength: 120, classification: 'POTENTIALLY_CUSTOMER_SAFE' },
        { name: 'owner_responsibility', label: 'Responsibility', kind: 'select', options: opt(this.vocab?.responsibilities ?? []) },
        { name: 'depends_on_milestone_id', label: 'Depends on', kind: 'select', options: p.milestones.map((m) => [m.id, m.label]) },
      ],
      run: (b) => projectApi.addMilestone(p, b) });
  }

  private updateMilestone(p: ProjectDetail, m: Milestone) {
    this.open({ title: `Plan or update: ${m.label}`, submit: 'Save', done: 'Milestone updated.',
      fields: [
        { name: 'status', label: 'Status', kind: 'select', required: true, value: m.status,
          options: opt(['NOT_STARTED', 'PLANNED', 'IN_PROGRESS', 'BLOCKED', 'CANCELLED', 'NOT_APPLICABLE']) },
        { name: 'status_reason', label: 'Reason (cancelled or not applicable)', kind: 'textarea', maxLength: 500 },
        { name: 'planned_date', label: 'Planned date (internal)', kind: 'date', value: m.planned_date },
        ...(p.actions.record_promised_date ? [{ name: 'customer_promised_date', label: 'Customer-promised date (only if already promised)', kind: 'date' as const, value: m.customer_promised_date }] : []),
      ],
      run: (b) => projectApi.updateMilestone(p, m, b) });
  }

  private completeMilestone(p: ProjectDetail, m: Milestone) {
    this.open({ title: `Complete: ${m.label}`, submit: 'Complete', done: 'Milestone completed.',
      intro: 'Completion is explicit and dated; it is never inferred from the calendar.',
      fields: [{ name: 'actual_date', label: 'Actual date', kind: 'date', required: true, value: new Date().toISOString().slice(0, 10) }, ...this.evidenceFields(p)],
      run: (b) => projectApi.completeMilestone(p, m, b) });
  }

  private updateReadiness(p: ProjectDetail, r: ReadinessItem) {
    this.open({ title: `Site readiness: ${r.label ?? humanize(r.category)}`, submit: 'Save', done: 'Site readiness updated.',
      intro: 'This records what is true on this site today. It never changes the accepted quotation or the Customer Promise.',
      fields: [
        { name: 'status', label: 'Status', kind: 'select', required: true, value: r.status, options: opt(this.vocab?.readiness_statuses ?? []) },
        { name: 'responsible_party', label: 'Who needs to act', kind: 'select', value: r.responsible_party,
          options: (this.vocab?.responsible_parties ?? []).map((c) => [c, party(c)]) },
        { name: 'action', label: 'Action needed', kind: 'textarea', maxLength: 500, value: r.action, classification: 'INTERNAL_ONLY' },
        { name: 'customer_action', label: 'What the customer needs to do', kind: 'textarea', maxLength: 300, value: r.customer_action,
          classification: 'CUSTOMER_ACTION', hint: 'Customer-safe words: it may be shown to the customer in a future portal.' },
        { name: 'due_date', label: 'Due date', kind: 'date', value: r.due_date },
        { name: 'note', label: 'Note', kind: 'textarea', value: r.note, classification: 'INTERNAL_ONLY' },
        ...this.evidenceFields(p),
      ],
      run: (b) => projectApi.updateReadiness(p, r, b) });
  }

  private addReadiness(p: ProjectDetail) {
    this.open({ title: 'Add a site-readiness item', submit: 'Add', done: 'Site-readiness item added.',
      intro: 'For something this site needs that the accepted quotation did not list.',
      fields: [
        { name: 'kind', label: 'Kind', kind: 'select', required: true, options: [['READINESS', 'Site readiness'], ['RESPONSIBILITY', 'Customer responsibility']] },
        { name: 'category', label: 'Category', kind: 'select', required: true, options: opt(this.vocab?.readiness_categories ?? []) },
        { name: 'label', label: 'What it is', kind: 'text', required: true, minLength: 3, maxLength: 160 },
      ],
      run: (b) => projectApi.addReadiness(p, b) });
  }

  private recordQc(p: ProjectDetail, category?: string, recheckOf?: string, point?: QcPoint) {
    const scoped = !!recheckOf || !!point;  // a recheck keeps its chain's scope; a planned check fixes its own
    this.open({ title: recheckOf ? `Recheck: ${humanize(category)}` : point ? `Result of QC-${point.point_no}: ${point.label}` : 'Record a quality-check result',
      submit: 'Record', done: 'Quality check recorded.',
      intro: recheckOf ? 'A recheck records a result. After a failure it is recorded once the remediation snags are verified, by someone who did not fix them.'
        : point?.evidence_required ? 'This planned check needs evidence of a pass.' : undefined,
      fields: [
        { name: 'category', label: 'Category', kind: 'select', required: true, value: category ?? point?.category ?? null, options: opt(this.vocab?.qc_categories ?? []) },
        { name: 'result', label: 'Result', kind: 'select', required: true,
          options: opt((this.vocab?.qc_results ?? []).filter((r) => !(recheckOf && r === 'TO_BE_CONFIRMED') && !(point && r === 'NOT_APPLICABLE'))) },
        { name: 'observation', label: 'Observation (required for a failure)', kind: 'textarea', classification: 'INTERNAL_ONLY',
          hint: p.actions.qc_required_not_applicable ? 'Not applicable on a required category needs a reason here.'
            : 'Not applicable on a required category needs owner decision PLB-OD-08.' },
        ...(scoped ? [] : [{ name: 'space_id', label: 'Space', kind: 'select' as const, options: p.spaces.map((x) => [x.id, x.label] as [string, string]) },
          { name: 'work_package_id', label: 'Work checked (completed work only)', kind: 'select' as const,
            options: this.workOptions(p, (w) => w.status === 'COMPLETED') }]),
        ...this.evidenceFields(p),
        ...(recheckOf ? [{ name: 'recheck_of_id', label: 'Recheck of', kind: 'select' as const, required: true, value: recheckOf, options: [[recheckOf, 'The latest result of this check']] as [string, string][] }] : []),
        ...(point ? [{ name: 'qc_point_id', label: 'Planned check', kind: 'select' as const, required: true, value: point.id, options: [[point.id, `QC-${point.point_no}`]] as [string, string][] }] : []),
      ],
      run: (b) => projectApi.recordQc(p, b) });
  }

  private addQcPoint(p: ProjectDetail) {
    this.open({ title: 'Plan a quality check', submit: 'Add to the QC plan', done: 'Quality check planned.',
      intro: 'A planned check is satisfied only by a pass (with evidence when required). If it no longer applies, withdraw it before any result.',
      fields: [
        { name: 'category', label: 'Category', kind: 'select', required: true, options: opt(this.vocab?.qc_categories ?? []) },
        { name: 'label', label: 'What is checked', kind: 'text', required: true, minLength: 3, maxLength: 160, classification: 'INTERNAL_ONLY' },
        { name: 'space_id', label: 'Space', kind: 'select', options: p.spaces.map((x) => [x.id, x.label]) },
        { name: 'work_package_id', label: 'Work it checks', kind: 'select', options: this.workOptions(p) },
        { name: 'evidence_required', label: 'A pass needs evidence (a scanned photo)', kind: 'checkbox', value: false },
      ],
      run: (b) => projectApi.addQcPoint(p, b) });
  }

  private withdrawQcPoint(p: ProjectDetail, q: QcPoint) {
    this.open({ title: `Withdraw QC-${q.point_no}: ${q.label}`, submit: 'Withdraw', danger: true, done: 'Planned check withdrawn.',
      fields: [{ name: 'reason', label: 'Why it no longer applies', kind: 'textarea', required: true, ...REASON }],
      run: (b) => projectApi.withdrawQcPoint(p, q, b) });
  }

  private raiseSnag(p: ProjectDetail, qcCheckId?: string) {
    this.open({ title: 'Raise a snag', submit: 'Raise', done: 'Snag raised.',
      fields: [
        { name: 'category', label: 'Category', kind: 'select', required: true, options: opt(this.vocab?.snag_categories ?? []) },
        { name: 'customer_title', label: 'Title (customer-safe words)', kind: 'text', required: true, minLength: 3, maxLength: 160,
          classification: 'POTENTIALLY_CUSTOMER_SAFE' },
        { name: 'description', label: 'Details', kind: 'textarea', maxLength: 2000, classification: 'INTERNAL_ONLY' },
        { name: 'space_id', label: 'Space', kind: 'select', options: p.spaces.map((x) => [x.id, x.label]) },
        { name: 'work_package_id', label: 'Work it concerns', kind: 'select', options: this.workOptions(p) },
        { name: 'item_reference', label: 'Item or unit (optional)', kind: 'text', maxLength: 200 },
        { name: 'is_blocking', label: 'Blocks the handover until resolved', kind: 'checkbox', value: true },
        { name: 'customer_visible', label: 'Show it to the customer in the portal (title only)', kind: 'checkbox', value: false },
        { name: 'priority', label: 'Priority', kind: 'select', required: true, value: 'NORMAL', options: opt(this.vocab?.snag_priorities ?? ['HIGH', 'NORMAL', 'LOW']) },
        { name: 'owner_user_id', label: 'Owner (the person fixing it)', kind: 'select', options: p.team.filter((m) => m.active && m.user).map((m) => [m.user!.id, who(m.user)]) },
        { name: 'responsible_party', label: 'Who needs to act', kind: 'select', value: 'VEDA', options: (this.vocab?.responsible_parties ?? []).map((c) => [c, party(c)]) },
        { name: 'target_date', label: 'Target date', kind: 'date' },
        ...(qcCheckId ? [{ name: 'qc_check_id', label: 'From quality check', kind: 'select' as const, required: true, value: qcCheckId, options: [[qcCheckId, 'The failed check']] as [string, string][] }] : []),
        ...this.evidenceFields(p),
      ],
      run: (b) => projectApi.raiseSnag(p, b) });
  }

  private assignSnag(p: ProjectDetail, sn: Snag) {
    this.open({ title: `Snag ${sn.snag_no}: assign`, submit: 'Assign', done: `Snag ${sn.snag_no} assigned.`,
      fields: [{ name: 'owner_user_id', label: 'Owner (the person fixing it)', kind: 'select', required: true, value: sn.owner?.id ?? null,
        options: p.team.filter((m) => m.active && m.user).map((m) => [m.user!.id, who(m.user)]) }],
      run: (b) => projectApi.updateSnag(p, sn, b) });
  }

  private reclassify(p: ProjectDetail, s: Snag) {
    const to = !s.is_blocking;
    this.open({ title: `Snag ${s.snag_no}: ${to ? 'make it block the handover' : 'stop it blocking the handover'}`, submit: 'Change', done: 'Snag reclassified.',
      intro: 'This changes handover readiness. It is recorded with your reason, the previous and the new classification.',
      fields: [{ name: 'reason', label: 'Reason', kind: 'textarea', required: true, maxLength: 500, ...REASON }],
      run: (b) => projectApi.reclassifySnag(p, s, { is_blocking: to, ...b }) });
  }

  private snagStatus(p: ProjectDetail, sn: Snag, status: string) {
    const fix = status === 'READY_FOR_RECHECK';
    const verdict = sn.status === 'READY_FOR_RECHECK' && (status === 'RESOLVED' || status === 'IN_PROGRESS');
    const withoutFix = status === 'CLOSED' && sn.status !== 'RESOLVED';
    const title = verdict && status === 'IN_PROGRESS' ? 'Recheck failed: back to fixing' : withoutFix ? 'Close without a fix' : SNAG_ACTION[status] ?? humanize(status);
    this.open({ title: `Snag ${sn.snag_no}: ${title}`, submit: title, done: `Snag ${sn.snag_no}: ${(SNAG_STATUS[status] ?? humanize(status)).toLowerCase()}.`,
      intro: verdict ? 'Verification is independent: you cannot verify a fix you made, or a snag you own.'
        : withoutFix ? 'Only for a snag that is a duplicate, not a defect, or raised in error. It stays in the history.' : undefined,
      fields: [
        ...(withoutFix ? [{ name: 'closure_code', label: 'Why', kind: 'select' as const, required: true,
          options: [['DUPLICATE', 'Duplicate'], ['NOT_A_DEFECT', 'Not a defect'], ['RAISED_IN_ERROR', 'Raised in error']] as [string, string][] }] : []),
        { name: 'note', label: fix ? 'What was fixed' : verdict ? 'What the recheck found' : 'Note', kind: 'textarea',
          ...(fix || verdict || withoutFix ? { required: true, ...REASON } : {}) },
        ...(fix ? [this.evidenceFields(p)[0]] : []),
      ],
      run: (b) => projectApi.snagStatus(p, sn, { status, ...b }) });
  }

  /** Who may take a snag to ``status`` (the server checks again; this only hides what the person cannot do). */
  private snagMoves(p: ProjectDetail, sn: Snag): string[] {
    const a = p.actions;
    const me = this.me?.id;
    const conflicted = me && (sn.owner?.id === me || sn.fixed_by?.id === me);
    return sn.allowed_next.filter((st) => {
      const verifying = (sn.status === 'READY_FOR_RECHECK' && (st === 'RESOLVED' || st === 'IN_PROGRESS')) || (st === 'CLOSED' && sn.status !== 'RESOLVED');
      return verifying ? a.verify_snag && !conflicted : a.manage_snag;
    });
  }

  // --- work packages --------------------------------------------------------------------------------------------------
  private workOptions(p: ProjectDetail, keep: (w: WorkPackage) => boolean = (w) => w.status !== 'CANCELLED'): [string, string][] {
    return p.work_packages.filter(keep).map((w) => [w.id, `WP-${w.package_no}: ${w.title}`]);
  }

  private addWork(p: ProjectDetail) {
    this.open({ title: 'Add work to the plan', submit: 'Add', done: 'Work added.',
      intro: 'Planned dates are an internal plan, never a promise to the customer; leave them empty if they are not known (the work is unscheduled). Work moves only by start and complete.',
      fields: [
        { name: 'title', label: 'Work (internal title)', kind: 'text', required: true, minLength: 3, maxLength: 160, classification: 'INTERNAL_ONLY' },
        { name: 'stage_code', label: 'Stage it belongs to', kind: 'select', required: true, value: p.stage.code,
          options: p.stages.filter((x) => !x.terminal && x.status !== 'COMPLETED').map((x) => [x.code, x.label]) },
        { name: 'space_id', label: 'Space', kind: 'select', options: p.spaces.map((x) => [x.id, x.label]) },
        { name: 'customer_label', label: 'Customer label (customer-safe words)', kind: 'text', maxLength: 120, classification: 'POTENTIALLY_CUSTOMER_SAFE' },
        { name: 'customer_visible', label: 'Show this work in the customer portal (needs a customer label)', kind: 'checkbox', value: false },
        { name: 'owner_user_id', label: 'Owner', kind: 'select', options: p.team.filter((m) => m.active && m.user).map((m) => [m.user!.id, who(m.user)]) },
        { name: 'depends_on_id', label: 'Starts after', kind: 'select', options: this.workOptions(p) },
        { name: 'planned_start', label: 'Planned start (internal)', kind: 'date' },
        { name: 'planned_finish', label: 'Planned finish (internal)', kind: 'date' },
        { name: 'description', label: 'Details', kind: 'textarea', maxLength: 2000, classification: 'INTERNAL_ONLY' },
      ],
      run: (b) => projectApi.addWork(p, b) });
  }

  private planWork(p: ProjectDetail, w: WorkPackage) {
    this.open({ title: `Plan WP-${w.package_no}: ${w.title}`, submit: 'Save', done: 'Work updated.',
      intro: 'Changing a planned date that was already set is a replan: say why. The previous dates stay on the timeline.',
      fields: [
        { name: 'customer_label', label: 'Customer label', kind: 'text', maxLength: 120, value: w.customer_label, classification: 'POTENTIALLY_CUSTOMER_SAFE' },
        { name: 'customer_visible', label: 'Show this work in the customer portal', kind: 'checkbox', value: w.customer_visible },
        { name: 'planned_start', label: 'Planned start (internal)', kind: 'date', value: w.planned_start },
        { name: 'planned_finish', label: 'Planned finish (internal)', kind: 'date', value: w.planned_finish },
        { name: 'reason', label: 'Reason for a replan', kind: 'textarea', maxLength: 1000 },
      ],
      run: (b) => projectApi.updateWork(p, w, b) });
  }

  private workCommand(p: ProjectDetail, w: WorkPackage, command: 'start' | 'complete' | 'reopen' | 'cancel') {
    const words = { start: 'Start', complete: 'Complete', reopen: 'Reopen', cancel: 'Cancel the work' }[command];
    const fields: Field[] = command === 'start' ? [{ name: 'actual_start', label: 'Started on', kind: 'date', required: true, value: TODAY() }]
      : command === 'complete' ? [{ name: 'actual_finish', label: 'Finished on', kind: 'date', required: true, value: TODAY() },
        { name: 'note', label: 'Note', kind: 'textarea', classification: 'INTERNAL_ONLY' }, ...this.evidenceFields(p)]
        : [{ name: 'reason', label: 'Reason', kind: 'textarea', required: true, ...REASON }];
    this.open({ title: `${words}: WP-${w.package_no} ${w.title}`, submit: words, danger: command === 'cancel' || command === 'reopen',
      done: `WP-${w.package_no}: ${command === 'cancel' ? 'cancelled' : command === 'reopen' ? 'reopened' : command === 'start' ? 'started' : 'completed'}.`,
      intro: command === 'complete' ? 'Completion is explicit and dated; a planned date passing never completes work.' : undefined,
      fields, run: (b) => projectApi.workCommand(p, w, command, b) });
  }

  // --- customer reports -----------------------------------------------------------------------------------------------
  private recordReport(p: ProjectDetail) {
    this.open({ title: 'Record an issue the customer reported', submit: 'Record', done: 'Report recorded.',
      intro: 'In the customer\'s own words, as they told you by phone or on site. It is reviewed like a portal report; it is not a defect until reviewed.',
      fields: [
        { name: 'description', label: 'What the customer reported', kind: 'textarea', required: true, minLength: 10, maxLength: 2000 },
        { name: 'area', label: 'Where (customer\'s words)', kind: 'text', maxLength: 120 },
      ],
      run: (b) => projectApi.recordReport(p, b) });
  }

  private triageReport(p: ProjectDetail, r: CustomerReport, outcome: 'NEW_SNAG' | 'EXISTING_SNAG' | 'DECLINED') {
    const words = { NEW_SNAG: 'Raise a snag from it', EXISTING_SNAG: 'Link to an existing snag', DECLINED: 'Decline with a reply' }[outcome];
    const fields: Field[] = outcome === 'NEW_SNAG' ? [
      { name: 'category', label: 'Snag category', kind: 'select', required: true, options: opt(this.vocab?.snag_categories ?? []) },
      { name: 'customer_title', label: 'Snag title (customer-safe words)', kind: 'text', required: true, minLength: 3, maxLength: 160, classification: 'POTENTIALLY_CUSTOMER_SAFE' },
      { name: 'owner_user_id', label: 'Owner', kind: 'select', options: p.team.filter((m) => m.active && m.user).map((m) => [m.user!.id, who(m.user)]) },
    ] : outcome === 'EXISTING_SNAG' ? [
      { name: 'snag_id', label: 'Snag', kind: 'select', required: true, options: p.snags.map((x) => [x.id, `Snag ${x.snag_no}: ${x.customer_title}`]) },
    ] : [
      { name: 'decline_code', label: 'Why', kind: 'select', required: true, options: [['DUPLICATE', 'Already recorded'], ['NOT_A_DEFECT', 'Checked: no fix needed'], ['NOT_IN_SCOPE', 'Not part of the agreed work']] },
    ];
    fields.push({ name: 'response', label: outcome === 'DECLINED' ? 'Reply to the customer' : 'Reply to the customer (optional)', kind: 'textarea', maxLength: 500,
      classification: 'POTENTIALLY_CUSTOMER_SAFE', ...(outcome === 'DECLINED' ? { required: true, minLength: 10 } : {}) });
    this.open({ title: `Report ${r.report_no}: ${words}`, submit: words, done: `Report ${r.report_no} reviewed.`,
      intro: outcome === 'NEW_SNAG' ? 'The snag is shown to the customer, who reported it.' : undefined,
      fields,
      run: (b) => {
        const body: Record<string, unknown> = { outcome, response: b.response };
        if (outcome === 'NEW_SNAG') body.snag = { category: b.category, customer_title: b.customer_title, ...(b.owner_user_id ? { owner_user_id: b.owner_user_id } : {}) };
        if (outcome === 'EXISTING_SNAG') body.snag_id = b.snag_id;
        if (outcome === 'DECLINED') body.decline_code = b.decline_code;
        return projectApi.triageReport(p, r, body);
      } });
  }

  private async preparePackage(p: ProjectDetail) {
    if (this.busy) return;
    this.busy = true;
    try {
      this.project = (await projectApi.preparePackage(p)).data;
      this.announcement = 'Handover package prepared.';
    } catch (e) {
      const problem = e as ApiProblem;
      if (problem.code === 'VERSION_CONFLICT') this.conflict = true;
      else this.problem = problem;
    } finally { this.busy = false; }
  }

  // --- sections -------------------------------------------------------------------------------------------------------
  private renderHero(p: ProjectDetail): TemplateResult {
    const ev = p.readiness;
    const gating = p.blockers.filter((b) => b.impact === 'GATING' && !['RESOLVED', 'CANCELLED'].includes(b.status)).length;
    return html`<dl class="hero card" aria-label="Project summary">
      <div><dt>Project reference</dt><dd>${p.project_number}</dd></div>
      <div><dt>Property</dt><dd>${p.property.property_number}${p.property.locality ? ` · ${p.property.locality}` : ''}${p.property.configuration_label ? ` · ${p.property.configuration_label}` : ''}</dd></div>
      <div><dt>Current stage</dt><dd>${p.stage.label} <span class="muted">(stage ${p.stage.sequence} of ${p.stage.of})</span></dd></div>
      <div><dt>Operational owner</dt><dd>${who(p.owner, 'Not assigned')}</dd></div>
      <div><dt>Next milestone</dt><dd>${p.next_milestone ? html`${p.next_milestone.label}${p.next_milestone.planned_date ? html` · ${formatDate(p.next_milestone.planned_date)}` : nothing}
        ${p.next_milestone.overdue ? html` <span class="badge warn">Past its planned date</span>` : nothing}` : html`<span class="muted">None planned</span>`}</dd></div>
      <div><dt>Readiness</dt><dd>${p.status === 'HANDED_OVER' ? html`<span class="badge ok">Handed over ${when(p.handed_over_on)}</span>`
        : p.awaiting_approval ? html`<span class="badge action">Awaiting approval for ${this.stageLabel(p.awaiting_approval.to_stage)}</span>`
          : ev?.allowed ? html`<span class="badge ok">Ready for ${this.stageLabel(ev.to)}</span>`
            : html`<span class="badge warn">${ev?.blockers.length ?? 0} to clear before ${this.stageLabel(ev?.to)}</span>`}</dd></div>
      <div><dt>Blocking issues</dt><dd>${gating ? html`<span class="badge gating">${gating} gating</span>` : html`<span class="muted">None</span>`}</dd></div>
    </dl>`;
  }

  private renderAttention(items: Attention[], p: ProjectDetail): TemplateResult {
    const next = p.readiness?.to;
    return html`<section class="stack" aria-labelledby="attention-h"><h2 id="attention-h">What needs attention</h2>
      ${items.length ? html`<ul class="attention">${items.map((a) => html`<li class=${a.severity}>
          <div class="row"><span class="badge ${a.severity === 'GATING' || a.severity === 'ACTION' ? 'gating' : a.severity === 'SITE' ? 'warn' : 'info'}">${SEVERITY[a.severity]}</span>
            ${a.severity === 'GATING' ? html`<strong>Blocked</strong>` : nothing}</div>
          <h3>${a.title}</h3>
          <dl class="meta">
            <dt>Who needs to act</dt><dd>${party(a.who)}</dd>
            ${a.action ? html`<dt>What is needed</dt><dd>${a.action}</dd>` : nothing}
            ${a.blocks ? html`<dt>What it blocks</dt><dd>${this.stageLabel(a.blocks)}</dd>` : nothing}
            ${a.severity === 'GATING' && next ? html`<dt>When resolved</dt><dd>The move to ${this.stageLabel(next)} can be requested.</dd>` : nothing}
          </dl></li>`)}</ul>` : html`<p class="muted">Nothing needs attention.</p>`}
    </section>`;
  }

  private renderNextActions(p: ProjectDetail): TemplateResult {
    const a = p.actions;
    const ev = p.readiness;
    const t = p.awaiting_approval;
    return html`<section class="stack" aria-labelledby="next-h"><h2 id="next-h">Next actions</h2>
      ${ev ? html`<p>${ev.allowed ? `Every gate for ${this.stageLabel(ev.to)} is satisfied.` : `Before ${this.stageLabel(ev.to)}:`}
        ${ev.risk === 'HIGH' ? html` <span class="badge warn">High-risk move</span>` : nothing}</p>
        ${p.next_actions.length ? html`<ul class="plain">${p.next_actions.map((x) => html`<li><strong>${party(x.who)}:</strong> ${x.message}</li>`)}</ul>` : nothing}` : nothing}
      <div class="actions">
        ${t ? html`
          ${a.approve_transition ? html`<button class="btn primary" @click=${() => this.decide(p, t, 'approve')}>Approve the move to ${this.stageLabel(t.to_stage)}</button>
            <button class="btn" @click=${() => this.decide(p, t, 'reject')}>Reject</button>` : nothing}
          ${(a.request_transition || a.complete_handover) ? html`<button class="btn" @click=${() => this.decide(p, t, 'withdraw')}>Withdraw the request</button>` : nothing}`
        : ev?.command === 'HANDOVER' ? (a.complete_handover ? html`<button class="btn primary" @click=${() => this.handover(p)}>Complete the handover</button>` : nothing)
          : ev && a.request_transition ? html`<button class="btn primary" @click=${() => this.requestMove(p)}>Request the move to ${this.stageLabel(ev.to)}</button>` : nothing}
      </div>
    </section>`;
  }

  private renderTeam(p: ProjectDetail): TemplateResult {
    const active = p.team.filter((m) => m.active);
    return html`<section class="stack" aria-labelledby="team-h"><div class="row"><h2 id="team-h">Owners and team</h2><span class="spacer"></span>
        ${p.actions.assign_team ? html`<button class="btn" @click=${() => this.assign(p)}>Assign</button>` : nothing}</div>
      ${p.needs_reassignment.length ? html`<vs-banner kind="warning">Needs reassignment: ${p.needs_reassignment.map(humanize).join(', ')}. The assigned owner can no longer act on this project; the assignment is kept in the history.</vs-banner>` : nothing}
      ${active.length ? html`<ul class="plain">${active.map((m) => html`<li>${humanize(m.responsibility)}: <strong>${who(m.user)}</strong>
        ${!m.eligible && m.responsibility !== 'MEMBER' ? html` <span class="badge warn">Needs reassignment</span>` : nothing}
        <span class="muted small">since ${when(m.assigned_on)}</span>
        ${p.actions.assign_team ? html` <button class="btn small ghost" @click=${() => this.removeMember(p, m)} aria-label=${`End ${who(m.user)}'s ${humanize(m.responsibility).toLowerCase()} assignment`}>End</button>` : nothing}</li>`)}</ul>`
        : html`<p class="muted">No one is assigned yet.</p>`}
    </section>`;
  }

  private renderOverview(p: ProjectDetail): TemplateResult {
    return html`${this.renderAttention(p.attention, p)}${this.renderNextActions(p)}${this.renderTeam(p)}`;
  }

  private gateResult(passed: boolean | null) {
    return passed === null ? html`<span class="badge info">Checked at the handover</span>` : passed ? html`<span class="badge ok">Satisfied</span>`
      : html`<span class="badge gating">Not satisfied</span>`;
  }

  private renderStage(p: ProjectDetail): TemplateResult {
    const ev = p.readiness;
    const pending = Object.entries(p.policy.decisions).filter(([, d]) => !d.decided);
    return html`<section class="stack" aria-labelledby="stages-h"><h2 id="stages-h" tabindex="-1">Stages</h2>
      <p class="small muted">Lifecycle ${p.lifecycle.version} (${humanize(p.lifecycle.status)}). Stages are completed in order; each move is a request the system checks.</p>
      <ol class="stages">${p.stages.map((s) => html`<li aria-current=${s.code === p.stage.code ? 'step' : 'false'}>
        <span class="muted">${s.sequence}.</span><span>${s.label}<span class="small muted"> · owner: ${humanize(s.owner_responsibility)}</span></span>
        <span class="badge ${s.status === 'COMPLETED' ? 'ok' : s.status === 'ACTIVE' ? 'action' : 'info'}">${humanize(s.status)}</span></li>`)}</ol></section>
      ${ev ? html`<section class="stack" aria-labelledby="gates-h"><h2 id="gates-h">Gates for ${this.stageLabel(ev.to)}</h2>
        <p class="small muted">${ev.risk === 'HIGH' ? 'High-risk move. ' : ''}${ev.independent_approval ? 'Needs an independent approval. ' : ''}Gates come from the owner's decision where recorded, otherwise the strict defaults.</p>
        <div class="table-wrap" tabindex="0" role="region" aria-label="Gates, scrolls sideways on small screens"><table class="cards"><caption class="sr-only">Gates of the next move</caption>
          <thead><tr><th scope="col">Gate</th><th scope="col">Source</th><th scope="col">Result</th><th scope="col">What is missing</th></tr></thead>
          <tbody>${ev.gates.map((g) => html`<tr><td data-label="Gate">${g.label}</td><td data-label="Source">${humanize(g.source)}</td>
            <td data-label="Result">${this.gateResult(g.passed)}</td>
            <td data-label="What is missing">${g.blockers.length ? html`<ul class="plain">${g.blockers.map((b) => html`<li>${b.message}${b.responsible_party ? html` <span class="muted">(${party(b.responsible_party)})</span>` : nothing}</li>`)}</ul>` : '—'}</td></tr>`)}</tbody>
        </table></div></section>` : nothing}
      <section class="stack" aria-labelledby="policy-h"><h2 id="policy-h">Owner decisions</h2>
        ${pending.length ? html`<p>${pending.length} decision(s) not yet recorded by the owner:</p>
          <ul class="plain">${pending.map(([code, d]) => html`<li>${code}: ${d.label}${d.read_by_engine ? '' : ' (recorded for the register)'}</li>`)}</ul>` : html`<p>Every decision is recorded.</p>`}
      </section>`;
  }

  private renderChecklist(p: ProjectDetail): TemplateResult {
    const a = p.actions;
    return html`<h2 id="checklist-h" tabindex="-1">Checklists</h2>
      ${p.checklist.map((g) => html`<section class="group stack" aria-labelledby=${`cl-${g.stage_code}`}>
        <div class="row"><h3 id=${`cl-${g.stage_code}`}>${g.stage_label}</h3><span class="badge ${g.done === g.total ? 'ok' : 'info'}">${g.done} of ${g.total}</span>
          ${g.current ? html`<span class="badge action">Current stage</span>` : g.closed ? html`<span class="badge info">Closed</span>` : nothing}</div>
        <ul class="plain">${g.items.map((i) => html`<li><div class="row">
          <span class="badge ${i.state === 'OPEN' ? 'warn' : 'ok'}">${humanize(i.state)}</span><span>${i.label}${i.required ? '' : ' (optional)'}</span>
          ${!g.closed && a.complete_checklist && i.state === 'OPEN' ? html`<button class="btn small" @click=${() => this.completeItem(p, i, false)} aria-label=${`Complete: ${i.label}`}>Complete</button>
            ${!i.required || a.checklist_not_applicable ? html`<button class="btn small ghost" @click=${() => this.completeItem(p, i, true)} aria-label=${`Mark not applicable: ${i.label}`}>Not applicable</button>` : nothing}` : nothing}
          ${!g.closed && a.complete_checklist && i.state !== 'OPEN' ? html`<button class="btn small ghost" @click=${() => this.reopenItem(p, i)} aria-label=${`Reopen: ${i.label}`}>Reopen</button>` : nothing}</div>
          ${i.state !== 'OPEN' ? html`<span class="small muted">${who(i.completed_by)}, ${when(i.completed_on)}${i.not_applicable_reason ? ` · not applicable: ${i.not_applicable_reason}` : ''}${i.note ? ` · ${i.note}` : ''}</span>` : nothing}
          ${i.reopen_reason && i.state === 'OPEN' ? html`<span class="small muted">Reopened: ${i.reopen_reason}</span>` : nothing}</li>`)}</ul>
      </section>`)}`;
  }

  private renderBlockers(p: ProjectDetail): TemplateResult {
    const open = p.blockers.filter((b) => !['RESOLVED', 'CANCELLED'].includes(b.status));
    const closed = p.blockers.filter((b) => ['RESOLVED', 'CANCELLED'].includes(b.status));
    const card = (b: Blocker) => html`<li class=${b.impact === 'GATING' && open.includes(b) ? 'GATING' : 'INFORMATIONAL'}>
      <div class="row"><span class="badge ${b.impact === 'GATING' ? 'gating' : 'info'}">${b.impact === 'GATING' ? `Gating: stops ${b.blocks?.label ?? ''}` : 'For information'}</span>
        <span class="badge info">${humanize(b.status)}</span><span class="small muted">${humanize(b.category)}</span></div>
      <h3>${b.title}</h3>
      <dl class="meta"><dt>Who needs to act</dt><dd>${party(b.responsible_party)}</dd>
        ${b.customer_action ? html`<dt>Customer action</dt><dd>${b.customer_action} <span class="class-tag">· ${CLASS_LABEL.CUSTOMER_ACTION}</span></dd>` : nothing}
        ${b.description ? html`<dt>Details</dt><dd>${b.description} <span class="class-tag">· ${CLASS_LABEL.INTERNAL_ONLY}</span></dd>` : nothing}
        <dt>Assigned to</dt><dd>${who(b.assigned_to, 'Not assigned')}</dd>
        <dt>Raised</dt><dd>${who(b.raised_by)}, ${when(b.raised_on)}</dd>
        ${b.target_date ? html`<dt>Target</dt><dd>${formatDate(b.target_date)}</dd>` : nothing}
        ${b.resolution ? html`<dt>${b.status === 'CANCELLED' ? 'Cancelled' : 'Resolved'}</dt><dd>${b.resolution} (${who(b.resolved_by)}, ${when(b.resolved_on)})</dd>` : nothing}</dl>
      ${open.includes(b) && p.actions.resolve_blocker ? html`<div class="actions">
        <button class="btn small" @click=${() => this.updateBlocker(p, b)} aria-label=${`Update: ${b.title}`}>Update</button>
        <button class="btn small" @click=${() => this.closeBlocker(p, b, 'resolve')} aria-label=${`Resolve: ${b.title}`}>Resolve</button>
        <button class="btn small ghost" @click=${() => this.closeBlocker(p, b, 'cancel')} aria-label=${`Cancel: ${b.title}`}>Cancel</button></div>` : nothing}</li>`;
    return html`<div class="row"><h2 id="blockers-h" tabindex="-1">Blockers and issues</h2><span class="spacer"></span>
        ${p.actions.raise_blocker ? html`<button class="btn" @click=${() => this.raiseBlocker(p)}>Raise a blocker</button>` : nothing}</div>
      <p class="small muted">A gating blocker stops the stage it names and every later one; an issue for information never stops progress.</p>
      ${open.length ? html`<ul class="attention" aria-label="Open blockers">${open.map(card)}</ul>` : html`<p class="muted">No open blockers.</p>`}
      ${closed.length ? html`<h3>Closed</h3><ul class="attention" aria-label="Closed blockers">${closed.map(card)}</ul>` : nothing}`;
  }

  private renderMilestones(p: ProjectDetail): TemplateResult {
    const a = p.actions;
    return html`<div class="row"><h2 id="milestones-h" tabindex="-1">Milestones</h2><span class="spacer"></span>
        ${a.manage_milestone ? html`<button class="btn" @click=${() => this.addMilestone(p)}>Add a milestone</button>` : nothing}</div>
      <p class="small muted">Planned dates are internal plans. A customer-promised date is recorded only when it was already promised. A milestone is completed explicitly.</p>
      ${p.milestones.length ? html`<div class="table-wrap" tabindex="0" role="region" aria-label="Milestones, scrolls sideways on small screens"><table class="cards">
        <caption class="sr-only">Milestones</caption>
        <thead><tr><th scope="col">Milestone</th><th scope="col">Stage</th><th scope="col">Status</th><th scope="col">Planned</th><th scope="col">Customer-promised</th>
          <th scope="col">Actual</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>${p.milestones.map((m) => html`<tr>
          <td data-label="Milestone">${m.label}<span class="small muted"> · ${humanize(m.code)}</span></td><td data-label="Stage">${this.stageLabel(m.stage_code)}</td>
          <td data-label="Status"><span class="badge ${m.status === 'COMPLETED' ? 'ok' : m.status === 'BLOCKED' ? 'gating' : 'info'}">${humanize(m.status)}</span>${m.overdue ? html` <span class="badge warn">Past planned date</span>` : nothing}</td>
          <td data-label="Planned">${m.planned_date ? formatDate(m.planned_date) : '—'}</td><td data-label="Customer-promised">${m.customer_promised_date ? formatDate(m.customer_promised_date) : '—'}</td>
          <td data-label="Actual">${m.actual_date ? formatDate(m.actual_date) : '—'}</td>
          <td data-label="Actions">${a.manage_milestone && !['COMPLETED', 'CANCELLED', 'NOT_APPLICABLE'].includes(m.status) ? html`<div class="actions">
            <button class="btn small" @click=${() => this.updateMilestone(p, m)} aria-label=${`Plan or update: ${m.label}`}>Update</button>
            <button class="btn small" @click=${() => this.completeMilestone(p, m)} aria-label=${`Complete: ${m.label}`}>Complete</button></div>` : '—'}</td></tr>`)}</tbody></table></div>`
        : html`<p class="muted">No milestones yet.</p>`}`;
  }

  private renderBaseline(p: ProjectDetail): TemplateResult {
    const b = p.baseline;
    return html`<h2 id="baseline-h" tabindex="-1">Commercial baseline</h2>
      ${b.verified ? html`<vs-banner kind="success">The baseline verifies: every accepted quotation matches its sealed digests and every accepted variation is recorded.</vs-banner>`
        : html`<vs-banner kind="danger"><strong>The baseline does not verify.</strong><ul class="plain">${b.problems.map((x) => html`<li>${x.message}</li>`)}</ul></vs-banner>`}
      <p class="small muted">The project never changes the accepted quotation. A change of scope or price is a variation, raised and accepted in the commercial workspace;
        once accepted it becomes the next effective baseline here.</p>
      <ol class="timeline" aria-label="Baseline lineage">${b.lineage.map((r) => html`<li>
        <strong>${r.kind === 'ORIGINAL' ? 'Original accepted baseline' : `Variation ${r.variation_no}`}</strong> · ${r.label ?? ''}
        ${r.current ? html` <span class="badge action">Current effective baseline</span>` : nothing}
        <div class="small muted">Accepted ${when(r.decided_on)} (${humanize(r.decision_method)})</div>
        ${b.full ? html`<dl class="meta"><dt>Accepted value</dt><dd>${money(r.accepted_total_minor)}</dd><dt>Cumulative value</dt><dd>${money(r.cumulative_value_minor)}</dd>
          <dt>Baseline digest</dt><dd class="mono">${r.baseline_sha256}</dd></dl>` : nothing}</li>`)}</ol>
      <h3>Variations</h3>
      ${b.variations.length ? html`<ul class="plain">${b.variations.map((v) => html`<li>${v.label}: ${humanize(v.status)}${b.full && v.total_minor != null ? ` · ${money(v.total_minor)}` : ''}</li>`)}</ul>`
        : html`<p class="muted">No variations.</p>`}
      <p><a href=${`/site/properties/${p.property.id}/commercial`} @click=${(e: Event) => { e.preventDefault(); navigate(`/site/properties/${p.property.id}/commercial`); }}>Open the commercial workspace</a></p>`;
  }

  private renderSite(p: ProjectDetail): TemplateResult {
    const a = p.actions;
    return html`<div class="row"><h2 id="site-h" tabindex="-1">Site readiness</h2><span class="spacer"></span>
        ${a.manage_site_readiness ? html`<button class="btn" @click=${() => this.addReadiness(p)}>Add an item</button>` : nothing}</div>
      <p><span class="badge ${p.site_readiness_state === 'READY' ? 'ok' : p.site_readiness_state === 'BLOCKED' ? 'gating' : 'warn'}">${humanize(p.site_readiness_state)}</span></p>
      <p class="small muted">Items from the accepted quotation's Customer Promise show the promised text; this records what is true on this site and never changes the quotation.</p>
      ${p.site_readiness.length ? html`<div class="table-wrap" tabindex="0" role="region" aria-label="Site readiness, scrolls sideways on small screens"><table class="cards">
        <caption class="sr-only">Site-readiness items</caption>
        <thead><tr><th scope="col">Item</th><th scope="col">Source</th><th scope="col">Status</th><th scope="col">Who acts</th><th scope="col">Action</th><th scope="col">Due</th>
          <th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>${p.site_readiness.map((r) => html`<tr>
          <td data-label="Item">${r.label ?? humanize(r.category)}<span class="small muted"> · ${humanize(r.category)}</span></td>
          <td data-label="Source">${r.source === 'CUSTOMER_PROMISE' ? `Customer Promise ${r.promise?.content_version ?? ''}` : 'Added by staff'}</td>
          <td data-label="Status"><span class="badge ${r.satisfied ? 'ok' : r.status === 'TO_BE_CONFIRMED' ? 'warn' : 'gating'}">${humanize(r.status)}</span></td>
          <td data-label="Who acts">${party(r.responsible_party)}</td>
          <td data-label="Action">${r.responsible_party === 'CUSTOMER' && r.customer_action ? r.customer_action : r.action ?? '—'}</td>
          <td data-label="Due">${r.due_date ? formatDate(r.due_date) : '—'}</td>
          <td data-label="Actions">${a.manage_site_readiness ? html`<button class="btn small" @click=${() => this.updateReadiness(p, r)} aria-label=${`Update: ${r.label ?? r.category}`}>Update</button>` : '—'}</td></tr>`)}</tbody></table></div>`
        : html`<p class="muted">No site-readiness item is recorded yet.</p>`}`;
  }

  private renderQuality(p: ProjectDetail): TemplateResult {
    const a = p.actions;
    const failed = p.qc.chains.filter((c) => c.head.result === 'FAIL');
    const badge = (r: string | null) => html`<span class="badge ${r === 'PASS' ? 'ok' : r === 'FAIL' ? 'gating' : 'info'}">${r ? humanize(r) : 'No result'}</span>`;
    return html`<div class="row"><h2 id="quality-h" tabindex="-1">Quality check</h2><span class="spacer"></span>
        ${a.manage_qc ? html`<button class="btn" @click=${() => this.addQcPoint(p)}>Plan a check</button>
          <button class="btn" @click=${() => this.recordQc(p)}>Record a result</button>` : nothing}</div>
      <p class="small muted">Each result starts a check; a recheck continues it. A check counts by its latest result, so a pass elsewhere never hides a failure.</p>
      ${failed.length ? html`<section class="stack" aria-labelledby="qc-failed-h"><h3 id="qc-failed-h">Failed checks to correct (${failed.length})</h3>
        <ul class="attention">${failed.map((c) => html`<li class="GATING"><div class="row">${badge('FAIL')}<strong>${humanize(c.head.category)}</strong>
          ${c.head.space ? html`<span class="small muted">${c.head.space}</span>` : nothing}</div>
          <p>${c.head.observation ?? ''}</p><span class="small muted">${who(c.head.checked_by)}, ${when(c.head.checked_on)}</span>
          ${a.manage_qc || a.manage_snag ? html`<div class="actions">
            ${a.manage_snag ? html`<button class="btn small" @click=${() => this.raiseSnag(p, c.head.id)} aria-label=${`Raise a snag for the ${humanize(c.head.category)} failure`}>Raise a snag</button>` : nothing}
            ${a.manage_qc ? html`<button class="btn small" @click=${() => this.recordQc(p, c.head.category, c.head.id)} aria-label=${`Recheck ${humanize(c.head.category)}`}>Recheck</button>` : nothing}
          </div>` : nothing}</li>`)}</ul></section>` : nothing}
      <h3>QC plan</h3>
      ${p.qc.points.length ? html`<div class="table-wrap" tabindex="0" role="region" aria-label="QC plan, scrolls sideways on small screens"><table class="cards">
        <caption class="sr-only">Planned quality checks</caption>
        <thead><tr><th scope="col">Check</th><th scope="col">Category</th><th scope="col">Where</th><th scope="col">Result</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>${p.qc.points.map((q) => html`<tr><td data-label="Check">QC-${q.point_no}: ${q.label}${q.evidence_required ? html` <span class="badge info">Evidence needed</span>` : nothing}</td>
          <td data-label="Category">${humanize(q.category)}</td><td data-label="Where">${q.space ?? '—'}${q.work_package_id ? ` · ${this.workName(p, q.work_package_id)}` : ''}</td>
          <td data-label="Result">${q.status === 'WITHDRAWN' ? html`<span class="badge info">Withdrawn</span> <span class="small muted">${q.withdrawn_reason ?? ''}</span>` : badge(q.result)}</td>
          <td data-label="Actions">${a.manage_qc && q.status === 'ACTIVE' ? html`<div class="actions">
            ${q.result === null ? html`<button class="btn small" @click=${() => this.recordQc(p, q.category, undefined, q)} aria-label=${`Record the result of QC-${q.point_no}`}>Record</button>
              <button class="btn small ghost" @click=${() => this.withdrawQcPoint(p, q)} aria-label=${`Withdraw QC-${q.point_no}`}>Withdraw</button>` : '—'}</div>` : '—'}</td></tr>`)}</tbody></table></div>`
        : html`<p class="muted">No quality check is planned. Required categories still need a result before handover.</p>`}
      <h3>By category</h3>
      <div class="table-wrap" tabindex="0" role="region" aria-label="Quality checks by category, scrolls sideways on small screens"><table class="cards">
        <caption class="sr-only">Latest result per quality-check category</caption>
        <thead><tr><th scope="col">Category</th><th scope="col">Required</th><th scope="col">Most recent result</th><th scope="col">Observation</th></tr></thead>
        <tbody>${p.qc.categories.map((c) => html`<tr><td data-label="Category">${humanize(c.category)}</td><td data-label="Required">${c.required ? 'Yes' : 'No'}</td>
          <td data-label="Most recent result">${c.latest ? html`${badge(c.latest.result)} <span class="small muted">${who(c.latest.checked_by)}, ${when(c.latest.checked_on)}</span>` : html`<span class="muted">No result</span>`}</td>
          <td data-label="Observation">${c.latest?.observation ?? '—'}</td></tr>`)}</tbody></table></div>
      <div class="row"><h2 id="snags-h">Snags</h2><span class="spacer"></span>${a.manage_snag ? html`<button class="btn" @click=${() => this.raiseSnag(p)}>Raise a snag</button>` : nothing}</div>
      <p class="small muted">The person who fixes a snag records the fix; someone else verifies it. Closing without a fix needs a reason.</p>
      ${p.snags.length ? html`<ul class="attention" aria-label="Snags">${p.snags.map((sn) => {
        const moves = this.snagMoves(p, sn);
        return html`<li class=${sn.is_blocking && ['OPEN', 'IN_PROGRESS', 'READY_FOR_RECHECK'].includes(sn.status) ? 'GATING' : 'INFORMATIONAL'}>
        <div class="row"><span class="badge ${['RESOLVED', 'CLOSED'].includes(sn.status) ? 'ok' : sn.is_blocking ? 'gating' : 'info'}">${SNAG_STATUS[sn.status] ?? humanize(sn.status)}</span>
          ${sn.is_blocking ? html`<span class="small">Blocks the handover</span>` : html`<span class="small muted">Does not block the handover</span>`}
          ${sn.source === 'CUSTOMER' ? html`<span class="badge action">Reported by the customer</span>` : nothing}
          ${sn.customer_visible ? html`<span class="badge info">Visible to the customer</span>` : nothing}
          ${sn.priority !== 'NORMAL' ? html`<span class="badge ${sn.priority === 'HIGH' ? 'warn' : 'info'}">${humanize(sn.priority)} priority</span>` : nothing}</div>
        <h3>Snag ${sn.snag_no}: ${sn.customer_title}</h3>
        <dl class="meta"><dt>Category</dt><dd>${humanize(sn.category)}</dd>${sn.space ? html`<dt>Space</dt><dd>${sn.space}</dd>` : nothing}
          ${sn.work_package_id ? html`<dt>Work</dt><dd>${this.workName(p, sn.work_package_id)}</dd>` : nothing}
          <dt>Owner</dt><dd>${who(sn.owner, 'Not assigned')} · ${party(sn.responsible_party)}</dd>
          ${sn.description ? html`<dt>Details</dt><dd>${sn.description}</dd>` : nothing}
          ${sn.fix_note ? html`<dt>Fix</dt><dd>${sn.fix_note} (${who(sn.fixed_by)}, ${when(sn.fixed_on)})</dd>` : nothing}
          ${sn.resolution_note ? html`<dt>${sn.status === 'RESOLVED' || sn.closure_code === 'FIXED' ? 'Verification' : 'Resolution'}</dt><dd>${sn.resolution_note}${sn.resolved_by ? ` (${who(sn.resolved_by)})` : ''}</dd>` : nothing}
          ${sn.closure_code ? html`<dt>Closed as</dt><dd>${humanize(sn.closure_code)}</dd>` : nothing}</dl>
        ${sn.classification_reason ? html`<p class="small muted">Classification changed: ${sn.classification_reason}</p>` : nothing}
        ${moves.length || (a.manage_snag && sn.status === 'OPEN') ? html`<div class="actions">
          ${a.manage_snag && ['OPEN', 'IN_PROGRESS'].includes(sn.status) ? html`<button class="btn small ghost" @click=${() => this.assignSnag(p, sn)} aria-label=${`Snag ${sn.snag_no}: assign`}>Assign</button>` : nothing}
          ${moves.map((st) => {
            const label = sn.status === 'READY_FOR_RECHECK' && st === 'IN_PROGRESS' ? 'Recheck failed' : st === 'CLOSED' && sn.status !== 'RESOLVED' ? 'Close without a fix' : SNAG_ACTION[st] ?? humanize(st);
            return html`<button class="btn small" @click=${() => this.snagStatus(p, sn, st)} aria-label=${`Snag ${sn.snag_no}: ${label}`}>${label}</button>`;
          })}
          ${a.reclassify_snag && !['RESOLVED', 'CLOSED'].includes(sn.status) ? html`<button class="btn small ghost" @click=${() => this.reclassify(p, sn)}
            aria-label=${`Snag ${sn.snag_no}: change whether it blocks the handover`}>Change blocking</button>` : nothing}</div>` : nothing}</li>`;
      })}</ul>` : html`<p class="muted">No snags.</p>`}`;
  }

  private workName(p: ProjectDetail, id: string): string {
    const w = p.work_packages.find((x) => x.id === id);
    return w ? `WP-${w.package_no}: ${w.title}` : '—';
  }

  private renderWork(p: ProjectDetail): TemplateResult {
    const a = p.actions;
    const byStage = p.stages.filter((st) => p.work_packages.some((w) => w.stage_code === st.code));
    return html`<div class="row"><h2 id="work-h" tabindex="-1">Work plan</h2><span class="spacer"></span>
        ${a.manage_work ? html`<button class="btn" @click=${() => this.addWork(p)}>Add work</button>` : nothing}</div>
      <p class="small muted">Work starts and completes in its own stage, after the work it follows. Blocked and correction-required are worked out from blockers and quality checks; they are never set by hand. A stage cannot complete while its work is open.</p>
      ${byStage.length ? byStage.map((st) => html`<section class="group stack" aria-labelledby=${`wp-${st.code}`}>
        <div class="row"><h3 id=${`wp-${st.code}`}>${st.label}</h3>${st.code === p.stage.code ? html`<span class="badge action">Current stage</span>` : nothing}</div>
        <ul class="attention">${p.work_packages.filter((w) => w.stage_code === st.code).map((w) => {
          const [label, tone] = WORK_STATE[w.state] ?? [humanize(w.state), 'info'];
          const live = w.stage_code === p.stage.code && a.manage_work;
          return html`<li class=${w.state === 'BLOCKED' || w.state === 'CORRECTION_REQUIRED' ? 'GATING' : 'INFORMATIONAL'}>
          <div class="row"><span class="badge ${tone}">${label}</span>${w.customer_visible ? html`<span class="badge info">Visible to the customer</span>` : nothing}
            ${!w.scheduled ? html`<span class="small muted">Unscheduled</span>` : nothing}${w.past_planned_finish ? html`<span class="badge warn">Past its planned finish</span>` : nothing}</div>
          <h3>WP-${w.package_no}: ${w.title}</h3>
          <dl class="meta">${w.customer_label ? html`<dt>Customer label</dt><dd>${w.customer_label}</dd>` : nothing}
            ${w.space ? html`<dt>Space</dt><dd>${w.space}</dd>` : nothing}<dt>Owner</dt><dd>${who(w.owner, 'Not assigned')}</dd>
            ${w.depends_on_id ? html`<dt>Starts after</dt><dd>${this.workName(p, w.depends_on_id)}</dd>` : nothing}
            ${w.scheduled ? html`<dt>Planned</dt><dd>${w.planned_start ? formatDate(w.planned_start) : '—'} to ${w.planned_finish ? formatDate(w.planned_finish) : '—'}${w.plan_revision ? ` (replanned ${w.plan_revision}×${w.replan_reason ? `: ${w.replan_reason}` : ''})` : ''}</dd>` : nothing}
            ${w.actual_start ? html`<dt>Actual</dt><dd>${formatDate(w.actual_start)} to ${w.actual_finish ? formatDate(w.actual_finish) : 'in progress'}</dd>` : nothing}
            ${w.cancel_reason ? html`<dt>Cancelled</dt><dd>${w.cancel_reason}</dd>` : nothing}
            ${w.reopen_reason && w.status === 'IN_PROGRESS' ? html`<dt>Reopened</dt><dd>${w.reopen_reason}</dd>` : nothing}</dl>
          ${live && w.status !== 'CANCELLED' ? html`<div class="actions">
            ${w.status === 'NOT_STARTED' ? html`<button class="btn small" @click=${() => this.workCommand(p, w, 'start')} aria-label=${`Start WP-${w.package_no}`}>Start</button>` : nothing}
            ${w.status === 'IN_PROGRESS' ? html`<button class="btn small" @click=${() => this.workCommand(p, w, 'complete')} aria-label=${`Complete WP-${w.package_no}`}>Complete</button>` : nothing}
            ${w.status === 'COMPLETED' ? html`<button class="btn small ghost" @click=${() => this.workCommand(p, w, 'reopen')} aria-label=${`Reopen WP-${w.package_no}`}>Reopen</button>` : nothing}
            ${w.status !== 'COMPLETED' ? html`<button class="btn small ghost" @click=${() => this.planWork(p, w)} aria-label=${`Plan WP-${w.package_no}`}>Plan</button>
              <button class="btn small ghost" @click=${() => this.workCommand(p, w, 'cancel')} aria-label=${`Cancel WP-${w.package_no}`}>Cancel</button>` : nothing}
          </div>` : nothing}</li>`;
        })}</ul></section>`) : html`<p class="muted">No work is planned yet.</p>`}`;
  }

  private renderReports(p: ProjectDetail): TemplateResult {
    const a = p.actions;
    const d01 = p.delivery_policy.decisions['PEX-D01'];
    return html`<div class="row"><h2 id="reports-h" tabindex="-1">Customer reports</h2><span class="spacer"></span>
        ${a.manage_snag ? html`<button class="btn" @click=${() => this.recordReport(p)}>Record a customer report</button>` : nothing}</div>
      <p class="small muted">Issues in the customer's own words. Each is reviewed: raised as a snag, linked to one, or declined with a reply the customer reads.
        A report waiting for review holds the handover.${d01 && !d01.decided ? ' Customers cannot report in the portal until owner decision PEX-D01 is recorded.' : ''}</p>
      ${p.customer_reports.length ? html`<ul class="attention" aria-label="Customer reports">${p.customer_reports.map((r) => html`<li class=${r.status === 'SUBMITTED' ? 'ACTION' : 'INFORMATIONAL'}>
        <div class="row"><span class="badge ${r.status === 'SUBMITTED' ? 'action' : r.status === 'ACCEPTED' ? 'ok' : 'info'}">${r.status === 'SUBMITTED' ? 'Waiting for review' : humanize(r.status)}</span>
          <span class="small muted">${r.channel === 'PORTAL' ? 'From the portal' : `Recorded by ${who(r.recorded_by)}`}, ${when(r.reported_on)}</span></div>
        <h3>Report ${r.report_no}${r.area ? `: ${r.area}` : ''}</h3>
        <p>${r.description}</p>
        ${r.status !== 'SUBMITTED' ? html`<dl class="meta"><dt>Reviewed</dt><dd>${who(r.triaged_by)}, ${when(r.triaged_on)}</dd>
          ${r.snag_id ? html`<dt>Snag</dt><dd>${(() => { const sn = p.snags.find((x) => x.id === r.snag_id); return sn ? `Snag ${sn.snag_no}: ${sn.customer_title}` : '—'; })()}</dd>` : nothing}
          ${r.decline_code ? html`<dt>Declined</dt><dd>${humanize(r.decline_code)}</dd>` : nothing}
          ${r.response ? html`<dt>Reply to the customer</dt><dd>${r.response}</dd>` : nothing}</dl>` : nothing}
        ${r.status === 'SUBMITTED' && a.manage_snag ? html`<div class="actions">
          <button class="btn small" @click=${() => this.triageReport(p, r, 'NEW_SNAG')} aria-label=${`Report ${r.report_no}: raise a snag`}>Raise a snag</button>
          ${p.snags.length ? html`<button class="btn small" @click=${() => this.triageReport(p, r, 'EXISTING_SNAG')} aria-label=${`Report ${r.report_no}: link to a snag`}>Link to a snag</button>` : nothing}
          <button class="btn small ghost" @click=${() => this.triageReport(p, r, 'DECLINED')} aria-label=${`Report ${r.report_no}: decline with a reply`}>Decline</button></div>` : nothing}</li>`)}</ul>`
        : html`<p class="muted">No customer report.</p>`}`;
  }

  private renderHandover(p: ProjectDetail): TemplateResult {
    const h = p.handover_readiness;
    const done = p.transitions.find((t) => t.kind === 'HANDOVER' && t.outcome === 'COMPLETED');
    return html`<h2 id="handover-h" tabindex="-1">Handover</h2>
      ${h.handed_over ? html`<vs-banner kind="success">Handed over ${when(p.handed_over_on)} by ${who(p.handed_over_by)}.</vs-banner>`
        : h.ready ? html`<vs-banner kind="success">Ready for handover: every prerequisite is satisfied.</vs-banner>`
          : html`<vs-banner kind="warning"><strong>Not ready for handover.</strong>${h.stage_reached === false ? ` The project is at ${p.stage.label}.` : ''}
            ${h.blockers.length ? html`<ul class="plain">${h.blockers.map((b) => html`<li>${b.message}</li>`)}</ul>` : nothing}</vs-banner>`}
      ${done?.handover ? html`<dl class="meta"><dt>Handover date</dt><dd>${formatDate(done.handover.handover_on)}</dd>
        <dt>Acknowledgement</dt><dd>${done.handover.acknowledgement_reference ?? '—'}</dd>
        <dt>Evidence</dt><dd>${done.handover.evidence_attachment_id ? 'Attached' : '—'}</dd>
        <dt>Observations</dt><dd>${done.handover.observations ?? '—'}</dd></dl>` : nothing}
      ${h.commercial_position ? html`<p class="small muted">Commercial position (for information): value ${h.commercial_position.value}, paid ${h.commercial_position.paid},
        outstanding ${h.commercial_position.outstanding}${h.commercial_position.lines_due ? `, ${h.commercial_position.lines_due} requested payment(s) unpaid` : ''}.</p>` : nothing}
      ${this.renderPackage(p)}
      ${p.readiness?.command === 'HANDOVER' && p.actions.complete_handover && !p.awaiting_approval ? html`<div><button class="btn primary" @click=${() => this.handover(p)}>Complete the handover</button></div>` : nothing}
      <p class="small muted">Warranty, service and final payment are separate workstreams; the handover creates none of them. Warranty terms are those of the accepted quotation.</p>`;
  }

  private renderPackage(p: ProjectDetail): TemplateResult {
    const pkg = [...p.handover_packages].reverse().find((x) => x.status !== 'SUPERSEDED');
    const c = pkg?.content;
    return html`<section class="stack" aria-labelledby="package-h"><div class="row"><h3 id="package-h">Handover package</h3><span class="spacer"></span>
        ${p.actions.prepare_handover_package && !p.awaiting_approval ? html`<button class="btn" ?disabled=${this.busy} @click=${() => this.preparePackage(p)}>${pkg ? 'Prepare again' : 'Prepare the package'}</button>` : nothing}</div>
      ${!pkg || !c ? html`<p class="muted">Not prepared. It is prepared in Ready for handover once every gate but the handover evidence is satisfied.</p>` : html`
        ${pkg.stale ? html`<vs-banner kind="warning">This package no longer matches the records (${humanize(pkg.stale)}). Prepare it again; the customer acknowledges the new one.</vs-banner>` : nothing}
        <dl class="meta"><dt>Package</dt><dd>${pkg.package_no} · ${humanize(pkg.status)} · prepared ${when(pkg.prepared_on)} by ${who(pkg.prepared_by)}</dd>
          <dt>Customer acknowledgement</dt><dd>${pkg.acknowledged_on ? `Acknowledged in the portal ${when(pkg.acknowledged_on)}` : 'Not acknowledged in the portal'}</dd>
          <dt>Work completed</dt><dd>${c.work.completed_count} (customer-visible: ${c.work.completed.map((w) => w.label).join(', ') || 'none'})</dd>
          <dt>Quality</dt><dd>${c.quality.checks_passed} passed, ${c.quality.corrected_after_failure} corrected after a failure, ${c.quality.failed} failed</dd>
          <dt>Snags</dt><dd>${c.snags.fixed_and_verified} fixed and verified, ${c.snags.closed_without_fix} closed without a fix, ${c.snags.open_non_blocking_count} open (non-blocking)</dd>
          <dt>Documents</dt><dd>None in the portal (no customer-visible document class is approved, CPP-D04)</dd>
          <dt>Warranty</dt><dd>As stated in accepted quotation ${c.warranty.quotation_number}</dd>
          <dt>Digest</dt><dd class="mono">${pkg.content_sha256}</dd></dl>`}
    </section>`;
  }

  private eventText(e: ProjectDetail['timeline'][number]): string {
    const stage = e.stage_code ? this.stageLabel(e.stage_code) : '';
    const states = e.from || e.to ? ` (${humanize(e.from) === '—' ? '' : `${humanize(e.from)} → `}${humanize(e.to)})` : '';
    return `${humanize(e.code)}${stage ? ` · ${stage}` : ''}${states}`;
  }

  private renderTimeline(p: ProjectDetail): TemplateResult {
    return html`<h2 id="timeline-h" tabindex="-1">Timeline</h2>
      <p class="small muted">Every event is recorded once and never changed.</p>
      <ol class="timeline" aria-label="Project timeline, oldest first">${p.timeline.map((e) => html`<li>
        <strong>${this.eventText(e)}</strong><div class="small muted">${who(e.by)}, ${when(e.on)}</div></li>`)}</ol>`;
  }

  private renderHistory(p: ProjectDetail): TemplateResult {
    return html`<h2 id="history-h" tabindex="-1">Audit and history</h2>
      <h3>Transition requests</h3>
      ${p.transitions.length ? html`<div class="table-wrap" tabindex="0" role="region" aria-label="Transition requests, scrolls sideways on small screens"><table class="cards">
        <caption class="sr-only">Every transition request, refused ones included</caption>
        <thead><tr><th scope="col">Move</th><th scope="col">Outcome</th><th scope="col">Requested</th><th scope="col">Decided</th><th scope="col">What was missing</th></tr></thead>
        <tbody>${p.transitions.map((t) => html`<tr><td data-label="Move">${this.stageLabel(t.from_stage)} → ${this.stageLabel(t.to_stage)}</td>
          <td data-label="Outcome"><span class="badge ${t.outcome === 'COMPLETED' ? 'ok' : t.outcome === 'REFUSED' || t.outcome === 'REJECTED' ? 'gating' : 'info'}">${OUTCOME[t.outcome]}</span></td>
          <td data-label="Requested">${who(t.requested_by)}, ${when(t.requested_on)}</td><td data-label="Decided">${t.decided_by ? `${who(t.decided_by)}, ${when(t.decided_on)}` : '—'}</td>
          <td data-label="What was missing">${t.blockers.length ? html`<ul class="plain">${t.blockers.map((b) => html`<li>${b.message}</li>`)}</ul>` : '—'}</td></tr>`)}</tbody></table></div>`
        : html`<p class="muted">No transition was requested yet.</p>`}
      ${p.actions.view_audit ? html`<h3>Record changes</h3>${this.history === null ? html`<vs-skeleton rows="4"></vs-skeleton>` : html`<div class="table-wrap" tabindex="0" role="region"
          aria-label="Audit entries, scrolls sideways on small screens"><table class="cards"><caption class="sr-only">Audit entries of this project's records</caption>
          <thead><tr><th scope="col">Record</th><th scope="col">Action</th><th scope="col">Fields changed</th><th scope="col">By</th><th scope="col">When</th></tr></thead>
          <tbody>${this.history.map((h) => html`<tr><td data-label="Record">${humanize(h.entity_type)}</td><td data-label="Action">${humanize(h.action)}</td>
            <td data-label="Fields changed">${h.changed_fields.map(humanize).join(', ') || '—'}</td><td data-label="By">${who(h.by)}</td><td data-label="When">${when(h.on)}</td></tr>`)}</tbody></table></div>`}`
        : html`<p class="small muted">The record-level audit history needs the project history capability.</p>`}`;
  }

  private renderRefusal(): TemplateResult | typeof nothing {
    const t = this.refusal;
    if (!t) return nothing;
    return html`<section class="card stack" aria-labelledby="refusal-h"><h2 id="refusal-h" tabindex="-1">The move to ${this.stageLabel(t.to_stage)} was refused</h2>
      <p>The request is recorded. Clear these first:</p>
      <ul class="plain">${t.blockers.map((b) => html`<li>${b.message}${b.responsible_party ? html` <span class="muted">(${party(b.responsible_party)})</span>` : nothing}</li>`)}</ul>
      <div><button class="btn small" @click=${() => (this.refusal = null)}>Dismiss</button></div></section>`;
  }

  private renderTab(p: ProjectDetail): TemplateResult {
    switch (this.tab) {
      case 'timeline': return this.renderTimeline(p);
      case 'stage': return this.renderStage(p);
      case 'checklist': return this.renderChecklist(p);
      case 'work': return this.renderWork(p);
      case 'reports': return this.renderReports(p);
      case 'blockers': return this.renderBlockers(p);
      case 'milestones': return this.renderMilestones(p);
      case 'baseline': return this.renderBaseline(p);
      case 'site': return this.renderSite(p);
      case 'quality': return this.renderQuality(p);
      case 'handover': return this.renderHandover(p);
      case 'history': return this.renderHistory(p);
      default: return this.renderOverview(p);
    }
  }

  override render() {
    if (this.missing) {
      const off = this.me?.features && (this.me.features as Record<string, boolean>).project_lifecycle === false;
      return html`<div class="page"><h1 class="title" id="page-title" tabindex="-1">Project</h1>
        <vs-empty-state heading=${off ? 'Project lifecycle is not enabled in this environment.' : 'This project does not exist or is not on your team.'}></vs-empty-state></div>`;
    }
    const p = this.project;
    return html`<div class="page">
      <div class="row"><a class="btn ghost" href="/projects" @click=${(e: Event) => { e.preventDefault(); navigate('/projects'); }}>← Projects</a></div>
      <div class="page-head"><div><p class="eyebrow">Project</p><h1 class="title" id="page-title" tabindex="-1">${p ? `${p.project_number} · ${p.stage.label}` : 'Project'}</h1></div></div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${this.conflict ? html`<vs-banner kind="danger"><span id="conflict" tabindex="-1">This project changed since you opened it. Nothing was overwritten.</span>
        <button class="btn small" @click=${() => this.load()}>Reload the project</button></vs-banner>` : nothing}
      ${!p ? html`<vs-skeleton rows="8"></vs-skeleton>` : html`
        ${p.lifecycle.status !== 'APPROVED' ? html`<vs-banner kind="warning">Lifecycle ${p.lifecycle.version} is a proposal: high-risk moves stay refused until the owner records the lifecycle policy.</vs-banner>` : nothing}
        ${this.renderHero(p)}
        ${this.renderRefusal()}
        <vs-tabs label="Project sections" .tabs=${TABS.map(([id, label]) => ({ id, label }))} selected=${this.tab}
          @tab-change=${(e: CustomEvent<Tab>) => this.setTab(e.detail)}><div class="stack">${this.renderTab(p)}</div></vs-tabs>`}
      ${this.renderForm()}
      <div class="sr-only" role="status" aria-live="polite">${this.announcement}</div>
    </div>`;
  }
}
customElements.define('vs-project-page', VsProjectPage);
