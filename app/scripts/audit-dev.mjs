// Development-dependency audit with reviewed, expiring exceptions (docs/operations/dependency-audit-exceptions.md).
// Production dependencies are audited separately and strictly (`npm audit --omit=dev`, no exceptions).
//
// Fails when any high or critical advisory is not covered by an exception in audit-exceptions.json, when a
// covering exception has expired, or when an exception breaks the policy (missing fields, not development
// scope, lifetime over 90 days). An exception whose advisory no longer appears is reported so it can be removed.
//
//   node scripts/audit-dev.mjs                         # runs `npm audit --json`
//   node scripts/audit-dev.mjs --input audit.json --exceptions file.json --today 2026-10-03
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const MAX_LIFETIME_DAYS = 90;
const BLOCKING = new Set(['high', 'critical']);
const REQUIRED = ['advisory', 'package', 'range', 'severity', 'scope', 'reason', 'approved_on', 'expires'];

export function evaluate(audit, exceptionsDoc, today) {
  const failures = [];
  const warnings = [];
  const exceptions = exceptionsDoc.exceptions ?? [];
  for (const ex of exceptions) {
    const missing = REQUIRED.filter((k) => !ex[k]);
    if (missing.length) failures.push(`exception ${ex.advisory ?? '?'}: missing ${missing.join(', ')}`);
    if (ex.scope !== 'development') failures.push(`exception ${ex.advisory}: scope must be "development"`);
    const lifetime = (Date.parse(ex.expires) - Date.parse(ex.approved_on)) / 86_400_000;
    if (!(lifetime >= 0 && lifetime <= MAX_LIFETIME_DAYS)) {
      failures.push(`exception ${ex.advisory}: must expire within ${MAX_LIFETIME_DAYS} days of approval`);
    }
  }
  const advisories = new Map();
  for (const vuln of Object.values(audit.vulnerabilities ?? {})) {
    for (const via of vuln.via ?? []) {
      if (typeof via === 'object' && via.url) advisories.set(`${via.url}|${via.name}|${via.range}`, via);
    }
  }
  const used = new Set();
  for (const adv of advisories.values()) {
    if (!BLOCKING.has(adv.severity)) continue;
    const id = adv.url.split('/').pop();
    const ex = exceptions.find((e) => e.advisory === id && e.package === adv.name && e.range === adv.range);
    if (!ex) {
      failures.push(`${adv.severity} ${id} in ${adv.name} ${adv.range}: ${adv.title} (no exception)`);
      continue;
    }
    used.add(ex);
    if (today > ex.expires) failures.push(`exception ${id} (${adv.name}) expired on ${ex.expires}: re-review or remove it`);
  }
  for (const ex of exceptions) {
    if (!used.has(ex)) warnings.push(`exception ${ex.advisory} (${ex.package}) no longer matches any advisory: remove it`);
  }
  return { failures, warnings, covered: used.size };
}

function arg(name) {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : undefined;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const input = arg('--input');
  let raw;
  if (input) {
    raw = readFileSync(input, 'utf8');
  } else {
    try {
      raw = execFileSync('npm', ['audit', '--json'], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
    } catch (err) {
      raw = err.stdout; // npm audit exits non-zero when it finds anything
    }
  }
  const exceptionsFile = arg('--exceptions') ?? new URL('../audit-exceptions.json', import.meta.url);
  const today = arg('--today') ?? new Date().toISOString().slice(0, 10);
  const { failures, warnings, covered } = evaluate(JSON.parse(raw), JSON.parse(readFileSync(exceptionsFile, 'utf8')), today);
  for (const w of warnings) console.log(`::warning::audit-dev: ${w}`);
  for (const f of failures) console.log(`::error::audit-dev: ${f}`);
  if (failures.length) process.exit(1);
  console.log(`audit-dev: no unexcepted high or critical advisories (${covered} covered by reviewed exceptions)`);
}
