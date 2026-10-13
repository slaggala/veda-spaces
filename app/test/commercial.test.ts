import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Me } from '../src/core/api/types.js';
import { sessionContext } from '../src/core/authz/context.js';
import '../src/modules/commercial/index.js';

/** MTQ B2-B4: the commercial workspace (scope → BOQ → estimate → quotation). The API is mocked; the server decides. */

const PERMS = ['scope.read', 'scope.edit', 'scope.confirm', 'boq.read', 'boq.generate', 'boq.override', 'boq.review',
  'cost_estimate.read', 'cost_estimate.create', 'cost_estimate.approve', 'quotation.read', 'quotation.create'];
const lineage = { stale: false, reasons: [] };
const journey = {
  property_number: 'VS-P-2026-000001', current_measurement_set: { id: 'm1', revision_no: 2, survey_level_code: 'FULL' },
  ruleset: { version: '2026.10.1', status: 'PROPOSED' }, requirements: { ACCEPTED: 3, PROPOSED: 1 },
  scopes: [{ id: 's1', version: 2, revision_no: 1, status: 'CONFIRMED', lineage }],
  boqs: [{ id: 'b1', version: 2, revision_no: 1, status: 'REVIEWED', lineage }],
  cost_estimates: [{ id: 'e1', version: 2, revision_no: 1, status: 'APPROVED', lineage }],
  quotations: [{ id: 'q1', version: 1, label: 'VS-Q-2026-000001 v1', status: 'DRAFT' }],
};
const policy = { version: '2026.10.0-UNSET', status: 'OWNER_DECISIONS_PENDING',
  decisions: { 'OI-MTQ-07': { label: 'GST treatment', decided: false }, 'OI-MTQ-09': { label: 'terms', decided: false } } };
const requirements = [{ id: 'r1', version: 1, space_id: 'sp1', space_label: 'Bedroom 2', requirement_type_code: 'WARDROBE', label: 'Wardrobe',
  necessity_code: 'MANDATORY', status: 'PROPOSED', classification: 'MANDATORY', source_code: 'MEASUREMENT_RULE', origin_code: 'AUTO',
  source_ref: { fact: 'W2 tagged WARDROBE' }, catalogue_mapped: true, decision_reason: null, notes: null }];
const scope = { ...journey.scopes[0], tier_code: 'ESSENTIAL', measurement_revision_no: 2, ruleset_version: '2026.10.1', ruleset_status: 'PROPOSED',
  exclusions: [], generation_run: {}, snapshot_sha256: 'x', items: [{ id: 'i1', version: 1, requirement_id: 'r1', space_id: 'sp1',
    space_label: 'Bedroom 2', item_type_code: 'WARDROBE', label: 'Wardrobe', origin_code: 'AUTO', necessity_code: 'MANDATORY',
    inclusion_code: 'INCLUDED', catalogue_mapped: true, unmapped_reason: null, effective_options: {}, finish_code: null,
    inputs: { WIDTH: { value: '10.83', unit: 'ft', source: 'MEASURED', explain: 'W2 length 3300 mm' } }, dimension_overrides: {},
    override_reason: null, dimension_source_code: 'MEASURED', carried_from_item_id: null }] };
const boq = { ...journey.boqs[0], scope_revision_no: 1, measurement_revision_no: 2, catalogue_card_version: 'SYNTHETIC-2',
  quantity_engine_version: '2026.10.1', issues: [{ code: 'RULESET_NOT_APPROVED', severity: 'WARNING', message: 'Proposed rules.' }], summary: {},
  lines: [{ id: 'l1', version: 1, space_id: 'sp1', space_label: 'Bedroom 2', label: 'Wardrobe — Body', uom_code: 'SFT', unit_text: 'sq ft',
    formula_kind: 'CARD_AREA', derivation: 'width 10.83 ft (W2 length 3300 mm) × height 6.89 ft = 74.62 sq ft',
    calculated_quantity_centi: 7462, override_quantity_centi: null, override_reason: null, final_quantity_centi: 7462,
    is_optional: false, dimension_source_code: 'MEASURED', status: 'OK', issues: [] }] };
const view = { key: 'sp1', label: 'Bedroom 2', amount_minor: 746200, discount_minor: 0, optional_minor: 0, unpriced_lines: 0 };
const estimate = { ...journey.cost_estimates[0], tier_code: 'ESSENTIAL', boq_id: 'b1', boq_revision_no: 1, rate_card_version: null,
  subtotal_minor: 746200, optional_minor: 0, discount_minor: 0, taxable_minor: 746200, tax_status: 'GST_POLICY_REQUIRED', tax_minor: null,
  total_minor: null, unpriced_lines: 0, pricing_basis_code: 'MEASURED', blockers: [{ code: 'GST_POLICY_REQUIRED', decision: 'OI-MTQ-07',
    severity: 'BLOCKING', message: 'GST treatment is not decided.' }], views: { rooms: [view], categories: [view], components: [view] },
  lines: [], adjustments: [], discount_policy: { enabled: false, message: 'Discount authority is not decided (OI-MTQ-06); discount actions are disabled.' } };
const quotation = { ...journey.quotations[0], quotation_number: 'VS-Q-2026-000001', version_no: 1, quotation_kind: 'BASE', title: 'Interior works',
  cover_note: null, base_total_minor: 746200, optional_minor: 0, discount_minor: 0, taxable_minor: 746200, tax_status: 'GST_POLICY_REQUIRED',
  tax_minor: null, total_minor: null, customer_issuable: false, valid_until: null, snapshot_sha256: null, snapshot_verified: null,
  blockers: [{ code: 'OWNER_DECISION_REQUIRED', decision: 'OI-MTQ-09', severity: 'BLOCKING', message: 'Terms are not recorded.' }],
  lineage: { estimate_revision_no: 1, boq_revision_no: 1, scope_revision_no: 1, measurement_revision_no: 2, cost_estimate_id: 'e1' }, sections: [] };

function serve(notFound = false) {
  window.fetch = async (input: RequestInfo | URL) => {
    const path = new URL(String(input), location.href).pathname;
    if (notFound) {
      return new Response(JSON.stringify({ status: 404, code: 'NOT_FOUND', title: 'Not found' }), { status: 404, headers: { 'Content-Type': 'application/problem+json' } });
    }
    const body = path.endsWith('/commercial') ? journey : path.endsWith('/commercial-policy') ? policy
      : path.endsWith('/requirements') ? requirements : path.startsWith('/api/v1/scopes/') ? scope
      : path.startsWith('/api/v1/boqs/') ? boq : path.startsWith('/api/v1/cost-estimates/') ? estimate
      : path.endsWith('/document') ? { document: {}, html: '<p>Quotation</p>' } : quotation;
    return new Response(JSON.stringify({ data: body }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
}

async function mount(notFound = false): Promise<HTMLElement & { tab: string }> {
  serve(notFound);
  const host = await fixture<HTMLDivElement>(html`<div></div>`);
  new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated',
    me: { id: 'u1', permissions: Object.fromEntries(PERMS.map((p) => [p, 'ALL'])), features: { mtq_site: true, mtq_estimation: true, mtq_quotation: true } } as unknown as Me } });
  const page = document.createElement('vs-commercial-page') as HTMLElement & { location: unknown; tab: string };
  page.location = { params: { id: 'p1' } };
  host.append(page);
  return page;
}

describe('commercial workspace', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  it('says the feature is off when the API answers 404', async () => {
    const page = await mount(true);
    await waitUntil(() => page.shadowRoot?.textContent?.includes('not enabled'), 'disabled message');
  });

  it('shows the lineage, the proposed-ruleset warning and the undecided owner decisions', async () => {
    const page = await mount();
    await waitUntil(() => page.shadowRoot?.textContent?.includes('VS-Q-2026-000001 v1'), 'journey loaded');
    const text = page.shadowRoot!.textContent!;
    expect(text).to.include('PROPOSED').and.include('OI-MTQ-07').and.include('Revision 2');
    await expect(page).to.be.accessible();
  });

  it('every stage is reviewable room by room and stays accessible', async () => {
    const page = await mount();
    await waitUntil(() => page.shadowRoot?.textContent?.includes('VS-Q-2026-000001 v1'), 'journey loaded');
    for (const [tab, expected] of [['scope', 'W2 tagged WARDROBE'], ['boq', 'W2 length 3300 mm'], ['estimate', 'discount actions are disabled'],
      ['quotation', 'Terms are not recorded']] as const) {
      page.tab = tab;
      await waitUntil(() => page.shadowRoot!.textContent!.includes(expected), `${tab} rendered`);
      if (tab !== 'quotation') expect(page.shadowRoot!.textContent).to.include('Bedroom 2');
      await expect(page).to.be.accessible();
    }
  });
});
