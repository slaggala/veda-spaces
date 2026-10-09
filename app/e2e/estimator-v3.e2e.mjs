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
const TURNSTILE_STUB = `window.turnstile = { render() { return 'w' + Math.random(); }, getResponse() { return 'stub-token'; }, reset() {} };`;

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 390, height: 860 } });
await context.addInitScript(() => {
  window.__csp = [];
  document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI}`));
});
await context.route('https://challenges.cloudflare.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/javascript', body: TURNSTILE_STUB }));
const page = await context.newPage();
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
async function estimate(trigger) {
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
  await page.waitForFunction(() => [...document.querySelectorAll('.v3-room img')].some((i) => i.complete && i.naturalWidth > 0));
  check('catalog images load (delivery variants, by hash)', true);
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
  const refined = await estimate(() => page.click('#v3-reestimate'));
  check('measurements refine the estimate later', refined.status === 201 && refined.body.data.range.low_minor !== wall.body.data.range.low_minor);

  const text = bodies.join('\n');
  check('the browser never receives a rate or staff data', !/"(rate|rates|rate_minor|staff_note|warranty_source|governance|pricing)"/.test(text));
  const csp = await page.evaluate(() => window.__csp || []);
  check('no Content-Security-Policy violation', csp.length === 0, csp.join('; '));
  check('no page error', errors.length === 0, errors.join('; '));

  // --- accessibility and performance (remediation: 360 px, keyboard, focus, overflow, slow network, media failure) ---
  const fresh = async (opts = {}) => {
    const ctx = await browser.newContext({ viewport: { width: 360, height: 740 }, ...opts });
    await ctx.route('https://challenges.cloudflare.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/javascript', body: TURNSTILE_STUB }));
    const pg = await ctx.newPage();
    const errs = [];
    pg.on('pageerror', (e) => errs.push(String(e)));
    return { ctx, pg, errs };
  };
  const overflow = (pg) => pg.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);

  { // 360 px, keyboard only, focus order, no horizontal overflow, reduced motion
    const { ctx, pg, errs } = await fresh({ reducedMotion: 'reduce' });
    await pg.goto(`${ON}/estimate-v3`);
    await pg.waitForSelector('#v3:not([hidden])');
    let overflowed = await overflow(pg);
    const order = [];
    for (let i = 0; i < 40; i += 1) {
      await pg.keyboard.press('Tab');
      const id = await pg.evaluate(() => document.activeElement?.id || document.activeElement?.textContent?.trim().slice(0, 30) || '');
      order.push(id);
      if (id === 'v3-to-rooms') break;
    }
    const positive = await pg.evaluate(() => [...document.querySelectorAll('[tabindex]')].filter((n) => Number(n.getAttribute('tabindex')) > 0).length);
    check('keyboard: Tab reaches "Choose rooms" in document order (no positive tabindex)', order.at(-1) === 'v3-to-rooms' && positive === 0, order.join(' > '));
    await pg.keyboard.press('Enter');
    await pg.waitForSelector('[data-v3="2"]:not([hidden])');
    check('focus moves to the new screen heading', await pg.evaluate(() => document.activeElement?.id) === 'v3-h2');
    overflowed ||= await overflow(pg);
    let reached = false;
    for (let i = 0; i < 80 && !reached; i += 1) {
      await pg.keyboard.press('Tab');
      reached = await pg.evaluate(() => document.activeElement?.id === 'v3-estimate');
    }
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.keyboard.press('Enter');
    const kres = await res;
    check('keyboard only: the estimate is reached', reached && kres.status() === 201, `${kres.status()} ${JSON.stringify((await kres.json().catch(() => ({}))).errors || '')}`);
    await pg.waitForSelector('[data-v3="3"]:not([hidden])');
    overflowed ||= await overflow(pg);
    check('360 px: no horizontal overflow on any screen', !overflowed);
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
    check('image failure: accessible text replaces each image', await pg.locator('.v3-img-missing').count() >= 2);
    check('no critical content only in media: rooms, items and finishes are text',
      ['Living room', 'TV unit', 'Laminate', 'Feature wall'].every((x) => textOnly.includes(x)));
    const res = pg.waitForResponse((r) => r.url().endsWith('/api/v1/public/catalog/estimates'));
    await pg.click('#v3-estimate');
    check('estimate generation without media', (await res).status() === 201);
    check('no page error (no media)', errs.length === 0, errs.join('; '));
    await ctx.close();
  }
} catch (err) {
  check('journey completed', false, String(err));
  await shot('failure');
} finally {
  await browser.close();
}
process.exit(results.every(Boolean) ? 0 : 1);
