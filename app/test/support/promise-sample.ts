import type { Landing, SectionView, VersionDetail, VersionSummary, Vocabulary } from '../../src/modules/promise/api.js';

/** SYNTHETIC Customer Promise API payloads shared by the unit tests and the browser journey (not a test file itself).
 * Nothing here is a Veda Spaces contact, promise, warranty, duration or payment instruction. */

export const SECTIONS: [string, string, string[], boolean, string][] = [
  ['CONTACTS', 'Contact and support', ['email_domains', 'contacts', 'support_escalation'], false, 'customer_promise.contacts.edit'],
  ['INCLUSIONS', 'Project inclusions', ['project_inclusions'], false, 'customer_promise.edit'],
  ['RESPONSIBILITIES', 'Customer responsibilities', ['client_responsibilities'], true, 'customer_promise.edit'],
  ['SITE_READINESS', 'Site readiness', ['site_readiness'], false, 'customer_promise.edit'],
  ['SITE_WORK', 'Site-dependent work', ['site_dependent_work'], true, 'customer_promise.edit'],
  ['WARRANTY', 'Warranty and service', ['manufacturer_warranty_note'], true, 'customer_promise.warranty.edit'],
  ['EXCLUSIONS', 'Warranty exclusions', ['warranty_exclusions'], true, 'customer_promise.warranty.edit'],
  ['SERVICE', 'Service guidance', ['service_guidance'], false, 'customer_promise.contacts.edit'],
  ['HANDOVER', 'Handover', ['handover'], false, 'customer_promise.edit'],
  ['CARE', 'Care guidance', ['care'], false, 'customer_promise.edit'],
  ['NEXT_STEPS', 'What happens next', ['next_steps'], false, 'customer_promise.edit'],
  ['PAYMENT_SAFETY', 'Payment safety', ['payment_safety'], true, 'customer_promise.payment_safety.edit'],
];

export const vocabulary: Vocabulary = {
  sections: SECTIONS.map(([code, title, keys, sensitive, edit]) => ({ code, title, keys, sensitive, edit_permission: edit,
    review_permission: sensitive ? 'customer_promise.review.sensitive' : 'customer_promise.review' })),
  areas: [],
  contact_kinds: ['QUOTATION', 'SUPPORT', 'SERVICE'],
  responsibility_categories: ['CLIENT_SUPPLIED_ITEM', 'APPLIANCE_MODEL', 'OTHER'],
  responsibility_statuses: ['REQUIRED', 'NOT_REQUIRED', 'TO_BE_CONFIRMED'],
  readiness_categories: ['FLOORING', 'ELECTRICAL_SUPPLY', 'OTHER'],
  readiness_statuses: ['READY', 'NOT_READY', 'CUSTOMER_ACTION_REQUIRED', 'NOT_APPLICABLE', 'TO_BE_CONFIRMED'],
  site_work_categories: ['ELECTRICAL', 'PLUMBING', 'CIVIL'],
  handover_categories: ['PROTECTION', 'CLEANING', 'FINAL_INSPECTION'],
  care_categories: ['FURNITURE_CLEANING', 'LAMINATE_CARE'],
  stages: ['PROPOSAL_ACCEPTED', 'VEDA_CONFIRMATION', 'SCOPE_DESIGN_FINALISATION', 'HANDOVER'],
  limits: { copy: 600, label: 80, duration: 80, summary: 500 },
};

const author = { id: 'u-author', display_name: 'SYNTHETIC Author' };

export const values: Record<string, Record<string, unknown>> = {
  CONTACTS: { email_domains: ['synthetic.example'], contacts: [
    { code: 'SYN_DESK', kind: 'QUOTATION', display_name: 'SYNTHETIC Desk', role: 'Consultant (synthetic)', phone: '+00 0000 000000',
      email: 'desk@synthetic.example', hours: null, channel_note: null, business_channel_approved: true },
    { code: 'SYN_SUP', kind: 'SUPPORT', display_name: 'SYNTHETIC Support', role: 'Care (synthetic)', phone: null,
      email: 'care@synthetic.example', hours: null, channel_note: null, business_channel_approved: true }], support_escalation: null },
  INCLUSIONS: { project_inclusions: [{ code: 'SYN_INSTALL', text: 'SYNTHETIC installation of the listed items.' }] },
  RESPONSIBILITIES: { client_responsibilities: [] },
  SITE_READINESS: { site_readiness: [] },
  SITE_WORK: { site_dependent_work: null },
  WARRANTY: { manufacturer_warranty_note: null },
  EXCLUSIONS: { warranty_exclusions: [] },
  SERVICE: { service_guidance: null },
  HANDOVER: { handover: [] },
  CARE: { care: [] },
  NEXT_STEPS: { next_steps: [{ code: 'SYN_A', stage: 'PROPOSAL_ACCEPTED', label: 'Accepted', text: 'SYNTHETIC step.', duration: null },
    { code: 'SYN_B', stage: 'HANDOVER', label: 'Handover', text: 'SYNTHETIC step.', duration: null }] },
  PAYMENT_SAFETY: { payment_safety: null },
};

export function summary(over: Partial<VersionSummary> = {}): VersionSummary {
  return {
    id: 'p1', version: 4, version_no: 1, status: 'DRAFT', origin: 'NEW', content_version: 'CPP-1', change_summary: 'SYNTHETIC first pack',
    based_on_version: null, content_sha256: 'a'.repeat(64), created_on: '2026-10-15T10:00:00Z', created_by: author, updated_on: null,
    submitted_on: null, submitted_by: null, approved_on: null, approved_by: null, published_on: null, published_by: null,
    published_sha256: null, superseded_on: null, superseded_by_version: null, effective: 'NOT_EFFECTIVE', quotations: {}, ...over,
  };
}

export function version(over: Partial<VersionDetail> = {}, section: Partial<SectionView> = {}): VersionDetail {
  const status = over.status ?? 'DRAFT';
  return {
    ...summary({ status }),
    sections: SECTIONS.map(([code, title, keys, sensitive, edit]) => ({
      code, title, keys, sensitive, edit_permission: edit, review_permission: sensitive ? 'customer_promise.review.sensitive' : 'customer_promise.review',
      changed: ['CONTACTS', 'INCLUSIONS', 'NEXT_STEPS'].includes(code), value: structuredClone(values[code]), sha256: 'b'.repeat(64), review: null,
      contributors: [author], can_edit: status === 'DRAFT', can_review: false, ...(code === 'INCLUSIONS' ? section : {}),
    })),
    changed_sections: ['CONTACTS', 'INCLUSIONS', 'NEXT_STEPS'], pending_reviews: status === 'IN_REVIEW' ? ['CONTACTS', 'INCLUSIONS', 'NEXT_STEPS'] : [],
    problems: [], reviews: [],
    actions: { save: status === 'DRAFT', summary: status === 'DRAFT', discard: status === 'DRAFT', submit: status === 'DRAFT', approve: false,
      return: false, publish: false, preview: true, history: true },
    ...over,
  };
}

export function landing(over: Partial<Landing> = {}): Landing {
  const areas = ['Your Veda Spaces contact', 'Project inclusions', 'Customer responsibilities', 'Site readiness', 'Site-dependent work',
    'Manufacturer warranty', 'Veda Spaces service and workmanship support', 'Warranty exclusions', 'How to request service',
    'Handover expectations', 'Care guidance', 'What happens after approval', 'Payment safety', 'Support and escalation'];
  return {
    authority: { state: 'NOT_RECORDED', register_reference: null, decided_on: null,
      message: 'Owner decision OI-MTQ-18 is not recorded: quotations show every customer information section as to be confirmed, whatever is published here.' },
    published: null, open: null, pending_reviews: [],
    areas: areas.map((title, i) => ({ code: `A${i}`, title, section: i === 6 ? null : 'INCLUSIONS', governed_by: i === 6 ? 'OI-MTQ-09' : 'OI-MTQ-18',
      status: i === 1 ? 'DRAFT' : 'NOT_STARTED', structure_exists: true, owner_approved_content: false, customer_sees: 'TO_BE_CONFIRMED' })),
    versions: 0, effective_dating: 'IMMEDIATE_ON_PUBLISH', actions: { create_draft: true, preview: true, history: true }, ...over,
  };
}
