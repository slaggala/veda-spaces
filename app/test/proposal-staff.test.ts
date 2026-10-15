import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Me } from '../src/core/api/types.js';
import { sessionContext } from '../src/core/authz/context.js';
import '../src/modules/proposal/staff-panel.js';
import { samplePage } from './support/proposal-sample.js';

/** CTB staff side: choose the version's contact and statuses from the approved pack; see the customer trust checklist. */

const pack = {
  content_version: 'SYN-C1',
  contacts: [{ code: 'SYN_DESK', kind: 'QUOTATION', display_name: 'SYNTHETIC Desk', role: 'Consultant' },
    { code: 'SYN_SUP', kind: 'SUPPORT', display_name: 'SYNTHETIC Support', role: 'Care' }],
  client_responsibilities: [{ code: 'A1', category: 'APPLIANCE_MODEL', text: 'SYNTHETIC appliance models.', default_status: 'REQUIRED' }],
  site_readiness: [{ code: 'F1', category: 'FLOORING', text: 'SYNTHETIC flooring.' }],
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify({ data: body }), { status, headers: { 'Content-Type': 'application/json' } });

async function mount(status: string, withPack = true) {
  const calls: { method: string; path: string; body: unknown; ifMatch: string | null }[] = [];
  const quotation = { id: 'q1', version: 3, status, terms: { customer_pack: withPack ? pack : null }, customer_inputs: null };
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), location.href).pathname;
    const headers = (init?.headers ?? {}) as Record<string, string>;
    calls.push({ method: init?.method ?? 'GET', path, body: init?.body ? JSON.parse(String(init.body)) : null, ifMatch: headers['If-Match'] ?? null });
    if (path.endsWith('/proposal-preview')) {
      return json({ frozen: false, status, proposal: samplePage().proposal, trust_checklist: { customer_ready: false, items: [
        { code: 'CONTACT', question: 'Who do I contact?', status: 'TO_BE_CONFIRMED', missing: 'no approved Veda Spaces contact chosen' },
        { code: 'BUYING', question: 'What am I buying?', status: 'ANSWERED', missing: null }] } });
    }
    if (path === '/api/v1/quotations/q1') return json(quotation);
    return json([]);
  };
  const host = await fixture<HTMLDivElement>(html`<div></div>`);
  new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated', me: { id: 'u1',
    permissions: Object.fromEntries(['quotation.read', 'quotation.create', 'proposal.preview'].map((p) => [p, 'ALL'])), features: {} } as unknown as Me } });
  const el = document.createElement('vs-proposal-staff') as HTMLElement & { quotationId: string; quotationStatus: string };
  el.quotationStatus = status;
  host.append(el);
  el.quotationId = 'q1';
  await waitUntil(() => el.shadowRoot?.textContent?.includes('Customer trust checklist'), 'loaded');
  return { el, calls };
}

describe('vs-proposal-staff customer information (CTB)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  it('lets staff choose the contact and statuses of a draft from the approved pack only, and saves them with If-Match', async () => {
    const { el, calls } = await mount('DRAFT');
    const root = el.shadowRoot!;
    const contact = root.querySelector('select[name=contact]') as HTMLSelectElement;
    expect([...contact.options].map((o) => o.value)).to.deep.equal(['', 'SYN_DESK']); // a SUPPORT contact is not a quotation contact
    expect((root.querySelector('select[name="resp:A1"]') as HTMLSelectElement).value).to.equal('REQUIRED'); // the pack's default
    contact.value = 'SYN_DESK';
    (root.querySelector('select[name="ready:F1"]') as HTMLSelectElement).value = 'CUSTOMER_ACTION_REQUIRED';
    (root.querySelector('form button.primary') as HTMLButtonElement).click();
    await waitUntil(() => calls.some((c) => c.method === 'PATCH'));
    const sent = calls.find((c) => c.method === 'PATCH')!;
    expect(sent.path).to.equal('/api/v1/quotations/q1');
    expect(sent.ifMatch).to.equal('"3"');
    expect(sent.body).to.deep.equal({ customer_information: { contact_code: 'SYN_DESK', responsibilities: { A1: 'REQUIRED' },
      readiness: { F1: 'CUSTOMER_ACTION_REQUIRED' } } });
    expect(root.textContent).to.contain('Who do I contact?').and.to.contain('no approved Veda Spaces contact chosen');
    await expect(el).to.be.accessible({ ignoredRules: ['region'] });
  });

  it('shows an issued version read-only, and says when no pack is recorded', async () => {
    const issued = await mount('ISSUED');
    expect((issued.el.shadowRoot!.querySelector('select[name=contact]') as HTMLSelectElement).disabled).to.equal(true);
    expect(issued.el.shadowRoot!.querySelector('form button.primary')).to.equal(null);
    const none = await mount('DRAFT', false);
    expect(none.el.shadowRoot!.textContent).to.contain('OI-MTQ-18').and.to.contain('to be confirmed');
    expect(none.el.shadowRoot!.querySelector('select[name=contact]')).to.equal(null);
  });
});
