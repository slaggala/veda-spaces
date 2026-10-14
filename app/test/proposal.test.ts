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

describe('vs-proposal-view specifications and media (CQX-04)', () => {
  const cat = { label: 'Carcass', summary: 'Moisture-resistant board', requirement: 'BWR grade board', grade: 'BWR', thickness: '18 mm',
    finish: null, brand_examples: 'Example A, Example B', equivalent_rule: 'Equivalent grade only', final_selection: 'Confirmed at design sign-off',
    warranty_summary: 'As per the manufacturer.' };
  const img = { title: 'Wardrobe', alt: 'A two-door laminate wardrobe', caption: null, label: 'Illustrative example' as const,
    urls: { thumb: '/api/v1/public/catalog/media/x', mobile: '/api/v1/public/catalog/media/y' } };

  it('shows each line\'s approved specification and labelled reference images with a gallery', async () => {
    const page = samplePage({ specifications: { name: 'Essential', version: '1.1', summary: 's', equivalent_policy: 'e', final_selection: 'f',
      lines: { L1: [cat] } }, media: { note: 'Reference image: it does not change the scope or the price.', lines: { L1: [img, { ...img, label: 'Design reference' }] },
      rooms: { R1: img, R2: null, R3: null } } });
    const el = await fixture<VsProposalView>(html`<vs-proposal-view .page=${page}></vs-proposal-view>`);
    const root = el.shadowRoot!;
    const spec = root.querySelector('details.spec')!;
    expect(spec.textContent).to.contain('BWR grade board').and.to.contain('Material warranty').and.to.contain('version 1.1');
    const thumbs = [...root.querySelectorAll('.thumbbtn')];
    expect(thumbs).to.have.length(2);
    expect(thumbs[0].getAttribute('aria-label')).to.equal('Open image 1 of 2: A two-door laminate wardrobe (Illustrative example)');
    expect(root.querySelector('.roomcard img')!.getAttribute('alt')).to.equal('A two-door laminate wardrobe');
    expect(root.querySelector('.roomcard .imglabel')!.textContent).to.equal('Illustrative example');
    (thumbs[1] as HTMLButtonElement).click();
    await el.updateComplete;
    const dialog = root.querySelector('vs-dialog')!;
    expect(dialog.getAttribute('heading')).to.equal('Wardrobe — Body');
    expect(dialog.textContent).to.contain('Design reference');
    await expect(el).to.be.accessible({ ignoredRules: ['image-redundant-alt'] });
  });

  it('falls back to the named placeholder when an image cannot load', async () => {
    const page = samplePage({ media: { note: 'n', lines: {}, rooms: { R1: { ...img, urls: { mobile: '/missing.png' } }, R2: null, R3: null } } });
    const el = await fixture<VsProposalView>(html`<vs-proposal-view .page=${page}></vs-proposal-view>`);
    await waitUntil(() => el.shadowRoot!.querySelectorAll('.roomcard .ph').length === 3, 'placeholder after a failed image', { timeout: 3000 });
  });
});

describe('vs-proposal-view pricing (CQX-05)', () => {
  it('shows the frozen totals, milestones as shares and validity, with no unit rate', async () => {
    const page = samplePage({ pricing: { currency: 'INR', total: '3,89,400.00', gst: { status: 'Included', amount: '59,400.00' }, discount: null,
      base_total: '3,30,000.00', optional_total: '15,000.00', rooms: [{ ref: 'R1', title: 'Master bedroom', subtotal: '1,20,000.00' }],
      milestones: [{ label: 'Booking', share: '10%', trigger: 'On acceptance (synthetic)' }], valid_until: '2026-11-13', days_left: 30,
      unit_rates_shown: false, package: null, alternatives: [{ reference: 'VS-Q-2026-000002 v1', package: null, total: '4,00,000.00', valid_until: null }] } });
    const el = await fixture<VsProposalView>(html`<vs-proposal-view .page=${page}></vs-proposal-view>`);
    const sec = el.shadowRoot!.querySelector('#pricing')!;
    expect(sec.textContent).to.contain('Booking').and.to.contain('10%').and.to.contain('30 days left').and.to.contain('unit rates are not part');
    expect(sec.textContent).to.contain('VS-Q-2026-000002 v1');
    await expect(el).to.be.accessible();
  });
});

describe('optional items (CQX-06)', () => {
  const withChoices = (status: 'CALCULATED' | 'PRICE_CONFIRMATION_REQUIRED', selected: string[] = []) => samplePage({
    capabilities: { interaction: true, acceptance: false },
    selections: { items: [{ ref: 'L9', state: selected.includes('L9') ? 'SELECTED' : 'NOT_SELECTED', priced: true }], selected_refs: selected,
      status, extra: status === 'CALCULATED' && selected.length ? '15,000.00' : null,
      total_with_selections: status === 'CALCULATED' && selected.length ? '4,07,100.00' : null } });

  it('offers a labelled choice per item and says the price needs confirmation', async () => {
    const el = await fixture<VsProposalView>(html`<vs-proposal-view .page=${withChoices('PRICE_CONFIRMATION_REQUIRED', ['L9'])}></vs-proposal-view>`);
    const set = el.shadowRoot!.querySelector('fieldset.optitem')!;
    expect(set.querySelector('legend')!.textContent).to.contain('Loft above wardrobe');
    const radios = [...set.querySelectorAll('input[type=radio]')] as HTMLInputElement[];
    expect(radios.map((r) => r.closest('label')!.textContent!.trim())).to.deep.equal(['Add to my proposal', 'Not for me', 'I would like to discuss it']);
    expect(radios[0].checked).to.equal(true);
    expect(el.shadowRoot!.querySelector('#optional')!.textContent).to.contain('PRICE CONFIRMATION REQUIRED');
    await expect(el).to.be.accessible();
  });

  it('shows the server total only when it is calculated, and never offers choices in preview', async () => {
    let el = await fixture<VsProposalView>(html`<vs-proposal-view .page=${withChoices('CALCULATED', ['L9'])}></vs-proposal-view>`);
    expect(el.shadowRoot!.querySelector('#optional')!.textContent).to.contain('₹ 4,07,100.00');
    el = await fixture<VsProposalView>(html`<vs-proposal-view preview .page=${withChoices('CALCULATED')}></vs-proposal-view>`);
    expect(el.shadowRoot!.querySelectorAll('input[type=radio]')).to.have.length(0);
  });

  it('sends the choice with the link header, reloads, and announces the result; a refusal lands in the error summary', async () => {
    history.replaceState(null, '', `/proposal#t=vsp_${'z'.repeat(43)}`);
    let refused = false;
    const calls = serve((path) => (path.endsWith('/selections') && refused
      ? json({ status: 422, code: 'VALIDATION_FAILED', title: 'x', detail: 'Please choose one of the optional items.', errors: [{ field: 'line_ref', code: 'NOT_OPTIONAL', message: 'Not an optional item of this proposal.' }] }, 422)
      : json(path.endsWith('/selections') ? withChoices('PRICE_CONFIRMATION_REQUIRED', ['L9']).selections : withChoices('PRICE_CONFIRMATION_REQUIRED'))));
    const page = await fixture(html`<vs-proposal-page></vs-proposal-page>`);
    await waitUntil(() => page.shadowRoot!.querySelector('vs-proposal-view'));
    const view = page.shadowRoot!.querySelector('vs-proposal-view') as VsProposalView;
    await view.updateComplete;
    (view.shadowRoot!.querySelector('input[type=radio]') as HTMLInputElement).click();
    await waitUntil(() => view.announcement.includes('added to your choices'));
    const post = calls.find((c) => c.path.endsWith('/selections'))!;
    expect(post.headers['X-Veda-Proposal']).to.equal(`vsp_${'z'.repeat(43)}`);
    expect(post.headers['Idempotency-Key']).to.match(/^[a-f0-9]{32}$/);
    refused = true;
    (view.shadowRoot!.querySelectorAll('input[type=radio]')[1] as HTMLInputElement).click();
    await waitUntil(() => view.shadowRoot!.querySelector('vs-error-summary'));
    expect(view.announcement).to.equal('Not saved.');
  });
});

describe('questions and change requests (CQX-07)', () => {
  const asked = (over: Partial<Page> = {}) => samplePage({ capabilities: { interaction: true, acceptance: false },
    requests: { can_ask: true, items: [{ ref: '#1', category: 'CHANGE_FINISH', category_label: 'Change a finish', line_ref: 'L1', room: 'Master bedroom',
      about_version: 1, about_variation: 0, message: '<img src=x onerror=alert(1)> acrylic please', requested_quantity: null, status: 'NEEDS_CLARIFICATION',
      status_label: 'We need a little more detail', response: 'Which colour?', sent_on: '2026-10-14T10:00:00Z', responded_on: null, answered_by_revision: null }] }, ...over });

  it('lists the customer\'s requests as text (never markup) with the answer, and asks only what the category needs', async () => {
    const el = await fixture<VsProposalView>(html`<vs-proposal-view .page=${asked()}></vs-proposal-view>`);
    const sec = el.shadowRoot!.querySelector('#questions')!;
    expect(sec.querySelector('img')).to.equal(null);
    expect(sec.querySelector('.msg')!.textContent).to.contain('<img src=x');
    expect(sec.textContent).to.contain('Which colour?');
    expect(sec.querySelector('select[name=line]')).to.equal(null);
    const cat = sec.querySelector('select[name=category]') as HTMLSelectElement;
    cat.value = 'CHANGE_QUANTITY';
    cat.dispatchEvent(new Event('change'));
    await el.updateComplete;
    expect(sec.querySelector('select[name=line]')).to.exist;
    expect(sec.querySelector('input[name=quantity]')).to.exist;
    await expect(el).to.be.accessible();
  });

  it('sends one request per submission with a stable idempotency key and clears the form', async () => {
    history.replaceState(null, '', `/proposal#t=vsp_${'q'.repeat(43)}`);
    const calls = serve((path) => json(path.endsWith('/requests') ? [] : asked()));
    const page = await fixture(html`<vs-proposal-page></vs-proposal-page>`);
    await waitUntil(() => page.shadowRoot!.querySelector('vs-proposal-view'));
    const view = page.shadowRoot!.querySelector('vs-proposal-view') as VsProposalView;
    await view.updateComplete;
    const form = view.shadowRoot!.querySelector('#questions form') as HTMLFormElement;
    (form.querySelector('textarea') as HTMLTextAreaElement).value = 'Could the kitchen be ready earlier?';
    form.requestSubmit();
    await waitUntil(() => view.announcement.includes('sent to Veda Spaces'));
    const post = calls.find((c) => c.path.endsWith('/requests'))!;
    expect(post.headers['Idempotency-Key']).to.match(/^[a-f0-9]{32}$/);
    expect((form.querySelector('textarea') as HTMLTextAreaElement).value).to.equal('');
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
