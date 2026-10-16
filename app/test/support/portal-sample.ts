import type { AccessRow, Commercials, Home, PropertyCard, PropertyView, QuotationPage, QuotationSummary, Step } from '../../src/modules/portal/api.js';
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
      phone: '+910000000000', email: 'hello@synthetic.example', hours: 'Mon–Sat, 10 am–7 pm' }, project_tracking: false, payments: null, ...over };
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
    support: { contacts: [], escalation: null }, commercials: null,
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

/** SYNTHETIC commercial view (PCM): every figure is a server string; the page formats nothing. */
export function commercials(over: Partial<Commercials> = {}): Commercials {
  return {
    available: true,
    summary: { currency: 'INR', total_value: '12,34,567.00 SYNTHETIC', includes_gst: '1,88,323.00', paid: '1,23,457.00', outstanding: '11,11,110.00',
      credit: null, next_payment: { label: 'Production', amount: '6,17,284.00', when: 'Before production (synthetic)', state: 'DUE', state_label: 'Due',
        due_on: '2026-11-30' }, as_of: '2026-10-16' },
    schedule: [
      { label: 'Booking', when: 'On acceptance (synthetic)', amount: '1,23,457.00', gst_included: '18,832.00', paid: '1,23,457.00', remaining: '0.00',
        state: 'PAID', state_label: 'Paid', requested: true, due_on: null },
      { label: 'Production', when: 'Before production (synthetic)', amount: '6,17,284.00', gst_included: '94,162.00', paid: '0.00', remaining: '6,17,284.00',
        state: 'DUE', state_label: 'Due', requested: true, due_on: '2026-11-30' },
      { label: 'Handover with a very long SYNTHETIC instalment name that must wrap on a phone', when: 'On handover (synthetic)', amount: '4,93,826.00',
        gst_included: '75,329.00', paid: '0.00', remaining: '4,93,826.00', state: 'UPCOMING', state_label: 'Upcoming', requested: false, due_on: null },
    ],
    payments: [{ amount: '1,23,457.00', received_on: '2026-10-14', method: 'Bank transfer', reference: 'UTR-SYNTHETIC-0000000001', note: 'Booking amount',
      status: 'RECORDED', status_label: 'Recorded', correction: null, receipt: { id: 'r1', number: 'VS-R-2026-00001', status: 'VALID' } }],
    invoices: [{ id: 'i1', number: 'VS-I-2026-00001', issued_on: '2026-10-15', due_on: '2026-11-30', label: 'Production', amount: '6,17,284.00',
      status: 'DUE', status_label: 'Due' }],
    receipts: [{ id: 'r1', number: 'VS-R-2026-00001', issued_on: '2026-10-14', amount: '1,23,457.00', status: 'VALID', status_label: 'Valid' }],
    notices: [], how_to_pay: 'Pay using the payment details Veda Spaces gave you in writing. Your payment appears here once Veda Spaces has recorded it.',
    ...over,
  };
}
