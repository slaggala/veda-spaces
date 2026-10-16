// Warranty and after-sales service (WSV): the staff queue and request page (triage, a coverage decision whose customer
// explanation and internal reason are required, the statements a decision may cite), and the customer's "Warranty &
// service" section (the warranty in plain words, never "covered" as such; a problem reported with a photo that is
// resized on the device and uploaded the way the server asks; a reply; confirming the resolution), in a real browser
// against the real app at 360, 390, 768 and 1280 px, with keyboard use, focus, accessible validation, no horizontal
// overflow, 44 px targets and axe (WCAG 2.2 AA). The API is answered by Playwright with a stateful SYNTHETIC model; the
// API's rules (coverage bases, isolation, idempotency, races) are proven by the API suites.
//   APP_BASE=http://localhost:5173 node e2e/warranty.e2e.mjs
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
const CARE = { id: 'u-care', display_name: 'SYNTHETIC Care' };
const PERMS = ['warranty.view', 'warranty.manage', 'warranty.service.view', 'warranty.service.triage', 'warranty.service.assess',
  'warranty.service.assign', 'profile.read'];
const ME = { id: 'u-care', email: 'care@synthetic.example', full_name: 'SYNTHETIC Care', display_name: 'SYNTHETIC', phone: null, timezone: 'Asia/Kolkata',
  locale: 'en-IN', status: 'ACTIVE', roles: [], authz_version: 1, permissions: Object.fromEntries(PERMS.map((p) => [p, 'ALL'])), suspended_permissions: [],
  session: { type: 'FULL', auth_methods: ['pwd'], mfa_verified_on: null, cooling_off_until: null }, mfa: { required: false, required_by: [], enrolled: false },
  email_change: null, features: { project_lifecycle: true, warranty_service: true }, version: 1 };
const LONG = 'The kitchen drawer next to the hob does not close fully and the SYNTHETIC soft-close channel makes a grinding noise when the drawer is full of utensils';
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');

const ENTITLEMENT = { registered: true, id: 'e1', project_id: 'pj1', handover_on: '2026-10-01', registered_on: '2026-10-01T10:00:00Z', registered_via: 'HANDOVER_EVENT',
  terms_sha256: 'a'.repeat(64), status: 'NOT_RECORDED', status_label: 'Not recorded in your portal', coverage: [],
  sources: [{ quotation_id: 'q1', quotation_number: 'VS-Q-2026-000001', kind: 'ORIGINAL', version_no: 1, variation_no: 0, terms_version: 'SYN-T1', snapshot_sha256: 'b'.repeat(64),
    warranty: ['SYNTHETIC: workmanship and fitment service for one year from handover, as set out in the policy.'], service_support: [],
    manufacturer_warranty_note: 'SYNTHETIC: appliances carry their maker\'s warranty.', warranty_exclusions: [{ code: 'SYN', text: 'SYNTHETIC: damage from misuse.' }] }],
  handover: { transition_id: 't1', handover_on: '2026-10-01', date_check: null, package_sha256: 'c'.repeat(64), acknowledged_on: null },
  policy: { version: 'WSV-POLICY-0', status: 'UNDECIDED', decisions: { 'WSV-D01': { label: 'structured terms', decided: false } } } };

function detail(state) {
  const status = state.status;
  return {
    id: 'r1', version: state.version, request_number: 'VS-SR-2026-000001', status, category: 'DOOR_OR_DRAWER', category_label: 'A door, shutter or drawer',
    priority: 'NORMAL', channel: 'PORTAL', reported_on: '2026-10-16', property_id: 'p1', project_id: 'pj1', owner: null, service_class: state.assessments.length ? 'WARRANTY' : null,
    outcome: state.assessments.at(-1)?.outcome ?? null, closure_code: null, cycle: 1, updated_on: '2026-10-16T10:00:00Z',
    description: LONG, area: 'Kitchen', space_id: null, noticed_on: '2026-10-14', related_request_id: null, duplicate_of_id: null, rejections: 0, closed_on: null,
    verified_by_kind: null, entitlement: ENTITLEMENT, assessments: state.assessments, visits: [], resolutions: [],
    notes: [{ id: 'n1', kind: 'INTERNAL', visibility: 'INTERNAL', text: 'SYNTHETIC: customer prefers mornings.', by: null, author: CARE, created_on: '2026-10-16T10:00:00Z' }],
    photos: [{ id: 'ph1', state: 'AVAILABLE', added_by: 'YOU', attachment_id: 'a1' }], evidence: [],
    actions: { triage: status === 'REPORTED', assess: status === 'TRIAGED', assign: status !== 'REPORTED', request_information: true, add_information: false,
      plan_visit: false, record_visit: false, add_evidence: false, resolve: false, verify: false, close: true, withdraw: true, reopen: false, view_audit: false },
    owner_options: [{ id: 'u-tech', display_name: 'SYNTHETIC Technician' }], evidence_options: [],
    vocabulary: { categories: [{ code: 'DOOR_OR_DRAWER', label: 'A door, shutter or drawer' }, { code: 'HARDWARE', label: 'Handles, hinges, channels or locks' }],
      outcomes: [{ code: 'COVERED', label: 'Covered by your warranty' }, { code: 'NOT_COVERED', label: 'Not covered by your warranty' },
        { code: 'INSPECTION_REQUIRED', label: 'We need to inspect it first' }], closures: ['DUPLICATE', 'CANNOT_SERVICE'], priorities: ['HIGH', 'NORMAL', 'LOW'],
      visit_kinds: ['INSPECTION', 'SERVICE'], max_rejections: 2 },
  };
}

async function serveStaff(p, state) {
  state.posts = [];
  await p.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const json = (status, body) => route.fulfill({ status, contentType: status < 400 ? 'application/json' : 'application/problem+json', body: JSON.stringify(body) });
    const ok = (data, status = 200) => json(status, { data });
    if (path === '/api/v1/auth/refresh') return ok({ access_token: 'synthetic-token' });
    if (path === '/api/v1/auth/me') return ok(ME);
    if (path === '/api/v1/service-requests' && req.method() === 'GET') return ok([{ ...detail(state) }, { ...detail(state), id: 'r2', request_number: 'VS-SR-2026-000002', status: 'CLOSED', owner: CARE }]);
    if (path === '/api/v1/service-requests/r1' && req.method() === 'GET') return ok(detail(state));
    if (req.method() === 'POST') {
      const body = req.postDataJSON() ?? {};
      state.posts.push({ path, body, ifMatch: req.headers()['if-match'] ?? null });
      state.version += 1;
      if (path.endsWith('/triage')) { state.status = 'TRIAGED'; return ok(detail(state)); }
      if (path.endsWith('/assessments')) {
        state.assessments.push({ id: 'as1', cycle: 1, outcome: body.outcome, outcome_label: 'Covered by your warranty', service_class: 'WARRANTY', basis_kind: 'WARRANTY_STATEMENT',
          basis_path: body.basis_path, as_of: '2026-10-16', coverage_status: null, explanation: body.explanation, internal_reason: body.internal_reason,
          period_basis: body.period_basis ?? null, assessed_by: CARE, assessed_on: '2026-10-16T11:00:00Z' });
        state.status = 'ASSESSED';
        return ok(detail(state));
      }
    }
    if (req.method() === 'GET') return ok([]);
    return json(404, { status: 404, code: 'NOT_FOUND', title: 'Not found' });
  });
}

// --- portal model ----------------------------------------------------------------------------------------------------------
const request = (state) => ({
  id: 'r1', reference: 'VS-SR-2026-000001', status: state.req, status_label: { REPORTED: 'Received', INFORMATION_REQUESTED: 'Waiting for your reply',
    RESOLVED: 'Please confirm it is resolved', CLOSED: 'Resolved' }[state.req], next: { REPORTED: 'VEDA_SPACES', INFORMATION_REQUESTED: 'YOU', RESOLVED: 'YOU', CLOSED: null }[state.req],
  category: 'A door, shutter or drawer', description: LONG, area: 'Kitchen', noticed_on: null, reported_on: '2026-10-16', project_id: 'pj1',
  photos: state.photos.map((id) => ({ id, state: 'AVAILABLE', added_by: 'YOU' })),
  messages: state.req === 'INFORMATION_REQUESTED' ? [{ from: 'VEDA_SPACES', label: 'Veda Spaces asked', text: 'When did you first notice the noise?', on: '2026-10-16T11:00:00Z' }]
    : state.answers.map((t) => ({ from: 'YOU', label: 'You replied', text: t, on: '2026-10-16T12:00:00Z' })),
  coverage: state.req === 'RESOLVED' || state.req === 'CLOSED' ? { outcome: 'COVERED', label: 'Covered by your warranty', explanation: 'We will re-align the channel at no cost.', chargeable_note: null } : null,
  visits: state.req === 'RESOLVED' ? [{ kind: 'Service visit', status: 'DONE', planned_on: '2026-10-17', done_on: '2026-10-17', note: 'Morning visit.' }] : [],
  resolution: state.req === 'RESOLVED' || state.req === 'CLOSED' ? { summary: 'We re-aligned the drawer channel; it now closes fully.', outcome: 'PENDING' } : null, evidence: [],
  can_add_information: state.req === 'INFORMATION_REQUESTED', can_add_photos: ['REPORTED', 'INFORMATION_REQUESTED'].includes(state.req),
  can_confirm: state.req === 'RESOLVED', can_reject: state.req === 'RESOLVED', can_withdraw: ['REPORTED', 'INFORMATION_REQUESTED'].includes(state.req),
});
const warranty = (state) => ({ available: true, max_photos: 6, categories: [{ code: 'DOOR_OR_DRAWER', label: 'A door, shutter or drawer' }, { code: 'HARDWARE', label: 'Handles, hinges, channels or locks' }],
  projects: [{ id: 'pj1', handed_over: true, can_report: true, requests: state.req ? [request(state)] : [],
    warranty: { state: 'REGISTERED', id: 'e1', handed_over_on: '2026-10-01', status: 'NOT_RECORDED', status_label: 'Not recorded in your portal',
      period_note: 'Your warranty period is as stated in your accepted quotation and the Veda Spaces Warranty, Service & Customer Care Policy.', coverage: [],
      statements: [{ kind: 'Warranty', text: 'SYNTHETIC: workmanship and fitment service for one year from handover, as set out in the policy.', source: 'VS-Q-2026-000001 v1' }],
      exclusions: ['SYNTHETIC: damage from misuse.'], manufacturer_notes: ['SYNTHETIC: appliances carry their maker\'s warranty.'], policy_url: null } }] });
const view = (state) => ({ id: 'p1', property: { reference: 'VS-P-2026-000001', configuration: '3 BHK apartment', locality: 'Synthetic Nagar', city: 'Hyderabad' },
  enquiry: { reference: '81DG-6BJR' }, headline: 'Your home has been handed over.', next_step: null, attention_count: 0, quotation: null, contact: null,
  project_tracking: true, payments: null, journey: [], quotations: [], included: null, commitments: null, responsibilities: null, support: null, commercials: null,
  documents: [{ kind: 'WARRANTY_SUMMARY', id: 'e1', title: 'Warranty summary', issued_on: '2026-10-01', project_id: 'pj1' }], attention: [], delivery: null, warranty: warranty(state) });

async function servePortal(p, state) {
  await p.addInitScript(() => sessionStorage.setItem('vs-portal-session', 'vpp_SYNTHETIC'));
  await p.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const json = (status, body) => route.fulfill({ status, contentType: status < 400 ? 'application/json' : 'application/problem+json', body: JSON.stringify(body) });
    const ok = (data, status = 200) => json(status, { data });
    const headers = req.headers();
    if (path === '/api/v1/auth/refresh') return json(401, { status: 401, code: 'AUTH_REQUIRED', title: 'Sign in' });
    if (headers['x-veda-portal'] !== 'vpp_SYNTHETIC' || headers.authorization) return json(401, { status: 401, code: 'PORTAL_SESSION_INVALID', title: 'Sign in' });
    const S = '/api/v1/public/portal/properties/p1/service-requests';
    if (path === '/api/v1/public/portal/properties/p1') return ok(view(state));
    if (path === S) { state.keys.push(headers['idempotency-key']); state.submitted.push(req.postDataJSON()); state.req = 'REPORTED'; return ok({ request: request(state) }, 201); }
    if (path === `${S}/r1/photos`) { state.declared.push(req.postDataJSON()); return ok({ photo_id: `ph${state.declared.length}`, upload: { required: true, method: 'PUT', url: `${S}/r1/photos/ph${state.declared.length}/content`, then: '' } }, 201); }
    if (/\/photos\/ph\d+\/content$/.test(path) && req.method() === 'PUT') { state.bytes += 1; return ok({ received: true }); }
    if (/\/photos\/ph\d+\/complete$/.test(path)) { state.photos.push(path.split('/').at(-2)); return ok({ request: request(state) }); }
    if (/\/photos\/ph\d+\/content$/.test(path)) return route.fulfill({ status: 200, contentType: 'image/png', headers: { 'cache-control': 'no-store' }, body: PNG });
    if (path === `${S}/r1/information`) { state.answers.push(req.postDataJSON().text); state.req = 'RESOLVED'; return ok({ request: request(state) }); }
    if (path === `${S}/r1/confirm`) { state.confirms += 1; state.req = 'CLOSED'; return ok({ request: request(state) }); }
    return json(404, { status: 404, code: 'NOT_FOUND', title: 'Not found' });
  });
}
const freshPortal = () => ({ req: null, keys: [], submitted: [], declared: [], bytes: 0, photos: [], answers: [], confirms: 0 });

async function axe(p, name) {
  await p.addScriptTag({ content: AXE });
  const v = await p.evaluate(async () => (await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }))
    .violations.map((x) => `${x.id} (${x.nodes.length}): ${x.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')}`));
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
      .map((n) => { const x = n.type === 'checkbox' ? n.closest('label') ?? n : n; const r = x.getBoundingClientRect();
        return { what: `${n.tagName.toLowerCase()} ${(n.textContent || n.name || n.id || '').trim().slice(0, 30)}`, w: Math.round(r.width), h: Math.round(r.height) }; })
      .filter((x) => x.w < 44 || x.h < 44);
  }, tag);
  check(`${name}: targets at least 44 px`, small.length === 0, JSON.stringify(small.slice(0, 5)));
}

const staff = (p) => p.locator('vs-service-request-page');
const dialogDone = (p) => p.waitForFunction(() => {
  const find = (root) => { const el = root.querySelector('vs-service-request-page'); if (el) return el; for (const n of root.querySelectorAll('*')) { if (n.shadowRoot) { const f = find(n.shadowRoot); if (f) return f; } } return null; };
  const el = find(document);
  return el && !el.shadowRoot.querySelector('vs-dialog[open]');
});
const activeName = (p) => p.evaluate(() => { let a = document.activeElement; while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement; return a?.getAttribute('name') || a?.id || a?.tagName; });

const browser = await chromium.launch();
try {
  // --- staff journey at desktop width ---------------------------------------------------------------------------------
  {
    const state = { status: 'REPORTED', version: 3, assessments: [] };
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    await serveStaff(p, state);
    await p.goto(`${BASE}/service`);
    const list = p.locator('vs-service-list-page');
    await list.getByRole('link', { name: 'VS-SR-2026-000001' }).waitFor();
    check('queue: requests with status and owner, from the portal', await list.getByText('From the portal').first().isVisible() && await list.getByText('Unassigned').first().isVisible());
    await list.getByRole('link', { name: 'VS-SR-2026-000001' }).click();
    await staff(p).locator('#page-title').waitFor();
    check('request: the customer\'s words, the frozen warranty statements and internal notes marked as such',
      await staff(p).getByText(LONG).isVisible() && await staff(p).getByText(/SYNTHETIC: workmanship and fitment service/).isVisible()
      && await staff(p).getByText(/internal/).first().isVisible());
    await staff(p).getByRole('button', { name: 'Triage', exact: true }).click();
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await dialogDone(p);
    check('triage: sent with the row version', state.posts.at(-1)?.path.endsWith('/triage') && state.posts.at(-1)?.ifMatch !== null);
    await staff(p).getByRole('button', { name: 'Decide coverage' }).click();
    await staff(p).locator('vs-dialog select[name=outcome]').selectOption('COVERED');
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await staff(p).locator('vs-dialog textarea[aria-invalid=true]').first().waitFor();
    check('coverage: the customer explanation and internal reason are required, nothing sent', !state.posts.some((x) => x.path.endsWith('/assessments')));
    await staff(p).locator('vs-dialog select[name=basis_path]').selectOption('sources/0/warranty/0');
    await staff(p).locator('vs-dialog textarea[name=period_basis]').fill('Reported fifteen days after handover.');
    await staff(p).locator('vs-dialog textarea[name=explanation]').fill('This is covered by your warranty; we will fix it.');
    await staff(p).locator('vs-dialog textarea[name=internal_reason]').fill('Channel mis-aligned at installation.');
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await dialogDone(p);
    const a = state.posts.find((x) => x.path.endsWith('/assessments'));
    check('coverage: decided on a cited statement with its period basis', a?.body.basis_path === 'sources/0/warranty/0' && !!a?.body.period_basis && a?.ifMatch !== null);
    check('coverage: recorded with both texts kept apart', await staff(p).getByText('This is covered by your warranty; we will fix it.').isVisible()
      && await staff(p).getByText('Channel mis-aligned at installation.', { exact: false }).isVisible());
    check('staff journey: no page errors', errors.length === 0, errors.join(' | '));
    await ctx.close();
  }
  // --- portal journey at a phone width ---------------------------------------------------------------------------------
  {
    const state = freshPortal();
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    await servePortal(p, state);
    await p.goto(`${BASE}/portal/properties/p1`);
    const proj = p.locator('vs-portal-project-page');
    await proj.locator('#h-service').waitFor();
    const svc = proj.locator('vs-portal-service');
    check('warranty: not shown as covered; the accepted quotation and the policy are named', await svc.getByText('Not recorded in your portal').isVisible()
      && await svc.getByText(/as stated in your accepted quotation/).isVisible() && !(await svc.textContent()).toLowerCase().includes('you are covered'));
    await svc.getByRole('button', { name: 'Report a problem' }).click();
    check('report: the form opens with focus on the first field', (await activeName(p)) === 'category');
    await svc.getByRole('button', { name: 'Send request' }).click();
    await svc.getByRole('alert').waitFor();
    check('report: too short is explained, nothing sent', state.submitted.length === 0);
    await svc.locator('textarea[name=description]').fill(LONG);
    await svc.locator('input[name=area]').fill('Kitchen');
    await svc.locator('input[name=photos]').setInputFiles({ name: 'drawer.png', mimeType: 'image/png', buffer: PNG });
    await svc.getByRole('button', { name: 'Send request' }).click();
    await svc.getByText(/has been received with 1 photo/).waitFor();
    check('report: sent once with a key; the photo resized to JPEG on the device, uploaded and completed',
      state.submitted.length === 1 && !!state.keys[0] && state.declared[0]?.mime_type === 'image/jpeg' && state.bytes === 1 && state.photos.length === 1);
    await svc.getByText('Received').first().waitFor();
    // Veda asks something; the customer replies
    state.req = 'INFORMATION_REQUESTED';
    await p.reload();
    await proj.locator('#h-service').waitFor();
    await svc.getByRole('button', { name: 'Reply to VS-SR-2026-000001' }).click();
    await svc.locator('textarea[name=text]').fill('About two days ago.');
    await svc.getByRole('button', { name: 'Send', exact: true }).click();
    await svc.getByRole('button', { name: /^It is resolved/ }).waitFor();
    check('reply: sent, and the resolution is offered for confirmation', state.answers.length === 1 && await svc.getByText('We re-aligned the drawer channel; it now closes fully.').isVisible());
    await svc.getByRole('button', { name: /^It is resolved/ }).click();
    await svc.getByText('Resolved').first().waitFor();
    check('confirm: once, and the request reads resolved', state.confirms === 1);
    check('portal journey: no page errors', errors.length === 0, errors.join(' | '));
    await ctx.close();
  }
  // --- layout, targets and axe at every width ----------------------------------------------------------------------------
  for (const [name, viewport] of [['360 px', { width: 360, height: 740 }], ['390 px', { width: 390, height: 844 }],
    ['768 px', { width: 768, height: 1024 }], ['1280 px', { width: 1280, height: 800 }]]) {
    const ctx = await browser.newContext({ viewport });
    const s = await ctx.newPage();
    await serveStaff(s, { status: 'TRIAGED', version: 3, assessments: [] });
    await s.goto(`${BASE}/service`);
    await s.locator('vs-service-list-page').getByRole('link', { name: 'VS-SR-2026-000001' }).waitFor();
    await layout(s, 'vs-service-list-page', `${name} staff queue`);
    await axe(s, `${name} staff queue`);
    await s.goto(`${BASE}/service/r1`);
    await staff(s).locator('#page-title').waitFor();
    await layout(s, 'vs-service-request-page', `${name} staff request`);
    await axe(s, `${name} staff request`);
    await s.screenshot({ path: `${OUT}/warranty-staff-${viewport.width}.png`, fullPage: true });
    const c = await ctx.newPage();
    const st = freshPortal();
    st.req = 'RESOLVED';
    st.photos = ['ph1'];
    await servePortal(c, st);
    await c.goto(`${BASE}/portal/properties/p1`);
    await c.locator('vs-portal-project-page #h-service').waitFor();
    await c.locator('vs-portal-project-page #service').scrollIntoViewIfNeeded();
    await c.locator('vs-portal-service').getByRole('button', { name: 'Report a problem' }).click();
    await layout(c, 'vs-portal-project-page', `${name} portal warranty and service`);
    await axe(c, `${name} portal warranty and service`);
    await c.screenshot({ path: `${OUT}/warranty-portal-${viewport.width}.png`, fullPage: true });
    await ctx.close();
  }
} finally {
  await browser.close();
}
const failed = results.filter((x) => !x).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
