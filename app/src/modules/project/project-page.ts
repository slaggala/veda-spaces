import { css, html, nothing, type TemplateResult } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatDate, formatINR, formatRelative, humanize } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import {
  projectApi, type Attention, type Blocker, type Candidate, type ChecklistItem, type GateBlocker, type HistoryRow, type Milestone,
  type ProjectDetail, type ReadinessItem, type Snag, type TeamMember, type Transition, type TransitionResult, type Vocabulary,
} from './api.js';
import { badgeStyles, CLASS_LABEL, OUTCOME, party, SEVERITY, when, who } from './labels.js';

type Tab = 'overview' | 'timeline' | 'stage' | 'checklist' | 'blockers' | 'milestones' | 'baseline' | 'site' | 'quality' | 'handover' | 'history';
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
  ['blockers', 'Blockers'], ['milestones', 'Milestones'], ['baseline', 'Commercial baseline'], ['site', 'Site readiness'],
  ['quality', 'Quality and snags'], ['handover', 'Handover'], ['history', 'Audit and history']];
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
          hint: 'For example the number of the signed handover sheet.' },
        { name: 'evidence_attachment_id', label: 'Handover evidence', kind: 'select', hint: 'A scanned photo already attached to this property.',
          options: p.evidence_options.map((o) => [o.id, `${humanize(o.category)} · ${humanize(o.attached_to)} · ${o.uploaded_on ? formatRelative(o.uploaded_on) : ''}`]) },
        { name: 'observations', label: 'Non-blocking observations (internal)', kind: 'textarea', maxLength: 2000, classification: 'INTERNAL_ONLY' },
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
        { name: 'note', label: 'Note (internal)', kind: 'textarea', classification: 'INTERNAL_ONLY' },
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
        { name: 'title', label: 'Title (internal)', kind: 'text', required: true, minLength: 3, maxLength: 160, classification: 'INTERNAL_ONLY' },
        { name: 'responsible_party', label: 'Who needs to act', kind: 'select', required: true, options: (v?.responsible_parties ?? []).map((c) => [c, party(c)]) },
        { name: 'customer_action', label: 'What the customer needs to do (when the customer acts)', kind: 'textarea', maxLength: 300,
          classification: 'CUSTOMER_ACTION', hint: 'Customer-safe words: it may be shown to the customer in a future portal.' },
        { name: 'description', label: 'Details (internal)', kind: 'textarea', maxLength: 2000, classification: 'INTERNAL_ONLY' },
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
      intro: 'A planned date is an internal plan, never a commitment to the customer. Record a customer-promised date only if it was already promised.',
      fields: [
        { name: 'milestone_code', label: 'Type', kind: 'select', required: true, options: opt(this.vocab?.milestone_types ?? []) },
        { name: 'label', label: 'Label (internal)', kind: 'text', required: true, maxLength: 120 },
        { name: 'stage_code', label: 'Stage it belongs to', kind: 'select', required: true, value: p.stage.code,
          options: p.stages.filter((s) => !s.terminal && s.status !== 'COMPLETED').map((s) => [s.code, s.label]) },
        { name: 'planned_date', label: 'Planned date (internal)', kind: 'date' },
        { name: 'customer_promised_date', label: 'Customer-promised date (only if already promised)', kind: 'date' },
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
        { name: 'customer_promised_date', label: 'Customer-promised date (only if already promised)', kind: 'date', value: m.customer_promised_date },
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
        { name: 'action', label: 'Action needed (internal)', kind: 'textarea', maxLength: 500, value: r.action, classification: 'INTERNAL_ONLY' },
        { name: 'customer_action', label: 'What the customer needs to do', kind: 'textarea', maxLength: 300, value: r.customer_action,
          classification: 'CUSTOMER_ACTION', hint: 'Customer-safe words: it may be shown to the customer in a future portal.' },
        { name: 'due_date', label: 'Due date', kind: 'date', value: r.due_date },
        { name: 'note', label: 'Note (internal)', kind: 'textarea', value: r.note, classification: 'INTERNAL_ONLY' },
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

  private recordQc(p: ProjectDetail, category?: string, recheckOf?: string) {
    this.open({ title: recheckOf ? `Recheck: ${humanize(category)}` : 'Record a quality-check result', submit: 'Record', done: 'Quality check recorded.',
      fields: [
        { name: 'category', label: 'Category', kind: 'select', required: true, value: category ?? null, options: opt(this.vocab?.qc_categories ?? []) },
        { name: 'result', label: 'Result', kind: 'select', required: true, options: opt(this.vocab?.qc_results ?? []) },
        { name: 'observation', label: 'Observation (required for a failure; internal)', kind: 'textarea', classification: 'INTERNAL_ONLY' },
        { name: 'space_id', label: 'Space', kind: 'select', options: p.spaces.map((s) => [s.id, s.label]) },
        ...this.evidenceFields(p),
        ...(recheckOf ? [{ name: 'recheck_of_id', label: 'Recheck of', kind: 'select' as const, required: true, value: recheckOf, options: [[recheckOf, 'The failed check']] as [string, string][] }] : []),
      ],
      run: (b) => projectApi.recordQc(p, b) });
  }

  private raiseSnag(p: ProjectDetail, qcCheckId?: string) {
    this.open({ title: 'Raise a snag', submit: 'Raise', done: 'Snag raised.',
      fields: [
        { name: 'category', label: 'Category', kind: 'select', required: true, options: opt(this.vocab?.snag_categories ?? []) },
        { name: 'customer_title', label: 'Title (customer-safe words)', kind: 'text', required: true, minLength: 3, maxLength: 160,
          classification: 'POTENTIALLY_CUSTOMER_SAFE' },
        { name: 'description', label: 'Details (internal)', kind: 'textarea', maxLength: 2000, classification: 'INTERNAL_ONLY' },
        { name: 'space_id', label: 'Space', kind: 'select', options: p.spaces.map((s) => [s.id, s.label]) },
        { name: 'item_reference', label: 'Item or unit (optional)', kind: 'text', maxLength: 200 },
        { name: 'is_blocking', label: 'Blocks the handover until resolved', kind: 'checkbox', value: true },
        { name: 'owner_user_id', label: 'Owner', kind: 'select', options: p.team.filter((m) => m.active && m.user).map((m) => [m.user!.id, who(m.user)]) },
        { name: 'responsible_party', label: 'Who needs to act', kind: 'select', value: 'VEDA', options: (this.vocab?.responsible_parties ?? []).map((c) => [c, party(c)]) },
        { name: 'target_date', label: 'Target date', kind: 'date' },
        ...(qcCheckId ? [{ name: 'qc_check_id', label: 'From quality check', kind: 'select' as const, required: true, value: qcCheckId, options: [[qcCheckId, 'The failed check']] as [string, string][] }] : []),
        ...this.evidenceFields(p),
      ],
      run: (b) => projectApi.raiseSnag(p, b) });
  }

  private snagStatus(p: ProjectDetail, s: Snag, status: string) {
    const needsNote = status === 'RESOLVED' || (status === 'CLOSED' && s.status !== 'RESOLVED');
    this.open({ title: `Snag ${s.snag_no}: ${humanize(status)}`, submit: humanize(status), done: `Snag ${s.snag_no}: ${humanize(status).toLowerCase()}.`,
      fields: [{ name: 'note', label: status === 'RESOLVED' ? 'What the recheck found' : 'Note', kind: 'textarea', ...(needsNote ? { required: true, ...REASON } : {}) }],
      run: (b) => projectApi.snagStatus(p, s, { status, ...b }) });
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
      ${active.length ? html`<ul class="plain">${active.map((m) => html`<li>${humanize(m.responsibility)}: <strong>${who(m.user)}</strong>
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
        ${b.customer_action ? html`<dt>Customer action</dt><dd>${b.customer_action} <span class="class-tag">(${CLASS_LABEL.CUSTOMER_ACTION})</span></dd>` : nothing}
        ${b.description ? html`<dt>Details</dt><dd>${b.description} <span class="class-tag">(${CLASS_LABEL.INTERNAL_ONLY})</span></dd>` : nothing}
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
    return html`<div class="row"><h2 id="quality-h" tabindex="-1">Quality check</h2><span class="spacer"></span>
        ${a.manage_qc ? html`<button class="btn" @click=${() => this.recordQc(p)}>Record a result</button>` : nothing}</div>
      <div class="table-wrap" tabindex="0" role="region" aria-label="Quality checks, scrolls sideways on small screens"><table class="cards">
        <caption class="sr-only">Latest result per quality-check category</caption>
        <thead><tr><th scope="col">Category</th><th scope="col">Required</th><th scope="col">Latest result</th><th scope="col">Observation</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>${p.qc.categories.map((c) => html`<tr><td data-label="Category">${humanize(c.category)}</td><td data-label="Required">${c.required ? 'Yes' : 'No'}</td>
          <td data-label="Latest result">${c.latest ? html`<span class="badge ${c.latest.result === 'PASS' ? 'ok' : c.latest.result === 'FAIL' ? 'gating' : 'info'}">${humanize(c.latest.result)}</span>
            <span class="small muted">${who(c.latest.checked_by)}, ${when(c.latest.checked_on)}</span>` : html`<span class="muted">No result</span>`}</td>
          <td data-label="Observation">${c.latest?.observation ?? '—'}</td>
          <td data-label="Actions">${c.latest?.result === 'FAIL' && a.manage_qc ? html`<div class="actions">
            <button class="btn small" @click=${() => this.recordQc(p, c.category, c.latest!.id)} aria-label=${`Recheck ${humanize(c.category)}`}>Recheck</button>
            ${a.manage_snag ? html`<button class="btn small" @click=${() => this.raiseSnag(p, c.latest!.id)} aria-label=${`Raise a snag for ${humanize(c.category)}`}>Raise a snag</button>` : nothing}</div>` : '—'}</td></tr>`)}</tbody></table></div>
      <div class="row"><h2 id="snags-h">Snags</h2><span class="spacer"></span>${a.manage_snag ? html`<button class="btn" @click=${() => this.raiseSnag(p)}>Raise a snag</button>` : nothing}</div>
      ${p.snags.length ? html`<ul class="attention" aria-label="Snags">${p.snags.map((s) => html`<li class=${s.is_blocking && ['OPEN', 'IN_PROGRESS', 'READY_FOR_RECHECK'].includes(s.status) ? 'GATING' : 'INFORMATIONAL'}>
        <div class="row"><span class="badge ${['RESOLVED', 'CLOSED'].includes(s.status) ? 'ok' : s.is_blocking ? 'gating' : 'info'}">${humanize(s.status)}</span>
          ${s.is_blocking ? html`<span class="small">Blocks the handover</span>` : html`<span class="small muted">Does not block the handover</span>`}</div>
        <h3>Snag ${s.snag_no}: ${s.customer_title}</h3>
        <dl class="meta"><dt>Category</dt><dd>${humanize(s.category)}</dd>${s.space ? html`<dt>Space</dt><dd>${s.space}</dd>` : nothing}
          <dt>Owner</dt><dd>${who(s.owner, 'Not assigned')} · ${party(s.responsible_party)}</dd>
          ${s.description ? html`<dt>Details</dt><dd>${s.description}</dd>` : nothing}
          ${s.resolution_note ? html`<dt>Resolution</dt><dd>${s.resolution_note}</dd>` : nothing}</dl>
        ${a.manage_snag && s.allowed_next.length ? html`<div class="actions">${s.allowed_next.map((st) => html`<button class="btn small" @click=${() => this.snagStatus(p, s, st)}
          aria-label=${`Snag ${s.snag_no}: ${humanize(st)}`}>${humanize(st)}</button>`)}</div>` : nothing}</li>`)}</ul>` : html`<p class="muted">No snags.</p>`}`;
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
      ${p.readiness?.command === 'HANDOVER' && p.actions.complete_handover && !p.awaiting_approval ? html`<div><button class="btn primary" @click=${() => this.handover(p)}>Complete the handover</button></div>` : nothing}
      <p class="small muted">Warranty, service and final payment are separate workstreams; the handover creates none of them.</p>`;
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
