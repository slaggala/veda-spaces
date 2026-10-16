import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Me } from '../src/core/api/types.js';
import { sessionContext } from '../src/core/authz/context.js';
import { filterNav, NAV_ITEMS } from '../src/core/authz/permissions.js';
import '../src/modules/project/index.js';
import type { Dashboard, ProjectDetail } from '../src/modules/project/api.js';
import { dashboard, project, row, transition, vocabulary } from './support/project-sample.js';

/** Project Lifecycle pages (PLB-10, PLB-11, PLB-40, PLB-41). The API is mocked with SYNTHETIC models; the server decides. */

type Call = { method: string; path: string; search: string; body: Record<string, unknown> | null; ifMatch: string | null; key: string | null };
const json = (body: unknown, status = 200) => new Response(JSON.stringify({ data: body }), { status, headers: { 'Content-Type': 'application/json' } });
const problem = (status: number, body: Record<string, unknown>) =>
  new Response(JSON.stringify({ status, title: 'Refused', ...body }), { status, headers: { 'Content-Type': 'application/problem+json' } });

interface Mock { dash?: Dashboard; detail?: ProjectDetail; post?: (path: string, body: Record<string, unknown> | null) => Response; get404?: boolean }

function serve(mock: Mock, calls: Call[]) {
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), location.href);
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    calls.push({ method, path: url.pathname, search: url.search, body, ifMatch: headers['If-Match'] ?? null, key: headers['Idempotency-Key'] ?? null });
    if (mock.get404) return problem(404, { code: 'NOT_FOUND' });
    if (method !== 'GET') return mock.post ? mock.post(url.pathname, body) : json(mock.detail ?? project());
    if (url.pathname === '/api/v1/projects') return json(mock.dash ?? dashboard());
    if (url.pathname === '/api/v1/projects/vocabulary') return json(vocabulary);
    if (url.pathname === '/api/v1/projects/p1/history') return json([]);
    if (url.pathname === '/api/v1/projects/p1/team/candidates') return json([{ id: 'u-ops', display_name: 'SYNTHETIC Ops', responsibilities: ['PROJECT', 'MEMBER'] }]);
    if (url.pathname.startsWith('/api/v1/projects/')) return json(mock.detail ?? project());
    return json({});
  };
}

async function mountWith(tag: string, mock: Mock = {}, perms: string[] = ['project.view'], features: Record<string, boolean> = { project_lifecycle: true }) {
  const calls: Call[] = [];
  serve(mock, calls);
  const host = await fixture<HTMLDivElement>(html`<div></div>`);
  new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated', me: { id: 'u-ops',
    permissions: Object.fromEntries(perms.map((p) => [p, 'ALL'])), features } as unknown as Me } });
  const el = document.createElement(tag) as HTMLElement & { updateComplete: Promise<unknown>; location?: unknown };
  if (tag === 'vs-project-page') el.location = { params: { id: 'p1' } };
  host.append(el);
  return { el, root: el.shadowRoot!, calls };
}

const text = (root: ShadowRoot) => root.textContent?.replace(/\s+/g, ' ') ?? '';
const button = (root: ParentNode, name: string | RegExp) =>
  [...root.querySelectorAll<HTMLButtonElement>('button')].find((b) => (typeof name === 'string' ? b.textContent?.trim() === name : name.test(b.textContent ?? '')))!;

describe('Projects dashboard (vs-project-list-page)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  it('answers the eight questions first and never ranks people', async () => {
    const { root } = await mountWith('vs-project-list-page');
    await waitUntil(() => root.querySelector('tbody tr'), 'rows');
    expect([...root.querySelectorAll('thead th')].map((t) => t.textContent)).to.deep.equal(['Project', 'Current stage', 'Owner', 'Next milestone',
      'Readiness', 'Blockers', 'Target date', 'Last material change']);
    const t = text(root);
    expect(t).to.contain('VS-P-2026-000001').and.to.contain('Stage 4 of 12').and.to.contain('2 to clear').and.to.contain('1 gating')
      .and.to.contain('past its planned date').and.to.contain('Lifecycle PLB-2026.10.1 is a proposal');
    expect(t.toLowerCase()).not.to.contain('rank').and.not.to.contain('score');
  });

  it('switches views and filters through the API', async () => {
    const { root, calls } = await mountWith('vs-project-list-page');
    await waitUntil(() => root.querySelector('tbody tr'), 'rows');
    button(root, /^Blocked/).click();
    await waitUntil(() => calls.some((c) => c.search.includes('view=blocked')), 'view requested');
    const form = root.querySelector('form[role=search]') as HTMLFormElement;
    (form.querySelector('select[name=readiness]') as HTMLSelectElement).value = 'awaiting_approval';
    form.requestSubmit();
    await waitUntil(() => calls.some((c) => c.search.includes('readiness=awaiting_approval') && c.search.includes('view=blocked')), 'filter requested');
  });

  it('offers booking only for an accepted quotation with nothing missing', async () => {
    const dash = dashboard({ projects: [], bookable: [
      { quotation_id: 'q1', quotation_number: 'VS-Q-2026-000001', label: 'VS-Q-2026-000001 v1', property_id: 'prop-1', decided_on: '2026-10-15T09:00:00Z', problems: [] },
      { quotation_id: 'q2', quotation_number: 'VS-Q-2026-000002', label: 'VS-Q-2026-000002 v1', property_id: 'prop-2', decided_on: null,
        problems: [{ code: 'ACCEPTANCE_EVIDENCE_MISSING', message: 'The acceptance was not recorded for this frozen baseline.' }] }] });
    const { root, calls } = await mountWith('vs-project-list-page', { dash, post: () => json(project()) }, ['project.view', 'project.create_from_acceptance']);
    await waitUntil(() => root.querySelector('#bookable-h'), 'queue');
    expect(text(root)).to.contain('The acceptance was not recorded for this frozen baseline.');
    expect([...root.querySelectorAll('button')].filter((b) => b.textContent?.startsWith('Book'))).to.have.length(1);
    button(root, 'Book VS-Q-2026-000001 as a project').click();
    await waitUntil(() => calls.some((c) => c.method === 'POST'), 'booked');
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.body).to.deep.equal({ quotation_id: 'q1', property_id: 'prop-1' });
    expect(post.key).to.be.a('string').and.not.be.empty; // a new row needs an Idempotency-Key
  });

  it('says so when the feature is off', async () => {
    const { root } = await mountWith('vs-project-list-page', { get404: true });
    await waitUntil(() => root.querySelector('vs-empty-state')?.getAttribute('heading')?.includes('not enabled'), 'disabled');
  });

  it('shows Projects in the navigation only with the feature on and the capability held', () => {
    const perms = { 'project.view': 'OWN' } as const;
    expect(filterNav(NAV_ITEMS, perms, { project_lifecycle: true }).some((i) => i.path === '/projects')).to.equal(true);
    expect(filterNav(NAV_ITEMS, perms, { project_lifecycle: false }).some((i) => i.path === '/projects')).to.equal(false);
    expect(filterNav(NAV_ITEMS, {}, { project_lifecycle: true }).some((i) => i.path === '/projects')).to.equal(false);
  });
});

describe('Project page (vs-project-page)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  async function ready(mock: Mock = {}) {
    const m = await mountWith('vs-project-page', mock);
    await waitUntil(() => m.root.querySelector('dl.hero'), 'project loaded');
    return m;
  }

  it('puts the situation first: the hero and why it is blocked, who acts, what it blocks and what comes next', async () => {
    const { root } = await ready();
    const hero = [...root.querySelectorAll('dl.hero dt')].map((d) => d.textContent);
    expect(hero).to.deep.equal(['Project reference', 'Property', 'Current stage', 'Operational owner', 'Next milestone', 'Readiness', 'Blocking issues']);
    const item = root.querySelector('.attention li.GATING')!;
    expect(item.textContent).to.contain('Blocked').and.to.contain('Appliance specifications required');
    const pairs = Object.fromEntries([...item.querySelectorAll('dt')].map((d) => [d.textContent, d.nextElementSibling?.textContent]));
    expect(pairs).to.deep.equal({ 'Who needs to act': 'Customer', 'What is needed': 'Share the hob and chimney models',
      'What it blocks': 'Production readiness', 'When resolved': 'The move to Production readiness can be requested.' });
  });

  it('has the eleven sections, reachable as tabs', async () => {
    const { root } = await ready();
    const tabs = root.querySelector('vs-tabs')!.shadowRoot!.querySelectorAll('[role=tab]');
    expect([...tabs].map((t) => t.textContent)).to.deep.equal(['Overview', 'Timeline', 'Stage and readiness', 'Checklist', 'Blockers', 'Milestones',
      'Commercial baseline', 'Site readiness', 'Quality and snags', 'Handover', 'Audit and history']);
  });

  it('requests a move with the version shown and keeps a refusal visible with its exact blockers', async () => {
    const refused = { transition: transition(), outcome: 'REFUSED', project: project() };
    const { el, root, calls } = await ready({ post: () => json(refused, 201) });
    button(root, 'Request the move to Production readiness').click();
    await el.updateComplete;
    (root.querySelector('vs-dialog button[type=submit]') as HTMLButtonElement).click();
    await waitUntil(() => root.querySelector('#refusal-h'), 'refusal shown');
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.path).to.equal('/api/v1/projects/p1/transitions');
    expect(post.body).to.deep.equal({ to_stage: 'PRODUCTION_READINESS' });
    expect(post.ifMatch).to.equal('"7"');
    const refusal = root.querySelector('section[aria-labelledby=refusal-h]')!.textContent!;
    expect(refusal).to.contain('stops production readiness').and.to.contain('flooring is customer action required');
    await waitUntil(() => root.activeElement?.id === 'refusal-h' || (root as unknown as Document).activeElement?.id === 'refusal-h', 'focus on the refusal');
  });

  it('validates a required reason in the dialog with an error summary and aria-invalid, before any request', async () => {
    const { el, root, calls } = await ready();
    (root.querySelector('vs-tabs') as HTMLElement).dispatchEvent(new CustomEvent('tab-change', { detail: 'blockers' }));
    await el.updateComplete;
    button(root, 'Resolve').click();
    await el.updateComplete;
    (root.querySelector('vs-dialog button[type=submit]') as HTMLButtonElement).click();
    await waitUntil(() => root.querySelector('vs-dialog textarea[aria-invalid=true]'), 'invalid field marked');
    const summary = root.querySelector('vs-dialog vs-error-summary') as HTMLElement & { errors: unknown[] };
    expect(summary.errors).to.have.length(1);
    expect(calls.filter((c) => c.method === 'POST')).to.have.length(0);
  });

  it('shows a conflict instead of overwriting', async () => {
    const { el, root } = await ready({ post: () => problem(409, { code: 'VERSION_CONFLICT', current_version: 8 }) });
    button(root, 'Request the move to Production readiness').click();
    await el.updateComplete;
    (root.querySelector('vs-dialog button[type=submit]') as HTMLButtonElement).click();
    await waitUntil(() => root.querySelector('#conflict'), 'conflict banner');
    expect(text(root)).to.contain('Nothing was overwritten');
  });

  it('maps server field errors back onto their fields', async () => {
    const { el, root } = await ready({ post: () => problem(422, { code: 'VALIDATION_FAILED',
      errors: [{ field: 'customer_action', code: 'REQUIRED', message: 'Required when the customer acts.' }] }) });
    (root.querySelector('vs-tabs') as HTMLElement).dispatchEvent(new CustomEvent('tab-change', { detail: 'blockers' }));
    await el.updateComplete;
    button(root, 'Raise a blocker').click();
    await el.updateComplete;
    const form = root.querySelector('#project-form') as HTMLFormElement;
    (form.querySelector('[name=impact]') as HTMLSelectElement).value = 'INFORMATIONAL';
    (form.querySelector('[name=title]') as HTMLInputElement).value = 'A synthetic note';
    (form.querySelector('[name=category]') as HTMLSelectElement).value = 'OTHER';
    (form.querySelector('[name=responsible_party]') as HTMLSelectElement).value = 'CUSTOMER';
    (root.querySelector('vs-dialog button[type=submit]') as HTMLButtonElement).click();
    await waitUntil(() => root.querySelector('#err-customer_action[aria-invalid=true]'), 'server error on the field');
    expect(root.querySelector('#err-customer_action-msg')!.textContent).to.contain('Required when the customer acts.');
  });

  it('hides commercial amounts without the baseline capability and labels customer-safe wording', async () => {
    const limited = project();
    limited.baseline = { ...limited.baseline, full: false, lineage: limited.baseline.lineage.map(({ accepted_total_minor: _a, cumulative_value_minor: _c, baseline_sha256: _b, ...r }) => r) };
    const { el, root } = await ready({ detail: limited });
    (root.querySelector('vs-tabs') as HTMLElement).dispatchEvent(new CustomEvent('tab-change', { detail: 'baseline' }));
    await el.updateComplete;
    expect(text(root)).to.contain('Original accepted baseline').and.not.to.contain('Accepted value');
    (root.querySelector('vs-tabs') as HTMLElement).dispatchEvent(new CustomEvent('tab-change', { detail: 'blockers' }));
    await el.updateComplete;
    expect(text(root)).to.contain('Customer-safe wording').and.to.contain('Internal only');
  });

  it('offers the approval only to someone other than the requester, and withdrawal to the requester', async () => {
    const waiting = transition({ outcome: 'AWAITING_APPROVAL', independent_approval: true });
    const p = project({ awaiting_approval: waiting });
    p.actions = { ...p.actions, approve_transition: false };
    const { root } = await ready({ detail: p });
    expect(button(root, 'Withdraw the request')).to.exist;
    expect([...root.querySelectorAll('button')].some((b) => b.textContent?.startsWith('Approve'))).to.equal(false);
  });
});

describe('Project page: final safety closure (M1, M2, S1)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  async function openTab(mock: Mock, tab: string) {
    const m = await mountWith('vs-project-page', mock);
    await waitUntil(() => m.root.querySelector('dl.hero'), 'project loaded');
    (m.root.querySelector('vs-tabs') as HTMLElement).dispatchEvent(new CustomEvent('tab-change', { detail: tab }));
    await m.el.updateComplete;
    return m;
  }

  it('offers a customer-promised date only when owner decision PLB-OD-13 lets this person record one', async () => {
    const { el, root } = await openTab({}, 'milestones');
    button(root, 'Add a milestone').click();
    await el.updateComplete;
    expect(root.querySelector('#project-form [name=customer_promised_date]')).to.equal(null);
    expect(root.querySelector('#project-form')!.textContent).to.contain('needs owner decision PLB-OD-13');
    const allowed = project();
    allowed.actions = { ...allowed.actions, record_promised_date: true };
    const second = await openTab({ detail: allowed }, 'milestones');
    button(second.root, 'Add a milestone').click();
    await second.el.updateComplete;
    expect(second.root.querySelector('#project-form [name=customer_promised_date]')).to.exist;
  });

  it('changes a snag\'s blocking only through its own reasoned command, when PLB-OD-06 allows', async () => {
    const snag = { id: 'n1', version: 3, snag_no: 1, category: 'FINISH', customer_title: 'Synthetic snag', description: null, space: null, space_id: null,
      item_reference: null, is_blocking: true, classification_reason: null, owner: null, responsible_party: 'VEDA', status: 'OPEN',
      allowed_next: ['IN_PROGRESS', 'CLOSED'], target_date: null, evidence: null, resolution_note: null, resolved_on: null, resolved_by: null,
      closed_on: null, closed_by: null, qc_check_id: null, raised_on: null, raised_by: null, work_package_id: null, source: 'STAFF' as const,
      priority: 'NORMAL' as const, customer_visible: false, fixed_by: null, fixed_on: null, fix_note: null, closure_code: null };
    const plain = project({ snags: [snag] });
    const first = await openTab({ detail: plain }, 'quality');
    expect([...first.root.querySelectorAll('button')].some((b) => b.textContent?.includes('Change blocking'))).to.equal(false);
    const allowed = project({ snags: [snag] });
    allowed.actions = { ...allowed.actions, reclassify_snag: true };
    const { el, root, calls } = await openTab({ detail: allowed }, 'quality');
    button(root, 'Change blocking').click();
    await el.updateComplete;
    (root.querySelector('vs-dialog button[type=submit]') as HTMLButtonElement).click();
    await waitUntil(() => root.querySelector('vs-dialog textarea[aria-invalid=true]'), 'reason required');
    expect(calls.filter((c) => c.method === 'POST')).to.have.length(0);
    (root.querySelector('#project-form textarea[name=reason]') as HTMLTextAreaElement).value = 'Cosmetic only; agreed on site';
    (root.querySelector('vs-dialog button[type=submit]') as HTMLButtonElement).click();
    await waitUntil(() => calls.some((c) => c.method === 'POST'), 'sent');
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.path).to.equal('/api/v1/projects/p1/snags/n1/classification');
    expect(post.body).to.deep.equal({ is_blocking: false, reason: 'Cosmetic only; agreed on site' });
    expect(post.ifMatch).to.equal('"3"');
  });

  it('shows an owner who can no longer act as needing reassignment, keeping the assignment', async () => {
    const p = project({ needs_reassignment: ['DESIGN'] });
    p.team = p.team.map((m) => (m.responsibility === 'DESIGN' ? { ...m, eligible: false } : m));
    const { root } = await openTab({ detail: p }, 'overview');
    expect(text(root)).to.contain('Needs reassignment: Design').and.to.contain('SYNTHETIC Designer');
  });
});

void row;
