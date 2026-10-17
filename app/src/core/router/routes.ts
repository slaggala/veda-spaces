import type { Route } from '@vaadin/router';
import { session } from '../auth/session.js';
import { evaluateGuard, landingPath, type Landing, type RouteMeta } from './guard.js';
import { navigate } from './next.js';

type Loader = () => Promise<unknown>;

interface Def extends RouteMeta {
  path: string;
  component: string;
  load: Loader;
  /** Document title for the page (WCAG 2.4.2, IR-19). */
  title: string;
  /** A complete document title instead of "title · Veda Workspace" (customer-facing pages). */
  fullTitle?: string;
}

const auth = () => import('../../modules/auth/index.js');
const leads = () => import('../../modules/leads/index.js');
const admin = () => import('../../modules/admin/index.js');
const audit = () => import('../../modules/audit/index.js');
const catalog = () => import('../../modules/catalog/index.js');
const siteModule = () => import('../../modules/site/index.js');
const commercialModule = () => import('../../modules/commercial/index.js');
const proposalModule = () => import('../../modules/proposal/index.js');
const promiseModule = () => import('../../modules/promise/index.js');
const projectModule = () => import('../../modules/project/index.js');
const portalModule = () => import('../../modules/portal/index.js');
const commercialsModule = () => import('../../modules/commercials/index.js');
const serviceModule = () => import('../../modules/service/index.js');

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
  // CQX: the customer's proposal, opened by its secure link (the token is in the fragment; every API call answers 404
  // while VEDA_CUSTOMER_PROPOSAL_ENABLED is off). No sign-in and no workspace chrome.
  { path: '/proposal', title: 'Your proposal', fullTitle: 'Your proposal · Veda Spaces', component: 'vs-proposal-page', access: 'public', load: proposalModule },
  // CPP: the customer's project portal (signed in by an emailed link; the session is sent only in X-Veda-Portal; every API
  // call answers 404 while VEDA_CUSTOMER_PORTAL_ENABLED is off). No workspace sign-in and no workspace chrome.
  { path: '/portal', title: 'Your project portal', fullTitle: 'Your project portal · Veda Spaces', component: 'vs-portal-home-page', access: 'public', load: portalModule },
  { path: '/portal/sign-in', title: 'Sign in to your project portal', fullTitle: 'Sign in · Your project portal · Veda Spaces', component: 'vs-portal-sign-in-page', access: 'public', load: portalModule },
  { path: '/portal/properties/:id', title: 'Your project', fullTitle: 'Your project · Veda Spaces', component: 'vs-portal-project-page', access: 'public', load: portalModule },
  { path: '/portal/quotations/:id', title: 'Your quotation', fullTitle: 'Your quotation · Veda Spaces', component: 'vs-portal-quotation-page', access: 'public', load: portalModule },
  // PCM: the customer's invoices and receipts in the portal (same session; 404 while VEDA_PROJECT_COMMERCIALS_ENABLED is off).
  { path: '/portal/invoices/:id', title: 'Your invoice', fullTitle: 'Your invoice · Veda Spaces', component: 'vs-portal-document-page', access: 'public', load: portalModule },
  { path: '/portal/receipts/:id', title: 'Your receipt', fullTitle: 'Your receipt · Veda Spaces', component: 'vs-portal-document-page', access: 'public', load: portalModule },
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
  { path: '/catalog', title: 'Estimator catalog', component: 'vs-catalog-page', access: 'auth', chrome: true, anyOf: ['catalog.view'], load: catalog },
  // MTQ B1 site measurement (staff only; every API call answers 404 while VEDA_MTQ_SITE_ENABLED is off).
  { path: '/site', title: 'Site measurement', component: 'vs-site-home-page', access: 'auth', chrome: true, anyOf: ['measurement.visit.read', 'property.read'], load: siteModule },
  { path: '/site/properties/:id', title: 'Property', component: 'vs-property-page', access: 'auth', chrome: true, anyOf: ['property.read'], load: siteModule },
  // MTQ B2-B4 scope, BOQ, estimate and quotation (every API call answers 404 while VEDA_MTQ_ESTIMATION_ENABLED is off).
  { path: '/site/properties/:id/commercial', title: 'Scope and quotation', component: 'vs-commercial-page', access: 'auth', chrome: true, anyOf: ['scope.read'], load: commercialModule },
  { path: '/site/sets/:id/capture', title: 'Capture', component: 'vs-capture-page', access: 'auth', chrome: true, anyOf: ['measurement.capture'], load: siteModule },
  { path: '/site/sets/:id/review', title: 'Measurement review', component: 'vs-review-page', access: 'auth', chrome: true, anyOf: ['measurement.read'], load: siteModule },
  // Commercial › Customer Promise (every API call answers 404 while VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED is off).
  { path: '/commercial/customer-promise', title: 'Customer Promise', component: 'vs-promise-page', access: 'auth', chrome: true, anyOf: ['customer_promise.view'], load: promiseModule },
  // Operations › Projects (every API call answers 404 while VEDA_PROJECT_LIFECYCLE_ENABLED is off).
  { path: '/projects', title: 'Projects', component: 'vs-project-list-page', access: 'auth', chrome: true, anyOf: ['project.view'], load: projectModule },
  { path: '/projects/:id', title: 'Project', component: 'vs-project-page', access: 'auth', chrome: true, anyOf: ['project.view'], load: projectModule },
  // Commercial › Payments (every API call answers 404 while VEDA_PROJECT_COMMERCIALS_ENABLED is off).
  { path: '/commercials', title: 'Payments', component: 'vs-commercials-list-page', access: 'auth', chrome: true, anyOf: ['commercials.view'], load: commercialsModule },
  { path: '/commercials/:id', title: 'Project commercials', component: 'vs-commercials-page', access: 'auth', chrome: true, anyOf: ['commercials.view'], load: commercialsModule },
  // After handover › Service (every API call answers 404 while VEDA_WARRANTY_SERVICE_ENABLED is off).
  { path: '/service', title: 'Service', component: 'vs-service-list-page', access: 'auth', chrome: true, anyOf: ['warranty.service.view'], load: serviceModule },
  { path: '/service/:id', title: 'Service request', component: 'vs-service-request-page', access: 'auth', chrome: true, anyOf: ['warranty.service.view'], load: serviceModule },
  { path: '/audit', title: 'Audit log', component: 'vs-audit-page', access: 'auth', chrome: true, anyOf: ['audit.read', 'security_event.read'], load: audit },
];

/** Landing pages for "/" in order of preference, each with its route's own permissions (the dashboard first). */
const LANDING_ORDER = ['/', '/site', '/leads', '/follow-ups', '/approvals', '/catalog', '/audit', '/admin/users', '/admin/roles', '/profile'];
export const LANDINGS: Landing[] = LANDING_ORDER.map((path) => {
  const def = ROUTES.find((d) => d.path === path);
  if (!def) throw new Error(`landing page ${path} is not a route`);
  return { path, anyOf: def.anyOf };
});

export const APP_TITLE = 'Veda Workspace';

/** "Page · Veda Workspace" for a path; unknown paths get "Page not found". */
export function titleForPath(pathname: string): string {
  const def = metaForPath(pathname) as Def | undefined;
  if (def?.fullTitle) return def.fullTitle;
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
        home: context.pathname === '/' ? landingPath(session.state.me?.permissions, LANDINGS) : null,
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
