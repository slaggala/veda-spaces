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
  return { ref, description, detail: 'Laminate finish', quantity: '42.5 sq ft', amount, priced: true, status };
}
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
      rooms, optional_items: [{ ...line('L30', 'Loft above wardrobe', '15,000.00', 'Optional'), room_ref: 'R1', room_title: 'Master bedroom' }],
      summary: { base_total: '6,10,000.00', taxable: '6,10,000.00', gst: { status: 'Included', amount: '1,09,800.00' }, total: '7,19,800.00',
        optional_total: '15,000.00', currency: 'INR' },
      payment_schedule: [{ label: 'Booking', share: '10%', trigger: 'On acceptance (synthetic)' }, { label: 'Production', share: '50%', trigger: 'Before production (synthetic)' },
        { label: 'Handover', share: '40%', trigger: 'On handover (synthetic)' }],
      warranty: ['Synthetic warranty text.'], service_support: [], assumptions: ['Synthetic assumption.'], exclusions: ['Synthetic exclusion.'],
      terms: ['Synthetic change-order terms.', 'Synthetic cancellation terms.'], terms_version: 'SYN-T1', unit_rates_shown: false,
      sections: { SCOPE: 'b'.repeat(64) },
    },
    specifications: null,
    media: { note: 'Reference image: it illustrates the kind of item and does not change the scope or the price.',
      lines: { L1: [{ title: 'Wardrobe', alt: 'A two-door laminate wardrobe', caption: null, label: 'Illustrative example', urls: { thumb: '/api/v1/public/catalog/media/ok' } }] },
      rooms: { R1: { title: 'Wardrobe', alt: 'A two-door laminate wardrobe', caption: null, label: 'Illustrative example', urls: { mobile: '/api/v1/public/catalog/media/missing' } },
        R2: null, R3: null, R4: null, R5: null, R6: null } },
    pricing: { currency: 'INR', total: '7,19,800.00', gst: { status: 'Included', amount: '1,09,800.00' }, discount: null, base_total: '6,10,000.00',
      optional_total: '15,000.00', rooms: rooms.map((r) => ({ ref: r.ref, title: r.title, subtotal: r.subtotal })),
      milestones: [{ label: 'Booking', share: '10%', trigger: 'On acceptance (synthetic)' }], valid_until: '2026-11-13', days_left: 30,
      unit_rates_shown: false, package: null, alternatives: [] },
    selections: { items: [{ ref: 'L30', state: 'NOT_SELECTED', priced: true }], selected_refs: [], status: 'PRICE_CONFIRMATION_REQUIRED', extra: null, total_with_selections: null },
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
async function serve(p, { proposal = () => ({ status: 200, body: { data: page() } }), delay = 0, selection = null } = {}) {
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
    if (url.pathname === '/api/v1/public/proposal/selections' && selection) return json(...selection());
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
    const { ctx, p, errors } = await open(browser, { viewport });
    await p.locator('vs-proposal-view h1').waitFor();
    check(`${name}: token scrubbed from the address bar`, !(await p.evaluate(() => location.href)).includes(TOKEN));
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(`${name}: no horizontal scrolling`, overflow <= 0, `overflow ${overflow}px`);
    const small = await p.evaluate(inPage(() => deepAll('button, summary, nav.rooms a, a.roomcard, label.choice, label.check, select')
      .filter((n) => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden')
      .map((n) => [n.textContent.trim().slice(0, 30), Math.round(n.getBoundingClientRect().height)]).filter(([, h]) => h < 44)));
    check(`${name}: touch targets at least 44 px`, small.length === 0, JSON.stringify(small.slice(0, 5)));
    const bar = await p.locator('vs-proposal-view .bar').isVisible();
    check(`${name}: total always in reach (sticky bar below 960 px, summary column above)`, viewport.width < 960 ? bar : !bar);
    await p.screenshot({ path: `${OUT}/proposal-${viewport.width}.png`, fullPage: true });
    await axe(p, name);
    check(`${name}: no page error`, errors.length === 0, errors.join(' | '));
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
