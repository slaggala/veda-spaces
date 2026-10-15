import { LitElement, css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { shared } from '../../design-system/styles.js';
import { forgetToken, newKey, proposalApi, takeToken, type Comparison, type Page } from './api.js';
import './proposal-view.js';

type Load = 'loading' | 'ready' | 'refused' | 'offline';

/** Safe, customer-facing words for every refusal; the server's own message is shown when it is one of these codes. */
const REFUSALS: Record<string, string> = {
  PROPOSAL_LINK_INVALID: 'This link is not valid. Please ask Veda Spaces for a new one.',
  PROPOSAL_LINK_REVOKED: 'This link is no longer active. Please ask Veda Spaces for a new one.',
  PROPOSAL_LINK_EXPIRED: 'This link has expired. Please ask Veda Spaces for a new one.',
  PROPOSAL_SUPERSEDED: 'A newer version of this proposal has been shared with you. Please use the latest link from Veda Spaces.',
  SNAPSHOT_INTEGRITY_FAILED: 'This proposal cannot be shown right now. Please contact your Veda Spaces representative.',
  RATE_LIMITED: 'Too many requests from this connection. Please wait a minute and try again.',
  NOT_FOUND: 'Customer proposals are not available here.',
};

/**
 * /proposal — the customer's proposal, opened by its secure link (CQX). Public route: no sign-in, no workspace shell.
 * The token is taken from the URL fragment and scrubbed at once (api.takeToken); every request sends it in a header.
 */
export class VsProposalPage extends LitElement {
  static override properties = {
    load: { state: true }, page: { state: true }, message: { state: true }, heading: { state: true },
    announcement: { state: true }, busy: { state: true }, errors: { state: true }, comparison: { state: true },
    retryable: { state: true },
  };
  declare retryable: boolean;
  /** The last action, kept while it may be retried (a transient failure: offline, server busy). */
  private lastAction: (() => void) | null = null;
  declare comparison: Comparison | null;
  declare announcement: string;
  declare busy: boolean;
  declare errors: { field: string; message: string }[];
  declare load: Load;
  declare page: Page | null;
  declare message: string;
  declare heading: string;
  private token: string | null = null;

  static override styles = [...shared, css`
    :host { display: block; min-height: 100vh; background: var(--vs-paper); }
    .center { max-width: 560px; margin: 0 auto; padding: var(--vs-space-7) var(--vs-space-4); display: flex; flex-direction: column; gap: var(--vs-space-4); }
    .brandname { font-family: var(--vs-font-serif); font-size: 26px; letter-spacing: .08em; color: var(--vs-copper-text); }
    h1 { font-family: var(--vs-font-serif); font-weight: 500; font-size: 30px; line-height: 36px; margin: 0; }
    button { min-height: var(--vs-target); }
    button:focus-visible, h1:focus-visible { outline: 2px solid var(--vs-focus-ring); outline-offset: 2px; }
  `];

  constructor() {
    super();
    this.load = 'loading';
    this.page = null;
    this.message = '';
    this.heading = '';
    this.announcement = '';
    this.busy = false;
    this.errors = [];
    this.comparison = null;
    this.retryable = false;
  }

  private onAck(e: CustomEvent<{ section: string; sha256: string; title: string }>) {
    const { section, sha256, title } = e.detail;
    void this.act(() => proposalApi(this.token ?? '').acknowledge(section, sha256), `${title}: acknowledged.`, undefined,
      () => `ack-${section}`);
  }

  /**
   * One key per decision attempt and per decision type (an Accept never reuses a Decline's key). The key survives only
   * a transient failure (a lost response is retried with it and returns the recorded decision); any definitive answer
   * retires it (N2).
   */
  private decideKeys = new Map<string, string>();

  private onDecide(e: CustomEvent<Record<string, unknown>>) {
    const decision = String(e.detail.decision);
    const key = this.decideKeys.get(decision) ?? newKey();
    this.decideKeys.set(decision, key);
    const accepted = decision === 'ACCEPTED';
    void this.act(async () => { await proposalApi(this.token ?? '').decide(e.detail, key); },
      accepted ? 'Your acceptance was recorded.' : 'Your decision was recorded.', () => this.decideKeys.delete(decision),
      (field) => (field === 'confirm' ? 'confirm' : ''));
  }

  private onCompare() {
    void this.act(async () => { this.comparison = (await proposalApi(this.token ?? '').compare()).data.comparison; }, 'Changes shown.');
  }

  /**
   * Run one customer action, then reload the page model (the server is the only source of totals and states).
   * `definitive` runs once the server has answered (success or refusal) — never after a transient failure, so a retry
   * of a lost request carries the same idempotency key. `field` maps a refused field of the request to the control the
   * error summary links to ('' for an error about the request as a whole). A retry keeps the error and its Try again
   * button on screen until it has an answer, so focus never leaves that context while it runs.
   */
  private async act(fn: () => Promise<unknown>, done: string, definitive?: () => void,
    field: (name: string) => string = () => '', retrying = false) {
    this.busy = true;
    if (!retrying) {
      this.errors = [];
      this.retryable = false;
    }
    this.announcement = retrying ? 'Trying again…' : 'Saving…';
    try {
      await fn();
      definitive?.();
      this.lastAction = null;
      await this.refresh();
      this.errors = [];
      this.retryable = false;
      this.announcement = done;
    } catch (e) {
      const p = e as ApiProblem;
      if (['PROPOSAL_LINK_REVOKED', 'PROPOSAL_LINK_EXPIRED', 'PROPOSAL_LINK_INVALID', 'PROPOSAL_SUPERSEDED'].includes(p.code)) {
        definitive?.();
        this.refuse(p);
        return;
      }
      if (transient(p)) {
        this.lastAction = () => { void this.act(fn, done, definitive, field, true); };
        this.retryable = true;
        this.errors = [{ field: '', message: p.status === 429
          ? 'Too many requests from this connection. Nothing was saved; please wait a minute and try again.'
          : p.status >= 500 ? 'Veda Spaces could not save this just now. Nothing was saved; please try again.'
            : 'You seem to be offline. Nothing was saved; check your connection and try again.' }];
        this.announcement = 'Not saved. You can try again.';
        return;
      }
      definitive?.();
      this.lastAction = null;
      this.retryable = false;
      const fields = (p.errors ?? []).map((er) => ({ field: field(er.field ?? ''), message: er.message ?? 'Please check this.' }));
      this.errors = fields.length ? fields : [{ field: '', message: p.detail || 'Something went wrong. Please try again.' }];
      this.announcement = 'Not saved.';
    } finally {
      this.busy = false;
    }
  }

  private onRetry() {
    if (!this.busy) this.lastAction?.();
  }

  /** One key per form submission: a retry after a slow network sends the same request, never a duplicate. */
  private askKey: string | null = null;

  private onAsk(e: CustomEvent<{ body: Record<string, unknown>; form: HTMLFormElement }>) {
    const { body, form } = e.detail;
    if (String(body.message ?? '').trim().length < 3) {
      this.errors = [{ field: 'message', message: 'Please write your message (at least 3 characters).' }];
      return;
    }
    this.askKey ??= newKey();
    const key = this.askKey;
    void this.act(async () => {
      await proposalApi(this.token ?? '').ask(body, key);
      form.reset();
    }, 'Your message was sent to Veda Spaces.', () => { this.askKey = null; },
    (f) => ({ message: 'message', line_ref: 'line', room_ref: 'room', requested_quantity: 'quantity', category: 'category' })[f] ?? '');
  }

  private onSelect(e: CustomEvent<{ line_ref: string; state: string; description: string }>) {
    const { line_ref, state, description } = e.detail;
    const words = { SELECTED: 'added to your choices', DESELECTED: 'marked not for you', REQUESTED_FOR_DISCUSSION: 'marked for discussion' }[state] ?? 'saved';
    void this.act(() => proposalApi(this.token ?? '').select(line_ref, state), `${description} ${words}.`, undefined,
      () => `opt-${line_ref}`);
  }

  override connectedCallback() {
    super.connectedCallback();
    document.title = 'Your proposal · Veda Spaces';
    this.token = takeToken();
    void this.refresh();
  }

  /** Reload the page model (after every customer action: the server is the only source of totals and states). */
  async refresh() {
    if (!this.token) {
      this.refuse({ code: 'PROPOSAL_LINK_INVALID' } as ApiProblem);
      return;
    }
    try {
      this.page = (await proposalApi(this.token).view()).data;
      this.load = 'ready';
    } catch (e) {
      this.refuse(e as ApiProblem);
    }
  }

  private refuse(p: ApiProblem) {
    if (transient(p)) {
      this.load = 'offline';
      this.heading = p.status === 429 ? 'Please wait a moment' : p.status >= 500 ? 'Something went wrong on our side' : 'You seem to be offline';
      this.message = p.status === 429 ? 'Too many requests from this connection. Please wait a minute, then try again.'
        : p.status >= 500 ? 'The proposal could not be loaded just now. Please try again.'
          : 'The proposal could not be loaded. Check your connection and try again.';
      return;
    }
    if (['PROPOSAL_LINK_REVOKED', 'PROPOSAL_LINK_EXPIRED', 'PROPOSAL_LINK_INVALID', 'PROPOSAL_SUPERSEDED'].includes(p.code)) forgetToken();
    this.load = 'refused';
    this.heading = p.code === 'PROPOSAL_SUPERSEDED' ? 'A newer proposal is available' : p.code === 'SNAPSHOT_INTEGRITY_FAILED'
      ? 'This proposal cannot be shown' : 'This link cannot be opened';
    this.message = REFUSALS[p.code] ?? 'Something went wrong. Please try again, or contact Veda Spaces.';
  }

  /**
   * Page entry: whenever the page changes what it shows as a whole (opening, a refusal, the proposal arriving after a
   * slow load or a retry), focus moves to that page's heading, so a keyboard or screen-reader user starts at the top
   * with its name. A refresh after a customer action keeps `load` at 'ready' and never moves focus here.
   */
  override updated(changed: Map<string, unknown>) {
    if (!changed.has('load') && !changed.has('heading')) return;
    if (this.load !== 'ready') {
      (this.renderRoot.querySelector('h1') as HTMLElement | null)?.focus();
      return;
    }
    if (changed.has('load') && changed.get('load') !== 'ready') {
      const view = this.renderRoot.querySelector('vs-proposal-view') as (HTMLElement & { focusEntry(): Promise<void> }) | null;
      void view?.focusEntry();
    }
  }

  override render() {
    if (this.load === 'ready' && this.page) {
      return html`<vs-proposal-view .page=${this.page} .announcement=${this.announcement} .busy=${this.busy} .errors=${this.errors}
        .retryable=${this.retryable} @proposal-retry=${this.onRetry}
        .comparison=${this.comparison} @proposal-select=${this.onSelect} @proposal-ask=${this.onAsk} @proposal-compare=${this.onCompare}
        @proposal-ack=${this.onAck} @proposal-decide=${this.onDecide}></vs-proposal-view>`;
    }
    return html`<div class="center"><div class="brandname">Veda Spaces</div>
      ${this.load === 'loading' ? html`<h1 tabindex="-1">Opening your proposal…</h1><vs-skeleton rows="6"></vs-skeleton>` : html`
        <h1 tabindex="-1">${this.heading}</h1><p role="alert">${this.message}${this.load === 'offline' ? ' A Try again button follows.' : ''}</p>
        ${this.load === 'offline' ? html`<div><button class="btn primary" @click=${() => { this.load = 'loading'; void this.refresh(); }}>Try again</button></div>` : nothing}`}
    </div>`;
  }
}

/** A failure worth retrying: no answer at all, the server busy (429) or failing (5xx). */
function transient(p: ApiProblem): boolean {
  return p.status === 0 || p.code === 'NETWORK_ERROR' || p.status === 429 || p.status >= 500;
}

customElements.define('vs-proposal-page', VsProposalPage);
