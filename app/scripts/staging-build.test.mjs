// node --test scripts/staging-build.test.mjs
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { APPROVAL, buildSite, canonicalSha256, checkStaging, checkV3Approval, estimatorFlags, PRODUCTION_API, readCopy, siteKey, STAGING_API, V3_DIGEST_EVIDENCE, V3_GIT_EVIDENCE, v3ImageCsp } from './staging-build.mjs';
import { createHash } from 'node:crypto';

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
  // V2 is refused until the owner approves exactly this customer copy for staging (final pre-activation closure).
  const v2 = join(tmp(), 'site');
  const flagsV2 = estimatorFlags({ STAGING_ESTIMATOR: 'on', STAGING_ESTIMATOR_UX: 'v2' });
  assert.throws(() => buildSite(SRC, v2, KEY, flagsV2), /STAGING_ESTIMATOR_UX=v2 is refused: the owner approval record is PENDING/, 'the committed record is pending');
  const copy = readCopy(join(SRC, 'assets/estimate-v2-copy.js'));
  const approved = { ...JSON.parse(readFileSync(APPROVAL, 'utf8')), status: 'APPROVED', owner: 'Test Owner', approved_on: '2026-10-09',
    customer_copy_sha256: canonicalSha256(copy),
    warranty_copy_sha256: canonicalSha256({ manufacturer: copy.promise.manufacturer, service: copy.promise.service, serviceNote: copy.promise.serviceNote }) };
  const approvalFile = join(tmp(), 'approval.json');
  writeFileSync(approvalFile, JSON.stringify(approved));
  buildSite(SRC, v2, KEY, { ...flagsV2, approvalFile });
  assert.match(readFileSync(join(v2, 'estimate.html'), 'utf8'), /<meta name="veda-estimator-ux" content="v2">/);
  writeFileSync(approvalFile, JSON.stringify({ ...approved, customer_copy_sha256: '0'.repeat(64) }));
  assert.throws(() => buildSite(SRC, v2, KEY, { ...flagsV2, approvalFile }), /customer copy is not the approved copy/, 'stale copy digest');
  writeFileSync(approvalFile, JSON.stringify({ ...approved, scope: { ...approved.scope, public_intake: true } }));
  assert.throws(() => buildSite(SRC, v2, KEY, { ...flagsV2, approvalFile }), /does not cover V2 on staging/, 'scope must exclude public intake');
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
  const copyFile = readFileSync(join(SRC, 'assets/estimate-v2-copy.js'), 'utf8');
  for (const [name, src] of [['UX V2 script', v2js], ['UX V2 copy', copyFile]]) {
    assert.ok(!/rate_minor|_minor\s*:\s*\d|innerHTML/.test(src), `${name}: no rate table, no innerHTML`);
    assert.ok(!/per sq|per sheet|10 years|30-year/i.test(src), `${name}: no rates or warranty durations`);
  }
  // Every customer-visible string lives in the copy file (L3): no multi-word literal is left in the script.
  const code = v2js.replace(/^\s*\/\/.*$/gm, '').replace(/\/\/ .*$/gm, '');
  const literals = [...code.matchAll(/'([^'\n]*)'|`([^`\n]*)`/g)].map((m) => (m[1] ?? m[2]).replace(/\$\{[^}]*\}/g, ' '));
  assert.deepEqual(literals.filter((t) => /[A-Za-z]{2,}\s+[A-Za-z]{2,}/.test(t) && t !== 'use strict'), [], 'UX V2 script: customer text belongs in estimate-v2-copy.js');
  // V2 never renders API text directly, only the block the reviewed matrix registers (M3).
  assert.ok(!/\be\.(disclaimer|exclusions|client_scope|assumptions|subject_to|title)\b|project_preparation\.(description|note|inclusions)|warranty\.(items|note)|custom_features_allowance\.description/.test(code),
    'UX V2 script: unregistered API text is never rendered');
  const COPY = readCopy(join(SRC, 'assets/estimate-v2-copy.js'));
  const leaves = (o) => (typeof o === 'string' ? [o] : Object.values(o).flatMap(leaves));
  const promises = leaves(COPY.promise);
  const copyText = promises.join('\n');
  // Phase 5: no material or hardware duration; the one duration is Veda Spaces' own service support, as the policy states.
  assert.ok(!/\d+\s*-?\s*(year|years|yr)s?\b|up to \d/i.test(copyText + code), 'UX V2: no numeric warranty duration');
  assert.deepEqual(promises.filter((t) => /\b(one|two|three|five|ten|thirty) years?\b/i.test(t)), [COPY.promise.service], 'UX V2: the only duration is the service-support sentence');
  const policy = readFileSync(join(SRC, 'warranty.html'), 'utf8');
  assert.ok(/one year of free service from the project handover date for fitment-related or workmanship issues/.test(policy), 'the policy supports the one-year service sentence');
  assert.ok(!/\b(complimentary|free)\b/i.test(copyText + code), 'UX V2: required work is never called free or complimentary');
  assert.ok(!/soft-close/i.test(COPY.promise.packageSubtitle), 'the package picker never promises soft-close hardware universally');
  // The customer-promise matrix and the page agree both ways (pre-activation closure).
  const matrix = JSON.parse(readFileSync(join(SRC, '../../../api/veda/modules/estimator/approved/essential-1.1-promise-matrix.json'), 'utf8'));
  const listed = new Set(matrix.rows.flatMap((r) => r.statements));
  for (const t of promises) assert.ok(listed.has(t), `page promise missing from the matrix: ${t}`);
  const pageText = readFileSync(join(SRC, 'estimate.html'), 'utf8').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
  for (const r of matrix.rows.filter((x) => x.kind === 'page' && !x.where.startsWith('Estimate response'))) {
    for (const t of r.statements) {
      const shown = promises.includes(t) || pageText.includes(t);
      assert.ok(r.status === 'REMOVED' ? !shown : shown, `${r.id}: ${r.status === 'REMOVED' ? 'removed promise still shown' : 'matrix statement not on the page'}: ${t}`);
    }
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

test('V3 (catalog-driven estimator) is not in a staging build without its approval record (ADR-013)', () => {
  const out = mkdtempSync(join(tmpdir(), 'veda-v3-'));
  buildSite(SRC, out, KEY, estimatorFlags({ STAGING_ESTIMATOR: 'on' }));
  for (const f of ['estimate-v3.html', 'assets/estimate-v3.js', 'assets/estimate-v3.css']) assert.ok(!existsSync(join(out, f)), f);
  assert.throws(() => buildSite(SRC, out, KEY, estimatorFlags({ STAGING_ESTIMATOR: 'on', STAGING_ESTIMATOR_VERSION: 'v3' })), /V3 staging activation record/);
  assert.throws(() => estimatorFlags({ STAGING_ESTIMATOR_VERSION: 'v4' }), /v1, v2 or v3/);
  assert.equal(estimatorFlags({}).version, 'v2');
  rmSync(out, { recursive: true, force: true });
});


// --- targeted media enablement: the V3 staging approval gate and the V3-only CSP delta ---------------------------------
function v3Record(over = {}) {
  const evidence = Object.fromEntries([...V3_GIT_EVIDENCE.map((k) => [k, { git_sha: 'a'.repeat(40), reference: `git ${k} (synthetic)` }]),
    ...V3_DIGEST_EVIDENCE.map((k) => [k, { sha256: 'b'.repeat(64), reference: `evidence ${k} (synthetic)` }])]);
  return { schema: 'veda.catalog.v3-staging-approval/1', status: 'APPROVED', release: 'V3-STAGING-1', author: 'Catalog lead (role, test)',
    approver: 'Owner (role, test)', approved_on: '2026-10-10',
    scope: { environments: ['staging'], version: 'v3', public_intake: false, media_delivery: true, three_d: false, video: false }, evidence, ...over };
}
function v3Files(record, bind = true) {
  const dir = mkdtempSync(join(tmpdir(), 'veda-v3-approval-'));
  const approvalFile = join(dir, 'v3-staging-approval.json');
  writeFileSync(approvalFile, JSON.stringify(record, null, 2));
  const sha = createHash('sha256').update(readFileSync(approvalFile)).digest('hex');
  const platformFile = join(dir, 'staging-platform.json');
  writeFileSync(platformFile, JSON.stringify({ catalog_v3: { approval_record_sha256: bind ? sha : null } }));
  return { dir, approvalFile, platformFile };
}

test('V3: an APPROVED, complete, independent, digest-bound record opens the gate; anything else is refused', () => {
  const ok = v3Files(v3Record());
  checkV3Approval(ok.approvalFile, ok.platformFile);
  const cases = [
    [v3Record({ status: 'DRAFT' }), true, /record is DRAFT/],
    [v3Record({ status: 'REVOKED' }), true, /record is REVOKED/],
    [v3Record({ approver: 'Catalog lead (role, test)' }), true, /not independent/],
    [v3Record({ approver: '[OWNER TO FILL]' }), true, /not independent/],
    [v3Record({ evidence: {} }), true, /evidence without a digest/],
    [v3Record({ evidence: { ...v3Record().evidence, real_card_evidence: { reference: 'pending' } } }), true, /real_card_evidence/],
    [v3Record({ scope: { ...v3Record().scope, public_intake: true } }), true, /staging only/],
    [v3Record({ scope: { ...v3Record().scope, environments: ['staging', 'production'] } }), true, /staging only/],
    [v3Record(), false, /not the one bound/],
  ];
  for (const [record, bind, why] of cases) {
    const f = v3Files(record, bind);
    assert.throws(() => checkV3Approval(f.approvalFile, f.platformFile), why);
    rmSync(f.dir, { recursive: true, force: true });
  }
  rmSync(ok.dir, { recursive: true, force: true });
});

test('V3 CSP delta: only the V3 page, only img-src, only the staging API host; the site policy is untouched', () => {
  const site = readFileSync(join(SRC, '_headers'), 'utf8').replaceAll(PRODUCTION_API, STAGING_API);
  const out = v3ImageCsp(site);
  assert.ok(out.startsWith(site.replace(/\n*$/, '\n')), 'the existing rules are unchanged');
  const rule = out.slice(out.indexOf('/estimate-v3*'));
  assert.match(rule, /^\/estimate-v3\*\n {2}! Content-Security-Policy\n {2}Content-Security-Policy: /);
  const v3 = rule.split('Content-Security-Policy: ')[1].trim();
  const base = site.split('\n').find((l) => l.trim().startsWith('Content-Security-Policy:')).trim().slice('Content-Security-Policy:'.length).trim();
  assert.equal(v3, base.replace("img-src 'self' data:", `img-src 'self' data: ${STAGING_API}`), 'exactly one change');
  assert.ok(!/\*|blob:|media-src|worker-src/.test(v3.match(/img-src [^;]*/)[0] + (v3.includes('media-src') ? ' media-src' : '') + (v3.includes('worker-src') ? ' worker-src' : '')), 'no wildcard, blob, media-src or worker-src');
  assert.ok(!out.includes('api.vedaspaces.com'), 'no production host');
});

test('V3 CSP delta: a build without the approved V3 page carries no V3 rule (production and staging unchanged)', () => {
  const out = mkdtempSync(join(tmpdir(), 'veda-v3-off-'));
  buildSite(SRC, out, KEY, estimatorFlags({ STAGING_ESTIMATOR: 'on' }));
  const headers = readFileSync(join(out, '_headers'), 'utf8');
  assert.ok(!headers.includes('/estimate-v3*') && !headers.includes(`img-src 'self' data: ${STAGING_API}`));
  rmSync(out, { recursive: true, force: true });
  const prod = readFileSync(join(SRC, '_headers'), 'utf8');
  assert.ok(!prod.includes('/estimate-v3*') && !prod.includes('api-staging'), 'the production _headers never names the staging host');
});

test('V3 with its approved, bound record: the page ships with the V3-only image policy', () => {
  const f = v3Files(v3Record());
  const out = mkdtempSync(join(tmpdir(), 'veda-v3-on-'));
  buildSite(SRC, out, KEY, { ...estimatorFlags({ STAGING_ESTIMATOR: 'on', STAGING_ESTIMATOR_VERSION: 'v3' }), v3ApprovalFile: f.approvalFile, platformFile: f.platformFile });
  assert.ok(existsSync(join(out, 'estimate-v3.html')));
  assert.ok(readFileSync(join(out, '_headers'), 'utf8').includes(`/estimate-v3*\n  ! Content-Security-Policy\n`));
  rmSync(out, { recursive: true, force: true });
  rmSync(f.dir, { recursive: true, force: true });
});
