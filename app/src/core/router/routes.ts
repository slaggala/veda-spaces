import type { Route } from '@vaadin/router';
import { session } from '../auth/session.js';
import { evaluateGuard, type RouteMeta } from './guard.js';
import { navigate } from './next.js';

type Loader = () => Promise<unknown>;

interface Def extends RouteMeta {
  path: string;
  component: string;
  load: Loader;
  /** Document title for the page (WCAG 2.4.2, IR-19). */
  title: string;
}

const auth = () => import('../../modules/auth/index.js');
const leads = () => import('../../modules/leads/index.js');
const admin = () => import('../../modules/admin/index.js');
const audit = () => import('../../modules/audit/index.js');

/** Route table. Each module's routes load on demand (route-level code splitting, 02 §2.1). */
export const ROUTES: Def[] = [
  { path: '/login', title: 'Sign in', component: 'vs-login-page', access: 'guest', load: auth },
  { path: '/mfa', title: 'Two-step verification', component: 'vs-mfa-challenge-page', access: 'guest', load: auth },
  { path: '/mfa/recovery', title: 'Use a recovery code', component: 'vs-mfa-recovery-page', access: 'guest', load: auth },
  { path: '/mfa/check-email', title: 'Check your email', component: 'vs-enroll-email-sent-page', access: 'guest', load: auth },
  { path: '/mfa/enroll', title: 'Set up two-step verification', component: 'vs-mfa-enroll-page', access: 'public', load: auth },
  { path: '/forgot-password', title: 'Forgot password', component: 'vs-forgot-password-page', access: 'public', load: auth },
  { path: '/reset-password', title: 'Reset password', component: 'vs-reset-password-page', access: 'public', load: auth },
  { path: '/accept-invite', title: 'Accept invitation', component: 'vs-accept-invite-page', access: 'public', load: auth },
  { path: '/verify-email', title: 'Verify email', component: 'vs-verify-email-page', access: 'public', load: auth },
  { path: '/cancel-email-change', title: 'Cancel email change', component: 'vs-cancel-email-page', access: 'public', load: auth },
  // Break-glass cancel link from the notification email (06 §7.5 step 5; DEV-005, AM-5, IR-07).
  { path: '/approvals/cancel', title: 'Cancel break-glass request', component: 'vs-approval-cancel-page', access: 'public', load: auth },
  { path: '/recovery-mode', title: 'Account recovery', component: 'vs-recovery-mode-page', access: 'auth', recovery: true, load: auth },
  { path: '/change-password', title: 'Change password', component: 'vs-change-password-page', access: 'auth', passwordChange: true, load: auth },
  { path: '/no-access', title: 'No access', component: 'vs-no-access-page', access: 'auth', chrome: true, load: auth },
  { path: '/profile', title: 'Profile', component: 'vs-profile-page', access: 'auth', chrome: true, anyOf: ['profile.read'], load: auth },

  { path: '/', title: 'Dashboard', component: 'vs-dashboard-page', access: 'auth', chrome: true, anyOf: ['lead.read'], load: leads },
  { path: '/leads', title: 'Leads', component: 'vs-lead-list-page', access: 'auth', chrome: true, anyOf: ['lead.read'], load: leads },
  { path: '/leads/:id', title: 'Lead', component: 'vs-lead-detail-page', access: 'auth', chrome: true, anyOf: ['lead.read'], load: leads },
  { path: '/follow-ups', title: 'Follow-ups', component: 'vs-followups-page', access: 'auth', chrome: true, anyOf: ['lead_activity.read'], load: leads },

  { path: '/admin/users', title: 'Users', component: 'vs-users-page', access: 'auth', chrome: true, anyOf: ['user.read'], load: admin },
  { path: '/admin/roles', title: 'Roles', component: 'vs-roles-page', access: 'auth', chrome: true, anyOf: ['role.read'], load: admin },
  { path: '/admin/permissions', title: 'Permissions', component: 'vs-permissions-page', access: 'auth', chrome: true, anyOf: ['permission.read'], load: admin },
  {
    path: '/approvals', title: 'Approvals', component: 'vs-approvals-page', access: 'auth', chrome: true,
    anyOf: ['user.mfa.reset', 'user.email.change', 'user.founder.manage'], load: admin,
  },
  { path: '/admin/founder-actions', title: 'Founder actions', component: 'vs-founder-actions-page', access: 'auth', chrome: true, anyOf: ['user.founder.manage'], load: admin },
  { path: '/audit', title: 'Audit log', component: 'vs-audit-page', access: 'auth', chrome: true, anyOf: ['audit.read', 'security_event.read'], load: audit },
];

export const APP_TITLE = 'Veda Workspace';

/** "Page · Veda Workspace" for a path; unknown paths get "Page not found". */
export function titleForPath(pathname: string): string {
  const def = metaForPath(pathname) as Def | undefined;
  return `${def ? def.title : 'Page not found'} · ${APP_TITLE}`;
}

export function metaForPath(pathname: string): RouteMeta | undefined {
  for (const def of ROUTES) {
    const pattern = new RegExp(`^${def.path.replace(/:[a-z_]+/g, '[^/]+')}/?$`);
    if (pattern.test(pathname)) return def;
  }
  return undefined;
}

export function buildRoutes(): Route[] {
  const routes: Route[] = ROUTES.map((def) => ({
    path: def.path,
    component: def.component,
    action: async (context, commands) => {
      await session.ready();
      const redirect = evaluateGuard(def, {
        state: session.state,
        mustChangePassword: session.mustChangePassword,
        path: context.pathname,
        search: window.location.pathname === context.pathname ? window.location.search : '',
      });
      if (redirect) {
        queueMicrotask(() => navigate(redirect));
        return commands.prevent();
      }
      await def.load();
      return undefined;
    },
  }));
  routes.push({ path: '(.*)', component: 'vs-not-found-page', action: async () => { await auth(); return undefined; } });
  return routes;
}
