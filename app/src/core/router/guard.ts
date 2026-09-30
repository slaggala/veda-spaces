import type { SessionState } from '../authz/context.js';
import { hasAny } from '../authz/permissions.js';

export type Access = 'public' | 'guest' | 'auth';

export interface RouteMeta {
  access: Access;
  /** Any-of permission codes required to view the route (06 §8 Layer 5, UI route guard). */
  anyOf?: readonly string[];
  /** Render inside the app shell (sidebar, top bar). */
  chrome?: boolean;
  /** Allowed inside a RECOVERY session (05 §11.5 allow-list). */
  recovery?: boolean;
  /** Allowed while a password change is forced (05 §3). */
  passwordChange?: boolean;
}

export interface GuardContext {
  state: SessionState;
  mustChangePassword: boolean;
  path: string;
  search?: string;
}

/**
 * Pure route guard: returns a redirect URL or null when navigation may proceed. The server remains
 * authoritative; this only avoids rendering screens the user can't use (RBAC-012).
 */
export function evaluateGuard(meta: RouteMeta, ctx: GuardContext): string | null {
  const { state } = ctx;
  const authed = state.status === 'authenticated' && Boolean(state.me);
  if (meta.access === 'public') return null;
  if (meta.access === 'guest') {
    if (!authed) return null;
    return state.me?.session.type === 'RECOVERY' ? '/recovery-mode' : '/';
  }
  if (!authed) {
    const target = `${ctx.path}${ctx.search ?? ''}`;
    return target === '/' ? '/login' : `/login?next=${encodeURIComponent(target)}`;
  }
  if (state.me?.session.type === 'RECOVERY') return meta.recovery ? null : '/recovery-mode';
  if (meta.recovery && !meta.chrome && ctx.path === '/recovery-mode') return '/';
  if (ctx.mustChangePassword && !meta.passwordChange) return '/change-password';
  if (meta.anyOf?.length && !hasAny(state.me?.permissions, meta.anyOf)) {
    return `/no-access?perm=${encodeURIComponent(meta.anyOf.join(' or '))}`;
  }
  return null;
}
