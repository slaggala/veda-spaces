import { LitElement, html } from 'lit';
import { shared } from '../design-system/styles.js';

export type ConflictChoice = 'reload' | 'reapply' | 'cancel';

export interface ConflictInfo {
  fields: string[];
  updatedBy?: string;
  updatedOn?: string;
}

/**
 * Version-conflict modal (09 §3.2, TD-F step 4): lists the fields changed by the other writer and offers
 * "Reload theirs" or "Re-apply mine". Re-apply resubmits the local edits against the new version.
 */
export class VsConflictDialog extends LitElement {
  static override properties = { info: { state: true }, open: { state: true } };
  declare info: ConflictInfo | null;
  declare open: boolean;
  private resolve: ((c: ConflictChoice) => void) | null = null;
  static override styles = shared;

  constructor() {
    super();
    this.info = null;
    this.open = false;
  }

  ask(info: ConflictInfo): Promise<ConflictChoice> {
    this.info = info;
    this.open = true;
    return new Promise((resolve) => (this.resolve = resolve));
  }

  private done(choice: ConflictChoice) {
    this.open = false;
    this.resolve?.(choice);
    this.resolve = null;
  }

  override render() {
    const info = this.info;
    return html`<vs-dialog .open=${this.open} heading="This record was changed by someone else" @close=${() => this.resolve && this.done('cancel')}>
      <p>${info?.updatedBy ? `${info.updatedBy} saved changes` : 'Someone saved changes'}${info?.updatedOn ? ` at ${info.updatedOn}` : ''} while you were editing.</p>
      ${info?.fields.length
        ? html`<div><p class="eyebrow">Changed by them</p><ul>${info.fields.map((f) => html`<li>${f.replace(/_/g, ' ')}</li>`)}</ul></div>`
        : html`<p class="muted">No overlapping fields were changed.</p>`}
      <div slot="actions">
        <button class="btn" @click=${() => this.done('reload')}>Reload theirs</button>
        <button class="btn primary" @click=${() => this.done('reapply')}>Re-apply mine</button>
      </div>
    </vs-dialog>`;
  }
}
customElements.define('vs-conflict-dialog', VsConflictDialog);

export function resolveConflict(info: ConflictInfo): Promise<ConflictChoice> {
  let el = document.querySelector('vs-conflict-dialog') as VsConflictDialog | null;
  if (!el) {
    el = document.createElement('vs-conflict-dialog') as VsConflictDialog;
    document.body.append(el);
  }
  return el.ask(info);
}
