// Access-control, session and intake journeys against a running API (run after workspace.e2e.mjs).
//   Needs E2E_OUT/founder.json from workspace.e2e.mjs and API_DIR (to drain the outbox worker).
// Journeys: permission denial for Sales · forced session expiry (admin revoke) · logout · duplicate and
// repeated website submissions · invalid website submission.
import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const BASE = process.env.APP_BASE ?? 'http://localhost:5173';
const OUT = process.env.E2E_OUT ?? 'e2e-artifacts';
const API_DIR = process.env.API_DIR;
const MAIL_DIR = path.join(API_DIR, 'var/mail');
const founder = JSON.parse(fs.readFileSync(`${OUT}/founder.json`, 'utf8'));
const SALES_EMAIL = 'priya.sales@vedaspaces.test';
const SALES_PASSWORD = 'Courtyard-Monsoon-Lamp-42';

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
  await new Promise((r) => setTimeout(r, (step + 1) * 30000 - Date.now() + 500)); // never reuse a step (MFA-009)
  const msg = Buffer.alloc(8);
  msg.writeBigUInt64BE(BigInt(step + 1));
  const mac = crypto.createHmac('sha1', b32(secret)).update(msg).digest();
  const off = mac[mac.length - 1] & 0xf;
  return String((mac.readUInt32BE(off) & 0x7fffffff) % 1e6).padStart(6, '0');
}
async function api(method, url, body, token, headers = {}) {
  const res = await fetch(`${BASE}${url}`, {
    method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...headers },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: res.status, body: await res.json().catch(() => null) };
}
function drainOutbox() {
  execFileSync(path.join(API_DIR, '.venv/bin/python'), ['-m', 'veda.cli', 'worker', '--once'], {
    cwd: API_DIR, env: { ...process.env, VEDA_DATABASE_URL: 'sqlite:///var/e2e.db', VEDA_EMAIL_CAPTURE_DIR: 'var/mail', VEDA_ENV: 'local' },
  });
}
function inviteLink(email) {
  const files = fs.readdirSync(MAIL_DIR).filter((f) => f.endsWith('user_invited.eml')).map((f) => path.join(MAIL_DIR, f));
  for (const f of files) {
    // Captured .eml bodies are quoted-printable: undo soft line breaks and =XX escapes.
    const text = fs.readFileSync(f, 'utf8').replace(/=\r?\n/g, '').replace(/=([0-9A-F]{2})/g, (_, h) => String.fromCharCode(parseInt(h, 16)));
    if (text.includes(`To: ${email}`)) return text.match(/(http:\/\/localhost:5173\/accept-invite#token=[A-Za-z0-9_-]+)/)[1];
  }
  throw new Error('invite email not found');
}

const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`); };
const browser = await chromium.launch();
let page = null;

try {
  // Founder API session (password + TOTP).
  let r = await api('POST', '/api/v1/auth/login', { email: founder.email, password: founder.password });
  r = await api('POST', '/api/v1/auth/mfa/verify', { mfa_token: r.body.data.mfa_token, code: await totp(founder.secret) });
  const ft = r.body.data.access_token;
  const roles = await api('GET', '/api/v1/roles', null, ft);
  const salesRole = roles.body.data.find((x) => x.code === 'SALES').id;
  r = await api('POST', '/api/v1/users', { email: SALES_EMAIL, full_name: 'Priya Sharma', role_ids: [salesRole] }, ft);
  check('founder invites a Sales user', r.status === 201, String(r.status));
  drainOutbox();

  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  page = await ctx.newPage();
  await page.goto(inviteLink(SALES_EMAIL));
  await page.getByLabel('New password', { exact: true }).fill(SALES_PASSWORD);
  await page.getByLabel('Confirm', { exact: true }).fill(SALES_PASSWORD);
  await page.getByRole('button', { name: /Set password/ }).click();
  await page.waitForURL(/\/login/);
  await page.getByLabel('Email', { exact: true }).fill(SALES_EMAIL);
  await page.getByLabel('Password', { exact: true }).fill(SALES_PASSWORD);
  await page.getByRole('button', { name: /Sign in/ }).click();
  await page.waitForURL((u) => !u.pathname.startsWith('/login'));
  check('Sales accepts invite (no MFA required) and signs in', true);

  const navUsers = await page.getByRole('link', { name: 'Users' }).count();
  await page.goto(`${BASE}/admin/users`);
  await page.getByText("You don't have access").waitFor();
  const apiDenied = await page.evaluate(async () => (await fetch('/api/v1/security-events')).status);
  check('permission denial: no admin nav, no-access page, API 401/403', navUsers === 0 && [401, 403].includes(apiDenied), `nav=${navUsers} api=${apiDenied}`);
  await page.screenshot({ path: `${OUT}/sales-no-access.png` });

  // Forced session expiry: the founder revokes all of Sales' sessions; the next request signs Sales out.
  const users = await api('GET', '/api/v1/users?q=priya', null, ft);
  const salesId = users.body.data[0].id;
  r = await api('POST', `/api/v1/users/${salesId}/sessions/revoke`, { reason: 'E2E revoke' }, ft);
  check('admin revokes Sales sessions', r.status === 200, JSON.stringify(r.body?.data));
  // In-app navigation (no reload): the next API call gets 401 SESSION_INVALID (09 §4.1 banner).
  await page.goto(`${BASE}/`);
  await page.waitForURL(/\/login/);
  const reloadSignedOut = true;
  check('revoked session: a full reload lands on sign-in', reloadSignedOut);
  await page.getByLabel('Email', { exact: true }).fill(SALES_EMAIL);
  await page.getByLabel('Password', { exact: true }).fill(SALES_PASSWORD);
  await page.getByRole('button', { name: /Sign in/ }).click();
  await page.waitForURL((u) => !u.pathname.startsWith('/login'));
  r = await api('POST', `/api/v1/users/${salesId}/sessions/revoke`, { reason: 'E2E revoke 2' }, ft);
  await page.getByRole('link', { name: 'Leads' }).first().click();
  await page.waitForURL(/\/login/);
  await page.getByText(/sign in again/i).first().waitFor();
  check('revoked session: next in-app request signs out with the expiry banner', r.status === 200);

  // Logout from the account menu.
  await page.getByLabel('Email', { exact: true }).fill(SALES_EMAIL);
  await page.getByLabel('Password', { exact: true }).fill(SALES_PASSWORD);
  await page.getByRole('button', { name: /Sign in/ }).click();
  await page.waitForURL((u) => !u.pathname.startsWith('/login'));
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page.getByRole('button', { name: /Sign out/ }).click();
  await page.waitForURL(/\/login/);
  await page.goto(`${BASE}/leads`);
  await page.waitForURL(/\/login/);
  check('logout ends the session; protected routes redirect to sign-in', true);

  // Website intake: duplicate phone, idempotent retry, invalid submission.
  const body = (msg) => ({ name: 'Farah Khan', phone: '99887 76655', message: msg, turnstile_token: 'dev-ok', company_website_url: '',
    consent: { acknowledged: true, policy_version: '2026-09-v1' } });
  const h = (k) => ({ 'Idempotency-Key': k, Origin: 'http://localhost:8000' });
  const k1 = `dup-a-${Date.now()}-xyz`;
  const a = await api('POST', '/api/v1/public/leads', body('kitchen'), null, h(k1));
  const replay = await api('POST', '/api/v1/public/leads', body('kitchen'), null, h(k1));
  const b = await api('POST', '/api/v1/public/leads', body('wardrobes'), null, h(`dup-b-${Date.now()}-xyz`));
  const reused = await api('POST', '/api/v1/public/leads', body('different'), null, h(k1));
  const invalid = await api('POST', '/api/v1/public/leads', { ...body('x'), phone: '123' }, null, h(`bad-${Date.now()}-xyzab`));
  check('repeated submission (same key) returns the original reference', a.status === 201 && replay.body?.data?.reference === a.body.data.reference);
  check('same key with a different body is refused', reused.status === 422 && reused.body.code === 'IDEMPOTENCY_KEY_REUSED');
  check('invalid submission returns field errors only', invalid.status === 422 && invalid.body.errors?.[0]?.field === 'phone'
    && !JSON.stringify(invalid.body).includes('VS-L-'));
  const list = await api('GET', '/api/v1/leads?q=farah', null, ft);
  const flags = list.body.data.map((x) => x.duplicate_status).sort();
  check('duplicate submission is stored and flagged, never dropped', b.status === 201 && b.body.data.reference !== a.body.data.reference
    && list.body.data.length === 2 && flags.join() === 'NONE,SUSPECTED', flags.join());
  const fctx = await browser.newContext();
  const fp = await fctx.newPage();
  await fp.goto(`${BASE}/login`);
  await fp.getByLabel('Email', { exact: true }).fill(founder.email);
  await fp.getByLabel('Password', { exact: true }).fill(founder.password);
  await fp.getByRole('button', { name: /Sign in/ }).click();
  await fp.locator('input[autocomplete="one-time-code"]:visible').first().fill(await totp(founder.secret));
  await fp.getByRole('button', { name: /Verify/ }).click();
  await fp.waitForURL(`${BASE}/`);
  await fp.goto(`${BASE}/leads?q=farah`);
  await fp.getByText('Farah Khan').first().waitFor();
  await fp.screenshot({ path: `${OUT}/duplicates-in-admin.png`, fullPage: true });
  check('duplicate leads visible in the admin list', (await fp.getByText('Farah Khan').count()) >= 2);
} catch (err) {
  check('journey aborted', false, String(err).split('\n')[0]);
  if (page) await page.screenshot({ path: `${OUT}/access-abort.png`, fullPage: true }).catch(() => {});
} finally {
  await browser.close();
  console.log(`${results.filter(Boolean).length}/${results.length} access checks passed`);
  process.exitCode = results.every(Boolean) ? 0 : 1;
}
