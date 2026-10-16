// Project Lifecycle (PLB-49): the staff journey dashboard → project → a refused move with its exact blockers → resolve the
// blocker → the move → site readiness → quality check and a snag → handover readiness, in a real browser against the real
// app, at 360, 390, 768 and 1280 px, with keyboard navigation, focus management, accessible validation, no horizontal
// overflow, 44 px targets and axe. The API is answered by Playwright with a stateful SYNTHETIC model (every /api request
// is intercepted; nothing reaches a server): the API's own rules (gates, scope, four-eyes, concurrency) are proven by
// the API suites; this proves what the staff browser does with them.
//   APP_BASE=http://localhost:5173 node e2e/project.e2e.mjs
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

const PERMS = ['project.view', 'project.manage_stage', 'project.complete_checklist', 'project.manage_milestone', 'project.raise_blocker',
  'project.resolve_blocker', 'project.manage_site_readiness', 'project.manage_qc', 'project.manage_snag', 'project.complete_handover',
  'project.view_commercial_baseline', 'project.view_audit', 'project.assign_team', 'project.manage_work', 'profile.read'];
const ME = { id: 'u-ops', email: 'ops@synthetic.example', full_name: 'SYNTHETIC Ops', display_name: 'SYNTHETIC', phone: null,
  timezone: 'Asia/Kolkata', locale: 'en-IN', status: 'ACTIVE', roles: [], authz_version: 1,
  permissions: Object.fromEntries(PERMS.map((p) => [p, 'OWN'])), suspended_permissions: [],
  session: { type: 'FULL', auth_methods: ['pwd'], mfa_verified_on: null, cooling_off_until: null },
  mfa: { required: false, required_by: [], enrolled: false }, email_change: null, features: { project_lifecycle: true }, version: 1 };

// SYNTHETIC content: invented for the browser journey, not Veda Spaces content.
const OPS = { id: 'u-ops', display_name: 'SYNTHETIC Ops' };
// The independent quality persona (PEX): verifies what ops fixed, never their own fix.
const QA_ME = { ...ME, id: 'u-qa', email: 'qa@synthetic.example', full_name: 'SYNTHETIC Quality',
  permissions: Object.fromEntries(['project.view', 'project.manage_qc', 'project.verify_snag', 'profile.read'].map((p) => [p, 'OWN'])) };
const STAGES = ['BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION',
  'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER'];
const label = (c) => c.charAt(0) + c.slice(1).toLowerCase().replace(/_/g, ' ');
const PROPERTY = { id: 'prop-1', property_number: 'VS-PR-2026-000001', configuration_label: '2 BHK', locality: 'Synthetic Nagar with a long locality name', city: 'Hyderabad' };
const POLICY = { version: 'PLB-POLICY-0', status: 'UNDECIDED', sha256: 'a'.repeat(64),
  decisions: Object.fromEntries(Array.from({ length: 13 }, (_, i) => [`PLB-OD-${String(i + 1).padStart(2, '0')}`, { label: `synthetic decision ${i + 1}`, decided: false, read_by_engine: i < 4 }])) };
const VOCAB = { stages: STAGES.map((c) => ({ code: c, label: label(c) })), responsibilities: ['COMMERCIAL', 'DESIGN', 'PROJECT', 'SITE', 'QUALITY', 'HANDOVER', 'MEMBER'],
  responsible_parties: ['CUSTOMER', 'VEDA', 'THIRD_PARTY', 'TO_BE_CONFIRMED'], milestone_types: ['SITE_READY', 'HANDOVER', 'OTHER'], milestone_states: ['PLANNED'],
  blocker_categories: ['CUSTOMER_DECISION', 'SITE', 'OTHER'], blocker_impacts: ['GATING', 'INFORMATIONAL'], blocker_statuses: ['OPEN', 'RESOLVED'],
  readiness_kinds: ['READINESS', 'RESPONSIBILITY'], readiness_categories: ['FLOORING', 'ACCESS'],
  readiness_statuses: ['READY', 'NOT_READY', 'CUSTOMER_ACTION_REQUIRED', 'VEDA_ACTION_REQUIRED', 'NOT_APPLICABLE', 'TO_BE_CONFIRMED'],
  qc_categories: ['DIMENSIONS_AND_ALIGNMENT', 'FINISH_AND_SURFACES', 'OTHER'], qc_results: ['PASS', 'FAIL', 'NOT_APPLICABLE', 'TO_BE_CONFIRMED'],
  snag_categories: ['FINISH', 'OTHER'], snag_statuses: ['OPEN', 'IN_PROGRESS', 'READY_FOR_RECHECK', 'RESOLVED', 'CLOSED'], gates: [] };

function blockersOf(state) {
  const out = [];
  if (state.blockerOpen) out.push({ gate: 'NO_GATING_BLOCKERS', code: 'GATING_BLOCKER_OPEN', message: 'An open gating blocker (customer decision) stops production readiness.',
    responsible_party: 'CUSTOMER', entity: { type: 'blocker', id: 'b1' }, blocks: 'PRODUCTION_READINESS' });
  if (state.itemOpen) out.push({ gate: 'CHECKLIST_COMPLETE', code: 'CHECKLIST_ITEM_OPEN', message: 'Checklist item not complete: Site readiness items reviewed with the customer.',
    responsible_party: 'VEDA', entity: { type: 'checklist_item', id: 'i1' } });
  if (state.site !== 'READY') out.push({ gate: 'SITE_READY', code: `SITE_${state.site}`, message: `Site readiness flooring is ${label(state.site).toLowerCase()}.`,
    responsible_party: 'CUSTOMER', entity: { type: 'site_readiness', id: 'r1' } });
  return out;
}

function detail(state) {
  const idx = STAGES.indexOf(state.stage);
  const next = STAGES[idx + 1];
  const blockers = state.stage === 'SITE_READINESS' ? blockersOf(state) : [];
  const evaluation = { from: state.stage, to: next, transition: `${state.stage}>${next}`, risk: 'STANDARD', command: 'STAGE',
    lifecycle: { version: 'PLB-2026.10.1', sha256: 'b'.repeat(64), status: 'PROPOSED' }, policy: { version: 'PLB-POLICY-0', sha256: 'c'.repeat(64) },
    independent_approval: false, allowed: blockers.length === 0, blockers,
    gates: [{ code: 'TRANSITION_ALLOWED', label: 'The target is the next stage of this project\'s lifecycle definition', source: 'STRUCTURAL', passed: true, blockers: [] },
      { code: 'NO_GATING_BLOCKERS', label: 'No open gating blocker stops this stage or an earlier one', source: 'STRUCTURAL', passed: !state.blockerOpen,
        blockers: blockers.filter((b) => b.gate === 'NO_GATING_BLOCKERS') },
      { code: 'CHECKLIST_COMPLETE', label: 'Every required checklist item of the current stage is done or marked not applicable', source: 'DEFAULT',
        passed: !state.itemOpen, blockers: blockers.filter((b) => b.gate === 'CHECKLIST_COMPLETE') },
      { code: 'SITE_READY', label: 'Every site-readiness item is ready or not applicable', source: 'DEFAULT', passed: state.site === 'READY',
        blockers: blockers.filter((b) => b.gate === 'SITE_READY') }] };
  const attention = [];
  if (state.blockerOpen) attention.push({ severity: 'GATING', kind: 'BLOCKER', title: 'Appliance specifications required', who: 'CUSTOMER',
    action: 'Please share the hob and chimney models', blocks: 'PRODUCTION_READINESS', entity: { type: 'blocker', id: 'b1' } });
  if (state.site !== 'READY' && state.site !== 'TO_BE_CONFIRMED') attention.push({ severity: 'SITE', kind: 'SITE_READINESS', title: 'SYNTHETIC: flooring complete.',
    who: 'CUSTOMER', action: 'Please complete the flooring in Bedroom 2', blocks: null, entity: { type: 'site_readiness', id: 'r1' } });
  if (state.snag && ['OPEN', 'IN_PROGRESS', 'READY_FOR_RECHECK'].includes(state.snag)) attention.push({ severity: 'GATING', kind: 'SNAG',
    title: 'Snag 1: Shutter edge to be refinished', who: 'VEDA', action: 'Fix and recheck', blocks: 'READY_FOR_HANDOVER', entity: { type: 'snag', id: 'n1' } });
  return {
    id: 'p1', version: state.version, project_number: 'VS-P-2026-000001', status: 'ACTIVE', source: 'ACCEPTED_QUOTATION', property: PROPERTY,
    quotation_number: 'VS-Q-2026-000001', source_quotation_id: 'q1', created_on: '2026-10-14T10:00:00Z', created_by: OPS, handed_over_on: null, handed_over_by: null,
    lifecycle: { version: 'PLB-2026.10.1', sha256: 'b'.repeat(64), status: 'PROPOSED' },
    stage: { code: state.stage, label: label(state.stage), description: 'SYNTHETIC stage.', sequence: idx + 1, of: 12, entered_on: '2026-10-14T10:00:00Z',
      owner_responsibility: 'SITE', customer_stage: 'SITE_READINESS' },
    owner: OPS, next_milestone: { id: 'm1', label: 'Site ready', code: 'SITE_READY', stage_code: 'SITE_READINESS', status: 'PLANNED', planned_date: '2026-10-01', overdue: true },
    readiness: evaluation, awaiting_approval: null,
    handover_readiness: { ready: false, handed_over: false, stage_reached: false, blockers: state.qc === 'FAIL'
      ? [{ gate: 'QC_PASSED', code: 'QC_FAILED', message: 'Quality check finish and surfaces failed; fix and recheck it.', responsible_party: 'VEDA' }] : [] },
    site_readiness_state: state.site === 'READY' ? 'READY' : 'BLOCKED', attention,
    next_actions: blockers.map((b) => ({ gate: b.gate, code: b.code, who: b.responsible_party, message: b.message, entity: b.entity })),
    needs_reassignment: [],
    team: [{ id: 'mem1', version: 1, user: OPS, responsibility: 'PROJECT', active: true, eligible: true, assigned_on: '2026-10-14T10:00:00Z', assigned_by: OPS, removed_on: null, removed_by: null, removal_reason: null }],
    stages: STAGES.map((c, i) => ({ code: c, label: label(c), description: '', sequence: i + 1, customer_stage: 'SITE_READINESS', owner_responsibility: 'PROJECT',
      terminal: c === 'HANDED_OVER', status: i < idx ? 'COMPLETED' : i === idx ? 'ACTIVE' : 'NOT_STARTED', entered_on: null, entered_by: null, completed_on: null,
      completed_by: null, exit: null })),
    checklist: [{ stage_code: 'SITE_READINESS', stage_label: 'Site readiness', current: state.stage === 'SITE_READINESS', closed: idx > 3, done: state.itemOpen ? 0 : 1, total: 1,
      items: [{ id: 'i1', version: state.itemVersion, code: 'SITE_READINESS_REVIEWED', label: 'Site readiness items reviewed with the customer', ref: 'PLB-17',
        required: true, state: state.itemOpen ? 'OPEN' : 'DONE', completed_by: state.itemOpen ? null : OPS, completed_on: state.itemOpen ? null : '2026-10-15T10:00:00Z',
        note: null, not_applicable_reason: null, reopen_reason: null, evidence: null }] }],
    blockers: [{ id: 'b1', version: state.blockerVersion, category: 'CUSTOMER_DECISION', source: 'STAFF', impact: 'GATING', title: 'Appliance specifications required',
      description: 'Internal: the hob model decides the cut-out.', customer_action: 'Please share the hob and chimney models', responsible_party: 'CUSTOMER', assigned_to: OPS,
      target_date: '2026-10-20', status: state.blockerOpen ? 'OPEN' : 'RESOLVED', blocks: { code: 'PRODUCTION_READINESS', label: 'Production readiness' },
      resolution: state.blockerOpen ? null : state.resolution, resolved_on: state.blockerOpen ? null : '2026-10-15T11:00:00Z', resolved_by: state.blockerOpen ? null : OPS,
      raised_on: '2026-10-14T11:00:00Z', raised_by: OPS, related: { milestone_id: null, checklist_item_id: null, site_readiness_id: null, quotation_id: null,
        work_package_id: null }, customer_summary: null }],
    milestones: [{ id: 'm1', version: 1, code: 'SITE_READY', label: 'Site ready', customer_label: null, description: null, stage_code: 'SITE_READINESS', status: 'PLANNED',
      status_reason: null, planned_date: '2026-10-01', actual_date: null, customer_promised_date: null, overdue: true, depends_on_milestone_id: null,
      owner_responsibility: 'SITE', evidence: null }],
    site_readiness: [{ id: 'r1', version: state.siteVersion, kind: 'READINESS', source: 'CUSTOMER_PROMISE', item_code: 'SYN_FLOOR', category: 'FLOORING',
      label: 'SYNTHETIC: flooring complete.', promise: { content_version: 'CPP-1', text: 'SYNTHETIC: flooring complete.', quoted_status: 'TO_BE_CONFIRMED' },
      status: state.site, satisfied: state.site === 'READY', responsible_party: 'CUSTOMER', action: 'Flooring not laid in Bedroom 2',
      customer_action: 'Please complete the flooring in Bedroom 2', due_date: '2026-10-25', note: null, evidence: null, resolved_on: null, resolved_by: null, updated_on: null }],
    qc: { required_categories: ['DIMENSIONS_AND_ALIGNMENT', 'FINISH_AND_SURFACES'], history: [],
      categories: [{ category: 'DIMENSIONS_AND_ALIGNMENT', required: true, latest: null },
        { category: 'FINISH_AND_SURFACES', required: true, latest: state.qc ? { id: 'qc1', category: 'FINISH_AND_SURFACES', result: state.qc, space: 'Kitchen', space_id: 's1',
          observation: state.qc === 'FAIL' ? 'Edge banding lifting on the tall unit' : null, evidence: null, recheck_of_id: null, checked_by: OPS, checked_on: '2026-10-15T12:00:00Z' } : null },
        { category: 'OTHER', required: false, latest: null }],
      points: [], chains: state.qc ? [{ root_id: 'qc1', length: 1, ever_failed: state.qc === 'FAIL', head: { id: 'qc1', category: 'FINISH_AND_SURFACES',
        result: state.qc, space: 'Kitchen', space_id: 's1', observation: state.qc === 'FAIL' ? 'Edge banding lifting on the tall unit' : null, evidence: null,
        recheck_of_id: null, qc_point_id: null, work_package_id: null, checked_by: OPS, checked_on: '2026-10-15T12:00:00Z' } }] : [] },
    snags: state.snag ? [{ id: 'n1', version: state.snagVersion, snag_no: 1, category: 'FINISH', customer_title: 'Shutter edge to be refinished',
      description: 'Edge banding lifting', space: 'Kitchen', space_id: 's1', item_reference: null, is_blocking: true, owner: OPS, responsible_party: 'VEDA',
      status: state.snag, allowed_next: { OPEN: ['IN_PROGRESS', 'CLOSED'], IN_PROGRESS: ['READY_FOR_RECHECK', 'CLOSED'], READY_FOR_RECHECK: ['IN_PROGRESS', 'RESOLVED', 'CLOSED'],
        RESOLVED: ['CLOSED'], CLOSED: [] }[state.snag], target_date: null, evidence: null, resolution_note: state.snag === 'RESOLVED' ? 'Rechecked' : null,
      resolved_on: null, resolved_by: state.snag === 'RESOLVED' ? QA : null, closed_on: null, closed_by: null, qc_check_id: 'qc1', raised_on: '2026-10-15T12:10:00Z',
      raised_by: OPS, work_package_id: null, source: 'QUALITY_CHECK', priority: 'NORMAL', customer_visible: false,
      fixed_by: ['READY_FOR_RECHECK', 'RESOLVED'].includes(state.snag) ? OPS : null, fixed_on: null, fix_note: state.fixNote ?? null, closure_code: null }] : [],
    work_packages: [], customer_reports: [], handover_packages: [],
    delivery_policy: { version: 'PEX-POLICY-0', status: 'UNDECIDED', decisions: { 'PEX-D01': { label: 'customer actions in the portal', decided: false },
      'PEX-D02': { label: 'the commercial condition for handover', decided: false } } },
    baseline: { full: true, verified: true, problems: [], current_seq: 1, open_variations: [], variations: [],
      lineage: [{ id: 'bl1', sequence_no: 1, kind: 'ORIGINAL', current: true, quotation_id: 'q1', label: 'VS-Q-2026-000001 v1', variation_no: 0, decided_on: '2026-10-13T10:00:00Z',
        decision_method: 'SIGNED_COPY', recorded_on: '2026-10-14T10:00:00Z', accepted_total_minor: 123456700, cumulative_value_minor: 123456700, baseline_sha256: 'd'.repeat(64) }] },
    transitions: state.transitions, timeline: state.timeline, spaces: [{ id: 's1', label: 'Kitchen' }], evidence_options: [],
    actions: { request_transition: true, complete_handover: true, approve_transition: false, assign_team: true, complete_checklist: true, checklist_not_applicable: false,
      manage_milestone: true, raise_blocker: true, resolve_blocker: true, manage_site_readiness: true, manage_qc: true, manage_snag: true,
      view_commercial_baseline: true, view_audit: true, record_promised_date: false, reclassify_snag: false, qc_required_not_applicable: false,
      manage_work: true, verify_snag: true, prepare_handover_package: false },
    policy: POLICY, classification: { classes: ['INTERNAL_ONLY', 'POTENTIALLY_CUSTOMER_SAFE', 'CUSTOMER_ACTION'], default: 'INTERNAL_ONLY', fields: {},
      published_through: 'VEDA_PROJECT_DELIVERY_PORTAL_ENABLED' },
    last_material_change: '2026-10-15T09:00:00Z',
  };
}

function row(state) {
  const d = detail(state);
  return { id: 'p1', version: d.version, project_number: d.project_number, status: 'ACTIVE', property: PROPERTY, quotation_number: d.quotation_number,
    stage: { code: state.stage, label: label(state.stage), sequence: d.stage.sequence, of: 12, entered_on: '2026-10-14T10:00:00Z' }, owner: OPS,
    next_action_owner: { responsibility: 'SITE', person: OPS }, next_milestone: d.next_milestone,
    readiness: { next_stage: d.readiness.to, next_stage_label: label(d.readiness.to), allowed: d.readiness.allowed, blocker_count: d.readiness.blockers.length,
      risk: 'STANDARD', independent_approval: false, awaiting_approval: false },
    blockers: { gating: state.blockerOpen ? 1 : 0, informational: 0, customer_actions: state.blockerOpen ? 1 : 0, assigned_to_me: 0 }, site_ready: state.site === 'READY',
    site_actions: state.site === 'READY' ? 0 : 1, handover_ready: false, target_date: '2026-12-15', last_material_change: '2026-10-15T09:00:00Z', member: true };
}

const QA = { id: 'u-qa', display_name: 'SYNTHETIC Quality' };
const event = (state, code, extra = {}) => state.timeline.push({ id: `e${state.timeline.length + 1}`, code, stage_code: state.stage, from: null, to: null, detail: {},
  by: OPS, on: '2026-10-15T12:00:00Z', ...extra });

async function serve(p, state, me = ME) {
  state.posts = [];
  await p.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const json = (status, body) => route.fulfill({ status, contentType: status < 400 ? 'application/json' : 'application/problem+json', body: JSON.stringify(body) });
    const ok = (data, status = 200) => json(status, { data });
    if (path === '/api/v1/auth/refresh') return ok({ access_token: 'synthetic-token' });
    if (path === '/api/v1/auth/me') return ok(me);
    if (path === '/api/v1/projects' && req.method() === 'GET') {
      return ok({ projects: [row(state)], counts: { all: 1, mine: 1, blocked: state.blockerOpen ? 1 : 0, action_required: 1, site_readiness: 1, installation: 0, handover: 0 },
        bookable: [], lifecycle: { version: 'PLB-2026.10.1', status: 'PROPOSED' }, policy: POLICY });
    }
    if (path === '/api/v1/projects/vocabulary') return ok(VOCAB);
    if (path === '/api/v1/projects/p1/history') return ok([{ entity_type: 'project_blocker', entity_id: 'b1', action: 'UPDATE', changed_fields: ['status', 'resolution'], by: OPS, on: '2026-10-15T11:00:00Z', via: 'API' }]);
    if (path === '/api/v1/projects/p1' && req.method() === 'GET') return ok(detail(state));
    if (req.method() === 'POST' || req.method() === 'PATCH') {
      const body = req.postDataJSON() ?? {};
      state.posts.push({ path, body, ifMatch: req.headers()['if-match'] ?? null });
      const bump = () => { state.version += 1; };
      if (path === '/api/v1/projects/p1/transitions') {
        if (req.headers()['if-match'] !== `"${state.version}"`) return json(409, { status: 409, code: 'VERSION_CONFLICT', title: 'Conflict' });
        const blockers = blockersOf(state);
        const t = { id: `t${state.transitions.length + 1}`, version: 1, kind: 'STAGE', from_stage: state.stage, to_stage: body.to_stage,
          outcome: blockers.length ? 'REFUSED' : 'COMPLETED', independent_approval: false, requested_by: OPS, requested_on: '2026-10-15T12:00:00Z', reason: null,
          decided_by: blockers.length ? null : OPS, decided_on: null, decision_reason: null, blockers, handover: null };
        state.transitions.unshift(t);
        if (blockers.length) event(state, 'TRANSITION_REFUSED');
        else { event(state, 'STAGE_COMPLETED'); state.stage = body.to_stage; event(state, 'STAGE_ENTERED'); bump(); }
        return ok({ transition: t, outcome: t.outcome, project: detail(state) }, 201);
      }
      if (path === '/api/v1/projects/p1/blockers/b1/resolve') {
        if (!body.resolution || body.resolution.length < 5) return json(422, { status: 422, code: 'VALIDATION_FAILED', title: 'Invalid', errors: [{ field: 'resolution', code: 'REASON_REQUIRED', message: 'At least 5 characters.' }] });
        state.blockerOpen = false; state.resolution = body.resolution; state.blockerVersion += 1; event(state, 'BLOCKER_RESOLVED'); bump();
        return ok(detail(state));
      }
      if (path === '/api/v1/projects/p1/checklist/i1/complete') { state.itemOpen = false; state.itemVersion += 1; event(state, 'CHECKLIST_ITEM_COMPLETED'); bump(); return ok(detail(state)); }
      if (path === '/api/v1/projects/p1/site-readiness/r1') { state.site = body.status ?? state.site; state.siteVersion += 1; event(state, 'SITE_READINESS_UPDATED'); bump(); return ok(detail(state)); }
      if (path === '/api/v1/projects/p1/qc-checks') { state.qc = body.result; event(state, 'QC_RECORDED'); bump(); return ok(detail(state), 201); }
      if (path === '/api/v1/projects/p1/snags') { state.snag = 'OPEN'; event(state, 'SNAG_RAISED'); bump(); return ok(detail(state), 201); }
      if (path === '/api/v1/projects/p1/snags/n1/status') {
        if (body.status === 'READY_FOR_RECHECK') state.fixNote = body.note;
        state.snag = body.status; state.snagVersion += 1; event(state, body.status === 'RESOLVED' ? 'SNAG_RESOLVED' : body.status === 'READY_FOR_RECHECK' ? 'SNAG_FIXED' : 'SNAG_UPDATED'); bump();
        return ok(detail(state));
      }
    }
    if (req.method() === 'GET') return ok([]);
    return json(404, { status: 404, code: 'NOT_FOUND', title: 'Not found' });
  });
}

const fresh = () => ({ stage: 'SITE_READINESS', version: 7, blockerOpen: true, blockerVersion: 2, resolution: null, itemOpen: true, itemVersion: 1,
  site: 'CUSTOMER_ACTION_REQUIRED', siteVersion: 3, qc: null, snag: null, snagVersion: 1, transitions: [],
  timeline: [{ id: 'e0', code: 'PROJECT_CREATED', stage_code: 'BOOKED', from: null, to: 'BOOKED', detail: {}, by: OPS, on: '2026-10-14T10:00:00Z' }] });

async function axe(p, name) {
  await p.addScriptTag({ content: AXE });
  const v = await p.evaluate(async () => (await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }))
    .violations.map((x) => `${x.id} (${x.nodes.length}): ${x.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')}`));
  check(`axe ${name}`, v.length === 0, v.join(', '));
}

/** No horizontal page scroll, and every visible control of the page at least 44 x 44 px (a checkbox by its label). */
async function layout(p, tag, name) {
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(`${name}: no horizontal overflow`, overflow <= 0, `${overflow}px`);
  const small = await p.evaluate((t) => {
    const found = [];
    const walk = (root) => { root.querySelectorAll('button, select, textarea, input, a').forEach((n) => found.push(n)); root.querySelectorAll('*').forEach((n) => n.shadowRoot && walk(n.shadowRoot)); };
    const host = (function find(root) { const el = root.querySelector(t); if (el) return el; for (const n of root.querySelectorAll('*')) { if (n.shadowRoot) { const f = find(n.shadowRoot); if (f) return f; } } return null; })(document);
    walk(host.shadowRoot);
    return found.filter((n) => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden' && n.closest('dialog:not([open])') === null)
      .map((n) => { const x = n.type === 'checkbox' ? n.closest('label') ?? n : n; const r = x.getBoundingClientRect();
        return { what: `${n.tagName.toLowerCase()} ${(n.textContent || n.name || n.id || '').trim().slice(0, 30)}`, w: Math.round(r.width), h: Math.round(r.height) }; })
      .filter((x) => x.w < 44 || x.h < 44);
  }, tag);
  check(`${name}: targets at least 44 px`, small.length === 0, JSON.stringify(small.slice(0, 5)));
}

const page = (p) => p.locator('vs-project-page');
const button = (p, name) => page(p).getByRole('button', { name, exact: true });
const tab = (p, name) => page(p).locator('vs-tabs').getByRole('tab', { name, exact: true });
async function submitDialog(p) {
  await page(p).locator('vs-dialog button[type=submit]').click();
}
async function dialogClosed(p) {
  await p.waitForFunction(() => {
    const host = document.querySelector('vs-app')?.shadowRoot ?? document;
    const find = (root) => { const el = root.querySelector('vs-project-page'); if (el) return el; for (const n of root.querySelectorAll('*')) { if (n.shadowRoot) { const f = find(n.shadowRoot); if (f) return f; } } return null; };
    const pageEl = find(host);
    return pageEl && !pageEl.shadowRoot.querySelector('vs-dialog[open]');
  });
}

const browser = await chromium.launch();
try {
  // The journey at desktop width.
  {
    const state = fresh();
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    await serve(p, state);
    await p.goto(`${BASE}/projects`);
    const list = p.locator('vs-project-list-page');
    await list.locator('tbody tr').first().waitFor();
    check('dashboard: the eight questions', (await list.locator('thead th').allTextContents()).join('|') === 'Project|Current stage|Owner|Next milestone|Readiness|Blockers|Target date|Last material change');
    check('dashboard: blocked and overdue visible', await list.getByText('1 gating').isVisible() && await list.getByText(/past its planned date/).isVisible());
    await list.getByRole('link', { name: 'VS-P-2026-000001' }).click();
    await page(p).locator('dl.hero').waitFor();
    check('project: hero answers stage, owner, readiness and blocking issues', (await page(p).locator('dl.hero dt').allTextContents()).length === 7);
    const blocked = page(p).locator('.attention li.GATING').first();
    check('project: the blocked item says who acts, what is needed and what it blocks',
      (await blocked.textContent()).includes('Customer') && (await blocked.textContent()).includes('Please share the hob and chimney models')
      && (await blocked.textContent()).includes('Production readiness'));
    // A refused move: recorded, exact blockers, focus on the refusal.
    await button(p, 'Request the move to Production readiness').click();
    await submitDialog(p);
    await page(p).locator('#refusal-h').waitFor();
    check('move: refused with its exact blockers', (await page(p).locator('section[aria-labelledby=refusal-h] li').count()) === 3);
    check('move: focus moves to the refusal', await p.evaluate(() => {
      let a = document.activeElement; while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement; return a?.id === 'refusal-h';
    }));
    check('move: sent with the version the page showed', state.posts[0].ifMatch === '"7"');
    // Keyboard: the tabs move with the arrow keys; a dialog opens with focus inside and Escape closes it.
    await tab(p, 'Overview').focus();
    await p.keyboard.press('ArrowRight');
    await p.keyboard.press('ArrowRight');
    check('keyboard: arrow keys move between sections', (await tab(p, 'Stage and readiness').getAttribute('aria-selected')) === 'true');
    check('stage: the gate table names what is missing', await page(p).getByText('Site readiness flooring is customer action required.').first().isVisible());
    await tab(p, 'Blockers').click();
    await button(p, 'Resolve: Appliance specifications required').click();
    await page(p).locator('vs-dialog #project-form').waitFor();
    await submitDialog(p);
    await page(p).locator('vs-dialog textarea[aria-invalid=true]').waitFor();
    check('validation: the empty reason is marked invalid and summarised', (await page(p).locator('vs-dialog vs-error-summary strong').textContent()).includes('Please fix 1'));
    check('validation: nothing was sent', !state.posts.some((x) => x.path.endsWith('/resolve')));
    await p.keyboard.press('Escape');
    await dialogClosed(p);
    await button(p, 'Resolve: Appliance specifications required').click();
    await page(p).locator('vs-dialog textarea').fill('Models received by email');
    await submitDialog(p);
    await dialogClosed(p);
    check('blocker: resolved with a reason', state.resolution === 'Models received by email' && !state.blockerOpen);
    // Checklist and site readiness.
    await tab(p, 'Checklist').click();
    await page(p).getByRole('button', { name: 'Complete: Site readiness items reviewed with the customer' }).click();
    await submitDialog(p);
    await dialogClosed(p);
    check('checklist: completed', !state.itemOpen);
    await tab(p, 'Site readiness').click();
    check('site readiness: the promised text and the customer action', await page(p).getByText('Please complete the flooring in Bedroom 2').first().isVisible());
    await page(p).getByRole('button', { name: 'Update: SYNTHETIC: flooring complete.' }).click();
    await page(p).locator('vs-dialog select[name=status]').selectOption('READY');
    await submitDialog(p);
    await dialogClosed(p);
    check('site readiness: ready', state.site === 'READY');
    await tab(p, 'Overview').click();
    await button(p, 'Request the move to Production readiness').click();
    await submitDialog(p);
    await page(p).getByRole('heading', { name: /Production readiness/, level: 1 }).waitFor();
    check('move: completed once every gate is satisfied', state.stage === 'PRODUCTION_READINESS');
    // Quality and snags.
    await tab(p, 'Quality and snags').click();
    await button(p, 'Record a result').click();
    await page(p).locator('vs-dialog select[name=category]').selectOption('FINISH_AND_SURFACES');
    await page(p).locator('vs-dialog select[name=result]').selectOption('FAIL');
    await page(p).locator('vs-dialog textarea[name=observation]').fill('Edge banding lifting on the tall unit');
    await submitDialog(p);
    await dialogClosed(p);
    check('quality: the failure is recorded', state.qc === 'FAIL');
    await page(p).getByRole('button', { name: 'Raise a snag for the Finish and surfaces failure' }).click();
    await page(p).locator('vs-dialog select[name=category]').selectOption('FINISH');
    await page(p).locator('vs-dialog input[name=customer_title]').fill('Shutter edge to be refinished');
    await submitDialog(p);
    await dialogClosed(p);
    await page(p).getByRole('button', { name: 'Snag 1: Start fixing' }).click();
    await submitDialog(p);
    await dialogClosed(p);
    check('snag: being fixed', state.snag === 'IN_PROGRESS');
    await page(p).getByRole('button', { name: 'Snag 1: Record the fix' }).click();
    await submitDialog(p);
    await page(p).locator('vs-dialog textarea[aria-invalid=true]').waitFor();
    check('snag: the fixer must say what was fixed', state.snag === 'IN_PROGRESS');
    await page(p).locator('vs-dialog textarea[name=note]').fill('Edge banding replaced');
    await submitDialog(p);
    await dialogClosed(p);
    check('snag: fixed, awaiting verification', state.snag === 'READY_FOR_RECHECK');
    check('snag: the fixer is never offered the verification', (await page(p).getByRole('button', { name: 'Snag 1: Verify the fix' }).count()) === 0);
    // The quality persona verifies in their own session.
    {
      const qctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const q = await qctx.newPage();
      await serve(q, state, QA_ME);
      await q.goto(`${BASE}/projects/p1`);
      await page(q).locator('dl.hero').waitFor();
      await tab(q, 'Quality and snags').click();
      await page(q).getByRole('button', { name: 'Snag 1: Verify the fix' }).click();
      await page(q).locator('vs-dialog textarea[name=note]').fill('Rechecked: edge rebanded');
      await submitDialog(q);
      await dialogClosed(q);
      check('snag: verified by someone independent', state.snag === 'RESOLVED');
      await qctx.close();
    }
    await tab(p, 'Handover').click();
    check('handover: not ready, with why', await page(p).getByText('Not ready for handover.').isVisible());
    await tab(p, 'Timeline').click();
    check('timeline: an ordered list with a name', (await page(p).locator('ol.timeline[aria-label]').count()) === 1
      && (await page(p).locator('ol.timeline li').count()) >= 8);
    check('journey: no page errors', errors.length === 0, errors.join(' | '));
    await ctx.close();
  }
  // Layout, targets and axe at every width, on the dashboard, the overview, the gates, the blockers and an open dialog.
  for (const [name, viewport] of [['360 px', { width: 360, height: 740 }], ['390 px', { width: 390, height: 844 }],
    ['768 px', { width: 768, height: 1024 }], ['1280 px', { width: 1280, height: 800 }]]) {
    const state = fresh();
    state.snag = 'OPEN';
    state.qc = 'FAIL';
    const ctx = await browser.newContext({ viewport });
    const p = await ctx.newPage();
    await serve(p, state);
    await p.goto(`${BASE}/projects`);
    await p.locator('vs-project-list-page tbody tr').first().waitFor();
    await layout(p, 'vs-project-list-page', `${name} dashboard`);
    await axe(p, `${name} dashboard`);
    await p.goto(`${BASE}/projects/p1`);
    await page(p).locator('dl.hero').waitFor();
    await layout(p, 'vs-project-page', `${name} overview`);
    await axe(p, `${name} overview`);
    await p.screenshot({ path: `${OUT}/project-overview-${viewport.width}.png`, fullPage: true });
    for (const t of ['Stage and readiness', 'Blockers', 'Site readiness', 'Quality and snags', 'Audit and history']) {
      await tab(p, t).click();
      await page(p).locator('vs-tabs h2').first().waitFor();
      await layout(p, 'vs-project-page', `${name} ${t}`);
    }
    await axe(p, `${name} audit and history`);
    await tab(p, 'Blockers').click();
    await button(p, 'Raise a blocker').click();
    await page(p).locator('vs-dialog #project-form').waitFor();
    await axe(p, `${name} dialog`);
    await p.screenshot({ path: `${OUT}/project-dialog-${viewport.width}.png` });
    await ctx.close();
  }
} finally {
  await browser.close();
}
const failed = results.filter((x) => !x).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
