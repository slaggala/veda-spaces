// Project execution delivery (PEX): the staff work plan (add, start, complete), a customer report reviewed with a reply,
// the handover package, and the customer's portal view of their home's work, quality, snags and handover (a report sent
// once despite a failed first attempt, the handover summary acknowledged), in a real browser against the real app at
// 360, 390, 768 and 1280 px, with keyboard use, focus, accessible validation, no horizontal overflow, 44 px targets and
// axe (WCAG 2.2 AA). The API is answered by Playwright with a stateful SYNTHETIC model (nothing reaches a server): the
// API's rules (gates, segregation, isolation, idempotency) are proven by the API suites; this proves what the browser does.
//   APP_BASE=http://localhost:5173 node e2e/delivery.e2e.mjs
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
const OPS = { id: 'u-ops', display_name: 'SYNTHETIC Ops' };
const PERMS = ['project.view', 'project.manage_work', 'project.manage_qc', 'project.manage_snag', 'project.complete_handover', 'project.raise_blocker', 'profile.read'];
const ME = { id: 'u-ops', email: 'ops@synthetic.example', full_name: 'SYNTHETIC Ops', display_name: 'SYNTHETIC', phone: null, timezone: 'Asia/Kolkata', locale: 'en-IN',
  status: 'ACTIVE', roles: [], authz_version: 1, permissions: Object.fromEntries(PERMS.map((p) => [p, 'OWN'])), suspended_permissions: [],
  session: { type: 'FULL', auth_methods: ['pwd'], mfa_verified_on: null, cooling_off_until: null }, mfa: { required: false, required_by: [], enrolled: false },
  email_change: null, features: { project_lifecycle: true }, version: 1 };
const STAGES = ['BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION',
  'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER'];
const label = (c) => c.charAt(0) + c.slice(1).toLowerCase().replace(/_/g, ' ');
const LONG = 'Kitchen tall units, loft above the refrigerator and the SYNTHETIC very long corner carousel with soft-close hardware';
const VOCAB = { stages: STAGES.map((c) => ({ code: c, label: label(c) })), responsibilities: ['PROJECT', 'MEMBER'], responsible_parties: ['CUSTOMER', 'VEDA'],
  milestone_types: ['OTHER'], milestone_states: [], blocker_categories: ['OTHER'], blocker_impacts: ['GATING', 'INFORMATIONAL'], blocker_statuses: [],
  readiness_kinds: [], readiness_categories: [], readiness_statuses: [], qc_categories: ['FINISH_AND_SURFACES', 'OTHER'], qc_results: ['PASS', 'FAIL', 'NOT_APPLICABLE', 'TO_BE_CONFIRMED'],
  snag_categories: ['FINISH', 'OTHER'], snag_statuses: ['OPEN', 'IN_PROGRESS', 'READY_FOR_RECHECK', 'RESOLVED', 'CLOSED'], gates: [],
  snag_priorities: ['HIGH', 'NORMAL', 'LOW'], snag_closure_codes: ['DUPLICATE', 'NOT_A_DEFECT', 'RAISED_IN_ERROR'],
  work_package_states: ['NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'], report_decline_codes: ['DUPLICATE', 'NOT_A_DEFECT', 'NOT_IN_SCOPE'] };

function wp(n, title, status, over = {}) {
  const state = over.state ?? status;
  return { id: `w${n}`, version: over.version ?? 1, package_no: n, stage_code: 'INSTALLATION', space: 'Kitchen', space_id: 's1', title, description: null,
    customer_label: over.customer_label ?? 'Kitchen', customer_visible: over.customer_visible ?? true, owner: OPS, depends_on_id: null, status, state,
    scheduled: !!over.planned_finish, planned_start: null, planned_finish: over.planned_finish ?? null, plan_revision: 0, replan_reason: null,
    past_planned_finish: false, actual_start: status === 'NOT_STARTED' ? null : '2026-10-15', actual_finish: status === 'COMPLETED' ? '2026-10-16' : null,
    started_by: status === 'NOT_STARTED' ? null : OPS, completed_by: status === 'COMPLETED' ? OPS : null, completion_note: null, reopen_reason: null,
    cancel_reason: null, evidence: null };
}

function detail(state) {
  const idx = STAGES.indexOf(state.stage);
  return {
    id: 'p1', version: state.version, project_number: 'VS-P-2026-000001', status: 'ACTIVE', source: 'ACCEPTED_QUOTATION',
    property: { id: 'prop-1', property_number: 'VS-PR-2026-000001', configuration_label: '3 BHK', locality: 'Synthetic Nagar', city: 'Hyderabad' },
    quotation_number: 'VS-Q-2026-000001', source_quotation_id: 'q1', created_on: '2026-10-14T10:00:00Z', created_by: OPS, handed_over_on: null, handed_over_by: null,
    lifecycle: { version: 'PLB-2026.10.1', sha256: 'b'.repeat(64), status: 'PROPOSED' },
    stage: { code: state.stage, label: label(state.stage), description: '', sequence: idx + 1, of: 12, entered_on: '2026-10-14T10:00:00Z', owner_responsibility: 'PROJECT', customer_stage: 'INSTALLATION' },
    owner: OPS, next_milestone: null, readiness: null, awaiting_approval: null,
    handover_readiness: { ready: false, handed_over: false, stage_reached: state.stage === 'READY_FOR_HANDOVER', blockers: state.reports.some((r) => r.status === 'SUBMITTED')
      ? [{ gate: 'CUSTOMER_REPORTS_TRIAGED', code: 'CUSTOMER_REPORT_UNTRIAGED', message: 'Customer report 1 has not been reviewed.', responsible_party: 'VEDA' }] : [],
    commercial_position: null },
    site_readiness_state: 'READY', attention: [], next_actions: [], needs_reassignment: [],
    team: [{ id: 'mem1', version: 1, user: OPS, responsibility: 'PROJECT', active: true, eligible: true, assigned_on: '2026-10-14T10:00:00Z', assigned_by: OPS,
      removed_on: null, removed_by: null, removal_reason: null }],
    stages: STAGES.map((c, i) => ({ code: c, label: label(c), description: '', sequence: i + 1, customer_stage: 'INSTALLATION', owner_responsibility: 'PROJECT',
      terminal: c === 'HANDED_OVER', status: i < idx ? 'COMPLETED' : i === idx ? 'ACTIVE' : 'NOT_STARTED', entered_on: null, entered_by: null, completed_on: null, completed_by: null, exit: null })),
    checklist: [], blockers: [], milestones: [], site_readiness: [],
    qc: { required_categories: ['FINISH_AND_SURFACES'], categories: [{ category: 'FINISH_AND_SURFACES', required: true, latest: null }], points: [], chains: [], history: [] },
    snags: state.snags, work_packages: state.work, customer_reports: state.reports, handover_packages: state.packages,
    customer_documents: { documents: state.docs ?? [], can_publish: true,
      classes: [{ code: 'PROGRESS_PHOTO', label: 'Progress photograph' }, { code: 'HANDOVER_PHOTO', label: 'Handover photograph' }, { code: 'APPROVED_DRAWING', label: 'Approved drawing' }],
      options: (state.docs ?? []).some((d) => d.status === 'PUBLISHED') ? [] : [{ id: 'att1', category: 'SITE_PHOTO', attached_to: 'property', uploaded_on: '2026-10-15T10:00:00Z' }] },
    delivery_policy: { version: 'PEX-POLICY-0', status: 'UNDECIDED', decisions: { 'PEX-D01': { label: 'customer actions', decided: false }, 'PEX-D02': { label: 'commercial condition', decided: false } } },
    baseline: { full: false, verified: true, problems: [], current_seq: 1, open_variations: [], variations: [], lineage: [] },
    transitions: [], timeline: [], spaces: [{ id: 's1', label: 'Kitchen' }], evidence_options: [],
    actions: { request_transition: true, complete_handover: true, approve_transition: false, assign_team: false, complete_checklist: false, checklist_not_applicable: false,
      manage_milestone: false, raise_blocker: true, resolve_blocker: false, manage_site_readiness: false, manage_qc: true, manage_snag: true, view_commercial_baseline: false,
      view_audit: false, record_promised_date: false, reclassify_snag: false, qc_required_not_applicable: false, manage_work: true, verify_snag: false,
      prepare_handover_package: state.stage === 'READY_FOR_HANDOVER' },
    policy: { version: 'PLB-POLICY-0', status: 'UNDECIDED', sha256: 'a'.repeat(64), decisions: {} },
    classification: { classes: ['INTERNAL_ONLY'], default: 'INTERNAL_ONLY', fields: {}, published_through: 'VEDA_PROJECT_DELIVERY_PORTAL_ENABLED' },
    last_material_change: '2026-10-16T09:00:00Z',
  };
}

const PACKAGE = (n) => ({ id: `hp${n}`, version: 1, package_no: n, status: 'PREPARED', content_sha256: String(n).repeat(64), redacted: false,
  content: { work: { completed: [{ label: 'Kitchen', finished_on: '2026-10-16' }], completed_count: 2, cancelled_count: 0 },
    quality: { checks_passed: 3, checks_not_applicable: 0, corrected_after_failure: 1, failed: 0 },
    snags: { fixed_and_verified: 1, closed_without_fix: 0, open_non_blocking: [], open_non_blocking_count: 0 }, documents: [],
    warranty: { source: 'ACCEPTED_QUOTATION', quotation_id: 'q1', quotation_number: 'VS-Q-2026-000001' } },
  prepared_on: '2026-10-16T10:00:00Z', prepared_by: OPS, acknowledged_on: null, completed_on: null, superseded_on: null, superseded_by: null, stale: null });

async function serveStaff(p, state) {
  state.posts = [];
  await p.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const json = (status, body) => route.fulfill({ status, contentType: status < 400 ? 'application/json' : 'application/problem+json', body: JSON.stringify(body) });
    const ok = (data, status = 200) => json(status, { data });
    if (path === '/api/v1/auth/refresh') return ok({ access_token: 'synthetic-token' });
    if (path === '/api/v1/auth/me') return ok(ME);
    if (path === '/api/v1/projects/vocabulary') return ok(VOCAB);
    if (path === '/api/v1/projects/p1' && req.method() === 'GET') return ok(detail(state));
    if (req.method() === 'POST' || req.method() === 'PATCH') {
      const body = req.postDataJSON() ?? {};
      state.posts.push({ path, body, ifMatch: req.headers()['if-match'] ?? null, key: req.headers()['idempotency-key'] ?? null });
      state.version += 1;
      if (path === '/api/v1/projects/p1/work-packages') {
        state.work.push(wp(state.work.length + 1, body.title, 'NOT_STARTED', { customer_label: body.customer_label ?? null, customer_visible: !!body.customer_visible }));
        return ok(detail(state), 201);
      }
      const m = path.match(/work-packages\/(w\d+)\/(start|complete)$/);
      if (m) {
        const i = state.work.findIndex((w) => w.id === m[1]);
        state.work[i] = wp(i + 1, state.work[i].title, m[2] === 'start' ? 'IN_PROGRESS' : 'COMPLETED', { version: state.work[i].version + 1,
          customer_label: state.work[i].customer_label, customer_visible: state.work[i].customer_visible });
        return ok(detail(state));
      }
      if (path === '/api/v1/projects/p1/customer-reports/r1/triage') {
        state.reports[0] = { ...state.reports[0], status: 'DECLINED', decline_code: body.decline_code, response: body.response, triaged_by: OPS,
          triaged_on: '2026-10-16T11:00:00Z', version: 2 };
        return ok(detail(state));
      }
      if (path === '/api/v1/projects/p1/handover-package') { state.packages = [PACKAGE(1)]; return ok(detail(state), 201); }
      if (path === '/api/v1/projects/p1/customer-documents') {
        state.docs = [{ id: 'd1', version: 1, attachment_id: body.attachment_id, document_class: body.document_class, class_label: 'Handover photograph', title: body.title,
          status: 'PUBLISHED', published_on: '2026-10-16T12:00:00Z', published_by: OPS, withdrawn_on: null, withdrawn_by: null, withdrawn_reason: null, available: true }];
        return ok(detail(state), 201);
      }
      if (path === '/api/v1/projects/p1/customer-documents/d1/withdraw') {
        state.docs = [{ ...state.docs[0], version: 2, status: 'WITHDRAWN', withdrawn_on: '2026-10-16T12:30:00Z', withdrawn_by: OPS, withdrawn_reason: body.reason }];
        return ok(detail(state));
      }
    }
    if (req.method() === 'GET') return ok([]);
    return json(404, { status: 404, code: 'NOT_FOUND', title: 'Not found' });
  });
}

const freshStaff = () => ({ stage: 'INSTALLATION', version: 5, packages: [], snags: [],
  work: [wp(1, LONG, 'COMPLETED'), wp(2, 'Wardrobe shutters in the master bedroom', 'IN_PROGRESS', { customer_label: 'Wardrobes' }),
    wp(3, 'Internal: electrical rework behind the TV unit', 'NOT_STARTED', { state: 'BLOCKED', customer_visible: false, customer_label: null })],
  reports: [{ id: 'r1', version: 1, report_no: 1, channel: 'PORTAL', description: 'The study table wobbles a little when the drawer is opened',
    area: 'Study', status: 'SUBMITTED', snag_id: null, decline_code: null, response: null, reported_on: '2026-10-16T09:00:00Z', recorded_by: null,
    triaged_by: null, triaged_on: null }] });

// --- portal model ----------------------------------------------------------------------------------------------------------
const delivery = (state) => ({
  id: 'pj1', status: 'ACTIVE', phase: { code: 'INSTALLATION', label: 'Installing your interiors' },
  work: { items: [{ label: LONG, state: 'COMPLETED', detail: 'Completed', completed_on: '2026-10-16' },
    { label: 'Wardrobes', state: 'BLOCKED', detail: 'On hold', completed_on: null }, { label: 'Lofts', state: 'ACTION_REQUIRED', detail: 'Waiting for something from you', completed_on: null },
    { label: 'TV unit', state: 'UPCOMING', detail: 'Not started yet', completed_on: null }], counts: { COMPLETED: 1, IN_PROGRESS: 0, ACTION_REQUIRED: 1, BLOCKED: 1, UPCOMING: 1 } },
  paused: [{ text: 'We are waiting for a material delivery for your wardrobes', state: 'BLOCKED', who: 'VEDA_SPACES' }],
  next_date: { label: 'Installation complete', date: '2026-11-02' }, quality: { checks_passed: 3, being_corrected: 1 },
  snags: [{ number: 1, title: 'Touch-up on the skirting near the balcony door', status: 'Being fixed', state: 'IN_PROGRESS' }],
  reports: state.reports, can_report: true,
  handover: { state: 'IN_PROGRESS', label: 'Ready for handover', date: null, remaining: [] },
  package: { id: 'hp1', number: 1, content_sha256: '1'.repeat(64), status: 'READY_TO_REVIEW', work_completed: [{ label: LONG, finished_on: '2026-10-16' }],
    quality: { checks_passed: 3, corrected_after_failure: 1 }, snags: { fixed_and_verified: 1, open_minor: [] }, documents: [],
    documents_note: 'Handover documents are not shown in your portal yet. Your Veda Spaces contact will give them to you.',
    warranty_note: 'Warranty is as set out in your accepted quotation.', acknowledged_on: state.ack, can_acknowledge: !state.ack },
});
const view = (state) => ({ id: 'p1', property: { reference: 'VS-P-2026-000001', configuration: '3 BHK apartment', locality: 'Synthetic Nagar', city: 'Hyderabad' },
  enquiry: { reference: '81DG-6BJR' }, headline: 'Your project is under way.', next_step: null, attention_count: state.ack ? 0 : 1, quotation: null, contact: null,
  project_tracking: true, payments: null, journey: [], quotations: [], included: null,
  documents: [{ kind: 'PROJECT_DOCUMENT', id: 'd1', document_class: 'HANDOVER_PHOTO', label: 'Handover photograph', title: 'Finished kitchen with the SYNTHETIC tall units and loft',
    published_on: '2026-10-16T12:00:00Z', width: 1600, height: 1200, project_id: 'pj1' }], commitments: null, responsibilities: null, support: null,
  commercials: null, attention: state.ack ? [] : [{ kind: 'HANDOVER_ACKNOWLEDGEMENT', status: 'ACTION_REQUIRED', title: 'Review your handover summary',
    text: 'Veda Spaces has prepared the summary of what is being handed over. Please review it and confirm you have received it.', due: null }],
  delivery: { available: true, projects: [delivery(state)] } });

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
    if (path === '/api/v1/public/portal/properties/p1') return ok(view(state));
    if (path === '/api/v1/public/portal/properties/p1/documents/d1/content') {
      state.images = (state.images ?? 0) + 1;
      return route.fulfill({ status: 200, contentType: 'image/png', headers: { 'cache-control': 'no-store' }, body: PNG });
    }
    if (path === '/api/v1/public/portal/properties/p1/projects/pj1/reports') {
      state.reportKeys.push(headers['idempotency-key']);
      if (state.failNext) { state.failNext = false; return route.fulfill({ status: 503, body: '' }); }
      if (!state.reports.length) state.reports.push({ number: 1, description: req.postDataJSON().description, area: req.postDataJSON().area ?? null,
        status: 'Received, being reviewed', outcome: null, response: null, snag_number: null });
      return ok({ reference: 'Report 1', received: true, delivery: delivery(state) }, 201);
    }
    if (path === '/api/v1/public/portal/properties/p1/projects/pj1/handover/acknowledge') {
      state.acks.push(req.postDataJSON());
      state.ack = state.ack ?? '2026-10-16T12:00:00Z';
      return ok({ acknowledged_on: state.ack, delivery: delivery(state) });
    }
    return json(404, { status: 404, code: 'NOT_FOUND', title: 'Not found' });
  });
}
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');
const freshPortal = () => ({ reports: [], reportKeys: [], acks: [], ack: null, failNext: true });

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

const staff = (p) => p.locator('vs-project-page');
const tab = (p, name) => staff(p).locator('vs-tabs').getByRole('tab', { name, exact: true });
const dialogDone = (p) => p.waitForFunction(() => {
  const find = (root) => { const el = root.querySelector('vs-project-page'); if (el) return el; for (const n of root.querySelectorAll('*')) { if (n.shadowRoot) { const f = find(n.shadowRoot); if (f) return f; } } return null; };
  const el = find(document);
  return el && !el.shadowRoot.querySelector('vs-dialog[open]');
});
const activeId = (p) => p.evaluate(() => { let a = document.activeElement; while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement; return a?.id || a?.tagName; });

const browser = await chromium.launch();
try {
  // --- staff journey at desktop width ---------------------------------------------------------------------------------
  {
    const state = freshStaff();
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    await serveStaff(p, state);
    await p.goto(`${BASE}/projects/p1`);
    await staff(p).locator('dl.hero').waitFor();
    await tab(p, 'Work plan').click();
    const plan = staff(p).locator('#work-h');
    await plan.waitFor();
    check('work plan: derived states, the internal work marked, no status picker',
      await staff(p).getByText('Correction required').count() === 0 && await staff(p).getByText('Blocked', { exact: true }).isVisible()
      && await staff(p).getByText('Unscheduled').first().isVisible() && (await staff(p).locator('select[name=status]').count()) === 0);
    await staff(p).getByRole('button', { name: 'Add work', exact: true }).click();
    await staff(p).locator('vs-dialog #project-form').waitFor();
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await staff(p).locator('vs-dialog input[aria-invalid=true]').first().waitFor();
    check('add work: the empty title is marked invalid, nothing sent', !state.posts.length);
    await staff(p).locator('vs-dialog input[name=title]').fill('TV unit with back panel');
    await staff(p).locator('vs-dialog input[name=customer_label]').fill('TV unit');
    await staff(p).locator('vs-dialog input[name=customer_visible]').check();
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await dialogDone(p);
    const add = state.posts.find((x) => x.path.endsWith('/work-packages'));
    check('add work: sent once with an idempotency key, no invented dates', !!add?.key && add.body.customer_visible === true && !('planned_start' in add.body));
    await staff(p).getByRole('button', { name: 'Start WP-4' }).click();
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await dialogDone(p);
    await staff(p).getByRole('button', { name: 'Complete WP-4' }).click();
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await dialogDone(p);
    const cmds = state.posts.filter((x) => /w4\/(start|complete)$/.test(x.path));
    check('work: started then completed by command, with the row version', cmds.length === 2 && cmds.every((c) => c.ifMatch !== null) && state.work[3].status === 'COMPLETED');
    // Customer reports: decline needs a customer-safe reply.
    await tab(p, 'Customer reports').click();
    await staff(p).getByText('The study table wobbles a little when the drawer is opened').waitFor();
    await staff(p).getByRole('button', { name: 'Report 1: decline with a reply' }).click();
    await staff(p).locator('vs-dialog select[name=decline_code]').selectOption('NOT_IN_SCOPE');
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await staff(p).locator('vs-dialog textarea[aria-invalid=true]').waitFor();
    check('decline: the reply to the customer is required', !state.posts.some((x) => x.path.endsWith('/triage')));
    await staff(p).locator('vs-dialog textarea[name=response]').fill('A study-table drawer runner is not part of the agreed work.');
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await dialogDone(p);
    check('decline: recorded with its reason and reply', state.reports[0].status === 'DECLINED' && state.reports[0].decline_code === 'NOT_IN_SCOPE');
    // The handover package, prepared in Ready for handover.
    state.stage = 'READY_FOR_HANDOVER';
    await p.reload();
    await staff(p).locator('dl.hero').waitFor();
    await tab(p, 'Handover').click();
    await staff(p).getByRole('button', { name: 'Prepare the package' }).click();
    await staff(p).getByText('Not acknowledged in the portal').waitFor();
    check('package: prepared, with no documents and the warranty as the accepted quotation states',
      await staff(p).getByText(/Shared separately, in Customer documents/).isVisible() && await staff(p).getByText('As stated in accepted quotation VS-Q-2026-000001').isVisible());
    // Customer documents (CPP-D04): sharing is explicit, titled in customer words, and withdrawing keeps the record.
    await tab(p, 'Customer documents').click();
    await staff(p).locator('#documents-h').waitFor();
    check('documents: nothing shared until staff share it', await staff(p).getByText('Nothing is shared with the customer yet.').isVisible());
    await staff(p).getByRole('button', { name: 'Share a document' }).click();
    await staff(p).locator('vs-dialog select[name=document_class]').selectOption('HANDOVER_PHOTO');
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await staff(p).locator('vs-dialog input[aria-invalid=true]').first().waitFor();
    check('share: the customer title is required, nothing sent', !state.posts.some((x) => x.path.endsWith('/customer-documents')));
    await staff(p).locator('vs-dialog input[name=title]').fill('Finished kitchen');
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await dialogDone(p);
    const share = state.posts.find((x) => x.path.endsWith('/customer-documents'));
    check('share: sent once with an idempotency key, the chosen file, class and title',
      !!share?.key && share.body.attachment_id === 'att1' && share.body.document_class === 'HANDOVER_PHOTO' && share.body.title === 'Finished kitchen');
    await staff(p).getByRole('button', { name: 'Stop sharing: Finished kitchen' }).click();
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await staff(p).locator('vs-dialog textarea[aria-invalid=true]').waitFor();
    await staff(p).locator('vs-dialog textarea[name=reason]').fill('Wrong photograph');
    await staff(p).locator('vs-dialog button[type=submit]').click();
    await dialogDone(p);
    const wd = state.posts.find((x) => x.path.endsWith('/withdraw'));
    check('stop sharing: needs a reason, sent with the row version, the record kept',
      wd?.ifMatch !== null && wd?.body.reason === 'Wrong photograph' && await staff(p).locator('span.badge', { hasText: 'Withdrawn' }).isVisible() && await staff(p).getByText('Wrong photograph').isVisible());
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
    await proj.locator('#h-delivery').waitFor();
    check('portal: phase, agreed date, work by state, paused in Veda\'s words, no percentage',
      await proj.getByText('Now: Installing your interiors').isVisible() && await proj.getByText(/Installation complete, /).isVisible()
      && await proj.getByText('We are waiting for a material delivery for your wardrobes').isVisible()
      && !/\d+ ?%/.test(await proj.locator('#delivery').textContent()));
    check('portal: the handover summary is in Action Required', await proj.getByText('Review your handover summary').isVisible());
    await proj.locator('nav.jump').getByRole('link', { name: 'Work on your home' }).click();
    check('section link moves focus to the delivery heading', (await activeId(p)) === 'h-delivery');
    await proj.getByRole('button', { name: 'Report something' }).click();
    check('report: the form opens with focus on the description', (await activeId(p)) === 'TEXTAREA');
    await proj.getByRole('button', { name: 'Send report' }).click();
    await proj.getByRole('alert').waitFor();
    check('report: too short is explained, nothing sent', state.reportKeys.length === 0);
    await proj.locator('textarea[name=description]').fill('The kitchen drawer next to the hob does not close fully');
    await proj.locator('input[name=area]').fill('Kitchen');
    await proj.getByRole('button', { name: 'Send report' }).click();
    await proj.getByText(/it will not be sent twice/).waitFor();
    await proj.getByRole('button', { name: 'Send report' }).click();
    await proj.getByText('Received, being reviewed').waitFor();
    check('report: one key for the retry, the report listed back in the customer\'s words',
      state.reportKeys.length === 2 && state.reportKeys[0] === state.reportKeys[1] && await proj.getByText('The kitchen drawer next to the hob does not close fully').isVisible());
    await proj.getByRole('button', { name: 'I have received this summary' }).click();
    await proj.getByText(/You confirmed receiving this summary/).waitFor();
    check('handover: acknowledged by its digest, once', state.acks.length === 1 && state.acks[0].content_sha256 === '1'.repeat(64)
      && (await proj.getByRole('button', { name: 'I have received this summary' }).count()) === 0);
    await proj.locator('nav.jump').getByRole('link', { name: 'Documents' }).click();
    await proj.locator('#documents vs-portal-image img').first().waitFor();
    check('documents: the shared photo loads through the portal session, titled in customer words',
      state.images >= 1 && await proj.locator('#documents span.strong', { hasText: 'Finished kitchen with the SYNTHETIC tall units and loft' }).isVisible());
    await proj.getByRole('button', { name: 'View Finished kitchen with the SYNTHETIC tall units and loft' }).click();
    await proj.locator('#documents vs-portal-image.large img').waitFor();
    check('documents: View shows it larger and says so to assistive technology',
      (await proj.getByRole('button', { name: 'Hide Finished kitchen with the SYNTHETIC tall units and loft' }).getAttribute('aria-expanded')) === 'true');
    check('portal journey: no page errors', errors.length === 0, errors.join(' | '));
    await ctx.close();
  }
  // --- layout, targets and axe at every width ----------------------------------------------------------------------------
  for (const [name, viewport] of [['360 px', { width: 360, height: 740 }], ['390 px', { width: 390, height: 844 }],
    ['768 px', { width: 768, height: 1024 }], ['1280 px', { width: 1280, height: 800 }]]) {
    const ctx = await browser.newContext({ viewport });
    const s = await ctx.newPage();
    const st = freshStaff();
    st.stage = 'READY_FOR_HANDOVER';
    st.packages = [PACKAGE(1)];
    await serveStaff(s, st);
    await s.goto(`${BASE}/projects/p1`);
    await staff(s).locator('dl.hero').waitFor();
    st.docs = [{ id: 'd1', version: 1, attachment_id: 'att1', document_class: 'HANDOVER_PHOTO', class_label: 'Handover photograph', title: 'Finished kitchen',
      status: 'PUBLISHED', published_on: '2026-10-16T12:00:00Z', published_by: OPS, withdrawn_on: null, withdrawn_by: null, withdrawn_reason: null, available: true }];
    for (const t of ['Work plan', 'Quality and snags', 'Customer reports', 'Customer documents', 'Handover']) {
      await tab(s, t).click();
      await staff(s).locator('vs-tabs h2').first().waitFor();
      await layout(s, 'vs-project-page', `${name} staff ${t}`);
      await axe(s, `${name} staff ${t}`);
    }
    await s.screenshot({ path: `${OUT}/delivery-staff-${viewport.width}.png`, fullPage: true });
    const c = await ctx.newPage();
    await servePortal(c, freshPortal());
    await c.goto(`${BASE}/portal/properties/p1`);
    await c.locator('vs-portal-project-page #h-delivery').waitFor();
    await c.locator('vs-portal-project-page').getByRole('button', { name: 'Report something' }).click();
    await c.locator('vs-portal-project-page #documents vs-portal-image img').first().waitFor();
    await layout(c, 'vs-portal-project-page', `${name} portal delivery`);
    await axe(c, `${name} portal delivery`);
    await c.screenshot({ path: `${OUT}/delivery-portal-${viewport.width}.png`, fullPage: true });
    await ctx.close();
  }
} finally {
  await browser.close();
}
const failed = results.filter((x) => !x).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
