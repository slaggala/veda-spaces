import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { CursorMeta, MfaStatus, SessionInfo } from '../../core/api/types.js';
import { session } from '../../core/auth/session.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatAbsolute, formatRelative, humanize } from '../../core/format/format.js';
import { navigate } from '../../core/router/next.js';
import { toast } from '../../design-system/components.js';
import { pageStyles, shared } from '../../design-system/styles.js';

/**
 * Profile (09 §4.10, §4.13): own profile fields, sign-in email (proposed-email workflow), password, MFA
 * status and recovery codes, own sessions. Deliberately shows NO security-event history (owner Decision 1).
 */
export class VsProfilePage extends SessionElement {
  static override properties = {
    tab: { state: true }, mfa: { state: true }, sessions: { state: true }, problem: { state: true }, codes: { state: true },
    emailDialog: { state: true }, emailError: { state: true }, busy: { state: true },
  };
  declare tab: string;
  declare mfa: MfaStatus | null;
  declare sessions: SessionInfo[] | null;
  declare problem: ApiProblem | null;
  declare codes: string[] | null;
  declare emailDialog: boolean;
  declare emailError: string;
  declare busy: boolean;
  static override styles = [...shared, pageStyles, css`form { display: flex; flex-direction: column; gap: 16px; max-width: 640px; } dl { display: grid; grid-template-columns: 180px 1fr; gap: 8px 16px; margin: 0; } dt { color: var(--vs-ink-muted); }`];

  constructor() {
    super();
    this.tab = 'profile';
    this.mfa = null;
    this.sessions = null;
    this.problem = null;
    this.codes = null;
    this.emailDialog = false;
    this.emailError = '';
    this.busy = false;
  }

  override connectedCallback() {
    super.connectedCallback();
    void this.loadMfa();
  }

  private async loadMfa() {
    try {
      this.mfa = (await api.get<MfaStatus>('/api/v1/auth/mfa')).data;
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  private async loadSessions() {
    try {
      const r = await api.get<SessionInfo[]>('/api/v1/auth/sessions');
      this.sessions = r.data;
      void (r.meta as Partial<CursorMeta>);
    } catch (e) {
      this.problem = e as ApiProblem;
    }
  }

  private async saveProfile(e: Event) {
    e.preventDefault();
    const f = e.target as HTMLFormElement;
    const val = (n: string) => (f.elements.namedItem(n) as HTMLInputElement).value.trim();
    const me = this.me;
    if (!me) return;
    this.busy = true;
    try {
      await api.patch('/api/v1/auth/me', {
        full_name: val('full_name'), display_name: val('display_name') || null, phone: val('phone') || null,
        timezone: val('timezone'), locale: val('locale'),
      }, { ifMatch: me.version });
      await session.reloadMe();
      toast('Profile saved', 'success');
    } catch (err) {
      this.problem = err as ApiProblem;
      if ((err as ApiProblem).code === 'VERSION_CONFLICT') await session.reloadMe();
    } finally {
      this.busy = false;
    }
  }

  private async requestEmailChange(e: Event) {
    e.preventDefault();
    const email = ((e.target as HTMLFormElement).elements.namedItem('new_email') as HTMLInputElement).value.trim();
    if (!email) return void (this.emailError = 'Enter the new address.');
    try {
      await api.put('/api/v1/auth/me/email', { new_email: email });
      this.emailDialog = false;
      await session.reloadMe();
      toast('Verification link sent to the new address', 'success');
    } catch (err) {
      const p = err as ApiProblem;
      this.emailError = p.code === 'DUPLICATE' ? 'That address is already in use.' : p.code === 'SAME_AS_CURRENT' ? 'That is already your sign-in email.' :
        p.code === 'COOLING_OFF' ? 'Email changes are locked during the post-recovery cooling-off.' : p.code === 'VALIDATION_FAILED' || p.code === 'INVALID_EMAIL' ? 'Enter a valid email address.' : p.detail || 'Could not start the change.';
    }
  }

  private async regenerateCodes() {
    try {
      const r = await api.post<{ recovery_codes: string[] }>('/api/v1/auth/mfa/recovery-codes');
      this.codes = r.data.recovery_codes;
      void this.loadMfa();
    } catch (err) {
      this.problem = err as ApiProblem;
    }
  }

  private async removeFactor() {
    if (!confirm('Remove your authenticator? Two-step verification will be turned off.')) return;
    try {
      await api.delete('/api/v1/auth/mfa/factor');
      await session.reloadMe();
      await this.loadMfa();
      toast('Authenticator removed');
    } catch (err) {
      this.problem = err as ApiProblem;
    }
  }

  private async revoke(id: string) {
    try {
      await api.delete(`/api/v1/auth/sessions/${id}`);
      await this.loadSessions();
    } catch (err) {
      this.problem = err as ApiProblem;
    }
  }

  private renderProfile() {
    const me = this.me;
    if (!me) return nothing;
    return html`<form @submit=${this.saveProfile} novalidate class="card">
      <div class="grid-2">
        <label class="field"><span class="label">Full name</span><input name="full_name" .value=${me.full_name} autocomplete="name" required maxlength="150" /></label>
        <label class="field"><span class="label">Display name</span><input name="display_name" .value=${me.display_name ?? ''} maxlength="80" /></label>
        <label class="field"><span class="label">Phone</span><input name="phone" type="tel" autocomplete="tel" .value=${me.phone ?? ''} /></label>
        <label class="field"><span class="label">Timezone</span><input name="timezone" .value=${me.timezone} /></label>
        <label class="field"><span class="label">Locale</span><input name="locale" .value=${me.locale} /></label>
      </div>
      <div class="row"><span class="spacer"></span><button class="btn primary" ?disabled=${this.busy}>Save</button></div>
    </form>`;
  }

  private renderSecurity() {
    const me = this.me;
    if (!me) return nothing;
    const cooling = me.session.cooling_off_until && new Date(me.session.cooling_off_until) > new Date();
    const mfa = this.mfa;
    return html`<div class="stack">
      <section class="card stack" aria-labelledby="email-h">
        <h2 id="email-h" class="eyebrow">Sign-in email</h2>
        <p><strong>${me.email}</strong> <span class="chip success">✓ verified</span></p>
        ${me.email_change
          ? html`<vs-banner kind="info">Change to <strong>${me.email_change.proposed_email}</strong> is pending verification (requested ${formatRelative(me.email_change.requested_on)}).
              Your current address stays active until you verify. To cancel, use the link we sent to your current address.</vs-banner>`
          : nothing}
        <div><button class="btn" ?disabled=${Boolean(cooling)} @click=${() => { this.emailError = ''; this.emailDialog = true; }}>Change email…</button>
          ${cooling ? html`<span class="small muted"> Locked until ${formatAbsolute(me.session.cooling_off_until)}</span>` : nothing}</div>
      </section>
      <section class="card stack" aria-labelledby="pw-h">
        <h2 id="pw-h" class="eyebrow">Password</h2>
        <div><button class="btn" ?disabled=${Boolean(cooling)} @click=${() => navigate('/change-password')}>Change password</button></div>
      </section>
      <section class="card stack" aria-labelledby="mfa-h">
        <h2 id="mfa-h" class="eyebrow">Two-step verification</h2>
        ${!mfa ? html`<vs-skeleton rows="2"></vs-skeleton>` : html`
          ${mfa.factor
            ? html`<p>✓ On — ${mfa.factor.label || 'Authenticator app'}${mfa.factor.confirmed_on ? `, since ${formatAbsolute(mfa.factor.confirmed_on)}` : ''}</p>
                <p class="small muted">${mfa.recovery_codes_remaining} recovery codes remaining.</p>`
            : html`<p>${mfa.required ? html`<span class="chip warning">Required</span> Set up an authenticator to use all of your permissions.` : 'Optional. Add an authenticator for extra protection.'}</p>`}
          ${mfa.required ? html`<p class="small muted">Required by: ${mfa.required_by.map(humanize).join(', ')}</p>` : nothing}
          <div class="row">
            ${mfa.factor
              ? html`<button class="btn" ?disabled=${Boolean(cooling)} @click=${this.regenerateCodes}>Regenerate recovery codes</button>
                  <a class="btn" href="/mfa/enroll?mode=profile">Replace authenticator</a>
                  ${!mfa.required ? html`<button class="btn ghost" ?disabled=${Boolean(cooling)} @click=${this.removeFactor}>Remove</button>` : nothing}`
              : html`<a class="btn primary" href="/mfa/enroll?mode=profile">Set up authenticator</a>`}
          </div>`}
        ${this.codes ? html`<vs-recovery-codes .codes=${this.codes} @continue=${() => (this.codes = null)}></vs-recovery-codes>` : nothing}
      </section>
    </div>`;
  }

  private renderSessions() {
    if (!this.sessions) return html`<vs-skeleton rows="3"></vs-skeleton>`;
    return html`<div class="card stack">
      <ul class="stack">${this.sessions.map(
        (s) => html`<li class="row"><div><strong>${s.device_label || 'Unknown device'}</strong> ${s.current ? html`<span class="chip success">This device</span>` : nothing}
          <div class="small muted">${s.ip_city ?? s.ip_address ?? ''} · started ${formatRelative(s.started_on)} · last seen ${formatRelative(s.last_seen_on)}</div></div>
          <span class="spacer"></span>${s.current ? nothing : html`<button class="btn small" @click=${() => this.revoke(s.id)}>Revoke</button>`}</li>`,
      )}</ul>
      <div><button class="btn" @click=${async () => { await session.logout(true); navigate('/login'); }}>Sign out everywhere</button></div>
    </div>`;
  }

  override render() {
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Account</p><h1 class="display">Profile</h1></div></div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      <vs-tabs .tabs=${[{ id: 'profile', label: 'Profile' }, { id: 'security', label: 'Security' }, { id: 'sessions', label: 'Sessions', hidden: !this.can('session.read') }]}
        .selected=${this.tab} @tab-change=${(e: CustomEvent<string>) => { this.tab = e.detail; if (e.detail === 'sessions') void this.loadSessions(); }}></vs-tabs>
      ${this.tab === 'profile' ? this.renderProfile() : this.tab === 'security' ? this.renderSecurity() : this.renderSessions()}
      <vs-dialog .open=${this.emailDialog} heading="Change sign-in email" @close=${() => (this.emailDialog = false)}>
        <form @submit=${this.requestEmailChange} novalidate>
          <p>We'll send a verification link to the new address. Your current address stays active for sign-in and password recovery until you verify, and we'll alert it too.</p>
          <label class="field"><span class="label">New email</span><input name="new_email" type="email" autocomplete="email" aria-invalid=${this.emailError ? 'true' : 'false'} /></label>
          <p class="danger-text" role="alert">${this.emailError || nothing}</p>
          <div class="row"><span class="spacer"></span><button type="button" class="btn" @click=${() => (this.emailDialog = false)}>Cancel</button><button class="btn primary">Send verification</button></div>
        </form>
      </vs-dialog>
    </div>`;
  }
}
customElements.define('vs-profile-page', VsProfilePage);
