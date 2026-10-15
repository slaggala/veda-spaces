import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Me } from '../src/core/api/types.js';
import { sessionContext } from '../src/core/authz/context.js';
import '../src/modules/site/site-home-page.js';

/**
 * Site home: "Start" moves a scheduled visit to IN_PROGRESS and opens its measurement set; "Continue" on a visit already
 * in progress (started here earlier, or from the property page) opens the set without asking to start it again. Staging
 * found the second case refused (IN_PROGRESS -> IN_PROGRESS) with no other way into capture. SYNTHETIC data; API mocked.
 */

const json = (body: unknown, status = 200) => new Response(JSON.stringify({ data: body }), { status, headers: { 'Content-Type': 'application/json' } });
const visit = (status: string) => ({ id: 'v1', version: 3, visit_number: 'VS-M-SYN-1', property_id: 'p1', lead_id: 'l1', visit_type_code: 'MEASUREMENT',
  status, survey_level_code: 'FULL', scheduled_start_on: '2026-10-16T04:30:00Z', started_on: null, assigned_to: { id: 'u1', display_name: 'SYNTHETIC' },
  allowed_transitions: [], customer_contact_name: null, customer_contact_phone: null, access_notes: null });

async function mount(status: string) {
  const calls: { method: string; path: string }[] = [];
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), location.href).pathname;
    const method = init?.method ?? 'GET';
    calls.push({ method, path });
    if (path === '/api/v1/mtq/templates') return json({ property_templates: {}, space_templates: {} });
    if (path === '/api/v1/measurement-visits' && method === 'GET') return json([visit(status)]);
    if (path === '/api/v1/properties') return json([]);
    if (path.endsWith('/status')) {
      return status === 'IN_PROGRESS'
        ? new Response(JSON.stringify({ status: 409, code: 'INVALID_TRANSITION', title: 'Refused' }), { status: 409, headers: { 'Content-Type': 'application/problem+json' } })
        : json({ ...visit('IN_PROGRESS'), version: 4 });
    }
    if (path.endsWith('/measurement-sets') && method === 'POST') return json({ id: 's1' }, 201);
    return json({});
  };
  const went: string[] = [];
  window.addEventListener('vaadin-router-go', (e) => went.push((e as CustomEvent).detail.pathname));
  const host = await fixture<HTMLDivElement>(html`<div></div>`);
  new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated', me: { id: 'u1',
    permissions: { 'measurement.visit.read': 'ALL', 'measurement.capture': 'ALL' }, features: { mtq_site: true } } as unknown as Me } });
  const el = document.createElement('vs-site-home-page') as HTMLElement;
  host.append(el);
  await waitUntil(() => el.shadowRoot?.textContent?.includes('VS-M-SYN-1'), 'visits loaded');
  return { root: el.shadowRoot!, calls, went };
}

describe('vs-site-home-page visits', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  it('"Continue" opens the measurement set of a visit already in progress, without starting it again', async () => {
    const { root, calls, went } = await mount('IN_PROGRESS');
    const button = [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Continue')!;
    button.click();
    await waitUntil(() => went.length > 0, 'navigated to capture');
    expect(calls.some((c) => c.path.endsWith('/status'))).to.equal(false);
    expect(calls.filter((c) => c.method === 'POST' && c.path === '/api/v1/measurement-visits/v1/measurement-sets').length).to.equal(1);
    expect(went[0]).to.equal('/site/sets/s1/capture');
    expect(root.textContent).not.to.contain('cannot become');
  });

  it('"Start" moves a scheduled visit to in progress first, then opens its measurement set', async () => {
    const { root, calls, went } = await mount('SCHEDULED');
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Start')!.click();
    await waitUntil(() => went.length > 0, 'navigated to capture');
    const posts = calls.filter((c) => c.method === 'POST').map((c) => c.path);
    expect(posts).to.deep.equal(['/api/v1/measurement-visits/v1/status', '/api/v1/measurement-visits/v1/measurement-sets']);
  });
});
