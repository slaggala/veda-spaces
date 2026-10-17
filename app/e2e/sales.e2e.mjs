// Sales & Customer Acquisition (SCA): the staff pipeline (stages derived from records, a stage claimed by a status marked
// in words, filters re-requested from the server, a row leading to its lead), the funnel ("Not tracked" where the site
// never sent a beacon, never 0) and the customer-journey demo (the real proposal and portal views on a synthetic model,
// marked DEMO top and bottom, never touching a customer API), in a real browser at 360, 390, 768 and 1280 px, with
// keyboard focus, no horizontal overflow, 44 px targets and axe (WCAG 2.2 AA). The API is answered by Playwright with a
// SYNTHETIC model; the derivations themselves are proven by the API suites.
//   APP_BASE=http://localhost:5173 node e2e/sales.e2e.mjs
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

// SYNTHETIC content: invented for the browser journey, not Veda Spaces content.
const PERMS = ['sales.pipeline.view', 'sales.funnel.view', 'sales.demo.view', 'lead.read', 'profile.read', 'quotation.read'];
const ME = { id: 'u-sales', email: 'sales@synthetic.example', full_name: 'SYNTHETIC Sales', display_name: 'SYNTHETIC', phone: null, timezone: 'Asia/Kolkata',
  locale: 'en-IN', status: 'ACTIVE', roles: [], authz_version: 1, permissions: Object.fromEntries(PERMS.map((p) => [p, 'ALL'])), suspended_permissions: [],
  session: { type: 'FULL', auth_methods: ['pwd'], mfa_verified_on: null, cooling_off_until: null }, mfa: { required: false, required_by: [], enrolled: false },
  email_change: null, features: { sales_experience: true }, version: 1 };
const OWNER = { id: 'u-sales', display_name: 'SYNTHETIC Sales' };
const FACTS = { estimate: null, contacted_on: null, consultation_on: null, properties: [], visits: [], quotation: null, quotations: 0, accepted: null, proposal: null,
  customer_requests: { total: 0, waiting_on_staff: 0, waiting_on_customer: 0 }, project: null };
const ROWS = [
  { lead: { id: 'l1', lead_number: 'VS-L-SYN-0001', name: 'SYNTHETIC One', city: 'Hyderabad', status: 'QUOTATION_SENT', created_on: '2026-10-01T04:30:00Z' },
    source: { code: 'WEBSITE', label: 'Website' }, channel: { code: 'ORGANIC_SEARCH', label: 'Organic search', detail: null },
    stage: { code: 'QUOTATION_ISSUED', label: 'Quotation issued', basis: 'QUOTATION_RECORD', basis_label: 'Quotation record', claimed_without_record: false },
    facts: { ...FACTS, properties: ['p1'], quotation: { id: 'q1', quotation_number: 'VS-Q-SYN-0001', version_no: 1, status: 'ISSUED', issued_on: '2026-10-10T04:30:00Z', valid_until: '2026-11-09', property_id: 'p1' }, quotations: 1 },
    quoted: { amount_minor: 185000000, currency: 'INR' }, owner: OWNER, last_activity_on: '2026-10-15T04:30:00Z', next_follow_up_on: '2026-10-20T04:30:00Z', is_follow_up_overdue: false,
    attention: [], customer_action: 'Decision on the issued quotation', closed: { won_on: null, lost_on: null, lost_reason: null } },
  { lead: { id: 'l2', lead_number: 'VS-L-SYN-0002', name: 'SYNTHETIC Two', city: 'Secunderabad', status: 'SITE_VISIT', created_on: '2026-10-03T04:30:00Z' },
    source: { code: 'REFERRAL', label: 'Referral' }, channel: { code: 'REFERRAL', label: 'Referral', detail: null },
    stage: { code: 'SITE_MEASUREMENT', label: 'Site measurement', basis: 'LEAD_STATUS', basis_label: 'Status recorded by staff', claimed_without_record: true },
    facts: FACTS, quoted: null, owner: null, last_activity_on: '2026-09-28T04:30:00Z', next_follow_up_on: '2026-10-12T04:30:00Z', is_follow_up_overdue: true,
    attention: [{ code: 'FOLLOW_UP_OVERDUE', label: 'Follow-up overdue' }, { code: 'UNASSIGNED', label: 'No owner' }], customer_action: null,
    closed: { won_on: null, lost_on: null, lost_reason: null } },
  { lead: { id: 'l3', lead_number: 'VS-L-SYN-0003', name: 'SYNTHETIC Three', city: null, status: 'NEW', created_on: '2026-10-14T04:30:00Z' },
    source: null, channel: { code: 'UNKNOWN', label: 'Unknown', detail: null },
    stage: { code: 'NEW', label: 'New enquiry', basis: 'NONE', basis_label: 'No evidence yet', claimed_without_record: false },
    facts: FACTS, quoted: null, owner: OWNER, last_activity_on: null, next_follow_up_on: null, is_follow_up_overdue: false,
    attention: [{ code: 'NO_FOLLOW_UP_PLANNED', label: 'No follow-up planned' }], customer_action: null, closed: { won_on: null, lost_on: null, lost_reason: null } },
];
const FUNNEL = {
  period: { from: '2026-09-18', to: '2026-10-17', timezone: 'Asia/Kolkata' }, as_of: '2026-10-17T10:00:00Z',
  site: { site_visit: { count: null, basis: 'CLIENT_EVENT', tracking: 'NOT_TRACKED', by_channel: null },
    estimator_started: { count: null, basis: 'CLIENT_EVENT', tracking: 'NOT_TRACKED', by_channel: null },
    enquiry_started: { count: 4, basis: 'CLIENT_EVENT', tracking: 'TRACKED', by_channel: { DIRECT: 4 } },
    journey_viewed: { count: 0, basis: 'CLIENT_EVENT', tracking: 'TRACKED', by_channel: {} } },
  estimates_completed: { count: 2, basis: 'AUTHORITATIVE', tracking: 'TRACKED' },
  leads: [['leads_created', 'Enquiries received', 3], ['leads_with_estimate', 'Enquiries with a budgetary estimate', 1], ['contacted', 'Contacted', 2],
    ['consultation', 'Consultation held', 1], ['measurement', 'Site measurement', 2], ['quotation_issued', 'Quotation issued', 1],
    ['quotation_opened', 'Quotation opened by the customer', 0], ['accepted', 'Accepted by the customer', 0], ['won', 'Won', 0], ['lost', 'Lost', 0]]
    .map(([code, label, count]) => ({ code, label, count, basis: 'AUTHORITATIVE', tracking: 'TRACKED' })),
  cohort: { size: 3, truncated: false, claimed_stages_without_record: 1 },
  current_stages: [{ code: 'NEW', label: 'New enquiry', count: 1 }, { code: 'SITE_MEASUREMENT', label: 'Site measurement', count: 1 }, { code: 'QUOTATION_ISSUED', label: 'Quotation issued', count: 1 }],
  ratios: { estimator_start_to_estimate: { value: null, reason: 'NOT_TRACKED' }, site_visit_to_enquiry: { value: null, reason: 'NOT_TRACKED' },
    enquiry_to_quotation: { value: 0.3333, reason: null }, quotation_to_acceptance: { value: 0, reason: null }, enquiry_to_won: { value: 0, reason: null },
    decided_to_won: { value: null, reason: 'NO_DENOMINATOR' } },
  by_channel: [['REFERRAL', 'Referral', 1], ['DIRECT', 'Direct contact', 0], ['SOCIAL', 'Social media', 0], ['PAID', 'Paid campaign', 0], ['ORGANIC_SEARCH', 'Organic search', 1],
    ['OTHER', 'Other', 0], ['UNKNOWN', 'Unknown', 1]].map(([code, label, leads]) => ({ code, label, leads, quotation_issued: code === 'ORGANIC_SEARCH' ? 1 : 0, accepted: 0, won: 0, lost: 0 })),
  by_source: [{ code: 'WEBSITE', label: 'Website', leads: 2, won: 0 }, { code: 'REFERRAL', label: 'Referral', leads: 1, won: 0 }], lost_reasons: [], stalled: { quiet: 1 },
};
const LABEL = 'DEMO: synthetic example, not a customer';
const CONTACT = { display_name: 'DEMO designer', role: 'Your design consultant (demo)', phone: '+00 0000 000000', email: 'demo@example.com', hours: 'Mon-Sat, 10:00-18:00', channel_note: null };
const PORTAL_CONTACT = { source: 'CONSULTANT', name: 'DEMO designer', role: 'Your design consultant (demo)', phone: '+00 0000 000000', email: 'demo@example.com', hours: 'Mon-Sat, 10:00-18:00' };
const NEXT_STEPS = [['PROPOSAL_ACCEPTED', 'Proposal accepted', 'You accept the quotation and Veda Spaces confirms receipt.'], ['HANDOVER', 'Handover', 'The handover package is prepared, reviewed with you and acknowledged.']]
  .map(([code, label, text]) => ({ code, stage: code, label, text, duration: null }));
const JOURNEY = [
  { key: 'consultation', label: 'Consultation', state: 'COMPLETED', detail: 'DEMO: first conversation held', date: '2026-09-07' },
  { key: 'site_measurement', label: 'Site measurement', state: 'COMPLETED', detail: 'DEMO: visit completed', date: '2026-09-14' },
  { key: 'quotation', label: 'Your quotation', state: 'COMPLETED', detail: 'DEMO: quotation issued', date: '2026-09-26' },
  { key: 'approval', label: 'Your approval', state: 'COMPLETED', detail: 'DEMO: accepted', date: '2026-10-03' },
  { key: 'execution', label: 'Execution', state: 'IN_PROGRESS', detail: 'DEMO: installation under way', date: null },
  { key: 'handover', label: 'Handover', state: 'UPCOMING', detail: 'After the joint inspection', date: null },
];
const QUOTATION = { id: 'demo-quotation', reference: 'DEMO-Q-0001', title: 'DEMO: 3 BHK apartment interiors', kind: 'QUOTATION', version_no: 1, state: 'ACCEPTED', status: 'COMPLETED',
  status_label: 'Accepted', issued_on: '2026-09-26', valid_until: '2026-10-26', days_left: null, total: 'DEMO amount', currency: 'INR' };
const PROJECT = { id: 'demo-project', status: 'ACTIVE', phase: { code: 'INSTALLATION', label: 'Installation' },
  work: { items: [{ label: 'Kitchen cabinetry', state: 'COMPLETED', detail: 'Installed', completed_on: '2026-10-14' }, { label: 'Master bedroom wardrobe', state: 'IN_PROGRESS', detail: 'Being installed', completed_on: null },
    { label: 'Living room TV unit', state: 'UPCOMING', detail: 'Planned next', completed_on: null }], counts: { COMPLETED: 1, IN_PROGRESS: 1, UPCOMING: 1 } },
  paused: [], next_date: null, quality: { checks_passed: 2, being_corrected: 0 }, snags: [{ number: 1, title: 'DEMO: drawer alignment', status: 'IN_PROGRESS', state: 'IN_PROGRESS' }],
  reports: [], can_report: false, handover: { state: 'UPCOMING', label: 'After the joint inspection', date: null, remaining: [{ label: 'Work packages', count: 2 }] }, documents: [], package: null };
const PORTAL = { demo: true, label: LABEL, id: 'demo-property', property: { reference: 'DEMO-P-0001', configuration: '3 BHK apartment', locality: 'Demo locality', city: 'Hyderabad' },
  enquiry: { reference: 'DEMO-REF1' }, headline: 'DEMO: your home interiors project',
  next_step: { key: 'execution', label: 'Execution', state: 'IN_PROGRESS', detail: 'DEMO: installation under way', date: null }, attention_count: 0, quotation: QUOTATION,
  contact: PORTAL_CONTACT, project_tracking: true, payments: { available: true, outstanding: 'DEMO amount', next_payment: null }, journey: JOURNEY, attention: [],
  quotations: [QUOTATION], documents: [{ kind: 'QUOTATION', ...QUOTATION }],
  commercials: { available: true, summary: { currency: 'INR', total_value: 'DEMO total', includes_gst: 'GST shown on the quotation', paid: 'DEMO paid', outstanding: 'DEMO outstanding', credit: null, next_payment: null, as_of: '2026-10-17' },
    schedule: [{ label: 'On acceptance', when: 'Paid', amount: 'DEMO amount', gst_included: null, paid: 'DEMO amount', remaining: null, state: 'PAID', state_label: 'Paid', requested: false, due_on: '2026-10-03' },
      { label: 'At handover', when: 'Upcoming', amount: 'DEMO amount', gst_included: null, paid: '0', remaining: 'DEMO amount', state: 'UPCOMING', state_label: 'Upcoming', requested: false, due_on: null }],
    payments: [], invoices: [], receipts: [], notices: [], how_to_pay: 'DEMO: how to pay is confirmed by Veda Spaces.' },
  included: [{ title: 'Kitchen', kind: 'ROOM', included_count: 2, optional_count: 0, items: [{ description: 'DEMO: base and wall units', detail: null, status: 'INCLUDED' }, { description: 'DEMO: tall unit', detail: null, status: 'INCLUDED' }] }],
  commitments: { source: 'DEMO', inclusions: [{ code: 'D1', text: 'DEMO: the scope listed in your quotation' }], warranty: ['DEMO: warranty and service as set out in your accepted quotation'],
    manufacturer_warranty_note: null, handover: [{ code: 'D2', text: 'DEMO: a walkthrough of every room with you' }], care: [{ code: 'D3', text: 'DEMO: care guidance for finishes and hardware' }],
    next_steps: NEXT_STEPS, payment_schedule: [{ label: 'On acceptance', share: 'Share A', trigger: 'Acceptance', amount: null }, { label: 'At handover', share: 'Share C', trigger: 'Handover', amount: null }],
    payment_safety: 'DEMO: pay only to the account named on your quotation.' },
  responsibilities: { client: [{ code: 'D4', text: 'DEMO: items you supply, as listed in your quotation' }], site_readiness: [{ code: 'D5', text: 'DEMO: the site is ready for installation on the agreed date' }] },
  support: { contacts: [PORTAL_CONTACT], escalation: 'DEMO: escalation route named on your quotation' }, delivery: { available: true, projects: [PROJECT] },
  warranty: { available: true, categories: [], max_photos: 0, projects: [{ id: 'demo-project', handed_over: false, can_report: false, warranty: { state: 'BEFORE_HANDOVER', message: 'DEMO: your warranty is registered at handover.' }, requests: [] }] } };
const ROOMS = [
  { ref: 'R1', title: 'Kitchen', kind: 'ROOM', subtotal: 'DEMO subtotal', included_count: 2, optional_count: 0, lines: [
    { ref: 'L1', description: 'DEMO: base and wall units', detail: 'Laminate finish (demo)', quantity: 'DEMO qty', amount: 'DEMO amount', priced: true, status: 'INCLUDED' },
    { ref: 'L2', description: 'DEMO: tall unit', detail: null, quantity: 'DEMO qty', amount: 'DEMO amount', priced: true, status: 'INCLUDED' }] },
  { ref: 'R2', title: 'Master bedroom', kind: 'ROOM', subtotal: 'DEMO subtotal', included_count: 1, optional_count: 1, lines: [
    { ref: 'L3', description: 'DEMO: wardrobe', detail: 'Hinged (demo)', quantity: 'DEMO qty', amount: 'DEMO amount', priced: true, status: 'INCLUDED' },
    { ref: 'L4', description: 'DEMO: loft storage', detail: null, quantity: 'DEMO qty', amount: 'DEMO amount', priced: true, status: 'OPTIONAL' }] }];
const PROPOSAL = { demo: true, label: LABEL, state: 'OPEN', link: { expires_on: '', status: 'PREVIEW' }, history: [], capabilities: { interaction: false, acceptance: false }, notices: [], actions: [],
  proposal: { schema: 'veda.customer-proposal/1', kind: 'QUOTATION', title: 'DEMO: your quotation', brand: { name: 'Veda Spaces', tagline: 'Interiors, measured and made' },
    reference: 'DEMO-Q-0001', quotation_number: 'DEMO-Q-0001', version_no: 1, variation_no: 0, issued_on: '2026-09-26', valid_until: '2026-10-26', subject: 'DEMO: 3 BHK apartment interiors',
    cover_note: 'DEMO: a synthetic quotation used to show the customer experience.', property: { reference: 'DEMO-P-0001', configuration: '3 BHK apartment', city: 'Hyderabad' },
    snapshot_sha256: null, rooms: ROOMS, optional_items: [ROOMS[1].lines[1]], summary: { base_total: 'DEMO total', total: 'DEMO total', currency: 'INR' },
    payment_schedule: [{ label: 'On acceptance', share: 'Share A', trigger: 'Acceptance', amount: null }, { label: 'At handover', share: 'Share C', trigger: 'Handover', amount: null }],
    warranty: ['DEMO: warranty and service as set out in the policy'], service_support: ['DEMO: service support after handover'], assumptions: ['DEMO: sizes as measured on site'],
    exclusions: ['DEMO: civil work'], terms: ['DEMO: terms as issued'], terms_version: 'DEMO', unit_rates_shown: false, sections: {},
    information: { content_version: 'DEMO', contacts: { quotation: CONTACT, support: [CONTACT], service: [CONTACT] }, support_escalation: 'DEMO: escalation route named on your quotation',
      project_inclusions: [{ code: 'D1', text: 'DEMO: the scope listed in your quotation' }], client_responsibilities: [{ code: 'D4', text: 'DEMO: items you supply, as listed in your quotation' }],
      site_readiness: [{ code: 'D5', text: 'DEMO: the site is ready for installation on the agreed date' }], site_dependent_work: null, manufacturer_warranty_note: null,
      warranty_exclusions: [{ code: 'D6', text: 'DEMO: damage from misuse' }],
      service_guidance: { contact: CONTACT, what_to_provide: ['DEMO: your reference and a photo'], reference_process: null, escalation: null },
      handover: [{ code: 'D2', text: 'DEMO: a walkthrough of every room with you' }], care: [{ code: 'D3', text: 'DEMO: care guidance for finishes and hardware' }], next_steps: NEXT_STEPS,
      payment_safety: 'DEMO: pay only to the account named on your quotation.' } } };
const DEMO = { demo: true, label: LABEL, as_of: '2026-10-17', portal: PORTAL, proposal: PROPOSAL, journey: JOURNEY };

async function serve(p, state) {
  state.requests = [];
  await p.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    state.requests.push({ method: req.method(), path, query: Object.fromEntries(url.searchParams) });
    const json = (status, body) => route.fulfill({ status, contentType: status < 400 ? 'application/json' : 'application/problem+json', body: JSON.stringify(body) });
    const ok = (data, meta) => json(200, meta ? { data, meta } : { data });
    if (path === '/api/v1/auth/refresh') return ok({ access_token: 'synthetic-token' });
    if (path === '/api/v1/auth/me') return ok(ME);
    if (path === '/api/v1/sales/pipeline') {
      const stage = url.searchParams.get('stage');
      const rows = ROWS.filter((r) => !stage || r.stage.code === stage);
      const counts = {};
      for (const r of rows) counts[r.stage.code] = (counts[r.stage.code] ?? 0) + 1;
      return ok(rows, { page: 1, limit: 25, total: rows.length, scanned: ROWS.length, truncated: false, stage_counts: counts });
    }
    if (path === '/api/v1/sales/funnel') return ok({ ...FUNNEL, period: { ...FUNNEL.period, from: url.searchParams.get('from') ?? FUNNEL.period.from, to: url.searchParams.get('to') ?? FUNNEL.period.to } });
    if (path === '/api/v1/sales/demo') return ok(DEMO);
    if (path === '/api/v1/sales/leads/l1/progression') return ok(ROWS[0]);
    return json(404, { status: 404, code: 'NOT_FOUND', title: 'Not found' });
  });
}

async function axe(p, name) {
  await p.addScriptTag({ content: AXE });
  const v = await p.evaluate(async () => (await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }))
    .violations.filter((x) => x.impact === 'serious' || x.impact === 'critical')
    .map((x) => `${x.id} (${x.nodes.length}): ${x.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')}`));
  check(`axe ${name}`, v.length === 0, v.join(', '));
}

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

const active = (p) => p.evaluate(() => { let a = document.activeElement; while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement;
  return { tag: a?.tagName, id: a?.id ?? '', text: (a?.textContent ?? '').trim().slice(0, 30) }; });
const kpi = (p, label) => p.evaluate((l) => {
  const find = (root) => { const el = root.querySelector('vs-sales-funnel-page'); if (el) return el; for (const n of root.querySelectorAll('*')) { if (n.shadowRoot) { const f = find(n.shadowRoot); if (f) return f; } } return null; };
  const tile = [...find(document).shadowRoot.querySelectorAll('vs-kpi-tile')].find((t) => t.label === l);
  return tile ? tile.shadowRoot.querySelector('.value').textContent.trim() : null;
}, label);

const browser = await chromium.launch();
try {
  // --- pipeline, funnel and demo journeys at desktop width -----------------------------------------------------------
  {
    const state = {};
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    await serve(p, state);
    await p.goto(`${BASE}/sales`);
    const pipe = p.locator('vs-sales-pipeline-page');
    await pipe.getByRole('link', { name: 'VS-L-SYN-0001' }).waitFor();
    const links = await pipe.getByRole('link', { name: /^VS-L-SYN-/ }).count();
    const quoted = await pipe.getByText('₹18,50,000', { exact: true }).count();
    const unassigned = await pipe.locator('tbody').getByText('Unassigned', { exact: true }).count();
    check('pipeline: loads every row with its stage, owner and quoted amount', links === 3 && quoted === 1 && unassigned === 1, `links ${links}, quoted ${quoted}, unassigned ${unassigned}`);
    check('pipeline: a stage claimed by a staff status is marked in words, an overdue follow-up too', await pipe.getByText('by status', { exact: true }).isVisible()
      && await pipe.getByText('Overdue', { exact: true }).isVisible() && await pipe.locator('tbody').getByText('Status recorded by staff').isVisible());
    check('pipeline: focus lands on the heading, then the first filter', (await active(p)).id === 'page-title' && (await p.keyboard.press('Tab'), (await active(p)).text === 'Open'));
    const before = state.requests.filter((r) => r.path === '/api/v1/sales/pipeline').length;
    await pipe.locator('select[name=stage]').selectOption('SITE_MEASUREMENT');
    await pipe.getByRole('link', { name: 'VS-L-SYN-0001' }).waitFor({ state: 'detached' });
    const last = state.requests.filter((r) => r.path === '/api/v1/sales/pipeline').at(-1);
    check('pipeline: a stage filter is re-requested from the server and the rows follow', state.requests.filter((r) => r.path === '/api/v1/sales/pipeline').length === before + 1
      && last.query.stage === 'SITE_MEASUREMENT' && last.query.status === 'open' && (await pipe.getByRole('link', { name: /^VS-L-SYN-/ }).count()) === 1);
    await pipe.getByRole('button', { name: /^Site measurement/ }).first().click(); // the stage chip toggles the same filter off
    await pipe.getByRole('link', { name: 'VS-L-SYN-0001' }).waitFor();
    check('pipeline journey: no page errors', errors.length === 0, errors.join(' | '));
    await pipe.getByRole('link', { name: 'VS-L-SYN-0001' }).click();
    await p.waitForURL(/\/leads\/l1$/);
    check('pipeline: a row leads to its lead', p.url().endsWith('/leads/l1'));

    await p.goto(`${BASE}/sales/funnel`);
    const fun = p.locator('vs-sales-funnel-page');
    await fun.locator('vs-kpi-tile').first().waitFor();
    check('funnel: a beacon never received reads "Not tracked", never 0; a tracked count is a figure', (await kpi(p, 'Site visits')) === 'Not tracked'
      && (await kpi(p, 'Estimator starts')) === 'Not tracked' && (await kpi(p, 'Estimates completed')) === '2' && (await kpi(p, 'Enquiries')) === '3');
    check('funnel: ratios carry their reason, never a percentage for nothing', await fun.getByText('No data yet', { exact: true }).isVisible() && await fun.getByText('33.3%', { exact: true }).isVisible()
      && (await fun.getByText('Not tracked', { exact: true }).count()) >= 4);
    await fun.locator('input[name=from]').fill('2026-10-01');
    await fun.locator('input[name=to]').fill('2026-10-15');
    await fun.getByRole('button', { name: 'Show' }).click();
    await fun.getByText(/1 Oct 2026 to 15 Oct 2026/).waitFor();
    const fq = state.requests.filter((r) => r.path === '/api/v1/sales/funnel').at(-1).query;
    check('funnel: the period is re-requested as chosen', fq.from === '2026-10-01' && fq.to === '2026-10-15');

    await p.goto(`${BASE}/sales/demo`);
    const demo = p.locator('vs-sales-demo-page');
    await demo.locator('vs-proposal-view').waitFor();
    check('demo: marked DEMO at the top and the bottom', (await demo.locator('vs-banner', { hasText: LABEL }).count()) === 2);
    check('demo: the customer\'s proposal is the real view in preview, on the synthetic model', await demo.locator('vs-proposal-view').getByText('DEMO: 3 BHK apartment interiors').first().isVisible()
      && await demo.locator('vs-proposal-view').getByText(/Staff preview/).isVisible());
    await demo.getByRole('tab', { name: "Customer's project portal" }).click();
    const portal = demo.locator('vs-sales-demo-portal');
    await portal.getByText('DEMO: your home interiors project').waitFor();
    check('demo: the customer\'s portal is the real view without header or sign-out', await portal.getByText('Kitchen cabinetry').isVisible()
      && (await portal.locator('vs-portal-header').count()) === 0 && (await portal.getByRole('button', { name: /Sign out/ }).count()) === 0);
    check('demo: no customer API was ever called', !state.requests.some((r) => r.path.startsWith('/api/v1/public')) && state.requests.some((r) => r.path === '/api/v1/sales/demo'),
      state.requests.map((r) => r.path).join(', '));
    check('journeys: no page errors', errors.length === 0, errors.join(' | '));
    await ctx.close();
  }
  // --- layout, targets and axe at every width ----------------------------------------------------------------------------
  for (const [name, viewport] of [['360 px', { width: 360, height: 740 }], ['390 px', { width: 390, height: 844 }],
    ['768 px', { width: 768, height: 1024 }], ['1280 px', { width: 1280, height: 800 }]]) {
    const ctx = await browser.newContext({ viewport });
    const p = await ctx.newPage();
    await serve(p, {});
    await p.goto(`${BASE}/sales`);
    await p.locator('vs-sales-pipeline-page').getByRole('link', { name: 'VS-L-SYN-0001' }).waitFor();
    await layout(p, 'vs-sales-pipeline-page', `${name} pipeline`);
    await axe(p, `${name} pipeline`);
    await p.screenshot({ path: `${OUT}/sales-pipeline-${viewport.width}.png`, fullPage: true });
    await p.goto(`${BASE}/sales/funnel`);
    await p.locator('vs-sales-funnel-page vs-kpi-tile').first().waitFor();
    await layout(p, 'vs-sales-funnel-page', `${name} funnel`);
    await axe(p, `${name} funnel`);
    await p.screenshot({ path: `${OUT}/sales-funnel-${viewport.width}.png`, fullPage: true });
    await p.goto(`${BASE}/sales/demo`);
    await p.locator('vs-sales-demo-page vs-proposal-view').waitFor();
    await layout(p, 'vs-sales-demo-page', `${name} demo proposal`);
    await axe(p, `${name} demo proposal`);
    await p.locator('vs-sales-demo-page').getByRole('tab', { name: "Customer's project portal" }).click();
    await p.locator('vs-sales-demo-portal').getByText('DEMO: your home interiors project').waitFor();
    await layout(p, 'vs-sales-demo-page', `${name} demo portal`);
    await axe(p, `${name} demo portal`);
    await p.screenshot({ path: `${OUT}/sales-demo-${viewport.width}.png`, fullPage: true });
    await ctx.close();
  }
} finally {
  await browser.close();
}
const failed = results.filter((x) => !x).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
