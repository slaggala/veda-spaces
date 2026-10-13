import { LitElement, html } from 'lit';
import { shared } from '../../design-system/styles.js';
import { queue, SITE_DB } from './offline-queue.js';

/** 'synced': everything was sent; 'discard': the user chose to drop what was not; 'cancel': stay signed in. */
export type SignOutChoice = 'synced' | 'discard' | 'cancel';

/**
 * Sign-out with site captures on the device (B1-PE-02). Registered by the shell as a logout guard, so it runs whether
 * or not the site pages were opened in this tab:
 *
 * - no site database on this device (the site module was never used): nothing to do, no prompt, nothing created;
 * - the user has nothing unsent: their operations and photos are deleted from the device, and sign-out proceeds;
 * - the user has unsent operations (pending, uploading, or waiting for a decision): they choose "Sync now" (send; signs
 *   out once nothing is left, otherwise says how many remain), "Discard and sign out" (delete their operations and
 *   photos), or stay signed in.
 *
 * Other users' operations, and those of unknown origin, are never touched here. The site service worker's cache holds
 * only the public app shell and build assets, no capture data, so it is left in place for the next surveyor offline.
 */
export async function siteSignOutGuard(userId: string): Promise<boolean> {
  if (!(await siteDatabaseExists())) return true;
  const unsent = (await queue.mine()).length;
  if (unsent) {
    const choice = await askSignOut(unsent, async () => { await queue.flushAll(); return (await queue.mine()).length; });
    if (choice === 'cancel') return false;
  }
  await queue.forget(userId);
  return true;
}

/** Whether this device holds the site database, found without creating it (an aborted upgrade creates nothing). */
export async function siteDatabaseExists(): Promise<boolean> {
  try {
    if (typeof indexedDB === 'undefined') return false;
    if (typeof indexedDB.databases === 'function') return (await indexedDB.databases()).some((d) => d.name === SITE_DB);
    return await new Promise<boolean>((resolve) => {
      const req = indexedDB.open(SITE_DB);
      req.onupgradeneeded = () => req.transaction?.abort();
      req.onsuccess = () => { req.result.close(); resolve(true); };
      req.onerror = () => resolve(false);
    });
  } catch {
    return false; // storage refused (private mode): there is nothing stored to protect
  }
}

/** The confirmation itself: an accessible modal on vs-dialog (focus trap, Esc cancels, focus restored). */
export class VsSiteSignOutDialog extends LitElement {
  static override properties = { open: { state: true }, unsent: { state: true }, retried: { state: true }, busy: { state: true } };
  declare open: boolean;
  declare unsent: number;
  declare retried: boolean;
  declare busy: boolean;
  private resolve: ((c: SignOutChoice) => void) | null = null;
  private sync: () => Promise<number> = async () => 0;
  static override styles = shared;

  constructor() {
    super();
    this.open = false; this.unsent = 0; this.retried = false; this.busy = false;
  }

  /** `sync` sends what it can and answers how many operations are still unsent. */
  ask(unsent: number, sync: () => Promise<number>): Promise<SignOutChoice> {
    this.unsent = unsent;
    this.sync = sync;
    this.retried = false;
    this.busy = false;
    this.open = true;
    return new Promise((resolve) => (this.resolve = resolve));
  }

  private async syncNow() {
    this.busy = true;
    let left = this.unsent;
    try { left = await this.sync(); } catch { /* counted as not sent */ }
    this.busy = false;
    if (!this.resolve) return; // dismissed meanwhile: the user stays signed in
    if (!left) { this.done('synced'); return; }
    this.unsent = left;
    this.retried = true;
  }

  private done(choice: SignOutChoice) {
    this.open = false;
    this.resolve?.(choice);
    this.resolve = null;
  }

  override render() {
    const n = this.unsent;
    const changes = `${n} change${n === 1 ? '' : 's'}`;
    return html`<vs-dialog .open=${this.open} heading="Site captures not sent yet" @close=${() => this.resolve && this.done('cancel')}>
      <p>${this.retried ? `${changes} could still not be sent: you may be offline, or the capture page needs your decision.`
        : `${changes} you captured on site ${n === 1 ? 'has' : 'have'} not reached the server.`}</p>
      <p>Signing out deletes your captures from this device. Sync first to keep them.</p>
      <p role="status" class="small">${this.busy ? 'Sending your captures…' : this.retried ? 'Stay signed in to resolve them on the capture page.' : ''}</p>
      <div slot="actions">
        <button class="btn" ?disabled=${this.busy} @click=${() => this.done('cancel')}>Stay signed in</button>
        <button class="btn danger" ?disabled=${this.busy} @click=${() => this.done('discard')}>Discard and sign out</button>
        <button class="btn primary" ?disabled=${this.busy} @click=${() => this.syncNow()}>Sync now</button>
      </div>
    </vs-dialog>`;
  }
}
customElements.define('vs-site-sign-out-dialog', VsSiteSignOutDialog);

function askSignOut(unsent: number, sync: () => Promise<number>): Promise<SignOutChoice> {
  let el = document.querySelector('vs-site-sign-out-dialog') as VsSiteSignOutDialog | null;
  if (!el) {
    el = document.createElement('vs-site-sign-out-dialog') as VsSiteSignOutDialog;
    document.body.append(el);
  }
  return el.ask(unsent, sync);
}
