import { expect, fixture, html } from '@open-wc/testing';
import { filterNav, NAV_ITEMS } from '../src/core/authz/permissions.js';
import '../src/shell/command-palette.js';

/** MC-3 (PR #87 review): a permission alone never makes a switched-off feature discoverable. */

const SITE = { 'measurement.visit.read': 'ALL', 'property.read': 'ALL' } as const;
const V1 = { 'lead.read': 'ALL', 'lead.create': 'ALL', 'lead_activity.read': 'ALL', 'profile.read': 'ALL', 'user.read': 'ALL',
  'role.read': 'ALL', 'permission.read': 'ALL', 'audit.read': 'ALL', 'user.mfa.reset': 'ALL', 'user.founder.manage': 'ALL',
  'catalog.view': 'ALL' } as const;
const ROLES = {
  FOUNDER: { ...V1, ...SITE },
  ADMIN: { ...V1, ...SITE },
  SALES: { 'lead.read': 'OWN', 'lead_activity.read': 'ALL', 'profile.read': 'ALL', 'property.read': 'OWN' },
  SURVEYOR: { 'profile.read': 'ALL', ...SITE },
} as const;
const V1_MENU = ['/', '/leads', '/follow-ups', '/approvals', '/admin/users', '/admin/roles', '/admin/permissions',
  '/admin/founder-actions', '/catalog', '/audit', '/profile'];

describe('MTQ navigation behind its feature flag (MC-3)', () => {
  for (const [role, perms] of Object.entries(ROLES)) {
    it(`hides Site visits from ${role} while the flag is off, whatever the permissions`, () => {
      for (const features of [undefined, null, {}, { mtq_site: false }]) {
        expect(filterNav(NAV_ITEMS, perms, features).map((i) => i.path)).to.not.include('/site');
      }
    });
  }
  it('shows Site visits only with the flag on AND a site permission', () => {
    expect(filterNav(NAV_ITEMS, ROLES.SURVEYOR, { mtq_site: true }).map((i) => i.path)).to.include('/site');
    expect(filterNav(NAV_ITEMS, V1, { mtq_site: true }).map((i) => i.path)).to.not.include('/site');
  });
  it('leaves the V1 menu exactly as it was', () => {
    expect(filterNav(NAV_ITEMS, ROLES.FOUNDER, { mtq_site: false }).map((i) => i.path)).to.deep.equal(V1_MENU);
    expect(filterNav(NAV_ITEMS, V1).map((i) => i.path)).to.deep.equal(V1_MENU);
  });
  it('keeps the command palette from finding the page while the flag is off', async () => {
    const off = await fixture(html`<vs-command-palette .perms=${ROLES.FOUNDER} .features=${{ mtq_site: false }}></vs-command-palette>`);
    (off as unknown as { show(): void }).show();
    await (off as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    expect(off.shadowRoot!.textContent).to.not.contain('Site visits');
    const on = await fixture(html`<vs-command-palette .perms=${ROLES.FOUNDER} .features=${{ mtq_site: true }}></vs-command-palette>`);
    (on as unknown as { show(): void }).show();
    await (on as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    expect(on.shadowRoot!.textContent).to.contain('Site visits');
  });
});
