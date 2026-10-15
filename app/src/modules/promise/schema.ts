import type { Vocabulary } from './api.js';

/**
 * How each customer-pack key is edited: structured fields, never raw JSON. A value goes to the API exactly as the
 * section's keys (the server validates every rule again). Empty optional text is sent as null; an entry is marked
 * ``active: false`` only when it is switched off (an active entry carries no flag, so it stays identical to the
 * published one).
 */

export type FieldKind = 'text' | 'textarea' | 'select' | 'checkbox';
export interface FieldDef {
  name: string; label: string; kind: FieldKind; optional?: boolean; max?: number; hint?: string;
  /** Select options: a vocabulary list, or a function of the whole draft (e.g. the version's contact codes). */
  options?: (v: Vocabulary, draft: Record<string, unknown>, context: Record<string, unknown>) => string[];
}
export interface ListDef { kind: 'list'; key: string; label: string; item: string; fields: FieldDef[]; active: boolean; reorder: boolean }
export interface TextDef { kind: 'scalar'; key: string; label: string; max: number; hint?: string }
export interface StringsDef { kind: 'strings'; key: string; label: string; item: string; max: number; hint?: string }
export interface ObjectDef { kind: 'object'; key: string; label: string; parts: Part[] }
export type Part = ListDef | TextDef | StringsDef | ObjectDef | (FieldDef & { kind: FieldKind });

const CODE: FieldDef = { name: 'code', label: 'Code', kind: 'text', max: 40, hint: 'Capital letters, digits and _ (e.g. SITE_ACCESS). Kept across versions.' };
const TEXT: FieldDef = { name: 'text', label: 'Customer wording', kind: 'textarea', max: 600 };
const cat = (pick: (v: Vocabulary) => string[]): FieldDef => ({ name: 'category', label: 'Category', kind: 'select', options: (v) => pick(v) });

const COPY_HINT = 'Customer copy: no amounts, durations, phone numbers, e-mail addresses, links or unsupported claims.';

export const PARTS: Record<string, Part[]> = {
  CONTACTS: [
    { kind: 'strings', key: 'email_domains', label: 'Veda Spaces business e-mail domains', item: 'Domain', max: 80,
      hint: 'Every contact e-mail must use one of these (for example, a company domain). Personal mailboxes are refused.' },
    { kind: 'list', key: 'contacts', label: 'Business contacts', item: 'Contact', active: true, reorder: true, fields: [
      CODE,
      { name: 'kind', label: 'Contact type', kind: 'select', options: (v) => v.contact_kinds,
        hint: 'QUOTATION: chosen per quotation. SUPPORT and SERVICE: shown for help and after handover.' },
      { name: 'display_name', label: 'Display name', kind: 'text', max: 80, hint: 'A desk or role name, or a staff name the person agreed to publish.' },
      { name: 'role', label: 'Role or title', kind: 'text', max: 80 },
      { name: 'phone', label: 'Business phone', kind: 'text', optional: true, max: 20 },
      { name: 'email', label: 'Business e-mail', kind: 'text', optional: true, max: 120 },
      { name: 'hours', label: 'Support hours', kind: 'text', optional: true, max: 80 },
      { name: 'channel_note', label: 'How this channel is used', kind: 'textarea', optional: true, max: 600, hint: 'No response-time promise.' },
      { name: 'business_channel_approved', label: 'This is a Veda Spaces business channel approved for publication', kind: 'checkbox' },
    ] },
    { kind: 'scalar', key: 'support_escalation', label: 'Escalation route', max: 600, hint: COPY_HINT },
  ],
  INCLUSIONS: [{ kind: 'list', key: 'project_inclusions', label: 'Project inclusions', item: 'Inclusion', active: true, reorder: true, fields: [CODE, TEXT] }],
  RESPONSIBILITIES: [{ kind: 'list', key: 'client_responsibilities', label: 'Customer responsibilities', item: 'Responsibility', active: true, reorder: true, fields: [
    CODE, cat((v) => v.responsibility_categories), TEXT,
    { name: 'default_status', label: 'Default state', kind: 'select', options: (v) => v.responsibility_statuses,
      hint: 'What a quotation shows until staff set this item for the customer.' },
  ] }],
  SITE_READINESS: [{ kind: 'list', key: 'site_readiness', label: 'Site-readiness requirements', item: 'Requirement', active: true, reorder: true, fields: [
    CODE, cat((v) => v.readiness_categories), TEXT,
  ] }],
  SITE_WORK: [{ kind: 'object', key: 'site_dependent_work', label: 'Site-dependent work policy', parts: [
    { name: 'intro', label: 'Why some work depends on the site', kind: 'textarea', max: 600 },
    { name: 'approval_rule', label: 'How such work is approved', kind: 'textarea', max: 600,
      hint: 'A change is agreed with the customer as a variation first; this page never sets a price.' },
    { kind: 'list', key: 'categories', label: 'Categories', item: 'Category', active: true, reorder: true, fields: [
      CODE, cat((v) => v.site_work_categories), TEXT,
    ] },
  ] }],
  WARRANTY: [{ kind: 'scalar', key: 'manufacturer_warranty_note', label: 'Manufacturer-warranty note', max: 600,
    hint: "The manufacturer's warranty only. Veda Spaces' own service and workmanship commitments are contract terms (owner decision OI-MTQ-09) and are not edited here." }],
  EXCLUSIONS: [{ kind: 'list', key: 'warranty_exclusions', label: 'Warranty exclusions', item: 'Exclusion', active: true, reorder: true, fields: [CODE, TEXT] }],
  SERVICE: [{ kind: 'object', key: 'service_guidance', label: 'How to request service', parts: [
    { name: 'contact_code', label: 'Service contact', kind: 'select', optional: true,
      options: (_v, _d, ctx) => ((ctx.contacts as Array<{ code: string; kind: string }> | undefined) ?? [])
        .filter((c) => c.kind === 'SUPPORT' || c.kind === 'SERVICE').map((c) => c.code),
      hint: 'A SUPPORT or SERVICE contact of this version (Contact and support section).' },
    { kind: 'strings', key: 'what_to_provide', label: 'What the customer should tell us', item: 'Item', max: 600 },
    { name: 'reference_process', label: 'What happens after a request', kind: 'textarea', optional: true, max: 600 },
    { name: 'escalation', label: 'Escalation', kind: 'textarea', optional: true, max: 600 },
  ] }],
  HANDOVER: [{ kind: 'list', key: 'handover', label: 'Handover expectations', item: 'Item', active: true, reorder: true, fields: [
    CODE, cat((v) => v.handover_categories), TEXT,
  ] }],
  CARE: [{ kind: 'list', key: 'care', label: 'Care guidance', item: 'Item', active: true, reorder: true, fields: [
    CODE, cat((v) => v.care_categories), TEXT,
  ] }],
  NEXT_STEPS: [{ kind: 'list', key: 'next_steps', label: 'Stages after approval', item: 'Stage', active: true, reorder: true, fields: [
    CODE,
    { name: 'stage', label: 'Stage', kind: 'select', options: (v) => v.stages, hint: 'Stages follow the fixed order of the project lifecycle.' },
    { name: 'label', label: 'Customer-facing name', kind: 'text', max: 80 },
    TEXT,
    { name: 'duration', label: 'Approved duration (optional)', kind: 'text', optional: true, max: 80,
      hint: 'Only a duration the owner approved; leave empty and none is shown.' },
  ] }],
  PAYMENT_SAFETY: [{ kind: 'scalar', key: 'payment_safety', label: 'Payment-safety wording', max: 600,
    hint: 'How customers recognise legitimate Veda Spaces payment instructions. Never account numbers, IFSC, UPI IDs, QR codes, card details or links: they are refused.' }],
};

/** An empty entry of a list (every field present, so the editor shows it). */
export function blankRow(def: ListDef, v: Vocabulary | null, draft: Record<string, unknown>, ctx: Record<string, unknown>): Record<string, unknown> {
  const row: Record<string, unknown> = {};
  for (const f of def.fields) {
    if (f.kind === 'checkbox') row[f.name] = false;
    else if (f.name === 'default_status') row[f.name] = 'TO_BE_CONFIRMED';
    else if (f.kind === 'select' && !f.optional && v) row[f.name] = f.options?.(v, draft, ctx)[0] ?? '';
    else row[f.name] = f.optional ? null : '';
  }
  return row;
}

export const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x ?? null)) as T;
