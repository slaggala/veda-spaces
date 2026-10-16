import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Me } from '../src/core/api/types.js';
import { sessionContext } from '../src/core/authz/context.js';
import { ROUTES } from '../src/core/router/routes.js';
import { keepSession, forgetSession, sessionToken } from '../src/modules/portal/api.js';
import '../src/modules/portal/index.js';
import { access, home, quotationPage, view } from './support/portal-sample.js';

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
