// node --test scripts/staging-build.test.mjs
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { buildSite, checkStaging, estimatorFlags, PRODUCTION_API, siteKey, STAGING_API } from './staging-build.mjs';

const SRC = fileURLToPath(new URL('../e2e/site-release', import.meta.url));
const KEY = '0x4AAAAAAAstagingTestKey01';
const tmp = () => mkdtempSync(join(tmpdir(), 'veda-staging-'));

test('the staging site points at the staging API, with credentials and the widget key', () => {
  const out = join(tmp(), 'site');
  buildSite(SRC, out, KEY);
  const html = readFileSync(join(out, 'index.html'), 'utf8');
  assert.match(html, new RegExp(`<meta name="veda-api-base" content="${STAGING_API}">`));
  assert.match(html, new RegExp(`<meta name="veda-turnstile-sitekey" content="${KEY}">`));
  assert.match(html, /<meta name="veda-api-credentials" content="include">/);
  const headers = readFileSync(join(out, '_headers'), 'utf8');
  assert.ok(headers.includes(`connect-src 'self' ${STAGING_API}`) && !headers.includes(PRODUCTION_API));
  assert.match(headers, /X-Robots-Tag: noindex, nofollow/);
  assert.equal(readFileSync(join(out, 'robots.txt'), 'utf8'), 'User-agent: *\nDisallow: /\n');
  assert.ok(!existsSync(join(out, 'sitemap.xml')));
});

test('the committed site stays intake-disabled (production)', () => {
  const html = readFileSync(join(SRC, 'index.html'), 'utf8');
  for (const name of ['veda-api-base', 'veda-turnstile-sitekey', 'veda-api-credentials']) {
    assert.ok(html.includes(`<meta name="${name}" content="">`), name);
  }
});

test('a build that names the production API is refused', () => {
  const out = join(tmp(), 'site');
  buildSite(SRC, out, KEY);
  writeFileSync(join(out, 'assets/extra.js'), `fetch('${PRODUCTION_API}/x')`);
  assert.throws(() => checkStaging(out), /names the production API/);
});

test('test and missing Turnstile keys are refused', () => {
  const secretShaped = '0x4AAAAAAAstagingSecretKeyLooksLikeThis'; // pragma: allowlist secret (fake, secret-key length)
  for (const key of [undefined, '', '1x00000000000000000000AA', '2x00000000000000000000AB', '3x00000000000000000000FF', secretShaped]) {
    assert.throws(() => siteKey(key), /not a test or secret key/, String(key));
  }
  assert.equal(siteKey(KEY), KEY);
  assert.equal(siteKey('0x4AAAAAAAAbcdEFghIJklMN'), '0x4AAAAAAAAbcdEFghIJklMN'); // a 24-character site key
});

test('an app build aimed at another API is refused before building', async () => {
  const { buildApp } = await import('./staging-build.mjs');
  process.env.VITE_API_BASE = PRODUCTION_API;
  try {
    assert.throws(() => buildApp(KEY), /a staging build uses/);
  } finally {
    delete process.env.VITE_API_BASE;
  }
});

test('the estimator page is off unless STAGING_ESTIMATOR=on, and Essential-only by default', () => {
  const off = join(tmp(), 'site');
  buildSite(SRC, off, KEY, estimatorFlags({}));
  const offHtml = readFileSync(join(off, 'estimate.html'), 'utf8');
  assert.match(offHtml, /<meta name="veda-estimator" content="">/);
  assert.match(offHtml, new RegExp(`<meta name="veda-api-base" content="${STAGING_API}">`));
  const on = join(tmp(), 'site');
  buildSite(SRC, on, KEY, estimatorFlags({ STAGING_ESTIMATOR: 'on' }));
  const onHtml = readFileSync(join(on, 'estimate.html'), 'utf8');
  assert.match(onHtml, /<meta name="veda-estimator" content="on">/);
  assert.match(onHtml, /<meta name="veda-estimator-packages" content="ESSENTIAL">/);
  assert.match(onHtml, /<meta name="veda-estimator-home-sizes" content="3BHK">/, 'D3: only supported sizes');
  assert.match(onHtml, /<meta name="veda-estimator-property-types" content="APARTMENT">/);
  assert.ok(!onHtml.includes(PRODUCTION_API));
  assert.throws(() => estimatorFlags({ STAGING_ESTIMATOR_PACKAGES: 'LUXURY' }), /must list ESSENTIAL/);
  assert.throws(() => estimatorFlags({ STAGING_ESTIMATOR_PACKAGES: 'ESSENTIAL,LUXURY' }), /optionally PREMIUM/, 'D2');
  assert.throws(() => estimatorFlags({ STAGING_ESTIMATOR_HOME_SIZES: '5BHK' }), /unknown home sizes/);
  assert.throws(() => estimatorFlags({ STAGING_ESTIMATOR_PROPERTY_TYPES: 'OFFICE' }), /unknown property types/);
  assert.match(onHtml, /<meta name="veda-estimator-ux" content="">/, 'V1 by default');
  const v2 = join(tmp(), 'site');
  buildSite(SRC, v2, KEY, estimatorFlags({ STAGING_ESTIMATOR: 'on', STAGING_ESTIMATOR_UX: 'v2' }));
  assert.match(readFileSync(join(v2, 'estimate.html'), 'utf8'), /<meta name="veda-estimator-ux" content="v2">/);
  assert.throws(() => estimatorFlags({ STAGING_ESTIMATOR_UX: 'v3' }), /v1 or v2/);
});

test('the committed estimator page is off and holds no rates', () => {
  const html = readFileSync(join(SRC, 'estimate.html'), 'utf8');
  for (const name of ['veda-estimator', 'veda-estimator-packages', 'veda-estimator-home-sizes', 'veda-estimator-property-types', 'veda-estimator-ux', 'veda-api-base', 'veda-turnstile-sitekey', 'veda-api-credentials']) {
    assert.ok(html.includes(`<meta name="${name}" content="">`), name);
  }
  const js = readFileSync(join(SRC, 'assets/estimate.js'), 'utf8');
  assert.ok(!/rate_minor|_minor\s*:\s*\d/.test(js), 'no rate table in the page script');
  assert.ok(!js.includes('innerHTML'), 'DOM built without innerHTML');
  const v2js = readFileSync(join(SRC, 'assets/estimate-v2.js'), 'utf8');
  assert.ok(!/rate_minor|_minor\s*:\s*\d|innerHTML/.test(v2js), 'UX V2 script: no rate table, no innerHTML');
  assert.ok(!/per sq|per sheet|10 years|30-year/i.test(v2js), 'UX V2 script: no rates or warranty durations in copy');
  // Phase 5: no material or hardware duration; the one duration is Veda Spaces' own service support, as the policy states.
  const copy = v2js.replace(/^\s*\/\/.*$/gm, ''); // what customers can see, not the comments
  assert.ok(!/\d+\s*-?\s*(year|years|yr)s?\b|up to \d/i.test(copy), 'UX V2 script: no numeric warranty duration');
  assert.deepEqual(copy.match(/[^'.]*\b(one|two|three|five|ten|thirty) years?\b[^'.]*/gi),
    ['Veda Spaces provides one year of applicable workmanship and fitment service support from handover, subject to the Warranty, Service & Customer Care Policy'],
    'UX V2 script: the only duration is the Veda Spaces service-support sentence');
  const policy = readFileSync(join(SRC, 'warranty.html'), 'utf8');
  assert.ok(/one year of free service from the project handover date for fitment-related or workmanship issues/.test(policy), 'the policy supports the one-year service sentence');
  assert.ok(!/\b(complimentary|free)\b/i.test(copy), 'UX V2 script: required work is never called free or complimentary');
  // Phase 12: the customer-promise matrix and the page agree both ways.
  const matrix = JSON.parse(readFileSync(join(SRC, '../../../docs/implementation/estimator/specifications/essential-1.1-promise-matrix.json'), 'utf8'));
  for (const row of matrix.page) assert.ok(copy.includes(row.statement), `matrix statement not on the page: ${row.statement}`);
  const listed = new Set(matrix.page.map((r) => r.statement));
  const constant = (name) => { const m = copy.match(new RegExp(`const ${name} = (\\[[^\\]]*\\]|'[^']*');`)); assert.ok(m, name); return JSON.parse(m[1].replace(/'/g, '"')); };
  for (const name of ['PACKAGE_TEXT', 'ALLOWANCE_TEXT', 'ALLOWANCE_NOTES', 'MANUFACTURER_DEFAULT', 'SERVICE_SUPPORT', 'SERVICE_NOTE', 'TRUST_MARKERS', 'NEXT_STEPS']) {
    for (const statement of [constant(name)].flat()) assert.ok(listed.has(statement), `page promise missing from the matrix: ${statement}`);
  }
});

test('the warranty policy page is the same customer-facing page on the live site and the staging site', () => {
  const live = readFileSync(join(SRC, '../../../dist/warranty.html'), 'utf8');
  const release = readFileSync(join(SRC, 'warranty.html'), 'utf8');
  assert.equal(live, release, 'dist/warranty.html and site-release/warranty.html must be identical');
  assert.equal(readFileSync(join(SRC, '../../../dist/assets/policy.css'), 'utf8'), readFileSync(join(SRC, 'assets/policy.css'), 'utf8'));
  for (const id of ['summary', 'coverage', 'exclusions', 'variations', 'tolerances', 'handover', 'service', 'tiles', 'claims', 'contact']) {
    assert.ok(release.includes(`id="${id}"`), `section ${id}`);
  }
  assert.ok(!/<script|<style|\sstyle=|\son[a-z]+=/i.test(release), 'no inline script or style (production CSP)');
  assert.match(release, /<link rel="canonical" href="https:\/\/www\.vedaspaces\.com\/warranty">/);
  assert.match(release, /Version 1\.0 · Effective 6 October 2026/);
  // Approved wording kept (spot checks of the clauses the estimator summary relies on).
  for (const clause of [
    'up to 10 years, depending on the plywood selected for the project and subject to the applicable manufacturer’s warranty',
    '3 years against manufacturing defects, subject to manufacturer terms and normal use',
    '5 years against manufacturing defects, subject to manufacturer terms and normal use',
    'does not extend Veda Spaces workmanship or free-service obligations',
    'one year of free service from the project handover date for fitment-related or workmanship issues',
    'Nothing in this policy is intended to limit rights that cannot legally be excluded under applicable law.',
  ]) assert.ok(release.includes(clause), clause);
  assert.ok(!/customer name|signature|policy reference/i.test(release), 'no contract or customer fields on the public page');
  for (const map of ['dist/sitemap.xml', 'app/e2e/site-release/sitemap.xml']) {
    assert.ok(readFileSync(join(SRC, '../../..', map), 'utf8').includes('<loc>https://www.vedaspaces.com/warranty</loc>'), map);
  }
});

test('the estimator V2 prototype stays on staging: not in the live site, no network, no inline code, noindex', () => {
  const proto = join(SRC, 'prototype/estimator-v2');
  const html = readFileSync(join(proto, 'index.html'), 'utf8');
  const js = readFileSync(join(proto, 'proto.js'), 'utf8');
  assert.ok(!existsSync(join(SRC, '../../../dist/prototype')), 'never in dist/ (the production site)');
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  assert.ok(!/<script(?![^>]*\bsrc=)|<style|\sstyle=|\son[a-z]+=/i.test(html), 'no inline script or style (production CSP)');
  assert.ok(!/fetch\(|XMLHttpRequest|sendBeacon|WebSocket|innerHTML/.test(js), 'no network calls and no innerHTML');
  assert.ok(!/rate_minor|_minor\s*:/.test(js), 'no rate table');
  const spec = readFileSync(join(proto, 'proto-spec.js'), 'utf8');
  assert.ok(!/₹|fetch\(|XMLHttpRequest|innerHTML/.test(spec), 'customer specification: no amounts, no network, no innerHTML');
  const out = join(tmp(), 'site');
  buildSite(SRC, out, KEY, estimatorFlags({}));
  assert.ok(existsSync(join(out, 'prototype/estimator-v2/index.html')), 'served by the staging site (behind Access)');
});
