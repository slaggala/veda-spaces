// Customer Promise portal (decision log 37): the staff journey landing → edit a section → submit → review → approve →
// publish → what changed → customer preview, in a real browser against the real app, at 360, 390, 768 and 1280 px,
// with no horizontal overflow, 44 px targets and axe. The API is answered by Playwright with SYNTHETIC models (every
// /api request is intercepted; nothing reaches a server): the API's own rules (four-eyes, content rules, concurrency)
// are proven by the API suites; this proves what the staff browser does with them.
//   APP_BASE=http://localhost:5173 node e2e/promise.e2e.mjs
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

const PERMS = ['customer_promise.view', 'customer_promise.draft.create', 'customer_promise.edit', 'customer_promise.contacts.edit',
  'customer_promise.warranty.edit', 'customer_promise.payment_safety.edit', 'customer_promise.submit', 'customer_promise.review',
  'customer_promise.review.sensitive', 'customer_promise.approve', 'customer_promise.publish', 'customer_promise.preview',
  'customer_promise.audit.read', 'profile.read'];
const ME = { id: 'u-syn', email: 'reviewer@synthetic.example', full_name: 'SYNTHETIC Reviewer', display_name: 'SYNTHETIC', phone: null,
  timezone: 'Asia/Kolkata', locale: 'en-IN', status: 'ACTIVE', roles: [], authz_version: 1,
  permissions: Object.fromEntries(PERMS.map((p) => [p, 'ALL'])), suspended_permissions: [],
  session: { type: 'FULL', auth_methods: ['pwd', 'totp'], mfa_verified_on: '2026-10-15T10:00:00Z', cooling_off_until: null },
  mfa: { required: true, required_by: ['ROLE'], enrolled: true }, email_change: null, features: { customer_promise_admin: true }, version: 1 };

// SYNTHETIC content: invented for the browser journey, not Veda Spaces content.
const SECTIONS = [['CONTACTS', 'Contact and support', ['email_domains', 'contacts', 'support_escalation'], false, 'customer_promise.contacts.edit'],
  ['INCLUSIONS', 'Project inclusions', ['project_inclusions'], false, 'customer_promise.edit'],
  ['RESPONSIBILITIES', 'Customer responsibilities', ['client_responsibilities'], true, 'customer_promise.edit'],
  ['SITE_READINESS', 'Site readiness', ['site_readiness'], false, 'customer_promise.edit'],
  ['SITE_WORK', 'Site-dependent work', ['site_dependent_work'], true, 'customer_promise.edit'],
  ['WARRANTY', 'Warranty and service', ['manufacturer_warranty_note'], true, 'customer_promise.warranty.edit'],
  ['EXCLUSIONS', 'Warranty exclusions', ['warranty_exclusions'], true, 'customer_promise.warranty.edit'],
  ['SERVICE', 'Service guidance', ['service_guidance'], false, 'customer_promise.contacts.edit'],
  ['HANDOVER', 'Handover', ['handover'], false, 'customer_promise.edit'], ['CARE', 'Care guidance', ['care'], false, 'customer_promise.edit'],
  ['NEXT_STEPS', 'What happens next', ['next_steps'], false, 'customer_promise.edit'],
  ['PAYMENT_SAFETY', 'Payment safety', ['payment_safety'], true, 'customer_promise.payment_safety.edit']];
const VOCAB = { sections: SECTIONS.map(([code, title, keys, sensitive, edit]) => ({ code, title, keys, sensitive, edit_permission: edit,
  review_permission: sensitive ? 'customer_promise.review.sensitive' : 'customer_promise.review' })), areas: [],
  contact_kinds: ['QUOTATION', 'SUPPORT', 'SERVICE'], responsibility_categories: ['APPLIANCE_MODEL', 'OTHER'],
  responsibility_statuses: ['REQUIRED', 'NOT_REQUIRED', 'TO_BE_CONFIRMED'], readiness_categories: ['FLOORING', 'OTHER'],
  readiness_statuses: ['READY', 'NOT_READY', 'CUSTOMER_ACTION_REQUIRED', 'NOT_APPLICABLE', 'TO_BE_CONFIRMED'], site_work_categories: ['ELECTRICAL'],
  handover_categories: ['CLEANING'], care_categories: ['FURNITURE_CLEANING'], stages: ['PROPOSAL_ACCEPTED', 'VEDA_CONFIRMATION', 'HANDOVER'],
  limits: { copy: 600, label: 80, duration: 80, summary: 500 } };
const CONTACT = { code: 'SYN_DESK', kind: 'SUPPORT', display_name: 'SYNTHETIC Support Desk with a deliberately long name to wrap', role: 'Care (synthetic)',
  phone: '+00 0000 000000', email: 'care@synthetic.example', hours: 'SYNTHETIC hours', channel_note: null, business_channel_approved: true };
const VALUES = {
  CONTACTS: { email_domains: ['synthetic.example'], contacts: [CONTACT], support_escalation: 'SYNTHETIC escalation route.' },
  INCLUSIONS: { project_inclusions: [{ code: 'SYN_INSTALL', text: 'SYNTHETIC installation of the listed items.' }] },
  RESPONSIBILITIES: { client_responsibilities: [{ code: 'SYN_APPL', category: 'APPLIANCE_MODEL', text: 'SYNTHETIC: share appliance models.', default_status: 'REQUIRED' }] },
  SITE_READINESS: { site_readiness: [] }, SITE_WORK: { site_dependent_work: { intro: 'SYNTHETIC: some needs show only on site.',
    approval_rule: 'SYNTHETIC: agreed first as a variation.', categories: [{ code: 'SYN_E', category: 'ELECTRICAL', text: 'SYNTHETIC electrical changes.' }] } },
  WARRANTY: { manufacturer_warranty_note: 'SYNTHETIC manufacturer note.' }, EXCLUSIONS: { warranty_exclusions: [] },
  SERVICE: { service_guidance: { contact_code: 'SYN_DESK', what_to_provide: ['SYNTHETIC: your reference.'], reference_process: null, escalation: null } },
  HANDOVER: { handover: [] }, CARE: { care: [] },
  NEXT_STEPS: { next_steps: [{ code: 'SYN_A', stage: 'PROPOSAL_ACCEPTED', label: 'Accepted', text: 'SYNTHETIC step.', duration: null }] },
  PAYMENT_SAFETY: { payment_safety: 'SYNTHETIC: pay only through recorded channels.' },
};
const AREAS = ['Your Veda Spaces contact', 'Project inclusions', 'Customer responsibilities', 'Site readiness', 'Site-dependent work',
  'Manufacturer warranty', 'Veda Spaces service and workmanship support', 'Warranty exclusions', 'How to request service',
  'Handover expectations', 'Care guidance', 'What happens after approval', 'Payment safety', 'Support and escalation'];
const who = { id: 'u-a', display_name: 'SYNTHETIC Author' };

function model(state) {
  const s = state.status;
  const summary = { id: 'p1', version: state.version, version_no: 1, status: s, origin: 'NEW', content_version: 'CPP-1', change_summary: 'SYNTHETIC first pack',
    based_on_version: null, content_sha256: 'a'.repeat(64), created_on: '2026-10-15T10:00:00Z', created_by: who, updated_on: null,
    submitted_on: s !== 'DRAFT' ? '2026-10-15T10:10:00Z' : null, submitted_by: s !== 'DRAFT' ? who : null,
    approved_on: ['APPROVED', 'PUBLISHED'].includes(s) ? '2026-10-15T10:20:00Z' : null, approved_by: ['APPROVED', 'PUBLISHED'].includes(s) ? who : null,
    published_on: s === 'PUBLISHED' ? '2026-10-15T10:30:00Z' : null, published_by: s === 'PUBLISHED' ? who : null, published_sha256: null,
    superseded_on: null, superseded_by_version: null, effective: s === 'PUBLISHED' ? 'CURRENT' : 'NOT_EFFECTIVE', quotations: {} };
  const pending = s === 'IN_REVIEW' && !state.reviewed ? ['INCLUSIONS'] : [];
  return { ...summary,
    sections: SECTIONS.map(([code, title, keys, sensitive, edit]) => ({ code, title, keys, sensitive, edit_permission: edit,
      review_permission: sensitive ? 'customer_promise.review.sensitive' : 'customer_promise.review', changed: code === 'INCLUSIONS',
      value: state.values[code], sha256: 'b'.repeat(64), contributors: code === 'INCLUSIONS' ? [who] : [],
      review: code === 'INCLUSIONS' && state.reviewed ? { decision: 'APPROVED', by: who, on: '2026-10-15T10:15:00Z', comment: null } : null,
      can_edit: s === 'DRAFT', can_review: s === 'IN_REVIEW' && code === 'INCLUSIONS' && !state.reviewed })),
    changed_sections: ['INCLUSIONS'], pending_reviews: pending, problems: [], reviews: state.reviewed
      ? [{ id: 'r1', round: 1, section: 'INCLUSIONS', decision: 'APPROVED', comment: null, by: who, on: '2026-10-15T10:15:00Z', current: true }] : [],
    actions: { save: s === 'DRAFT', summary: s === 'DRAFT', discard: s === 'DRAFT', submit: s === 'DRAFT', approve: s === 'IN_REVIEW' && !pending.length,
      return: ['IN_REVIEW', 'APPROVED'].includes(s), publish: s === 'APPROVED', preview: true, history: true },
    events: [{ code: 'DRAFT_CREATED', section: null, from: null, to: 'DRAFT', reason: null, detail: null, by: who, on: '2026-10-15T10:00:00Z' }] };
}

async function serve(p, state) {
  state.puts = [];
  await p.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const json = (status, body) => route.fulfill({ status, contentType: status < 400 ? 'application/json' : 'application/problem+json', body: JSON.stringify(body) });
    const ok = (data) => json(200, { data });
    if (path === '/api/v1/auth/refresh') return ok({ access_token: 'synthetic-token' });
    if (path === '/api/v1/auth/me') return ok(ME);
    if (path === '/api/v1/customer-promise') {
      return ok({ authority: { state: 'NOT_RECORDED', register_reference: null, decided_on: null,
        message: 'Owner decision OI-MTQ-18 is not recorded: quotations show every customer information section as to be confirmed, whatever is published here.' },
        published: state.status === 'PUBLISHED' ? model(state) : null, open: state.status === 'PUBLISHED' ? null : model(state), pending_reviews: [],
        areas: AREAS.map((title, i) => ({ code: `A${i}`, title, section: i === 6 ? null : 'INCLUSIONS', governed_by: i === 6 ? 'OI-MTQ-09' : 'OI-MTQ-18',
          status: 'NOT_STARTED', structure_exists: true, owner_approved_content: false, customer_sees: 'TO_BE_CONFIRMED' })),
        versions: 1, effective_dating: 'IMMEDIATE_ON_PUBLISH', actions: { create_draft: false, preview: true, history: true } });
    }
    if (path === '/api/v1/customer-promise/vocabulary') return ok(VOCAB);
    if (path === '/api/v1/customer-promise/versions') return ok([model(state)]);
    if (path === '/api/v1/customer-promise/versions/p1/changes') {
      return ok({ from: null, to: { pack_id: 'p1', version_no: 1, status: state.status }, changes: [
        { section: 'INCLUSIONS', change: 'ADDED', subject: 'Project inclusion', item: 'SYN_INSTALL', message: 'Project inclusion added: SYN_INSTALL', before: null,
          after: state.values.INCLUSIONS.project_inclusions[0].text }] });
    }
    if (path === '/api/v1/customer-promise/versions/p1/preview') {
      return ok({ label: state.status === 'PUBLISHED' ? 'PUBLISHED' : 'PREVIEW / NOT PUBLISHED', published: state.status === 'PUBLISHED', pack_id: 'p1',
        version_no: 1, status: state.status, content_version: 'CPP-1', creates: { quotation: false, customer_link: false, acceptance_evidence: false },
        information: { content_version: 'CPP-1', contacts: { quotation: null, support: [CONTACT], service: [] }, support_escalation: 'SYNTHETIC escalation route.',
          project_inclusions: state.values.INCLUSIONS.project_inclusions, client_responsibilities: [{ code: 'SYN_APPL', category: 'APPLIANCE_MODEL', text: 'SYNTHETIC: share appliance models.', status: 'REQUIRED' }],
          site_readiness: null, site_dependent_work: { ...VALUES.SITE_WORK.site_dependent_work }, manufacturer_warranty_note: 'SYNTHETIC manufacturer note.',
          warranty_exclusions: null, service_guidance: { contact: CONTACT, what_to_provide: ['SYNTHETIC: your reference.'], reference_process: null, escalation: null },
          handover: null, care: null, next_steps: VALUES.NEXT_STEPS.next_steps, payment_safety: 'SYNTHETIC: pay only through recorded channels.' } });
    }
    const write = (next) => { if (req.headers()['if-match'] !== `"${state.version}"`) return json(409, { status: 409, code: 'VERSION_CONFLICT', title: 'Conflict' });
      next(); state.version += 1; return ok(model(state)); };
    if (req.method() === 'PUT' && path === '/api/v1/customer-promise/versions/p1/sections/INCLUSIONS') {
      const body = req.postDataJSON();
      state.puts.push(body);
      return write(() => { state.values = { ...state.values, INCLUSIONS: body.value }; });
    }
    if (req.method() === 'POST' && path === '/api/v1/customer-promise/versions/p1/submit') return write(() => { state.status = 'IN_REVIEW'; });
    if (req.method() === 'POST' && path === '/api/v1/customer-promise/versions/p1/sections/INCLUSIONS/review') return write(() => { state.reviewed = true; });
    if (req.method() === 'POST' && path === '/api/v1/customer-promise/versions/p1/approve') return write(() => { state.status = 'APPROVED'; });
    if (req.method() === 'POST' && path === '/api/v1/customer-promise/versions/p1/publish') return write(() => { state.status = 'PUBLISHED'; });
    if (path === '/api/v1/customer-promise/versions/p1') return ok(model(state));
    if (req.method() === 'GET') return ok([]);
    return json(404, { status: 404, code: 'NOT_FOUND', title: 'Not found' });
  });
}

const fresh = () => ({ status: 'DRAFT', version: 3, reviewed: false, values: JSON.parse(JSON.stringify(VALUES)) });

async function axe(p, name) {
  await p.addScriptTag({ content: AXE });
  const v = await p.evaluate(async () => (await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }))
    .violations.map((x) => `${x.id} (${x.nodes.length}): ${x.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')}`));
  check(`axe ${name}`, v.length === 0, v.join(', '));
}

function deepAll(selector) {
  const out = [];
  const walk = (root) => { root.querySelectorAll(selector).forEach((n) => out.push(n)); root.querySelectorAll('*').forEach((n) => n.shadowRoot && walk(n.shadowRoot)); };
  walk(document);
  return out;
}
const inPage = (fn) => `(() => { ${deepAll.toString()}; return (${fn.toString()})(); })()`;

/** No horizontal page scroll, and every visible control of the portal at least 44 x 44 px (a checkbox by its label). */
async function layout(p, name) {
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(`${name}: no horizontal overflow`, overflow <= 0, `${overflow}px`);
  const small = await p.evaluate(inPage(() => {
    const found = [];
    const walk = (root) => { root.querySelectorAll('button, select, textarea, input').forEach((n) => found.push(n)); root.querySelectorAll('*').forEach((n) => n.shadowRoot && walk(n.shadowRoot)); };
    walk(deepAll('vs-promise-page')[0].shadowRoot);
    return found.filter((n) => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden')
      .map((n) => { const t = n.type === 'checkbox' ? n.closest('label') ?? n : n; const r = t.getBoundingClientRect();
        return { what: `${n.tagName.toLowerCase()} ${(n.textContent || n.id || '').trim().slice(0, 30)}`, w: Math.round(r.width), h: Math.round(r.height) }; })
      .filter((x) => x.w < 44 || x.h < 44);
  }));
  check(`${name}: portal targets at least 44 px`, small.length === 0, JSON.stringify(small.slice(0, 5)));
}

const page = (p) => p.locator('vs-promise-page');
const button = (p, name) => page(p).getByRole('button', { name, exact: true });
async function confirmDialog(p) {
  await page(p).locator('vs-dialog button[type=submit]').click();
  await page(p).locator('vs-dialog[open]').waitFor({ state: 'detached' });
}

const browser = await chromium.launch();
try {
  // The whole journey at desktop width.
  {
    const state = fresh();
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    p.on('dialog', (d) => d.accept());
    await serve(p, state);
    await p.goto(`${BASE}/commercial/customer-promise`);
    await page(p).getByText('Completeness of the customer information').waitFor();
    check('landing: OI-MTQ-18 state is stated', await page(p).getByText('Owner decision OI-MTQ-18').isVisible());
    check('landing: fourteen areas', (await page(p).locator('section[aria-labelledby=completeness] tbody tr').count()) === 14);
    await button(p, 'Open version 1').click();
    await page(p).locator('#version-title').waitFor();
    await page(p).locator('nav.sections').getByRole('button', { name: /Project inclusions/ }).click();
    const text = page(p).locator('vs-promise-editor textarea').first();
    await text.fill('SYNTHETIC installation and fixing of the listed items.');
    await page(p).getByRole('button', { name: 'Save section' }).click();
    await page(p).getByText('Project inclusions saved.').waitFor({ state: 'attached' });
    check('edit: the section is saved as structured fields', JSON.stringify(state.puts[0]) === JSON.stringify({ value: { project_inclusions: [
      { code: 'SYN_INSTALL', text: 'SYNTHETIC installation and fixing of the listed items.' }] } }), JSON.stringify(state.puts[0]));
    await button(p, 'Submit for review').click();
    await confirmDialog(p);
    await page(p).getByRole('heading', { name: /Version 1 · In review/ }).waitFor();
    check('submit: the version is in review', state.status === 'IN_REVIEW');
    await page(p).locator('nav.sections').getByRole('button', { name: /Project inclusions/ }).click();
    await button(p, 'Approve section').click();
    await button(p, 'Approve version').waitFor();
    check('review: the section is approved', state.reviewed);
    await button(p, 'Approve version').click();
    await confirmDialog(p);
    await button(p, 'Publish').waitFor();
    await button(p, 'Publish').click();
    await confirmDialog(p);
    await page(p).getByRole('heading', { name: /Version 1 · Published/ }).waitFor();
    check('publish: the version is published', state.status === 'PUBLISHED');
    await button(p, 'What changed').click();
    await page(p).getByText('Project inclusion added: SYN_INSTALL').waitFor();
    check('changes: in words with before and after', (await page(p).locator('td.after').first().textContent()).includes('fixing of the listed items'));
    await button(p, 'Preview as customer').click();
    await page(p).locator('.preview-banner').waitFor();
    check('preview: labelled by the API', (await page(p).locator('.preview-banner').textContent()).trim() === 'PUBLISHED');
    check('preview: the customer proposal panels', (await page(p).locator('vs-promise-preview').textContent()) !== null
      && await page(p).locator('vs-promise-preview').getByText('Paying Veda Spaces safely').isVisible());
    check('journey: no page errors', errors.length === 0, errors.join(' | '));
    await ctx.close();
  }
  // Layout, targets and axe at every width, on the landing, a draft's editor and the preview.
  for (const [name, viewport] of [['360 px', { width: 360, height: 740 }], ['390 px', { width: 390, height: 844 }],
    ['768 px', { width: 768, height: 1024 }], ['1280 px', { width: 1280, height: 800 }]]) {
    const state = fresh();
    const ctx = await browser.newContext({ viewport });
    const p = await ctx.newPage();
    await serve(p, state);
    await p.goto(`${BASE}/commercial/customer-promise`);
    await page(p).getByText('Completeness of the customer information').waitFor();
    await layout(p, `${name} landing`);
    await axe(p, `${name} landing`);
    await button(p, 'Open version 1').click();
    await page(p).locator('#version-title').waitFor();
    for (const section of ['Contact and support', 'Site-dependent work', 'What happens next']) {
      await page(p).locator('nav.sections').getByRole('button', { name: new RegExp(section) }).click();
      await page(p).locator('#section-title').filter({ hasText: section }).waitFor();
      await layout(p, `${name} editor ${section}`);
    }
    await axe(p, `${name} editor`);
    await button(p, 'Preview as customer').click();
    await page(p).locator('vs-promise-preview').waitFor();
    for (const width of ['Mobile 360px', 'Tablet 768px', 'Desktop 1280px']) {
      await button(p, width).click();
      await layout(p, `${name} preview ${width}`);
    }
    check(`${name} preview: PREVIEW / NOT PUBLISHED`, (await page(p).locator('.preview-banner').textContent()).trim() === 'PREVIEW / NOT PUBLISHED');
    await axe(p, `${name} preview`);
    await p.screenshot({ path: `${OUT}/promise-preview-${viewport.width}.png`, fullPage: true });
    await ctx.close();
  }
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r).length;
console.log(`${results.length - failed}/${results.length} checks passed (SYNTHETIC_VALIDATED)`);
process.exit(failed ? 1 : 0);
