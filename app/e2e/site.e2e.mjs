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

// 6. Flag off (the live configuration) → the WhatsApp hand-off, only after the required fields validate (RR-11):
//    no API call, no consent block, no Privacy Notice link, and never a blank enquiry.
await open(OFF);
let apiCalls = 0;
let popups = 0;
page.on('request', (r) => { if (r.url().includes('/api/')) apiCalls += 1; });
page.on('popup', () => { popups += 1; });
const offState = await page.evaluate(() => ({
  consentShown: !document.querySelector('.consent').hidden, privacyLinks: [...document.querySelectorAll('a[href="/privacy"]')]
    .filter((a) => a.offsetParent !== null).length, turnstile: !!document.querySelector('script[src*="turnstile"]'),
}));
check('flag off hides consent, verification and the Privacy Notice link', !offState.consentShown && offState.privacyLinks === 0 &&
  !offState.turnstile, JSON.stringify(offState));
const offErrors = () => page.evaluate(() => ({
  invalid: [...document.querySelectorAll('#contact-form [aria-invalid="true"]')].map((el) => el.id).sort(),
  summary: document.querySelector('#form-summary').hidden ? '' : document.querySelector('#form-summary').textContent,
  role: document.querySelector('#form-summary').getAttribute('role'),
  focused: document.activeElement?.id,
}));
const settle = () => page.waitForTimeout(300);
const cases = [
  ['empty submission', '', '', ['cf-name', 'cf-phone']],
  ['missing name', '', '98480 12345', ['cf-name']],
  ['missing phone', 'Asha Reddy', '', ['cf-phone']],
  ['invalid phone', 'Asha Reddy', '12ab34', ['cf-phone']],
  ['too-short phone', 'Asha Reddy', '98480', ['cf-phone']],
];
for (const [label, name, phone, expected] of cases) {
  await open(OFF);
  await page.fill('#cf-name', name);
  await page.fill('#cf-phone', phone);
  await submit();
  await settle();
  const st = await offErrors();
  const values = await page.evaluate(() => [document.querySelector('#cf-name').value, document.querySelector('#cf-phone').value]);
  check(`flag off: ${label} → no WhatsApp, errors shown and announced`,
    popups === 0 && JSON.stringify(st.invalid) === JSON.stringify(expected) && st.role === 'alert' && st.focused === 'form-summary' &&
    /Please fix/.test(st.summary) && values[0] === name && values[1] === phone, JSON.stringify(st));
}
check('flag off: consent is never required or claimed', !(await offErrors()).invalid.includes('cf-consent'));

// Valid fallback: WhatsApp opens once, the message carries only the entered fields, safely encoded.
// wa.me is stubbed so the popup URL is exactly what the page built (no external navigation).
await page.context().route('https://wa.me/**', (route) => route.fulfill({ status: 200, contentType: 'text/html', body: 'ok' }));
await open(OFF);
const special = 'Zoë & "O\'Brien" <b>#1</b>';
await page.fill('#cf-name', special);
await page.fill('#cf-phone', '+91 (98480) 12-345');
await page.fill('#cf-brief', 'Kitchen &text=injected#frag %20 ✓');
await page.fill('#cf-website', 'bot-value');
let popupWait = page.waitForEvent('popup');
await submit();
let pop = await popupWait;
let waUrl = new URL(pop.url());
const text = waUrl.searchParams.get('text') || '';
check('flag off: valid submission opens WhatsApp with the entered details', waUrl.origin === 'https://wa.me' &&
  waUrl.pathname === '/919515125153' && [...waUrl.searchParams.keys()].join() === 'text' && text.includes(`Name: ${special}`) &&
  text.includes('Phone: +91 (98480) 12-345') && text.includes('Requirements: Kitchen &text=injected#frag %20 ✓') && waUrl.hash === '',
  text.split('\n')[2]);
check('flag off: message has no honeypot, consent or API configuration', !/bot-value|consent|Privacy|api|turnstile|token/i.test(text));
await pop.close();

// Keyboard submission (Enter in a field) follows the same validation, then hands off when valid.
await open(OFF);
const before = popups;
await page.focus('#cf-name');
await page.keyboard.press('Enter');
await settle();
check('flag off: Enter on an empty form is blocked', popups === before && (await offErrors()).focused === 'form-summary');
await page.fill('#cf-name', 'Asha Reddy');
await page.fill('#cf-phone', '9876543210');
popupWait = page.waitForEvent('popup');
await page.focus('#cf-phone');
await page.keyboard.press('Enter');
pop = await popupWait;
waUrl = new URL(pop.url());
check('flag off: Enter on a valid form hands off to WhatsApp', (waUrl.searchParams.get('text') || '').includes('Name: Asha Reddy'));
await pop.close();

// Mobile viewport: errors shown and focusable without horizontal scroll.
await page.setViewportSize({ width: 360, height: 800 });
await open(OFF);
const beforeMobile = popups;
await submit();
await settle();
const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
check('flag off: mobile empty submission blocked without overflow', popups === beforeMobile &&
  (await offErrors()).invalid.length === 2 && mobileOverflow <= 1, `${mobileOverflow}px`);
await page.setViewportSize({ width: 1280, height: 900 });
check('flag off: no API call in any case', apiCalls === 0, `${apiCalls} calls`);
await collectCsp();

// 6b. 404 page under the production headers (RR-01): HTTP 404, styled by /assets/404.css, no inline code, 0 CSP violations.
for (const path of ['/no-such-page', '/404.html', '/privacy']) {
  const res = await page.goto(`${OFF}${path}`);
  const info = await page.evaluate(() => ({
    bg: getComputedStyle(document.body).backgroundColor, h1: document.querySelector('h1')?.textContent,
    grid: getComputedStyle(document.querySelector('main')).display,
    inline: document.querySelectorAll('style, script:not([src]), [style]').length,
    handlers: [...document.querySelectorAll('*')].filter((el) => [...el.attributes].some((a) => a.name.startsWith('on'))).length,
    css: [...document.styleSheets].some((sh) => (sh.href || '').endsWith('/assets/404.css') && sh.cssRules.length > 10),
  }));
  const status = path === '/404.html' ? 200 : 404;
  check(`404 page ${path}: HTTP ${status}, styled, no inline code`, res.status() === status && info.bg === 'rgb(251, 247, 239)' &&
    info.grid === 'grid' && info.css && info.inline === 0 && info.handlers === 0 && /This room/.test(info.h1 || ''),
    `status=${res.status()} ${JSON.stringify(info)}`);
  await collectCsp();
}
await page.setViewportSize({ width: 360, height: 800 });
await page.goto(`${OFF}/no-such-page`);
const nf = await page.evaluate(() => ({
  overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  cols: getComputedStyle(document.querySelector('main')).gridTemplateColumns.split(' ').length,
}));
check('404 page at 360 px: single column, no horizontal scroll', nf.overflow <= 1 && nf.cols === 1, JSON.stringify(nf));
await page.keyboard.press('Tab');
const firstFocus = await page.evaluate(() => ({ label: document.activeElement?.getAttribute('aria-label'),
  outline: getComputedStyle(document.activeElement).outlineStyle }));
check('404 page: first Tab reaches the home link with a visible focus ring', firstFocus.label === 'Veda Spaces home' &&
  firstFocus.outline === 'solid', JSON.stringify(firstFocus));
await collectCsp();
// The homepage and its assets still load under the same policy.
const home = await page.goto(`${OFF}/`);
check('homepage still returns 200 with its stylesheet', home.status() === 200 &&
  (await page.evaluate(() => [...document.styleSheets].some((sh) => (sh.href || '').endsWith('/assets/styles.css')))));
await page.setViewportSize({ width: 1280, height: 900 });
await collectCsp();

// 7. Mobile width (360 px) without horizontal scroll, in both modes.
await page.setViewportSize({ width: 360, height: 800 });
for (const base of [ON, OFF]) {
  await open(base);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check(`360 px without horizontal scroll (${base === ON ? 'on' : 'off'})`, overflow <= 1, `${overflow}px`);
  await collectCsp();
}

// 8. Warranty, Service & Customer Care Policy page (/warranty): readable on a phone, linked from the footer.
await page.setViewportSize({ width: 360, height: 800 });
await page.goto(`${OFF}/warranty`);
const policy = await page.evaluate(() => ({
  h1: document.querySelector('h1')?.textContent,
  sections: [...document.querySelectorAll('main h2[id]')].map((h) => h.id),
  overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  tel: !!document.querySelector('section[aria-labelledby="contact"] a[href="tel:+919515125153"]'),
}));
check('warranty page: summary first, then terms, service, exclusions and contact', policy.h1 === 'Warranty, Service & Customer Care Policy' &&
  policy.sections[0] === 'summary' && ['coverage', 'exclusions', 'service', 'claims', 'contact'].every((id) => policy.sections.includes(id)) && policy.tel,
  JSON.stringify({ h1: policy.h1, tel: policy.tel, sections: policy.sections.join(',') }));
check('warranty page: 360 px without horizontal scroll', policy.overflow <= 1, `${policy.overflow}px`);
await collectCsp();
await page.setViewportSize({ width: 1280, height: 900 });
await page.goto(`${OFF}/`);
check('footer links the warranty policy', (await page.locator('footer a[href="/warranty"]').count()) === 1);
await collectCsp();

check('no Content-Security-Policy violations under the production policy', csp.length === 0, csp.slice(0, 3).join('; '));
check('no page errors', errors.length === 0, errors.join('; '));
await browser.close();
console.log(`${results.filter(Boolean).length}/${results.length} site checks passed`);
process.exitCode = results.every(Boolean) ? 0 : 1;
