import { ContextProvider } from '@lit/context';
import { Router } from '@vaadin/router';
import { LitElement, css, html, nothing } from 'lit';
import { api } from '../core/api/client.js';
import { loadLookups } from '../core/api/lookups.js';
import type { LookupCategory } from '../core/api/types.js';
import { session } from '../core/auth/session.js';
import { requestStepUp } from '../core/auth/step-up.js';
import { lookupsContext, sessionContext } from '../core/authz/context.js';
import { filterNav, has, NAV_ITEMS, type NavItem } from '../core/authz/permissions.js';
import { formatAbsolute, initials } from '../core/format/format.js';
import { t } from '../core/i18n/strings.js';
import { buildRoutes, metaForPath, titleForPath } from '../core/router/routes.js';
import { navigate } from '../core/router/next.js';
import { ensureToaster } from '../design-system/components.js';
import { icon } from '../design-system/icons.js';
import { shared } from '../design-system/styles.js';
import './command-palette.js';
import './conflict-dialog.js';
import './notifications-tray.js';
import './step-up-dialog.js';

/**
 * <vs-app>: application root. Provides session/permission and lookup context (@lit/context), hosts the
 * router outlet, and renders the permission-driven shell (09 §3.1). RECOVERY sessions get the
 * restricted shell with only "Set up new authenticator" and "Sign out" (09 §4.10).
 */
export class VsApp extends LitElement {
  static override properties = {
    pathname: { state: true }, menuOpen: { state: true }, approvalsPending: { state: true }, announced: { state: true },
  };
  declare pathname: string;
  declare announced: string;
  private navigations = 0;
  declare menuOpen: boolean;
  declare approvalsPending: number;
  private sessionProvider = new ContextProvider(this, { context: sessionContext, initialValue: session.state });
  private lookupsProvider = new ContextProvider(this, { context: lookupsContext, initialValue: {} as Record<string, LookupCategory> });
  private router: Router | null = null;

  static override styles = [
    ...shared,
    css`
      :host { display: block; min-height: 100vh; background: var(--vs-paper); }
      .layout { display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; }
      .layout.bare { display: block; }
      nav.side { background: var(--vs-sidebar); color: var(--vs-on-sidebar); display: flex; flex-direction: column; padding: 24px 0; position: sticky; top: 0; height: 100vh; overflow-y: auto; }
      .brand { font-family: var(--vs-font-serif); font-size: 22px; letter-spacing: .24em; padding: 0 24px 24px; line-height: 26px; }
      .brand small { display: block; font: 600 10px/14px var(--vs-font-sans); letter-spacing: .24em; color: var(--vs-on-sidebar-muted); }
      .group { font: 600 11px/16px var(--vs-font-sans); letter-spacing: .18em; text-transform: uppercase; color: var(--vs-on-sidebar-muted); padding: 20px 24px 8px; }
      nav.side a { display: flex; align-items: center; gap: 12px; min-height: 44px; padding: 0 24px; color: var(--vs-on-sidebar-muted); text-decoration: none; border-left: 2px solid transparent; font-weight: 500; }
      nav.side a:hover { color: var(--vs-on-sidebar); }
      nav.side a[aria-current='page'] { color: var(--vs-on-sidebar); border-left-color: var(--vs-copper); }
      nav.side .bottom { margin-top: auto; }
      .main { display: flex; flex-direction: column; min-width: 0; }
      header.top { display: flex; align-items: center; gap: 8px; padding: 8px 24px; border-bottom: 1px solid var(--vs-line); background: var(--vs-paper); position: sticky; top: 0; z-index: 20; min-height: 60px; }
      header.top .search { display: inline-flex; align-items: center; gap: 8px; color: var(--vs-ink-muted); background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: 2px; min-height: 40px; padding: 0 12px; cursor: pointer; font: inherit; }
      .avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--vs-cream); color: var(--vs-ink); display: inline-flex; align-items: center; justify-content: center; font: 700 12px/1 var(--vs-font-sans); }
      .menu { position: relative; }
      .menu-panel { position: absolute; right: 0; top: 48px; min-width: 220px; background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: 8px; box-shadow: var(--vs-shadow); padding: 8px; z-index: 50; display: flex; flex-direction: column; }
      .menu-panel a, .menu-panel button { text-align: left; background: none; border: 0; min-height: 44px; padding: 0 12px; font: inherit; color: var(--vs-ink); cursor: pointer; text-decoration: none; display: flex; align-items: center; gap: 8px; }
      .menu-btn { background: none; border: 0; cursor: pointer; min-height: 44px; min-width: 44px; }
      .badge { background: var(--vs-copper-strong); color: var(--vs-on-copper-strong); border-radius: 999px; font: 700 11px/18px var(--vs-font-sans); padding: 0 6px; margin-left: auto; }
      .banners { display: flex; flex-direction: column; gap: 8px; padding: 12px 24px 0; }
      .banners:empty { display: none; }
      nav.tabs { display: none; }
      @media (max-width: 1199px) {
        .layout { grid-template-columns: 72px 1fr; }
        .brand, .group, nav.side a span { display: none; }
        nav.side a { justify-content: center; padding: 0; }
      }
      @media (max-width: 767px) {
        .layout { display: block; padding-bottom: 64px; }
        nav.side { display: none; }
        header.top { padding: 8px 12px; }
        header.top .search .search-text { display: none; }
        nav.tabs { display: flex; position: fixed; bottom: 0; left: 0; right: 0; background: var(--vs-surface); border-top: 1px solid var(--vs-line); z-index: 30; }
        nav.tabs a { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 56px; color: var(--vs-ink-muted); text-decoration: none; font: 600 11px/14px var(--vs-font-sans); }
        nav.tabs a[aria-current='page'] { color: var(--vs-copper-text); }
      }
      .recovery { max-width: 560px; margin: 64px auto; padding: 0 16px; display: flex; flex-direction: column; gap: 16px; }
    `,
  ];

  constructor() {
    super();
    this.pathname = window.location.pathname;
    this.menuOpen = false;
    this.approvalsPending = 0;
    this.announced = '';
    ensureToaster();
    api.hooks.onStepUp = (problem) => requestStepUp(problem);
    session.addEventListener('change', () => this.onSessionChange());
    session.addEventListener('session-lost', () => {
      const here = `${window.location.pathname}${window.location.search}`;
      navigate(here.startsWith('/login') ? '/login' : `/login?next=${encodeURIComponent(here)}`);
    });
    window.addEventListener('vaadin-router-location-changed', (e) => {
      this.pathname = e.detail.location.pathname;
      this.menuOpen = false;
      this.onNavigated(this.navigations++ === 0);
    });
  }

  /** WCAG 2.4.2 and AX-01 (IR-19): every route has its own title; after an in-app navigation focus moves to the
   *  page heading (or the main region) and the new page is announced. The first load keeps the browser's focus. */
  private onNavigated(first: boolean) {
    const title = titleForPath(this.pathname);
    document.title = title;
    this.announced = title.split(' · ')[0];
    if (first) return;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const outlet = this.renderRoot.querySelector<HTMLElement>('#outlet');
      const page = outlet?.firstElementChild as HTMLElement | null;
      const heading = (page?.shadowRoot ?? page)?.querySelector<HTMLElement>('h1');
      if (heading) {
        if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: false });
      } else {
        outlet?.focus();
      }
    }));
  }

  private onSessionChange() {
    this.sessionProvider.setValue({ ...session.state });
    this.requestUpdate();
    if (session.isAuthenticated && !session.isRecovery) {
      loadLookups()
        .then((l) => this.lookupsProvider.setValue(l))
        .catch(() => undefined);
      void this.loadApprovalsBadge();
    }
  }

  private async loadApprovalsBadge() {
    const perms = session.me?.permissions;
    if (!(has(perms, 'user.mfa.reset') || has(perms, 'user.email.change') || has(perms, 'user.founder.manage'))) return;
    try {
      const r = await api.get<unknown[]>('/api/v1/approvals', { status: 'PENDING', role: 'approver' });
      this.approvalsPending = Array.isArray(r.data) ? r.data.length : 0;
    } catch {
      this.approvalsPending = 0;
    }
  }

  protected override firstUpdated() {
    const outlet = this.renderRoot.querySelector('#outlet');
    this.router = new Router(outlet);
    void this.router.setRoutes(buildRoutes());
    void session.ready();
  }

  private isActive(item: NavItem): boolean {
    return item.path === '/' ? this.pathname === '/' : this.pathname.startsWith(item.path);
  }

  private navLink(item: NavItem) {
    return html`<a href=${item.path} aria-current=${this.isActive(item) ? 'page' : 'false'} title=${item.label}>
      ${icon(item.icon)}<span>${item.label}</span>
      ${item.path === '/approvals' && this.approvalsPending ? html`<span class="badge" aria-label="${this.approvalsPending} pending">${this.approvalsPending}</span>` : nothing}
    </a>`;
  }

  private renderBanners() {
    const me = session.me;
    const cooling = me?.session.cooling_off_until;
    return html`<div class="banners">${cooling && new Date(cooling) > new Date()
      ? html`<vs-banner kind="warning">For your security, email, password and access changes are locked until ${formatAbsolute(cooling)}.</vs-banner>`
      : nothing}</div>`;
  }

  override render() {
    const meta = metaForPath(this.pathname);
    const me = session.me;
    const chrome = Boolean(meta?.chrome) && session.isAuthenticated && !session.isRecovery;
    const items = filterNav(NAV_ITEMS, me?.permissions);
    const main = items.filter((i) => i.group === 'main');
    const adminItems = items.filter((i) => i.group === 'admin');
    const account = items.filter((i) => i.group === 'account');

    return html`
      <div class="layout ${chrome ? '' : 'bare'}">
        ${chrome
          ? html`<nav class="side" aria-label="Main">
              <div class="brand">VEDA<br />SPACES<small>WORKSPACE</small></div>
              ${main.map((i) => this.navLink(i))}
              ${adminItems.length ? html`<div class="group">Admin</div>${adminItems.map((i) => this.navLink(i))}` : nothing}
              <div class="bottom">${account.map((i) => this.navLink(i))}</div>
            </nav>`
          : nothing}
        <div class="main">
          ${chrome
            ? html`<header class="top">
                <button class="search" @click=${() => (this.renderRoot.querySelector('vs-command-palette') as { show(): void } | null)?.show()}
                  aria-label="Search (Ctrl K)">${icon('search')}<span class="search-text">Search</span><span class="small">⌘K</span></button>
                <span class="spacer"></span>
                <vs-notifications-tray></vs-notifications-tray>
                <div class="menu">
                  <button class="menu-btn" aria-controls="account-menu" aria-expanded=${this.menuOpen ? 'true' : 'false'} aria-label="Account menu"
                    @click=${() => (this.menuOpen = !this.menuOpen)}><span class="avatar" aria-hidden="true">${initials(me?.display_name || me?.full_name)}</span></button>
                  ${this.menuOpen
                    ? html`<div class="menu-panel" id="account-menu" @keydown=${(e: KeyboardEvent) => {
                        if (e.key !== 'Escape') return;
                        this.menuOpen = false;
                        (this.renderRoot.querySelector('.menu-btn') as HTMLElement | null)?.focus();
                      }}>
                        <span class="small muted">${me?.full_name}</span>
                        <a href="/profile">${icon('settings')} Profile</a>
                        <button @click=${async () => { await session.logout(); navigate('/login'); }}>${icon('logout')} Sign out</button>
                      </div>`
                    : nothing}
                </div>
              </header>
              ${this.renderBanners()}`
            : nothing}
          <main id="outlet" tabindex="-1"></main>
        </div>
      </div>
      ${chrome
        ? html`<nav class="tabs" aria-label="Primary">
            ${items.filter((i) => i.mobile).map((i) => html`<a href=${i.path} aria-current=${this.isActive(i) ? 'page' : 'false'}>${icon(i.icon)}${i.label}</a>`)}
          </nav>
          <vs-command-palette .perms=${me?.permissions ?? {}}></vs-command-palette>`
        : nothing}
      <vs-step-up-dialog></vs-step-up-dialog>
      <span class="sr-only" aria-live="polite">${session.state.status === 'loading' ? t('app.name') : this.announced}</span>
    `;
  }
}
customElements.define('vs-app', VsApp);
