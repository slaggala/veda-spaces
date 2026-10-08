// Budgetary Estimate wizard (ADR-012, owner instruction Part D) against a running API with the SYNTHETIC rate card,
// under the production Content-Security-Policy. Turnstile is a local stub (no network).
//   SITE_ON=http://localhost:8000 SITE_OFF=http://localhost:8001 node e2e/estimator.e2e.mjs
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const ON = process.env.SITE_ON ?? 'http://localhost:8000';
const OFF = process.env.SITE_OFF ?? 'http://localhost:8001';
const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`); };
const TURNSTILE_STUB = `window.turnstile = { render() { return 'w' + Math.random(); }, getResponse() { return 'stub-token'; }, reset() {} };`;

const browser = await chromium.launch();
const context = await browser.newContext();
await context.addInitScript(() => {
  window.__csp = [];
  document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI}`));
});
await context.route('https://challenges.cloudflare.com/**', (route) =>
  route.fulfill({ status: 200, contentType: 'text/javascript', body: TURNSTILE_STUB }));
const page = await context.newPage();
const errors = [];
const csp = [];
page.on('pageerror', (e) => errors.push(String(e)));
const collectCsp = async () => { csp.push(...(await page.evaluate(() => window.__csp || []))); };
// axe is loaded through the DevTools protocol (page.evaluate), which the page's CSP does not govern, so the journey
// itself keeps running under the real production policy (and is checked for violations below). preload is off because
// axe would otherwise fetch the cross-origin font stylesheet with XHR, which connect-src rightly blocks; that request is
// the test's, not the page's.
async function axe(name) {
  await page.evaluate(AXE);
  const violations = await page.evaluate(async () => {
    const res = await window.axe.run(document.querySelector('main'), { preload: false,
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } });
    return res.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
  });
  check(`axe: ${name}`, violations.length === 0, violations.join(', '));
}
const visible = (sel) => page.locator(sel).isVisible();

// 1. Off (committed page, production): "coming soon", no wizard, no request.
await page.goto(`${OFF}/estimate`);
check('off: coming-soon panel shown, wizard hidden', (await visible('#est-off')) && !(await visible('#est-app')));
await collectCsp();

// 2. On: step 1 → 2 → 3 → 4 → estimate.
await page.goto(`${ON}/estimate?visit=1`);
await page.evaluate(() => sessionStorage.clear());
await page.goto(`${ON}/estimate?visit=2`);
check('on: wizard shown', await visible('#step-1'));
await axe('step 1 (home)');
await page.selectOption('#est-home-size', '2BHK');
await page.fill('#est-city', 'Kondapur, Hyderabad');
await page.click('#step-1 button[type="submit"]');
await page.check('input[value="MASTER_BEDROOM:WARDROBE"]');
await page.check('input[value="KITCHEN:KITCHEN"]');
await axe('step 2 (rooms)');
await page.click('#step-2 button[type="submit"]');
check('step 3 lists a measurement per input', (await page.locator('[data-role="value"]').count()) >= 4);
// Unticking "typical" without a value is refused with a focused summary.
// The wizard lists items in room order (kitchen first); only the wardrobe has a WIDTH here.
await page.uncheck('[data-input="WIDTH"][data-role="typical"]');
await page.click('#step-3 button[type="submit"]');
check('missing measurement → focused summary', await page.evaluate(() => document.activeElement?.id === 'est-summary'));
await page.fill('[data-input="WIDTH"][data-role="value"]', '6');
await axe('step 3 (measurements)');
await page.click('#step-3 button[type="submit"]');
const premiumDisabled = await page.locator('input[name="package"][value="PREMIUM"]').isDisabled();
check('step 4: Premium and Luxury unavailable without approved rates', premiumDisabled &&
  (await page.locator('input[name="package"][value="LUXURY"]').isDisabled()));
await page.selectOption('[data-option="DOOR"]', 'SLIDING');
await axe('step 4 (preferences)');
await page.click('#est-calculate');
await page.waitForSelector('#step-5:not([hidden])');
const result = await page.evaluate(() => ({
  title: document.getElementById('est-result-title').textContent,
  range: document.getElementById('est-range').textContent,
  prep: document.getElementById('est-prep-label').textContent,
  disclaimer: document.getElementById('est-disclaimer').textContent,
  assumptions: document.querySelectorAll('#est-assumptions li').length,
  text: document.querySelector('main').innerText,
}));
check('result: title, range, grouped preparation package, disclaimer', result.title === 'VEDA SPACES PRELIMINARY BUDGETARY ESTIMATE' &&
  /₹[\d,]+ – ₹[\d,]+/.test(result.range) && result.prep === 'Project Preparation & Protection Package' &&
  result.disclaimer.startsWith('This is a preliminary budgetary estimate'), JSON.stringify(result.range));
check('result: typical sizes labelled as assumptions', result.assumptions >= 2);
check('result: no "mandatory" framing and no line rates', !/mandatory/i.test(result.text) && !/per sq/i.test(result.text));
await axe('step 5 (estimate)');

// 3. Enquiry linked to the estimate → customer reference only.
await page.click('#est-to-quote');
await page.fill('#eq-name', 'Meera Iyer');
await page.fill('#eq-phone', '98480 12345');
await page.check('#eq-consent');
await axe('step 6 (enquiry)');
await page.click('#eq-submit');
await page.waitForSelector('#step-7:not([hidden])');
const ref = await page.textContent('#eq-reference');
check('enquiry → confirmation with a customer reference', /^[0-9A-Z]{4}-[0-9A-Z]{4}$/.test(ref || ''), ref);
await collectCsp();

// 4. Mobile width.
await page.setViewportSize({ width: 360, height: 800 });
await page.goto(`${ON}/estimate?visit=3`);
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
check('360 px without horizontal scroll', overflow <= 1, `${overflow}px`);
await collectCsp();

check('no Content-Security-Policy violations under the production policy', csp.length === 0, csp.slice(0, 3).join('; '));
check('no page errors', errors.length === 0, errors.join('; '));
await browser.close();
console.log(`${results.filter(Boolean).length}/${results.length} estimator checks passed`);
process.exitCode = results.every(Boolean) ? 0 : 1;
