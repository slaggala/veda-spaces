// Estimator UX V2 clickable prototype (docs/implementation/estimator/ESTIMATOR-UX-V2.md) under the production CSP.
//   node e2e/static-server.mjs e2e/site-release 8001 &  SITE_OFF=http://localhost:8001 node e2e/estimator-v2-prototype.e2e.mjs
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const ROOT = `${process.env.SITE_OFF ?? 'http://localhost:8001'}/prototype/estimator-v2/`;
const BASE = `${ROOT}?variant=B`;
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
const fresh = async (url = BASE) => { await page.goto(url); await page.evaluate(() => sessionStorage.clear()); await page.reload(); await page.waitForSelector('[data-screen="1"]:not([hidden])'); };
const toResult = async () => { for (const n of [1, 2, 3, 4]) await next(n); await page.check('#verify'); await page.click('#see-budget'); await page.waitForSelector('[data-screen="6"]:not([hidden])'); };
const resultText = () => page.evaluate(() => { document.querySelectorAll('[data-screen="6"] details').forEach((d) => { d.open = true; }); return document.querySelector('[data-screen="6"]').innerText; });

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
// Variant B (trust-first): the validation tasks, as far as automation can check them.
const ctas = await page.locator('#cta button').allTextContents();
check('B: CTA order personalise → quotation → designer', ctas.join(' | ') === 'Personalise and narrow my estimate | Get a detailed quotation | Talk to a designer', ctas.join(' | '));
const b = await resultText();
check('B task 1: the material promise (what kitchen and wardrobe are made of)', /What Essential includes/.test(b) && /Cabinet structure/.test(b) && /Doors and shutters/.test(b) &&
  (await page.locator('.room-card .spec-line').count()) >= 8);
check('B task 2: the execution package is included in the range', /Site Execution & Handover Package/.test(b) && (b.match(/Included in your estimated range/g) || []).length === 2 &&
  /Included in this range: your rooms, the Site Execution & Handover Package and the Design Personalisation Allowance\. GST is extra\./.test(b));
check('B task 3: the allowance is not an automatic extra', /Design Personalisation Allowance/.test(b) && /not an automatic extra charge/.test(b));
check('B task 4: what changes the range', /Why is this a range\?/.test(b) && /How your range is built/.test(b) && /physical site measurement/.test(b));
check('B task 5–6: exclusions and warranty findable', /Not included/.test(b) && /Warranty/.test(b) && (await page.locator('[data-screen="6"] a[href="/warranty"]').count()) === 1);
check('B task 7: how to compare with another provider', /How to compare this estimate/.test(b) && /Hardware brand and type/.test(b));
check('no rates, price ceilings or conflicting warranty periods on the result', !/per sq|\/sq ?ft|per sheet|₹2,500|₹800|₹1,000 per|10 years|30-year|30 years/i.test(b));
check('room subtotals shown, no line amounts', (await page.locator('.room-amount').count()) === 9);
await axe('6 result (variant B)');
check('360 px without horizontal scroll (result)', (await overflow()) <= 1);
// Optional refinement narrows or moves the range.
// Detailed specification on demand; the default promises only what both historical specifications agree on.
await page.click('#result-body .link:has-text("View detailed material specification")');
const spec = await page.locator('[data-screen="10"]').innerText();
check('detailed specification: 9 categories, no conflicting grade promised by default', (await page.locator('#spec-detail .spec-cat').count()) === 9 &&
  !/Sylvan Blu|Blum|0\.72|1\.3 mm/.test(spec) && /approved equivalent/.test(spec));
await axe('10 detailed specification');
await page.click('#spec-back');
check('specification back returns to the estimate', await visible(6));
// T9: personalise without technical knowledge (primary CTA).
await page.click('#cta button:has-text("Personalise and narrow my estimate")');
check('B: personalise opens the plain-language refinement', (await page.textContent('#h8')) === 'Personalise and narrow my estimate' &&
  (await page.locator('[data-screen="8"] small').count()) >= 3);
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
// Talk to a designer: consultation request, no amount.
await fresh();
await toResult();
await page.click('#cta button:has-text("Talk to a designer")');
check('talk to a designer: consultation request without an amount', await visible(7) && (await page.textContent('#h7')) === 'Request a design consultation' &&
  !/₹/.test(await page.locator('[data-screen="7"]').innerText()));
// Variant A: the current result page plus material summaries; approved labels; quotation first.
await fresh(`${ROOT}?variant=A`);
await toResult();
const a = await resultText();
check('A: approved labels, material summary per room, quotation first', /Project Preparation & Protection Package/.test(a) && /Custom Features Allowance/.test(a) &&
  (await page.locator('.totals .spec-line').count()) === 9 && (await page.locator('#cta button').first().textContent()) === 'Get my detailed quotation →');
check('A: no rates or conflicting warranty periods', !/per sq|per sheet|₹2,500|10 years|30-year/i.test(a));
await axe('6 result (variant A)');
// Specification candidates (owner decision T1) are only shown when asked for.
await fresh(`${ROOT}?variant=B&spec=oct`);
await toResult();
await page.click('#result-body .link:has-text("View detailed material specification")');
check('candidate specification shown only on request (?spec=oct)', /Sylvan Blu/.test(await page.locator('[data-screen="10"]').innerText()));
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
