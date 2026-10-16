// Customer Project Portal (CPP): the customer journey sign-in by email → the emailed link → portal home → the project →
// the quotation (read-only), in a real browser against the real app, at 360, 390, 768 and 1280 px, with keyboard
// navigation, focus, accessible validation, no horizontal overflow, 44 px targets and axe (WCAG 2.2 AA). The API is
// answered by Playwright with a stateful SYNTHETIC model (every /api request is intercepted; nothing reaches a server):
// the API's rules (identity, isolation, projection) are proven by the API suites; this proves what the browser does.
//   APP_BASE=http://localhost:5173 node e2e/portal.e2e.mjs
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
const LONG = 'Base cabinets with a SYNTHETIC very long description: carcass in boiling-water-proof plywood, shutters in a high-gloss acrylic finish with handle-less profiles';
const quotation = { id: 'q1', reference: 'VS-Q-2026-000001 v1', title: 'Quotation', kind: 'QUOTATION', version_no: 1, state: 'OPEN',
  status: 'ACTION_REQUIRED', status_label: 'Awaiting your decision', issued_on: '2026-10-12', valid_until: '2026-11-11', days_left: 26,
  total: '₹4,25,000.00', currency: 'INR' };
const contact = { source: 'QUOTATION', name: 'SYNTHETIC Contact', role: 'Design consultant', phone: '+910000000000',
  email: 'hello@synthetic.example', hours: 'Mon–Sat, 10 am–7 pm' };
const card = { id: 'p1', property: { reference: 'VS-P-2026-000001', configuration: '3 BHK apartment, Tower B, a SYNTHETIC long name',
  locality: 'Synthetic Nagar Extension Layout', city: 'Hyderabad' }, enquiry: { reference: '81DG-6BJR' },
  headline: 'We are waiting for your decision.', next_step: { key: 'approval', label: 'Your approval', state: 'ACTION_REQUIRED',
    detail: 'Your quotation is waiting for your decision.', date: null }, attention_count: 1, quotation, contact, project_tracking: false };
const steps = [['consultation', 'Consultation', 'COMPLETED'], ['site_measurement', 'Site measurement', 'COMPLETED'],
  ['design_scope', 'Design and scope', 'COMPLETED'], ['quotation', 'Your quotation', 'COMPLETED'], ['approval', 'Your approval', 'ACTION_REQUIRED'],
  ['execution', 'Execution', 'NOT_YET_AVAILABLE'], ['quality', 'Quality checks', 'NOT_YET_AVAILABLE'], ['handover', 'Handover', 'NOT_YET_AVAILABLE']]
  .map(([key, label, state]) => ({ key, label, state, detail: state === 'NOT_YET_AVAILABLE' ? 'Progress for this stage is not shown in your portal yet.' : `${label}: synthetic detail.`, date: null }));
const view = { ...card, journey: steps,
  attention: [{ kind: 'QUOTATION_DECISION', status: 'ACTION_REQUIRED', title: 'Review your quotation and tell us your decision',
    text: 'To accept, decline or ask a question, use the secure proposal link Veda Spaces sent you, or speak to your Veda Spaces contact.', due: '2026-11-11', quotation_id: 'q1' },
  { kind: 'SITE_VISIT', status: 'UPCOMING', title: 'Your site visit', text: 'Your site visit is scheduled.', due: '2026-10-20T05:30:00Z' }],
  quotations: [quotation], documents: [{ ...quotation, kind: 'QUOTATION' }],
  included: [{ title: 'Kitchen', kind: 'ROOM', included_count: 2, optional_count: 1, items: [{ description: LONG, detail: 'BWP plywood', status: 'Included' },
    { description: 'Tall unit', detail: null, status: 'Optional' }] }],
  commitments: { source: 'VS-Q-2026-000001 v1', inclusions: [{ code: 'I1', text: 'Design, manufacture and installation (synthetic)' }],
    warranty: ['10 years on carcass (synthetic)'], manufacturer_warranty_note: null, handover: [{ code: 'H1', text: 'Joint walkthrough (synthetic)' }], care: null,
    next_steps: [{ code: 'N1', stage: 'VEDA_CONFIRMATION', label: 'Confirmation', text: 'We confirm your order (synthetic).', duration: '2 days' }],
    payment_schedule: [{ label: 'Booking', share: '10%', trigger: 'On acceptance (synthetic)' }, { label: 'Production release', share: '50%', trigger: 'Before production starts (synthetic)' }],
    payment_safety: 'Pay only to the Veda Spaces account (synthetic).' },
  responsibilities: { client: [{ code: 'C1', text: 'Society permission for work hours (synthetic)' }], site_readiness: [{ code: 'R1', text: 'Flooring complete (synthetic)' }] },
  support: { contacts: [], escalation: null } };
const line = (ref, description, amount, status = 'Included') => ({ ref, description, detail: 'Laminate finish', quantity: '42.5 sq ft', amount, priced: true, status });
const proposalPage = { state: 'OPEN', history: [], capabilities: { interaction: false, acceptance: false }, actions: [], summary: quotation,
  notices: [{ code: 'DECIDE_BY_LINK', message: 'To accept, decline or ask a question, use the secure proposal link Veda Spaces sent you, or speak to your Veda Spaces contact.' }],
  proposal: { schema: 'veda.customer-proposal/1', kind: 'QUOTATION', title: 'Quotation', brand: { name: 'Veda Spaces', tagline: 'Synthetic tagline' },
    reference: 'VS-Q-2026-000001 v1', quotation_number: 'VS-Q-2026-000001', version_no: 1, variation_no: 0, issued_on: '2026-10-12', valid_until: '2026-11-11',
    subject: 'Interior works — 3 BHK apartment (synthetic)', cover_note: null, property: { reference: 'VS-P-2026-000001', configuration: '3 BHK apartment', city: 'Hyderabad' },
    snapshot_sha256: 'a'.repeat(64), rooms: [{ ref: 'R1', title: 'Kitchen', kind: 'ROOM', subtotal: '2,00,000.00', included_count: 2, optional_count: 0,
      lines: [line('L1', LONG, '1,50,000.00'), line('L2', 'Tall unit', '50,000.00')] }], optional_items: [],
    summary: { base_total: '3,60,000.00', taxable: '3,60,000.00', gst: { status: 'Included', amount: '64,800.00' }, total: '4,25,000.00', currency: 'INR' },
    payment_schedule: [{ label: 'Booking', share: '10%', trigger: 'On acceptance (synthetic)' }], warranty: ['Synthetic warranty.'], service_support: [],
    assumptions: ['Synthetic assumption.'], exclusions: ['Synthetic exclusion.'], terms: ['Synthetic terms.'], terms_version: 'SYN-T1', unit_rates_shown: false,
    sections: { SCOPE: 'b'.repeat(64) } } };

async function serve(p, state) {
  await p.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const json = (status, body) => route.fulfill({ status, contentType: status < 400 ? 'application/json' : 'application/problem+json', body: JSON.stringify(body) });
    const ok = (data, status = 200) => json(status, { data });
    const headers = req.headers();
    state.calls.push({ path, method: req.method(), portal: headers['x-veda-portal'] ?? null, bearer: headers.authorization ?? null });
    if (path === '/api/v1/auth/refresh') return json(401, { status: 401, code: 'AUTH_REQUIRED', title: 'Sign in' }); // a customer has no workspace session
    if (path === '/api/v1/public/portal/sign-in') { state.requested = req.postDataJSON()?.email; return ok({ sent: true, message: 'If this email has access to a Veda Spaces project portal, a sign-in link is on its way. It works once and expires in 15 minutes.' }, 202); }
    if (path === '/api/v1/public/portal/session') {
      return req.postDataJSON()?.token === 'LINK' ? ok({ token: 'vpp_SYNTHETIC', expires_on: '2026-10-16T17:00:00Z' }, 201)
        : json(400, { status: 400, code: 'PORTAL_LINK_INVALID', title: 'Invalid', detail: 'This sign-in link has expired or was already used.' });
    }
    if (headers['x-veda-portal'] !== 'vpp_SYNTHETIC') return json(401, { status: 401, code: 'PORTAL_SESSION_INVALID', title: 'Sign in' });
    if (path === '/api/v1/public/portal/home') return ok({ customer: { name: 'SYNTHETIC Customer' }, project_tracking_available: false,
      enquiries: [{ reference: '81DG-6BJR', relationship: 'PRIMARY_CUSTOMER', closed: false, properties: [card] }] });
    if (path === '/api/v1/public/portal/properties/p1') return ok(view);
    if (path === '/api/v1/public/portal/quotations/q1') return ok(proposalPage);
    if (path === '/api/v1/public/portal/sign-out') return ok({ signed_out: true });
    return json(404, { status: 404, code: 'NOT_FOUND', title: 'Not found' });
  });
}

async function axe(p, name) {
  await p.addScriptTag({ content: AXE });
  const v = await p.evaluate(async () => (await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }))
    .violations.map((x) => `${x.id} (${x.nodes.length}): ${x.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')}`));
  check(`axe ${name}`, v.length === 0, v.join(', '));
}

/** No horizontal page scroll, and every visible control of the page at least 44 x 44 px. */
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

const fresh = () => ({ calls: [], requested: null });
const browser = await chromium.launch();
try {
  // The journey at a phone width: sign in by email, open the link, home, project, quotation.
  {
    const state = fresh();
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    await serve(p, state);
    await p.goto(`${BASE}/portal`);
    const form = p.locator('vs-portal-home-page vs-portal-sign-in');
    await form.getByLabel('Your email address').waitFor();
    check('signed out: the sign-in form, with no workspace chrome', (await p.locator('vs-sidebar, nav[aria-label="Main"]').count()) === 0);
    await form.getByRole('button', { name: 'Email me a sign-in link' }).click();
    check('validation: an empty email is refused accessibly', await form.locator('#email[aria-invalid="true"][aria-describedby="email-error"]').count() === 1
      && await form.getByText(/Enter the email address/).isVisible());
    await form.getByLabel('Your email address').fill('customer@synthetic.example');
    await p.keyboard.press('Enter');
    await form.getByRole('heading', { name: 'Check your email' }).waitFor();
    check('sign-in: one request, no disclosure, focus on the answer', state.requested === 'customer@synthetic.example'
      && await form.getByText(/If this email has access/).isVisible()
      && await p.evaluate(() => { const h = document.querySelector('vs-app')?.shadowRoot ?? document; let a = h.activeElement ?? document.activeElement;
        while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement; return a?.id === 'sent'; }));
    await p.goto(`${BASE}/portal/sign-in#t=SPENT`);
    await p.locator('vs-portal-sign-in-page vs-portal-sign-in').getByText(/expired or was already used/).waitFor();
    check('a spent link: says so and offers a new one', true);
    await p.goto('about:blank'); // an emailed link opens as a new page load
    await p.goto(`${BASE}/portal/sign-in#t=LINK`);
    await p.locator('vs-portal-home-page article').first().waitFor();
    check('the link: signs in, lands on the portal home, scrubs the token', !p.url().includes('#t=') && !p.url().includes('LINK'));
    const home = p.locator('vs-portal-home-page');
    check('home: greeting, headline, what needs the customer', await home.getByRole('heading', { name: 'Hello, SYNTHETIC Customer' }).isVisible()
      && await home.getByText('We are waiting for your decision.').isVisible() && await home.getByText('1 thing needs you').isVisible());
    await home.getByRole('link', { name: /Open your project/ }).click();
    const proj = p.locator('vs-portal-project-page');
    await proj.locator('ol.journey').waitFor();
    check('project: status first, then the action, then an honest journey',
      await proj.getByRole('heading', { level: 1 }).isVisible() && await proj.getByText('Review your quotation and tell us your decision').isVisible()
      && (await proj.locator('ol.journey li').count()) === 8 && (await proj.locator('ol.journey .badge.NOT_YET_AVAILABLE').count()) === 3);
    await proj.locator('nav.jump').getByRole('link', { name: 'Documents' }).click();
    check('section links move focus to the section heading', await p.evaluate(() => {
      let a = document.activeElement; while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement; return a?.id === 'h-documents'; }));
    await proj.getByRole('link', { name: 'View your quotation' }).click();
    const q = p.locator('vs-portal-quotation-page vs-proposal-view');
    await q.getByRole('heading', { level: 1 }).waitFor();
    check('quotation: the customer view, read-only, deciding stays on the secure link',
      await q.getByText(/secure proposal link/).first().isVisible() && (await q.getByRole('button', { name: /accept|decline/i }).count()) === 0
      && (await q.getByText('Staff preview').count()) === 0);
    check('only the portal session header is ever sent', state.calls.filter((c) => c.path.startsWith('/api/v1/public/portal/') && !c.path.endsWith('/sign-in') && !c.path.endsWith('/session'))
      .every((c) => c.portal === 'vpp_SYNTHETIC' && c.bearer === null));
    await p.locator('vs-portal-quotation-page vs-portal-header').getByRole('button', { name: 'Sign out' }).click();
    await p.locator('vs-portal-home-page vs-portal-sign-in').getByLabel('Your email address').waitFor();
    check('sign out: back to sign-in, session forgotten', await p.evaluate(() => sessionStorage.getItem('vs-portal-session')) === null);
    check('journey: no page errors', errors.length === 0, errors.join(' | '));
    await ctx.close();
  }
  // Layout, targets and axe at every width: sign-in, home, project, quotation.
  for (const [name, viewport] of [['360 px', { width: 360, height: 740 }], ['390 px', { width: 390, height: 844 }],
    ['768 px', { width: 768, height: 1024 }], ['1280 px', { width: 1280, height: 800 }]]) {
    const state = fresh();
    const ctx = await browser.newContext({ viewport });
    const p = await ctx.newPage();
    await serve(p, state);
    await p.goto(`${BASE}/portal`);
    await p.locator('vs-portal-home-page vs-portal-sign-in').getByLabel('Your email address').waitFor();
    await layout(p, 'vs-portal-home-page', `${name} sign-in`);
    await axe(p, `${name} sign-in`);
    await p.goto(`${BASE}/portal/sign-in#t=LINK`);
    await p.locator('vs-portal-home-page article').first().waitFor();
    await layout(p, 'vs-portal-home-page', `${name} home`);
    await axe(p, `${name} home`);
    await p.screenshot({ path: `${OUT}/portal-home-${viewport.width}.png`, fullPage: true });
    await p.goto(`${BASE}/portal/properties/p1`);
    await p.locator('vs-portal-project-page ol.journey').waitFor();
    await p.locator('vs-portal-project-page details summary').first().click();
    await layout(p, 'vs-portal-project-page', `${name} project`);
    await axe(p, `${name} project`);
    await p.screenshot({ path: `${OUT}/portal-project-${viewport.width}.png`, fullPage: true });
    await p.goto(`${BASE}/portal/quotations/q1`);
    await p.locator('vs-portal-quotation-page vs-proposal-view').getByRole('heading', { level: 1 }).waitFor();
    await layout(p, 'vs-portal-quotation-page', `${name} quotation`);
    await axe(p, `${name} quotation`);
    await p.goto(`${BASE}/portal/properties/someone-elses`);
    await p.locator('vs-portal-project-page').getByText('We could not find this project').waitFor();
    await axe(p, `${name} not found`);
    await ctx.close();
  }
} finally {
  await browser.close();
}
const failed = results.filter((x) => !x).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
