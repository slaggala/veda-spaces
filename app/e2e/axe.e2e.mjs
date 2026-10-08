// axe-core WCAG 2.x A/AA scan of key screens (09 §5, AX-01…AX-08 automated subset). Needs a running stack,
// E2E_OUT/founder.json from workspace.e2e.mjs, and the website served at SITE_ON.
import crypto from 'node:crypto';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const BASE = process.env.APP_BASE ?? 'http://localhost:5173';
const SITE = process.env.SITE_ON ?? 'http://localhost:8000';
const OUT = process.env.E2E_OUT ?? 'e2e-artifacts';
const founder = JSON.parse(fs.readFileSync(`${OUT}/founder.json`, 'utf8'));

function b32(s) {
  const a = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const ch of s) bits += a.indexOf(ch).toString(2).padStart(5, '0');
  const out = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) out.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(out);
}
async function totp(secret) {
  const step = Math.floor(Date.now() / 30000);
  await new Promise((r) => setTimeout(r, (step + 1) * 30000 - Date.now() + 500));
  const msg = Buffer.alloc(8);
  msg.writeBigUInt64BE(BigInt(step + 1));
  const mac = crypto.createHmac('sha1', b32(secret)).update(msg).digest();
  const off = mac[mac.length - 1] & 0xf;
  return String((mac.readUInt32BE(off) & 0x7fffffff) % 1e6).padStart(6, '0');
}
// The enquiry form and its result panels are in scope for the site gate (AX-08, LEAD-019). Contrast problems in the
// pre-existing marketing sections outside them are reported and tracked (OI-11), not gated.
const FORM_SCOPE = ['#contact-form', '#form-success', '#form-fallback'];
async function scan(page, name, { gateScope = null } = {}) {
  await page.addScriptTag({ content: AXE });
  const nodes = await page.evaluate(async (scope) => {
    const res = await window.axe.run(document, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } });
    return res.violations.flatMap((v) => v.nodes.map((n) => {
      const el = typeof n.target[0] === 'string' ? document.querySelector(n.target[0]) : null;
      return { rule: v.id, impact: v.impact, target: n.target.join(' '),
        inScope: !scope || Boolean(el && el.closest(scope.join(','))) };
    }));
  }, gateScope);
  const serious = nodes.filter((n) => n.inScope && ['serious', 'critical'].includes(n.impact));
  const tracked = nodes.filter((n) => !n.inScope).length;
  console.log(`${serious.length ? 'FAIL' : 'PASS'} ${name}: ${serious.length} serious/critical in scope` +
    `${gateScope ? `, ${tracked} tracked outside the form (OI-11)` : ''}`);
  for (const s of serious) console.log(`   - ${s.rule} ${s.target}`);
  return serious.length === 0;
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const ok = [];
await page.goto(`${BASE}/login`);
await page.getByRole('button', { name: /Sign in/ }).waitFor();
ok.push(await scan(page, 'login'));
await page.getByLabel('Email', { exact: true }).fill(founder.email);
await page.getByLabel('Password', { exact: true }).fill(founder.password);
await page.getByRole('button', { name: /Sign in/ }).click();
await page.locator('input[autocomplete="one-time-code"]:visible').first().waitFor();
ok.push(await scan(page, 'MFA challenge'));
await page.locator('input[autocomplete="one-time-code"]:visible').first().fill(await totp(founder.secret));
await page.getByRole('button', { name: /Verify/ }).click();
await page.waitForURL((u) => !u.pathname.startsWith('/login') && !u.pathname.startsWith('/mfa'));
for (const [name, path, wait] of [['dashboard', '/', /Good (morning|afternoon|evening)/], ['lead list', '/leads', 'Anita Reddy'],
  ['users', '/admin/users', 'Users'], ['roles', '/admin/roles', 'Roles'], ['audit log', '/audit', 'Audit log']]) {
  await page.goto(`${BASE}${path}`);
  await page.getByText(wait).first().waitFor();
  await page.waitForTimeout(500);
  ok.push(await scan(page, name));
}
await page.goto(`${BASE}/leads`);
await page.getByText('Anita Reddy').first().click();
await page.getByText(/VS-L-\d{4}-\d{6}/).first().waitFor();
ok.push(await scan(page, 'lead detail'));

// RR-18: the states the re-review found (UI-016 AX-01, AX-09), scanned and exercised in the running app.
function check(name, pass, detail = '') {
  console.log(`${pass ? 'PASS' : 'FAIL'} ${name}${detail ? ` (${detail})` : ''}`);
  ok.push(Boolean(pass));
}
// Lead detail tabs: tablist, tabs and tabpanel wired inside one root (ID references resolve).
const tabWiring = await page.locator('vs-tabs').first().evaluate((el) => {
  const root = el.shadowRoot;
  const panel = root.querySelector('[role="tabpanel"]');
  const tabs = [...root.querySelectorAll('[role="tab"]')];
  return Boolean(root.querySelector('[role="tablist"]').getAttribute('aria-label')) && tabs.length > 0
    && tabs.every((t) => root.getElementById(t.getAttribute('aria-controls')) === panel)
    && root.getElementById(panel.getAttribute('aria-labelledby'))?.getAttribute('aria-selected') === 'true'
    && panel.querySelector('slot').assignedElements().length > 0;
});
check('lead detail tabs wired to their tabpanel', tabWiring);
await page.getByRole('tab', { name: /Notes/ }).focus();
await page.keyboard.press('End');
check('tabs: End moves to the last tab', await page.getByRole('tab', { name: /History/ }).getAttribute('aria-selected') === 'true');
ok.push(await scan(page, 'lead detail, History tab'));

// Account menu: closes on an outside press, on focus leaving and on Escape from the toggle.
const toggle = page.getByRole('button', { name: 'Account menu' });
await toggle.click();
ok.push(await scan(page, 'account menu open'));
await page.locator('h1').first().click(); // plain page text, away from the menu
check('account menu closes on an outside press', await toggle.getAttribute('aria-expanded') === 'false');
await toggle.click();
await toggle.focus();
await page.keyboard.press('Escape');
check('account menu closes on Escape from its toggle and keeps focus there',
  await toggle.getAttribute('aria-expanded') === 'false' && await toggle.evaluate((el) => el.matches(':focus')));
await toggle.click();
await page.locator('#account-menu').getByRole('link', { name: /Profile/ }).focus();
await page.keyboard.press('Tab');
await page.keyboard.press('Tab');
check('account menu closes when keyboard focus leaves it', await toggle.getAttribute('aria-expanded') === 'false');

// Command palette: combobox + listbox, arrow keys keep focus in the input, Enter opens the lead.
await page.keyboard.press('Control+k');
const combo = page.getByRole('combobox', { name: 'Search leads and pages' });
await combo.waitFor();
ok.push(await scan(page, 'command palette'));
await combo.fill('Anita');
const option = page.getByRole('option', { name: /Anita Reddy/ }).first();
await option.waitFor();
check('palette: first result is the active descendant',
  await combo.getAttribute('aria-activedescendant') === await option.getAttribute('id') && await option.getAttribute('aria-selected') === 'true');
await page.keyboard.press('ArrowDown');
await page.keyboard.press('ArrowUp');
check('palette: focus stays in the combobox while options move', await combo.evaluate((el) => el.matches(':focus')));
ok.push(await scan(page, 'command palette with results'));
await page.keyboard.press('Enter');
await page.waitForURL(/\/leads\/[0-9a-f]{32}$/);
check('palette: Enter opens the active lead', true);
// The marketing site fades sections in on scroll; reduced motion renders everything at full opacity (AX-10).
// bypassCSP lets the axe script run; the production CSP itself is exercised by site.e2e.mjs.
const siteCtx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce', bypassCSP: true });
await siteCtx.route('https://challenges.cloudflare.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/javascript',
  body: "window.turnstile = { render() { return 'w1'; }, getResponse() { return 'stub'; }, reset() {} };" }));
const site = await siteCtx.newPage();
await site.goto(`${SITE}/#contact`);
ok.push(await scan(site, 'website (idle)', { gateScope: FORM_SCOPE }));
await site.locator('#contact-form button[type="submit"]').click();
ok.push(await scan(site, 'website form (error state)', { gateScope: FORM_SCOPE }));
// Flag-off (the live configuration) validation state, and the 404 page (RR-01, RR-11).
const OFF = process.env.SITE_OFF ?? 'http://localhost:8001';
await site.goto(`${OFF}/?axe=off#contact`);
await site.locator('#contact-form button[type="submit"]').click();
ok.push(await scan(site, 'website form, intake off (error state)', { gateScope: FORM_SCOPE }));
await site.goto(`${OFF}/no-such-page`);
ok.push(await scan(site, '404 page'));
await site.goto(`${OFF}/warranty`);
ok.push(await scan(site, 'warranty policy page'));
await site.setViewportSize({ width: 360, height: 800 });
ok.push(await scan(site, 'warranty policy page (360 px)'));
await browser.close();
console.log(`${ok.filter(Boolean).length}/${ok.length} screens without serious/critical violations`);
process.exitCode = ok.every(Boolean) ? 0 : 1;
