// Project Commercials (PCM): the staff journey Payments → one record → record a payment (with its confirmation) → its
// receipt, and the customer journey project → Payments → Action Required → the invoice → the receipt, in a real browser
// against the real app, at 360, 390, 768 and 1280 px, with keyboard, focus, accessible validation, no horizontal overflow,
// 44 px targets and axe (WCAG 2.2 AA). The API is answered by Playwright with a stateful SYNTHETIC model (every /api
// request is intercepted; nothing reaches a server): the API's rules (money, idempotency, scope, isolation) are proven by
// the API suites; this proves what the browser does with them.
//   APP_BASE=http://localhost:5173 node e2e/commercials.e2e.mjs
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const BASE = process.env.APP_BASE ?? 'http://localhost:5173';
const OUT = process.env.E2E_OUT ?? 'e2e-artifacts';
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`); };

// SYNTHETIC content: invented for the browser journey, not Veda Spaces content or amounts.
const PERMS = ['commercials.view', 'commercials.schedule.manage', 'commercials.payment.record', 'commercials.payment.reverse',
  'commercials.invoice.issue', 'commercials.audit.view', 'profile.read'];
const ME = { id: 'u-acc', email: 'accounts@synthetic.example', full_name: 'SYNTHETIC Accounts', display_name: 'SYNTHETIC', phone: null,
  timezone: 'Asia/Kolkata', locale: 'en-IN', status: 'ACTIVE', roles: [], authz_version: 1,
  permissions: Object.fromEntries(PERMS.map((p) => [p, 'ALL'])), suspended_permissions: [],
  session: { type: 'FULL', auth_methods: ['pwd'], mfa_verified_on: null, cooling_off_until: null },
  mfa: { required: false, required_by: [], enrolled: false }, email_change: null, features: { project_commercials: true }, version: 1 };
const who = { id: 'u-other', display_name: 'SYNTHETIC Manager' };
const LONG = 'Handover and joint inspection with a SYNTHETIC very long instalment name that has to wrap on a phone';

function position(paid) {
  const value = 123456700;
  const out = value - paid;
  const f = (m) => (m / 100).toLocaleString('en-US', { minimumFractionDigits: 2 }); // SYNTHETIC server strings
  return { currency: 'INR', value_minor: value, value: f(value), tax_minor: 18832300, tax: '188,323.00', paid_minor: paid, paid: f(paid),
    outstanding_minor: out, outstanding: f(out), credit_minor: 0, credit: null, schedule_state: 'IN_BALANCE', unscheduled_minor: 0,
    unscheduled: '0.00', next_instalment_id: paid >= 12345700 ? 'i2' : 'i1', as_of: '2026-10-16' };
}
function detail(state) {
  const paid = state.payments.reduce((n, p) => n + p.amount_minor, 0);
  const line = (id, n, label, when, amount, applied, st, extra = {}) => ({ id, position: n, label, when, amount_minor: amount,
    amount: (amount / 100).toLocaleString('en-US', { minimumFractionDigits: 2 }), gst_included: '18,832.00', share: null, applied_minor: applied,
    applied: (applied / 100).toLocaleString('en-US', { minimumFractionDigits: 2 }), remaining_minor: amount - applied,
    remaining: ((amount - applied) / 100).toLocaleString('en-US', { minimumFractionDigits: 2 }), state: st, state_label: st === 'PAID' ? 'Paid' : st === 'DUE' ? 'Due' : 'Upcoming',
    requested_on: null, requested_by: null, due_on: null, invoice: null, ...extra });
  return {
    id: 'a1', version: 3 + state.payments.length, quotation_number: 'VS-Q-2026-000001', base_quotation: { id: 'q1', reference: 'VS-Q-2026-000001 v1' },
    lead: { id: 'l1', name: 'SYNTHETIC Customer with a long name', reference: '81DG-6BJR', erased: false },
    property: { id: 'p1', reference: 'VS-P-2026-000001', city: 'Hyderabad' }, opened_on: '2026-10-15T09:00:00Z', position: position(paid),
    baseline: [{ sequence_no: 1, kind: 'ORIGINAL', quotation_id: 'q1', reference: 'VS-Q-2026-000001 v1', accepted_total: '1,234,567.00', accepted_gst: '188,323.00',
      value: '1,234,567.00', decided_on: '2026-10-14T09:00:00Z', baseline_sha256: 'a'.repeat(64), snapshot_sha256: 'b'.repeat(64) }],
    schedule: { id: 's1', revision_no: 1, source: 'QUOTATION_MILESTONES', reason: null, total: '1,234,567.00', lines: [
      line('i1', 1, 'Booking', 'On acceptance (synthetic)', 12345700, Math.min(paid, 12345700), paid >= 12345700 ? 'PAID' : 'UPCOMING'),
      line('i2', 2, 'Production', 'Before production (synthetic)', 61728350, 0, 'DUE', { requested_on: '2026-10-15T09:00:00Z', requested_by: who, due_on: '2026-11-30' }),
      line('i3', 3, LONG, 'On handover (synthetic)', 49382650, 0, 'UPCOMING')] },
    revisions: [{ id: 's1', revision_no: 1, status: 'CURRENT', source: 'QUOTATION_MILESTONES', reason: null, total: '1,234,567.00', created_on: '2026-10-15T09:00:00Z', created_by: who, superseded_on: null }],
    payments: state.payments.map((p, n) => ({ id: `pay${n}`, amount_minor: p.amount_minor, amount: (p.amount_minor / 100).toLocaleString('en-US', { minimumFractionDigits: 2 }),
      received_on: p.received_on, method_code: p.method_code, method: 'Bank transfer', external_reference: p.external_reference ?? null, customer_note: null,
      internal_note: null, recorded_on: '2026-10-16T09:00:00Z', recorded_by: { id: 'u-acc', display_name: 'SYNTHETIC' }, status: 'RECORDED', reversal: null,
      receipt: { id: `r${n}`, number: `VS-R-2026-0000${n + 1}` } })),
    invoices: [], problems: [], policy: { version: 'PCM-POLICY-0', status: 'UNDECIDED', decisions: { 'PCM-D01': { label: 'invoice issuer particulars', decided: false } } },
    capabilities: { writable: true, manage_schedule: true, record_payment: true, reverse_payment: true, issue_invoice: true, view_audit: true, invoice_issuable: false },
    methods: [['BANK_TRANSFER', 'Bank transfer'], ['UPI', 'UPI'], ['CHEQUE', 'Cheque'], ['CASH', 'Cash'], ['OTHER', 'Other']].map(([code, label]) => ({ code, label })),
    reversal_reasons: ['RECORDED_IN_ERROR', 'DUPLICATE', 'PAYMENT_RETURNED', 'OTHER'],
  };
}
const receiptDoc = { kind: 'RECEIPT', id: 'r0', number: 'VS-R-2026-00001', status: 'VALID', status_label: 'Valid', property_id: 'p1', notices: [],
  issued_on: '2026-10-16T09:00:00Z', html: '<!doctype html><title>Payment receipt</title><p>SYNTHETIC</p>', filename: 'VS-R-2026-00001.html',
  document: { kind: 'RECEIPT', title: 'Payment receipt', number: 'VS-R-2026-00001', date: '2026-10-16', brand: { name: 'Veda Spaces', tagline: 'Synthetic' },
    customer: { name: 'SYNTHETIC Customer' }, property: { reference: 'VS-P-2026-000001', configuration: '3 BHK apartment', city: 'Hyderabad' },
    quotation: { reference: 'VS-Q-2026-000001 v1', quotation_number: 'VS-Q-2026-000001', variations: [] }, currency: 'INR',
    payment: { amount: '123,457.00', received_on: '2026-10-16', method: 'Bank transfer', reference: 'UTR-SYNTHETIC-0000000000001', note: null },
    applied_to: [{ label: 'Booking', amount: '123,457.00' }], position: { value: '1,234,567.00', paid: '123,457.00', outstanding: '1,111,110.00', credit: null },
    payment_safety: 'Pay only to the account Veda Spaces gave you in writing (synthetic).',
    statement: 'Veda Spaces recorded this payment as received on 2026-10-16. Veda Spaces does not collect payments through this document or the project portal.' } };
const invoiceDoc = { ...receiptDoc, kind: 'INVOICE', id: 'i9', number: 'VS-I-2026-00001', status: 'DUE', status_label: 'Due', filename: 'VS-I-2026-00001.html',
  document: { ...receiptDoc.document, kind: 'INVOICE', title: 'Tax invoice', number: 'VS-I-2026-00001', due_on: '2026-11-30', payment: undefined, applied_to: undefined,
    issuer: { legal_name: 'SYNTHETIC Interiors (test only)', address_lines: ['1 Test Street', 'Test City 000000'], gstin: '00AAAAA0000A0Z0', sac_code: '995411', footer: [] },
    instalment: { label: 'Production', when: 'Before production (synthetic)', position: 2, of: 3 },
    amounts: { instalment: '617,283.50', gst_included: '94,162.00', paid_towards: '0.00', due: '617,283.50' }, note: null } };
const commercials = { available: true,
  summary: { currency: 'INR', total_value: '1,234,567.00', includes_gst: '188,323.00', paid: '123,457.00', outstanding: '1,111,110.00', credit: null,
    next_payment: { label: 'Production', amount: '617,283.50', when: 'Before production (synthetic)', state: 'DUE', state_label: 'Due', due_on: '2026-11-30' }, as_of: '2026-10-16' },
  schedule: [
    { label: 'Booking', when: 'On acceptance (synthetic)', amount: '123,457.00', gst_included: '18,832.00', paid: '123,457.00', remaining: '0.00', state: 'PAID', state_label: 'Paid', requested: true, due_on: null },
    { label: 'Production', when: 'Before production (synthetic)', amount: '617,283.50', gst_included: '94,162.00', paid: '0.00', remaining: '617,283.50', state: 'DUE', state_label: 'Due', requested: true, due_on: '2026-11-30' },
    { label: LONG, when: 'On handover (synthetic)', amount: '493,826.50', gst_included: '75,329.00', paid: '0.00', remaining: '493,826.50', state: 'UPCOMING', state_label: 'Upcoming', requested: false, due_on: null }],
  payments: [{ amount: '123,457.00', received_on: '2026-10-16', method: 'Bank transfer', reference: 'UTR-SYNTHETIC-0000000000001', note: 'Booking amount (synthetic)',
    status: 'RECORDED', status_label: 'Recorded', correction: null, receipt: { id: 'r0', number: 'VS-R-2026-00001', status: 'VALID' } }],
  invoices: [{ id: 'i9', number: 'VS-I-2026-00001', issued_on: '2026-10-16', due_on: '2026-11-30', label: 'Production', amount: '617,283.50', status: 'DUE', status_label: 'Due' }],
  receipts: [{ id: 'r0', number: 'VS-R-2026-00001', issued_on: '2026-10-16', amount: '123,457.00', status: 'VALID', status_label: 'Valid' }],
  notices: [], how_to_pay: 'Pay using the payment details Veda Spaces gave you in writing. Your payment appears here once Veda Spaces has recorded it.' };
const steps = ['Consultation', 'Site measurement', 'Design and scope', 'Your quotation', 'Your approval'].map((label, i) => ({ key: `k${i}`, label, state: 'COMPLETED', detail: `${label} (synthetic).`, date: null }))
  .concat(['Execution', 'Quality checks', 'Handover'].map((label, i) => ({ key: `n${i}`, label, state: 'NOT_YET_AVAILABLE', detail: 'Not shown in your portal yet.', date: null })));
const view = { id: 'p1', property: { reference: 'VS-P-2026-000001', configuration: '3 BHK apartment', locality: 'Synthetic Nagar', city: 'Hyderabad' },
  enquiry: { reference: '81DG-6BJR' }, headline: 'You have approved your quotation.', next_step: null, attention_count: 1, quotation: null, contact: null,
  project_tracking: false, payments: { available: true, outstanding: '1,111,110.00', next_payment: commercials.summary.next_payment }, journey: steps,
  attention: [{ kind: 'PAYMENT_DUE', status: 'ACTION_REQUIRED', title: 'Payment due: Production', text: '617,283.50 is due. ' + commercials.how_to_pay,
    due: '2026-11-30', amount: '617,283.50', invoice_id: 'i9' }], quotations: [],
  documents: [{ kind: 'INVOICE', ...commercials.invoices[0] }, { kind: 'RECEIPT', ...commercials.receipts[0] }],
  included: null, commitments: null, responsibilities: null, support: null, commercials };

async function serve(p, state) {
  await p.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const json = (status, body) => route.fulfill({ status, contentType: status < 400 ? 'application/json' : 'application/problem+json', body: JSON.stringify(body) });
    const ok = (data, status = 200) => json(status, { data });
    const headers = req.headers();
    if (path.startsWith('/api/v1/public/portal/')) {
      if (headers['x-veda-portal'] !== 'vpp_SYNTHETIC' || headers.authorization) return json(401, { status: 401, code: 'PORTAL_SESSION_INVALID', title: 'Sign in' });
      if (path === '/api/v1/public/portal/properties/p1') return ok(view);
      if (path === '/api/v1/public/portal/invoices/i9') return ok(invoiceDoc);
      if (path === '/api/v1/public/portal/receipts/r0') return ok(receiptDoc);
      return json(404, { status: 404, code: 'NOT_FOUND', title: 'Not found' });
    }
    if (path === '/api/v1/auth/refresh') return ok({ access_token: 'synthetic-token' });
    if (path === '/api/v1/auth/me') return ok(ME);
    if (path === '/api/v1/commercials' && req.method() === 'GET') {
      const d = detail(state);
      return ok([{ ...d, next: { label: 'Production', amount: '617,283.50', state: 'DUE', due_on: '2026-11-30' }, overdue: 0 }]);
    }
    if (path === '/api/v1/commercials/candidates') return ok([]);
    if (path === '/api/v1/commercials/a1' && req.method() === 'GET') return ok(detail(state));
    if (path === '/api/v1/commercials/a1/history') return ok([{ id: 'e1', code: 'PAYMENT_RECORDED', entity_id: 'pay0', detail: { amount_minor: 12345700 }, at: '2026-10-16T09:00:00Z', by: who }]);
    if (path === '/api/v1/commercials/a1/payments' && req.method() === 'POST') {
      const body = req.postDataJSON();
      state.posts.push({ body, key: headers['idempotency-key'] ?? null });
      if (!state.payments.some((x) => x.key === headers['idempotency-key'])) state.payments.push({ ...body, key: headers['idempotency-key'] });
      return ok({ ...detail(state), payment_id: 'pay0', receipt_id: 'r0', replayed: false }, 201);
    }
    if (path === '/api/v1/commercial-receipts/r0') return ok({ id: 'r0', number: 'VS-R-2026-00001', payment_id: 'pay0', account_id: 'a1', status: 'VALID',
      document: receiptDoc.document, html: receiptDoc.html, filename: receiptDoc.filename });
    return json(404, { status: 404, code: 'NOT_FOUND', title: 'Not found' });
  });
}

async function axe(p, name) {
  await p.addScriptTag({ content: AXE });
  const v = await p.evaluate(async () => (await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }))
    .violations.map((x) => `${x.id} (${x.nodes.length}): ${x.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')}`));
  check(`axe ${name}`, v.length === 0, v.join(', '));
}

/** No horizontal page scroll, and every visible control of the component at least 44 x 44 px. */
async function layout(p, tag, name) {
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(`${name}: no horizontal overflow`, overflow <= 0, `${overflow}px`);
  const small = await p.evaluate((t) => {
    const found = [];
    const walk = (root) => { root.querySelectorAll('button, select, textarea, input, a, summary').forEach((n) => found.push(n)); root.querySelectorAll('*').forEach((n) => n.shadowRoot && walk(n.shadowRoot)); };
    const host = (function find(root) { const el = root.querySelector(t); if (el) return el; for (const n of root.querySelectorAll('*')) { if (n.shadowRoot) { const f = find(n.shadowRoot); if (f) return f; } } return null; })(document);
    walk(host.shadowRoot);
    return found.filter((n) => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden' && n.closest('dialog:not([open])') === null)
      .map((n) => { const r = n.getBoundingClientRect(); return { what: `${n.tagName.toLowerCase()} ${(n.textContent || n.name || n.id || '').trim().slice(0, 30)}`, w: Math.round(r.width), h: Math.round(r.height) }; })
      .filter((x) => x.w < 44 || x.h < 44);
  }, tag);
  check(`${name}: targets at least 44 px`, small.length === 0, JSON.stringify(small.slice(0, 5)));
}

const active = (p) => p.evaluate(() => { let a = document.activeElement; while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement; return a?.id ?? a?.tagName; });
const fresh = () => ({ payments: [], posts: [] });
const portalSession = (ctx) => ctx.addInitScript(() => sessionStorage.setItem('vs-portal-session', 'vpp_SYNTHETIC'));
const browser = await chromium.launch();
try {
  // Staff at a phone width: Payments → the record → record a payment, with validation and a confirmation → its receipt.
  {
    const state = fresh();
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    await serve(p, state);
    await p.goto(`${BASE}/commercials`);
    const list = p.locator('vs-commercials-list-page');
    await list.getByRole('link', { name: 'SYNTHETIC Customer with a long name' }).click();
    const page = p.locator('vs-commercials-page');
    await page.locator('.figures').waitFor();
    check('record: value, paid, outstanding and next payment come first', await page.getByText('Project value').isVisible()
      && await page.getByText('₹ 1,234,567.00').first().isVisible() && await page.getByText('Next payment').isVisible());
    await page.getByRole('tab', { name: 'Payments and receipts' }).click();
    await page.getByRole('button', { name: 'Record a payment' }).click();
    const dialog = page.locator('vs-dialog[open]');
    await dialog.getByLabel(/Amount received/).waitFor();
    check('the dialog says a payment record is not a bank confirmation', await dialog.getByText(/not a bank or\s+payment-provider confirmation/).isVisible());
    await dialog.getByLabel(/Amount received/).fill('12,345.678');
    await dialog.getByRole('button', { name: 'Review' }).click();
    check('validation: a malformed amount is refused accessibly, nothing sent',
      await dialog.locator('#f-amount[aria-invalid="true"]').count() === 1 && state.posts.length === 0);
    await dialog.getByLabel(/Amount received/).fill('123457');
    await dialog.getByLabel(/Reference/).fill('UTR-SYNTHETIC-0000000000001');
    await dialog.getByRole('button', { name: 'Review' }).click();
    await dialog.getByRole('heading', { name: 'Check before you confirm' }).waitFor();
    check('confirmation: focus moves to the summary, still nothing sent', (await active(p)) === 'confirm-h' && state.posts.length === 0);
    await dialog.getByRole('button', { name: 'Confirm: Record payment' }).click();
    await page.getByRole('button', { name: 'VS-R-2026-00001' }).waitFor();
    check('recorded once, in paise, with an idempotency key', state.posts.length === 1 && state.posts[0].body.amount_minor === 12345700
      && /^[A-Za-z0-9_-]{16,64}$/.test(state.posts[0].key ?? ''));
    await page.getByRole('button', { name: 'VS-R-2026-00001' }).click();
    const doc = page.locator('vs-dialog[open]');
    await doc.getByRole('button', { name: 'Download' }).waitFor();
    check('the receipt shows the frozen document and offers its sealed file', await doc.getByText('UTR-SYNTHETIC-0000000000001').isVisible());
    check('staff journey: no page errors', errors.length === 0, errors.join(' | '));
    await ctx.close();
  }
  // The customer: Payments, Action Required, the invoice and the receipt; never a way to pay.
  {
    const state = fresh();
    const ctx = await browser.newContext({ viewport: { width: 360, height: 740 } });
    await portalSession(ctx);
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    await serve(p, state);
    await p.goto(`${BASE}/portal/properties/p1`);
    const proj = p.locator('vs-portal-project-page');
    await proj.locator('#h-payments').waitFor();
    check('portal: Action Required names the payment due, with its invoice', await proj.getByText('Payment due: Production').isVisible()
      && await proj.getByRole('link', { name: 'View the invoice' }).isVisible());
    check('portal: value, paid and outstanding in plain words', await proj.getByText('Total project value').isVisible()
      && await proj.getByText('₹ 1,111,110.00').first().isVisible());
    check('portal: no way to pay here', (await proj.getByRole('button', { name: /^pay( now| online)?$/i }).count()) === 0
      && (await proj.getByRole('link', { name: /^pay( now| online)?$/i }).count()) === 0 && await proj.getByText(/does not collect payments through this portal/).isVisible());
    await proj.locator('nav.jump').getByRole('link', { name: 'Payments' }).click();
    check('the Payments link moves focus to its heading', (await active(p)) === 'h-payments');
    await proj.getByRole('link', { name: 'View the invoice' }).click();
    const d = p.locator('vs-portal-document-page');
    await d.getByRole('heading', { name: 'Tax invoice VS-I-2026-00001' }).waitFor();
    check('invoice: what is due, by when, from the frozen document', await d.getByText('Amount due (₹)').isVisible() && await d.getByText(/Due by/).first().isVisible());
    await p.goto(`${BASE}/portal/receipts/r0`);
    await d.getByRole('heading', { name: 'Receipt VS-R-2026-00001' }).waitFor();
    check('receipt: the payment recorded and what it was applied to', await d.getByText('Applied to').isVisible());
    await p.goto(`${BASE}/portal/invoices/someone-elses`);
    await d.getByText('We could not find this document').waitFor();
    check('another customer\'s document: not found, no detail', true);
    check('customer journey: no page errors', errors.length === 0, errors.join(' | '));
    await ctx.close();
  }
  // Layout, targets and axe at every width.
  for (const [name, viewport] of [['360 px', { width: 360, height: 740 }], ['390 px', { width: 390, height: 844 }],
    ['768 px', { width: 768, height: 1024 }], ['1280 px', { width: 1280, height: 800 }]]) {
    const state = fresh();
    state.payments.push({ amount_minor: 12345700, received_on: '2026-10-16', method_code: 'BANK_TRANSFER', external_reference: 'UTR-SYNTHETIC-0000000000001', key: 'k' });
    const ctx = await browser.newContext({ viewport });
    await portalSession(ctx);
    const p = await ctx.newPage();
    await serve(p, state);
    await p.goto(`${BASE}/commercials`);
    await p.locator('vs-commercials-list-page table').waitFor();
    await layout(p, 'vs-commercials-list-page', `${name} staff list`);
    await axe(p, `${name} staff list`);
    await p.goto(`${BASE}/commercials/a1`);
    const page = p.locator('vs-commercials-page');
    await page.locator('.figures').waitFor();
    for (const t of ['Overview', 'Payment schedule', 'Payments and receipts', 'Invoices', 'History']) {
      await page.getByRole('tab', { name: t }).click();
      await layout(p, 'vs-commercials-page', `${name} staff ${t}`);
      await axe(p, `${name} staff ${t}`);
    }
    await p.screenshot({ path: `${OUT}/commercials-staff-${viewport.width}.png`, fullPage: true });
    await p.goto(`${BASE}/portal/properties/p1`);
    await p.locator('vs-portal-project-page #h-payments').waitFor();
    await layout(p, 'vs-portal-project-page', `${name} portal payments`);
    await axe(p, `${name} portal payments`);
    await p.screenshot({ path: `${OUT}/commercials-portal-${viewport.width}.png`, fullPage: true });
    for (const [path, label] of [['/portal/invoices/i9', 'invoice'], ['/portal/receipts/r0', 'receipt']]) {
      await p.goto(`${BASE}${path}`);
      await p.locator('vs-portal-document-page #doc-title').waitFor();
      await layout(p, 'vs-portal-document-page', `${name} portal ${label}`);
      await axe(p, `${name} portal ${label}`);
    }
    await ctx.close();
  }
} finally {
  await browser.close();
}
const failed = results.filter((x) => !x).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
