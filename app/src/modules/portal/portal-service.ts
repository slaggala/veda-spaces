import { LitElement, css, html, nothing } from 'lit';
import { newIdempotencyKey } from '../../core/api/client.js';
import { preparePhoto } from '../site/photos.js';
import { portalApi, transient, type PhotoUpload, type ServiceRequestView, type WarrantyView } from './api.js';
import './portal-image.js';
import { portalStyles, stateBadge, when } from './portal-ui.js';

const NEXT_WORDS = { YOU: 'Waiting for you', VEDA_SPACES: 'With Veda Spaces' } as const;
const STATE: Record<string, string> = { RESOLVED: 'ACTION_REQUIRED', INFORMATION_REQUESTED: 'ACTION_REQUIRED', CLOSED: 'COMPLETED',
  AWAITING_COMMERCIAL_AGREEMENT: 'INFORMATION', REPORTED: 'UPCOMING', TRIAGED: 'IN_PROGRESS', ASSESSED: 'IN_PROGRESS', IN_PROGRESS: 'IN_PROGRESS' };

async function base64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

/**
 * The customer's "Warranty & service" section (WSV): what their accepted quotation says about warranty (verbatim), the
 * status of any recorded coverage in plain words (never a green "covered" for the warranty as such), their service
 * requests and what happens next, and a mobile-first "Report a problem" form with photos. Photos are resized and
 * stripped of location data on the device, then uploaded the way the server asks; the server checks and scans each one
 * before anyone sees it. Every write uses a key, so a retry after a lost answer never sends anything twice.
 */
export class VsPortalService extends LitElement {
  static override properties = { view: { attribute: false }, propertyId: { attribute: false }, reporting: { state: true },
    sending: { state: true }, error: { state: true }, status: { state: true }, replying: { state: true } };
  declare view: WarrantyView;
  declare propertyId: string;
  declare reporting: string | null;
  declare sending: boolean;
  declare error: string;
  declare status: string;
  declare replying: string | null;
  private key = '';
  private photoKeys: string[] = [];

  static override styles = [...portalStyles, css`
    :host { display: block; }
    .grid2 { display: grid; grid-template-columns: 1fr; gap: var(--vs-space-3); }
    .photos { display: flex; flex-wrap: wrap; gap: var(--vs-space-2); }
    .photos vs-portal-image { width: 88px; }
    .msg { border-left: 3px solid var(--vs-line); padding-left: var(--vs-space-2); overflow-wrap: anywhere; }
    .msg.VEDA_SPACES { border-left-color: var(--vs-copper); }
    .request { border-top: 1px solid var(--vs-line); padding-top: var(--vs-space-3); display: flex; flex-direction: column; gap: var(--vs-space-2); }
    .request:first-of-type { border-top: 0; padding-top: 0; }
    .words { overflow-wrap: anywhere; white-space: pre-wrap; }
    input[type=file] { min-height: var(--vs-target); }
    select, input, textarea { min-height: var(--vs-target); }
    summary { cursor: pointer; min-height: var(--vs-target); display: flex; align-items: center; font-weight: 600; }
    summary:focus-visible { outline: 2px solid var(--vs-focus-ring); outline-offset: 2px; }
  `];

  constructor() {
    super();
    this.reporting = null;
    this.sending = false;
    this.error = '';
    this.status = '';
    this.replying = null;
  }

  private changed() {
    this.dispatchEvent(new CustomEvent('service-changed', { bubbles: true, composed: true }));
  }

  private async start(projectId: string) {
    this.reporting = projectId;
    this.error = '';
    this.key = newIdempotencyKey();
    this.photoKeys = [];
    await this.updateComplete;
    this.renderRoot.querySelector<HTMLSelectElement>('select[name=category]')?.focus();
  }

  private async uploadPhotos(requestId: string, files: File[]): Promise<number> {
    let done = 0;
    for (const [i, file] of files.entries()) {
      this.status = `Uploading photo ${i + 1} of ${files.length}…`;
      const prepared = await preparePhoto(file);
      this.photoKeys[i] ??= newIdempotencyKey();
      const declared = (await portalApi.photoDeclare(this.propertyId, requestId, { mime_type: 'image/jpeg', byte_size: prepared.blob.size,
        sha256: prepared.sha256 }, this.photoKeys[i])).data;
      await this.send(requestId, declared.photo_id, declared.upload, prepared.blob);
      await portalApi.photoComplete(this.propertyId, requestId, declared.photo_id);
      done += 1;
    }
    return done;
  }

  private async send(requestId: string, photoId: string, upload: PhotoUpload, blob: Blob) {
    if (!upload.required) return;
    if (upload.method === 'POST' && upload.url) {
      const form = new FormData();
      for (const [k, v] of Object.entries(upload.fields ?? {})) form.append(k, v);
      form.append('file', blob); // the private bucket's pre-signed POST; the server's completion decides whether it arrived
      await fetch(upload.url, { method: 'POST', body: form, mode: 'no-cors', credentials: 'omit', referrerPolicy: 'no-referrer' });
      return;
    }
    await portalApi.photoContent(this.propertyId, requestId, photoId, await base64(blob));
  }

  private async submit(e: Event, projectId: string) {
    e.preventDefault();
    if (this.sending) return;
    const form = e.target as HTMLFormElement;
    const get = (n: string) => (form.elements.namedItem(n) as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null)?.value.trim() ?? '';
    const description = get('description');
    const chosen = [...((form.elements.namedItem('photos') as HTMLInputElement | null)?.files ?? [])];
    const files = chosen.slice(0, this.view.max_photos);
    if (description.length < 10) {
      this.error = 'Please describe the problem (at least 10 characters).';
      await this.updateComplete;
      this.renderRoot.querySelector<HTMLTextAreaElement>('textarea[name=description]')?.focus();
      return;
    }
    this.sending = true;
    this.error = '';
    try {
      const body: Record<string, unknown> = { project_id: projectId, category: get('category'), description };
      if (get('area')) body.area = get('area');
      if (get('noticed_on')) body.noticed_on = get('noticed_on');
      const r = (await portalApi.serviceSubmit(this.propertyId, body, this.key)).data.request;
      let photos = 0;
      try { photos = await this.uploadPhotos(r.id, files); } catch {
        this.status = '';
        this.error = `${r.reference} was received, but a photo could not be uploaded. You can add photos to it below.`;
      }
      this.reporting = null;
      this.status = `Thank you. ${r.reference} has been received${photos ? ` with ${photos} photo${photos === 1 ? '' : 's'}` : ''}; Veda Spaces will review it.`
        + (chosen.length > files.length ? ` Only the first ${files.length} photos were sent.` : '');
      this.changed();
    } catch (err) {
      const p = err as { status: number; code?: string; detail?: string };
      this.error = transient(p) ? 'We could not send your request. Check your connection and try again; it will not be sent twice.'
        : p.detail ?? 'Your request could not be sent. Please speak to your Veda Spaces contact.';
    } finally { this.sending = false; }
  }

  private async act(r: ServiceRequestView, action: 'information' | 'confirm' | 'reject' | 'withdraw', body: Record<string, unknown> = {}, done = '') {
    if (this.sending) return;
    this.sending = true;
    this.error = '';
    try {
      await portalApi.serviceAct(this.propertyId, r.id, action, body);
      this.replying = null;
      this.status = done;
      this.changed();
    } catch (err) {
      const p = err as { status: number; detail?: string };
      this.error = transient(p) ? 'We could not send that. Check your connection and try again.' : p.detail ?? 'That could not be done. Please speak to your Veda Spaces contact.';
    } finally { this.sending = false; }
  }

  private async reply(e: Event, r: ServiceRequestView, action: 'information' | 'reject') {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const text = (form.elements.namedItem('text') as HTMLTextAreaElement).value.trim();
    const files = [...((form.elements.namedItem('photos') as HTMLInputElement | null)?.files ?? [])];
    if (text.length < (action === 'reject' ? 10 : 3)) {
      this.error = action === 'reject' ? 'Please tell us what is still not right (at least 10 characters).' : 'Please write your answer.';
      return;
    }
    let photoProblem = '';
    if (files.length && r.can_add_photos) {
      this.sending = true;
      try { this.photoKeys = []; await this.uploadPhotos(r.id, files); } catch { photoProblem = 'A photo could not be uploaded; your answer was still sent.'; }
      this.sending = false;
    }
    await this.act(r, action, action === 'reject' ? { reason: text } : { text }, action === 'reject' ? 'Thank you. Veda Spaces will look at it again.' : 'Thank you for your answer.');
    if (photoProblem && !this.error) this.error = photoProblem; // kept visible after the answer is sent (review L4)
  }

  private warranty(p: WarrantyView['projects'][number]) {
    const w = p.warranty;
    if (w.state !== 'REGISTERED') return html`<p>${w.message}</p>`;
    return html`<div class="stack">
      <p>Handed over ${when(w.handed_over_on ?? '')}. ${stateBadge(w.status === 'ACTIVE' ? 'IN_PROGRESS' : 'INFORMATION', w.status_label ?? '')}</p>
      ${w.period_note ? html`<p class="small">${w.period_note}</p>` : nothing}
      ${(w.coverage ?? []).map((c) => html`<div class="item"><div class="step-head"><span class="strong">${c.label}</span>${stateBadge(c.status === 'ACTIVE' ? 'IN_PROGRESS' : 'INFORMATION', c.status_label)}</div>
        <span>${c.covers}</span>${c.ends_on ? html`<span class="small muted">${c.status === 'EXPIRED' ? 'Ended' : 'Until'} ${when(c.ends_on)}</span>` : nothing}</div>`)}
      ${(w.statements ?? []).length ? html`<details><summary>What your accepted quotation says</summary><ul class="bullets">${w.statements!.map((s) => html`<li><span class="strong">${s.kind}:</span> ${s.text} <span class="small muted">(${s.source})</span></li>`)}</ul></details>` : nothing}
      ${(w.exclusions ?? []).length ? html`<details><summary>What is not covered</summary><ul class="bullets">${w.exclusions!.map((x) => html`<li>${x}</li>`)}</ul></details>` : nothing}
      ${(w.manufacturer_notes ?? []).length ? html`<details><summary>Manufacturer warranties</summary>${w.manufacturer_notes!.map((x) => html`<p class="small">${x}</p>`)}</details>` : nothing}
      ${w.policy_url ? html`<p class="small"><a href=${w.policy_url} target="_blank" rel="noopener">Warranty, Service &amp; Customer Care Policy<span class="sr-only"> (opens in a new tab)</span></a></p>` : nothing}
    </div>`;
  }

  private request(r: ServiceRequestView) {
    const photoPath = (id: string) => `/properties/${encodeURIComponent(this.propertyId)}/service-requests/${encodeURIComponent(r.id)}/photos/${encodeURIComponent(id)}/content`;
    const evidencePath = (id: string) => `/properties/${encodeURIComponent(this.propertyId)}/service-requests/${encodeURIComponent(r.id)}/evidence/${encodeURIComponent(id)}/content`;
    const replying = this.replying === r.id;
    return html`<li class="request">
      <div class="step-head"><span class="strong">${r.reference}: ${r.category}</span>${stateBadge(STATE[r.status] ?? 'INFORMATION', r.status_label)}</div>
      ${r.next ? html`<span class="small muted">${NEXT_WORDS[r.next]}</span>` : nothing}
      <span class="words">${r.description}</span>
      <span class="small muted">${r.area ? `${r.area} · ` : ''}Reported ${when(r.reported_on)}</span>
      ${r.photos.length ? html`<div class="photos">${r.photos.map((ph, i) => ph.state === 'AVAILABLE'
        ? html`<vs-portal-image .path=${photoPath(ph.id)} .label=${`Your photo ${i + 1} of ${r.reference}`} .variant=${'thumb'}></vs-portal-image>`
        : html`<span class="small muted">${ph.state === 'CHECKING' ? 'Photo being checked' : 'Photo not available'}</span>`)}</div>` : nothing}
      ${r.messages.map((m) => html`<p class="msg ${m.from}"><span class="small muted">${m.label} · ${when(m.on)}</span><br>${m.text}</p>`)}
      ${r.coverage ? html`<p><span class="strong">${r.coverage.label}.</span> ${r.coverage.explanation}${r.coverage.chargeable_note ? html`<br><span class="small">${r.coverage.chargeable_note}</span>` : nothing}</p>` : nothing}
      ${r.visits.map((v) => html`<p class="small">${v.kind}: ${v.status === 'DONE' ? `done ${when(v.done_on ?? '')}` : `planned for ${when(v.planned_on)}`}${v.note ? ` · ${v.note}` : ''}</p>`)}
      ${r.resolution ? html`<p><span class="strong">What we did:</span> ${r.resolution.summary}</p>` : nothing}
      ${r.evidence.length ? html`<div class="photos">${r.evidence.map((ev) => html`<vs-portal-image .path=${evidencePath(ev.id)} .label=${ev.caption ?? 'Photo from Veda Spaces'} .variant=${'thumb'}></vs-portal-image>`)}</div>` : nothing}
      ${replying ? html`<form class="stack" novalidate @submit=${(e: Event) => this.reply(e, r, r.can_add_information ? 'information' : 'reject')}>
          <label class="field"><span class="label">${r.can_add_information ? 'Your answer (required)' : 'What is still not right? (required)'}</span>
            <textarea name="text" maxlength=${r.can_add_information ? 2000 : 1000} required></textarea></label>
          ${r.can_add_photos ? html`<label class="field"><span class="label">Add photos (optional)</span><input type="file" name="photos" accept="image/*" multiple /></label>` : nothing}
          <div class="row"><button class="btn primary" type="submit" ?disabled=${this.sending}>Send</button>
            <button class="btn ghost" type="button" @click=${() => { this.replying = null; this.error = ''; }}>Cancel</button></div></form>`
        : html`<div class="row">
          ${r.can_add_information ? html`<button class="btn primary" @click=${() => (this.replying = r.id)}>Reply<span class="sr-only"> to ${r.reference}</span></button>` : nothing}
          ${r.can_confirm ? html`<button class="btn primary" ?disabled=${this.sending} @click=${() => this.act(r, 'confirm', {}, `Thank you. ${r.reference} is closed.`)}>It is resolved<span class="sr-only">: ${r.reference}</span></button>` : nothing}
          ${r.can_reject ? html`<button class="btn" @click=${() => (this.replying = r.id)}>Still not right<span class="sr-only">: ${r.reference}</span></button>` : nothing}
          ${r.can_withdraw ? html`<button class="btn ghost" ?disabled=${this.sending} @click=${() => this.act(r, 'withdraw', {}, `${r.reference} has been withdrawn.`)}>Withdraw<span class="sr-only"> ${r.reference}</span></button>` : nothing}
        </div>`}
    </li>`;
  }

  private form(projectId: string) {
    return html`<form class="stack" novalidate @submit=${(e: Event) => this.submit(e, projectId)}>
      <label class="field"><span class="label">What kind of problem? (required)</span>
        <select name="category" required>${this.view.categories.map((c) => html`<option value=${c.code}>${c.label}</option>`)}</select></label>
      <label class="field"><span class="label">What have you noticed? (required)</span>
        <textarea name="description" minlength="10" maxlength="2000" required aria-describedby="service-hint"></textarea>
        <span class="hint small muted" id="service-hint">In your own words. Veda Spaces reviews every request and tells you here whether your warranty covers it.</span></label>
      <div class="grid2">
        <label class="field"><span class="label">Where is it? (optional)</span><input name="area" maxlength="120" autocomplete="off" /></label>
        <label class="field"><span class="label">When did you first notice it? (optional)</span><input name="noticed_on" type="date" max=${new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date())} /></label>
      </div>
      <label class="field"><span class="label">Photos (optional, up to ${this.view.max_photos})</span>
        <input type="file" name="photos" accept="image/*" multiple aria-describedby="photo-hint" />
        <span class="hint small muted" id="photo-hint">Photos are resized and their location data removed on your phone before they are sent.</span></label>
      <div class="row"><button class="btn primary" type="submit" ?disabled=${this.sending}>${this.sending ? 'Sending…' : 'Send request'}</button>
        <button class="btn ghost" type="button" @click=${() => { this.reporting = null; this.error = ''; }}>Cancel</button></div>
    </form>`;
  }

  override render() {
    const v = this.view;
    return html`<div class="stack">
      ${this.error ? html`<p class="notice" role="alert">${this.error}</p>` : nothing}
      <p class="small" role="status" aria-live="polite">${this.status}</p>
      ${v.projects.length ? v.projects.map((p) => html`<article class="card stack" aria-labelledby=${`warranty-${p.id}`}>
        <h3 id=${`warranty-${p.id}`}>Your warranty</h3>
        ${this.warranty(p)}
        <h3>Service requests</h3>
        ${p.requests.length ? html`<ul class="plain">${p.requests.map((r) => this.request(r))}</ul>` : html`<p class="small muted">No service requests yet.</p>`}
        ${p.can_report ? (this.reporting === p.id ? this.form(p.id)
          : html`<div><button class="btn" @click=${() => this.start(p.id)}>Report a problem</button></div>`) : nothing}
      </article>`) : html`<p class="card muted">Warranty and service appear here once your home is handed over.</p>`}
    </div>`;
  }
}
customElements.define('vs-portal-service', VsPortalService);
