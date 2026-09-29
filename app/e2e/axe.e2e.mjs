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
async function scan(page, name) {
  await page.addScriptTag({ content: AXE });
  const res = await page.evaluate(async () => window.axe.run(document, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }));
  const serious = res.violations.filter((v) => ['serious', 'critical'].includes(v.impact));
  console.log(`${serious.length ? 'FAIL' : 'PASS'} ${name}: ${res.violations.length} violation(s), ${serious.length} serious/critical`);
  for (const v of res.violations) console.log(`   - [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} node(s))`);
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
// The marketing site fades sections in on scroll; reduced motion renders everything at full opacity (AX-10).
const site = await browser.newPage({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' });
await site.goto(`${SITE}/#contact`);
ok.push(await scan(site, 'website (idle)'));
await site.locator('#contact-form button[type="submit"]').click();
ok.push(await scan(site, 'website form (error state)'));
await browser.close();
console.log(`${ok.filter(Boolean).length}/${ok.length} screens without serious/critical violations`);
process.exitCode = ok.every(Boolean) ? 0 : 1;
