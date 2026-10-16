import { expect, fixture, html } from '@open-wc/testing';
import { filterNav, NAV_ITEMS } from '../src/core/authz/permissions.js';
import type { ServiceRequestView, WarrantyView } from '../src/modules/portal/api.js';
import '../src/modules/portal/portal-service.js';

/** Warranty and after-sales service (WSV): navigation behind its flag, and the customer's section in plain words. */

const req = (over: Partial<ServiceRequestView> = {}): ServiceRequestView => ({
  id: 'r1', reference: 'VS-SR-2026-000001', status: 'RESOLVED', status_label: 'Please confirm it is resolved', next: 'YOU',
  category: 'A door, shutter or drawer', description: 'The kitchen drawer next to the hob does not close fully', area: 'Kitchen',
  noticed_on: null, reported_on: '2026-10-16', project_id: 'p1', photos: [], messages: [],
  coverage: { outcome: 'COVERED', label: 'Covered by your warranty', explanation: 'We will fix it.', chargeable_note: null },
  visits: [{ kind: 'Service visit', status: 'DONE', planned_on: '2026-10-17', done_on: '2026-10-17', note: null }],
  resolution: { summary: 'We re-aligned the channel.', outcome: 'PENDING' }, evidence: [],
  can_add_information: false, can_add_photos: false, can_confirm: true, can_reject: true, can_withdraw: false, ...over,
});
const view = (requests: ServiceRequestView[], status = 'NOT_RECORDED'): WarrantyView => ({
  available: true, max_photos: 6, categories: [{ code: 'DOOR_OR_DRAWER', label: 'A door, shutter or drawer' }],
  projects: [{ id: 'p1', handed_over: true, can_report: true, requests,
    warranty: { state: 'REGISTERED', id: 'e1', handed_over_on: '2026-10-01', status, status_label: status === 'ACTIVE' ? 'Active' : 'Not recorded in your portal',
      period_note: status === 'ACTIVE' ? null : 'Your warranty period is as stated in your accepted quotation and the Veda Spaces Warranty, Service & Customer Care Policy.',
      coverage: [], statements: [{ kind: 'Warranty', text: 'SYNTHETIC warranty statement.', source: 'VS-Q-2026-000001 v1' }], exclusions: ['SYNTHETIC misuse'],
      manufacturer_notes: [], policy_url: null } }],
});

describe('Warranty and service (WSV)', () => {
  it('shows Service only with the flag on and a service permission', () => {
    const perms = { 'warranty.service.view': 'ALL', 'profile.read': 'ALL' } as const;
    expect(filterNav(NAV_ITEMS, perms, { warranty_service: false }).map((i) => i.path)).to.not.include('/service');
    expect(filterNav(NAV_ITEMS, perms, { warranty_service: true }).map((i) => i.path)).to.include('/service');
    expect(filterNav(NAV_ITEMS, { 'commercials.view': 'ALL' }, { warranty_service: true }).map((i) => i.path)).to.not.include('/service');
  });

  it('never shows the warranty as "covered" and quotes the accepted quotation verbatim', async () => {
    const el = await fixture(html`<vs-portal-service .view=${view([])} .propertyId=${'prop1'}></vs-portal-service>`);
    const text = el.shadowRoot!.textContent ?? '';
    expect(text).to.contain('Not recorded in your portal').and.to.contain('as stated in your accepted quotation');
    expect(text).to.contain('SYNTHETIC warranty statement.');
    expect(text.toLowerCase()).to.not.contain('you are covered');
  });

  it('offers exactly the customer actions the server allows, with accessible names', async () => {
    const el = await fixture(html`<vs-portal-service .view=${view([req()])} .propertyId=${'prop1'}></vs-portal-service>`);
    const names = [...el.shadowRoot!.querySelectorAll('button')].map((b) => b.textContent?.replace(/\s+/g, ' ').trim());
    expect(names).to.include('It is resolved: VS-SR-2026-000001').and.include('Still not right: VS-SR-2026-000001');
    expect(names.some((n) => n?.startsWith('Withdraw'))).to.equal(false);
    const closed = await fixture(html`<vs-portal-service .view=${view([req({ status: 'CLOSED', status_label: 'Resolved', next: null, can_confirm: false, can_reject: false })])}
      .propertyId=${'prop1'}></vs-portal-service>`);
    const closedNames = [...closed.shadowRoot!.querySelectorAll('button')].map((b) => b.textContent?.trim());
    expect(closedNames.some((n) => n?.startsWith('It is resolved'))).to.equal(false);
  });

  it('opens the report form with focus on the first field and refuses a too-short description without sending', async () => {
    let calls = 0;
    const original = window.fetch;
    window.fetch = async () => { calls += 1; return new Response('{}'); };
    try {
      const el = await fixture(html`<vs-portal-service .view=${view([])} .propertyId=${'prop1'}></vs-portal-service>`) as HTMLElement & { updateComplete: Promise<unknown> };
      [...el.shadowRoot!.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Report a problem')!.click();
      await el.updateComplete;
      await el.updateComplete;
      expect((el.shadowRoot!.activeElement as HTMLElement | null)?.getAttribute('name')).to.equal('category');
      el.shadowRoot!.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
      await el.updateComplete;
      expect(el.shadowRoot!.querySelector('[role=alert]')?.textContent).to.contain('at least 10 characters');
      expect(calls).to.equal(0);
    } finally { window.fetch = original; }
  });
});
