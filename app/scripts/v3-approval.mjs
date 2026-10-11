// The V3 staging approval rules for the staging build: api/veda/modules/catalog/v3_approval_policy.json, implemented
// exactly as written there (the Python validator and the Terraform module implement the same text). The shared
// conformance cases (api/tests/fixtures/v3_approval/cases.json) prove the three decide every case identically.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const POLICY_FILE = fileURLToPath(new URL('../../api/veda/modules/catalog/v3_approval_policy.json', import.meta.url));
export const POLICY = JSON.parse(readFileSync(POLICY_FILE, 'utf8'));
export const CODES = POLICY.codes.map((c) => c.code);
export const MESSAGES = Object.fromEntries(POLICY.codes.map((c) => [c.code, c.message]));

const match = (pattern, value) => typeof value === 'string' && new RegExp(pattern).test(value);
const trim = (value) => value.replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, '');
const norm = (value) => (typeof value === 'string' ? trim(value).replace(/[ \t\r\n]+/g, ' ').toLowerCase() : null);
const isObject = (value) => typeof value === 'object' && value !== null && !Array.isArray(value);
const present = (value) => value !== undefined && value !== null;
const DAY = 86400000;

// A date as days since the epoch (UTC), or null when it is not a real calendar day in date_pattern form.
function day(value) {
  if (!match(POLICY.date_pattern, value)) return null;
  const [y, m, d] = value.split('-').map(Number);
  const t = Date.UTC(y, m - 1, d);
  const back = new Date(t);
  if (back.getUTCFullYear() !== y || back.getUTCMonth() !== m - 1 || back.getUTCDate() !== d) return null;
  return t / DAY;
}

export function utcToday() {
  return new Date().toISOString().slice(0, 10);
}

function evidenceOk(evidence) {
  const required = [...POLICY.git_evidence, ...POLICY.digest_evidence];
  if (!isObject(evidence)) return false;
  const keys = Object.keys(evidence);
  if (keys.length !== required.length || !required.every((k) => keys.includes(k))) return false;
  return keys.every((k) => {
    const v = evidence[k];
    if (!isObject(v) || !(typeof v.reference === 'string' && trim(v.reference).length >= POLICY.reference_min_length)) return false;
    return POLICY.git_evidence.includes(k) ? match(POLICY.git_sha_pattern, v.git_sha) : match(POLICY.sha256_pattern, v.sha256);
  });
}

// The failing rule codes, in policy order. `raw` is the record file's bytes (null: no record); `today` a YYYY-MM-DD UTC
// date; `boundSha256` the digest the record must have.
export function evaluate(raw, { today, boundSha256 }) {
  if (raw === null || raw === undefined) return ['NO_RECORD'];
  let doc;
  try { doc = JSON.parse(Buffer.from(raw).toString('utf8')); } catch { doc = null; }
  if (!isObject(doc)) return ['MALFORMED'];
  const failing = new Set();
  const now = day(today);

  if (doc.schema !== POLICY.schema) failing.add('SCHEMA');
  if (doc.status !== POLICY.approved_status) failing.add('STATUS');
  if (doc.environment !== POLICY.environment) failing.add('ENVIRONMENT');
  if (!match(POLICY.release_pattern, doc.release)) failing.add('RELEASE');

  const scope = doc.approval_scope;
  if (!(isObject(scope) && Object.entries(POLICY.scope).every(([k, v]) => scope[k] === v) && typeof scope.media_delivery === 'boolean')) {
    failing.add('SCOPE');
  }

  if (doc.status === POLICY.revoked_status || present(doc.revoked_at) || present(doc.revocation_reason)) failing.add('REVOKED');

  const approver = norm(doc.approver);
  const author = norm(doc.author);
  const placeholder = POLICY.placeholder.toUpperCase();
  if (!approver || !author || approver === author || doc.approver.toUpperCase().includes(placeholder)
    || doc.author.toUpperCase().includes(placeholder)) failing.add('APPROVER');

  const approved = day(doc.approved_at);
  if (approved === null) failing.add('APPROVAL_DATE');
  else if (approved > now) failing.add('APPROVAL_IN_FUTURE');

  const review = day(doc.review_by);
  if (review === null || (approved !== null && !(approved < review && review <= approved + POLICY.max_review_days))) {
    failing.add('REVIEW_WINDOW');
  }
  if (review !== null && review <= now) failing.add('REVIEW_REACHED');

  const hasExpiry = present(doc.expires_at);
  const hasDecision = present(doc.non_expiring_decision);
  const expires = day(doc.expires_at);
  const decision = doc.non_expiring_decision;
  if (hasExpiry === hasDecision
    || (hasExpiry && (expires === null || (approved !== null && expires <= approved)))
    || (hasDecision && !(typeof decision === 'string' && trim(decision).length >= POLICY.non_expiring_min_length))) {
    failing.add('EXPIRY_POLICY');
  }
  if (expires !== null && expires <= now) failing.add('EXPIRED');

  if (!evidenceOk(doc.evidence)) failing.add('EVIDENCE');

  if (!(match(POLICY.sha256_pattern, boundSha256) && boundSha256 === createHash('sha256').update(raw).digest('hex'))) {
    failing.add('DIGEST_MISMATCH');
  }
  return CODES.filter((c) => failing.has(c));
}

export function messages(codes) {
  return codes.map((c) => MESSAGES[c]);
}
