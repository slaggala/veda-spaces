import { ContextConsumer } from '@lit/context';
import { LitElement } from 'lit';
import type { Me, PermissionMap, Scope } from '../api/types.js';
import { has, hasAny } from './permissions.js';
import { sessionContext, type SessionState } from './context.js';

/**
 * Base class for components that need the session / effective permissions. The state arrives through
 * @lit/context from <vs-app> (02 §2.1) and re-renders the component when it changes.
 */
export class SessionElement extends LitElement {
  protected sessionConsumer = new ContextConsumer(this, { context: sessionContext, subscribe: true });

  get sessionState(): SessionState | undefined {
    return this.sessionConsumer.value;
  }
  get me(): Me | null {
    return this.sessionConsumer.value?.me ?? null;
  }
  get perms(): PermissionMap {
    return this.me?.permissions ?? {};
  }
  can(code: string, minScope?: Scope): boolean {
    return has(this.perms, code, minScope);
  }
  canAny(...codes: string[]): boolean {
    return hasAny(this.perms, codes);
  }
}
