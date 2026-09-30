import { ApiProblem, networkProblem, parseProblem } from './problem.js';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
export type QueryValue = string | number | boolean | null | undefined | Array<string | number>;

export interface RequestOptions {
  method?: HttpMethod;
  query?: Record<string, QueryValue> | URLSearchParams;
  body?: unknown;
  /** Resource version for optimistic concurrency; sent as If-Match: "<version>" (08 §2.7). */
  ifMatch?: number | string;
  idempotencyKey?: string;
  headers?: Record<string, string>;
  /** Do not attach the bearer token (public endpoints). */
  anonymous?: boolean;
  /** Internal: prevent recursion for refresh / retry. */
  noRetry?: boolean;
  signal?: AbortSignal;
}

export interface ApiResult<T> {
  status: number;
  data: T;
  meta: Record<string, unknown>;
  links: Record<string, string | null>;
  etag: string | null;
  requestId: string | null;
  headers: Headers;
}

export interface ApiClientHooks {
  /** Called when X-Authz-Version differs from the last seen value. */
  onAuthzVersion?: (version: number) => void;
  /** Called on 403 PERMISSION_DENIED (effective permissions may have changed, 02 §2.3). */
  onPermissionDenied?: (problem: ApiProblem) => void;
  /** Called on 403 STEP_UP_REQUIRED. Resolve true once step-up succeeded to retry the request once. */
  onStepUp?: (problem: ApiProblem) => Promise<boolean>;
  /** Called when the session is gone (refresh failed, SESSION_INVALID). */
  onSessionLost?: (problem: ApiProblem) => void;
}

export const CSRF_HEADER = { 'X-Requested-With': 'veda-workspace' } as const;

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

/**
 * The single HTTP client of the SPA (02 §2.1). Holds the access token in memory only, performs a
 * single-flight refresh on 401 TOKEN_EXPIRED and retries the original request once, parses
 * problem+json, and surfaces request ids.
 */
export class ApiClient {
  readonly baseUrl: string;
  hooks: ApiClientHooks = {};
  private accessToken: string | null = null;
  private refreshInFlight: Promise<boolean> | null = null;
  private lastAuthzVersion: number | null = null;
  private readonly fetchImpl: FetchLike;

  constructor(baseUrl = '', fetchImpl?: FetchLike) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.fetchImpl = fetchImpl ?? ((input, init) => fetch(input, init));
  }

  get token(): string | null {
    return this.accessToken;
  }

  setAccessToken(token: string | null): void {
    this.accessToken = token;
    if (!token) this.lastAuthzVersion = null;
  }

  buildUrl(path: string, query?: RequestOptions['query']): string {
    let qs = '';
    if (query instanceof URLSearchParams) {
      qs = query.toString();
    } else if (query) {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(query)) {
        if (value === undefined || value === null || value === '') continue;
        if (Array.isArray(value)) {
          if (value.length) params.set(key, value.join(','));
        } else {
          params.set(key, String(value));
        }
      }
      qs = params.toString();
    }
    return `${this.baseUrl}${path}${qs ? `?${qs}` : ''}`;
  }

  /**
   * Refresh the access token using the HttpOnly refresh cookie (05 §6). Concurrent callers share one
   * in-flight request (single-flight). Resolves true when a new access token was obtained.
   */
  refresh(): Promise<boolean> {
    if (!this.refreshInFlight) {
      this.refreshInFlight = this.doRefresh().finally(() => {
        this.refreshInFlight = null;
      });
    }
    return this.refreshInFlight;
  }

  private async doRefresh(): Promise<boolean> {
    try {
      const response = await this.fetchImpl(this.buildUrl('/api/v1/auth/refresh'), {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', ...CSRF_HEADER },
      });
      if (!response.ok) {
        this.accessToken = null;
        return false;
      }
      const body = (await response.json()) as { data?: { access_token?: string } };
      this.accessToken = body.data?.access_token ?? null;
      return Boolean(this.accessToken);
    } catch {
      return false;
    }
  }

  async request<T = unknown>(path: string, options: RequestOptions = {}): Promise<ApiResult<T>> {
    const method = options.method ?? 'GET';
    const headers: Record<string, string> = { Accept: 'application/json', ...options.headers };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (options.ifMatch !== undefined && options.ifMatch !== null) headers['If-Match'] = `"${options.ifMatch}"`;
    if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey;
    if (!options.anonymous && this.accessToken) headers.Authorization = `Bearer ${this.accessToken}`;
    if (/^\/api\/v1\/auth\/(refresh|logout|logout-all)$/.test(path)) Object.assign(headers, CSRF_HEADER);

    let response: Response;
    try {
      response = await this.fetchImpl(this.buildUrl(path, options.query), {
        method,
        headers,
        credentials: 'include',
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
        signal: options.signal,
      });
    } catch (error) {
      throw networkProblem(error);
    }

    this.observeAuthzVersion(response.headers);

    if (response.ok) {
      const requestId = response.headers.get('X-Request-ID');
      if (response.status === 204) {
        return { status: 204, data: undefined as T, meta: {}, links: {}, etag: null, requestId, headers: response.headers };
      }
      const text = await response.text();
      const body = text ? (JSON.parse(text) as Record<string, unknown>) : {};
      return {
        status: response.status,
        data: body.data as T,
        meta: (body.meta as Record<string, unknown>) ?? {},
        links: (body.links as Record<string, string | null>) ?? {},
        etag: response.headers.get('ETag'),
        requestId,
        headers: response.headers,
      };
    }

    const problem = await parseProblem(response);

    if (problem.status === 401 && problem.code === 'TOKEN_EXPIRED' && !options.noRetry && !options.anonymous) {
      const refreshed = await this.refresh();
      if (refreshed) return this.request<T>(path, { ...options, noRetry: true });
      this.hooks.onSessionLost?.(problem);
      throw problem;
    }
    if (problem.status === 401 && problem.code === 'SESSION_INVALID' && !options.anonymous) {
      this.accessToken = null;
      this.hooks.onSessionLost?.(problem);
    }
    if (problem.status === 403 && problem.code === 'STEP_UP_REQUIRED' && this.hooks.onStepUp && !options.noRetry) {
      const ok = await this.hooks.onStepUp(problem);
      if (ok) return this.request<T>(path, { ...options, noRetry: true });
    }
    if (problem.status === 403 && problem.code === 'PERMISSION_DENIED') this.hooks.onPermissionDenied?.(problem);
    throw problem;
  }

  private observeAuthzVersion(headers: Headers): void {
    const raw = headers.get('X-Authz-Version');
    if (!raw) return;
    const version = Number(raw);
    if (!Number.isFinite(version)) return;
    if (this.lastAuthzVersion !== null && version !== this.lastAuthzVersion) this.hooks.onAuthzVersion?.(version);
    this.lastAuthzVersion = version;
  }

  get<T>(path: string, query?: RequestOptions['query'], options: RequestOptions = {}) {
    return this.request<T>(path, { ...options, method: 'GET', query });
  }
  post<T>(path: string, body?: unknown, options: RequestOptions = {}) {
    return this.request<T>(path, { ...options, method: 'POST', body: body ?? {} });
  }
  put<T>(path: string, body?: unknown, options: RequestOptions = {}) {
    return this.request<T>(path, { ...options, method: 'PUT', body: body ?? {} });
  }
  patch<T>(path: string, body: unknown, options: RequestOptions = {}) {
    return this.request<T>(path, { ...options, method: 'PATCH', body });
  }
  delete<T = void>(path: string, options: RequestOptions = {}) {
    return this.request<T>(path, { ...options, method: 'DELETE' });
  }
}

const base = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_BASE ?? '';

/** The application-wide client instance. */
export const api = new ApiClient(base);

/** Generate a client idempotency key (08 §2.8: 16–64 chars of [A-Za-z0-9_-]). */
export function newIdempotencyKey(): string {
  const bytes = new Uint8Array(18);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}
