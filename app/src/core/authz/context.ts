import { createContext } from '@lit/context';
import type { LookupCategory, Me } from '../api/types.js';

/** App-wide state provided with @lit/context (02 §2.1). */
export interface SessionState {
  status: 'loading' | 'anonymous' | 'authenticated';
  me: Me | null;
}

export const sessionContext = createContext<SessionState>(Symbol('veda-session'));
export const lookupsContext = createContext<Record<string, LookupCategory>>(Symbol('veda-lookups'));
