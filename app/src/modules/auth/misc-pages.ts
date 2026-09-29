import { LitElement, html } from 'lit';
import { NAV_ITEMS } from '../../core/authz/permissions.js';
import { t } from '../../core/i18n/strings.js';
import { pageStyles, shared } from '../../design-system/styles.js';

/** Designed "You don't have access" page (09 §3.4). */
export class VsNoAccessPage extends LitElement {
  static override styles = [...shared, pageStyles];
  override render() {
    const perm = new URLSearchParams(window.location.search).get('perm') ?? '';
    return html`<div class="page"><vs-empty-state heading=${t('noaccess.title')}>
      <p>This page needs the <span class="mono">${perm}</span> permission. ${t('noaccess.body')}</p>
      <a class="btn" href=${NAV_ITEMS[0].path}>Go to dashboard</a>
    </vs-empty-state></div>`;
  }
}
customElements.define('vs-no-access-page', VsNoAccessPage);

export class VsNotFoundPage extends LitElement {
  static override styles = [...shared, pageStyles];
  override render() {
    return html`<div class="page"><vs-empty-state heading="Page not found"><a class="btn" href="/">Go home</a></vs-empty-state></div>`;
  }
}
customElements.define('vs-not-found-page', VsNotFoundPage);
