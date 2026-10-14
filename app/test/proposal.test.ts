import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Page } from '../src/modules/proposal/api.js';
import '../src/modules/proposal/index.js';
import type { VsProposalView } from '../src/modules/proposal/proposal-view.js';

/** CQX: the customer proposal page. SYNTHETIC page models; the API is mocked; the server decides everything. */

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

function serve(handler: (path: string, init?: RequestInit) => Response) {
  const calls: { path: string; headers: Record<string, string> }[] = [];
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), location.href).pathname;
    calls.push({ path, headers: (init?.headers ?? {}) as Record<string, string> });
    return handler(path, init);
  };
  return calls;
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(status < 400 ? { data: body } : body), { status, headers: { 'Content-Type': status < 400 ? 'application/json' : 'application/problem+json' } });

describe('vs-proposal-view (CQX-03)', () => {
  it('shows the overview, room cards with counts and room-by-room detail, accessibly', async () => {
    const el = await fixture<VsProposalView>(html`<vs-proposal-view .page=${samplePage()}></vs-proposal-view>`);
    const root = el.shadowRoot!;
    expect(root.querySelector('h1')!.textContent).to.contain('3 BHK');
    const cards = [...root.querySelectorAll('.roomcard')];
    expect(cards).to.have.length(3);
    expect(cards[0].getAttribute('aria-label')).to.equal('Master bedroom: 2 included items, 1 optional, ₹ 1,20,000.00');
    expect(root.querySelectorAll('details.room')).to.have.length(3);
    expect(root.textContent).to.contain('₹ 3,89,400.00');
    await expect(el).to.be.accessible();
  });

  it('jumps to a room from its card and opens it, moving focus there', async () => {
    const el = await fixture<VsProposalView>(html`<vs-proposal-view .page=${samplePage()}></vs-proposal-view>`);
    const root = el.shadowRoot!;
    (root.querySelector('a.roomcard[href="#R2"]') as HTMLAnchorElement).click();
    const room = root.querySelector('#R2') as HTMLDetailsElement;
    expect(room.open).to.equal(true);
    expect(root.activeElement).to.equal(room);
  });

  it('marks states, earlier versions and staff preview, and never offers actions in preview', async () => {
    const page = samplePage({ state: 'SUPERSEDED', history: [{ version_no: 1, issued_on: '2026-10-01' }],
      notices: [{ code: 'SUPERSEDED', message: 'A newer version of this proposal is available.' }],
      actions: [{ code: 'X', label: 'Do something', target: 'sum' }] });
    page.proposal.version_no = 2;
    const el = await fixture<VsProposalView>(html`<vs-proposal-view preview .page=${page}></vs-proposal-view>`);
    const root = el.shadowRoot!;
    expect(root.textContent).to.contain('Replaced by a newer version');
    expect(root.textContent).to.contain('version 1 (2026-10-01)');
    expect(root.querySelector('.preview-mark')).to.exist;
    expect(root.textContent).not.to.contain('Do something');
    expect(root.querySelector('.bar')).to.equal(null);
  });

  it('opens every room before printing', async () => {
    const el = await fixture<VsProposalView>(html`<vs-proposal-view .page=${samplePage()}></vs-proposal-view>`);
    window.dispatchEvent(new Event('beforeprint'));
    expect([...el.shadowRoot!.querySelectorAll('details')].every((d) => (d as HTMLDetailsElement).open)).to.equal(true);
  });
});

describe('vs-proposal-page (CQX-01/03)', () => {
  afterEach(() => sessionStorage.clear());

  it('takes the token from the fragment, scrubs the address bar and sends it only as a header', async () => {
    history.replaceState(null, '', `/proposal#t=vsp_${'x'.repeat(43)}`);
    const calls = serve(() => json(samplePage()));
    const el = await fixture(html`<vs-proposal-page></vs-proposal-page>`);
    await waitUntil(() => el.shadowRoot!.querySelector('vs-proposal-view'));
    expect(window.location.hash).to.equal('');
    expect(calls[0].path).to.equal('/api/v1/public/proposal');
    expect(calls[0].headers['X-Veda-Proposal']).to.equal(`vsp_${'x'.repeat(43)}`);
    expect(calls[0].headers.Authorization).to.equal(undefined);
    expect(document.title).to.equal('Your proposal · Veda Spaces');
  });

  it('explains a revoked, expired or superseded link safely and forgets it', async () => {
    for (const [code, words] of [['PROPOSAL_LINK_REVOKED', 'no longer active'], ['PROPOSAL_LINK_EXPIRED', 'has expired'],
      ['PROPOSAL_SUPERSEDED', 'newer version']] as const) {
      history.replaceState(null, '', `/proposal#t=vsp_${'y'.repeat(43)}`);
      serve(() => json({ status: 410, code, title: 'Gone', detail: 'x' }, 410));
      const el = await fixture(html`<vs-proposal-page></vs-proposal-page>`);
      await waitUntil(() => el.shadowRoot!.querySelector('[role="alert"]'));
      expect(el.shadowRoot!.textContent).to.contain(words);
      expect(sessionStorage.getItem('vs-proposal-link')).to.equal(null);
      await expect(el).to.be.accessible();
    }
  });

  it('without a link says so without calling the API', async () => {
    history.replaceState(null, '', '/proposal');
    const calls = serve(() => json(samplePage()));
    const el = await fixture(html`<vs-proposal-page></vs-proposal-page>`);
    await waitUntil(() => el.shadowRoot!.querySelector('[role="alert"]'));
    expect(calls).to.have.length(0);
    expect(el.shadowRoot!.textContent).to.contain('not valid');
  });
});
