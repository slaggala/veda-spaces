// Staging builds for Cloudflare Pages (AUT-204). Staging sits behind Cloudflare Access and talks only to the staging
// API; a staging build that names the production API is refused.
//   node scripts/staging-build.mjs site   → dist-staging-site/ (the marketing site of e2e/site-release, intake on)
//   node scripts/staging-build.mjs app    → dist/ (the staff workspace SPA)
// Both need STAGING_TURNSTILE_SITE_KEY (the real staging widget, AUT-203; the public site key, not the secret).
import { execFileSync } from 'node:child_process';
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

/** Refuse any output that names the production API, or that lacks the staging API. */
export function checkStaging(dir) {
  const hits = files(dir).filter((f) => readFileSync(f, 'latin1').includes(PRODUCTION_API));
  if (hits.length) throw new Error(`staging build names the production API: ${hits.join(', ')}`);
  if (!files(dir).some((f) => readFileSync(f, 'latin1').includes(STAGING_API))) {
    throw new Error('staging build does not name the staging API');
  }
}

export function buildSite(src, out, key, estimator = estimatorFlags(process.env)) {
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
  }
  writeFileSync(join(out, 'estimate.html'), est);
  writeFileSync(join(out, '_headers'), stagingHeaders(readFileSync(join(out, '_headers'), 'utf8')));
  writeFileSync(join(out, 'robots.txt'), 'User-agent: *\nDisallow: /\n');
  rmSync(join(out, 'sitemap.xml'), { force: true });
  checkStaging(out);
}

/** STAGING_ESTIMATOR=on enables the estimator page; STAGING_ESTIMATOR_PACKAGES lists offered packages (default ESSENTIAL). */
export function estimatorFlags(env) {
  const packages = (env.STAGING_ESTIMATOR_PACKAGES || 'ESSENTIAL').split(',').map((p) => p.trim()).filter(Boolean);
  const unknown = packages.filter((p) => !['ESSENTIAL', 'PREMIUM', 'LUXURY'].includes(p));
  if (unknown.length || !packages.includes('ESSENTIAL')) {
    throw new Error(`STAGING_ESTIMATOR_PACKAGES must list ESSENTIAL and only known packages (got ${packages.join(',')})`);
  }
  return { enabled: env.STAGING_ESTIMATOR === 'on', packages };
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
