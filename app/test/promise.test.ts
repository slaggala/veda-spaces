import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import type { Me } from '../src/core/api/types.js';
import { sessionContext } from '../src/core/authz/context.js';
import { filterNav, NAV_ITEMS } from '../src/core/authz/permissions.js';
import '../src/modules/promise/index.js';
import type { Landing, VersionDetail } from '../src/modules/promise/api.js';
import { landing, summary, version, vocabulary } from './support/promise-sample.js';

/** Customer Promise portal (decision log 37). The API is mocked and SYNTHETIC; the server decides every action. */

type Call = { method: string; path: string; body: unknown; ifMatch: string | null };
const json = (body: unknown, status = 200) => new Response(JSON.stringify({ data: body }), { status, headers: { 'Content-Type': 'application/json' } });
const problem = (status: number, body: Record<string, unknown>) =>
  new Response(JSON.stringify({ status, title: 'Refused', ...body }), { status, headers: { 'Content-Type': 'application/problem+json' } });

interface Mock { landing?: Landing; detail?: VersionDetail; put?: (body: unknown) => Response; post?: (path: string, body: unknown) => Response }

async function mount(mock: Mock = {}, perms: string[] = ['customer_promise.view']) {
  const calls: Call[] = [];
  const detail = mock.detail ?? version();
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), location.href).pathname;
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    calls.push({ method, path, body, ifMatch: headers['If-Match'] ?? null });
    if (method === 'PUT') return mock.put ? mock.put(body) : json(detail);
    if (method === 'POST') return mock.post ? mock.post(path, body) : json(detail);
    if (path === '/api/v1/customer-promise') return json(mock.landing ?? landing());
    if (path === '/api/v1/customer-promise/vocabulary') return json(vocabulary);
    if (path === '/api/v1/customer-promise/versions') return json([summary({ status: detail.status })]);
    if (path.endsWith('/changes')) {
      return json({ from: { pack_id: 'p0', version_no: 1, status: 'PUBLISHED' }, to: { pack_id: 'p1', version_no: 2, status: 'DRAFT' }, changes: [
        { section: 'CONTACTS', change: 'CHANGED', subject: 'Contact', item: 'SYN_SUP', message: 'Contact SYN_SUP: name changed', before: 'SYNTHETIC Support', after: 'SYNTHETIC Support Desk' },
        { section: 'EXCLUSIONS', change: 'ADDED', subject: 'Warranty exclusion', item: 'SYN_W', message: 'Warranty exclusion added: SYN_W', before: null, after: 'SYNTHETIC water damage.' }] });
    }
    if (path.endsWith('/preview')) {
      return json({ label: 'PREVIEW / NOT PUBLISHED', published: false, pack_id: 'p1', version_no: 1, status: 'DRAFT', content_version: 'CPP-1',
        creates: { quotation: false }, information: { content_version: 'CPP-1', contacts: { quotation: null, support: [{ display_name: 'SYNTHETIC Support',
          role: 'Care (synthetic)', phone: null, email: 'care@synthetic.example', hours: null, channel_note: null }], service: [] },
        support_escalation: null, project_inclusions: [{ code: 'SYN_INSTALL', text: 'SYNTHETIC installation of the listed items.' }],
        client_responsibilities: null, site_readiness: null, site_dependent_work: null, manufacturer_warranty_note: null, warranty_exclusions: null,
        service_guidance: null, handover: null, care: null, next_steps: null, payment_safety: 'SYNTHETIC: pay only through recorded channels.' } });
    }
    if (path.startsWith('/api/v1/customer-promise/versions/')) return json(detail);
    return json({});
  };
  const host = await fixture<HTMLDivElement>(html`<div></div>`);
  new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated', me: { id: 'u1',
    permissions: Object.fromEntries(perms.map((p) => [p, 'ALL'])), features: { customer_promise_admin: true } } as unknown as Me } });
  const el = document.createElement('vs-promise-page') as HTMLElement & { updateComplete: Promise<unknown> };
  host.append(el);
  await waitUntil(() => el.shadowRoot?.textContent?.includes('Completeness of the customer information'), 'landing loaded');
  return { el, root: el.shadowRoot!, calls };
}

async function open(el: HTMLElement & { updateComplete: Promise<unknown> }, root: ShadowRoot, section = 'Project inclusions') {
  (root.querySelector('button[aria-label="Open version 1 from the history"]') as HTMLButtonElement).click();
  await waitUntil(() => root.querySelector('vs-promise-editor'), 'version opened');
  [...root.querySelectorAll<HTMLButtonElement>('nav.sections button')].find((b) => b.textContent?.includes(section))!.click();
  await el.updateComplete;
  const editor = root.querySelector('vs-promise-editor') as HTMLElement & { updateComplete: Promise<unknown>; dirty: boolean };
  await editor.updateComplete;
  return editor;
}

describe('vs-promise-page (Customer Promise)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  it('shows the OI-MTQ-18 state and the fourteen areas, with structure kept apart from owner-approved content', async () => {
    const { root } = await mount();
    expect(root.textContent).to.contain('Owner decision OI-MTQ-18').and.to.contain('to be confirmed');
    const rows = root.querySelectorAll('section[aria-labelledby=completeness] tbody tr');
    expect(rows.length).to.equal(14);
    expect(rows[6].textContent).to.contain('Contract terms (OI-MTQ-09)');
    expect([...root.querySelectorAll('section[aria-labelledby=completeness] th')].map((t) => t.textContent)).to.include.members(['Structure', 'Owner-approved content']);
    expect(root.textContent).to.contain('Start a new draft');
    const viewer = await mount({ landing: landing({ actions: { create_draft: false, preview: false, history: false } }) });
    expect(viewer.root.textContent).to.not.contain('Start a new draft');
  });

  it('is in the navigation only with the feature on and the view capability', () => {
    const perms = { 'customer_promise.view': 'ALL' } as const;
    const path = '/commercial/customer-promise';
    expect(filterNav(NAV_ITEMS, perms, { customer_promise_admin: true }).map((i) => i.path)).to.include(path);
    expect(filterNav(NAV_ITEMS, perms, { customer_promise_admin: false }).map((i) => i.path)).to.not.include(path);
    expect(filterNav(NAV_ITEMS, {}, { customer_promise_admin: true }).map((i) => i.path)).to.not.include(path);
  });

  it('edits a section with structured fields and saves exactly its keys with If-Match (no raw JSON)', async () => {
    const { el, root, calls } = await mount();
    const editor = await open(el, root);
    const er = editor.shadowRoot!;
    expect(er.querySelector('textarea')).to.not.equal(null);
    expect(er.textContent).to.not.contain('{"');
    const text = er.querySelector('textarea') as HTMLTextAreaElement;
    text.value = 'SYNTHETIC installation and fixing of the listed items.';
    text.dispatchEvent(new Event('input'));
    [...er.querySelectorAll('button')].find((b) => b.textContent?.startsWith('Add inclusion'))!.click();
    await editor.updateComplete;
    const inputs = er.querySelectorAll<HTMLInputElement>('input:not([type=checkbox])');
    inputs[inputs.length - 1].value = 'SYN_CLEAN';
    inputs[inputs.length - 1].dispatchEvent(new Event('input'));
    const texts = er.querySelectorAll<HTMLTextAreaElement>('textarea');
    texts[texts.length - 1].value = 'SYNTHETIC cleaning after installation.';
    texts[texts.length - 1].dispatchEvent(new Event('input'));
    const active = er.querySelectorAll<HTMLInputElement>('input[type=checkbox]');
    active[active.length - 1].click(); // the new entry is kept but not published yet
    await editor.updateComplete;
    expect(editor.dirty).to.equal(true);
    (er.querySelector('button[type=submit]') as HTMLButtonElement).click();
    await waitUntil(() => calls.some((c) => c.method === 'PUT'));
    const put = calls.find((c) => c.method === 'PUT')!;
    expect(put.path).to.equal('/api/v1/customer-promise/versions/p1/sections/INCLUSIONS');
    expect(put.ifMatch).to.equal('"4"');
    expect(put.body).to.deep.equal({ value: { project_inclusions: [
      { code: 'SYN_INSTALL', text: 'SYNTHETIC installation and fixing of the listed items.' },
      { code: 'SYN_CLEAN', text: 'SYNTHETIC cleaning after installation.', active: false }] } });
    await expect(el).to.be.accessible({ ignoredRules: ['region'] });
  });

  it('marks the control a server field error names and lists it in the error summary', async () => {
    const { el, root } = await mount({ put: () => problem(422, { code: 'VALIDATION_FAILED',
      errors: [{ field: 'project_inclusions[0].text', code: 'INVALID', message: 'customer copy must not contain an unsupported claim' }] }) });
    const editor = await open(el, root);
    (editor.shadowRoot!.querySelector('button[type=submit]') as HTMLButtonElement).click();
    await waitUntil(() => (root.querySelector('vs-error-summary') as HTMLElement).shadowRoot?.textContent?.includes('unsupported claim'), 'summary');
    await editor.updateComplete;
    const field = editor.shadowRoot!.querySelector('textarea') as HTMLTextAreaElement;
    expect(field.getAttribute('aria-invalid')).to.equal('true');
    const described = field.getAttribute('aria-describedby')!;
    expect(editor.shadowRoot!.getElementById(described.split(' ').pop()!)!.textContent).to.contain('unsupported claim');
  });

  it('says plainly when someone else changed the version, and overwrites nothing', async () => {
    const { el, root, calls } = await mount({ put: () => problem(409, { code: 'VERSION_CONFLICT', detail: 'The record was changed after you loaded it.' }) });
    const editor = await open(el, root);
    const text = editor.shadowRoot!.querySelector('textarea') as HTMLTextAreaElement;
    text.value = 'SYNTHETIC edited.';
    text.dispatchEvent(new Event('input'));
    (editor.shadowRoot!.querySelector('button[type=submit]') as HTMLButtonElement).click();
    await waitUntil(() => root.textContent?.includes('Someone else changed this version'), 'conflict');
    expect(editor.dirty).to.equal(true); // the user's edit is still on screen
    expect(calls.filter((c) => c.method === 'PUT').length).to.equal(1); // no automatic retry
  });

  it('offers review, approval and publication only where the API says the user may act', async () => {
    const inReview = version({ status: 'IN_REVIEW' }, { can_review: true });
    const { el, root } = await mount({ detail: inReview });
    await open(el, root);
    expect(root.textContent).to.contain('Approve section').and.to.contain('Request changes');
    expect(root.textContent).to.not.contain('Approve version').and.to.not.contain('Publish');
    expect(root.querySelector('vs-promise-editor')!.shadowRoot!.querySelector('button[type=submit]')).to.equal(null); // read-only
    const approvable = version({ status: 'IN_REVIEW', pending_reviews: [], actions: { ...inReview.actions, approve: true, return: true } });
    const second = await mount({ detail: approvable });
    await open(second.el, second.root);
    expect(second.root.textContent).to.contain('Approve version').and.to.contain('Return to draft');
    expect(second.root.textContent).to.not.contain('Approve section');
  });

  it('asks for confirmation and a comment before requesting changes', async () => {
    const { el, root, calls } = await mount({ detail: version({ status: 'IN_REVIEW' }, { can_review: true }) });
    await open(el, root);
    [...root.querySelectorAll('button')].find((b) => b.textContent === 'Request changes')!.click();
    await el.updateComplete;
    const area = root.querySelector('vs-dialog textarea[name=comment]') as HTMLTextAreaElement;
    expect(area).to.not.equal(null);
    (root.querySelector('vs-dialog button[type=submit]') as HTMLButtonElement).click();
    await el.updateComplete;
    expect(calls.some((c) => c.method === 'POST')).to.equal(false); // a comment is required
    area.value = 'SYNTHETIC: please reword this.';
    (root.querySelector('vs-dialog button[type=submit]') as HTMLButtonElement).click();
    await waitUntil(() => calls.some((c) => c.method === 'POST'));
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.path).to.equal('/api/v1/customer-promise/versions/p1/sections/INCLUSIONS/review');
    expect(post.body).to.deep.equal({ decision: 'CHANGES_REQUESTED', comment: 'SYNTHETIC: please reword this.' });
  });

  it('shows what changed in words, grouped by section, with before and after', async () => {
    const { el, root } = await mount();
    await open(el, root);
    [...root.querySelectorAll('.tabs button')].find((b) => b.textContent === 'What changed')!.dispatchEvent(new MouseEvent('click'));
    await waitUntil(() => root.textContent?.includes('Contact SYN_SUP: name changed'), 'changes');
    const headings = [...root.querySelectorAll('section h3')].map((h) => h.textContent);
    expect(headings).to.include('Contact and support (1 change)').and.to.include('Warranty exclusions (1 change)');
    expect(root.querySelector('td.before')!.textContent).to.equal('SYNTHETIC Support');
    expect(root.querySelector('td.after')!.textContent).to.equal('SYNTHETIC Support Desk');
  });

  it('previews through the customer proposal panels, unmistakably marked as not published', async () => {
    const { el, root } = await mount();
    await open(el, root);
    [...root.querySelectorAll('.tabs button')].find((b) => b.textContent === 'Preview as customer')!.dispatchEvent(new MouseEvent('click'));
    await waitUntil(() => root.querySelector('vs-promise-preview'), 'preview');
    expect(root.querySelector('.preview-banner')!.textContent).to.equal('PREVIEW / NOT PUBLISHED');
    const preview = root.querySelector('vs-promise-preview') as HTMLElement & { updateComplete: Promise<unknown> };
    await preview.updateComplete;
    expect(preview.shadowRoot!.textContent).to.contain('SYNTHETIC Support').and.to.contain('SYNTHETIC installation')
      .and.to.contain('pay only through recorded channels').and.to.contain('Contact details to be confirmed');
    [...root.querySelectorAll('.widths button')].find((b) => b.textContent?.startsWith('Mobile'))!.dispatchEvent(new MouseEvent('click'));
    await el.updateComplete;
    expect((root.querySelector('.frame') as HTMLElement).style.maxWidth).to.equal('360px');
  });
});
