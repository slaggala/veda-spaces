import { ContextConsumer } from '@lit/context';
import { html, nothing } from 'lit';
import { lookupOptions } from '../../core/api/lookups.js';
import type { LookupCategory } from '../../core/api/types.js';
import { lookupsContext } from '../../core/authz/context.js';
import { SessionElement } from '../../core/authz/session-element.js';

/** Session-aware element that also consumes the lookup lists (08 §7) through @lit/context. */
export class LookupAwareElement extends SessionElement {
  protected lookupsConsumer = new ContextConsumer(this, { context: lookupsContext, subscribe: true });

  get lookups(): Record<string, LookupCategory> {
    return this.lookupsConsumer.value ?? {};
  }

  /** <select> options for a lookup category; values are codes (writes use *_code, 08 §2.2). */
  lookupSelect(name: string, category: string, value: string | null | undefined, opts: { label: string; required?: boolean; error?: string; placeholder?: string } ) {
    const options = lookupOptions(this.lookups, category);
    const current = value ?? '';
    const known = options.some((o) => o.code === current);
    return html`<label class="field"><span class="label">${opts.label}${opts.required ? ' *' : ''}</span>
      <select name=${name} aria-required=${opts.required ? 'true' : 'false'} aria-invalid=${opts.error ? 'true' : 'false'}>
        <option value="" ?selected=${!current}>${opts.placeholder ?? 'Choose…'}</option>
        ${!known && current ? html`<option value=${current} selected>${current}</option>` : nothing}
        ${options.map((o) => html`<option value=${o.code} ?selected=${o.code === current}>${o.label}</option>`)}
      </select>
      ${opts.error ? html`<span class="error">⚠ ${opts.error}</span>` : nothing}</label>`;
  }
}
