// Catalog-driven estimator V3 (ADR-013) against the real API with the SYNTHETIC slice (api/tools/e2e_catalog.py),
// under the site's Content-Security-Policy (images allowed from the local API on /estimate-v3 only).
//   SITE_ON=http://localhost:8000 node e2e/estimator-v3.e2e.mjs
// Checks: rooms, finishes and extras come from the catalog; images carry their labels; "What is this?" explains;
// the gallery opens; the 3D view shows its preview first and falls back to the gallery (no renderer is vendored);
// the estimate is created from the configuration, changes with storage and extras, refines with measurements, and
// the browser never receives a rate; no CSP violation, no page error, no axe violation.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const ON = process.env.SITE_ON ?? 'http://localhost:8000';
const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`); };
// An asynchronous Turnstile stand-in that behaves like the real widget: render() returns at once, the token arrives
// later through the callback, and it may expire, fail first, be empty, be redelivered after use, differ from what
// getResponse() reports, or be one the server refuses (prefix "fail"). Behaviour is read from window.__tsConfig at each
// issue, so a test can change it mid-flow. No scenario gets an instant token.
const TURNSTILE_STUB = `(() => {
  const cfg = () => Object.assign({ delay: 700, expireAfter: 0, expireOnce: true, errorFirst: false, prefix: 'stub',
    empty: false, repeat: false, mismatch: false }, window.__tsConfig || {});
  let n = 0; const w = {};
  function issue(id) {
    const o = w[id]; clearTimeout(o.t); clearTimeout(o.e); const last = o.token || o.last; o.token = '';
    o.t = setTimeout(() => {
      const c = cfg();
      if (c.errorFirst && !o.errored) { o.errored = true; o.opts['error-callback'] && o.opts['error-callback'](); return; }
      if (c.empty) { o.opts.callback && o.opts.callback(''); return; }
      o.token = c.repeat && last ? last : c.prefix + '-' + (++n); o.last = o.token; o.opts.callback && o.opts.callback(o.token);
      if (c.expireAfter && !(c.expireOnce && o.expired)) o.e = setTimeout(() => { o.expired = true; o.token = ''; o.opts['expired-callback'] && o.opts['expired-callback'](); }, c.expireAfter);
    }, cfg().delay);
  }
  // A test can expire every live token at an exact moment (for example while a request is in flight).
  window.__tsExpire = () => Object.values(w).forEach((o) => { clearTimeout(o.e); o.token = ''; o.opts['expired-callback'] && o.opts['expired-callback'](); });
  window.__tsReissue = () => Object.keys(w).forEach(issue);
  window.turnstile = { render(sel, opts) { const id = 'w' + (++n); w[id] = { opts }; issue(id); return id; },
    reset(id) { if (w[id]) issue(id); },
    getResponse(id) { const t = (w[id] && w[id].token) || ''; return t && cfg().mismatch ? t + '-other' : t; }, remove() {} };
})();`;

// The estimate route keeps its production rate limit (10 a minute per network); the journey paces itself under it.
const postTimes = [];
const watchPosts = (target) => target.on('request', (r) => { if (r.method() === 'POST' && r.url().endsWith('/api/v1/public/catalog/estimates')) postTimes.push(Date.now()); });
async function pace(next) {
  for (;;) {
    const recent = postTimes.filter((at) => Date.now() - at < 61000);
    if (recent.length + next <= 9) return;
    await new Promise((r) => setTimeout(r, 61000 - (Date.now() - Math.min(...recent))));
  }
}
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 390, height: 860 } });
await context.addInitScript(() => {
  window.__csp = [];
  document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI}`));
});
await context.route('https://challenges.cloudflare.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/javascript', body: TURNSTILE_STUB }));
const page = await context.newPage();
watchPosts(page);
const errors = [];
const bodies = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('response', async (r) => { if (r.url().includes('/api/v1/public/catalog') && !r.url().includes('/media/')) bodies.push(await r.text().catch(() => '')); });
const shot = async (name) => { if (process.env.E2E_OUT) await page.screenshot({ path: path.join(process.env.E2E_OUT, `estimator-v3-${name}.png`), fullPage: true }); };
async function axe(name) {
  await page.evaluate(AXE);
  const v = await page.evaluate(async () => {
    const res = await window.axe.run(document.querySelector('main'), { preload: false, runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } });
    return res.violations.map((x) => `${x.id}: ${x.nodes.map((n) => n.target.join(' ')).join(', ')}`);
  });
  check(`axe: ${name}`, v.length === 0, v.join('; '));
}
const ready = (pg, button = '#v3-estimate') => pg.waitForSelector(`${button}[aria-disabled="false"]`, { timeout: 15000 });
async function estimate(trigger, button = '#v3-estimate') {
  await ready(page, button);
  const res = page.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
  await trigger();
  const r = await res;
  return { status: r.status(), body: await r.json() };
}

try {
  await page.goto(`${ON}/estimate-v3`);
  await page.waitForSelector('#v3:not([hidden])', { timeout: 15000 });
  check('the V3 page loads the active catalog', await page.locator('#v3-homes input').count() >= 1);
  await axe('home');
  await page.click('#v3-to-rooms');
  await page.waitForSelector('[data-v3="2"]:not([hidden])');
  check('the living room card comes from the catalog', await page.locator('.v3-room h3', { hasText: 'Living room' }).count() === 1);
  check('the TV unit and its laminate finish are offered', await page.locator('.v3-product h4', { hasText: 'TV unit' }).count() === 1
    && await page.locator('input[value="laminate"]').isChecked());
  check('veneer is consultation-only: shown, not selectable, routed to a consultation',
    await page.locator('input[value="veneer"]').isDisabled() && await page.locator('.v3-consult[href="/#contact"]').count() >= 1);
  check('soft-close storage is not offered (blocked)', await page.locator('text=Soft-close').count() === 0);
  await page.waitForFunction(() => [...document.querySelectorAll('#v3-rooms img')].length > 0
    && [...document.querySelectorAll('#v3-rooms img')].every((i) => i.complete), null, { timeout: 15000 });
  const images = await page.evaluate(() => [...document.querySelectorAll('#v3-rooms img')].map((i) => ({
    src: i.currentSrc || i.src, loaded: i.complete && i.naturalWidth > 0, alt: i.getAttribute('alt') })));
  check('catalog images really load (each decoded, from a hashed delivery path, with alt text)', images.length >= 2
    && images.every((i) => i.loaded && /\/api\/v1\/public\/catalog\/media\/[0-9a-f]{64}$/.test(i.src) && i.alt),
    JSON.stringify(images.filter((i) => !i.loaded).map((i) => i.src)));
  check('images are labelled as illustrative', await page.locator('.v3-badge', { hasText: 'Illustrative example' }).count() > 0);
  await page.locator('.v3-extra summary', { hasText: 'What is this?' }).first().click();
  check('“What is this?” explains an extra', (await page.locator('.v3-extra details[open] p').first().innerText()).length > 10);
  await page.click('text=See examples');
  check('the gallery opens as a dialog', await page.locator('#v3-gallery[open] img').count() >= 2);
  await page.click('#v3-gallery-close');
  check('3D is unavailable by default: no 3D control, the gallery remains', await page.locator('text=View in 3D').count() === 0
    && await page.locator('text=See examples').count() >= 1);
  await axe('rooms');
  await shot('rooms');

  const base = await estimate(() => page.click('#v3-estimate'));
  check('an estimate from the default configuration', base.status === 201 && /^C[0-9A-Z]{8}$/.test(base.body.data.configuration_reference), String(base.status));
  await page.waitForSelector('[data-v3="3"]:not([hidden])');
  const shown = await page.locator('#v3-result').innerText();
  const d = base.body.data;
  const expected = [d.configuration_reference, d.catalog_release, `GST at ${d.gst.pct}%`, 'Site Execution & Handover Package',
    'Design Personalisation Allowance', `Valid for ${d.validity_days} days`, d.expires_on, 'not a final quotation',
    d.timeline.label, ...d.assumptions, ...d.exclusions, ...d.client_scope, ...(d.project_preparation.inclusions || [])];
  const missing = expected.filter((x) => !shown.includes(x));
  check('every customer-critical field of the response is on the result page', missing.length === 0, missing.join(' | '));
  check('the specification version is shown', /Specification: /.test(shown));
  await axe('result');
  await shot('result');

  await page.click('[data-v3-back="2"]');
  await page.check('input[name="v3-living-room-tv-unit-variant"][value="box"]');
  const box = await estimate(() => page.click('#v3-estimate'));
  check('the style choice changes the estimate', box.status === 201 && box.body.data.range.low_minor < base.body.data.range.low_minor);
  await page.click('[data-v3-back="2"]');
  await page.check('input[name="v3-living-room-tv-unit-variant"][value="panelled"]');
  await page.locator('.v3-extra', { hasText: 'Feature wall' }).locator('input[type="checkbox"]').check();
  const wall = await estimate(() => page.click('#v3-estimate'));
  check('the feature wall adds to the estimate', wall.status === 201 && wall.body.data.range.low_minor > base.body.data.range.low_minor);
  await page.click('#v3-refine summary');
  await page.fill('#v3-refine-fields input', '18');
  await page.locator('#v3-refine-fields input').dispatchEvent('change');
  const refined = await estimate(() => page.click('#v3-reestimate'), '#v3-reestimate');
  check('measurements refine the estimate later', refined.status === 201 && refined.body.data.range.low_minor !== wall.body.data.range.low_minor);

  const text = bodies.join('\n');
  check('the browser never receives a rate or staff data', !/"(rate|rates|rate_minor|staff_note|warranty_source|governance|pricing)"/.test(text));
  const csp = await page.evaluate(() => window.__csp || []);
  check('no Content-Security-Policy violation', csp.length === 0, csp.join('; '));
  check('no page error', errors.length === 0, errors.join('; '));

  // --- accessibility and performance (remediation: 360 px, keyboard, focus, overflow, slow network, media failure) ---
  const fresh = async (opts = {}, tsConfig = {}) => {
    await pace(2);
    const ctx = await browser.newContext({ viewport: { width: 360, height: 740 }, ...opts });
    await ctx.addInitScript((c) => { window.__tsConfig = c; }, tsConfig);
    await ctx.route('https://challenges.cloudflare.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/javascript', body: TURNSTILE_STUB }));
    const pg = await ctx.newPage();
    watchPosts(pg);
    const errs = [];
    pg.on('pageerror', (e) => errs.push(String(e)));
    return { ctx, pg, errs };
  };
  // Overflow: the document never scrolls sideways, and no visible element extends past the viewport (longest text).
  const overflow = (pg) => pg.evaluate(() => {
    const width = document.documentElement.clientWidth;
    if (document.documentElement.scrollWidth > width) return 'document';
    const wide = [...document.querySelectorAll('main *')].find((n) => {
      const r = n.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && getComputedStyle(n).visibility !== 'hidden' && (r.right > width + 1 || r.left < -1);
    });
    return wide ? `${wide.tagName.toLowerCase()}${wide.id ? `#${wide.id}` : ''}.${wide.className}` : '';
  });
  const focused = (pg) => pg.evaluate(() => {
    const a = document.activeElement;
    if (!a || a === document.body) return { kind: 'body' };
    const kind = a.tagName === 'INPUT' ? a.type : a.tagName.toLowerCase();
    return { kind, id: a.id || '', name: a.name || '', value: a.value || '', inDialog: !!a.closest('dialog[open]'),
      extra: a.closest('.v3-extra')?.querySelector('strong')?.textContent || '', text: (a.textContent || '').trim().slice(0, 40) };
  });

  { // 360 px, keyboard only: focus order through every control kind, real selections, dialog, overflow, reduced motion
    const { ctx, pg, errs } = await fresh({ reducedMotion: 'reduce' });
    const sent = [];
    pg.on('request', (r) => { if (r.method() === 'POST' && r.url().endsWith('/api/v1/public/catalog/estimates')) sent.push(r); });
    await pg.goto(`${ON}/estimate-v3`);
    await pg.waitForSelector('#v3:not([hidden])');
    const where = { initial: await overflow(pg) };
    const order = [];
    for (let i = 0; i < 40; i += 1) {
      await pg.keyboard.press('Tab');
      const f = await focused(pg);
      order.push(f.id || f.kind);
      if (f.id === 'v3-to-rooms') break;
    }
    const positive = await pg.evaluate(() => [...document.querySelectorAll('[tabindex]')].filter((n) => Number(n.getAttribute('tabindex')) > 0).length);
    check('keyboard: Tab reaches "Choose rooms" in document order (no positive tabindex)', order.at(-1) === 'v3-to-rooms' && positive === 0, order.join(' > '));
    await pg.keyboard.press('Enter');
    await pg.waitForSelector('[data-v3="2"]:not([hidden])');
    check('focus moves to the new screen heading', await pg.evaluate(() => document.activeElement?.id) === 'v3-h2');
    // Pass 1: walk the whole rooms screen by keyboard and record every kind of control focus reaches, in order.
    const kinds = new Set();
    let lost = 0;
    for (let i = 0; i < 160; i += 1) {
      await pg.keyboard.press('Tab');
      const f = await focused(pg);
      kinds.add(f.kind);
      if (f.kind === 'body') lost += 1;
      if (f.id === 'v3-estimate') break;
    }
    // Pass 2, from the screen heading: open the gallery dialog and close it with Escape, open a "What is this?" panel,
    // choose the box style (arrow keys in the radio group), tick the feature wall (Space), then estimate.
    await pg.focus('#v3-h2');
    let styled = false; let walled = false; let galleried = false; let opened = false; let reached = false;
    for (let i = 0; i < 160 && !reached; i += 1) {
      await pg.keyboard.press('Tab');
      const f = await focused(pg);
      if (f.kind === 'body') lost += 1;
      if (!galleried && f.kind === 'button' && f.text === 'See examples') {
        await pg.keyboard.press('Enter');
        await pg.waitForSelector('#v3-gallery[open]');
        const inside = await focused(pg);
        where.gallery = await overflow(pg);
        await pg.keyboard.press('Escape');
        await pg.waitForFunction(() => !document.querySelector('#v3-gallery').open);
        const back = await focused(pg);
        galleried = inside.inDialog && back.text === 'See examples';
        check('keyboard: the gallery dialog takes focus, Escape closes it, focus returns to its button', galleried, `${JSON.stringify(inside)} → ${JSON.stringify(back)}`);
        if (inside.inDialog) kinds.add('dialog');
      } else if (!opened && f.kind === 'summary') {
        await pg.keyboard.press('Enter');
        opened = await pg.evaluate(() => !!document.activeElement?.closest('details[open]'));
        where.expanded = await overflow(pg);
      } else if (!styled && f.kind === 'radio' && f.name === 'v3-living-room-tv-unit-variant') {
        await pg.keyboard.press(f.value === 'box' ? 'Space' : 'ArrowDown');
        const after = await focused(pg);
        styled = after.value === 'box' && await pg.locator('input[name="v3-living-room-tv-unit-variant"][value="box"]').isChecked();
        check('keyboard: choosing a style keeps focus on the choice (not lost after re-render)', after.kind === 'radio' && after.value === 'box', JSON.stringify(after));
      } else if (!walled && f.kind === 'checkbox' && f.extra === 'Feature wall') {
        await pg.keyboard.press('Space');
        walled = await pg.locator('.v3-extra', { hasText: 'Feature wall' }).locator('input[type="checkbox"]').isChecked();
      }
      reached = f.id === 'v3-estimate';
    }
    check('keyboard: focus order covers radios, checkboxes, buttons, links, panels and the dialog, never lost',
      ['radio', 'checkbox', 'button', 'a', 'summary', 'dialog'].every((k) => kinds.has(k)) && lost === 0, `${[...kinds].join(', ')}; lost ${lost}`);
    check('keyboard: a style and an extra are really selected by keyboard', styled && walled && opened);
    await ready(pg); // the keyboard user waits for "Ready." announced by the status region
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.keyboard.press('Enter');
    const kres = await res;
    const body = JSON.parse(sent.at(-1)?.postData() || '{}');
    const room = (body.configuration?.rooms || [])[0] || {};
    check('keyboard only: the estimate is reached with the keyboard selections', reached && kres.status() === 201
      && room.products?.['tv-unit']?.variant === 'box' && 'feature-wall' in (room.extras || {}),
      `${kres.status()} ${JSON.stringify(room)}`);
    await pg.waitForSelector('[data-v3="3"]:not([hidden])');
    where.result = await overflow(pg);
    // The longest customer text: the longest catalog name and statement, rendered at 360 px, stay inside the viewport.
    where.longest = await pg.evaluate(() => {
      const longest = [...document.querySelectorAll('main li, main p, main strong, main h3, main h4, main small')]
        .sort((a, b) => b.textContent.length - a.textContent.length).slice(0, 5);
      const width = document.documentElement.clientWidth;
      return longest.filter((n) => n.getBoundingClientRect().right > width + 1).map((n) => n.textContent.slice(0, 40)).join(' | ');
    });
    const failing = Object.entries(where).filter(([, v]) => v);
    check('360 px: no horizontal overflow (initial, expanded panel, gallery, result, longest text)', failing.length === 0
      && Object.keys(where).length === 5, JSON.stringify(where));
    check('reduced motion is respected', await pg.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior !== 'smooth'));
    check('no page error (keyboard run)', errs.length === 0, errs.join('; '));
    await ctx.close();
  }

  { // slow network: every API call delayed, images slower still; the page stays usable
    const { ctx, pg, errs } = await fresh();
    await ctx.route('**/api/v1/public/catalog/media/**', async (route) => { await new Promise((r) => setTimeout(r, 3000)); await route.continue(); });
    await ctx.route('**/api/v1/public/catalog', async (route) => { await new Promise((r) => setTimeout(r, 1500)); await route.continue(); });
    await ctx.route('**/api/v1/public/catalog/estimates', async (route) => { await new Promise((r) => setTimeout(r, 1500)); await route.continue(); });
    await pg.goto(`${ON}/estimate-v3`);
    await pg.waitForSelector('#v3:not([hidden])', { timeout: 15000 });
    await pg.click('#v3-to-rooms');
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'), { timeout: 15000 });
    await pg.click('#v3-estimate');
    check('slow network: the estimate still completes', (await res).status() === 201);
    check('no page error (slow network)', errs.length === 0, errs.join('; '));
    await ctx.close();
  }

  { // media fails to load: text fallbacks, no critical content only in media, the estimate still works
    const { ctx, pg, errs } = await fresh();
    await ctx.route('**/api/v1/public/catalog/media/**', (route) => route.abort());
    await pg.goto(`${ON}/estimate-v3`);
    await pg.waitForSelector('#v3:not([hidden])');
    await pg.click('#v3-to-rooms');
    await pg.waitForSelector('.v3-img-missing');
    const textOnly = await pg.locator('#v3-rooms').innerText();
    await pg.waitForFunction(() => document.querySelectorAll('#v3-rooms img').length === 0, null, { timeout: 15000 });
    check('image failure: every image really fails and is replaced by its accessible text (no broken image left)',
      await pg.locator('.v3-img-missing').count() >= 2 && await pg.locator('#v3-rooms img').count() === 0);
    check('no critical content only in media: rooms, items and finishes are text',
      ['Living room', 'TV unit', 'Laminate', 'Feature wall'].every((x) => textOnly.includes(x)));
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('estimate generation without media', (await res).status() === 201);
    check('no page error (no media)', errs.length === 0, errs.join('; '));
    await ctx.close();
  }

  // --- anti-bot token readiness (customer-safety closure) ----------------------------------------------------------
  const posts = (pg) => { const sent = []; pg.on('request', (r) => { if (r.method() === 'POST' && r.url().endsWith('/api/v1/public/catalog/estimates')) sent.push(r); }); return sent; };
  const toRooms = async (pg) => { await pg.goto(`${ON}/estimate-v3`); await pg.waitForSelector('#v3:not([hidden])'); await pg.click('#v3-to-rooms'); await pg.waitForSelector('[data-v3="2"]:not([hidden])'); };
  const statusText = (pg) => pg.locator('#v3-ts-estimate-status').innerText();
  const settle = (ms) => new Promise((r) => setTimeout(r, ms));

  { // 1, 2: before the script loads, and after the renderer but before the token callback: nothing is sent
    const { ctx, pg, errs } = await fresh({}, { delay: 6000 }); // a wide window between renderer and token
    let release; const gate = new Promise((r) => { release = r; });
    await ctx.route('https://challenges.cloudflare.com/**', async (route) => { await gate; await route.fulfill({ status: 200, contentType: 'text/javascript', body: TURNSTILE_STUB }); });
    const sent = posts(pg);
    await toRooms(pg);
    await pg.click('#v3-estimate', { force: true });
    await settle(300);
    check('1. a click before the anti-bot script loads sends nothing', sent.length === 0 && (await statusText(pg)).includes('Preparing'));
    release();
    await pg.waitForFunction(() => window.turnstile);
    await pg.click('#v3-estimate', { force: true });
    await settle(300);
    check('2. a click after the renderer but before the token sends nothing', sent.length === 0
      && await pg.getAttribute('#v3-estimate', 'aria-disabled') === 'true' && (await statusText(pg)).includes('Completing'));
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('3. a click after the token arrives sends one request', (await res).status() === 201 && sent.length === 1);
    check('the request carries an idempotency key', /^v3-[0-9a-f]{32}$/.test(sent[0].headers()['idempotency-key'] || ''));
    check('no page error (token readiness)', errs.length === 0, errs.join('; '));
    await ctx.close();
  }

  { // 4, 5: double click and Enter-key repeat send one request
    const { ctx, pg } = await fresh();
    await ctx.route('**/api/v1/public/catalog/estimates', async (route) => { await settle(800); await route.continue(); });
    const sent = posts(pg);
    await toRooms(pg);
    await ready(pg);
    await pg.dblclick('#v3-estimate', { force: true });
    await pg.waitForSelector('[data-v3="3"]:not([hidden])', { timeout: 15000 });
    check('4. a double click sends one request', sent.length === 1, String(sent.length));
    await ctx.close();
  }
  {
    const { ctx, pg } = await fresh();
    await ctx.route('**/api/v1/public/catalog/estimates', async (route) => { await settle(800); await route.continue(); });
    const sent = posts(pg);
    await toRooms(pg);
    await ready(pg);
    await pg.focus('#v3-estimate');
    for (let i = 0; i < 6; i += 1) await pg.keyboard.press('Enter');
    await pg.waitForSelector('[data-v3="3"]:not([hidden])', { timeout: 15000 });
    check('5. a repeated Enter key sends one request', sent.length === 1, String(sent.length));
    await ctx.close();
  }

  { // 6: the token expires before submitting: nothing is sent, the customer is told, a fresh token follows
    const { ctx, pg } = await fresh();
    const sent = posts(pg);
    await toRooms(pg);
    await ready(pg);
    // Expire the live token now, and make its renewal slow, so the next click is certainly made without a token.
    await pg.evaluate(() => { window.__tsConfig = { ...window.__tsConfig, delay: 4000 }; window.__tsExpire(); });
    await pg.waitForFunction(() => document.querySelector('#v3-ts-estimate-status')?.textContent.includes('expired'), null, { timeout: 5000 });
    check('6. an expired token disables submission and is announced', await pg.getAttribute('#v3-estimate', 'aria-disabled') === 'true');
    await pg.click('#v3-estimate', { force: true });
    await settle(150);
    check('6. nothing is sent with an expired token', sent.length === 0);
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('6. a fresh token then succeeds', (await res).status() === 201 && sent.length === 1);
    await ctx.close();
  }

  { // 7: the token expires while the request is in flight: one request, it completes, no duplicate
    const { ctx, pg } = await fresh();
    await ctx.route('**/api/v1/public/catalog/estimates', async (route) => { await settle(2000); await route.continue(); });
    const sent = posts(pg);
    await toRooms(pg);
    await ready(pg);
    const request = pg.waitForRequest((r) => r.method() === 'POST' && r.url().endsWith('/api/v1/public/catalog/estimates'));
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'), { timeout: 15000 });
    await pg.click('#v3-estimate');
    await request; // the request is in flight (held by the route) ...
    await pg.evaluate(() => window.__tsExpire()); // ... when its token expires
    await pg.click('#v3-estimate', { force: true }); // a second activation meanwhile is ignored
    check('7. expiry during submission: the request completes once', (await res).status() === 201 && sent.length === 1, String(sent.length));
    await ctx.close();
  }

  { // 8: the anti-bot script fails to load: nothing is sent, an accessible retry is offered, retry then works
    const { ctx, pg, errs } = await fresh();
    let failing = true;
    await ctx.unroute('https://challenges.cloudflare.com/**');
    await ctx.route('https://challenges.cloudflare.com/**', (route) => (failing ? route.abort()
      : route.fulfill({ status: 200, contentType: 'text/javascript', body: TURNSTILE_STUB })));
    const sent = posts(pg);
    await toRooms(pg);
    await pg.waitForSelector('#v3-ts-estimate-retry:not([hidden])', { timeout: 20000 });
    await pg.click('#v3-estimate', { force: true });
    await settle(200);
    check('8. a failed script load sends nothing and offers a retry', sent.length === 0
      && (await statusText(pg)).includes('could not be completed'));
    failing = false;
    check('8. the retry control is keyboard reachable', await pg.evaluate(() => {
      const b = document.querySelector('#v3-ts-estimate-retry'); return !!b && !b.hidden && b.tabIndex >= 0 && !b.disabled; }));
    await pg.focus('#v3-ts-estimate-retry');
    await pg.keyboard.press('Enter');
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('8. the retry loads the check and the estimate succeeds', (await res).status() === 201 && sent.length === 1);
    check('no page error (script failure)', errs.length === 0, errs.join('; '));
    await ctx.close();
  }

  { // 9, 10, 12, 13: the server refuses the token: a controlled, announced, focused message; choices kept; safe retry
    const { ctx, pg } = await fresh({}, { prefix: 'fail' });
    const sent = posts(pg);
    await toRooms(pg);
    await pg.locator('.v3-extra', { hasText: 'Feature wall' }).locator('input[type="checkbox"]').check();
    await ready(pg);
    const refused = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('9. a refused token returns 422', (await refused).status() === 422);
    await pg.waitForSelector('#v3-summary:not([hidden])');
    const summary = await pg.locator('#v3-summary').innerText();
    check('9. the message is controlled (no security detail)', summary.includes('security check could not be completed')
      && !/turnstile|captcha|token|siteverify/i.test(summary), summary);
    check('12. focus moves to the error summary', await pg.evaluate(() => document.activeElement?.id) === 'v3-summary');
    const summaryOverflow = await overflow(pg);
    check('360 px: the error summary does not overflow', !summaryOverflow, summaryOverflow);
    check('13. waiting and error states are announced', await pg.getAttribute('#v3-summary', 'role') === 'alert'
      && await pg.getAttribute('#v3-ts-estimate-status', 'role') === 'status');
    check('9. the choices are kept', await pg.locator('.v3-extra', { hasText: 'Feature wall' }).locator('input[type="checkbox"]').isChecked());
    await pg.evaluate(() => { window.__tsConfig = { ...window.__tsConfig, prefix: 'ok' }; });
    await pg.click('#v3-ts-estimate-retry').catch(() => {}); // the retry is offered, or a fresh token is already on its way
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    const ok = await res;
    check('10. a safe retry succeeds with a fresh token', ok.status() === 201 && sent.length === 2);
    check('10. a refused request is not resent with its old idempotency key',
      sent[0].headers()['idempotency-key'] !== sent[1].headers()['idempotency-key']);
    await ctx.close();
  }

  { // 11: a lost response is retried with the same idempotency key, so the server returns the same estimate
    const { ctx, pg } = await fresh();
    let drop = true;
    await ctx.route('**/api/v1/public/catalog/estimates', async (route) => {
      if (drop) { drop = false; const r = await route.fetch(); await settle(50); await route.abort(); return r; }
      await route.continue();
    });
    const sent = posts(pg);
    await toRooms(pg);
    await ready(pg);
    await pg.click('#v3-estimate');
    await pg.waitForSelector('#v3-summary:not([hidden])', { timeout: 15000 });
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    const second = await res;
    check('11. after a lost response the retry reuses the idempotency key', sent.length === 2
      && sent[0].headers()['idempotency-key'] === sent[1].headers()['idempotency-key']);
    check('11. the server replays the same estimate (no duplicate)', second.status() === 201 && second.headers()['idempotent-replayed'] === 'true');
    await ctx.close();
  }

  // --- canonical customer-copy closure, Phase 8: the remaining token cases and the customer messages ----------------
  { // a Turnstile error callback: nothing is sent, the anti-bot message and a retry are offered, the retry works
    const { ctx, pg } = await fresh({}, { errorFirst: true });
    const sent = posts(pg);
    await toRooms(pg);
    await pg.waitForSelector('#v3-ts-estimate-retry:not([hidden])', { timeout: 15000 });
    const said = await statusText(pg);
    await pg.click('#v3-estimate', { force: true });
    await settle(200);
    check('14. a Turnstile error callback sends nothing and says the security check failed', sent.length === 0
      && said.includes('The security check could not be completed. Please retry.'), said);
    await pg.click('#v3-ts-estimate-retry');
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('14. after the error callback a retry succeeds', (await res).status() === 201 && sent.length === 1);
    await ctx.close();
  }

  { // an empty token from the callback is not a token
    const { ctx, pg } = await fresh({}, { empty: true });
    const sent = posts(pg);
    await toRooms(pg);
    await settle(1500);
    await pg.click('#v3-estimate', { force: true });
    await settle(200);
    check('15. an empty token keeps submission disabled and sends nothing', sent.length === 0
      && await pg.getAttribute('#v3-estimate', 'aria-disabled') === 'true');
    await pg.evaluate(() => { window.__tsConfig = { ...window.__tsConfig, empty: false }; window.__tsReissue(); });
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('15. a real token then succeeds', (await res).status() === 201 && sent.length === 1);
    await ctx.close();
  }

  { // a token older than the accepted age is never sent: it is renewed first
    const { ctx, pg } = await fresh();
    const sent = posts(pg);
    await toRooms(pg);
    await ready(pg);
    await pg.evaluate(() => { const real = Date.now; window.__realNow = real; Date.now = () => real() + 290000; });
    await pg.click('#v3-estimate');
    await settle(200);
    check('16. a stale token (older than its accepted age) is not sent', sent.length === 0
      && (await statusText(pg)).includes('expired'), await statusText(pg));
    await pg.evaluate(() => { Date.now = window.__realNow; });
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('16. the renewed token succeeds', (await res).status() === 201 && sent.length === 1);
    await ctx.close();
  }

  { // the widget's live response differs from the token the callback delivered: never sent
    const { ctx, pg } = await fresh();
    const sent = posts(pg);
    await toRooms(pg);
    await ready(pg);
    await pg.evaluate(() => { window.__tsConfig = { ...window.__tsConfig, mismatch: true }; });
    await pg.click('#v3-estimate');
    await settle(200);
    check('17. a token that does not match the widget is not sent', sent.length === 0);
    await pg.evaluate(() => { window.__tsConfig = { ...window.__tsConfig, mismatch: false }; window.__tsReissue(); });
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('17. a matching token then succeeds', (await res).status() === 201 && sent.length === 1);
    await ctx.close();
  }

  { // a used token delivered again (after a success) is ignored; the next request waits for a new one
    const { ctx, pg } = await fresh();
    const sent = posts(pg);
    await toRooms(pg);
    await ready(pg);
    await pg.evaluate(() => { window.__tsConfig = { ...window.__tsConfig, repeat: true }; });
    const first = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('18. the first request succeeds', (await first).status() === 201);
    await pg.click('[data-v3-back="2"]');
    await settle(1500); // the renewal redelivers the same (used) token
    await pg.click('#v3-estimate', { force: true });
    await settle(200);
    check('18. a redelivered used token is never sent again', sent.length === 1
      && await pg.getAttribute('#v3-estimate', 'aria-disabled') === 'true');
    await pg.evaluate(() => { window.__tsConfig = { ...window.__tsConfig, repeat: false }; window.__tsReissue(); });
    await ready(pg);
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('18. a new token then succeeds', (await res).status() === 201 && sent.length === 2
      && new Set(sent.map((r) => JSON.parse(r.postData()).turnstile_token)).size === 2);
    await ctx.close();
  }

  { // waiting for a token: the button is disabled and a double click while waiting sends nothing, then exactly one
    const { ctx, pg } = await fresh({}, { delay: 3000 });
    const sent = posts(pg);
    await toRooms(pg);
    check('19. the button is disabled while the check is pending', await pg.getAttribute('#v3-estimate', 'aria-disabled') === 'true'
      && (await pg.getAttribute('#v3-estimate', 'class') || '').includes('v3-waiting'));
    await pg.dblclick('#v3-estimate', { force: true });
    await settle(200);
    check('19. a double click while waiting sends nothing', sent.length === 0);
    await ready(pg);
    await ctx.route('**/api/v1/public/catalog/estimates', async (route) => { await settle(800); await route.continue(); });
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('19. while submitting the button is disabled', await pg.getAttribute('#v3-estimate', 'aria-disabled') === 'true');
    await pg.dblclick('#v3-estimate', { force: true });
    check('19. then exactly one request is sent', (await res).status() === 201 && sent.length === 1, String(sent.length));
    await ctx.close();
  }

  // Each status gets its own message; only an anti-bot refusal mentions the security check. These responses are
  // simulated by the browser route (the server's own 409 and 422 paths are covered by the API tests).
  const mapped = [
    ['20. a server used-token rejection', 422, { code: 'CAPTCHA_FAILED', detail: 'x' }, 'The security check could not be completed. Please retry.'],
    ['21. a 422', 422, { code: 'VALIDATION_FAILED', errors: [{ field: 'rooms', code: 'OUT_OF_RANGE', message: 'TV wall width must be between 3 and 20 ft.' }] }, 'Please review the highlighted information.'],
    ['22. a 409', 409, { code: 'IDEMPOTENCY_KEY_REUSED' }, 'This request conflicts with an earlier submission. Please refresh and try again.'],
    ['23. a 429', 429, { code: 'RATE_LIMITED' }, 'Too many attempts. Please wait before trying again.'],
    ['24. a 500', 500, { code: 'INTERNAL' }, 'We could not prepare an estimate right now.'],
    ['25. a 503', 503, { code: 'ESTIMATOR_UNAVAILABLE' }, 'We could not prepare an estimate right now.'],
  ];
  for (const [name, status, body, message] of mapped) {
    const { ctx, pg } = await fresh();
    let answered = false;
    await ctx.route('**/api/v1/public/catalog/estimates', async (route) => {
      if (answered) return route.continue();
      answered = true;
      return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    });
    const sent = posts(pg);
    await toRooms(pg);
    await ready(pg);
    await pg.click('#v3-estimate');
    await pg.waitForSelector('#v3-summary:not([hidden])', { timeout: 15000 });
    const summary = await pg.locator('#v3-summary').innerText();
    const antiBot = /security check/i.test(summary);
    check(`${name} shows its own message`, summary.includes(message) && (status === 422 && body.code === 'CAPTCHA_FAILED' ? antiBot : !antiBot), summary);
    if (body.errors) check(`${name} lists the highlighted problem`, summary.includes(body.errors[0].message), summary);
    if (status === 409) {
      await ready(pg);
      const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates') && r.request().method() === 'POST');
      await pg.click('#v3-estimate');
      const retried = await res;
      check('22. after a 409 the page drops its key and the retry succeeds with a new one', retried.status() === 201
        && sent.length === 2 && sent[0].headers()['idempotency-key'] !== sent[1].headers()['idempotency-key']);
    }
    await ctx.close();
  }
} catch (err) {
  check('journey completed', false, String(err));
  await shot('failure');
} finally {
  await browser.close();
}
process.exit(results.every(Boolean) ? 0 : 1);
