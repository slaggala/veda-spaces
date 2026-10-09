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
  check('the TV unit and its finishes are offered', await page.locator('.v3-product h4', { hasText: 'TV unit' }).count() === 1
    && await page.locator('input[value="laminate"]').isChecked() && await page.locator('input[value="veneer"]').count() === 1);
  await page.waitForFunction(() => [...document.querySelectorAll('.v3-room img')].some((i) => i.complete && i.naturalWidth > 0));
  check('catalog images load (delivery variants, by hash)', true);
  check('images are labelled as illustrative', await page.locator('.v3-badge', { hasText: 'Illustrative example' }).count() > 0);
  await page.locator('.v3-extra summary', { hasText: 'What is this?' }).first().click();
  check('“What is this?” explains an extra', (await page.locator('.v3-extra details[open] p').first().innerText()).length > 10);
  await page.click('text=See examples');
  check('the gallery opens as a dialog', await page.locator('#v3-gallery[open] img').count() >= 2);
  await page.click('#v3-gallery-close');
  await page.click('text=View in 3D');
  check('3D falls back to the gallery without a renderer', await page.locator('#v3-gallery[open]').count() === 1
    && await page.locator('.v3-3d', { hasText: 'not available on this device' }).count() === 1);
  await page.click('#v3-gallery-close');
  await axe('rooms');
  await shot('rooms');

  const base = await estimate(() => page.click('#v3-estimate'));
  check('an estimate from the default configuration', base.status === 201 && /^C[0-9A-Z]{8}$/.test(base.body.data.configuration_reference), String(base.status));
  await page.waitForSelector('[data-v3="3"]:not([hidden])');
  check('the result shows the range, the reference and the disclaimer', (await page.locator('#v3-result').innerText()).includes(base.body.data.configuration_reference)
    && (await page.locator('#v3-result').innerText()).includes('not a final quotation'));
  await axe('result');
  await shot('result');

  await page.click('[data-v3-back="2"]');
  await page.check('input[name="v3-living-room-tv-unit-variant"][value="box"]');
  const box = await estimate(() => page.click('#v3-estimate'));
  await page.click('[data-v3-back="2"]');
  await page.locator('.v3-extra', { hasText: 'Soft-close storage' }).locator('input[type="checkbox"]').check();
  const soft = await estimate(() => page.click('#v3-estimate'));
  check('soft-close storage changes the estimate', box.status === 201 && soft.status === 201 && soft.body.data.range.low_minor > box.body.data.range.low_minor);
  await page.click('[data-v3-back="2"]');
  await page.check('input[name="v3-living-room-tv-unit-variant"][value="panelled"]');
  const refused = await estimate(() => page.click('#v3-estimate'));
  check('an unsupported combination is refused and explained', refused.status === 422 && await page.locator('#v3-summary:not([hidden]) li').count() >= 1);
  await page.locator('.v3-extra', { hasText: 'Soft-close storage' }).locator('input[type="checkbox"]').uncheck();
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
} catch (err) {
  check('journey completed', false, String(err));
  await shot('failure');
} finally {
  await browser.close();
}
process.exit(results.every(Boolean) ? 0 : 1);
