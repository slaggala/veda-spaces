// End-to-end smoke of the Veda Workspace against a running API (12 §4.8 journeys, subset).
//
//   API:  flask --app wsgi run --port 5000 (VEDA_COOKIE_SECURE=false)
//   SPA:  npx vite --port 5173
//   Run:  INVITE_LINK=... node e2e/workspace.e2e.mjs
//
// Journeys: invite acceptance with forced MFA enrollment (path B) → recovery codes → dashboard →
// website enquiry appears in the lead list → lead detail → status change → sign out → sign in with TOTP.
import crypto from 'node:crypto';
import fs from 'node:fs';
import { chromium } from 'playwright';

const BASE = process.env.APP_BASE ?? 'http://localhost:5173';
const INVITE = process.env.INVITE_LINK;
const PASSWORD = 'Studio-Evening-Lantern-5';
const OUT = process.env.E2E_OUT ?? 'e2e-artifacts';
fs.mkdirSync(OUT, { recursive: true });

function base32Decode(s) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const ch of s.replace(/=+$/, '')) bits += alphabet.indexOf(ch).toString(2).padStart(5, '0');
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

let lastStep = -1;
async function totp(secret) {
  let step = Math.floor(Date.now() / 30000);
  if (step <= lastStep) {
    await new Promise((r) => setTimeout(r, (lastStep + 1) * 30000 - Date.now() + 500));
    step = Math.floor(Date.now() / 30000);
  }
  lastStep = step;
  const msg = Buffer.alloc(8);
  msg.writeBigUInt64BE(BigInt(step));
  const mac = crypto.createHmac('sha1', base32Decode(secret)).update(msg).digest();
  const off = mac[mac.length - 1] & 0xf;
  return String((mac.readUInt32BE(off) & 0x7fffffff) % 1e6).padStart(6, '0');
}

const results = [];
async function step(name, fn) {
  try {
    await fn();
    results.push(['PASS', name]);
    console.log(`PASS ${name}`);
  } catch (err) {
    results.push(['FAIL', name, String(err).split('\n')[0]]);
    console.log(`FAIL ${name}: ${err}`);
    await page.screenshot({ path: `${OUT}/fail-${results.length}.png`, fullPage: true }).catch(() => {});
    throw err;
  }
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
let secret = '';
let founderEmail = process.env.FOUNDER_EMAIL ?? 'founder@vedaspaces.test';

try {
  await step('accept invitation (path B: forced MFA enrollment)', async () => {
    await page.goto(INVITE);
    await page.getByLabel('New password', { exact: true }).fill(PASSWORD);
    await page.getByLabel('Confirm', { exact: true }).fill(PASSWORD);
    await page.getByRole('button', { name: /Set password/ }).click();
    await page.getByText("Can't scan? Enter this key").click();
    secret = (await page.locator('p.secret').textContent()).trim();
    if (!/^[A-Z2-7]{32}$/.test(secret)) throw new Error(`unexpected secret ${secret}`);
    // Local throwaway database only: hand the TOTP secret to the follow-on journey (access.e2e.mjs).
    fs.writeFileSync(`${OUT}/founder.json`, JSON.stringify({ email: founderEmail, password: PASSWORD, secret }));
    await page.getByLabel('6-digit code').fill(await totp(secret));
    await page.getByRole('button', { name: /Confirm/ }).click();
    await page.getByRole('list', { name: 'Recovery codes' }).waitFor();
    const codes = await page.getByRole('list', { name: 'Recovery codes' }).locator('li').allTextContents();
    if (codes.length !== 10) throw new Error(`expected 10 recovery codes, got ${codes.length}`);
    await page.getByLabel('I have saved these codes').check();
    await page.getByRole('button', { name: /Continue/ }).click();
    await page.waitForURL(`${BASE}/`);
  });

  await step('dashboard renders for the Founder', async () => {
    await page.getByText(/Good (morning|afternoon|evening)/).waitFor();
    await page.screenshot({ path: `${OUT}/dashboard.png`, fullPage: true });
  });

  await step('website enquiry reaches the lead list', async () => {
    const res = await fetch(`${BASE}/api/v1/public/leads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': `e2e-${Date.now()}-abcdef`, Origin: 'http://localhost:8000' },
      body: JSON.stringify({ name: 'Anita Reddy', phone: '98765 43210', email: 'anita@example.com', city: 'Hyderabad',
        project_type_code: 'MODULAR_KITCHEN', property_type_code: 'APARTMENT', budget_range_code: '5L_10L',
        message: '3BHK handover in December', consent: { acknowledged: true, policy_version: '2026-09-v1' },
        turnstile_token: 'dev-ok', company_website_url: '' }),
    });
    const body = await res.json();
    if (res.status !== 201 || !/^[0-9A-Z]{4}-[0-9A-Z]{4}$/.test(body.data.reference)) throw new Error(JSON.stringify(body));
    await page.goto(`${BASE}/leads`);
    await page.getByText('Anita Reddy').first().waitFor();
    await page.screenshot({ path: `${OUT}/leads.png`, fullPage: true });
  });

  await step('lead detail and status change', async () => {
    await page.getByText('Anita Reddy').first().click();
    await page.waitForURL(/\/leads\/[0-9a-f]{32}$/);
    await page.getByText(/VS-L-\d{4}-\d{6}/).first().waitFor();
    await page.getByRole('button', { name: /Move to Contacted/ }).first().click();
    // Dialog actions are slotted light-DOM content; locate them through their host component.
    const dialogConfirm = page.locator('vs-status-dialog button.primary');
    await dialogConfirm.waitFor();
    await dialogConfirm.click();
    await page.getByText(/Status changed: New → Contacted/).first().waitFor({ timeout: 10000 });
    await page.screenshot({ path: `${OUT}/lead-detail.png`, fullPage: true });
  });

  await step('audit viewer shows the change', async () => {
    await page.goto(`${BASE}/audit`);
    await page.locator('td', { hasText: /^UPDATE$/ }).first().waitFor();
  });

  await step('sign out and sign back in with TOTP', async () => {
    await page.getByRole('button', { name: 'Account menu' }).click();
    await page.getByRole('button', { name: /Sign out/ }).click();
    await page.waitForURL(/\/login/);
    await page.getByLabel('Email', { exact: true }).fill(founderEmail);
    await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
    await page.getByRole('button', { name: /Sign in/ }).click();
    await page.locator('input[autocomplete="one-time-code"]:visible').first().fill(await totp(secret));
    await page.getByRole('button', { name: /Verify/ }).click();
    await page.waitForURL(`${BASE}/`);
  });

  await step('mobile width lead list (360 px, no horizontal scroll)', async () => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto(`${BASE}/leads`);
    await page.getByText('Anita Reddy').first().waitFor();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 1) throw new Error(`horizontal overflow ${overflow}px`);
    await page.screenshot({ path: `${OUT}/mobile-leads.png`, fullPage: true });
  });
} finally {
  const relevant = consoleErrors.filter((e) => !/Failed to load resource: the server responded with a status of 401/.test(e));
  console.log(`console errors: ${relevant.length}`);
  relevant.slice(0, 5).forEach((e) => console.log(`  ${e}`));
  await browser.close();
  const failed = results.filter((r) => r[0] === 'FAIL').length;
  console.log(`${results.length - failed}/${results.length} journeys passed`);
  process.exitCode = failed ? 1 : 0;
}
