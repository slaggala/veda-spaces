// Estimator UX V2 clickable prototype (docs/implementation/estimator/ESTIMATOR-UX-V2.md) under the production CSP.
//   node e2e/static-server.mjs e2e/site-release 8001 &  SITE_OFF=http://localhost:8001 node e2e/estimator-v2-prototype.e2e.mjs
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const BASE = `${process.env.SITE_OFF ?? 'http://localhost:8001'}/prototype/estimator-v2/`;
const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`); };

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 360, height: 780 } });
await context.addInitScript(() => {
  window.__csp = [];
  document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI}`));
});
const page = await context.newPage();
const errors = [];
const requests = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('request', (r) => { if (/\/api\//.test(r.url()) || r.method() !== 'GET') requests.push(`${r.method()} ${r.url()}`); });
async function axe(name) {
  await page.evaluate(AXE);
  const v = await page.evaluate(async () => {
    const res = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] }, preload: false });
    return res.violations.map((x) => `${x.id}: ${x.nodes.map((n) => n.target.join(' ')).join(', ')}`);
  });
  check(`axe: ${name}`, v.length === 0, v.join('; '));
}
const overflow = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
const visible = (n) => page.locator(`[data-screen="${n}"]`).isVisible();
const next = (n) => page.click(`[data-screen="${n}"] [data-next]`);
// Start again: clear the tab's saved state in a fresh document (a previous page can still save on pending events).
const fresh = async () => { await page.goto(BASE); await page.evaluate(() => sessionStorage.clear()); await page.reload(); await page.waitForSelector('[data-screen="1"]:not([hidden])'); };

await page.goto(BASE);
const t0 = Date.now();
check('screen 1: home type, apartment preselected, villa not selectable', await visible(1) &&
  await page.isChecked('input[name="type"][value="APARTMENT"]') && await page.isDisabled('input[name="type"][value="VILLA"]'));
check('facilitator tools hidden unless asked for', !(await page.locator('#facilitator').isVisible()));
check('no technical terms up front', !/\b(sq ?ft|rft|carcass|SFT|RFT|width|height)\b/i.test(await page.locator('[data-screen="1"]').innerText()));
await axe('1 home type');
await next(1);
check('screen 2: only 3 BHK selectable', await page.isChecked('input[name="bhk"][value="3BHK"]') &&
  (await page.locator('input[name="bhk"]:disabled').count()) === 3);
await axe('2 BHK');
await next(2);
await axe('3 new or renovation');
await next(3);
const rooms = await page.locator('.room').count();
check('screen 4: rooms preselected for a 3 BHK, no measurements asked', rooms === 9 &&
  (await page.locator('[data-screen="4"] input[type="number"]').count()) === 0 && (await page.locator('.room.off').count()) === 0, `${rooms} rooms`);
await axe('4 rooms');
check('360 px without horizontal scroll (rooms)', (await overflow()) <= 1);
const roomsHeight = await page.evaluate(() => document.documentElement.scrollHeight);
check('rooms read as a home: extras folded, page short', (await page.locator('.extras[open]').count()) === 0 && roomsHeight < 2200, `${roomsHeight}px`);
await page.evaluate(() => document.querySelectorAll('.extras').forEach((d) => { d.open = true; }));
// Prevent, never reject: switch on every extra, bedside tables to the maximum; vanity units stop at the engine limit.
// Each change re-renders the cards (and disables extras at a limit), so pick the first open one every time.
for (let guard = 0; guard < 60; guard += 1) {
  const open = page.locator('.extras input[type="checkbox"]:not([disabled]):not(:checked)').first();
  if (!(await open.count())) break;
  await open.click();
}
for (let guard = 0; guard < 20; guard += 1) {
  const plus = page.locator('.stepper button[aria-label^="More"]:not([aria-disabled="true"])').first();
  if (!(await plus.count())) break;
  await plus.click();
}
const limited = await page.locator('.extra.limit').count();
const used = await page.evaluate(() => {
  const s = JSON.parse(sessionStorage.getItem('veda-estimator-v2-prototype'));
  return Object.values(s.rooms).filter((r) => r.on).length;
});
check('limits prevented in the rooms step ("Limit reached for your home")', limited > 0 && used === 9, `${limited} extras disabled`);
// Back to the typical selection for the timed path.
await fresh();
for (const n of [1, 2, 3, 4]) await next(n);
await page.check('#verify');
await axe('5 package');
await page.click('#see-budget');
await page.waitForSelector('[data-screen="6"]:not([hidden])');
const ms = Date.now() - t0;
const range = await page.textContent('#range');
check('progress bar only on steps 1–5', !(await page.locator('#progress').isVisible()));
check('estimate shown before any contact details', /₹[\d,]+ – ₹[\d,]+/.test(range) && !(await visible(7)), range);
check('time to first estimate on the default path (automated, 5 taps)', ms < 120000, `${ms} ms`);
const details = await page.evaluate(() => ({
  open: [...document.querySelectorAll('[data-screen="6"] summary')].map((s) => s.textContent),
  disclaimer: document.querySelector('.disclaimer').textContent,
}));
check('result: package, allowance, assumptions and disclaimer present', ['Project Preparation & Protection Package', 'Custom Features Allowance', 'Assumptions'].every((t) => details.open.includes(t)) &&
  details.disclaimer.startsWith('This is a preliminary budgetary estimate'));
await page.evaluate(() => document.querySelectorAll('details').forEach((d) => { d.open = true; }));
await axe('6 result');
check('360 px without horizontal scroll (result)', (await overflow()) <= 1);
// Optional refinement narrows or moves the range.
await page.click('#to-refine');
await page.fill('[data-screen="8"] input >> nth=0', '16');
await page.click('#update');
const refined = await page.textContent('#refined-range');
check('refinement updates the range', /₹[\d,]+ – ₹[\d,]+/.test(refined) && refined !== range, `${range} → ${refined}`);
await axe('8 refine');
// Lead capture: linked error summary, then confirmation; nothing is sent.
await page.click('[data-screen="8"] [data-goto="7"]');
await page.click('#send');
check('lead: errors linked and fields marked invalid', (await page.locator('#lead-summary a').count()) === 3 &&
  (await page.getAttribute('#name', 'aria-invalid')) === 'true');
await axe('7 lead (errors)');
await page.fill('#name', 'Test Customer');
await page.fill('#phone', '98480 12345');
await page.check('#consent');
await page.check('#verify2');
await page.click('#send');
await page.waitForSelector('[data-screen="9"]:not([hidden])');
check('confirmation with the estimate reference', /PROTO-/.test(await page.textContent('#estimate-ref')));
await axe('9 confirmation');
// Luxury: consultation without an amount.
await fresh();
for (const n of [1, 2, 3, 4]) await next(n);
await page.check('input[name="pkg"][value="LUXURY"]');
await page.check('#verify');
await page.click('#see-budget');
check('luxury: consultation request, no amount', await visible(7) && (await page.textContent('#h7')) === 'Request a design consultation' &&
  !/₹/.test(await page.locator('[data-screen="7"]').innerText()));
// Reload keeps the place.
await page.reload();
check('reload keeps the screen and answers', await visible(7));

const csp = await page.evaluate(() => window.__csp || []);
check('no network calls to any API (prototype)', requests.length === 0, requests.slice(0, 3).join('; '));
check('no Content-Security-Policy violations under the production policy', csp.length === 0, csp.join('; '));
check('no page errors', errors.length === 0, errors.join('; '));
await browser.close();
console.log(`${results.filter(Boolean).length}/${results.length} prototype checks passed`);
process.exitCode = results.every(Boolean) ? 0 : 1;
