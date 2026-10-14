import { LitElement, css, html, nothing } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { shared } from '../../design-system/styles.js';
import { forgetToken, newKey, proposalApi, takeToken, type Page } from './api.js';
import './proposal-view.js';

type Load = 'loading' | 'ready' | 'refused' | 'offline';

/** Safe, customer-facing words for every refusal; the server's own message is shown when it is one of these codes. */
const REFUSALS: Record<string, string> = {
  PROPOSAL_LINK_INVALID: 'This link is not valid. Please ask Veda Spaces for a new one.',
  PROPOSAL_LINK_REVOKED: 'This link is no longer active. Please ask Veda Spaces for a new one.',
  PROPOSAL_LINK_EXPIRED: 'This link has expired. Please ask Veda Spaces for a new one.',
  PROPOSAL_SUPERSEDED: 'A newer version of this proposal has been shared with you. Please use the latest link from Veda Spaces.',
  SNAPSHOT_INTEGRITY_FAILED: 'This proposal cannot be shown right now. Veda Spaces has been notified; please contact your Veda Spaces representative.',
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
    announcement: { state: true }, busy: { state: true }, errors: { state: true },
  };
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
  }

  /** Run one customer action, then reload the page model (the server is the only source of totals and states). */
  private async act(fn: () => Promise<unknown>, done: string) {
    this.busy = true;
    this.errors = [];
    this.announcement = 'Saving…';
    try {
      await fn();
      await this.refresh();
      this.announcement = done;
    } catch (e) {
      const p = e as ApiProblem;
      if (['PROPOSAL_LINK_REVOKED', 'PROPOSAL_LINK_EXPIRED', 'PROPOSAL_LINK_INVALID', 'PROPOSAL_SUPERSEDED'].includes(p.code)) {
        this.refuse(p);
        return;
      }
      const fields = (p.errors ?? []).map((er) => ({ field: er.field, message: er.message ?? 'Please check this.' }));
      this.errors = fields.length ? fields : [{ field: '', message: p.detail || 'Something went wrong. Please try again.' }];
      this.announcement = 'Not saved.';
    } finally {
      this.busy = false;
    }
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
      this.askKey = null;
      form.reset();
    }, 'Your message was sent to Veda Spaces.');
  }

  private onSelect(e: CustomEvent<{ line_ref: string; state: string; description: string }>) {
    const { line_ref, state, description } = e.detail;
    const words = { SELECTED: 'added to your choices', DESELECTED: 'marked not for you', REQUESTED_FOR_DISCUSSION: 'marked for discussion' }[state] ?? 'saved';
    void this.act(() => proposalApi(this.token ?? '').select(line_ref, state), `${description} ${words}.`);
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
    if (p.status === 0 || p.code === 'NETWORK_ERROR') {
      this.load = 'offline';
      this.heading = 'You seem to be offline';
      this.message = 'The proposal could not be loaded. Check your connection and try again.';
      return;
    }
    if (['PROPOSAL_LINK_REVOKED', 'PROPOSAL_LINK_EXPIRED', 'PROPOSAL_LINK_INVALID', 'PROPOSAL_SUPERSEDED'].includes(p.code)) forgetToken();
    this.load = 'refused';
    this.heading = p.code === 'PROPOSAL_SUPERSEDED' ? 'A newer proposal is available' : p.code === 'SNAPSHOT_INTEGRITY_FAILED'
      ? 'This proposal cannot be shown' : 'This link cannot be opened';
    this.message = REFUSALS[p.code] ?? 'Something went wrong. Please try again, or contact Veda Spaces.';
  }

  override updated() {
    if (this.load !== 'ready') (this.renderRoot.querySelector('h1') as HTMLElement | null)?.focus();
  }

  override render() {
    if (this.load === 'ready' && this.page) {
      return html`<vs-proposal-view .page=${this.page} .announcement=${this.announcement} .busy=${this.busy} .errors=${this.errors}
        @proposal-select=${this.onSelect} @proposal-ask=${this.onAsk}></vs-proposal-view>`;
    }
    return html`<div class="center"><div class="brandname">Veda Spaces</div>
      ${this.load === 'loading' ? html`<h1 tabindex="-1">Opening your proposal…</h1><vs-skeleton rows="6"></vs-skeleton>` : html`
        <h1 tabindex="-1">${this.heading}</h1><p role=${this.load === 'offline' ? 'status' : 'alert'}>${this.message}</p>
        ${this.load === 'offline' ? html`<div><button class="btn primary" @click=${() => { this.load = 'loading'; void this.refresh(); }}>Try again</button></div>` : nothing}`}
    </div>`;
  }
}

customElements.define('vs-proposal-page', VsProposalPage);
