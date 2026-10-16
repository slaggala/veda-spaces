import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Me } from '../src/core/api/types.js';
import { sessionContext } from '../src/core/authz/context.js';
import { filterNav, NAV_ITEMS } from '../src/core/authz/permissions.js';
import { ROUTES } from '../src/core/router/routes.js';
import { paiseToRupees, rupeesToPaise, type Detail } from '../src/modules/commercials/api.js';
import '../src/modules/commercials/index.js';
import { forgetSession, keepSession } from '../src/modules/portal/api.js';
import '../src/modules/portal/index.js';
import { commercials, view } from './support/portal-sample.js';

/** Project Commercials pages (PCM), staff and customer. The API is mocked with SYNTHETIC models: every figure is a server
 * string, and the pages only show it. */

type Call = { method: string; path: string; body: Record<string, unknown> | null; ifMatch: string | null; key: string | null; portal: string | null };
const json = (body: unknown, status = 200) => new Response(JSON.stringify({ data: body }), { status, headers: { 'Content-Type': 'application/json' } });
const problem = (status: number, body: Record<string, unknown>) =>
  new Response(JSON.stringify({ status, title: 'Refused', ...body }), { status, headers: { 'Content-Type': 'application/problem+json' } });
const text = (root: ShadowRoot | Element) => root.textContent?.replace(/\s+/g, ' ') ?? '';
const button = (root: ParentNode, name: string | RegExp) =>
  [...root.querySelectorAll<HTMLButtonElement>('button')].find((b) => (typeof name === 'string' ? b.textContent?.trim() === name : name.test(b.textContent ?? '')))!;

const person = (id: string, name: string) => ({ id, display_name: name });
function detail(over: Partial<Detail> = {}): Detail {
  return {
    id: 'a1', version: 3, quotation_number: 'VS-Q-2026-000001', base_quotation: { id: 'q1', reference: 'VS-Q-2026-000001 v1' },
    lead: { id: 'l1', name: 'SYNTHETIC Customer', reference: '81DG-6BJR', erased: false }, property: { id: 'p1', reference: 'VS-P-2026-000001', city: 'Hyderabad' },
    opened_on: '2026-10-15T09:00:00Z',
    position: { currency: 'INR', value_minor: 123456700, value: '1,234,567.00', tax_minor: 18832300, tax: '188,323.00', paid_minor: 12345700, paid: '123,457.00',
      outstanding_minor: 111111000, outstanding: '1,111,110.00', credit_minor: 0, credit: null, schedule_state: 'IN_BALANCE', unscheduled_minor: 0,
      unscheduled: '0.00', next_instalment_id: 'i2', as_of: '2026-10-16' },
    baseline: [{ sequence_no: 1, kind: 'ORIGINAL', quotation_id: 'q1', reference: 'VS-Q-2026-000001 v1', accepted_total: '1,234,567.00',
      accepted_gst: '188,323.00', value: '1,234,567.00', decided_on: '2026-10-14T09:00:00Z', baseline_sha256: 'a'.repeat(64), snapshot_sha256: 'b'.repeat(64) }],
    schedule: { id: 's1', revision_no: 1, source: 'QUOTATION_MILESTONES', reason: null, total: '1,234,567.00', lines: [
      { id: 'i1', position: 1, label: 'Booking', when: 'On acceptance (synthetic)', amount_minor: 12345700, amount: '123,457.00', gst_included: '18,832.00',
        share: '10%', applied_minor: 12345700, applied: '123,457.00', remaining_minor: 0, remaining: '0.00', state: 'PAID', state_label: 'Paid',
        requested_on: null, requested_by: null, due_on: null, invoice: null },
      { id: 'i2', position: 2, label: 'Production', when: 'Before production (synthetic)', amount_minor: 61728350, amount: '617,283.50', gst_included: '94,162.00',
        share: '50%', applied_minor: 0, applied: '0.00', remaining_minor: 61728350, remaining: '617,283.50', state: 'DUE', state_label: 'Due',
        requested_on: '2026-10-15T09:00:00Z', requested_by: person('u-m', 'SYNTHETIC Manager'), due_on: '2026-11-30', invoice: null },
      { id: 'i3', position: 3, label: 'Handover', when: 'On handover (synthetic)', amount_minor: 49382650, amount: '493,826.50', gst_included: '75,329.00',
        share: '40%', applied_minor: 0, applied: '0.00', remaining_minor: 49382650, remaining: '493,826.50', state: 'UPCOMING', state_label: 'Upcoming',
        requested_on: null, requested_by: null, due_on: null, invoice: null }] },
    revisions: [{ id: 's1', revision_no: 1, status: 'CURRENT', source: 'QUOTATION_MILESTONES', reason: null, total: '1,234,567.00',
      created_on: '2026-10-15T09:00:00Z', created_by: person('u-m', 'SYNTHETIC Manager'), superseded_on: null }],
    payments: [
      { id: 'pay-own', amount_minor: 12345700, amount: '123,457.00', received_on: '2026-10-14', method_code: 'BANK_TRANSFER', method: 'Bank transfer',
        external_reference: 'UTR-SYN-1', customer_note: null, internal_note: 'Staff only note', recorded_on: '2026-10-14T10:00:00Z',
        recorded_by: person('u-me', 'Me'), status: 'RECORDED', reversal: null, receipt: { id: 'r1', number: 'VS-R-2026-00001' } },
      { id: 'pay-other', amount_minor: 500, amount: '5.00', received_on: '2026-10-13', method_code: 'CASH', method: 'Cash', external_reference: null,
        customer_note: null, internal_note: null, recorded_on: '2026-10-13T10:00:00Z', recorded_by: person('u-x', 'Someone else'), status: 'RECORDED',
        reversal: null, receipt: { id: 'r0', number: 'VS-R-2026-00000' } }],
    invoices: [{ id: 'inv1', version: 1, status: 'DRAFT', number: null, instalment_id: 'i2', label: 'Production', amount_minor: 61728350, amount: '617,283.50',
      gst_included: '94,162.00', due_on: null, customer_note: null, drafted_on: '2026-10-15T09:00:00Z', drafted_by: person('u-m', 'SYNTHETIC Manager'),
      issued_on: null, issued_by: null, cancelled_on: null, cancelled_by: null, cancel_reason: null }],
    problems: [], policy: { version: 'PCM-POLICY-0', status: 'UNDECIDED', decisions: { 'PCM-D01': { label: 'invoice issuer particulars', decided: false } } },
    capabilities: { writable: true, manage_schedule: true, record_payment: true, reverse_payment: true, issue_invoice: true, view_audit: true,
      invoice_issuable: false },
    methods: [{ code: 'BANK_TRANSFER', label: 'Bank transfer' }, { code: 'UPI', label: 'UPI' }, { code: 'CHEQUE', label: 'Cheque' },
      { code: 'CASH', label: 'Cash' }, { code: 'OTHER', label: 'Other' }],
    reversal_reasons: ['RECORDED_IN_ERROR', 'DUPLICATE', 'PAYMENT_RETURNED', 'OTHER'],
    ...over,
  };
}

function serve(routes: Record<string, (body: Record<string, unknown> | null) => Response>, calls: Call[]) {
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), location.href);
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    calls.push({ method, path: url.pathname, body, ifMatch: headers['If-Match'] ?? null, key: headers['Idempotency-Key'] ?? null,
      portal: headers['X-Veda-Portal'] ?? null });
    const handler = routes[`${method} ${url.pathname}`];
    return handler ? handler(body) : problem(404, { code: 'NOT_FOUND' });
  };
}

async function staff(routes: Record<string, (body: Record<string, unknown> | null) => Response>) {
  const calls: Call[] = [];
  serve(routes, calls);
  const host = await fixture<HTMLDivElement>(html`<div></div>`);
  new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated', me: { id: 'u-me',
    permissions: { 'commercials.view': 'ALL', 'commercials.payment.record': 'ALL' }, features: { project_commercials: true } } as unknown as Me } });
  const el = document.createElement('vs-commercials-page') as HTMLElement & { location?: unknown };
  el.location = { params: { id: 'a1' } };
  host.append(el);
  return { el, root: el.shadowRoot!, calls };
}

async function tab(root: ShadowRoot, label: string) {
  const tabs = root.querySelector('vs-tabs')!.shadowRoot!;
  [...tabs.querySelectorAll<HTMLButtonElement>('[role=tab]')].find((t) => t.textContent?.trim() === label)!.click();
}

describe('Project commercials: money input is exact', () => {
  it('turns typed rupees into paise from the text, never through a float', () => {
    expect(rupeesToPaise('0.29')).to.equal(29);
    expect(rupeesToPaise('1,00,000.07')).to.equal(10000007);
    expect(rupeesToPaise('617283.5')).to.equal(61728350);
    expect(rupeesToPaise('25000')).to.equal(2500000);
    for (const bad of ['', '-1', '1.234', '1e5', 'abc', '01', '.5']) expect(rupeesToPaise(bad), bad).to.equal(null);
    expect(paiseToRupees(61728350)).to.equal('617283.50');
    expect(paiseToRupees(-50)).to.equal('-0.50');
    expect(rupeesToPaise(paiseToRupees(123456789))).to.equal(123456789);
  });

  it('is a staff route and a navigation item only with the feature and the capability', () => {
    for (const path of ['/commercials', '/commercials/:id']) {
      const r = ROUTES.find((x) => x.path === path)!;
      expect(r.access).to.equal('auth');
      expect(r.anyOf).to.deep.equal(['commercials.view']);
    }
    const perms = { 'commercials.view': 'ALL' } as const;
    expect(filterNav(NAV_ITEMS, perms, { project_commercials: true }).map((i) => i.path)).to.include('/commercials');
    expect(filterNav(NAV_ITEMS, perms, { project_commercials: false }).map((i) => i.path)).to.not.include('/commercials');
    expect(filterNav(NAV_ITEMS, {}, { project_commercials: true }).map((i) => i.path)).to.not.include('/commercials');
  });
});

describe('Project commercials (vs-commercials-page)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  it('shows the server\'s figures and says payments are recorded, never collected', async () => {
    const { root } = await staff({ 'GET /api/v1/commercials/a1': () => json(detail()) });
    await waitUntil(() => root.querySelector('.figures'), 'summary');
    const t = text(root);
    for (const figure of ['1,234,567.00', '123,457.00', '1,111,110.00', '617,283.50', '188,323.00']) expect(t).to.contain(figure);
    await tab(root, 'Payments and receipts');
    await waitUntil(() => root.querySelector('#h-payments'), 'payments');
    expect(text(root)).to.contain('collects nothing online');
    expect(text(root)).to.contain('Staff note: Staff only note');
  });

  it('records a payment in paise with an idempotency key, after an explicit confirmation', async () => {
    let posted: Record<string, unknown> | null = null;
    const { root, calls } = await staff({
      'GET /api/v1/commercials/a1': () => json(detail()),
      'POST /api/v1/commercials/a1/payments': (b) => { posted = b; return json({ ...detail(), payment_id: 'p9', receipt_id: 'r9', replayed: false }, 201); },
    });
    await waitUntil(() => root.querySelector('.figures'), 'summary');
    await tab(root, 'Payments and receipts');
    await waitUntil(() => button(root, 'Record a payment'), 'button');
    button(root, 'Record a payment').click();
    await waitUntil(() => root.querySelector('#f-amount'), 'form');
    const amount = root.querySelector<HTMLInputElement>('#f-amount')!;
    amount.value = '0.1.2';
    button(root, 'Review').click();
    await waitUntil(() => root.querySelector('#f-amount-err'), 'error');
    expect(amount.getAttribute('aria-invalid')).to.equal('true');
    amount.value = '617283.5';
    (root.querySelector<HTMLInputElement>('#f-external_reference')!).value = 'UTR-SYN-77';
    button(root, 'Review').click();
    await waitUntil(() => root.querySelector('#confirm-h'), 'confirm step');
    expect(text(root.querySelector('.confirm')!)).to.contain('617283.50');
    expect(calls.filter((c) => c.method === 'POST')).to.have.length(0);
    button(root, 'Confirm: Record payment').click();
    await waitUntil(() => posted, 'posted');
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.key).to.match(/^[A-Za-z0-9_-]{16,64}$/);
    expect(posted!.amount_minor).to.equal(61728350);
    expect(Number.isInteger(posted!.amount_minor)).to.equal(true);
    expect(posted!.external_reference).to.equal('UTR-SYN-77');
  });

  it('offers reversal only of someone else\'s payment, and invoices are not issuable until the particulars are configured (PCM-D01)', async () => {
    const calls: Call[] = [];
    serve({ 'GET /api/v1/commercials/a1': () => json(detail()) }, calls);
    const host = await fixture<HTMLDivElement>(html`<div></div>`);
    new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated', me: { id: 'u-me',
      permissions: { 'commercials.view': 'ALL', 'commercials.payment.reverse': 'ALL', 'commercials.invoice.issue': 'ALL' },
      features: { project_commercials: true } } as unknown as Me } });
    const el = document.createElement('vs-commercials-page') as HTMLElement & { location?: unknown };
    el.location = { params: { id: 'a1' } };
    host.append(el);
    const root = el.shadowRoot!;
    await waitUntil(() => root.querySelector('.figures'), 'summary');
    await tab(root, 'Payments and receipts');
    await waitUntil(() => root.querySelector('#h-payments'), 'payments');
    const reverse = [...root.querySelectorAll('button')].filter((b) => b.textContent?.startsWith('Reverse'));
    expect(reverse).to.have.length(1);
    expect(reverse[0].textContent).to.contain('5.00');
    await tab(root, 'Invoices');
    await waitUntil(() => root.querySelector('#h-invoices'), 'invoices');
    expect(text(root)).to.contain('PCM-D01');
    expect(text(root)).to.contain('invoice particulars');
    expect(text(root)).to.contain('are not configured');
    expect(button(root, 'Issue').disabled).to.equal(true);
  });

  it('a version conflict reloads instead of overwriting', async () => {
    const { root } = await staff({
      'GET /api/v1/commercials/a1': () => json(detail()),
      'POST /api/v1/commercials/a1/instalments/i3/request': () => problem(409, { code: 'VERSION_CONFLICT' }),
    });
    await waitUntil(() => root.querySelector('.figures'), 'summary');
    await tab(root, 'Payment schedule');
    await waitUntil(() => root.querySelector('#h-schedule'), 'schedule');
    button(root, /Ask for it\s*Handover/).click();
    await waitUntil(() => root.querySelector('#f-due_on'), 'form');
    button(root, 'Ask the customer').click();
    await waitUntil(() => root.querySelector('#conflict'), 'conflict');
    expect(text(root)).to.contain('Nothing was overwritten');
    expect(button(root, 'Reload')).to.exist;
  });

  it('says so when the feature is off or the record is not visible', async () => {
    const { root } = await staff({ 'GET /api/v1/commercials/a1': () => problem(404, { code: 'NOT_FOUND' }) });
    await waitUntil(() => root.querySelector('vs-empty-state'), 'empty');
    expect(root.querySelector('vs-empty-state')!.getAttribute('heading')).to.contain('not visible to you');
  });
});

describe('Customer portal: payments (PCM)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; forgetSession(); });
  const P = '/api/v1/public/portal';

  async function portal(tag: string, id: string, routes: Record<string, (body: Record<string, unknown> | null) => Response>) {
    const calls: Call[] = [];
    serve(routes, calls);
    keepSession('vpp_TEST');
    const el = document.createElement(tag) as HTMLElement & { location?: unknown };
    el.location = { params: { id } };
    const host = await fixture<HTMLDivElement>(html`<div></div>`);
    host.append(el);
    return { root: el.shadowRoot!, calls };
  }

  it('shows the value, paid, outstanding, the next payment, the schedule and history, with no way to pay', async () => {
    const v = view({ commercials: commercials(), attention: [{ kind: 'PAYMENT_DUE', status: 'ACTION_REQUIRED', title: 'Payment due: Production',
      text: '6,17,284.00 is due. Pay using the payment details Veda Spaces gave you in writing.', due: '2026-11-30', amount: '6,17,284.00', invoice_id: 'i1' }],
      documents: [{ kind: 'INVOICE', id: 'i1', number: 'VS-I-2026-00001', issued_on: '2026-10-15', amount: '6,17,284.00', status: 'DUE', status_label: 'Due' }] });
    const { root, calls } = await portal('vs-portal-project-page', 'p1', { [`GET ${P}/properties/p1`]: () => json(v) });
    await waitUntil(() => root.querySelector('#h-payments'), 'payments');
    const t = text(root);
    for (const s of ['Total project value', '12,34,567.00 SYNTHETIC', '1,23,457.00', '11,11,110.00', 'Next payment', 'UTR-SYNTHETIC-0000000001',
      'does not collect payments through this portal']) expect(t).to.contain(s);
    expect(root.querySelector('a[href="/portal/invoices/i1"]')).to.exist;
    expect(root.querySelector('a[href="/portal/receipts/r1"]')).to.exist;
    expect([...root.querySelectorAll('a, button')].some((b) => /\bpay now\b|^pay$/i.test(b.textContent?.trim() ?? ''))).to.equal(false);
    for (const badge of root.querySelectorAll('#payments .badge')) expect(badge.textContent?.trim()).to.not.equal('');
    expect(calls.every((c) => c.portal === 'vpp_TEST')).to.equal(true);
  });

  it('is calm when there is no commercial record, or it cannot be verified', async () => {
    const { root } = await portal('vs-portal-project-page', 'p1', { [`GET ${P}/properties/p1`]: () => json(view({ commercials: null })) });
    await waitUntil(() => root.querySelector('#h-payments'), 'payments');
    expect(text(root)).to.contain('Your payment details appear here once Veda Spaces has set up');
    const second = await portal('vs-portal-project-page', 'p1', {
      [`GET ${P}/properties/p1`]: () => json(view({ commercials: { available: false, message: 'Your payment details are not available right now. Please contact Veda Spaces.' } })) });
    await waitUntil(() => second.root.querySelector('#h-payments'), 'payments');
    expect(text(second.root)).to.contain('not available right now');
  });

  it('opens an invoice from the frozen document and offers the sealed file to download', async () => {
    const doc = { kind: 'INVOICE', id: 'i1', number: 'VS-I-2026-00001', status: 'DUE', status_label: 'Due', property_id: 'p1', notices: [],
      html: '<!doctype html><p>sealed</p>', filename: 'VS-I-2026-00001.html',
      document: { title: 'Tax invoice', number: 'VS-I-2026-00001', date: '2026-10-15', due_on: '2026-11-30', brand: { name: 'Veda Spaces' },
        issuer: { legal_name: 'SYNTHETIC Interiors', address_lines: ['1 Test Street'], gstin: '00AAAAA0000A0Z0', footer: [] },
        customer: { name: 'SYNTHETIC Customer' }, property: { reference: 'VS-P-2026-000001', configuration: '3 BHK apartment', city: 'Hyderabad' },
        quotation: { reference: 'VS-Q-2026-000001 v1', variations: [] }, instalment: { label: 'Production', when: 'Before production', position: 2, of: 3 },
        amounts: { instalment: '6,17,284.00', gst_included: '94,162.00', paid_towards: '0.00', due: '6,17,284.00' },
        position: { value: '12,34,567.00', paid: '1,23,457.00', outstanding: '11,11,110.00' }, payment_safety: null,
        statement: 'Veda Spaces does not collect payments through this document or the project portal.' } };
    const { root } = await portal('vs-portal-document-page', 'i1', { [`GET ${P}/invoices/i1`]: () => json(doc) });
    await waitUntil(() => root.querySelector('#doc-title'), 'document');
    const t = text(root);
    for (const s of ['Tax invoice VS-I-2026-00001', 'GSTIN 00AAAAA0000A0Z0', 'Amount due (₹)', '6,17,284.00', 'does not collect payments']) expect(t).to.contain(s);
    expect(text(root)).to.not.contain('sealed'); // the sealed HTML is downloaded, never inserted
    expect(button(root, /Download/)).to.exist;
  });

  it('answers "not found" for a document that is not the customer\'s', async () => {
    const { root } = await portal('vs-portal-document-page', 'x', {});
    await waitUntil(() => text(root).includes('could not find this document'), 'not found');
  });
});
