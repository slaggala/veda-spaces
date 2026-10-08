// Budgetary Estimate UX V2 (STAGING_ESTIMATOR_UX=v2) against the real API with the SYNTHETIC rate card and the
// SYNTHETIC customer specification, under the production Content-Security-Policy. Includes the V1/V2 equivalence
// check: the same selections give the same estimate in both experiences.
//   SITE_ON=http://localhost:8000 node e2e/estimator-v2.e2e.mjs   (the test server switches UX with ?ux=v2)
// Against another card or specification loaded locally (never committed): E2E_CARD=<card.json> E2E_SPEC=<spec code>;
// E2E_QUIET=1 keeps amounts out of the output.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const HERE = path.dirname(fileURLToPath(import.meta.url));
const CARD = JSON.parse(fs.readFileSync(process.env.E2E_CARD ?? path.join(HERE, '../../api/tests/fixtures/estimator/synthetic-rate-card.json'), 'utf8'));
const SPEC_CODE = process.env.E2E_SPEC ?? 'SYNTHETIC-ESSENTIAL-1.1';
const QUIET = Boolean(process.env.E2E_QUIET);
const ON = process.env.SITE_ON ?? 'http://localhost:8000';
const V2 = `${ON}/estimate?ux=v2`;
const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`); };
const TURNSTILE_STUB = `window.turnstile = { render() { return 'w' + Math.random(); }, getResponse() { return 'stub-token'; }, reset() {} };`;

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 360, height: 800 } });
await context.addInitScript(() => {
  window.__csp = [];
  document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI}`));
});
await context.route('https://challenges.cloudflare.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/javascript', body: TURNSTILE_STUB }));
const page = await context.newPage();
const errors = [];
const csp = [];
page.on('pageerror', (e) => errors.push(String(e)));
const collectCsp = async () => { csp.push(...(await page.evaluate(() => window.__csp || []))); };
const shot = async (name) => { if (process.env.E2E_OUT) await page.screenshot({ path: path.join(process.env.E2E_OUT, `estimator-v2-${name}.png`), fullPage: true }); };
async function axe(name) {
  await page.evaluate(AXE);
  const v = await page.evaluate(async () => {
    const res = await window.axe.run(document.querySelector('main'), { preload: false, runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } });
    return res.violations.map((x) => `${x.id}: ${x.nodes.map((n) => n.target.join(' ')).join(', ')}`);
  });
  check(`axe: ${name}`, v.length === 0, v.join('; '));
}
const visible = (n) => page.locator(`[data-v2="${n}"]`).isVisible();
const next = (n) => page.click(`[data-v2="${n}"] [data-v2-next]`);
const fresh = async (url = V2) => { await page.goto(url); await page.evaluate(() => sessionStorage.clear()); await page.reload(); };
async function toResult() {
  await next(1);
  await page.check('input[name="v2-size"][value="3BHK"]');
  await next(2);
  await next(3);
  await next(4);
  const req = page.waitForRequest((r) => r.url().endsWith('/api/v1/public/estimates') && r.method() === 'POST');
  const res = page.waitForResponse((r) => r.url().endsWith('/api/v1/public/estimates'));
  await page.click('#v2-see');
  const [request, response] = await Promise.all([req, res]);
  await page.waitForSelector('[data-v2="6"]:not([hidden])');
  return { body: JSON.parse(request.postData()), data: (await response.json()).data };
}

// 1. V2 runs instead of V1 when switched on; first estimate without contact details or measurements.
await fresh();
check('V2 shown, V1 hidden', await visible(1) && !(await page.locator('#est-app').isVisible()));
await axe('V2 1 home type');
await next(1);
check('only supported sizes selectable', await page.isDisabled('input[name="v2-size"][value="1BHK"]') && !(await page.isDisabled('input[name="v2-size"][value="3BHK"]')));
await axe('V2 2 BHK');
await page.check('input[name="v2-size"][value="3BHK"]');
await next(2);
await axe('V2 3 new or renovation');
await next(3);
check('rooms preselected, no measurement fields', (await page.locator('.v2-room').count()) === 9 && (await page.locator('[data-v2="4"] input[type="number"]').count()) === 0);
await axe('V2 4 rooms');
await shot('4-rooms');
await next(4);
check('Premium unavailable; Luxury is a consultation', await page.isDisabled('input[name="v2-pkg"][value="PREMIUM"]') && !(await page.isDisabled('input[name="v2-pkg"][value="LUXURY"]')));
await axe('V2 5 package');
await fresh();
const v2run = await toResult();
check('estimate before any contact details; no measurements sent', /₹[\d,]+ – ₹[\d,]+/.test(await page.textContent('#v2-range')) &&
  v2run.body.selections.every((s) => Object.keys(s.measurements).length === 0) && !(await visible(7)));
// 2. Result page: summary first, explanations second, technical detail on demand (trust finalisation).
const blocks = await page.locator('#v2-result-body > section h3').allTextContents();
check('result order', blocks.join(' | ') === 'How your estimate is built | What Essential includes | Your rooms | Site Execution & Handover Package | Design Personalisation Allowance | Warranty and service | Not included | How to compare this estimate | Typical 3 BHK assumptions used | What happens next?', blocks.join(' | '));
const text = await page.locator('[data-v2="6"]').innerText();
const top = await page.locator('#v2-top').innerText();
check('range explained immediately: what it includes, GST separately, why it is a range, how to narrow it',
  /Your estimate includes\s+Your selected rooms and products\s+Site Execution & Handover Package\s+Design Personalisation Allowance\s+GST is shown separately\./.test(top) &&
  (await page.locator('#v2-top .v2-block').nth(1).locator('li').count()) === 5 && /Why is this a range\?/.test(top) &&
  (await page.locator('#v2-top button:has-text("Personalise and narrow my estimate")').count()) === 1);
const markers = await page.locator('#v2-top .v2-markers li').allTextContents();
check('factual trust markers only', markers.join(' | ') === 'No contact details required for your first estimate | Room-wise estimate shown | Material specification available | Warranty and exclusions disclosed | GST shown separately' &&
  !/no\.?\s*1|best|cheapest|lowest|most accurate|guarantee/i.test(text), markers.join(' | '));
check('GST shown the same way in the summary and the build-up', (await page.textContent('#v2-gst')).includes((await page.locator('#v2-build dd').last().textContent()).replace('about ', '')));
// How your estimate is built: every displayed component adds up to the displayed range (Phase 8).
const rows = await page.locator('#v2-build dd[data-low]').evaluateAll((dds) => dds.map((d) => [d.previousElementSibling.textContent, Number(d.dataset.low), Number(d.dataset.high)]));
const parts = rows.slice(0, -1);
const total = rows[rows.length - 1];
const sum = (i) => parts.reduce((a, r) => a + r[i], 0);
check('how your estimate is built reconciles to the range', total[1] === v2run.data.range.low_minor && total[2] === v2run.data.range.high_minor &&
  sum(1) === total[1] && sum(2) === total[2] && rows[0][1] === v2run.data.rooms.reduce((a, r) => a + r.amount_minor, 0) &&
  parts.some((r) => r[0].includes('Site Execution & Handover Package') && r[1] === v2run.data.project_preparation.amount_minor) &&
  parts.some((r) => r[0].includes('Design Personalisation Allowance') && r[1] === v2run.data.custom_features_allowance.low_minor && r[2] === v2run.data.custom_features_allowance.high_minor),
  QUIET ? '' : JSON.stringify(rows));
check('material promise from the specification snapshot, categories on demand', v2run.data.specification?.spec_code === SPEC_CODE && /Approved brands such as the named examples/.test(text) &&
  (await page.locator('#v2-result-body details:has(summary:has-text("material categories")) dt').count()) === v2run.data.specification.categories.length);
// Room promises come from the server's room details (priced lines), never a generic line (Phase 3).
const cards = await page.locator('.v2-room-card').evaluateAll((els) => els.map((c) => ({ name: c.querySelector('h4').textContent, amount: Number(c.querySelector('.v2-room-amount').textContent.replace(/[^\d]/g, '')), line: c.querySelector('.v2-spec-line')?.textContent.replace('Essential specification: ', '') || null,
  more: [...c.querySelectorAll('details')].map((d) => d.querySelector('summary').textContent), parts: [...c.querySelectorAll('details h5')].map((h) => h.textContent) })));
const byRoom = Object.fromEntries(v2run.data.room_details.map((d) => [d.room, d.materials?.line || null]));
const shownLines = v2run.data.rooms.map((r, i) => [r.room, cards[i]?.line]);
check('room subtotals shown with room-specific specification lines', cards.length === v2run.data.rooms.length && shownLines.every(([room, line]) => line === byRoom[room]) &&
  byRoom.KITCHEN === 'Branded plywood cabinetry · Laminate finish · Soft-close kitchen hardware' && !/Soft-close/.test(byRoom.POOJA || '') &&
  !/plywood/i.test(byRoom.WHOLE_HOME || '') && /^Branded plywood furniture · Laminate finish · Soft-close wardrobe hardware$/.test(byRoom.MASTER_BEDROOM || ''), JSON.stringify(byRoom));
check('room subtotals as displayed add up to "Your selected rooms"', cards.reduce((a, c) => a + c.amount, 0) * 100 === rows[0][1]);
check('one "View inclusions & materials" per room with four parts', cards.every((c) => c.more.join() === 'View inclusions & materials' && c.parts.join(' | ') === 'Included items | Material specification | Optional or selected extras | Assumptions'));
check('package and allowance included, allowance not an automatic extra', (text.match(/Included in your estimated range/g) || []).length === 2 && /It is not an automatic extra charge\./.test(text) &&
  /The upper amount is not charged automatically\./.test(text) && /execute the selected project scope professionally/.test(text) && !/complimentary|free of charge|\bfree\b/i.test(text));
const policyText = await (await fetch(`${ON}/warranty`)).text();
check('warranty: manufacturer-backed protection and Veda Spaces service support kept apart; the one duration matches the policy',
  (await page.locator('#v2-result-body h4:has-text("Manufacturer-backed protection")').count()) === 1 && (await page.locator('#v2-result-body h4:has-text("Veda Spaces service support")').count()) === 1 &&
  /one year of applicable workmanship and fitment service support from handover/.test(text) && /one year of free service from (your|the) project handover date/.test(policyText) &&
  (await page.locator('[data-v2="6"] a:has-text("View full warranty and exclusions")').count()) === 1);
check('no rates, price limits or material warranty durations shown', !/per sq|per sheet|per running|₹2,500|\d+\s*-?\s*(year|years|yr)\b|up to \d/i.test(text));
check('technical assumptions collapsed by default, plain assumptions shown', (await page.locator('#v2-result-body details:has(summary:has-text("View technical assumptions"))').evaluate((d) => !d.open)) &&
  /Three wardrobes with lofts/.test(text) && /Whole-home ceiling and lighting based on typical 3 BHK dimensions/.test(text) && !/assumed \d/.test(text.split('View technical assumptions')[0].split('Typical 3 BHK assumptions used').pop()));
const steps = await page.locator('#v2-next-steps ol li').allTextContents();
check('what happens next: six steps', steps.length === 6 && /approve the scope before any work starts/.test(steps[5]));
const ctas = await page.locator('#v2-next-steps button').allTextContents();
check('CTA hierarchy', ctas.join(' | ') === 'Personalise and narrow my estimate | Get my detailed quotation | Talk to a designer', ctas.join(' | '));
// Keyboard: a room's details open from the keyboard alone.
await page.focus('#v2-h6');
let reached = false;
for (let i = 0; i < 80 && !reached; i += 1) {
  await page.keyboard.press('Tab');
  reached = await page.evaluate(() => document.activeElement?.tagName === 'SUMMARY' && document.activeElement.textContent === 'View inclusions & materials');
}
if (reached) await page.keyboard.press('Enter');
check('keyboard: Tab reaches a room and Enter opens its inclusions and materials', reached && await page.evaluate(() => document.activeElement.parentElement.open));
check('screen reader: the range is announced, every result section is named', (await page.getAttribute('#v2-h6', 'aria-live')) === 'polite' &&
  (await page.locator('#v2-result-body > section').evaluateAll((ss) => ss.every((x) => x.getAttribute('aria-label') && x.querySelector('h3')))));
await shot('6-result');
await page.evaluate(() => document.querySelectorAll('#est-v2 details').forEach((d) => { d.open = true; }));
await axe('V2 6 result');
check('360 px without horizontal scroll (result)', (await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)) <= 1);
// 3. Detailed material specification on demand.
await page.click('#v2-result-body button:has-text("View detailed material specification")');
check('detailed specification screen', await visible(10) && (await page.locator('#v2-spec .v2-spec-cat').count()) === v2run.data.specification.categories.length);
const terms = await page.locator('#v2-spec .v2-spec-cat').evaluateAll((cats) => cats.map((c) => [...c.querySelectorAll('dt')].map((d) => d.textContent)));
check('every category separates requirement, equivalent rule and final selection (T3)', terms.every((t) => ['Material requirement', 'Approved equivalent', 'Final selection'].every((x) => t.includes(x))));
await axe('V2 10 specification');
await shot('10-specification');
await page.click('#v2-spec-back');
// 4. Refinement without engineering terms: one measurement, a new estimate.
await page.click('#v2-next-steps button:has-text("Personalise and narrow my estimate")');
const refineText = await page.locator('[data-v2="8"]').innerText();
check('refinement in customer words (ft and sq ft only)', !/RUN|WIDTH|AREA|carcass|uom/.test(refineText) && (await page.locator('#v2-refine input').count()) === 4);
await axe('V2 8 refine');
await shot('8-refine');
await page.fill('#v2-m-kitchen-kitchen', '16');
const refineReq = page.waitForRequest((r) => r.url().endsWith('/api/v1/public/estimates') && r.method() === 'POST');
await page.click('#v2-update');
const refinedBody = JSON.parse((await refineReq).postData());
await page.waitForFunction((before) => document.getElementById('v2-refined').textContent && document.getElementById('v2-refined').textContent !== before, await page.textContent('#v2-range'));
check('refinement sends the measurement and updates the estimate', refinedBody.selections.find((s) => s.product === 'KITCHEN').measurements.RUN?.value === 16);
// 5. Lead capture: linked errors, then a request linked to the latest estimate.
await page.click('[data-v2="8"] [data-v2-goto="7"]');
await page.click('#v2-send');
check('lead errors linked to fields', (await page.locator('#v2-summary a').count()) === 3 && (await page.getAttribute('#v2-name', 'aria-invalid')) === 'true');
await axe('V2 7 lead (errors)');
await page.fill('#v2-name', 'Meera Iyer');
await page.fill('#v2-phone', '98480 23456');
await page.check('#v2-consent');
const enq = page.waitForRequest((r) => r.url().endsWith('/api/v1/public/enquiries'));
await page.click('#v2-send');
const enquiryBody = JSON.parse((await enq).postData());
await page.waitForSelector('[data-v2="9"]:not([hidden])');
check('enquiry links the latest estimate; customer reference shown', /^[0-9A-Z]{4}-[0-9A-Z]{4}$/.test((await page.textContent('#v2-reference')) || '') && enquiryBody.estimate_reference && !enquiryBody.consultation);
await axe('V2 9 confirmation');
await shot('9-confirmation');
// 6. Talk to a designer and Luxury: consultation requests without an amount.
await fresh();
await toResult();
await page.click('#v2-next-steps button:has-text("Talk to a designer")');
check('talk to a designer: consultation, no amount', (await page.textContent('#v2-h7')) === 'Request a design consultation' && !/₹/.test(await page.locator('[data-v2="7"]').innerText()));
await fresh();
await next(1); await page.check('input[name="v2-size"][value="3BHK"]'); await next(2); await next(3); await next(4);
await page.check('input[name="v2-pkg"][value="LUXURY"]');
let luxuryCalls = 0;
page.on('request', (r) => { if (r.url().endsWith('/api/v1/public/estimates')) luxuryCalls += 1; });
await page.click('#v2-see');
check('Luxury: consultation without any price request', await visible(7) && luxuryCalls === 0);
// Optional items (painting) sit outside the room subtotals but inside the range: the build-up still adds up.
await fresh();
await next(1); await page.check('input[name="v2-size"][value="3BHK"]'); await next(2); await next(3);
await page.locator('.v2-room', { hasText: 'Whole home' }).locator('summary').click();
await page.check('#v2-x-whole-painting');
await next(4);
const optRes = page.waitForResponse((r) => r.url().endsWith('/api/v1/public/estimates'));
await page.click('#v2-see');
const optData = (await (await optRes).json()).data;
await page.waitForSelector('[data-v2="6"]:not([hidden])');
const optRows = await page.locator('#v2-build dd[data-low]').evaluateAll((dds) => dds.map((d) => [d.previousElementSibling.textContent, Number(d.dataset.low), Number(d.dataset.high)]));
const optParts = optRows.slice(0, -1);
check('optional items shown in the build-up, which still reconciles', optData.optional_items_minor > 0 && optParts.some((r) => r[0].includes('Optional items')) &&
  optParts.reduce((a, r) => a + r[1], 0) === optData.range.low_minor && optParts.reduce((a, r) => a + r[2], 0) === optData.range.high_minor &&
  /Premium emulsion/.test(optData.room_details.find((d) => d.room === 'WHOLE_HOME').materials?.line || ''));
await collectCsp();

// 7. V1/V2 equivalence: drive V1 with exactly the selections V2 sent (same rooms, products, effective options).
const defaults = Object.fromEntries(CARD.products.map((p) => [p.code, Object.fromEntries((p.options || []).map((o) => [o.name, o.default]))]));
const want = v2run.body.selections.map((s) => ({ room: s.room, product: s.product, options: { ...defaults[s.product], ...s.options } }));
await page.goto(`${ON}/estimate`);
await page.evaluate(() => sessionStorage.clear());
await page.goto(`${ON}/estimate?v1=1`);
await page.selectOption('#est-home-size', '3BHK');
await page.click('#step-1 button[type="submit"]');
for (const w of want) await page.check(`input[value="${w.room}:${w.product}"]`);
await page.click('#step-2 button[type="submit"]');
await page.click('#step-3 button[type="submit"]');
const items = await page.evaluate(() => JSON.parse(sessionStorage.getItem('veda-estimate-v1')).items.map((i) => `${i.room}:${i.product}`));
for (const [idx, key] of items.entries()) {
  const w = want.find((x) => `${x.room}:${x.product}` === key);
  for (const [name, value] of Object.entries(w.options)) {
    const sel = page.locator(`[data-item="${idx}"][data-option="${name}"]`);
    if (await sel.count()) await sel.selectOption(value);
  }
}
const v1res = page.waitForResponse((r) => r.url().endsWith('/api/v1/public/estimates'));
await page.click('#est-calculate');
const v1data = (await (await v1res).json()).data;
const rooms = (d) => JSON.stringify([...d.rooms].map((r) => [r.room, r.amount_minor]).sort());
if (!QUIET && rooms(v1data) !== rooms(v2run.data)) console.log('rooms V1', rooms(v1data), 'V2', rooms(v2run.data));
const same = v1data.range.low_minor === v2run.data.range.low_minor && v1data.range.high_minor === v2run.data.range.high_minor &&
  rooms(v1data) === rooms(v2run.data) &&
  v1data.custom_features_allowance.low_minor === v2run.data.custom_features_allowance.low_minor &&
  v1data.project_preparation.amount_minor === v2run.data.project_preparation.amount_minor;
check('V1/V2 equivalence: same selections give the same range, rooms, package and allowance', same,
  QUIET ? '' : `V1 ${v1data.range.low_minor}–${v1data.range.high_minor} · V2 ${v2run.data.range.low_minor}–${v2run.data.range.high_minor}`);

check('no Content-Security-Policy violations under the production policy', csp.length === 0, csp.slice(0, 3).join('; '));
check('no page errors', errors.length === 0, errors.join('; '));
await browser.close();
console.log(`${results.filter(Boolean).length}/${results.length} estimator V2 checks passed`);
process.exitCode = results.every(Boolean) ? 0 : 1;
