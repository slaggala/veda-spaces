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
  execFileSync(process.env.API_PYTHON ?? path.join(API_DIR, '.venv/bin/python'), ['-m', 'veda.cli', 'worker', '--once'], {
    cwd: API_DIR, env: { ...process.env, VEDA_DATABASE_URL: 'sqlite:///var/e2e.db', VEDA_EMAIL_CAPTURE_DIR: 'var/mail', VEDA_ENV: 'local' },
  });
}
function mailLink(template, email, pathPrefix) {
  const files = fs.readdirSync(MAIL_DIR).filter((f) => f.endsWith(`${template}.eml`)).map((f) => path.join(MAIL_DIR, f)).sort();
  for (const f of files.reverse()) {
    // Captured .eml bodies are quoted-printable: undo soft line breaks and =XX escapes.
    const text = fs.readFileSync(f, 'utf8').replace(/=\r?\n/g, '').replace(/=([0-9A-F]{2})/g, (_, h) => String.fromCharCode(parseInt(h, 16)));
    const m = text.match(new RegExp(`(http://localhost:5173${pathPrefix}#token=[A-Za-z0-9_-]+)`));
    if (text.includes(`To: ${email}`) && m) return m[1];
  }
  throw new Error(`${template} email for ${email} not found`);
}
const inviteLink = (email) => mailLink('user_invited', email, '/accept-invite');

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
  // IR-38: prove authorization (403 with a valid Sales token), not only authentication (401 without one).
  const salesLogin = await api('POST', '/api/v1/auth/login', { email: SALES_EMAIL, password: SALES_PASSWORD });
  const salesToken = salesLogin.body?.data?.access_token;
  const denied = await api('GET', '/api/v1/security-events', null, salesToken);
  const anonymous = await api('GET', '/api/v1/security-events');
  check('permission denial: no admin nav, no-access page, API 403 with a Sales token, 401 without', navUsers === 0 &&
    denied.status === 403 && denied.body?.code === 'PERMISSION_DENIED' && anonymous.status === 401,
    `nav=${navUsers} bearer=${denied.status} anonymous=${anonymous.status}`);

  // IR-19: every route sets its own title, and in-app navigation moves focus to the new page's heading.
  await page.goto(`${BASE}/`);
  await page.getByRole('link', { name: 'Leads' }).first().click();
  await page.waitForURL(/\/leads$/);
  await page.waitForFunction(() => document.title === 'Leads · Veda Workspace');
  const focusOnHeading = await page.waitForFunction(() => {
    let el = document.activeElement;
    while (el?.shadowRoot?.activeElement) el = el.shadowRoot.activeElement;
    return el?.tagName === 'H1' || el?.id === 'outlet';
  }, null, { timeout: 5000 }).then(() => true, () => false);
  check('route change updates the title and moves focus to the page heading (WCAG 2.4.2)', focusOnHeading);
  await page.screenshot({ path: `${OUT}/sales-no-access.png` });

  // Forced session expiry: the founder revokes all of Sales' sessions; the next request signs Sales out.
  const users = await api('GET', '/api/v1/users?q=priya', null, ft);
  const salesId = users.body.data[0].id;
  r = await api('POST', `/api/v1/users/${salesId}/sessions/revoke`, { reason: 'E2E revoke' }, ft);
  check('admin revokes Sales sessions', r.status === 200, JSON.stringify(r.body?.data));
  // In-app navigation (no reload): the next API call gets 401 SESSION_INVALID (09 §4.1 banner).
  await page.reload();
  const reloadSignedOut = await page.waitForURL(/\/login/, { timeout: 10000 }).then(() => true, () => false);
  check('revoked session: a full reload lands on sign-in', reloadSignedOut, page.url());
  await page.getByLabel('Email', { exact: true }).fill(SALES_EMAIL);
  await page.getByLabel('Password', { exact: true }).fill(SALES_PASSWORD);
  await page.getByRole('button', { name: /Sign in/ }).click();
  await page.waitForURL((u) => !u.pathname.startsWith('/login'));
  await page.getByRole('link', { name: 'Dashboard' }).first().click();
  await page.waitForURL(`${BASE}/`);
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
  const redirected = await page.waitForURL(/\/login/, { timeout: 10000 }).then(() => true, () => false);
  const refreshAfterLogout = await page.evaluate(async () => (await fetch('/api/v1/auth/refresh', {
    method: 'POST', headers: { 'X-Requested-With': 'veda-workspace' } })).status);
  check('logout ends the session; protected routes redirect to sign-in', redirected && refreshAfterLogout === 401,
    `refresh=${refreshAfterLogout}`);


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

  // IR-15 (TD-F step 4): another writer changes city and priority while the founder edits only the message;
  // "Re-apply mine" must send the message alone and keep the other writer's changes.
  const lead = list.body.data[0];
  await fp.goto(`${BASE}/leads/${lead.id}`);
  await fp.getByRole('button', { name: 'Edit', exact: true }).click();
  await fp.locator('textarea[name="message"]').fill('Founder note: prefers a site visit on Saturday');
  const fresh = await api('GET', `/api/v1/leads/${lead.id}`, null, ft);
  const other = await api('PATCH', `/api/v1/leads/${lead.id}`, { city: 'Secunderabad', priority: 'HIGH' }, ft,
    { 'If-Match': `"${fresh.body.data.version}"` });
  await fp.getByRole('button', { name: 'Save', exact: true }).click();
  await fp.getByRole('button', { name: 'Re-apply mine' }).click();
  await fp.getByText('Lead saved').first().waitFor({ timeout: 10000 });
  const after = (await api('GET', `/api/v1/leads/${lead.id}`, null, ft)).body.data;
  check('conflict re-apply keeps the other writer\'s changes (no lost update)', other.status === 200 &&
    after.city === 'Secunderabad' && after.priority === 'HIGH' && after.message === 'Founder note: prefers a site visit on Saturday',
    `${after.city}/${after.priority}`);

  // IR-07: a Founder cancels a break-glass request from the emailed link, on the SPA page.
  const target = (await api('GET', '/api/v1/users?q=priya', null, ft)).body.data[0];
  // A freshly MFA-verified Founder session (Founder actions need step-up within 10 minutes, G10).
  let fl = await api('POST', '/api/v1/auth/login', { email: founder.email, password: founder.password });
  fl = await api('POST', '/api/v1/auth/mfa/verify', { mfa_token: fl.body.data.mfa_token, code: await totp(founder.secret) });
  const bg = await api('POST', '/api/v1/founder-actions', { action: 'GRANT_FOUNDER', target_user_id: target.id,
    reason: 'E2E break-glass veto' }, fl.body.data.access_token);
  drainOutbox();
  const cancelLink = mailLink('break_glass_requested', founder.email, '/approvals/cancel');
  await fp.goto(cancelLink);
  await fp.getByRole('button', { name: 'Cancel the request' }).click();
  await fp.getByText('Request cancelled').waitFor({ timeout: 10000 });
  const approval = await api('GET', `/api/v1/approvals/${bg.body?.data?.approval_id}`, null, ft);
  check('break-glass cancel link works end to end from the email', bg.status === 202 && bg.body.data.channel === 'BREAK_GLASS'
    && approval.body?.data?.status === 'CANCELLED', `${bg.status} ${approval.body?.data?.status}`);

  // IR-36: "Sign out everywhere" (Profile → Sessions) leaves the page for sign-in. Last: it ends every Founder session.
  await fp.goto(`${BASE}/profile`);
  await fp.getByRole('tab', { name: 'Sessions' }).click();
  await fp.getByRole('button', { name: 'Sign out everywhere' }).click();
  const everywhere = await fp.waitForURL(/\/login/, { timeout: 10000 }).then(() => true, () => false);
  const stale = await api('GET', '/api/v1/auth/me', null, fl.body.data.access_token);
  check('"Sign out everywhere" lands on sign-in and ends the other sessions', everywhere && stale.status === 401,
    `${fp.url()} other=${stale.status}`);
} catch (err) {
  check('journey aborted', false, String(err).split('\n')[0]);
  if (page) await page.screenshot({ path: `${OUT}/access-abort.png`, fullPage: true }).catch(() => {});
} finally {
  await browser.close();
  console.log(`${results.filter(Boolean).length}/${results.length} access checks passed`);
  process.exitCode = results.every(Boolean) ? 0 : 1;
}
