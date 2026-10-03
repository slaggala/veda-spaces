// node --test scripts/audit-dev.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { evaluate } from './audit-dev.mjs';

const exceptions = JSON.parse(readFileSync(new URL('../audit-exceptions.json', import.meta.url), 'utf8'));
const braces = {
  source: 1240992,
  name: 'braces',
  url: 'https://github.com/advisories/GHSA-vfj7-8cjw-p6xm',
  severity: 'high',
  range: '<=3.0.3',
  title: 'braces vulnerable to stack-exhaustion denial of service through deeply nested patterns',
};
const audit = (...vias) => ({
  vulnerabilities: {
    braces: { name: 'braces', severity: 'high', via: vias },
    micromatch: { name: 'micromatch', severity: 'high', via: ['braces'] },
  },
});

test('the reviewed braces advisory is covered until it expires', () => {
  const r = evaluate(audit(braces), exceptions, '2026-10-03');
  assert.deepEqual(r.failures, []);
  assert.equal(r.covered, 1);
});

test('an expired exception fails', () => {
  const r = evaluate(audit(braces), exceptions, '2027-01-01');
  assert.match(r.failures.join(), /expired on 2026-12-31/);
});

test('any other high or critical advisory fails', () => {
  const other = { ...braces, name: 'lodash', url: 'https://github.com/advisories/GHSA-xxxx-yyyy-zzzz', severity: 'critical' };
  const r = evaluate(audit(braces, other), exceptions, '2026-10-03');
  assert.match(r.failures.join(), /critical GHSA-xxxx-yyyy-zzzz in lodash/);
});

test('the same advisory in a wider range or another package is not covered', () => {
  assert.equal(evaluate(audit({ ...braces, range: '<=3.0.4' }), exceptions, '2026-10-03').failures.length, 1);
  assert.equal(evaluate(audit({ ...braces, name: 'braces-fork' }), exceptions, '2026-10-03').failures.length, 1);
});

test('moderate and low advisories do not block', () => {
  const low = { ...braces, url: 'https://github.com/advisories/GHSA-low', name: 'x', severity: 'moderate' };
  assert.deepEqual(evaluate(audit(braces, low), exceptions, '2026-10-03').failures, []);
});

test('a stale exception is reported, not failed', () => {
  const r = evaluate({ vulnerabilities: {} }, exceptions, '2026-10-03');
  assert.deepEqual(r.failures, []);
  assert.match(r.warnings.join(), /no longer matches any advisory/);
});

test('exceptions must be development-scoped and expire within 90 days', () => {
  const bad = { exceptions: [{ ...exceptions.exceptions[0], scope: 'production', expires: '2027-06-30' }] };
  const r = evaluate(audit(braces), bad, '2026-10-03');
  assert.match(r.failures.join(), /scope must be "development"/);
  assert.match(r.failures.join(), /within 90 days/);
});
