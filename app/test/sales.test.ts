import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Me } from '../src/core/api/types.js';
import { sessionContext } from '../src/core/authz/context.js';
import { filterNav, NAV_ITEMS } from '../src/core/authz/permissions.js';
import type { Demo, Funnel, PipelineRow } from '../src/modules/sales/api.js';
import { countText, quotedText, ratioText, stageLabel, attentionLabel, channelLabel } from '../src/modules/sales/labels.js';
import '../src/modules/sales/index.js';

/**
 * Sales & Customer Acquisition (SCA): navigation behind its flag, the vocabulary helpers, and the pages' refusal to
 * invent a number ("Not tracked" is never 0, a claimed stage is marked in words, the demo never reaches a customer API).
 * SYNTHETIC data; the API is a window.fetch stub.
 */

const V1 = { 'lead.read': 'ALL', 'lead.create': 'ALL', 'lead_activity.read': 'ALL', 'profile.read': 'ALL', 'user.read': 'ALL',
  'role.read': 'ALL', 'permission.read': 'ALL', 'audit.read': 'ALL', 'user.mfa.reset': 'ALL', 'user.founder.manage': 'ALL',
  'catalog.view': 'ALL' } as const;
const SALES = { 'sales.pipeline.view': 'ALL', 'sales.funnel.view': 'ALL', 'sales.demo.view': 'ALL' } as const;
const V1_MENU = ['/', '/leads', '/follow-ups', '/approvals', '/admin/users', '/admin/roles', '/admin/permissions',
  '/admin/founder-actions', '/catalog', '/audit', '/profile'];

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const problem = (status: number, code: string) =>
  new Response(JSON.stringify({ status, code, title: code }), { status, headers: { 'Content-Type': 'application/problem+json' } });

const row = (over: Partial<PipelineRow> = {}): PipelineRow => ({
  lead: { id: 'l1', lead_number: 'VS-L-SYN-0001', name: 'SYNTHETIC One', city: 'Hyderabad', status: 'QUOTATION_SENT', created_on: '2026-10-01T04:30:00Z' },
  source: { code: 'WEBSITE', label: 'Website' }, channel: { code: 'ORGANIC_SEARCH', label: 'Organic search', detail: null },
  stage: { code: 'QUOTATION_ISSUED', label: 'Quotation issued', basis: 'LEAD_STATUS', basis_label: 'Status recorded by staff', claimed_without_record: true },
  facts: { estimate: null, contacted_on: null, consultation_on: null, properties: [], visits: [], quotation: null, quotations: 0, accepted: null, proposal: null,
    customer_requests: { total: 0, waiting_on_staff: 0, waiting_on_customer: 0 }, project: null },
  quoted: { withheld: true }, owner: null, last_activity_on: '2026-10-10T04:30:00Z', next_follow_up_on: '2026-10-11T04:30:00Z', is_follow_up_overdue: true,
  attention: [{ code: 'FOLLOW_UP_OVERDUE', label: 'Follow-up overdue' }], customer_action: 'Decision on the issued quotation',
  closed: { won_on: null, lost_on: null, lost_reason: null }, ...over,
});

const funnel = (): Funnel => ({
  period: { from: '2026-09-18', to: '2026-10-17', timezone: 'Asia/Kolkata' }, as_of: '2026-10-17T10:00:00Z',
  site: {
    site_visit: { count: null, basis: 'CLIENT_EVENT', tracking: 'NOT_TRACKED', by_channel: null },
    estimator_started: { count: null, basis: 'CLIENT_EVENT', tracking: 'NOT_TRACKED', by_channel: null },
    enquiry_started: { count: 4, basis: 'CLIENT_EVENT', tracking: 'TRACKED', by_channel: { DIRECT: 4 } },
    journey_viewed: { count: 0, basis: 'CLIENT_EVENT', tracking: 'TRACKED', by_channel: {} },
  },
  estimates_completed: { count: 0, basis: 'AUTHORITATIVE', tracking: 'TRACKED' },
  leads: [{ code: 'leads_created', label: 'Enquiries received', count: 3, basis: 'AUTHORITATIVE', tracking: 'TRACKED' },
    { code: 'quotation_issued', label: 'Quotation issued', count: 1, basis: 'AUTHORITATIVE', tracking: 'TRACKED' },
    { code: 'accepted', label: 'Accepted by the customer', count: 0, basis: 'AUTHORITATIVE', tracking: 'TRACKED' },
    { code: 'won', label: 'Won', count: 0, basis: 'AUTHORITATIVE', tracking: 'TRACKED' }, { code: 'lost', label: 'Lost', count: 0, basis: 'AUTHORITATIVE', tracking: 'TRACKED' }],
  cohort: { size: 3, truncated: false, claimed_stages_without_record: 1 },
  current_stages: [{ code: 'NEW', label: 'New enquiry', count: 2 }, { code: 'QUOTATION_ISSUED', label: 'Quotation issued', count: 1 }],
  ratios: { estimator_start_to_estimate: { value: null, reason: 'NOT_TRACKED' }, site_visit_to_enquiry: { value: null, reason: 'NOT_TRACKED' },
    enquiry_to_quotation: { value: 0.3333, reason: null }, quotation_to_acceptance: { value: 0, reason: null }, enquiry_to_won: { value: 0, reason: null },
    decided_to_won: { value: null, reason: 'NO_DENOMINATOR' } },
  by_channel: [{ code: 'DIRECT', label: 'Direct contact', leads: 3, quotation_issued: 1, accepted: 0, won: 0, lost: 0 }],
  by_source: [{ code: 'WEBSITE', label: 'Website', leads: 3, won: 0 }], lost_reasons: [], stalled: { quiet: 1 },
});

const CONTACT = { display_name: 'DEMO designer', role: 'Your design consultant (demo)', phone: '+00 0000 000000', email: 'demo@example.com', hours: null, channel_note: null };
const demo = (): Demo => ({
  demo: true, label: 'DEMO: synthetic example, not a customer', as_of: '2026-10-17',
  journey: [{ key: 'consultation', label: 'Consultation', state: 'COMPLETED', detail: 'DEMO: first conversation held', date: '2026-09-07' },
    { key: 'execution', label: 'Execution', state: 'IN_PROGRESS', detail: 'DEMO: installation under way', date: null }],
  portal: {
    demo: true, label: 'DEMO: synthetic example, not a customer', id: 'demo-property',
    property: { reference: 'DEMO-P-0001', configuration: '3 BHK apartment', locality: 'Demo locality', city: 'Hyderabad' }, enquiry: { reference: 'DEMO-REF1' },
    headline: 'DEMO: your home interiors project', next_step: { key: 'execution', label: 'Execution', state: 'IN_PROGRESS', detail: 'DEMO: installation under way', date: null },
    attention_count: 0, quotation: null, contact: { source: 'CONSULTANT', name: 'DEMO designer', role: 'Your design consultant (demo)', phone: '+00 0000 000000', email: 'demo@example.com', hours: null },
    project_tracking: true, payments: null, journey: [], attention: [], quotations: [], documents: [], commercials: null, included: null, commitments: null,
    responsibilities: null, support: null, delivery: null, warranty: null,
  },
  proposal: {
    demo: true, label: 'DEMO: synthetic example, not a customer', state: 'OPEN', link: { expires_on: '', status: 'PREVIEW' }, history: [],
    capabilities: { interaction: false, acceptance: false }, notices: [], actions: [],
    proposal: {
      schema: 'veda.customer-proposal/1', kind: 'QUOTATION', title: 'DEMO: your quotation', brand: { name: 'Veda Spaces', tagline: 'Interiors, measured and made' },
      reference: 'DEMO-Q-0001', quotation_number: 'DEMO-Q-0001', version_no: 1, variation_no: 0, issued_on: '2026-09-26', valid_until: '2026-10-26',
      subject: 'DEMO: 3 BHK apartment interiors', cover_note: 'DEMO: a synthetic quotation.', property: { reference: 'DEMO-P-0001', configuration: '3 BHK apartment', city: 'Hyderabad' },
      snapshot_sha256: null, rooms: [], optional_items: [], summary: { base_total: 'DEMO total', total: 'DEMO total', currency: 'INR' }, payment_schedule: [],
      warranty: [], service_support: [], assumptions: [], exclusions: [], terms: [], terms_version: 'DEMO', unit_rates_shown: false, sections: {},
      information: { content_version: 'DEMO', contacts: { quotation: CONTACT, support: [CONTACT], service: [CONTACT] }, support_escalation: null,
        project_inclusions: [{ code: 'D1', text: 'DEMO: the scope listed in your quotation' }], client_responsibilities: null, site_readiness: null, site_dependent_work: null,
        manufacturer_warranty_note: null, warranty_exclusions: null, service_guidance: null, handover: null, care: null, next_steps: null, payment_safety: null },
    },
  } as unknown as Demo['proposal'],
});

interface Stub { calls: { method: string; path: string; query: string }[] }
function stub(handler: (path: string, query: URLSearchParams) => Response): Stub {
  const calls: Stub['calls'] = [];
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), location.href);
    calls.push({ method: init?.method ?? 'GET', path: url.pathname, query: url.search });
    return handler(url.pathname, url.searchParams);
  };
  return { calls };
}

async function mount(tag: string, perms: Record<string, string> = SALES, props: Record<string, unknown> = {}) {
  const host = await fixture<HTMLDivElement>(html`<div></div>`);
  new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated',
    me: { id: 'u1', permissions: perms, features: { sales_experience: true } } as unknown as Me } });
  const el = document.createElement(tag) as HTMLElement & { updateComplete: Promise<unknown> };
  Object.assign(el, props);
  host.append(el);
  await el.updateComplete;
  return el;
}

describe('Sales & Customer Acquisition (SCA)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  it('hides the sales pages without the feature, whatever the permissions, and leaves the V1 menu exactly as it was', () => {
    const perms = { ...V1, ...SALES };
    for (const features of [undefined, null, {}, { sales_experience: false }]) {
      const paths = filterNav(NAV_ITEMS, perms, features).map((i) => i.path);
      expect(paths).to.not.include('/sales').and.not.include('/sales/funnel').and.not.include('/sales/demo');
    }
    expect(filterNav(NAV_ITEMS, perms, { sales_experience: false }).map((i) => i.path)).to.deep.equal(V1_MENU);
    expect(filterNav(NAV_ITEMS, V1).map((i) => i.path)).to.deep.equal(V1_MENU);
  });

  it('shows each sales page only with the feature on AND its own permission', () => {
    const on = { sales_experience: true };
    expect(filterNav(NAV_ITEMS, SALES, on).map((i) => i.path)).to.include.members(['/sales', '/sales/funnel', '/sales/demo']);
    expect(filterNav(NAV_ITEMS, { 'sales.pipeline.view': 'ALL' }, on).map((i) => i.path)).to.deep.equal(['/sales']);
    expect(filterNav(NAV_ITEMS, V1, on).map((i) => i.path)).to.deep.equal(V1_MENU);
  });

  it('labels: the server label wins, the mirrored vocabulary fills in, and nothing becomes a number it is not', () => {
    expect(stageLabel({ code: 'SITE_MEASUREMENT', label: 'Server label' })).to.equal('Server label');
    expect(stageLabel({ code: 'SITE_MEASUREMENT' })).to.equal('Site measurement');
    expect(stageLabel('BRAND_NEW_STAGE')).to.equal('Brand new stage');
    expect(attentionLabel('QUIET')).to.equal('No activity for 14 days and nothing planned');
    expect(channelLabel({ code: 'PAID' })).to.equal('Paid campaign');
    expect(countText({ count: null, tracking: 'NOT_TRACKED' })).to.equal('Not tracked');
    expect(countText({ count: 0, tracking: 'TRACKED' })).to.equal('0');
    expect(countText({ count: 12, tracking: 'TRACKED' })).to.equal('12');
    expect(ratioText({ value: null, reason: 'NOT_TRACKED' })).to.equal('Not tracked');
    expect(ratioText({ value: null, reason: 'NO_DENOMINATOR' })).to.equal('No data yet');
    expect(ratioText({ value: 0.3333, reason: null })).to.equal('33.3%');
    expect(ratioText({ value: 0, reason: null })).to.equal('0%');
    expect(quotedText({ withheld: true })).to.equal('Withheld');
    expect(quotedText({ amount_minor: 185000000, currency: 'INR' })).to.equal('₹18,50,000');
    expect(quotedText(null)).to.equal('—');
  });

  it('funnel: a beacon never received reads "Not tracked", never 0; a tracked zero reads 0; null ratios carry their reason', async () => {
    stub((path) => (path === '/api/v1/sales/funnel' ? json({ data: funnel() }) : problem(404, 'NOT_FOUND')));
    const el = await mount('vs-sales-funnel-page');
    await waitUntil(() => el.shadowRoot?.querySelector('vs-kpi-tile'), 'report rendered');
    const tiles = [...el.shadowRoot!.querySelectorAll('vs-kpi-tile')] as (HTMLElement & { label: string; value: string; hint: string })[];
    const tile = (label: string) => tiles.find((t) => t.label === label)!;
    expect(tile('Site visits').value).to.equal('Not tracked');
    expect(tile('Estimator starts').value).to.equal('Not tracked');
    expect(tile('Estimates completed').value).to.equal('0');
    expect(tile('Enquiries').value).to.equal('3');
    const text = el.shadowRoot!.textContent ?? '';
    expect(text).to.contain('No data yet').and.contain('33.3%');
    expect(tile('Site visits').hint).to.equal('No beacon received for this event');
  });

  it('pipeline: a stage claimed by a staff status is marked in words, the overdue follow-up too, and a withheld amount is never a figure', async () => {
    stub((path) => (path === '/api/v1/sales/pipeline' ? json({ data: [row()], meta: { page: 1, limit: 25, total: 1, scanned: 1, truncated: false,
      stage_counts: { QUOTATION_ISSUED: 1 } } }) : problem(404, 'NOT_FOUND')));
    const el = await mount('vs-sales-pipeline-page');
    await waitUntil(() => el.shadowRoot?.querySelector('tbody tr'), 'rows rendered');
    const tr = el.shadowRoot!.querySelector('tbody tr')!;
    const text = tr.textContent!.replace(/\s+/g, ' ');
    expect(text).to.contain('by status').and.contain('Status recorded by staff').and.contain('Quotation issued');
    expect(text).to.contain('Overdue').and.contain('Withheld').and.contain('Follow-up overdue').and.contain('Decision on the issued quotation');
    expect(tr.querySelector('a')!.getAttribute('href')).to.equal('/leads/l1');
    expect(el.shadowRoot!.querySelector('h1')!.textContent).to.equal('Sales pipeline');
    expect(el.shadowRoot!.activeElement).to.equal(el.shadowRoot!.querySelector('h1'));
  });

  it('pipeline: a filter is re-requested from the server, never applied here', async () => {
    const s = stub((path) => (path === '/api/v1/sales/pipeline' ? json({ data: [], meta: { page: 1, limit: 25, total: 0, scanned: 0, truncated: false, stage_counts: {} } })
      : problem(404, 'NOT_FOUND')));
    const el = await mount('vs-sales-pipeline-page');
    await waitUntil(() => el.shadowRoot?.querySelector('vs-empty-state'), 'loaded');
    const select = el.shadowRoot!.querySelector<HTMLSelectElement>('select[name=stage]')!;
    select.value = 'SITE_MEASUREMENT';
    select.dispatchEvent(new Event('change'));
    await waitUntil(() => s.calls.length === 2, 're-requested');
    expect(s.calls[1].query).to.contain('stage=SITE_MEASUREMENT').and.contain('status=open');
  });

  it('pipeline: says when the feature is off instead of showing an empty queue', async () => {
    stub(() => problem(404, 'NOT_FOUND'));
    const el = await mount('vs-sales-pipeline-page');
    await waitUntil(() => el.shadowRoot?.querySelector('vs-banner'), 'banner');
    expect(el.shadowRoot!.textContent).to.contain('The sales pipeline is not switched on here');
    expect(el.shadowRoot!.querySelector('vs-empty-state')).to.equal(null);
  });

  it('progression card: renders nothing when the feature is off (404) or the viewer may not see the pipeline (403)', async () => {
    for (const status of [404, 403]) {
      const s = stub(() => problem(status, status === 404 ? 'NOT_FOUND' : 'PERMISSION_DENIED'));
      const el = await mount('vs-sales-progression-card', SALES, { leadId: 'l1' });
      await waitUntil(() => s.calls.length === 1 && !el.shadowRoot?.querySelector('section'), 'asked the server and hid itself');
      expect(s.calls[0].path).to.equal('/api/v1/sales/leads/l1/progression');
      expect(el.shadowRoot!.querySelector('section') === null).to.equal(true);
      expect((el.shadowRoot!.textContent ?? '').trim()).to.equal('');
    }
  });

  it('progression card: shows the stage, the records and a way to the property', async () => {
    stub(() => json({ data: row({ facts: { ...row().facts, properties: ['p1'], visits: [{ id: 'v1', visit_number: 'VS-M-SYN-1', status: 'COMPLETED',
      scheduled_start_on: '2026-10-05T04:30:00Z', completed_on: '2026-10-05T06:30:00Z', property_id: 'p1' }] } }) }));
    const el = await mount('vs-sales-progression-card', SALES, { leadId: 'l1' });
    await waitUntil(() => el.shadowRoot?.querySelector('dl'), 'loaded');
    const text = el.shadowRoot!.textContent!.replace(/\s+/g, ' ');
    expect(text).to.contain('Sales progression').and.contain('VS-M-SYN-1').and.contain('by status');
    expect(el.shadowRoot!.querySelector('a.btn')!.getAttribute('href')).to.equal('/site/properties/p1');
  });

  it('demo: carries the DEMO banner at the top and the bottom, renders both customer views, and never calls a customer API', async () => {
    const s = stub((path) => (path === '/api/v1/sales/demo' ? json({ data: demo() }) : problem(404, 'NOT_FOUND')));
    const el = await mount('vs-sales-demo-page');
    await waitUntil(() => el.shadowRoot?.querySelector('vs-proposal-view'), 'proposal rendered');
    const banners = [...el.shadowRoot!.querySelectorAll('vs-banner')].map((b) => b.textContent?.trim());
    expect(banners).to.deep.equal(['DEMO: synthetic example, not a customer', 'DEMO: synthetic example, not a customer']);
    expect(el.shadowRoot!.querySelectorAll('h1').length).to.equal(1);
    const proposal = el.shadowRoot!.querySelector('vs-proposal-view') as HTMLElement & { preview: boolean; updateComplete: Promise<unknown> };
    await proposal.updateComplete;
    expect(proposal.preview).to.equal(true);
    expect(proposal.shadowRoot!.textContent).to.contain('DEMO: 3 BHK apartment interiors');
    const tabs = el.shadowRoot!.querySelector('vs-tabs')!;
    [...tabs.shadowRoot!.querySelectorAll('button')].find((b) => b.textContent?.includes('project portal'))!.click();
    await el.updateComplete;
    await waitUntil(() => el.shadowRoot?.querySelector('vs-sales-demo-portal'), 'portal rendered');
    const portal = el.shadowRoot!.querySelector('vs-sales-demo-portal') as HTMLElement & { updateComplete: Promise<unknown> };
    await portal.updateComplete;
    expect(portal.shadowRoot!.textContent).to.contain('DEMO: your home interiors project');
    expect(portal.shadowRoot!.querySelector('vs-portal-header')).to.equal(null);
    expect(s.calls.map((c) => c.path)).to.deep.equal(['/api/v1/sales/demo']);
    expect(s.calls.some((c) => c.path.startsWith('/api/v1/public'))).to.equal(false);
  });
});
