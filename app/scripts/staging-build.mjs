// Staging builds for Cloudflare Pages (AUT-204). Staging sits behind Cloudflare Access and talks only to the staging
// API; a staging build that names the production API is refused.
//   node scripts/staging-build.mjs site   → dist-staging-site/ (the marketing site of e2e/site-release, intake on)
//   node scripts/staging-build.mjs app    → dist/ (the staff workspace SPA)
// Both need STAGING_TURNSTILE_SITE_KEY (the real staging widget, AUT-203; the public site key, not the secret).
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cpSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const STAGING_API = 'https://api-staging.vedaspaces.com';
export const PRODUCTION_API = 'https://api.vedaspaces.com';
const APP = fileURLToPath(new URL('..', import.meta.url));

export function siteKey(value) {
  // A real widget key. Cloudflare's always-pass/fail test keys (1x…, 2x…, 3x…) are refused (AUT-203, D8), and so is
  // a secret key: it also starts with 0x but is longer (about 35 characters against 24), and it would be published.
  if (!/^0x[0-9A-Za-z_-]{16,26}$/.test(value ?? '')) {
    throw new Error(
      'STAGING_TURNSTILE_SITE_KEY must be the staging widget site key (0x…, about 24 characters), not a test or secret key',
    );
  }
  return value;
}

const files = (dir) =>
  readdirSync(dir).flatMap((n) => (statSync(join(dir, n)).isDirectory() ? files(join(dir, n)) : [join(dir, n)]));

function setMeta(html, name, value) {
  const empty = `<meta name="${name}" content="">`;
  if (!html.includes(empty)) throw new Error(`index.html has no empty <meta name="${name}">`);
  return html.replace(empty, `<meta name="${name}" content="${value}">`);
}

// Staging headers: the CSP may reach the staging API only, and nothing is indexed.
function stagingHeaders(text) {
  if (!text.includes(PRODUCTION_API)) throw new Error('_headers: expected the production API in connect-src');
  return text.replaceAll(PRODUCTION_API, STAGING_API).replace(/^\/\*\n/m, '/*\n  X-Robots-Tag: noindex, nofollow\n');
}

/**
 * Targeted media enablement: the V3 page (and only it) may load catalog images from the protected staging API. Cloudflare
 * Pages combines the headers of every matching rule, and two CSPs only narrow each other, so the V3 rule detaches the
 * site-wide policy (`! Content-Security-Policy`) and restates it with exactly one change: the staging API host in
 * img-src. No wildcard, no blob:, no media-src or worker-src change (video and 3D stay disabled).
 */
export const V3_PATH_RULE = '/estimate-v3*';
export function v3ImageCsp(headersText) {
  const csp = headersText.split('\n').find((l) => l.trim().startsWith('Content-Security-Policy:'));
  if (!csp) throw new Error('_headers: no site-wide Content-Security-Policy to restate for V3');
  const value = csp.trim().slice('Content-Security-Policy:'.length).trim();
  const img = "img-src 'self' data:";
  if ((value.match(/img-src [^;]*/g) || []).join() !== img) throw new Error(`_headers: expected "${img}" in the site CSP`);
  const v3 = value.replace(img, `${img} ${STAGING_API}`);
  return `${headersText.replace(/\n*$/, '\n')}\n${V3_PATH_RULE}\n  ! Content-Security-Policy\n  Content-Security-Policy: ${v3}\n`;
}

/** Refuse any output that names the production API, or that lacks the staging API. */
export function checkStaging(dir) {
  const hits = files(dir).filter((f) => readFileSync(f, 'latin1').includes(PRODUCTION_API));
  if (hits.length) throw new Error(`staging build names the production API: ${hits.join(', ')}`);
  if (!files(dir).some((f) => readFileSync(f, 'latin1').includes(STAGING_API))) {
    throw new Error('staging build does not name the staging API');
  }
}

// The owner's activation-approval record for ESSENTIAL-1.1, packaged with the API (final pre-activation closure).
export const APPROVAL = fileURLToPath(new URL('../../api/veda/modules/estimator/approved/essential-1.1-approval.json', import.meta.url));

/** The canonical digest the API uses for approval records (sorted keys, compact, ASCII-escaped JSON). */
export function canonicalSha256(value) {
  const esc = (v) => JSON.stringify(v).replace(/[\u007f-\uffff]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);
  const canon = (v) => (Array.isArray(v) ? `[${v.map(canon).join(',')}]`
    : v && typeof v === 'object' ? `{${Object.keys(v).sort().map((k) => `${esc(k)}:${canon(v[k])}`).join(',')}}` : esc(v));
  return createHash('sha256').update(canon(value)).digest('hex');
}

export function readCopy(file) {
  const text = readFileSync(file, 'utf8');
  return JSON.parse(text.slice(text.indexOf('Object.freeze(') + 'Object.freeze('.length, text.lastIndexOf(');')));
}

/** STAGING_ESTIMATOR_UX=v2 is refused unless the owner approved exactly this customer copy for staging. */
export function checkV2Approval(copyFile, approvalFile = APPROVAL) {
  const approval = JSON.parse(readFileSync(approvalFile, 'utf8'));
  const copy = readCopy(copyFile);
  const p = copy.promise;
  const problems = [];
  if (approval.status !== 'APPROVED' || !approval.owner || !approval.approved_on) problems.push(`the owner approval record is ${approval.status}`);
  if (approval.customer_copy_sha256 !== canonicalSha256(copy)) problems.push('the customer copy is not the approved copy');
  if (approval.warranty_copy_sha256 !== canonicalSha256({ manufacturer: p.manufacturer, service: p.service, serviceNote: p.serviceNote })) problems.push('the warranty copy is not the approved copy');
  const scope = approval.scope || {};
  if (!(scope.environments || []).includes('staging') || scope.ux !== 'v2' || scope.public_intake !== false) problems.push('the approval does not cover V2 on staging without public intake');
  if (problems.length) throw new Error(`STAGING_ESTIMATOR_UX=v2 is refused: ${problems.join('; ')}`);
}

/**
 * The catalog-driven estimator V3 (ADR-013) needs its owner-approved staging record (api/veda/modules/catalog/
 * staging_approval.py defines it; none exists yet). The build accepts only an APPROVED record with every evidence
 * digest, an approver who is not the author, the staging-only scope, and whose file SHA-256 is the
 * catalog_v3.approval_record_sha256 bound in infra/config/staging-platform.json.
 */
export const V3_APPROVAL = fileURLToPath(new URL('../../api/veda/modules/catalog/approved/v3-staging-approval.json', import.meta.url));
export const PLATFORM = fileURLToPath(new URL('../../infra/config/staging-platform.json', import.meta.url));
export const V3_GIT_EVIDENCE = ['application_commit', 'pr69_merge'];
export const V3_DIGEST_EVIDENCE = ['application_certification', 'real_card_evidence', 'infrastructure_plan', 'infrastructure_apply',
  'scanner_capacity', 'scanner_decision', 'media_bucket', 'iam', 'ssm_settings', 'csp', 'media_smoke_test',
  'promise_owner_approval', 'media_rights_approver'];
export function checkV3Approval(approvalFile = V3_APPROVAL, platformFile = PLATFORM, today = new Date().toISOString().slice(0, 10)) {
  let raw;
  let approval;
  try { raw = readFileSync(approvalFile); approval = JSON.parse(raw.toString('utf8')); } catch { approval = null; }
  const problems = [];
  if (!approval) problems.push('no approved V3 staging activation record');
  else {
    const scope = approval.approval_scope || {};
    const same = (a, b) => String(a || '').trim().toLowerCase().replace(/\s+/g, ' ') === String(b || '').trim().toLowerCase().replace(/\s+/g, ' ');
    const day = (v) => (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null);
    if (approval.schema !== 'veda.catalog.v3-staging-approval/2') problems.push('not a V3 staging approval record (schema 2)');
    if (approval.status !== 'APPROVED') problems.push(`the V3 staging activation record is ${approval.status}`);
    if (approval.environment !== 'staging') problems.push('the record is not for staging');
    if (!approval.approver || !day(approval.approved_at) || !approval.release) problems.push('the record names no approver, approval date or release');
    if (same(approval.approver, approval.author) || /TO FILL/i.test(`${approval.approver} ${approval.author}`)) problems.push('the approver is not independent of the author');
    if (approval.revoked_at || approval.revocation_reason) problems.push('the approval is revoked');
    if (!day(approval.review_by) || approval.review_by <= today) problems.push('the approval review date is missing or has been reached');
    if (day(approval.expires_at) ? approval.expires_at <= today : !approval.non_expiring_decision) problems.push('the approval has expired or has no expiry policy');
    if (scope.version !== 'v3' || scope.protected !== true || scope.public_intake !== false || scope.three_d !== false
      || scope.video !== false) problems.push('the record does not cover V3 on protected staging only, without public intake, 3D or video');
    const ev = approval.evidence || {};
    const missing = [...V3_GIT_EVIDENCE.filter((k) => !/^[0-9a-f]{40}$/.test(ev[k]?.git_sha || '')),
      ...V3_DIGEST_EVIDENCE.filter((k) => !/^[0-9a-f]{64}$/.test(ev[k]?.sha256 || ''))];
    if (missing.length) problems.push(`evidence without a digest: ${missing.join(', ')}`);
    let bound;
    try { bound = JSON.parse(readFileSync(platformFile, 'utf8')).catalog_v3?.approval_record_sha256; } catch { bound = null; }
    if (bound !== createHash('sha256').update(raw).digest('hex')) problems.push('the record is not the one bound in staging-platform.json (catalog_v3.approval_record_sha256)');
  }
  if (problems.length) throw new Error(`STAGING_ESTIMATOR_VERSION=v3 is refused: ${problems.join('; ')}`);
}

export function buildSite(src, out, key, estimator = estimatorFlags(process.env)) {
  if (estimator.enabled && estimator.ux === 'v2') checkV2Approval(join(src, 'assets/estimate-v2-copy.js'), estimator.approvalFile);
  if (estimator.version === 'v3') checkV3Approval(estimator.v3ApprovalFile, estimator.platformFile);
  siteKey(key);
  rmSync(out, { recursive: true, force: true });
  cpSync(src, out, { recursive: true });
  let html = readFileSync(join(out, 'index.html'), 'utf8');
  html = setMeta(html, 'veda-api-base', STAGING_API);
  html = setMeta(html, 'veda-turnstile-sitekey', key);
  html = setMeta(html, 'veda-api-credentials', 'include'); // the Access cookie of the API host (staging only)
  writeFileSync(join(out, 'index.html'), html);
  // The Budgetary Estimate page (ADR-012): the same intake metas; the estimator itself only when STAGING_ESTIMATOR=on,
  // with Essential only unless approved packages are listed (Premium/Luxury need approved rates).
  let est = readFileSync(join(out, 'estimate.html'), 'utf8');
  est = setMeta(est, 'veda-api-base', STAGING_API);
  est = setMeta(est, 'veda-turnstile-sitekey', key);
  est = setMeta(est, 'veda-api-credentials', 'include');
  if (estimator.enabled) {
    est = setMeta(est, 'veda-estimator', 'on');
    est = setMeta(est, 'veda-estimator-packages', estimator.packages.join(','));
    est = setMeta(est, 'veda-estimator-home-sizes', estimator.homeSizes.join(','));
    est = setMeta(est, 'veda-estimator-property-types', estimator.propertyTypes.join(','));
    if (estimator.ux === 'v2') est = setMeta(est, 'veda-estimator-ux', 'v2'); // UX V2; V1 stays the default
  }
  writeFileSync(join(out, 'estimate.html'), est);
  // V3 ships only with its approval (checked above); otherwise its page and assets are not in the build at all.
  if (estimator.version === 'v3' && estimator.enabled) {
    let v3 = readFileSync(join(out, 'estimate-v3.html'), 'utf8');
    for (const [name, value] of [['veda-api-base', STAGING_API], ['veda-turnstile-sitekey', key], ['veda-api-credentials', 'include'], ['veda-estimator-version', 'v3']]) v3 = setMeta(v3, name, value);
    writeFileSync(join(out, 'estimate-v3.html'), v3);
  } else {
    for (const f of ['estimate-v3.html', 'assets/estimate-v3.js', 'assets/estimate-v3.css']) rmSync(join(out, f), { force: true });
  }
  let headers = stagingHeaders(readFileSync(join(out, '_headers'), 'utf8'));
  if (estimator.version === 'v3' && estimator.enabled) headers = v3ImageCsp(headers); // only with the approved V3 page
  writeFileSync(join(out, '_headers'), headers);
  writeFileSync(join(out, 'robots.txt'), 'User-agent: *\nDisallow: /\n');
  rmSync(join(out, 'sitemap.xml'), { force: true });
  checkStaging(out);
}

/**
 * STAGING_ESTIMATOR=on enables the estimator page. The page offers only what the active rate card supports (ADR-012
 * §11 D1–D3): STAGING_ESTIMATOR_PACKAGES (default ESSENTIAL; Luxury is never priced, it is a consultation),
 * STAGING_ESTIMATOR_HOME_SIZES (default 3BHK) and STAGING_ESTIMATOR_PROPERTY_TYPES (default APARTMENT). STAGING_ESTIMATOR_UX
 * chooses the customer experience: v1 (default) or v2 (docs/implementation/estimator/ESTIMATOR-UX-V2*.md).
 */
export function estimatorFlags(env) {
  const list = (value, fallback) => (value || fallback).split(',').map((p) => p.trim()).filter(Boolean);
  const packages = list(env.STAGING_ESTIMATOR_PACKAGES, 'ESSENTIAL');
  if (packages.some((p) => !['ESSENTIAL', 'PREMIUM'].includes(p)) || !packages.includes('ESSENTIAL')) {
    throw new Error(`STAGING_ESTIMATOR_PACKAGES must list ESSENTIAL and optionally PREMIUM (got ${packages.join(',')})`);
  }
  const homeSizes = list(env.STAGING_ESTIMATOR_HOME_SIZES, '3BHK');
  if (!homeSizes.length || homeSizes.some((h) => !['1BHK', '2BHK', '3BHK', '4BHK', 'CUSTOM'].includes(h))) {
    throw new Error(`STAGING_ESTIMATOR_HOME_SIZES lists unknown home sizes (got ${homeSizes.join(',')})`);
  }
  const propertyTypes = list(env.STAGING_ESTIMATOR_PROPERTY_TYPES, 'APARTMENT');
  if (!propertyTypes.length || propertyTypes.some((t) => !['APARTMENT', 'VILLA'].includes(t))) {
    throw new Error(`STAGING_ESTIMATOR_PROPERTY_TYPES lists unknown property types (got ${propertyTypes.join(',')})`);
  }
  const ux = env.STAGING_ESTIMATOR_UX || 'v1';
  if (!['v1', 'v2'].includes(ux)) throw new Error(`STAGING_ESTIMATOR_UX must be v1 or v2 (got ${ux})`);
  // STAGING_ESTIMATOR_VERSION: v1/v2 follow STAGING_ESTIMATOR_UX; v3 is the catalog-driven estimator (ADR-013).
  const version = env.STAGING_ESTIMATOR_VERSION || 'v2';
  if (!['v1', 'v2', 'v3'].includes(version)) throw new Error(`STAGING_ESTIMATOR_VERSION must be v1, v2 or v3 (got ${version})`);
  return { enabled: env.STAGING_ESTIMATOR === 'on', packages, homeSizes, propertyTypes, ux, version };
}

export function buildApp(key) {
  siteKey(key);
  if (process.env.VITE_API_BASE && process.env.VITE_API_BASE !== STAGING_API) {
    throw new Error(`VITE_API_BASE is ${process.env.VITE_API_BASE}; a staging build uses ${STAGING_API} only`);
  }
  const env = { ...process.env, VITE_API_BASE: STAGING_API, VITE_TURNSTILE_SITE_KEY: key };
  execFileSync('npm', ['run', 'build'], { cwd: APP, env, stdio: 'inherit' });
  const out = join(APP, 'dist');
  writeFileSync(join(out, '_headers'), stagingHeaders(readFileSync(join(out, '_headers'), 'utf8')));
  checkStaging(out);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [what] = process.argv.slice(2);
  const key = process.env.STAGING_TURNSTILE_SITE_KEY;
  if (what === 'site') buildSite(join(APP, 'e2e/site-release'), join(APP, 'dist-staging-site'), key);
  else if (what === 'app') buildApp(key);
  else throw new Error('usage: node scripts/staging-build.mjs site|app');
  console.log(`staging ${what} build: API ${STAGING_API}, no production API reference`);
}
