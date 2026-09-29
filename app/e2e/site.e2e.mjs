// Website enquiry form states (09 §4.11, AX-08, LEAD-019) against a running API.
//   SITE_ON=http://localhost:8000 (veda-api-base set)  SITE_OFF=http://localhost:8001 (flag off)
import { chromium } from 'playwright';

const ON = process.env.SITE_ON ?? 'http://localhost:8000';
const OFF = process.env.SITE_OFF ?? 'http://localhost:8001';
const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`); };

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));

// 1. Field-level validation: error summary receives focus, fields are marked invalid.
await page.goto(`${ON}/#contact`);
await page.locator('#contact-form button[type="submit"]').click();
const summaryFocused = await page.evaluate(() => document.activeElement?.id === 'form-summary');
const invalid = await page.locator('#contact-form [aria-invalid="true"]').count();
check('error summary focused with invalid fields', summaryFocused && invalid >= 3, `${invalid} invalid`);

// 2. Honeypot is never focusable or announced.
const hp = await page.evaluate(() => {
  const el = document.getElementById('cf-website');
  return { tab: el.tabIndex, hidden: el.closest('[aria-hidden="true"]') !== null, left: el.getBoundingClientRect().left };
});
check('honeypot off-screen, aria-hidden, not tabbable', hp.tab === -1 && hp.hidden && hp.left < -1000);

// 3. Successful submission → confirmation panel with the public reference.
await page.fill('#cf-name', 'Meera Iyer');
await page.fill('#cf-phone', '98480 12345');
await page.selectOption('#cf-property', 'VILLA');
await page.selectOption('#cf-service', 'RENOVATION');
await page.selectOption('#cf-budget', '20L_35L');
await page.fill('#cf-brief', 'Renovating a 4BHK villa');
await page.check('#cf-consent');
await page.locator('#contact-form button[type="submit"]').click();
await page.locator('#form-success').waitFor({ state: 'visible' });
const ref = await page.textContent('#form-reference');
const panelFocused = await page.evaluate(() => document.activeElement?.id === 'form-success');
check('201 shows the reference and focuses the panel', /^[0-9A-Z]{4}-[0-9A-Z]{4}$/.test(ref) && panelFocused, ref);

// 4. Network failure → WhatsApp fallback with the prefilled enquiry.
await page.goto(`${ON}/#contact`);
await page.route('**/api/v1/public/leads', (route) => route.abort());
await page.fill('#cf-name', 'Ravi Kumar');
await page.fill('#cf-phone', '9876543210');
await page.check('#cf-consent');
await page.locator('#contact-form button[type="submit"]').click();
await page.locator('#form-fallback').waitFor({ state: 'visible' });
const href = await page.getAttribute('#fallback-whatsapp', 'href');
check('network error offers prefilled WhatsApp', href.startsWith('https://wa.me/919515125153?text=') && decodeURIComponent(href).includes('Ravi Kumar'));
await page.unroute('**/api/v1/public/leads');

// 5. Flag off → unchanged WhatsApp hand-off (no API call).
await page.goto(`${OFF}/#contact`);
let apiCalls = 0;
page.on('request', (r) => { if (r.url().includes('/api/v1/')) apiCalls += 1; });
const popup = page.waitForEvent('popup');
await page.fill('#cf-name', 'Asha');
await page.fill('#cf-phone', '9876543210');
await page.locator('#contact-form button[type="submit"]').click();
const pop = await popup;
check('flag off keeps the WhatsApp hand-off', pop.url().startsWith('https://') && apiCalls === 0, pop.url().slice(0, 40));

// 6. Mobile width (360 px) without horizontal scroll.
await page.setViewportSize({ width: 360, height: 800 });
await page.goto(`${ON}/#contact`);
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
check('360 px without horizontal scroll', overflow <= 1, `${overflow}px`);

check('no page errors', errors.length === 0, errors.join('; '));
await browser.close();
console.log(`${results.filter(Boolean).length}/${results.length} site checks passed`);
process.exitCode = results.every(Boolean) ? 0 : 1;
