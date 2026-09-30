import { expect } from '@open-wc/testing';
import type { Me } from '../src/core/api/types.js';
import { filterNav, NAV_ITEMS, has, canOnRow } from '../src/core/authz/permissions.js';
import { evaluateGuard } from '../src/core/router/guard.js';
import { sanitizeNext } from '../src/core/router/next.js';

export function makeMe(permissions: Record<string, 'ALL' | 'OWN'>, overrides: Partial<Me> = {}): Me {
  return {
    id: 'u1', email: 'p@vedaspaces.com', full_name: 'Priya Sharma', display_name: 'Priya', phone: null, timezone: 'Asia/Kolkata', locale: 'en-IN',
    status: 'ACTIVE', roles: [], authz_version: 1, permissions, suspended_permissions: [],
    session: { type: 'FULL', auth_methods: ['pwd'], mfa_verified_on: null, cooling_off_until: null },
    mfa: { required: false, required_by: [], enrolled: false }, email_change: null, version: 1, ...overrides,
  };
}

const SALES = { 'lead.create': 'ALL', 'lead.read': 'OWN', 'lead.update': 'OWN', 'lead_activity.read': 'ALL', 'profile.read': 'ALL', 'notification.read': 'OWN' } as const;
const ADMIN = { ...SALES, 'lead.read': 'ALL', 'user.read': 'ALL', 'role.read': 'ALL', 'permission.read': 'ALL', 'audit.read': 'ALL', 'user.mfa.reset': 'ALL' } as const;

describe('sanitizeNext (A-08)', () => {
  it('accepts same-origin relative paths', () => {
    expect(sanitizeNext('/leads?status=NEW')).to.equal('/leads?status=NEW');
    expect(sanitizeNext(encodeURIComponent('/leads/abc'))).to.equal('/leads/abc');
  });
  it('rejects protocol-relative, backslash, absolute and odd values', () => {
    for (const bad of ['//evil.com', '/\\evil.com', 'https://evil.com', 'evil.com', 'javascript:alert(1)', '%2F%2Fevil.com', '', null, '/login?next=/x']) {
      expect(sanitizeNext(bad as string | null)).to.equal('/', String(bad));
    }
  });
});

describe('permission-driven navigation (09 §3.1)', () => {
  it('shows only main items to Sales and hides the admin group', () => {
    const paths = filterNav(NAV_ITEMS, SALES).map((i) => i.path);
    expect(paths).to.include.members(['/', '/leads', '/follow-ups', '/profile']);
    expect(paths).to.not.include('/admin/users');
    expect(paths).to.not.include('/audit');
    expect(paths).to.not.include('/approvals');
  });
  it('shows the admin group to holders of the admin permissions', () => {
    const paths = filterNav(NAV_ITEMS, ADMIN).map((i) => i.path);
    expect(paths).to.include.members(['/admin/users', '/admin/roles', '/admin/permissions', '/audit', '/approvals']);
    expect(paths).to.not.include('/admin/founder-actions');
  });
  it('compares scopes and evaluates OWN rows', () => {
    expect(has(SALES, 'lead.read')).to.equal(true);
    expect(has(SALES, 'lead.read', 'ALL')).to.equal(false);
    expect(canOnRow(SALES, 'lead.update', 'u1', { assigned_to: { id: 'u1' } })).to.equal(true);
    expect(canOnRow(SALES, 'lead.update', 'u1', { assigned_to: { id: 'u2' }, created_by: { id: 'u3' } })).to.equal(false);
    expect(canOnRow(ADMIN, 'lead.read', 'u1', { assigned_to: { id: 'u2' } })).to.equal(true);
  });
});

describe('route guard', () => {
  const anon = { state: { status: 'anonymous' as const, me: null }, mustChangePassword: false };
  it('redirects anonymous users to login with a next parameter', () => {
    expect(evaluateGuard({ access: 'auth' }, { ...anon, path: '/leads', search: '?status=NEW' })).to.equal(`/login?next=${encodeURIComponent('/leads?status=NEW')}`);
    expect(evaluateGuard({ access: 'auth' }, { ...anon, path: '/' })).to.equal('/login');
    expect(evaluateGuard({ access: 'guest' }, { ...anon, path: '/login' })).to.equal(null);
  });
  it('sends users without the permission to the no-access page', () => {
    const ctx = { state: { status: 'authenticated' as const, me: makeMe(SALES) }, mustChangePassword: false, path: '/admin/users' };
    expect(evaluateGuard({ access: 'auth', anyOf: ['user.read'] }, ctx)).to.match(/^\/no-access\?perm=user\.read/);
    expect(evaluateGuard({ access: 'auth', anyOf: ['lead.read'] }, { ...ctx, path: '/leads' })).to.equal(null);
  });
  it('confines RECOVERY sessions to the recovery allow-list', () => {
    const me = makeMe({}, { session: { type: 'RECOVERY', auth_methods: ['pwd', 'recovery'], mfa_verified_on: null, cooling_off_until: null } });
    const ctx = { state: { status: 'authenticated' as const, me }, mustChangePassword: false, path: '/leads' };
    expect(evaluateGuard({ access: 'auth', anyOf: ['lead.read'] }, ctx)).to.equal('/recovery-mode');
    expect(evaluateGuard({ access: 'auth', recovery: true }, { ...ctx, path: '/recovery-mode' })).to.equal(null);
    expect(evaluateGuard({ access: 'guest' }, { ...ctx, path: '/login' })).to.equal('/recovery-mode');
  });
  it('forces the change-password screen when required', () => {
    const ctx = { state: { status: 'authenticated' as const, me: makeMe(SALES) }, mustChangePassword: true, path: '/leads' };
    expect(evaluateGuard({ access: 'auth', anyOf: ['lead.read'] }, ctx)).to.equal('/change-password');
    expect(evaluateGuard({ access: 'auth', passwordChange: true }, { ...ctx, path: '/change-password' })).to.equal(null);
  });
});

describe('route titles (WCAG 2.4.2, IR-19)', () => {
  it('gives every route its own document title', async () => {
    const { ROUTES, titleForPath } = await import('../src/core/router/routes.js');
    const titles = new Set(ROUTES.map((r) => titleForPath(r.path.replace(':id', '0190a0b1c2d37e8f9a0b1c2d3e4f5a6b'))));
    expect(titles.size).to.equal(ROUTES.length);
    expect(titleForPath('/leads')).to.equal('Leads · Veda Workspace');
    expect(titleForPath('/approvals/cancel')).to.equal('Cancel break-glass request · Veda Workspace');
    expect(titleForPath('/nowhere')).to.equal('Page not found · Veda Workspace');
  });
});
