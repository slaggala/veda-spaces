import type { Dashboard, ProjectDetail, ProjectRow, Transition, Vocabulary } from '../../src/modules/project/api.js';

/** SYNTHETIC project models shaped exactly as the Project Lifecycle API returns them (api/veda/modules/project/present.py). */

const person = (id: string, name: string) => ({ id, display_name: name });
export const OPS = person('u-ops', 'SYNTHETIC Ops');
export const DESIGNER = person('u-des', 'SYNTHETIC Designer');
const STAGES = ['BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION',
  'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER'];
const label = (c: string) => c.charAt(0) + c.slice(1).toLowerCase().replace(/_/g, ' ');
const PROPERTY = { id: 'prop-1', property_number: 'VS-PR-2026-000001', configuration_label: '2 BHK', locality: 'Synthetic Nagar', city: 'Hyderabad' };
const POLICY = { version: 'PLB-POLICY-0', status: 'UNDECIDED', sha256: 'a'.repeat(64),
  decisions: Object.fromEntries(Array.from({ length: 13 }, (_, i) => [`PLB-OD-${String(i + 1).padStart(2, '0')}`,
    { label: `synthetic decision ${i + 1}`, decided: false, read_by_engine: i < 4 }])) };

export const vocabulary: Vocabulary = {
  stages: STAGES.map((c) => ({ code: c, label: label(c) })), responsibilities: ['COMMERCIAL', 'DESIGN', 'PROJECT', 'SITE', 'QUALITY', 'HANDOVER', 'MEMBER'],
  responsible_parties: ['CUSTOMER', 'VEDA', 'THIRD_PARTY', 'TO_BE_CONFIRMED'], milestone_types: ['DESIGN_SIGN_OFF', 'HANDOVER', 'OTHER'],
  milestone_states: ['NOT_STARTED', 'PLANNED', 'COMPLETED'], blocker_categories: ['SITE', 'CUSTOMER_DECISION', 'OTHER'], blocker_impacts: ['GATING', 'INFORMATIONAL'],
  blocker_statuses: ['OPEN', 'RESOLVED'], readiness_kinds: ['READINESS', 'RESPONSIBILITY'], readiness_categories: ['FLOORING', 'ACCESS', 'APPLIANCE_MODEL'],
  readiness_statuses: ['READY', 'NOT_READY', 'CUSTOMER_ACTION_REQUIRED', 'VEDA_ACTION_REQUIRED', 'NOT_APPLICABLE', 'TO_BE_CONFIRMED'],
  qc_categories: ['DIMENSIONS_AND_ALIGNMENT', 'FINISH_AND_SURFACES', 'OTHER'], qc_results: ['PASS', 'FAIL', 'NOT_APPLICABLE', 'TO_BE_CONFIRMED'],
  snag_categories: ['FINISH', 'OTHER'], snag_statuses: ['OPEN', 'IN_PROGRESS', 'READY_FOR_RECHECK', 'RESOLVED', 'CLOSED'],
  gates: [{ code: 'CHECKLIST_COMPLETE', label: 'Checklist', structural: false }],
  snag_priorities: ['HIGH', 'NORMAL', 'LOW'], snag_closure_codes: ['DUPLICATE', 'NOT_A_DEFECT', 'RAISED_IN_ERROR'],
  work_package_states: ['NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'], report_decline_codes: ['DUPLICATE', 'NOT_A_DEFECT', 'NOT_IN_SCOPE'],
};

export function row(over: Partial<ProjectRow> = {}): ProjectRow {
  return { id: 'p1', version: 4, project_number: 'VS-P-2026-000001', status: 'ACTIVE', property: PROPERTY, quotation_number: 'VS-Q-2026-000001',
    stage: { code: 'SITE_READINESS', label: 'Site readiness', sequence: 4, of: 12, entered_on: '2026-10-14T10:00:00Z' },
    owner: OPS, next_action_owner: { responsibility: 'SITE', person: OPS },
    next_milestone: { id: 'm1', label: 'Site ready', code: 'SITE_READY', stage_code: 'SITE_READINESS', status: 'PLANNED', planned_date: '2026-10-01', overdue: true },
    readiness: { next_stage: 'PRODUCTION_READINESS', next_stage_label: 'Production readiness', allowed: false, blocker_count: 2, risk: 'STANDARD',
      independent_approval: false, awaiting_approval: false },
    blockers: { gating: 1, informational: 1, customer_actions: 1, assigned_to_me: 0 }, site_ready: false, site_actions: 1, handover_ready: false,
    target_date: '2026-12-15', last_material_change: '2026-10-15T09:00:00Z', member: true, ...over };
}

export function dashboard(over: Partial<Dashboard> = {}): Dashboard {
  return { projects: [row()], counts: { all: 1, mine: 1, blocked: 1, action_required: 1, site_readiness: 1, installation: 0, handover: 0 },
    bookable: [], lifecycle: { version: 'PLB-2026.10.1', status: 'PROPOSED' }, policy: POLICY, ...over };
}

const blockerMsg = { gate: 'NO_GATING_BLOCKERS', code: 'GATING_BLOCKER_OPEN', message: 'An open gating blocker (customer decision) stops production readiness.',
  responsible_party: 'CUSTOMER', entity: { type: 'blocker', id: 'b1' }, blocks: 'PRODUCTION_READINESS' };
const siteMsg = { gate: 'SITE_READY', code: 'SITE_CUSTOMER_ACTION_REQUIRED', message: 'Site readiness flooring is customer action required.',
  responsible_party: 'CUSTOMER', entity: { type: 'site_readiness', id: 'r1' } };

export function transition(over: Partial<Transition> = {}): Transition {
  return { id: 't1', version: 1, kind: 'STAGE', from_stage: 'SITE_READINESS', to_stage: 'PRODUCTION_READINESS', outcome: 'REFUSED',
    independent_approval: false, requested_by: OPS, requested_on: '2026-10-15T09:00:00Z', reason: null, decided_by: null, decided_on: null,
    decision_reason: null, blockers: [blockerMsg, siteMsg], handover: null, ...over };
}

export function project(over: Partial<ProjectDetail> = {}): ProjectDetail {
  return {
    id: 'p1', version: 7, project_number: 'VS-P-2026-000001', status: 'ACTIVE', source: 'ACCEPTED_QUOTATION', property: PROPERTY,
    quotation_number: 'VS-Q-2026-000001', source_quotation_id: 'q1', created_on: '2026-10-14T10:00:00Z', created_by: OPS, handed_over_on: null,
    handed_over_by: null, lifecycle: { version: 'PLB-2026.10.1', sha256: 'b'.repeat(64), status: 'PROPOSED' },
    stage: { code: 'SITE_READINESS', label: 'Site readiness', description: 'The site satisfies what production depends on.', sequence: 4, of: 12,
      entered_on: '2026-10-14T10:00:00Z', owner_responsibility: 'SITE', customer_stage: 'SITE_READINESS' },
    owner: OPS, next_milestone: row().next_milestone,
    readiness: { from: 'SITE_READINESS', to: 'PRODUCTION_READINESS', transition: 'SITE_READINESS>PRODUCTION_READINESS', risk: 'STANDARD', command: 'STAGE',
      lifecycle: { version: 'PLB-2026.10.1', sha256: 'b'.repeat(64), status: 'PROPOSED' }, policy: { version: 'PLB-POLICY-0', sha256: 'c'.repeat(64) },
      independent_approval: false, allowed: false, blockers: [blockerMsg, siteMsg],
      gates: [{ code: 'TRANSITION_ALLOWED', label: 'The target is the next stage', source: 'STRUCTURAL', passed: true, blockers: [] },
        { code: 'NO_GATING_BLOCKERS', label: 'No open gating blocker', source: 'STRUCTURAL', passed: false, blockers: [blockerMsg] },
        { code: 'SITE_READY', label: 'Every site-readiness item is ready', source: 'DEFAULT', passed: false, blockers: [siteMsg] }] },
    awaiting_approval: null,
    handover_readiness: { ready: false, handed_over: false, stage_reached: false, blockers: [] },
    site_readiness_state: 'BLOCKED',
    attention: [{ severity: 'GATING', kind: 'BLOCKER', title: 'Appliance specifications required', who: 'CUSTOMER',
      action: 'Share the hob and chimney models', blocks: 'PRODUCTION_READINESS', entity: { type: 'blocker', id: 'b1' } }],
    next_actions: [{ gate: 'NO_GATING_BLOCKERS', code: 'GATING_BLOCKER_OPEN', who: 'CUSTOMER', message: blockerMsg.message, entity: blockerMsg.entity }],
    team: [{ id: 'mem1', version: 1, user: OPS, responsibility: 'PROJECT', active: true, eligible: true, assigned_on: '2026-10-14T10:00:00Z', assigned_by: OPS,
      removed_on: null, removed_by: null, removal_reason: null },
    { id: 'mem2', version: 1, user: DESIGNER, responsibility: 'DESIGN', active: true, eligible: true, assigned_on: '2026-10-14T10:00:00Z', assigned_by: OPS,
      removed_on: null, removed_by: null, removal_reason: null }],
    needs_reassignment: [],
    stages: STAGES.map((c, i) => ({ code: c, label: label(c), description: '', sequence: i + 1, customer_stage: 'SITE_READINESS', owner_responsibility: 'PROJECT',
      terminal: c === 'HANDED_OVER', status: i < 3 ? 'COMPLETED' : i === 3 ? 'ACTIVE' : 'NOT_STARTED', entered_on: null, entered_by: null,
      completed_on: null, completed_by: null, exit: null })),
    checklist: [{ stage_code: 'SITE_READINESS', stage_label: 'Site readiness', current: true, closed: false, done: 0, total: 1,
      items: [{ id: 'i1', version: 1, code: 'SITE_READINESS_REVIEWED', label: 'Site readiness items reviewed with the customer', ref: 'PLB-17',
        required: true, state: 'OPEN', completed_by: null, completed_on: null, note: null, not_applicable_reason: null, reopen_reason: null, evidence: null }] }],
    blockers: [{ id: 'b1', version: 2, category: 'CUSTOMER_DECISION', source: 'STAFF', impact: 'GATING', title: 'Appliance specifications required',
      description: 'Internal detail', customer_action: 'Share the hob and chimney models', responsible_party: 'CUSTOMER', assigned_to: OPS,
      target_date: null, status: 'OPEN', blocks: { code: 'PRODUCTION_READINESS', label: 'Production readiness' }, resolution: null, resolved_on: null,
      resolved_by: null, raised_on: '2026-10-14T11:00:00Z', raised_by: OPS,
      related: { milestone_id: null, checklist_item_id: null, site_readiness_id: null, quotation_id: null, work_package_id: null },
      customer_summary: null }],
    milestones: [], site_readiness: [{ id: 'r1', version: 3, kind: 'READINESS', source: 'CUSTOMER_PROMISE', item_code: 'SYN_FLOOR', category: 'FLOORING',
      label: 'SYNTHETIC: flooring complete.', promise: { content_version: 'CPP-1', text: 'SYNTHETIC: flooring complete.', quoted_status: 'TO_BE_CONFIRMED' },
      status: 'CUSTOMER_ACTION_REQUIRED', satisfied: false, responsible_party: 'CUSTOMER', action: 'Flooring not laid', customer_action: 'Please complete the flooring',
      due_date: null, note: null, evidence: null, resolved_on: null, resolved_by: null, updated_on: null }],
    qc: { required_categories: ['DIMENSIONS_AND_ALIGNMENT'], categories: [{ category: 'DIMENSIONS_AND_ALIGNMENT', required: true, latest: null }],
      points: [], chains: [], history: [] },
    snags: [], work_packages: [], customer_reports: [], handover_packages: [],
    delivery_policy: { version: 'PEX-POLICY-0', status: 'UNDECIDED', decisions: { 'PEX-D01': { label: 'customer actions in the portal', decided: false },
      'PEX-D02': { label: 'the commercial condition for handover', decided: false } } },
    baseline: { full: true, verified: true, problems: [], current_seq: 1, open_variations: [], variations: [],
      lineage: [{ id: 'bl1', sequence_no: 1, kind: 'ORIGINAL', current: true, quotation_id: 'q1', label: 'VS-Q-2026-000001 v1', variation_no: 0,
        decided_on: '2026-10-13T10:00:00Z', decision_method: 'SIGNED_COPY', recorded_on: '2026-10-14T10:00:00Z', accepted_total_minor: 123456700,
        cumulative_value_minor: 123456700, baseline_sha256: 'd'.repeat(64) }] },
    transitions: [], timeline: [{ id: 'e1', code: 'PROJECT_CREATED', stage_code: 'BOOKED', from: null, to: 'BOOKED', detail: {}, by: OPS, on: '2026-10-14T10:00:00Z' }],
    spaces: [{ id: 's1', label: 'Kitchen' }], evidence_options: [],
    actions: { request_transition: true, complete_handover: true, approve_transition: false, assign_team: true, complete_checklist: true,
      checklist_not_applicable: false, manage_milestone: true, raise_blocker: true, resolve_blocker: true, manage_site_readiness: true, manage_qc: true,
      manage_snag: true, view_commercial_baseline: true, view_audit: true, record_promised_date: false, reclassify_snag: false,
      qc_required_not_applicable: false, manage_work: true, verify_snag: false, prepare_handover_package: false },
    policy: POLICY, classification: { classes: ['INTERNAL_ONLY'], default: 'INTERNAL_ONLY', fields: {}, published_through: 'VEDA_PROJECT_DELIVERY_PORTAL_ENABLED' },
    last_material_change: '2026-10-15T09:00:00Z', ...over,
  };
}
