import { css, html, nothing, type TemplateResult } from 'lit';
import type { ApiProblem } from '../../core/api/problem.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatAbsolute, humanize } from '../../core/format/format.js';
import { shared, tableStyles } from '../../design-system/styles.js';
import { previewPage, staffProposal, type Activity, type Grant, type Preview, type StaffRequest, type VariationView } from './api.js';
import { tableLikeStyles, variationTable } from './proposal-view.js';

const KINDS = ['PRIMARY_CUSTOMER', 'CO_OWNER', 'FAMILY_MEMBER', 'OTHER'];

/**
 * <vs-proposal-staff>: the staff side of one quotation version's customer proposal (CQX). Share a secure link (shown
 * once: it is stored only as a digest), rotate or revoke it, see whether it was opened, and preview exactly what the
 * customer sees. Later CQX steps add customer requests and acceptance evidence here.
 */
export class VsProposalStaff extends SessionElement {
  static override properties = {
    quotationId: { attribute: false }, quotationStatus: { attribute: false }, grants: { state: true }, preview: { state: true },
    issued: { state: true }, problem: { state: true }, busy: { state: true }, activity: { state: true }, chain: { state: true }, variation: { state: true },
  };
  declare chain: { id: string; label: string; status: string }[];
  declare variation: VariationView | null;
  declare activity: Activity | null;
  declare quotationId: string;
  declare quotationStatus: string;
  declare grants: Grant[];
  declare preview: Preview | null;
  declare issued: Grant | null;
  declare problem: ApiProblem | null;
  declare busy: boolean;

  static override styles = [...shared, tableStyles, tableLikeStyles, css`
    :host { display: block; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; }
    button, select, input { min-height: 44px; }
    .once { border: 1px solid var(--vs-success); border-left-width: 3px; border-radius: 8px; padding: 12px 16px; background: var(--vs-surface); overflow-wrap: anywhere; }
    .preview { border: 1px solid var(--vs-line); border-radius: 8px; background: var(--vs-paper); }
    .msg { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; }
  `];

  constructor() {
    super();
    this.quotationId = ''; this.quotationStatus = ''; this.grants = []; this.preview = null; this.issued = null;
    this.problem = null; this.busy = false; this.activity = null; this.chain = []; this.variation = null;
  }

  override updated(changed: Map<string, unknown>) {
    if (changed.has('quotationId') && this.quotationId) void this.load();
  }

  protected async act(fn: () => Promise<unknown>) {
    this.problem = null;
    this.busy = true;
    try { await fn(); await this.load(); } catch (e) { this.problem = e as ApiProblem; } finally { this.busy = false; }
  }

  protected async load() {
    try {
      this.grants = this.can('proposal.share') ? (await staffProposal.grants(this.quotationId)).data : [];
      this.preview = this.can('proposal.preview') ? (await staffProposal.preview(this.quotationId)).data : null;
      this.variation = this.preview?.proposal.kind === 'VARIATION' ? (await staffProposal.variationPreview(this.quotationId)).data : null;
      await this.loadMore();
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  /** What the customer did on this version (choices, and later requests and acknowledgements). */
  protected async loadMore(): Promise<void> {
    this.activity = this.can('proposal.request.review') ? (await staffProposal.activity(this.quotationId)).data : null;
    this.chain = this.activity?.requests.length && this.can('quotation.read') ? (await staffProposal.chain(this.quotationId)).data.versions : [];
  }

  private share(e: Event) {
    e.preventDefault();
    const f = new FormData(e.target as HTMLFormElement);
    void this.act(async () => {
      this.issued = (await staffProposal.share(this.quotationId, {
        recipient_kind: String(f.get('kind')), recipient_label: (f.get('label') as string) || null, expires_in_days: Number(f.get('days')),
      })).data;
    });
  }

  override render() {
    const shareable = ['ISSUED', 'ACCEPTED'].includes(this.quotationStatus);
    return html`<div class="stack">
      ${this.problem ? html`<vs-problem-banner .problem=${this.problem}></vs-problem-banner>` : nothing}
      ${this.can('proposal.share') ? this.sharing(shareable) : nothing}
      ${this.more()}
      ${this.variation ? html`${this.variation.issuable ? nothing : html`<vs-banner kind="warning">Staff preview only: this variation cannot be issued yet (see the quotation's blockers, e.g. the variation policy OI-MTQ-13).</vs-banner>`}
        <div class="preview">${variationTable(this.variation)}</div>` : nothing}
      ${this.preview ? html`<section class="stack" aria-labelledby="pv"><h3 id="pv" class="title">What the customer sees</h3>
        ${this.preview.frozen ? nothing : html`<vs-banner kind="warning">${this.preview.watermark}</vs-banner>`}
        <div class="preview"><vs-proposal-view preview .page=${previewPage(this.preview)}></vs-proposal-view></div></section>` : nothing}
    </div>`;
  }

  private answer(e: Event, r: StaffRequest) {
    e.preventDefault();
    const f = new FormData(e.target as HTMLFormElement);
    const status = String(f.get('status'));
    const response = (f.get('response') as string) || null;
    const target = f.get('target') as string | null;
    void this.act(() => (status === 'LINK' && target ? staffProposal.link(r, target, response) : staffProposal.respond(r, status, response)));
  }

  private requestsTable(requests: StaffRequest[]) {
    const statuses = ['UNDER_REVIEW', 'NEEDS_CLARIFICATION', 'DECLINED', 'RESOLVED'];
    return html`<section class="card stack" aria-labelledby="creq"><h3 id="creq" class="title">Customer questions and change requests</h3>
      ${requests.length ? requests.map((r) => html`<article class="stack card" aria-label=${`Request from ${humanize(r.recipient_kind ?? '')}`}>
        <div class="row"><span class="chip">${humanize(r.category)}</span><span class="chip">${humanize(r.status)}</span>
          <span class="small muted">v${r.version_no}${r.variation_no ? ` · variation ${r.variation_no}` : ''} · ${humanize(r.recipient_kind ?? '')} · ${formatAbsolute(r.sent_on)}</span></div>
        ${r.room || r.line_ref ? html`<div class="small">${r.room ?? ''}${r.line_ref ? ` · line ${r.line_ref}` : ''}${r.requested_quantity ? ` · quantity ${r.requested_quantity}` : ''}</div>` : nothing}
        <p class="msg">${r.message}</p>
        ${r.response ? html`<p class="small">Answer shown to the customer: ${r.response}</p>` : nothing}
        ${r.resulting_label ? html`<p class="small">Answered by ${r.resulting_label}</p>` : nothing}
        ${['DECLINED', 'RESOLVED'].includes(r.status) ? nothing : html`<form class="actions" @submit=${(e: Event) => this.answer(e, r)}>
          <label class="field"><span class="label">Status</span><select name="status">
            ${statuses.map((st) => html`<option value=${st}>${humanize(st)}</option>`)}${this.chain.length ? html`<option value="LINK">Answered by a revision</option>` : nothing}</select></label>
          ${this.chain.length ? html`<label class="field"><span class="label">Revision</span><select name="target"><option value="">—</option>
            ${this.chain.map((v) => html`<option value=${v.id}>${v.label} (${humanize(v.status)})</option>`)}</select></label>` : nothing}
          <label class="field"><span class="label">Answer (the customer sees it)</span><input name="response" maxlength="2000"></label>
          <button class="btn" ?disabled=${this.busy}>Save</button></form>`}
      </article>`) : html`<p class="muted">No questions or change requests yet.</p>`}
      <p class="small muted">Customer text is never added to scope. Agree a change by revising the scope and pricing as usual, then link the revised version or variation here.</p>
    </section>`;
  }

  protected more(): TemplateResult | typeof nothing {
    const a = this.activity;
    if (!a) return nothing;
    return html`${this.requestsTable(a.requests)}<section class="card stack" aria-labelledby="choices"><h3 id="choices" class="title">Customer choices on optional items</h3>
      ${a.selections.length ? html`<div class="table-wrap"><table><thead><tr><th>Item</th><th>Choice</th><th>Changes</th><th>Last change</th></tr></thead>
        <tbody>${a.selections.map((x) => html`<tr><td>${x.description ?? x.line_ref}</td><td><span class="chip">${humanize(x.state)}</span></td>
          <td>${x.change_no}</td><td>${formatAbsolute(x.changed_on)}</td></tr>`)}</tbody></table></div>
        <p class="small muted">A choice is a request: it changes nothing until a revised quotation (or the customer's acceptance) includes it.</p>`
        : html`<p class="muted">No choices yet.</p>`}</section>`;
  }

  private sharing(shareable: boolean) {
    const copy = (text: string) => navigator.clipboard?.writeText(text);
    return html`<section class="card stack" aria-labelledby="share"><h3 id="share" class="title">Secure links</h3>
      ${this.issued?.link ? html`<div class="once" role="status"><strong>Link created. Copy it now: it is shown only once.</strong>
        <div class="mono">${this.issued.link}</div><div class="actions"><button class="btn small" @click=${() => copy(this.issued?.link ?? '')}>Copy link</button>
        <button class="btn small ghost" @click=${() => { this.issued = null; }}>Done</button></div>
        <p class="small muted">Send it to the customer yourself (no message is sent by the workspace). Anyone holding the link can open the proposal until it expires or is revoked.</p></div>` : nothing}
      ${shareable ? html`<form class="actions" @submit=${(e: Event) => this.share(e)}>
          <label class="field"><span class="label">For</span><select name="kind">${KINDS.map((k) => html`<option value=${k}>${humanize(k)}</option>`)}</select></label>
          <label class="field"><span class="label">Note (staff only)</span><input name="label" maxlength="80"></label>
          <label class="field"><span class="label">Expires in (days)</span><input name="days" type="number" min="1" max="30" required value="14"></label>
          <button class="btn primary" ?disabled=${this.busy}>Create link</button></form>`
        : html`<p class="muted">Only an issued quotation can be shared with a customer.</p>`}
      ${this.grants.length ? html`<div class="table-wrap"><table><thead><tr><th>For</th><th>Version</th><th>Status</th><th>Expires</th><th>Opened</th><th><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>${this.grants.map((g) => html`<tr><td>${humanize(g.recipient_kind)}${g.recipient_label ? html`<br><span class="small muted">${g.recipient_label}</span>` : nothing}</td>
          <td>v${g.version_no}</td><td><span class="chip">${humanize(g.status)}</span>${g.revoke_reason_code ? html`<br><span class="small">${humanize(g.revoke_reason_code)}</span>` : nothing}</td>
          <td>${formatAbsolute(g.expires_on)}</td><td>${g.view_count ? html`${g.view_count}× · last ${formatAbsolute(g.last_viewed_on)}` : 'Not yet'}</td>
          <td>${['CREATED', 'ACTIVE'].includes(g.status) ? html`<div class="actions">
            <button class="btn small" ?disabled=${this.busy} aria-label="Replace the link for ${humanize(g.recipient_kind)}" @click=${() => this.act(async () => { this.issued = (await staffProposal.rotate(g)).data; })}>New link</button>
            ${this.can('proposal.access.revoke') ? html`<button class="btn small ghost" ?disabled=${this.busy} aria-label="Revoke the link for ${humanize(g.recipient_kind)}" @click=${() => this.act(() => staffProposal.revoke(g))}>Revoke</button>` : nothing}</div>` : nothing}</td></tr>`)}
        </tbody></table></div>` : nothing}</section>`;
  }
}

customElements.define('vs-proposal-staff', VsProposalStaff);
