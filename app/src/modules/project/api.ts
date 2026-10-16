import { api, newIdempotencyKey } from '../../core/api/client.js';

/** Types and calls of the Project Lifecycle API (staff only; every route answers 404 while VEDA_PROJECT_LIFECYCLE_ENABLED
 * is off). Writes to an existing row send the version the page showed (If-Match); a new row sends an Idempotency-Key.
 * The server evaluates every gate and checks every capability in the project's scope: the page only hides controls. */

const BASE = '/api/v1/projects';

export interface Person { id: string; display_name: string | null }
export interface PropertyRef { id: string; property_number: string; configuration_label: string | null; locality: string | null; city: string | null }
export interface EntityRef { type: string; id: string }
export interface GateBlocker {
  gate: string; code: string; message: string; responsible_party?: string; entity?: EntityRef; blocks?: string;
  decision?: string; responsibility?: string; category?: string; item_code?: string;
}
export interface Gate { code: string; label: string; source: 'STRUCTURAL' | 'DEFAULT' | 'OWNER_DECISION'; passed: boolean | null; blockers: GateBlocker[] }
export interface Evaluation {
  from: string; to: string | null; transition: string | null; risk: 'STANDARD' | 'HIGH' | null; command: 'STAGE' | 'HANDOVER' | null;
  lifecycle: { version: string; sha256: string; status: string }; policy: { version: string; sha256: string };
  independent_approval: boolean; gates: Gate[]; blockers: GateBlocker[]; allowed: boolean;
}
export interface CommercialPosition { account_id: string; value: string; paid: string; outstanding: string; schedule_state: string; lines_due: number }
export interface HandoverReadiness { ready: boolean; handed_over: boolean; stage_reached?: boolean; blockers: GateBlocker[]; commercial_position?: CommercialPosition | null }

export interface ProjectRow {
  id: string; version: number; project_number: string; status: string; property: PropertyRef; quotation_number: string;
  stage: { code: string; label: string; sequence: number; of: number; entered_on: string | null };
  owner: Person | null; next_action_owner: { responsibility: string; person: Person | null };
  next_milestone: { id: string; label: string; code: string; stage_code: string; status: string; planned_date: string | null; overdue: boolean } | null;
  readiness: { next_stage: string | null; next_stage_label: string | null; allowed: boolean; blocker_count: number; risk: string | null;
    independent_approval: boolean; awaiting_approval: boolean } | null;
  blockers: { gating: number; informational: number; customer_actions: number; assigned_to_me: number };
  site_ready: boolean; site_actions: number; handover_ready: boolean; target_date: string | null; last_material_change: string | null; member: boolean;
}
export interface Bookable { quotation_id: string; quotation_number: string; label: string; property_id: string; decided_on: string | null;
  problems: { code: string; message: string }[] }
export interface PolicyView { version: string; status: string; sha256: string;
  decisions: Record<string, { label: string; decided: boolean; read_by_engine: boolean }> }
export interface Dashboard {
  projects: ProjectRow[]; counts: Record<string, number>; bookable: Bookable[];
  lifecycle: { version: string; status: string }; policy: PolicyView;
}

export interface Stage {
  code: string; label: string; description: string; sequence: number; customer_stage: string; owner_responsibility: string; terminal: boolean;
  status: 'NOT_STARTED' | 'ACTIVE' | 'COMPLETED'; entered_on: string | null; entered_by: Person | null; completed_on: string | null;
  completed_by: Person | null; exit: { to: string; risk: string; default_gates: string[] } | null;
}
export interface Evidence { attachment_id: string | null; reference: string | null }
export interface ChecklistItem {
  id: string; version: number; code: string; label: string; ref: string; required: boolean; state: 'OPEN' | 'DONE' | 'NOT_APPLICABLE';
  completed_by: Person | null; completed_on: string | null; note: string | null; not_applicable_reason: string | null;
  reopen_reason: string | null; evidence: Evidence | null;
}
export interface ChecklistGroup { stage_code: string; stage_label: string; current: boolean; closed: boolean; done: number; total: number; items: ChecklistItem[] }
export interface Blocker {
  id: string; version: number; category: string; source: string; impact: 'GATING' | 'INFORMATIONAL'; title: string; description: string | null;
  customer_action: string | null; responsible_party: string; assigned_to: Person | null; target_date: string | null; status: string;
  blocks: { code: string; label: string } | null; resolution: string | null; resolved_on: string | null; resolved_by: Person | null;
  raised_on: string | null; raised_by: Person | null;
  related: { milestone_id: string | null; checklist_item_id: string | null; site_readiness_id: string | null; quotation_id: string | null;
    work_package_id: string | null };
  customer_summary: string | null;
}
export interface Milestone {
  id: string; version: number; code: string; label: string; customer_label: string | null; description: string | null; stage_code: string;
  status: string; status_reason: string | null; planned_date: string | null; actual_date: string | null; customer_promised_date: string | null;
  overdue: boolean; depends_on_milestone_id: string | null; owner_responsibility: string | null; evidence: Evidence | null;
}
export interface ReadinessItem {
  id: string; version: number; kind: string; source: 'CUSTOMER_PROMISE' | 'STAFF'; item_code: string; category: string; label: string | null;
  promise: { content_version: string | null; text: string | null; quoted_status: string | null } | null;
  status: string; satisfied: boolean; responsible_party: string; action: string | null; customer_action: string | null; due_date: string | null;
  note: string | null; evidence: Evidence | null; resolved_on: string | null; resolved_by: Person | null; updated_on: string | null;
}
export interface QcRow {
  id: string; category: string; result: string; space: string | null; space_id: string | null; observation: string | null; evidence: Evidence | null;
  recheck_of_id: string | null; qc_point_id: string | null; work_package_id: string | null; checked_by: Person | null; checked_on: string | null;
}
export interface QcPoint {
  id: string; version: number; point_no: number; category: string; label: string; space: string | null; space_id: string | null;
  work_package_id: string | null; evidence_required: boolean; status: 'ACTIVE' | 'WITHDRAWN'; withdrawn_reason: string | null;
  result: string | null; head_id: string | null;
}
export interface QcChain { head: QcRow; length: number; ever_failed: boolean; root_id: string }
/** A body of work in one stage. `state` is derived by the server (BLOCKED from open gating blockers; CORRECTION_REQUIRED
 * when completed work failed its check or has an open snag): it is never chosen. */
export interface WorkPackage {
  id: string; version: number; package_no: number; stage_code: string; space: string | null; space_id: string | null; title: string;
  description: string | null; customer_label: string | null; customer_visible: boolean; owner: Person | null; depends_on_id: string | null;
  status: 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
  state: 'NOT_STARTED' | 'IN_PROGRESS' | 'BLOCKED' | 'COMPLETED' | 'CORRECTION_REQUIRED' | 'CANCELLED';
  scheduled: boolean; planned_start: string | null; planned_finish: string | null; plan_revision: number; replan_reason: string | null;
  past_planned_finish: boolean; actual_start: string | null; actual_finish: string | null; started_by: Person | null; completed_by: Person | null;
  completion_note: string | null; reopen_reason: string | null; cancel_reason: string | null; evidence: Evidence | null;
}
export interface CustomerReport {
  id: string; version: number; report_no: number; channel: 'PORTAL' | 'STAFF'; description: string; area: string | null;
  status: 'SUBMITTED' | 'ACCEPTED' | 'DECLINED'; snag_id: string | null; decline_code: string | null; response: string | null;
  reported_on: string | null; recorded_by: Person | null; triaged_by: Person | null; triaged_on: string | null;
}
export interface HandoverPackage {
  id: string; version: number; package_no: number; status: 'PREPARED' | 'SUPERSEDED' | 'COMPLETED'; content_sha256: string; redacted: boolean;
  content: {
    work: { completed: { label: string; finished_on: string | null }[]; completed_count: number; cancelled_count: number };
    quality: { checks_passed: number; checks_not_applicable: number; corrected_after_failure: number; failed: number };
    snags: { fixed_and_verified: number; closed_without_fix: number; open_non_blocking: { number: number; title: string }[]; open_non_blocking_count: number };
    documents: unknown[]; warranty: { source: string; quotation_id: string; quotation_number: string };
  };
  prepared_on: string | null; prepared_by: Person | null; acknowledged_on: string | null; completed_on: string | null;
  superseded_on: string | null; superseded_by: Person | null; stale: string | null;
}
export interface Snag {
  id: string; version: number; snag_no: number; category: string; customer_title: string; description: string | null; space: string | null;
  space_id: string | null; item_reference: string | null; is_blocking: boolean; classification_reason: string | null; owner: Person | null; responsible_party: string; status: string;
  allowed_next: string[]; target_date: string | null; evidence: Evidence | null; resolution_note: string | null; resolved_on: string | null;
  resolved_by: Person | null; closed_on: string | null; closed_by: Person | null; qc_check_id: string | null; raised_on: string | null; raised_by: Person | null;
  work_package_id: string | null; source: 'STAFF' | 'QUALITY_CHECK' | 'CUSTOMER'; priority: 'HIGH' | 'NORMAL' | 'LOW'; customer_visible: boolean;
  fixed_by: Person | null; fixed_on: string | null; fix_note: string | null; closure_code: string | null;
}
export interface BaselineRow {
  id: string; sequence_no: number; kind: 'ORIGINAL' | 'VARIATION'; current: boolean; quotation_id: string; label: string | null; variation_no: number;
  decided_on: string | null; decision_method: string; recorded_on: string | null;
  accepted_total_minor?: number; cumulative_value_minor?: number; selected_optional_count?: number; snapshot_sha256?: string;
  accepted_baseline_sha256?: string; estimate_snapshot_sha256?: string; baseline_sha256?: string; previous_baseline_id?: string | null;
  customer_promise?: Record<string, unknown> | null;
  lineage?: { measurement_revision_no: number; scope_revision_no: number; boq_revision_no: number; estimate_revision_no: number };
}
export interface BaselineView {
  full: boolean; verified: boolean; problems: { code: string; message: string }[]; current_seq: number; lineage: BaselineRow[];
  variations: { quotation_id: string; label: string; status: string; total_minor?: number | null }[];
  open_variations: { quotation_id: string; label: string; status: string }[];
}
export interface Transition {
  id: string; version: number; kind: 'STAGE' | 'HANDOVER'; from_stage: string; to_stage: string;
  outcome: 'REFUSED' | 'AWAITING_APPROVAL' | 'COMPLETED' | 'REJECTED' | 'WITHDRAWN'; independent_approval: boolean;
  requested_by: Person | null; requested_on: string | null; reason: string | null; decided_by: Person | null; decided_on: string | null;
  decision_reason: string | null; blockers: GateBlocker[];
  handover: { handover_on: string | null; acknowledgement_reference: string | null; evidence_attachment_id: string | null; observations: string | null } | null;
  evaluation?: Evaluation; evaluation_sha256?: string;
}
export interface TimelineEvent { id: string; code: string; stage_code: string | null; from: string | null; to: string | null;
  detail: Record<string, unknown>; by: Person | null; on: string | null }
export interface Attention { severity: 'ACTION' | 'GATING' | 'SITE' | 'INFORMATIONAL'; kind: string; title: string; who: string;
  action: string | null; blocks: string | null; entity: EntityRef }
export interface TeamMember { id: string; version: number; user: Person | null; responsibility: string; active: boolean; eligible: boolean; assigned_on: string | null;
  assigned_by: Person | null; removed_on: string | null; removed_by: Person | null; removal_reason: string | null }
export interface Actions {
  request_transition: boolean; complete_handover: boolean; approve_transition: boolean; assign_team: boolean; complete_checklist: boolean;
  checklist_not_applicable: boolean; manage_milestone: boolean; raise_blocker: boolean; resolve_blocker: boolean; manage_site_readiness: boolean;
  manage_qc: boolean; manage_snag: boolean; view_commercial_baseline: boolean; view_audit: boolean;
  /** Owner decisions PLB-OD-13, PLB-OD-06, PLB-OD-08 recorded and naming a capability this person holds here. */
  record_promised_date: boolean; reclassify_snag: boolean; qc_required_not_applicable: boolean;
  /** PEX: work packages, independent snag verification, the handover package (READY_FOR_HANDOVER only). */
  manage_work: boolean; verify_snag: boolean; prepare_handover_package: boolean;
}
export interface ProjectDetail {
  id: string; version: number; project_number: string; status: string; source: string; property: PropertyRef; quotation_number: string;
  source_quotation_id: string; created_on: string | null; created_by: Person | null; handed_over_on: string | null; handed_over_by: Person | null;
  lifecycle: { version: string; sha256: string; status: string };
  stage: { code: string; label: string; description: string; sequence: number; of: number; entered_on: string | null; owner_responsibility: string;
    customer_stage: string };
  owner: Person | null; next_milestone: ProjectRow['next_milestone']; readiness: Evaluation | null; awaiting_approval: Transition | null;
  handover_readiness: HandoverReadiness; site_readiness_state: 'NOT_ASSESSED' | 'READY' | 'BLOCKED' | 'TO_BE_CONFIRMED';
  attention: Attention[]; next_actions: { gate: string; code: string; who: string; message: string; entity: EntityRef | null }[];
  team: TeamMember[]; needs_reassignment: string[]; stages: Stage[]; checklist: ChecklistGroup[]; blockers: Blocker[]; milestones: Milestone[]; site_readiness: ReadinessItem[];
  qc: { required_categories: string[]; categories: { category: string; required: boolean; latest: QcRow | null }[]; points: QcPoint[];
    chains: QcChain[]; history: QcRow[] };
  work_packages: WorkPackage[]; customer_reports: CustomerReport[]; handover_packages: HandoverPackage[];
  delivery_policy: { version: string; status: string; decisions: Record<string, { label: string; decided: boolean }> };
  snags: Snag[]; baseline: BaselineView; transitions: Transition[]; timeline: TimelineEvent[]; spaces: { id: string; label: string }[];
  evidence_options: { id: string; category: string; attached_to: string; uploaded_on: string | null }[];
  actions: Actions; policy: PolicyView; classification: { classes: string[]; default: string; fields: Record<string, Record<string, string>>; published_through: string };
  last_material_change: string | null;
}
export interface TransitionResult { transition: Transition; outcome: Transition['outcome']; project: ProjectDetail }
export interface Vocabulary {
  stages: { code: string; label: string }[]; responsibilities: string[]; responsible_parties: string[]; milestone_types: string[];
  milestone_states: string[]; blocker_categories: string[]; blocker_impacts: string[]; blocker_statuses: string[]; readiness_kinds: string[];
  readiness_categories: string[]; readiness_statuses: string[]; qc_categories: string[]; qc_results: string[]; snag_categories: string[];
  snag_statuses: string[]; gates: { code: string; label: string; structural: boolean }[];
  snag_priorities: string[]; snag_closure_codes: string[]; work_package_states: string[]; report_decline_codes: string[];
}
export interface Candidate { id: string; display_name: string | null; responsibilities: string[] }
export interface HistoryRow { entity_type: string; entity_id: string; action: string; changed_fields: string[]; by: Person | null; on: string | null; via: string }

export type Query = Partial<Record<'view' | 'q' | 'stage' | 'owner' | 'blocker' | 'readiness' | 'milestone' | 'handover', string>>;
type Body = Record<string, unknown>;
const at = (p: { id: string }) => `${BASE}/${p.id}`;

export const projectApi = {
  list: (q: Query = {}) => api.get<Dashboard>(BASE, q),
  vocabulary: () => api.get<Vocabulary>(`${BASE}/vocabulary`),
  get: (id: string) => api.get<ProjectDetail>(`${BASE}/${id}`),
  history: (p: ProjectDetail) => api.get<HistoryRow[]>(`${at(p)}/history`),
  candidates: (p: ProjectDetail) => api.get<Candidate[]>(`${at(p)}/team/candidates`),
  book: (quotation_id: string, property_id: string) =>
    api.post<ProjectDetail>(BASE, { quotation_id, property_id }, { idempotencyKey: newIdempotencyKey() }),
  // Writes on the project as a whole (the version the page showed).
  assign: (p: ProjectDetail, body: Body) => api.post<ProjectDetail>(`${at(p)}/team`, body, { ifMatch: p.version }),
  transition: (p: ProjectDetail, body: Body) => api.post<TransitionResult>(`${at(p)}/transitions`, body, { ifMatch: p.version }),
  handover: (p: ProjectDetail, body: Body) => api.post<TransitionResult>(`${at(p)}/handover`, body, { ifMatch: p.version }),
  // Writes on one row (that row's version).
  decide: (p: ProjectDetail, t: Transition, action: 'approve' | 'reject' | 'withdraw', body: Body) =>
    api.post<TransitionResult>(`${at(p)}/transitions/${t.id}/${action}`, body, { ifMatch: t.version }),
  removeMember: (p: ProjectDetail, m: TeamMember, body: Body) => api.post<ProjectDetail>(`${at(p)}/team/${m.id}/remove`, body, { ifMatch: m.version }),
  completeItem: (p: ProjectDetail, i: ChecklistItem, body: Body) => api.post<ProjectDetail>(`${at(p)}/checklist/${i.id}/complete`, body, { ifMatch: i.version }),
  reopenItem: (p: ProjectDetail, i: ChecklistItem, body: Body) => api.post<ProjectDetail>(`${at(p)}/checklist/${i.id}/reopen`, body, { ifMatch: i.version }),
  addMilestone: (p: ProjectDetail, body: Body) => api.post<ProjectDetail>(`${at(p)}/milestones`, body, { idempotencyKey: newIdempotencyKey() }),
  updateMilestone: (p: ProjectDetail, m: Milestone, body: Body) => api.patch<ProjectDetail>(`${at(p)}/milestones/${m.id}`, body, { ifMatch: m.version }),
  completeMilestone: (p: ProjectDetail, m: Milestone, body: Body) =>
    api.post<ProjectDetail>(`${at(p)}/milestones/${m.id}/complete`, body, { ifMatch: m.version }),
  raiseBlocker: (p: ProjectDetail, body: Body) => api.post<ProjectDetail>(`${at(p)}/blockers`, body, { idempotencyKey: newIdempotencyKey() }),
  updateBlocker: (p: ProjectDetail, b: Blocker, body: Body) => api.patch<ProjectDetail>(`${at(p)}/blockers/${b.id}`, body, { ifMatch: b.version }),
  closeBlocker: (p: ProjectDetail, b: Blocker, action: 'resolve' | 'cancel', body: Body) =>
    api.post<ProjectDetail>(`${at(p)}/blockers/${b.id}/${action}`, body, { ifMatch: b.version }),
  addReadiness: (p: ProjectDetail, body: Body) => api.post<ProjectDetail>(`${at(p)}/site-readiness`, body, { idempotencyKey: newIdempotencyKey() }),
  updateReadiness: (p: ProjectDetail, r: ReadinessItem, body: Body) =>
    api.patch<ProjectDetail>(`${at(p)}/site-readiness/${r.id}`, body, { ifMatch: r.version }),
  recordQc: (p: ProjectDetail, body: Body) => api.post<ProjectDetail>(`${at(p)}/qc-checks`, body, { idempotencyKey: newIdempotencyKey() }),
  raiseSnag: (p: ProjectDetail, body: Body) => api.post<ProjectDetail>(`${at(p)}/snags`, body, { idempotencyKey: newIdempotencyKey() }),
  snagStatus: (p: ProjectDetail, s: Snag, body: Body) => api.post<ProjectDetail>(`${at(p)}/snags/${s.id}/status`, body, { ifMatch: s.version }),
  reclassifySnag: (p: ProjectDetail, s: Snag, body: Body) =>
    api.post<ProjectDetail>(`${at(p)}/snags/${s.id}/classification`, body, { ifMatch: s.version }),
  updateSnag: (p: ProjectDetail, s: Snag, body: Body) => api.patch<ProjectDetail>(`${at(p)}/snags/${s.id}`, body, { ifMatch: s.version }),
  // PEX: work packages, the QC plan, customer reports and the handover package.
  addWork: (p: ProjectDetail, body: Body) => api.post<ProjectDetail>(`${at(p)}/work-packages`, body, { idempotencyKey: newIdempotencyKey() }),
  updateWork: (p: ProjectDetail, w: WorkPackage, body: Body) => api.patch<ProjectDetail>(`${at(p)}/work-packages/${w.id}`, body, { ifMatch: w.version }),
  workCommand: (p: ProjectDetail, w: WorkPackage, command: 'start' | 'complete' | 'reopen' | 'cancel', body: Body) =>
    api.post<ProjectDetail>(`${at(p)}/work-packages/${w.id}/${command}`, body, { ifMatch: w.version }),
  addQcPoint: (p: ProjectDetail, body: Body) => api.post<ProjectDetail>(`${at(p)}/qc-points`, body, { idempotencyKey: newIdempotencyKey() }),
  withdrawQcPoint: (p: ProjectDetail, q: QcPoint, body: Body) => api.post<ProjectDetail>(`${at(p)}/qc-points/${q.id}/withdraw`, body, { ifMatch: q.version }),
  recordReport: (p: ProjectDetail, body: Body) => api.post<ProjectDetail>(`${at(p)}/customer-reports`, body, { idempotencyKey: newIdempotencyKey() }),
  triageReport: (p: ProjectDetail, r: CustomerReport, body: Body) =>
    api.post<ProjectDetail>(`${at(p)}/customer-reports/${r.id}/triage`, body, { ifMatch: r.version }),
  preparePackage: (p: ProjectDetail) => api.post<ProjectDetail>(`${at(p)}/handover-package`, {}, { ifMatch: p.version }),
};
