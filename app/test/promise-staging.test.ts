import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Me } from '../src/core/api/types.js';
import { sessionContext } from '../src/core/authz/context.js';
import '../src/modules/promise/index.js';
import { landing, summary, version, vocabulary } from './support/promise-sample.js';

/**
 * Customer Promise defects found in protected staging (VEDA-SPACES-PROTECTED-STAGING-CUSTOMER-PROMISE-TO-PROPOSAL-
 * VALIDATION), under the staging Content-Security-Policy for styles (style-src without 'unsafe-inline'): the preview
 * width must still apply (a style attribute is refused there; CSSOM is not), and every table must render as a table
 * (header above body), not as a two-column grid. SYNTHETIC data; the API is mocked.
 */

const json = (body: unknown) => new Response(JSON.stringify({ data: body }), { status: 200, headers: { 'Content-Type': 'application/json' } });
const preview = { label: 'PREVIEW / NOT PUBLISHED', published: false, pack_id: 'p1', version_no: 1, status: 'DRAFT', content_version: 'CPP-1',
  creates: { quotation: false }, information: { content_version: 'CPP-1', contacts: { quotation: null, support: [], service: [] }, support_escalation: null,
    project_inclusions: null, client_responsibilities: null, site_readiness: null, site_dependent_work: null, manufacturer_warranty_note: null,
    warranty_exclusions: null, service_guidance: null, handover: null, care: null, next_steps: null, payment_safety: null } };

before(() => {
  const meta = document.createElement('meta');
  meta.httpEquiv = 'Content-Security-Policy';
  meta.content = "style-src 'self'";
  document.head.append(meta);
});

async function mount() {
  window.fetch = async (input: RequestInfo | URL) => {
    const path = new URL(String(input), location.href).pathname;
    if (path === '/api/v1/customer-promise') return json(landing({ open: summary() }));
    if (path === '/api/v1/customer-promise/vocabulary') return json(vocabulary);
    if (path === '/api/v1/customer-promise/versions') return json([]);
    if (path.endsWith('/preview')) return json(preview);
    return json(version());
  };
  const host = await fixture<HTMLDivElement>(html`<div style="width: 1280px"></div>`);
  new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated', me: { id: 'u1',
    permissions: { 'customer_promise.view': 'ALL', 'customer_promise.preview': 'ALL' }, features: { customer_promise_admin: true } } as unknown as Me } });
  const el = document.createElement('vs-promise-page') as HTMLElement & { updateComplete: Promise<unknown> };
  host.append(el);
  await waitUntil(() => el.shadowRoot?.textContent?.includes('Completeness of the customer information'), 'landing loaded');
  return { el, root: el.shadowRoot! };
}

describe('vs-promise-page under the staging style policy', () => {
  it('renders the completeness table as a table: header above the body, not beside it', async () => {
    const { root } = await mount();
    const table = root.querySelector('section[aria-labelledby=completeness] table') as HTMLTableElement;
    expect(getComputedStyle(table).display).to.equal('table');
    const head = table.tHead!.getBoundingClientRect();
    const body = table.tBodies[0].getBoundingClientRect();
    expect(body.top).to.be.at.least(head.bottom - 1);
    expect(Math.abs(body.left - head.left)).to.be.below(2);
  });

  it('applies the preview width (CSSOM, allowed by the policy)', async () => {
    const { el, root } = await mount();
    (root.querySelector('.version-cards button') as HTMLButtonElement).click();
    await waitUntil(() => root.querySelector('.tabs'), 'version opened');
    [...root.querySelectorAll<HTMLButtonElement>('.tabs button')].find((b) => b.textContent === 'Preview as customer')!.click();
    await waitUntil(() => root.querySelector('.frame'), 'preview');
    [...root.querySelectorAll<HTMLButtonElement>('.widths button')].find((b) => b.textContent?.startsWith('Mobile'))!.click();
    await el.updateComplete;
    const frame = root.querySelector('.frame') as HTMLElement;
    expect(frame.style.maxWidth).to.equal('360px');
    expect(frame.getBoundingClientRect().width).to.be.at.most(361);
  });
});
