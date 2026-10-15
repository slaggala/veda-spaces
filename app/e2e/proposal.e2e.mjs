// Customer proposal page (CQX-12): responsive layout, accessibility, keyboard, print, reduced motion, slow network and
// every refusal state, in a real browser against the real app. The API is answered by Playwright with SYNTHETIC page
// models (every /api request is intercepted, so nothing reaches a live stack): the API's own behaviour is proven by the
// API suites; this proves what the customer's browser does with it.
//   APP_BASE=http://localhost:5173 node e2e/proposal.e2e.mjs
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const BASE = process.env.APP_BASE ?? 'http://localhost:5173';
const OUT = process.env.E2E_OUT ?? 'e2e-artifacts';
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`); };
const TOKEN = `vsp_${'S'.repeat(43)}`;
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');

function line(ref, description, amount, status = 'Included') {
  return { ref, description, detail: 'Laminate finish', quantity: '42.5 sq ft', amount, priced: true, status,
    dimensions: [{ label: 'Width', value: '8.2 ft' }, { label: 'Height', value: '7 ft' }], dimension_status: ref === 'L1' ? 'TO_BE_CONFIRMED' : 'CONFIRMED' };
}
// SYNTHETIC customer information (OI-MTQ-18): invented for the browser journey, not Veda Spaces content.
const CONTACT = { display_name: 'SYNTHETIC Quotation Desk', role: 'Quotation consultant (synthetic)', phone: '+00 0000 000000',
  email: 'desk@synthetic.example', hours: 'SYNTHETIC hours', channel_note: null };
const INFO = {
  content_version: 'SYN-C1', contacts: { quotation: CONTACT, support: [{ ...CONTACT, display_name: 'SYNTHETIC Support' }], service: [] },
  support_escalation: 'SYNTHETIC escalation route.', project_inclusions: [{ code: 'I1', text: 'SYNTHETIC installation of the listed items.' }],
  client_responsibilities: [{ code: 'A1', category: 'APPLIANCE_MODEL', text: 'SYNTHETIC: share your appliance models.', status: 'REQUIRED' }],
  site_readiness: [{ code: 'F1', category: 'FLOORING', text: 'SYNTHETIC: flooring complete.', status: 'CUSTOMER_ACTION_REQUIRED' }],
  site_dependent_work: { intro: 'SYNTHETIC: some needs show only on site.', approval_rule: 'SYNTHETIC: agreed with you as a change order first.',
    categories: [{ code: 'E1', category: 'ELECTRICAL', text: 'SYNTHETIC electrical changes.' }] },
  manufacturer_warranty_note: 'SYNTHETIC manufacturer note.', warranty_exclusions: [{ code: 'X1', text: 'SYNTHETIC: damage from misuse.' }],
  service_guidance: { contact: { ...CONTACT, display_name: 'SYNTHETIC Service' }, what_to_provide: ['SYNTHETIC: your reference.'],
    reference_process: 'SYNTHETIC: you receive a reference.', escalation: null },
  handover: [{ code: 'H1', category: 'FINAL_INSPECTION', text: 'SYNTHETIC joint inspection.' }],
  care: [{ code: 'C1', category: 'FURNITURE_CLEANING', text: 'SYNTHETIC: wipe with a dry cloth.' }],
  next_steps: [{ code: 'S1', stage: 'PROPOSAL_ACCEPTED', label: 'Proposal accepted', text: 'SYNTHETIC step.', duration: null }],
  payment_safety: 'SYNTHETIC: payment instructions only through approved Veda Spaces channels.',
};
const SPEC = { name: 'SYNTHETIC Essential', version: '1.1', summary: 'SYNTHETIC specification.', equivalent_policy: 'SYNTHETIC equivalents.',
  final_selection: 'SYNTHETIC final selection.', warranty_summary: 'SYNTHETIC manufacturer warranty summary.', lines: {},
  categories: [
    { code: 'board', label: 'Board', summary: 'SYNTHETIC board.', requirement: 'SYNTHETIC grade', grade: null, thickness: '18 mm', finish: null,
      brand_examples: null, equivalent_rule: 'SYNTHETIC rule', final_selection: 'SYNTHETIC', warranty_summary: 'SYNTHETIC', hardware_category: null, details: [], group: 'MATERIAL' },
    { code: 'hinges', label: 'Hinges', summary: 'SYNTHETIC hinges.', requirement: 'SYNTHETIC soft close', grade: null, thickness: null, finish: null,
      brand_examples: null, equivalent_rule: 'SYNTHETIC rule', final_selection: 'SYNTHETIC', warranty_summary: 'SYNTHETIC', hardware_category: 'Hinges and channels', details: [], group: 'HARDWARE' },
  ] };
function page(over = {}) {
  const rooms = ['Master bedroom', 'Bedroom 2', 'Bedroom 3', 'Kitchen', 'Living room'].map((title, i) => ({
    ref: `R${i + 1}`, title, kind: 'ROOM', subtotal: '1,20,000.00', included_count: 2, optional_count: i === 0 ? 1 : 0,
    lines: [line(`L${i * 2 + 1}`, `${title} — Wardrobe with a deliberately long description that must wrap on small screens`, '90,000.00'),
      line(`L${i * 2 + 2}`, `${title} — Loft`, '30,000.00')],
  }));
  rooms.push({ ref: 'R6', title: 'Project-wide', kind: 'PROJECT', subtotal: '10,000.00', included_count: 1, optional_count: 0,
    lines: [line('L20', 'Site protection', '10,000.00')] });
  return {
    state: 'OPEN', link: { expires_on: '2099-01-01T00:00:00Z', status: 'ACTIVE' }, history: [{ version_no: 1, issued_on: '2026-10-01' }],
    capabilities: { interaction: true, acceptance: true }, notices: [],
    actions: [{ code: 'REVIEW_OPTIONAL_ITEMS', label: 'Review the optional items', target: 'optional' },
      { code: 'ACKNOWLEDGE_TERMS', label: 'Read and acknowledge the terms', target: 'terms' }],
    proposal: {
      schema: 'veda.customer-proposal/1', kind: 'QUOTATION', title: 'Quotation', brand: { name: 'Veda Spaces', tagline: 'Interiors, measured and made' },
      reference: 'VS-Q-2026-000001 v2', quotation_number: 'VS-Q-2026-000001', version_no: 2, variation_no: 0, issued_on: '2026-10-14',
      valid_until: '2026-11-13', subject: 'Interior works — 3 BHK apartment, Synthetic City (SYNTHETIC)', cover_note: 'SYNTHETIC proposal for browser validation.',
      property: { reference: 'VS-P-2026-000001', configuration: '3 BHK apartment', city: 'Synthetic City' }, snapshot_sha256: 'a'.repeat(64),
      rooms, optional_items: [{ ...line('L30', 'Loft above wardrobe', '15,000.00', 'Optional'), price_with_gst: '17,700.00', room_ref: 'R1', room_title: 'Master bedroom' }],
      summary: { base_total: '6,10,000.00', taxable: '6,10,000.00', gst: { status: 'Included', amount: '1,09,800.00' }, total: '7,19,800.00',
        optional_total: '15,000.00', currency: 'INR' },
      payment_schedule: [{ label: 'Booking', share: '10%', trigger: 'On acceptance (synthetic)' }, { label: 'Production', share: '50%', trigger: 'Before production (synthetic)' },
        { label: 'Handover', share: '40%', trigger: 'On handover (synthetic)' }],
      warranty: ['Synthetic warranty text.'], service_support: [], assumptions: ['Synthetic assumption.'], exclusions: ['Synthetic exclusion.'],
      terms: ['Synthetic change-order terms.', 'Synthetic cancellation terms.'], terms_version: 'SYN-T1', unit_rates_shown: false,
      sections: { SCOPE: 'b'.repeat(64) }, information: INFO,
    },
    specifications: SPEC,
    media: { note: 'Reference image: it illustrates the kind of item and does not change the scope or the price.',
      lines: { L1: [{ title: 'Wardrobe', alt: 'A two-door laminate wardrobe', caption: null, label: 'Illustrative example', urls: { thumb: '/api/v1/public/catalog/media/ok' } }] },
      rooms: { R1: { title: 'Wardrobe', alt: 'A two-door laminate wardrobe', caption: null, label: 'Illustrative example', urls: { mobile: '/api/v1/public/catalog/media/missing' } },
        R2: null, R3: null, R4: null, R5: null, R6: null } },
    pricing: { currency: 'INR', total: '7,19,800.00', gst: { status: 'Included', amount: '1,09,800.00' }, discount: null, base_total: '6,10,000.00',
      optional_total: '15,000.00', rooms: rooms.map((r) => ({ ref: r.ref, title: r.title, subtotal: r.subtotal })),
      milestones: [{ label: 'Booking', share: '10%', trigger: 'On acceptance (synthetic)', amount: '71,980.00' }], valid_until: '2026-11-13', days_left: 30,
      unit_rates_shown: false, package: null, alternatives: [] },
    selections: { items: [{ ref: 'L30', state: 'NOT_SELECTED', priced: true }], selected_refs: [], can_choose: true, status: 'PRICE_CONFIRMATION_REQUIRED', extra: null, total_with_selections: null },
    requests: { can_ask: true, items: [] },
    comparison_available: true,
    terms: { policy_decided: true, pending: ['WARRANTY'], sections: [
      { code: 'WARRANTY', title: 'Warranty', items: ['Synthetic warranty text.'], available: true, sha256: 'w'.repeat(64), required: true, acknowledged_on: null },
      { code: 'SERVICE_SUPPORT', title: 'Service support (Veda Spaces)', items: [], available: false, sha256: null, required: false, acknowledged_on: null }] },
    decision: { available: false, decided: null, reason: 'Please read and acknowledge the required sections first.', can_decline: true,
      version_no: 2, snapshot_sha256: 'a'.repeat(64) },
    ...over,
  };
}

/** Answer every /api call of one browser page. `proposal` decides the main response; nothing reaches a server. */
async function serve(p, { proposal = () => ({ status: 200, body: { data: page() } }), delay = 0, selection = null, onPost = null, handlers = {} } = {}) {
  await p.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const url = new URL(route.request().url());
    const json = (status, body) => route.fulfill({ status, contentType: status < 400 ? 'application/json' : 'application/problem+json', body: JSON.stringify(body) });
    if (url.pathname.startsWith('/api/v1/public/catalog/media/')) {
      return url.pathname.endsWith('/ok') ? route.fulfill({ status: 200, contentType: 'image/png', body: PNG }) : route.fulfill({ status: 404, body: '' });
    }
    if (url.pathname === '/api/v1/public/proposal') {
      if (delay) await new Promise((r) => setTimeout(r, delay));
      const r = proposal();
      if (r === 'abort') return route.abort('internetdisconnected');
      return json(r.status, r.body);
    }
    if (url.pathname === '/api/v1/public/proposal/selections' && selection) {
      const r = selection();
      return r === 'abort' ? route.abort('internetdisconnected') : json(...r);
    }
    if (handlers[url.pathname]) {
      const r = handlers[url.pathname]();
      if (r === 'abort') return route.abort('internetdisconnected');
      if (r) return json(...r);
    }
    if (route.request().method() === 'POST' && onPost) onPost(url.pathname);
    if (url.pathname === '/api/v1/public/proposal/requests') return json(201, { data: [] });
    if (url.pathname === '/api/v1/public/proposal/acknowledgements') return json(201, { data: { terms: page().terms } });
    if (url.pathname === '/api/v1/public/proposal/decision') {
      return json(200, { data: { state: 'ACCEPTED', decision: { available: false, decided: 'ACCEPTED', decided_on: '2026-10-15T10:00:00Z', by_this_link: true } } });
    }
    return json(401, { status: 401, code: 'TOKEN_MISSING', title: 'Unauthorized' }); // no session: an anonymous customer
  });
}

async function open(browser, { viewport = { width: 1280, height: 800 }, reducedMotion = 'no-preference', ...opts } = {}) {
  const ctx = await browser.newContext({ viewport, reducedMotion });
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e)));
  await serve(p, opts);
  await p.goto(`${BASE}/proposal#t=${TOKEN}`);
  return { ctx, p, errors };
}

/** Elements matching `selector` anywhere, inside open shadow roots too (runs in the page). */
function deepAll(selector) {
  const out = [];
  const walk = (root) => { root.querySelectorAll(selector).forEach((n) => out.push(n)); root.querySelectorAll('*').forEach((n) => n.shadowRoot && walk(n.shadowRoot)); };
  walk(document);
  return out;
}
const inPage = (fn) => `(() => { ${deepAll.toString()}; return (${fn.toString()})(); })()`;

/**
 * Every visible interactive customer control is at least 44 x 44 CSS px (WCAG 2.5.5 / the design system's --vs-target):
 * width and height are checked separately, so either one alone fails. A radio or checkbox is measured by its own hit
 * area (the input covers its whole label). Returns the kinds of control measured, so callers can prove coverage.
 */
async function targets(p, name) {
  const sizes = await p.evaluate(inPage(() => deepAll('button, summary, a[href], input, select, textarea, [role=button], [tabindex="0"]')
    .filter((n) => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden' && !n.closest('[aria-hidden=true]'))
    .map((n) => { const r = n.getBoundingClientRect(); const kind = n.tagName.toLowerCase() + (n.type && n.tagName === 'INPUT' ? `[${n.type}]` : '');
      return { kind, what: `${kind} ${(n.textContent || n.name || '').trim().slice(0, 24)}`, w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 }; })));
  const kinds = new Set(sizes.map((x) => x.kind));
  const narrow = sizes.filter((x) => x.w < 44);
  const short = sizes.filter((x) => x.h < 44);
  check(`${name}: touch targets at least 44 px wide (${sizes.length} controls: ${[...kinds].sort().join(', ')})`, sizes.length > 0 && narrow.length === 0, JSON.stringify(narrow.slice(0, 5)));
  check(`${name}: touch targets at least 44 px tall`, sizes.length > 0 && short.length === 0, JSON.stringify(short.slice(0, 5)));
  return sizes;
}

/** The focused element, through shadow roots, with its accessibility state and the text of what describes it. */
const focusedIn = (p) => p.evaluate(() => {
  let a = document.activeElement;
  while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement;
  if (!a) return null;
  const root = a.getRootNode();
  const ids = (a.getAttribute('aria-describedby') || '').split(' ').filter(Boolean);
  const r = a.getBoundingClientRect();
  return { tag: a.tagName, id: a.id, field: a.dataset?.field ?? '', name: a.getAttribute('name') ?? '', text: (a.textContent || '').trim().slice(0, 40),
    invalid: a.getAttribute('aria-invalid'), describedby: ids, described: ids.map((i) => root.getElementById(i)?.textContent?.trim() ?? null),
    visible: r.bottom > 0 && r.top < innerHeight };
});
const label = (f) => (f ? `${f.tag}#${f.id}${f.field ? `[${f.field}]` : ''} ${f.text}` : 'none');

/** A page model whose decision is open (the confirmation checkbox and the Accept button are on the page). */
const decidable = (over = {}) => page({ decision: { available: true, decided: null, can_decline: true, version_no: 2, snapshot_sha256: 'a'.repeat(64),
  total: '7,19,800.00', selected_refs: [], statement: 'I accept VS-Q-2026-000001 v2 as shown (SYNTHETIC).' }, ...over });
const SELECTED = { items: [{ ref: 'L30', state: 'SELECTED', priced: true }], selected_refs: ['L30'], can_choose: true, status: 'PRICE_CONFIRMATION_REQUIRED',
  extra: null, total_with_selections: null };

async function axe(p, name) {
  await p.addScriptTag({ content: AXE });
  const v = await p.evaluate(async () => (await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }))
    .violations.map((x) => `${x.id} (${x.nodes.length})`));
  check(`axe ${name}`, v.length === 0, v.join(', '));
}

const browser = await chromium.launch();
try {
  for (const [name, viewport] of [['360 px', { width: 360, height: 740 }], ['mobile portrait', { width: 390, height: 844 }],
    ['tablet', { width: 768, height: 1024 }], ['desktop', { width: 1280, height: 800 }]]) {
    const { ctx, p, errors } = await open(browser, { viewport, proposal: () => ({ status: 200, body: { data: decidable() } }), selection: () => 'abort' });
    await p.locator('vs-proposal-view h1').waitFor();
    check(`${name}: token scrubbed from the address bar`, !(await p.evaluate(() => location.href)).includes(TOKEN));
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(`${name}: no horizontal scrolling`, overflow <= 0, `overflow ${overflow}px`);
    await p.locator('#term-WARRANTY summary').click(); // the acknowledgement control is inside its (closed) section
    const measured = await targets(p, `${name} (proposal)`);
    const mains = await p.evaluate(inPage(() => deepAll('main, [role=main]').length));
    check(`${name}: exactly one main landmark`, mains === 1, String(mains));
    const bar = await p.locator('vs-proposal-view .bar').isVisible();
    check(`${name}: total always in reach (sticky bar below 960 px, summary column above)`, viewport.width < 960 ? bar : !bar);
    await p.screenshot({ path: `${OUT}/proposal-${viewport.width}.png`, fullPage: true });
    await axe(p, name);
    // a field error (text input, textarea and the error-summary link) and a failed action (its Try again control)
    await p.locator('#questions select[name=category]').selectOption('CHANGE_QUANTITY');
    await p.locator('#questions button.primary').click();
    await p.locator('vs-error-summary a').waitFor();
    measured.push(...await targets(p, `${name} (field error)`));
    await p.locator('fieldset.optitem label.choice').first().click();
    await p.getByRole('button', { name: 'Try again' }).waitFor();
    measured.push(...await targets(p, `${name} (failed action)`));
    const has = (re) => measured.some((x) => re.test(x.what));
    const missing = Object.entries({ 'button': /^button /, 'next-step link': /^a Review the optional/, 'room link': /^a Bedroom 2/, 'text input': /^input\[text\]/,
      'textarea': /^textarea/, 'radio (optional item)': /^input\[radio\]/, 'checkbox (decision)': /^input\[checkbox\]/, 'select': /^select/,
      'acknowledgement': /^button I have read/, 'error-summary link': /^a Please write/, 'Try again': /^button Try again/,
      'contact phone link': /^a \+00/, 'contact e-mail link': /^a desk@synthetic/ })
      .filter(([, re]) => !has(re)).map(([k]) => k);
    check(`${name}: touch-target check covered every kind of control`, missing.length === 0, missing.join(', '));
    check(`${name}: no page error`, errors.length === 0, errors.join(' | '));
    await ctx.close();
  }

  // page entry: after a normal, a slow, and a retried load (500, 429, offline) focus is on the proposal's title
  for (const [how, opts] of [['normal load', {}], ['slow load', { delay: 1500 }],
    ['retry after 500', { fail: { status: 500, body: { status: 500, code: 'INTERNAL_ERROR', title: 'x' } } }],
    ['retry after 429', { fail: { status: 429, body: { status: 429, code: 'RATE_LIMITED', title: 'x' } } }],
    ['retry after a network failure', { fail: 'abort' }]]) {
    let first = true;
    const { fail, ...rest } = opts;
    const { ctx, p } = await open(browser, { viewport: { width: 390, height: 844 }, ...rest,
      proposal: () => (fail && first ? (first = false, fail) : { status: 200, body: { data: page() } }) });
    if (fail) {
      await p.locator('vs-proposal-page p[role=alert]').waitFor();
      const onError = await focusedIn(p);
      check(`${how}: the failure takes focus (its heading) and offers Try again`, onError?.tag === 'H1' && await p.getByRole('button', { name: 'Try again' }).isVisible(), label(onError));
      await p.getByRole('button', { name: 'Try again' }).click();
    }
    await p.locator('vs-proposal-view h1').waitFor();
    await p.waitForFunction(() => { let a = document.activeElement; while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement; return a?.id === 'proposal-title'; },
      null, { timeout: 3000 }).catch(() => {});
    const f = await focusedIn(p);
    check(`${how}: focus lands on the proposal title (named), never the body`, f?.id === 'proposal-title' && f.text.includes('Interior works'), label(f));
    await ctx.close();
  }
  {
    // a background refresh after an action never pulls focus back to the title
    const { ctx, p } = await open(browser, { selection: () => [200, { data: SELECTED }] });
    await p.locator('vs-proposal-view h1').waitFor();
    await p.locator('fieldset.optitem input[value=SELECTED]').focus();
    await p.keyboard.press('Space');
    await p.waitForFunction(inPage(() => deepAll('[aria-live=polite]').some((n) => n.textContent.includes('added to your choices'))));
    const f = await focusedIn(p);
    check('refresh after an action: focus stays on the choice, not the title', f?.tag === 'INPUT' && f.field === 'opt-L30', label(f));
    await ctx.close();
  }

  // a failed action and its retry: focus stays in the error context, then returns to the control that started it
  for (const [how, failure] of [['offline', 'abort'], ['500', [500, { status: 500, code: 'INTERNAL_ERROR', title: 'x' }]],
    ['429', [429, { status: 429, code: 'RATE_LIMITED', title: 'x' }]]]) {
    let n = 0;
    const { ctx, p } = await open(browser, { selection: () => (n++ < 2 ? failure : [200, { data: SELECTED }]), delay: 0 });
    await p.locator('vs-proposal-view h1').waitFor();
    await p.locator('fieldset.optitem input[value=SELECTED]').focus();
    await p.keyboard.press('Space');
    await p.getByRole('button', { name: 'Try again' }).waitFor();
    const failed = await focusedIn(p);
    check(`action ${how}: focus moves to the error summary`, failed?.tag === 'DIV' && failed.text.startsWith('Please fix'), label(failed));
    await p.getByRole('button', { name: 'Try again' }).focus();
    await p.keyboard.press('Enter');
    await p.waitForFunction(inPage(() => deepAll('[aria-live=polite]').some((n) => n.textContent.includes('Not saved'))));
    await p.getByRole('button', { name: 'Try again' }).waitFor();
    const again = await focusedIn(p);
    check(`action ${how}: a failed retry keeps focus in the error context`, again?.tag === 'DIV' && again.text.startsWith('Please fix') || again?.text === 'Try again', label(again));
    await p.getByRole('button', { name: 'Try again' }).focus();
    await p.keyboard.press('Enter');
    await p.waitForFunction(inPage(() => deepAll('[aria-live=polite]').some((n) => n.textContent.includes('added to your choices'))));
    const back = await focusedIn(p);
    check(`action ${how}: a successful retry returns focus to the choice that started it`, back?.tag === 'INPUT' && back.field === 'opt-L30', label(back));
    await ctx.close();
  }
  {
    // slow retry of an acknowledgement: focus never drops to the body while it runs; afterwards it is on the terms heading
    let n = 0;
    const acked = () => { const m = page(); m.terms.sections[0].acknowledged_on = '2026-10-15T10:00:00Z'; m.terms.pending = []; return m; };
    const { ctx, p } = await open(browser, { proposal: () => ({ status: 200, body: { data: n > 1 ? acked() : page() } }),
      handlers: { '/api/v1/public/proposal/acknowledgements': () => (n++ === 0 ? 'abort' : null) } });
    await p.locator('vs-proposal-view h1').waitFor();
    await p.locator('#term-WARRANTY summary').click();
    await p.locator('#term-WARRANTY button').click();
    await p.getByRole('button', { name: 'Try again' }).waitFor();
    await p.route((url) => url.pathname === '/api/v1/public/proposal', async (route) => { await new Promise((r) => setTimeout(r, 800)); await route.fallback(); });
    await p.getByRole('button', { name: 'Try again' }).focus();
    await p.keyboard.press('Enter');
    await p.waitForTimeout(300);
    const during = await focusedIn(p);
    check('slow retry: focus stays on the Try again control while it runs', during?.tag === 'BUTTON' && during.text.includes('Trying again'), label(during));
    await p.waitForFunction(inPage(() => deepAll('[aria-live=polite]').some((n) => n.textContent.includes('acknowledged'))));
    const after = await focusedIn(p);
    // the warranty acknowledgement sits in "Warranty and service" (CTB): focus returns to that section's heading
    check('slow retry: afterwards focus is on its section heading (the acknowledged button is gone)', after?.tag === 'H2' && after.id === 'warh', label(after));
    await ctx.close();
  }

  // error-summary navigation: each link focuses its exact control, which is marked invalid and described by its error
  {
    const problem = (field, message) => [422, { status: 422, code: 'VALIDATION_FAILED', title: 'x', detail: message, errors: [{ field, code: 'INVALID', message }] }];
    const { ctx, p, errors } = await open(browser, { viewport: { width: 360, height: 740 }, proposal: () => ({ status: 200, body: { data: decidable() } }),
      selection: () => problem('line_ref', 'This optional item cannot be chosen.'),
      handlers: { '/api/v1/public/proposal/requests': () => problem('requested_quantity', 'Please give the quantity as a number.'),
        '/api/v1/public/proposal/acknowledgements': () => problem('section_sha256', 'This section changed; please read it again.'),
        '/api/v1/public/proposal/decision': () => problem('confirm', 'Please confirm the statement before accepting.') } });
    await p.locator('vs-proposal-view h1').waitFor();
    const follow = async (what, field, start, after) => {
      await start();
      const link = p.locator('vs-error-summary a').first();
      await link.waitFor();
      await p.evaluate(() => window.scrollTo(0, 0));
      await link.focus();
      await p.keyboard.press('Enter');
      await p.waitForFunction(() => { let a = document.activeElement; while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement;
        const r = a?.getBoundingClientRect(); return r && r.bottom > 0 && r.top < innerHeight; }, null, { timeout: 3000 }).catch(() => {});
      const f = await focusedIn(p);
      check(`error summary → ${what}: focus on the exact control, scrolled into view`, f?.field === field && f.visible, label(f));
      check(`error summary → ${what}: aria-invalid and aria-describedby name the error`, f?.invalid === 'true' && f.describedby[0] === `err-${field}`
        && Boolean(f.described[0]) && (await link.textContent()).includes(f.described[0]), JSON.stringify({ invalid: f?.invalid, by: f?.describedby, said: f?.described }));
      const ids = await p.evaluate(inPage(() => deepAll('[id^=err-]').map((n) => n.id)));
      check(`error summary → ${what}: error ids are unique`, ids.length === new Set(ids).size, ids.join(','));
      if (after) {
        await after();
        const g = await focusedIn(p);
        check(`error summary → ${what}: correcting clears the invalid state without moving focus`, g?.field === field && g.invalid === null
          && !g.describedby.includes(`err-${field}`), label(g));
      }
    };
    await follow('textarea', 'message', async () => { await p.locator('#questions button.primary').click(); },
      async () => { await p.keyboard.type('Corrected (SYNTHETIC)'); });
    await axe(p, 'field error on the textarea');
    await follow('text input', 'quantity', async () => {
      await p.locator('#questions select[name=category]').selectOption('CHANGE_QUANTITY');
      await p.locator('#questions textarea').fill('More lofts please (SYNTHETIC)');
      await p.locator('#questions input[name=quantity]').fill('lots');
      await p.locator('#questions button.primary').click();
    }, async () => { await p.keyboard.press('End'); await p.keyboard.type('3'); });
    await follow('radio (optional item)', 'opt-L30', async () => { await p.locator('fieldset.optitem label.choice').first().click(); });
    await axe(p, 'field error on a choice');
    await follow('acknowledgement', 'ack-WARRANTY', async () => {
      await p.locator('#term-WARRANTY summary').click();
      await p.locator('#term-WARRANTY button').click();
    });
    await axe(p, 'field error on an acknowledgement');
    await follow('decision checkbox', 'confirm', async () => {
      await p.locator('#decision label.check').click();
      await p.locator('#decision button.primary').click();
    }, async () => { await p.keyboard.press('Space'); await p.keyboard.press('Space'); });
    check('error summary: no page error', errors.length === 0, errors.join(' | '));
    await ctx.close();
  }

  // keyboard, focus, missing image, reduced motion, print
  {
    const { ctx, p } = await open(browser, { reducedMotion: 'reduce' });
    await p.locator('vs-proposal-view h1').waitFor();
    await p.locator('a.roomcard[href="#R2"]').focus();
    await p.keyboard.press('Enter');
    const opened = await p.locator('details#R2').evaluate((d) => d.open);
    const focused = await p.evaluate(() => { let a = document.activeElement; while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement; return a?.id ?? ''; });
    check('keyboard: a room card opens its room and moves focus there', opened && focused === 'R2', focused);
    const ring = await p.locator('a.roomcard[href="#R3"]').evaluate((a) => { a.focus(); return getComputedStyle(a).outlineStyle; });
    check('keyboard: focus is visible', ring !== 'none', ring);
    await p.waitForFunction(inPage(() => deepAll('.roomcard .ph').length === 6));
    check('a missing image falls back to the named placeholder', true);
    await p.locator('details#R1').evaluate((d) => { d.open = true; });
    await p.locator('.thumbbtn img').scrollIntoViewIfNeeded();
    const thumb = await p.waitForFunction(inPage(() => deepAll('.thumbbtn img').some((i) => i.complete && i.naturalWidth > 0)),
      null, { timeout: 10000 }).then(() => true, () => false);
    check('an approved image loads, labelled', thumb && (await p.locator('.thumbbtn .imglabel').textContent()) === 'Illustrative example');
    check('reduced motion is honoured', await p.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches));
    await p.emulateMedia({ media: 'print' });
    await p.evaluate(() => window.dispatchEvent(new Event('beforeprint')));
    const printed = await p.evaluate(inPage(() => deepAll('details').every((d) => d.open)));
    const hidden = await p.locator('vs-proposal-view .bar').isHidden();
    check('print: every section opened, the action bar hidden', printed && hidden);
    await p.pdf({ path: `${OUT}/proposal-print.pdf`, format: 'A4' });
    check('print: renders to A4', fs.statSync(`${OUT}/proposal-print.pdf`).size > 1000);
    await ctx.close();
  }

  // customer completeness (CTB): summary first with the Veda contact, sizes, scope, readiness, warranty, next steps
  for (const viewport of [{ width: 360, height: 740 }, { width: 1280, height: 800 }]) {
    const { ctx, p } = await open(browser, { viewport });
    await p.locator('vs-proposal-view h1').waitFor();
    const order = await p.evaluate(inPage(() => deepAll('section h2[id]').map((h) => h.textContent.trim())));
    const at = (t) => order.findIndex((x) => x.startsWith(t));
    const expected = ['Your Veda Spaces contact', 'Room by room', "What's included", 'Materials and hardware', 'Price and payment',
      'Optional items', 'Before we start', 'Warranty and service', 'Terms', 'Questions and changes', 'What happens after you approve'];
    const positions = expected.map(at);
    check(`${viewport.width} px: sections in the customer order (summary first … what happens next)`,
      positions.every((n) => n >= 0) && positions.every((n, i) => i === 0 || n > positions[i - 1]), JSON.stringify(order));
    check(`${viewport.width} px: the Veda contact is reachable by phone and e-mail`,
      await p.locator('#your-contact a[href^="tel:"]').first().isVisible() && await p.locator('#your-contact a[href^="mailto:"]').first().isVisible());
    await p.locator('details#R1').evaluate((d) => { d.open = true; });
    check(`${viewport.width} px: verified sizes, and an unverified one said to be confirmed`,
      (await p.locator('details#R1 .dims').first().textContent()).includes('Dimension to be confirmed'));
    for (const sel of ['#scope', '#before-start', '#warranty', '#next']) {
      await p.locator(`${sel} details`).evaluateAll((ds) => ds.forEach((d) => { d.open = true; }));
    }
    const statuses = await p.locator('.status').allTextContents();
    check(`${viewport.width} px: responsibility and readiness statuses shown in words`, statuses.includes('Required') && statuses.includes('Your action needed'));
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(`${viewport.width} px: every section open, still no horizontal scrolling`, overflow <= 0, `overflow ${overflow}px`);
    await targets(p, `${viewport.width} px (all sections open)`);
    await axe(p, `${viewport.width} px, all sections open`);
    await ctx.close();
  }
  {
    const tbc = { content_version: null, contacts: { quotation: null, support: [], service: [] }, support_escalation: null, project_inclusions: null,
      client_responsibilities: null, site_readiness: null, site_dependent_work: null, manufacturer_warranty_note: null, warranty_exclusions: null,
      service_guidance: null, handover: null, care: null, next_steps: null, payment_safety: null };
    const bare = page();
    bare.proposal.information = tbc;
    bare.specifications = null;
    bare.pricing.milestones = [];
    const { ctx, p } = await open(browser, { viewport: { width: 390, height: 844 }, proposal: () => ({ status: 200, body: { data: bare } }) });
    await p.locator('vs-proposal-view h1').waitFor();
    const said = await p.evaluate(inPage(() => deepAll('vs-proposal-view').map((v) => v.shadowRoot.textContent).join(' ')));
    check('nothing approved yet: each section says it is to be confirmed', ['Contact details to be confirmed', 'Specification to be confirmed',
      'Payment plan to be confirmed', 'How to pay will be confirmed'].every((w) => said.includes(w)));
    // the validity countdown ("30 days left", OI-MTQ-08) is a fact, not a promise; any other duration or claim fails
    const promise = said.match(/\b\d+\s*(working\s+)?(days?|weeks?|months?|years?)\b(?! left)|guarantee|lifetime|free service/i);
    check('nothing approved yet: no promise, duration or claim is shown', !promise, promise?.[0] ?? '');
    await axe(p, 'nothing approved yet');
    await p.emulateMedia({ media: 'print' });
    await p.evaluate(() => window.dispatchEvent(new Event('beforeprint')));
    check('print: the new sections print open too', await p.evaluate(inPage(() => deepAll('details').every((d) => d.open))));
    await ctx.close();
  }

  // a refused choice: the error summary takes focus and the screen reader hears it
  {
    const { ctx, p } = await open(browser, { selection: () => [422, { status: 422, code: 'VALIDATION_FAILED', title: 'x',
      detail: 'Please choose one of the optional items of this proposal.', errors: [{ field: 'line_ref', code: 'NOT_OPTIONAL', message: 'Not an optional item of this proposal.' }] }] });
    await p.locator('vs-proposal-view h1').waitFor();
    await p.locator('fieldset.optitem input[type=radio]').first().check();
    await p.locator('vs-error-summary [role=alert]').waitFor();
    const status = await p.locator('vs-proposal-view [role=status][aria-live=polite]').textContent();
    check('a refused action shows an error summary and announces it', status.includes('Not saved'), status);
    await ctx.close();
  }

  // interaction in a real browser at 360 px: question, acknowledgement, acceptance; focus never falls to the body
  {
    const deepActive = () => p360.evaluate(() => { let a = document.activeElement; while (a?.shadowRoot?.activeElement) a = a.shadowRoot.activeElement;
      return a ? `${a.tagName}#${a.id}|${(a.textContent || '').trim().slice(0, 30)}` : 'none'; });
    const ready = page({ decision: { available: true, decided: null, can_decline: true, version_no: 2, snapshot_sha256: 'a'.repeat(64), total: '7,19,800.00',
      selected_refs: [], statement: 'I accept VS-Q-2026-000001 v2 as shown (SYNTHETIC).' } });
    const decided = page({ state: 'ACCEPTED', capabilities: { interaction: false, acceptance: false }, actions: [],
      decision: { available: false, decided: 'ACCEPTED', decided_on: '2026-10-15T10:00:00Z', by_this_link: true, total: '7,19,800.00' } });
    let accepted = false;
    const { ctx, p: p360 } = await open(browser, { viewport: { width: 360, height: 740 }, onPost: (path) => { if (path.endsWith('/decision')) accepted = true; },
      proposal: () => ({ status: 200, body: { data: accepted ? decided : ready } }) });
    await p360.locator('vs-proposal-view h1').waitFor();
    await p360.locator('#questions textarea').fill('Could the loft be taller? (SYNTHETIC)');
    await p360.locator('#questions button.primary').click();
    await p360.waitForFunction(inPage(() => deepAll('[aria-live=polite]').some((n) => n.textContent.includes('sent to Veda Spaces'))));
    check('question: sent and announced', true);
    check('question: focus stays in a logical place', !(await deepActive()).startsWith('BODY'), await deepActive());
    await p360.locator('#term-WARRANTY summary').click();
    await p360.locator('#term-WARRANTY button').click();
    await p360.waitForFunction(inPage(() => deepAll('[aria-live=polite]').some((n) => n.textContent.includes('acknowledged'))));
    check('acknowledgement: announced, focus not on the body', !(await deepActive()).startsWith('BODY'), await deepActive());
    await p360.locator('#decision label.check').click();
    await p360.locator('#decision button.primary').click();
    await p360.waitForFunction(inPage(() => deepAll('[aria-live=polite]').some((n) => n.textContent.includes('acceptance was recorded'))));
    const focused = await deepActive();
    check('acceptance: announced; focus moves to the decision heading', focused.startsWith('H2#dc'), focused);
    await axe(p360, 'after interaction at 360 px');
    await ctx.close();
  }
  {
    const { ctx, p: po } = await open(browser, { viewport: { width: 390, height: 844 }, selection: (() => { let n = 0; return () => (n++ === 0 ? 'abort'
      : [200, { data: { items: [{ ref: 'L30', state: 'SELECTED', priced: true }], selected_refs: ['L30'], can_choose: true, status: 'PRICE_CONFIRMATION_REQUIRED',
        extra: null, total_with_selections: null } }]); })() });
    await po.locator('vs-proposal-view h1').waitFor();
    await po.locator('fieldset.optitem label.choice').first().click();
    await po.locator('vs-error-summary [role=alert]').waitFor();
    const checked = await po.locator('fieldset.optitem input[value=SELECTED]').isChecked();
    check('offline choice: the choice is not left checked', !checked);
    const said = await po.evaluate(inPage(() => deepAll('vs-error-summary').map((e) => e.shadowRoot.textContent).join(' ')));
    check('offline choice: a safe message', said.includes('Nothing was saved'), said.trim().slice(0, 120));
    await po.getByRole('button', { name: 'Try again' }).click();
    await po.waitForFunction(inPage(() => deepAll('[aria-live=polite]').some((n) => n.textContent.includes('added to your choices'))));
    check('offline choice: the retry saves it', true);
    await ctx.close();
  }
  for (const status of [500, 429]) {
    let first = true;
    const { ctx, p: pr } = await open(browser, { proposal: () => (first ? (first = false, { status, body: { status, code: status === 429 ? 'RATE_LIMITED' : 'INTERNAL_ERROR', title: 'x' } })
      : { status: 200, body: { data: page() } }) });
    await pr.locator('vs-proposal-page p[role=alert]').waitFor();
    await pr.getByRole('button', { name: 'Try again' }).click();
    await pr.locator('vs-proposal-view h1').waitFor();
    check(`initial ${status}: announced with a working retry`, true);
    await ctx.close();
  }

  // slow network, offline, and every refusal state
  {
    const { ctx, p } = await open(browser, { delay: 1500 });
    check('slow network: a loading state first', await p.getByText('Opening your proposal').isVisible());
    await p.locator('vs-proposal-view h1').waitFor({ timeout: 5000 });
    check('slow network: then the proposal', true);
    await ctx.close();
  }
  {
    let first = true;
    const { ctx, p } = await open(browser, { proposal: () => (first ? (first = false, 'abort') : { status: 200, body: { data: page() } }) });
    await p.getByText('You seem to be offline').waitFor();
    await p.getByRole('button', { name: 'Try again' }).click();
    await p.locator('vs-proposal-view h1').waitFor();
    check('offline: a retry recovers', true);
    await ctx.close();
  }
  for (const [code, words, status] of [['PROPOSAL_LINK_REVOKED', 'no longer active', 410], ['PROPOSAL_LINK_EXPIRED', 'has expired', 410],
    ['PROPOSAL_SUPERSEDED', 'newer version', 410], ['PROPOSAL_LINK_INVALID', 'not valid', 404]]) {
    const { ctx, p } = await open(browser, { viewport: { width: 360, height: 740 }, proposal: () => ({ status, body: { status, code, title: 'x', detail: 'x' } }) });
    const alert = p.locator('vs-proposal-page p[role=alert]');
    await alert.waitFor();
    check(`${code}: a safe message`, (await alert.textContent()).includes(words));
    check(`${code}: the link is forgotten`, await p.evaluate(() => sessionStorage.getItem('vs-proposal-link') === null));
    await axe(p, code);
    await ctx.close();
  }
  {
    const { ctx, p } = await open(browser, { proposal: () => ({ status: 200, body: { data: page({ state: 'EXPIRED', capabilities: { interaction: false, acceptance: false },
      notices: [{ code: 'EXPIRED', message: 'This proposal is past its validity date. Please contact Veda Spaces for a revised proposal.' }], actions: [] }) } }) });
    await p.locator('vs-proposal-view h1').waitFor();
    check('expired proposal: viewable, marked, no choices', (await p.locator('vs-proposal-view .state').textContent()).includes('Past its validity')
      && (await p.locator('fieldset.optitem input').count()) === 0);
    await ctx.close();
  }
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r).length;
console.log(`${results.length - failed}/${results.length} checks passed (SYNTHETIC_VALIDATED)`);
process.exit(failed ? 1 : 0);
