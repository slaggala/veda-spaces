import type { LeadStatus } from '../../core/api/types.js';

/** Lead state machine input rules (04 §3). The server's allowed_transitions decides WHICH moves exist. */
export const OPEN_STATUSES: readonly LeadStatus[] = ['NEW', 'CONTACTED', 'SITE_VISIT', 'QUOTATION_SENT', 'NEGOTIATION'];

export type TransitionKind = 'forward' | 'back' | 'won' | 'lost' | 'reopen';

export interface TransitionRules {
  kind: TransitionKind;
  permission: 'lead.status.change' | 'lead.reopen';
  commentRequired: boolean;
  lostReasonRequired: boolean;
  wonOnAllowed: boolean;
  cancelsPlanned: boolean;
}

export interface TransitionInput {
  comment?: string;
  lost_reason_code?: string;
  lost_reason_note?: string;
  won_on?: string;
}

const isOpen = (s: LeadStatus) => OPEN_STATUSES.includes(s);

export function transitionRules(from: LeadStatus, to: LeadStatus): TransitionRules | null {
  if (from === to) return null;
  if (from === 'LOST') return to === 'CONTACTED' ? rule('reopen', 'lead.reopen', true) : null;
  if (from === 'WON') return to === 'NEGOTIATION' ? rule('reopen', 'lead.reopen', true) : null;
  if (!isOpen(from)) return null;
  if (to === 'LOST') return { ...rule('lost', 'lead.status.change', false), lostReasonRequired: true, cancelsPlanned: true };
  if (to === 'WON') {
    const late = from === 'NEGOTIATION' || from === 'QUOTATION_SENT';
    return { ...rule('won', 'lead.status.change', !late), wonOnAllowed: true, cancelsPlanned: true };
  }
  const fi = OPEN_STATUSES.indexOf(from);
  const ti = OPEN_STATUSES.indexOf(to);
  if (ti > fi) return rule('forward', 'lead.status.change', false);
  if (ti === fi - 1) return rule('back', 'lead.status.change', true);
  return null;
}

function rule(kind: TransitionKind, permission: TransitionRules['permission'], commentRequired: boolean): TransitionRules {
  return { kind, permission, commentRequired, lostReasonRequired: false, wonOnAllowed: false, cancelsPlanned: false };
}

/** Client-side mirror of the server's required-input codes: COMMENT_REQUIRED, LOST_REASON_REQUIRED. */
export function validateTransition(from: LeadStatus, to: LeadStatus, input: TransitionInput): Record<string, string> {
  const rules = transitionRules(from, to);
  const errors: Record<string, string> = {};
  if (!rules) {
    errors.to_status = 'This move is not allowed.';
    return errors;
  }
  if (rules.commentRequired && !input.comment?.trim()) errors.comment = 'Add a comment explaining this change.';
  if (rules.lostReasonRequired && !input.lost_reason_code) errors.lost_reason_code = 'Choose a lost reason.';
  if (rules.lostReasonRequired && input.lost_reason_code === 'OTHER' && !input.lost_reason_note?.trim()) {
    errors.lost_reason_note = 'Describe the reason.';
  }
  return errors;
}

/** Body for POST /leads/{id}/status (08 §8.6). */
export function transitionBody(to: LeadStatus, input: TransitionInput): Record<string, string> {
  const body: Record<string, string> = { to_status: to };
  if (input.comment?.trim()) body.comment = input.comment.trim();
  if (to === 'LOST') {
    if (input.lost_reason_code) body.lost_reason_code = input.lost_reason_code;
    if (input.lost_reason_note?.trim()) body.lost_reason_note = input.lost_reason_note.trim();
  }
  if (to === 'WON' && input.won_on) body.won_on = input.won_on;
  return body;
}

/** The "primary" next step shown as the main button: the next forward open status (or WON). */
export function primaryTransition(from: LeadStatus, allowed: readonly LeadStatus[]): LeadStatus | null {
  if (!isOpen(from)) return null;
  const order: LeadStatus[] = [...OPEN_STATUSES, 'WON'];
  const next = order[order.indexOf(from) + 1];
  return next && allowed.includes(next) ? next : null;
}
