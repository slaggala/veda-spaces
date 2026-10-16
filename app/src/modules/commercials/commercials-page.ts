import { css, html, nothing, type TemplateResult } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatAbsolute, formatDate, humanize } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import '../../design-system/components.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';
import {
  commercialsApi, download, newIdempotencyKey, paiseToRupees, REVERSAL_TEXT, rupeesToPaise,
  type Detail, type DocumentModel, type HistoryRow, type InstalmentInput, type Invoice, type Line, type Payment,
} from './api.js';
import { commercialStyles, stateBadge } from './ui.js';

type Tab = 'overview' | 'schedule' | 'payments' | 'invoices' | 'history';
interface Field { name: string; label: string; kind: 'text' | 'textarea' | 'select' | 'date' | 'money'; required?: boolean; hint?: string;
  options?: [string, string][]; value?: string; minLength?: number; maxLength?: number }
interface Form { title: string; intro?: TemplateResult | string; fields: Field[]; submit: string; danger?: boolean; done: string;
  confirm?: (body: Record<string, string>) => TemplateResult; run: (body: Record<string, string>) => Promise<unknown> }
interface Row { label: string; when: string; amount: string; requested: boolean; due_on: string }
interface Doc { title: string; status: string; model: DocumentModel; html: string | null; filename: string | null }

const TABS: [Tab, string][] = [['overview', 'Overview'], ['schedule', 'Payment schedule'], ['payments', 'Payments and receipts'],
  ['invoices', 'Invoices'], ['history', 'History']];
const who = (p: { display_name: string | null } | null | undefined) => p?.display_name ?? '—';
const day = (d: string | null | undefined) => (d ? formatDate(d) : '—');

/**
 * /commercials/:id — one project's commercial record: the value agreed (accepted quotation and variations), what has been
 * paid and what is outstanding, the payment schedule, recorded payments with their receipts, invoices, and the history.
 * Every figure comes from the server's one calculation; every command goes to the server, which checks the capability in
 * this customer's scope, locks the record and re-reads it. A payment is staff's record of money received outside Veda
 * Spaces' systems: never a bank confirmation, and never collected here.
 */
export class VsCommercialsPage extends SessionElement {
  static override properties = {
    location: { attribute: false }, account: { state: true }, tab: { state: true }, form: { state: true }, rows: { state: true },
    doc: { state: true }, formErrors: { state: true }, problem: { state: true }, conflict: { state: true }, busy: { state: true },
    announcement: { state: true }, history: { state: true }, missing: { state: true }, confirming: { state: true },
  };
  declare location: { params: Record<string, string> } | undefined;
  declare account: Detail | null;
  declare tab: Tab;
  declare form: Form | null;
  declare rows: Row[] | null;
  declare doc: Doc | null;
  declare formErrors: { field: string; message: string }[];
  declare problem: ApiProblem | null;
  declare conflict: boolean;
  declare busy: boolean;
  declare announcement: string;
  declare history: HistoryRow[] | null;
  declare missing: boolean;
  /** The values of a form awaiting the second, confirming click (payments and reversals). */
  declare confirming: Record<string, string> | null;
  private key = '';
  private scheduleReason = '';

  static override styles = [...shared, pageStyles, tableStyles, commercialStyles, css`
    .actions { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .btn.small { min-height: var(--vs-target); }
    td .btn { white-space: nowrap; }
    td, th { overflow-wrap: anywhere; }
    .rows { display: grid; gap: var(--vs-space-3); }
    .row-edit { display: grid; gap: var(--vs-space-2); grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr)); align-items: end;
      border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); padding: var(--vs-space-3); }
    .confirm { border: 1px solid var(--vs-copper); border-radius: var(--vs-radius-card); padding: var(--vs-space-3) var(--vs-space-4); }
    dl.meta { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 4px var(--vs-space-3); margin: 0; font-size: 14px; }
    dl.meta dt { color: var(--vs-ink-muted); } dl.meta dd { margin: 0; overflow-wrap: anywhere; }
    code { overflow-wrap: anywhere; font-size: 12px; }
  `];

  constructor() {
    super();
    this.account = null;
    this.tab = 'overview';
    this.form = null;
    this.rows = null;
    this.doc = null;
    this.formErrors = [];
    this.problem = null;
    this.conflict = false;
    this.busy = false;
    this.announcement = '';
    this.history = null;
    this.missing = false;
    this.confirming = null;
  }

  private get routeId(): string { return this.location?.params?.id ?? window.location.pathname.split('/').pop() ?? ''; }

  override connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  private async load() {
    this.problem = null;
    try {
      this.account = (await commercialsApi.get(this.routeId)).data;
      this.conflict = false;
      this.history = null;
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 404) this.missing = true;
      else this.problem = p;
    }
  }

  private async focusOn(selector: string) {
    await this.updateComplete;
    (this.renderRoot.querySelector(selector) as HTMLElement | null)?.focus();
  }

  private async setTab(tab: Tab) {
    this.tab = tab;
    if (tab === 'history' && this.history === null && this.account?.capabilities.view_audit) {
      try { this.history = (await commercialsApi.history(this.account.id)).data; } catch (e) { this.problem = e as ApiProblem; }
    }
  }

  // --- the generic form dialog ----------------------------------------------------------------------------------------
  private open(form: Form) {
    this.form = form;
    this.formErrors = [];
    this.confirming = null;
    this.problem = null;
    this.key = newIdempotencyKey();
  }

  private collect(el: HTMLFormElement): Record<string, string> {
    const out: Record<string, string> = {};
    for (const f of this.form?.fields ?? []) {
      const input = el.elements.namedItem(f.name) as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | null;
      if (input && input.value.trim() !== '') out[f.name] = input.value.trim();
    }
    return out;
  }

  private async fail(err: unknown) {
    const p = err as ApiProblem;
    if (p.code === 'VERSION_CONFLICT' || p.code === 'PRECONDITION_REQUIRED') {
      this.form = null;
      this.rows = null;
      this.conflict = true;
      await this.focusOn('#conflict');
      return;
    }
    this.formErrors = p.errors.length ? p.errors.map((x) => ({ field: x.field, message: x.message ?? humanize(x.code) }))
      : [{ field: '', message: p.detail || p.title }];
    await this.updateComplete;
    (this.renderRoot.querySelector('vs-dialog vs-error-summary') as unknown as { focusSummary?: () => void } | null)?.focusSummary?.();
  }

  private async submit(e: Event) {
    e.preventDefault();
    const form = this.form;
    if (!form || this.busy) return;
    const body = this.confirming ?? this.collect(e.target as HTMLFormElement);
    const errors = form.fields.flatMap((f) => {
      const v = body[f.name] ?? '';
      if (f.required && !v) return [{ field: f.name, message: `${f.label}: required.` }];
      if (f.minLength && v && v.length < f.minLength) return [{ field: f.name, message: `${f.label}: at least ${f.minLength} characters.` }];
      if (f.kind === 'money' && v && rupeesToPaise(v) === null) return [{ field: f.name, message: `${f.label}: an amount in rupees, for example 25000 or 25000.50.` }];
      return [];
    });
    if (errors.length) {
      this.formErrors = errors;
      await this.updateComplete;
      (this.renderRoot.querySelector('vs-dialog vs-error-summary') as unknown as { focusSummary?: () => void } | null)?.focusSummary?.();
      return;
    }
    if (form.confirm && !this.confirming) { // a financial record: show exactly what will be recorded, then confirm
      this.confirming = body;
      this.formErrors = [];
      await this.focusOn('#confirm-h');
      return;
    }
    this.busy = true;
    try {
      const r = (await form.run(body)) as { data: Detail };
      if (r?.data && 'position' in r.data) this.account = r.data;
      this.form = null;
      this.confirming = null;
      this.history = null;
      this.announcement = form.done;
      await this.focusOn('#page-title');
    } catch (err) {
      this.confirming = null;
      await this.fail(err);
    } finally { this.busy = false; }
  }

  private renderField(f: Field): TemplateResult {
    const err = this.formErrors.find((x) => x.field === f.name)?.message;
    const id = `f-${f.name}`;
    const described = [f.hint ? `${id}-hint` : '', err ? `${id}-err` : ''].filter(Boolean).join(' ') || nothing;
    const control = f.kind === 'textarea'
      ? html`<textarea id=${id} name=${f.name} maxlength=${f.maxLength ?? 1000} aria-invalid=${err ? 'true' : 'false'} aria-describedby=${described}
          .value=${f.value ?? ''}></textarea>`
      : f.kind === 'select'
        ? html`<select id=${id} name=${f.name} aria-invalid=${err ? 'true' : 'false'} aria-describedby=${described}>
            ${(f.options ?? []).map(([v, l]) => html`<option value=${v} ?selected=${f.value === v}>${l}</option>`)}</select>`
        : html`<input id=${id} name=${f.name} type=${f.kind === 'date' ? 'date' : 'text'} inputmode=${f.kind === 'money' ? 'decimal' : nothing}
            maxlength=${f.maxLength ?? 200} aria-invalid=${err ? 'true' : 'false'} aria-describedby=${described} .value=${f.value ?? ''}>`;
    return html`<label class="field"><span class="label">${f.label}${f.required ? ' (required)' : ''}</span>${control}
      ${f.hint ? html`<span class="hint" id=${`${id}-hint`}>${f.hint}</span>` : nothing}
      ${err ? html`<span class="error" id=${`${id}-err`}>${err}</span>` : nothing}</label>`;
  }

  private renderForm(): TemplateResult {
    const f = this.form;
    const confirming = !!(f && this.confirming && f.confirm);
    return html`<vs-dialog heading=${f?.title ?? ''} wide ?open=${!!f} @close=${() => { this.form = null; this.confirming = null; }}
      @focus-field=${(e: CustomEvent<string>) => (this.renderRoot.querySelector(`#f-${e.detail}`) as HTMLElement | null)?.focus()}>
      ${f ? html`<form id="pcm-form" class="stack" novalidate @submit=${(e: Event) => this.submit(e)}>
        ${f.intro ? html`<p>${f.intro}</p>` : nothing}
        <vs-error-summary .errors=${this.formErrors}></vs-error-summary>
        ${confirming ? html`<div class="confirm stack"><h3 id="confirm-h" tabindex="-1">Check before you confirm</h3>${f.confirm!(this.confirming!)}</div>`
          : f.fields.map((x) => this.renderField(x))}
      </form>` : nothing}
      <div slot="actions">
        ${confirming ? html`<button class="btn" @click=${() => { this.confirming = null; }}>Back</button>`
          : html`<button class="btn" @click=${() => { this.form = null; }}>Cancel</button>`}
        <button class="btn ${f?.danger ? 'danger' : 'primary'}" type="submit" form="pcm-form" ?disabled=${this.busy}>
          ${confirming ? `Confirm: ${f?.submit ?? ''}` : f?.confirm ? 'Review' : f?.submit ?? 'Save'}</button></div>
    </vs-dialog>`;
  }

  // --- commands -------------------------------------------------------------------------------------------------------
  private recordPayment(a: Detail) {
    this.open({
      title: 'Record a payment', submit: 'Record payment', done: 'Payment recorded; its receipt was issued.',
      intro: html`Record a payment only once the money has reached Veda Spaces. This records what staff confirmed; it is not a bank or
        payment-provider confirmation, and nothing is collected here. Outstanding now: <strong>${a.position.outstanding}</strong>.`,
      fields: [
        { name: 'amount', label: 'Amount received (₹)', kind: 'money', required: true, hint: 'For example 25000 or 25000.50. It cannot exceed the outstanding balance.' },
        { name: 'received_on', label: 'Date received', kind: 'date', required: true, value: a.position.as_of },
        { name: 'method_code', label: 'How it was paid', kind: 'select', required: true, options: a.methods.map((m) => [m.code, m.label]), value: 'BANK_TRANSFER' },
        { name: 'external_reference', label: 'Reference (UTR, cheque number)', kind: 'text', maxLength: 100, hint: 'Shown to the customer and on the receipt.' },
        { name: 'customer_note', label: 'Note for the customer', kind: 'text', maxLength: 300, hint: 'Shown to the customer and on the receipt.' },
        { name: 'internal_note', label: 'Staff note', kind: 'textarea', maxLength: 1000, hint: 'Staff only. Never shown to the customer.' },
      ],
      confirm: (b) => html`<dl class="meta"><dt>Amount</dt><dd class="strong">₹ ${paiseToRupees(rupeesToPaise(b.amount) ?? 0)}</dd>
        <dt>Received</dt><dd>${day(b.received_on)}</dd><dt>Method</dt><dd>${a.methods.find((m) => m.code === b.method_code)?.label}</dd>
        <dt>Reference</dt><dd>${b.external_reference ?? '—'}</dd></dl><p class="small muted">A receipt is issued at once and the customer is told it is in their portal.</p>`,
      run: (b) => commercialsApi.pay(a, {
        amount_minor: rupeesToPaise(b.amount), received_on: b.received_on, method_code: b.method_code,
        ...(b.external_reference ? { external_reference: b.external_reference } : {}),
        ...(b.customer_note ? { customer_note: b.customer_note } : {}), ...(b.internal_note ? { internal_note: b.internal_note } : {}),
      }, this.key),
    });
  }

  private reversePayment(a: Detail, p: Payment) {
    this.open({
      title: `Reverse the payment of ${p.amount}`, submit: 'Reverse payment', danger: true, done: 'Payment reversed; its receipt is cancelled.',
      intro: 'A reversal corrects a payment that was recorded in error. The payment stays in the history as reversed and its receipt is shown as cancelled. You cannot reverse a payment you recorded.',
      fields: [
        { name: 'reason_code', label: 'Why', kind: 'select', required: true, options: a.reversal_reasons.map((r) => [r, REVERSAL_TEXT[r] ?? humanize(r)]) },
        { name: 'note', label: 'Staff note', kind: 'textarea', maxLength: 500, hint: 'Required for "Other reason". Staff only.' },
      ],
      confirm: (b) => html`<p>Reverse <strong>${p.amount}</strong> received on ${day(p.received_on)} (${p.method}): ${REVERSAL_TEXT[b.reason_code]}.</p>`,
      run: (b) => commercialsApi.reverse(a, p.id, { reason_code: b.reason_code, ...(b.note ? { note: b.note } : {}) }),
    });
  }

  private requestInstalment(a: Detail, l: Line) {
    this.open({
      title: `Ask for ${l.label}`, submit: 'Ask the customer', done: `${l.label} requested.`,
      intro: `The customer's portal will show ${l.remaining} as due. Leave the date empty if no date was agreed: no date is ever assumed.`,
      fields: [{ name: 'due_on', label: 'Due by (optional)', kind: 'date', value: l.due_on ?? '' }],
      run: (b) => commercialsApi.request(a, l.id, b.due_on ?? null),
    });
  }

  private draftInvoice(a: Detail, l: Line) {
    this.open({
      title: `Invoice ${l.label}`, submit: 'Create draft', done: 'Draft invoice created. Review it before issuing.',
      intro: `A draft is never shown to the customer. It requests this instalment (${l.amount}${l.gst_included ? `, including GST of ${l.gst_included}` : ''}).`,
      fields: [{ name: 'due_on', label: 'Due by (optional)', kind: 'date', value: l.due_on ?? '' },
        { name: 'customer_note', label: 'Note on the invoice', kind: 'text', maxLength: 500 }],
      run: async (b) => {
        await commercialsApi.draft(a, { instalment_id: l.id, ...(b.due_on ? { due_on: b.due_on } : {}),
          ...(b.customer_note ? { customer_note: b.customer_note } : {}) }, this.key);
        const fresh = await commercialsApi.get(a.id);
        this.tab = 'invoices';
        return fresh;
      },
    });
  }

  private cancelInvoice(a: Detail, inv: Invoice) {
    this.open({
      title: `Cancel invoice ${inv.number}`, submit: 'Cancel invoice', danger: true, done: 'Invoice cancelled. The document stays, marked cancelled.',
      fields: [{ name: 'reason', label: 'Reason (staff only)', kind: 'textarea', required: true, minLength: 5, maxLength: 500 }],
      run: async (b) => { await commercialsApi.cancel(inv, b.reason); return commercialsApi.get(a.id); },
    });
  }

  private async issueInvoice(a: Detail, inv: Invoice) {
    this.busy = true;
    try {
      await commercialsApi.issue(inv);
      this.account = (await commercialsApi.get(a.id)).data;
      this.announcement = 'Invoice issued; the customer is told it is in their portal.';
    } catch (e) {
      const p = e as ApiProblem;
      if (p.code === 'VERSION_CONFLICT') this.conflict = true;
      else this.problem = p;
    } finally { this.busy = false; }
  }

  private async abandonInvoice(inv: Invoice) {
    this.busy = true;
    try {
      this.account = (await commercialsApi.abandon(inv)).data;
      this.announcement = 'Draft discarded.';
    } catch (e) { this.problem = e as ApiProblem; } finally { this.busy = false; }
  }

  private async showInvoice(inv: Invoice) {
    try {
      const v = (await commercialsApi.invoice(inv.id)).data;
      const model = v.document ?? v.preview?.document;
      if (!model) { this.announcement = 'This draft no longer matches the current schedule.'; return; }
      this.doc = { title: v.number ? `Invoice ${v.number}` : 'Draft invoice (not a customer document)', status: v.status, model,
        html: v.html ?? v.preview?.html ?? null, filename: v.filename ?? null };
    } catch (e) { this.problem = e as ApiProblem; }
  }

  private async showReceipt(id: string) {
    try {
      const r = (await commercialsApi.receipt(id)).data;
      this.doc = { title: `Receipt ${r.number}`, status: r.status, model: r.document, html: r.html, filename: r.filename };
    } catch (e) { this.problem = e as ApiProblem; }
  }

  // --- schedule editor ------------------------------------------------------------------------------------------------
  private editSchedule(a: Detail) {
    const rows: Row[] = (a.schedule?.lines ?? []).map((l) => ({ label: l.label, when: l.when, amount: paiseToRupees(l.amount_minor),
      requested: !!l.requested_on, due_on: l.due_on ?? '' }));
    if (a.position.unscheduled_minor > 0) rows.push({ label: '', when: '', amount: paiseToRupees(a.position.unscheduled_minor), requested: false, due_on: '' });
    if (!rows.length) rows.push({ label: '', when: '', amount: paiseToRupees(a.position.value_minor), requested: false, due_on: '' });
    this.rows = rows;
    this.scheduleReason = '';
    this.formErrors = [];
  }

  private async saveSchedule(e: Event) {
    e.preventDefault();
    const a = this.account;
    if (!a || !this.rows || this.busy) return;
    const errors: { field: string; message: string }[] = [];
    const items: InstalmentInput[] = this.rows.map((r, i) => {
      const minor = rupeesToPaise(r.amount);
      if (!r.label.trim()) errors.push({ field: `row-${i}-label`, message: `Instalment ${i + 1}: what it is for is required.` });
      if (!r.when.trim()) errors.push({ field: `row-${i}-when`, message: `Instalment ${i + 1}: when it is due is required.` });
      if (minor === null || minor <= 0) errors.push({ field: `row-${i}-amount`, message: `Instalment ${i + 1}: an amount in rupees above zero.` });
      return { label: r.label.trim(), when: r.when.trim(), amount_minor: minor ?? 0, requested: r.requested, due_on: r.due_on || null };
    });
    if (this.scheduleReason.trim().length < 5) errors.push({ field: 'reason', message: 'Reason: at least 5 characters.' });
    if (errors.length) {
      this.formErrors = errors;
      await this.updateComplete;
      (this.renderRoot.querySelector('vs-dialog vs-error-summary') as unknown as { focusSummary?: () => void } | null)?.focusSummary?.();
      return;
    }
    this.busy = true;
    try {
      this.account = (await commercialsApi.revise(a, this.scheduleReason.trim(), items)).data;
      this.rows = null;
      this.announcement = 'Payment schedule revised.';
      await this.focusOn('#page-title');
    } catch (err) { await this.fail(err); } finally { this.busy = false; }
  }

  private setRow(i: number, patch: Partial<Row>) {
    this.rows = (this.rows ?? []).map((r, n) => (n === i ? { ...r, ...patch } : r));
  }

  private renderScheduleEditor(): TemplateResult {
    const a = this.account;
    const rows = this.rows;
    const err = (f: string) => this.formErrors.find((x) => x.field === f)?.message;
    return html`<vs-dialog heading="Revise the payment schedule" wide ?open=${!!rows} @close=${() => (this.rows = null)}
      @focus-field=${(e: CustomEvent<string>) => (this.renderRoot.querySelector(`#${e.detail}`) as HTMLElement | null)?.focus()}>
      ${rows && a ? html`<form id="pcm-schedule" class="stack" novalidate @submit=${(e: Event) => this.saveSchedule(e)}>
        <p>The instalments must add up exactly to the project value, <strong>${a.position.value}</strong>. Recorded payments are never
          changed: they are applied to the new schedule in order. An instalment with an issued invoice must keep its label and amount.</p>
        <vs-error-summary .errors=${this.formErrors}></vs-error-summary>
        <div class="rows">${rows.map((r, i) => html`<fieldset class="row-edit"><legend>Instalment ${i + 1}</legend>
          <label class="field"><span class="label">What it is for</span><input id=${`row-${i}-label`} maxlength="120" .value=${r.label}
            aria-invalid=${err(`row-${i}-label`) ? 'true' : 'false'} @input=${(e: Event) => this.setRow(i, { label: (e.target as HTMLInputElement).value })}></label>
          <label class="field"><span class="label">When it is due</span><input id=${`row-${i}-when`} maxlength="200" .value=${r.when}
            aria-invalid=${err(`row-${i}-when`) ? 'true' : 'false'} @input=${(e: Event) => this.setRow(i, { when: (e.target as HTMLInputElement).value })}></label>
          <label class="field"><span class="label">Amount (₹)</span><input id=${`row-${i}-amount`} inputmode="decimal" .value=${r.amount}
            aria-invalid=${err(`row-${i}-amount`) ? 'true' : 'false'} @input=${(e: Event) => this.setRow(i, { amount: (e.target as HTMLInputElement).value })}></label>
          <label class="field"><span class="label">Due by (optional)</span><input type="date" .value=${r.due_on}
            @input=${(e: Event) => this.setRow(i, { due_on: (e.target as HTMLInputElement).value })}></label>
          <button type="button" class="btn ghost small" ?disabled=${rows.length === 1}
            @click=${() => { this.rows = rows.filter((_, n) => n !== i); }}>Remove<span class="sr-only"> instalment ${i + 1}</span></button>
        </fieldset>`)}</div>
        <button type="button" class="btn small" ?disabled=${rows.length >= 24}
          @click=${() => { this.rows = [...rows, { label: '', when: '', amount: '', requested: false, due_on: '' }]; }}>Add an instalment</button>
        <label class="field"><span class="label">Why the schedule changes (required)</span><textarea id="reason" maxlength="1000"
          aria-invalid=${err('reason') ? 'true' : 'false'} .value=${this.scheduleReason}
          @input=${(e: Event) => { this.scheduleReason = (e.target as HTMLTextAreaElement).value; }}></textarea></label>
      </form>` : nothing}
      <div slot="actions"><button class="btn" @click=${() => (this.rows = null)}>Cancel</button>
        <button class="btn primary" type="submit" form="pcm-schedule" ?disabled=${this.busy}>Save the schedule</button></div>
    </vs-dialog>`;
  }

  // --- document viewer ------------------------------------------------------------------------------------------------
  private renderDoc(): TemplateResult {
    const d = this.doc;
    const m = (d?.model ?? {}) as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
    return html`<vs-dialog heading=${d?.title ?? ''} wide ?open=${!!d} @close=${() => (this.doc = null)}>
      ${d ? html`<div class="stack">
        ${d.status === 'CANCELLED' ? html`<vs-banner kind="warning">Cancelled. The document is kept as it was issued.</vs-banner>` : nothing}
        <dl class="meta"><dt>Number</dt><dd>${m.number ?? 'Draft'}</dd><dt>Date</dt><dd>${day(m.date)}</dd>
          ${m.instalment ? html`<dt>For</dt><dd>${m.instalment.label} (${m.instalment.position} of ${m.instalment.of})</dd>
            <dt>Instalment</dt><dd>${m.amounts.instalment}</dd>${m.amounts.gst_included ? html`<dt>Of which GST</dt><dd>${m.amounts.gst_included}</dd>` : nothing}
            <dt>Paid towards it</dt><dd>${m.amounts.paid_towards}</dd><dt>Amount due</dt><dd class="strong">${m.amounts.due}</dd>
            <dt>Due by</dt><dd>${day(m.due_on)}</dd>` : nothing}
          ${m.payment ? html`<dt>Amount</dt><dd class="strong">${m.payment.amount}</dd><dt>Received</dt><dd>${day(m.payment.received_on)}</dd>
            <dt>Method</dt><dd>${m.payment.method}</dd><dt>Reference</dt><dd>${m.payment.reference ?? '—'}</dd>` : nothing}
          <dt>Project value</dt><dd>${m.position?.value}</dd><dt>Paid</dt><dd>${m.position?.paid}</dd><dt>Outstanding</dt><dd>${m.position?.outstanding}</dd>
          ${m.issuer ? html`<dt>Issued by</dt><dd>${m.issuer.legal_name}${m.issuer.gstin ? `, GSTIN ${m.issuer.gstin}` : ''}</dd>` : html`<dt>Issuer</dt><dd>Not recorded (owner decision PCM-D01)</dd>`}
        </dl>
        <p class="small muted">${m.statement}</p>
      </div>` : nothing}
      <div slot="actions"><button class="btn" @click=${() => (this.doc = null)}>Close</button>
        ${d?.html && d.filename ? html`<button class="btn primary" @click=${() => download(d.filename!, d.html!)}>Download</button>` : nothing}</div>
    </vs-dialog>`;
  }

  // --- tabs -----------------------------------------------------------------------------------------------------------
  private renderSummary(a: Detail): TemplateResult {
    const nxt = a.schedule?.lines.find((l) => l.id === a.position.next_instalment_id) ?? null;
    return html`<section class="figures" aria-label="Commercial position">
      <div class="figure"><span class="label">Project value</span><span class="value">₹ ${a.position.value}</span>
        <span class="hint">${a.position.tax ? `Includes GST of ₹ ${a.position.tax}` : 'GST as quoted'}</span></div>
      <div class="figure"><span class="label">Paid</span><span class="value">₹ ${a.position.paid}</span><span class="hint">Recorded by Veda Spaces</span></div>
      <div class="figure"><span class="label">Outstanding</span><span class="value">₹ ${a.position.outstanding}</span>
        <span class="hint">${a.position.credit ? `Paid ₹ ${a.position.credit} more than the value` : `As of ${day(a.position.as_of)}`}</span></div>
      <div class="figure"><span class="label">Next payment</span><span class="value small">${nxt ? `₹ ${nxt.remaining}` : '—'}</span>
        <span class="hint">${nxt ? html`${nxt.label} · ${stateBadge(nxt.state, nxt.state_label)}` : 'Nothing outstanding'}</span></div>
    </section>`;
  }

  private renderOverview(a: Detail): TemplateResult {
    return html`
      ${a.position.schedule_state === 'REVISION_REQUIRED' ? html`<vs-banner kind="warning">An accepted variation changed the project value; the schedule
        differs by ₹ ${a.position.unscheduled}. ${a.capabilities.manage_schedule && a.capabilities.writable
          ? html`<button class="btn small" @click=${() => this.editSchedule(a)}>Revise the schedule</button>` : nothing}</vs-banner>` : nothing}
      <section class="card stack" aria-labelledby="h-baseline"><h2 id="h-baseline" class="section-title">Agreed value</h2>
        <p class="muted small">From the accepted quotation and each accepted variation. These never change when prices change.</p>
        <div class="table-wrap" tabindex="0" role="region" aria-label="Agreed value"><table><thead><tr><th scope="col">#</th><th scope="col">Quotation</th><th scope="col">Accepted</th>
          <th scope="col">Accepted total (₹)</th><th scope="col">Value after (₹)</th></tr></thead>
          <tbody>${a.baseline.map((b) => html`<tr><td>${b.sequence_no}</td><td>${b.reference}<span class="sub">${b.kind === 'ORIGINAL' ? 'Original' : 'Variation'}</span></td>
            <td>${formatAbsolute(b.decided_on)}</td><td class="num">${b.accepted_total}</td><td class="num">${b.value}</td></tr>`)}</tbody></table></div>
      </section>`;
  }

  private renderSchedule(a: Detail): TemplateResult {
    const s = a.schedule;
    const can = a.capabilities.writable;
    return html`<section class="stack" aria-labelledby="h-schedule">
      <div class="row"><h2 id="h-schedule" class="section-title">Payment schedule${s ? ` · revision ${s.revision_no}` : ''}</h2>
        ${a.capabilities.manage_schedule && can ? html`<button class="btn small" @click=${() => this.editSchedule(a)}>${s ? 'Revise the schedule' : 'Create the schedule'}</button>` : nothing}</div>
      ${!s ? html`<vs-empty-state heading="No payment schedule yet"><p>The accepted quotation had no payment milestones. Create one that adds up to ₹ ${a.position.value}.</p></vs-empty-state>`
        : html`<div class="table-wrap" tabindex="0" role="region" aria-label="Payment schedule"><table><thead><tr><th scope="col">#</th><th scope="col">Instalment</th><th scope="col">Amount (₹)</th>
          <th scope="col">Paid (₹)</th><th scope="col">Remaining (₹)</th><th scope="col">Status</th><th scope="col">Due</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
          <tbody>${s.lines.map((l) => html`<tr><td>${l.position}</td><td>${l.label}<span class="sub">${l.when}</span></td>
            <td class="num">${l.amount}${l.gst_included ? html`<span class="sub">GST ${l.gst_included}</span>` : nothing}</td>
            <td class="num">${l.applied}</td><td class="num">${l.remaining}</td><td>${stateBadge(l.state, l.state_label)}</td>
            <td>${l.due_on ? day(l.due_on) : l.requested_on ? 'No date set' : '—'}</td>
            <td><div class="actions">
              ${a.capabilities.manage_schedule && can && l.remaining_minor > 0 ? html`<button class="btn small" @click=${() => this.requestInstalment(a, l)}>${l.requested_on ? 'Change due date' : 'Ask for it'}<span class="sr-only"> ${l.label}</span></button>` : nothing}
              ${l.invoice ? html`<button class="btn small ghost" @click=${() => this.showInvoice(a.invoices.find((i) => i.id === l.invoice!.id)!)}>${l.invoice.number ?? 'Draft invoice'}</button>`
                : a.capabilities.issue_invoice && can && l.remaining_minor > 0 ? html`<button class="btn small ghost" @click=${() => this.draftInvoice(a, l)}>Invoice<span class="sr-only"> ${l.label}</span></button>` : nothing}
            </div></td></tr>`)}</tbody></table></div>`}
      ${a.revisions.length > 1 ? html`<details><summary>Earlier revisions (${a.revisions.length - 1})</summary><ul>${a.revisions.filter((r) => r.status !== 'CURRENT')
        .map((r) => html`<li>Revision ${r.revision_no}: ₹ ${r.total}, ${humanize(r.source)}${r.reason ? ` — ${r.reason}` : ''} (${who(r.created_by)}, ${formatAbsolute(r.created_on)})</li>`)}</ul></details>` : nothing}
    </section>`;
  }

  private renderPayments(a: Detail): TemplateResult {
    return html`<section class="stack" aria-labelledby="h-payments">
      <div class="row"><h2 id="h-payments" class="section-title">Payments and receipts</h2>
        ${a.capabilities.record_payment && a.capabilities.writable && a.position.outstanding_minor > 0
          ? html`<button class="btn primary small" @click=${() => this.recordPayment(a)}>Record a payment</button>` : nothing}</div>
      <p class="small muted">Payments recorded by Veda Spaces staff when money reached Veda Spaces. Veda Spaces collects nothing online.</p>
      ${!a.payments.length ? html`<vs-empty-state heading="No payments recorded yet"></vs-empty-state>` : html`<div class="table-wrap" tabindex="0" role="region" aria-label="Payments"><table>
        <thead><tr><th scope="col">Received</th><th scope="col">Amount (₹)</th><th scope="col">Method and reference</th><th scope="col">Status</th>
          <th scope="col">Recorded by</th><th scope="col">Receipt</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>${a.payments.map((p) => html`<tr><td>${day(p.received_on)}</td><td class="num">${p.amount}</td>
          <td>${p.method}${p.external_reference ? html`<span class="sub">${p.external_reference}</span>` : nothing}
            ${p.internal_note ? html`<span class="sub">Staff note: ${p.internal_note}</span>` : nothing}</td>
          <td>${p.status === 'REVERSED' ? html`<span class="badge REVERSED">Reversed</span><span class="sub">${REVERSAL_TEXT[p.reversal!.reason_code]} · ${who(p.reversal!.reversed_by)}</span>`
            : html`<span class="badge PAID">Recorded</span>`}</td>
          <td>${who(p.recorded_by)}<span class="sub">${formatAbsolute(p.recorded_on)}</span></td>
          <td>${p.receipt ? html`<button class="btn small ghost" @click=${() => this.showReceipt(p.receipt!.id)}>${p.receipt.number}</button>` : '—'}</td>
          <td>${p.status === 'RECORDED' && a.capabilities.reverse_payment && a.capabilities.writable && p.recorded_by?.id !== this.me?.id
            ? html`<button class="btn small danger" @click=${() => this.reversePayment(a, p)}>Reverse<span class="sr-only"> ${p.amount}</span></button>` : nothing}</td></tr>`)}</tbody></table></div>`}
    </section>`;
  }

  private renderInvoices(a: Detail): TemplateResult {
    const issuable = a.capabilities.invoice_issuable;
    return html`<section class="stack" aria-labelledby="h-invoices"><h2 id="h-invoices" class="section-title">Invoices</h2>
      ${!issuable ? html`<vs-banner kind="info">Invoices can be drafted and previewed, but not issued, until the invoice issuer particulars are recorded
        (owner decision PCM-D01: legal name, address, GSTIN, SAC, whether it is a tax invoice).</vs-banner>` : nothing}
      ${!a.invoices.length ? html`<vs-empty-state heading="No invoices yet"><p>Create one from an instalment in the payment schedule.</p></vs-empty-state>`
        : html`<div class="table-wrap" tabindex="0" role="region" aria-label="Invoices"><table><thead><tr><th scope="col">Invoice</th><th scope="col">Instalment</th><th scope="col">Amount (₹)</th>
          <th scope="col">Due</th><th scope="col">Status</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
          <tbody>${a.invoices.map((i) => html`<tr><td>${i.number ?? 'Draft'}<span class="sub">${i.issued_on ? `Issued ${formatAbsolute(i.issued_on)} · ${who(i.issued_by)}` : `Drafted by ${who(i.drafted_by)}`}</span></td>
            <td>${i.label ?? '—'}</td><td class="num">${i.amount}</td><td>${day(i.due_on)}</td>
            <td><span class="badge ${i.status}">${humanize(i.status)}</span>${i.cancel_reason ? html`<span class="sub">${i.cancel_reason}</span>` : nothing}</td>
            <td><div class="actions"><button class="btn small ghost" @click=${() => this.showInvoice(i)}>${i.status === 'DRAFT' ? 'Preview' : 'View'}<span class="sr-only"> ${i.number ?? 'draft'}</span></button>
              ${i.status === 'DRAFT' && a.capabilities.issue_invoice && a.capabilities.writable ? html`
                <button class="btn small primary" ?disabled=${!issuable || this.busy} @click=${() => this.issueInvoice(a, i)}>Issue</button>
                <button class="btn small" ?disabled=${this.busy} @click=${() => this.abandonInvoice(i)}>Discard</button>` : nothing}
              ${i.status === 'ISSUED' && a.capabilities.issue_invoice && a.capabilities.writable ? html`<button class="btn small danger" @click=${() => this.cancelInvoice(a, i)}>Cancel</button>` : nothing}
            </div></td></tr>`)}</tbody></table></div>`}
    </section>`;
  }

  private renderHistory(a: Detail): TemplateResult {
    if (!a.capabilities.view_audit) return html`<vs-empty-state heading="You do not have access to the commercial history."></vs-empty-state>`;
    if (!this.history) return html`<vs-skeleton rows="5"></vs-skeleton>`;
    return html`<section class="stack" aria-labelledby="h-history"><h2 id="h-history" class="section-title">History</h2>
      <ol class="history">${this.history.map((e) => html`<li><span class="strong">${humanize(e.code)}</span> · ${who(e.by)} · ${formatAbsolute(e.at)}
        <span class="sub">${Object.entries(e.detail).filter(([k]) => k !== 'entity').map(([k, v]) => `${humanize(k)}: ${String(v)}`).join(' · ')}</span></li>`)}</ol></section>`;
  }

  private renderTab(a: Detail): TemplateResult {
    switch (this.tab) {
      case 'schedule': return this.renderSchedule(a);
      case 'payments': return this.renderPayments(a);
      case 'invoices': return this.renderInvoices(a);
      case 'history': return this.renderHistory(a);
      default: return this.renderOverview(a);
    }
  }

  override render() {
    if (this.missing) {
      const off = (this.me?.features as Record<string, boolean> | undefined)?.project_commercials === false;
      return html`<div class="page"><h1 class="title" id="page-title" tabindex="-1">Project commercials</h1>
        <vs-empty-state heading=${off ? 'Project commercials are not enabled in this environment.' : 'This commercial record does not exist or is not visible to you.'}></vs-empty-state></div>`;
    }
    const a = this.account;
    return html`<div class="page">
      <div class="row"><a class="btn ghost" href="/commercials" @click=${(e: Event) => { e.preventDefault(); navigate('/commercials'); }}>← Payments</a></div>
      <div class="page-head"><div><p class="eyebrow">Project commercials</p>
        <h1 class="title" id="page-title" tabindex="-1">${a ? `${a.lead.name ?? 'Customer'} · ${a.quotation_number}` : 'Project commercials'}</h1>
        ${a ? html`<p class="muted">${a.property.reference ?? ''}${a.property.city ? ` · ${a.property.city}` : ''} · opened ${formatAbsolute(a.opened_on)}</p>` : nothing}</div></div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${this.conflict ? html`<vs-banner kind="danger"><span id="conflict" tabindex="-1">This record changed since you opened it. Nothing was overwritten.</span>
        <button class="btn small" @click=${() => this.load()}>Reload</button></vs-banner>` : nothing}
      ${!a ? html`<vs-skeleton rows="8"></vs-skeleton>` : html`
        ${a.problems.length ? html`<vs-banner kind="danger"><span><strong>This record does not verify.</strong> Nothing new can be recorded until it is investigated:
          ${a.problems.map((p) => p.message).join(' ')}</span></vs-banner>` : nothing}
        ${this.renderSummary(a)}
        <vs-tabs label="Commercial sections" .tabs=${TABS.map(([id, label]) => ({ id, label }))} selected=${this.tab}
          @tab-change=${(e: CustomEvent<Tab>) => this.setTab(e.detail)}><div class="stack">${this.renderTab(a)}</div></vs-tabs>`}
      ${this.renderForm()}${this.renderScheduleEditor()}${this.renderDoc()}
      <div class="sr-only" role="status" aria-live="polite">${this.announcement}</div>
    </div>`;
  }
}
customElements.define('vs-commercials-page', VsCommercialsPage);
