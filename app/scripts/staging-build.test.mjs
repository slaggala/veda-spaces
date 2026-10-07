// node --test scripts/staging-build.test.mjs
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { buildSite, checkStaging, PRODUCTION_API, siteKey, STAGING_API } from './staging-build.mjs';

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
