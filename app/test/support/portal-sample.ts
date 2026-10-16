import type { AccessRow, Home, PropertyCard, PropertyView, QuotationPage, QuotationSummary, Step } from '../../src/modules/portal/api.js';
import { samplePage } from './proposal-sample.js';

/** SYNTHETIC portal models (not Veda Spaces content), shaped exactly as the API returns them. */

export function quotation(over: Partial<QuotationSummary> = {}): QuotationSummary {
  return { id: 'q1', reference: 'VS-Q-2026-000001 v1', title: 'Quotation', kind: 'QUOTATION', version_no: 1, state: 'OPEN',
    status: 'ACTION_REQUIRED', status_label: 'Awaiting your decision', issued_on: '2026-10-12', valid_until: '2026-11-11',
    days_left: 26, total: '₹4,25,000.00', currency: 'INR', ...over };
}

export const JOURNEY: Step[] = [
  { key: 'consultation', label: 'Consultation', state: 'COMPLETED', detail: 'We have your enquiry.', date: null },
  { key: 'site_measurement', label: 'Site measurement', state: 'COMPLETED', detail: 'Your site has been measured and the measurements checked.', date: '2026-10-08' },
  { key: 'design_scope', label: 'Design and scope', state: 'COMPLETED', detail: 'The scope of work for your home has been prepared.', date: null },
  { key: 'quotation', label: 'Your quotation', state: 'COMPLETED', detail: 'Your quotation has been shared with you.', date: '2026-10-12' },
  { key: 'approval', label: 'Your approval', state: 'ACTION_REQUIRED', detail: 'Your quotation is waiting for your decision.', date: null },
  { key: 'execution', label: 'Execution', state: 'NOT_YET_AVAILABLE', detail: 'Progress for this stage is not shown in your portal yet.', date: null },
  { key: 'quality', label: 'Quality checks', state: 'NOT_YET_AVAILABLE', detail: 'Progress for this stage is not shown in your portal yet.', date: null },
  { key: 'handover', label: 'Handover', state: 'NOT_YET_AVAILABLE', detail: 'Progress for this stage is not shown in your portal yet.', date: null },
];

export function card(over: Partial<PropertyCard> = {}): PropertyCard {
  return { id: 'p1', property: { reference: 'VS-P-2026-000001', configuration: '3 BHK apartment with a very long SYNTHETIC configuration name',
    locality: 'Synthetic Nagar', city: 'Hyderabad' }, enquiry: { reference: '81DG-6BJR' }, headline: 'We are waiting for your decision.',
    next_step: { key: 'approval', label: 'Your approval', state: 'ACTION_REQUIRED', detail: 'Your quotation is waiting for your decision.', date: null },
    attention_count: 1, quotation: quotation(), contact: { source: 'QUOTATION', name: 'SYNTHETIC Contact', role: 'Design consultant',
      phone: '+910000000000', email: 'hello@synthetic.example', hours: 'Mon–Sat, 10 am–7 pm' }, project_tracking: false, ...over };
}

export function home(over: Partial<Home> = {}): Home {
  return { customer: { name: 'SYNTHETIC Customer' }, enquiries: [{ reference: '81DG-6BJR', relationship: 'PRIMARY_CUSTOMER', closed: false,
    properties: [card()] }], project_tracking_available: false, ...over };
}

export function view(over: Partial<PropertyView> = {}): PropertyView {
  return {
    ...card(), journey: JOURNEY,
    attention: [{ kind: 'QUOTATION_DECISION', status: 'ACTION_REQUIRED', title: 'Review your quotation and tell us your decision',
      text: 'To accept, decline or ask a question, use the secure proposal link Veda Spaces sent you, or speak to your Veda Spaces contact.',
      due: '2026-11-11', quotation_id: 'q1' }],
    quotations: [quotation()], documents: [{ ...quotation(), kind: 'QUOTATION' }],
    included: [{ title: 'Kitchen', kind: 'ROOM', included_count: 2, optional_count: 1, items: [
      { description: 'Base cabinets with a long SYNTHETIC description of the carcass and shutter finish', detail: 'BWP plywood', status: 'Included' },
      { description: 'Tall unit', detail: null, status: 'Optional' }] }],
    commitments: { source: 'VS-Q-2026-000001 v1', inclusions: [{ code: 'I1', text: 'Design, manufacture and installation' }],
      warranty: ['10 years on carcass (SYNTHETIC)'], manufacturer_warranty_note: null, handover: [{ code: 'H1', text: 'Joint walkthrough' }],
      care: null, next_steps: [{ code: 'N1', stage: 'VEDA_CONFIRMATION', label: 'Confirmation', text: 'We confirm your order.', duration: '2 days' }],
      payment_schedule: [{ label: 'Booking', share: '10%', trigger: 'On acceptance' }], payment_safety: 'Pay only to the Veda Spaces account.' },
    responsibilities: { client: [{ code: 'C1', text: 'Society permission for work hours' }], site_readiness: [{ code: 'R1', text: 'Flooring complete' }] },
    support: { contacts: [], escalation: null },
    ...over,
  };
}

export function quotationPage(over: Partial<QuotationPage> = {}): QuotationPage {
  const page = samplePage();
  return { state: page.state, proposal: page.proposal, history: page.history, capabilities: { interaction: false, acceptance: false },
    notices: [{ code: 'DECIDE_BY_LINK', message: 'To accept, decline or ask a question, use the secure proposal link Veda Spaces sent you.' }],
    actions: [], summary: quotation(), ...over } as QuotationPage;
}

export function access(over: Partial<AccessRow> = {}): AccessRow {
  return { id: 'a1', version: 1, relationship: 'PRIMARY_CUSTOMER', status: 'ACTIVE',
    account: { display_name: 'SYNTHETIC Customer', email: 'customer@synthetic.example', status: 'ACTIVE', last_signed_in_on: null },
    granted_on: '2026-10-16T05:00:00Z', granted_by: { id: 'u1', display_name: 'SYNTHETIC Sales' }, revoked_on: null, revoked_by: null,
    revoke_reason_code: null, ...over };
}
