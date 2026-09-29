import { api, ApiClient } from '../api/client.js';
import type { ApiProblem } from '../api/problem.js';
import type { AuthenticatedResult, LoginResult, Me, RecoveryResult } from '../api/types.js';
import type { SessionState } from '../authz/context.js';
import { setUserTimeZone } from '../format/format.js';

type Message = { type: 'login' } | { type: 'logout' } | { type: 'me-changed' };

/**
 * Session controller (02 §2.2 core/auth): silent refresh on boot, memory-only access token, /auth/me as
 * the source of profile + effective permissions, BroadcastChannel sync so login/logout in one tab is
 * reflected in every tab.
 */
export class SessionController extends EventTarget {
  state: SessionState = { status: 'loading', me: null };
  /** Pending MFA challenge from the login step (kept in memory only, never persisted). */
  pendingMfa: { token: string; email: string; recoveryAvailable: boolean } | null = null;
  /** Banner shown on the login screen, e.g. after SESSION_INVALID or a completed reset. */
  flash: { kind: 'info' | 'warning'; text: string } | null = null;
  /** Set from the login response; only change-password, /auth/me and logout are usable (05 §3). */
  mustChangePassword = false;
  private channel: BroadcastChannel | null = null;
  private readyPromise: Promise<void> | null = null;
  private readonly client: ApiClient;

  constructor(client: ApiClient = api) {
    super();
    this.client = client;
    if (typeof BroadcastChannel !== 'undefined') {
      this.channel = new BroadcastChannel('veda-session');
      this.channel.onmessage = (event: MessageEvent<Message>) => void this.onPeerMessage(event.data);
    }
    client.hooks.onAuthzVersion = () => void this.reloadMe();
    client.hooks.onPermissionDenied = () => void this.reloadMe();
    client.hooks.onSessionLost = (problem: ApiProblem) => this.handleSessionLost(problem);
  }

  get me(): Me | null {
    return this.state.me;
  }

  get isAuthenticated(): boolean {
    return this.state.status === 'authenticated';
  }

  get isRecovery(): boolean {
    return this.state.me?.session.type === 'RECOVERY';
  }

  /** Boot: POST /auth/refresh (cookie) then GET /auth/me (02 §2.3). Idempotent. */
  ready(): Promise<void> {
    if (!this.readyPromise) this.readyPromise = this.restore();
    return this.readyPromise;
  }

  private async restore(): Promise<void> {
    const ok = await this.client.refresh();
    if (!ok) {
      this.set({ status: 'anonymous', me: null });
      return;
    }
    await this.reloadMe();
  }

  async reloadMe(): Promise<Me | null> {
    try {
      const { data } = await this.client.get<Me>('/api/v1/auth/me');
      setUserTimeZone(data.timezone);
      if (data.must_change_password !== undefined) this.mustChangePassword = data.must_change_password;
      this.set({ status: 'authenticated', me: data });
      return data;
    } catch (e) {
      const p = e as ApiProblem;
      if (p.status === 401) this.set({ status: 'anonymous', me: null });
      return null;
    }
  }

  async login(email: string, password: string, turnstileToken?: string): Promise<LoginResult> {
    const body: Record<string, string> = { email, password };
    if (turnstileToken) body.turnstile_token = turnstileToken;
    const { data } = await this.client.post<LoginResult>('/api/v1/auth/login', body, { anonymous: true });
    if (data.status === 'AUTHENTICATED') {
      this.mustChangePassword = Boolean(data.must_change_password);
      await this.completeAuthentication(data);
    }
    else if (data.status === 'MFA_REQUIRED')
      this.pendingMfa = { token: data.mfa_token, email, recoveryAvailable: data.recovery_available };
    return data;
  }

  async verifyMfa(code: string): Promise<AuthenticatedResult> {
    if (!this.pendingMfa) throw new Error('No pending MFA challenge');
    const { data } = await this.client.post<AuthenticatedResult>(
      '/api/v1/auth/mfa/verify',
      { mfa_token: this.pendingMfa.token, code },
      { anonymous: true },
    );
    this.pendingMfa = null;
    this.mustChangePassword = Boolean(data.must_change_password);
    await this.completeAuthentication(data);
    return data;
  }

  async recover(password: string, recoveryCode: string): Promise<RecoveryResult> {
    if (!this.pendingMfa) throw new Error('No pending MFA challenge');
    const { data } = await this.client.post<RecoveryResult>(
      '/api/v1/auth/mfa/recovery',
      { mfa_token: this.pendingMfa.token, password, recovery_code: recoveryCode },
      { anonymous: true },
    );
    this.pendingMfa = null;
    this.client.setAccessToken(data.access_token);
    await this.reloadMe();
    return data;
  }

  /** Store the access token of an AUTHENTICATED response and load the profile. */
  async completeAuthentication(result: { access_token: string }): Promise<void> {
    this.client.setAccessToken(result.access_token);
    await this.reloadMe();
    this.broadcast({ type: 'login' });
  }

  async logout(all = false): Promise<void> {
    try {
      await this.client.post(all ? '/api/v1/auth/logout-all' : '/api/v1/auth/logout');
    } catch {
      /* the local session is cleared regardless */
    }
    this.clearLocal();
    this.broadcast({ type: 'logout' });
  }

  clearLocal(): void {
    this.client.setAccessToken(null);
    this.pendingMfa = null;
    this.mustChangePassword = false;
    this.set({ status: 'anonymous', me: null });
  }

  private handleSessionLost(problem: ApiProblem): void {
    if (this.state.status !== 'authenticated') return;
    this.flash = { kind: 'warning', text: problem.code === 'SESSION_INVALID' ? 'Session expired, please sign in again.' : 'Please sign in again.' };
    this.clearLocal();
    this.dispatchEvent(new Event('session-lost'));
  }

  private async onPeerMessage(message: Message): Promise<void> {
    if (message.type === 'logout') {
      this.clearLocal();
      this.dispatchEvent(new Event('session-lost'));
    } else if (message.type === 'login' && !this.isAuthenticated) {
      if (await this.client.refresh()) await this.reloadMe();
    } else if (message.type === 'me-changed' && this.isAuthenticated) {
      await this.reloadMe();
    }
  }

  broadcast(message: Message): void {
    this.channel?.postMessage(message);
  }

  private set(state: SessionState): void {
    this.state = state;
    this.dispatchEvent(new CustomEvent('change', { detail: state }));
  }
}

export const session = new SessionController();
