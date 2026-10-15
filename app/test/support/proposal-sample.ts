import type { Page } from '../../src/modules/proposal/api.js';

/** A SYNTHETIC customer proposal page model shared by the proposal tests (not a test file itself). */
export function samplePage(over: Partial<Page> = {}): Page {
  const line = (ref: string, description: string, amount: string, status = 'Included') =>
    ({ ref, description, detail: 'Laminate finish', quantity: '42.5 sq ft', amount, priced: true, status });
  return {
    state: 'OPEN',
    link: { expires_on: '2099-01-01T00:00:00Z', status: 'ACTIVE' },
    history: [],
    capabilities: { interaction: false, acceptance: false },
    notices: [],
    actions: [],
    proposal: {
      schema: 'veda.customer-proposal/1', kind: 'QUOTATION', title: 'Quotation', brand: { name: 'Veda Spaces', tagline: 'Interiors, measured and made' },
      reference: 'VS-Q-2026-000001 v1', quotation_number: 'VS-Q-2026-000001', version_no: 1, variation_no: 0, issued_on: '2026-10-14',
      valid_until: '2026-11-13', subject: 'Interior works — 3 BHK apartment', cover_note: null,
      property: { reference: 'VS-P-2026-000001', configuration: '3 BHK apartment', city: 'Synthetic City' }, snapshot_sha256: 'a'.repeat(64),
      rooms: [
        { ref: 'R1', title: 'Master bedroom', kind: 'ROOM', subtotal: '1,20,000.00', included_count: 2, optional_count: 1,
          lines: [line('L1', 'Wardrobe — Body', '90,000.00'), line('L2', 'Wardrobe — Shutters', '30,000.00')] },
        { ref: 'R2', title: 'Kitchen', kind: 'ROOM', subtotal: '2,00,000.00', included_count: 1, optional_count: 0,
          lines: [line('L3', 'Kitchen — Base units', '2,00,000.00')] },
        { ref: 'R3', title: 'Project-wide', kind: 'PROJECT', subtotal: '10,000.00', included_count: 1, optional_count: 0,
          lines: [line('L4', 'Site protection', '10,000.00')] },
      ],
      optional_items: [{ ...line('L9', 'Loft above wardrobe', '15,000.00', 'Optional'), room_ref: 'R1', room_title: 'Master bedroom' }],
      summary: { base_total: '3,30,000.00', taxable: '3,30,000.00', gst: { status: 'Included', amount: '59,400.00' }, total: '3,89,400.00',
        optional_total: '15,000.00', currency: 'INR' },
      payment_schedule: [{ label: 'Booking', share: '10%', trigger: 'On acceptance (synthetic)' }], warranty: ['Synthetic warranty.'],
      service_support: [], assumptions: ['Synthetic assumption.'], exclusions: ['Synthetic exclusion.'], terms: ['Synthetic terms.'],
      terms_version: 'SYN-T1', unit_rates_shown: false, sections: { SCOPE: 'b'.repeat(64) },
    },
    ...over,
  };
}
