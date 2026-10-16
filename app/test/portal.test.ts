import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Me } from '../src/core/api/types.js';
import { sessionContext } from '../src/core/authz/context.js';
import { ROUTES } from '../src/core/router/routes.js';
import { keepSession, forgetSession, sessionToken } from '../src/modules/portal/api.js';
import '../src/modules/portal/index.js';
import { access, deliveryProject, home, quotationPage, view } from './support/portal-sample.js';

/** Customer Project Portal pages (CPP). The API is mocked with SYNTHETIC models; the server decides everything. */

type Call = { method: string; path: string; body: Record<string, unknown> | null; headers: Record<string, string> };
const json = (body: unknown, status = 200) => new Response(JSON.stringify({ data: body }), { status, headers: { 'Content-Type': 'application/json' } });
const problem = (status: number, code: string) =>
  new Response(JSON.stringify({ status, title: 'Refused', code, detail: 'Refused.' }), { status, headers: { 'Content-Type': 'application/problem+json' } });

function serve(routes: Record<string, (body: Record<string, unknown> | null) => Response>, calls: Call[]) {
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), location.href);
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    calls.push({ method, path: url.pathname, body, headers: (init?.headers ?? {}) as Record<string, string> });
    const handler = routes[`${method} ${url.pathname}`];
    return handler ? handler(body) : problem(404, 'NOT_FOUND');
  };
}

async function mount(tag: string, id?: string) {
  const el = document.createElement(tag) as HTMLElement & { location?: unknown };
  if (id) el.location = { params: { id } };
  const host = await fixture<HTMLDivElement>(html`<div></div>`);
  host.append(el);
  return { el, root: el.shadowRoot! };
}

const text = (root: ShadowRoot) => root.textContent?.replace(/\s+/g, ' ') ?? '';
const button = (root: ParentNode, name: string) => [...root.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent?.trim() === name);
const P = '/api/v1/public/portal';

describe('Customer Project Portal', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; forgetSession(); history.replaceState(null, '', '/'); });

  it('registers public routes outside the workspace chrome', () => {
    for (const path of ['/portal', '/portal/sign-in', '/portal/properties/:id', '/portal/quotations/:id']) {
      const r = ROUTES.find((x) => x.path === path)!;
      expect(r.access).to.equal('public');
      expect(r.chrome).to.not.equal(true);
      expect(r.fullTitle).to.contain('Veda Spaces');
    }
  });

  it('signed out: asks for an email, validates it accessibly, and never says whether it has access', async () => {
    const calls: Call[] = [];
    serve({ [`POST ${P}/sign-in`]: () => json({ sent: true, message: 'If this email has access, a sign-in link is on its way.' }, 202) }, calls);
    const { root } = await mount('vs-portal-home-page');
    await waitUntil(() => root.querySelector('vs-portal-sign-in')?.shadowRoot?.querySelector('form'), 'form');
    const inner = root.querySelector('vs-portal-sign-in')!.shadowRoot!;
    const form = inner.querySelector('form')!;
    (inner.querySelector('#email') as HTMLInputElement).value = 'not-an-email';
    form.requestSubmit();
    await waitUntil(() => inner.querySelector('#email-error'), 'error');
    expect(inner.querySelector('#email')!.getAttribute('aria-invalid')).to.equal('true');
    expect(inner.querySelector('#email')!.getAttribute('aria-describedby')).to.equal('email-error');
    expect(calls).to.have.length(0);
    (inner.querySelector('#email') as HTMLInputElement).value = 'someone@example.test';
    form.requestSubmit();
    await waitUntil(() => inner.querySelector('#sent'), 'sent');
    expect(calls[0].body).to.deep.equal({ email: 'someone@example.test' });
    expect(calls[0].headers.Authorization).to.equal(undefined);
    expect(text(inner)).to.contain('If this email has access');
  });

  it('the emailed link signs in once, scrubs the token from the address bar and keeps the session in this tab', async () => {
    const calls: Call[] = [];
    serve({ [`POST ${P}/session`]: () => json({ token: 'vpp_SESSION', expires_on: '2026-10-16T17:00:00Z' }, 201) }, calls);
    history.replaceState(null, '', '/portal/sign-in#t=LINKTOKEN');
    await mount('vs-portal-sign-in-page');
    await waitUntil(() => sessionToken() === 'vpp_SESSION', 'session kept');
    expect(calls[0].body).to.deep.equal({ token: 'LINKTOKEN' });
    expect(window.location.hash).to.equal('');
  });

  it('a spent link offers a new one, in words', async () => {
    serve({ [`POST ${P}/session`]: () => problem(400, 'PORTAL_LINK_INVALID') }, []);
    history.replaceState(null, '', '/portal/sign-in#t=SPENT');
    const { root } = await mount('vs-portal-sign-in-page');
    await waitUntil(() => root.querySelector('vs-portal-sign-in')?.shadowRoot?.querySelector('form'), 'form');
    const inner = root.querySelector('vs-portal-sign-in')!.shadowRoot!;
    await waitUntil(() => text(inner).includes('expired or was already used'), 'notice');
    expect(sessionToken()).to.equal(null);
  });

  it('home: the most useful things first, sent only with the portal header', async () => {
    keepSession('vpp_SESSION');
    const calls: Call[] = [];
    serve({ [`GET ${P}/home`]: () => json(home()) }, calls);
    const { root } = await mount('vs-portal-home-page');
    await waitUntil(() => root.querySelector('article'), 'card');
    const t = text(root);
    expect(t).to.contain('Hello, SYNTHETIC Customer');
    expect(t).to.contain('We are waiting for your decision.');
    expect(t).to.contain('1 thing needs you');
    expect(t).to.contain('Awaiting your decision');
    expect(root.querySelector('a.btn.primary')!.getAttribute('href')).to.equal('/portal/properties/p1');
    expect(calls[0].headers['X-Veda-Portal']).to.equal('vpp_SESSION');
    expect(calls[0].headers.Authorization).to.equal(undefined);
  });

  it('an ended session returns to sign-in and forgets the token', async () => {
    keepSession('vpp_OLD');
    serve({ [`GET ${P}/home`]: () => problem(401, 'PORTAL_SESSION_INVALID') }, []);
    const { root } = await mount('vs-portal-home-page');
    await waitUntil(() => root.querySelector('vs-portal-sign-in'), 'sign-in');
    expect(sessionToken()).to.equal(null);
  });

  it('project: status, what needs the customer, an honest journey, commitments and contact', async () => {
    keepSession('vpp_SESSION');
    serve({ [`GET ${P}/properties/p1`]: () => json(view()) }, []);
    const { root } = await mount('vs-portal-project-page', 'p1');
    await waitUntil(() => root.querySelector('ol.journey'), 'journey');
    const t = text(root);
    expect(t).to.contain('Review your quotation and tell us your decision');
    expect(root.querySelector('a[href="/portal/quotations/q1"]')).to.exist;
    const steps = [...root.querySelectorAll('ol.journey li')].map((li) => li.textContent!.replace(/\s+/g, ' '));
    expect(steps).to.have.length(8);
    expect(steps[4]).to.contain('Action required');
    expect(steps[5]).to.contain('Not yet available');
    expect(t).to.contain('Pay only to the Veda Spaces account.');
    expect(t).to.contain('Society permission for work hours');
    expect(root.querySelector('a[href="tel:+910000000000"]')).to.exist;
    expect(root.querySelector('h1')!.textContent).to.contain('3 BHK apartment');
    for (const id of ['attention', 'journey', 'quotation', 'included', 'commitments', 'your-part', 'documents', 'contact']) {
      expect(root.querySelector(`nav.jump a[href="#${id}"]`), id).to.exist;
      expect(root.getElementById(`h-${id}`), id).to.exist;
    }
  });

  it('project: nothing is invented before a quotation exists', async () => {
    keepSession('vpp_SESSION');
    serve({ [`GET ${P}/properties/p1`]: () => json(view({ quotation: null, quotations: [], documents: [], included: null, commitments: null,
      responsibilities: null, attention: [], contact: null })) }, []);
    const { root } = await mount('vs-portal-project-page', 'p1');
    await waitUntil(() => root.querySelector('ol.journey'), 'journey');
    const t = text(root);
    expect(t).to.contain('Nothing needs you right now.');
    expect(t).to.contain('Your quotation will appear here once Veda Spaces issues it.');
    expect(t).to.contain('Contact details are not available in your portal yet.');
    expect(t).to.not.contain('₹');
  });

  it('project: another customer\'s or a missing project answers "not found" without detail', async () => {
    keepSession('vpp_SESSION');
    serve({}, []);
    const { root } = await mount('vs-portal-project-page', 'someone-elses');
    await waitUntil(() => text(root).includes('We could not find this project'), 'not found');
  });

  it('quotation: the CQX customer view, read-only (no action, no staff mark)', async () => {
    keepSession('vpp_SESSION');
    serve({ [`GET ${P}/quotations/q1`]: () => json(quotationPage()) }, []);
    const { root } = await mount('vs-portal-quotation-page', 'q1');
    await waitUntil(() => root.querySelector('vs-proposal-view'), 'view');
    const view = root.querySelector('vs-proposal-view')!;
    await (view as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    const inner = view.shadowRoot!;
    expect(view.hasAttribute('portal')).to.equal(true);
    expect(inner.textContent).to.not.contain('Staff preview');
    expect([...inner.querySelectorAll('button')].map((b) => b.textContent?.trim()).filter((t) => /accept|decline|select|ask/i.test(t ?? ''))).to.deep.equal([]);
    expect(inner.textContent).to.contain('secure proposal link');
  });
});

describe('Lead page: customer portal access (staff)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  async function mountCard(perms: string[], features: Record<string, boolean>) {
    const host = await fixture<HTMLDivElement>(html`<div></div>`);
    new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated', me: { id: 'u1',
      permissions: Object.fromEntries(perms.map((p) => [p, 'ALL'])), features } as unknown as Me } });
    const el = document.createElement('vs-portal-access-card') as HTMLElement & { leadId: string; updateComplete: Promise<unknown> };
    el.leadId = 'l1';
    host.append(el);
    await el.updateComplete;
    return { el, root: el.shadowRoot! };
  }

  it('is absent while the portal is off or without the capability', async () => {
    const calls: Call[] = [];
    serve({}, calls);
    for (const [perms, features] of [[['portal.access.view'], { customer_portal: false }], [[], { customer_portal: true }]] as const) {
      const { root } = await mountCard([...perms], { ...features });
      expect(root.querySelector('section')).to.equal(null);
    }
    expect(calls).to.have.length(0);
  });

  it('invites with an idempotency key and ends access with the version the user saw', async () => {
    const calls: Call[] = [];
    serve({
      'GET /api/v1/leads/l1/portal-access': () => json([access()]),
      'POST /api/v1/leads/l1/portal-access': () => json([access(), access({ id: 'a2', account: { ...access().account, display_name: 'Second' } })], 201),
      'POST /api/v1/portal-access/a1/revoke': () => json([access({ status: 'REVOKED' })]),
    }, calls);
    const { root, el } = await mountCard(['portal.access.view', 'portal.access.grant', 'portal.access.revoke'], { customer_portal: true });
    await waitUntil(() => text(root).includes('SYNTHETIC Customer'), 'row');
    [...root.querySelectorAll('button')].find((b) => b.textContent?.includes('Invite a customer'))!.click();
    await el.updateComplete;
    (root.querySelector('input[name="email"]') as HTMLInputElement).value = 'second@example.test';
    root.querySelector('form')!.requestSubmit();
    await waitUntil(() => calls.some((c) => c.method === 'POST' && c.path.endsWith('/portal-access')), 'grant');
    const grant = calls.find((c) => c.method === 'POST' && c.path.endsWith('/portal-access'))!;
    expect(grant.body).to.deep.equal({ email: 'second@example.test', relationship: 'PRIMARY_CUSTOMER' });
    expect(grant.headers['Idempotency-Key']).to.be.a('string').and.have.length.greaterThan(15);
    await waitUntil(() => text(root).includes('Second'), 'second row');
    [...root.querySelectorAll('button')].find((b) => b.textContent?.includes('End access'))!.click();
    await el.updateComplete;
    const dialog = root.querySelector('vs-dialog')!;
    [...dialog.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'End access')!.click();
    await waitUntil(() => calls.some((c) => c.path.endsWith('/revoke')), 'revoke');
    expect(calls.find((c) => c.path.endsWith('/revoke'))!.headers['If-Match']).to.equal('"1"');
  });
});

describe('Customer Project Portal: work on your home (PEX)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; forgetSession(); });

  it('says honestly what is done, in progress, on hold and next, with no percentage', async () => {
    keepSession('vpp_SESSION');
    serve({ [`GET ${P}/properties/p1`]: () => json(view({ delivery: { available: true, projects: [deliveryProject()] } })) }, []);
    const { root } = await mount('vs-portal-project-page', 'p1');
    await waitUntil(() => root.getElementById('h-delivery'), 'delivery');
    const t = text(root);
    expect(t).to.contain('Now: Installing your interiors').and.to.contain('No date has been agreed with you for the next step yet');
    expect(t).to.contain('We are waiting for a material delivery').and.to.contain('Veda Spaces is working on this');
    expect(t).to.contain('3 quality checks passed, 1 being corrected').and.to.contain('Snag 1: Touch-up on the skirting');
    expect(t).to.contain('Not ready for handover yet').and.to.contain('Work still to finish (3)');
    expect(root.getElementById('delivery')!.textContent).not.to.match(/\d+ ?%/);  // progress is never a percentage
    const states = [...root.querySelectorAll('#delivery li.item .badge')].map((b) => b.textContent?.trim());
    expect(states.slice(0, 4)).to.deep.equal(['Action required', 'On hold', 'Upcoming', 'Completed']);  // what needs the customer first
    expect(root.querySelector('nav.jump a[href="#delivery"]')).to.exist;
    expect(button(root, 'Report something')).to.equal(undefined);  // PEX-D01 not recorded: no form
    expect(t).to.contain('please speak to your Veda Spaces contact');
  });

  it('sends a report once, with one key reused on a retry, and shows the reference', async () => {
    keepSession('vpp_SESSION');
    const calls: Call[] = [];
    let attempts = 0;
    const after = deliveryProject({ can_report: true, reports: [{ number: 1, description: 'The drawer does not close fully', area: 'Kitchen',
      status: 'Received, being reviewed', outcome: null, response: null, snag_number: null }] });
    serve({
      [`GET ${P}/properties/p1`]: () => json(view({ delivery: { available: true, projects: [deliveryProject({ can_report: true })] } })),
      [`POST ${P}/properties/p1/projects/pj1/reports`]: () => (++attempts === 1 ? new Response('', { status: 503 })
        : json({ reference: 'Report 1', received: true, delivery: after }, 201)),
    }, calls);
    const { el, root } = await mount('vs-portal-project-page', 'p1');
    await waitUntil(() => button(root, 'Report something'), 'form offered');
    button(root, 'Report something')!.click();
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    button(root, 'Send report')!.click();
    await waitUntil(() => root.querySelector('[role=alert]'), 'too short');
    expect(calls.filter((c) => c.method === 'POST')).to.have.length(0);
    (root.querySelector('textarea[name=description]') as HTMLTextAreaElement).value = 'The drawer does not close fully';
    button(root, 'Send report')!.click();
    await waitUntil(() => text(root).includes('it will not be sent twice'), 'retry offered');
    button(root, 'Send report')!.click();
    await waitUntil(() => text(root).includes('Received, being reviewed'), 'sent');
    const posts = calls.filter((c) => c.method === 'POST');
    expect(posts).to.have.length(2);
    expect(posts[0].headers['Idempotency-Key']).to.equal(posts[1].headers['Idempotency-Key']);
    expect(posts[1].headers['X-Veda-Portal']).to.equal('vpp_SESSION');
    expect(posts[1].body).to.deep.equal({ description: 'The drawer does not close fully' });
    expect(text(root)).to.contain('Report 1 has been received');
  });

  it('confirms the handover summary by its digest and then shows it as received', async () => {
    keepSession('vpp_SESSION');
    const calls: Call[] = [];
    const pkg = { id: 'hp1', number: 1, content_sha256: 'c'.repeat(64), status: 'READY_TO_REVIEW' as const,
      work_completed: [{ label: 'Kitchen cabinets', finished_on: '2026-10-14' }], quality: { checks_passed: 4, corrected_after_failure: 1 },
      snags: { fixed_and_verified: 2, open_minor: [] }, documents: [], documents_note: 'Handover documents are not shown in your portal yet.',
      warranty_note: 'Warranty is as set out in your accepted quotation.', acknowledged_on: null, can_acknowledge: true };
    const ready = deliveryProject({ handover: { state: 'IN_PROGRESS', label: 'Ready for handover', date: null, remaining: [] }, package: pkg });
    serve({
      [`GET ${P}/properties/p1`]: () => json(view({ delivery: { available: true, projects: [ready] } })),
      [`POST ${P}/properties/p1/projects/pj1/handover/acknowledge`]: () => json({ acknowledged_on: '2026-10-16T10:00:00Z',
        delivery: { ...ready, package: { ...pkg, acknowledged_on: '2026-10-16T10:00:00Z', can_acknowledge: false } } }),
    }, calls);
    const { root } = await mount('vs-portal-project-page', 'p1');
    await waitUntil(() => button(root, 'I have received this summary'), 'acknowledge offered');
    expect(text(root)).to.contain('Warranty is as set out in your accepted quotation.').and.to.contain('Kitchen cabinets');
    button(root, 'I have received this summary')!.click();
    await waitUntil(() => text(root).includes('You confirmed receiving this summary'), 'received');
    expect(calls.find((c) => c.method === 'POST')!.body).to.deep.equal({ package_id: 'hp1', content_sha256: 'c'.repeat(64) });
    expect(button(root, 'I have received this summary')).to.equal(undefined);
  });
});
