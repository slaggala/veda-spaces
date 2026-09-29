import { css, html, nothing } from 'lit';
import type { Me } from '../api/types.js';
import { canOnRow, has, hasAll, hasAny } from './permissions.js';
import { SessionElement } from './session-element.js';

/**
 * <vs-can permission="lead.assign"> renders its slot only when the effective map contains the code
 * (09 §3.4, UI-013). `all` / `any` accept space-separated lists. `.scopeFor=${lead}` evaluates OWN
 * ownership client-side. The fallback slot renders otherwise. UI gating is cosmetic (RBAC-012).
 */
export class VsCan extends SessionElement {
  static override properties = {
    permission: { type: String },
    any: { type: String },
    all: { type: String },
    scopeFor: { attribute: false },
    meOverride: { attribute: false },
  };
  declare permission: string;
  declare any: string;
  declare all: string;
  declare scopeFor: { assigned_to?: { id: string } | null; created_by?: { id: string } | null } | null;
  /** Testing / non-context hosts may supply the profile directly. */
  declare meOverride: Me | null;
  static override styles = css`:host { display: contents; }`;

  get allowed(): boolean {
    const me = this.meOverride ?? this.me;
    const perms = me?.permissions;
    if (this.permission) {
      if (this.scopeFor) return canOnRow(perms, this.permission, me?.id, this.scopeFor);
      if (!has(perms, this.permission)) return false;
    }
    if (this.any && !hasAny(perms, this.any.split(/\s+/).filter(Boolean))) return false;
    if (this.all && !hasAll(perms, this.all.split(/\s+/).filter(Boolean))) return false;
    return Boolean(this.permission || this.any || this.all);
  }

  override render() {
    return this.allowed ? html`<slot></slot>` : html`<slot name="fallback"></slot>${nothing}`;
  }
}

if (!customElements.get('vs-can')) customElements.define('vs-can', VsCan);
