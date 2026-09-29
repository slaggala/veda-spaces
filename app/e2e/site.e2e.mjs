// Website enquiry form states (09 §4.11, AX-08, LEAD-019) against a running API, under the production CSP.
//   node e2e/static-server.mjs ../dist 8000 http://localhost:5000   (intake on, test Turnstile key)
//   node e2e/static-server.mjs ../dist 8001                         (flag off, production headers)
//   SITE_ON=http://localhost:8000 SITE_OFF=http://localhost:8001 node e2e/site.e2e.mjs
// Turnstile is replaced by a local stub (no network), which records resets (IR-18).
import { chromium } from 'playwright';

const ON = process.env.SITE_ON ?? 'http://localhost:8000';
const OFF = process.env.SITE_OFF ?? 'http://localhost:8001';
const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`); };

const TURNSTILE_STUB = `window.__ts = { resets: 0, n: 0 };
window.turnstile = { render() { return 'w1'; }, getResponse() { return 'stub-token-' + window.__ts.n; },
  reset() { window.__ts.resets += 1; window.__ts.n += 1; } };`;

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
const formDisplay = () => page.evaluate(() => getComputedStyle(document.getElementById('contact-form')).display);
const fillValid = async (name = 'Meera Iyer') => {
  await page.fill('#cf-name', name);
  await page.fill('#cf-phone', '98480 12345');
  await page.check('#cf-consent');
};
const submit = () => page.locator('#contact-form button[type="submit"]').click();
let visits = 0;
// A fresh document for every case: a hash-only navigation would keep the previous form state.
const open = async (base) => {
  await page.goto(`${base}/?visit=${++visits}#contact`);
  if (base === ON) await page.waitForFunction(() => window.turnstile !== undefined);
};

// 1. Field-level validation: error summary receives focus, fields are marked invalid; built without innerHTML.
await open(ON);
await submit();
const summaryFocused = await page.evaluate(() => document.activeElement?.id === 'form-summary');
const invalid = await page.locator('#contact-form [aria-invalid="true"]').count();
check('error summary focused with invalid fields', summaryFocused && invalid >= 3, `${invalid} invalid`);

// 2. Honeypot is never focusable or announced.
const hp = await page.evaluate(() => {
  const el = document.getElementById('cf-website');
  return { tab: el.tabIndex, hidden: el.closest('[aria-hidden="true"]') !== null, left: el.getBoundingClientRect().left };
});
check('honeypot off-screen, aria-hidden, not tabbable', hp.tab === -1 && hp.hidden && hp.left < -1000);

// 3. Server-side 422 after client validation passes → field error, Turnstile reset, corrected resubmit → 201 (IR-18).
await page.fill('#cf-name', '12');
await page.fill('#cf-phone', '98480 12345');
await page.check('#cf-consent');
await submit();
await page.locator('#cf-name[aria-invalid="true"]').waitFor();
const resets = await page.evaluate(() => window.__ts.resets);
check('server 422 shows the field error and resets Turnstile', resets === 1, `resets=${resets}`);
await page.fill('#cf-name', 'Meera Iyer');
await page.selectOption('#cf-property', 'VILLA');
await page.fill('#cf-brief', 'Renovating a 4BHK villa');
await submit();
await page.locator('#form-success').waitFor({ state: 'visible' });
const ref = await page.textContent('#form-reference');
const panelFocused = await page.evaluate(() => document.activeElement?.id === 'form-success');
check('corrected resubmission → 201 with reference, panel focused', /^[0-9A-Z]{4}-[0-9A-Z]{4}$/.test(ref) && panelFocused, ref);
check('form hidden after success (IR-17)', (await formDisplay()) === 'none', await formDisplay());
await collectCsp();

// 4. Unknown policy version → WhatsApp fallback, never an inline field error (IR-31).
await open(ON);
await page.evaluate(() => { document.querySelector('meta[name="veda-policy-version"]').content = '1999-01-v0'; });
await fillValid('Kavya Rao');
await submit();
await page.locator('#form-fallback').waitFor({ state: 'visible' });
const staleText = await page.textContent('#fallback-message');
check('UNKNOWN_POLICY_VERSION → fallback with reload prompt', /reload/i.test(staleText) &&
  (await page.locator('#contact-form [aria-invalid="true"]').count()) === 0, staleText.slice(0, 50));
check('form hidden after fallback (IR-17)', (await formDisplay()) === 'none');
await collectCsp();

// 5. Network failure → WhatsApp fallback with the prefilled enquiry.
await open(ON);
await page.route('**/api/v1/public/leads', (route) => route.abort());
await fillValid('Ravi Kumar');
await submit();
await page.locator('#form-fallback').waitFor({ state: 'visible' });
const href = await page.getAttribute('#fallback-whatsapp', 'href');
check('network error offers prefilled WhatsApp', href.startsWith('https://wa.me/919515125153?text=') && decodeURIComponent(href).includes('Ravi Kumar'));
await page.unroute('**/api/v1/public/leads');
await collectCsp();

// 6. Flag off → the original WhatsApp hand-off: no API call, no consent block, no Privacy Notice link.
await open(OFF);
let apiCalls = 0;
page.on('request', (r) => { if (r.url().includes('/api/v1/')) apiCalls += 1; });
const offState = await page.evaluate(() => ({
  consentShown: !document.querySelector('.consent').hidden, privacyLinks: [...document.querySelectorAll('a[href="/privacy"]')]
    .filter((a) => a.offsetParent !== null).length, turnstile: !!document.querySelector('script[src*="turnstile"]'),
}));
check('flag off hides consent, verification and the Privacy Notice link', !offState.consentShown && offState.privacyLinks === 0 &&
  !offState.turnstile, JSON.stringify(offState));
const popup = page.waitForEvent('popup');
await page.fill('#cf-name', 'Asha');
await page.fill('#cf-phone', '9876543210');
await submit();
const pop = await popup;
check('flag off keeps the WhatsApp hand-off', pop.url().startsWith('https://') && apiCalls === 0, pop.url().slice(0, 40));
await pop.close();
await collectCsp();

// 7. Mobile width (360 px) without horizontal scroll, in both modes.
await page.setViewportSize({ width: 360, height: 800 });
for (const base of [ON, OFF]) {
  await open(base);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check(`360 px without horizontal scroll (${base === ON ? 'on' : 'off'})`, overflow <= 1, `${overflow}px`);
  await collectCsp();
}

check('no Content-Security-Policy violations under the production policy', csp.length === 0, csp.slice(0, 3).join('; '));
check('no page errors', errors.length === 0, errors.join('; '));
await browser.close();
console.log(`${results.filter(Boolean).length}/${results.length} site checks passed`);
process.exitCode = results.every(Boolean) ? 0 : 1;
